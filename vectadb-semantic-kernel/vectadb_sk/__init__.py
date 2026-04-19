"""
vectadb-semantic-kernel — VectaDB observability and memory integration for
Microsoft Semantic Kernel.

Quick start::

    from vectadb_sk import VectaDBSKTracer, VectaDBPlugin, VectaDBVectorStore

    # Observability: wrap a kernel with a tracer
    with VectaDBSKTracer("http://localhost:8080", session_id="my-run") as tracer:
        tracer.register(kernel)
        result = await kernel.invoke(...)

    # Memory: search and store via the plugin
    plugin = VectaDBPlugin(base_url="http://localhost:8080")
    kernel.add_plugin(plugin, plugin_name="VectaDB")

    # Direct vector store access
    store = VectaDBVectorStore(base_url="http://localhost:8080")
    await store.upsert("doc-1", "VectaDB is a graph-vector hybrid DB.")
    results = await store.search("graph database")
"""

from .client import SyncVectaDBClient, VectaDBClient, VectaDBClientError
from .filters import VectaDBFunctionFilter
from .models import (
    BulkIngestionResponse,
    EventIngestionResponse,
    HealthResponse,
    SKEventType,
    VectaDBEvent,
    VectaDBSource,
    VectorSearchResult,
)
from .plugin import VectaDBPlugin
from .tracer import VectaDBSKTracer, create_tracer_from_env
from .vector_store import VectaDBVectorStore

__all__ = [
    # Tracer / orchestrator
    "VectaDBSKTracer",
    "create_tracer_from_env",
    # Filter
    "VectaDBFunctionFilter",
    # Plugin
    "VectaDBPlugin",
    # Vector store
    "VectaDBVectorStore",
    # Clients
    "VectaDBClient",
    "SyncVectaDBClient",
    "VectaDBClientError",
    # Models
    "SKEventType",
    "VectaDBEvent",
    "VectaDBSource",
    "VectorSearchResult",
    "BulkIngestionResponse",
    "EventIngestionResponse",
    "HealthResponse",
]

__version__ = "0.1.0"
