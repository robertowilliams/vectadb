# VectaDB Bedrock Log Test

This test suite demonstrates VectaDB's observability capabilities for LLM agents by processing and analyzing real AWS Bedrock chain-of-thought logs.

## Overview

The test processes the `bedrock_chain_of_thought_logs.json` file containing Claude Haiku 4.5 interaction logs from AWS Bedrock. The logs capture a healthcare virtual assistant handling patient immunization queries with tool calls and error handling.

## What the Test Does

1. **Log Parsing**: Parses AWS Bedrock log entries in JSON format
2. **Data Extraction**: Extracts:
   - User queries and assistant responses
   - Tool calls (searchImmunization, getPatient, bookAppointment, getSlots)
   - Tool results and errors
   - System prompts and configurations
   - Throttling exceptions
   - Performance metrics (latency, token usage)

3. **VectaDB Storage**: Stores all extracted data as structured logs with:
   - Agent ID: `bedrock_claude_haiku_4_5`
   - Log levels: INFO, WARNING, ERROR
   - Rich metadata for each event
   - Automatic embedding generation for semantic search

4. **Semantic Queries**: Tests VectaDB's search capabilities:
   - Find error messages
   - Identify throttling issues
   - Search tool calls
   - Query patient-specific interactions
   - Analyze latency patterns

5. **Analytics**: Retrieves agent performance metrics and patterns

## Log File Details

The `bedrock_chain_of_thought_logs.json` file contains:
- **3 successful conversations** with complete request/response cycles
- **Multiple tool calls** to FHIR API (healthcare data system)
- **Internal errors** from tool execution
- **19 throttling exceptions** (ThrottlingException)
- **Token usage statistics** for each request
- **Latency metrics** ranging from 858ms to 2990ms
- **Multi-region inference** (us-east-2, eu-north-1, us-west-2, ap-northeast-2)

### Example Interaction Flow

1. User asks: "What immunizations does patient PAT001 need?"
2. Assistant calls tool: `searchImmunization(PAT001)`
3. Tool returns: Internal error
4. Assistant retries with: `getPatient(PAT001)`
5. Tool returns: Internal error
6. Assistant provides helpful error response to user
7. Multiple retry attempts hit throttling limits

## Prerequisites

1. **VectaDB running**: The database must be running on `http://localhost:3000`
2. **Dependencies**: Rust toolchain (automatically installed via Cargo)

## Running the Tests

### Option 1: Flat Log Ingestion

Ingest logs as flat records with embeddings for semantic search:

```bash
./run_test.sh
```

This stores logs as individual entities with vector embeddings.

### Option 2: Graph Structure Ingestion (Recommended)

Ingest logs as a **graph structure** with nodes and edges:

```bash
./ingest_as_graph.sh
```

This creates a rich graph representation:
- **Nodes**: Request, Response, UserQuery, ToolCall, ToolResult, Error
- **Edges**: triggers, produces, invokes, returns, provides_context_to, contains

**Advantages of graph ingestion:**
- Explicit relationships between events
- Conversation flow reconstruction
- Error causality tracking
- Tool usage chain analysis
- Natural graph traversal queries

See [BEDROCK_GRAPH_INGESTION.md](BEDROCK_GRAPH_INGESTION.md) for details.

### Manual Run

```bash
# Start VectaDB (in another terminal)
cd vectadb
cargo run --release

# Run the graph ingestion
cd test
cargo run --release --bin bedrock_graph_ingestion
```

## Expected Output

```
🚀 VectaDB Bedrock Log Test Suite
═══════════════════════════════════════

🏥 Checking VectaDB health...
✅ VectaDB is healthy: {...}

📂 Loading Bedrock logs from: ./test/bedrock_chain_of_thought_logs.json
📊 Processing 27 Bedrock log entries...
✅ Processed entry 0
✅ Processed entry 5
✅ Processed entry 10
...

📈 PROCESSING SUMMARY
═══════════════════════════════════════
Requests:             3
Responses:            3
User Messages:        2
Assistant Messages:   3
Tool Calls:           3
Tool Results:         3
Tool Errors:          3
Tool Configurations:  3
System Prompts:       3
Throttling Errors:    19
Processing Errors:    0
═══════════════════════════════════════

🔍 RUNNING TEST QUERIES
═══════════════════════════════════════

1️⃣  Query: Find all error-related logs
   Found 5 error-related logs

2️⃣  Query: Find throttling errors
   Found 19 throttling errors

3️⃣  Query: Find tool calls
   Found 3 tool call logs

4️⃣  Query: Find patient PAT001 queries
   Found 8 patient-related logs

5️⃣  Query: Find high latency responses
   Found 3 latency-related logs

═══════════════════════════════════════

📊 RETRIEVING ANALYTICS
═══════════════════════════════════════

Analytics: {...}

✨ Test suite completed successfully!
```

## What This Test Demonstrates

### 1. **Observability for LLM Agents**
- Complete conversation tracking
- Tool usage monitoring
- Error pattern detection
- Performance analysis

### 2. **Semantic Search Capabilities**
- Natural language queries over structured logs
- Contextual understanding of agent behavior
- Pattern matching across similar events

### 3. **Real-World Agent Scenarios**
- Multi-turn conversations
- Tool calling and error handling
- Retry logic and resilience
- Rate limiting and throttling

### 4. **Production-Ready Features**
- Bulk log ingestion
- Structured metadata preservation
- Time-series analysis ready
- Multi-agent support

## Key Insights from the Test Data

1. **Error Handling**: All 3 tool calls failed with internal errors, demonstrating the need for robust error tracking
2. **Throttling**: 19 throttling exceptions show the importance of rate limit monitoring
3. **Latency Variance**: Response times varied from 858ms to 2990ms, highlighting performance monitoring needs
4. **Multi-Region**: Requests routed to 4 different AWS regions, showing distributed system complexity
5. **Token Usage**: Total of 5,827 tokens across 3 conversations, useful for cost tracking

## Use Cases

This test validates VectaDB for:
- **LLM Agent Debugging**: Find why agents are making errors
- **Performance Monitoring**: Track latency and token usage
- **Tool Call Analysis**: Understand which tools are used and their success rates
- **Error Clustering**: Group similar errors for root cause analysis
- **Conversation Replay**: Reconstruct full agent interaction flows
- **Compliance & Auditing**: Complete audit trail of agent decisions

## Database Verification

After running the Bedrock test, you should verify that data was properly stored in both databases:

```bash
./verify_databases.sh
```

This will:
- ✅ Check SurrealDB connectivity and entity/relation counts
- ✅ Check Qdrant collections and vector counts
- ✅ Test vector similarity search
- ✅ Provide detailed statistics report

See [DATABASE_VERIFICATION.md](DATABASE_VERIFICATION.md) for details.

## Graph Database Testing

Test VectaDB's graph database functionality (entities and relations):

```bash
./test_graph.sh
```

This comprehensive test validates:
- ✅ Entity creation and retrieval
- ✅ Relation creation with properties
- ✅ Complex graph structures
- ✅ Bidirectional relations
- ✅ Multiple relation types
- ✅ Multi-level graph depth

See [GRAPH_DATABASE_TEST.md](GRAPH_DATABASE_TEST.md) for details.

## Next Steps

After running this test, you can:

1. **Verify Data Storage**: Run `./verify_databases.sh` to confirm data was ingested
2. **Explore the Data**: Use VectaDB's API to query the ingested logs
3. **Add More Logs**: Process your own Bedrock or other LLM logs
4. **Build Dashboards**: Use the analytics endpoint to create visualizations
5. **Set Up Alerts**: Monitor for specific error patterns or thresholds
6. **Compare Agents**: Load logs from different models/agents for comparison

## Troubleshooting

### VectaDB Not Running
```
❌ VectaDB health check failed: Connection refused
```
**Solution**: Start VectaDB first:
```bash
cd vectadb
cargo run --release
```

### Log File Not Found
```
❌ Failed to process log file: No such file or directory
```
**Solution**: Ensure you're running from the `test/` directory and the log file exists.

### Build Errors
**Solution**: Ensure Rust toolchain is installed:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

## Contributing

To extend this test:
1. Add more query patterns in `run_test_queries()`
2. Process additional log formats
3. Add custom analytics calculations
4. Integrate with other observability tools

## License

Apache 2.0 - Same as VectaDB
