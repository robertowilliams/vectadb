use crate::error::{Result, VectaDBError};
use serde::Deserialize;
use std::env;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub server: ServerConfig,
    pub database: DatabaseConfig,
    pub embedding: EmbeddingConfig,
    pub api: ApiConfig,
    pub similarity: SimilarityConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DatabaseConfig {
    pub surrealdb: SurrealDBConfig,
    pub qdrant: QdrantConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SurrealDBConfig {
    pub endpoint: String,
    pub namespace: String,
    pub database: String,
    pub username: String,
    pub password: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct QdrantConfig {
    pub url: String,
    pub api_key: Option<String>,
    pub collection_prefix: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EmbeddingConfig {
    pub model: String,
    pub dim: usize,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ApiConfig {
    pub key: String,
    pub jwt_secret: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SimilarityConfig {
    pub threshold: f32,
    pub limit: usize,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        dotenvy::dotenv().ok();

        Ok(Config {
            server: ServerConfig {
                host: env::var("SERVER_HOST").unwrap_or_else(|_| "0.0.0.0".to_string()),
                port: env::var("SERVER_PORT")
                    .unwrap_or_else(|_| "8080".to_string())
                    .parse()
                    .map_err(|e| VectaDBError::Config(format!("Invalid SERVER_PORT: {}", e)))?,
            },
            database: DatabaseConfig {
                surrealdb: SurrealDBConfig {
                    endpoint: env::var("SURREAL_ENDPOINT")
                        .unwrap_or_else(|_| "localhost:8000".to_string()),
                    namespace: env::var("SURREAL_NAMESPACE")
                        .unwrap_or_else(|_| "vectadb".to_string()),
                    database: env::var("SURREAL_DATABASE")
                        .unwrap_or_else(|_| "main".to_string()),
                    username: env::var("SURREAL_USER")
                        .unwrap_or_else(|_| "root".to_string()),
                    password: env::var("SURREAL_PASS")
                        .unwrap_or_else(|_| "root".to_string()),
                },
                qdrant: QdrantConfig {
                    url: env::var("QDRANT_URL")
                        .unwrap_or_else(|_| "http://localhost:6333".to_string()),
                    api_key: env::var("QDRANT_API_KEY").ok(),
                    collection_prefix: env::var("QDRANT_COLLECTION_PREFIX")
                        .unwrap_or_else(|_| "vectadb_".to_string()),
                },
            },
            embedding: EmbeddingConfig {
                model: env::var("EMBEDDING_MODEL")
                    .unwrap_or_else(|_| "sentence-transformers/all-MiniLM-L6-v2".to_string()),
                dim: env::var("EMBEDDING_DIM")
                    .unwrap_or_else(|_| "384".to_string())
                    .parse()
                    .map_err(|e| VectaDBError::Config(format!("Invalid EMBEDDING_DIM: {}", e)))?,
            },
            api: ApiConfig {
                key: env::var("API_KEY")
                    .map_err(|_| VectaDBError::Config("API_KEY not set".to_string()))?,
                jwt_secret: env::var("JWT_SECRET")
                    .unwrap_or_else(|_| "change-me-in-production".to_string()),
            },
            similarity: SimilarityConfig {
                threshold: env::var("SIMILARITY_THRESHOLD")
                    .unwrap_or_else(|_| "0.65".to_string())
                    .parse()
                    .map_err(|e| VectaDBError::Config(format!("Invalid SIMILARITY_THRESHOLD: {}", e)))?,
                limit: env::var("SIMILARITY_LIMIT")
                    .unwrap_or_else(|_| "10".to_string())
                    .parse()
                    .map_err(|e| VectaDBError::Config(format!("Invalid SIMILARITY_LIMIT: {}", e)))?,
            },
        })
    }
}
