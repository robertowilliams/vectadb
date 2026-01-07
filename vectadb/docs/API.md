# VectaDB API Documentation

**Version**: 0.1.0
**Base URL**: `http://localhost:8080`
**Last Updated**: January 7, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Health Check](#health-check)
4. [Ontology Management](#ontology-management)
5. [Entity Validation](#entity-validation)
6. [Query Expansion](#query-expansion)
7. [Entity Operations](#entity-operations)
8. [Relation Operations](#relation-operations)
9. [Hybrid Queries](#hybrid-queries)
10. [Event Ingestion](#event-ingestion)
11. [Error Responses](#error-responses)
12. [Examples](#examples)

---

## Overview

VectaDB provides a RESTful API for managing ontologies, entities, relations, and performing hybrid graph-vector queries.

### Key Features

- ✅ Type-safe ontology management
- ✅ Entity and relation validation
- ✅ Semantic similarity search (vector)
- ✅ Graph traversal queries
- ✅ Hybrid query coordination
- ✅ Event ingestion for observability

### API Versioning

All endpoints are prefixed with `/api/v1/` for version 1.

---

## Authentication

**Current Status**: No authentication required (development mode)

**Future**: API key authentication via header:
```
Authorization: Bearer <api_key>
```

---

## Health Check

### GET /health

Check if the API server is running and healthy.

**Response**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-01-07T12:00:00Z"
}
```

**Status Codes**:
- `200` - Service is healthy
- `503` - Service unavailable

**Example**:
```bash
curl http://localhost:8080/health
```

---

## Ontology Management

### POST /api/v1/ontology/schema

Upload an ontology schema in JSON or YAML format.

**Request Body** (JSON):
```json
{
  "namespace": "example",
  "version": "1.0.0",
  "entity_types": [
    {
      "id": "Person",
      "label": "Person",
      "description": "A human being",
      "properties": [
        {
          "name": "name",
          "property_type": "String",
          "required": true
        }
      ]
    }
  ],
  "relation_types": [
    {
      "id": "knows",
      "label": "Knows",
      "domain": "Person",
      "range": "Person"
    }
  ]
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Schema uploaded successfully"
}
```

**Status Codes**:
- `200` - Schema uploaded successfully
- `400` - Invalid schema format
- `422` - Schema validation failed

---

### GET /api/v1/ontology/schema

Retrieve the currently loaded ontology schema.

**Response**:
```json
{
  "namespace": "example",
  "version": "1.0.0",
  "entity_types": [...],
  "relation_types": [...]
}
```

**Status Codes**:
- `200` - Schema retrieved
- `404` - No schema loaded

---

### GET /api/v1/ontology/types/:type_id

Get details about a specific entity type.

**Path Parameters**:
- `type_id` - Entity type identifier

**Response**:
```json
{
  "id": "Person",
  "label": "Person",
  "description": "A human being",
  "properties": [...]
}
```

**Status Codes**:
- `200` - Type found
- `404` - Type not found

---

### GET /api/v1/ontology/types/:type_id/subtypes

Get all subtypes of a specific entity type.

**Path Parameters**:
- `type_id` - Entity type identifier

**Response**:
```json
{
  "type_id": "Person",
  "subtypes": ["Student", "Teacher", "Employee"]
}
```

**Status Codes**:
- `200` - Subtypes retrieved
- `404` - Type not found

---

## Entity Validation

### POST /api/v1/validate/entity

Validate an entity against the ontology schema.

**Request Body**:
```json
{
  "type": "Person",
  "properties": {
    "name": "John Doe",
    "age": 30
  }
}
```

**Response** (Success):
```json
{
  "valid": true
}
```

**Response** (Failure):
```json
{
  "valid": false,
  "errors": [
    "Missing required property: email",
    "Property 'age' has wrong type: expected String, got Number"
  ]
}
```

**Status Codes**:
- `200` - Validation completed
- `400` - Invalid request format

---

### POST /api/v1/validate/relation

Validate a relation against the ontology schema.

**Request Body**:
```json
{
  "type": "knows",
  "from_entity_type": "Person",
  "to_entity_type": "Person"
}
```

**Response**:
```json
{
  "valid": true
}
```

**Status Codes**:
- `200` - Validation completed
- `400` - Invalid request format

---

## Query Expansion

### POST /api/v1/query/expand

Expand entity types using ontology hierarchy.

**Request Body**:
```json
{
  "entity_types": ["Person"]
}
```

**Response**:
```json
{
  "original_types": ["Person"],
  "expanded_types": ["Person", "Student", "Teacher", "Employee"]
}
```

**Status Codes**:
- `200` - Expansion successful
- `404` - No schema loaded

---

### POST /api/v1/query/compatible_relations

Get compatible relations for entity types.

**Request Body**:
```json
{
  "from_type": "Person",
  "to_type": "Company"
}
```

**Response**:
```json
{
  "compatible_relations": ["works_at", "founded"]
}
```

**Status Codes**:
- `200` - Relations retrieved
- `404` - No schema loaded

---

## Entity Operations

### POST /api/v1/entities

Create a new entity.

**Request Body**:
```json
{
  "type": "Person",
  "properties": {
    "name": "John Doe",
    "email": "john@example.com",
    "age": 30
  }
}
```

**Response**:
```json
{
  "id": "person_123abc",
  "type": "Person",
  "properties": {...},
  "created_at": "2026-01-07T12:00:00Z"
}
```

**Status Codes**:
- `201` - Entity created
- `400` - Invalid entity data
- `422` - Validation failed

---

### GET /api/v1/entities/:id

Retrieve an entity by ID.

**Path Parameters**:
- `id` - Entity identifier

**Response**:
```json
{
  "id": "person_123abc",
  "type": "Person",
  "properties": {...},
  "created_at": "2026-01-07T12:00:00Z",
  "updated_at": "2026-01-07T12:30:00Z"
}
```

**Status Codes**:
- `200` - Entity found
- `404` - Entity not found

---

### PUT /api/v1/entities/:id

Update an existing entity.

**Path Parameters**:
- `id` - Entity identifier

**Request Body**:
```json
{
  "properties": {
    "name": "John Smith",
    "age": 31
  }
}
```

**Response**:
```json
{
  "id": "person_123abc",
  "type": "Person",
  "properties": {...},
  "updated_at": "2026-01-07T13:00:00Z"
}
```

**Status Codes**:
- `200` - Entity updated
- `404` - Entity not found
- `422` - Validation failed

---

### DELETE /api/v1/entities/:id

Delete an entity.

**Path Parameters**:
- `id` - Entity identifier

**Response**:
```json
{
  "status": "deleted",
  "id": "person_123abc"
}
```

**Status Codes**:
- `200` - Entity deleted
- `404` - Entity not found

---

## Relation Operations

### POST /api/v1/relations

Create a new relation between entities.

**Request Body**:
```json
{
  "type": "knows",
  "from_entity_id": "person_123",
  "to_entity_id": "person_456",
  "properties": {
    "since": "2020-01-01",
    "strength": 0.8
  }
}
```

**Response**:
```json
{
  "id": "relation_789xyz",
  "type": "knows",
  "from_entity_id": "person_123",
  "to_entity_id": "person_456",
  "properties": {...},
  "created_at": "2026-01-07T12:00:00Z"
}
```

**Status Codes**:
- `201` - Relation created
- `400` - Invalid relation data
- `422` - Validation failed

---

### GET /api/v1/relations/:id

Retrieve a relation by ID.

**Path Parameters**:
- `id` - Relation identifier

**Response**:
```json
{
  "id": "relation_789xyz",
  "type": "knows",
  "from_entity_id": "person_123",
  "to_entity_id": "person_456",
  "properties": {...}
}
```

**Status Codes**:
- `200` - Relation found
- `404` - Relation not found

---

### DELETE /api/v1/relations/:id

Delete a relation.

**Path Parameters**:
- `id` - Relation identifier

**Response**:
```json
{
  "status": "deleted",
  "id": "relation_789xyz"
}
```

**Status Codes**:
- `200` - Relation deleted
- `404` - Relation not found

---

## Hybrid Queries

### POST /api/v1/query/hybrid

Execute a hybrid query combining vector similarity and graph traversal.

**Request Body**:
```json
{
  "vector_query": {
    "query_text": "machine learning researcher",
    "entity_types": ["Person"],
    "top_k": 10,
    "min_score": 0.7
  },
  "graph_query": {
    "start_entity_types": ["Person"],
    "relation_types": ["works_at", "collaborated_with"],
    "traversal_direction": "outgoing",
    "max_depth": 2
  },
  "merge_strategy": "union"
}
```

**Response**:
```json
{
  "results": [
    {
      "entity_id": "person_123",
      "type": "Person",
      "properties": {...},
      "vector_score": 0.92,
      "graph_path_length": 1
    }
  ],
  "metadata": {
    "total_results": 15,
    "vector_results": 10,
    "graph_results": 8,
    "execution_time_ms": 45
  }
}
```

**Merge Strategies**:
- `union` - Combine all results (default)
- `intersection` - Only results in both
- `vector_prioritized` - Rank by vector score
- `graph_prioritized` - Rank by graph distance

**Status Codes**:
- `200` - Query successful
- `400` - Invalid query format
- `422` - Query execution failed

---

## Event Ingestion

### POST /api/v1/events

Ingest a single event for observability.

**Request Body**:
```json
{
  "trace_id": "trace_abc123",
  "timestamp": "2026-01-07T12:00:00Z",
  "event_type": "tool_call",
  "agent_id": "agent_456",
  "session_id": "session_789",
  "properties": {
    "tool_name": "calculator",
    "input": "2 + 2",
    "output": "4",
    "duration_ms": 15
  },
  "source": {
    "system": "langchain",
    "log_group": "/aws/lambda/my-agent"
  }
}
```

**Response**:
```json
{
  "event_id": "event_xyz789",
  "trace_id": "trace_abc123",
  "status": "ingested"
}
```

**Status Codes**:
- `201` - Event ingested
- `400` - Invalid event format

---

### POST /api/v1/events/batch

Ingest multiple events in bulk.

**Request Body**:
```json
{
  "events": [
    {
      "timestamp": "2026-01-07T12:00:00Z",
      "event_type": "tool_call",
      "properties": {...}
    },
    {
      "timestamp": "2026-01-07T12:00:01Z",
      "event_type": "decision",
      "properties": {...}
    }
  ]
}
```

**Response**:
```json
{
  "ingested_count": 2,
  "failed_count": 0,
  "event_ids": ["event_1", "event_2"]
}
```

**Status Codes**:
- `200` - Batch ingested
- `207` - Partial success
- `400` - Invalid batch format

---

## Error Responses

All error responses follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional error context"
    }
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Entity/relation validation failed |
| `NOT_FOUND` | 404 | Resource not found |
| `INVALID_REQUEST` | 400 | Malformed request |
| `SCHEMA_NOT_LOADED` | 404 | No ontology schema available |
| `DATABASE_ERROR` | 500 | Internal database error |
| `EMBEDDING_ERROR` | 500 | Embedding generation failed |

---

## Examples

### Complete Workflow Example

```bash
# 1. Check health
curl http://localhost:8080/health

# 2. Upload schema
curl -X POST http://localhost:8080/api/v1/ontology/schema \
  -H "Content-Type: application/json" \
  -d @schema.json

# 3. Create entity
curl -X POST http://localhost:8080/api/v1/entities \
  -H "Content-Type: application/json" \
  -d '{
    "type": "Person",
    "properties": {
      "name": "Alice",
      "role": "Researcher"
    }
  }'

# 4. Create relation
curl -X POST http://localhost:8080/api/v1/relations \
  -H "Content-Type: application/json" \
  -d '{
    "type": "knows",
    "from_entity_id": "person_1",
    "to_entity_id": "person_2"
  }'

# 5. Hybrid query
curl -X POST http://localhost:8080/api/v1/query/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "vector_query": {
      "query_text": "machine learning",
      "entity_types": ["Person"],
      "top_k": 5
    },
    "merge_strategy": "vector_prioritized"
  }'
```

---

## Rate Limiting

**Current Status**: No rate limiting

**Future**: Rate limits will be applied per API key:
- 1000 requests/minute for standard keys
- 10000 requests/minute for premium keys

---

## Pagination

For endpoints returning lists (planned):

**Request**:
```
GET /api/v1/entities?page=2&per_page=50
```

**Response Headers**:
```
X-Total-Count: 250
X-Page: 2
X-Per-Page: 50
Link: <...>; rel="next", <...>; rel="prev"
```

---

## Webhooks (Planned)

Subscribe to events:
- `entity.created`
- `entity.updated`
- `entity.deleted`
- `relation.created`
- `relation.deleted`

---

## Related Documentation

- [Testing Guide](./TESTING.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Development Guide](./DEVELOPMENT.md)

---

**Questions or Issues?**
File an issue at: https://github.com/robertowilliams/vectadb/issues
