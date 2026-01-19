# Quick Start Guide

## Test VectaDB in 5 Steps

### 1. Start VectaDB

Open a terminal and start VectaDB:

```bash
cd vectadb
cargo run --release
```

Wait for the message: `🚀 VectaDB server listening on 0.0.0.0:3000`

### 2. Ingest Bedrock Logs as Graph

Open another terminal and ingest test data as graph structure:

```bash
cd test
./ingest_as_graph.sh
```

This ingests AWS Bedrock logs as **nodes and edges** while automatically generating **embeddings** for semantic search. You get both graph database (SurrealDB) and vector database (Qdrant) populated in one operation.

### 3. Verify Database Storage

Confirm data was stored in both databases:

```bash
./verify_databases.sh
```

### 4. Test Graph Database

Test graph functionality (entities and relations):

```bash
./test_graph.sh
```

### 5. View Results

The graph ingestion will:
- ✅ Load 27 Bedrock log entries
- ✅ Create 17 nodes (Request, Response, UserQuery, ToolCall, ToolResult, Error, etc.)
- ✅ Create 15 edges (triggers, produces, invokes, returns, etc.)
- ✅ Generate embeddings for each node automatically
- ✅ Store graph in SurrealDB + embeddings in Qdrant
- ✅ Enable both graph traversal and semantic search

## What You'll See

```
╔════════════════════════════════════════╗
║   BEDROCK GRAPH INGESTION             ║
║   AWS Bedrock Logs → Graph Database   ║
╚════════════════════════════════════════╝

✅ VectaDB is healthy
📊 Reading Bedrock log file...
📦 Found 27 log entries

🔄 Starting graph ingestion...
   ✅ Processed entry 1/27
   ✅ Processed entry 6/27
   ...
   ✅ Processed entry 26/27

╔════════════════════════════════════════╗
║     GRAPH INGESTION SUMMARY           ║
╚════════════════════════════════════════╝

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

✨ Graph ingestion completed successfully!
```

## What's Being Tested

The test processes real AWS Bedrock logs from a healthcare LLM agent:
- Claude Haiku 4.5 model
- Patient immunization queries
- FHIR API tool calls (searchImmunization, getPatient, etc.)
- Error handling and retries
- Rate limiting (throttling exceptions)

**Graph representation:**
- Logs become nodes (Request, Response, ToolCall, etc.)
- Relationships become edges (triggers, produces, invokes, returns)
- Embeddings automatically generated from node properties

## Key Features Demonstrated

1. **Graph Ingestion**: Logs stored as connected graph structure
2. **Dual Storage**: Graph in SurrealDB + Embeddings in Qdrant (automatic)
3. **Semantic Search**: Find similar events using vector search
4. **Graph Traversal**: Follow conversation flow through edges
5. **Hybrid Queries**: Combine graph patterns with semantic similarity
6. **Causality Tracking**: See how errors propagate through tool chains

## Next Steps

- Read the full [README.md](README.md) for detailed information
- Check [BEDROCK_GRAPH_INGESTION.md](BEDROCK_GRAPH_INGESTION.md) for graph details
- Explore the implementation: [bedrock_graph_ingestion.rs](bedrock_graph_ingestion.rs)
- View the source data: [bedrock_chain_of_thought_logs.json](bedrock_chain_of_thought_logs.json)
- Learn about dual storage in the graph ingestion docs

## Troubleshooting

**Port already in use?**
```bash
# Change VectaDB port
PORT=8080 cargo run --release

# Update test
VECTADB_URL=http://localhost:8080 cargo run --release
```

**Need help?**
- Check [README.md](README.md) for detailed troubleshooting
- Review VectaDB logs for errors
