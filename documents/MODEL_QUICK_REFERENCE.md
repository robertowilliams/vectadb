# Model Quick Reference - VectaDB Schema Agent

## TL;DR - What to Use

```bash
# First-time schema fix (RECOMMENDED)
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json

# Best formatting
./run_schema_agent.sh qwen3-235b bedrock_schema.json

# Fastest/cheapest testing
./run_schema_agent.sh glm-4.7 bedrock_schema.json

# Code generation
./run_schema_agent.sh qwen3-coder bedrock_schema.json

# Interactive help
./run_schema_agent.sh deepseek-v3.2 - interactive
```

## Model Tiers

### 🏆 Tier 1: Premium (Complex Reasoning)

#### DeepSeek V3.2 ⭐ RECOMMENDED
```bash
Model: hf:deepseek-ai/DeepSeek-V3.2
Provider: Fireworks AI
Cost: $0.56/$1.68 per 1M tokens
Context: 162K tokens
```
**Use for:** First-time fixes, complex errors, large schemas
**Best at:** Understanding Rust/serde errors, multi-step debugging

#### DeepSeek V3
```bash
Model: hf:deepseek-ai/DeepSeek-V3
Provider: Together AI
Cost: $1.25 per 1M tokens
Context: 131K tokens
```
**Use for:** Complex reasoning, proven performance
**Best at:** Error analysis, root cause identification

#### DeepSeek R1
```bash
Model: hf:deepseek-ai/DeepSeek-R1-0528
Provider: Fireworks AI
Cost: $3.00/$8.00 per 1M tokens
Context: 131K tokens
```
**Use for:** Multi-step transformations, when others fail
**Best at:** Advanced reasoning with chain-of-thought

---

### 📊 Tier 2: Structured Output

#### Qwen3-235B Instruct ⭐ RECOMMENDED FOR GENERATION
```bash
Model: hf:Qwen/Qwen3-235B-A22B-Instruct-2507
Provider: Fireworks AI
Cost: $0.22/$0.88 per 1M tokens
Context: 262K tokens
```
**Use for:** Schema generation, clean formatting
**Best at:** Perfect JSON/YAML output

#### Qwen3-235B Thinking
```bash
Model: hf:Qwen/Qwen3-235B-A22B-Thinking-2507
Provider: Together AI
Cost: $0.65/$3.00 per 1M tokens
Context: 262K tokens
```
**Use for:** Complex reasoning + clean output
**Best at:** Combining reasoning with structured generation

---

### ⚡ Tier 3: Fast & Efficient

#### Llama 4 Maverick ⭐ RECOMMENDED FOR ITERATION
```bash
Model: hf:meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8
Provider: Fireworks AI
Cost: $0.22/$0.88 per 1M tokens
Context: 536K tokens (!)
```
**Use for:** Quick fixes, iterative development
**Best at:** Speed/quality balance, multimodal

#### Llama 3.3 70B
```bash
Model: hf:meta-llama/Llama-3.3-70B-Instruct
Provider: Fireworks AI
Cost: $0.90 per 1M tokens
Context: 131K tokens
```
**Use for:** Reliable standard validation
**Best at:** Proven performance, fast inference

---

### 🎯 Tier 4: Specialized

#### Kimi K2 Thinking
```bash
Model: hf:moonshotai/Kimi-K2-Thinking
Provider: Synthetic
Cost: $0.55 per 1M tokens
Context: 262K tokens
```
**Use for:** Large context reasoning
**Best at:** Complex analysis with huge schemas

#### Qwen3 Coder 480B ⭐ FOR CODE/SCHEMAS
```bash
Model: hf:Qwen/Qwen3-Coder-480B-A35B-Instruct
Provider: Fireworks AI
Cost: $0.45/$1.80 per 1M tokens
Context: 262K tokens
```
**Use for:** Schema generation from code
**Best at:** JSON/YAML/code formatting

---

### 💰 Tier 5: Budget-Friendly

#### GLM 4.7 ⭐ BEST BUDGET OPTION
```bash
Model: hf:zai-org/GLM-4.7
Provider: Synthetic
Cost: $0.55/$2.19 per 1M tokens
Context: 202K tokens
```
**Use for:** Testing, simple validation
**Best at:** Fast, cheap, large context

#### MiniMax M2
```bash
Model: hf:MiniMaxAI/MiniMax-M2
Provider: Fireworks AI
Cost: $0.30/$1.20 per 1M tokens
Context: 196K tokens
```
**Use for:** High-volume testing
**Best at:** Ultra-cheap, decent quality

#### GPT-OSS-120B
```bash
Model: hf:openai/gpt-oss-120b
Provider: Fireworks AI
Cost: $0.10 per 1M tokens (!)
Context: 131K tokens
```
**Use for:** Experimentation, massive scale
**Best at:** Cheapest option available

---

## Quick Decision Matrix

| Your Situation | Recommended Model | Command |
|----------------|-------------------|---------|
| First time fixing schema | DeepSeek V3.2 | `./run_schema_agent.sh deepseek-v3.2 schema.json` |
| Previous fix didn't work | DeepSeek R1 | `./run_schema_agent.sh deepseek-r1 schema.json` |
| Generating new schema | Qwen3-235B | `./run_schema_agent.sh qwen3-235b schema.json` |
| Need it fast | Llama4-Maverick | `./run_schema_agent.sh llama4-maverick schema.json` |
| Tight budget | GLM-4.7 | `./run_schema_agent.sh glm-4.7 schema.json` |
| Code-heavy schema | Qwen3-Coder | `./run_schema_agent.sh qwen3-coder schema.json` |
| Very large schema | Llama4-Maverick (536K!) | `./run_schema_agent.sh llama4-maverick schema.json` |
| Testing/development | MiniMax-M2 or GLM-4.7 | `./run_schema_agent.sh minimax-m2 schema.json` |

---

## Cost Comparison (per 1M tokens)

```
Ultra-Cheap:
  GPT-OSS-120B:    $0.10
  MiniMax M2:      $0.30-$1.20
  GLM-4.7:         $0.55-$2.19
  Kimi K2:         $0.55

Budget:
  DeepSeek V3.2:   $0.56-$1.68
  Llama4-Maverick: $0.22-$0.88
  Qwen3-235B:      $0.22-$0.88
  Llama 3.3:       $0.90

Standard:
  DeepSeek V3:     $1.25
  Qwen3-Coder:     $0.45-$1.80

Premium:
  Qwen3-Thinking:  $0.65-$3.00
  DeepSeek R1:     $3.00-$8.00
```

---

## Context Length Comparison

```
Huge (500K+):
  Llama4-Maverick: 536K ← Largest!

Large (200K+):
  Qwen3-235B:      262K
  Qwen3-Thinking:  262K
  Qwen3-Coder:     262K
  Kimi K2:         262K
  GLM-4.7:         202K
  MiniMax M2:      196K

Standard (130K+):
  DeepSeek V3.2:   162K
  All others:      131K
```

---

## For Your Bedrock Schema Task

### Primary Recommendation: DeepSeek V3.2
```bash
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```
**Why:** Best reasoning, extended context, good price

### Backup Option: Qwen3-235B
```bash
./run_schema_agent.sh qwen3-235b bedrock_schema.json
```
**Why:** Best formatting, clean output

### Testing/Iteration: Llama4-Maverick or GLM-4.7
```bash
# Fast and balanced
./run_schema_agent.sh llama4-maverick bedrock_schema.json

# Cheapest
./run_schema_agent.sh glm-4.7 bedrock_schema.json
```

---

## Environment Setup

### Option 1: Using .env.models (Recommended)

```bash
# Copy example
cp .env.models.example .env.models

# Edit with your preferred models
nano .env.models

# Set default model
DEFAULT_MODEL=deepseek-v3.2

# Run with wrapper
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```

### Option 2: Direct Python

```bash
# With environment
python vectadb_schema_agent.py \
  --model deepseek-v3.2 \
  --schema-file bedrock_schema.json

# Override API
python vectadb_schema_agent.py \
  --model qwen3-235b \
  --api-base http://remote-server:8000 \
  --schema-file bedrock_schema.json
```

---

## Common Workflows

### Workflow 1: First-Time Fix
```bash
# Use best reasoning
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json

# Verify
curl http://localhost:8080/health | jq '.ontology_loaded'

# Ingest
python ingest_bedrock_graph.py
```

### Workflow 2: Iterative Development
```bash
# Fast iteration
./run_schema_agent.sh llama4-maverick bedrock_schema.json

# Test again
./run_schema_agent.sh llama4-maverick bedrock_schema_v2.json

# Final polish
./run_schema_agent.sh qwen3-235b bedrock_schema_final.json
```

### Workflow 3: Budget Development
```bash
# Test with cheap model
./run_schema_agent.sh glm-4.7 bedrock_schema.json

# If it works, done!
# If not, upgrade to DeepSeek V3.2
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```

### Workflow 4: Generation from Data
```bash
# Use specialized model
./run_schema_agent.sh qwen3-coder - interactive

# Select option 2: Generate schema from sample data
# Point to: test/bedrock_chain_of_thought_logs.json
```

---

## Model Selection Tips

1. **Start cheap, upgrade if needed**
   - Try GLM-4.7 or MiniMax-M2 first
   - If fails → Llama4-Maverick
   - If still fails → DeepSeek V3.2
   - Last resort → DeepSeek R1

2. **Match model to task**
   - Error analysis → DeepSeek V3.2
   - Schema generation → Qwen3-235B or Qwen3-Coder
   - Quick fixes → Llama4-Maverick or GLM-4.7
   - Large schemas → Llama4-Maverick (536K context!)

3. **Consider iteration count**
   - One-shot → DeepSeek V3.2 (worth the cost)
   - Many iterations → GLM-4.7 (cheap)
   - Production → Qwen3-235B (clean output)

4. **Context matters**
   - Huge schemas → Llama4-Maverick (536K)
   - Standard → Any model
   - Multiple files → Llama4-Maverick or Qwen3-235B

---

## List All Configured Models

```bash
./run_schema_agent.sh - - list

# Or
python model_config.py --list
```

Shows:
- Which models are configured
- Their API endpoints
- Default model
- VectaDB URL

---

## Interactive Mode

```bash
# Best for learning
./run_schema_agent.sh deepseek-v3.2 - interactive

# Budget-friendly
./run_schema_agent.sh glm-4.7 - interactive
```

Interactive provides:
1. Error analysis
2. Schema generation
3. File fixing
4. Best practices

---

## Summary

**For Bedrock schema:** `deepseek-v3.2` or `qwen3-235b`
**For quick testing:** `glm-4.7` or `llama4-maverick`
**For production:** `qwen3-235b` (clean output)
**For budget:** `glm-4.7` or `minimax-m2`
**For huge schemas:** `llama4-maverick` (536K context)

**Recommended command:**
```bash
./run_schema_agent.sh deepseek-v3.2 bedrock_schema.json
```

This will give you the best chance of success on the first try! 🎯
