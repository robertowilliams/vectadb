"""VectaDB Python SDK.

The official Python client for VectaDB - The Observability Database for LLM Agents.

Basic usage:
    >>> from vectadb import VectaDB
    >>> client = VectaDB(base_url="http://localhost:8080")
    >>>
    >>> # Upload ontology schema
    >>> schema = {
    ...     "namespace": "example",
    ...     "version": "1.0.0",
    ...     "entity_types": [...]
    ... }
    >>> client.ontology.upload_schema(schema)
    >>>
    >>> # Create an entity
    >>> entity = client.entities.create(
    ...     type="Person",
    ...     properties={"name": "Alice", "role": "Researcher"}
    ... )
    >>>
    >>> # Perform hybrid query
    >>> results = client.queries.hybrid(
    ...     vector_query={"query_text": "machine learning", "entity_types": ["Person"]},
    ...     merge_strategy="vector_prioritized"
    ... )

Async usage:
    >>> import asyncio
    >>> from vectadb import AsyncVectaDB
    >>>
    >>> async def main():
    ...     async with AsyncVectaDB(base_url="http://localhost:8080") as client:
    ...         entity = await client.entities.create(
    ...             type="Person",
    ...             properties={"name": "Bob"}
    ...         )
    ...         print(entity)
    >>>
    >>> asyncio.run(main())
"""

from vectadb.client import VectaDB
from vectadb.async_client import AsyncVectaDB
from vectadb.models import (
    Entity,
    Relation,
    OntologySchema,
    EntityType,
    RelationType,
    HybridQueryRequest,
    QueryResult,
)
from vectadb.exceptions import (
    VectaDBError,
    ConnectionError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
)

__version__ = "0.1.0"
__all__ = [
    # Clients
    "VectaDB",
    "AsyncVectaDB",
    # Models
    "Entity",
    "Relation",
    "OntologySchema",
    "EntityType",
    "RelationType",
    "HybridQueryRequest",
    "QueryResult",
    # Exceptions
    "VectaDBError",
    "ConnectionError",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
]
