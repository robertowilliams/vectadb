#!/bin/bash
# Ingest Bedrock Logs as Graph - Store logs as nodes and edges in graph database

set -e

echo "🔗 Bedrock Graph Ingestion"
echo "============================"
echo ""

# Check if VectaDB is running
echo "🔍 Checking if VectaDB is running..."
if ! curl -s http://localhost:3000/health > /dev/null 2>&1; then
    echo "❌ VectaDB is not running on http://localhost:3000"
    echo ""
    echo "Please start VectaDB first:"
    echo "  cd vectadb"
    echo "  cargo run --release"
    echo ""
    exit 1
fi

echo "✅ VectaDB is running"
echo ""

# Build and run the ingestion
echo "🔨 Building graph ingestion..."
cargo build --release --bin bedrock_graph_ingestion

echo ""
echo "🧪 Ingesting Bedrock logs as graph..."
echo ""

VECTADB_URL=${VECTADB_URL:-http://localhost:3000} \
  cargo run --release --bin bedrock_graph_ingestion

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Graph ingestion completed!"
    echo ""
    echo "Next steps:"
    echo "  - Run './verify_databases.sh' to verify the graph data"
    echo "  - Check SurrealDB for entities (Request, Response, ToolCall, etc.)"
    echo "  - Check relations (triggers, produces, invokes, returns, etc.)"
else
    echo ""
    echo "❌ Graph ingestion failed!"
fi

exit $EXIT_CODE
