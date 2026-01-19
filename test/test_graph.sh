#!/bin/bash
# Test Graph Database - Validates SurrealDB graph functionality

set -e

echo "🔗 VectaDB Graph Database Test"
echo "==============================="
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

# Build and run the test
echo "🔨 Building graph test..."
cargo build --release --bin graph_database_test

echo ""
echo "🧪 Running graph database tests..."
echo ""

VECTADB_URL=${VECTADB_URL:-http://localhost:3000} \
  cargo run --release --bin graph_database_test

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ All graph tests passed!"
else
    echo ""
    echo "❌ Some graph tests failed!"
fi

exit $EXIT_CODE
