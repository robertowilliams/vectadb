// Qdrant client for vector similarity search

use anyhow::{Context, Result};
use qdrant_client::prelude::*;
use qdrant_client::qdrant::{
    vectors_config::Config, CreateCollection, Distance, PointStruct, SearchPoints,
    VectorParams, VectorsConfig,
};
use std::collections::HashMap;
use tracing::{debug, info, warn};

use crate::config::QdrantConfig;
use super::types::{Entity, ScoredEntity};

/// Qdrant client wrapper for vector operations
pub struct QdrantClient {
    client: qdrant_client::client::QdrantClient,
    collection_prefix: String,
}

impl QdrantClient {
    /// Create a new Qdrant client and connect
    pub async fn new(config: &QdrantConfig) -> Result<Self> {
        info!("Connecting to Qdrant at {}", config.url);

        let mut client_config = QdrantClientConfig::from_url(&config.url);

        // Add API key if provided
        if let Some(api_key) = &config.api_key {
            client_config.set_api_key(api_key);
        }

        let client = qdrant_client::client::QdrantClient::new(Some(client_config))
            .context("Failed to create Qdrant client")?;

        info!("Connected to Qdrant");

        Ok(Self {
            client,
            collection_prefix: config.collection_prefix.clone(),
        })
    }

    /// Get collection name for an entity type
    fn collection_name(&self, entity_type: &str) -> String {
        format!("{}{}", self.collection_prefix, entity_type)
    }

    /// Check if Qdrant is healthy
    pub async fn health_check(&self) -> Result<bool> {
        match self.client.health_check().await {
            Ok(_) => Ok(true),
            Err(e) => {
                warn!("Qdrant health check failed: {}", e);
                Ok(false)
            }
        }
    }

    // ============================================================================
    // Collection Management
    // ============================================================================

    /// Create a collection for an entity type
    pub async fn create_collection(
        &self,
        entity_type: &str,
        vector_size: u64,
    ) -> Result<()> {
        let collection_name = self.collection_name(entity_type);
        debug!("Creating Qdrant collection: {}", collection_name);

        // Check if collection already exists
        match self.client.collection_exists(&collection_name).await {
            Ok(true) => {
                debug!("Collection {} already exists", collection_name);
                return Ok(());
            }
            Ok(false) => {}
            Err(e) => {
                warn!("Failed to check if collection exists: {}", e);
            }
        }

        // Create collection with cosine distance
        let create_collection = CreateCollection {
            collection_name: collection_name.clone(),
            vectors_config: Some(VectorsConfig {
                config: Some(Config::Params(VectorParams {
                    size: vector_size,
                    distance: Distance::Cosine.into(),
                    ..Default::default()
                })),
            }),
            ..Default::default()
        };

        self.client
            .create_collection(&create_collection)
            .await
            .context(format!("Failed to create collection {}", collection_name))?;

        info!("Created Qdrant collection: {}", collection_name);
        Ok(())
    }

    /// Delete a collection
    pub async fn delete_collection(&self, entity_type: &str) -> Result<()> {
        let collection_name = self.collection_name(entity_type);
        debug!("Deleting Qdrant collection: {}", collection_name);

        self.client
            .delete_collection(&collection_name)
            .await
            .context(format!("Failed to delete collection {}", collection_name))?;

        info!("Deleted Qdrant collection: {}", collection_name);
        Ok(())
    }

    /// Check if a collection exists
    pub async fn collection_exists(&self, entity_type: &str) -> Result<bool> {
        let collection_name = self.collection_name(entity_type);
        self.client
            .collection_exists(&collection_name)
            .await
            .context("Failed to check collection existence")
    }

    // ============================================================================
    // Vector Operations
    // ============================================================================

    /// Upsert an embedding for an entity
    pub async fn upsert_embedding(
        &self,
        entity_type: &str,
        entity_id: &str,
        embedding: Vec<f32>,
    ) -> Result<()> {
        let collection_name = self.collection_name(entity_type);
        debug!("Upserting embedding for entity {} in {}", entity_id, collection_name);

        // Ensure collection exists
        if !self.collection_exists(entity_type).await? {
            return Err(anyhow::anyhow!(
                "Collection {} does not exist. Create it first.",
                collection_name
            ));
        }

        // Create point with entity ID and embedding
        use qdrant_client::qdrant::Value as QdrantValue;
        use std::collections::HashMap;

        let mut payload_map: HashMap<String, QdrantValue> = HashMap::new();
        payload_map.insert("entity_id".to_string(), entity_id.to_string().into());

        let payload: qdrant_client::Payload = payload_map.into();

        let point = PointStruct::new(
            entity_id.to_string(),
            embedding,
            payload,
        );

        self.client
            .upsert_points(&collection_name, None, vec![point], None)
            .await
            .context("Failed to upsert embedding")?;

        debug!("Upserted embedding for entity {}", entity_id);
        Ok(())
    }

    /// Delete an embedding
    pub async fn delete_embedding(&self, entity_type: &str, entity_id: &str) -> Result<()> {
        let collection_name = self.collection_name(entity_type);
        debug!("Deleting embedding for entity {} from {}", entity_id, collection_name);

        use qdrant_client::qdrant::{PointsSelector, PointsIdsList};

        let points_selector = PointsSelector {
            points_selector_one_of: Some(
                qdrant_client::qdrant::points_selector::PointsSelectorOneOf::Points(
                    PointsIdsList {
                        ids: vec![entity_id.to_string().into()],
                    },
                ),
            ),
        };

        self.client
            .delete_points(&collection_name, None, &points_selector, None)
            .await
            .context("Failed to delete embedding")?;

        debug!("Deleted embedding for entity {}", entity_id);
        Ok(())
    }

    // ============================================================================
    // Search Operations
    // ============================================================================

    /// Search for similar entities using vector similarity
    pub async fn search_similar(
        &self,
        entity_type: &str,
        query_vector: Vec<f32>,
        limit: usize,
    ) -> Result<Vec<String>> {
        let collection_name = self.collection_name(entity_type);
        debug!("Searching for similar entities in {} (limit: {})", collection_name, limit);

        // Ensure collection exists
        if !self.collection_exists(entity_type).await? {
            debug!("Collection {} does not exist, returning empty results", collection_name);
            return Ok(vec![]);
        }

        let search_points = SearchPoints {
            collection_name: collection_name.clone(),
            vector: query_vector,
            limit: limit as u64,
            with_payload: Some(true.into()),
            ..Default::default()
        };

        let search_result = self
            .client
            .search_points(&search_points)
            .await
            .context("Failed to search vectors")?;

        let entity_ids: Vec<String> = search_result
            .result
            .into_iter()
            .filter_map(|point| {
                // Extract entity_id from point ID
                point.id.map(|id| match id.point_id_options {
                    Some(qdrant_client::qdrant::point_id::PointIdOptions::Uuid(uuid)) => uuid,
                    Some(qdrant_client::qdrant::point_id::PointIdOptions::Num(num)) => {
                        num.to_string()
                    }
                    None => String::new(),
                })
            })
            .filter(|id| !id.is_empty())
            .collect();

        debug!("Found {} similar entities", entity_ids.len());
        Ok(entity_ids)
    }

    /// Search for similar entities with scores
    pub async fn search_similar_with_scores(
        &self,
        entity_type: &str,
        query_vector: Vec<f32>,
        limit: usize,
    ) -> Result<Vec<(String, f32)>> {
        let collection_name = self.collection_name(entity_type);
        debug!("Searching for similar entities with scores in {}", collection_name);

        // Ensure collection exists
        if !self.collection_exists(entity_type).await? {
            debug!("Collection {} does not exist, returning empty results", collection_name);
            return Ok(vec![]);
        }

        let search_points = SearchPoints {
            collection_name: collection_name.clone(),
            vector: query_vector,
            limit: limit as u64,
            with_payload: Some(true.into()),
            ..Default::default()
        };

        let search_result = self
            .client
            .search_points(&search_points)
            .await
            .context("Failed to search vectors")?;

        let results: Vec<(String, f32)> = search_result
            .result
            .into_iter()
            .filter_map(|point| {
                let entity_id = point.id.and_then(|id| match id.point_id_options {
                    Some(qdrant_client::qdrant::point_id::PointIdOptions::Uuid(uuid)) => {
                        Some(uuid)
                    }
                    Some(qdrant_client::qdrant::point_id::PointIdOptions::Num(num)) => {
                        Some(num.to_string())
                    }
                    None => None,
                })?;

                Some((entity_id, point.score))
            })
            .collect();

        debug!("Found {} similar entities with scores", results.len());
        Ok(results)
    }

    /// Search across multiple entity types (for ontology-expanded queries)
    pub async fn search_similar_multi_type(
        &self,
        entity_types: &[String],
        query_vector: Vec<f32>,
        limit: usize,
    ) -> Result<HashMap<String, Vec<String>>> {
        debug!("Searching across {} entity types", entity_types.len());

        let mut results = HashMap::new();

        for entity_type in entity_types {
            match self.search_similar(entity_type, query_vector.clone(), limit).await {
                Ok(ids) => {
                    results.insert(entity_type.clone(), ids);
                }
                Err(e) => {
                    warn!("Failed to search in collection {}: {}", entity_type, e);
                    results.insert(entity_type.clone(), vec![]);
                }
            }
        }

        debug!("Multi-type search completed");
        Ok(results)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> QdrantConfig {
        QdrantConfig {
            url: "http://localhost:6333".to_string(),
            api_key: None,
            collection_prefix: "test_".to_string(),
        }
    }

    #[tokio::test]
    #[ignore] // Requires Qdrant running
    async fn test_connection() {
        let config = test_config();
        let client = QdrantClient::new(&config).await;
        assert!(client.is_ok());
    }

    #[tokio::test]
    #[ignore] // Requires Qdrant running
    async fn test_health_check() {
        let config = test_config();
        let client = QdrantClient::new(&config).await.unwrap();
        let healthy = client.health_check().await.unwrap();
        assert!(healthy);
    }

    #[tokio::test]
    #[ignore] // Requires Qdrant running
    async fn test_create_collection() {
        let config = test_config();
        let client = QdrantClient::new(&config).await.unwrap();

        // Create collection
        let result = client.create_collection("TestEntity", 384).await;
        assert!(result.is_ok());

        // Verify it exists
        let exists = client.collection_exists("TestEntity").await.unwrap();
        assert!(exists);

        // Cleanup
        let _ = client.delete_collection("TestEntity").await;
    }
}
