# VectaDB Schema Agent - Summary

## What Was Created

An intelligent agent system that uses external LLMs to automatically fix VectaDB schema issues and assist with data ingestion.

## Files Created

1. **vectadb_schema_agent.py** - Main agent implementation
2. **SCHEMA_AGENT_README.md** - Complete usage documentation
3. **MODEL_SELECTION_GUIDE.md** - Detailed model comparison and recommendations
4. **demo_schema_agent.sh** - Demo script showing agent usage

## Key Features

### 1. Automatic Schema Fixing
```bash
python vectadb_schema_agent.py \
  --model deepseek-v3 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json
```

The agent will:
- ✅ Load your schema
- ✅ Attempt to upload to VectaDB
- ✅ If it fails, analyze the error using LLM
- ✅ Generate corrected schema
- ✅ Upload the fixed version
- ✅ Save corrected schema to file

### 2. Schema Generation from Data
```python
# Generate schema from your Bedrock logs
sample_data = [
    {
        "timestamp": "2025-01-09T12:00:00Z",
        "request_id": "req-123",
        "model": "claude-3"
    }
]

schema = agent.generate_schema_from_sample(
    sample_data,
    namespace="bedrock.healthcare",
    version="1.0.0"
)
```

### 3. Interactive Troubleshooting
```bash
python vectadb_schema_agent.py --interactive
```

Provides:
- Error analysis
- Schema generation
- Best practices
- Step-by-step guidance

### 4. Multi-Model Support

The agent works with 5 different LLMs optimized for different tasks:

| Model | Best For | Resource Use |
|-------|----------|--------------|
| **DeepSeek-V3** ⭐ | Complex errors, reasoning | High |
| **Qwen3-235B** | Clean output generation | Very High |
| **DeepSeek-R1** | Advanced reasoning | High |
| **Llama4-Maverick** | Speed + quality balance | Medium |
| **GLM-4.7** | Quick fixes, low resources | Low |

## Recommended Approach for Bedrock Schema

### Step 1: Use the Agent to Fix the Schema

```bash
# Make sure VectaDB is running
cd vectadb && cargo run --release &

# Make sure your LLM server is running
vllm serve hf:deepseek-ai/DeepSeek-V3 --port 8000 &

# Run the agent
python vectadb_schema_agent.py \
  --model deepseek-v3 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json \
  --format json
```

### Step 2: Verify Schema Upload

```bash
curl http://localhost:8080/health | jq '.'
# Should show: "ontology_loaded": true
```

### Step 3: Run Bedrock Ingestion

```bash
python ingest_bedrock_graph.py
```

### Step 4: View in Graph UI

```bash
# Open browser to:
http://localhost:5173/graph
```

## Why This Approach Works

### Problem
VectaDB has strict schema requirements that don't match standard JSON Schema:
- Properties must be HashMaps (objects), not arrays
- Specific field naming (e.g., `entity_type` vs `type`)
- Rust serde deserialization rules

### Solution
The LLM agent:
1. **Understands the error messages** - Parses Rust/serde errors
2. **Knows VectaDB's structure** - Has the schema format in its system prompt
3. **Generates correct format** - Creates schemas that pass validation
4. **Iterates if needed** - Can try multiple fixes

### Agent Intelligence

The agent uses specialized prompts that include:

```python
system_prompt = """You are a VectaDB schema expert. VectaDB uses Rust with serde.

VectaDB Schema Structure:
- namespace: string
- version: string
- entity_types: HashMap<String, EntityType>  # Object, not array!
- relation_types: HashMap<String, RelationType>
- rules: Vec<InferenceRule>

EntityType:
- properties: HashMap<String, PropertyDefinition>  # Object!

CRITICAL: Properties must be HashMap (object/map), not array!
"""
```

This makes the LLM generate the **exact format** VectaDB expects.

## Model Recommendations

### For Your Bedrock Schema Issue

**Primary: DeepSeek-V3**
- Best reasoning capability
- Excellent error analysis
- Understands Rust/serde

**Alternative: Qwen3-235B**
- Best JSON formatting
- Great for generation from scratch

**Quick Testing: Llama4-Maverick**
- Faster, smaller
- Good for iteration

## Usage Patterns

### Pattern 1: One-Shot Fix
```bash
./demo_schema_agent.sh
```

### Pattern 2: Programmatic
```python
from vectadb_schema_agent import SchemaAgent

agent = SchemaAgent.create_with_model(
    "deepseek-v3",
    api_base="http://localhost:8000"
)

success = agent.fix_and_upload_schema("bedrock_schema.json", "json")
```

### Pattern 3: Interactive
```bash
python vectadb_schema_agent.py --interactive
# Choose option 3: Fix and upload schema file
```

## Integration with Existing Scripts

The agent complements your existing ingestion scripts:

```bash
# Old workflow (manual schema fixing)
1. Edit bedrock_schema.json
2. Try upload → fails
3. Read error, manually fix
4. Repeat until it works
5. Run ingestion

# New workflow (agent-assisted)
1. python vectadb_schema_agent.py --schema-file bedrock_schema.json
2. Run ingestion
```

## Expected Output

When successful:

```
================================================================================
VectaDB Schema Agent - Using DeepSeek-V3
================================================================================

📖 Loading schema from: bedrock_schema.json
✅ Schema loaded: bedrock.healthcare v1.0.0

🚀 Attempting to upload schema to VectaDB...
❌ Upload failed: 400
Error: invalid type: sequence, expected a map

🤖 Analyzing error with DeepSeek-V3...

📊 Error Analysis:
  Type: serde_deserialization
  Cause: Properties defined as array instead of HashMap
  Fix: Convert to object with property names as keys

🔧 Applying fix...
✅ Fixed schema uploaded successfully!
💾 Corrected schema saved to: bedrock_schema_corrected.json
```

## Next Steps

1. **Start your LLM server**
   ```bash
   vllm serve hf:deepseek-ai/DeepSeek-V3 --port 8000
   ```

2. **Run the agent**
   ```bash
   python vectadb_schema_agent.py \
     --model deepseek-v3 \
     --api-base http://localhost:8000 \
     --schema-file bedrock_schema.json
   ```

3. **Verify and ingest**
   ```bash
   curl http://localhost:8080/health
   python ingest_bedrock_graph.py
   ```

4. **View in UI**
   ```bash
   open http://localhost:5173/graph
   ```

## Benefits

✅ **Automatic**: No manual schema editing
✅ **Intelligent**: Understands complex error messages
✅ **Flexible**: Multiple model options
✅ **Educational**: Explains what went wrong
✅ **Saves Time**: Minutes instead of hours
✅ **Iterative**: Can fix multiple times if needed

## Resources

- **Main documentation**: SCHEMA_AGENT_README.md
- **Model selection**: MODEL_SELECTION_GUIDE.md
- **Quick demo**: ./demo_schema_agent.sh
- **Python API**: vectadb_schema_agent.py

## Support

The agent handles:
- ✅ Serde deserialization errors
- ✅ Type mismatches (array vs map)
- ✅ Missing required fields
- ✅ Invalid structure
- ✅ Format conversion (JSON ↔ YAML)

The agent **cannot** handle:
- ❌ Invalid business logic
- ❌ Missing LLM server
- ❌ VectaDB not running
- ❌ Network connectivity issues

For best results:
1. Use DeepSeek-V3 or Qwen3-235B
2. Provide complete error messages
3. Have VectaDB running locally
4. Ensure LLM API is accessible

---

**Ready to try it?**

```bash
# Quick start
python vectadb_schema_agent.py \
  --model deepseek-v3 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json
```

Good luck! The agent should be able to fix your Bedrock schema and get your data ingested into VectaDB. 🚀
