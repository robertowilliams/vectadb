// VectaDB - The Observability Database for LLM Agents
// Author: Roberto Williams Batista

mod config;
mod error;
mod models;
mod embeddings;
mod ontology;
mod intelligence;
mod api;

use config::Config;
use error::Result;

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
    tracing::info!("SurrealDB: {}", config.surrealdb.url);
    tracing::info!("Qdrant: {}", config.qdrant.url);

    // TODO: Initialize database connections
    // TODO: Initialize embedding service

    // Create API router
    let app = api::create_router();

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
