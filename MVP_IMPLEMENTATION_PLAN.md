# VectaDB MVP Implementation Plan

**Date:** 2026-01-06
**Goal:** Translate Python PoC to Rust and integrate SurrealDB + Qdrant

---

## 1. Current Python Architecture Analysis

### Components Identified

**main.py (2046 lines)** contains:

1. **Data Models (Pydantic)**
   - `AgentRequest`, `TaskRequest`, `LogRequest`
   - `ThoughtRequest`, `EmbedRequest`
   - `SimilarAgentDescriptionRequest`, `SimilarTaskDescriptionRequest`

2. **Database Integrations**
   - **CouchDB**: Document storage (agents, tasks, logs)
   - **ChromaDB**: Vector embeddings (384-dim, all-MiniLM-L6-v2)
   - **Neo4j**: Graph relationships (Agent→Task→Thought→Log)

3. **Core Functions**
   - `generate_short_id()`: ID generation (6-10 chars)
   - `ingest_log()`: Multi-backend log storage
   - `encode_text()`: Text → embeddings
   - `chroma_find_similar_*()`: Semantic search
   - `neo4j_upsert_*()`: Graph operations
   - `neo4j_store_thought()`: Chain-of-thought tracking

4. **API Endpoints (FastAPI)**
   - JSON-RPC: `/api/v1/rpc/agents`, `/api/v1/rpc/tasks`
   - REST: `/agents`, `/tasks`, `/logs`, `/thoughts`
   - Similarity: `/similar/agents`, `/similar/tasks`
   - Monitoring: `/health`, `/metrics` (Prometheus)
   - Admin UI: `/`, `/ui/*`

5. **Features**
   - Authentication: API key + session-based
   - Metrics: Prometheus (logs, errors, latency, anomaly scores)
   - Admin dashboard: HTML/JS UI

---

## 2. VectaDB Rust Architecture

### Stack Selection

```
┌────────────────────────────────────────┐
│   VectaDB API Server (Axum + Rust)    │
│   • REST + JSON-RPC endpoints          │
│   • Authentication & metrics           │
└────────────────────────────────────────┘
              ↓
┌────────────────────────────────────────┐
│     VectaDB Intelligence Layer         │
│   • Query Router                       │
│   • Query Optimizer                    │
│   • Cache Manager                      │
│   • Result Aggregator                  │
└────────────────────────────────────────┘
         ↓               ↓
┌──────────────┐  ┌──────────────┐
│  SurrealDB   │  │   Qdrant     │
│              │  │              │
│ • Documents  │  │ • Vectors    │
│ • Graphs     │  │ • Similarity │
│ • Relations  │  │ • HNSW index │
└──────────────┘  └──────────────┘
```

### Crate Dependencies

```toml
[dependencies]
# Web framework
axum = "0.7"
tokio = { version = "1", features = ["full"] }
tower = "0.4"
tower-http = { version = "0.5", features = ["cors", "trace"] }

# Database clients
surrealdb = "2.0"
qdrant-client = "1.10"

# Serialization
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# Embeddings
fastembed = "3"

# Configuration
config = "0.14"
dotenvy = "0.15"

# Logging & metrics
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
prometheus = "0.13"

# Error handling
anyhow = "1"
thiserror = "1"

# Utilities
uuid = { version = "1", features = ["v4", "serde"] }
nanoid = "0.4"
chrono = { version = "0.4", features = ["serde"] }

# Security
argon2 = "0.5"
jsonwebtoken = "9"
```

---

## 3. Project Structure

```
vectadb/
├── Cargo.toml
├── .env.example
├── README.md
├── docker-compose.yml          # SurrealDB + Qdrant
│
├── src/
│   ├── main.rs                 # Entry point
│   ├── config.rs               # Configuration management
│   ├── error.rs                # Error types
│   │
│   ├── models/                 # Data models
│   │   ├── mod.rs
│   │   ├── agent.rs
│   │   ├── task.rs
│   │   ├── log.rs
│   │   ├── thought.rs
│   │   └── embedding.rs
│   │
│   ├── db/                     # Database layer
│   │   ├── mod.rs
│   │   ├── surrealdb.rs        # SurrealDB client
│   │   ├── qdrant.rs           # Qdrant client
│   │   └── router.rs           # Query routing logic
│   │
│   ├── api/                    # API layer
│   │   ├── mod.rs
│   │   ├── routes.rs           # Route definitions
│   │   ├── handlers/           # Request handlers
│   │   │   ├── mod.rs
│   │   │   ├── agents.rs
│   │   │   ├── tasks.rs
│   │   │   ├── logs.rs
│   │   │   ├── thoughts.rs
│   │   │   └── similarity.rs
│   │   └── middleware/         # Auth, logging, metrics
│   │       ├── mod.rs
│   │       ├── auth.rs
│   │       └── metrics.rs
│   │
│   ├── embeddings/             # Embedding generation
│   │   ├── mod.rs
│   │   └── fastembed.rs
│   │
│   └── utils/                  # Utilities
│       ├── mod.rs
│       └── id_gen.rs           # Short ID generation
│
├── tests/
│   ├── integration/
│   │   ├── agents_test.rs
│   │   ├── tasks_test.rs
│   │   └── similarity_test.rs
│   └── common/
│       └── mod.rs              # Test utilities
│
└── docs/
    ├── API.md
    └── ARCHITECTURE.md
```

---

## 4. Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal:** Basic project setup and data models

- [ ] Install Rust toolchain
- [ ] Create project structure
- [ ] Define core data models (Agent, Task, Log, Thought)
- [ ] Implement configuration management
- [ ] Set up logging with `tracing`
- [ ] Create `docker-compose.yml` for SurrealDB + Qdrant

**Deliverables:**
- Working Rust project structure
- Data models with serde serialization
- Configuration loaded from `.env`

### Phase 2: Database Integration (Week 2)

**Goal:** Connect to SurrealDB and Qdrant

#### SurrealDB Integration

```rust
// src/db/surrealdb.rs
use surrealdb::Surreal;
use surrealdb::engine::remote::ws::{Client, Ws};

pub struct SurrealDBClient {
    db: Surreal<Client>,
}

impl SurrealDBClient {
    pub async fn new(url: &str, namespace: &str, database: &str) -> Result<Self> {
        let db = Surreal::new::<Ws>(url).await?;
        db.use_ns(namespace).use_db(database).await?;
        Ok(Self { db })
    }

    pub async fn create_agent(&self, agent: &Agent) -> Result<Agent> {
        let created: Option<Agent> = self.db
            .create(("agent", &agent.id))
            .content(agent)
            .await?;
        Ok(created.unwrap())
    }

    pub async fn create_task(&self, task: &Task) -> Result<Task> {
        let created: Option<Task> = self.db
            .create(("task", &task.id))
            .content(task)
            .await?;
        Ok(created.unwrap())
    }

    pub async fn link_task_to_agent(&self, task_id: &str, agent_id: &str) -> Result<()> {
        self.db
            .query("RELATE $agent->belongs_to->$task")
            .bind(("agent", format!("agent:{}", agent_id)))
            .bind(("task", format!("task:{}", task_id)))
            .await?;
        Ok(())
    }

    pub async fn get_agent_with_tasks(&self, agent_id: &str) -> Result<AgentWithRelations> {
        let result = self.db
            .query("SELECT *, ->belongs_to->task.* AS tasks FROM agent WHERE id = $id")
            .bind(("id", agent_id))
            .await?;
        Ok(result)
    }
}
```

#### Qdrant Integration

```rust
// src/db/qdrant.rs
use qdrant_client::{Qdrant, QdrantClient};
use qdrant_client::qdrant::{CreateCollectionBuilder, Distance, VectorParamsBuilder};

pub struct QdrantDBClient {
    client: QdrantClient,
    agent_collection: String,
    task_collection: String,
}

impl QdrantDBClient {
    pub async fn new(url: &str, agent_collection: &str, task_collection: &str) -> Result<Self> {
        let client = QdrantClient::from_url(url).build()?;

        // Create collections if they don't exist
        Self::ensure_collection(&client, agent_collection, 384).await?;
        Self::ensure_collection(&client, task_collection, 384).await?;

        Ok(Self {
            client,
            agent_collection: agent_collection.to_string(),
            task_collection: task_collection.to_string(),
        })
    }

    async fn ensure_collection(client: &QdrantClient, name: &str, vector_size: u64) -> Result<()> {
        if client.collection_exists(name).await? {
            return Ok(());
        }

        client.create_collection(
            CreateCollectionBuilder::new(name)
                .vectors_config(VectorParamsBuilder::new(vector_size, Distance::Cosine))
        ).await?;

        Ok(())
    }

    pub async fn upsert_agent(&self, agent_id: &str, embedding: Vec<f32>, metadata: serde_json::Value) -> Result<()> {
        use qdrant_client::qdrant::{PointStruct, UpsertPointsBuilder};

        let point = PointStruct::new(
            agent_id.to_string(),
            embedding,
            metadata,
        );

        self.client.upsert_points(
            UpsertPointsBuilder::new(&self.agent_collection, vec![point])
        ).await?;

        Ok(())
    }

    pub async fn search_similar_agents(
        &self,
        query_vector: Vec<f32>,
        limit: usize,
        threshold: f32,
    ) -> Result<Vec<SimilarAgent>> {
        use qdrant_client::qdrant::SearchPointsBuilder;

        let results = self.client.search_points(
            SearchPointsBuilder::new(&self.agent_collection, query_vector, limit as u64)
                .score_threshold(threshold)
        ).await?;

        Ok(results.result.into_iter().map(|r| SimilarAgent {
            id: r.id.unwrap().to_string(),
            score: r.score,
            metadata: r.payload,
        }).collect())
    }
}
```

**Deliverables:**
- SurrealDB client with CRUD operations
- Qdrant client with vector upsert/search
- Integration tests for both databases

### Phase 3: VectaDB Router (Week 3)

**Goal:** Build intelligent query routing layer

```rust
// src/db/router.rs
pub struct VectaDBRouter {
    surrealdb: Arc<SurrealDBClient>,
    qdrant: Arc<QdrantDBClient>,
    embedder: Arc<EmbeddingService>,
}

impl VectaDBRouter {
    pub async fn create_agent(&self, request: CreateAgentRequest) -> Result<Agent> {
        // 1. Generate embedding from metadata
        let text = self.build_agent_text(&request);
        let embedding = self.embedder.encode(&text).await?;

        // 2. Store in SurrealDB (parallel)
        let agent = Agent {
            id: nanoid::nanoid!(10),
            role: request.role,
            goal: request.goal,
            metadata: request.metadata,
            created_at: Utc::now(),
        };

        // 3. Store in both databases in parallel
        let (surreal_result, qdrant_result) = tokio::join!(
            self.surrealdb.create_agent(&agent),
            self.qdrant.upsert_agent(&agent.id, embedding, agent.to_json())
        );

        surreal_result?;
        qdrant_result?;

        Ok(agent)
    }

    pub async fn find_similar_agents(
        &self,
        query: &str,
        threshold: f32,
        limit: usize,
    ) -> Result<Vec<AgentWithSimilarity>> {
        // 1. Generate query embedding
        let query_embedding = self.embedder.encode(query).await?;

        // 2. Search Qdrant for similar vectors
        let similar = self.qdrant.search_similar_agents(
            query_embedding,
            limit,
            threshold,
        ).await?;

        // 3. Fetch full details from SurrealDB
        let agent_ids: Vec<String> = similar.iter().map(|s| s.id.clone()).collect();
        let agents = self.surrealdb.get_agents_by_ids(&agent_ids).await?;

        // 4. Merge results
        Ok(self.merge_similarity_results(agents, similar))
    }

    pub async fn get_agent_execution_trace(&self, agent_id: &str) -> Result<AgentTrace> {
        // Single SurrealDB query with graph traversal
        self.surrealdb.query(r#"
            SELECT
                *,
                ->belongs_to->task.* AS tasks,
                ->generated_thought->thought.* AS thoughts,
                ->generated_log->log.* AS logs
            FROM agent WHERE id = $id
        "#)
        .bind(("id", agent_id))
        .await
    }
}
```

**Deliverables:**
- VectaDB router with intelligent query routing
- Parallel operations where possible
- Query optimizer for common patterns

### Phase 4: REST API (Week 4)

**Goal:** Implement Axum REST API

```rust
// src/api/routes.rs
use axum::{Router, routing::{get, post}};

pub fn create_router(state: AppState) -> Router {
    Router::new()
        // Health & metrics
        .route("/health", get(handlers::health))
        .route("/metrics", get(handlers::metrics))

        // Agents
        .route("/api/v1/agents", post(handlers::agents::create_agent))
        .route("/api/v1/agents", get(handlers::agents::list_agents))
        .route("/api/v1/agents/:id", get(handlers::agents::get_agent))

        // Tasks
        .route("/api/v1/tasks", post(handlers::tasks::create_task))
        .route("/api/v1/tasks/:id", get(handlers::tasks::get_task))

        // Logs
        .route("/api/v1/logs", post(handlers::logs::ingest_log))

        // Thoughts
        .route("/api/v1/thoughts", post(handlers::thoughts::create_thought))

        // Similarity search
        .route("/api/v1/similar/agents", post(handlers::similarity::search_agents))
        .route("/api/v1/similar/tasks", post(handlers::similarity::search_tasks))

        // Traces
        .route("/api/v1/traces/:agent_id", get(handlers::traces::get_execution_trace))

        // Middleware
        .layer(middleware::auth::AuthLayer::new())
        .layer(middleware::metrics::MetricsLayer::new())
        .with_state(state)
}
```

```rust
// src/api/handlers/agents.rs
use axum::{Json, extract::State};

pub async fn create_agent(
    State(state): State<AppState>,
    Json(request): Json<CreateAgentRequest>,
) -> Result<Json<Agent>, ApiError> {
    let agent = state.router.create_agent(request).await?;
    Ok(Json(agent))
}

pub async fn list_agents(
    State(state): State<AppState>,
    Query(params): Query<ListParams>,
) -> Result<Json<Vec<Agent>>, ApiError> {
    let agents = state.router.list_agents(params.limit, params.offset).await?;
    Ok(Json(agents))
}
```

**Deliverables:**
- Full REST API with Axum
- Authentication middleware
- Prometheus metrics
- Error handling

### Phase 5: Testing & Documentation (Week 5)

**Goal:** Integration tests and documentation

```rust
// tests/integration/agents_test.rs
#[tokio::test]
async fn test_create_and_search_agent() {
    let client = setup_test_client().await;

    // Create agent
    let agent = client.create_agent(CreateAgentRequest {
        role: "researcher".to_string(),
        goal: "analyze data patterns".to_string(),
        metadata: json!({"skills": ["machine learning", "statistics"]}),
    }).await.unwrap();

    assert_eq!(agent.role, "researcher");

    // Search for similar
    let similar = client.find_similar_agents(
        "data scientist with ML skills",
        0.7,
        10,
    ).await.unwrap();

    assert!(similar.len() > 0);
    assert!(similar[0].similarity > 0.7);
}
```

**Deliverables:**
- Integration tests for all endpoints
- Unit tests for core logic
- API documentation
- Architecture documentation
- README with setup instructions

---

## 5. Migration Strategy

### From Python to Rust

| Python Component | Rust Equivalent | Notes |
|-----------------|-----------------|-------|
| CouchDB | SurrealDB | Documents + graph in one |
| Neo4j | SurrealDB | Native graph support |
| ChromaDB | Qdrant | Specialized vector DB |
| FastAPI | Axum | High-performance async |
| Pydantic | Serde | Serialization |
| sentence-transformers | fastembed | Rust embeddings |
| Prometheus client | prometheus crate | Metrics |
| python-dotenv | dotenvy | Environment |

### Data Migration

1. **Export from CouchDB**
   ```bash
   # Export all documents
   curl http://admin:password@localhost:5984/enroll/_all_docs?include_docs=true > couch_export.json
   ```

2. **Import to SurrealDB**
   ```rust
   // Batch import script
   for doc in couch_export {
       match doc.type {
           "agent" => surrealdb.create_agent(doc).await?,
           "task" => surrealdb.create_task(doc).await?,
           "log" => surrealdb.create_log(doc).await?,
       }
   }
   ```

3. **Re-generate embeddings**
   ```rust
   // Regenerate vectors for Qdrant
   let agents = surrealdb.get_all_agents().await?;
   for agent in agents {
       let embedding = embedder.encode(&agent.to_text()).await?;
       qdrant.upsert_agent(&agent.id, embedding, agent.metadata).await?;
   }
   ```

---

## 6. Docker Setup

### docker-compose.yml

```yaml
version: '3.8'

services:
  surrealdb:
    image: surrealdb/surrealdb:latest
    ports:
      - "8000:8000"
    command: start --log trace --user root --pass root memory
    volumes:
      - surrealdb_data:/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  vectadb:
    build: .
    ports:
      - "8080:8080"
    environment:
      - SURREAL_URL=ws://surrealdb:8000
      - QDRANT_URL=http://qdrant:6333
      - RUST_LOG=info
    depends_on:
      - surrealdb
      - qdrant

volumes:
  surrealdb_data:
  qdrant_data:
```

---

## 7. Configuration

### .env.example

```bash
# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8080

# SurrealDB
SURREAL_URL=ws://localhost:8000
SURREAL_NAMESPACE=vectadb
SURREAL_DATABASE=production
SURREAL_USER=root
SURREAL_PASS=root

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_AGENT_COLLECTION=agents
QDRANT_TASK_COLLECTION=tasks

# Embeddings
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384

# API
API_KEY=your-secure-api-key-here
JWT_SECRET=your-jwt-secret

# Similarity
SIMILARITY_THRESHOLD=0.65
SIMILARITY_LIMIT=10

# Logging
RUST_LOG=info,vectadb=debug
```

---

## 8. Performance Targets

| Operation | Target Latency | Python Baseline |
|-----------|---------------|-----------------|
| Create agent | < 50ms | ~100ms |
| Vector search (10K) | < 10ms | ~50ms |
| Vector search (100K) | < 20ms | ~200ms |
| Graph traversal | < 15ms | ~80ms |
| Complex query (vector+graph) | < 30ms | ~150ms |
| Log ingestion (1K batch) | < 100ms | ~500ms |

**Expected Improvement:** 2-10x faster than Python implementation

---

## 9. Success Criteria

### MVP Complete When:

- ✅ All Python endpoints translated to Rust
- ✅ SurrealDB stores documents + graphs
- ✅ Qdrant handles vector similarity search
- ✅ Performance benchmarks show 2x+ improvement
- ✅ Integration tests passing (>80% coverage)
- ✅ API documentation complete
- ✅ Docker compose setup working
- ✅ Data migration script functional

### Validation Tests:

1. **Functional parity**: All Python API endpoints work in Rust
2. **Performance**: 2x faster on benchmark suite
3. **Data integrity**: Migrated data matches Python DB
4. **Concurrent load**: Handle 100 req/sec without degradation

---

## 10. Next Steps

### Immediate Actions:

1. **Install Rust**
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   source $HOME/.cargo/env
   ```

2. **Create project**
   ```bash
   cd /Users/roberto/Documents/VECTADB
   cargo new vectadb
   cd vectadb
   ```

3. **Set up databases**
   ```bash
   docker-compose up -d surrealdb qdrant
   ```

4. **Start coding!**
   - Begin with `src/models/` (data structures)
   - Then `src/db/` (database clients)
   - Finally `src/api/` (REST endpoints)

---

## 11. Timeline

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | Foundation | Project structure, models, config |
| 2 | Database | SurrealDB + Qdrant integration |
| 3 | Router | VectaDB query routing layer |
| 4 | API | Axum REST endpoints |
| 5 | Testing | Integration tests, docs |

**Total:** 5 weeks to MVP

---

## Conclusion

The VectaDB MVP will be a complete rewrite in Rust that:

1. **Replaces** CouchDB + Neo4j with SurrealDB
2. **Replaces** ChromaDB with Qdrant
3. **Adds** intelligent query routing layer
4. **Provides** 2-10x performance improvement
5. **Maintains** API compatibility with Python version

The meta-database architecture positions VectaDB as a specialized observability database for LLM agents, not just a translation of the Python PoC.

**Let's build it!** 🚀
