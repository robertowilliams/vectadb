"""
VectaDB Semantic Kernel plugin.

Exposes VectaDB's search and memory capabilities as native SK kernel functions
that can be called from prompts, plans, or other kernel functions.

Usage::

    from vectadb_sk import VectaDBPlugin

    plugin = VectaDBPlugin(base_url="http://localhost:8080", collection="docs")

    # Register with a kernel (without semantic-kernel installed)
    # kernel.add_plugin(plugin, plugin_name="VectaDB")

    # Or call directly
    results = await plugin.search("what is VectaDB?", n_results=3)
    await plugin.store("doc-1", "VectaDB is a graph-vector hybrid database.")
    record = await plugin.get("doc-1")
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .client import VectaDBClient, VectaDBClientError
from .models import VectorSearchResult

logger = logging.getLogger(__name__)


# We define our own thin decorator so callers don't need semantic-kernel at
# import time.  When SK IS installed, `kernel.add_plugin(plugin)` will pick
# up the real `@kernel_function` metadata from SK.  When SK is not installed,
# our stub decorator is a no-op that just preserves the docstring.
try:
    from semantic_kernel.functions import kernel_function  # type: ignore[import-not-found]
except ImportError:
    def kernel_function(  # type: ignore[misc]
        description: str = "",
        name: Optional[str] = None,
    ):
        """Stub @kernel_function decorator used when semantic-kernel is absent."""
        def decorator(fn):  # type: ignore[misc]
            fn.__kernel_function__ = True
            fn.__kernel_function_description__ = description
            fn.__kernel_function_name__ = name or fn.__name__
            return fn
        return decorator


class VectaDBPlugin:
    """
    Semantic Kernel plugin exposing VectaDB search and memory operations.

    All methods are decorated with @kernel_function so SK can:
      - Discover them via introspection when added with kernel.add_plugin()
      - Invoke them from plans and prompts
      - Pass them as tool definitions to LLMs

    The plugin owns its own VectaDBClient and can be used standalone (no
    Kernel required) for direct async calls.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        collection: str = "default",
        fail_silently: bool = True,
    ):
        self._client = VectaDBClient(base_url=base_url, api_key=api_key)
        self.collection = collection
        self.fail_silently = fail_silently

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.close()

    async def __aenter__(self) -> "VectaDBPlugin":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Kernel functions
    # ------------------------------------------------------------------

    @kernel_function(
        description=(
            "Search VectaDB for documents semantically similar to the query. "
            "Returns a newline-separated list of matching document contents."
        ),
        name="search",
    )
    async def search(
        self,
        query: str,
        n_results: int = 5,
        min_score: float = 0.0,
        entity_type: Optional[str] = None,
    ) -> str:
        """
        Run a hybrid semantic + keyword search.

        Returns a newline-separated string of matching content snippets suitable
        for injecting into a prompt context.
        """
        try:
            results: list[VectorSearchResult] = await self._client.search(
                query,
                n_results=n_results,
                min_score=min_score,
                entity_type=entity_type,
            )
            if not results:
                return "No results found."
            lines = [
                f"[{i + 1}] (score={r.score:.3f}) {r.content}"
                for i, r in enumerate(results)
            ]
            return "\n".join(lines)
        except VectaDBClientError as exc:
            if not self.fail_silently:
                raise
            logger.warning("VectaDB search failed (non-fatal): %s", exc)
            return "Search unavailable."

    @kernel_function(
        description=(
            "Store a document in VectaDB with the given ID and content. "
            "Returns the stored document ID."
        ),
        name="store",
    )
    async def store(
        self,
        record_id: str,
        content: str,
        entity_type: Optional[str] = None,
    ) -> str:
        """Insert or update a document in VectaDB.  Returns the record ID."""
        try:
            payload: dict[str, Any] = {
                "id": record_id,
                "content": content,
                "collection": self.collection,
            }
            if entity_type:
                payload["entity_type"] = entity_type

            resp = await self._client._client.post("/api/v1/entities", json=payload)
            self._client._raise_for_status(resp)
            return record_id
        except VectaDBClientError as exc:
            if not self.fail_silently:
                raise
            logger.warning("VectaDB store failed (non-fatal): %s", exc)
            return f"Failed to store {record_id}: {exc}"

    @kernel_function(
        description=(
            "Retrieve a document from VectaDB by its ID. "
            "Returns the document content or an empty string if not found."
        ),
        name="get",
    )
    async def get(self, record_id: str) -> str:
        """Retrieve a single document by ID.  Returns the content string."""
        try:
            resp = await self._client._client.get(f"/api/v1/entities/{record_id}")
            if resp.status_code == 404:
                return ""
            self._client._raise_for_status(resp)
            data = resp.json()
            # Handle various response shapes
            if isinstance(data, dict):
                return str(
                    data.get("content")
                    or data.get("properties", {}).get("content")
                    or data
                )
            return str(data)
        except VectaDBClientError as exc:
            if not self.fail_silently:
                raise
            logger.warning("VectaDB get failed (non-fatal): %s", exc)
            return ""

    @kernel_function(
        description="Search VectaDB and return structured result objects.",
        name="search_structured",
    )
    async def search_structured(
        self,
        query: str,
        n_results: int = 5,
    ) -> list[VectorSearchResult]:
        """
        Like search() but returns a list of VectorSearchResult objects rather
        than a formatted string.  Useful for programmatic consumption.
        """
        try:
            return await self._client.search(query, n_results=n_results)
        except VectaDBClientError as exc:
            if not self.fail_silently:
                raise
            logger.warning("VectaDB search_structured failed (non-fatal): %s", exc)
            return []
