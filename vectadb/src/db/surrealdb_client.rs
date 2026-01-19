// SurrealDB client for graph and entity storage

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use surrealdb::engine::remote::http::{Client, Http};
use surrealdb::opt::auth::Root;
use surrealdb::sql::Datetime;
use surrealdb::Surreal;
use std::sync::Arc;
use tracing::{debug, info, warn};

use crate::config::DatabaseConfig;
use crate::ontology::OntologySchema;
use super::types::{Entity, Relation};

/// SurrealDB client wrapper
pub struct SurrealDBClient {
    db: Arc<Surreal<Client>>,
    namespace: String,
    database: String,
}

/// Stored ontology schema record
#[derive(Debug, Clone, Serialize, Deserialize)]
struct OntologyRecord {
    namespace: String,
    version: String,
    schema_json: String,
    created_at: Datetime,
}

impl SurrealDBClient {
    /// Get reference to the underlying Surreal database connection
    pub fn db(&self) -> &Surreal<Client> {
        &self.db
    }

    /// Create a new SurrealDB client and connect
    pub async fn new(config: &DatabaseConfig) -> Result<Self> {
        info!("Connecting to SurrealDB at {}", config.surrealdb.endpoint);
        debug!("Connection details - namespace: {}, database: {}",
               config.surrealdb.namespace, config.surrealdb.database);

        // Connect to SurrealDB
        debug!("Step 1: Establishing HTTP connection...");
        let db = match Surreal::new::<Http>(&config.surrealdb.endpoint).await {
            Ok(client) => {
                debug!("Step 1: HTTP connection established successfully");
                client
            }
            Err(e) => {
                warn!("Step 1 failed with error: {:?}", e);
                return Err(anyhow::anyhow!("Failed to establish HTTP connection to SurrealDB: {}", e));
            }
        };

        // Authenticate
        debug!("Step 2: Authenticating as root user...");
        db.signin(Root {
            username: &config.surrealdb.username,
            password: &config.surrealdb.password,
        })
        .await
        .context("Failed to authenticate with SurrealDB")?;
        debug!("Step 2: Authentication successful");

        // Use namespace and database
        debug!("Step 3: Selecting namespace '{}' and database '{}'...",
               config.surrealdb.namespace, config.surrealdb.database);
        db.use_ns(&config.surrealdb.namespace)
            .use_db(&config.surrealdb.database)
            .await
            .context("Failed to select namespace/database")?;
        debug!("Step 3: Namespace and database selected successfully");

        info!(
            "Connected to SurrealDB: {}/{}",
            config.surrealdb.namespace, config.surrealdb.database
        );

        let client = Self {
            db: Arc::new(db),
            namespace: config.surrealdb.namespace.clone(),
            database: config.surrealdb.database.clone(),
        };

        // Initialize schema
        client.initialize_schema().await?;

        Ok(client)
    }

    /// Initialize database schema
    async fn initialize_schema(&self) -> Result<()> {
        debug!("Initializing SurrealDB schema");

        // Define ontology_schema table
        self.db
            .query(
                "DEFINE TABLE IF NOT EXISTS ontology_schema SCHEMAFULL;
                 DEFINE FIELD IF NOT EXISTS namespace ON ontology_schema TYPE string;
                 DEFINE FIELD IF NOT EXISTS version ON ontology_schema TYPE string;
                 DEFINE FIELD IF NOT EXISTS schema_json ON ontology_schema TYPE string;
                 DEFINE FIELD IF NOT EXISTS created_at ON ontology_schema TYPE datetime;
                 DEFINE INDEX IF NOT EXISTS idx_namespace ON ontology_schema COLUMNS namespace UNIQUE;",
            )
            .await
            .context("Failed to define ontology_schema table")?;

        // Define entity table
        self.db
            .query(
                "DEFINE TABLE IF NOT EXISTS entity SCHEMAFULL;
                 DEFINE FIELD IF NOT EXISTS entity_type ON entity TYPE string;
                 DEFINE FIELD IF NOT EXISTS properties ON entity FLEXIBLE TYPE object;
                 DEFINE FIELD IF NOT EXISTS embedding ON entity TYPE option<array>;
                 DEFINE FIELD IF NOT EXISTS metadata ON entity FLEXIBLE TYPE option<object>;
                 DEFINE FIELD IF NOT EXISTS created_at ON entity TYPE datetime DEFAULT time::now();
                 DEFINE FIELD IF NOT EXISTS updated_at ON entity TYPE datetime DEFAULT time::now();
                 DEFINE INDEX IF NOT EXISTS idx_type ON entity COLUMNS entity_type;",
            )
            .await
            .context("Failed to define entity table")?;

        // Define relation table
        self.db
            .query(
                "DEFINE TABLE IF NOT EXISTS relation SCHEMAFULL;
                 DEFINE FIELD IF NOT EXISTS relation_type ON relation TYPE string;
                 DEFINE FIELD IF NOT EXISTS source_id ON relation TYPE string;
                 DEFINE FIELD IF NOT EXISTS target_id ON relation TYPE string;
                 DEFINE FIELD IF NOT EXISTS properties ON relation FLEXIBLE TYPE object;
                 DEFINE FIELD IF NOT EXISTS created_at ON relation TYPE datetime DEFAULT time::now();
                 DEFINE INDEX IF NOT EXISTS idx_relation_type ON relation COLUMNS relation_type;
                 DEFINE INDEX IF NOT EXISTS idx_source ON relation COLUMNS source_id;
                 DEFINE INDEX IF NOT EXISTS idx_target ON relation COLUMNS target_id;",
            )
            .await
            .context("Failed to define relation table")?;

        // Phase 5: Define agent_trace table
        self.db
            .query(
                "DEFINE TABLE IF NOT EXISTS agent_trace SCHEMAFULL;
                 DEFINE FIELD IF NOT EXISTS id ON agent_trace TYPE string;
                 DEFINE FIELD IF NOT EXISTS session_id ON agent_trace TYPE string;
                 DEFINE FIELD IF NOT EXISTS agent_id ON agent_trace TYPE option<string>;
                 DEFINE FIELD IF NOT EXISTS status ON agent_trace TYPE string;
                 DEFINE FIELD IF NOT EXISTS start_time ON agent_trace TYPE string;
                 DEFINE FIELD IF NOT EXISTS created_at ON agent_trace TYPE string;
                 DEFINE FIELD IF NOT EXISTS updated_at ON agent_trace TYPE string;
                 DEFINE INDEX IF NOT EXISTS idx_session_id ON agent_trace COLUMNS session_id;
                 DEFINE INDEX IF NOT EXISTS idx_agent_id ON agent_trace COLUMNS agent_id;
                 DEFINE INDEX IF NOT EXISTS idx_start_time ON agent_trace COLUMNS start_time;",
            )
            .await
            .context("Failed to define agent_trace table")?;

        // Phase 5: Define agent_event table
        self.db
            .query(
                "DEFINE TABLE IF NOT EXISTS agent_event SCHEMAFULL;
                 DEFINE FIELD IF NOT EXISTS id ON agent_event TYPE string;
                 DEFINE FIELD IF NOT EXISTS trace_id ON agent_event TYPE string;
                 DEFINE FIELD IF NOT EXISTS timestamp ON agent_event TYPE string;
                 DEFINE FIELD IF NOT EXISTS event_type ON agent_event TYPE option<string>;
                 DEFINE FIELD IF NOT EXISTS agent_id ON agent_event TYPE option<string>;
                 DEFINE FIELD IF NOT EXISTS session_id ON agent_event TYPE option<string>;
                 DEFINE FIELD IF NOT EXISTS properties ON agent_event TYPE object;
                 DEFINE FIELD IF NOT EXISTS source ON agent_event TYPE option<object>;
                 DEFINE FIELD IF NOT EXISTS created_at ON agent_event TYPE string;
                 DEFINE FIELD IF NOT EXISTS updated_at ON agent_event TYPE string;
                 DEFINE INDEX IF NOT EXISTS idx_trace_id ON agent_event COLUMNS trace_id;
                 DEFINE INDEX IF NOT EXISTS idx_timestamp ON agent_event COLUMNS timestamp;
                 DEFINE INDEX IF NOT EXISTS idx_event_type ON agent_event COLUMNS event_type;",
            )
            .await
            .context("Failed to define agent_event table")?;

        debug!("SurrealDB schema initialized (including Phase 5 tables)");
        Ok(())
    }

    /// Check if SurrealDB is healthy
    pub async fn health_check(&self) -> Result<bool> {
        match self.db.health().await {
            Ok(_) => Ok(true),
            Err(e) => {
                warn!("SurrealDB health check failed: {}", e);
                Ok(false)
            }
        }
    }

    // ============================================================================
    // Ontology Schema Operations
    // ============================================================================

    /// Store ontology schema
    pub async fn store_schema(&self, schema: &OntologySchema) -> Result<()> {
        debug!("Storing ontology schema: {}", schema.namespace);

        let schema_json = serde_json::to_string(schema)
            .context("Failed to serialize ontology schema")?;

        let record = OntologyRecord {
            namespace: schema.namespace.clone(),
            version: schema.version.clone(),
            schema_json,
            created_at: Datetime::default(),
        };

        // Use upsert to handle dotted namespaces and updates
        match self.db
            .upsert::<Option<OntologyRecord>>(("ontology_schema", schema.namespace.clone()))
            .content(record)
            .await
        {
            Ok(_) => {
                info!("Stored ontology schema: {}", schema.namespace);
                Ok(())
            }
            Err(e) => {
                warn!("Failed to upsert ontology schema: {:?}", e);
                Err(anyhow::anyhow!("Failed to store ontology schema: {:?}", e))
            }
        }
    }

    /// Get the current ontology schema
    pub async fn get_schema(&self) -> Result<Option<OntologySchema>> {
        debug!("Retrieving ontology schema");

        // Get the most recent schema
        let mut result = self
            .db
            .query("SELECT * FROM ontology_schema ORDER BY created_at DESC LIMIT 1")
            .await
            .context("Failed to query ontology schema")?;

        let records: Vec<OntologyRecord> = result.take(0)?;

        if let Some(record) = records.first() {
            let schema: OntologySchema = serde_json::from_str(&record.schema_json)
                .context("Failed to deserialize ontology schema")?;
            Ok(Some(schema))
        } else {
            Ok(None)
        }
    }

    // ============================================================================
    // Entity Operations
    // ============================================================================

    /// Create a new entity
    pub async fn create_entity(&self, entity: &Entity) -> Result<String> {
        debug!("Creating entity of type: {}", entity.entity_type);

        // Create record using SurrealDB query to avoid datetime serialization issues
        let record_id_string = entity.id_string();

        // Use SurrealDB query with bind parameters and explicit datetime values
        let query = format!(
            "CREATE entity:⟨{}⟩ SET entity_type = $entity_type, properties = $properties, embedding = $embedding, metadata = $metadata, created_at = time::now(), updated_at = time::now()",
            record_id_string
        );

        match self
            .db
            .query(query)
            .bind(("entity_type", entity.entity_type.clone()))
            .bind(("properties", serde_json::to_value(&entity.properties)?))
            .bind(("embedding", entity.embedding.clone()))
            .bind(("metadata", serde_json::to_value(&entity.metadata)?))
            .await
        {
            Ok(_) => {
                debug!("Created entity: {}", record_id_string);
                Ok(record_id_string)
            }
            Err(e) => {
                warn!("Failed to insert entity of type {}: {:?}", entity.entity_type, e);
                Err(anyhow::anyhow!("Failed to insert entity: {:?}", e))
            }
        }
    }

    /// Get an entity by ID
    pub async fn get_entity(&self, id: &str) -> Result<Option<Entity>> {
        debug!("Getting entity: {}", id);

        let entity: Option<Entity> = self
            .db
            .select(("entity", id))
            .await
            .context("Failed to get entity")?;

        Ok(entity)
    }

    /// Update an entity
    pub async fn update_entity(&self, id: &str, entity: &Entity) -> Result<()> {
        debug!("Updating entity: {}", id);

        let entity_clone = entity.clone();
        let _: Option<Entity> = self
            .db
            .update(("entity", id))
            .content(entity_clone)
            .await
            .context("Failed to update entity")?;

        debug!("Updated entity: {}", id);
        Ok(())
    }

    /// Delete an entity
    pub async fn delete_entity(&self, id: &str) -> Result<()> {
        debug!("Deleting entity: {}", id);

        let _: Option<Entity> = self
            .db
            .delete(("entity", id))
            .await
            .context("Failed to delete entity")?;

        debug!("Deleted entity: {}", id);
        Ok(())
    }

    /// Query entities by type
    pub async fn query_entities(&self, entity_type: &str) -> Result<Vec<Entity>> {
        debug!("Querying entities of type: {}", entity_type);

        let entity_type_owned = entity_type.to_string();
        let mut result = self
            .db
            .query("SELECT * FROM entity WHERE entity_type = $type")
            .bind(("type", entity_type_owned))
            .await
            .context("Failed to query entities")?;

        let entities: Vec<Entity> = result.take(0)?;

        debug!("Found {} entities of type {}", entities.len(), entity_type);
        Ok(entities)
    }

    /// Query entities by type (including subtypes)
    pub async fn query_entities_expanded(&self, entity_types: &[String]) -> Result<Vec<Entity>> {
        debug!("Querying entities of types: {:?}", entity_types);

        let types_owned = entity_types.to_vec();
        let mut result = self
            .db
            .query("SELECT * FROM entity WHERE entity_type IN $types")
            .bind(("types", types_owned))
            .await
            .context("Failed to query entities")?;

        let entities: Vec<Entity> = result.take(0)?;

        debug!("Found {} entities", entities.len());
        Ok(entities)
    }

    // ============================================================================
    // Relation Operations
    // ============================================================================

    /// Create a new relation
    pub async fn create_relation(&self, relation: &Relation) -> Result<String> {
        debug!(
            "Creating relation: {} -> {} -> {}",
            relation.source_id, relation.relation_type, relation.target_id
        );

        // Create record using SurrealDB query to avoid datetime serialization issues
        let record_id_string = relation.id_string();

        // Use SurrealDB query with bind parameters and explicit datetime
        let query = format!(
            "CREATE relation:⟨{}⟩ SET relation_type = $relation_type, source_id = $source_id, target_id = $target_id, properties = $properties, created_at = time::now()",
            record_id_string
        );

        match self
            .db
            .query(query)
            .bind(("relation_type", relation.relation_type.clone()))
            .bind(("source_id", relation.source_id.clone()))
            .bind(("target_id", relation.target_id.clone()))
            .bind(("properties", serde_json::to_value(&relation.properties)?))
            .await
        {
            Ok(_) => {
                debug!("Created relation: {}", record_id_string);
                Ok(record_id_string)
            }
            Err(e) => {
                warn!("Failed to insert relation {}: {:?}", relation.relation_type, e);
                Err(anyhow::anyhow!("Failed to insert relation: {:?}", e))
            }
        }
    }

    /// Get a relation by ID
    pub async fn get_relation(&self, id: &str) -> Result<Option<Relation>> {
        debug!("Getting relation: {}", id);

        let relation: Option<Relation> = self
            .db
            .select(("relation", id))
            .await
            .context("Failed to get relation")?;

        Ok(relation)
    }

    /// Delete a relation
    pub async fn delete_relation(&self, id: &str) -> Result<()> {
        debug!("Deleting relation: {}", id);

        let _: Option<Relation> = self
            .db
            .delete(("relation", id))
            .await
            .context("Failed to delete relation")?;

        debug!("Deleted relation: {}", id);
        Ok(())
    }

    /// Get outgoing relations from an entity
    pub async fn get_outgoing_relations(
        &self,
        entity_id: &str,
        relation_type: Option<&str>,
    ) -> Result<Vec<Relation>> {
        debug!("Getting outgoing relations from: {}", entity_id);

        let entity_id_owned = entity_id.to_string();

        let mut result = if let Some(rel_type) = relation_type {
            let rel_type_owned = rel_type.to_string();
            self.db
                .query("SELECT * FROM relation WHERE source_id = $entity_id AND relation_type = $rel_type")
                .bind(("entity_id", entity_id_owned))
                .bind(("rel_type", rel_type_owned))
                .await
        } else {
            self.db
                .query("SELECT * FROM relation WHERE source_id = $entity_id")
                .bind(("entity_id", entity_id_owned))
                .await
        }
        .context("Failed to query outgoing relations")?;

        let relations: Vec<Relation> = result.take(0)?;

        debug!("Found {} outgoing relations", relations.len());
        Ok(relations)
    }

    /// Get incoming relations to an entity
    pub async fn get_incoming_relations(
        &self,
        entity_id: &str,
        relation_type: Option<&str>,
    ) -> Result<Vec<Relation>> {
        debug!("Getting incoming relations to: {}", entity_id);

        let entity_id_owned = entity_id.to_string();

        let mut result = if let Some(rel_type) = relation_type {
            let rel_type_owned = rel_type.to_string();
            self.db
                .query("SELECT * FROM relation WHERE target_id = $entity_id AND relation_type = $rel_type")
                .bind(("entity_id", entity_id_owned))
                .bind(("rel_type", rel_type_owned))
                .await
        } else {
            self.db
                .query("SELECT * FROM relation WHERE target_id = $entity_id")
                .bind(("entity_id", entity_id_owned))
                .await
        }
        .context("Failed to query incoming relations")?;

        let relations: Vec<Relation> = result.take(0)?;

        debug!("Found {} incoming relations", relations.len());
        Ok(relations)
    }

    // ============================================================================
    // Graph Traversal
    // ============================================================================

    /// Traverse the graph from a starting entity
    pub async fn traverse_graph(
        &self,
        start_id: &str,
        relation_type: &str,
        depth: usize,
    ) -> Result<Vec<Entity>> {
        debug!(
            "Traversing graph from {} with relation {} to depth {}",
            start_id, relation_type, depth
        );

        if depth == 0 {
            return Ok(vec![]);
        }

        let mut visited = std::collections::HashSet::new();
        let mut result = Vec::new();
        let mut current_level = vec![start_id.to_string()];

        for _ in 0..depth {
            let mut next_level = Vec::new();

            for entity_id in current_level {
                if visited.contains(&entity_id) {
                    continue;
                }
                visited.insert(entity_id.clone());

                // Get outgoing relations
                let relations = self
                    .get_outgoing_relations(&entity_id, Some(relation_type))
                    .await?;

                for relation in relations {
                    // Get target entity
                    if let Some(target) = self.get_entity(&relation.target_id).await? {
                        result.push(target.clone());
                        next_level.push(target.id_string());
                    }
                }
            }

            current_level = next_level;

            if current_level.is_empty() {
                break;
            }
        }

        debug!("Graph traversal found {} entities", result.len());
        Ok(result)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::SurrealDBConfig;

    fn test_config() -> DatabaseConfig {
        DatabaseConfig {
            surrealdb: SurrealDBConfig {
                endpoint: "ws://localhost:8000".to_string(),
                namespace: "test".to_string(),
                database: "test".to_string(),
                username: "root".to_string(),
                password: "root".to_string(),
            },
            qdrant: crate::config::QdrantConfig {
                url: "http://localhost:6333".to_string(),
                api_key: None,
                collection_prefix: "test_".to_string(),
            },
        }
    }

    #[tokio::test]
    #[ignore] // Requires SurrealDB running
    async fn test_connection() {
        let config = test_config();
        let client = SurrealDBClient::new(&config).await;
        assert!(client.is_ok());
    }

    #[tokio::test]
    #[ignore] // Requires SurrealDB running
    async fn test_health_check() {
        let config = test_config();
        let client = SurrealDBClient::new(&config).await.unwrap();
        let healthy = client.health_check().await.unwrap();
        assert!(healthy);
    }
}
