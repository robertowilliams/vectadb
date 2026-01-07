// API handlers for ontology and entity operations

use axum::{
    extract::{Path, State},
    http::StatusCode,
    Json,
};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

use crate::db::{Entity, QdrantClient, Relation, SurrealDBClient};
use crate::embeddings::EmbeddingService;
use crate::intelligence::OntologyReasoner;
use crate::ontology::{OntologyLoader, OntologyValidator};
use crate::query::QueryCoordinator;
use super::types::*;

/// Application state with database clients
#[derive(Clone)]
pub struct AppState {
    pub reasoner: Arc<RwLock<Option<OntologyReasoner>>>,
    pub surreal: Option<Arc<SurrealDBClient>>,
    pub qdrant: Option<Arc<QdrantClient>>,
    pub embedding_service: Option<Arc<EmbeddingService>>,
    pub query_coordinator: Option<Arc<QueryCoordinator>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            reasoner: Arc::new(RwLock::new(None)),
            surreal: None,
            qdrant: None,
            embedding_service: None,
            query_coordinator: None,
        }
    }

    pub fn with_databases(
        reasoner: Arc<RwLock<Option<OntologyReasoner>>>,
        surreal: Arc<SurrealDBClient>,
        qdrant: Arc<QdrantClient>,
        embedding_service: Arc<EmbeddingService>,
    ) -> Self {
        let query_coordinator = Arc::new(QueryCoordinator::new(
            surreal.clone(),
            qdrant.clone(),
            reasoner.clone(),
            embedding_service.clone(),
        ));

        Self {
            reasoner,
            surreal: Some(surreal),
            qdrant: Some(qdrant),
            embedding_service: Some(embedding_service),
            query_coordinator: Some(query_coordinator),
        }
    }
}

// ============================================================================
// Health & Status
// ============================================================================

pub async fn health_check(
    State(state): State<AppState>,
) -> Json<HealthResponse> {
    let reasoner = state.reasoner.read().await;

    let (ontology_loaded, ontology_namespace, ontology_version) = if let Some(r) = reasoner.as_ref() {
        let schema = r.schema();
        (true, Some(schema.namespace.clone()), Some(schema.version.clone()))
    } else {
        (false, None, None)
    };

    Json(HealthResponse {
        status: "healthy".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        ontology_loaded,
        ontology_namespace,
        ontology_version,
    })
}

// ============================================================================
// Ontology Management
// ============================================================================

pub async fn upload_schema(
    State(state): State<AppState>,
    Json(request): Json<UploadSchemaRequest>,
) -> Result<Json<UploadSchemaResponse>, (StatusCode, Json<ErrorResponse>)> {
    // Parse schema based on format
    let schema = match request.format {
        SchemaFormat::Json => OntologyLoader::from_json_str(&request.schema),
        SchemaFormat::Yaml => OntologyLoader::from_yaml_str(&request.schema),
    }
    .map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse::new("InvalidSchema", e.to_string())),
        )
    })?;

    let namespace = schema.namespace.clone();
    let version = schema.version.clone();

    // Create new reasoner with schema
    let reasoner = OntologyReasoner::new(schema);

    // Update state
    let mut state_reasoner = state.reasoner.write().await;
    *state_reasoner = Some(reasoner);

    Ok(Json(UploadSchemaResponse {
        success: true,
        message: "Ontology schema uploaded successfully".to_string(),
        namespace,
        version,
    }))
}

pub async fn get_schema(
    State(state): State<AppState>,
) -> Result<Json<serde_json::Value>, (StatusCode, Json<ErrorResponse>)> {
    let reasoner = state.reasoner.read().await;

    let reasoner = reasoner.as_ref().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse::new(
                "NoSchema",
                "No ontology schema loaded",
            )),
        )
    })?;

    let schema = reasoner.schema();
    let json = serde_json::to_value(schema).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse::new("SerializationError", e.to_string())),
        )
    })?;

    Ok(Json(json))
}

pub async fn get_entity_type(
    State(state): State<AppState>,
    axum::extract::Path(type_id): axum::extract::Path<String>,
) -> Result<Json<GetEntityTypeResponse>, (StatusCode, Json<ErrorResponse>)> {
    let reasoner = state.reasoner.read().await;

    let reasoner = reasoner.as_ref().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse::new(
                "NoSchema",
                "No ontology schema loaded",
            )),
        )
    })?;

    let schema = reasoner.schema();
    let entity_type = schema.entity_types.get(&type_id).ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse::new(
                "TypeNotFound",
                format!("Entity type '{}' not found", type_id),
            )),
        )
    })?;

    let properties = entity_type
        .properties
        .iter()
        .map(|p| PropertyInfo {
            name: p.name.clone(),
            property_type: format!("{:?}", p.property_type),
            required: p.required,
            cardinality: format!("{:?}", p.cardinality),
            description: p.description.clone(),
        })
        .collect();

    let constraints = entity_type
        .constraints
        .iter()
        .map(|c| format!("{:?}", c))
        .collect();

    Ok(Json(GetEntityTypeResponse {
        id: entity_type.id.clone(),
        label: entity_type.label.clone(),
        parent: entity_type.parent.clone(),
        properties,
        constraints,
    }))
}

pub async fn get_subtypes(
    State(state): State<AppState>,
    axum::extract::Path(type_id): axum::extract::Path<String>,
) -> Result<Json<GetSubtypesResponse>, (StatusCode, Json<ErrorResponse>)> {
    let reasoner = state.reasoner.read().await;

    let reasoner = reasoner.as_ref().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse::new(
                "NoSchema",
                "No ontology schema loaded",
            )),
        )
    })?;

    let schema = reasoner.schema();

    // Check if type exists
    if !schema.entity_types.contains_key(&type_id) {
        return Err((
            StatusCode::NOT_FOUND,
            Json(ErrorResponse::new(
                "TypeNotFound",
                format!("Entity type '{}' not found", type_id),
            )),
        ));
    }

    let subtypes = schema.get_subtypes(&type_id);

    Ok(Json(GetSubtypesResponse {
        type_id,
        subtypes,
    }))
}

// ============================================================================
// Entity Validation
// ============================================================================

pub async fn validate_entity(
    State(state): State<AppState>,
    Json(request): Json<ValidateEntityRequest>,
) -> Result<Json<ValidateEntityResponse>, (StatusCode, Json<ErrorResponse>)> {
    let reasoner = state.reasoner.read().await;

    let reasoner = reasoner.as_ref().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse::new(
                "NoSchema",
                "No ontology schema loaded",
            )),
        )
    })?;

    let validator = OntologyValidator::new(reasoner.schema().clone());

    match validator.validate_entity(&request.entity_type, &request.properties) {
        Ok(()) => Ok(Json(ValidateEntityResponse {
            valid: true,
            errors: vec![],
        })),
        Err(errors) => Ok(Json(ValidateEntityResponse {
            valid: false,
            errors: errors
                .into_iter()
                .map(|e| ValidationErrorInfo {
                    error_type: format!("{:?}", e).split('(').next().unwrap_or("Error").to_string(),
                    message: e.to_string(),
                })
                .collect(),
        })),
    }
}

pub async fn validate_relation(
    State(state): State<AppState>,
    Json(request): Json<ValidateRelationRequest>,
) -> Result<Json<ValidateRelationResponse>, (StatusCode, Json<ErrorResponse>)> {
    let reasoner = state.reasoner.read().await;

    let reasoner = reasoner.as_ref().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse::new(
                "NoSchema",
                "No ontology schema loaded",
            )),
        )
    })?;

    let validator = OntologyValidator::new(reasoner.schema().clone());

    match validator.validate_relation(
        &request.relation_type,
        &request.source_type,
        &request.target_type,
    ) {
        Ok(()) => Ok(Json(ValidateRelationResponse {
            valid: true,
            error: None,
        })),
        Err(e) => Ok(Json(ValidateRelationResponse {
            valid: false,
            error: Some(e.to_string()),
        })),
    }
}

// ============================================================================
// Query Expansion
// ============================================================================

pub async fn expand_query(
    State(state): State<AppState>,
    Json(request): Json<ExpandQueryRequest>,
) -> Result<Json<ExpandQueryResponse>, (StatusCode, Json<ErrorResponse>)> {
    let reasoner = state.reasoner.read().await;

    let reasoner = reasoner.as_ref().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse::new(
                "NoSchema",
                "No ontology schema loaded",
            )),
        )
    })?;

    let expanded = reasoner.expand_query(&request.entity_type).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            Json(ErrorResponse::new("QueryExpansionError", e.to_string())),
        )
    })?;

    let inferred_relations = if request.include_inferred_relations {
        expanded
            .inferred_relations
            .into_iter()
            .map(|r| InferredRelationInfo {
                relation_type: r.relation_type,
                source_type: r.source_type,
                target_type: r.target_type,
                reason: format!("{:?}", r.reason),
            })
            .collect()
    } else {
        vec![]
    };

    Ok(Json(ExpandQueryResponse {
        original_type: expanded.original_type,
        expanded_types: expanded.expanded_types,
        inferred_relations,
        metadata: expanded.metadata,
    }))
}

pub async fn get_compatible_relations(
    State(state): State<AppState>,
    Json(request): Json<GetCompatibleRelationsRequest>,
) -> Result<Json<GetCompatibleRelationsResponse>, (StatusCode, Json<ErrorResponse>)> {
    let reasoner = state.reasoner.read().await;

    let reasoner = reasoner.as_ref().ok_or_else(|| {
        (
            StatusCode::NOT_FOUND,
            Json(ErrorResponse::new(
                "NoSchema",
                "No ontology schema loaded",
            )),
        )
    })?;

    let compatible_relations = reasoner.get_compatible_relations(
        &request.source_type,
        &request.target_type,
    );

    Ok(Json(GetCompatibleRelationsResponse {
        source_type: request.source_type,
        target_type: request.target_type,
        compatible_relations,
    }))
}

// ============================================================================
// Entity CRUD
// ============================================================================

pub async fn create_entity(
    State(state): State<AppState>,
    Json(request): Json<CreateEntityRequest>,
) -> Result<Json<CreateEntityResponse>, (StatusCode, Json<ErrorResponse>)> {
    // Check if databases are available
    let surreal = state.surreal.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Database not connected",
            )),
        )
    })?;

    let qdrant = state.qdrant.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Vector database not connected",
            )),
        )
    })?;

    let embedding_service = state.embedding_service.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "ServiceNotAvailable",
                "Embedding service not available",
            )),
        )
    })?;

    // Validate entity against ontology if loaded
    let reasoner = state.reasoner.read().await;
    if let Some(ref r) = *reasoner {
        let validator = OntologyValidator::new(r.schema().clone());
        validator
            .validate_entity(&request.entity_type, &request.properties)
            .map_err(|errors| {
                let error_messages: Vec<String> = errors.iter().map(|e| e.to_string()).collect();
                (
                    StatusCode::BAD_REQUEST,
                    Json(ErrorResponse::new(
                        "ValidationError",
                        format!("Entity validation failed: {}", error_messages.join("; ")),
                    )),
                )
            })?;
    }
    drop(reasoner);

    // Create entity
    let mut entity = Entity::new(request.entity_type.clone(), request.properties);
    if let Some(metadata) = request.metadata {
        entity = entity.with_metadata(metadata);
    }

    // Generate embedding from text properties
    let text_content = extract_text_from_properties(&entity.properties);
    if !text_content.is_empty() {
        match embedding_service.encode(&text_content) {
            Ok(embedding) => {
                entity = entity.with_embedding(embedding);
            }
            Err(e) => {
                tracing::warn!("Failed to generate embedding: {}", e);
            }
        }
    }

    // Store in SurrealDB
    let entity_id = surreal
        .create_entity(&entity)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to create entity: {}", e),
                )),
            )
        })?;

    // Store embedding in Qdrant if present
    if let Some(ref embedding) = entity.embedding {
        // Ensure collection exists
        if !qdrant
            .collection_exists(&entity.entity_type)
            .await
            .unwrap_or(false)
        {
            qdrant
                .create_collection(&entity.entity_type, embedding.len() as u64)
                .await
                .map_err(|e| {
                    tracing::warn!("Failed to create Qdrant collection: {}", e);
                })
                .ok();
        }

        qdrant
            .upsert_embedding(&entity.entity_type, &entity_id, embedding.clone())
            .await
            .map_err(|e| {
                tracing::warn!("Failed to store embedding: {}", e);
            })
            .ok();
    }

    Ok(Json(CreateEntityResponse {
        id: entity_id,
        entity_type: entity.entity_type,
        created_at: entity.created_at.to_rfc3339(),
    }))
}

pub async fn get_entity(
    State(state): State<AppState>,
    Path(entity_id): Path<String>,
) -> Result<Json<EntityResponse>, (StatusCode, Json<ErrorResponse>)> {
    let surreal = state.surreal.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Database not connected",
            )),
        )
    })?;

    let entity = surreal
        .get_entity(&entity_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to get entity: {}", e),
                )),
            )
        })?
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                Json(ErrorResponse::new(
                    "EntityNotFound",
                    format!("Entity '{}' not found", entity_id),
                )),
            )
        })?;

    Ok(Json(EntityResponse {
        id: entity.id,
        entity_type: entity.entity_type,
        properties: entity.properties,
        embedding: entity.embedding,
        created_at: entity.created_at.to_rfc3339(),
        updated_at: entity.updated_at.to_rfc3339(),
        metadata: entity.metadata,
    }))
}

pub async fn update_entity(
    State(state): State<AppState>,
    Path(entity_id): Path<String>,
    Json(request): Json<UpdateEntityRequest>,
) -> Result<StatusCode, (StatusCode, Json<ErrorResponse>)> {
    let surreal = state.surreal.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Database not connected",
            )),
        )
    })?;

    // Get existing entity
    let mut entity = surreal
        .get_entity(&entity_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to get entity: {}", e),
                )),
            )
        })?
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                Json(ErrorResponse::new(
                    "EntityNotFound",
                    format!("Entity '{}' not found", entity_id),
                )),
            )
        })?;

    // Update properties
    entity.properties = request.properties;
    entity.updated_at = chrono::Utc::now();

    // Validate if ontology is loaded
    let reasoner = state.reasoner.read().await;
    if let Some(ref r) = *reasoner {
        let validator = OntologyValidator::new(r.schema().clone());
        validator
            .validate_entity(&entity.entity_type, &entity.properties)
            .map_err(|errors| {
                let error_messages: Vec<String> = errors.iter().map(|e| e.to_string()).collect();
                (
                    StatusCode::BAD_REQUEST,
                    Json(ErrorResponse::new(
                        "ValidationError",
                        format!("Entity validation failed: {}", error_messages.join("; ")),
                    )),
                )
            })?;
    }
    drop(reasoner);

    // Update in database
    surreal
        .update_entity(&entity_id, &entity)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to update entity: {}", e),
                )),
            )
        })?;

    Ok(StatusCode::NO_CONTENT)
}

pub async fn delete_entity(
    State(state): State<AppState>,
    Path(entity_id): Path<String>,
) -> Result<StatusCode, (StatusCode, Json<ErrorResponse>)> {
    let surreal = state.surreal.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Database not connected",
            )),
        )
    })?;

    let qdrant = state.qdrant.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Vector database not connected",
            )),
        )
    })?;

    // Get entity to find its type
    let entity = surreal
        .get_entity(&entity_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to get entity: {}", e),
                )),
            )
        })?
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                Json(ErrorResponse::new(
                    "EntityNotFound",
                    format!("Entity '{}' not found", entity_id),
                )),
            )
        })?;

    // Delete from SurrealDB
    surreal
        .delete_entity(&entity_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to delete entity: {}", e),
                )),
            )
        })?;

    // Delete from Qdrant (if it exists)
    qdrant
        .delete_embedding(&entity.entity_type, &entity_id)
        .await
        .ok();

    Ok(StatusCode::NO_CONTENT)
}

// ============================================================================
// Relation CRUD
// ============================================================================

pub async fn create_relation(
    State(state): State<AppState>,
    Json(request): Json<CreateRelationRequest>,
) -> Result<Json<CreateRelationResponse>, (StatusCode, Json<ErrorResponse>)> {
    let surreal = state.surreal.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Database not connected",
            )),
        )
    })?;

    // Verify source and target entities exist
    let source_entity = surreal
        .get_entity(&request.source_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to get source entity: {}", e),
                )),
            )
        })?
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                Json(ErrorResponse::new(
                    "EntityNotFound",
                    format!("Source entity '{}' not found", request.source_id),
                )),
            )
        })?;

    let target_entity = surreal
        .get_entity(&request.target_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to get target entity: {}", e),
                )),
            )
        })?
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                Json(ErrorResponse::new(
                    "EntityNotFound",
                    format!("Target entity '{}' not found", request.target_id),
                )),
            )
        })?;

    // Validate relation if ontology is loaded
    let reasoner = state.reasoner.read().await;
    if let Some(ref r) = *reasoner {
        let validator = OntologyValidator::new(r.schema().clone());
        validator
            .validate_relation(
                &request.relation_type,
                &source_entity.entity_type,
                &target_entity.entity_type,
            )
            .map_err(|e| {
                (
                    StatusCode::BAD_REQUEST,
                    Json(ErrorResponse::new(
                        "ValidationError",
                        format!("Relation validation failed: {}", e),
                    )),
                )
            })?;
    }
    drop(reasoner);

    // Create relation
    let relation = Relation::new(
        request.relation_type.clone(),
        request.source_id.clone(),
        request.target_id.clone(),
        request.properties,
    );

    let relation_id = surreal
        .create_relation(&relation)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to create relation: {}", e),
                )),
            )
        })?;

    Ok(Json(CreateRelationResponse {
        id: relation_id,
        relation_type: relation.relation_type,
        source_id: relation.source_id,
        target_id: relation.target_id,
        created_at: relation.created_at.to_rfc3339(),
    }))
}

pub async fn get_relation(
    State(state): State<AppState>,
    Path(relation_id): Path<String>,
) -> Result<Json<RelationResponse>, (StatusCode, Json<ErrorResponse>)> {
    let surreal = state.surreal.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Database not connected",
            )),
        )
    })?;

    let relation = surreal
        .get_relation(&relation_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to get relation: {}", e),
                )),
            )
        })?
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                Json(ErrorResponse::new(
                    "RelationNotFound",
                    format!("Relation '{}' not found", relation_id),
                )),
            )
        })?;

    Ok(Json(RelationResponse {
        id: relation.id,
        relation_type: relation.relation_type,
        source_id: relation.source_id,
        target_id: relation.target_id,
        properties: relation.properties,
        created_at: relation.created_at.to_rfc3339(),
    }))
}

pub async fn delete_relation(
    State(state): State<AppState>,
    Path(relation_id): Path<String>,
) -> Result<StatusCode, (StatusCode, Json<ErrorResponse>)> {
    let surreal = state.surreal.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Database not connected",
            )),
        )
    })?;

    // Verify relation exists
    surreal
        .get_relation(&relation_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to get relation: {}", e),
                )),
            )
        })?
        .ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                Json(ErrorResponse::new(
                    "RelationNotFound",
                    format!("Relation '{}' not found", relation_id),
                )),
            )
        })?;

    surreal
        .delete_relation(&relation_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to delete relation: {}", e),
                )),
            )
        })?;

    Ok(StatusCode::NO_CONTENT)
}

// ============================================================================
// Hybrid Query
// ============================================================================

pub async fn hybrid_query(
    State(state): State<AppState>,
    Json(request): Json<HybridQuery>,
) -> Result<Json<QueryResult>, (StatusCode, Json<ErrorResponse>)> {
    let coordinator = state.query_coordinator.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "ServiceNotAvailable",
                "Query coordinator not available",
            )),
        )
    })?;

    let result = coordinator
        .execute(&request)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "QueryError",
                    format!("Query execution failed: {}", e),
                )),
            )
        })?;

    Ok(Json(result))
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Extract text content from entity properties for embedding generation
fn extract_text_from_properties(properties: &HashMap<String, serde_json::Value>) -> String {
    let mut text_parts = Vec::new();

    for (key, value) in properties {
        match value {
            serde_json::Value::String(s) => {
                text_parts.push(format!("{}: {}", key, s));
            }
            serde_json::Value::Number(n) => {
                text_parts.push(format!("{}: {}", key, n));
            }
            serde_json::Value::Bool(b) => {
                text_parts.push(format!("{}: {}", key, b));
            }
            _ => {}
        }
    }

    text_parts.join(". ")
}
