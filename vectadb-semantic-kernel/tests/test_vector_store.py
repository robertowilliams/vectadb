"""Tests for VectaDBVectorStore using respx HTTP mocking."""

import pytest
import respx
import httpx

from vectadb_sk.vector_store import VectaDBVectorStore
from vectadb_sk.models import SKEventType


BASE_URL = "http://localhost:8080"

SEARCH_RESPONSE = {
    "results": [
        {"id": "doc-1", "content": "Graph databases store relationships.", "score": 0.92},
        {"id": "doc-2", "content": "VectaDB supports hybrid search.", "score": 0.85},
    ]
}


def make_store(**kwargs):
    defaults = dict(
        base_url=BASE_URL,
        collection="test_col",
        session_id="vs-session",
        agent_id="test-agent",
        fail_silently=False,
    )
    defaults.update(kwargs)
    return VectaDBVectorStore(**defaults)


class TestVectaDBVectorStoreSearch:

    @respx.mock
    async def test_search_returns_results(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        store = make_store()
        results = await store.search("graph database")
        assert len(results) == 2
        assert results[0].id == "doc-1"
        assert results[0].score == pytest.approx(0.92)

    @respx.mock
    async def test_search_emits_vector_search_event(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        store = make_store()
        await store.search("graph database", n_results=2)

        events = store.drain_queue()
        assert len(events) == 1
        assert events[0].event_type == SKEventType.VECTOR_SEARCH

    @respx.mock
    async def test_search_event_contains_query_and_result_count(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        store = make_store()
        await store.search("my query", n_results=10)

        ev = store.drain_queue()[0]
        assert ev.properties["query"] == "my query"
        assert ev.properties["n_results"] == 10
        assert ev.properties["results_returned"] == 2

    @respx.mock
    async def test_search_fails_silently(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        store = make_store(fail_silently=True)
        results = await store.search("query")
        assert results == []

    @respx.mock
    async def test_search_raises_when_not_silent(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(500, text="error")
        )
        store = make_store(fail_silently=False)
        from vectadb_sk.client import VectaDBClientError
        with pytest.raises(VectaDBClientError):
            await store.search("query")


class TestVectaDBVectorStoreUpsert:

    @respx.mock
    async def test_upsert_returns_record_id(self):
        respx.post(f"{BASE_URL}/api/v1/entities").mock(
            return_value=httpx.Response(200, json={"id": "doc-1"})
        )
        store = make_store()
        result = await store.upsert("doc-1", "Some content")
        assert result == "doc-1"

    @respx.mock
    async def test_upsert_emits_memory_write_event(self):
        respx.post(f"{BASE_URL}/api/v1/entities").mock(
            return_value=httpx.Response(200, json={"id": "doc-1"})
        )
        store = make_store()
        await store.upsert("doc-1", "Some content")

        events = store.drain_queue()
        assert len(events) == 1
        assert events[0].event_type == SKEventType.MEMORY_WRITE
        assert events[0].properties["operation"] == "upsert"
        assert events[0].properties["record_id"] == "doc-1"

    @respx.mock
    async def test_upsert_content_length_recorded(self):
        respx.post(f"{BASE_URL}/api/v1/entities").mock(
            return_value=httpx.Response(200, json={"id": "x"})
        )
        store = make_store()
        content = "hello world"
        await store.upsert("x", content)
        ev = store.drain_queue()[0]
        assert ev.properties["content_length"] == len(content)


class TestVectaDBVectorStoreGet:

    @respx.mock
    async def test_get_existing_record_returns_content(self):
        respx.get(f"{BASE_URL}/api/v1/entities/doc-1").mock(
            return_value=httpx.Response(200, json={"id": "doc-1", "content": "hello"})
        )
        store = make_store()
        result = await store.get("doc-1")
        assert result is not None
        assert result["content"] == "hello"

    @respx.mock
    async def test_get_missing_record_returns_none(self):
        respx.get(f"{BASE_URL}/api/v1/entities/missing").mock(
            return_value=httpx.Response(404, json={"error": "not found"})
        )
        store = make_store()
        result = await store.get("missing")
        assert result is None

    @respx.mock
    async def test_get_emits_memory_read_event(self):
        respx.get(f"{BASE_URL}/api/v1/entities/doc-1").mock(
            return_value=httpx.Response(200, json={"id": "doc-1", "content": "hi"})
        )
        store = make_store()
        await store.get("doc-1")

        events = store.drain_queue()
        assert len(events) == 1
        assert events[0].event_type == SKEventType.MEMORY_READ
        assert events[0].properties["operation"] == "get"
        assert events[0].properties["found"] is True


class TestVectaDBVectorStoreDelete:

    @respx.mock
    async def test_delete_returns_true_on_success(self):
        respx.delete(f"{BASE_URL}/api/v1/entities/doc-1").mock(
            return_value=httpx.Response(200, json={"deleted": True})
        )
        store = make_store()
        result = await store.delete("doc-1")
        assert result is True

    @respx.mock
    async def test_delete_emits_memory_write_event(self):
        respx.delete(f"{BASE_URL}/api/v1/entities/doc-1").mock(
            return_value=httpx.Response(200, json={"deleted": True})
        )
        store = make_store()
        await store.delete("doc-1")

        events = store.drain_queue()
        assert len(events) == 1
        assert events[0].event_type == SKEventType.MEMORY_WRITE
        assert events[0].properties["operation"] == "delete"


class TestDrainQueue:

    @respx.mock
    async def test_drain_clears_all_events(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        store = make_store()
        await store.search("q1")
        await store.search("q2")

        first = store.drain_queue()
        assert len(first) == 2

        second = store.drain_queue()
        assert second == []

    @respx.mock
    async def test_no_events_emitted_when_emit_events_false(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        store = make_store(emit_events=False)
        await store.search("query")
        events = store.drain_queue()
        assert events == []
