# VectaDB Python SDK

Official Python client library for **VectaDB** - The Observability Database for LLM Agents.

## Features

- 🔄 **Synchronous and Asynchronous** - Full support for both sync and async/await patterns
- 🎯 **Type-Safe** - Built with Pydantic for complete type safety and validation
- 📊 **Complete API Coverage** - All VectaDB features available
- 🚀 **Easy to Use** - Intuitive, Pythonic API design
- 📝 **Well Documented** - Comprehensive documentation and examples
- ✅ **Fully Tested** - Extensive test coverage

## Installation

```bash
pip install vectadb
```

## Quick Start

### Synchronous Usage

```python
from vectadb import VectaDB

# Initialize client
client = VectaDB(base_url="http://localhost:8080")

# Check server health
health = client.health()
print(f"Server status: {health.status}")

# Upload ontology schema
schema = {
    "namespace": "example",
    "version": "1.0.0",
    "entity_types": [
        {
            "id": "Person",
            "parent_type": None,
            "properties": {
                "name": {"type": "string", "required": True, "indexed": True},
                "email": {"type": "string", "required": False, "indexed": False}
            }
        }
    ],
    "relation_types": []
}
client.ontology.upload_schema(schema)

# Create an entity
person = client.entities.create(
    type="Person",
    properties={"name": "Alice", "email": "alice@example.com"}
)
print(f"Created entity: {person.id}")

# Query entities
results = client.queries.hybrid(
    vector_query={
        "query_text": "Alice",
        "entity_types": ["Person"],
        "limit": 10
    },
    merge_strategy="vector_only"
)
print(f"Found {len(results.results)} results")
```

### Asynchronous Usage

```python
import asyncio
from vectadb import AsyncVectaDB

async def main():
    async with AsyncVectaDB(base_url="http://localhost:8080") as client:
        # Check server health
        health = await client.health()
        print(f"Server status: {health.status}")

        # Upload schema
        schema = {...}
        await client.ontology.upload_schema(schema)

        # Create entity
        person = await client.entities.create(
            type="Person",
            properties={"name": "Bob"}
        )
        print(f"Created entity: {person.id}")

        # Query with concurrent operations
        task1 = client.entities.create(type="Person", properties={"name": "Alice"})
        task2 = client.entities.create(type="Person", properties={"name": "Charlie"})
        alice, charlie = await asyncio.gather(task1, task2)

asyncio.run(main())
```

## API Overview

### Client Initialization

```python
from vectadb import VectaDB, AsyncVectaDB

# Synchronous client
client = VectaDB(
    base_url="http://localhost:8080",
    api_key="your-api-key",  # Optional
    timeout=30.0  # Request timeout in seconds
)

# Asynchronous client
async_client = AsyncVectaDB(
    base_url="http://localhost:8080",
    api_key="your-api-key",
    timeout=30.0
)
```

### Ontology Management

```python
# Upload schema
schema = {...}
client.ontology.upload_schema(schema)

# Get current schema
schema = client.ontology.get_schema()

# Get entity type details
entity_type = client.ontology.get_entity_type("Person")

# Get subtypes
subtypes = client.ontology.get_subtypes("Animal")
```

### Entity Operations

```python
# Create entity
entity = client.entities.create(
    type="Person",
    properties={"name": "Alice", "role": "Engineer"}
)

# Get entity by ID
entity = client.entities.get(entity_id)

# Update entity
updated = client.entities.update(
    entity_id,
    properties={"name": "Alice", "role": "Senior Engineer"}
)

# Delete entity
client.entities.delete(entity_id)

# Validate entity
validation = client.entities.validate(
    type="Person",
    properties={"name": "Bob"}
)
if validation.valid:
    print("Entity is valid")
```

### Relation Operations

```python
# Create relation
relation = client.relations.create(
    type="knows",
    from_entity_id=person1_id,
    to_entity_id=person2_id,
    properties={"since": "2024"}
)

# Get relation
relation = client.relations.get(relation_id)

# Delete relation
client.relations.delete(relation_id)
```

### Hybrid Queries

```python
# Vector-only query
results = client.queries.hybrid(
    vector_query={
        "query_text": "machine learning expert",
        "entity_types": ["Person"],
        "limit": 10
    },
    merge_strategy="vector_only"
)

# Graph-only query
results = client.queries.hybrid(
    graph_query={
        "start_entity_id": person_id,
        "relation_types": ["knows"],
        "max_depth": 2
    },
    merge_strategy="graph_only"
)

# Hybrid query (vector + graph)
results = client.queries.hybrid(
    vector_query={
        "query_text": "AI researcher",
        "entity_types": ["Person"],
        "limit": 20
    },
    graph_query={
        "start_entity_id": person_id,
        "relation_types": ["works_with"],
        "max_depth": 1
    },
    merge_strategy="union"
)

# Process results
for result in results.results:
    print(f"Entity: {result.entity.id}, Score: {result.score}")

# Expand entity types
expanded = client.queries.expand_types(["Animal"])
# Returns: ["Animal", "Dog", "Cat", ...] (including subtypes)
```

### Event Ingestion (Agent Observability)

```python
from datetime import datetime

# Ingest single event
event = {
    "event_type": "agent.task.started",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "agent_id": "agent-123",
    "metadata": {
        "task_id": "task-456",
        "task_type": "data_analysis"
    }
}
response = client.events.ingest(event)
print(f"Event ID: {response.event_id}")

# Ingest batch of events
events = [
    {
        "event_type": "agent.llm.call",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent_id": "agent-123",
        "metadata": {"model": "gpt-4", "tokens": 150}
    },
    {
        "event_type": "agent.task.completed",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent_id": "agent-123",
        "metadata": {"duration_ms": 5000}
    }
]
response = client.events.ingest_batch(events)
print(f"Batch ID: {response.batch_id}, Successful: {response.successful}")
```

## Error Handling

```python
from vectadb.exceptions import (
    VectaDBError,
    ConnectionError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    ServerError,
    RateLimitError
)

try:
    entity = client.entities.get("non-existent-id")
except NotFoundError as e:
    print(f"Entity not found: {e.message}")
    print(f"Status code: {e.status_code}")

except ValidationError as e:
    print(f"Validation failed: {e.message}")
    print(f"Details: {e.details}")

except ConnectionError as e:
    print(f"Connection failed: {e.message}")

except VectaDBError as e:
    print(f"VectaDB error: {e.message}")
```

## Models

All API responses are returned as Pydantic models with full type safety:

```python
from vectadb.models import (
    Entity,
    Relation,
    OntologySchema,
    EntityType,
    ValidationResponse,
    HybridQueryResponse,
    QueryResult,
    Event,
    EventResponse
)

# Access model fields with autocomplete and type checking
entity = client.entities.get(entity_id)
print(entity.id)  # str
print(entity.type)  # str
print(entity.properties)  # Dict[str, Any]
print(entity.embedding)  # Optional[List[float]]
```

## Examples

See the `examples/` directory for complete working examples:

- `basic_usage.py` - Basic CRUD operations
- `async_usage.py` - Async operations with concurrent requests
- `event_ingestion.py` - Agent observability event tracking

## Development

### Setup

```bash
# Clone repository
git clone https://github.com/robertowilliams/vectadb.git
cd vectadb/vectadb-python

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=vectadb --cov-report=html

# Specific test file
pytest tests/test_client.py

# Async tests only
pytest tests/test_async_client.py -v
```

### Code Quality

```bash
# Format code
black vectadb/ tests/
isort vectadb/ tests/

# Lint
ruff check vectadb/ tests/

# Type check
mypy vectadb/
```

## Requirements

- Python 3.8 or later
- VectaDB server running (default: `http://localhost:8080`)

## Dependencies

- `httpx` - HTTP client with sync/async support
- `pydantic` - Data validation and type safety
- `python-dateutil` - Date/time utilities

## License

Apache License 2.0

## Links

- **Documentation**: https://vectadb.readthedocs.io
- **Repository**: https://github.com/robertowilliams/vectadb
- **Issues**: https://github.com/robertowilliams/vectadb/issues
- **VectaDB Server**: https://github.com/robertowilliams/vectadb

## Contributing

Contributions are welcome! Please see the [Development Guide](../vectadb/docs/DEVELOPMENT.md) for details.

## Support

For questions and support:
- Open an issue on GitHub
- Check the documentation
- Review the examples

---

**VectaDB Python SDK** - Making LLM agent observability easy with Python.
