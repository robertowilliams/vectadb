// API routes configuration

use axum::{
    routing::{delete, get, post, put},
    Router,
};
use tower_http::cors::CorsLayer;

use super::handlers::{self, AppState};

/// Create the main API router (without database dependencies)
pub fn create_router() -> Router {
    let state = AppState::new();
    create_router_with_state(state)
}

/// Create API router with custom state (for database integration)
pub fn create_router_with_state(state: AppState) -> Router {
    Router::new()
        // Health check
        .route("/health", get(handlers::health_check))

        // Ontology management
        .route("/api/v1/ontology/schema", post(handlers::upload_schema))
        .route("/api/v1/ontology/schema", get(handlers::get_schema))
        .route("/api/v1/ontology/types/:type_id", get(handlers::get_entity_type))
        .route("/api/v1/ontology/types/:type_id/subtypes", get(handlers::get_subtypes))

        // Entity validation
        .route("/api/v1/validate/entity", post(handlers::validate_entity))
        .route("/api/v1/validate/relation", post(handlers::validate_relation))

        // Query expansion
        .route("/api/v1/query/expand", post(handlers::expand_query))
        .route("/api/v1/query/compatible_relations", post(handlers::get_compatible_relations))

        // Entity CRUD
        .route("/api/v1/entities", post(handlers::create_entity))
        .route("/api/v1/entities/:id", get(handlers::get_entity))
        .route("/api/v1/entities/:id", put(handlers::update_entity))
        .route("/api/v1/entities/:id", delete(handlers::delete_entity))

        // Relation CRUD
        .route("/api/v1/relations", post(handlers::create_relation))
        .route("/api/v1/relations/:id", get(handlers::get_relation))
        .route("/api/v1/relations/:id", delete(handlers::delete_relation))

        // Hybrid queries
        .route("/api/v1/query/hybrid", post(handlers::hybrid_query))

        // Add CORS middleware
        .layer(CorsLayer::permissive())

        // Add state
        .with_state(state)
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::{Request, StatusCode};
    use tower::ServiceExt;

    #[tokio::test]
    async fn test_health_check() {
        let app = create_router();

        let response = app
            .oneshot(Request::builder().uri("/health").body(Body::empty()).unwrap())
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn test_get_schema_not_loaded() {
        let app = create_router();

        let response = app
            .oneshot(
                Request::builder()
                    .uri("/api/v1/ontology/schema")
                    .body(Body::empty())
                    .unwrap(),
            )
            .await
            .unwrap();

        assert_eq!(response.status(), StatusCode::NOT_FOUND);
    }
}
