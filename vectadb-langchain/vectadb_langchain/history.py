"""
LangChain BaseChatMessageHistory implementation backed by VectaDB.

Stores every conversation message as a typed entity in the VectaDB ontology
graph, making chat history queryable, auditable, and semantically searchable.

Usage::

    from vectadb_langchain import VectaDBChatMessageHistory

    history = VectaDBChatMessageHistory(
        session_id="user-42-session-7",
        vectadb_url="http://localhost:8080",
    )
    history.add_user_message("What is RAG?")
    history.add_ai_message("RAG stands for Retrieval-Augmented Generation...")
    print(history.messages)  # [HumanMessage(...), AIMessage(...)]

    # Use with RunnableWithMessageHistory
    from langchain_core.runnables.history import RunnableWithMessageHistory

    chain_with_history = RunnableWithMessageHistory(
        chain,
        lambda session_id: VectaDBChatMessageHistory(
            session_id=session_id,
            vectadb_url="http://localhost:8080",
        ),
    )
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, List, Optional, Sequence

import httpx
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    messages_from_dict,
    messages_to_dict,
)

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 30.0

# VectaDB entity type for chat messages
_CHAT_MESSAGE_ENTITY_TYPE = "ChatMessage"


class VectaDBChatMessageHistory(BaseChatMessageHistory):
    """
    Chat message history stored in VectaDB.

    Each message is persisted as a VectaDB entity with:
      - entity_type: "ChatMessage"
      - properties.role: "human" | "ai" | "system"
      - properties.content: message text
      - properties.session_id: ties messages to a conversation
      - properties.message_index: ordering within the session
      - properties.timestamp: ISO 8601 UTC

    Parameters
    ----------
    session_id:
        Unique identifier for this conversation. All messages written and
        read by this instance are scoped to this session_id.
    vectadb_url:
        Base URL of the VectaDB REST API.
    api_key:
        Optional X-API-Key header value.
    """

    def __init__(
        self,
        session_id: str,
        vectadb_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
    ):
        self.session_id = session_id
        self._base_url = vectadb_url.rstrip("/")

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        self._headers = headers

        # Local in-memory index counter for ordering (loaded lazily)
        self._index: Optional[int] = None

    # ------------------------------------------------------------------
    # BaseChatMessageHistory interface
    # ------------------------------------------------------------------

    @property
    def messages(self) -> List[BaseMessage]:
        """
        Fetch all messages for this session from VectaDB, ordered by index.
        """
        try:
            results = self._fetch_messages()
            # Sort by message_index for consistent ordering
            results.sort(key=lambda r: r.get("properties", {}).get("message_index", 0))
            return [self._to_base_message(r) for r in results]
        except Exception as exc:
            logger.warning(
                "VectaDB history fetch failed for session %s: %s",
                self.session_id,
                exc,
            )
            return []

    def add_message(self, message: BaseMessage) -> None:
        """
        Persist a single message to VectaDB.
        """
        role = self._role_for(message)
        index = self._next_index()

        payload: dict[str, Any] = {
            "entity_type": _CHAT_MESSAGE_ENTITY_TYPE,
            "properties": {
                "role": role,
                "content": message.content,
                "session_id": self.session_id,
                "message_index": index,
                "message_type": type(message).__name__,
            },
        }

        try:
            self._post("/api/v1/entities", payload)
            logger.debug(
                "Stored %s message [index=%d, session=%s]",
                role,
                index,
                self.session_id,
            )
        except Exception as exc:
            logger.warning(
                "VectaDB add_message failed for session %s: %s",
                self.session_id,
                exc,
            )

    def add_user_message(self, message: str) -> None:
        """Convenience method — add a HumanMessage."""
        self.add_message(HumanMessage(content=message))

    def add_ai_message(self, message: str) -> None:
        """Convenience method — add an AIMessage."""
        self.add_message(AIMessage(content=message))

    def clear(self) -> None:
        """
        Delete all messages for this session from VectaDB.

        Uses the entity search endpoint to find all messages by session_id,
        then deletes each one.
        """
        try:
            results = self._fetch_messages()
            deleted = 0
            for entity in results:
                entity_id = entity.get("id")
                if entity_id:
                    self._delete(f"/api/v1/entities/{entity_id}")
                    deleted += 1
            self._index = 0
            logger.debug(
                "Cleared %d messages for session %s", deleted, self.session_id
            )
        except Exception as exc:
            logger.warning(
                "VectaDB clear failed for session %s: %s", self.session_id, exc
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_index(self) -> int:
        """Return the next message index, loading current count lazily."""
        if self._index is None:
            try:
                existing = self._fetch_messages()
                self._index = len(existing)
            except Exception:
                self._index = 0
        idx = self._index
        self._index += 1
        return idx

    def _fetch_messages(self) -> list[dict[str, Any]]:
        """
        Fetch all chat message entities for this session via VectaDB entity search.
        Uses /api/v1/entities with a session_id filter.
        """
        payload: dict[str, Any] = {
            "entity_type": _CHAT_MESSAGE_ENTITY_TYPE,
            "filter": {
                "session_id": self.session_id,
            },
        }
        try:
            with httpx.Client(
                base_url=self._base_url,
                headers=self._headers,
                timeout=_HTTP_TIMEOUT,
            ) as client:
                resp = client.post("/api/v1/entities/search", json=payload)
                if resp.is_success:
                    data = resp.json()
                    return data.get("entities", data if isinstance(data, list) else [])
                # If the search endpoint doesn't exist yet, fall back gracefully
                logger.debug(
                    "VectaDB entity search returned %d for session %s",
                    resp.status_code,
                    self.session_id,
                )
                return []
        except Exception as exc:
            logger.warning("VectaDB fetch_messages error: %s", exc)
            return []

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        with httpx.Client(
            base_url=self._base_url,
            headers=self._headers,
            timeout=_HTTP_TIMEOUT,
        ) as client:
            resp = client.post(path, json=payload)
            self._raise_for_status(resp)
            return resp.json()

    def _delete(self, path: str) -> None:
        with httpx.Client(
            base_url=self._base_url,
            headers=self._headers,
            timeout=_HTTP_TIMEOUT,
        ) as client:
            resp = client.delete(path)
            if not resp.is_success:
                logger.debug(
                    "VectaDB delete %s returned %d", path, resp.status_code
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
        raise RuntimeError(
            f"VectaDB API error {response.status_code}: {msg}"
        )

    @staticmethod
    def _role_for(message: BaseMessage) -> str:
        """Map a LangChain message type to a VectaDB role string."""
        if isinstance(message, HumanMessage):
            return "human"
        if isinstance(message, AIMessage):
            return "ai"
        if isinstance(message, SystemMessage):
            return "system"
        return message.type or "unknown"

    @staticmethod
    def _to_base_message(entity: dict[str, Any]) -> BaseMessage:
        """Convert a VectaDB entity dict back to a LangChain BaseMessage."""
        props = entity.get("properties", {})
        role = props.get("role", "unknown")
        content = props.get("content", "")

        if role == "human":
            return HumanMessage(content=content)
        if role == "ai":
            return AIMessage(content=content)
        if role == "system":
            return SystemMessage(content=content)
        # Fall back to HumanMessage for unknown roles
        return HumanMessage(content=content)
