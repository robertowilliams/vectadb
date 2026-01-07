// Shared database types

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Entity stored in the database
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    pub id: String,
    pub entity_type: String,
    pub properties: HashMap<String, serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding: Option<Vec<f32>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    #[serde(skip_serializing_if = "HashMap::is_empty")]
    pub metadata: HashMap<String, String>,
}

impl Entity {
    pub fn new(entity_type: String, properties: HashMap<String, serde_json::Value>) -> Self {
        let now = Utc::now();
        Self {
            id: nanoid::nanoid!(),
            entity_type,
            properties,
            embedding: None,
            created_at: now,
            updated_at: now,
            metadata: HashMap::new(),
        }
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
    pub id: String,
    pub relation_type: String,
    pub source_id: String,
    pub target_id: String,
    pub properties: HashMap<String, serde_json::Value>,
    pub created_at: DateTime<Utc>,
}

impl Relation {
    pub fn new(
        relation_type: String,
        source_id: String,
        target_id: String,
        properties: HashMap<String, serde_json::Value>,
    ) -> Self {
        Self {
            id: nanoid::nanoid!(),
            relation_type,
            source_id,
            target_id,
            properties,
            created_at: Utc::now(),
        }
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
