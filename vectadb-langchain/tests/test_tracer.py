"""
Tests for VectaDBTracer.

Verifies context manager lifecycle, event flushing on exit, session ID
generation, and the create_tracer_from_env() factory.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from vectadb_langchain.tracer import VectaDBTracer, create_tracer_from_env
from vectadb_langchain.callbacks import VectaDBCallbackHandler
from vectadb_langchain.models import LangChainEventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tracer(**kwargs) -> VectaDBTracer:
    """Create a tracer with a mocked SyncVectaDBClient."""
    tracer = VectaDBTracer(
        vectadb_url="http://localhost:8080",
        fail_silently=True,
        **kwargs,
    )
    mock_client = MagicMock()
    mock_client.ingest_events_bulk.return_value = MagicMock(ingested=5, failed=0)
    tracer._client = mock_client
    return tracer


# ---------------------------------------------------------------------------
# Session ID
# ---------------------------------------------------------------------------

def test_session_id_auto_generated():
    tracer = make_tracer()
    assert tracer.session_id.startswith("lc-")
    assert len(tracer.session_id) > 3


def test_explicit_session_id():
    tracer = make_tracer(session_id="my-custom-session")
    assert tracer.session_id == "my-custom-session"


def test_session_ids_are_unique():
    t1 = make_tracer()
    t2 = make_tracer()
    assert t1.session_id != t2.session_id


# ---------------------------------------------------------------------------
# callback_handler property
# ---------------------------------------------------------------------------

def test_callback_handler_is_correct_type():
    tracer = make_tracer()
    assert isinstance(tracer.callback_handler, VectaDBCallbackHandler)


def test_callback_handler_has_matching_session_id():
    tracer = make_tracer()
    assert tracer.callback_handler.session_id == tracer.session_id


def test_callback_handler_framework_propagated():
    tracer = make_tracer(framework="myfw")
    assert tracer.callback_handler.framework == "myfw"


# ---------------------------------------------------------------------------
# Context manager — sync
# ---------------------------------------------------------------------------

def test_context_manager_enters_and_exits():
    tracer = make_tracer()
    with tracer:
        pass  # no-op run
    tracer._client.close.assert_called_once()


def test_context_manager_flushes_handler_events():
    tracer = make_tracer()
    run_id = uuid.uuid4()

    # Enqueue an event, then enter the context manager — __exit__ should flush it
    with tracer:
        tracer.callback_handler.on_llm_start(
            serialized={"_type": "openai", "model": "gpt-4o"},
            prompts=["test"],
            run_id=run_id,
        )

    # ingest_events_bulk should have been called with the queued event
    tracer._client.ingest_events_bulk.assert_called_once()
    call_args = tracer._client.ingest_events_bulk.call_args
    events = call_args[0][0]
    assert len(events) == 1
    assert events[0].event_type == LangChainEventType.LLM_START.value


def test_context_manager_flushes_on_exception():
    tracer = make_tracer()
    run_id = uuid.uuid4()
    tracer.callback_handler.on_llm_start(
        serialized={"_type": "openai"},
        prompts=["q"],
        run_id=run_id,
    )

    with pytest.raises(ValueError):
        with tracer:
            raise ValueError("boom")

    # Events should still have been flushed
    tracer._client.ingest_events_bulk.assert_called_once()


def test_context_manager_calls_client_close():
    tracer = make_tracer()
    with tracer:
        pass
    tracer._client.close.assert_called_once()


# ---------------------------------------------------------------------------
# Context manager — async
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_context_manager_enters_and_exits():
    tracer = make_tracer()
    async with tracer:
        pass
    tracer._client.close.assert_called_once()


@pytest.mark.asyncio
async def test_async_context_manager_flushes_events():
    tracer = make_tracer()
    run_id = uuid.uuid4()
    tracer.callback_handler.on_llm_start(
        serialized={"_type": "openai", "model": "gpt-4"},
        prompts=["async test"],
        run_id=run_id,
    )
    async with tracer:
        pass
    tracer._client.ingest_events_bulk.assert_called_once()


# ---------------------------------------------------------------------------
# Manual flush
# ---------------------------------------------------------------------------

def test_manual_flush_drains_handler():
    tracer = make_tracer()
    run_id = uuid.uuid4()
    tracer.callback_handler.on_tool_start(
        serialized={"name": "calculator"},
        input_str="2+2",
        run_id=run_id,
    )
    tracer._begin()
    tracer.flush()
    tracer._client.ingest_events_bulk.assert_called_once()


# ---------------------------------------------------------------------------
# create_tracer_from_env
# ---------------------------------------------------------------------------

def test_create_tracer_from_env_defaults():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("VECTADB_URL", None)
        os.environ.pop("VECTADB_API_KEY", None)
        os.environ.pop("VECTADB_SESSION_ID", None)
        os.environ.pop("VECTADB_RUN_NAME", None)
        os.environ.pop("VECTADB_FAIL_SILENT", None)

        tracer = create_tracer_from_env()
        assert tracer.vectadb_url == "http://localhost:8080"
        assert tracer.fail_silently is True
        assert tracer.run_name == "langchain_run"
        tracer._client.close()


def test_create_tracer_from_env_reads_env_vars():
    env = {
        "VECTADB_URL": "http://prod.vectadb:9090",
        "VECTADB_API_KEY": "sk-secret",
        "VECTADB_SESSION_ID": "env-session-123",
        "VECTADB_RUN_NAME": "prod_run",
        "VECTADB_FAIL_SILENT": "false",
    }
    with patch.dict(os.environ, env):
        tracer = create_tracer_from_env()
        assert tracer.vectadb_url == "http://prod.vectadb:9090"
        assert tracer.session_id == "env-session-123"
        assert tracer.run_name == "prod_run"
        assert tracer.fail_silently is False
        tracer._client.close()
