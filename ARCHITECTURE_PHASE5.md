# VectaDB Architecture - Phase 5 (Log Integration)

**Date**: January 7, 2026
**Focus**: Agent observability via log ingestion

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Production Systems                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │  LangChain Agent │  │  LlamaIndex App  │  │   Custom Agent   │     │
│  │  (AWS Lambda)    │  │  (ECS)           │  │   (Kubernetes)   │     │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘     │
│           │                     │                      │                │
│           └─────────────────────┴──────────────────────┘                │
│                                 │                                        │
│                           Logs via stdout/stderr                         │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Log Aggregation Layer                               │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    AWS CloudWatch Logs                            │  │
│  │  • Log Groups: /aws/lambda/*, /ecs/*, etc.                       │  │
│  │  • Retention: 7-30 days                                           │  │
│  │  • Access: IAM roles                                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              VectaDB CloudWatch Agent (Rust)                             │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Poll Loop (10s interval)                                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │  │
│  │  │  Fetch   │→ │  Parse   │→ │  Batch   │→ │  Send    │        │  │
│  │  │  Logs    │  │  Events  │  │  (100)   │  │  API     │        │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │  │
│  │                                                                   │  │
│  │  Components:                                                      │  │
│  │  • CloudWatch SDK (aws-sdk-cloudwatchlogs)                       │  │
│  │  • Regex + JSON Parser                                           │  │
│  │  • State Manager (last poll tracking)                            │  │
│  │  • VectaDB API Client (reqwest)                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  Configuration:                                                          │
│  • Log groups to monitor                                                │
│  • Parser rules (regex patterns)                                        │
│  • VectaDB endpoint + API key                                           │
│  • Poll interval, batch size                                            │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  ▼
                      POST /api/v1/events/batch
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         VectaDB Core API                                 │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Event Ingestion Pipeline                                         │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │  │
│  │  │ Validate │→ │  Trace   │→ │  Store   │→ │  Embed   │        │  │
│  │  │  Schema  │  │  Detect  │  │  Entity  │  │  Vector  │        │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │  │
│  │       │              │              │              │             │  │
│  │       │              │              ▼              ▼             │  │
│  │       │              │      ┌──────────┐  ┌──────────┐         │  │
│  │       │              │      │ SurrealDB│  │  Qdrant  │         │  │
│  │       │              │      │  Entity  │  │  Vector  │         │  │
│  │       │              │      └──────────┘  └──────────┘         │  │
│  │       │              ▼                                           │  │
│  │       │      ┌──────────────┐                                   │  │
│  │       │      │ Auto-Create  │                                   │  │
│  │       │      │ Trace if     │                                   │  │
│  │       │      │ session_id   │                                   │  │
│  │       │      └──────────────┘                                   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  Endpoints:                                                              │
│  • POST /api/v1/events        (single event)                            │
│  • POST /api/v1/events/batch  (bulk ingestion)                          │
│  • GET  /api/v1/events        (query with filters)                      │
│  • GET  /api/v1/traces/:id    (retrieve trace + events)                 │
└─────────────────────────────────┼────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Storage Layer                                    │
│  ┌────────────────────────┐         ┌────────────────────────┐         │
│  │      SurrealDB         │         │        Qdrant          │         │
│  │  (Graph + Documents)   │         │    (Vector Search)     │         │
│  ├────────────────────────┤         ├────────────────────────┤         │
│  │ Tables:                │         │ Collections:           │         │
│  │ • agent_trace          │         │ • events               │         │
│  │ • agent_event          │         │ • 384-dim vectors      │         │
│  │ • Relations:           │         │ • Cosine similarity    │         │
│  │   - hasEvent           │         └────────────────────────┘         │
│  │   - causedBy           │                                             │
│  └────────────────────────┘                                             │
│                                                                          │
│  Indices:                                                                │
│  • timestamp (temporal queries)                                          │
│  • event_type (filtering)                                                │
│  • session_id (trace grouping)                                           │
│  • agent_id (agent filtering)                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Log Generation → CloudWatch
```
Agent System:
  print(f"[{timestamp}] Tool: web_search | Input: {query}")
                ↓
        CloudWatch Logs:
          /aws/lambda/langchain-agent
            ├─ stream-1: log entry A
            ├─ stream-2: log entry B
            └─ stream-3: log entry C
```

### 2. CloudWatch → VectaDB Agent
```
Poll Loop (every 10s):
  1. Query: Get logs since last_poll_time
  2. Response: 500 log entries
  3. Parse each log:
     - Try JSON parsing first
     - Try regex patterns
     - Create fallback event
  4. Batch: Group into chunks of 100
  5. Send: POST /api/v1/events/batch
```

### 3. VectaDB Agent → Core API
```
HTTP Request:
  POST /api/v1/events/batch
  Authorization: Bearer api_key_xxx
  Body: {
    "events": [
      {
        "timestamp": "2026-01-07T17:00:00Z",
        "event_type": "tool_call",
        "session_id": "req-abc123",
        "properties": {
          "tool_name": "web_search",
          "tool_input": {"query": "weather SF"}
        },
        "source": {
          "system": "cloudwatch",
          "log_group": "/aws/lambda/agent",
          "log_stream": "stream-1",
          "log_id": "evt-xyz"
        }
      },
      ... 99 more events
    ]
  }
```

### 4. Core API → Storage
```
For each event:
  1. Trace Detection:
     - If session_id exists: get_or_create_trace()
     - Creates trace entity if needed

  2. Event Storage (SurrealDB):
     - Create event entity
     - Link to trace via hasEvent relation

  3. Vector Embedding (Qdrant):
     - Extract text: tool_name + tool_input
     - Generate embedding: BGE model (384-dim)
     - Store in Qdrant with event_id

  4. Response:
     - Success: event_id + trace_id
     - Error: index + error message
```

---

## Component Details

### CloudWatch Agent

**Language**: Rust
**Runtime**: Standalone binary or Docker container
**Dependencies**:
- aws-sdk-cloudwatchlogs
- reqwest (HTTP client)
- serde (JSON/YAML)
- regex

**Responsibilities**:
1. Poll CloudWatch at intervals
2. Track last poll time per log group
3. Parse logs using rules
4. Batch events (100 per request)
5. Send to VectaDB API
6. Handle errors and retry

**Configuration**:
```yaml
aws_region: us-east-1
log_groups:
  - name: /aws/lambda/agent
parser_rules:
  - pattern: "Tool: (?P<tool>\\w+)"
    event_type: tool_call
vectadb_endpoint: http://vectadb:8080
vectadb_api_key: xxx
poll_interval_seconds: 10
batch_size: 100
```

**Performance**:
- Memory: ~50MB
- CPU: <5% (idle), ~30% (parsing)
- Throughput: 1000+ events/sec

---

### VectaDB Core API

**Event Ingestion Handler**:
```rust
async fn ingest_events_bulk(
    events: Vec<EventIngestionRequest>
) -> BulkEventIngestionResponse {
    // 1. Group by session_id for trace detection
    let grouped = group_by_session(events);

    // 2. Process each group
    for (session_id, group_events) in grouped {
        // Get or create trace
        let trace_id = get_or_create_trace(session_id).await?;

        // 3. Store events in parallel
        let futures = group_events.map(|event| {
            async {
                // Store entity
                let event_id = store_event(event, trace_id).await?;

                // Generate embedding
                let embedding = embed_text(event.properties).await?;
                store_vector(event_id, embedding).await?;

                Ok(event_id)
            }
        });

        join_all(futures).await;
    }
}
```

**Trace Auto-Creation**:
```rust
async fn get_or_create_trace(session_id: &str) -> String {
    // Query SurrealDB for existing trace
    let query = "SELECT id FROM agent_trace WHERE session_id = $sid";
    let result = db.query(query).bind(("sid", session_id)).await?;

    if let Some(trace) = result.first() {
        trace.id
    } else {
        // Create new trace
        let trace_id = format!("trace_{}", nanoid());
        db.create("agent_trace")
            .content(json!({
                "id": trace_id,
                "session_id": session_id,
                "status": "running",
                "start_time": Utc::now()
            }))
            .await?;

        trace_id
    }
}
```

---

### Storage Schema

#### SurrealDB Tables

**agent_trace**:
```sql
DEFINE TABLE agent_trace SCHEMAFULL;
DEFINE FIELD id ON agent_trace TYPE string;
DEFINE FIELD session_id ON agent_trace TYPE string;
DEFINE FIELD agent_id ON agent_trace TYPE option<string>;
DEFINE FIELD status ON agent_trace TYPE string;  -- running, completed, failed
DEFINE FIELD start_time ON agent_trace TYPE datetime;
DEFINE FIELD end_time ON agent_trace TYPE option<datetime>;
DEFINE FIELD total_events ON agent_trace TYPE int DEFAULT 0;
DEFINE FIELD created_at ON agent_trace TYPE datetime;

DEFINE INDEX idx_session_id ON agent_trace COLUMNS session_id;
DEFINE INDEX idx_start_time ON agent_trace COLUMNS start_time;
```

**agent_event**:
```sql
DEFINE TABLE agent_event SCHEMAFULL;
DEFINE FIELD id ON agent_event TYPE string;
DEFINE FIELD trace_id ON agent_event TYPE string;
DEFINE FIELD timestamp ON agent_event TYPE datetime;
DEFINE FIELD event_type ON agent_event TYPE option<string>;
DEFINE FIELD properties ON agent_event TYPE object;  -- flexible JSON
DEFINE FIELD source ON agent_event TYPE option<object>;
DEFINE FIELD created_at ON agent_event TYPE datetime;

DEFINE INDEX idx_trace_id ON agent_event COLUMNS trace_id;
DEFINE INDEX idx_timestamp ON agent_event COLUMNS timestamp;
DEFINE INDEX idx_event_type ON agent_event COLUMNS event_type;
```

**Relations**:
```sql
DEFINE TABLE hasEvent SCHEMAFULL;
DEFINE FIELD in ON hasEvent TYPE record<agent_trace>;
DEFINE FIELD out ON hasEvent TYPE record<agent_event>;
```

#### Qdrant Collections

**events** collection:
```json
{
  "vectors": {
    "size": 384,
    "distance": "Cosine"
  },
  "payload_schema": {
    "event_id": "keyword",
    "trace_id": "keyword",
    "event_type": "keyword",
    "timestamp": "integer"
  }
}
```

---

## Query Patterns

### Temporal Queries
```sql
-- Events in time range
SELECT * FROM agent_event
WHERE timestamp >= "2026-01-07T00:00:00Z"
  AND timestamp < "2026-01-08T00:00:00Z"
ORDER BY timestamp DESC;

-- Traces by day
SELECT session_id, COUNT() as event_count
FROM agent_event
WHERE timestamp >= "2026-01-07T00:00:00Z"
GROUP BY session_id
ORDER BY event_count DESC;
```

### Trace Reconstruction
```sql
-- Get trace with all events
SELECT
  id,
  session_id,
  status,
  ->hasEvent->agent_event as events
FROM agent_trace
WHERE id = $trace_id;
```

### Semantic Search
```rust
// Find similar events
let query_embedding = embed_text("database connection timeout").await;

let search_result = qdrant_client
    .search_points("events", query_embedding, 10)
    .await?;

// Get full event details from SurrealDB
let event_ids = search_result.iter().map(|r| r.id);
let events = db.select::<Vec<Event>>("agent_event")
    .where("id IN $ids")
    .bind(("ids", event_ids))
    .await?;
```

### Aggregations
```sql
-- Error rate by event type
SELECT
  event_type,
  COUNT() as total,
  COUNT_IF(event_type = 'error') as errors
FROM agent_event
WHERE timestamp >= time::now() - 1h
GROUP BY event_type;
```

---

## Scalability Considerations

### Agent Scaling
- **Horizontal**: Deploy multiple agents for different regions/accounts
- **Vertical**: Increase batch size and poll frequency
- **Partitioning**: Separate agents per log group

### API Scaling
- **Rate Limiting**: Per API key (Week 2)
- **Connection Pooling**: SurrealDB and Qdrant clients
- **Async Processing**: All I/O is non-blocking
- **Batching**: Process 100+ events in parallel

### Storage Scaling
- **SurrealDB**: Distributed mode (future)
- **Qdrant**: Sharding by collection (future)
- **Retention**: Auto-delete events older than 30 days

---

## Error Handling

### Agent Errors
```rust
match cloudwatch_client.fetch_logs().await {
    Ok(logs) => process_logs(logs),
    Err(e) => {
        error!("Failed to fetch logs: {}", e);
        // Continue to next log group, don't crash
    }
}

match vectadb_client.ingest_events(events).await {
    Ok(response) => {
        if response.failed > 0 {
            warn!("{} events failed ingestion", response.failed);
            // Log individual errors
        }
    }
    Err(e) => {
        error!("VectaDB API error: {}", e);
        // Retry with exponential backoff
        retry_with_backoff(events).await;
    }
}
```

### API Errors
```rust
// Validation errors
if event.timestamp > Utc::now() {
    return Err(ValidationError::FutureTimestamp);
}

// Database errors
match db.create("agent_event").content(event).await {
    Ok(_) => Ok(()),
    Err(e) if is_duplicate_key_error(&e) => {
        warn!("Duplicate event: {}", event.id);
        Ok(()) // Idempotent
    }
    Err(e) => Err(e)
}
```

---

## Monitoring

### Agent Metrics
- Events fetched per minute
- Events parsed successfully
- Events sent to VectaDB
- Parse failures
- API errors
- Memory usage
- CPU usage

### API Metrics
- Ingestion rate (events/sec)
- P50/P95/P99 latency
- Error rate
- Trace creation rate
- Database connection pool

### Dashboards
- Grafana with Prometheus metrics
- CloudWatch Logs Insights
- VectaDB admin UI (future)

---

## Security

### Authentication (Week 2)
```
Agent → VectaDB:
  Authorization: Bearer api_key_abc123

VectaDB:
  1. Validate API key
  2. Check rate limits
  3. Log request (audit)
  4. Process if authorized
```

### AWS Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:FilterLogEvents",
        "logs:GetLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/lambda/*"
    }
  ]
}
```

---

## Deployment

### Docker Compose (Development)
```yaml
services:
  cloudwatch-agent:
    build: ./vectadb-agents/cloudwatch
    environment:
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_REGION=us-east-1
    volumes:
      - ./config.yaml:/app/config.yaml
    networks:
      - vectadb-network
    depends_on:
      - vectadb
```

### Kubernetes (Production)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cloudwatch-agent
spec:
  replicas: 3
  template:
    spec:
      serviceAccountName: cloudwatch-agent
      containers:
      - name: agent
        image: vectadb/cloudwatch-agent:latest
        env:
        - name: CONFIG_PATH
          value: /config/config.yaml
        volumeMounts:
        - name: config
          mountPath: /config
      volumes:
      - name: config
        configMap:
          name: cloudwatch-agent-config
```

---

## Future Enhancements

### Real-time Ingestion
- CloudWatch Logs Subscriptions (push instead of poll)
- Lambda function triggered on log arrival
- Sub-second latency

### Multi-Source Support
- DataDog agent
- Splunk agent
- Generic webhook receiver
- Direct SDK instrumentation (Python, JS)

### Advanced Analytics
- Anomaly detection (ML models)
- Pattern recognition (frequent sequences)
- Cost optimization (token usage alerts)
- Performance profiling (tool latency heatmaps)

---

**Architecture Status**: Phase 5 Ready
**Implementation**: 5 days
**Team**: 1 Backend Engineer (Rust)
