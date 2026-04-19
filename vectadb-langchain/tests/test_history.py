"""
Tests for VectaDBChatMessageHistory.

Uses respx to mock the VectaDB HTTP API.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from vectadb_langchain.history import VectaDBChatMessageHistory

BASE_URL = "http://localhost:8080"
SESSION_ID = "conv-session-xyz"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def history() -> VectaDBChatMessageHistory:
    return VectaDBChatMessageHistory(
        session_id=SESSION_ID,
        vectadb_url=BASE_URL,
    )


def make_entity(role: str, content: str, index: int = 0) -> dict:
    return {
        "id": f"entity-{index}",
        "properties": {
            "role": role,
            "content": content,
            "session_id": SESSION_ID,
            "message_index": index,
            "message_type": {"human": "HumanMessage", "ai": "AIMessage", "system": "SystemMessage"}.get(role, "HumanMessage"),
        },
    }


# ---------------------------------------------------------------------------
# messages property
# ---------------------------------------------------------------------------

@respx.mock
def test_messages_returns_empty_on_new_session(history):
    respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(200, json={"entities": []})
    )
    assert history.messages == []


@respx.mock
def test_messages_returns_ordered_messages(history):
    respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(200, json={
            "entities": [
                make_entity("ai", "I am an AI assistant.", index=1),
                make_entity("human", "Hello!", index=0),  # returned out of order
            ]
        })
    )
    msgs = history.messages
    assert len(msgs) == 2
    # Should be ordered by message_index
    assert isinstance(msgs[0], HumanMessage)
    assert msgs[0].content == "Hello!"
    assert isinstance(msgs[1], AIMessage)
    assert msgs[1].content == "I am an AI assistant."


@respx.mock
def test_messages_handles_fetch_error_gracefully(history):
    respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(500, json={"error": "db error"})
    )
    # Should return [] rather than raise
    assert history.messages == []


# ---------------------------------------------------------------------------
# add_message / add_user_message / add_ai_message
# ---------------------------------------------------------------------------

@respx.mock
def test_add_user_message_posts_entity(history):
    search_mock = respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(200, json={"entities": []})
    )
    entity_mock = respx.post(f"{BASE_URL}/api/v1/entities").mock(
        return_value=httpx.Response(200, json={"id": "msg-1"})
    )
    history.add_user_message("What is RAG?")
    assert entity_mock.called
    import json
    body = json.loads(entity_mock.calls[0].request.content)
    assert body["properties"]["role"] == "human"
    assert body["properties"]["content"] == "What is RAG?"
    assert body["properties"]["session_id"] == SESSION_ID


@respx.mock
def test_add_ai_message_posts_entity(history):
    respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(200, json={"entities": []})
    )
    entity_mock = respx.post(f"{BASE_URL}/api/v1/entities").mock(
        return_value=httpx.Response(200, json={"id": "msg-2"})
    )
    history.add_ai_message("RAG stands for Retrieval-Augmented Generation.")
    body = __import__("json").loads(entity_mock.calls[0].request.content)
    assert body["properties"]["role"] == "ai"


@respx.mock
def test_add_message_system_message(history):
    respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(200, json={"entities": []})
    )
    entity_mock = respx.post(f"{BASE_URL}/api/v1/entities").mock(
        return_value=httpx.Response(200, json={"id": "msg-3"})
    )
    history.add_message(SystemMessage(content="You are a helpful assistant."))
    body = __import__("json").loads(entity_mock.calls[0].request.content)
    assert body["properties"]["role"] == "system"


@respx.mock
def test_message_index_increments(history):
    respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(200, json={"entities": []})
    )
    import json
    indices = []

    def capture(request):
        body = json.loads(request.content)
        indices.append(body["properties"]["message_index"])
        return httpx.Response(200, json={"id": "x"})

    respx.post(f"{BASE_URL}/api/v1/entities").mock(side_effect=capture)
    history.add_user_message("msg 1")
    history.add_ai_message("msg 2")
    history.add_user_message("msg 3")
    assert indices == [0, 1, 2]


@respx.mock
def test_add_message_handles_api_error_gracefully(history):
    respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(200, json={"entities": []})
    )
    respx.post(f"{BASE_URL}/api/v1/entities").mock(
        return_value=httpx.Response(500, json={"error": "write failed"})
    )
    # Should not raise
    history.add_user_message("this will fail silently")


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

@respx.mock
def test_clear_deletes_all_session_messages(history):
    respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(200, json={
            "entities": [
                make_entity("human", "Hi", 0),
                make_entity("ai", "Hello", 1),
            ]
        })
    )
    delete_mock = respx.delete(url__regex=r".*/api/v1/entities/entity-\d+").mock(
        return_value=httpx.Response(200, json={})
    )
    history.clear()
    assert delete_mock.call_count == 2


@respx.mock
def test_clear_resets_index(history):
    respx.post(f"{BASE_URL}/api/v1/entities/search").mock(
        return_value=httpx.Response(200, json={"entities": []})
    )
    history._index = 5
    history.clear()
    assert history._index == 0


# ---------------------------------------------------------------------------
# _to_base_message type mapping
# ---------------------------------------------------------------------------

def test_to_base_message_human():
    entity = {"properties": {"role": "human", "content": "Hello"}}
    msg = VectaDBChatMessageHistory._to_base_message(entity)
    assert isinstance(msg, HumanMessage)
    assert msg.content == "Hello"


def test_to_base_message_ai():
    entity = {"properties": {"role": "ai", "content": "Hi there"}}
    msg = VectaDBChatMessageHistory._to_base_message(entity)
    assert isinstance(msg, AIMessage)


def test_to_base_message_system():
    entity = {"properties": {"role": "system", "content": "You are helpful"}}
    msg = VectaDBChatMessageHistory._to_base_message(entity)
    assert isinstance(msg, SystemMessage)


def test_to_base_message_unknown_role_falls_back_to_human():
    entity = {"properties": {"role": "mystery", "content": "?"}}
    msg = VectaDBChatMessageHistory._to_base_message(entity)
    assert isinstance(msg, HumanMessage)
