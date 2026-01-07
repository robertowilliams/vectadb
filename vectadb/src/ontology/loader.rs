// Ontology loader for YAML files

use super::schema::OntologySchema;
use crate::error::{Result, VectaDBError};
use std::path::Path;

/// Ontology loader
pub struct OntologyLoader;

impl OntologyLoader {
    /// Load ontology from YAML file
    pub fn from_yaml_file<P: AsRef<Path>>(path: P) -> Result<OntologySchema> {
        let content = std::fs::read_to_string(path.as_ref()).map_err(|e| {
            VectaDBError::Config(format!(
                "Failed to read ontology file '{}': {}",
                path.as_ref().display(),
                e
            ))
        })?;

        Self::from_yaml_str(&content)
    }

    /// Load ontology from YAML string
    pub fn from_yaml_str(yaml: &str) -> Result<OntologySchema> {
        let schema: OntologySchema = serde_yaml::from_str(yaml).map_err(|e| {
            VectaDBError::Config(format!("Failed to parse ontology YAML: {}", e))
        })?;

        // Validate the schema
        schema.validate().map_err(|e| {
            VectaDBError::Config(format!("Ontology validation failed: {}", e))
        })?;

        Ok(schema)
    }

    /// Save ontology to YAML file
    pub fn to_yaml_file<P: AsRef<Path>>(schema: &OntologySchema, path: P) -> Result<()> {
        let yaml = Self::to_yaml_str(schema)?;

        std::fs::write(path.as_ref(), yaml).map_err(|e| {
            VectaDBError::Config(format!(
                "Failed to write ontology file '{}': {}",
                path.as_ref().display(),
                e
            ))
        })?;

        Ok(())
    }

    /// Convert ontology to YAML string
    pub fn to_yaml_str(schema: &OntologySchema) -> Result<String> {
        serde_yaml::to_string(schema).map_err(|e| {
            VectaDBError::Config(format!("Failed to serialize ontology to YAML: {}", e))
        })
    }

    /// Load ontology from JSON string
    pub fn from_json_str(json: &str) -> Result<OntologySchema> {
        let schema = OntologySchema::from_json(json).map_err(|e| {
            VectaDBError::Config(format!("Failed to parse ontology JSON: {}", e))
        })?;

        // Validate the schema
        schema.validate().map_err(|e| {
            VectaDBError::Config(format!("Ontology validation failed: {}", e))
        })?;

        Ok(schema)
    }

    /// Convert ontology to JSON string
    pub fn to_json_str(schema: &OntologySchema) -> Result<String> {
        schema.to_json().map_err(|e| {
            VectaDBError::Config(format!("Failed to serialize ontology to JSON: {}", e))
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ontology::entity_type::EntityType;
    use crate::ontology::relation_type::RelationType;

    #[test]
    fn test_yaml_round_trip() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());
        schema.add_entity_type(EntityType::new("Agent".to_string(), "Agent".to_string()));
        schema.add_relation_type(RelationType::new(
            "executes".to_string(),
            "executes".to_string(),
            "Agent".to_string(),
            "Agent".to_string(),
        ));

        let yaml = OntologyLoader::to_yaml_str(&schema).unwrap();
        let loaded = OntologyLoader::from_yaml_str(&yaml).unwrap();

        assert_eq!(loaded.namespace, schema.namespace);
        assert_eq!(loaded.version, schema.version);
        assert_eq!(loaded.entity_types.len(), 1);
        assert_eq!(loaded.relation_types.len(), 1);
    }

    #[test]
    fn test_json_round_trip() {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());
        schema.add_entity_type(EntityType::new("Task".to_string(), "Task".to_string()));

        let json = OntologyLoader::to_json_str(&schema).unwrap();
        let loaded = OntologyLoader::from_json_str(&json).unwrap();

        assert_eq!(loaded.namespace, schema.namespace);
        assert_eq!(loaded.entity_types.len(), 1);
    }

    #[test]
    fn test_invalid_yaml() {
        let invalid_yaml = "this is not valid yaml: {{{";
        let result = OntologyLoader::from_yaml_str(invalid_yaml);
        assert!(result.is_err());
    }

    #[test]
    fn test_validation_failure() {
        // Create schema with missing parent
        let yaml = r#"
namespace: "test"
version: "1.0"
entity_types:
  Child:
    id: "Child"
    label: "Child"
    parent: "NonExistent"
    properties: []
    constraints: []
    metadata: null
relation_types: {}
rules: []
"#;

        let result = OntologyLoader::from_yaml_str(yaml);
        assert!(result.is_err());
    }
}
