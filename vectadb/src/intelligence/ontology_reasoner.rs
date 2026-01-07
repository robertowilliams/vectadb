// Ontology-aware query reasoning and expansion

use crate::ontology::schema::OntologySchema;
use crate::error::{Result, VectaDBError};
use std::collections::{HashMap, HashSet};

/// Expanded query with ontology-inferred information
#[derive(Debug, Clone)]
pub struct ExpandedQuery {
    /// Original entity type
    pub original_type: String,

    /// All types to search (including subtypes)
    pub expanded_types: Vec<String>,

    /// Inferred relations to consider
    pub inferred_relations: Vec<InferredRelation>,

    /// Metadata about the expansion
    pub metadata: HashMap<String, String>,
}

/// Inferred relation from ontology
#[derive(Debug, Clone)]
pub struct InferredRelation {
    /// Relation type
    pub relation_type: String,

    /// Source entity type
    pub source_type: String,

    /// Target entity type
    pub target_type: String,

    /// Why this relation was inferred
    pub reason: InferenceReason,
}

/// Reason for relation inference
#[derive(Debug, Clone, PartialEq)]
pub enum InferenceReason {
    /// Relation is transitive
    Transitive,

    /// Relation is symmetric
    Symmetric,

    /// Inverse relation exists
    Inverse,

    /// Subtype compatibility
    SubtypeInheritance,
}

/// Ontology-aware reasoner
pub struct OntologyReasoner {
    schema: OntologySchema,
}

impl OntologyReasoner {
    /// Create a new reasoner with the given schema
    pub fn new(schema: OntologySchema) -> Self {
        Self { schema }
    }

    /// Expand a query to include subtypes and inferred relations
    pub fn expand_query(&self, entity_type: &str) -> Result<ExpandedQuery> {
        // Check if entity type exists
        if !self.schema.entity_types.contains_key(entity_type) {
            return Err(VectaDBError::InvalidInput(format!(
                "Entity type '{}' not found in ontology",
                entity_type
            )));
        }

        // Get all subtypes (including the type itself)
        let expanded_types = self.schema.get_subtypes(entity_type);

        // Infer relations
        let inferred_relations = self.infer_relations(entity_type);

        // Collect metadata
        let mut metadata = HashMap::new();
        metadata.insert(
            "expansion_count".to_string(),
            expanded_types.len().to_string(),
        );
        metadata.insert(
            "inference_count".to_string(),
            inferred_relations.len().to_string(),
        );

        Ok(ExpandedQuery {
            original_type: entity_type.to_string(),
            expanded_types,
            inferred_relations,
            metadata,
        })
    }

    /// Infer relations for an entity type
    pub fn infer_relations(&self, entity_type: &str) -> Vec<InferredRelation> {
        let mut inferred = Vec::new();

        for (relation_id, relation_type) in &self.schema.relation_types {
            // Check if this relation applies to the entity type
            if self.is_type_compatible(entity_type, &relation_type.domain) {
                // Add direct relation
                inferred.push(InferredRelation {
                    relation_type: relation_id.clone(),
                    source_type: entity_type.to_string(),
                    target_type: relation_type.range.clone(),
                    reason: InferenceReason::SubtypeInheritance,
                });

                // If symmetric, add reverse
                if relation_type.symmetric {
                    inferred.push(InferredRelation {
                        relation_type: relation_id.clone(),
                        source_type: relation_type.range.clone(),
                        target_type: entity_type.to_string(),
                        reason: InferenceReason::Symmetric,
                    });
                }

                // If has inverse, add it
                if let Some(inverse_id) = &relation_type.inverse {
                    inferred.push(InferredRelation {
                        relation_type: inverse_id.clone(),
                        source_type: relation_type.range.clone(),
                        target_type: entity_type.to_string(),
                        reason: InferenceReason::Inverse,
                    });
                }
            }
        }

        inferred
    }

    /// Get transitive closure for a relation
    pub fn get_transitive_closure(
        &self,
        relation_type: &str,
        start_entity: &str,
        entities: &HashMap<String, HashSet<String>>,
    ) -> HashSet<String> {
        let mut closure = HashSet::new();
        let mut to_visit = vec![start_entity.to_string()];
        let mut visited = HashSet::new();

        // Check if relation is transitive
        let is_transitive = self
            .schema
            .relation_types
            .get(relation_type)
            .map(|r| r.transitive)
            .unwrap_or(false);

        if !is_transitive {
            // Just return direct connections
            if let Some(connected) = entities.get(start_entity) {
                return connected.clone();
            }
            return closure;
        }

        // BFS to find transitive closure
        while let Some(current) = to_visit.pop() {
            if visited.contains(&current) {
                continue;
            }
            visited.insert(current.clone());

            if let Some(connected) = entities.get(&current) {
                for target in connected {
                    closure.insert(target.clone());
                    to_visit.push(target.clone());
                }
            }
        }

        closure
    }

    /// Check if a type is compatible (equals or is subtype of)
    fn is_type_compatible(&self, actual_type: &str, expected_type: &str) -> bool {
        if actual_type == expected_type {
            return true;
        }

        if let Some(entity_type) = self.schema.entity_types.get(actual_type) {
            return entity_type.is_subtype_of(expected_type, &self.schema);
        }

        false
    }

    /// Get all compatible relations for a type pair
    pub fn get_compatible_relations(
        &self,
        source_type: &str,
        target_type: &str,
    ) -> Vec<String> {
        let mut compatible = Vec::new();

        for (relation_id, relation_type) in &self.schema.relation_types {
            if relation_type.can_connect(source_type, target_type, &self.schema) {
                compatible.push(relation_id.clone());
            }
        }

        compatible
    }

    /// Update the schema
    pub fn update_schema(&mut self, schema: OntologySchema) -> Result<()> {
        // Validate new schema
        schema.validate().map_err(|e| {
            VectaDBError::InvalidInput(format!("Invalid ontology schema: {}", e))
        })?;

        self.schema = schema;
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
    use crate::ontology::entity_type::EntityType;
    use crate::ontology::relation_type::RelationType;

    fn create_test_schema() -> OntologySchema {
        let mut schema = OntologySchema::new("test".to_string(), "1.0".to_string());

        // Create entity types
        schema.add_entity_type(EntityType::new("Agent".to_string(), "Agent".to_string()));
        schema.add_entity_type(
            EntityType::new("LLMAgent".to_string(), "LLM Agent".to_string())
                .with_parent("Agent".to_string()),
        );
        schema.add_entity_type(
            EntityType::new("HumanAgent".to_string(), "Human Agent".to_string())
                .with_parent("Agent".to_string()),
        );
        schema.add_entity_type(EntityType::new("Task".to_string(), "Task".to_string()));

        // Create relation types
        schema.add_relation_type(RelationType::new(
            "executes".to_string(),
            "executes".to_string(),
            "Agent".to_string(),
            "Task".to_string(),
        ));

        schema.add_relation_type(
            RelationType::new(
                "collaborates_with".to_string(),
                "collaborates with".to_string(),
                "Agent".to_string(),
                "Agent".to_string(),
            )
            .symmetric(),
        );

        schema.add_relation_type(
            RelationType::new(
                "has_subtask".to_string(),
                "has subtask".to_string(),
                "Task".to_string(),
                "Task".to_string(),
            )
            .transitive(),
        );

        schema
    }

    #[test]
    fn test_expand_query() {
        let schema = create_test_schema();
        let reasoner = OntologyReasoner::new(schema);

        let expanded = reasoner.expand_query("Agent").unwrap();

        assert_eq!(expanded.original_type, "Agent");
        assert_eq!(expanded.expanded_types.len(), 3); // Agent, LLMAgent, HumanAgent
        assert!(expanded.expanded_types.contains(&"Agent".to_string()));
        assert!(expanded.expanded_types.contains(&"LLMAgent".to_string()));
        assert!(expanded.expanded_types.contains(&"HumanAgent".to_string()));
    }

    #[test]
    fn test_expand_query_leaf_type() {
        let schema = create_test_schema();
        let reasoner = OntologyReasoner::new(schema);

        let expanded = reasoner.expand_query("LLMAgent").unwrap();

        assert_eq!(expanded.original_type, "LLMAgent");
        assert_eq!(expanded.expanded_types.len(), 1); // Just LLMAgent
        assert!(expanded.expanded_types.contains(&"LLMAgent".to_string()));
    }

    #[test]
    fn test_infer_relations() {
        let schema = create_test_schema();
        let reasoner = OntologyReasoner::new(schema);

        let inferred = reasoner.infer_relations("Agent");

        // Should infer: executes, collaborates_with (and its symmetric version)
        assert!(!inferred.is_empty());

        // Check that executes relation is inferred
        let has_executes = inferred
            .iter()
            .any(|r| r.relation_type == "executes" && r.target_type == "Task");
        assert!(has_executes);

        // Check that collaborates_with is inferred
        let has_collab = inferred
            .iter()
            .any(|r| r.relation_type == "collaborates_with");
        assert!(has_collab);
    }

    #[test]
    fn test_symmetric_relation_inference() {
        let schema = create_test_schema();
        let reasoner = OntologyReasoner::new(schema);

        let inferred = reasoner.infer_relations("Agent");

        // Should have symmetric inference for collaborates_with
        let symmetric_count = inferred
            .iter()
            .filter(|r| r.reason == InferenceReason::Symmetric)
            .count();
        assert!(symmetric_count > 0);
    }

    #[test]
    fn test_get_compatible_relations() {
        let schema = create_test_schema();
        let reasoner = OntologyReasoner::new(schema);

        let relations = reasoner.get_compatible_relations("Agent", "Task");
        assert!(relations.contains(&"executes".to_string()));

        let relations = reasoner.get_compatible_relations("LLMAgent", "Task");
        assert!(relations.contains(&"executes".to_string())); // LLMAgent is subtype of Agent
    }

    #[test]
    fn test_transitive_closure() {
        let schema = create_test_schema();
        let reasoner = OntologyReasoner::new(schema);

        // Create a task hierarchy: A -> B -> C
        let mut task_graph = HashMap::new();
        task_graph.insert(
            "task_a".to_string(),
            vec!["task_b".to_string()].into_iter().collect(),
        );
        task_graph.insert(
            "task_b".to_string(),
            vec!["task_c".to_string()].into_iter().collect(),
        );

        let closure = reasoner.get_transitive_closure("has_subtask", "task_a", &task_graph);

        // Should include both task_b and task_c (transitive)
        assert!(closure.contains("task_b"));
        assert!(closure.contains("task_c"));
        assert_eq!(closure.len(), 2);
    }

    #[test]
    fn test_expand_query_unknown_type() {
        let schema = create_test_schema();
        let reasoner = OntologyReasoner::new(schema);

        let result = reasoner.expand_query("UnknownType");
        assert!(result.is_err());
    }

    #[test]
    fn test_update_schema() {
        let schema = create_test_schema();
        let mut reasoner = OntologyReasoner::new(schema);

        let mut new_schema = OntologySchema::new("test2".to_string(), "2.0".to_string());
        new_schema.add_entity_type(EntityType::new("NewType".to_string(), "New Type".to_string()));

        assert!(reasoner.update_schema(new_schema).is_ok());
        assert_eq!(reasoner.schema().version, "2.0");
    }
}
