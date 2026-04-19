"""
Semantic Kernel function invocation filter for VectaDB observability.

Implements SK's IFunctionInvocationFilter protocol — a callable that wraps
every kernel function call to record timing, inputs, outputs, and errors as
typed VectaDB events.

Usage::

    tracer = VectaDBSKTracer("http://localhost:8080", session_id="my-session")
    tracer.register(kernel)  # adds this filter to the kernel

    # Or use the filter directly
    filter = VectaDBFunctionFilter(client, session_id="my-session")
    kernel.add_filter("function_invocation", filter)
"""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

from .models import SKEventType, VectaDBEvent, VectaDBSource

logger = logging.getLogger(__name__)


class VectaDBFunctionFilter:
    """
    Semantic Kernel IFunctionInvocationFilter implementation.

    Records FUNCTION_INVOKED and FUNCTION_ERROR events around every kernel
    function call.  Events are queued internally; call drain_queue() to
    retrieve them for bulk ingestion.

    This class follows the IFunctionInvocationFilter protocol: it is an async
    callable with the signature::

        async def __call__(
            self,
            context: FunctionInvocationContext,
            next: Callable[[FunctionInvocationContext], Coroutine],
        ) -> None

    Because we don't want to import semantic-kernel at module load time
    (it's an optional dependency), we accept Any-typed arguments.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = "semantic-kernel",
        record_inputs: bool = True,
        record_outputs: bool = True,
        fail_silently: bool = True,
    ):
        self.session_id = session_id
        self.agent_id = agent_id
        self.record_inputs = record_inputs
        self.record_outputs = record_outputs
        self.fail_silently = fail_silently
        self._queue: deque[VectaDBEvent] = deque()

    # ------------------------------------------------------------------
    # IFunctionInvocationFilter protocol
    # ------------------------------------------------------------------

    async def __call__(
        self,
        context: Any,
        next: Callable[[Any], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Called by SK around every function invocation.

        ``context`` is a FunctionInvocationContext from semantic-kernel.
        We inspect it using attribute access so we don't hard-import SK.
        """
        plugin_name = self._safe_get(context, "function.plugin_name", "unknown")
        function_name = self._safe_get(context, "function.name", "unknown")
        full_name = f"{plugin_name}.{function_name}"

        arguments = {}
        if self.record_inputs:
            try:
                raw_args = getattr(context, "arguments", None)
                if raw_args is not None:
                    # KernelArguments behaves like a dict
                    if hasattr(raw_args, "items"):
                        arguments = {k: self._safe_repr(v) for k, v in raw_args.items()}
                    else:
                        arguments = {"value": self._safe_repr(raw_args)}
            except Exception:
                pass

        start = time.monotonic()
        error_info: Optional[str] = None

        try:
            await next(context)
        except Exception as exc:
            error_info = str(exc)
            self._enqueue_error(full_name, plugin_name, function_name, arguments, exc)
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            if error_info is None:
                self._enqueue_success(
                    full_name, plugin_name, function_name, arguments, context, duration_ms
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _enqueue_success(
        self,
        full_name: str,
        plugin_name: str,
        function_name: str,
        arguments: dict[str, Any],
        context: Any,
        duration_ms: int,
    ) -> None:
        properties: dict[str, Any] = {
            "function": full_name,
            "plugin_name": plugin_name,
            "function_name": function_name,
            "duration_ms": duration_ms,
        }
        if arguments and self.record_inputs:
            properties["arguments"] = arguments
        if self.record_outputs:
            try:
                result = getattr(context, "result", None)
                if result is not None:
                    properties["result"] = self._safe_repr(result)
            except Exception:
                pass

        self._queue.append(
            VectaDBEvent(
                timestamp=datetime.now(timezone.utc),
                event_type=SKEventType.FUNCTION_INVOKED,
                agent_id=self.agent_id,
                session_id=self.session_id,
                properties=properties,
                source=VectaDBSource(),
            )
        )

    def _enqueue_error(
        self,
        full_name: str,
        plugin_name: str,
        function_name: str,
        arguments: dict[str, Any],
        exc: Exception,
    ) -> None:
        properties: dict[str, Any] = {
            "function": full_name,
            "plugin_name": plugin_name,
            "function_name": function_name,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }
        if arguments and self.record_inputs:
            properties["arguments"] = arguments

        self._queue.append(
            VectaDBEvent(
                timestamp=datetime.now(timezone.utc),
                event_type=SKEventType.FUNCTION_ERROR,
                agent_id=self.agent_id,
                session_id=self.session_id,
                properties=properties,
                source=VectaDBSource(),
            )
        )

    def drain_queue(self) -> list[VectaDBEvent]:
        """Remove and return all queued events (thread-safe pop from left)."""
        events: list[VectaDBEvent] = []
        while self._queue:
            try:
                events.append(self._queue.popleft())
            except IndexError:
                break
        return events

    @staticmethod
    def _safe_get(obj: Any, dotted_path: str, default: Any = None) -> Any:
        """Navigate a dotted attribute path, returning default on any failure."""
        try:
            current = obj
            for part in dotted_path.split("."):
                current = getattr(current, part)
            return current
        except Exception:
            return default

    @staticmethod
    def _safe_repr(value: Any, max_length: int = 500) -> str:
        """Convert a value to a short string representation."""
        try:
            s = str(value)
            return s[:max_length] + "…" if len(s) > max_length else s
        except Exception:
            return "<unrepresentable>"
