# API Reference

## VQL — VectaDB Query Language

VQL extends SQL with two operators: **vector similarity** (`<SIMILAR>`) and **graph traversal** (`->`).

### Vector Similarity

```sql
SELECT * FROM error_log
WHERE message <SIMILAR 0.85> "connection timeout"
ORDER BY similarity DESC
LIMIT 20;
```

Threshold is cosine similarity: 0.0 (no match) to 1.0 (identical). Values above 0.8 represent strong semantic similarity.

### Graph Traversal

```sql
SELECT
  agent.*,
  ->belongs_to->task.* AS tasks,
  ->generated_thought->thought.* AS reasoning
FROM agent WHERE id = $agent_id;
```

Multiple hops: `->belongs_to->task->has_log->log.*`

### Auto-Vectorization

```sql
CREATE agent:a1 CONTENT {
  role: "researcher",
  goal: "analyze financial data"
} WITH VECTOR AUTO;
```

### Batch Ingestion

```sql
INSERT INTO log BATCH [
  { agent_id: "a1", message: "Processing", level: "INFO" },
  { agent_id: "a1", message: "Timeout",    level: "ERROR" }
] WITH THROUGHPUT OPTIMIZED;
```

---

## REST API

### Health

```
GET /health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "backends": { "surrealdb": "connected", "qdrant": "connected" }
}
```

### Agents

| Method | Path | Description |
|---|---|---|
| GET | `/agents` | List all agents |
| GET | `/agents/{id}` | Get agent by ID |
| POST | `/agents` | Create agent (auto-vectorizes) |
| POST | `/agents/search` | Semantic search |
| GET | `/agents/{id}/trace` | Full execution trace |
| GET | `/agents/{id}/anomalies` | Anomaly history |
| GET | `/agents/{id}/audit` | Audit trail |
| DELETE | `/agents/{id}/data?gdpr=true` | GDPR purge |

### Logs

| Method | Path | Description |
|---|---|---|
| POST | `/logs` | Ingest single entry |
| POST | `/logs/batch` | Batch ingest (20–50K/sec) |
| POST | `/logs/search` | Semantic search |
| GET | `/logs/clusters` | Current error clusters |

### Analytics

| Method | Path | Description |
|---|---|---|
| POST | `/analytics/anomalies` | Run anomaly detection |
| GET | `/analytics/clusters` | Error cluster summary |
| GET | `/analytics/costs` | LLM cost report |
| GET | `/analytics/dashboard` | Full dashboard data |

---

## Python SDK

```bash
pip install vectadb
```

```python
from vectadb import VectaDB

db = VectaDB("vectadb://localhost:3000")

# Create agent
agent = db.agents.create(role="researcher", goal="analyze data", auto_vector=True)

# Semantic search
similar = db.agents.search_similar(query="financial analyst", threshold=0.8, limit=10)

# Ingest log
db.logs.ingest(agent_id=agent.id, level="ERROR", message="Connection timeout")

# Get trace
trace = db.agents.get_trace(agent.id)

# Anomaly detection
anomalies = db.analytics.detect_anomalies()
```

### LangChain

```python
from vectadb import VectaDB, VectaDBCallback

db = VectaDB("vectadb://localhost:3000")
agent = AgentExecutor(agent=researcher, tools=tools, callbacks=[VectaDBCallback(db)])
result = agent.run("Analyze Q4 earnings")
```

---

## Rust SDK

```toml
[dependencies]
vectadb = "0.1"
tokio = { version = "1", features = ["full"] }
```

```rust
use vectadb::{VectaDB, Agent};

#[tokio::main]
async fn main() -> Result<()> {
    let db = VectaDB::connect("vectadb://localhost:3000").await?;

    let agent = db.agents().create(Agent {
        role: "researcher".into(),
        goal: "analyze financial patterns".into(),
        auto_vector: true,
        ..Default::default()
    }).await?;

    let trace = db.agents().get_trace(&agent.id).await?;
    let anomalies = db.analytics().detect_anomalies(None).await?;
    Ok(())
}
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SURREAL_URL` | `ws://localhost:8000` | SurrealDB WebSocket URL |
| `SURREAL_USER` | `root` | SurrealDB username |
| `SURREAL_PASS` | `root` | SurrealDB password |
| `SURREAL_NAMESPACE` | `vectadb` | SurrealDB namespace |
| `SURREAL_DATABASE` | `production` | SurrealDB database |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant HTTP URL |
| `QDRANT_AGENT_COLLECTION` | `agents` | Qdrant agents collection |
| `QDRANT_TASK_COLLECTION` | `tasks` | Qdrant tasks collection |
| `API_KEY` | *(none)* | API authentication key |
| `RUST_LOG` | `info` | Log level |
