"""VectaDB data models."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Ontology Models
# ============================================================================

class PropertyDefinition(BaseModel):
    """Property definition for an entity type."""

    name: str
    property_type: str
    required: bool = False
    description: Optional[str] = None


class EntityType(BaseModel):
    """Entity type definition."""

    id: str
    label: str
    description: Optional[str] = None
    parent: Optional[str] = None
    properties: List[PropertyDefinition] = Field(default_factory=list)


class RelationType(BaseModel):
    """Relation type definition."""

    id: str
    label: str
    domain: str  # Source entity type
    range: str  # Target entity type
    description: Optional[str] = None
    inverse: Optional[str] = None


class OntologySchema(BaseModel):
    """Complete ontology schema."""

    namespace: str
    version: str
    entity_types: List[EntityType] = Field(default_factory=list)
    relation_types: List[RelationType] = Field(default_factory=list)


# ============================================================================
# Entity & Relation Models
# ============================================================================

class Entity(BaseModel):
    """Entity model."""

    id: Optional[str] = None
    type: str
    properties: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Relation(BaseModel):
    """Relation model."""

    id: Optional[str] = None
    type: str
    from_entity_id: str
    to_entity_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


# ============================================================================
# Validation Models
# ============================================================================

class ValidationRequest(BaseModel):
    """Entity validation request."""

    type: str
    properties: Dict[str, Any]


class ValidationResponse(BaseModel):
    """Validation response."""

    valid: bool
    errors: List[str] = Field(default_factory=list)


# ============================================================================
# Query Models
# ============================================================================

class VectorQuery(BaseModel):
    """Vector similarity query."""

    query_text: str
    entity_types: List[str]
    top_k: int = 10
    min_score: Optional[float] = None


class GraphQuery(BaseModel):
    """Graph traversal query."""

    start_entity_types: List[str]
    relation_types: Optional[List[str]] = None
    traversal_direction: str = "outgoing"  # outgoing, incoming, both
    max_depth: int = 2


class HybridQueryRequest(BaseModel):
    """Hybrid query combining vector and graph."""

    vector_query: Optional[VectorQuery] = None
    graph_query: Optional[GraphQuery] = None
    merge_strategy: str = "union"  # union, intersection, vector_prioritized, graph_prioritized


class QueryResult(BaseModel):
    """Query result."""

    entity_id: str
    type: str
    properties: Dict[str, Any]
    vector_score: Optional[float] = None
    graph_path_length: Optional[int] = None


class HybridQueryResponse(BaseModel):
    """Hybrid query response."""

    results: List[QueryResult]
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Event Ingestion Models
# ============================================================================

class Event(BaseModel):
    """Event for observability."""

    trace_id: Optional[str] = None
    timestamp: datetime
    event_type: Optional[str] = None
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    properties: Dict[str, Any]
    source: Optional[Dict[str, Any]] = None


class EventBatch(BaseModel):
    """Batch of events."""

    events: List[Event]


class EventResponse(BaseModel):
    """Event ingestion response."""

    event_id: str
    trace_id: Optional[str] = None
    status: str


class EventBatchResponse(BaseModel):
    """Batch event ingestion response."""

    ingested_count: int
    failed_count: int
    event_ids: List[str]


# ============================================================================
# Health Check
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: Optional[str] = None
    timestamp: Optional[datetime] = None
