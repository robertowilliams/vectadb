// Relation type definitions for ontology

use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

/// Represents an ontology relation/object property
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RelationType {
    /// Unique identifier (e.g., "executes", "hasSubTask")
    pub id: String,

    /// Human-readable label
    pub label: String,

    /// Source entity type (domain)
    pub domain: String,

    /// Target entity type (range)
    pub range: String,

    /// Inverse relation (if exists)
    pub inverse: Option<String>,

    /// Is this relation transitive? (if A→B and B→C then A→C)
    pub transitive: bool,

    /// Is this relation symmetric? (if A→B then B→A)
    pub symmetric: bool,

    /// Is this relation functional? (max one target per source)
    pub functional: bool,

    /// Is this relation reflexive? (A→A always true)
    pub reflexive: bool,

    /// Additional metadata
    pub metadata: JsonValue,
}

impl RelationType {
    /// Create a new relation type
    pub fn new(id: String, label: String, domain: String, range: String) -> Self {
        Self {
            id,
            label,
            domain,
            range,
            inverse: None,
            transitive: false,
            symmetric: false,
            functional: false,
            reflexive: false,
            metadata: JsonValue::Null,
        }
    }

    /// Set inverse relation
    pub fn with_inverse(mut self, inverse: String) -> Self {
        self.inverse = Some(inverse);
        self
    }

    /// Mark as transitive
    pub fn transitive(mut self) -> Self {
        self.transitive = true;
        self
    }

    /// Mark as symmetric
    pub fn symmetric(mut self) -> Self {
        self.symmetric = true;
        self
    }

    /// Mark as functional (max one target)
    pub fn functional(mut self) -> Self {
        self.functional = true;
        self
    }

    /// Mark as reflexive
    pub fn reflexive(mut self) -> Self {
        self.reflexive = true;
        self
    }

    /// Check if relation can connect two entity types
    pub fn can_connect(
        &self,
        source_type: &str,
        target_type: &str,
        schema: &super::schema::OntologySchema,
    ) -> bool {
        // Check if source is compatible with domain
        let source_compatible = if let Some(source_entity) = schema.entity_types.get(source_type) {
            source_entity.is_subtype_of(&self.domain, schema)
        } else {
            false
        };

        // Check if target is compatible with range
        let target_compatible = if let Some(target_entity) = schema.entity_types.get(target_type) {
            target_entity.is_subtype_of(&self.range, schema)
        } else {
            false
        };

        source_compatible && target_compatible
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ontology::entity_type::EntityType;
    use crate::ontology::schema::OntologySchema;
    use std::collections::HashMap;

    #[test]
    fn test_relation_type_creation() {
        let rel = RelationType::new(
            "executes".to_string(),
            "executes".to_string(),
            "Agent".to_string(),
            "Task".to_string(),
        );

        assert_eq!(rel.id, "executes");
        assert_eq!(rel.domain, "Agent");
        assert_eq!(rel.range, "Task");
        assert!(!rel.transitive);
    }

    #[test]
    fn test_transitive_relation() {
        let rel = RelationType::new(
            "hasSubTask".to_string(),
            "has subtask".to_string(),
            "Task".to_string(),
            "Task".to_string(),
        )
        .transitive();

        assert!(rel.transitive);
    }

    #[test]
    fn test_symmetric_relation() {
        let rel = RelationType::new(
            "collaboratesWith".to_string(),
            "collaborates with".to_string(),
            "Agent".to_string(),
            "Agent".to_string(),
        )
        .symmetric();

        assert!(rel.symmetric);
    }

    #[test]
    fn test_relation_with_inverse() {
        let rel = RelationType::new(
            "executes".to_string(),
            "executes".to_string(),
            "Agent".to_string(),
            "Task".to_string(),
        )
        .with_inverse("executedBy".to_string());

        assert_eq!(rel.inverse, Some("executedBy".to_string()));
    }

    #[test]
    fn test_can_connect() {
        let mut entity_types = HashMap::new();
        entity_types.insert(
            "Agent".to_string(),
            EntityType::new("Agent".to_string(), "Agent".to_string()),
        );
        entity_types.insert(
            "Task".to_string(),
            EntityType::new("Task".to_string(), "Task".to_string()),
        );
        entity_types.insert(
            "LLMAgent".to_string(),
            EntityType::new("LLMAgent".to_string(), "LLM Agent".to_string())
                .with_parent("Agent".to_string()),
        );

        let schema = OntologySchema {
            namespace: "test".to_string(),
            version: "1.0".to_string(),
            entity_types,
            relation_types: HashMap::new(),
            rules: Vec::new(),
        };

        let rel = RelationType::new(
            "executes".to_string(),
            "executes".to_string(),
            "Agent".to_string(),
            "Task".to_string(),
        );

        // Agent can execute Task
        assert!(rel.can_connect("Agent", "Task", &schema));

        // LLMAgent (subtype of Agent) can execute Task
        assert!(rel.can_connect("LLMAgent", "Task", &schema));

        // Task cannot execute Agent (wrong direction)
        assert!(!rel.can_connect("Task", "Agent", &schema));
    }
}
