# Quick Start: VectaDB Schema Agent

Get your Bedrock logs into VectaDB in 5 minutes using AI-powered schema fixing.

## Prerequisites

```bash
# 1. VectaDB running
cd vectadb && cargo run --release &

# 2. An LLM server (choose one):

# Option A: vLLM with DeepSeek-V3 (recommended)
vllm serve hf:deepseek-ai/DeepSeek-V3 --port 8000 &

# Option B: vLLM with Llama4 (faster, less GPU)
vllm serve hf:meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8 --port 8000 &

# Option C: Use a cloud API
# Set --api-base to your provider's URL
```

## Step 1: Fix the Schema (30 seconds)

```bash
python3 vectadb_schema_agent.py \
  --model deepseek-v3 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json \
  --format json
```

**What happens:**
- ✅ Agent loads your schema
- ✅ Tries to upload to VectaDB
- ✅ If error: analyzes it with LLM
- ✅ Generates corrected schema
- ✅ Uploads the fix
- ✅ Saves corrected version

## Step 2: Verify Schema (5 seconds)

```bash
curl http://localhost:8080/health | jq '.'
```

**Look for:**
```json
{
  "ontology_loaded": true,
  "ontology_namespace": "bedrock.healthcare",
  "ontology_version": "1.0.0"
}
```

## Step 3: Ingest Data (2 minutes)

```bash
python3 ingest_bedrock_graph.py
```

**What happens:**
- ✅ Loads bedrock_chain_of_thought_logs.json
- ✅ Creates BedrockRequest entities
- ✅ Creates Agent, Patient, ToolUse entities
- ✅ Creates relations between them
- ✅ Links requests sequentially

## Step 4: View in Graph UI (immediately)

```bash
open http://localhost:5173/graph
```

**You should see:**
- Interactive D3.js force-directed graph
- Colored nodes by type (Request, Agent, Patient, etc.)
- Edges showing relationships
- Click nodes to see details

---

## If Something Goes Wrong

### Agent can't fix the schema

**Try a more powerful model:**
```bash
python3 vectadb_schema_agent.py \
  --model deepseek-r1 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json
```

### Ingestion fails

**Check what was created:**
```bash
# List entities
curl http://localhost:8080/api/v1/entities | jq '.entities | length'

# List relations
curl http://localhost:8080/api/v1/relations | jq '.relations | length'
```

### Graph is empty

**Verify data exists:**
```bash
# Check health includes entity count
curl http://localhost:8080/health | jq '.'

# Manually refresh the graph page
open http://localhost:5173/graph
```

---

## Interactive Mode (Alternative)

If you prefer step-by-step guidance:

```bash
python3 vectadb_schema_agent.py \
  --model deepseek-v3 \
  --api-base http://localhost:8000 \
  --interactive
```

**Then choose:**
1. `3` - Fix and upload schema file
2. Enter `bedrock_schema.json`
3. Enter `json` for format

---

## Model Quick Reference

| Use Case | Model | Command |
|----------|-------|---------|
| **First try** | DeepSeek-V3 | `--model deepseek-v3` |
| **Best output** | Qwen3-235B | `--model qwen3-235b` |
| **Fastest** | GLM-4.7 | `--model glm-4` |
| **Balanced** | Llama4-Maverick | `--model llama4-maverick` |

---

## Complete End-to-End Example

```bash
# Terminal 1: Start VectaDB
cd vectadb
cargo run --release

# Terminal 2: Start LLM
vllm serve hf:deepseek-ai/DeepSeek-V3 --port 8000

# Terminal 3: Run workflow
cd ..

# Fix schema
python3 vectadb_schema_agent.py \
  --model deepseek-v3 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json

# Verify
curl http://localhost:8080/health | jq '.ontology_loaded'
# Should output: true

# Ingest data
python3 ingest_bedrock_graph.py

# Check results
curl http://localhost:8080/api/v1/entities | jq '.entities | length'

# Open graph UI
open http://localhost:5173/graph
```

---

## Expected Timeline

| Step | Time | What You See |
|------|------|--------------|
| Schema fix | 30s | LLM analyzes error, generates fix |
| Verify | 5s | `ontology_loaded: true` |
| Ingestion | 2min | Progress for each entity/relation |
| View graph | instant | Interactive visualization |

**Total: ~3 minutes**

---

## Success Indicators

✅ Schema uploaded:
```bash
$ curl http://localhost:8080/health | jq '.ontology_loaded'
true
```

✅ Data ingested:
```bash
$ curl http://localhost:8080/api/v1/entities | jq '.entities | length'
50+
```

✅ Graph visible:
- Open http://localhost:5173/graph
- See colored nodes
- Can drag/zoom/click

---

## Next Steps

Once you have data in the graph:

1. **Explore the visualization**
   - Drag nodes around
   - Zoom in/out
   - Click nodes to see properties
   - Click edges to see relation details

2. **Adjust the physics**
   - Click "Show Controls"
   - Adjust charge strength
   - Change link distance
   - Modify collision radius

3. **Query the data**
   - Use the Graph view filters
   - Search for specific entities
   - Follow relationship chains

---

## Common Issues & Solutions

### "LLM API not responding"
```bash
# Check if running
curl http://localhost:8000/v1/models

# If not, start it
vllm serve <model-name> --port 8000
```

### "VectaDB not accessible"
```bash
# Check if running
curl http://localhost:8080/health

# If not, start it
cd vectadb && cargo run --release
```

### "Schema still failing after fix"
```bash
# Try stronger model
python3 vectadb_schema_agent.py \
  --model deepseek-r1 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema_corrected.json
```

### "No data in graph"
```bash
# Check if entities were created
curl http://localhost:8080/api/v1/entities

# Re-run ingestion if needed
python3 ingest_bedrock_graph.py
```

---

## That's It!

You should now have:
- ✅ Working schema uploaded
- ✅ Bedrock logs ingested as entities
- ✅ Relations showing interactions
- ✅ Interactive graph visualization

**Questions?** Check:
- SCHEMA_AGENT_README.md - Full documentation
- MODEL_SELECTION_GUIDE.md - Choosing the right model
- AGENT_SUMMARY.md - Overview and architecture

**Happy graphing! 🎉**
