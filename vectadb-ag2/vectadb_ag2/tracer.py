"""
VectaDBAG2Tracer — multi-agent observability context manager for AG2.

Instruments any number of AG2 ConversableAgents to emit typed audit events
to VectaDB without modifying the agent definitions or conversation logic.

Sync usage::

    from vectadb_ag2 import VectaDBAG2Tracer

    with VectaDBAG2Tracer(vectadb_url="http://localhost:8080") as tracer:
        tracer.attach(planner)
        tracer.attach(executor)
        # ... run group chat or pairwise conversation ...
    # All queued events flushed to VectaDB on __exit__

Async usage::

    async with VectaDBAG2Tracer(vectadb_url="http://localhost:8080") as tracer:
        tracer.attach(planner)
        result = await some_async_ag2_workflow()

Pre-attach usage (agents provided at construction time)::

    with VectaDBAG2Tracer(
        vectadb_url="http://localhost:8080",
        agents=[planner, executor, critic],
    ) as tracer:
        groupchat.run(...)
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from .client import SyncVectaDBClient
from .hooks import VectaDBLoggingHook, _safe_str
from .models import VectaDBEvent

logger = logging.getLogger(__name__)


class VectaDBAG2Tracer:
    """
    Context manager that instruments AG2 agents and flushes audit events
    to VectaDB on exit.

    Parameters
    ----------
    vectadb_url:
        Base URL of the VectaDB REST API (default: http://localhost:8080).
    api_key:
        Optional API key sent as X-API-Key header.
    session_id:
        Explicit session ID. Auto-generated (``ag2-<uuid>``) if not provided.
    agents:
        Optional list of AG2 agents to instrument immediately.
    batch_size:
        Events per bulk ingestion request.
    generate_embeddings:
        Ask VectaDB to generate vector embeddings for each event.
    auto_create_traces:
        Ask VectaDB to auto-create trace records from session_id.
    fail_silently:
        If True, VectaDB connectivity problems are logged but never propagate.
    """

    def __init__(
        self,
        vectadb_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        session_id: Optional[str] = None,
        agents: Optional[list[Any]] = None,
        batch_size: int = 100,
        generate_embeddings: bool = True,
        auto_create_traces: bool = True,
        fail_silently: bool = True,
    ):
        self.vectadb_url = vectadb_url
        self.api_key = api_key
        self.generate_embeddings = generate_embeddings
        self.auto_create_traces = auto_create_traces
        self.fail_silently = fail_silently

        self._session_id: str = session_id or f"ag2-{uuid.uuid4().hex[:12]}"
        self._hooks: list[VectaDBLoggingHook] = []
        self._start_time: Optional[float] = None

        self._client = SyncVectaDBClient(
            base_url=vectadb_url,
            api_key=api_key,
            batch_size=batch_size,
        )

        # Attach any agents provided at construction time
        for agent in (agents or []):
            self.attach(agent)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        """The session ID shared across all attached agents."""
        return self._session_id

    def attach(self, agent: Any) -> VectaDBLoggingHook:
        """
        Instrument an AG2 agent and return the hook for direct access.

        Can be called before or inside the context manager.
        """
        hook = VectaDBLoggingHook(session_id=self._session_id)
        hook.attach(agent)
        self._hooks.append(hook)
        logger.debug(
            "VectaDBAG2Tracer attached to agent '%s' [session=%s]",
            hook.agent_name,
            self._session_id,
        )
        return hook

    def flush(self) -> None:
        """
        Drain all hooks and send queued events to VectaDB.

        Call this manually if you are not using the context manager.
        """
        self._end(error=None)

    # ------------------------------------------------------------------
    # Context manager — sync
    # ------------------------------------------------------------------

    def __enter__(self) -> "VectaDBAG2Tracer":
        self._start_time = time.monotonic()
        logger.info(
            "VectaDBAG2Tracer session started [session=%s]", self._session_id
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._end(error=exc_val)
        self._client.close()

    # ------------------------------------------------------------------
    # Context manager — async
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "VectaDBAG2Tracer":
        self._start_time = time.monotonic()
        logger.info(
            "VectaDBAG2Tracer session started [session=%s]", self._session_id
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._end(error=exc_val)
        self._client.close()

    # ------------------------------------------------------------------
    # Internal lifecycle
    # ------------------------------------------------------------------

    def _end(self, error: Optional[BaseException]) -> None:
        duration_ms = (
            round((time.monotonic() - self._start_time) * 1000, 2)
            if self._start_time
            else None
        )

        # Collect events from all attached hooks
        all_events: list[VectaDBEvent] = []
        for hook in self._hooks:
            all_events.extend(hook.drain_queue())

        if all_events:
            logger.info(
                "VectaDBAG2Tracer flushing %d events from %d agent(s) [session=%s]",
                len(all_events),
                len(self._hooks),
                self._session_id,
            )
            self._ingest_bulk(all_events)

        if error is not None:
            logger.info(
                "VectaDBAG2Tracer session ended with error after %.0fms [session=%s]: %s",
                duration_ms or 0,
                self._session_id,
                _safe_str(error),
            )
        else:
            logger.info(
                "VectaDBAG2Tracer session completed in %.0fms [session=%s]",
                duration_ms or 0,
                self._session_id,
            )

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
                    "VectaDB bulk ingest: %d succeeded, %d failed [session=%s]",
                    response.ingested,
                    response.failed,
                    self._session_id,
                )
        except Exception as exc:
            if self.fail_silently:
                logger.warning("VectaDB ingestion error (non-fatal): %s", exc)
            else:
                raise


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_tracer_from_env(agents: Optional[list[Any]] = None) -> VectaDBAG2Tracer:
    """
    Create a VectaDBAG2Tracer from environment variables.

    Variables
    ---------
    VECTADB_URL         — VectaDB base URL (default: http://localhost:8080)
    VECTADB_API_KEY     — Optional API key
    VECTADB_SESSION_ID  — Optional explicit session ID
    VECTADB_FAIL_SILENT — "false" to let errors propagate (default: true)
    """
    import os

    return VectaDBAG2Tracer(
        vectadb_url=os.getenv("VECTADB_URL", "http://localhost:8080"),
        api_key=os.getenv("VECTADB_API_KEY"),
        session_id=os.getenv("VECTADB_SESSION_ID"),
        fail_silently=os.getenv("VECTADB_FAIL_SILENT", "true").lower() != "false",
        agents=agents or [],
    )
