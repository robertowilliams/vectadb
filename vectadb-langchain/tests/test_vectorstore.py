"""
Tests for VectaDBVectorStore.

Uses respx to mock the VectaDB HTTP API so no live server is needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from langchain_core.documents import Document

from vectadb_langchain.vectorstore import VectaDBVectorStore

BASE_URL = "http://localhost:8080"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store() -> VectaDBVectorStore:
    return VectaDBVectorStore(
        vectadb_url=BASE_URL,
        collection="test_docs",
    )


# ---------------------------------------------------------------------------
# add_texts
# ---------------------------------------------------------------------------

@respx.mock
def test_add_texts_returns_ids(store):
    respx.post(f"{BASE_URL}/api/v1/entities").mock(
        return_value=httpx.Response(200, json={"id": "entity-abc"})
    )
    ids = store.add_texts(["hello world"])
    assert ids == ["entity-abc"]


@respx.mock
def test_add_texts_multiple_documents(store):
    call_count = 0
    def entity_side_effect(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"id": f"entity-{call_count}"})

    respx.post(f"{BASE_URL}/api/v1/entities").mock(side_effect=entity_side_effect)
    ids = store.add_texts(["doc one", "doc two", "doc three"])
    assert len(ids) == 3
    assert call_count == 3


@respx.mock
def test_add_texts_uses_provided_ids(store):
    respx.post(f"{BASE_URL}/api/v1/entities").mock(
        return_value=httpx.Response(200, json={"id": "my-custom-id"})
    )
    ids = store.add_texts(["text"], ids=["my-custom-id"])
    assert ids == ["my-custom-id"]


@respx.mock
def test_add_texts_includes_metadata(store):
    captured_body = {}

    def capture(request):
        import json
        captured_body.update(json.loads(request.content))
        return httpx.Response(200, json={"id": "e1"})

    respx.post(f"{BASE_URL}/api/v1/entities").mock(side_effect=capture)
    store.add_texts(["text"], metadatas=[{"author": "Alice", "year": 2024}])
    assert captured_body["properties"]["author"] == "Alice"
    assert captured_body["properties"]["year"] == 2024


@respx.mock
def test_add_texts_empty_list_returns_empty(store):
    ids = store.add_texts([])
    assert ids == []


# ---------------------------------------------------------------------------
# similarity_search
# ---------------------------------------------------------------------------

@respx.mock
def test_similarity_search_returns_documents(store):
    respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json={
            "results": [
                {
                    "id": "doc-1",
                    "score": 0.92,
                    "properties": {"content": "VectaDB is a graph database", "collection": "test"},
                },
                {
                    "id": "doc-2",
                    "score": 0.85,
                    "properties": {"content": "LangChain is a framework", "collection": "test"},
                },
            ]
        })
    )
    docs = store.similarity_search("vector database", k=2)
    assert len(docs) == 2
    assert isinstance(docs[0], Document)
    assert "VectaDB" in docs[0].page_content
    assert docs[0].metadata["vectadb_id"] == "doc-1"


@respx.mock
def test_similarity_search_empty_results(store):
    respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    docs = store.similarity_search("unknown query")
    assert docs == []


@respx.mock
def test_similarity_search_handles_api_error_gracefully(store):
    respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(500, json={"error": "internal error"})
    )
    # Should not raise — returns empty list
    docs = store.similarity_search("anything")
    assert docs == []


# ---------------------------------------------------------------------------
# similarity_search_with_score
# ---------------------------------------------------------------------------

@respx.mock
def test_similarity_search_with_score_returns_tuples(store):
    respx.post(f"{BASE_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json={
            "results": [
                {
                    "id": "doc-1",
                    "score": 0.95,
                    "properties": {"content": "Highly relevant result"},
                }
            ]
        })
    )
    results = store.similarity_search_with_score("query", k=1)
    assert len(results) == 1
    doc, score = results[0]
    assert isinstance(doc, Document)
    assert score == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

@respx.mock
def test_delete_returns_true_on_success(store):
    respx.delete(f"{BASE_URL}/api/v1/entities/doc-1").mock(
        return_value=httpx.Response(200, json={"deleted": True})
    )
    result = store.delete(ids=["doc-1"])
    assert result is True


@respx.mock
def test_delete_empty_ids_returns_true(store):
    result = store.delete(ids=[])
    assert result is True


@respx.mock
def test_delete_returns_false_on_failure(store):
    respx.delete(f"{BASE_URL}/api/v1/entities/bad-id").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    result = store.delete(ids=["bad-id"])
    assert result is False


# ---------------------------------------------------------------------------
# from_texts classmethod
# ---------------------------------------------------------------------------

@respx.mock
def test_from_texts_creates_store_and_adds_texts():
    respx.post(f"{BASE_URL}/api/v1/entities").mock(
        return_value=httpx.Response(200, json={"id": "e1"})
    )
    mock_embedding = MagicMock()
    store = VectaDBVectorStore.from_texts(
        texts=["sample document"],
        embedding=mock_embedding,
        vectadb_url=BASE_URL,
        collection="my_collection",
    )
    assert isinstance(store, VectaDBVectorStore)
    assert store.collection == "my_collection"


# ---------------------------------------------------------------------------
# to_document helper
# ---------------------------------------------------------------------------

def test_to_document_strips_internal_keys():
    result = {
        "id": "e1",
        "score": 0.8,
        "properties": {
            "content": "hello",
            "collection": "docs",
            "doc_id": "abc",
            "author": "Bob",
        },
    }
    doc = VectaDBVectorStore._to_document(result)
    assert doc.page_content == "hello"
    assert "collection" not in doc.metadata
    assert "doc_id" not in doc.metadata
    assert doc.metadata["author"] == "Bob"
    assert doc.metadata["vectadb_id"] == "e1"
    assert doc.metadata["score"] == pytest.approx(0.8)
