# VectaDB Schema Agent - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     VectaDB + Graph UI System                    │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   Bedrock    │         │  Schema      │         │   VectaDB    │
│   Logs       │────────▶│  Agent       │────────▶│   Backend    │
│   (JSON)     │         │  (AI)        │         │   (Rust)     │
└──────────────┘         └──────────────┘         └──────────────┘
                                │                         │
                                │                         │
                                ▼                         ▼
                         ┌──────────────┐         ┌──────────────┐
                         │     LLM      │         │   Graph DB   │
                         │   Server     │         │   (SQLite)   │
                         │  (vLLM)      │         └──────────────┘
                         └──────────────┘                │
                                                          │
                                                          ▼
                                                   ┌──────────────┐
                                                   │   Vue UI     │
                                                   │   (D3.js)    │
                                                   └──────────────┘
```

## Data Flow

### Phase 1: Schema Fixing

```
┌─────────────────────────────────────────────────────────────────┐
│                      Schema Fixing Flow                          │
└─────────────────────────────────────────────────────────────────┘

1. Load Schema
   ├─ bedrock_schema.json
   └─ Parse JSON/YAML

2. Attempt Upload
   ├─ POST /api/v1/ontology/schema
   └─ VectaDB validates

3. Error Occurs
   ├─ "invalid type: sequence, expected a map"
   └─ Rust serde error

4. LLM Analysis
   ├─ Send error + schema to LLM
   ├─ LLM understands Rust/serde
   └─ Generates corrected schema

5. Apply Fix
   ├─ Convert arrays to objects
   ├─ Fix property structure
   └─ Retry upload

6. Success
   ├─ Schema uploaded
   └─ ontology_loaded = true
```

### Phase 2: Data Ingestion

```
┌─────────────────────────────────────────────────────────────────┐
│                    Data Ingestion Flow                           │
└─────────────────────────────────────────────────────────────────┘

1. Load Logs
   ├─ bedrock_chain_of_thought_logs.json
   └─ 29 log entries

2. Extract Entities
   ├─ BedrockRequest (29)
   ├─ Agent (1)
   ├─ Patient (detected from text)
   └─ ToolUse (from tool calls)

3. Create Relations
   ├─ MADE_BY: Request → Agent
   ├─ REFERENCES_PATIENT: Request → Patient
   ├─ INVOKED_TOOL: Request → ToolUse
   └─ FOLLOWED_BY: Request → Request

4. Store in VectaDB
   ├─ POST /api/v1/entities
   ├─ POST /api/v1/relations
   └─ SQLite persistence

5. Query from UI
   ├─ GET /api/v1/entities
   ├─ GET /api/v1/relations
   └─ Convert to graph format
```

### Phase 3: Visualization

```
┌─────────────────────────────────────────────────────────────────┐
│                   Graph Visualization Flow                       │
└─────────────────────────────────────────────────────────────────┘

1. Load GraphView
   ├─ http://localhost:5173/graph
   └─ Vue component mounts

2. Fetch Data
   ├─ store.fetchEntities()
   ├─ store.fetchRelations()
   └─ Convert to GraphData

3. Render with D3.js
   ├─ Create force simulation
   ├─ Draw nodes (circles)
   ├─ Draw edges (lines with arrows)
   └─ Add interaction handlers

4. User Interaction
   ├─ Drag nodes
   ├─ Zoom/pan
   ├─ Click for details
   └─ Adjust physics
```

## Component Interaction

```
┌─────────────────────────────────────────────────────────────────┐
│                  Component Responsibilities                      │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  vectadb_schema_agent.py                                         │
│  ────────────────────────────────────────────────────────────── │
│  • Analyzes schema errors                                        │
│  • Calls LLM for fixes                                          │
│  • Manages upload retries                                        │
│  • Saves corrected schemas                                       │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  LLM Server (vLLM)                                               │
│  ────────────────────────────────────────────────────────────── │
│  • Receives error + schema                                       │
│  • Uses system prompt with VectaDB rules                         │
│  • Generates corrected structure                                 │
│  • Returns JSON with fix                                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  VectaDB Backend (Rust)                                          │
│  ────────────────────────────────────────────────────────────── │
│  • Validates schema with serde                                   │
│  • Stores ontology definition                                    │
│  • Validates entities against schema                             │
│  • Persists to SQLite                                            │
│  • Serves REST API                                               │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  ingest_bedrock_graph.py                                         │
│  ────────────────────────────────────────────────────────────── │
│  • Reads Bedrock logs                                            │
│  • Extracts entities                                             │
│  • Creates relations                                             │
│  • Calls VectaDB API                                             │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Vue UI + D3.js                                                  │
│  ────────────────────────────────────────────────────────────── │
│  • GraphView.vue - Page container                               │
│  • GraphVisualization.vue - D3.js component                      │
│  • vectadb.ts store - Data management                            │
│  • client.ts - API calls                                         │
└──────────────────────────────────────────────────────────────────┘
```

## Schema Fixing Example

```
┌─────────────────────────────────────────────────────────────────┐
│              How the Agent Fixes the Schema                      │
└─────────────────────────────────────────────────────────────────┘

❌ WRONG (What you wrote):
{
  "entity_types": [
    {
      "id": "BedrockRequest",
      "properties": [
        {"name": "request_id", "type": "string"}
      ]
    }
  ]
}

⚠️  ERROR from VectaDB:
"invalid type: sequence, expected a map at line 1 column 72"

🤖 LLM Analysis:
{
  "error_type": "serde_type_mismatch",
  "root_cause": "Properties must be HashMap<String, PropertyDefinition>",
  "fix_strategy": "Convert arrays to objects with names as keys"
}

✅ CORRECT (What the agent generates):
{
  "entity_types": {
    "BedrockRequest": {
      "description": "A Bedrock request",
      "parent_type": null,
      "properties": {
        "request_id": {
          "type": "string",
          "required": true,
          "indexed": true,
          "description": "Request ID"
        }
      }
    }
  }
}
```

## LLM Model Selection

```
┌─────────────────────────────────────────────────────────────────┐
│                   Model Decision Tree                            │
└─────────────────────────────────────────────────────────────────┘

                    What do you need?
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    Complex Error?    Speed Most       Generate
      Multiple            Important?     New Schema?
      Failures?              │               │
          │                  │               │
          ▼                  ▼               ▼
    ┌──────────┐      ┌──────────┐    ┌──────────┐
    │ DeepSeek │      │   GLM    │    │  Qwen3   │
    │   V3/R1  │      │   4.7    │    │  235B    │
    └──────────┘      └──────────┘    └──────────┘
         │                  │               │
         │                  │               │
    Best          Fastest         Best
    Reasoning     Response        Formatting
```

## API Endpoints Used

```
┌─────────────────────────────────────────────────────────────────┐
│                      VectaDB REST API                            │
└─────────────────────────────────────────────────────────────────┘

Schema Management:
  POST   /api/v1/ontology/schema
    └─ Upload schema (JSON or YAML)

  GET    /api/v1/ontology/schema
    └─ Retrieve current schema

Entity Management:
  POST   /api/v1/entities
    └─ Create entity (requires type + properties)

  GET    /api/v1/entities
    └─ List all entities

  GET    /api/v1/entities/{id}
    └─ Get specific entity

Relation Management:
  POST   /api/v1/relations
    └─ Create relation (requires type + from/to entities)

  GET    /api/v1/relations
    └─ List all relations

Health:
  GET    /health
    └─ System status + schema info
```

## File Structure

```
vectadb3/
├── vectadb/                          # Rust backend
│   ├── src/
│   │   ├── ontology/                 # Schema validation
│   │   ├── api/                      # REST endpoints
│   │   └── storage/                  # SQLite
│   └── Cargo.toml
│
├── vectadb-ui/                       # Vue frontend
│   ├── src/
│   │   ├── views/
│   │   │   └── GraphView.vue        # Main graph page
│   │   ├── components/
│   │   │   └── GraphVisualization.vue # D3.js component
│   │   ├── stores/
│   │   │   └── vectadb.ts           # State management
│   │   └── api/
│   │       └── client.ts            # API calls
│   └── package.json
│
├── test/
│   └── bedrock_chain_of_thought_logs.json  # Sample data
│
├── vectadb_schema_agent.py          # AI agent
├── ingest_bedrock_graph.py          # Data ingestion
├── bedrock_schema.json               # Schema definition
│
└── Documentation:
    ├── SCHEMA_AGENT_README.md
    ├── MODEL_SELECTION_GUIDE.md
    ├── QUICKSTART_AGENT.md
    └── AGENT_SUMMARY.md
```

## Execution Flow Timeline

```
Time    Component              Action
━━━━    ━━━━━━━━━━━━━━━━━━    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
T+0s    User                   Runs schema agent
T+1s    Agent                  Loads bedrock_schema.json
T+2s    Agent                  POST /api/v1/ontology/schema
T+3s    VectaDB                Validates with serde → Error!
T+4s    Agent                  Sends error to LLM
T+5-15s LLM                    Analyzes error, generates fix
T+16s   Agent                  Receives corrected schema
T+17s   Agent                  POST /api/v1/ontology/schema (retry)
T+18s   VectaDB                Validates → Success!
T+19s   Agent                  Saves corrected file
T+20s   Agent                  Reports success
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
T+21s   User                   Runs ingest_bedrock_graph.py
T+22s   Ingestion              Loads 29 log entries
T+23s   Ingestion              Creates BedrockRequest #1
T+24s   Ingestion              Creates Agent entity
T+25s   Ingestion              Creates MADE_BY relation
...     ...                    ... (processes all 29 logs)
T+120s  Ingestion              Completes successfully
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
T+121s  User                   Opens http://localhost:5173/graph
T+122s  Vue UI                 Mounts GraphView component
T+123s  UI                     GET /api/v1/entities
T+124s  UI                     GET /api/v1/relations
T+125s  UI                     Converts to GraphData format
T+126s  D3.js                  Creates force simulation
T+127s  D3.js                  Renders graph with 29+ nodes
T+128s  Browser                Displays interactive graph
```

## Success Criteria

```
┌─────────────────────────────────────────────────────────────────┐
│                  How to Verify Success                           │
└─────────────────────────────────────────────────────────────────┘

✅ Phase 1: Schema Fixed
   $ curl http://localhost:8080/health | jq '.ontology_loaded'
   true

✅ Phase 2: Data Ingested
   $ curl http://localhost:8080/api/v1/entities | jq '.entities | length'
   50+

✅ Phase 3: Graph Visible
   • Open http://localhost:5173/graph
   • See colored nodes
   • Can drag, zoom, click
   • Details panel works
```

This architecture provides:
- 🎯 **Automated** schema fixing via AI
- 🔄 **Iterative** error correction
- 📊 **Visual** data exploration
- 🚀 **Fast** development workflow
