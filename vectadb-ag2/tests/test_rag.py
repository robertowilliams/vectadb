"""
Tests for VectaDBRetriever.

Verifies that hybrid query calls hit the correct endpoint, results are
parsed correctly, empty results are handled safely, and event emission
works for tracer integration.
"""

from __future__ import annotations

import pytest
import respx
import httpx

from vectadb_ag2.rag import VectaDBRetriever, VectaDBRetrieverError
from vectadb_ag2.models import AG2EventType


VECTADB_URL = "http://localhost:8080"


def make_retriever(**kwargs) -> VectaDBRetriever:
    defaults = dict(
        vectadb_url=VECTADB_URL,
        entity_type="Document",
        n_results=3,
        fail_silently=False,
    )
    defaults.update(kwargs)
    return VectaDBRetriever(**defaults)


# Sample VectaDB hybrid query response
SAMPLE_RESPONSE = [
    {
        "id": "doc-1",
        "score": 0.92,
        "entity": {
            "id": "doc-1",
            "entity_type": "Document",
            "properties": {
                "content": "RAG combines retrieval with generation.",
                "source": "arxiv",
            },
        },
    },
    {
        "id": "doc-2",
        "score": 0.87,
        "entity": {
            "id": "doc-2",
            "entity_type": "Document",
            "properties": {
                "content": "Vector databases store embeddings.",
                "source": "blog",
            },
        },
    },
]


# ---------------------------------------------------------------------------
# retrieve() — happy path
# ---------------------------------------------------------------------------

@respx.mock
def test_retrieve_calls_hybrid_query_endpoint():
    route = respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    retriever = make_retriever()
    retriever.retrieve("What is RAG?")
    assert route.called


@respx.mock
def test_retrieve_passes_query_text():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    retriever = make_retriever()
    retriever.retrieve("What is RAG?")

    sent_body = respx.calls.last.request.content
    import json
    payload = json.loads(sent_body)
    assert payload["query"] == "What is RAG?"


@respx.mock
def test_retrieve_passes_n_results():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    retriever = make_retriever(n_results=7)
    retriever.retrieve("query")

    import json
    payload = json.loads(respx.calls.last.request.content)
    assert payload["top_k"] == 7


@respx.mock
def test_retrieve_n_results_overrideable_per_call():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    retriever = make_retriever(n_results=3)
    retriever.retrieve("query", n_results=10)

    import json
    payload = json.loads(respx.calls.last.request.content)
    assert payload["top_k"] == 10


@respx.mock
def test_retrieve_returns_correct_structure():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    retriever = make_retriever()
    results = retriever.retrieve("RAG")

    assert len(results) == 2
    doc = results[0]
    assert doc["id"] == "doc-1"
    assert "RAG" in doc["content"]
    assert doc["score"] == pytest.approx(0.92)
    assert doc["entity_type"] == "Document"
    assert "source" in doc["metadata"]


@respx.mock
def test_retrieve_handles_empty_results():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=[])
    )
    retriever = make_retriever()
    results = retriever.retrieve("nothing here")
    assert results == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@respx.mock
def test_retrieve_raises_on_api_error_when_not_silent():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(500, json={"error": "internal", "message": "db down"})
    )
    retriever = make_retriever(fail_silently=False)
    with pytest.raises(VectaDBRetrieverError):
        retriever.retrieve("query")


@respx.mock
def test_retrieve_returns_empty_on_api_error_when_silent():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(500, json={"error": "oops"})
    )
    retriever = make_retriever(fail_silently=True)
    results = retriever.retrieve("query")
    assert results == []


# ---------------------------------------------------------------------------
# retrieve_as_chromadb — AG2 compatibility
# ---------------------------------------------------------------------------

@respx.mock
def test_retrieve_as_chromadb_returns_correct_keys():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    retriever = make_retriever()
    result = retriever.retrieve_as_chromadb(["What is RAG?"], n_results=2)

    assert "ids" in result
    assert "documents" in result
    assert "metadatas" in result


@respx.mock
def test_retrieve_as_chromadb_is_list_of_lists():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    retriever = make_retriever()
    result = retriever.retrieve_as_chromadb(["q1", "q2"], n_results=2)

    assert len(result["ids"]) == 2        # one inner list per query
    assert isinstance(result["ids"][0], list)


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

@respx.mock
def test_retrieve_emits_start_and_end_events():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=SAMPLE_RESPONSE)
    )
    retriever = make_retriever()
    retriever.retrieve("test query")

    events = retriever.drain_queue()
    types = [e.event_type for e in events]
    assert AG2EventType.RETRIEVE_START.value in types
    assert AG2EventType.RETRIEVE_END.value in types


@respx.mock
def test_drain_queue_clears_events():
    respx.post(f"{VECTADB_URL}/api/v1/query/hybrid").mock(
        return_value=httpx.Response(200, json=[])
    )
    retriever = make_retriever(fail_silently=True)
    retriever.retrieve("q")

    first = retriever.drain_queue()
    second = retriever.drain_queue()
    assert len(first) > 0
    assert len(second) == 0


# ---------------------------------------------------------------------------
# _parse_results — edge cases
# ---------------------------------------------------------------------------

def test_parse_results_handles_dict_with_results_key():
    data = {"results": SAMPLE_RESPONSE}
    results = VectaDBRetriever._parse_results(data)
    assert len(results) == 2


def test_parse_results_handles_unknown_shape():
    results = VectaDBRetriever._parse_results(None)
    assert results == []
