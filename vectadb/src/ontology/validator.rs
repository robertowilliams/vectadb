// Entity and relation validation against ontology schema

use serde_json::Value as JsonValue;
use std::collections::HashMap;

use super::schema::OntologySchema;
use super::entity_type::{PropertyType, Cardinality, Constraint};

/// Ontology validator
pub struct OntologyValidator {
    schema: OntologySchema,
}

/// Validation error
#[derive(Debug, Clone, PartialEq)]
pub enum ValidationError {
    /// Entity type not found in schema
    UnknownEntityType(String),

    /// Relation type not found in schema
    UnknownRelationType(String),

    /// Required property is missing
    MissingRequiredProperty {
        entity_type: String,
        property: String,
    },

    /// Property type mismatch
    PropertyTypeMismatch {
        property: String,
        expected: String,
        found: String,
    },

    /// Cardinality violation
    CardinalityViolation {
        property: String,
        expected: String,
        found: usize,
    },

    /// Constraint violation
    ConstraintViolation {
        property: String,
        constraint: String,
        value: String,
    },

    /// Invalid relation (incompatible types)
    InvalidRelation {
        relation: String,
        source_type: String,
        target_type: String,
        reason: String,
    },
}

impl std::fmt::Display for ValidationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ValidationError::UnknownEntityType(t) => {
                write!(f, "Unknown entity type: {}", t)
            }
            ValidationError::UnknownRelationType(t) => {
                write!(f, "Unknown relation type: {}", t)
            }
            ValidationError::MissingRequiredProperty {
                entity_type,
                property,
            } => {
                write!(
                    f,
                    "Missing required property '{}' for entity type '{}'",
                    property, entity_type
                )
            }
            ValidationError::PropertyTypeMismatch {
                property,
                expected,
                found,
            } => {
                write!(
                    f,
                    "Property '{}': expected type '{}', found '{}'",
                    property, expected, found
                )
            }
            ValidationError::CardinalityViolation {
                property,
                expected,
                found,
            } => {
                write!(
                    f,
                    "Property '{}': expected {}, found {} values",
                    property, expected, found
                )
            }
            ValidationError::ConstraintViolation {
                property,
                constraint,
                value,
            } => {
                write!(
                    f,
                    "Property '{}': constraint '{}' violated by value '{}'",
                    property, constraint, value
                )
            }
            ValidationError::InvalidRelation {
                relation,
                source_type,
                target_type,
                reason,
            } => {
                write!(
                    f,
                    "Invalid relation '{}' from '{}' to '{}': {}",
                    relation, source_type, target_type, reason
                )
            }
        }
    }
}

impl std::error::Error for ValidationError {}

impl OntologyValidator {
    /// Create a new validator with the given schema
    pub fn new(schema: OntologySchema) -> Self {
        Self { schema }
    }

    /// Validate an entity against the schema
    pub fn validate_entity(
        &self,
        entity_type_id: &str,
        properties: &HashMap<String, JsonValue>,
    ) -> Result<(), Vec<ValidationError>> {
        let mut errors = Vec::new();

        // Check if entity type exists
        let entity_type = match self.schema.entity_types.get(entity_type_id) {
            Some(et) => et,
            None => {
                errors.push(ValidationError::UnknownEntityType(
                    entity_type_id.to_string(),
                ));
                return Err(errors);
            }
        };

        // Get all properties (including inherited)
        let all_properties = entity_type.get_all_properties(&self.schema);

        // Check required properties
        for prop_def in &all_properties {
            if prop_def.required && !properties.contains_key(&prop_def.name) {
                errors.push(ValidationError::MissingRequiredProperty {
                    entity_type: entity_type_id.to_string(),
                    property: prop_def.name.clone(),
                });
            }
        }

        // Validate each provided property
        for (prop_name, prop_value) in properties {
            // Find property definition
            let prop_def = all_properties
                .iter()
                .find(|p| &p.name == prop_name);

            if let Some(def) = prop_def {
                // Validate type
                if let Err(e) = self.validate_property_type(
                    prop_name,
                    prop_value,
                    &def.property_type,
                ) {
                    errors.push(e);
                }

                // Validate cardinality
                if let Err(e) = self.validate_cardinality(
                    prop_name,
                    prop_value,
                    &def.cardinality,
                ) {
                    errors.push(e);
                }
            }
            // Note: We don't error on unknown properties (open world assumption)
        }

        // Validate constraints
        for constraint in &entity_type.constraints {
            if let Err(e) = self.validate_constraint(constraint, properties) {
                errors.push(e);
            }
        }

        if errors.is_empty() {
            Ok(())
        } else {
            Err(errors)
        }
    }

    /// Validate a relation
    pub fn validate_relation(
        &self,
        relation_type_id: &str,
        source_type: &str,
        target_type: &str,
    ) -> Result<(), ValidationError> {
        // Check if relation type exists
        let relation_type = self
            .schema
            .relation_types
            .get(relation_type_id)
            .ok_or_else(|| {
                ValidationError::UnknownRelationType(relation_type_id.to_string())
            })?;

        // Check if source and target types can be connected
        if !relation_type.can_connect(source_type, target_type, &self.schema) {
            return Err(ValidationError::InvalidRelation {
                relation: relation_type_id.to_string(),
                source_type: source_type.to_string(),
                target_type: target_type.to_string(),
                reason: format!(
                    "Expected domain '{}' and range '{}', got source '{}' and target '{}'",
                    relation_type.domain, relation_type.range, source_type, target_type
                ),
            });
        }

        Ok(())
    }

    /// Validate property type
    fn validate_property_type(
        &self,
        prop_name: &str,
        value: &JsonValue,
        expected_type: &PropertyType,
    ) -> Result<(), ValidationError> {
        let actual_type = match value {
            JsonValue::String(_) => "String",
            JsonValue::Number(_) => "Number",
            JsonValue::Bool(_) => "Boolean",
            JsonValue::Array(_) => "Array",
            JsonValue::Object(_) => "Object",
            JsonValue::Null => "Null",
        };

        let matches = match expected_type {
            PropertyType::String => value.is_string(),
            PropertyType::Number => value.is_number(),
            PropertyType::Boolean => value.is_boolean(),
            PropertyType::DateTime => value.is_string(), // TODO: validate datetime format
            PropertyType::Reference(_) => value.is_string(),
            PropertyType::Embedding => value.is_array(),
            PropertyType::Object => value.is_object(),
            PropertyType::Array(_) => value.is_array(),
        };

        if !matches {
            return Err(ValidationError::PropertyTypeMismatch {
                property: prop_name.to_string(),
                expected: format!("{:?}", expected_type),
                found: actual_type.to_string(),
            });
        }

        Ok(())
    }

    /// Validate cardinality
    fn validate_cardinality(
        &self,
        prop_name: &str,
        value: &JsonValue,
        cardinality: &Cardinality,
    ) -> Result<(), ValidationError> {
        let count = if value.is_array() {
            value.as_array().map(|a| a.len()).unwrap_or(0)
        } else {
            1
        };

        let valid = match cardinality {
            Cardinality::One => count == 1,
            Cardinality::ZeroOrOne => count <= 1,
            Cardinality::Many => true,
            Cardinality::OneOrMore => count >= 1,
        };

        if !valid {
            return Err(ValidationError::CardinalityViolation {
                property: prop_name.to_string(),
                expected: format!("{:?}", cardinality),
                found: count,
            });
        }

        Ok(())
    }

    /// Validate constraint
    fn validate_constraint(
        &self,
        constraint: &Constraint,
        properties: &HashMap<String, JsonValue>,
    ) -> Result<(), ValidationError> {
        match constraint {
            Constraint::ValueRange { min, max } => {
                // Check all number properties
                for (prop_name, value) in properties {
                    if let Some(num) = value.as_f64() {
                        if num < *min || num > *max {
                            return Err(ValidationError::ConstraintViolation {
                                property: prop_name.clone(),
                                constraint: format!("ValueRange({}, {})", min, max),
                                value: num.to_string(),
                            });
                        }
                    }
                }
            }
            Constraint::Pattern(pattern) => {
                // TODO: Validate regex pattern
                // Would need regex crate
                let _ = pattern; // Suppress warning for now
            }
            Constraint::Enum(allowed_values) => {
                // Check all string properties
                for (prop_name, value) in properties {
                    if let Some(s) = value.as_str() {
                        if !allowed_values.contains(&s.to_string()) {
                            return Err(ValidationError::ConstraintViolation {
                                property: prop_name.clone(),
                                constraint: format!("Enum({:?})", allowed_values),
                                value: s.to_string(),
                            });
                        }
                    }
                }
            }
            Constraint::StringLength { min, max } => {
                // Check all string properties
                for (prop_name, value) in properties {
                    if let Some(s) = value.as_str() {
                        let len = s.len();
                        if let Some(min_len) = min {
                            if len < *min_len {
                                return Err(ValidationError::ConstraintViolation {
                                    property: prop_name.clone(),
                                    constraint: format!("StringLength(min: {})", min_len),
                                    value: s.to_string(),
                                });
                            }
                        }
                        if let Some(max_len) = max {
                            if len > *max_len {
                                return Err(ValidationError::ConstraintViolation {
                                    property: prop_name.clone(),
                                    constraint: format!("StringLength(max: {})", max_len),
                                    value: s.to_string(),
                                });
                            }
                        }
                    }
                }
            }
            Constraint::Custom(_) => {
                // TODO: Implement custom constraint validation
            }
        }

        Ok(())
    }

    /// Get the schema
    pub fn schema(&self) -> &OntologySchema {
        &self.schema
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::entity_type::{EntityType, PropertyDefinition};
    use super::super::relation_type::RelationType;

    #[test]
    fn test_validate_entity_success() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        let agent = EntityType::new("Agent".to_string(), "Agent".to_string())
            .with_property(
                PropertyDefinition::new("name".to_string(), PropertyType::String).required()
            );
        schema.add_entity_type(agent);

        let validator = OntologyValidator::new(schema);

        let mut properties = HashMap::new();
        properties.insert("name".to_string(), JsonValue::String("Test Agent".to_string()));

        assert!(validator.validate_entity("Agent", &properties).is_ok());
    }

    #[test]
    fn test_validate_entity_missing_required() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        let agent = EntityType::new("Agent".to_string(), "Agent".to_string())
            .with_property(
                PropertyDefinition::new("name".to_string(), PropertyType::String).required()
            );
        schema.add_entity_type(agent);

        let validator = OntologyValidator::new(schema);

        let properties = HashMap::new(); // Missing required "name"

        let result = validator.validate_entity("Agent", &properties);
        assert!(result.is_err());

        let errors = result.unwrap_err();
        assert_eq!(errors.len(), 1);
        assert!(matches!(
            errors[0],
            ValidationError::MissingRequiredProperty { .. }
        ));
    }

    #[test]
    fn test_validate_entity_type_mismatch() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        let agent = EntityType::new("Agent".to_string(), "Agent".to_string())
            .with_property(
                PropertyDefinition::new("age".to_string(), PropertyType::Number)
            );
        schema.add_entity_type(agent);

        let validator = OntologyValidator::new(schema);

        let mut properties = HashMap::new();
        properties.insert("age".to_string(), JsonValue::String("not a number".to_string()));

        let result = validator.validate_entity("Agent", &properties);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_relation_success() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        schema.add_entity_type(EntityType::new("Agent".to_string(), "Agent".to_string()));
        schema.add_entity_type(EntityType::new("Task".to_string(), "Task".to_string()));
        schema.add_relation_type(RelationType::new(
            "executes".to_string(),
            "executes".to_string(),
            "Agent".to_string(),
            "Task".to_string(),
        ));

        let validator = OntologyValidator::new(schema);

        assert!(validator
            .validate_relation("executes", "Agent", "Task")
            .is_ok());
    }

    #[test]
    fn test_validate_relation_invalid() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        schema.add_entity_type(EntityType::new("Agent".to_string(), "Agent".to_string()));
        schema.add_entity_type(EntityType::new("Task".to_string(), "Task".to_string()));
        schema.add_relation_type(RelationType::new(
            "executes".to_string(),
            "executes".to_string(),
            "Agent".to_string(),
            "Task".to_string(),
        ));

        let validator = OntologyValidator::new(schema);

        // Wrong direction
        let result = validator.validate_relation("executes", "Task", "Agent");
        assert!(result.is_err());
    }
}
