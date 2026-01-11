#!/bin/bash
#
# VectaDB Schema Agent Runner
# Simplified wrapper that loads configuration from .env.models
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}VectaDB Schema Agent${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if .env.models exists
if [ ! -f ".env.models" ]; then
    echo -e "${YELLOW}⚠️  .env.models not found${NC}"
    echo "Creating from example..."

    if [ -f ".env.models.example" ]; then
        cp .env.models.example .env.models
        echo -e "${GREEN}✅ Created .env.models from example${NC}"
        echo "Edit .env.models to configure your models"
        echo ""
    else
        echo -e "${RED}❌ .env.models.example not found${NC}"
        exit 1
    fi
fi

# Load environment variables
export $(grep -v '^#' .env.models | grep -v '^$' | xargs)

# Check for model_config.py
if [ ! -f "model_config.py" ]; then
    echo -e "${RED}❌ model_config.py not found${NC}"
    exit 1
fi

# Parse command line arguments
MODEL="${1:-}"
SCHEMA_FILE="${2:-}"
ACTION="${3:-fix}"

# Show usage if no arguments
if [ -z "$SCHEMA_FILE" ]; then
    echo "Usage: $0 <model> <schema-file> [action]"
    echo ""
    echo "Models:"
    echo "  deepseek-v3.2       Latest DeepSeek with extended context (recommended)"
    echo "  deepseek-v3         Original DeepSeek V3"
    echo "  deepseek-r1         Advanced reasoning"
    echo "  qwen3-235b          Best structured output"
    echo "  qwen3-235b-thinking Reasoning + structured output"
    echo "  llama4-maverick     Fast and balanced"
    echo "  llama-3.3-70b       Reliable and proven"
    echo "  kimi-k2-thinking    Large context (262K)"
    echo "  qwen3-coder         Code specialist"
    echo "  glm-4.7             Lightweight and cheap"
    echo "  minimax-m2          Ultra cheap"
    echo ""
    echo "Actions:"
    echo "  fix        Fix and upload schema (default)"
    echo "  analyze    Analyze errors only"
    echo "  generate   Generate from sample data"
    echo "  interactive Interactive mode"
    echo "  list       List configured models"
    echo ""
    echo "Examples:"
    echo "  $0 deepseek-v3.2 bedrock_schema.json"
    echo "  $0 qwen3-235b bedrock_schema.json fix"
    echo "  $0 glm-4.7 bedrock_schema.json analyze"
    echo "  $0 llama4-maverick - interactive"
    echo "  $0 - - list"
    echo ""
    exit 0
fi

# Handle special actions
if [ "$ACTION" = "list" ] || [ "$SCHEMA_FILE" = "list" ]; then
    python3 model_config.py --list
    exit 0
fi

if [ "$ACTION" = "interactive" ] || [ "$SCHEMA_FILE" = "interactive" ] || [ "$SCHEMA_FILE" = "-" ]; then
    echo -e "${BLUE}Starting interactive mode...${NC}"
    if [ -n "$MODEL" ] && [ "$MODEL" != "-" ]; then
        python3 vectadb_schema_agent.py --model "$MODEL" --interactive
    else
        python3 vectadb_schema_agent.py --interactive
    fi
    exit 0
fi

# Check if VectaDB is running
echo -e "${BLUE}🔍 Checking VectaDB status...${NC}"
VECTADB_URL="${VECTADB_URL:-http://localhost:8080}"

if curl -s "$VECTADB_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ VectaDB is running${NC}"
else
    echo -e "${RED}❌ VectaDB is not running at $VECTADB_URL${NC}"
    echo "Start it with: cd vectadb && cargo run --release"
    exit 1
fi

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo -e "${RED}❌ Schema file not found: $SCHEMA_FILE${NC}"
    exit 1
fi

# Determine format
FORMAT="json"
if [[ "$SCHEMA_FILE" == *.yaml ]] || [[ "$SCHEMA_FILE" == *.yml ]]; then
    FORMAT="yaml"
fi

echo -e "${BLUE}📄 Schema file: $SCHEMA_FILE${NC}"
echo -e "${BLUE}📋 Format: $FORMAT${NC}"
echo ""

# Run the agent
case "$ACTION" in
    fix)
        echo -e "${BLUE}🔧 Fixing and uploading schema...${NC}"
        if [ -n "$MODEL" ] && [ "$MODEL" != "-" ]; then
            python3 vectadb_schema_agent.py \
                --model "$MODEL" \
                --schema-file "$SCHEMA_FILE" \
                --format "$FORMAT"
        else
            python3 vectadb_schema_agent.py \
                --schema-file "$SCHEMA_FILE" \
                --format "$FORMAT"
        fi
        ;;

    analyze)
        echo -e "${BLUE}🔍 Analyzing schema...${NC}"
        echo "Note: This would be implemented to analyze without uploading"
        python3 vectadb_schema_agent.py \
            --model "${MODEL:-deepseek-v3.2}" \
            --schema-file "$SCHEMA_FILE" \
            --format "$FORMAT"
        ;;

    *)
        echo -e "${RED}❌ Unknown action: $ACTION${NC}"
        echo "Use: fix, analyze, generate, interactive, or list"
        exit 1
        ;;
esac

# Check result
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✅ Success!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Verify: curl $VECTADB_URL/health | jq '.ontology_loaded'"
    echo "  2. Ingest: python3 ingest_bedrock_graph.py"
    echo "  3. View: open http://localhost:5173/graph"
else
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}❌ Failed${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "Try:"
    echo "  - Different model: $0 deepseek-r1 $SCHEMA_FILE"
    echo "  - Interactive mode: $0 $MODEL - interactive"
    echo "  - Check logs above for errors"
fi
