"""
VectaDBSKTracer — context manager for end-to-end Semantic Kernel observability.

Attaches a VectaDBFunctionFilter to a Kernel, buffers events from all
registered filters and vector stores, and bulk-ingests them to VectaDB on
flush() / __exit__.

Usage (sync context manager)::

    with VectaDBSKTracer("http://localhost:8080", session_id="sk-run-001") as tracer:
        tracer.register(kernel)
        result = kernel.invoke(...)
    # Events are flushed automatically on __exit__

Usage (async context manager)::

    async with VectaDBSKTracer("http://localhost:8080") as tracer:
        tracer.register(kernel)
        result = await kernel.invoke_async(...)

Usage (manual)::

    tracer = VectaDBSKTracer.create_from_env()
    tracer.register(kernel)
    # … run your kernel …
    tracer.flush()
    tracer.close()

Environment variables (create_from_env / create_tracer_from_env)::

    VECTADB_URL          VectaDB base URL     (default: http://localhost:8080)
    VECTADB_API_KEY      Optional API key
    VECTADB_SESSION_ID   Explicit session ID  (default: auto-generated)
    VECTADB_FAIL_SILENT  "false" to raise     (default: true)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Optional

from .client import SyncVectaDBClient, VectaDBClient
from .filters import VectaDBFunctionFilter
from .models import VectaDBEvent
from .vector_store import VectaDBVectorStore

logger = logging.getLogger(__name__)


class VectaDBSKTracer:
    """
    Orchestrator for VectaDB observability across a Semantic Kernel session.

    Responsibilities:
      - Generate / accept a session_id for the run
      - Create and register a VectaDBFunctionFilter with the kernel
      - Optionally accept VectaDBVectorStore instances for store-level events
      - Flush all queued events to VectaDB via bulk ingestion
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        session_id: Optional[str] = None,
        agent_id: str = "semantic-kernel",
        auto_create_traces: bool = True,
        generate_embeddings: bool = True,
        fail_silently: bool = True,
    ):
        self.session_id: str = session_id or f"sk-{uuid.uuid4().hex[:12]}"
        self.agent_id = agent_id
        self.fail_silently = fail_silently
        self._auto_create_traces = auto_create_traces
        self._generate_embeddings = generate_embeddings

        self._sync_client = SyncVectaDBClient(
            base_url=base_url,
            api_key=api_key,
        )

        self._filters: list[VectaDBFunctionFilter] = []
        self._stores: list[VectaDBVectorStore] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, kernel: Any) -> VectaDBFunctionFilter:
        """
        Create a VectaDBFunctionFilter and register it with the given kernel.

        ``kernel`` is expected to be a semantic_kernel.Kernel instance, but
        we use duck typing so no import of semantic-kernel is required.

        Returns the filter so callers can store a reference if needed.
        """
        f = VectaDBFunctionFilter(
            session_id=self.session_id,
            agent_id=self.agent_id,
            fail_silently=self.fail_silently,
        )
        try:
            kernel.add_filter("function_invocation", f)
        except Exception as exc:
            logger.warning("Could not register filter with kernel: %s", exc)
        self._filters.append(f)
        return f

    def attach_store(self, store: VectaDBVectorStore) -> None:
        """
        Register a VectaDBVectorStore so its events are included in flush().

        Call this after constructing a store to ensure memory read/write events
        are captured alongside function invocation events.
        """
        self._stores.append(store)

    # ------------------------------------------------------------------
    # Event collection and ingestion
    # ------------------------------------------------------------------

    def _collect_events(self) -> list[VectaDBEvent]:
        events: list[VectaDBEvent] = []
        for f in self._filters:
            events.extend(f.drain_queue())
        for s in self._stores:
            events.extend(s.drain_queue())
        return events

    def flush(self) -> int:
        """
        Drain all event queues and bulk-ingest into VectaDB.

        Returns the number of events successfully ingested.
        """
        events = self._collect_events()
        if not events:
            return 0

        result = self._sync_client.ingest_events_bulk(
            events,
            auto_create_traces=self._auto_create_traces,
            generate_embeddings=self._generate_embeddings,
        )
        if result is None:
            logger.warning("VectaDB bulk ingestion returned None")
            return 0

        logger.info(
            "VectaDB flush: %d ingested, %d failed (session=%s)",
            result.ingested,
            result.failed,
            self.session_id,
        )
        return result.ingested

    def close(self) -> None:
        """Flush remaining events and close the underlying HTTP client."""
        try:
            self.flush()
        except Exception as exc:
            logger.warning("Error during final flush: %s", exc)
        self._sync_client.close()

    # ------------------------------------------------------------------
    # Sync context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "VectaDBSKTracer":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "VectaDBSKTracer":
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def create_from_env(cls) -> "VectaDBSKTracer":
        """
        Create a tracer using configuration from environment variables.

        VECTADB_URL          VectaDB base URL     (default: http://localhost:8080)
        VECTADB_API_KEY      Optional API key
        VECTADB_SESSION_ID   Explicit session ID  (default: auto-generated)
        VECTADB_FAIL_SILENT  "false" to raise on errors (default: true)
        """
        return cls(
            base_url=os.environ.get("VECTADB_URL", "http://localhost:8080"),
            api_key=os.environ.get("VECTADB_API_KEY") or None,
            session_id=os.environ.get("VECTADB_SESSION_ID") or None,
            fail_silently=os.environ.get("VECTADB_FAIL_SILENT", "true").lower() != "false",
        )


# Public alias matching the naming convention of other vectadb-* packages
create_tracer_from_env = VectaDBSKTracer.create_from_env
