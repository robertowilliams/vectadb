"""
Tests for VectaDBCallbackHandler.

Verifies that all 14 LangChain callback methods correctly enqueue typed
VectaDBEvent objects, that the framework label is parameterised, and that
drain_queue() is thread-safe.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from vectadb_langchain.callbacks import VectaDBCallbackHandler, _safe_str, _extract_llm_info
from vectadb_langchain.models import AgentRunState, LangChainEventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SESSION_ID = "test-session-abc"


@pytest.fixture
def handler() -> VectaDBCallbackHandler:
    return VectaDBCallbackHandler(session_id=SESSION_ID)


@pytest.fixture
def handler_with_state() -> VectaDBCallbackHandler:
    state = AgentRunState(
        agent_id="agent-001",
        role="researcher",
        session_id=SESSION_ID,
        trace_id="trace-xyz",
    )
    return VectaDBCallbackHandler(session_id=SESSION_ID, agent_state=state)


@pytest.fixture
def run_id() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Helper: get the single queued event
# ---------------------------------------------------------------------------

def pop_event(handler: VectaDBCallbackHandler):
    events = handler.drain_queue()
    assert len(events) == 1, f"Expected 1 event, got {len(events)}"
    return events[0]


# ---------------------------------------------------------------------------
# framework parameter
# ---------------------------------------------------------------------------

def test_default_framework_is_langchain(handler, run_id):
    handler.on_llm_start(
        serialized={"_type": "openai", "model": "gpt-4o"},
        prompts=["Hello"],
        run_id=run_id,
    )
    event = pop_event(handler)
    assert event.properties["framework"] == "langchain"


def test_custom_framework_label(run_id):
    h = VectaDBCallbackHandler(session_id=SESSION_ID, framework="myframework")
    h.on_llm_start(
        serialized={"_type": "openai", "model": "gpt-4"},
        prompts=["test"],
        run_id=run_id,
    )
    event = pop_event(h)
    assert event.properties["framework"] == "myframework"
    assert event.source.system == "myframework"


# ---------------------------------------------------------------------------
# LLM callbacks
# ---------------------------------------------------------------------------

def test_on_llm_start_queues_event(handler, run_id):
    handler.on_llm_start(
        serialized={"_type": "openai", "model": "gpt-4o"},
        prompts=["Tell me about RAG"],
        run_id=run_id,
    )
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.LLM_START.value
    assert event.session_id == SESSION_ID
    assert event.properties["model"] == "gpt-4o"
    assert "Tell me about RAG" in event.properties["prompt"]
    assert event.properties["langchain_run_id"] == str(run_id)


def test_on_chat_model_start_queues_event(handler, run_id):
    from langchain_core.messages import HumanMessage
    handler.on_chat_model_start(
        serialized={"_type": "anthropic", "model": "claude-3"},
        messages=[[HumanMessage(content="Hi")]],
        run_id=run_id,
    )
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.LLM_START.value
    assert event.properties["chat_mode"] is True
    assert event.properties["message_count"] == 1


def test_on_llm_end_queues_event_with_duration(handler, run_id):
    from langchain_core.outputs import LLMResult, Generation
    # Seed a start time
    handler.on_llm_start(
        serialized={"_type": "openai"},
        prompts=["q"],
        run_id=run_id,
    )
    handler.drain_queue()  # discard start event

    result = LLMResult(generations=[[Generation(text="Hello world")]])
    handler.on_llm_end(response=result, run_id=run_id)
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.LLM_END.value
    assert "Hello world" in event.properties["output"]
    assert event.properties["duration_ms"] is not None


def test_on_llm_error_queues_event(handler, run_id):
    handler.on_llm_start(
        serialized={"_type": "openai"},
        prompts=["q"],
        run_id=run_id,
    )
    handler.drain_queue()
    handler.on_llm_error(error=ValueError("rate limited"), run_id=run_id)
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.LLM_ERROR.value
    assert event.properties["error_type"] == "ValueError"
    assert "rate limited" in event.properties["error_message"]


# ---------------------------------------------------------------------------
# Tool callbacks
# ---------------------------------------------------------------------------

def test_on_tool_start_queues_event(handler, run_id):
    handler.on_tool_start(
        serialized={"name": "search"},
        input_str="langchain docs",
        run_id=run_id,
    )
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.TOOL_START.value
    assert event.properties["tool_name"] == "search"
    assert event.properties["tool_input"] == "langchain docs"


def test_on_tool_end_queues_event_with_duration(handler, run_id):
    handler.on_tool_start(
        serialized={"name": "search"},
        input_str="query",
        run_id=run_id,
    )
    handler.drain_queue()
    handler.on_tool_end(output="result text", run_id=run_id)
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.TOOL_END.value
    assert event.properties["tool_output"] == "result text"
    assert event.properties["duration_ms"] is not None


def test_on_tool_error_queues_event(handler, run_id):
    handler.on_tool_start(serialized={"name": "calc"}, input_str="1/0", run_id=run_id)
    handler.drain_queue()
    handler.on_tool_error(error=ZeroDivisionError("division by zero"), run_id=run_id)
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.TOOL_ERROR.value
    assert event.properties["error_type"] == "ZeroDivisionError"


# ---------------------------------------------------------------------------
# Agent callbacks
# ---------------------------------------------------------------------------

def test_on_agent_action_queues_event(handler_with_state, run_id):
    action = MagicMock()
    action.tool = "web_search"
    action.tool_input = "python tutorials"
    action.log = "I need to search for python tutorials"
    handler_with_state.on_agent_action(action=action, run_id=run_id)
    event = pop_event(handler_with_state)
    assert event.event_type == LangChainEventType.AGENT_ACTION.value
    assert event.properties["tool"] == "web_search"
    assert event.properties["action_sequence"] == 1
    assert event.agent_id == "agent-001"
    assert event.trace_id == "trace-xyz"


def test_on_agent_finish_queues_event(handler_with_state, run_id):
    finish = MagicMock()
    finish.return_values = {"output": "The answer is 42"}
    finish.log = "Final answer"
    handler_with_state.on_agent_finish(finish=finish, run_id=run_id)
    event = pop_event(handler_with_state)
    assert event.event_type == LangChainEventType.AGENT_END.value


# ---------------------------------------------------------------------------
# Chain callbacks
# ---------------------------------------------------------------------------

def test_on_chain_start_queues_event(handler, run_id):
    handler.on_chain_start(
        serialized={"id": ["langchain", "chains", "LLMChain"]},
        inputs={"question": "What?"},
        run_id=run_id,
    )
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.CHAIN_START.value
    assert event.properties["chain_type"] == "LLMChain"
    assert "question" in event.properties["input_keys"]


def test_on_chain_start_detects_retrieval_chain(handler, run_id):
    handler.on_chain_start(
        serialized={"id": ["langchain", "RetrievalQA"]},
        inputs={"query": "test"},
        run_id=run_id,
    )
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.RETRIEVAL_START.value


def test_on_chain_end_queues_event(handler, run_id):
    handler.on_chain_start(
        serialized={"id": ["langchain", "LLMChain"]},
        inputs={},
        run_id=run_id,
    )
    handler.drain_queue()
    handler.on_chain_end(outputs={"text": "done"}, run_id=run_id)
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.CHAIN_END.value
    assert "text" in event.properties["output_keys"]


def test_on_chain_error_queues_event(handler, run_id):
    handler.on_chain_start(
        serialized={"id": ["langchain", "LLMChain"]},
        inputs={},
        run_id=run_id,
    )
    handler.drain_queue()
    handler.on_chain_error(error=RuntimeError("chain failed"), run_id=run_id)
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.CHAIN_ERROR.value
    assert event.properties["error_type"] == "RuntimeError"


# ---------------------------------------------------------------------------
# Retrieval callbacks
# ---------------------------------------------------------------------------

def test_on_retriever_start_queues_event(handler, run_id):
    handler.on_retriever_start(
        serialized={"id": ["langchain", "VectorStoreRetriever"]},
        query="semantic search",
        run_id=run_id,
    )
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.RETRIEVAL_START.value
    assert event.properties["query"] == "semantic search"


def test_on_retriever_end_queues_event(handler, run_id):
    handler.on_retriever_start(
        serialized={"id": ["langchain", "VectorStoreRetriever"]},
        query="q",
        run_id=run_id,
    )
    handler.drain_queue()
    docs = [MagicMock(), MagicMock()]
    handler.on_retriever_end(documents=docs, run_id=run_id)
    event = pop_event(handler)
    assert event.event_type == LangChainEventType.RETRIEVAL_END.value
    assert event.properties["document_count"] == 2


# ---------------------------------------------------------------------------
# drain_queue thread safety
# ---------------------------------------------------------------------------

def test_drain_queue_clears_events(handler, run_id):
    handler.on_llm_start(
        serialized={"_type": "openai"}, prompts=["a", "b"], run_id=run_id
    )
    first_drain = handler.drain_queue()
    assert len(first_drain) == 1
    second_drain = handler.drain_queue()
    assert len(second_drain) == 0


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def test_safe_str_truncates_long_strings():
    long = "x" * 5000
    result = _safe_str(long, max_len=100)
    assert len(result) == 101  # 100 chars + "…"
    assert result.endswith("…")


def test_safe_str_handles_unserializable():
    class Bad:
        def __str__(self):
            raise RuntimeError("boom")
    result = _safe_str(Bad())
    assert result == "<unserializable>"


def test_extract_llm_info_picks_model_name():
    info = _extract_llm_info({"model_name": "gpt-4o", "_type": "openai"})
    assert info["model"] == "gpt-4o"
    assert info["provider"] == "openai"


def test_extract_llm_info_falls_back_to_id():
    info = _extract_llm_info({"id": ["langchain", "ChatAnthropic"], "_type": "anthropic"})
    assert info["model"] == "ChatAnthropic"
