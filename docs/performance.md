# Performance & Benchmarks

## Benchmark Setup

- **Hardware:** AWS c5.2xlarge (8 vCPU, 16GB RAM)
- **Dataset:** 1M agents, 10M logs, 100K thoughts, 50K tasks
- **Workload:** 40% vector, 30% graph, 20% aggregations, 10% simple lookups
- **Tools:** Criterion.rs, Apache JMeter, custom workload generator

## Results

### Query Latency

| Query Type | VectaDB | PostgreSQL+pgvector | Improvement |
|---|---|---|---|
| Error clustering (100K) | 3–5ms | 25–50ms | **5–10x** |
| Vector search (10K) | 3–7ms | 15–30ms | **2–4x** |
| Vector search (100K) | 4–10ms | 25–60ms | **2–6x** |
| Vector search (1M) | 5–20ms | 50–200ms | **3–10x** |
| Execution trace (5 hops) | 10–20ms | 50–100ms | **2–5x** |
| Vector + graph combined | 15–30ms | 30–100ms | **2–4x** |
| Anomaly detection | 15–25ms | 100–300ms | **6–12x** |
| Dashboard (full) | <20ms | >50ms | **2.5x** |
| Simple document lookup | 3–5ms | 2–4ms | ~Tie |

!!! note
    Simple document lookups are slightly slower due to routing overhead — acceptable for workloads that primarily use vector and graph queries.

### Throughput

| Operation | VectaDB | PostgreSQL |
|---|---|---|
| Batch log ingestion | 20–50K logs/sec | 12–33K logs/sec |
| Concurrent reads (100 users) | <30ms p95 | <80ms p95 |

## Routing Overhead

| Component | Added Latency |
|---|---|
| Query parsing | 0.1–0.5ms |
| Routing decision | 0.1–0.3ms |
| Connection pool | 0.05–0.2ms |
| Result aggregation | 0.2–1.0ms |
| Serialization | 0.1–0.5ms |
| **Total** | **0.55–2.5ms** |

Target: <2ms overhead at p95.

## Caching

| Level | Content | Hit Rate |
|---|---|---|
| L1 — Query cache | Full query results | 40–70% |
| L2 — Embedding cache | Precomputed vectors | 60–80% |
| L3 — Document cache | Agent/task records | 30–50% |
| L4 — Aggregation cache | Metrics and summaries | 50–70% |

## Optimization Tips

**Always use batch ingestion at scale:**
```bash
POST /logs/batch   # 20–50K logs/sec
POST /logs         # ~1K logs/sec (avoid at scale)
```

**Precompute embeddings in bulk:**
```python
embeddings = db.embeddings.batch_generate(texts=messages, batch_size=256)
```

**Configure connection pools proportionally to concurrent clients:**
```
SURREAL_POOL_SIZE=20
QDRANT_POOL_SIZE=20
```

## When VectaDB Wins

- Semantic error clustering (5–10x)
- Multi-hop graph traversal (2–5x)
- Mixed vector + graph queries (2–4x)
- Vector search at scale >100K vectors (3–10x)

## When the Advantage Is Smaller

- Simple CRUD operations (routing adds 1–2ms)
- Ultra-high write throughput
- Datasets <10K records

## Running Benchmarks

```bash
cd vectadb && cargo bench
cd benchmarks && ./run_load_test.sh --users 100 --duration 60s
./run_scenario_bench.sh --dataset 1m --scenarios all
```
