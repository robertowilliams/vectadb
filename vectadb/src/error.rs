use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use thiserror::Error;

/// VectaDB Result type
pub type Result<T> = std::result::Result<T, VectaDBError>;

/// Main error type for VectaDB
#[derive(Error, Debug)]
pub enum VectaDBError {
    #[error("SurrealDB error: {0}")]
    SurrealDB(String),

    #[error("Qdrant error: {0}")]
    Qdrant(String),

    #[error("Embedding error: {0}")]
    Embedding(String),

    #[error("Configuration error: {0}")]
    Config(String),

    #[error("Not found: {0}")]
    NotFound(String),

    #[error("Invalid input: {0}")]
    InvalidInput(String),

    #[error("Authentication failed: {0}")]
    Unauthorized(String),

    #[error("Internal server error: {0}")]
    Internal(String),

    #[error("Serialization error: {0}")]
    Serialization(String),
}

impl IntoResponse for VectaDBError {
    fn into_response(self) -> Response {
        let (status, error_message) = match self {
            VectaDBError::NotFound(msg) => (StatusCode::NOT_FOUND, msg),
            VectaDBError::InvalidInput(msg) => (StatusCode::BAD_REQUEST, msg),
            VectaDBError::Unauthorized(msg) => (StatusCode::UNAUTHORIZED, msg),
            VectaDBError::SurrealDB(msg) => (StatusCode::INTERNAL_SERVER_ERROR, format!("Database error: {}", msg)),
            VectaDBError::Qdrant(msg) => (StatusCode::INTERNAL_SERVER_ERROR, format!("Vector DB error: {}", msg)),
            VectaDBError::Embedding(msg) => (StatusCode::INTERNAL_SERVER_ERROR, format!("Embedding error: {}", msg)),
            VectaDBError::Config(msg) => (StatusCode::INTERNAL_SERVER_ERROR, format!("Config error: {}", msg)),
            VectaDBError::Internal(msg) => (StatusCode::INTERNAL_SERVER_ERROR, msg),
            VectaDBError::Serialization(msg) => (StatusCode::INTERNAL_SERVER_ERROR, format!("Serialization error: {}", msg)),
        };

        let body = Json(json!({
            "error": error_message,
        }));

        (status, body).into_response()
    }
}

// Conversion from common error types
impl From<surrealdb::Error> for VectaDBError {
    fn from(err: surrealdb::Error) -> Self {
        VectaDBError::SurrealDB(err.to_string())
    }
}

impl From<serde_json::Error> for VectaDBError {
    fn from(err: serde_json::Error) -> Self {
        VectaDBError::Serialization(err.to_string())
    }
}

impl From<anyhow::Error> for VectaDBError {
    fn from(err: anyhow::Error) -> Self {
        VectaDBError::Internal(err.to_string())
    }
}

impl From<std::io::Error> for VectaDBError {
    fn from(err: std::io::Error) -> Self {
        VectaDBError::Internal(err.to_string())
    }
}
