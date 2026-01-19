#!/bin/bash
# Verify Database Ingestion - Check if data was properly stored in SurrealDB and Qdrant

set -e

echo "🔍 VectaDB Database Verification"
echo "=================================="
echo ""

# Default URLs
SURREALDB_URL=${SURREALDB_URL:-http://localhost:8000}
QDRANT_URL=${QDRANT_URL:-http://localhost:6333}

echo "Configuration:"
echo "  SurrealDB: $SURREALDB_URL"
echo "  Qdrant:    $QDRANT_URL"
echo ""

# Build the verification tool
echo "🔨 Building verification tool..."
cargo build --release --bin database_verification

echo ""
echo "🧪 Running database verification..."
echo ""

# Run the verification
SURREALDB_URL=$SURREALDB_URL QDRANT_URL=$QDRANT_URL \
  cargo run --release --bin database_verification

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Database verification completed successfully!"
else
    echo ""
    echo "❌ Database verification failed!"
    echo ""
    echo "Make sure:"
    echo "  1. VectaDB is running"
    echo "  2. SurrealDB is accessible at $SURREALDB_URL"
    echo "  3. Qdrant is accessible at $QDRANT_URL"
    echo "  4. You have run bedrock_test to ingest data"
fi

exit $EXIT_CODE
