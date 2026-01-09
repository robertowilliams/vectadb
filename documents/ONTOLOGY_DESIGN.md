# VectaDB Ontology Support - Design Document

## Overview

This document outlines how to integrate ontology support into VectaDB while maintaining the current observability-focused architecture.

## Architecture Integration

### Current Architecture
```
VectaDB API (Axum)
    ↓
Intelligence Layer (Router, Optimizer, Cache)
    ↓
SurrealDB (Documents/Graphs) + Qdrant (Vectors)
```

### Enhanced Architecture with Ontology
```
VectaDB API (Axum)
    ↓
Intelligence Layer
    ├── Query Router
    ├── Query Optimizer
    ├── Cache Manager
    └── Ontology Reasoner ← NEW
        ↓
    ┌───────────────┬─────────────┬──────────────┐
    │               │             │              │
SurrealDB      Qdrant      Ontology Store    Schema Registry
(Data/Graph)  (Vectors)   (OWL/RDF)         (Types/Rules)
```

## Ontology Data Model

### 1. Entity Types (Ontology Classes)

```rust
// vectadb/src/ontology/entity_type.rs

/// Represents an ontology class/type
pub struct EntityType {
    pub id: String,           // e.g., "Agent", "Task", "LLMAgent"
    pub label: String,        // Human-readable name
    pub parent: Option<String>, // Inheritance: "LLMAgent" -> "Agent"
    pub properties: Vec<PropertyDefinition>,
    pub constraints: Vec<Constraint>,
    pub metadata: JsonValue,
}

/// Property definition in ontology
pub struct PropertyDefinition {
    pub name: String,
    pub property_type: PropertyType,
    pub required: bool,
    pub cardinality: Cardinality,
}

pub enum PropertyType {
    String,
    Number,
    Boolean,
    DateTime,
    Reference(String), // Reference to another entity type
    Embedding,
}

pub enum Cardinality {
    One,           // Exactly one
    ZeroOrOne,     // Optional
    Many,          // Zero or more
    OneOrMore,     // At least one
}

/// Constraints on entities
pub enum Constraint {
    ValueRange { min: f64, max: f64 },
    Pattern(String), // Regex pattern
    Custom(String),  // Custom validation rule
}
```

### 2. Relations (Object Properties)

```rust
// vectadb/src/ontology/relation_type.rs

/// Represents an ontology relation/object property
pub struct RelationType {
    pub id: String,              // e.g., "executes", "hasSubTask"
    pub label: String,
    pub domain: String,          // Source entity type
    pub range: String,           // Target entity type
    pub inverse: Option<String>, // Inverse relation
    pub transitive: bool,        // Transitive property
    pub symmetric: bool,         // Symmetric property
    pub functional: bool,        // Functional property (max 1 target)
}
```

### 3. Ontology Schema

```rust
// vectadb/src/ontology/schema.rs

/// Complete ontology schema
pub struct OntologySchema {
    pub namespace: String,
    pub version: String,
    pub entity_types: HashMap<String, EntityType>,
    pub relation_types: HashMap<String, RelationType>,
    pub rules: Vec<InferenceRule>,
}

/// Inference rules for reasoning
pub struct InferenceRule {
    pub id: String,
    pub rule_type: RuleType,
    pub conditions: Vec<Condition>,
    pub conclusion: Conclusion,
}

pub enum RuleType {
    SubClassOf,      // Inheritance
    Equivalent,      // Equivalence
    Disjoint,        // Mutual exclusion
    Custom(String),  // User-defined
}
```

## Implementation Phases

### Phase 1: Core Ontology Layer (Week 1-2)

**Files to Create:**
```
vectadb/src/ontology/
├── mod.rs
├── entity_type.rs      # Entity type definitions
├── relation_type.rs    # Relation type definitions
├── schema.rs           # Ontology schema management
├── validator.rs        # Entity/relation validation
└── store.rs           # Ontology persistence
```

**Key Features:**
- Define entity types with inheritance
- Define relation types with constraints
- Validate entities against schema
- Store ontology in SurrealDB

### Phase 2: Ontology-Aware Queries (Week 3-4)

**Enhance Intelligence Layer:**
```rust
// vectadb/src/intelligence/ontology_reasoner.rs

pub struct OntologyReasoner {
    schema: OntologySchema,
}

impl OntologyReasoner {
    /// Expand query based on ontology
    pub fn expand_query(&self, query: Query) -> ExpandedQuery {
        // Example: Query for "Agent" includes "LLMAgent", "HumanAgent"
        let expanded_types = self.get_subclasses(&query.entity_type);

        ExpandedQuery {
            original: query,
            expanded_types,
            inferred_relations: self.infer_relations(&query),
        }
    }

    /// Infer additional relations
    pub fn infer_relations(&self, query: &Query) -> Vec<InferredRelation> {
        // Example: If "executes" is transitive, follow chain
        // Example: If "hasParent" inverse is "hasChild", include both
        todo!()
    }

    /// Validate entity against ontology
    pub fn validate_entity(&self, entity: &Entity) -> Result<()> {
        let entity_type = self.schema.get_entity_type(&entity.type_id)?;

        // Check required properties
        // Validate property types
        // Check constraints
        // Validate relations

        Ok(())
    }
}
```

### Phase 3: Semantic Search Enhancement (Week 5-6)

**Ontology-Guided Vector Search:**
```rust
// vectadb/src/intelligence/semantic_search.rs

pub struct SemanticSearch {
    reasoner: OntologyReasoner,
    vector_store: QdrantClient,
}

impl SemanticSearch {
    /// Search with ontology expansion
    pub async fn search_with_ontology(
        &self,
        query: SearchQuery,
    ) -> Result<Vec<SearchResult>> {
        // 1. Expand query using ontology
        let expanded = self.reasoner.expand_query(query.clone());

        // 2. Search across all relevant entity types
        let mut results = Vec::new();
        for entity_type in expanded.expanded_types {
            let type_results = self.search_in_collection(
                &entity_type,
                &query.embedding
            ).await?;
            results.extend(type_results);
        }

        // 3. Apply ontology-based ranking
        self.rank_by_ontology(&mut results, &expanded);

        Ok(results)
    }

    /// Rank results using ontological distance
    fn rank_by_ontology(
        &self,
        results: &mut [SearchResult],
        expanded: &ExpandedQuery,
    ) {
        // Boost results that match original type exactly
        // Apply penalties for distant subtypes
        // Consider relation strength
    }
}
```

### Phase 4: Real-World Example - Agent Ontology (Week 7-8)

**Example Ontology for LLM Agents:**
```yaml
# agent_ontology.yaml

namespace: "http://vectadb.com/ontology/agents/v1"
version: "1.0.0"

entity_types:
  Agent:
    label: "Agent"
    properties:
      - name: id
        type: String
        required: true
      - name: name
        type: String
        required: true
      - name: created_at
        type: DateTime
        required: true
      - name: capabilities
        type: String
        cardinality: Many

  LLMAgent:
    label: "LLM-Powered Agent"
    parent: Agent
    properties:
      - name: model_name
        type: String
        required: true
      - name: temperature
        type: Number
        constraints:
          - ValueRange: { min: 0.0, max: 2.0 }
      - name: system_prompt
        type: String
        required: true

  HumanAgent:
    label: "Human Agent"
    parent: Agent
    properties:
      - name: email
        type: String
        required: true
        constraints:
          - Pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"

  Task:
    label: "Task"
    properties:
      - name: id
        type: String
        required: true
      - name: description
        type: String
        required: true
      - name: status
        type: String
        constraints:
          - Enum: [pending, in_progress, completed, failed]
      - name: description_embedding
        type: Embedding

relation_types:
  executes:
    label: "executes"
    domain: Agent
    range: Task
    inverse: executed_by

  has_subtask:
    label: "has subtask"
    domain: Task
    range: Task
    transitive: true
    inverse: subtask_of

  collaborates_with:
    label: "collaborates with"
    domain: Agent
    range: Agent
    symmetric: true

  depends_on:
    label: "depends on"
    domain: Task
    range: Task
    transitive: true

inference_rules:
  - id: agent_hierarchy
    type: SubClassOf
    description: "LLMAgent and HumanAgent are subtypes of Agent"

  - id: task_transitivity
    type: Custom
    description: "If A has_subtask B and B has_subtask C, then A has_subtask C"
```

## API Enhancements

### 1. Ontology Management Endpoints

```rust
// POST /api/v1/ontology/schema
// Upload or update ontology schema
{
  "namespace": "http://vectadb.com/ontology/agents/v1",
  "entity_types": [...],
  "relation_types": [...]
}

// GET /api/v1/ontology/schema
// Retrieve current ontology schema

// GET /api/v1/ontology/types/{type_id}
// Get details of specific entity type

// GET /api/v1/ontology/types/{type_id}/subtypes
// Get all subtypes of an entity type
```

### 2. Ontology-Aware Query Endpoints

```rust
// POST /api/v1/query/semantic
// Semantic query with ontology expansion
{
  "entity_type": "Agent",  // Will include LLMAgent, HumanAgent
  "query": "AI agent that writes code",
  "expand_subtypes": true,
  "infer_relations": true,
  "limit": 10
}

// POST /api/v1/validate
// Validate entity against ontology
{
  "entity": {
    "type": "LLMAgent",
    "properties": {
      "name": "CodeBot",
      "model_name": "gpt-4",
      "temperature": 0.7
    }
  }
}
```

### 3. Enhanced Agent/Task Creation with Validation

```rust
// POST /api/v1/agents
// Now validates against ontology
{
  "type": "LLMAgent",  // Must be valid entity type
  "properties": {
    "name": "CodeBot",
    "model_name": "gpt-4",
    "temperature": 0.7,
    "system_prompt": "You are a helpful coding assistant"
  }
}
// Returns validation errors if constraints violated
```

## Storage Strategy

### SurrealDB Schema for Ontology

```rust
// Store ontology schema
DEFINE TABLE ontology_schema SCHEMAFULL;
DEFINE FIELD namespace ON ontology_schema TYPE string;
DEFINE FIELD version ON ontology_schema TYPE string;
DEFINE FIELD entity_types ON ontology_schema TYPE object;
DEFINE FIELD relation_types ON ontology_schema TYPE object;

// Store validated entities with type info
DEFINE TABLE entities SCHEMAFULL;
DEFINE FIELD id ON entities TYPE string;
DEFINE FIELD type_id ON entities TYPE string;
DEFINE FIELD properties ON entities TYPE object;
DEFINE FIELD validated_at ON entities TYPE datetime;

// Store typed relations
DEFINE TABLE relations SCHEMAFULL;
DEFINE FIELD from_entity ON relations TYPE string;
DEFINE FIELD to_entity ON relations TYPE string;
DEFINE FIELD relation_type ON relations TYPE string;
DEFINE FIELD properties ON relations TYPE object;
```

## Benefits for VectaDB

### 1. Enhanced Observability
- **Type-safe agent tracking**: LLMAgent vs HumanAgent
- **Semantic task classification**: Different task types with inheritance
- **Relationship inference**: Automatically infer task dependencies

### 2. Better Search
- **Hierarchical queries**: Search for "Agent" includes all agent subtypes
- **Semantic filtering**: Find agents with specific capabilities
- **Relation-aware search**: Find tasks related through transitive relations

### 3. Data Quality
- **Schema validation**: Prevent invalid data entry
- **Constraint enforcement**: Ensure data integrity
- **Type safety**: Strong typing for entities and relations

### 4. Reasoning Capabilities
- **Inference**: Derive new facts from existing data
- **Consistency checking**: Detect contradictions
- **Query expansion**: Automatically broaden searches

## Example Use Cases

### Use Case 1: Find All Coding Agents
```rust
// Query: Find agents capable of coding
// Without ontology: Manual filtering
// With ontology: Automatic expansion

query = {
  "type": "Agent",
  "capabilities": "coding",
  "expand_subtypes": true  // Includes LLMAgent, HumanAgent
}

// VectaDB automatically:
// 1. Expands to LLMAgent and HumanAgent
// 2. Searches embeddings in both collections
// 3. Ranks by ontological relevance
```

### Use Case 2: Task Dependency Chain
```rust
// Query: Find all tasks in dependency chain
// Without ontology: Manual graph traversal
// With ontology: Automatic transitive inference

query = {
  "type": "Task",
  "id": "task-123",
  "relation": "depends_on",
  "transitive": true  // Follows entire chain
}

// VectaDB automatically:
// 1. Recognizes "depends_on" is transitive
// 2. Traverses entire dependency tree
// 3. Returns all related tasks
```

### Use Case 3: Agent Collaboration Graph
```rust
// Query: Find collaboration network
// Without ontology: Complex multi-hop queries
// With ontology: Semantic expansion

query = {
  "type": "Agent",
  "relation": "collaborates_with",
  "depth": 2,
  "symmetric": true  // Uses ontology symmetry
}

// VectaDB automatically:
// 1. Uses symmetric property
// 2. Builds bidirectional graph
// 3. Finds collaboration clusters
```

## Implementation Priorities

### Must Have (MVP)
1. ✅ Basic entity type definitions
2. ✅ Entity type inheritance
3. ✅ Schema validation
4. ✅ Query expansion (subtypes)

### Should Have (v1.1)
5. ⬜ Relation type constraints
6. ⬜ Transitive relation inference
7. ⬜ Custom inference rules
8. ⬜ Ontology versioning

### Nice to Have (v2.0)
9. ⬜ Full OWL/RDF import
10. ⬜ SPARQL query support
11. ⬜ Automated reasoning engine
12. ⬜ Ontology visualization

## Crates to Add

```toml
[dependencies]
# Ontology support
sophia = "0.8"           # RDF/OWL toolkit
oxigraph = "0.4"         # RDF database (optional)
serde_yaml = "0.9"       # YAML ontology files

# Validation
jsonschema = "0.17"      # JSON schema validation
regex = "1.10"           # Pattern constraints
```

## Migration Path

1. **Week 1-2**: Implement basic ontology layer (no breaking changes)
2. **Week 3-4**: Add optional ontology validation to existing APIs
3. **Week 5-6**: Enhance search with ontology expansion
4. **Week 7-8**: Document and test real-world agent ontologies

## Alignment with Paper

With ontology support, VectaDB achieves the paper's vision:

✅ **Unified data model** - Vectors, graphs, and ontologies
✅ **Ontology-native** - First-class ontological semantics
✅ **Hybrid queries** - Structural + similarity + ontological
✅ **Semantic reasoning** - Inference and expansion
✅ **Research-grade** - Suitable for academic work

---

## Next Steps

1. Review this design
2. Prioritize features for MVP
3. Implement Phase 1 (ontology core)
4. Test with real agent ontologies
5. Update paper to reflect implementation

**Questions?**
- Should we support full OWL or start simpler?
- YAML vs JSON for ontology definition?
- How complex should inference rules be?
