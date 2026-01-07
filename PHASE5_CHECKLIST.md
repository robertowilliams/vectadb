# Phase 5 Implementation Checklist

**Goal**: Log-based agent observability via CloudWatch integration
**Duration**: 5 days
**Language**: Rust (VectaDB Core + CloudWatch Agent)

---

## Day 1: Event Ingestion API ✅/❌

### VectaDB Core Changes

- [ ] **types.rs**: Add event ingestion request/response types
  - [ ] `EventIngestionRequest` struct
  - [ ] `BulkEventIngestionRequest` struct
  - [ ] `LogSource` struct for source metadata
  - [ ] `IngestionOptions` for configuration
  - [ ] Response types with error handling

- [ ] **handlers.rs**: Implement ingestion handlers
  - [ ] `ingest_event()` - Single event ingestion
  - [ ] `ingest_events_bulk()` - Batch ingestion (critical for logs)
  - [ ] `get_or_create_trace_by_session()` - Auto-trace logic
  - [ ] `create_event_entity()` - Store in SurrealDB
  - [ ] `store_event_vector()` - Store in Qdrant

- [ ] **routes.rs**: Add new routes
  - [ ] `POST /api/v1/events`
  - [ ] `POST /api/v1/events/batch`

- [ ] **Testing**
  - [ ] Unit tests for event validation
  - [ ] Test auto-trace creation
  - [ ] Test bulk ingestion (100+ events)
  - [ ] Test error handling

**Deliverable**: VectaDB API can receive and store events

---

## Day 2: Agent Framework ✅/❌

### Create CloudWatch Agent Project

- [ ] **Project setup**
  - [ ] `mkdir -p vectadb-agents/cloudwatch`
  - [ ] `cargo init` in cloudwatch directory
  - [ ] Create `Cargo.toml` with dependencies

- [ ] **config.rs**: Configuration system
  - [ ] `AgentConfig` struct
  - [ ] `LogGroupConfig` for CloudWatch
  - [ ] `ParserRule` for log parsing
  - [ ] YAML parsing with serde_yaml

- [ ] **vectadb_client.rs**: API client
  - [ ] `VectaDBClient` struct
  - [ ] `ingest_events_bulk()` method
  - [ ] `health_check()` method
  - [ ] Error handling with retry logic

- [ ] **Testing**
  - [ ] Test config parsing from YAML
  - [ ] Mock VectaDB client requests
  - [ ] Test error handling

**Deliverable**: Agent framework ready for CloudWatch integration

---

## Day 3: CloudWatch Integration ✅/❌

### CloudWatch SDK Integration

- [ ] **cloudwatch_client.rs**: AWS SDK wrapper
  - [ ] `CloudWatchClient` struct
  - [ ] `fetch_log_events()` method
  - [ ] `fetch_from_stream()` for specific streams
  - [ ] `filter_logs()` for all streams
  - [ ] Handle pagination (if >10k events)

- [ ] **parser.rs**: Log parsing logic
  - [ ] `LogParser` struct
  - [ ] `parse()` method with JSON + regex support
  - [ ] `try_parse_json()` for structured logs
  - [ ] `build_event_from_captures()` for regex
  - [ ] `create_fallback_event()` for unparsed logs

- [ ] **Testing**
  - [ ] Mock CloudWatch responses
  - [ ] Test JSON log parsing
  - [ ] Test regex pattern matching
  - [ ] Test field extraction

**Deliverable**: Agent can fetch and parse CloudWatch logs

---

## Day 4: Main Agent Loop ✅/❌

### Agent Execution

- [ ] **state.rs**: State management
  - [ ] `AgentState` struct
  - [ ] Track last poll time per log group
  - [ ] Persist state (optional, for restarts)

- [ ] **main.rs**: Main loop
  - [ ] Initialize tracing (JSON logging)
  - [ ] Load configuration
  - [ ] Create CloudWatch client
  - [ ] Create VectaDB client
  - [ ] Health check VectaDB connection
  - [ ] Poll loop with configurable interval
  - [ ] Fetch logs per log group
  - [ ] Parse logs to events
  - [ ] Batch and send to VectaDB
  - [ ] Update last poll time
  - [ ] Error handling and retry logic
  - [ ] Graceful shutdown (SIGTERM)

- [ ] **Error Handling**
  - [ ] Log fetch failures (warn, continue)
  - [ ] Parse failures (warn, skip)
  - [ ] VectaDB API failures (error, retry)
  - [ ] AWS credentials errors (fatal)

**Deliverable**: Full end-to-end agent working

---

## Day 5: Configuration & Documentation ✅/❌

### Deployment Ready

- [ ] **config.example.yaml**: Example configuration
  - [ ] AWS region
  - [ ] Multiple log groups
  - [ ] Parser rules for LangChain
  - [ ] Parser rules for generic errors
  - [ ] VectaDB endpoint configuration

- [ ] **Dockerfile**: Container packaging
  - [ ] Multi-stage build (builder + runtime)
  - [ ] Minimal base image (debian-slim)
  - [ ] Health check command
  - [ ] Proper user permissions

- [ ] **docker-compose.yml**: Local testing
  - [ ] Add cloudwatch-agent service
  - [ ] Link to vectadb network
  - [ ] Mount config volume
  - [ ] AWS credentials via env vars

- [ ] **README.md**: Complete documentation
  - [ ] Overview and features
  - [ ] Quick start guide
  - [ ] Configuration reference
  - [ ] Parser rule examples
  - [ ] Troubleshooting guide
  - [ ] AWS IAM permissions required

- [ ] **Testing & Validation**
  - [ ] Test with real CloudWatch (manual)
  - [ ] Verify events in VectaDB
  - [ ] Check trace auto-creation
  - [ ] Load test (1000+ events)

**Deliverable**: Production-ready CloudWatch agent

---

## Integration Testing Scenarios

### Scenario 1: LangChain on Lambda
```bash
# Setup
- Deploy LangChain agent to Lambda
- Configure CloudWatch agent
- Run agent

# Verify
- Events appear in VectaDB
- Traces grouped by request_id
- Tool calls parsed correctly
```

### Scenario 2: Multiple Log Groups
```bash
# Setup
- Configure 3+ log groups
- Different parser rules per group
- Run agent

# Verify
- All log groups polled
- Events from all sources
- No missed logs
```

### Scenario 3: High Volume
```bash
# Setup
- Log group with 10k+ events/minute
- Batch size: 100
- Run agent

# Verify
- No events lost
- Consistent ingestion rate
- Memory usage stable
```

---

## Success Metrics

### Functional
- [ ] Agent connects to CloudWatch successfully
- [ ] Parses 90%+ of logs correctly
- [ ] Creates traces from session IDs automatically
- [ ] Handles 1000+ events/minute
- [ ] Zero data loss

### Performance
- [ ] Memory usage < 100MB
- [ ] CPU usage < 10% (idle)
- [ ] API calls batched efficiently
- [ ] Latency < 5s (poll to ingestion)

### Reliability
- [ ] Graceful error handling
- [ ] Automatic retry on failures
- [ ] Survives CloudWatch API errors
- [ ] Survives VectaDB downtime
- [ ] Clean shutdown on SIGTERM

---

## Files to Create

### VectaDB Core
```
vectadb/src/api/types.rs         (add 150+ lines)
vectadb/src/api/handlers.rs      (add 300+ lines)
vectadb/src/api/routes.rs        (add 2 routes)
```

### CloudWatch Agent
```
vectadb-agents/cloudwatch/
├── Cargo.toml                   (50 lines)
├── Dockerfile                   (20 lines)
├── config.example.yaml          (80 lines)
├── README.md                    (200 lines)
└── src/
    ├── main.rs                  (150 lines)
    ├── config.rs                (100 lines)
    ├── cloudwatch_client.rs     (200 lines)
    ├── parser.rs                (250 lines)
    ├── vectadb_client.rs        (150 lines)
    └── state.rs                 (50 lines)
```

**Total New Code**: ~1,500 lines

---

## Post-Phase 5

### Week 2 Priority
1. Authentication (API keys)
2. Rate limiting
3. Performance optimization

### Future Enhancements
1. Real-time CloudWatch Subscriptions (vs polling)
2. DataDog agent
3. Splunk agent
4. Generic webhook agent
5. Python SDK (optional direct instrumentation)

---

## Quick Commands

### Build Agent
```bash
cd vectadb-agents/cloudwatch
cargo build --release
```

### Run Agent
```bash
export AWS_ACCESS_KEY_ID=xxx
export AWS_SECRET_ACCESS_KEY=xxx
export CONFIG_PATH=config.yaml
cargo run --release
```

### Test VectaDB API
```bash
# Health check
curl http://localhost:8080/health

# Test event ingestion
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-01-07T17:00:00Z",
    "event_type": "test",
    "properties": {"message": "test event"}
  }'
```

### Docker Build
```bash
cd vectadb-agents/cloudwatch
docker build -t vectadb/cloudwatch-agent:latest .
```

---

## Notes

- **AWS Permissions Required**:
  - `logs:FilterLogEvents`
  - `logs:GetLogEvents`
  - `logs:DescribeLogGroups`
  - `logs:DescribeLogStreams`

- **VectaDB API Key**: Generate via `POST /api/v1/auth/keys` (Week 2)

- **Monitoring**: Agent logs in JSON format for easy ingestion

- **Scaling**: Deploy multiple agents for different regions/accounts

---

**Status**: Ready to implement
**Start Date**: TBD
**Owner**: Backend Engineer (Rust)
