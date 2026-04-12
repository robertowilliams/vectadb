"""
VectaDB data models for CrewAI audit events.

Maps CrewAI lifecycle events to VectaDB's event ingestion schema,
which aligns with the W3C PROV provenance standard used throughout VectaDB.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Event type taxonomy — mirrors VectaDB's ontology layer
# ---------------------------------------------------------------------------

class CrewEventType(str, Enum):
    """Typed event taxonomy aligned with VectaDB's ontology for CrewAI runs."""

    # Crew-level lifecycle
    CREW_START = "crew_start"
    CREW_END = "crew_end"
    CREW_ERROR = "crew_error"

    # Agent-level lifecycle
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    AGENT_ACTION = "agent_action"        # A single ReAct-style reasoning step

    # Task-level lifecycle
    TASK_START = "task_start"
    TASK_END = "task_end"
    TASK_ERROR = "task_error"

    # LLM interactions (prompt → response provenance)
    LLM_START = "llm_start"
    LLM_END = "llm_end"
    LLM_ERROR = "llm_error"
    LLM_TOKEN = "llm_token"             # Streaming token (sampled, not every token)

    # Tool use (evidence / tool-call provenance)
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"

    # Chain / retrieval
    CHAIN_START = "chain_start"
    CHAIN_END = "chain_end"
    CHAIN_ERROR = "chain_error"

    # Retrieval (RAG evidence)
    RETRIEVAL_START = "retrieval_start"
    RETRIEVAL_END = "retrieval_end"


# ---------------------------------------------------------------------------
# Pydantic models matching VectaDB's EventIngestionRequest schema
# ---------------------------------------------------------------------------

class VectaDBSource(BaseModel):
    """Source metadata — identifies where this event originated."""
    system: str = "crewai"
    log_group: str = "crewai"
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
# Internal run-state tracking
# ---------------------------------------------------------------------------

class AgentRunState(BaseModel):
    """Tracks mutable state for a single agent within a crew run."""
    agent_id: str
    role: str
    session_id: str
    trace_id: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool_call_count: int = 0
    llm_call_count: int = 0
    action_sequence: int = 0


class CrewRunState(BaseModel):
    """Top-level state for a complete crew kickoff."""
    session_id: str
    crew_name: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agents: dict[str, AgentRunState] = Field(default_factory=dict)
    active_trace_id: Optional[str] = None
    task_trace_map: dict[str, str] = Field(default_factory=dict)  # task_key → trace_id

    @model_validator(mode="after")
    def _validate(self) -> "CrewRunState":
        return self
