"""
LangGraph node tracer for VectaDB.

Instruments every node in a LangGraph StateGraph to emit NODE_START, NODE_END,
and NODE_ERROR events to VectaDB — capturing the full state-machine execution
trace alongside any LLM/tool events from inside nodes.

Usage (traced_node decorator)::

    from langgraph.graph import StateGraph
    from vectadb_langchain import VectaDBLangGraphTracer

    tracer = VectaDBLangGraphTracer(vectadb_url="http://localhost:8080")

    builder = StateGraph(MyState)
    builder.add_node("planner",  tracer.traced_node("planner")(planner_fn))
    builder.add_node("executor", tracer.traced_node("executor")(executor_fn))
    graph = builder.compile()
    graph.invoke({"messages": [...]})
    print(tracer.session_id)

Usage (wrap_graph)::

    tracer = VectaDBLangGraphTracer(vectadb_url="http://localhost:8080")
    # Instrument all nodes at once before compile()
    builder = tracer.wrap_graph(builder)
    graph = builder.compile()
    graph.invoke(...)

Both patterns attach the same VectaDBCallbackHandler to node invocations,
so LLM calls and tool uses inside nodes appear under the same session_id.
"""

from __future__ import annotations

import functools
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

from .callbacks import VectaDBCallbackHandler, _safe_str
from .client import SyncVectaDBClient
from .models import LangChainEventType, VectaDBEvent, VectaDBSource

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VectaDBLangGraphTracer:
    """
    Instruments LangGraph StateGraph nodes to emit audit events to VectaDB.

    Parameters
    ----------
    vectadb_url:
        Base URL of the VectaDB REST API.
    api_key:
        Optional X-API-Key header value.
    session_id:
        Explicit session ID. Auto-generated UUID if not provided.
    graph_name:
        Human-readable label for the graph (used in event metadata).
    framework:
        Framework label embedded in every event property (default: "langgraph").
    batch_size:
        Number of events per bulk ingestion request.
    generate_embeddings:
        Ask VectaDB to generate vector embeddings for each event.
    auto_create_traces:
        Ask VectaDB to auto-create trace records from session_id.
    fail_silently:
        If True, VectaDB connectivity problems will be logged but never
        propagate to crash the graph execution.
    """

    def __init__(
        self,
        vectadb_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        session_id: Optional[str] = None,
        graph_name: str = "graph",
        framework: str = "langgraph",
        batch_size: int = 100,
        generate_embeddings: bool = True,
        auto_create_traces: bool = True,
        fail_silently: bool = True,
    ):
        self.graph_name = graph_name
        self.framework = framework
        self.generate_embeddings = generate_embeddings
        self.auto_create_traces = auto_create_traces
        self.fail_silently = fail_silently

        self._session_id: str = session_id or f"lg-{uuid.uuid4().hex[:12]}"

        self._client = SyncVectaDBClient(
            base_url=vectadb_url,
            api_key=api_key,
            batch_size=batch_size,
        )

        # Shared callback handler — threads LLM/tool events from inside nodes
        # under the same session_id as the graph-level NODE_* events.
        self._callback_handler = VectaDBCallbackHandler(
            session_id=self._session_id,
            framework=framework,
        )

        # Queue for graph-level node events (not going through the handler)
        self._node_events: list[VectaDBEvent] = []

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def callback_handler(self) -> VectaDBCallbackHandler:
        """
        The shared callback handler. Pass this in node configs to capture
        LLM and tool events under the same session as node events::

            config={"callbacks": [tracer.callback_handler]}
        """
        return self._callback_handler

    # ------------------------------------------------------------------
    # Instrumentation API
    # ------------------------------------------------------------------

    def traced_node(self, name: str) -> Callable[[F], F]:
        """
        Decorator that wraps a node function to emit NODE_START / NODE_END /
        NODE_ERROR events around every invocation.

        Usage::

            @tracer.traced_node("my_node")
            def my_node_fn(state):
                ...
                return state
        """
        def decorator(fn: F) -> F:
            @functools.wraps(fn)
            def wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
                return self._run_traced(name, fn, state, *args, **kwargs)

            @functools.wraps(fn)
            async def async_wrapper(state: Any, *args: Any, **kwargs: Any) -> Any:
                return await self._run_traced_async(name, fn, state, *args, **kwargs)

            import asyncio
            if asyncio.iscoroutinefunction(fn):
                return async_wrapper  # type: ignore[return-value]
            return wrapper  # type: ignore[return-value]

        return decorator

    def wrap_graph(self, builder: Any) -> Any:
        """
        Instrument all nodes already registered on a StateGraph builder.

        Call this after all ``builder.add_node(...)`` calls but before
        ``builder.compile()``.

        Returns the same builder (mutated in-place) for chaining::

            graph = tracer.wrap_graph(builder).compile()
        """
        try:
            nodes: dict[str, Any] = builder.nodes  # type: ignore[attr-defined]
        except AttributeError:
            logger.warning(
                "VectaDBLangGraphTracer.wrap_graph: builder has no .nodes attribute — "
                "skipping instrumentation"
            )
            return builder

        for node_name, node_fn in list(nodes.items()):
            if callable(node_fn):
                nodes[node_name] = self.traced_node(node_name)(node_fn)
                logger.debug(
                    "VectaDB: wrapped LangGraph node '%s' [session=%s]",
                    node_name,
                    self._session_id,
                )

        return builder

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def flush(self) -> None:
        """
        Send all buffered node events and callback handler events to VectaDB.
        Call after graph.invoke() if not using the context manager.
        """
        # Drain callback handler (LLM/tool events from inside nodes)
        handler_events = self._callback_handler.drain_queue()
        all_events = self._node_events + handler_events
        self._node_events = []

        if all_events:
            self._ingest_bulk(all_events)

    def __enter__(self) -> "VectaDBLangGraphTracer":
        return self

    def __exit__(self, *args: Any) -> None:
        self.flush()
        self._client.close()

    # ------------------------------------------------------------------
    # Sync/async execution helpers
    # ------------------------------------------------------------------

    def _run_traced(
        self,
        node_name: str,
        fn: Callable[..., Any],
        state: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        start = time.monotonic()
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"

        self._emit_node_event(
            LangChainEventType.NODE_START,
            node_name=node_name,
            trace_id=trace_id,
            extra={
                "input_keys": list(state.keys()) if isinstance(state, dict) else [],
            },
        )

        try:
            result = fn(state, *args, **kwargs)
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            self._emit_node_event(
                LangChainEventType.NODE_END,
                node_name=node_name,
                trace_id=trace_id,
                extra={
                    "output_keys": list(result.keys()) if isinstance(result, dict) else [],
                    "duration_ms": duration_ms,
                },
            )
            return result
        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            self._emit_node_event(
                LangChainEventType.NODE_ERROR,
                node_name=node_name,
                trace_id=trace_id,
                extra={
                    "error_type": type(exc).__name__,
                    "error_message": _safe_str(exc),
                    "duration_ms": duration_ms,
                },
            )
            raise

    async def _run_traced_async(
        self,
        node_name: str,
        fn: Callable[..., Any],
        state: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        start = time.monotonic()
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"

        self._emit_node_event(
            LangChainEventType.NODE_START,
            node_name=node_name,
            trace_id=trace_id,
            extra={
                "input_keys": list(state.keys()) if isinstance(state, dict) else [],
            },
        )

        try:
            result = await fn(state, *args, **kwargs)
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            self._emit_node_event(
                LangChainEventType.NODE_END,
                node_name=node_name,
                trace_id=trace_id,
                extra={
                    "output_keys": list(result.keys()) if isinstance(result, dict) else [],
                    "duration_ms": duration_ms,
                },
            )
            return result
        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            self._emit_node_event(
                LangChainEventType.NODE_ERROR,
                node_name=node_name,
                trace_id=trace_id,
                extra={
                    "error_type": type(exc).__name__,
                    "error_message": _safe_str(exc),
                    "duration_ms": duration_ms,
                },
            )
            raise

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    def _emit_node_event(
        self,
        event_type: LangChainEventType,
        node_name: str,
        trace_id: str,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        event = VectaDBEvent(
            trace_id=trace_id,
            timestamp=_now(),
            event_type=event_type.value,
            session_id=self._session_id,
            properties={
                "node_name": node_name,
                "graph_name": self.graph_name,
                "framework": self.framework,
                **(extra or {}),
            },
            source=VectaDBSource(
                system=self.framework,
                log_group=f"{self.framework}/{self.graph_name}",
                log_stream=self._session_id,
                log_id=str(uuid.uuid4()),
            ),
        )
        self._node_events.append(event)

    def _ingest_bulk(self, events: list[VectaDBEvent]) -> None:
        if not events:
            return
        try:
            response = self._client.ingest_events_bulk(
                events,
                auto_create_traces=self.auto_create_traces,
                generate_embeddings=self.generate_embeddings,
            )
            if response:
                logger.debug(
                    "VectaDB LangGraph flush: %d succeeded, %d failed [session=%s]",
                    response.ingested,
                    response.failed,
                    self._session_id,
                )
        except Exception as exc:
            if self.fail_silently:
                logger.warning(
                    "VectaDB LangGraph ingestion error (non-fatal): %s", exc
                )
            else:
                raise
