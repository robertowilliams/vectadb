"""
VectaDB vector store implementation for Semantic Kernel.

Wraps VectaDB's REST API to act as a first-class SK VectorStore, supporting
upsert, get, search, and delete operations.  Every operation optionally emits
a MEMORY_READ, MEMORY_WRITE, or VECTOR_SEARCH event to VectaDB for full
observability of the retrieval pipeline.

Usage::

    store = VectaDBVectorStore(
        base_url="http://localhost:8080",
        collection="my_docs",
        session_id="sk-session-001",
    )
    await store.upsert("doc-1", "VectaDB is a graph-vector hybrid DB.", metadata={"tag": "db"})
    results = await store.search("graph database", n_results=5)
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any, Optional

from .client import VectaDBClient, VectaDBClientError
from .models import SKEventType, VectaDBEvent, VectorSearchResult, VectaDBSource

logger = logging.getLogger(__name__)


class VectaDBVectorStore:
    """
    Semantic Kernel-compatible vector store backed by VectaDB.

    Each mutating operation (upsert, delete) emits a MEMORY_WRITE event.
    Each read operation (get, search) emits a MEMORY_READ or VECTOR_SEARCH event.
    Events are queued and drained by VectaDBSKTracer.flush().
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        collection: str = "default",
        session_id: Optional[str] = None,
        agent_id: str = "semantic-kernel",
        fail_silently: bool = True,
        emit_events: bool = True,
    ):
        self._client = VectaDBClient(base_url=base_url, api_key=api_key)
        self.collection = collection
        self.session_id = session_id
        self.agent_id = agent_id
        self.fail_silently = fail_silently
        self.emit_events = emit_events
        self._queue: deque[VectaDBEvent] = deque()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> "VectaDBVectorStore":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def upsert(
        self,
        record_id: str,
        content: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
        entity_type: Optional[str] = None,
    ) -> str:
        """
        Insert or update a record in VectaDB.

        Sends a POST /api/v1/entities request.  Returns the record_id on success.
        """
        payload: dict[str, Any] = {
            "id": record_id,
            "content": content,
            "collection": self.collection,
        }
        if metadata:
            payload["metadata"] = metadata
        if entity_type:
            payload["entity_type"] = entity_type

        try:
            resp = await self._client._client.post("/api/v1/entities", json=payload)
            self._client._raise_for_status(resp)
        except VectaDBClientError as exc:
            if not self.fail_silently:
                raise
            logger.warning("VectaDB upsert failed (non-fatal): %s", exc)

        if self.emit_events:
            self._queue.append(
                VectaDBEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type=SKEventType.MEMORY_WRITE,
                    agent_id=self.agent_id,
                    session_id=self.session_id,
                    properties={
                        "operation": "upsert",
                        "record_id": record_id,
                        "collection": self.collection,
                        "content_length": len(content),
                        "metadata": metadata or {},
                    },
                    source=VectaDBSource(),
                )
            )
        return record_id

    async def delete(self, record_id: str) -> bool:
        """
        Delete a record from VectaDB by ID.

        Returns True if the record was deleted, False otherwise.
        """
        success = False
        try:
            resp = await self._client._client.delete(f"/api/v1/entities/{record_id}")
            success = resp.is_success
        except Exception as exc:
            if not self.fail_silently:
                raise
            logger.warning("VectaDB delete failed (non-fatal): %s", exc)

        if self.emit_events:
            self._queue.append(
                VectaDBEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type=SKEventType.MEMORY_WRITE,
                    agent_id=self.agent_id,
                    session_id=self.session_id,
                    properties={
                        "operation": "delete",
                        "record_id": record_id,
                        "collection": self.collection,
                        "success": success,
                    },
                    source=VectaDBSource(),
                )
            )
        return success

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get(self, record_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve a single record by ID.

        Returns the record dict or None if not found.
        """
        result: Optional[dict[str, Any]] = None
        found = False
        try:
            resp = await self._client._client.get(f"/api/v1/entities/{record_id}")
            if resp.is_success:
                result = resp.json()
                found = True
            elif resp.status_code == 404:
                result = None
            else:
                self._client._raise_for_status(resp)
        except VectaDBClientError as exc:
            if not self.fail_silently:
                raise
            logger.warning("VectaDB get failed (non-fatal): %s", exc)

        if self.emit_events:
            self._queue.append(
                VectaDBEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type=SKEventType.MEMORY_READ,
                    agent_id=self.agent_id,
                    session_id=self.session_id,
                    properties={
                        "operation": "get",
                        "record_id": record_id,
                        "collection": self.collection,
                        "found": found,
                    },
                    source=VectaDBSource(),
                )
            )
        return result

    async def search(
        self,
        query: str,
        *,
        n_results: int = 5,
        min_score: float = 0.0,
        entity_type: Optional[str] = None,
    ) -> list[VectorSearchResult]:
        """
        Run a hybrid semantic + keyword search against VectaDB.

        Returns results ordered by descending relevance score.
        """
        results: list[VectorSearchResult] = []
        try:
            results = await self._client.search(
                query,
                n_results=n_results,
                min_score=min_score,
                entity_type=entity_type,
            )
        except VectaDBClientError as exc:
            if not self.fail_silently:
                raise
            logger.warning("VectaDB search failed (non-fatal): %s", exc)

        if self.emit_events:
            self._queue.append(
                VectaDBEvent(
                    timestamp=datetime.now(timezone.utc),
                    event_type=SKEventType.VECTOR_SEARCH,
                    agent_id=self.agent_id,
                    session_id=self.session_id,
                    properties={
                        "query": query,
                        "n_results": n_results,
                        "collection": self.collection,
                        "results_returned": len(results),
                        "top_score": results[0].score if results else None,
                    },
                    source=VectaDBSource(),
                )
            )
        return results

    # ------------------------------------------------------------------
    # Event queue
    # ------------------------------------------------------------------

    def drain_queue(self) -> list[VectaDBEvent]:
        """Remove and return all queued events."""
        events: list[VectaDBEvent] = []
        while self._queue:
            try:
                events.append(self._queue.popleft())
            except IndexError:
                break
        return events
