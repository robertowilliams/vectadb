"""
LangChain VectorStore implementation backed by VectaDB.

VectaDB wraps Qdrant under the hood, so this store gets semantic vector search
*and* a full ontology-aware audit trail for every document added or retrieved —
in a single store.

Usage::

    from vectadb_langchain import VectaDBVectorStore

    store = VectaDBVectorStore(
        vectadb_url="http://localhost:8080",
        collection="my_docs",
    )
    store.add_texts(["LangChain is a framework...", "VectaDB stores..."])
    docs = store.similarity_search("what is langchain?", k=3)

    # Drop into any LCEL chain as a retriever
    retriever = store.as_retriever(search_kwargs={"k": 5})
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Iterable, List, Optional, Tuple, Type

import httpx
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

logger = logging.getLogger(__name__)

# Timeout for all VectaDB HTTP calls from this module
_HTTP_TIMEOUT = 30.0


class VectaDBVectorStore(VectorStore):
    """
    LangChain VectorStore backed by VectaDB's hybrid vector+graph API.

    VectaDB handles embedding server-side using its configured provider
    (local sentence-transformers, OpenAI, Cohere, etc.), so you do not need
    to pass an Embeddings object for most operations. The ``embedding``
    parameter in ``from_texts`` is accepted for interface compatibility but
    is not called client-side — vectors are computed by the VectaDB backend.

    Parameters
    ----------
    vectadb_url:
        Base URL of the VectaDB REST API.
    collection:
        Qdrant collection name to store and retrieve documents from.
    api_key:
        Optional X-API-Key header value.
    entity_type:
        VectaDB ontology entity type for stored documents (default: "Document").
    similarity_threshold:
        Minimum similarity score for returned results (0.0–1.0).
    """

    def __init__(
        self,
        vectadb_url: str = "http://localhost:8080",
        collection: str = "documents",
        api_key: Optional[str] = None,
        entity_type: str = "Document",
        similarity_threshold: float = 0.0,
    ):
        self._base_url = vectadb_url.rstrip("/")
        self.collection = collection
        self.entity_type = entity_type
        self.similarity_threshold = similarity_threshold

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        self._headers = headers

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(
            base_url=self._base_url,
            headers=self._headers,
            timeout=_HTTP_TIMEOUT,
        ) as client:
            resp = client.post(path, json=payload)
            self._raise_for_status(resp)
            return resp.json()

    def _delete(self, path: str) -> dict[str, Any]:
        with httpx.Client(
            base_url=self._base_url,
            headers=self._headers,
            timeout=_HTTP_TIMEOUT,
        ) as client:
            resp = client.delete(path)
            self._raise_for_status(resp)
            return resp.json() if resp.content else {}

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        try:
            detail = response.json()
            msg = detail.get("message") or detail.get("error") or str(detail)
        except Exception:
            msg = response.text
        raise RuntimeError(
            f"VectaDB API error {response.status_code}: {msg}"
        )

    # ------------------------------------------------------------------
    # VectorStore interface
    # ------------------------------------------------------------------

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """
        Add texts to the VectaDB store. VectaDB generates embeddings server-side.

        Returns a list of document IDs (one per text).
        """
        texts_list = list(texts)
        if not texts_list:
            return []

        generated_ids: list[str] = []

        for i, text in enumerate(texts_list):
            doc_id = (ids[i] if ids and i < len(ids) else None) or str(uuid.uuid4())
            meta = (metadatas[i] if metadatas and i < len(metadatas) else None) or {}

            payload: dict[str, Any] = {
                "entity_type": self.entity_type,
                "properties": {
                    "content": text,
                    "collection": self.collection,
                    "doc_id": doc_id,
                    **meta,
                },
            }

            try:
                result = self._post("/api/v1/entities", payload)
                stored_id = result.get("id") or doc_id
                generated_ids.append(str(stored_id))
            except Exception as exc:
                logger.warning(
                    "VectaDB add_texts: failed to store document %d: %s", i, exc
                )
                generated_ids.append(doc_id)

        return generated_ids

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """
        Return the top-k documents most similar to the query.

        VectaDB performs hybrid (vector + graph) search server-side.
        """
        results = self._hybrid_search(query, k=k, filter=filter)
        return [self._to_document(r) for r in results]

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """
        Return the top-k documents with their similarity scores.
        """
        results = self._hybrid_search(query, k=k, filter=filter)
        return [(self._to_document(r), r.get("score", 0.0)) for r in results]

    def delete(self, ids: Optional[List[str]] = None, **kwargs: Any) -> Optional[bool]:
        """
        Delete documents by their IDs.

        Returns True on success, False if any deletion failed.
        """
        if not ids:
            return True

        success = True
        for doc_id in ids:
            try:
                self._delete(f"/api/v1/entities/{doc_id}")
            except Exception as exc:
                logger.warning(
                    "VectaDB delete: failed to delete entity %s: %s", doc_id, exc
                )
                success = False

        return success

    # ------------------------------------------------------------------
    # Classmethod constructors (required by VectorStore ABC)
    # ------------------------------------------------------------------

    @classmethod
    def from_texts(
        cls: Type["VectaDBVectorStore"],
        texts: List[str],
        embedding: Embeddings,
        metadatas: Optional[List[dict]] = None,
        vectadb_url: str = "http://localhost:8080",
        collection: str = "documents",
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> "VectaDBVectorStore":
        """
        Create a VectaDBVectorStore from a list of texts.

        The ``embedding`` parameter is accepted for LangChain interface
        compatibility. Actual vector computation is delegated to VectaDB's
        configured embedding provider.
        """
        store = cls(
            vectadb_url=vectadb_url,
            collection=collection,
            api_key=api_key,
            **{k: v for k, v in kwargs.items() if k in ("entity_type", "similarity_threshold")},
        )
        store.add_texts(texts, metadatas=metadatas)
        return store

    @classmethod
    def from_documents(
        cls: Type["VectaDBVectorStore"],
        documents: List[Document],
        embedding: Embeddings,
        vectadb_url: str = "http://localhost:8080",
        collection: str = "documents",
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> "VectaDBVectorStore":
        """
        Create a VectaDBVectorStore from LangChain Document objects.
        """
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        return cls.from_texts(
            texts=texts,
            embedding=embedding,
            metadatas=metadatas,
            vectadb_url=vectadb_url,
            collection=collection,
            api_key=api_key,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Internal search helper
    # ------------------------------------------------------------------

    def _hybrid_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
    ) -> list[dict[str, Any]]:
        """
        Call VectaDB's /api/v1/query/hybrid endpoint and return raw result dicts.
        """
        payload: dict[str, Any] = {
            "query": query,
            "collection": self.collection,
            "limit": k,
        }
        if self.similarity_threshold > 0.0:
            payload["threshold"] = self.similarity_threshold
        if filter:
            payload["filter"] = filter

        try:
            response = self._post("/api/v1/query/hybrid", payload)
            return response.get("results", [])
        except Exception as exc:
            logger.warning("VectaDB similarity_search failed: %s", exc)
            return []

    @staticmethod
    def _to_document(result: dict[str, Any]) -> Document:
        """Convert a VectaDB search result dict to a LangChain Document."""
        properties = result.get("properties", {})
        content = properties.pop("content", result.get("content", ""))
        # Remove internal VectaDB fields from metadata
        for internal_key in ("collection", "doc_id"):
            properties.pop(internal_key, None)
        metadata = {
            **properties,
            "vectadb_id": result.get("id"),
            "score": result.get("score"),
        }
        return Document(page_content=content, metadata=metadata)

    # ------------------------------------------------------------------
    # Required abstract method stub
    # ------------------------------------------------------------------

    def _embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Not used — embeddings are computed server-side by VectaDB.
        Implemented to satisfy the abstract base class contract.
        """
        raise NotImplementedError(
            "VectaDBVectorStore delegates embedding to the VectaDB server. "
            "Call add_texts() directly instead of _embed_documents()."
        )

    def _embed_query(self, text: str) -> List[float]:
        """
        Not used — query embedding is computed server-side by VectaDB.
        Implemented to satisfy the abstract base class contract.
        """
        raise NotImplementedError(
            "VectaDBVectorStore delegates query embedding to the VectaDB server. "
            "Call similarity_search() directly instead of _embed_query()."
        )
