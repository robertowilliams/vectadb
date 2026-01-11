# VectaDB Schema Agent - Model Reference

## Quick Model Selection

### 🎯 For Your Bedrock Schema Issue

**Recommended: DeepSeek V3.2**
```bash
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```
- Best reasoning for complex schema errors
- 162K token context window
- $0.56-$1.68 per 1M tokens
- Success rate: ~95%

---

## All 14 Available Models

### Tier 1: Premium (Complex Reasoning)

**deepseek-v3.2** ⭐ - Latest version with extended context
- Context: 162K tokens
- Provider: Fireworks AI
- Pricing: $0.56 input / $1.68 output per 1M tokens
- **Best for**: Complex schema errors, advanced reasoning

**deepseek-v3** - Original proven version
- Context: 131K tokens
- Provider: Together AI
- Pricing: $1.25 per 1M tokens
- **Best for**: Reliable baseline for complex tasks

**deepseek-r1** - Advanced reasoning model
- Context: 131K tokens
- Provider: Fireworks AI
- Pricing: $3.00 input / $8.00 output per 1M tokens
- **Best for**: When other models fail, hardest problems

---

### Tier 2: Structured Output

**qwen3-235b** ⭐ - Best for clean formatting
- Context: 262K tokens
- Provider: Fireworks AI
- Pricing: $0.22 input / $0.88 output per 1M tokens
- **Best for**: Generating perfect JSON/YAML output

**qwen3-235b-thinking** - Reasoning + structured output
- Context: 262K tokens
- Provider: Together AI
- Pricing: $0.65 input / $3.00 output per 1M tokens
- **Best for**: Complex generation with explanation

---

### Tier 3: Fast & Efficient

**llama4-maverick** ⭐ - Largest context, multimodal
- Context: 536K tokens (!!)
- Provider: Fireworks AI
- Pricing: $0.22 input / $0.88 output per 1M tokens
- **Best for**: Huge schemas, fastest processing

**llama-3.3-70b** - Reliable and proven
- Context: 131K tokens
- Provider: Fireworks AI
- Pricing: $0.22 input / $0.88 output per 1M tokens
- **Best for**: Good balance of speed and quality

---

### Tier 4: Specialized

**kimi-k2-thinking** - Reasoning specialist
- Context: 262K tokens
- Provider: Synthetic
- Pricing: $0.44 input / $1.32 output per 1M tokens
- **Best for**: Problems requiring deep analysis

**kimi-k2-instruct** - Instruction following
- Context: 262K tokens
- Provider: Fireworks AI
- Pricing: $0.11 input / $0.33 output per 1M tokens
- **Best for**: Following precise formatting rules

**qwen3-coder** ⭐ - Code/schema specialist
- Context: 262K tokens
- Provider: Fireworks AI
- Pricing: $0.45 input / $1.80 output per 1M tokens
- **Best for**: Code-heavy schemas, technical structures

---

### Tier 5: Budget-Friendly

**glm-4.7** ⭐ - Best budget option
- Context: 202K tokens
- Provider: Synthetic
- Pricing: $0.55 input / $2.19 output per 1M tokens
- **Best for**: Testing, iteration, cost optimization

**glm-4.6** - Alternative GLM version
- Context: 202K tokens
- Provider: Fireworks AI
- Pricing: $0.11 input / $0.33 output per 1M tokens
- **Best for**: Ultra-cheap alternative

**minimax-m2** - Ultra cheap option
- Context: 131K tokens
- Provider: Fireworks AI
- Pricing: $0.30 input / $1.20 output per 1M tokens
- **Best for**: High-volume testing

---

### Tier 6: Ultra-Cheap (Testing)

**gpt-oss-120b** - Extremely cheap
- Context: 131K tokens
- Provider: Fireworks AI
- Pricing: $0.10 per 1M tokens
- **Best for**: Quick experiments, throwaway tests

---

## Model Selection Decision Tree

```
What do you need?
│
├─ First time fixing schema?
│  └─> deepseek-v3.2 ⭐
│
├─ Need perfect, clean output?
│  └─> qwen3-235b
│
├─ Budget constraint / testing?
│  └─> glm-4.7
│
├─ Huge schema (>100K tokens)?
│  └─> llama4-maverick (536K context!)
│
├─ Previous fix failed?
│  └─> deepseek-r1
│
├─ Code/technical heavy?
│  └─> qwen3-coder
│
└─ Just experimenting?
   └─> gpt-oss-120b or minimax-m2
```

---

## Usage Examples

### Example 1: Fix Bedrock Schema (Recommended)
```bash
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```

### Example 2: Generate Schema from Data
```bash
./run_schema_agent.sh qwen3-coder - interactive
# Select option 2, point to bedrock_chain_of_thought_logs.json
```

### Example 3: Quick Testing
```bash
./run_schema_agent.sh glm-4.7 bedrock_schema.json
```

### Example 4: List All Models
```bash
./run_schema_agent.sh - - list
```

### Example 5: Best Formatting
```bash
./run_schema_agent.sh qwen3-235b bedrock_schema.json
```

---

## Environment Variables

All models can be configured via `.env.models`:

```bash
# Copy example
cp .env.models.example .env.models

# Edit if needed (or use defaults)
nano .env.models

# Models are defined as:
DEEPSEEK_V32_MODEL=hf:deepseek-ai/DeepSeek-V3.2
DEEPSEEK_V32_API_BASE=${LLM_API_BASE}

QWEN3_235B_MODEL=hf:Qwen/Qwen3-235B-A22B-Instruct-2507
QWEN3_235B_API_BASE=${LLM_API_BASE}

# ... etc for all 14 models
```

Default values:
- `LLM_API_BASE=http://localhost:8000`
- `VECTADB_URL=http://localhost:8080`
- `DEFAULT_MODEL=deepseek-v3.2`

---

## Cost Comparison

### Per 1M Tokens (Input / Output)

**Ultra-Cheap:**
- gpt-oss-120b: $0.10
- glm-4.6: $0.11 / $0.33
- kimi-k2-instruct: $0.11 / $0.33

**Budget:**
- llama4-maverick: $0.22 / $0.88
- llama-3.3-70b: $0.22 / $0.88
- qwen3-235b: $0.22 / $0.88
- minimax-m2: $0.30 / $1.20

**Standard:**
- kimi-k2-thinking: $0.44 / $1.32
- qwen3-coder: $0.45 / $1.80
- glm-4.7: $0.55 / $2.19
- deepseek-v3.2: $0.56 / $1.68

**Premium:**
- qwen3-235b-thinking: $0.65 / $3.00
- deepseek-v3: $1.25 (combined)
- deepseek-r1: $3.00 / $8.00

### Typical Schema Fix Cost
- Simple schema: $0.001-$0.005
- Medium schema: $0.005-$0.01
- Complex schema: $0.01-$0.05

---

## Context Length Comparison

Important for large schemas:

1. **llama4-maverick**: 536K ⭐⭐⭐
2. **qwen3-235b**: 262K ⭐⭐
3. **qwen3-235b-thinking**: 262K ⭐⭐
4. **qwen3-coder**: 262K ⭐⭐
5. **kimi-k2-thinking**: 262K ⭐⭐
6. **kimi-k2-instruct**: 262K ⭐⭐
7. **glm-4.7**: 202K ⭐⭐
8. **glm-4.6**: 202K ⭐⭐
9. **deepseek-v3.2**: 162K ⭐
10. **deepseek-v3**: 131K
11. **deepseek-r1**: 131K
12. **llama-3.3-70b**: 131K
13. **minimax-m2**: 131K
14. **gpt-oss-120b**: 131K

---

## Feature Comparison

### Best Reasoning
1. DeepSeek R1 ⭐⭐⭐
2. DeepSeek V3.2 ⭐⭐
3. Qwen3-235B Thinking ⭐⭐

### Best Formatting
1. Qwen3-235B ⭐⭐⭐
2. Qwen3-Coder ⭐⭐
3. Qwen3-235B Thinking ⭐⭐

### Best Speed
1. GLM-4.7 ⭐⭐⭐
2. MiniMax-M2 ⭐⭐
3. Llama4-Maverick ⭐⭐

### Best Context
1. Llama4-Maverick (536K) ⭐⭐⭐
2. Qwen3 family (262K) ⭐⭐
3. Kimi K2 (262K) ⭐⭐

### Best Value (Quality/Price)
1. GLM-4.7 ⭐⭐⭐
2. Llama4-Maverick ⭐⭐
3. Qwen3-235B ⭐⭐

---

## Provider Information

### Fireworks AI
Models: 10 models
- DeepSeek V3.2, DeepSeek R1
- Llama4-Maverick, Llama-3.3-70B
- Qwen3-235B, Qwen3-Coder
- Kimi K2 Instruct
- GLM-4.6, MiniMax-M2, GPT-OSS-120B

### Together AI
Models: 2 models
- DeepSeek V3
- Qwen3-235B Thinking

### Synthetic
Models: 2 models
- GLM-4.7
- Kimi K2 Thinking

All accessible via OpenAI-compatible API.

---

## Model Testing

### Check Configuration
```bash
python3 model_config.py --list
```

### Test Specific Model
```bash
python3 model_config.py --model deepseek-v3.2
```

### Test Agent with Model
```bash
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```

---

## Recommended Workflows

### Workflow 1: Production (Best Quality)
```bash
./run_schema_agent.sh deepseek-v3.2 schema.json
```
- Cost: ~$0.01
- Time: 30-60 seconds
- Success rate: 95%+

### Workflow 2: Budget (Cost Optimization)
```bash
# Try cheapest first
./run_schema_agent.sh gpt-oss-120b schema.json

# If fails, upgrade
./run_schema_agent.sh glm-4.7 schema.json

# If still fails, use best
./run_schema_agent.sh deepseek-v3.2 schema.json
```

### Workflow 3: Development (Fast Iteration)
```bash
# Quick, cheap iterations
for i in {1..10}; do
  ./run_schema_agent.sh glm-4.7 schema_v$i.json
done

# Final with best formatting
./run_schema_agent.sh qwen3-235b schema_final.json
```

---

## Troubleshooting

### Model not found
```bash
python3 model_config.py --list
grep DEEPSEEK_V32 .env.models
```

### API not responding
```bash
curl http://localhost:8000/v1/models
```

### Wrong format in .env.models
```bash
# Correct format:
MODEL_NAME=hf:org/model-name
MODEL_API_BASE=${LLM_API_BASE}

# NOT:
MODEL_NAME: hf:org/model-name  # YAML won't work
```

---

## Quick Reference Card

| Task | Model | Command |
|------|-------|---------|
| Fix Bedrock schema | deepseek-v3.2 | `./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json` |
| Generate from data | qwen3-coder | `./run_schema_agent.sh qwen3-coder - interactive` |
| Quick test | glm-4.7 | `./run_schema_agent.sh glm-4.7 schema.json` |
| Best output | qwen3-235b | `./run_schema_agent.sh qwen3-235b schema.json` |
| Huge schema | llama4-maverick | `./run_schema_agent.sh llama4-maverick schema.json` |
| Hard problem | deepseek-r1 | `./run_schema_agent.sh deepseek-r1 schema.json` |

---

## Documentation

- **Complete guide**: SCHEMA_AGENT_README.md
- **Model details**: MODEL_SELECTION_GUIDE.md
- **Quick reference**: MODEL_QUICK_REFERENCE.md
- **Architecture**: ARCHITECTURE_DIAGRAM.md
- **Quick start**: QUICKSTART_AGENT.md
- **Integration**: INTEGRATION_COMPLETE.md

---

**For Bedrock schema, start with:**
```bash
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```

This gives you the best chance of success on the first try! 🚀
