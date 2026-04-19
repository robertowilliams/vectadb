"""
VectaDBTracer — standalone LangChain observability tracer.

Wraps any LangChain Runnable (LCEL chain, agent, etc.) as a context manager
and automatically attaches VectaDBCallbackHandler to capture the full audit
trail without modifying the chain definition.

Usage (context manager)::

    from vectadb_langchain import VectaDBTracer

    tracer = VectaDBTracer(vectadb_url="http://localhost:8080")
    with tracer:
        result = chain.invoke(
            {"question": "What is RAG?"},
            config={"callbacks": [tracer.callback_handler]},
        )
    print(tracer.session_id)  # query VectaDB for this session's audit trail

Usage (async context manager)::

    async with VectaDBTracer(vectadb_url="http://localhost:8080") as tracer:
        result = await chain.ainvoke(
            {"question": "What is RAG?"},
            config={"callbacks": [tracer.callback_handler]},
        )
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from .callbacks import VectaDBCallbackHandler, _safe_str
from .client import SyncVectaDBClient, VectaDBClient, VectaDBClientError
from .models import RunState, VectaDBEvent, VectaDBSource

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VectaDBTracer:
    """
    Instruments a LangChain Runnable to emit audit events to VectaDB.

    Parameters
    ----------
    vectadb_url:
        Base URL of the VectaDB REST API (default: http://localhost:8080).
    api_key:
        Optional API key sent as X-API-Key header.
    session_id:
        Explicit session ID. Auto-generated UUID if not provided.
    run_name:
        Human-readable label for this run (used in VectaDB metadata).
    framework:
        Framework label embedded in every event property (default: "langchain").
    batch_size:
        Number of events per bulk ingestion request.
    generate_embeddings:
        Ask VectaDB to generate vector embeddings for each event.
    auto_create_traces:
        Ask VectaDB to auto-create trace records from session_id.
    fail_silently:
        If True, VectaDB connectivity problems will be logged but never
        propagate to crash the caller (recommended for production).
    """

    def __init__(
        self,
        vectadb_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        session_id: Optional[str] = None,
        run_name: str = "langchain_run",
        framework: str = "langchain",
        batch_size: int = 100,
        generate_embeddings: bool = True,
        auto_create_traces: bool = True,
        fail_silently: bool = True,
    ):
        self.vectadb_url = vectadb_url
        self.api_key = api_key
        self.run_name = run_name
        self.framework = framework
        self.generate_embeddings = generate_embeddings
        self.auto_create_traces = auto_create_traces
        self.fail_silently = fail_silently

        self._session_id: str = session_id or f"lc-{uuid.uuid4().hex[:12]}"
        self._run_state: Optional[RunState] = None
        self._start_time: Optional[float] = None

        self._client = SyncVectaDBClient(
            base_url=vectadb_url,
            api_key=api_key,
            batch_size=batch_size,
        )

        self._handler = VectaDBCallbackHandler(
            session_id=self._session_id,
            framework=framework,
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        """The session ID for this tracer instance."""
        return self._session_id

    @property
    def callback_handler(self) -> VectaDBCallbackHandler:
        """
        Pass this to chain.invoke(config={"callbacks": [tracer.callback_handler]}).
        """
        return self._handler

    # ------------------------------------------------------------------
    # Context-manager support (sync)
    # ------------------------------------------------------------------

    def __enter__(self) -> "VectaDBTracer":
        self._begin()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._end(error=exc_val)
        self._client.close()

    # ------------------------------------------------------------------
    # Context-manager support (async)
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "VectaDBTracer":
        self._begin()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Flush remaining events via the sync client (runs on background thread)
        self._end(error=exc_val)
        self._client.close()

    # ------------------------------------------------------------------
    # Manual flush (for use outside context manager)
    # ------------------------------------------------------------------

    def flush(self, error: Optional[BaseException] = None) -> None:
        """
        Drain the callback handler queue and send all events to VectaDB.

        Call this if you are not using the context manager pattern.
        """
        self._end(error=error)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def _begin(self) -> None:
        self._start_time = time.monotonic()
        self._run_state = RunState(
            session_id=self._session_id,
            run_name=self.run_name,
        )
        logger.info(
            "VectaDB tracer starting run '%s' [session=%s, framework=%s]",
            self.run_name,
            self._session_id,
            self.framework,
        )

    def _end(self, error: Optional[BaseException] = None) -> None:
        duration_ms = (
            round((time.monotonic() - self._start_time) * 1000, 2)
            if self._start_time
            else None
        )

        # Drain remaining handler events
        queued = self._handler.drain_queue()

        if queued:
            logger.info(
                "VectaDB tracer flushing %d queued events [session=%s]",
                len(queued),
                self._session_id,
            )
            self._ingest_bulk(queued)

        if error is not None:
            logger.info(
                "VectaDB tracer run '%s' ended with error after %.0fms [session=%s]: %s",
                self.run_name,
                duration_ms or 0,
                self._session_id,
                _safe_str(error),
            )
        else:
            logger.info(
                "VectaDB tracer run '%s' completed in %.0fms [session=%s]",
                self.run_name,
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
            self._handle_error(exc)

    def _handle_error(self, exc: Exception) -> None:
        if self.fail_silently:
            logger.warning("VectaDB ingestion error (non-fatal): %s", exc)
        else:
            raise exc


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_tracer_from_env() -> VectaDBTracer:
    """
    Create a VectaDBTracer from environment variables.

    Variables:
        VECTADB_URL          — VectaDB base URL (default: http://localhost:8080)
        VECTADB_API_KEY      — Optional API key
        VECTADB_SESSION_ID   — Optional explicit session ID
        VECTADB_RUN_NAME     — Run name label (default: langchain_run)
        VECTADB_FAIL_SILENT  — "false" to let errors propagate (default: true)
    """
    import os

    return VectaDBTracer(
        vectadb_url=os.getenv("VECTADB_URL", "http://localhost:8080"),
        api_key=os.getenv("VECTADB_API_KEY"),
        session_id=os.getenv("VECTADB_SESSION_ID"),
        run_name=os.getenv("VECTADB_RUN_NAME", "langchain_run"),
        fail_silently=os.getenv("VECTADB_FAIL_SILENT", "true").lower() != "false",
    )
