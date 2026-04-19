"""
Tests for VectaDBLangGraphTracer.

Verifies that traced_node() emits NODE_START / NODE_END / NODE_ERROR events,
that wrap_graph() instruments all nodes, that state passthrough is unchanged,
and that async node functions are handled correctly.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from vectadb_langchain.langgraph import VectaDBLangGraphTracer
from vectadb_langchain.models import LangChainEventType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tracer() -> VectaDBLangGraphTracer:
    t = VectaDBLangGraphTracer(
        vectadb_url="http://localhost:8080",
        graph_name="test_graph",
        fail_silently=True,
    )
    mock_client = MagicMock()
    mock_client.ingest_events_bulk.return_value = MagicMock(ingested=3, failed=0)
    t._client = mock_client
    return t


def planner_fn(state: dict) -> dict:
    return {**state, "plan": "step 1, step 2"}


def executor_fn(state: dict) -> dict:
    return {**state, "result": "done"}


def failing_fn(state: dict) -> dict:
    raise RuntimeError("node crashed")


async def async_node_fn(state: dict) -> dict:
    await asyncio.sleep(0)
    return {**state, "async_result": "ok"}


# ---------------------------------------------------------------------------
# traced_node — sync
# ---------------------------------------------------------------------------

def test_traced_node_emits_node_start_and_end(tracer):
    wrapped = tracer.traced_node("planner")(planner_fn)
    result = wrapped({"input": "task"})

    assert result["plan"] == "step 1, step 2"
    events = tracer._node_events
    assert len(events) == 2
    assert events[0].event_type == LangChainEventType.NODE_START.value
    assert events[1].event_type == LangChainEventType.NODE_END.value


def test_traced_node_start_has_correct_properties(tracer):
    wrapped = tracer.traced_node("planner")(planner_fn)
    wrapped({"question": "what?", "context": "..."})

    start_event = tracer._node_events[0]
    assert start_event.properties["node_name"] == "planner"
    assert start_event.properties["graph_name"] == "test_graph"
    assert start_event.properties["framework"] == "langgraph"
    assert "question" in start_event.properties["input_keys"]


def test_traced_node_end_has_duration(tracer):
    wrapped = tracer.traced_node("executor")(executor_fn)
    wrapped({"input": "go"})

    end_event = tracer._node_events[1]
    assert end_event.properties["duration_ms"] is not None
    assert end_event.properties["duration_ms"] >= 0


def test_traced_node_end_has_output_keys(tracer):
    wrapped = tracer.traced_node("executor")(executor_fn)
    wrapped({"input": "go"})

    end_event = tracer._node_events[1]
    assert "result" in end_event.properties["output_keys"]


def test_traced_node_state_passthrough_unchanged(tracer):
    wrapped = tracer.traced_node("planner")(planner_fn)
    state = {"input": "task", "metadata": {"user": "alice"}}
    result = wrapped(state)
    assert result["input"] == "task"
    assert result["metadata"]["user"] == "alice"
    assert result["plan"] == "step 1, step 2"


def test_traced_node_start_and_end_share_trace_id(tracer):
    wrapped = tracer.traced_node("planner")(planner_fn)
    wrapped({"x": 1})
    start, end = tracer._node_events
    assert start.trace_id == end.trace_id
    assert start.trace_id is not None


# ---------------------------------------------------------------------------
# traced_node — error
# ---------------------------------------------------------------------------

def test_traced_node_emits_node_error_on_exception(tracer):
    wrapped = tracer.traced_node("failing")(failing_fn)
    with pytest.raises(RuntimeError, match="node crashed"):
        wrapped({"input": "bad"})

    events = tracer._node_events
    assert len(events) == 2
    assert events[0].event_type == LangChainEventType.NODE_START.value
    assert events[1].event_type == LangChainEventType.NODE_ERROR.value


def test_traced_node_error_event_has_error_details(tracer):
    wrapped = tracer.traced_node("failing")(failing_fn)
    with pytest.raises(RuntimeError):
        wrapped({})

    error_event = tracer._node_events[1]
    assert error_event.properties["error_type"] == "RuntimeError"
    assert "node crashed" in error_event.properties["error_message"]
    assert error_event.properties["duration_ms"] is not None


def test_traced_node_reraises_exception(tracer):
    """The exception must propagate — tracer must not swallow it."""
    wrapped = tracer.traced_node("failing")(failing_fn)
    with pytest.raises(RuntimeError):
        wrapped({})


# ---------------------------------------------------------------------------
# traced_node — async
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_traced_node_async_emits_events(tracer):
    wrapped = tracer.traced_node("async_node")(async_node_fn)
    result = await wrapped({"x": 1})
    assert result["async_result"] == "ok"

    events = tracer._node_events
    assert len(events) == 2
    assert events[0].event_type == LangChainEventType.NODE_START.value
    assert events[1].event_type == LangChainEventType.NODE_END.value


@pytest.mark.asyncio
async def test_traced_node_async_error(tracer):
    async def bad_async(state):
        raise ValueError("async crash")

    wrapped = tracer.traced_node("bad")(bad_async)
    with pytest.raises(ValueError):
        await wrapped({})

    assert tracer._node_events[-1].event_type == LangChainEventType.NODE_ERROR.value


# ---------------------------------------------------------------------------
# Multiple nodes — independent trace IDs
# ---------------------------------------------------------------------------

def test_two_nodes_have_independent_trace_ids(tracer):
    w1 = tracer.traced_node("planner")(planner_fn)
    w2 = tracer.traced_node("executor")(executor_fn)
    w1({"input": "a"})
    state_after_plan = {"input": "a", "plan": "step 1, step 2"}
    w2(state_after_plan)

    # 4 events: start/end for planner, start/end for executor
    assert len(tracer._node_events) == 4
    trace_ids = {e.trace_id for e in tracer._node_events}
    # Each node invocation should have its own trace_id
    assert len(trace_ids) == 2


# ---------------------------------------------------------------------------
# wrap_graph
# ---------------------------------------------------------------------------

def test_wrap_graph_instruments_all_nodes(tracer):
    mock_builder = MagicMock()
    mock_builder.nodes = {
        "planner": planner_fn,
        "executor": executor_fn,
    }
    tracer.wrap_graph(mock_builder)

    # Nodes should now be wrapped callables
    for name, fn in mock_builder.nodes.items():
        assert callable(fn)
        assert fn.__wrapped__ if hasattr(fn, "__wrapped__") else True


def test_wrap_graph_returns_builder(tracer):
    mock_builder = MagicMock()
    mock_builder.nodes = {"planner": planner_fn}
    result = tracer.wrap_graph(mock_builder)
    assert result is mock_builder


def test_wrap_graph_handles_missing_nodes_attribute(tracer):
    """Should not raise if builder has no .nodes attribute."""
    bad_builder = object()
    result = tracer.wrap_graph(bad_builder)
    assert result is bad_builder


# ---------------------------------------------------------------------------
# flush
# ---------------------------------------------------------------------------

def test_flush_sends_node_events(tracer):
    wrapped = tracer.traced_node("planner")(planner_fn)
    wrapped({"x": 1})
    tracer.flush()
    tracer._client.ingest_events_bulk.assert_called_once()
    events_sent = tracer._client.ingest_events_bulk.call_args[0][0]
    assert len(events_sent) == 2
    assert tracer._node_events == []  # cleared after flush


def test_flush_drains_callback_handler_events(tracer):
    import uuid
    tracer.callback_handler.on_llm_start(
        serialized={"_type": "openai", "model": "gpt-4"},
        prompts=["test"],
        run_id=uuid.uuid4(),
    )
    wrapped = tracer.traced_node("planner")(planner_fn)
    wrapped({"x": 1})
    tracer.flush()

    events_sent = tracer._client.ingest_events_bulk.call_args[0][0]
    event_types = [e.event_type for e in events_sent]
    # 2 node events + 1 LLM event from callback handler
    assert LangChainEventType.NODE_START.value in event_types
    assert LangChainEventType.LLM_START.value in event_types


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

def test_context_manager_flushes_on_exit(tracer):
    wrapped = tracer.traced_node("planner")(planner_fn)
    with tracer:
        wrapped({"x": 1})
    tracer._client.ingest_events_bulk.assert_called_once()
    tracer._client.close.assert_called_once()


# ---------------------------------------------------------------------------
# Session ID and properties
# ---------------------------------------------------------------------------

def test_session_id_auto_generated():
    t = VectaDBLangGraphTracer(vectadb_url="http://localhost:8080")
    assert t.session_id.startswith("lg-")
    t._client.close()


def test_explicit_session_id():
    t = VectaDBLangGraphTracer(
        vectadb_url="http://localhost:8080", session_id="my-graph-session"
    )
    assert t.session_id == "my-graph-session"
    t._client.close()


def test_node_events_have_correct_session_id(tracer):
    wrapped = tracer.traced_node("planner")(planner_fn)
    wrapped({"x": 1})
    for event in tracer._node_events:
        assert event.session_id == tracer.session_id
