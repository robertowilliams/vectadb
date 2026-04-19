# Architecture

## Meta-Database Design

VectaDB is not a new database engine — it is an **intelligence layer** that sits in front of best-of-breed open-source databases, routing queries to the right backend and aggregating results.

```
┌─────────────────────────────────────────────────────────┐
│                  VectaDB Client SDK                     │
│              (Python, Rust, TypeScript)                 │
└─────────────────────────────────────────────────────────┘
                         ↓ HTTP / WebSocket
┌─────────────────────────────────────────────────────────┐
│              VectaDB API Server (Axum / Rust)           │
├─────────────────────────────────────────────────────────┤
│     VQL Parser → Query Optimizer → Execution Planner   │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                  Intelligence Layer                     │
├──────────────────┬──────────────────┬───────────────────┤
│  Query Router    │  Cache Manager   │  Batch Optimizer  │
│  Result Merger   │  Prefetcher      │  Anomaly Detector │
└─────────────────────────────────────────────────────────┘
              ↓                           ↓
   ┌──────────────────┐         ┌──────────────────┐
   │    SurrealDB     │         │     Qdrant        │
   │ • Documents      │         │ • Vectors        │
   │ • Graphs         │         │ • Similarity     │
   │ • Relationships  │         │ • Clustering     │
   │ • Time-series    │         │                  │
   └──────────────────┘         └──────────────────┘
```

## Component Stack

### SurrealDB (Documents + Graphs)

- Port: `8000`
- Storage: RocksDB (production) / file (development)
- Namespace: `vectadb` / Database: `production`
- License: BSL 1.1 → Apache 2.0

### Qdrant (Vector Search)

- HTTP port: `6333` | gRPC port: `6334`
- HNSW approximate nearest neighbor search
- License: Apache 2.0

### VectaDB Intelligence Layer

| Component | Responsibility |
|---|---|
| VQL Parser | Parses VectaDB Query Language into an execution plan |
| Query Optimizer | Routes to SurrealDB, Qdrant, or both in parallel |
| Cache Manager | LRU cache (40–70% hit rate target) |
| Batch Optimizer | Coalesces bulk writes for throughput |
| Anomaly Detector | ML outlier detection on performance profiles |

## Data Model

### Graph Relationships (SurrealDB)

```
agent ->belongs_to-> task
agent ->generated_thought-> thought
agent ->generated_log-> log
task  ->has_thought-> thought
task  ->has_log-> log
decision ->based_on_thought-> thought
decision ->accessed_data-> data
decision ->llm_call-> audit_event
```

### Vector Collections (Qdrant)

| Collection | Vector | Payload |
|---|---|---|
| `agents` | 384-dim (role + goal + performance) | agent_id, role, avg_duration, error_rate |
| `tasks` | 384-dim (task description) | task_id, agent_id, status |
| `errors` | 384-dim (error message) | log_id, agent_id, level, timestamp |

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| API server | Rust + Axum | 1.75+ |
| Async runtime | Tokio | Latest |
| Document/graph DB | SurrealDB | 2.3.10 |
| Vector DB | Qdrant | Latest |
| Embeddings | fastembed (all-MiniLM-L6-v2) | Latest |
| UI dashboard | Vue 3 + TypeScript | 3.x |

## Licensing

VectaDB is **Apache 2.0**. Neo4j (GPL v3) was explicitly rejected — its viral copyleft would require the entire project to be GPL-licensed.

| Dependency | License |
|---|---|
| SurrealDB | BSL 1.1 → Apache 2.0 |
| Qdrant | Apache 2.0 |
| Axum / Tokio | MIT |
| fastembed | Apache 2.0 |
