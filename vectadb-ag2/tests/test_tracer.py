"""
Tests for VectaDBAG2Tracer.

Verifies session ID generation, agent attachment, event flushing on context
manager exit, async context manager, flush on exception, and
create_tracer_from_env() factory.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from vectadb_ag2.tracer import VectaDBAG2Tracer, create_tracer_from_env
from vectadb_ag2.models import AG2EventType


# ---------------------------------------------------------------------------
# Minimal mock agent
# ---------------------------------------------------------------------------

class MockAgent:
    def __init__(self, name: str = "agent"):
        self.name = name
        self._hooks: dict[str, list] = {}
        self.function_map: dict = {}

    def register_hook(self, hookable_method: str, hook) -> None:
        self._hooks.setdefault(hookable_method, []).append(hook)

    def trigger_message_hooks(self, messages):
        for hook in self._hooks.get("process_all_messages_before_reply", []):
            messages = hook(messages)
        return messages


def make_tracer(**kwargs) -> VectaDBAG2Tracer:
    tracer = VectaDBAG2Tracer(
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
    assert tracer.session_id.startswith("ag2-")
    assert len(tracer.session_id) > 4


def test_explicit_session_id():
    tracer = make_tracer(session_id="my-ag2-session")
    assert tracer.session_id == "my-ag2-session"


def test_session_ids_are_unique():
    t1 = make_tracer()
    t2 = make_tracer()
    assert t1.session_id != t2.session_id


# ---------------------------------------------------------------------------
# attach()
# ---------------------------------------------------------------------------

def test_attach_returns_hook():
    tracer = make_tracer()
    agent = MockAgent()
    hook = tracer.attach(agent)
    assert hook is not None


def test_attach_registers_message_hook_on_agent():
    tracer = make_tracer()
    agent = MockAgent()
    tracer.attach(agent)
    assert "process_all_messages_before_reply" in agent._hooks


def test_attach_picks_up_agent_name():
    tracer = make_tracer()
    agent = MockAgent(name="executor")
    hook = tracer.attach(agent)
    assert hook.agent_name == "executor"


def test_attach_shares_session_id_with_hook():
    tracer = make_tracer(session_id="shared-session")
    agent = MockAgent()
    hook = tracer.attach(agent)
    assert hook.session_id == "shared-session"


# ---------------------------------------------------------------------------
# Context manager — sync
# ---------------------------------------------------------------------------

def test_context_manager_enters_and_exits():
    tracer = make_tracer()
    with tracer:
        pass
    tracer._client.close.assert_called_once()


def test_context_manager_flushes_events_on_exit():
    tracer = make_tracer()
    agent = MockAgent()
    tracer.attach(agent)

    with tracer:
        agent.trigger_message_hooks([{"role": "user", "content": "hello"}])

    tracer._client.ingest_events_bulk.assert_called_once()


def test_context_manager_flushes_on_exception():
    tracer = make_tracer()
    agent = MockAgent()
    tracer.attach(agent)
    agent.trigger_message_hooks([{"role": "user", "content": "msg"}])

    with pytest.raises(RuntimeError):
        with tracer:
            raise RuntimeError("crash")

    tracer._client.ingest_events_bulk.assert_called_once()


def test_context_manager_closes_client_on_exception():
    tracer = make_tracer()
    with pytest.raises(ValueError):
        with tracer:
            raise ValueError("boom")
    tracer._client.close.assert_called_once()


# ---------------------------------------------------------------------------
# Context manager — async
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_context_manager_closes_client():
    tracer = make_tracer()
    async with tracer:
        pass
    tracer._client.close.assert_called_once()


@pytest.mark.asyncio
async def test_async_context_manager_flushes_events():
    tracer = make_tracer()
    agent = MockAgent()
    tracer.attach(agent)
    agent.trigger_message_hooks([{"role": "user", "content": "async hello"}])

    async with tracer:
        pass

    tracer._client.ingest_events_bulk.assert_called_once()


# ---------------------------------------------------------------------------
# flush() — manual
# ---------------------------------------------------------------------------

def test_manual_flush_drains_all_hooks():
    tracer = make_tracer()
    a1, a2 = MockAgent(name="a1"), MockAgent(name="a2")
    tracer.attach(a1)
    tracer.attach(a2)

    a1.trigger_message_hooks([{"role": "user", "content": "from a1"}])
    a2.trigger_message_hooks([{"role": "user", "content": "from a2"}])

    tracer.__enter__()
    tracer.flush()

    tracer._client.ingest_events_bulk.assert_called_once()
    events_sent = tracer._client.ingest_events_bulk.call_args[0][0]
    assert len(events_sent) == 2


# ---------------------------------------------------------------------------
# Pre-attach via constructor
# ---------------------------------------------------------------------------

def test_agents_provided_at_construction_are_attached():
    a1, a2 = MockAgent(name="a1"), MockAgent(name="a2")
    tracer = make_tracer(agents=[a1, a2])
    assert len(tracer._hooks) == 2


# ---------------------------------------------------------------------------
# create_tracer_from_env
# ---------------------------------------------------------------------------

def test_create_tracer_from_env_defaults():
    for key in ("VECTADB_URL", "VECTADB_API_KEY", "VECTADB_SESSION_ID", "VECTADB_FAIL_SILENT"):
        os.environ.pop(key, None)

    with patch.dict(os.environ, {}, clear=False):
        tracer = create_tracer_from_env()
        assert tracer.vectadb_url == "http://localhost:8080"
        assert tracer.fail_silently is True
        tracer._client.close()


def test_create_tracer_from_env_reads_env_vars():
    env = {
        "VECTADB_URL": "http://prod.vectadb:9090",
        "VECTADB_API_KEY": "sk-secret",
        "VECTADB_SESSION_ID": "env-session-456",
        "VECTADB_FAIL_SILENT": "false",
    }
    with patch.dict(os.environ, env):
        tracer = create_tracer_from_env()
        assert tracer.vectadb_url == "http://prod.vectadb:9090"
        assert tracer.session_id == "env-session-456"
        assert tracer.fail_silently is False
        tracer._client.close()
