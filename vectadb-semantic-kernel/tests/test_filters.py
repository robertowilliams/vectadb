"""Tests for VectaDBFunctionFilter — no semantic-kernel dependency required."""

import asyncio
import pytest

from vectadb_sk.filters import VectaDBFunctionFilter
from vectadb_sk.models import SKEventType


# ---------------------------------------------------------------------------
# Minimal mock of FunctionInvocationContext
# ---------------------------------------------------------------------------

class MockFunction:
    def __init__(self, plugin_name="TestPlugin", name="test_function"):
        self.plugin_name = plugin_name
        self.name = name


class MockArguments(dict):
    """Dict subclass with .items() — behaves like KernelArguments."""
    pass


class MockContext:
    def __init__(self, plugin_name="TestPlugin", function_name="test_fn", arguments=None, result=None):
        self.function = MockFunction(plugin_name, function_name)
        self.arguments = MockArguments(arguments or {"input": "hello"})
        self.result = result


async def identity_next(context):
    """A 'next' callable that does nothing (simulates successful invocation)."""
    pass


async def raising_next(context):
    """A 'next' callable that raises (simulates failed invocation)."""
    raise RuntimeError("kernel function blew up")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVectaDBFunctionFilter:

    @pytest.fixture
    def filter(self):
        return VectaDBFunctionFilter(
            session_id="test-session",
            agent_id="test-agent",
        )

    async def test_successful_invocation_enqueues_function_invoked(self, filter):
        ctx = MockContext(result="42")
        await filter(ctx, identity_next)

        events = filter.drain_queue()
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == SKEventType.FUNCTION_INVOKED
        assert ev.session_id == "test-session"
        assert ev.agent_id == "test-agent"

    async def test_function_name_in_properties(self, filter):
        ctx = MockContext(plugin_name="MyPlugin", function_name="my_fn")
        await filter(ctx, identity_next)

        ev = filter.drain_queue()[0]
        assert ev.properties["plugin_name"] == "MyPlugin"
        assert ev.properties["function_name"] == "my_fn"
        assert ev.properties["function"] == "MyPlugin.my_fn"

    async def test_duration_recorded(self, filter):
        ctx = MockContext()
        await filter(ctx, identity_next)

        ev = filter.drain_queue()[0]
        assert "duration_ms" in ev.properties
        assert isinstance(ev.properties["duration_ms"], int)
        assert ev.properties["duration_ms"] >= 0

    async def test_arguments_recorded_when_record_inputs_true(self):
        f = VectaDBFunctionFilter(record_inputs=True)
        ctx = MockContext(arguments={"query": "hello"})
        await f(ctx, identity_next)

        ev = f.drain_queue()[0]
        assert "arguments" in ev.properties
        assert ev.properties["arguments"]["query"] == "hello"

    async def test_arguments_omitted_when_record_inputs_false(self):
        f = VectaDBFunctionFilter(record_inputs=False)
        ctx = MockContext(arguments={"query": "hello"})
        await f(ctx, identity_next)

        ev = f.drain_queue()[0]
        assert "arguments" not in ev.properties

    async def test_result_recorded_when_record_outputs_true(self):
        f = VectaDBFunctionFilter(record_outputs=True)
        ctx = MockContext(result="the answer")
        await f(ctx, identity_next)

        ev = f.drain_queue()[0]
        assert "result" in ev.properties
        assert "the answer" in ev.properties["result"]

    async def test_result_omitted_when_record_outputs_false(self):
        f = VectaDBFunctionFilter(record_outputs=False)
        ctx = MockContext(result="the answer")
        await f(ctx, identity_next)

        ev = f.drain_queue()[0]
        assert "result" not in ev.properties

    async def test_failed_invocation_enqueues_function_error(self, filter):
        ctx = MockContext()
        with pytest.raises(RuntimeError):
            await filter(ctx, raising_next)

        events = filter.drain_queue()
        assert len(events) == 1
        ev = events[0]
        assert ev.event_type == SKEventType.FUNCTION_ERROR

    async def test_error_message_in_properties(self, filter):
        ctx = MockContext()
        with pytest.raises(RuntimeError):
            await filter(ctx, raising_next)

        ev = filter.drain_queue()[0]
        assert "error" in ev.properties
        assert "kernel function blew up" in ev.properties["error"]
        assert ev.properties["error_type"] == "RuntimeError"

    async def test_error_reraises_exception(self, filter):
        ctx = MockContext()
        with pytest.raises(RuntimeError, match="kernel function blew up"):
            await filter(ctx, raising_next)

    async def test_multiple_invocations_accumulate_events(self, filter):
        for _ in range(3):
            await filter(MockContext(), identity_next)

        events = filter.drain_queue()
        assert len(events) == 3

    async def test_drain_queue_clears_events(self, filter):
        await filter(MockContext(), identity_next)

        first = filter.drain_queue()
        assert len(first) == 1

        second = filter.drain_queue()
        assert second == []

    async def test_session_id_propagated_to_events(self):
        f = VectaDBFunctionFilter(session_id="sk-abc123")
        await f(MockContext(), identity_next)
        ev = f.drain_queue()[0]
        assert ev.session_id == "sk-abc123"

    async def test_no_session_id_allowed(self):
        f = VectaDBFunctionFilter(session_id=None)
        await f(MockContext(), identity_next)
        ev = f.drain_queue()[0]
        assert ev.session_id is None

    async def test_source_system_is_semantic_kernel(self, filter):
        await filter(MockContext(), identity_next)
        ev = filter.drain_queue()[0]
        assert ev.source is not None
        assert ev.source.system == "semantic_kernel"

    async def test_safe_repr_truncates_long_values(self):
        long_str = "x" * 1000
        result = VectaDBFunctionFilter._safe_repr(long_str)
        assert len(result) <= 505  # 500 chars + ellipsis

    async def test_safe_get_nested_attribute(self):
        ctx = MockContext(plugin_name="Plug", function_name="fn")
        val = VectaDBFunctionFilter._safe_get(ctx, "function.plugin_name")
        assert val == "Plug"

    async def test_safe_get_returns_default_on_missing_attr(self):
        ctx = MockContext()
        val = VectaDBFunctionFilter._safe_get(ctx, "nonexistent.path", default="fallback")
        assert val == "fallback"
