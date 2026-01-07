// VectaDB Ontology Layer
// Provides ontological semantics for entities and relations

pub mod entity_type;
pub mod relation_type;
pub mod schema;
pub mod validator;
pub mod loader;

pub use entity_type::{EntityType, PropertyDefinition, PropertyType, Cardinality, Constraint};
pub use relation_type::{RelationType};
pub use schema::{OntologySchema, InferenceRule, RuleType, Condition, Conclusion};
pub use validator::{OntologyValidator, ValidationError};
pub use loader::OntologyLoader;
