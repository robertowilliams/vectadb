"""
VectaDBLoggingHook — observability hook for AG2 ConversableAgent.

Registers onto any AG2 agent via agent.register_hook() and captures:

  • Every new inbound message seen before an agent reply
  • Tool/function calls and their results (or errors)

Events are queued in-memory and drained by VectaDBAG2Tracer on flush.

Usage::

    from vectadb_ag2 import VectaDBLoggingHook

    hook = VectaDBLoggingHook(session_id="my-session", agent_name="planner")
    hook.attach(agent)          # registers hooks + wraps function_map
    # ... run your AG2 conversation ...
    events = hook.drain_queue() # flush manually, or use VectaDBAG2Tracer
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Optional

from .models import AG2EventType, VectaDBEvent, VectaDBSource

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_str(obj: Any, max_len: int = 4096) -> str:
    """Convert any object to a truncated string safe for JSON storage."""
    try:
        s = str(obj)
        return s[:max_len] + "…" if len(s) > max_len else s
    except Exception:
        return "<unserializable>"


class VectaDBLoggingHook:
    """
    Attaches to an AG2 ConversableAgent and emits typed VectaDB audit events.

    One hook instance per agent. The tracer manages a collection of hooks
    across multi-agent sessions.

    Parameters
    ----------
    session_id:
        Session identifier shared across all agents in a run.
    agent_name:
        Human-readable agent name. Overwritten by agent.name on attach().
    framework:
        Framework label embedded in every event's properties.
    trace_id:
        Optional trace ID to associate events with an existing VectaDB trace.
    """

    def __init__(
        self,
        session_id: str,
        agent_name: str = "unknown",
        framework: str = "ag2",
        trace_id: Optional[str] = None,
    ):
        self.session_id = session_id
        self.agent_name = agent_name
        self.framework = framework
        self.trace_id = trace_id

        self._queue: list[VectaDBEvent] = []
        self._lock = Lock()

        # Track how many messages we've already processed for each agent
        # so that process_all_messages_before_reply doesn't emit duplicates
        self._last_message_count: int = 0

    # ------------------------------------------------------------------
    # Attachment
    # ------------------------------------------------------------------

    def attach(self, agent: Any) -> None:
        """
        Register this hook on an AG2 ConversableAgent.

        Also wraps any functions already present in agent.function_map so
        that tool calls are captured. Functions registered *after* attach()
        should be wrapped manually via wrap_tool().
        """
        # Use the agent's name if available
        if name := getattr(agent, "name", None):
            self.agent_name = str(name)

        # Register the message observer hook
        agent.register_hook(
            "process_all_messages_before_reply",
            self._on_messages,
        )

        # Wrap any tools already registered on the agent
        fn_map: dict[str, Callable] = getattr(agent, "function_map", {})
        for tool_name, fn in list(fn_map.items()):
            fn_map[tool_name] = self._make_tool_wrapper(tool_name, fn)

        logger.debug(
            "VectaDBLoggingHook attached to agent '%s' [session=%s]",
            self.agent_name,
            self.session_id,
        )

    # ------------------------------------------------------------------
    # Hook handler — messages
    # ------------------------------------------------------------------

    def _on_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Called by AG2 before the agent generates a reply.

        Emits AGENT_MESSAGE events only for messages that are new since the
        last invocation (AG2 passes the full history every time).
        Returns the message list unchanged.
        """
        new_count = len(messages)

        if new_count < self._last_message_count:
            # Count decreased — new conversation started, reset from zero
            self._last_message_count = 0
        elif new_count == self._last_message_count:
            # No new messages — pass through unchanged
            return messages

        new_messages = messages[self._last_message_count:]
        self._last_message_count = new_count

        for msg in new_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content") or ""
            event = self._make_event(
                AG2EventType.AGENT_MESSAGE,
                {
                    "role": role,
                    "content": _safe_str(content),
                    "content_length": len(content) if isinstance(content, str) else 0,
                    "agent_name": self.agent_name,
                    "message_index": self._last_message_count - len(new_messages)
                    + new_messages.index(msg),
                },
            )
            self._enqueue(event)

        return messages

    # ------------------------------------------------------------------
    # Tool wrapper
    # ------------------------------------------------------------------

    def wrap_tool(self, tool_name: str, fn: Callable) -> Callable:
        """
        Return a version of fn that emits TOOL_CALL / TOOL_RESULT / TOOL_ERROR
        events. Use this for functions registered on the agent after attach().

        Example::

            agent.function_map["search"] = hook.wrap_tool("search", search_fn)
        """
        return self._make_tool_wrapper(tool_name, fn)

    def _make_tool_wrapper(self, tool_name: str, fn: Callable) -> Callable:
        hook = self

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            hook._enqueue(
                hook._make_event(
                    AG2EventType.TOOL_CALL,
                    {
                        "tool_name": tool_name,
                        "args": _safe_str(args),
                        "kwargs": _safe_str(kwargs),
                    },
                )
            )
            try:
                result = fn(*args, **kwargs)
                duration_ms = round((time.monotonic() - start) * 1000, 2)
                hook._enqueue(
                    hook._make_event(
                        AG2EventType.TOOL_RESULT,
                        {
                            "tool_name": tool_name,
                            "result": _safe_str(result),
                            "duration_ms": duration_ms,
                        },
                    )
                )
                return result
            except Exception as exc:
                duration_ms = round((time.monotonic() - start) * 1000, 2)
                hook._enqueue(
                    hook._make_event(
                        AG2EventType.TOOL_ERROR,
                        {
                            "tool_name": tool_name,
                            "error_type": type(exc).__name__,
                            "error_message": _safe_str(exc),
                            "duration_ms": duration_ms,
                        },
                    )
                )
                raise

        # Preserve metadata for introspection
        wrapper.__wrapped__ = fn  # type: ignore[attr-defined]
        wrapper.__name__ = getattr(fn, "__name__", tool_name)
        return wrapper

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def drain_queue(self) -> list[VectaDBEvent]:
        """Return and clear the current event queue (thread-safe)."""
        with self._lock:
            events, self._queue = self._queue, []
            return events

    def _enqueue(self, event: VectaDBEvent) -> None:
        with self._lock:
            self._queue.append(event)

    # ------------------------------------------------------------------
    # Event factory
    # ------------------------------------------------------------------

    def _make_event(
        self,
        event_type: AG2EventType,
        properties: dict[str, Any],
    ) -> VectaDBEvent:
        return VectaDBEvent(
            trace_id=self.trace_id,
            timestamp=_now(),
            event_type=event_type.value,
            agent_id=self.agent_name,
            session_id=self.session_id,
            properties={
                "framework": self.framework,
                **properties,
            },
            source=VectaDBSource(
                system=self.framework,
                log_group=f"{self.framework}/{self.agent_name}",
                log_stream=self.session_id,
                log_id=str(uuid.uuid4()),
            ),
        )
