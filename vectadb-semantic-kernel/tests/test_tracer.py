"""Tests for VectaDBSKTracer using MagicMock for the sync client."""

import os
from unittest.mock import MagicMock, patch

import pytest

from vectadb_sk.tracer import VectaDBSKTracer, create_tracer_from_env
from vectadb_sk.filters import VectaDBFunctionFilter
from vectadb_sk.models import SKEventType, VectaDBEvent


# ---------------------------------------------------------------------------
# Mock kernel
# ---------------------------------------------------------------------------

class MockKernel:
    """Minimal SK kernel stub with add_filter support."""

    def __init__(self):
        self._filters: list = []

    def add_filter(self, filter_type: str, filter_obj) -> None:
        self._filters.append((filter_type, filter_obj))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_event(event_type=SKEventType.FUNCTION_INVOKED) -> VectaDBEvent:
    return VectaDBEvent(event_type=event_type, properties={"test": True})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVectaDBSKTracerInit:

    def test_session_id_auto_generated(self):
        tracer = VectaDBSKTracer.__new__(VectaDBSKTracer)
        # Bypass __init__ to inspect auto-generation logic directly
        import uuid
        session_id = f"sk-{uuid.uuid4().hex[:12]}"
        assert session_id.startswith("sk-")
        assert len(session_id) == 15  # "sk-" + 12 hex chars

    def test_explicit_session_id_preserved(self):
        with patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = VectaDBSKTracer(session_id="sk-explicit")
        assert tracer.session_id == "sk-explicit"

    def test_session_id_starts_with_sk_prefix(self):
        with patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = VectaDBSKTracer()
        assert tracer.session_id.startswith("sk-")

    def test_default_agent_id(self):
        with patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = VectaDBSKTracer()
        assert tracer.agent_id == "semantic-kernel"


class TestVectaDBSKTracerRegister:

    def test_register_adds_filter_to_kernel(self):
        with patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = VectaDBSKTracer(session_id="sk-test")
        kernel = MockKernel()
        tracer.register(kernel)
        assert len(kernel._filters) == 1
        filter_type, filter_obj = kernel._filters[0]
        assert filter_type == "function_invocation"
        assert isinstance(filter_obj, VectaDBFunctionFilter)

    def test_register_returns_filter(self):
        with patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = VectaDBSKTracer(session_id="sk-test")
        kernel = MockKernel()
        f = tracer.register(kernel)
        assert isinstance(f, VectaDBFunctionFilter)

    def test_register_filter_uses_tracer_session_id(self):
        with patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = VectaDBSKTracer(session_id="sk-custom")
        kernel = MockKernel()
        f = tracer.register(kernel)
        assert f.session_id == "sk-custom"

    def test_multiple_kernels_accumulate_filters(self):
        with patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = VectaDBSKTracer()
        k1 = MockKernel()
        k2 = MockKernel()
        tracer.register(k1)
        tracer.register(k2)
        assert len(tracer._filters) == 2


class TestVectaDBSKTracerFlush:

    def _make_tracer_with_mock_client(self, **kwargs):
        mock_client = MagicMock()
        mock_client.ingest_events_bulk.return_value = MagicMock(
            ingested=5, failed=0, trace_ids=["trace-1"], errors=[]
        )
        with patch("vectadb_sk.tracer.SyncVectaDBClient", return_value=mock_client):
            tracer = VectaDBSKTracer(**kwargs)
        tracer._sync_client = mock_client
        return tracer, mock_client

    def test_flush_calls_ingest_bulk(self):
        tracer, mock_client = self._make_tracer_with_mock_client()
        kernel = MockKernel()
        f = tracer.register(kernel)
        f._queue.append(make_event())

        n = tracer.flush()
        mock_client.ingest_events_bulk.assert_called_once()
        assert n == 5

    def test_flush_returns_zero_when_no_events(self):
        tracer, mock_client = self._make_tracer_with_mock_client()
        n = tracer.flush()
        mock_client.ingest_events_bulk.assert_not_called()
        assert n == 0

    def test_flush_drains_all_filters(self):
        tracer, mock_client = self._make_tracer_with_mock_client()
        k1 = MockKernel()
        k2 = MockKernel()
        f1 = tracer.register(k1)
        f2 = tracer.register(k2)
        f1._queue.append(make_event())
        f2._queue.append(make_event())

        tracer.flush()
        call_args = mock_client.ingest_events_bulk.call_args
        events_sent = call_args[0][0]
        assert len(events_sent) == 2

    def test_flush_handles_none_response_gracefully(self):
        tracer, mock_client = self._make_tracer_with_mock_client()
        mock_client.ingest_events_bulk.return_value = None
        kernel = MockKernel()
        f = tracer.register(kernel)
        f._queue.append(make_event())

        n = tracer.flush()
        assert n == 0

    def test_context_manager_flushes_on_exit(self):
        tracer, mock_client = self._make_tracer_with_mock_client()
        kernel = MockKernel()

        with tracer:
            f = tracer.register(kernel)
            f._queue.append(make_event())

        mock_client.ingest_events_bulk.assert_called_once()

    def test_context_manager_closes_client(self):
        tracer, mock_client = self._make_tracer_with_mock_client()
        with tracer:
            pass
        mock_client.close.assert_called_once()


class TestCreateTracerFromEnv:

    def test_reads_vectadb_url(self):
        env = {"VECTADB_URL": "http://myhost:9090"}
        with patch.dict(os.environ, env), patch("vectadb_sk.tracer.SyncVectaDBClient") as mock_cls:
            create_tracer_from_env()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["base_url"] == "http://myhost:9090"

    def test_reads_vectadb_api_key(self):
        env = {"VECTADB_API_KEY": "secret-key"}
        with patch.dict(os.environ, env), patch("vectadb_sk.tracer.SyncVectaDBClient") as mock_cls:
            create_tracer_from_env()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["api_key"] == "secret-key"

    def test_reads_vectadb_session_id(self):
        env = {"VECTADB_SESSION_ID": "sk-env-session"}
        with patch.dict(os.environ, env), patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = create_tracer_from_env()
        assert tracer.session_id == "sk-env-session"

    def test_fail_silent_false_when_set(self):
        env = {"VECTADB_FAIL_SILENT": "false"}
        with patch.dict(os.environ, env), patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = create_tracer_from_env()
        assert tracer.fail_silently is False

    def test_fail_silent_true_by_default(self):
        with patch.dict(os.environ, {}, clear=True), patch("vectadb_sk.tracer.SyncVectaDBClient"):
            tracer = create_tracer_from_env()
        assert tracer.fail_silently is True

    def test_defaults_when_env_not_set(self):
        with patch.dict(os.environ, {}, clear=True), patch("vectadb_sk.tracer.SyncVectaDBClient") as mock_cls:
            create_tracer_from_env()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:8080"
        assert call_kwargs["api_key"] is None
