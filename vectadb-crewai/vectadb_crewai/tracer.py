"""
VectaDBTracer — the main orchestrator for CrewAI audit tracing.

This is the primary interface users interact with. It:

  1. Creates a session ID for the entire crew run
  2. Builds per-agent VectaDBCallbackHandlers and injects them into each agent
  3. Wraps crew.kickoff() to capture crew-level start/end events
  4. Provides CrewAI-native step/task callbacks for higher-level lifecycle events
  5. Flushes all queued events to VectaDB on completion (or on error)

Usage::

    from vectadb_crewai import VectaDBTracer

    tracer = VectaDBTracer(vectadb_url="http://localhost:8080")
    result = tracer.kickoff(crew, inputs={"topic": "AI safety"})
    print(tracer.session_id)   # use to query VectaDB audit trail
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from crewai import Agent, Crew, Task

from .callbacks import VectaDBCallbackHandler, _safe_str
from .client import SyncVectaDBClient, VectaDBClientError
from .models import (
    AgentRunState,
    CrewEventType,
    CrewRunState,
    VectaDBEvent,
    VectaDBSource,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VectaDBTracer:
    """
    Instruments a CrewAI Crew to emit audit events to VectaDB.

    Parameters
    ----------
    vectadb_url:
        Base URL of the VectaDB REST API (default: http://localhost:8080).
    api_key:
        Optional API key sent as X-API-Key header.
    crew_name:
        Human-readable name for this crew (used in VectaDB metadata).
    batch_size:
        Number of events per bulk ingestion request.
    flush_on_error:
        Whether to still flush events if the crew run raises an exception.
    generate_embeddings:
        Ask VectaDB to generate vector embeddings for each event.
    auto_create_traces:
        Ask VectaDB to auto-create trace records from session_id.
    fail_silently:
        If True, VectaDB connectivity problems will be logged but never
        propagate to crash the crew run (recommended for production).
    """

    def __init__(
        self,
        vectadb_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        crew_name: str = "default_crew",
        batch_size: int = 100,
        flush_on_error: bool = True,
        generate_embeddings: bool = True,
        auto_create_traces: bool = True,
        fail_silently: bool = True,
    ):
        self.vectadb_url = vectadb_url
        self.api_key = api_key
        self.crew_name = crew_name
        self.flush_on_error = flush_on_error
        self.generate_embeddings = generate_embeddings
        self.auto_create_traces = auto_create_traces
        self.fail_silently = fail_silently

        self._client = SyncVectaDBClient(
            base_url=vectadb_url,
            api_key=api_key,
            batch_size=batch_size,
        )

        self._session_id: Optional[str] = None
        self._run_state: Optional[CrewRunState] = None
        self._handlers: list[VectaDBCallbackHandler] = []
        self._crew_start_time: Optional[float] = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> Optional[str]:
        """The session ID for the most recent (or active) crew run."""
        return self._session_id

    @property
    def run_state(self) -> Optional[CrewRunState]:
        return self._run_state

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def kickoff(
        self,
        crew: Crew,
        inputs: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Instrument crew and call crew.kickoff(inputs).

        This is a drop-in replacement for crew.kickoff() that wraps the run
        with full VectaDB audit tracing.

        Returns whatever crew.kickoff() returns.
        """
        self._begin_run(crew)
        result = None
        error: Optional[BaseException] = None

        try:
            result = crew.kickoff(inputs=inputs or {})
            return result
        except Exception as exc:
            error = exc
            raise
        finally:
            self._end_run(result=result, error=error)

    def instrument(self, crew: Crew) -> "VectaDBTracer":
        """
        Attach VectaDB callbacks to a crew without running it.

        Use this if you want to call crew.kickoff() yourself, or if you're
        using CrewAI's async kickoff variants. You must call tracer.flush()
        manually when the run is complete.

        Returns self for chaining.
        """
        self._begin_run(crew)
        return self

    def flush(
        self,
        result: Any = None,
        error: Optional[BaseException] = None,
    ) -> None:
        """
        Flush all queued events to VectaDB.

        Call this after crew.kickoff() when using tracer.instrument() directly.
        """
        self._end_run(result=result, error=error)

    # ------------------------------------------------------------------
    # CrewAI native step/task callbacks
    # ------------------------------------------------------------------

    def _make_step_callback(
        self, agent_state: AgentRunState
    ) -> Callable[[Any], None]:
        """
        Returns a function suitable for Crew(step_callback=...).

        Called by CrewAI after every agent step (thought + action + observation).
        """
        def step_callback(step_output: Any) -> None:
            try:
                event = VectaDBEvent(
                    trace_id=agent_state.trace_id,
                    timestamp=_now(),
                    event_type=CrewEventType.AGENT_ACTION.value,
                    agent_id=agent_state.agent_id,
                    session_id=agent_state.session_id,
                    properties={
                        "step_output": _safe_str(step_output),
                        "action_sequence": agent_state.action_sequence,
                        "framework": "crewai",
                        "callback_source": "step_callback",
                    },
                    source=VectaDBSource(
                        system="crewai",
                        log_group=f"crewai/{agent_state.agent_id}",
                        log_stream=agent_state.session_id,
                        log_id=str(uuid.uuid4()),
                    ),
                )
                # Directly flush this high-priority event
                self._ingest_event(event)
            except Exception as exc:
                logger.debug("step_callback event failed: %s", exc)

        return step_callback

    def _make_task_callback(self, crew: "Crew") -> Callable[[Any], None]:
        """
        Returns a function suitable for Crew(task_callback=...).

        Called by CrewAI when a Task completes. Uses a counter to correlate
        task_end events with the corresponding task_start (same task_index).
        """
        task_counter: dict[str, int] = {"n": 0}
        total_tasks = len(crew.tasks)

        def task_callback(task_output: Any) -> None:
            try:
                session_id = self._session_id or "unknown"
                idx = task_counter["n"]
                task_counter["n"] += 1

                # Best-effort: pull description from the task list if available
                description = ""
                agent_role = "unknown"
                if idx < total_tasks:
                    t = crew.tasks[idx]
                    description = _safe_str(t.description)[:200]
                    agent_role = getattr(getattr(t, "agent", None), "role", "unassigned")

                event = VectaDBEvent(
                    trace_id=None,
                    timestamp=_now(),
                    event_type=CrewEventType.TASK_END.value,
                    agent_id=None,
                    session_id=session_id,
                    properties={
                        "task_index": idx,
                        "task_output": _safe_str(task_output),
                        "description": description,
                        "agent_role": agent_role,
                        "framework": "crewai",
                        "callback_source": "task_callback",
                    },
                    source=VectaDBSource(
                        system="crewai",
                        log_group="crewai/tasks",
                        log_stream=session_id,
                        log_id=str(uuid.uuid4()),
                    ),
                )
                self._ingest_event(event)
            except Exception as exc:
                logger.debug("task_callback event failed: %s", exc)

        return task_callback

    # ------------------------------------------------------------------
    # Internal run lifecycle
    # ------------------------------------------------------------------

    def _begin_run(self, crew: Crew) -> None:
        """Set up session state and inject callbacks into the crew."""
        self._session_id = f"crew-{uuid.uuid4().hex[:12]}"
        self._crew_start_time = time.monotonic()
        self._handlers = []

        self._run_state = CrewRunState(
            session_id=self._session_id,
            crew_name=self.crew_name,
        )

        logger.info(
            "VectaDB tracer starting crew '%s' [session=%s]",
            self.crew_name,
            self._session_id,
        )

        # Attach per-agent callbacks
        for agent in crew.agents:
            self._attach_agent(agent)

        # Wrap each task to emit task_start events
        for idx, task in enumerate(crew.tasks):
            self._wrap_task_execute(task, idx)

        # Attach crew-level native callbacks (non-destructively)
        self._patch_crew_callbacks(crew)

        # Emit crew_start event
        self._ingest_event(
            VectaDBEvent(
                timestamp=_now(),
                event_type=CrewEventType.CREW_START.value,
                session_id=self._session_id,
                properties={
                    "crew_name": self.crew_name,
                    "agent_count": len(crew.agents),
                    "task_count": len(crew.tasks),
                    "agent_roles": [a.role for a in crew.agents],
                    "task_descriptions": [
                        _safe_str(t.description)[:200] for t in crew.tasks
                    ],
                    "framework": "crewai",
                },
                source=VectaDBSource(
                    system="crewai",
                    log_group=f"crewai/{self.crew_name}",
                    log_stream=self._session_id,
                    log_id=str(uuid.uuid4()),
                ),
            )
        )

    def _attach_agent(self, agent: Agent) -> None:
        """Create an AgentRunState + CallbackHandler and inject into agent."""
        agent_id = f"{agent.role.replace(' ', '_').lower()}-{uuid.uuid4().hex[:6]}"
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"

        agent_state = AgentRunState(
            agent_id=agent_id,
            role=agent.role,
            session_id=self._session_id,  # type: ignore[arg-type]
            trace_id=trace_id,
        )

        if self._run_state:
            self._run_state.agents[agent_id] = agent_state

        handler = VectaDBCallbackHandler(
            session_id=self._session_id,  # type: ignore[arg-type]
            agent_state=agent_state,
        )
        self._handlers.append(handler)

        # Inject into agent's callback list
        existing = list(agent.callbacks or [])
        existing.append(handler)
        agent.callbacks = existing

        # Emit agent_start event
        self._ingest_event(
            VectaDBEvent(
                trace_id=trace_id,
                timestamp=_now(),
                event_type=CrewEventType.AGENT_START.value,
                agent_id=agent_id,
                session_id=self._session_id,
                properties={
                    "role": agent.role,
                    "goal": _safe_str(agent.goal),
                    "backstory": _safe_str(getattr(agent, "backstory", "") or ""),
                    "tools": [
                        getattr(t, "name", str(t))
                        for t in (agent.tools or [])
                    ],
                    "llm": _safe_str(getattr(agent, "llm", "default")),
                    "framework": "crewai",
                },
                source=VectaDBSource(
                    system="crewai",
                    log_group=f"crewai/{agent_id}",
                    log_stream=self._session_id,  # type: ignore[arg-type]
                    log_id=str(uuid.uuid4()),
                ),
            )
        )

        logger.debug(
            "Attached VectaDB callback to agent '%s' [agent_id=%s, trace=%s]",
            agent.role,
            agent_id,
            trace_id,
        )

    def _wrap_task_execute(self, task: Task, task_idx: int) -> None:
        """
        Monkey-patch a Task's execute_sync to emit a task_start event
        immediately before the task begins executing.

        task_end is already handled by the Crew(task_callback=...) hook.
        This fills the missing gap so both bookends are captured.
        """
        execute_fn = getattr(task, "execute_sync", None)
        if execute_fn is None:
            logger.debug(
                "Task %d (%s) has no execute_sync — skipping task_start patch",
                task_idx,
                getattr(task, "description", "")[:60],
            )
            return

        session_id = self._session_id
        tracer = self  # capture reference (not self in closure to avoid circular ref issues)

        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                tracer._ingest_event(
                    VectaDBEvent(
                        timestamp=_now(),
                        event_type=CrewEventType.TASK_START.value,
                        session_id=session_id,
                        properties={
                            "task_index": task_idx,
                            "description": _safe_str(task.description)[:200],
                            "expected_output": _safe_str(
                                getattr(task, "expected_output", "") or ""
                            )[:200],
                            "agent_role": getattr(
                                getattr(task, "agent", None), "role", "unassigned"
                            ),
                            "framework": "crewai",
                        },
                        source=VectaDBSource(
                            system="crewai",
                            log_group="crewai/tasks",
                            log_stream=session_id or "unknown",
                            log_id=str(uuid.uuid4()),
                        ),
                    )
                )
            except Exception as exc:
                logger.debug("task_start event failed: %s", exc)
            return execute_fn(*args, **kwargs)

        task.execute_sync = _wrapped
        logger.debug(
            "Wrapped task %d for task_start tracing: %s",
            task_idx,
            _safe_str(task.description)[:60],
        )

    def _patch_crew_callbacks(self, crew: Crew) -> None:
        """Attach native CrewAI step/task callbacks without overwriting existing ones."""
        if not self._run_state or not self._run_state.agents:
            return

        # step_callback: use the first agent's state for the crew-level callback
        first_agent_state = next(iter(self._run_state.agents.values()))
        new_step_cb = self._make_step_callback(first_agent_state)
        new_task_cb = self._make_task_callback(crew)

        # Chain with any existing callbacks
        existing_step = getattr(crew, "step_callback", None)
        existing_task = getattr(crew, "task_callback", None)

        if existing_step is not None:
            _orig_step = existing_step
            def chained_step(output: Any) -> None:
                new_step_cb(output)
                _orig_step(output)
            crew.step_callback = chained_step
        else:
            crew.step_callback = new_step_cb

        if existing_task is not None:
            _orig_task = existing_task
            def chained_task(output: Any) -> None:
                new_task_cb(output)
                _orig_task(output)
            crew.task_callback = chained_task
        else:
            crew.task_callback = new_task_cb

    def _end_run(
        self,
        result: Any = None,
        error: Optional[BaseException] = None,
    ) -> None:
        """Emit end events, drain all handler queues, flush to VectaDB."""
        if not self._session_id:
            return

        duration_ms = (
            round((time.monotonic() - self._crew_start_time) * 1000, 2)
            if self._crew_start_time
            else None
        )

        # Emit crew_end or crew_error
        if error is not None:
            end_event = VectaDBEvent(
                timestamp=_now(),
                event_type=CrewEventType.CREW_ERROR.value,
                session_id=self._session_id,
                properties={
                    "crew_name": self.crew_name,
                    "error_type": type(error).__name__,
                    "error_message": _safe_str(error),
                    "duration_ms": duration_ms,
                    "framework": "crewai",
                },
                source=VectaDBSource(
                    system="crewai",
                    log_group=f"crewai/{self.crew_name}",
                    log_stream=self._session_id,
                    log_id=str(uuid.uuid4()),
                ),
            )
        else:
            end_event = VectaDBEvent(
                timestamp=_now(),
                event_type=CrewEventType.CREW_END.value,
                session_id=self._session_id,
                properties={
                    "crew_name": self.crew_name,
                    "result": _safe_str(result),
                    "duration_ms": duration_ms,
                    "framework": "crewai",
                },
                source=VectaDBSource(
                    system="crewai",
                    log_group=f"crewai/{self.crew_name}",
                    log_stream=self._session_id,
                    log_id=str(uuid.uuid4()),
                ),
            )

        # Drain all handler queues
        all_events: list[VectaDBEvent] = [end_event]
        for handler in self._handlers:
            all_events.extend(handler.drain_queue())

        logger.info(
            "VectaDB tracer flushing %d events [session=%s]",
            len(all_events),
            self._session_id,
        )

        if error is None or self.flush_on_error:
            self._ingest_bulk(all_events)

    # ------------------------------------------------------------------
    # Ingestion helpers
    # ------------------------------------------------------------------

    def _ingest_event(self, event: VectaDBEvent) -> None:
        """Immediately ingest a single event (fire-and-forget on failure)."""
        try:
            self._client.ingest_event(event, generate_embeddings=self.generate_embeddings)
        except VectaDBClientError as exc:
            self._handle_client_error(exc)
        except Exception as exc:
            self._handle_client_error(exc)

    def _ingest_bulk(self, events: list[VectaDBEvent]) -> None:
        """Bulk ingest a list of events."""
        if not events:
            return
        try:
            response = self._client.ingest_events_bulk(
                events,
                auto_create_traces=self.auto_create_traces,
                generate_embeddings=self.generate_embeddings,
            )
            if response:
                logger.info(
                    "VectaDB bulk ingest: %d succeeded, %d failed [session=%s]",
                    response.ingested,
                    response.failed,
                    self._session_id,
                )
        except Exception as exc:
            self._handle_client_error(exc)

    def _handle_client_error(self, exc: Exception) -> None:
        if self.fail_silently:
            logger.warning("VectaDB ingestion error (non-fatal): %s", exc)
        else:
            raise exc

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "VectaDBTracer":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.flush(error=exc_val)
        self._client.close()


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_tracer_from_env() -> VectaDBTracer:
    """
    Create a VectaDBTracer from environment variables.

    Variables:
        VECTADB_URL          — VectaDB base URL (default: http://localhost:8080)
        VECTADB_API_KEY      — Optional API key
        VECTADB_CREW_NAME    — Crew name label (default: my_crew)
        VECTADB_FAIL_SILENT  — "false" to let errors propagate (default: true)
    """
    import os

    return VectaDBTracer(
        vectadb_url=os.getenv("VECTADB_URL", "http://localhost:8080"),
        api_key=os.getenv("VECTADB_API_KEY"),
        crew_name=os.getenv("VECTADB_CREW_NAME", "my_crew"),
        fail_silently=os.getenv("VECTADB_FAIL_SILENT", "true").lower() != "false",
    )
