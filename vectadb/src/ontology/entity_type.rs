// Entity type definitions for ontology

use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

/// Represents an ontology class/type
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityType {
    /// Unique identifier (e.g., "Agent", "LLMAgent")
    pub id: String,

    /// Human-readable label
    pub label: String,

    /// Parent type for inheritance (e.g., "LLMAgent" -> "Agent")
    pub parent: Option<String>,

    /// Property definitions
    pub properties: Vec<PropertyDefinition>,

    /// Constraints on this type
    pub constraints: Vec<Constraint>,

    /// Additional metadata
    pub metadata: JsonValue,
}

/// Property definition in ontology
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PropertyDefinition {
    /// Property name
    pub name: String,

    /// Property type
    pub property_type: PropertyType,

    /// Is this property required?
    pub required: bool,

    /// Cardinality of the property
    pub cardinality: Cardinality,

    /// Optional description
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

/// Property type
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(tag = "type", content = "config")]
pub enum PropertyType {
    String,
    Number,
    Boolean,
    DateTime,
    /// Reference to another entity type
    Reference(String),
    /// Vector embedding
    Embedding,
    /// JSON object
    Object,
    /// Array of another type
    Array(Box<PropertyType>),
}

/// Cardinality constraints
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Cardinality {
    /// Exactly one value required
    One,
    /// Zero or one value (optional)
    ZeroOrOne,
    /// Zero or more values
    Many,
    /// At least one value required
    OneOrMore,
}

/// Constraints on values
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", content = "config")]
pub enum Constraint {
    /// Value must be within range (for numbers)
    ValueRange { min: f64, max: f64 },

    /// Value must match regex pattern
    Pattern(String),

    /// Value must be one of enum values
    Enum(Vec<String>),

    /// String length constraints
    StringLength { min: Option<usize>, max: Option<usize> },

    /// Custom validation rule
    Custom(String),
}

impl EntityType {
    /// Create a new entity type
    pub fn new(id: String, label: String) -> Self {
        Self {
            id,
            label,
            parent: None,
            properties: Vec::new(),
            constraints: Vec::new(),
            metadata: JsonValue::Null,
        }
    }

    /// Set parent type (for inheritance)
    pub fn with_parent(mut self, parent: String) -> Self {
        self.parent = Some(parent);
        self
    }

    /// Add a property
    pub fn with_property(mut self, property: PropertyDefinition) -> Self {
        self.properties.push(property);
        self
    }

    /// Add a constraint
    pub fn with_constraint(mut self, constraint: Constraint) -> Self {
        self.constraints.push(constraint);
        self
    }

    /// Get all properties including inherited ones
    pub fn get_all_properties(&self, schema: &super::schema::OntologySchema) -> Vec<PropertyDefinition> {
        let mut properties = self.properties.clone();

        // Add parent properties if exists
        if let Some(parent_id) = &self.parent {
            if let Some(parent_type) = schema.entity_types.get(parent_id) {
                let parent_props = parent_type.get_all_properties(schema);
                properties.extend(parent_props);
            }
        }

        properties
    }

    /// Check if this type is a subtype of another
    pub fn is_subtype_of(&self, other_id: &str, schema: &super::schema::OntologySchema) -> bool {
        if self.id == other_id {
            return true;
        }

        if let Some(parent_id) = &self.parent {
            if parent_id == other_id {
                return true;
            }

            // Check recursively
            if let Some(parent_type) = schema.entity_types.get(parent_id) {
                return parent_type.is_subtype_of(other_id, schema);
            }
        }

        false
    }
}

impl PropertyDefinition {
    /// Create a new property definition
    pub fn new(name: String, property_type: PropertyType) -> Self {
        Self {
            name,
            property_type,
            required: false,
            cardinality: Cardinality::ZeroOrOne,
            description: None,
        }
    }

    /// Mark as required
    pub fn required(mut self) -> Self {
        self.required = true;
        self.cardinality = Cardinality::One;
        self
    }

    /// Set cardinality
    pub fn with_cardinality(mut self, cardinality: Cardinality) -> Self {
        self.cardinality = cardinality;
        self
    }

    /// Add description
    pub fn with_description(mut self, description: String) -> Self {
        self.description = Some(description);
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ontology::schema::OntologySchema;
    use std::collections::HashMap;

    #[test]
    fn test_entity_type_creation() {
        let entity_type = EntityType::new("Agent".to_string(), "Agent".to_string())
            .with_property(
                PropertyDefinition::new("name".to_string(), PropertyType::String)
                    .required()
            );

        assert_eq!(entity_type.id, "Agent");
        assert_eq!(entity_type.properties.len(), 1);
        assert!(entity_type.properties[0].required);
    }

    #[test]
    fn test_entity_type_inheritance() {
        let mut entity_types = HashMap::new();

        let agent = EntityType::new("Agent".to_string(), "Agent".to_string());
        let llm_agent = EntityType::new("LLMAgent".to_string(), "LLM Agent".to_string())
            .with_parent("Agent".to_string());

        entity_types.insert("Agent".to_string(), agent);
        entity_types.insert("LLMAgent".to_string(), llm_agent.clone());

        let schema = OntologySchema {
            namespace: "test".to_string(),
            version: "1.0".to_string(),
            entity_types,
            relation_types: HashMap::new(),
            rules: Vec::new(),
        };

        assert!(llm_agent.is_subtype_of("Agent", &schema));
        assert!(llm_agent.is_subtype_of("LLMAgent", &schema));
        assert!(!llm_agent.is_subtype_of("Task", &schema));
    }

    #[test]
    fn test_property_types() {
        let string_prop = PropertyDefinition::new("name".to_string(), PropertyType::String);
        assert_eq!(string_prop.property_type, PropertyType::String);

        let ref_prop = PropertyDefinition::new(
            "agent".to_string(),
            PropertyType::Reference("Agent".to_string())
        );
        assert!(matches!(ref_prop.property_type, PropertyType::Reference(_)));
    }

    #[test]
    fn test_cardinality() {
        let prop = PropertyDefinition::new("tags".to_string(), PropertyType::String)
            .with_cardinality(Cardinality::Many);

        assert_eq!(prop.cardinality, Cardinality::Many);
    }
}
