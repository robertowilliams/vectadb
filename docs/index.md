# VectaDB

> **"Debug Your Agents Like Never Before"**

VectaDB is an open-source meta-database purpose-built for LLM agent observability. It combines SurrealDB (documents + graphs) and Qdrant (vector search) behind a single unified API — enabling teams to find similar errors in milliseconds, trace agent reasoning chains, and detect anomalies with ML.

## Why VectaDB?

LLM agents fail unpredictably. Existing tools like Datadog and New Relic were built for traditional applications — they have no concept of semantic error similarity, chain-of-thought traces, or vector-based anomaly detection. VectaDB fills that gap.

## Key Capabilities

| Capability | What it does |
|---|---|
| **Semantic Error Clustering** | Groups 500 error variants into 3 clusters in 3–5ms |
| **Execution Trace Visualization** | Single query returns the complete agent reasoning chain |
| **ML-Powered Anomaly Detection** | Flags agents 2.5+ std deviations outside their peer group |
| **Audit & Compliance** | GDPR, SOC 2, HIPAA-ready audit trails built in |

## Performance Headlines

| Query Type | VectaDB | PostgreSQL+pgvector | Improvement |
|---|---|---|---|
| Error clustering | 3–5ms | 25–50ms | **5–10x faster** |
| Vector search (1M) | 5–10ms | 50–200ms | **10–20x faster** |
| Execution trace | 10–15ms | 30–80ms | **2–5x faster** |
| Anomaly detection | 15–25ms | 100–300ms | **6–12x faster** |

## Quick Start

```bash
git clone https://github.com/robertowilliams/VectaDB.git
cd VectaDB
docker-compose up -d
cd vectadb && cargo run --release
```

## Quick Facts

- **Language:** Rust (core API layer)
- **License:** Apache 2.0
- **Backends:** SurrealDB v2.x + Qdrant (latest)
- **API port:** 3000 | SurrealDB: 8000 | Qdrant: 6333/6334
