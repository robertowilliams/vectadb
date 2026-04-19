"""
Async HTTP client for the VectaDB REST API.

Mirrors the Rust VectaDBClient in vectadb-agents/cloudwatch/src/vectadb_client.rs
but implemented in Python using httpx for async support.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Optional

import httpx

from .models import (
    BulkIngestionRequest,
    BulkIngestionResponse,
    EventIngestionResponse,
    HealthResponse,
    VectaDBEvent,
    BulkIngestionOptions,
)

logger = logging.getLogger(__name__)


class VectaDBClientError(Exception):
    """Raised when the VectaDB API returns an error response."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class VectaDBClient:
    """
    Async HTTP client wrapping VectaDB's REST API.

    Usage::

        async with VectaDBClient("http://localhost:8080") as client:
            ok = await client.health_check()
            await client.ingest_event(event)
    """

    DEFAULT_TIMEOUT = 30.0       # seconds
    DEFAULT_BATCH_SIZE = 100
    MAX_RETRIES = 3

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.batch_size = batch_size

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "VectaDBClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> HealthResponse:
        """Return VectaDB health status. Raises VectaDBClientError on failure."""
        try:
            resp = await self._client.get("/health")
            self._raise_for_status(resp)
            return HealthResponse.model_validate(resp.json())
        except httpx.RequestError as exc:
            raise VectaDBClientError(f"Connection error: {exc}") from exc

    async def is_healthy(self) -> bool:
        """Return True if VectaDB is reachable and healthy, False otherwise."""
        try:
            health = await self.health_check()
            return health.status == "healthy"
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------

    async def ingest_event(
        self,
        event: VectaDBEvent,
        *,
        generate_embeddings: bool = True,
    ) -> EventIngestionResponse:
        """Ingest a single event and return the created event + trace IDs."""
        try:
            resp = await self._client.post(
                "/api/v1/events",
                json=event.to_api_dict(),
            )
            self._raise_for_status(resp)
            return EventIngestionResponse.model_validate(resp.json())
        except httpx.RequestError as exc:
            raise VectaDBClientError(f"Connection error: {exc}") from exc

    async def ingest_events_bulk(
        self,
        events: list[VectaDBEvent],
        *,
        auto_create_traces: bool = True,
        generate_embeddings: bool = True,
        extract_relationships: bool = False,
    ) -> BulkIngestionResponse:
        """
        Ingest a list of events in bulk, with automatic batching and retries.

        Mirrors the batching + retry logic from the Rust cloudwatch agent.
        """
        if not events:
            return BulkIngestionResponse(ingested=0, failed=0)

        options = BulkIngestionOptions(
            auto_create_traces=auto_create_traces,
            generate_embeddings=generate_embeddings,
            extract_relationships=extract_relationships,
        )

        # Split into batches
        batches = [
            events[i : i + self.batch_size]
            for i in range(0, len(events), self.batch_size)
        ]
        logger.debug(
            "Ingesting %d events in %d batch(es)", len(events), len(batches)
        )

        total_ingested = 0
        total_failed = 0
        all_trace_ids: list[str] = []
        all_errors: list[Any] = []

        for batch_idx, batch in enumerate(batches):
            request = BulkIngestionRequest(events=batch, options=options)
            result = await self._send_bulk_with_retry(
                request, batch_idx=batch_idx, batch_size=len(batch)
            )
            total_ingested += result.ingested
            total_failed += result.failed
            for tid in result.trace_ids:
                if tid not in all_trace_ids:
                    all_trace_ids.append(tid)
            for err in result.errors:
                all_errors.append(err)

        return BulkIngestionResponse(
            ingested=total_ingested,
            failed=total_failed,
            trace_ids=all_trace_ids,
            errors=all_errors,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _send_bulk_with_retry(
        self,
        request: BulkIngestionRequest,
        *,
        batch_idx: int,
        batch_size: int,
    ) -> BulkIngestionResponse:
        """Send a bulk ingestion request with exponential-backoff retries."""
        import asyncio

        last_exc: Optional[Exception] = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = await self._client.post(
                    "/api/v1/events/batch",
                    json=request.to_api_dict(),
                )
                self._raise_for_status(resp)
                result = BulkIngestionResponse.model_validate(resp.json())
                if result.failed > 0:
                    logger.warning(
                        "Batch %d: %d succeeded, %d failed",
                        batch_idx,
                        result.ingested,
                        result.failed,
                    )
                return result
            except (httpx.RequestError, VectaDBClientError) as exc:
                last_exc = exc
                logger.warning(
                    "Batch %d attempt %d/%d failed: %s",
                    batch_idx,
                    attempt,
                    self.MAX_RETRIES,
                    exc,
                )
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(2 ** (attempt - 1))

        # All retries exhausted — mark entire batch as failed
        logger.error(
            "Batch %d failed after %d retries: %s",
            batch_idx,
            self.MAX_RETRIES,
            last_exc,
        )
        from .models import BulkIngestionError
        errors = [
            BulkIngestionError(
                index=i,
                error=f"Batch failed after {self.MAX_RETRIES} retries: {last_exc}",
            )
            for i in range(batch_size)
        ]
        return BulkIngestionResponse(
            ingested=0, failed=batch_size, errors=errors
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            detail = response.json()
            msg = detail.get("message") or detail.get("error") or str(detail)
        except Exception:
            msg = response.text
        raise VectaDBClientError(
            f"VectaDB API error {response.status_code}: {msg}",
            status_code=response.status_code,
        )


# ---------------------------------------------------------------------------
# Synchronous wrapper (for non-async LangChain usage)
# ---------------------------------------------------------------------------

class SyncVectaDBClient:
    """
    Synchronous wrapper around VectaDBClient backed by a persistent background
    asyncio event loop on a daemon thread.

    Why this is better than the previous asyncio.run()-per-call approach:
      - A single httpx connection pool is created once and reused for every call,
        eliminating TCP handshake overhead on each event.
      - No event-loop setup/teardown per call — coroutines are submitted to the
        already-running background loop via asyncio.run_coroutine_threadsafe().
      - The background thread is a daemon, so it won't block process exit even if
        close() is never called.

    Thread safety: all async operations are serialised through the single event
    loop; callers block on future.result() so the public methods are safe to call
    from any thread.
    """

    _INIT_TIMEOUT = 10.0   # seconds to wait for the client to initialise
    _CALL_TIMEOUT = 30.0   # default per-call timeout

    def __init__(self, **kwargs: Any):
        self._kwargs = kwargs
        self._async_client: Optional[VectaDBClient] = None
        self._closed = False

        # Start a dedicated event loop on a daemon background thread
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            name="vectadb-sync-client",
            daemon=True,
        )
        self._thread.start()

        # Initialise the async client on the background loop
        future = asyncio.run_coroutine_threadsafe(self._init_client(), self._loop)
        try:
            future.result(timeout=self._INIT_TIMEOUT)
        except Exception as exc:
            logger.warning("VectaDB async client init failed: %s", exc)

    async def _init_client(self) -> None:
        self._async_client = VectaDBClient(**self._kwargs)

    # ------------------------------------------------------------------
    # Internal dispatch helper
    # ------------------------------------------------------------------

    def _run(self, coro: Any, timeout: float = _CALL_TIMEOUT) -> Any:
        """Submit a coroutine to the background loop and block until done."""
        if self._closed or self._async_client is None:
            raise VectaDBClientError("SyncVectaDBClient is closed or not initialised")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    # ------------------------------------------------------------------
    # Public API (mirrors VectaDBClient)
    # ------------------------------------------------------------------

    def ingest_event(
        self, event: VectaDBEvent, **kw: Any
    ) -> Optional[EventIngestionResponse]:
        try:
            return self._run(self._async_client.ingest_event(event, **kw))  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("VectaDB ingest_event failed (non-fatal): %s", exc)
            return None

    def ingest_events_bulk(
        self, events: list[VectaDBEvent], **kw: Any
    ) -> Optional[BulkIngestionResponse]:
        if not events:
            return BulkIngestionResponse(ingested=0, failed=0)
        try:
            return self._run(self._async_client.ingest_events_bulk(events, **kw))  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("VectaDB ingest_events_bulk failed (non-fatal): %s", exc)
            return None

    def is_healthy(self) -> bool:
        try:
            return self._run(self._async_client.is_healthy())  # type: ignore[union-attr]
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """
        Gracefully close the underlying async HTTP client and stop the
        background event loop.  Safe to call multiple times.
        """
        if self._closed:
            return
        self._closed = True

        if self._async_client is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    self._async_client.close(), self._loop
                ).result(timeout=5.0)
            except Exception as exc:
                logger.debug("Error closing async client: %s", exc)

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5.0)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
