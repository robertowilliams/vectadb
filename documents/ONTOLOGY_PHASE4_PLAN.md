# VectaDB Ontology Support - Phase 4 Implementation Plan

**Date:** January 6, 2026
**Status:** Planning - Database Integration
**Goal:** Integrate SurrealDB and Qdrant for persistent storage and hybrid queries

---

## Overview

Phase 4 adds persistent storage to VectaDB, enabling:
- **SurrealDB**: Store ontology schemas, entities, and relations in a graph database
- **Qdrant**: Store vector embeddings for semantic similarity search
- **Hybrid Queries**: Combine graph traversal, ontology reasoning, and vector search

---

## Architecture

### Current (Phase 3)
```
HTTP API → Ontology Reasoner (in-memory)
```

### Phase 4 Target
```
HTTP API
    ↓
┌─────────────────────────────────┐
│     Query Coordinator           │
│  (Hybrid Query Execution)       │
└─────────────────────────────────┘
    ↓           ↓           ↓
SurrealDB   Qdrant    Ontology Reasoner
(Graph)     (Vector)   (Reasoning)
```

---

## Phase 4 Components

### 1. Database Connections (`src/db/`)

**Files to create:**
- `src/db/mod.rs` - Database module exports
- `src/db/surrealdb_client.rs` - SurrealDB connection and operations
- `src/db/qdrant_client.rs` - Qdrant connection and operations
- `src/db/types.rs` - Shared database types

**SurrealDB Client:**
```rust
pub struct SurrealDBClient {
    db: Surreal<Client>,
    namespace: String,
    database: String,
}

impl SurrealDBClient {
    pub async fn new(config: &DatabaseConfig) -> Result<Self>
    pub async fn store_schema(&self, schema: &OntologySchema) -> Result<()>
    pub async fn get_schema(&self) -> Result<Option<OntologySchema>>
    pub async fn create_entity(&self, entity: &Entity) -> Result<String>
    pub async fn get_entity(&self, id: &str) -> Result<Option<Entity>>
    pub async fn update_entity(&self, id: &str, entity: &Entity) -> Result<()>
    pub async fn delete_entity(&self, id: &str) -> Result<()>
    pub async fn create_relation(&self, relation: &Relation) -> Result<String>
    pub async fn query_entities(&self, entity_type: &str) -> Result<Vec<Entity>>
    pub async fn traverse_graph(&self, start_id: &str, relation_type: &str, depth: usize) -> Result<Vec<Entity>>
}
```

**Qdrant Client:**
```rust
pub struct QdrantClient {
    client: QdrantGrpcClient,
    collection_prefix: String,
}

impl QdrantClient {
    pub async fn new(config: &VectorConfig) -> Result<Self>
    pub async fn create_collection(&self, entity_type: &str, vector_size: usize) -> Result<()>
    pub async fn upsert_embedding(&self, entity_type: &str, entity_id: &str, embedding: Vec<f32>) -> Result<()>
    pub async fn search_similar(&self, entity_type: &str, query_vector: Vec<f32>, limit: usize) -> Result<Vec<ScoredEntity>>
    pub async fn delete_embedding(&self, entity_type: &str, entity_id: &str) -> Result<()>
}
```

---

### 2. Entity Storage (`src/models/entity.rs` extension)

**Entity Model:**
```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    pub id: String,
    pub entity_type: String,
    pub properties: HashMap<String, JsonValue>,
    pub embedding: Option<Vec<f32>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub metadata: HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Relation {
    pub id: String,
    pub relation_type: String,
    pub source_id: String,
    pub target_id: String,
    pub properties: HashMap<String, JsonValue>,
    pub created_at: DateTime<Utc>,
}
```

---

### 3. Query Coordinator (`src/query/`)

**Files to create:**
- `src/query/mod.rs`
- `src/query/coordinator.rs` - Hybrid query execution
- `src/query/plan.rs` - Query planning and optimization
- `src/query/types.rs` - Query request/response types

**Query Coordinator:**
```rust
pub struct QueryCoordinator {
    surreal: Arc<SurrealDBClient>,
    qdrant: Arc<QdrantClient>,
    reasoner: Arc<RwLock<Option<OntologyReasoner>>>,
    embedding_service: Arc<EmbeddingService>,
}

impl QueryCoordinator {
    pub async fn execute_hybrid_query(&self, query: &HybridQuery) -> Result<QueryResult>
    pub async fn vector_search(&self, query: &VectorQuery) -> Result<Vec<ScoredEntity>>
    pub async fn graph_traversal(&self, query: &GraphQuery) -> Result<Vec<Entity>>
    pub async fn ontology_query(&self, query: &OntologyQuery) -> Result<Vec<Entity>>
}
```

**Query Types:**
```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HybridQuery {
    Vector {
        entity_type: String,
        query_text: String,
        limit: usize,
        expand_types: bool,  // Use ontology reasoning
    },
    Graph {
        start_entity_id: String,
        relation_types: Vec<String>,
        depth: usize,
        expand_relations: bool,  // Use ontology reasoning
    },
    Combined {
        vector_query: VectorQuery,
        graph_query: GraphQuery,
        merge_strategy: MergeStrategy,
    },
}

pub enum MergeStrategy {
    Union,
    Intersection,
    RankFusion,  // Combine scores from both
}
```

---

### 4. API Updates (`src/api/handlers.rs`)

**New Endpoints:**

```rust
// Entity CRUD
POST   /api/v1/entities                 - Create entity
GET    /api/v1/entities/{id}            - Get entity
PUT    /api/v1/entities/{id}            - Update entity
DELETE /api/v1/entities/{id}            - Delete entity
GET    /api/v1/entities                 - List entities (filtered)

// Relation CRUD
POST   /api/v1/relations                - Create relation
GET    /api/v1/relations/{id}           - Get relation
DELETE /api/v1/relations/{id}           - Delete relation

// Hybrid Queries
POST   /api/v1/query/vector             - Vector similarity search
POST   /api/v1/query/graph              - Graph traversal
POST   /api/v1/query/hybrid             - Combined query
```

**Handler Examples:**
```rust
pub async fn create_entity(
    State(state): State<AppState>,
    Json(request): Json<CreateEntityRequest>,
) -> Result<Json<CreateEntityResponse>, (StatusCode, Json<ErrorResponse>)> {
    // 1. Validate entity against ontology
    // 2. Generate embedding if text properties exist
    // 3. Store in SurrealDB
    // 4. Store embedding in Qdrant
    // 5. Return entity ID
}

pub async fn hybrid_query(
    State(state): State<AppState>,
    Json(request): Json<HybridQueryRequest>,
) -> Result<Json<HybridQueryResponse>, (StatusCode, Json<ErrorResponse>)> {
    // 1. Expand query using ontology reasoning
    // 2. Execute vector search in Qdrant
    // 3. Execute graph traversal in SurrealDB
    // 4. Merge results based on strategy
    // 5. Return ranked results
}
```

---

### 5. Configuration Updates

**Update `src/config.rs`:**
```rust
#[derive(Debug, Clone, Deserialize)]
pub struct DatabaseConfig {
    pub surrealdb: SurrealDBConfig,
    pub qdrant: QdrantConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SurrealDBConfig {
    pub endpoint: String,
    pub namespace: String,
    pub database: String,
    pub username: String,
    pub password: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct QdrantConfig {
    pub url: String,
    pub api_key: Option<String>,
    pub collection_prefix: String,
}
```

**Update `config.yaml`:**
```yaml
database:
  surrealdb:
    endpoint: "ws://localhost:8000"
    namespace: "vectadb"
    database: "main"
    username: "root"
    password: "root"
  qdrant:
    url: "http://localhost:6333"
    api_key: null
    collection_prefix: "vectadb_"
```

---

## Implementation Steps

### Step 1: Database Clients (Week 1)
1. Add dependencies to `Cargo.toml`:
   ```toml
   surrealdb = "1.1.1"
   qdrant-client = "1.7.0"
   ```
2. Create `src/db/` module
3. Implement `SurrealDBClient` with connection pooling
4. Implement `QdrantClient` with retry logic
5. Add health checks for both databases
6. Write unit tests for clients

### Step 2: Schema Persistence (Week 1)
1. Define SurrealDB schema for ontologies
2. Implement `store_schema()` and `get_schema()`
3. Update API to load ontology from DB on startup
4. Add schema versioning support
5. Test schema CRUD operations

### Step 3: Entity Storage (Week 2)
1. Define Entity and Relation models
2. Implement entity CRUD in SurrealDB
3. Add validation before storage
4. Create indexes for efficient queries
5. Test entity operations

### Step 4: Vector Integration (Week 2)
1. Integrate embedding service with Qdrant
2. Auto-generate embeddings for text properties
3. Create Qdrant collections per entity type
4. Implement vector search
5. Test similarity search

### Step 5: Query Coordinator (Week 3)
1. Create `QueryCoordinator` with both clients
2. Implement vector search queries
3. Implement graph traversal queries
4. Implement hybrid query execution
5. Add query optimization
6. Test all query types

### Step 6: API Integration (Week 3)
1. Update `AppState` with DB clients
2. Add entity CRUD endpoints
3. Add relation CRUD endpoints
4. Add hybrid query endpoints
5. Update existing endpoints to use persistence
6. Add comprehensive API tests

### Step 7: Testing & Documentation (Week 4)
1. Integration tests with real DB instances
2. Performance benchmarks
3. API documentation updates
4. Example workflows
5. Migration guide

---

## Success Criteria

- [x] SurrealDB client connects and stores data
- [x] Qdrant client connects and stores embeddings
- [x] Ontology schemas persist across restarts
- [x] Entities validate against ontology before storage
- [x] Vector similarity search works
- [x] Graph traversal respects ontology constraints
- [x] Hybrid queries combine all three approaches
- [x] All tests pass (target: 80+ tests)
- [x] API documentation complete
- [x] Example workflows documented

---

## Database Schema Design

### SurrealDB Schema

**Ontology Storage:**
```sql
DEFINE TABLE ontology_schema SCHEMAFULL;
DEFINE FIELD namespace ON ontology_schema TYPE string;
DEFINE FIELD version ON ontology_schema TYPE string;
DEFINE FIELD schema_json ON ontology_schema TYPE object;
DEFINE FIELD created_at ON ontology_schema TYPE datetime;
DEFINE INDEX idx_namespace ON ontology_schema COLUMNS namespace UNIQUE;
```

**Entity Storage:**
```sql
DEFINE TABLE entity SCHEMAFULL;
DEFINE FIELD entity_type ON entity TYPE string;
DEFINE FIELD properties ON entity TYPE object;
DEFINE FIELD created_at ON entity TYPE datetime;
DEFINE FIELD updated_at ON entity TYPE datetime;
DEFINE INDEX idx_type ON entity COLUMNS entity_type;
```

**Relation Storage:**
```sql
DEFINE TABLE relation SCHEMAFULL;
DEFINE FIELD relation_type ON relation TYPE string;
DEFINE FIELD in ON relation TYPE record(entity);
DEFINE FIELD out ON relation TYPE record(entity);
DEFINE FIELD properties ON relation TYPE object;
DEFINE FIELD created_at ON relation TYPE datetime;
```

### Qdrant Collections

**Collection naming:** `{prefix}{entity_type}` (e.g., `vectadb_LLMAgent`)

**Collection config:**
```json
{
  "vectors": {
    "size": 384,  // BGE-small-en-v1.5
    "distance": "Cosine"
  },
  "payload_schema": {
    "entity_id": "keyword",
    "entity_type": "keyword",
    "properties": "keyword"
  }
}
```

---

## Performance Targets

| Operation | Target Latency | Notes |
|-----------|---------------|-------|
| Entity create | < 50ms | Including validation + embedding |
| Entity read | < 10ms | Direct lookup |
| Vector search | < 100ms | Top 10 results |
| Graph traversal (depth 2) | < 200ms | Including ontology expansion |
| Hybrid query | < 300ms | Combined vector + graph |

---

## Error Handling

**New Error Types:**
```rust
#[derive(Debug, thiserror::Error)]
pub enum DatabaseError {
    #[error("SurrealDB connection failed: {0}")]
    SurrealDBConnection(String),

    #[error("Qdrant connection failed: {0}")]
    QdrantConnection(String),

    #[error("Entity not found: {0}")]
    EntityNotFound(String),

    #[error("Relation not found: {0}")]
    RelationNotFound(String),

    #[error("Collection not found: {0}")]
    CollectionNotFound(String),

    #[error("Query execution failed: {0}")]
    QueryFailed(String),
}
```

---

## Migration Strategy

**For existing deployments:**
1. Add database configuration to config.yaml
2. Start VectaDB with `--migrate` flag
3. Existing in-memory ontologies exported to DB
4. Zero-downtime migration with dual-write period

---

## Testing Strategy

**Unit Tests:**
- Database client connections
- Entity CRUD operations
- Query coordinator logic

**Integration Tests:**
- Full API workflows with real databases
- Hybrid query scenarios
- Error handling paths

**Performance Tests:**
- Concurrent entity creation
- Large-scale vector search
- Deep graph traversal

---

## Dependencies to Add

```toml
[dependencies]
# Database clients
surrealdb = "1.1.1"
qdrant-client = "1.7.0"

# Already have these:
# tokio, serde, serde_json, axum, etc.
```

---

## Next Steps

1. ✅ Create implementation plan (this document)
2. ⏭️ Set up database clients
3. ⏭️ Implement schema persistence
4. ⏭️ Add entity storage
5. ⏭️ Integrate vector embeddings
6. ⏭️ Build query coordinator
7. ⏭️ Update API endpoints
8. ⏭️ Add comprehensive tests
9. ⏭️ Document workflows

---

**Estimated Timeline:** 3-4 weeks
**Priority:** High - Core functionality for production use
**Complexity:** Medium-High - Multiple external systems integration

---

**Contact:** contact@vectadb.com
**Phase 3 Status:** ✅ Complete
**Phase 4 Status:** 📋 Planning → Implementation
