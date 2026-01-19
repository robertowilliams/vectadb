# Graph Database Test

Comprehensive test suite for VectaDB's graph database functionality powered by SurrealDB. This test validates entity creation, relation management, and graph traversal capabilities.

## Purpose

VectaDB uses **SurrealDB as a graph database** to store entities and their relationships. This test suite validates that the graph functionality works correctly by testing:

1. **Entity Management**: Create, retrieve, and delete entities
2. **Relation Management**: Create relations between entities with properties
3. **Graph Structures**: Build complex graph topologies
4. **Relationship Types**: Multiple relation types between same entities
5. **Bidirectional Relations**: Two-way relationships
6. **Graph Depth**: Multi-level relationship chains

## Graph Model

VectaDB's graph model consists of:

```
┌─────────────┐
│   Entity    │  (Node in the graph)
├─────────────┤
│ id          │  Unique identifier
│ entity_type │  Type (Agent, Task, Log, etc.)
│ properties  │  Flexible key-value data
│ embedding   │  Optional vector embedding
│ created_at  │  Timestamp
│ updated_at  │  Timestamp
│ metadata    │  Additional metadata
└─────────────┘

┌─────────────┐
│  Relation   │  (Edge in the graph)
├─────────────┤
│ id          │  Unique identifier
│ relation_type│ Type of relationship
│ source_id   │  Source entity ID
│ target_id   │  Target entity ID
│ properties  │  Flexible key-value data
│ created_at  │  Timestamp
└─────────────┘
```

## Test Scenarios

### Test 1: Simple Entity-Relation-Entity

Creates a basic graph with two entities connected by a relation:

```
┌────────┐  executes  ┌────────┐
│ Agent  │ ────────→  │  Task  │
└────────┘            └────────┘
```

**Validates:**
- Entity creation with properties
- Relation creation between entities
- Relation retrieval and verification
- Property storage on relations

### Test 2: Complex Graph Structure

Builds a multi-entity graph with hierarchical relationships:

```
┌────────┐  performs  ┌────────┐
│ Agent  │ ────────→  │  Task  │
└────────┘            └────┬───┘
                           │ generates
                           ├──────────→ ┌──────┐
                           │            │ Log1 │
                           │            └──────┘
                           ├──────────→ ┌──────┐
                           │            │ Log2 │
                           │            └──────┘
                           └──────────→ ┌──────┐
                                        │ Log3 │
                                        └──────┘
```

**Validates:**
- One-to-many relationships
- Graph fan-out patterns
- Multiple relations from single entity

### Test 3: Bidirectional Relations

Tests symmetric relationships between entities:

```
┌─────────────┐  collaborates_with  ┌─────────────┐
│ Agent Alpha │ ←─────────────────→ │  Agent Beta │
└─────────────┘                     └─────────────┘
```

**Validates:**
- Bidirectional edges
- Symmetric relationship patterns
- Peer-to-peer connections

### Test 4: Multiple Relation Types

Creates different types of relations between the same entities:

```
                      owns
            ┌─────────────────────┐
            │      monitors       │
┌────────┐  │  ┌─────────────┐   │  ┌────────┐
│ Agent  │ ─┼─→│  schedules  │ ──┼→ │  Task  │
└────────┘  │  └─────────────┘   │  └────────┘
            └─────────────────────┘
```

**Validates:**
- Multiple edge types between same nodes
- Relationship differentiation
- Complex relationship semantics

### Test 5: Relations with Rich Properties

Tests storing detailed metadata on relations:

```
┌────────┐  executes (with properties)  ┌────────┐
│ Agent  │ ──────────────────────────→  │  Task  │
└────────┘                               └────────┘
            Properties:
            - started_at: timestamp
            - completed_at: timestamp
            - duration_ms: number
            - status: string
            - retries: number
            - metadata: object
```

**Validates:**
- Property storage on edges
- Complex data types
- Temporal information
- Nested objects in properties

### Test 6: Multi-Level Graph Depth

Creates a deep chain of relationships:

```
┌────────┐  executes  ┌────────┐  contains  ┌─────────┐  produces  ┌──────┐
│ Agent  │ ────────→  │  Task  │ ────────→  │ SubTask │ ────────→  │ Log  │
└────────┘            └────────┘            └─────────┘            └──────┘
  Level 0              Level 1               Level 2               Level 3
```

**Validates:**
- Graph traversal depth
- Transitive relationships
- Path construction
- Chain integrity

## Running the Test

### Quick Start

```bash
./test_graph.sh
```

### Manual Execution

```bash
cargo run --release --bin graph_database_test
```

### Custom VectaDB URL

```bash
VECTADB_URL=http://custom-host:3000 ./test_graph.sh
```

## Expected Output

```
╔════════════════════════════════════════╗
║   GRAPH DATABASE TEST SUITE           ║
║   SurrealDB Graph Functionality       ║
╚════════════════════════════════════════╝

Configuration:
  VectaDB API: http://localhost:3000

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RUNNING GRAPH TESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 TEST 1: Simple Entity-Relation-Entity
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Creating Agent entity...
      ✅ Created Agent: ent_abc123
   Creating Task entity...
      ✅ Created Task: ent_def456
   Creating 'executes' relation...
      ✅ Created Relation: rel_ghi789
   Verifying relation...
      ✅ Relation verified
   ✅ Test 1 PASSED

📊 TEST 2: Complex Graph Structure
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Building: Agent → Task → Log chain
      ✅ Agent created
      ✅ Task created
      ✅ 3 Logs created
      ✅ Agent → Task relation
      ✅ Task → Logs relations (3)
   ✅ Test 2 PASSED

📊 TEST 3: Bidirectional Relations
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Building: Agent ↔ Agent collaboration
      ✅ Two agents created
      ✅ Bidirectional relations created
   ✅ Test 3 PASSED

📊 TEST 4: Multiple Relation Types
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Building: Complex relationships between entities
      ✅ Entities created
      ✅ Relation 'owns' created
      ✅ Relation 'monitors' created
      ✅ Relation 'schedules' created
   ✅ Test 4 PASSED

📊 TEST 5: Relations with Rich Properties
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Creating relation with rich properties...
   Verifying relation properties...
      ✅ Properties stored: {...}
   ✅ Test 5 PASSED

📊 TEST 6: Multi-Level Graph Depth
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Building: Agent → Task → SubTask → Log (3 levels)
      ✅ 3-level graph chain created
   ✅ Test 6 PASSED

🧹 CLEANUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Deleting 10 relations...
      ✅ Relations deleted
   Deleting 12 entities...
      ✅ Entities deleted

╔════════════════════════════════════════╗
║     GRAPH DATABASE TEST SUMMARY       ║
╚════════════════════════════════════════╝

  Total Entities Created:  12
  Total Relations Created: 10

  Test Coverage:
    ✅ Simple entity-relation-entity
    ✅ Complex graph structures
    ✅ Bidirectional relations
    ✅ Multiple relation types
    ✅ Relations with properties
    ✅ Multi-level graph depth

  Graph Capabilities Validated:
    ✅ Entity creation and retrieval
    ✅ Relation creation and retrieval
    ✅ Property storage on relations
    ✅ Multiple relations between entities
    ✅ Graph chain construction
    ✅ Entity/relation cleanup

  ✅ ALL TESTS PASSED
```

## What This Test Validates

### Core Graph Operations

1. **Entity CRUD**
   - Create entities with typed properties
   - Retrieve entities by ID
   - Delete entities

2. **Relation CRUD**
   - Create relations between entities
   - Store properties on relations
   - Retrieve relations by ID
   - Delete relations

3. **Graph Patterns**
   - One-to-one relationships
   - One-to-many relationships
   - Many-to-many relationships
   - Hierarchical structures
   - Network topologies

4. **Data Integrity**
   - Referential integrity (source/target IDs)
   - Property preservation
   - Type safety
   - Cleanup and cascade operations

## API Endpoints Tested

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/entities` | POST | Create entity |
| `/api/v1/entities/:id` | GET | Retrieve entity |
| `/api/v1/entities/:id` | DELETE | Delete entity |
| `/api/v1/relations` | POST | Create relation |
| `/api/v1/relations/:id` | GET | Retrieve relation |
| `/api/v1/relations/:id` | DELETE | Delete relation |

## Graph Query Capabilities (SurrealDB)

VectaDB's SurrealDB integration supports:

### Outgoing Relations
Query all relations from an entity:
```
SELECT * FROM relation WHERE source_id = $entity_id
```

### Incoming Relations
Query all relations to an entity:
```
SELECT * FROM relation WHERE target_id = $entity_id
```

### Graph Traversal
Navigate relationships by type and depth:
```rust
traverse_graph(start_id, relation_type, depth)
```

### Relation Type Filtering
Query specific relationship types:
```
SELECT * FROM relation WHERE relation_type = $type
```

## Use Cases

### 1. Agent Workflow Tracking
```
Agent → executes → Task → generates → Logs
```
Track which agents execute which tasks and what logs they produce.

### 2. Task Dependencies
```
Task A → depends_on → Task B → depends_on → Task C
```
Model task dependencies and execution order.

### 3. Error Causality
```
Error1 → triggers → Error2 → causes → Error3
```
Trace error chains and root cause analysis.

### 4. Agent Collaboration
```
Agent1 ↔ collaborates_with ↔ Agent2
      ↘ shares_context_with ↗
```
Model multi-agent interactions and information sharing.

### 5. Hierarchical Organizations
```
Team → contains → Agent → executes → Task
```
Organize agents into teams with task assignments.

## Integration with Vector Database

The graph database (SurrealDB) works alongside the vector database (Qdrant):

- **SurrealDB**: Stores entities, relations, and structured properties
- **Qdrant**: Stores vector embeddings for semantic search
- **VectaDB**: Coordinates both for hybrid graph + vector queries

Example workflow:
1. Create entity in SurrealDB
2. Generate embedding from entity properties
3. Store embedding in Qdrant
4. Create relations in SurrealDB
5. Query: Semantic search (Qdrant) + Graph traversal (SurrealDB)

## Troubleshooting

### VectaDB Not Running

**Error**: Connection refused

**Solution**: Start VectaDB
```bash
cd vectadb
cargo run --release
```

### Test Failures

**Common Issues:**

1. **Entities not created**: Check SurrealDB connection
2. **Relations fail**: Verify entity IDs exist
3. **Cleanup errors**: Manual cleanup may be needed

**Manual Cleanup:**
```bash
# Connect to SurrealDB
curl -X POST http://localhost:8000/sql \
  -H "Authorization: Basic $(echo -n 'root:root' | base64)" \
  -H "NS: vectadb" \
  -H "DB: main" \
  -d '{"query": "DELETE entity; DELETE relation;"}'
```

### Relation Properties Not Stored

**Issue**: Properties appear empty

**Check**: Verify JSON structure in request body
```json
{
  "relation_type": "executes",
  "source_id": "entity_123",
  "target_id": "entity_456",
  "properties": {
    "key": "value"
  }
}
```

## Performance Considerations

### Entity Creation
- Typical: 50-100ms per entity
- Includes: ID generation, property validation, storage

### Relation Creation
- Typical: 50-100ms per relation
- Includes: Validation, referential checks, storage

### Graph Traversal
- Depth 1: ~100ms
- Depth 2: ~200ms
- Depth 3+: Increases with fan-out

### Batch Operations
For bulk operations, consider:
- Batch entity creation
- Batch relation creation
- Transaction support (SurrealDB)

## Advanced Graph Features

### Available (Not Tested Yet)

1. **Graph Traversal API**
   - `get_outgoing_relations(entity_id, relation_type?)`
   - `get_incoming_relations(entity_id, relation_type?)`
   - `traverse_graph(start_id, relation_type, depth)`

2. **SurrealDB Native Queries**
   - Direct SurrealQL queries
   - Complex graph patterns
   - Aggregate operations

3. **Ontology Integration**
   - Relation type validation
   - Entity type hierarchies
   - Compatible relation queries

### Future Enhancements

- [ ] Graph traversal test (multi-hop queries)
- [ ] Shortest path algorithms
- [ ] Cycle detection
- [ ] Subgraph extraction
- [ ] Bulk operations test
- [ ] Transaction rollback test
- [ ] Performance benchmarks

## Related Tests

- [bedrock_test.rs](bedrock_test.rs) - Data ingestion test
- [database_verification.rs](database_verification.rs) - Database validation
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [README.md](README.md) - Main documentation

## Exit Codes

- `0` - All tests passed
- `1` - One or more tests failed

## Contributing

To add new graph test scenarios:

1. Add test method to `GraphTester` struct
2. Call from `main()` function
3. Update this documentation
4. Document expected graph structure

## License

Apache 2.0 - Same as VectaDB
