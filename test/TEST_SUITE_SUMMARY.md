# VectaDB Test Suite Summary

Complete overview of the VectaDB testing infrastructure for AWS Bedrock log analysis and database verification.

## Overview

This test suite validates VectaDB's core functionality as an observability platform for LLM agents through four comprehensive tests:

1. **Bedrock Log Test** - Flat data ingestion and semantic search
2. **Database Verification Test** - System-level storage validation
3. **Graph Database Test** - Graph functionality validation
4. **Bedrock Graph Ingestion** - Graph structure ingestion with dual storage

## Test Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                       VectaDB Test Suite                               │
└───────────────────────────────────────────────────────────────────────┘
                               │
           ┌───────────────────┼─────────────────┐
           │                   │                 │
    ┌──────▼──────┐  ┌─────────▼────────┐  ┌────▼───────┐
    │  Bedrock    │  │ Bedrock Graph    │  │  Database  │
    │  Flat Test  │  │   Ingestion      │  │   Verify   │
    └──────┬──────┘  └─────────┬────────┘  └────┬───────┘
           │                   │                 │
    ┌──────▼──────────┐  ┌─────▼─────────┐  ┌───▼──────────┐
    │  VectaDB API    │  │  VectaDB API  │  │  Direct DB   │
    │  - Flat Logs    │  │  - Entities   │  │  - SurrealDB │
    │  - Search       │  │  - Relations  │  │  - Qdrant    │
    │  - Analytics    │  │  - Dual Store │  │  - Validation│
    └─────────────────┘  └───────────────┘  └──────────────┘
           │                      │                 │
    ┌──────▼──────────────────────▼─────────────────▼──────┐
    │           VectaDB Server (Port 3000)                 │
    │   • Automatic embedding generation                   │
    │   • Dual storage: Graph (SurrealDB) + Vectors        │
    └────────┬──────────────────────────┬───────────────────┘
             │                          │
      ┌──────▼──────┐            ┌──────▼──────┐
      │  SurrealDB  │            │   Qdrant    │
      │  (Port 8000)│            │ (Port 6333) │
      │  Graph DB   │            │  Vector DB  │
      └─────────────┘            └─────────────┘
```

## Test Files

### Core Test Programs

| File | Purpose | Lines | Language |
|------|---------|-------|----------|
| `bedrock_test.rs` | Flat data ingestion test | ~650 | Rust |
| `database_verification.rs` | Database validation | ~550 | Rust |
| `graph_database_test.rs` | Graph functionality test | ~550 | Rust |
| `bedrock_graph_ingestion.rs` | Graph structure ingestion | ~580 | Rust |

### Scripts

| File | Purpose |
|------|---------|
| `run_test.sh` | Run Bedrock flat log test |
| `ingest_as_graph.sh` | Run Bedrock graph ingestion |
| `verify_databases.sh` | Run database verification |
| `test_graph.sh` | Run graph database test |

### Documentation

| File | Purpose |
|------|---------|
| `README.md` | Main test suite documentation |
| `QUICKSTART.md` | Quick start guide (updated for graph ingestion) |
| `DATABASE_VERIFICATION.md` | Database verification details |
| `GRAPH_DATABASE_TEST.md` | Graph test documentation |
| `BEDROCK_GRAPH_INGESTION.md` | Graph ingestion with dual storage |
| `TEST_SUITE_SUMMARY.md` | This file |

### Data

| File | Size | Description |
|------|------|-------------|
| `bedrock_chain_of_thought_logs.json` | 59KB | Real AWS Bedrock logs (27 entries) |

### Configuration

| File | Purpose |
|------|---------|
| `Cargo.toml` | Rust project configuration |
| `Cargo.lock` | Dependency lock file |

## Test 1: Bedrock Log Test

### Purpose
Validates VectaDB's ability to ingest, store, and query LLM agent logs through the API.

### What It Tests
- ✅ Log parsing and extraction
- ✅ API endpoint functionality
- ✅ Embedding generation
- ✅ Semantic search
- ✅ Analytics aggregation
- ✅ Error handling

### Test Data
- **Source**: AWS Bedrock chain-of-thought logs
- **Model**: Claude Haiku 4.5
- **Scenario**: Healthcare virtual assistant
- **Log Entries**: 27 raw events
- **Extracted Events**: ~40+ structured logs

### Event Types Extracted
1. User queries (2)
2. Assistant responses (3)
3. Tool calls (3)
4. Tool results (3)
5. Tool errors (3)
6. System prompts (3)
7. Tool configurations (3)
8. Throttling exceptions (19)
9. Performance metrics (3)

### Queries Tested
1. Error-related logs
2. Throttling errors
3. Tool calls
4. Patient-specific queries
5. Latency patterns

### Running
```bash
./run_test.sh
```

### Expected Duration
~5-10 seconds

### Success Criteria
- All 27 log entries processed
- ~40+ events extracted and stored
- 5 search queries return results
- Analytics data available
- No processing errors

## Test 2: Database Verification

### Purpose
Validates that data was actually persisted in both SurrealDB and Qdrant by directly querying the databases.

### What It Tests
- ✅ SurrealDB connectivity
- ✅ Entity table population
- ✅ Relation table population
- ✅ Qdrant connectivity
- ✅ Collection creation
- ✅ Vector storage
- ✅ Similarity search

### Running
```bash
./verify_databases.sh
```

### Expected Duration
~2-5 seconds

### Success Criteria
- Both databases healthy
- Entity records exist
- Vector collections exist
- Search returns results
- Data counts match expectations

## Test 3: Graph Database Test

### Purpose
Validates SurrealDB's graph database functionality by creating entities, relations, and complex graph structures.

### What It Tests
- ✅ Entity creation and retrieval
- ✅ Relation creation with properties
- ✅ Simple entity-relation-entity
- ✅ Complex graph structures (one-to-many)
- ✅ Bidirectional relations
- ✅ Multiple relation types between entities
- ✅ Relations with rich properties
- ✅ Multi-level graph depth

### Test Scenarios

1. **Simple Relation**: Agent → executes → Task
2. **Complex Structure**: Agent → Task → [Log1, Log2, Log3]
3. **Bidirectional**: Agent1 ↔ collaborates_with ↔ Agent2
4. **Multiple Types**: Agent → [owns, monitors, schedules] → Task
5. **Rich Properties**: Relations with timestamps, status, metadata
6. **Graph Depth**: Agent → Task → SubTask → Log (3 levels)

### Running
```bash
./test_graph.sh
```

### Expected Duration
~3-5 seconds

### Success Criteria
- All 6 test scenarios pass
- ~12 entities created
- ~10 relations created
- All properties preserved
- Successful cleanup

## Test 4: Bedrock Graph Ingestion

### Purpose
Ingests AWS Bedrock logs as a **graph structure** (nodes and edges) while **automatically** populating both the graph database (SurrealDB) and vector database (Qdrant).

### What It Tests
- ✅ Graph structure creation from logs
- ✅ Node types (Request, Response, UserQuery, ToolCall, ToolResult, Error, AssistantResponse)
- ✅ Edge types (triggers, produces, invokes, returns, provides_context_to, contains)
- ✅ Automatic embedding generation from node properties
- ✅ Dual storage (SurrealDB + Qdrant in one operation)
- ✅ Conversation flow representation
- ✅ Error causality tracking

### Test Data
- **Source**: Same AWS Bedrock logs as Test 1
- **Model**: Claude Haiku 4.5
- **Graph Output**: 17 nodes, 15 edges

### Node Types Created
1. Request (3) - Initial requests to Bedrock
2. Response (3) - Responses from Bedrock
3. UserQuery (2) - User's text queries
4. ToolCall (3) - Tool invocations
5. ToolResult (3) - Results from tools
6. Error (3) - Error events
7. AssistantResponse (varies) - Assistant text responses

### Edge Types Created
1. `triggers` - UserQuery → Request
2. `produces` - Request → Response
3. `contains` - Response → AssistantResponse
4. `invokes` - Response → ToolCall
5. `returns` - ToolCall → ToolResult
6. `provides_context_to` - ToolResult → Next Request
7. `contains` - ToolResult → Error

### Dual Storage Mechanism
**Single API call creates:**
1. Entity (node) in SurrealDB with properties
2. Text extraction from properties via `extract_text_from_properties()`
3. Embedding generation automatically
4. Vector storage in Qdrant collection
5. Relation (edge) in SurrealDB linking nodes

**Result**: Graph traversal queries + Semantic search enabled simultaneously

### Running
```bash
./ingest_as_graph.sh
```

### Expected Duration
~5-10 seconds

### Success Criteria
- 27 log entries processed
- 17 nodes created across 7 types
- 15 edges created across 7 types
- Embeddings generated for all nodes
- Both databases populated
- Graph structure represents conversation flow

## Complete Test Workflow

### Recommended Workflow (Graph Ingestion)

```bash
# Terminal 1: Start VectaDB
cd vectadb
cargo run --release

# Terminal 2: Run tests
cd test

# Step 1: Ingest Bedrock logs as graph (recommended)
./ingest_as_graph.sh

# Step 2: Verify storage in both databases
./verify_databases.sh

# Step 3: Test graph functionality
./test_graph.sh
```

### Alternative Workflow (Flat Ingestion)

```bash
# Step 1: Ingest Bedrock logs as flat records
./run_test.sh

# Step 2: Verify storage
./verify_databases.sh

# Step 3: Test graph functionality
./test_graph.sh
```

## Test Results Interpretation

### Bedrock Flat Test Output

**Successful Run:**
```
✅ Processed entry 0
✅ Processed entry 5
...
📈 PROCESSING SUMMARY
Requests:             3
Responses:            3
Tool Calls:           3
Tool Errors:          3
Throttling Errors:    19
✨ Test suite completed successfully!
```

**Failed Run:**
```
❌ VectaDB health check failed: Connection refused
```

### Bedrock Graph Ingestion Output

**Successful Run:**
```
╔════════════════════════════════════════╗
║   BEDROCK GRAPH INGESTION             ║
║   AWS Bedrock Logs → Graph Database   ║
╚════════════════════════════════════════╝

✅ VectaDB is healthy
📊 Found 27 log entries

🔄 Starting graph ingestion...
   ✅ Processed entry 1/27
   ✅ Processed entry 6/27
   ...

╔════════════════════════════════════════╗
║     GRAPH INGESTION SUMMARY           ║
╚════════════════════════════════════════╝

  Nodes Created:          17
  Edges Created:          15

✨ Graph ingestion completed successfully!
```

**What This Means:**
- Logs stored as graph structure (not flat records)
- Each node has embeddings in Qdrant
- Each edge represents relationship (triggers, produces, invokes, etc.)
- Can perform both graph traversal AND semantic search

### Database Verification Output

**With Data:**
```
╔════════════════════════════════════════╗
║         OVERALL STATUS                ║
╚════════════════════════════════════════╝
   ✅ ALL SYSTEMS OPERATIONAL
   ✅ DATA SUCCESSFULLY INGESTED
```

**Without Data:**
```
╔════════════════════════════════════════╗
║         OVERALL STATUS                ║
╚════════════════════════════════════════╝
   ✅ ALL SYSTEMS OPERATIONAL
   ⚠️  NO DATA FOUND - Run bedrock_test first
```

## Metrics Collected

### Ingestion Metrics
- Processing time per log entry
- Total logs processed
- Events extracted by type
- API call success rate
- Error count

### Storage Metrics
- Entity count (SurrealDB)
- Relation count (SurrealDB)
- Collection count (Qdrant)
- Vector count (Qdrant)
- Vector dimensions
- Storage distribution by type

### Query Metrics
- Search result counts
- Similarity scores
- Query response times
- Analytics aggregations

## Key Insights from Tests

### From Bedrock Logs

1. **Error Patterns**: 100% tool failure rate (3/3 calls)
2. **Throttling**: 19 throttling exceptions in short time
3. **Latency**: 858ms - 2990ms range
4. **Multi-Region**: 4 different AWS inference regions
5. **Retry Logic**: Agent attempted 3 different approaches
6. **Token Usage**: 5,827 total tokens across conversations

### From Database Verification

1. **Data Persistence**: Confirms data survives API layer
2. **Vector Quality**: Validates embedding generation
3. **Search Accuracy**: Tests semantic similarity
4. **System Integration**: Verifies SurrealDB ↔ Qdrant sync
5. **Performance**: Measures direct database query speed

## Use Cases Demonstrated

### 1. LLM Agent Observability
- Track agent decisions and reasoning
- Monitor tool usage patterns
- Identify failure modes
- Analyze retry strategies

### 2. Performance Monitoring
- Latency tracking
- Token usage analysis
- Rate limit detection
- Regional performance comparison

### 3. Error Analysis
- Error clustering by similarity
- Root cause identification
- Failure pattern detection
- Tool reliability measurement

### 4. Compliance & Auditing
- Complete interaction history
- Decision trail reconstruction
- Data lineage tracking
- Audit log generation

### 5. Agent Improvement
- Compare agent behaviors
- A/B testing different models
- Prompt engineering validation
- Tool effectiveness analysis

## Dependencies

### Rust Crates
- `tokio` - Async runtime
- `reqwest` - HTTP client
- `serde` / `serde_json` - Serialization
- `base64` - Encoding for auth
- `rand` - Random number generation

### External Services
- **VectaDB** - Main application server
- **SurrealDB** - Graph database
- **Qdrant** - Vector database

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VECTADB_URL` | `http://localhost:3000` | VectaDB API endpoint |
| `SURREALDB_URL` | `http://localhost:8000` | SurrealDB HTTP endpoint |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant REST API endpoint |

## Exit Codes

### Bedrock Test
- `0` - All logs processed successfully
- `1` - Processing failed or VectaDB unavailable

### Database Verification
- `0` - All databases healthy and accessible
- `1` - One or more databases unhealthy

## CI/CD Integration

### GitHub Actions Example

```yaml
name: VectaDB Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      surrealdb:
        image: surrealdb/surrealdb:latest
        ports:
          - 8000:8000
        options: >-
          start --user root --pass root memory

      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - 6333:6333

    steps:
      - uses: actions/checkout@v3

      - name: Start VectaDB
        run: |
          cd vectadb
          cargo run --release &
          sleep 10

      - name: Run Bedrock Test
        run: |
          cd test
          ./run_test.sh

      - name: Verify Databases
        run: |
          cd test
          ./verify_databases.sh
```

## Performance Benchmarks

### Typical Performance (MacBook Pro M1)

| Operation | Duration |
|-----------|----------|
| Bedrock test (27 entries) | 5-8 seconds |
| Database verification | 2-4 seconds |
| Single log ingestion | ~100-200ms |
| Semantic search (10 results) | ~50-100ms |
| Vector search (Qdrant) | ~10-30ms |

## Future Enhancements

### Planned Features
- [ ] Streaming log ingestion
- [ ] Real-time analytics dashboard
- [ ] Multi-model comparison tests
- [ ] Load testing suite
- [ ] Performance regression detection
- [ ] Automated test report generation

### Additional Test Scenarios
- [ ] Large-scale ingestion (1000+ logs)
- [ ] Concurrent client simulation
- [ ] Database failover testing
- [ ] Data consistency validation
- [ ] Schema migration testing

## Contributing

To add new tests:

1. Create new `.rs` file in `test/`
2. Add binary entry to `Cargo.toml`
3. Create corresponding run script
4. Document in README.md
5. Add to this summary

## License

Apache 2.0 - Same as VectaDB

## Support

- **Issues**: https://github.com/anthropics/vectadb/issues
- **Documentation**: See README.md files in test directory
- **Examples**: Check `bedrock_chain_of_thought_logs.json` for data format

---

**Last Updated**: 2026-01-09
**Test Suite Version**: 1.0
**VectaDB Version**: 0.1.0
