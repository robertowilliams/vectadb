// Shared database types

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use surrealdb::sql::{Datetime, Thing};

/// Entity stored in the database
/// Note: id is Thing type for proper SurrealDB deserialization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    pub id: Thing,
    pub entity_type: String,
    pub properties: HashMap<String, serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding: Option<Vec<f32>>,
    pub created_at: Datetime,
    pub updated_at: Datetime,
    #[serde(skip_serializing_if = "HashMap::is_empty")]
    pub metadata: HashMap<String, String>,
}

impl Entity {
    pub fn new(entity_type: String, properties: HashMap<String, serde_json::Value>) -> Self {
        let id_string = nanoid::nanoid!();
        Self {
            id: Thing::from(("entity".to_string(), id_string)),
            entity_type,
            properties,
            embedding: None,
            created_at: Datetime::default(),
            updated_at: Datetime::default(),
            metadata: HashMap::new(),
        }
    }

    /// Get the ID as a string (just the ID part without table name)
    pub fn id_string(&self) -> String {
        self.id.id.to_string()
    }

    pub fn with_embedding(mut self, embedding: Vec<f32>) -> Self {
        self.embedding = Some(embedding);
        self
    }

    pub fn with_metadata(mut self, metadata: HashMap<String, String>) -> Self {
        self.metadata = metadata;
        self
    }
}

/// Relation between entities
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Relation {
    pub id: Thing,
    pub relation_type: String,
    pub source_id: String,
    pub target_id: String,
    pub properties: HashMap<String, serde_json::Value>,
    pub created_at: Datetime,
}

impl Relation {
    pub fn new(
        relation_type: String,
        source_id: String,
        target_id: String,
        properties: HashMap<String, serde_json::Value>,
    ) -> Self {
        let id_string = nanoid::nanoid!();
        Self {
            id: Thing::from(("relation".to_string(), id_string)),
            relation_type,
            source_id,
            target_id,
            properties,
            created_at: Datetime::default(),
        }
    }

    /// Get the ID as a string (just the ID part without table name)
    pub fn id_string(&self) -> String {
        self.id.id.to_string()
    }
}

/// Entity with similarity score (from vector search)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoredEntity {
    pub entity: Entity,
    pub score: f32,
}

/// Graph traversal result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphPath {
    pub entities: Vec<Entity>,
    pub relations: Vec<Relation>,
}
