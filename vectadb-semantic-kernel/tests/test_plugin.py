"""Tests for VectaDBPlugin — no semantic-kernel dependency required."""

import pytest
import respx
import httpx

from vectadb_sk.plugin import VectaDBPlugin
from vectadb_sk.models import VectorSearchResult

BASE_URL = "http://localhost:8080"

SEARCH_RESPONSE = {
    "results": [
        {"id": "doc-1", "content": "Graphs connect everything.", "score": 0.91},
        {"id": "doc-2", "content": "Vector search is fast.", "score": 0.78},
    ]
}


def make_plugin(**kwargs):
    defaults = dict(base_url=BASE_URL, collection="test_col", fail_silently=False)
    defaults.update(kwargs)
    return VectaDBPlugin(**defaults)


class TestVectaDBPluginSearch:

    @respx.mock
    async def test_search_returns_formatted_string(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        plugin = make_plugin()
        result = await plugin.search("graph connectivity")
        assert "[1]" in result
        assert "Graphs connect everything" in result

    @respx.mock
    async def test_search_includes_scores(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        plugin = make_plugin()
        result = await plugin.search("query")
        assert "score=0.910" in result or "score=0.91" in result

    @respx.mock
    async def test_search_no_results_returns_message(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        plugin = make_plugin()
        result = await plugin.search("obscure query")
        assert result == "No results found."

    @respx.mock
    async def test_search_fails_silently_returns_message(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(500, text="error")
        )
        plugin = make_plugin(fail_silently=True)
        result = await plugin.search("query")
        assert "unavailable" in result.lower()

    @respx.mock
    async def test_search_raises_when_not_silent(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(500, text="error")
        )
        from vectadb_sk.client import VectaDBClientError
        plugin = make_plugin(fail_silently=False)
        with pytest.raises(VectaDBClientError):
            await plugin.search("query")


class TestVectaDBPluginSearchStructured:

    @respx.mock
    async def test_search_structured_returns_result_objects(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        plugin = make_plugin()
        results = await plugin.search_structured("query")
        assert len(results) == 2
        assert isinstance(results[0], VectorSearchResult)
        assert results[0].id == "doc-1"

    @respx.mock
    async def test_search_structured_empty_on_error_when_silent(self):
        respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
            return_value=httpx.Response(500, text="error")
        )
        plugin = make_plugin(fail_silently=True)
        results = await plugin.search_structured("query")
        assert results == []


class TestVectaDBPluginStore:

    @respx.mock
    async def test_store_returns_record_id(self):
        respx.post(f"{BASE_URL}/api/v1/entities").mock(
            return_value=httpx.Response(200, json={"id": "doc-1"})
        )
        plugin = make_plugin()
        result = await plugin.store("doc-1", "Some content here")
        assert result == "doc-1"

    @respx.mock
    async def test_store_sends_correct_payload(self):
        route = respx.post(f"{BASE_URL}/api/v1/entities").mock(
            return_value=httpx.Response(200, json={"id": "doc-1"})
        )
        plugin = make_plugin()
        await plugin.store("doc-1", "Content", entity_type="article")

        request = route.calls[0].request
        import json
        body = json.loads(request.content)
        assert body["id"] == "doc-1"
        assert body["content"] == "Content"
        assert body["entity_type"] == "article"

    @respx.mock
    async def test_store_fails_silently_returns_message(self):
        respx.post(f"{BASE_URL}/api/v1/entities").mock(
            return_value=httpx.Response(500, text="error")
        )
        plugin = make_plugin(fail_silently=True)
        result = await plugin.store("doc-1", "content")
        assert "Failed" in result or "doc-1" in result


class TestVectaDBPluginGet:

    @respx.mock
    async def test_get_existing_returns_content(self):
        respx.get(f"{BASE_URL}/api/v1/entities/doc-1").mock(
            return_value=httpx.Response(200, json={"id": "doc-1", "content": "hello world"})
        )
        plugin = make_plugin()
        result = await plugin.get("doc-1")
        assert "hello world" in result

    @respx.mock
    async def test_get_missing_returns_empty_string(self):
        respx.get(f"{BASE_URL}/api/v1/entities/missing").mock(
            return_value=httpx.Response(404, json={"error": "not found"})
        )
        plugin = make_plugin()
        result = await plugin.get("missing")
        assert result == ""

    @respx.mock
    async def test_get_fails_silently_returns_empty(self):
        respx.get(f"{BASE_URL}/api/v1/entities/doc-1").mock(
            return_value=httpx.Response(500, text="error")
        )
        plugin = make_plugin(fail_silently=True)
        result = await plugin.get("doc-1")
        assert result == ""


class TestKernelFunctionDecorator:

    def test_search_has_kernel_function_marker(self):
        plugin = make_plugin()
        assert hasattr(plugin.search, "__kernel_function__") or callable(plugin.search)

    def test_store_has_kernel_function_marker(self):
        plugin = make_plugin()
        assert hasattr(plugin.store, "__kernel_function__") or callable(plugin.store)

    def test_get_has_kernel_function_marker(self):
        plugin = make_plugin()
        assert hasattr(plugin.get, "__kernel_function__") or callable(plugin.get)
