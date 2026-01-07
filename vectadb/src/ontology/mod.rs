// VectaDB Ontology Layer
// Provides ontological semantics for entities and relations

pub mod entity_type;
pub mod relation_type;
pub mod schema;
pub mod validator;
pub mod loader;

pub use schema::OntologySchema;
pub use validator::OntologyValidator;
pub use loader::OntologyLoader;
