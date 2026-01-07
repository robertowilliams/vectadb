# VectaDB API Examples

Complete guide with curl examples for testing the VectaDB REST API.

## Prerequisites

1. Start VectaDB server:
```bash
cd vectadb
cargo run --release
```

2. Server should be running on `http://localhost:8080`

---

## 1. Health Check

Check if the server is running and see ontology status.

```bash
curl http://localhost:8080/health | jq
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "ontology_loaded": false,
  "ontology_namespace": null,
  "ontology_version": null
}
```

---

## 2. Upload Ontology Schema

Upload the example agent ontology.

```bash
curl -X POST http://localhost:8080/api/v1/ontology/schema \
  -H "Content-Type: application/json" \
  -d @- <<'EOF' | jq
{
  "schema": "namespace: \"http://vectadb.com/ontology/agents/v1\"\nversion: \"1.0.0\"\nentity_types:\n  Agent:\n    id: \"Agent\"\n    label: \"Agent\"\n    parent: null\n    properties:\n      - name: \"id\"\n        property_type:\n          type: \"String\"\n        required: true\n        cardinality: \"One\"\n      - name: \"name\"\n        property_type:\n          type: \"String\"\n        required: true\n        cardinality: \"One\"\n    constraints: []\n    metadata: null\n  LLMAgent:\n    id: \"LLMAgent\"\n    label: \"LLM-Powered Agent\"\n    parent: \"Agent\"\n    properties:\n      - name: \"model_name\"\n        property_type:\n          type: \"String\"\n        required: true\n        cardinality: \"One\"\n    constraints: []\n    metadata: null\n  Task:\n    id: \"Task\"\n    label: \"Task\"\n    parent: null\n    properties:\n      - name: \"id\"\n        property_type:\n          type: \"String\"\n        required: true\n        cardinality: \"One\"\n    constraints: []\n    metadata: null\nrelation_types:\n  executes:\n    id: \"executes\"\n    label: \"executes\"\n    domain: \"Agent\"\n    range: \"Task\"\n    inverse: null\n    transitive: false\n    symmetric: false\n    functional: false\n    reflexive: false\n    metadata: null\nrules: []\n",
  "format": "yaml"
}
EOF
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Ontology schema uploaded successfully",
  "namespace": "http://vectadb.com/ontology/agents/v1",
  "version": "1.0.0"
}
```

### Alternative: Upload from file

```bash
# Convert YAML to JSON string and upload
SCHEMA_YAML=$(cat vectadb/ontologies/agent_ontology.yaml)
curl -X POST http://localhost:8080/api/v1/ontology/schema \
  -H "Content-Type: application/json" \
  -d "{\"schema\":$(jq -Rs . <<<\"$SCHEMA_YAML\"),\"format\":\"yaml\"}" | jq
```

---

## 3. Get Ontology Schema

Retrieve the currently loaded schema.

```bash
curl http://localhost:8080/api/v1/ontology/schema | jq
```

**Expected Response:**
```json
{
  "namespace": "http://vectadb.com/ontology/agents/v1",
  "version": "1.0.0",
  "entity_types": {
    "Agent": {...},
    "LLMAgent": {...},
    "Task": {...}
  },
  "relation_types": {...},
  "rules": []
}
```

---

## 4. Get Entity Type Details

Get details about a specific entity type.

```bash
curl http://localhost:8080/api/v1/ontology/types/LLMAgent | jq
```

**Expected Response:**
```json
{
  "id": "LLMAgent",
  "label": "LLM-Powered Agent",
  "parent": "Agent",
  "properties": [
    {
      "name": "model_name",
      "property_type": "String",
      "required": true,
      "cardinality": "One",
      "description": null
    },
    {
      "name": "id",
      "property_type": "String",
      "required": true,
      "cardinality": "One",
      "description": null
    },
    {
      "name": "name",
      "property_type": "String",
      "required": true,
      "cardinality": "One",
      "description": null
    }
  ],
  "constraints": []
}
```

---

## 5. Get Type Hierarchy (Subtypes)

Get all subtypes of an entity type.

```bash
curl http://localhost:8080/api/v1/ontology/types/Agent/subtypes | jq
```

**Expected Response:**
```json
{
  "type_id": "Agent",
  "subtypes": [
    "Agent",
    "LLMAgent"
  ]
}
```

---

## 6. Validate Entity (Valid)

Validate an entity that meets all requirements.

```bash
curl -X POST http://localhost:8080/api/v1/validate/entity \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "LLMAgent",
    "properties": {
      "id": "agent-001",
      "name": "CodeBot",
      "model_name": "gpt-4"
    }
  }' | jq
```

**Expected Response:**
```json
{
  "valid": true,
  "errors": []
}
```

---

## 7. Validate Entity (Invalid)

Validate an entity that's missing required properties.

```bash
curl -X POST http://localhost:8080/api/v1/validate/entity \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "LLMAgent",
    "properties": {
      "id": "agent-001"
    }
  }' | jq
```

**Expected Response:**
```json
{
  "valid": false,
  "errors": [
    {
      "error_type": "MissingRequiredProperty",
      "message": "Missing required property 'name' for entity type 'LLMAgent'"
    },
    {
      "error_type": "MissingRequiredProperty",
      "message": "Missing required property 'model_name' for entity type 'LLMAgent'"
    }
  ]
}
```

---

## 8. Validate Relation (Valid)

Check if a relation is valid between two entity types.

```bash
curl -X POST http://localhost:8080/api/v1/validate/relation \
  -H "Content-Type: application/json" \
  -d '{
    "relation_type": "executes",
    "source_type": "LLMAgent",
    "target_type": "Task"
  }' | jq
```

**Expected Response:**
```json
{
  "valid": true,
  "error": null
}
```

---

## 9. Validate Relation (Invalid)

Check an invalid relation (wrong direction).

```bash
curl -X POST http://localhost:8080/api/v1/validate/relation \
  -H "Content-Type": "application/json" \
  -d '{
    "relation_type": "executes",
    "source_type": "Task",
    "target_type": "Agent"
  }' | jq
```

**Expected Response:**
```json
{
  "valid": false,
  "error": "Invalid relation 'executes' from 'Task' to 'Agent': Expected domain 'Agent' and range 'Task', got source 'Task' and target 'Agent'"
}
```

---

## 10. Expand Query (with Relations)

Expand a query to include all subtypes and inferred relations.

```bash
curl -X POST http://localhost:8080/api/v1/query/expand \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "Agent",
    "include_inferred_relations": true
  }' | jq
```

**Expected Response:**
```json
{
  "original_type": "Agent",
  "expanded_types": [
    "Agent",
    "LLMAgent"
  ],
  "inferred_relations": [
    {
      "relation_type": "executes",
      "source_type": "Agent",
      "target_type": "Task",
      "reason": "SubtypeInheritance"
    }
  ],
  "metadata": {
    "expansion_count": "2",
    "inference_count": "1"
  }
}
```

---

## 11. Expand Query (without Relations)

Expand query without relation inference.

```bash
curl -X POST http://localhost:8080/api/v1/query/expand \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "Agent",
    "include_inferred_relations": false
  }' | jq
```

**Expected Response:**
```json
{
  "original_type": "Agent",
  "expanded_types": [
    "Agent",
    "LLMAgent"
  ],
  "inferred_relations": [],
  "metadata": {
    "expansion_count": "2",
    "inference_count": "0"
  }
}
```

---

## 12. Get Compatible Relations

Find all relations that can connect two entity types.

```bash
curl -X POST http://localhost:8080/api/v1/query/compatible_relations \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "LLMAgent",
    "target_type": "Task"
  }' | jq
```

**Expected Response:**
```json
{
  "source_type": "LLMAgent",
  "target_type": "Task",
  "compatible_relations": [
    "executes"
  ]
}
```

---

## Error Handling Examples

### Schema Not Loaded

```bash
# Try to get schema before uploading
curl http://localhost:8080/api/v1/ontology/schema | jq
```

**Response:**
```json
{
  "error": "NoSchema",
  "message": "No ontology schema loaded"
}
```

### Invalid Schema Format

```bash
curl -X POST http://localhost:8080/api/v1/ontology/schema \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "invalid yaml {{{",
    "format": "yaml"
  }' | jq
```

**Response:**
```json
{
  "error": "InvalidSchema",
  "message": "Failed to parse ontology YAML: ..."
}
```

### Type Not Found

```bash
curl http://localhost:8080/api/v1/ontology/types/NonExistentType | jq
```

**Response:**
```json
{
  "error": "TypeNotFound",
  "message": "Entity type 'NonExistentType' not found"
}
```

---

## Complete Workflow Script

Here's a complete test script that runs all operations in sequence:

```bash
#!/bin/bash

# API_TEST.sh - Complete VectaDB API test workflow

set -e  # Exit on error

BASE_URL="http://localhost:8080"

echo "=== VectaDB API Test Workflow ==="
echo

# 1. Health Check
echo "1. Checking health..."
curl -s $BASE_URL/health | jq '.status'
echo

# 2. Upload Schema
echo "2. Uploading ontology schema..."
UPLOAD_RESULT=$(curl -s -X POST $BASE_URL/api/v1/ontology/schema \
  -H "Content-Type: application/json" \
  -d '{
    "schema": "namespace: \"test://api\"\nversion: \"1.0\"\nentity_types:\n  Agent:\n    id: \"Agent\"\n    label: \"Agent\"\n    parent: null\n    properties:\n      - name: \"id\"\n        property_type:\n          type: \"String\"\n        required: true\n        cardinality: \"One\"\n      - name: \"name\"\n        property_type:\n          type: \"String\"\n        required: true\n        cardinality: \"One\"\n    constraints: []\n    metadata: null\n  LLMAgent:\n    id: \"LLMAgent\"\n    label: \"LLM Agent\"\n    parent: \"Agent\"\n    properties:\n      - name: \"model\"\n        property_type:\n          type: \"String\"\n        required: true\n        cardinality: \"One\"\n    constraints: []\n    metadata: null\nrelation_types: {}\nrules: []\n",
    "format": "yaml"
  }')
echo $UPLOAD_RESULT | jq '.success'
echo

# 3. Get Type Details
echo "3. Getting LLMAgent type details..."
curl -s $BASE_URL/api/v1/ontology/types/LLMAgent | jq '.label'
echo

# 4. Validate Entity
echo "4. Validating valid entity..."
curl -s -X POST $BASE_URL/api/v1/validate/entity \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "LLMAgent",
    "properties": {
      "id": "test-001",
      "name": "TestBot",
      "model": "gpt-4"
    }
  }' | jq '.valid'
echo

# 5. Expand Query
echo "5. Expanding query for Agent type..."
curl -s -X POST $BASE_URL/api/v1/query/expand \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "Agent",
    "include_inferred_relations": false
  }' | jq '.expanded_types'
echo

echo "=== All tests passed! ==="
```

Save this as `test_api.sh`, make it executable (`chmod +x test_api.sh`), and run it!

---

## Notes

- All examples use `jq` for JSON formatting. Install with: `brew install jq` (macOS) or `apt install jq` (Linux)
- Make sure VectaDB is running before testing
- The API returns proper HTTP status codes (200, 400, 404, etc.)
- All timestamps should be in ISO 8601 format
- CORS is enabled for all origins (development mode)

---

**For more examples, see:**
- `/tests/api_tests.rs` - Integration test suite
- `/vectadb/ontologies/agent_ontology.yaml` - Complete example ontology
