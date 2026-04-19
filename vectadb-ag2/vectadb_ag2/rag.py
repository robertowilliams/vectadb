"""
VectaDBRetriever — AG2-compatible retriever backed by VectaDB hybrid search.

Replaces ChromaDB / local vector stores in AG2 RAG pipelines with VectaDB's
unified vector + graph query endpoint (POST /api/v1/query/hybrid).

Standalone usage::

    from vectadb_ag2 import VectaDBRetriever

    retriever = VectaDBRetriever(
        vectadb_url="http://localhost:8080",
        entity_type="Document",
        n_results=5,
    )
    docs = retriever.retrieve("What is RAG?")
    # [{"content": "...", "id": "...", "score": 0.92, "metadata": {...}}, ...]

With AG2's RetrieveUserProxyAgent::

    from autogen.agentchat.contrib.retrieve_user_proxy_agent import (
        RetrieveUserProxyAgent,
    )
    retriever = VectaDBRetriever(vectadb_url="http://localhost:8080")

    ragproxy = RetrieveUserProxyAgent(
        name="ragproxy",
        retrieve_config=retriever.as_retrieve_config(),
    )
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

import httpx

from .models import AG2EventType, VectaDBEvent, VectaDBSource

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


class VectaDBRetrieverError(Exception):
    """Raised when VectaDB returns an error during retrieval."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class VectaDBRetriever:
    """
    Retrieves documents from VectaDB using hybrid (vector + graph) search.

    Designed for use in AG2 RAG pipelines as a drop-in replacement for
    ChromaDB or other vector stores. Results are returned in a format
    compatible with AG2's RetrieveUserProxyAgent.

    Parameters
    ----------
    vectadb_url:
        Base URL of the VectaDB REST API.
    api_key:
        Optional API key sent as X-API-Key header.
    entity_type:
        VectaDB entity type to search within (default: "Document").
    n_results:
        Default number of results to return per query.
    fail_silently:
        If True, retrieval errors return empty results instead of raising.
    session_id:
        Optional session ID for event provenance.
    emit_events:
        If True and an event_queue list is provided, emit RETRIEVE_START /
        RETRIEVE_END events into it for upstream tracer collection.
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        vectadb_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        entity_type: str = "Document",
        n_results: int = 5,
        fail_silently: bool = True,
        session_id: Optional[str] = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ):
        self.vectadb_url = vectadb_url.rstrip("/")
        self.entity_type = entity_type
        self.n_results = n_results
        self.fail_silently = fail_silently
        self.session_id = session_id or f"ag2-rag-{uuid.uuid4().hex[:8]}"

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key

        self._client = httpx.Client(
            base_url=self.vectadb_url,
            headers=headers,
            timeout=timeout,
        )

        # Event queue shared with an upstream tracer if desired
        self._event_queue: list[VectaDBEvent] = []

    # ------------------------------------------------------------------
    # Primary retrieval API
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        n_results: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Query VectaDB and return matching documents.

        Returns a list of dicts with keys:
            ``id``, ``content``, ``score``, ``entity_type``, ``metadata``

        Parameters
        ----------
        query:
            Natural-language query string.
        n_results:
            Number of results (overrides instance default).
        """
        top_k = n_results or self.n_results
        start = time.monotonic()

        self._emit(
            AG2EventType.RETRIEVE_START,
            {"query": query, "top_k": top_k, "entity_type": self.entity_type},
        )

        try:
            resp = self._client.post(
                "/api/v1/query/hybrid",
                json={
                    "query": query,
                    "entity_type": self.entity_type,
                    "top_k": top_k,
                },
            )
            _raise_for_status(resp)
            data = resp.json()
            results = self._parse_results(data)

            duration_ms = round((time.monotonic() - start) * 1000, 2)
            self._emit(
                AG2EventType.RETRIEVE_END,
                {
                    "query": query,
                    "result_count": len(results),
                    "duration_ms": duration_ms,
                },
            )
            return results

        except (httpx.RequestError, VectaDBRetrieverError) as exc:
            logger.warning("VectaDB retrieval failed: %s", exc)
            if self.fail_silently:
                return []
            raise

    def retrieve_as_chromadb(
        self,
        query_texts: list[str],
        n_results: int,
        **_: Any,
    ) -> dict[str, list[list[Any]]]:
        """
        ChromaDB-compatible interface for AG2's RetrieveUserProxyAgent.

        Returns a dict with keys ``ids``, ``documents``, ``metadatas`` where
        each value is a list-of-lists (one inner list per query).

        This can be used as a custom ``query_vector_db`` override::

            ragproxy._retrieve_config["customized_answer_prefix"] = ...
        """
        ids: list[list[str]] = []
        documents: list[list[str]] = []
        metadatas: list[list[dict]] = []

        for query in query_texts:
            docs = self.retrieve(query, n_results=n_results)
            ids.append([d["id"] for d in docs])
            documents.append([d["content"] for d in docs])
            metadatas.append([d.get("metadata", {}) for d in docs])

        return {"ids": ids, "documents": documents, "metadatas": metadatas}

    # ------------------------------------------------------------------
    # AG2 integration helpers
    # ------------------------------------------------------------------

    def as_retrieve_config(
        self,
        task: str = "qa",
        chunk_token_size: int = 2000,
    ) -> dict[str, Any]:
        """
        Return a ``retrieve_config`` dict for AG2's RetrieveUserProxyAgent.

        Usage::

            ragproxy = RetrieveUserProxyAgent(
                name="ragproxy",
                retrieve_config=retriever.as_retrieve_config(),
            )

        Note: AG2 will skip its own embedding/chunking pipeline when
        ``vector_db`` is set to ``"custom"`` and ``docs_path`` is empty.
        """
        retriever = self

        def custom_query(query_texts, n_results, **kwargs):
            return retriever.retrieve_as_chromadb(query_texts, n_results)

        return {
            "task": task,
            "vector_db": "custom",
            "docs_path": [],
            "chunk_token_size": chunk_token_size,
            "customized_answer_prefix": "",
            "get_or_create": True,
            "db_config": {"client": custom_query},
        }

    # ------------------------------------------------------------------
    # Event emission (for integration with VectaDBAG2Tracer)
    # ------------------------------------------------------------------

    def drain_queue(self) -> list[VectaDBEvent]:
        """Return and clear any retrieval events queued for the tracer."""
        events, self._event_queue = self._event_queue, []
        return events

    def _emit(self, event_type: AG2EventType, properties: dict[str, Any]) -> None:
        event = VectaDBEvent(
            timestamp=_now(),
            event_type=event_type.value,
            session_id=self.session_id,
            properties={"framework": "ag2", **properties},
            source=VectaDBSource(
                system="ag2",
                log_group="ag2/retriever",
                log_stream=self.session_id,
                log_id=str(uuid.uuid4()),
            ),
        )
        self._event_queue.append(event)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_results(data: Any) -> list[dict[str, Any]]:
        """
        Normalise VectaDB's hybrid query response into a flat list of dicts.

        VectaDB returns either:
          - A list of QueryResult objects (``{"id": ..., "score": ..., "entity": {...}}``)
          - Or a dict with a ``results`` key
        """
        if isinstance(data, list):
            raw = data
        elif isinstance(data, dict):
            raw = data.get("results") or data.get("entities") or []
        else:
            return []

        out: list[dict[str, Any]] = []
        for item in raw:
            entity = item.get("entity") or item
            props = entity.get("properties") or {}
            content = (
                props.get("content")
                or props.get("text")
                or props.get("body")
                or str(props)
            )
            out.append(
                {
                    "id": str(item.get("id") or entity.get("id") or ""),
                    "content": content,
                    "score": float(item.get("score") or 0.0),
                    "entity_type": entity.get("entity_type", ""),
                    "metadata": {
                        k: v
                        for k, v in props.items()
                        if k not in ("content", "text", "body")
                    },
                }
            )
        return out

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "VectaDBRetriever":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    try:
        detail = response.json()
        msg = detail.get("message") or detail.get("error") or str(detail)
    except Exception:
        msg = response.text
    raise VectaDBRetrieverError(
        f"VectaDB API error {response.status_code}: {msg}",
        status_code=response.status_code,
    )
