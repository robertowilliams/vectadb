"""
VectaDB data models for Semantic Kernel audit events.

Maps SK function invocation, memory, and vector search lifecycle events to
VectaDB's event ingestion schema, aligned with the W3C PROV provenance standard
used throughout VectaDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Event type taxonomy
# ---------------------------------------------------------------------------

class SKEventType(str, Enum):
    """Typed event taxonomy aligned with VectaDB's ontology for Semantic Kernel runs."""

    # Kernel function lifecycle
    FUNCTION_INVOKED = "function_invoked"   # SK function completed successfully
    FUNCTION_ERROR = "function_error"       # SK function raised an exception

    # Prompt rendering
    PROMPT_RENDERED = "prompt_rendered"     # Prompt template rendered with variables

    # Memory / vector store
    MEMORY_READ = "memory_read"             # Vector store get / search operation
    MEMORY_WRITE = "memory_write"           # Vector store upsert / delete operation
    VECTOR_SEARCH = "vector_search"         # Semantic similarity search result


# ---------------------------------------------------------------------------
# Pydantic models matching VectaDB's EventIngestionRequest schema
# ---------------------------------------------------------------------------

class VectaDBSource(BaseModel):
    """Source metadata — identifies where this event originated."""
    system: str = "semantic_kernel"
    log_group: str = "semantic_kernel"
    log_stream: str = "default"
    log_id: str = ""


class VectaDBEvent(BaseModel):
    """
    Single event for VectaDB's /api/v1/events endpoint.

    Each event maps to a typed entity in the VectaDB ontology graph and
    optionally carries a vector embedding for semantic similarity search.
    """
    trace_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    properties: dict[str, Any] = Field(default_factory=dict)
    source: Optional[VectaDBSource] = None

    model_config = {"populate_by_name": True}

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize to the exact shape VectaDB's REST API expects."""
        data: dict[str, Any] = {
            "timestamp": self.timestamp.isoformat(),
            "properties": self.properties,
        }
        if self.trace_id is not None:
            data["trace_id"] = self.trace_id
        if self.event_type is not None:
            data["event_type"] = self.event_type
        if self.agent_id is not None:
            data["agent_id"] = self.agent_id
        if self.session_id is not None:
            data["session_id"] = self.session_id
        if self.source is not None:
            data["source"] = self.source.model_dump()
        return data


class BulkIngestionOptions(BaseModel):
    auto_create_traces: bool = True
    generate_embeddings: bool = True
    extract_relationships: bool = False


class BulkIngestionRequest(BaseModel):
    events: list[VectaDBEvent]
    options: BulkIngestionOptions = Field(default_factory=BulkIngestionOptions)

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "events": [e.to_api_dict() for e in self.events],
            "options": self.options.model_dump(),
        }


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class EventIngestionResponse(BaseModel):
    event_id: str
    trace_id: str
    created_at: datetime


class BulkIngestionError(BaseModel):
    index: int
    error: str


class BulkIngestionResponse(BaseModel):
    ingested: int
    failed: int
    trace_ids: list[str] = Field(default_factory=list)
    errors: list[BulkIngestionError] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    version: str
    ontology_loaded: bool
    ontology_namespace: Optional[str] = None
    ontology_version: Optional[str] = None


# ---------------------------------------------------------------------------
# Vector store models
# ---------------------------------------------------------------------------

class VectorSearchResult(BaseModel):
    """A single result from a VectaDB hybrid or semantic search."""
    id: str
    content: str
    score: float = 0.0
    entity_type: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
