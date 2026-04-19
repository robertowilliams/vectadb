"""
LangChain BaseCallbackHandler implementation for VectaDB audit tracing.

LangChain agents and chains fire a rich set of callback events at every step.
This handler intercepts those events and forwards them as typed VectaDB audit
events, capturing:

  • LLM calls   — prompt text, model name, token usage, response
  • Tool calls  — tool name, input, output, latency
  • Agent steps — ReAct thought/action/observation cycles
  • Chain runs  — sub-chain start/end (retrieval chains, etc.)
  • Errors      — all of the above when things go wrong

Events are queued in-memory and flushed to VectaDB's bulk ingestion API
either immediately (per-event mode) or in batches (batch mode, default).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional, Sequence, Union

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from .models import (
    AgentRunState,
    LangChainEventType,
    VectaDBEvent,
    VectaDBSource,
)

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


def _extract_llm_info(serialized: dict[str, Any]) -> dict[str, str]:
    """Pull model/provider info from LangChain's serialized LLM dict."""
    info: dict[str, str] = {}
    for key in ("model", "model_name", "model_id", "deployment_name"):
        if v := serialized.get(key):
            info["model"] = str(v)
            break
    if not info.get("model"):
        info["model"] = serialized.get("id", ["unknown"])[-1]
    info["provider"] = serialized.get("_type", "unknown")
    return info


class VectaDBCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler that captures agent and chain runs into VectaDB.

    Can be used standalone with any LangChain Runnable::

        handler = VectaDBCallbackHandler(session_id="my-session")
        chain.invoke(input, config={"callbacks": [handler]})
        events = handler.drain_queue()  # flush manually, or use VectaDBTracer

    Or managed automatically via VectaDBTracer (recommended).
    """

    # LangChain BaseCallbackHandler flag: do not raise on errors in callbacks
    raise_error = False

    def __init__(
        self,
        session_id: str,
        agent_state: Optional[AgentRunState] = None,
        flush_interval: int = 20,   # flush every N events
        framework: str = "langchain",
    ):
        super().__init__()
        self.session_id = session_id
        self.agent_state = agent_state
        self.flush_interval = flush_interval
        self.framework = framework

        self._queue: list[VectaDBEvent] = []
        self._lock = Lock()

        # Timing maps keyed by run_id (str)
        self._tool_start_times: dict[str, float] = {}
        self._llm_start_times: dict[str, float] = {}
        self._chain_start_times: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def agent_id(self) -> Optional[str]:
        return self.agent_state.agent_id if self.agent_state else None

    @property
    def trace_id(self) -> Optional[str]:
        return self.agent_state.trace_id if self.agent_state else None

    def drain_queue(self) -> list[VectaDBEvent]:
        """Return and clear the current event queue (thread-safe)."""
        with self._lock:
            events, self._queue = self._queue, []
            return events

    # ------------------------------------------------------------------
    # Internal event factory
    # ------------------------------------------------------------------

    def _make_event(
        self,
        event_type: LangChainEventType,
        properties: dict[str, Any],
        run_id: Optional[Any] = None,
    ) -> VectaDBEvent:
        props = {
            "framework": self.framework,
            **properties,
        }
        if run_id is not None:
            props["langchain_run_id"] = str(run_id)

        return VectaDBEvent(
            trace_id=self.trace_id,
            timestamp=_now(),
            event_type=event_type.value,
            agent_id=self.agent_id,
            session_id=self.session_id,
            properties=props,
            source=VectaDBSource(
                system=self.framework,
                log_group=f"{self.framework}/{self.agent_id or 'unknown'}",
                log_stream=self.session_id,
                log_id=str(uuid.uuid4()),
            ),
        )

    def _enqueue(self, event: VectaDBEvent) -> None:
        with self._lock:
            self._queue.append(event)

    # ------------------------------------------------------------------
    # LLM callbacks
    # ------------------------------------------------------------------

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._llm_start_times[str(run_id)] = time.monotonic()

        llm_info = _extract_llm_info(serialized)
        prompt_text = "\n\n---\n\n".join(prompts)

        event = self._make_event(
            LangChainEventType.LLM_START,
            {
                "model": llm_info.get("model", "unknown"),
                "provider": llm_info.get("provider", "unknown"),
                "prompt": _safe_str(prompt_text),
                "prompt_length": len(prompt_text),
            },
            run_id=run_id,
        )
        self._enqueue(event)
        if self.agent_state:
            self.agent_state.llm_call_count += 1

    def on_chat_model_start(
        self,
        serialized: Dict[str, Any],
        messages: List[List[BaseMessage]],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._llm_start_times[str(run_id)] = time.monotonic()

        llm_info = _extract_llm_info(serialized)
        flat_messages = [m for group in messages for m in group]
        formatted = "\n".join(
            f"[{m.__class__.__name__}] {_safe_str(m.content)}"
            for m in flat_messages
        )

        event = self._make_event(
            LangChainEventType.LLM_START,
            {
                "model": llm_info.get("model", "unknown"),
                "provider": llm_info.get("provider", "unknown"),
                "prompt": _safe_str(formatted),
                "message_count": len(flat_messages),
                "chat_mode": True,
            },
            run_id=run_id,
        )
        self._enqueue(event)
        if self.agent_state:
            self.agent_state.llm_call_count += 1

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        duration_ms = self._pop_duration(self._llm_start_times, str(run_id))

        # Extract text output and token usage
        output_texts = []
        for gen_list in response.generations:
            for gen in gen_list:
                text = getattr(gen, "text", None) or _safe_str(gen)
                output_texts.append(text)

        token_usage: dict[str, Any] = {}
        if response.llm_output:
            usage = response.llm_output.get("token_usage") or {}
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }

        event = self._make_event(
            LangChainEventType.LLM_END,
            {
                "output": _safe_str("\n".join(output_texts)),
                "duration_ms": duration_ms,
                **{k: v for k, v in token_usage.items() if v is not None},
            },
            run_id=run_id,
        )
        self._enqueue(event)

    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        duration_ms = self._pop_duration(self._llm_start_times, str(run_id))
        event = self._make_event(
            LangChainEventType.LLM_ERROR,
            {
                "error_type": type(error).__name__,
                "error_message": _safe_str(error),
                "duration_ms": duration_ms,
            },
            run_id=run_id,
        )
        self._enqueue(event)

    # ------------------------------------------------------------------
    # Tool callbacks
    # ------------------------------------------------------------------

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._tool_start_times[str(run_id)] = time.monotonic()

        tool_name = serialized.get("name") or kwargs.get("name") or "unknown_tool"
        event = self._make_event(
            LangChainEventType.TOOL_START,
            {
                "tool_name": tool_name,
                "tool_input": _safe_str(input_str),
                "tool_input_length": len(input_str),
            },
            run_id=run_id,
        )
        self._enqueue(event)
        if self.agent_state:
            self.agent_state.tool_call_count += 1

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        duration_ms = self._pop_duration(self._tool_start_times, str(run_id))
        tool_name = kwargs.get("name") or "unknown_tool"

        event = self._make_event(
            LangChainEventType.TOOL_END,
            {
                "tool_name": tool_name,
                "tool_output": _safe_str(output),
                "tool_output_length": len(output) if isinstance(output, str) else 0,
                "duration_ms": duration_ms,
            },
            run_id=run_id,
        )
        self._enqueue(event)

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        duration_ms = self._pop_duration(self._tool_start_times, str(run_id))
        tool_name = kwargs.get("name") or "unknown_tool"

        event = self._make_event(
            LangChainEventType.TOOL_ERROR,
            {
                "tool_name": tool_name,
                "error_type": type(error).__name__,
                "error_message": _safe_str(error),
                "duration_ms": duration_ms,
            },
            run_id=run_id,
        )
        self._enqueue(event)

    # ------------------------------------------------------------------
    # Agent action callbacks (ReAct thought/action/observation)
    # ------------------------------------------------------------------

    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        if self.agent_state:
            self.agent_state.action_sequence += 1
            seq = self.agent_state.action_sequence
        else:
            seq = None

        event = self._make_event(
            LangChainEventType.AGENT_ACTION,
            {
                "tool": getattr(action, "tool", str(action)),
                "tool_input": _safe_str(getattr(action, "tool_input", "")),
                "log": _safe_str(getattr(action, "log", "")),
                "action_sequence": seq,
            },
            run_id=run_id,
        )
        self._enqueue(event)

    def on_agent_finish(
        self,
        finish: Any,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        event = self._make_event(
            LangChainEventType.AGENT_END,
            {
                "output": _safe_str(getattr(finish, "return_values", finish)),
                "log": _safe_str(getattr(finish, "log", "")),
                "tool_calls_total": self.agent_state.tool_call_count if self.agent_state else None,
                "llm_calls_total": self.agent_state.llm_call_count if self.agent_state else None,
            },
            run_id=run_id,
        )
        self._enqueue(event)

    # ------------------------------------------------------------------
    # Chain callbacks (sub-chains, retrieval, etc.)
    # ------------------------------------------------------------------

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._chain_start_times[str(run_id)] = time.monotonic()
        chain_type = serialized.get("id", ["unknown"])[-1]

        # Detect retrieval chains specifically for evidence provenance
        event_type = (
            LangChainEventType.RETRIEVAL_START
            if "retriev" in chain_type.lower()
            else LangChainEventType.CHAIN_START
        )

        event = self._make_event(
            event_type,
            {
                "chain_type": chain_type,
                "input_keys": list(inputs.keys()) if isinstance(inputs, dict) else [],
            },
            run_id=run_id,
        )
        self._enqueue(event)

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        duration_ms = self._pop_duration(self._chain_start_times, str(run_id))

        event = self._make_event(
            LangChainEventType.CHAIN_END,
            {
                "output_keys": list(outputs.keys()) if isinstance(outputs, dict) else [],
                "duration_ms": duration_ms,
            },
            run_id=run_id,
        )
        self._enqueue(event)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        duration_ms = self._pop_duration(self._chain_start_times, str(run_id))
        event = self._make_event(
            LangChainEventType.CHAIN_ERROR,
            {
                "error_type": type(error).__name__,
                "error_message": _safe_str(error),
                "duration_ms": duration_ms,
            },
            run_id=run_id,
        )
        self._enqueue(event)

    # ------------------------------------------------------------------
    # Retrieval callbacks (LangChain retriever interface)
    # ------------------------------------------------------------------

    def on_retriever_start(
        self,
        serialized: Dict[str, Any],
        query: str,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._chain_start_times[str(run_id)] = time.monotonic()
        event = self._make_event(
            LangChainEventType.RETRIEVAL_START,
            {
                "query": _safe_str(query),
                "retriever_type": serialized.get("id", ["unknown"])[-1],
            },
            run_id=run_id,
        )
        self._enqueue(event)

    def on_retriever_end(
        self,
        documents: Any,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        duration_ms = self._pop_duration(self._chain_start_times, str(run_id))
        doc_count = len(documents) if hasattr(documents, "__len__") else 0

        event = self._make_event(
            LangChainEventType.RETRIEVAL_END,
            {
                "document_count": doc_count,
                "duration_ms": duration_ms,
            },
            run_id=run_id,
        )
        self._enqueue(event)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _pop_duration(timing_map: dict[str, float], key: str) -> Optional[float]:
        """Pop a start time from the map and return elapsed ms."""
        start = timing_map.pop(key, None)
        if start is None:
            return None
        return round((time.monotonic() - start) * 1000, 2)
