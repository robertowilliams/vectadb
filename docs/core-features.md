# Core Features

## Semantic Error Clustering

Traditional log tools match errors by exact string or regex. VectaDB uses vector embeddings to group semantically similar errors.

**The problem:**
```
"Connection timeout to https://api.example.com"
"Request to api.example.com timed out after 30s"
"api.example.com connection failed"
"Failed to reach api.example.com: ETIMEDOUT"
```
Four different strings. One problem. Traditional tools generate four separate alerts.

**VectaDB's approach:**
```sql
SELECT * FROM error_log
WHERE error_message <SIMILAR 0.85> "timeout connecting to API"
  AND timestamp > NOW() - 24h
ORDER BY similarity DESC;
```

**Result:**
```
Cluster 1: "API timeout"           → 487 occurrences, 23 agents
Cluster 2: "Rate limit exceeded"   → 142 occurrences, 8 agents
Cluster 3: "Invalid JSON response" →  89 occurrences, 12 agents
```

| Method | Latency (100K) | Latency (1M) |
|---|---|---|
| VectaDB | 3–5ms | 5–10ms |
| PostgreSQL LIKE | 25–50ms | 100–300ms |

---

## Execution Trace Visualization

Every agent action is stored as a node in SurrealDB's graph. A single VQL query traverses the entire reasoning chain:

```sql
SELECT
  agent.*,
  ->belongs_to->task.* AS tasks,
  ->generated_thought->thought.* AS reasoning,
  ->generated_log->log.* AS logs
FROM agent WHERE id = $agent_id;
```

**Output:**
```
Agent: researcher_42
  ├─ Task: analyze_data [FAILED]
  │   ├─ Thought: "Loading dataset from API"
  │   ├─ Log[INFO]:  GET api.example.com (200ms)
  │   ├─ Thought: "Processing 10K records"
  │   ├─ Log[ERROR]: Connection timeout ← ROOT CAUSE
  │   └─ Thought: "Retrying... max retries exceeded"
  └─ Dependencies: api.example.com (3 calls, 2 timeouts)
```

Full trace returns in **10–20ms** vs 50–100ms with PostgreSQL JOINs.

**API:**
```bash
GET /agents/{agent_id}/trace
GET /tasks/{task_id}/trace
GET /decisions/{decision_id}/trace
```

---

## ML-Powered Anomaly Detection

VectaDB vectorizes agent performance profiles and clusters them by role. Agents >2.5 standard deviations from their cluster centroid are flagged.

**Detection steps:**

1. Vectorize each agent's performance window (1h / 24h / 7d)
2. Retrieve cluster centroid for the agent's role
3. Compute cosine distance
4. Flag outliers, find k nearest well-performing peers

**Example alert:**
```
🚨 ANOMALY DETECTED: researcher_42
   Avg duration:  45s  (role avg: 12s)  — 3.7x slower
   Error rate:    23%  (role avg: 2%)

   Similar well-performing agents:
     researcher_15  (avg: 11s, 1% errors)
     researcher_89  (avg: 13s, 2% errors)

💡 Recommendation: Compare execution traces with researcher_15
```

**API:**
```bash
POST /analytics/anomalies
POST /analytics/anomalies?role=researcher
GET  /agents/{agent_id}/anomalies
```

---

## Audit & Compliance

### What Is Tracked

| Event Type | Captured Data |
|---|---|
| Agent actions | Who, what, when, why — every task and tool call |
| Configuration changes | What changed, who changed it, previous value |
| Data access | Which data was read, by which agent |
| Decision provenance | Full chain of thoughts that led to a decision |
| LLM interactions | Prompt, model, token count, cost, latency |
| Compliance events | GDPR deletions, access requests, consent changes |

### Decision Provenance Query

```sql
SELECT
  decision.*,
  ->based_on_thought->thought.* AS reasoning,
  ->accessed_data->data.* AS consulted_data,
  ->llm_call->audit_log.* AS llm_interactions
FROM decision WHERE id = $decision_id;
```

### Framework Support

| Framework | Support |
|---|---|
| **GDPR** | Right to be forgotten, consent tracking |
| **SOC 2** | Immutable access logs |
| **HIPAA** | Audit trail retention, PII access logging |

### Audit API

```bash
GET  /agents/{agent_id}/audit
GET  /audit/llm-calls?from=2026-01-01&to=2026-04-01
GET  /audit/decisions/{id}
DELETE /agents/{agent_id}/data?gdpr=true
```

---

## Real-Time Dashboard

```
┌─────────────────────────────────────────────┐
│     Agent Observability Dashboard           │
├─────────────────────────────────────────────┤
│  📊 Real-Time Metrics (5s refresh)          │
│  • Active Agents:    487                   │
│  • Avg Duration:    8.2s  (↑ 15% ⚠️)       │
│  • Error Rate:      2.3%                   │
│                                             │
│  🔥 Error Clusters (24h)                   │
│  • "API timeout"    — 487 (23 agents)     │
│                                             │
│  🎯 Anomalies                               │
│  • researcher_42:  3.7x slower            │
│                                             │
│  💰 LLM Costs (30d): $1,247.32            │
└─────────────────────────────────────────────┘
```

Dashboard query performance: **<20ms** for the full view.
