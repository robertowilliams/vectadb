#!/bin/bash

# Demo script for testing VectaDB Schema Agent with Synthetic API
# Usage: ./demo_schema_agent.sh [your-api-key]

set -e

echo "================================================================================"
echo "VectaDB Schema Agent - Synthetic API Demo"
echo "================================================================================"
echo ""

# Check if API key provided as argument
if [ -n "$1" ]; then
    export SYNTHETIC_API_KEY="$1"
    echo "✅ Using API key from argument"
elif [ -n "$SYNTHETIC_API_KEY" ]; then
    echo "✅ Using API key from environment"
else
    echo "❌ ERROR: No API key provided"
    echo ""
    echo "Usage:"
    echo "  ./demo_schema_agent.sh YOUR_API_KEY"
    echo ""
    echo "Or set it in your environment:"
    echo "  export SYNTHETIC_API_KEY=your_key"
    echo "  ./demo_schema_agent.sh"
    echo ""
    echo "Get your API key from: https://glhf.chat"
    exit 1
fi

# Check if VectaDB is running
echo ""
echo "🔍 Checking VectaDB status..."
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ VectaDB is running"
    ONTOLOGY_STATUS=$(curl -s http://localhost:8080/health | python3 -c "import sys, json; print(json.load(sys.stdin)['ontology_loaded'])")
    echo "   Ontology loaded: $ONTOLOGY_STATUS"
else
    echo "❌ VectaDB is not running on port 8080"
    echo "   Start it with: cd vectadb && cargo run --release"
    exit 1
fi

# Check if schema file exists
echo ""
echo "📄 Checking schema file..."
if [ -f "bedrock_schema.json" ]; then
    echo "✅ Found bedrock_schema.json"
    NAMESPACE=$(python3 -c "import sys, json; print(json.load(open('bedrock_schema.json'))['namespace'])" 2>/dev/null || echo "unknown")
    echo "   Namespace: $NAMESPACE"
else
    echo "❌ bedrock_schema.json not found"
    exit 1
fi

# Test Synthetic API connection
echo ""
echo "🔌 Testing Synthetic API connection..."
TEST_RESPONSE=$(curl -s -X POST https://api.glhf.chat/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $SYNTHETIC_API_KEY" \
    -d '{
        "model": "hf:zai-org/GLM-4.7",
        "messages": [{"role": "user", "content": "Say only: API works"}],
        "max_tokens": 10
    }' 2>&1)

if echo "$TEST_RESPONSE" | grep -q '"choices"'; then
    echo "✅ Synthetic API is responding"
    echo "   Model: GLM-4.7"
else
    echo "❌ Synthetic API test failed"
    echo "   Response: $TEST_RESPONSE"
    echo ""
    echo "Common issues:"
    echo "  - Invalid API key"
    echo "  - No internet connection"
    echo "  - API rate limit exceeded"
    exit 1
fi

# Run the schema agent
echo ""
echo "================================================================================"
echo "🚀 Running Schema Agent with GLM-4.7"
echo "================================================================================"
echo ""

python3 vectadb_schema_agent.py \
    --model glm-4.7 \
    --api-base "https://api.glhf.chat/v1" \
    --api-key "$SYNTHETIC_API_KEY" \
    --schema-file bedrock_schema.json \
    --format json

# Check result
echo ""
echo "================================================================================"
echo "📊 Verifying Result"
echo "================================================================================"
echo ""

ONTOLOGY_STATUS=$(curl -s http://localhost:8080/health | python3 -c "import sys, json; d=json.load(sys.stdin); print('Loaded:', d['ontology_loaded'], '| Namespace:', d.get('ontology_namespace', 'none'))")
echo "VectaDB Status: $ONTOLOGY_STATUS"

if curl -s http://localhost:8080/health | python3 -c "import sys, json; exit(0 if json.load(sys.stdin)['ontology_loaded'] else 1)"; then
    echo ""
    echo "✅ SUCCESS! Schema has been uploaded to VectaDB"
    echo ""
    echo "Next steps:"
    echo "  1. Ingest data:    python3 ingest_bedrock_graph.py"
    echo "  2. View graph:     open http://localhost:5173/graph"
    echo ""
else
    echo ""
    echo "⚠️  Schema upload may have failed. Check the output above for errors."
    echo ""
fi

echo "================================================================================"
