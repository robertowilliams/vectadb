#!/bin/bash
# Run VectaDB Bedrock Log Test

set -e

echo "🚀 VectaDB Bedrock Log Test Runner"
echo "===================================="
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
echo "🔨 Building test binary..."
cd "$(dirname "$0")"
cargo build --release

echo ""
echo "🧪 Running Bedrock log test..."
echo ""

VECTADB_URL=http://localhost:3000 cargo run --release

echo ""
echo "✨ Test completed!"
