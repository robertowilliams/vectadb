// Ontology schema management

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use super::entity_type::EntityType;
use super::relation_type::RelationType;

/// Complete ontology schema
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OntologySchema {
    /// Ontology namespace/URI
    pub namespace: String,

    /// Schema version
    pub version: String,

    /// Entity type definitions
    pub entity_types: HashMap<String, EntityType>,

    /// Relation type definitions
    pub relation_types: HashMap<String, RelationType>,

    /// Inference rules
    pub rules: Vec<InferenceRule>,
}

/// Inference rule for reasoning
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceRule {
    /// Rule identifier
    pub id: String,

    /// Rule type
    pub rule_type: RuleType,

    /// Description
    pub description: String,

    /// Conditions that must be met
    pub conditions: Vec<Condition>,

    /// Conclusion to infer
    pub conclusion: Conclusion,
}

/// Type of inference rule
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum RuleType {
    /// Subclass relationship
    SubClassOf,

    /// Equivalence relationship
    Equivalent,

    /// Mutual exclusion
    Disjoint,

    /// Property chain (e.g., hasParent o hasSibling -> hasUncleAunt)
    PropertyChain,

    /// Custom rule
    Custom(String),
}

/// Condition in a rule
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Condition {
    /// Subject (entity or variable)
    pub subject: String,

    /// Predicate (relation type)
    pub predicate: String,

    /// Object (entity or variable)
    pub object: String,
}

/// Conclusion to infer
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Conclusion {
    /// Subject (entity or variable)
    pub subject: String,

    /// Predicate (relation type)
    pub predicate: String,

    /// Object (entity or variable)
    pub object: String,
}

impl OntologySchema {
    /// Create a new empty schema
    pub fn new(namespace: String, version: String) -> Self {
        Self {
            namespace,
            version,
            entity_types: HashMap::new(),
            relation_types: HashMap::new(),
            rules: Vec::new(),
        }
    }

    /// Add an entity type
    pub fn add_entity_type(&mut self, entity_type: EntityType) {
        self.entity_types.insert(entity_type.id.clone(), entity_type);
    }

    /// Add a relation type
    pub fn add_relation_type(&mut self, relation_type: RelationType) {
        self.relation_types
            .insert(relation_type.id.clone(), relation_type);
    }

    /// Add an inference rule
    pub fn add_rule(&mut self, rule: InferenceRule) {
        self.rules.push(rule);
    }

    /// Get all subtypes of an entity type (including itself)
    pub fn get_subtypes(&self, type_id: &str) -> Vec<String> {
        let mut subtypes = vec![type_id.to_string()];

        for (id, entity_type) in &self.entity_types {
            if id != type_id && entity_type.is_subtype_of(type_id, self) {
                subtypes.push(id.clone());
            }
        }

        subtypes
    }

    /// Get all supertypes of an entity type (including itself)
    pub fn get_supertypes(&self, type_id: &str) -> Vec<String> {
        let mut supertypes = vec![type_id.to_string()];

        if let Some(entity_type) = self.entity_types.get(type_id) {
            let mut current = entity_type;
            while let Some(parent_id) = &current.parent {
                supertypes.push(parent_id.clone());
                if let Some(parent) = self.entity_types.get(parent_id) {
                    current = parent;
                } else {
                    break;
                }
            }
        }

        supertypes
    }

    /// Validate the schema for consistency
    pub fn validate(&self) -> Result<(), String> {
        // Check for circular inheritance
        for (id, entity_type) in &self.entity_types {
            if self.has_circular_inheritance(id)? {
                return Err(format!("Circular inheritance detected for type: {}", id));
            }

            // Check if parent exists
            if let Some(parent_id) = &entity_type.parent {
                if !self.entity_types.contains_key(parent_id) {
                    return Err(format!(
                        "Parent type '{}' not found for type '{}'",
                        parent_id, id
                    ));
                }
            }
        }

        // Check relation types
        for (id, relation_type) in &self.relation_types {
            // Check if domain exists
            if !self.entity_types.contains_key(&relation_type.domain) {
                return Err(format!(
                    "Domain type '{}' not found for relation '{}'",
                    relation_type.domain, id
                ));
            }

            // Check if range exists
            if !self.entity_types.contains_key(&relation_type.range) {
                return Err(format!(
                    "Range type '{}' not found for relation '{}'",
                    relation_type.range, id
                ));
            }

            // Check if inverse exists
            if let Some(inverse_id) = &relation_type.inverse {
                if !self.relation_types.contains_key(inverse_id) {
                    return Err(format!(
                        "Inverse relation '{}' not found for relation '{}'",
                        inverse_id, id
                    ));
                }
            }
        }

        Ok(())
    }

    /// Check for circular inheritance
    fn has_circular_inheritance(&self, type_id: &str) -> Result<bool, String> {
        let mut visited = std::collections::HashSet::new();
        let mut current_id = type_id.to_string();

        while let Some(entity_type) = self.entity_types.get(&current_id) {
            if !visited.insert(current_id.clone()) {
                return Ok(true); // Circular inheritance detected
            }

            if let Some(parent_id) = &entity_type.parent {
                current_id = parent_id.clone();
            } else {
                break;
            }
        }

        Ok(false)
    }

    /// Load schema from JSON
    pub fn from_json(json: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(json)
    }

    /// Serialize schema to JSON
    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string_pretty(self)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_schema_creation() {
        let schema = OntologySchema::new(
            "http://vectadb.com/ontology/test".to_string(),
            "1.0.0".to_string(),
        );

        assert_eq!(schema.namespace, "http://vectadb.com/ontology/test");
        assert_eq!(schema.version, "1.0.0");
        assert!(schema.entity_types.is_empty());
        assert!(schema.relation_types.is_empty());
    }

    #[test]
    fn test_add_entity_type() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        let entity_type = EntityType::new("Agent".to_string(), "Agent".to_string());
        schema.add_entity_type(entity_type);

        assert_eq!(schema.entity_types.len(), 1);
        assert!(schema.entity_types.contains_key("Agent"));
    }

    #[test]
    fn test_get_subtypes() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        schema.add_entity_type(EntityType::new("Agent".to_string(), "Agent".to_string()));
        schema.add_entity_type(
            EntityType::new("LLMAgent".to_string(), "LLM Agent".to_string())
                .with_parent("Agent".to_string()),
        );
        schema.add_entity_type(
            EntityType::new("HumanAgent".to_string(), "Human Agent".to_string())
                .with_parent("Agent".to_string()),
        );

        let subtypes = schema.get_subtypes("Agent");
        assert_eq!(subtypes.len(), 3);
        assert!(subtypes.contains(&"Agent".to_string()));
        assert!(subtypes.contains(&"LLMAgent".to_string()));
        assert!(subtypes.contains(&"HumanAgent".to_string()));
    }

    #[test]
    fn test_get_supertypes() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        schema.add_entity_type(EntityType::new("Agent".to_string(), "Agent".to_string()));
        schema.add_entity_type(
            EntityType::new("LLMAgent".to_string(), "LLM Agent".to_string())
                .with_parent("Agent".to_string()),
        );

        let supertypes = schema.get_supertypes("LLMAgent");
        assert_eq!(supertypes.len(), 2);
        assert!(supertypes.contains(&"LLMAgent".to_string()));
        assert!(supertypes.contains(&"Agent".to_string()));
    }

    #[test]
    fn test_schema_validation() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        schema.add_entity_type(EntityType::new("Agent".to_string(), "Agent".to_string()));
        schema.add_entity_type(
            EntityType::new("Task".to_string(), "Task".to_string()),
        );
        schema.add_relation_type(RelationType::new(
            "executes".to_string(),
            "executes".to_string(),
            "Agent".to_string(),
            "Task".to_string(),
        ));

        assert!(schema.validate().is_ok());
    }

    #[test]
    fn test_schema_validation_missing_parent() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        schema.add_entity_type(
            EntityType::new("LLMAgent".to_string(), "LLM Agent".to_string())
                .with_parent("Agent".to_string()), // Parent doesn't exist
        );

        assert!(schema.validate().is_err());
    }

    #[test]
    fn test_circular_inheritance_detection() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        // This would create a circular inheritance (in practice, would need manual HashMap manipulation)
        schema.add_entity_type(EntityType::new("A".to_string(), "A".to_string()));
        schema.add_entity_type(
            EntityType::new("B".to_string(), "B".to_string()).with_parent("A".to_string()),
        );

        assert!(!schema.has_circular_inheritance("B").unwrap());
    }

    #[test]
    fn test_schema_serialization() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());
        schema.add_entity_type(EntityType::new("Agent".to_string(), "Agent".to_string()));

        let json = schema.to_json().unwrap();
        let deserialized = OntologySchema::from_json(&json).unwrap();

        assert_eq!(deserialized.namespace, schema.namespace);
        assert_eq!(deserialized.entity_types.len(), 1);
    }
}
