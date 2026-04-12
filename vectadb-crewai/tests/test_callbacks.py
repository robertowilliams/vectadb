"""Tests for VectaDBCallbackHandler."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from vectadb_crewai.callbacks import VectaDBCallbackHandler
from vectadb_crewai.models import AgentRunState, CrewEventType


@pytest.fixture
def agent_state():
    return AgentRunState(
        agent_id="agent-test-001",
        role="tester",
        session_id="sess-test",
        trace_id="trace-test",
    )


@pytest.fixture
def handler(agent_state):
    return VectaDBCallbackHandler(
        session_id="sess-test",
        agent_state=agent_state,
    )


def _run_id() -> uuid.UUID:
    return uuid.uuid4()


class TestLLMCallbacks:
    def test_on_llm_start_enqueues_event(self, handler):
        rid = _run_id()
        handler.on_llm_start(
            serialized={"id": ["openai", "ChatOpenAI"], "model_name": "gpt-4"},
            prompts=["What is AI?"],
            run_id=rid,
        )
        events = handler.drain_queue()
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == CrewEventType.LLM_START.value
        assert ev.properties["model"] == "gpt-4"
        assert "What is AI?" in ev.properties["prompt"]

    def test_on_llm_start_increments_count(self, handler, agent_state):
        handler.on_llm_start(
            serialized={"id": ["ChatOpenAI"]},
            prompts=["test"],
            run_id=_run_id(),
        )
        assert agent_state.llm_call_count == 1

    def test_on_llm_end_captures_output(self, handler):
        from langchain_core.outputs import LLMResult, Generation

        rid = _run_id()
        handler.on_llm_start(
            serialized={"id": ["ChatOpenAI"]},
            prompts=["test"],
            run_id=rid,
        )
        handler.drain_queue()  # clear start event

        result = LLMResult(generations=[[Generation(text="Paris is the capital.")]])
        handler.on_llm_end(result, run_id=rid)

        events = handler.drain_queue()
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == CrewEventType.LLM_END.value
        assert "Paris" in ev.properties["output"]
        assert ev.properties["duration_ms"] is not None

    def test_on_llm_error(self, handler):
        rid = _run_id()
        handler.on_llm_start(
            serialized={"id": ["ChatOpenAI"]},
            prompts=["test"],
            run_id=rid,
        )
        handler.drain_queue()

        handler.on_llm_error(ValueError("rate limit exceeded"), run_id=rid)
        events = handler.drain_queue()
        assert events[0].event_type == CrewEventType.LLM_ERROR.value
        assert "rate limit" in events[0].properties["error_message"]


class TestToolCallbacks:
    def test_on_tool_start_enqueues(self, handler, agent_state):
        rid = _run_id()
        handler.on_tool_start(
            serialized={"name": "web_search"},
            input_str="latest AI news",
            run_id=rid,
        )
        events = handler.drain_queue()
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == CrewEventType.TOOL_START.value
        assert ev.properties["tool_name"] == "web_search"
        assert ev.properties["tool_input"] == "latest AI news"
        assert agent_state.tool_call_count == 1

    def test_on_tool_end(self, handler):
        rid = _run_id()
        handler.on_tool_start(
            serialized={"name": "calculator"},
            input_str="2+2",
            run_id=rid,
        )
        handler.drain_queue()

        handler.on_tool_end("4", run_id=rid, name="calculator")
        events = handler.drain_queue()
        assert events[0].event_type == CrewEventType.TOOL_END.value
        assert events[0].properties["tool_output"] == "4"
        assert events[0].properties["duration_ms"] is not None

    def test_on_tool_error(self, handler):
        rid = _run_id()
        handler.on_tool_start(
            serialized={"name": "file_reader"},
            input_str="/etc/secret",
            run_id=rid,
        )
        handler.drain_queue()

        handler.on_tool_error(
            PermissionError("access denied"), run_id=rid, name="file_reader"
        )
        events = handler.drain_queue()
        assert events[0].event_type == CrewEventType.TOOL_ERROR.value
        assert events[0].properties["error_type"] == "PermissionError"


class TestAgentCallbacks:
    def test_on_agent_action(self, handler, agent_state):
        action = MagicMock()
        action.tool = "web_search"
        action.tool_input = "AI trends 2026"
        action.log = "I need to search for AI trends."

        handler.on_agent_action(action, run_id=_run_id())
        events = handler.drain_queue()
        assert events[0].event_type == CrewEventType.AGENT_ACTION.value
        assert events[0].properties["tool"] == "web_search"
        assert agent_state.action_sequence == 1

    def test_on_agent_finish(self, handler, agent_state):
        finish = MagicMock()
        finish.return_values = {"output": "Final answer: 42"}
        finish.log = "I now have the final answer."

        handler.on_agent_finish(finish, run_id=_run_id())
        events = handler.drain_queue()
        assert events[0].event_type == CrewEventType.AGENT_END.value
        assert "42" in events[0].properties["output"]


class TestChainCallbacks:
    def test_on_chain_start_end(self, handler):
        rid = _run_id()
        handler.on_chain_start(
            serialized={"id": ["StuffDocumentsChain"]},
            inputs={"query": "test"},
            run_id=rid,
        )
        handler.on_chain_end(outputs={"answer": "yes"}, run_id=rid)

        events = handler.drain_queue()
        types = [e.event_type for e in events]
        assert CrewEventType.CHAIN_START.value in types
        assert CrewEventType.CHAIN_END.value in types

    def test_retrieval_detected(self, handler):
        rid = _run_id()
        handler.on_chain_start(
            serialized={"id": ["VectorStoreRetriever"]},
            inputs={"query": "search term"},
            run_id=rid,
        )
        events = handler.drain_queue()
        # Should emit retrieval_start, not chain_start
        assert events[0].event_type == CrewEventType.RETRIEVAL_START.value


class TestDrainQueue:
    def test_drain_clears_queue(self, handler):
        for _ in range(5):
            handler.on_llm_start(
                serialized={"id": ["ChatOpenAI"]},
                prompts=["test"],
                run_id=_run_id(),
            )
        events = handler.drain_queue()
        assert len(events) == 5
        assert handler.drain_queue() == []

    def test_properties_include_session_id(self, handler):
        handler.on_llm_start(
            serialized={"id": ["ChatOpenAI"]},
            prompts=["x"],
            run_id=_run_id(),
        )
        ev = handler.drain_queue()[0]
        assert ev.session_id == "sess-test"
        assert ev.trace_id == "trace-test"
        assert ev.agent_id == "agent-test-001"
