"""Tests for the VectaDB HTTP client using respx (httpx mock)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from vectadb_crewai.client import SyncVectaDBClient, VectaDBClient, VectaDBClientError
from vectadb_crewai.models import (
    BulkIngestionResponse,
    CrewEventType,
    EventIngestionResponse,
    VectaDBEvent,
)


BASE_URL = "http://localhost:8080"


@pytest.fixture
def event():
    return VectaDBEvent(
        trace_id="t1",
        event_type=CrewEventType.LLM_START.value,
        agent_id="agent-001",
        session_id="sess-001",
        properties={"prompt": "hello world"},
    )


@pytest.mark.asyncio
async def test_health_check_success():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/health").mock(
            return_value=httpx.Response(
                200,
                json={
                    "status": "healthy",
                    "version": "0.1.0",
                    "ontology_loaded": True,
                },
            )
        )
        async with VectaDBClient(BASE_URL) as client:
            health = await client.health_check()
            assert health.status == "healthy"
            assert health.ontology_loaded is True


@pytest.mark.asyncio
async def test_health_check_failure():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/health").mock(
            return_value=httpx.Response(503, json={"error": "unavailable"})
        )
        async with VectaDBClient(BASE_URL) as client:
            with pytest.raises(VectaDBClientError) as exc_info:
                await client.health_check()
            assert "503" in str(exc_info.value)


@pytest.mark.asyncio
async def test_is_healthy_false_on_error():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/health").mock(side_effect=httpx.ConnectError("refused"))
        async with VectaDBClient(BASE_URL) as client:
            result = await client.is_healthy()
            assert result is False


@pytest.mark.asyncio
async def test_ingest_event_success(event):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/api/v1/events").mock(
            return_value=httpx.Response(
                200,
                json={
                    "event_id": "evt-123",
                    "trace_id": "t1",
                    "created_at": "2026-01-01T00:00:00Z",
                },
            )
        )
        async with VectaDBClient(BASE_URL) as client:
            response = await client.ingest_event(event)
            assert response.event_id == "evt-123"
            assert response.trace_id == "t1"


@pytest.mark.asyncio
async def test_ingest_event_propagates_error(event):
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/api/v1/events").mock(
            return_value=httpx.Response(500, json={"error": "internal", "message": "DB error"})
        )
        async with VectaDBClient(BASE_URL) as client:
            with pytest.raises(VectaDBClientError) as exc_info:
                await client.ingest_event(event)
            assert "500" in str(exc_info.value)
            assert "DB error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ingest_events_bulk_empty():
    async with VectaDBClient(BASE_URL) as client:
        result = await client.ingest_events_bulk([])
        assert result.ingested == 0
        assert result.failed == 0


@pytest.mark.asyncio
async def test_ingest_events_bulk_success():
    events = [
        VectaDBEvent(properties={"i": i, "event_type": "llm_start"})
        for i in range(3)
    ]
    with respx.mock(base_url=BASE_URL) as mock:
        mock.post("/api/v1/events/batch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ingested": 3,
                    "failed": 0,
                    "trace_ids": ["trace-1"],
                    "errors": [],
                },
            )
        )
        async with VectaDBClient(BASE_URL) as client:
            result = await client.ingest_events_bulk(events)
            assert result.ingested == 3
            assert result.failed == 0
            assert "trace-1" in result.trace_ids


@pytest.mark.asyncio
async def test_ingest_events_bulk_batching():
    """Ensure large event lists are split into batches."""
    events = [VectaDBEvent(properties={"i": i}) for i in range(5)]
    call_count = 0

    with respx.mock(base_url=BASE_URL) as mock:
        def batch_handler(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={"ingested": 3, "failed": 0, "trace_ids": [], "errors": []},
            )

        mock.post("/api/v1/events/batch").mock(side_effect=batch_handler)

        async with VectaDBClient(BASE_URL, batch_size=3) as client:
            result = await client.ingest_events_bulk(events)

        # 5 events / batch_size=3 → 2 batches
        assert call_count == 2


@pytest.mark.asyncio
async def test_api_key_header(event):
    """Ensure X-API-Key header is included when configured."""
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.get("/health").mock(
            return_value=httpx.Response(
                200,
                json={"status": "healthy", "version": "0.1.0", "ontology_loaded": False},
            )
        )
        async with VectaDBClient(BASE_URL, api_key="my-secret-key") as client:
            await client.health_check()

        request = route.calls[0].request
        assert request.headers.get("x-api-key") == "my-secret-key"


# ---------------------------------------------------------------------------
# SyncVectaDBClient tests
# ---------------------------------------------------------------------------

def _make_mock_async_client(
    healthy: bool = True,
    ingest_response: EventIngestionResponse | None = None,
    bulk_response: BulkIngestionResponse | None = None,
) -> MagicMock:
    """Return a mock VectaDBClient whose coroutine methods return canned values."""
    mock = MagicMock()
    mock.is_healthy = AsyncMock(return_value=healthy)
    mock.ingest_event = AsyncMock(
        return_value=ingest_response
        or EventIngestionResponse(
            event_id="evt-sync-1",
            trace_id="trace-sync-1",
            created_at="2026-01-01T00:00:00Z",
        )
    )
    mock.ingest_events_bulk = AsyncMock(
        return_value=bulk_response
        or BulkIngestionResponse(ingested=3, failed=0, trace_ids=["trace-bulk-1"])
    )
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def sync_client(event):
    """SyncVectaDBClient with the underlying async client mocked out."""
    mock_async = _make_mock_async_client()
    with patch(
        "vectadb_crewai.client.VectaDBClient",
        return_value=mock_async,
    ):
        client = SyncVectaDBClient(base_url=BASE_URL)
    client._async_client = mock_async   # ensure the mock is wired in
    yield client
    client.close()


class TestSyncVectaDBClient:
    def test_is_healthy_returns_true(self, sync_client):
        assert sync_client.is_healthy() is True

    def test_ingest_event_returns_response(self, sync_client, event):
        resp = sync_client.ingest_event(event)
        assert resp is not None
        assert resp.event_id == "evt-sync-1"
        assert resp.trace_id == "trace-sync-1"

    def test_ingest_events_bulk_returns_response(self, sync_client, event):
        resp = sync_client.ingest_events_bulk([event, event, event])
        assert resp is not None
        assert resp.ingested == 3
        assert resp.failed == 0
        assert "trace-bulk-1" in resp.trace_ids

    def test_ingest_events_bulk_empty_shortcircuits(self, sync_client):
        resp = sync_client.ingest_events_bulk([])
        assert resp.ingested == 0
        assert resp.failed == 0
        # The async client should NOT have been called
        sync_client._async_client.ingest_events_bulk.assert_not_called()

    def test_ingest_event_returns_none_on_error(self, sync_client, event):
        sync_client._async_client.ingest_event = AsyncMock(
            side_effect=Exception("network failure")
        )
        result = sync_client.ingest_event(event)
        assert result is None  # fail_silently: does not raise

    def test_is_healthy_false_on_error(self, sync_client):
        sync_client._async_client.is_healthy = AsyncMock(
            side_effect=Exception("connection refused")
        )
        assert sync_client.is_healthy() is False

    def test_close_is_idempotent(self, sync_client):
        sync_client.close()
        sync_client.close()  # should not raise

    def test_background_thread_is_daemon(self, sync_client):
        assert sync_client._thread.daemon is True

    def test_run_raises_after_close(self, sync_client, event):
        sync_client.close()
        result = sync_client.ingest_event(event)
        assert result is None  # closed client swallows the VectaDBClientError
