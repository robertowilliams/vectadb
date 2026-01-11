# VectaDB Schema Agent

An intelligent agent that uses external LLMs to automatically fix VectaDB schema issues, generate schemas from sample data, and provide troubleshooting assistance.

## Features

- ✅ **Automatic Error Analysis** - Analyzes schema upload errors and provides detailed diagnostics
- ✅ **Schema Correction** - Automatically fixes common schema format issues
- ✅ **Schema Generation** - Generates VectaDB schemas from sample data
- ✅ **Interactive Mode** - Step-by-step troubleshooting and assistance
- ✅ **Multi-Model Support** - Works with various open-source LLMs via OpenAI-compatible API

## Recommended Models

The agent supports multiple LLMs, each optimized for different use cases:

### Best Overall: DeepSeek-V3
```bash
# Best for: Complex reasoning, error analysis, multi-step debugging
Model: hf:deepseek-ai/DeepSeek-V3
Strengths: Superior reasoning capabilities, excellent at understanding complex errors
```

### Best for Structured Output: Qwen3-235B
```bash
# Best for: Generating clean, well-formatted schemas
Model: hf:Qwen/Qwen3-235B-A22B-Instruct
Strengths: Excellent at producing structured JSON/YAML output
```

### Best for Advanced Reasoning: DeepSeek-R1
```bash
# Best for: Complex transformations, chain-of-thought problem solving
Model: hf:deepseek-ai/DeepSeek-R1-0528
Strengths: Advanced reasoning with explicit thought process
```

### Best for Speed: Llama 4 Maverick
```bash
# Best for: Quick fixes, general assistance
Model: hf:meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8
Strengths: Good balance of speed and quality, smaller model size
```

### Best for Lightweight: GLM-4.7
```bash
# Best for: Simple validation, quick fixes
Model: hf:zai-org/GLM-4.7
Strengths: Fast, lightweight, low resource requirements
```

## Installation

```bash
# No additional dependencies needed beyond requests and pyyaml
pip install requests pyyaml
```

## Usage

### 1. Fix and Upload a Schema File

```bash
python vectadb_schema_agent.py \
  --model deepseek-v3 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json \
  --format json
```

This will:
1. Load your schema file
2. Attempt to upload it to VectaDB
3. If it fails, analyze the error using the LLM
4. Generate a corrected schema
5. Attempt to upload the corrected version
6. Save the corrected schema to a `_corrected` file

### 2. Interactive Mode

```bash
python vectadb_schema_agent.py \
  --model qwen3-235b \
  --api-base http://localhost:8000 \
  --interactive
```

Interactive mode provides:
- Schema error analysis
- Schema generation from sample data
- Schema file fixing and upload
- Best practices and tips

### 3. Generate Schema from Sample Data

```python
from vectadb_schema_agent import SchemaAgent, LLMConfig

# Configure LLM
config = LLMConfig(
    name="DeepSeek-V3",
    model="hf:deepseek-ai/DeepSeek-V3",
    api_base="http://localhost:8000"
)

agent = SchemaAgent(config)

# Generate schema from sample data
sample_data = [
    {
        "timestamp": "2025-01-09T12:00:00Z",
        "request_id": "req-123",
        "model": "claude-3",
        "user_message": "Hello"
    }
]

schema = agent.generate_schema_from_sample(
    sample_data,
    namespace="my.application",
    version="1.0.0"
)

print(json.dumps(schema, indent=2))
```

### 4. Programmatic Error Analysis

```python
from vectadb_schema_agent import SchemaAgent

agent = SchemaAgent.create_with_model(
    "deepseek-v3",
    api_base="http://localhost:8000"
)

# Analyze a schema error
error_message = "invalid type: sequence, expected a map at line 1 column 72"
attempted_schema = """{ "entity_types": [...] }"""

analysis = agent.analyze_schema_error(error_message, attempted_schema)

print(f"Error Type: {analysis['error_type']}")
print(f"Root Cause: {analysis['root_cause']}")
print(f"Fix Strategy: {analysis['fix_strategy']}")
```

## Model Selection Guide

### For Your Use Case: Bedrock Log Schema

**Recommended: DeepSeek-V3** or **Qwen3-235B**

```bash
# Option 1: DeepSeek-V3 (best reasoning)
python vectadb_schema_agent.py \
  --model deepseek-v3 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json

# Option 2: Qwen3-235B (best structured output)
python vectadb_schema_agent.py \
  --model qwen3-235b \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json
```

### Quick Comparison

| Model | Speed | Reasoning | Structured Output | Resource Usage |
|-------|-------|-----------|-------------------|----------------|
| DeepSeek-V3 | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | High |
| DeepSeek-R1 | ⚡⚡ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | High |
| Qwen3-235B | ⚡⚡⚡ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Very High |
| Llama4-Maverick | ⚡⚡⚡⚡ | ⭐⭐⭐ | ⭐⭐⭐ | Medium |
| GLM-4.7 | ⚡⚡⚡⚡⚡ | ⭐⭐ | ⭐⭐⭐ | Low |

## Common Issues and Solutions

### Issue 1: "invalid type: sequence, expected a map"

**Cause:** Properties defined as array instead of object

**Solution:** The agent will convert:
```json
// Wrong
"properties": [
  {"name": "prop1", ...}
]

// Correct
"properties": {
  "prop1": {...}
}
```

### Issue 2: "missing field `entity_type`"

**Cause:** Wrong API parameter name

**Solution:** The agent will remind you:
- API expects `entity_type` not `type`
- Use the corrected payload format

### Issue 3: Schema format incompatibility

**Cause:** JSON structure doesn't match Rust serde expectations

**Solution:** The agent analyzes the Rust error message and generates the correct structure

## Advanced Usage

### Custom Model Configuration

```python
from vectadb_schema_agent import SchemaAgent, LLMConfig

# Use a custom model
config = LLMConfig(
    name="My Custom Model",
    model="custom/model-name",
    api_base="http://my-server:8000",
    api_key="sk-xxxxx",  # If required
    max_tokens=8000,
    temperature=0.0  # Deterministic output
)

agent = SchemaAgent(config, vectadb_url="http://localhost:8080")
```

### Batch Processing

```python
import glob

agent = SchemaAgent.create_with_model("deepseek-v3", "http://localhost:8000")

# Fix all schema files
for schema_file in glob.glob("schemas/*.json"):
    print(f"Processing {schema_file}...")
    success = agent.fix_and_upload_schema(schema_file, "json")
    if success:
        print(f"✅ {schema_file} uploaded successfully")
    else:
        print(f"❌ {schema_file} needs manual review")
```

## Integration with Bedrock Ingestion

```bash
# Step 1: Fix the schema
python vectadb_schema_agent.py \
  --model deepseek-v3 \
  --api-base http://localhost:8000 \
  --schema-file bedrock_schema.json

# Step 2: Run the ingestion
python ingest_bedrock_graph.py
```

## Troubleshooting

### LLM Server Not Responding

```bash
# Test the LLM API
curl http://localhost:8000/v1/models

# If using vLLM, start it with:
vllm serve hf:deepseek-ai/DeepSeek-V3 \
  --host 0.0.0.0 \
  --port 8000
```

### VectaDB Not Accessible

```bash
# Check VectaDB health
curl http://localhost:8080/health

# Start VectaDB if needed
cd vectadb && cargo run --release
```

### Agent Not Finding Errors

The agent is most effective when:
- Error messages are complete (not truncated)
- The attempted schema is provided in full
- Using a model with strong reasoning (DeepSeek-V3 or R1)

## Contributing

To add support for a new model:

```python
# In vectadb_schema_agent.py
RECOMMENDED_MODELS = {
    "my-model": {
        "name": "My Model Name",
        "model": "hf:org/model-name",
        "strengths": "What it's good at",
        "use_case": "When to use it"
    }
}
```

## License

Same as VectaDB project

## Support

For issues or questions:
1. Check the error analysis output
2. Try interactive mode for step-by-step guidance
3. Review VectaDB documentation
4. File an issue on GitHub
