"""
vectadb-ag2 — VectaDB observability and RAG integration for AG2 (AutoGen).

Public API
----------
VectaDBLoggingHook
    Attaches to any ConversableAgent and emits typed audit events.

VectaDBAG2Tracer
    Multi-agent context manager — instruments agents and flushes to VectaDB.

VectaDBRetriever
    Hybrid-search retriever for AG2 RAG pipelines (replaces ChromaDB).

create_tracer_from_env
    Build a VectaDBAG2Tracer from VECTADB_* environment variables.

AG2EventType
    Enum of all event types emitted by this package.

VectaDBEvent
    Pydantic model for a single VectaDB audit event.
"""

from .hooks import VectaDBLoggingHook
from .models import AG2EventType, VectaDBEvent
from .rag import VectaDBRetriever, VectaDBRetrieverError
from .tracer import VectaDBAG2Tracer, create_tracer_from_env

__all__ = [
    "VectaDBLoggingHook",
    "VectaDBAG2Tracer",
    "VectaDBRetriever",
    "VectaDBRetrieverError",
    "create_tracer_from_env",
    "AG2EventType",
    "VectaDBEvent",
]

__version__ = "0.1.0"
