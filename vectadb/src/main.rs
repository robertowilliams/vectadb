// VectaDB - The Observability Database for LLM Agents
// Author: Roberto Williams Batista

mod config;
mod error;
mod models;
mod embeddings;
mod ontology;
mod intelligence;
mod api;
mod db;
mod query;

use config::Config;
use error::Result;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::warn;

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    // Print ASCII banner
    println!(r#"
 __     __        _        ____  ____
 \ \   / /__  ___| |_ __ _|  _ \| __ )
  \ \ / / _ \/ __| __/ _` | | | |  _ \
   \ V /  __/ (__| || (_| | |_| | |_) |
    \_/ \___|\___|\__\__,_|____/|____/

    The Observability Database for LLM Agents
    Version 0.1.0 | Built with Rust
    Contact: contact@vectadb.com
"#);

    tracing::info!("Starting VectaDB...");

    // Load configuration
    let config = Config::from_env()?;
    tracing::info!("Configuration loaded successfully");
    tracing::info!("Server will listen on {}:{}", config.server.host, config.server.port);
    tracing::info!("SurrealDB: {}", config.database.surrealdb.endpoint);
    tracing::info!("Qdrant: {}", config.database.qdrant.url);

    // Initialize database connections
    tracing::info!("Connecting to SurrealDB...");
    let surreal = match db::SurrealDBClient::new(&config.database).await {
        Ok(client) => {
            tracing::info!("SurrealDB connected successfully");
            Some(Arc::new(client))
        }
        Err(e) => {
            warn!("Failed to connect to SurrealDB: {}. Continuing without database support.", e);
            None
        }
    };

    tracing::info!("Connecting to Qdrant...");
    let qdrant = match db::QdrantClient::new(&config.database.qdrant).await {
        Ok(client) => {
            tracing::info!("Qdrant connected successfully");
            Some(Arc::new(client))
        }
        Err(e) => {
            warn!("Failed to connect to Qdrant: {}. Continuing without vector search.", e);
            None
        }
    };

    // Initialize embedding manager (plugin system or local service)
    tracing::info!("Initializing embedding manager (provider: {})...", config.embedding.provider);
    let embedding_service = match embeddings::EmbeddingManager::new(config.embedding.clone()).await {
        Ok(manager) => {
            tracing::info!("Embedding manager initialized successfully");
            tracing::info!("Using provider: {} (dimension: {})", manager.provider(), manager.dimension());
            Some(Arc::new(manager))
        }
        Err(e) => {
            warn!("Failed to initialize embedding manager: {}. Vector features disabled.", e);
            None
        }
    };

    // Load ontology schema from database if available
    let reasoner = Arc::new(RwLock::new(None));
    if let Some(ref surreal_client) = surreal {
        match surreal_client.get_schema().await {
            Ok(Some(schema)) => {
                tracing::info!("Loaded ontology schema from database");
                let mut reasoner_guard = reasoner.write().await;
                let r = intelligence::OntologyReasoner::new(schema);
                tracing::info!("Ontology reasoner initialized with persisted schema");
                *reasoner_guard = Some(r);
            }
            Ok(None) => {
                tracing::info!("No ontology schema found in database");
            }
            Err(e) => {
                warn!("Failed to load schema from database: {}", e);
            }
        }
    }

    // Create API router with database support
    let app = if surreal.is_some() && qdrant.is_some() && embedding_service.is_some() {
        tracing::info!("Creating API router with full database support");
        let state = api::handlers::AppState::with_databases(
            reasoner.clone(),
            surreal.unwrap(),
            qdrant.unwrap(),
            embedding_service.unwrap(),
        );
        api::routes::create_router_with_state(state)
    } else {
        tracing::info!("Creating API router without database support (ontology-only mode)");
        let mut state = api::handlers::AppState::new();
        state.reasoner = reasoner;
        api::routes::create_router_with_state(state)
    };

    // Start HTTP server
    let addr = format!("{}:{}", config.server.host, config.server.port);
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .map_err(|e| crate::error::VectaDBError::Config(format!("Failed to bind to {}: {}", addr, e)))?;

    tracing::info!("VectaDB API server listening on {}", addr);
    tracing::info!("VectaDB initialized successfully");
    tracing::info!("Press Ctrl+C to shutdown");

    // Run server with graceful shutdown
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await
        .map_err(|e| crate::error::VectaDBError::Config(format!("Server error: {}", e)))?;

    tracing::info!("Shutting down VectaDB...");
    Ok(())
}

async fn shutdown_signal() {
    tokio::signal::ctrl_c()
        .await
        .expect("Failed to install CTRL+C signal handler");
}
