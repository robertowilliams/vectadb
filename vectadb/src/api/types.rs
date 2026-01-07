// API request and response types

use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;
use std::collections::HashMap;

// ============================================================================
// Ontology Management
// ============================================================================

/// Upload ontology schema request
#[derive(Debug, Serialize, Deserialize)]
pub struct UploadSchemaRequest {
    /// Schema in JSON or YAML format
    pub schema: String,

    /// Format: "json" or "yaml"
    pub format: SchemaFormat,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SchemaFormat {
    Json,
    Yaml,
}

/// Schema upload response
#[derive(Debug, Serialize, Deserialize)]
pub struct UploadSchemaResponse {
    pub success: bool,
    pub message: String,
    pub namespace: String,
    pub version: String,
}

/// Get entity type response
#[derive(Debug, Serialize, Deserialize)]
pub struct GetEntityTypeResponse {
    pub id: String,
    pub label: String,
    pub parent: Option<String>,
    pub properties: Vec<PropertyInfo>,
    pub constraints: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PropertyInfo {
    pub name: String,
    pub property_type: String,
    pub required: bool,
    pub cardinality: String,
    pub description: Option<String>,
}

/// Get subtypes response
#[derive(Debug, Serialize, Deserialize)]
pub struct GetSubtypesResponse {
    pub type_id: String,
    pub subtypes: Vec<String>,
}

// ============================================================================
// Entity Validation
// ============================================================================

/// Validate entity request
#[derive(Debug, Serialize, Deserialize)]
pub struct ValidateEntityRequest {
    pub entity_type: String,
    pub properties: HashMap<String, JsonValue>,
}

/// Validation response
#[derive(Debug, Serialize, Deserialize)]
pub struct ValidateEntityResponse {
    pub valid: bool,
    pub errors: Vec<ValidationErrorInfo>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ValidationErrorInfo {
    pub error_type: String,
    pub message: String,
}

/// Validate relation request
#[derive(Debug, Serialize, Deserialize)]
pub struct ValidateRelationRequest {
    pub relation_type: String,
    pub source_type: String,
    pub target_type: String,
}

/// Validate relation response
#[derive(Debug, Serialize, Deserialize)]
pub struct ValidateRelationResponse {
    pub valid: bool,
    pub error: Option<String>,
}

// ============================================================================
// Query Expansion
// ============================================================================

/// Expand query request
#[derive(Debug, Serialize, Deserialize)]
pub struct ExpandQueryRequest {
    pub entity_type: String,
    pub include_inferred_relations: bool,
}

/// Expand query response
#[derive(Debug, Serialize, Deserialize)]
pub struct ExpandQueryResponse {
    pub original_type: String,
    pub expanded_types: Vec<String>,
    pub inferred_relations: Vec<InferredRelationInfo>,
    pub metadata: HashMap<String, String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct InferredRelationInfo {
    pub relation_type: String,
    pub source_type: String,
    pub target_type: String,
    pub reason: String,
}

/// Get compatible relations request
#[derive(Debug, Serialize, Deserialize)]
pub struct GetCompatibleRelationsRequest {
    pub source_type: String,
    pub target_type: String,
}

/// Get compatible relations response
#[derive(Debug, Serialize, Deserialize)]
pub struct GetCompatibleRelationsResponse {
    pub source_type: String,
    pub target_type: String,
    pub compatible_relations: Vec<String>,
}

// ============================================================================
// Health & Status
// ============================================================================

/// Health check response
#[derive(Debug, Serialize, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub ontology_loaded: bool,
    pub ontology_namespace: Option<String>,
    pub ontology_version: Option<String>,
}

// ============================================================================
// Error Response
// ============================================================================

/// Standard error response
#[derive(Debug, Serialize, Deserialize)]
pub struct ErrorResponse {
    pub error: String,
    pub message: String,
}

impl ErrorResponse {
    pub fn new(error: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            error: error.into(),
            message: message.into(),
        }
    }
}

// ============================================================================
// Entity CRUD
// ============================================================================

/// Create entity request
#[derive(Debug, Serialize, Deserialize)]
pub struct CreateEntityRequest {
    pub entity_type: String,
    pub properties: HashMap<String, JsonValue>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, String>>,
}

/// Create entity response
#[derive(Debug, Serialize, Deserialize)]
pub struct CreateEntityResponse {
    pub id: String,
    pub entity_type: String,
    pub created_at: String,
}

/// Update entity request
#[derive(Debug, Serialize, Deserialize)]
pub struct UpdateEntityRequest {
    pub properties: HashMap<String, JsonValue>,
}

/// Entity response (for GET)
#[derive(Debug, Serialize, Deserialize)]
pub struct EntityResponse {
    pub id: String,
    pub entity_type: String,
    pub properties: HashMap<String, JsonValue>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding: Option<Vec<f32>>,
    pub created_at: String,
    pub updated_at: String,
    pub metadata: HashMap<String, String>,
}

/// List entities response
#[derive(Debug, Serialize, Deserialize)]
pub struct ListEntitiesResponse {
    pub entities: Vec<EntityResponse>,
    pub total: usize,
}

// ============================================================================
// Relation CRUD
// ============================================================================

/// Create relation request
#[derive(Debug, Serialize, Deserialize)]
pub struct CreateRelationRequest {
    pub relation_type: String,
    pub source_id: String,
    pub target_id: String,
    #[serde(default)]
    pub properties: HashMap<String, JsonValue>,
}

/// Create relation response
#[derive(Debug, Serialize, Deserialize)]
pub struct CreateRelationResponse {
    pub id: String,
    pub relation_type: String,
    pub source_id: String,
    pub target_id: String,
    pub created_at: String,
}

/// Relation response (for GET)
#[derive(Debug, Serialize, Deserialize)]
pub struct RelationResponse {
    pub id: String,
    pub relation_type: String,
    pub source_id: String,
    pub target_id: String,
    pub properties: HashMap<String, JsonValue>,
    pub created_at: String,
}

// ============================================================================
// Hybrid Query
// ============================================================================

/// Hybrid query request (re-export from query module)
pub use crate::query::{
    HybridQuery, VectorQuery, GraphQuery, CombinedQuery,
    TraversalDirection, MergeStrategy, QueryResult,
};
