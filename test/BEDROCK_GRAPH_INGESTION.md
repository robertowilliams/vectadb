## Bedrock Graph Ingestion

This tool ingests AWS Bedrock chain-of-thought logs **as a graph structure** in SurrealDB, where each event becomes a **node** and relationships between events become **edges**.

## Purpose

Instead of storing logs as flat records, this creates a **rich graph representation** that captures the conversational flow, tool call chains, and error propagation patterns.

**What happens during ingestion:**
1. ✅ Creates **nodes** (entities) in SurrealDB with properties
2. ✅ Creates **edges** (relations) in SurrealDB linking nodes
3. ✅ **Automatically generates embeddings** from node properties
4. ✅ **Stores embeddings** in Qdrant for semantic search
5. ✅ Preserves all raw log data in node properties

**Result:** You get both:
- **Graph database** (SurrealDB) with nodes and edges for traversal
- **Vector database** (Qdrant) with embeddings for semantic search

## Graph Model

### Node Types (Entities)

| Node Type | Description | Properties |
|-----------|-------------|------------|
| `Request` | Initial request to Bedrock | request_id, timestamp, model_id, region, input_tokens |
| `Response` | Response from Bedrock | stop_reason, latency_ms, input_tokens, output_tokens, inference_region |
| `UserQuery` | User's text query | query, text_length |
| `AssistantResponse` | Assistant's text response | text, text_length |
| `ToolCall` | Tool invocation by assistant | tool_use_id, tool_name, tool_input |
| `ToolResult` | Result from tool execution | tool_use_id, result, is_error |
| `Error` | Error from tool or system | error_message, source |

### Edge Types (Relations)

| Edge Type | Source → Target | Meaning |
|-----------|-----------------|---------|
| `triggers` | UserQuery → Request | User query initiates request |
| `produces` | Request → Response | Request generates response |
| `contains` | Response → AssistantResponse | Response includes text |
| `invokes` | Response → ToolCall | Response calls tool |
| `returns` | ToolCall → ToolResult | Tool call produces result |
| `provides_context_to` | ToolResult → Request | Result provides context for next request |
| `contains` | ToolResult → Error | Result contains error |

## Graph Structure Example

For a typical Bedrock conversation flow:

```
┌────────────┐
│ UserQuery  │ "What immunizations does patient PAT001 need?"
└──────┬─────┘
       │ triggers
       ▼
┌────────────┐
│  Request   │ request_id: abc123, model: claude-haiku-4-5
└──────┬─────┘
       │ produces
       ▼
┌────────────┐
│  Response  │ stop_reason: tool_use, latency: 858ms
└──────┬─────┘
       │ invokes
       ▼
┌────────────┐
│  ToolCall  │ tool: searchImmunization, input: {patient_id: "PAT001"}
└──────┬─────┘
       │ returns
       ▼
┌────────────┐
│ ToolResult │ result: "Internal error occurred"
└──────┬─────┘
       │ contains
       ▼
┌────────────┐
│   Error    │ error_message: "Internal error occurred"
└────────────┘
       │ provides_context_to
       ▼
   (Next Request in conversation...)
```

## Complete Conversation Graph

The full graph for the Bedrock logs creates a **conversation flow**:

```
UserQuery1 → Request1 → Response1 → ToolCall1 → ToolResult1 → Error1
                                                       │
                                                       ▼ provides_context_to
UserQuery2 → Request2 → Response2 → ToolCall2 → ToolResult2 → Error2
                                                       │
                                                       ▼ provides_context_to
             Request3 → Response3 → AssistantResponse
```

This allows:
- **Conversation replay**: Follow the path through the graph
- **Error propagation tracking**: See how errors flow through the conversation
- **Tool usage analysis**: Find all tool calls and their results
- **Latency analysis**: Measure time between related events

## Running the Ingestion

### Quick Start

```bash
./ingest_as_graph.sh
```

### Manual Execution

```bash
cargo run --release --bin bedrock_graph_ingestion
```

### Custom VectaDB URL

```bash
VECTADB_URL=http://custom-host:3000 ./ingest_as_graph.sh
```

## Expected Output

```
╔════════════════════════════════════════╗
║   BEDROCK GRAPH INGESTION             ║
║   AWS Bedrock Logs → Graph Database   ║
╚════════════════════════════════════════╝

Configuration:
  VectaDB API: http://localhost:3000

✅ VectaDB is healthy

📊 Reading Bedrock log file: ./test/bedrock_chain_of_thought_logs.json
📦 Found 27 log entries

🔄 Starting graph ingestion...

   ✅ Processed entry 1/27
   ✅ Processed entry 6/27
   ✅ Processed entry 11/27
   ✅ Processed entry 16/27
   ✅ Processed entry 21/27
   ✅ Processed entry 26/27

✅ Graph ingestion complete!

╔════════════════════════════════════════╗
║     GRAPH INGESTION SUMMARY           ║
╚════════════════════════════════════════╝

  Requests Processed: 27

  Nodes Created:
    - Requests:           3
    - Responses:          3
    - User Queries:       2
    - Tool Calls:         3
    - Tool Results:       3
    - Errors:             3
    ─────────────────────────────────────
    Total Nodes:          17

  Edges Created:        15

  Graph Structure:
    UserQuery → triggers → Request
    Request → produces → Response
    Response → contains → AssistantResponse
    Response → invokes → ToolCall
    ToolCall → returns → ToolResult
    ToolResult → provides_context_to → Request
    ToolResult → contains → Error

✨ Graph ingestion completed successfully!
```

## Verifying the Graph

After ingestion, verify the graph was created:

```bash
./verify_databases.sh
```

Expected to see:
- **Entities**: 17 nodes (Request, Response, UserQuery, ToolCall, etc.)
- **Relations**: 15 edges connecting the nodes

## Querying the Graph

### Example Queries

Once ingested, you can query the graph using SurrealDB or VectaDB APIs:

#### 1. Find all user queries

```sql
SELECT * FROM entity WHERE entity_type = 'UserQuery'
```

#### 2. Find all errors

```sql
SELECT * FROM entity WHERE entity_type = 'Error'
```

#### 3. Find tool calls that resulted in errors

```sql
SELECT * FROM relation
WHERE relation_type = 'returns'
AND target_id IN (
    SELECT id FROM entity WHERE entity_type = 'ToolResult' AND properties.is_error = true
)
```

#### 4. Trace conversation flow

```sql
-- Start from a user query
SELECT * FROM entity WHERE entity_type = 'UserQuery'
-- Follow triggers → Request → produces → Response → invokes → ToolCall
```

## Graph Traversal Use Cases

### 1. Conversation Replay

Follow the path through the graph to reconstruct the full conversation:
1. Start at UserQuery
2. Follow `triggers` to Request
3. Follow `produces` to Response
4. Follow `invokes` to ToolCall(s)
5. Follow `returns` to ToolResult(s)
6. Follow `provides_context_to` to next Request
7. Repeat...

### 2. Error Root Cause Analysis

Find the original request that led to an error:
1. Start at Error node
2. Traverse backwards through `contains`
3. Find ToolResult
4. Traverse backwards through `returns`
5. Find ToolCall
6. Traverse backwards through `invokes`
7. Find Response
8. Traverse backwards through `produces`
9. Find original Request

### 3. Tool Success Rate

Query all ToolCall nodes and check their ToolResult nodes for errors.

### 4. Latency Analysis

Find paths with high latency:
1. Query Response nodes by `latency_ms`
2. Traverse to find which ToolCall caused delay
3. Analyze tool performance patterns

### 5. Retry Pattern Detection

Find sequences where same tool is called multiple times:
1. Group ToolCall nodes by tool_name
2. Find sequences with same tool_name
3. Analyze success/failure patterns

## Dual Database Storage

The graph ingestion stores data in **both databases simultaneously**:

### SurrealDB (Graph Database)
- **Nodes**: 7 entity types (Request, Response, UserQuery, etc.)
- **Edges**: 7 relation types (triggers, produces, invokes, etc.)
- **Properties**: All raw log data preserved
- **Purpose**: Graph traversal, relationship queries, causality tracking

### Qdrant (Vector Database)
- **Collections**: One per entity type (Request, Response, etc.)
- **Vectors**: Embeddings generated from text properties
- **Dimension**: 384 (default embedding model)
- **Purpose**: Semantic search, similarity queries, contextual retrieval

### Query Combinations

You can combine both:
1. **Graph query** → Find related nodes
2. **Vector search** → Find semantically similar nodes
3. **Hybrid** → Graph traversal + semantic similarity

Example: "Find all ToolCall nodes similar to 'search patient records' that returned errors"
- Vector search: Find similar ToolCall nodes
- Graph traversal: Follow `returns` edge to ToolResult nodes
- Filter: Where `is_error = true`

## Advantages Over Flat Log Storage

| Aspect | Flat Logs | Graph Structure |
|--------|-----------|-----------------|
| **Relationships** | Implicit (must infer) | Explicit (stored as edges) |
| **Traversal** | Complex queries | Natural graph traversal |
| **Causality** | Hidden | Visible in edges |
| **Context** | Scattered | Connected |
| **Analysis** | String matching | Graph algorithms + Vector search |
| **Visualization** | Linear timeline | Network diagram |
| **Embeddings** | Per log entry | Per graph node (more granular) |

## Graph Analytics Enabled

With the graph structure, you can now perform:

- **Path analysis**: Find common conversation patterns
- **Centrality**: Identify most-used tools or error-prone components
- **Clustering**: Group similar conversation flows
- **Anomaly detection**: Find unusual graph patterns
- **Impact analysis**: See cascading effects of errors
- **Dependency mapping**: Understand tool dependencies

## Comparison to Other Tests

| Test | Focus | Data Model |
|------|-------|------------|
| `bedrock_test.rs` | Log ingestion | Flat records in database |
| `bedrock_graph_ingestion.rs` | Graph ingestion | Nodes and edges in graph |
| `database_verification.rs` | Storage validation | Checks both approaches |
| `graph_database_test.rs` | Graph functionality | Tests graph operations |

## Integration Example

Typical workflow:

```bash
# 1. Ingest logs as graph structure
./ingest_as_graph.sh

# 2. Verify graph was created
./verify_databases.sh

# 3. Test graph functionality
./test_graph.sh

# 4. Query and analyze the graph
# (use SurrealDB queries or VectaDB API)
```

## Data Preservation

The graph ingestion preserves all original data:
- Request IDs for traceability
- Timestamps for temporal analysis
- Token counts for cost tracking
- Latency metrics for performance
- Full tool inputs/outputs
- Error messages and context

## Future Enhancements

Potential additions:
- [ ] Multi-turn conversation linking
- [ ] Agent node for tracking which agent made requests
- [ ] Session node for grouping conversations
- [ ] Performance metrics on edges (execution time)
- [ ] Confidence scores on relations
- [ ] Graph visualization export (Cypher, GraphML)
- [ ] Temporal graph queries
- [ ] Subgraph extraction by conversation

## Troubleshooting

### Ingestion Fails

**Issue**: Errors during ingestion

**Solutions**:
1. Check VectaDB is running
2. Verify log file exists
3. Check SurrealDB connection
4. Review error messages

### Duplicate Nodes

**Issue**: Running ingestion multiple times creates duplicates

**Solution**: The test creates new nodes each time. Clear database first:
```bash
# Clear all entities and relations
curl -X POST http://localhost:8000/sql \
  -H "Authorization: Basic $(echo -n 'root:root' | base64)" \
  -H "NS: vectadb" \
  -H "DB: main" \
  -d '{"query": "DELETE entity; DELETE relation;"}'
```

### Missing Relations

**Issue**: Some edges not created

**Possible causes**:
1. Tool results appear before tool calls (ordering)
2. Request IDs don't match
3. Partial log files

The ingestion handles ordering by storing mappings for later linking.

## Performance

- **Processing rate**: ~2-5 logs/second
- **Node creation**: ~100ms per node
- **Edge creation**: ~50ms per edge
- **Total time**: ~5-10 seconds for 27 log entries

## Related Documentation

- [README.md](README.md) - Main test suite docs
- [GRAPH_DATABASE_TEST.md](GRAPH_DATABASE_TEST.md) - Graph functionality test
- [DATABASE_VERIFICATION.md](DATABASE_VERIFICATION.md) - Verification test
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide

## License

Apache 2.0 - Same as VectaDB
