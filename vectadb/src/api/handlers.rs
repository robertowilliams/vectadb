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
// Event Ingestion (Phase 5)
// ============================================================================

/// Ingest a single event
pub async fn ingest_event(
    State(state): State<AppState>,
    Json(request): Json<EventIngestionRequest>,
) -> Result<Json<EventIngestionResponse>, (StatusCode, Json<ErrorResponse>)> {
    let surreal = state.surreal.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Database not connected",
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

    // Get or create trace
    let trace_id = if let Some(ref tid) = request.trace_id {
        tid.clone()
    } else if let Some(ref sid) = request.session_id {
        get_or_create_trace_by_session(&state, sid, request.agent_id.as_deref())
            .await
            .map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(ErrorResponse::new(
                        "TraceError",
                        format!("Failed to get/create trace: {}", e),
                    )),
                )
            })?
    } else {
        // No trace_id or session_id - create a new trace
        create_trace_for_session(&state, "default", request.agent_id.as_deref())
            .await
            .map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(ErrorResponse::new(
                        "TraceError",
                        format!("Failed to create trace: {}", e),
                    )),
                )
            })?
    };

    // Create event entity
    let event_id = create_event_entity(surreal, &request, &trace_id)
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "DatabaseError",
                    format!("Failed to create event: {}", e),
                )),
            )
        })?;

    // Generate and store embedding if properties contain text
    let text_content = extract_text_from_json(&request.properties);
    if !text_content.is_empty() {
        if let Ok(embedding) = embedding_service.encode(&text_content) {
            store_event_vector(
                state.qdrant.as_ref().unwrap(),
                &event_id,
                embedding,
            )
            .await
            .ok(); // Log but don't fail on vector storage error
        }
    }

    Ok(Json(EventIngestionResponse {
        event_id,
        trace_id,
        created_at: request.timestamp,
    }))
}

/// Ingest events in bulk
pub async fn ingest_events_bulk(
    State(state): State<AppState>,
    Json(request): Json<BulkEventIngestionRequest>,
) -> Result<Json<BulkEventIngestionResponse>, (StatusCode, Json<ErrorResponse>)> {
    let surreal = state.surreal.as_ref().ok_or_else(|| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(ErrorResponse::new(
                "DatabaseNotAvailable",
                "Database not connected",
            )),
        )
    })?;

    let embedding_service = state.embedding_service.as_ref();

    let mut ingested = 0;
    let mut failed = 0;
    let mut trace_ids = Vec::new();
    let mut errors = Vec::new();

    for (index, event_request) in request.events.iter().enumerate() {
        // Get or create trace
        let trace_id_result = if let Some(ref tid) = event_request.trace_id {
            Ok(tid.clone())
        } else if let Some(ref sid) = event_request.session_id {
            if request.options.auto_create_traces {
                get_or_create_trace_by_session(&state, sid, event_request.agent_id.as_deref()).await
            } else {
                Err(anyhow::anyhow!("Trace not found and auto-create disabled"))
            }
        } else {
            // No trace_id or session_id
            if request.options.auto_create_traces {
                create_trace_for_session(&state, "default", event_request.agent_id.as_deref()).await
            } else {
                Err(anyhow::anyhow!("No trace specified and auto-create disabled"))
            }
        };

        let trace_id = match trace_id_result {
            Ok(tid) => tid,
            Err(e) => {
                failed += 1;
                errors.push(IngestionError {
                    index,
                    error: format!("Failed to get/create trace: {}", e),
                });
                continue;
            }
        };

        // Create event entity
        match create_event_entity(surreal, event_request, &trace_id).await {
            Ok(event_id) => {
                // Generate and store embedding if requested
                if request.options.generate_embeddings {
                    if let Some(embedding_svc) = embedding_service {
                        let text_content = extract_text_from_json(&event_request.properties);
                        if !text_content.is_empty() {
                            if let Ok(embedding) = embedding_svc.encode(&text_content) {
                                if let Some(qdrant) = state.qdrant.as_ref() {
                                    store_event_vector(qdrant, &event_id, embedding)
                                        .await
                                        .ok(); // Don't fail on vector storage error
                                }
                            }
                        }
                    }
                }

                ingested += 1;
                if !trace_ids.contains(&trace_id) {
                    trace_ids.push(trace_id);
                }
            }
            Err(e) => {
                failed += 1;
                errors.push(IngestionError {
                    index,
                    error: format!("Failed to create event: {}", e),
                });
            }
        }
    }

    Ok(Json(BulkEventIngestionResponse {
        ingested,
        failed,
        trace_ids,
        errors,
    }))
}

/// Get or create trace by session_id with resilient detection
async fn get_or_create_trace_by_session(
    state: &AppState,
    session_id: &str,
    agent_id: Option<&str>,
) -> Result<String, anyhow::Error> {
    let surreal = state
        .surreal
        .as_ref()
        .ok_or_else(|| anyhow::anyhow!("Database not available"))?;

    // Strategy 1: Try exact session_id match first
    #[derive(Debug, serde::Deserialize)]
    struct TraceRecord {
        id: String,
        start_time: Option<String>,
    }

    let query = format!(
        "SELECT id, start_time FROM agent_trace WHERE session_id = '{}' ORDER BY start_time DESC LIMIT 1",
        session_id.replace('\'', "\\'")
    );

    let mut result = surreal.db().query(query).await?;
    let traces: Vec<TraceRecord> = result.take(0).unwrap_or_default();

    if let Some(trace) = traces.first() {
        tracing::debug!("Found trace by session_id: {}", trace.id);
        return Ok(trace.id.clone());
    }

    // Strategy 2: If agent_id provided, check for recent trace (within 1 hour)
    if let Some(aid) = agent_id {
        let query = format!(
            "SELECT id, start_time FROM agent_trace WHERE agent_id = '{}' AND status = 'running' AND start_time > time::now() - 1h ORDER BY start_time DESC LIMIT 1",
            aid.replace('\'', "\\'")
        );

        let mut result = surreal.db().query(query).await?;
        let traces: Vec<TraceRecord> = result.take(0).unwrap_or_default();

        if let Some(trace) = traces.first() {
            tracing::debug!("Found trace by agent_id: {}", trace.id);
            return Ok(trace.id.clone());
        }
    }

    // Strategy 3: Create new trace
    tracing::info!("Creating new trace for session_id: {}", session_id);
    create_trace_for_session(state, session_id, agent_id).await
}

/// Create a new trace for a session
async fn create_trace_for_session(
    state: &AppState,
    session_id: &str,
    agent_id: Option<&str>,
) -> Result<String, anyhow::Error> {
    let surreal = state
        .surreal
        .as_ref()
        .ok_or_else(|| anyhow::anyhow!("Database not available"))?;

    let trace_id = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now();

    let agent_id_str = agent_id.map(|s| format!("'{}'", s.replace('\'', "\\'")))
        .unwrap_or_else(|| "NONE".to_string());

    let query = format!(
        "CREATE agent_trace CONTENT {{
            id: '{}',
            session_id: '{}',
            agent_id: {},
            status: 'running',
            start_time: '{}',
            created_at: '{}',
            updated_at: '{}'
        }}",
        trace_id,
        session_id.replace('\'', "\\'"),
        agent_id_str,
        now.to_rfc3339(),
        now.to_rfc3339(),
        now.to_rfc3339()
    );

    surreal.db().query(query).await?;

    Ok(trace_id)
}

/// Create event entity in SurrealDB
async fn create_event_entity(
    surreal: &SurrealDBClient,
    request: &EventIngestionRequest,
    trace_id: &str,
) -> Result<String, anyhow::Error> {
    let event_id = uuid::Uuid::new_v4().to_string();
    let now = chrono::Utc::now();

    // Build event properties as JSON
    let mut event_data = serde_json::json!({
        "id": event_id,
        "trace_id": trace_id,
        "timestamp": request.timestamp.to_rfc3339(),
        "properties": request.properties,
        "created_at": now.to_rfc3339(),
        "updated_at": now.to_rfc3339(),
    });

    // Add optional fields
    if let Some(ref event_type) = request.event_type {
        event_data["event_type"] = serde_json::json!(event_type);
    }
    if let Some(ref agent_id) = request.agent_id {
        event_data["agent_id"] = serde_json::json!(agent_id);
    }
    if let Some(ref session_id) = request.session_id {
        event_data["session_id"] = serde_json::json!(session_id);
    }
    if let Some(ref source) = request.source {
        event_data["source"] = serde_json::json!(source);
    }

    let query = format!("CREATE agent_event CONTENT {}", event_data);

    surreal.db().query(query).await?;

    // Create relation from trace to event
    let trace_record_id = format!("agent_trace:`{}`", trace_id);
    let event_record_id = format!("agent_event:`{}`", event_id);

    let relation_query = format!(
        "RELATE {}->contains->{} CONTENT {{
            created_at: '{}'
        }}",
        trace_record_id,
        event_record_id,
        now.to_rfc3339()
    );

    surreal.db().query(relation_query).await?;

    Ok(event_id)
}

/// Store event embedding in Qdrant
async fn store_event_vector(
    qdrant: &QdrantClient,
    event_id: &str,
    embedding: Vec<f32>,
) -> Result<(), anyhow::Error> {
    const EVENTS_COLLECTION: &str = "agent_events";

    // Ensure collection exists
    if !qdrant.collection_exists(EVENTS_COLLECTION).await? {
        qdrant
            .create_collection(EVENTS_COLLECTION, embedding.len() as u64)
            .await?;
    }

    // Store embedding
    qdrant
        .upsert_embedding(EVENTS_COLLECTION, event_id, embedding)
        .await?;

    Ok(())
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

/// Extract text content from JSON value for embedding generation
fn extract_text_from_json(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Object(map) => {
            let mut text_parts = Vec::new();
            for (key, val) in map {
                match val {
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
        _ => String::new(),
    }
}
