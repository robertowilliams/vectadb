# VectaDB Schema Agent - Models Update Summary

## What Was Updated

The VectaDB Schema Agent has been enhanced with **14 different LLM models** from your provided list, organized into tiers and with full environment variable support.

## Files Created/Updated

### 1. Updated Agent (`vectadb_schema_agent.py`)
- ✅ Added 14 models from your list
- ✅ Organized into 6 tiers (Premium, Structured Output, Fast, Specialized, Budget, Coding)
- ✅ Added provider information
- ✅ Added pricing details
- ✅ Added tier classifications

### 2. Environment Configuration (`.env.models.example`)
- ✅ Environment variables for all 14 models
- ✅ Detailed comments and usage examples
- ✅ Cost optimization tips
- ✅ Model selection guide
- ✅ Default model configuration

### 3. Model Config Loader (`model_config.py`)
- ✅ Loads models from `.env.models` file
- ✅ Supports variable interpolation
- ✅ Lists configured models
- ✅ Provides configuration summaries
- ✅ CLI tool for testing

### 4. Wrapper Script (`run_schema_agent.sh`)
- ✅ Simplified command-line interface
- ✅ Auto-loads environment configuration
- ✅ Checks VectaDB status
- ✅ Colored output
- ✅ Built-in help

### 5. Quick Reference (`MODEL_QUICK_REFERENCE.md`)
- ✅ One-page guide for all models
- ✅ Quick decision matrix
- ✅ Cost comparisons
- ✅ Context length comparisons
- ✅ Common workflows

## The 14 Models

### Tier 1: Premium (Complex Reasoning)
1. **DeepSeek V3.2** ⭐ - Latest with 162K context
2. **DeepSeek V3** - Original proven version
3. **DeepSeek R1** - Advanced reasoning

### Tier 2: Structured Output
4. **Qwen3-235B Instruct** ⭐ - Best formatting
5. **Qwen3-235B Thinking** - Reasoning + output

### Tier 3: Fast & Efficient
6. **Llama 4 Maverick** ⭐ - 536K context, multimodal
7. **Llama 3.3 70B** - Reliable and proven

### Tier 4: Specialized
8. **Kimi K2 Thinking** - 262K context reasoning
9. **Kimi K2 Instruct** - Instruction-following
10. **Qwen3 Coder** ⭐ - Code/schema specialist

### Tier 5: Budget-Friendly
11. **GLM 4.7** ⭐ - Best budget option
12. **GLM 4.6** - Alternative GLM
13. **MiniMax M2** - Ultra cheap
14. **GPT-OSS-120B** - Extremely cheap ($0.10/1M tokens!)

## Environment Variables Created

```bash
# Models with environment variables:
DEEPSEEK_V32_MODEL          # DeepSeek V3.2
DEEPSEEK_V3_MODEL           # DeepSeek V3
DEEPSEEK_R1_MODEL           # DeepSeek R1
QWEN3_235B_MODEL            # Qwen3-235B Instruct
QWEN3_235B_THINKING_MODEL   # Qwen3-235B Thinking
LLAMA4_MAVERICK_MODEL       # Llama 4 Maverick
LLAMA_33_70B_MODEL          # Llama 3.3 70B
KIMI_K2_THINKING_MODEL      # Kimi K2 Thinking
KIMI_K2_INSTRUCT_MODEL      # Kimi K2 Instruct
QWEN3_CODER_MODEL           # Qwen3 Coder
GLM_47_MODEL                # GLM 4.7
GLM_46_MODEL                # GLM 4.6
MINIMAX_M2_MODEL            # MiniMax M2
GPT_OSS_MODEL               # GPT-OSS-120B

# Plus configuration:
LLM_API_BASE                # Default API endpoint
LLM_API_KEY                 # Optional API key
VECTADB_URL                 # VectaDB backend
DEFAULT_MODEL               # Default model to use
```

## Recommended Models for Your Use Case

### For Bedrock Schema (Your Task)

**Primary: DeepSeek V3.2**
```bash
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```
- Best reasoning capability
- Extended context (162K)
- Excellent error analysis
- Good price/performance

**Backup: Qwen3-235B**
```bash
./run_schema_agent.sh qwen3-235b bedrock_schema.json
```
- Best for clean output
- Perfect JSON/YAML formatting
- Excellent structured generation

**Testing: GLM-4.7**
```bash
./run_schema_agent.sh glm-4.7 bedrock_schema.json
```
- Fast and cheap
- Good for iteration
- Large context (202K)

## Quick Start

### 1. Setup Environment
```bash
# Copy example config
cp .env.models.example .env.models

# Edit if needed (or use as-is)
nano .env.models

# Set default model
echo "DEFAULT_MODEL=deepseek-v3.2" >> .env.models
```

### 2. Run the Agent
```bash
# Using wrapper (easiest)
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json

# Or direct Python
python vectadb_schema_agent.py \
  --model deepseek-v3.2 \
  --schema-file bedrock_schema.json
```

### 3. Interactive Mode
```bash
./run_schema_agent.sh deepseek-v3.2 - interactive
```

## Usage Examples

### Example 1: Fix Bedrock Schema
```bash
# Best model for complex errors
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```

### Example 2: Generate Schema from Data
```bash
# Use code specialist
./run_schema_agent.sh qwen3-coder - interactive
# Select option 2, point to bedrock_chain_of_thought_logs.json
```

### Example 3: Quick Testing
```bash
# Cheap and fast
./run_schema_agent.sh glm-4.7 bedrock_schema.json
```

### Example 4: List Configured Models
```bash
./run_schema_agent.sh - - list
```

### Example 5: Best Formatting
```bash
# Clean, production-ready output
./run_schema_agent.sh qwen3-235b bedrock_schema.json
```

## Model Selection Flowchart

```
Start: Need to fix schema
│
├─ First time? → DeepSeek V3.2 ⭐
├─ Need clean output? → Qwen3-235B
├─ Budget constraint? → GLM-4.7
├─ Huge schema (>100K)? → Llama4-Maverick (536K context!)
├─ Previous fix failed? → DeepSeek R1
├─ Code-heavy? → Qwen3-Coder
└─ Just testing? → MiniMax-M2 or GPT-OSS
```

## Cost Optimization Strategy

### Strategy 1: Start Cheap
```bash
# Try cheapest first
./run_schema_agent.sh gpt-oss-120b schema.json

# If fails, upgrade
./run_schema_agent.sh glm-4.7 schema.json

# If still fails, go premium
./run_schema_agent.sh deepseek-v3.2 schema.json
```

### Strategy 2: Start Strong
```bash
# Use best first (usually works first try)
./run_schema_agent.sh deepseek-v3.2 schema.json

# Total cost: ~$0.01 for typical schema
```

### Strategy 3: Iterative Development
```bash
# Fast, cheap iterations
for i in {1..10}; do
  ./run_schema_agent.sh glm-4.7 schema_v$i.json
done

# Final polish with best
./run_schema_agent.sh qwen3-235b schema_final.json
```

## Provider Information

Models are hosted on three providers:

1. **Fireworks AI** - Most models, good performance
2. **Together AI** - DeepSeek V3, Qwen3 Thinking
3. **Synthetic** - GLM-4.7, Kimi K2 Thinking

All accessible via OpenAI-compatible API.

## Context Lengths

Important for large schemas:

- **Llama4-Maverick**: 536K (Largest!)
- **Qwen3-235B**: 262K
- **Qwen3-Coder**: 262K
- **Kimi K2**: 262K
- **GLM-4.7**: 202K
- **DeepSeek V3.2**: 162K
- **Most others**: 131K

## Pricing (per 1M tokens)

**Ultra-Cheap:**
- GPT-OSS: $0.10
- MiniMax-M2: $0.30-$1.20

**Budget:**
- GLM-4.7: $0.55-$2.19
- Qwen3-235B: $0.22-$0.88
- Llama4-Maverick: $0.22-$0.88

**Standard:**
- DeepSeek V3.2: $0.56-$1.68
- DeepSeek V3: $1.25
- Qwen3-Coder: $0.45-$1.80

**Premium:**
- Qwen3-Thinking: $0.65-$3.00
- DeepSeek R1: $3.00-$8.00

## Features by Model

### Best Reasoning
1. DeepSeek R1
2. DeepSeek V3.2
3. Qwen3-235B Thinking

### Best Formatting
1. Qwen3-235B
2. Qwen3-Coder
3. Qwen3-235B Thinking

### Best Speed
1. GLM-4.7
2. MiniMax-M2
3. Llama4-Maverick

### Best Context
1. Llama4-Maverick (536K)
2. Qwen3 family (262K)
3. Kimi K2 (262K)

### Best Value
1. GLM-4.7 (cheap + large context)
2. Llama4-Maverick (fast + huge context)
3. Qwen3-235B (quality + price)

## Integration with Existing Scripts

The new models work seamlessly with existing ingestion:

```bash
# 1. Fix schema with agent
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json

# 2. Verify
curl http://localhost:8080/health | jq '.ontology_loaded'

# 3. Ingest (existing script)
python ingest_bedrock_graph.py

# 4. View (existing UI)
open http://localhost:5173/graph
```

## Testing

```bash
# Test model configuration
python model_config.py --list

# Test specific model
python model_config.py --model deepseek-v3.2

# Test agent with model
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```

## Troubleshooting

### Model not found
```bash
# Check configuration
python model_config.py --list

# Make sure model is in .env.models
grep DEEPSEEK_V32 .env.models
```

### API not responding
```bash
# Check LLM API
curl http://localhost:8000/v1/models

# Or use remote API
LLM_API_BASE=http://remote:8000 ./run_schema_agent.sh deepseek-v3.2 schema.json
```

### Wrong format in .env.models
```bash
# Make sure format is:
MODEL_NAME=hf:org/model-name
MODEL_API_BASE=${LLM_API_BASE}

# Not:
MODEL_NAME: hf:org/model-name  # YAML format won't work
```

## Next Steps

1. **Copy environment config**
   ```bash
   cp .env.models.example .env.models
   ```

2. **Choose your model**
   - DeepSeek V3.2 for complex fixes
   - Qwen3-235B for clean output
   - GLM-4.7 for testing

3. **Run the agent**
   ```bash
   ./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
   ```

4. **Ingest and visualize**
   ```bash
   python ingest_bedrock_graph.py
   open http://localhost:5173/graph
   ```

## Summary

✅ **14 models** added from your list
✅ **Environment variables** for easy configuration
✅ **Tier system** for easy selection
✅ **Wrapper script** for simple usage
✅ **Full documentation** with examples
✅ **Cost optimization** strategies
✅ **Ready to use** right now!

**Recommended for Bedrock schema:**
```bash
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```

This gives you the best chance of success on the first try! 🚀
