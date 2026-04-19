"""
Tests for VectaDBLoggingHook.

Verifies message capture, tool call wrapping, thread-safe queue drain,
and correct event types for success / error paths.
"""

from __future__ import annotations

import pytest

from vectadb_ag2.hooks import VectaDBLoggingHook, _safe_str
from vectadb_ag2.models import AG2EventType


# ---------------------------------------------------------------------------
# Minimal mock agent (no autogen dependency required)
# ---------------------------------------------------------------------------

class MockAgent:
    """Minimal stand-in for autogen.ConversableAgent."""

    def __init__(self, name: str = "test_agent"):
        self.name = name
        self._hooks: dict[str, list] = {}
        self.function_map: dict[str, callable] = {}

    def register_hook(self, hookable_method: str, hook) -> None:
        self._hooks.setdefault(hookable_method, []).append(hook)

    def trigger_message_hooks(self, messages: list[dict]) -> list[dict]:
        """Simulate AG2 calling process_all_messages_before_reply."""
        for hook in self._hooks.get("process_all_messages_before_reply", []):
            messages = hook(messages)
        return messages


def make_hook(**kwargs) -> VectaDBLoggingHook:
    return VectaDBLoggingHook(session_id="test-session", **kwargs)


# ---------------------------------------------------------------------------
# attach()
# ---------------------------------------------------------------------------

def test_attach_sets_agent_name():
    agent = MockAgent(name="planner")
    hook = make_hook()
    hook.attach(agent)
    assert hook.agent_name == "planner"


def test_attach_registers_message_hook():
    agent = MockAgent()
    hook = make_hook()
    hook.attach(agent)
    assert "process_all_messages_before_reply" in agent._hooks
    assert hook._on_messages in agent._hooks["process_all_messages_before_reply"]


def test_attach_wraps_existing_tools():
    def calc(x, y):
        return x + y

    agent = MockAgent()
    agent.function_map["calc"] = calc
    hook = make_hook()
    hook.attach(agent)

    # The wrapped function should have __wrapped__ pointing to the original
    assert hasattr(agent.function_map["calc"], "__wrapped__")
    assert agent.function_map["calc"].__wrapped__ is calc


# ---------------------------------------------------------------------------
# _on_messages — AGENT_MESSAGE events
# ---------------------------------------------------------------------------

def test_new_messages_emit_agent_message_events():
    agent = MockAgent()
    hook = make_hook()
    hook.attach(agent)

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]
    agent.trigger_message_hooks(messages)

    events = hook.drain_queue()
    assert len(events) == 2
    assert all(e.event_type == AG2EventType.AGENT_MESSAGE.value for e in events)


def test_message_event_has_correct_role_and_content():
    agent = MockAgent()
    hook = make_hook()
    hook.attach(agent)

    messages = [{"role": "user", "content": "What is RAG?"}]
    agent.trigger_message_hooks(messages)

    events = hook.drain_queue()
    assert events[0].properties["role"] == "user"
    assert events[0].properties["content"] == "What is RAG?"


def test_only_new_messages_emitted_on_subsequent_calls():
    agent = MockAgent()
    hook = make_hook()
    hook.attach(agent)

    # First call — 1 message
    agent.trigger_message_hooks([{"role": "user", "content": "msg1"}])
    hook.drain_queue()  # clear

    # Second call — 2 messages total (1 new)
    agent.trigger_message_hooks([
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "msg2"},
    ])
    events = hook.drain_queue()
    assert len(events) == 1
    assert events[0].properties["content"] == "msg2"


def test_message_hook_returns_messages_unchanged():
    agent = MockAgent()
    hook = make_hook()
    hook.attach(agent)

    original = [{"role": "user", "content": "unchanged"}]
    result = agent.trigger_message_hooks(original)
    assert result == original


def test_counter_resets_when_message_count_decreases():
    agent = MockAgent()
    hook = make_hook()
    hook.attach(agent)

    # First conversation: 2 messages → counter = 2
    agent.trigger_message_hooks([
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "reply a"},
    ])
    hook.drain_queue()

    # New conversation: 1 message (count < previous counter)
    # Hook should reset and capture this message
    agent.trigger_message_hooks([{"role": "user", "content": "b"}])
    events = hook.drain_queue()
    assert len(events) == 1
    assert events[0].properties["content"] == "b"


# ---------------------------------------------------------------------------
# Tool call wrapping
# ---------------------------------------------------------------------------

def test_tool_call_emits_tool_call_and_result():
    def add(x, y):
        return x + y

    agent = MockAgent()
    agent.function_map["add"] = add
    hook = make_hook()
    hook.attach(agent)

    agent.function_map["add"](2, 3)

    events = hook.drain_queue()
    types = [e.event_type for e in events]
    assert AG2EventType.TOOL_CALL.value in types
    assert AG2EventType.TOOL_RESULT.value in types


def test_tool_result_has_duration_ms():
    def noop():
        return "ok"

    agent = MockAgent()
    agent.function_map["noop"] = noop
    hook = make_hook()
    hook.attach(agent)
    agent.function_map["noop"]()

    events = hook.drain_queue()
    result_event = next(e for e in events if e.event_type == AG2EventType.TOOL_RESULT.value)
    assert result_event.properties["duration_ms"] is not None
    assert result_event.properties["duration_ms"] >= 0


def test_tool_error_emits_on_exception():
    def bad_tool():
        raise ValueError("tool failed")

    hook = make_hook()
    wrapped = hook.wrap_tool("bad", bad_tool)

    with pytest.raises(ValueError):
        wrapped()

    events = hook.drain_queue()
    types = [e.event_type for e in events]
    assert AG2EventType.TOOL_ERROR.value in types


def test_tool_error_event_has_error_details():
    def bad_tool():
        raise RuntimeError("something broke")

    hook = make_hook()
    wrapped = hook.wrap_tool("bad", bad_tool)

    with pytest.raises(RuntimeError):
        wrapped()

    events = hook.drain_queue()
    err = next(e for e in events if e.event_type == AG2EventType.TOOL_ERROR.value)
    assert err.properties["error_type"] == "RuntimeError"
    assert "something broke" in err.properties["error_message"]


def test_tool_error_reraises_exception():
    def explode():
        raise TypeError("boom")

    hook = make_hook()
    wrapped = hook.wrap_tool("explode", explode)
    with pytest.raises(TypeError, match="boom"):
        wrapped()


# ---------------------------------------------------------------------------
# drain_queue
# ---------------------------------------------------------------------------

def test_drain_queue_clears_events():
    agent = MockAgent()
    hook = make_hook()
    hook.attach(agent)
    agent.trigger_message_hooks([{"role": "user", "content": "hi"}])

    first = hook.drain_queue()
    second = hook.drain_queue()
    assert len(first) == 1
    assert len(second) == 0


# ---------------------------------------------------------------------------
# Session / properties
# ---------------------------------------------------------------------------

def test_event_session_id_matches_hook():
    agent = MockAgent()
    hook = make_hook()
    hook.attach(agent)
    agent.trigger_message_hooks([{"role": "user", "content": "x"}])

    events = hook.drain_queue()
    assert events[0].session_id == "test-session"


def test_event_framework_is_ag2():
    agent = MockAgent()
    hook = make_hook()
    hook.attach(agent)
    agent.trigger_message_hooks([{"role": "user", "content": "x"}])

    events = hook.drain_queue()
    assert events[0].properties["framework"] == "ag2"


# ---------------------------------------------------------------------------
# safe_str helper
# ---------------------------------------------------------------------------

def test_safe_str_truncates_long_strings():
    long = "a" * 5000
    result = _safe_str(long, max_len=100)
    assert len(result) <= 101  # 100 + ellipsis char
    assert result.endswith("…")


def test_safe_str_handles_non_strings():
    assert _safe_str({"key": "val"}) == "{'key': 'val'}"
