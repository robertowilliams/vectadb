// Integration tests for VectaDB REST API

use axum::{
    body::Body,
    http::{Request, StatusCode},
};
use serde_json::{json, Value};
use tower::ServiceExt;

// Helper to create test app
fn create_test_app() -> axum::Router {
    vectadb::api::routes::create_router()
}

// Helper to parse JSON response
async fn parse_json_response(response: axum::response::Response) -> Value {
    let body = axum::body::to_bytes(response.into_body(), usize::MAX)
        .await
        .unwrap();
    serde_json::from_slice(&body).unwrap()
}

#[tokio::test]
async fn test_health_check() {
    let app = create_test_app();

    let response = app
        .oneshot(
            Request::builder()
                .uri("/health")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let body = parse_json_response(response).await;
    assert_eq!(body["status"], "healthy");
    assert_eq!(body["version"], env!("CARGO_PKG_VERSION"));
    assert_eq!(body["ontology_loaded"], false);
}

#[tokio::test]
async fn test_upload_schema_yaml() {
    let app = create_test_app();

    let schema_yaml = r#"
namespace: "test://ontology"
version: "1.0.0"
entity_types:
  TestEntity:
    id: "TestEntity"
    label: "Test Entity"
    parent: null
    properties:
      - name: "id"
        property_type:
          type: "String"
        required: true
        cardinality: "One"
    constraints: []
    metadata: null
relation_types: {}
rules: []
"#;

    let request_body = json!({
        "schema": schema_yaml,
        "format": "yaml"
    });

    let response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/ontology/schema")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(&request_body).unwrap()))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);

    let body = parse_json_response(response).await;
    assert_eq!(body["success"], true);
    assert_eq!(body["namespace"], "test://ontology");
    assert_eq!(body["version"], "1.0.0");
}

#[tokio::test]
async fn test_upload_schema_json() {
    let app = create_test_app();

    let schema_json = json!({
        "namespace": "test://ontology",
        "version": "1.0.0",
        "entity_types": {
            "TestEntity": {
                "id": "TestEntity",
                "label": "Test Entity",
                "parent": null,
                "properties": [{
                    "name": "id",
                    "property_type": {"type": "String"},
                    "required": true,
                    "cardinality": "One"
                }],
                "constraints": [],
                "metadata": null
            }
        },
        "relation_types": {},
        "rules": []
    });

    let request_body = json!({
        "schema": serde_json::to_string(&schema_json).unwrap(),
        "format": "json"
    });

    let response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/ontology/schema")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(&request_body).unwrap()))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
}

#[tokio::test]
async fn test_upload_invalid_schema() {
    let app = create_test_app();

    let request_body = json!({
        "schema": "invalid yaml {{{",
        "format": "yaml"
    });

    let response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/ontology/schema")
                .header("content-type", "application/json")
                .body(Body::from(serde_json::to_vec(&request_body).unwrap()))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);

    let body = parse_json_response(response).await;
    assert_eq!(body["error"], "InvalidSchema");
}

#[tokio::test]
async fn test_get_schema_before_upload() {
    let app = create_test_app();

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

    let body = parse_json_response(response).await;
    assert_eq!(body["error"], "NoSchema");
}

#[tokio::test]
async fn test_complete_workflow() {
    let app = create_test_app();

    // 1. Upload schema
    let schema_yaml = r#"
namespace: "test://workflow"
version: "1.0.0"
entity_types:
  Agent:
    id: "Agent"
    label: "Agent"
    parent: null
    properties:
      - name: "id"
        property_type:
          type: "String"
        required: true
        cardinality: "One"
      - name: "name"
        property_type:
          type: "String"
        required: true
        cardinality: "One"
    constraints: []
    metadata: null
  LLMAgent:
    id: "LLMAgent"
    label: "LLM Agent"
    parent: "Agent"
    properties:
      - name: "model_name"
        property_type:
          type: "String"
        required: true
        cardinality: "One"
    constraints: []
    metadata: null
  Task:
    id: "Task"
    label: "Task"
    parent: null
    properties:
      - name: "id"
        property_type:
          type: "String"
        required: true
        cardinality: "One"
    constraints: []
    metadata: null
relation_types:
  executes:
    id: "executes"
    label: "executes"
    domain: "Agent"
    range: "Task"
    inverse: null
    transitive: false
    symmetric: false
    functional: false
    reflexive: false
    metadata: null
rules: []
"#;

    let upload_response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/ontology/schema")
                .header("content-type", "application/json")
                .body(Body::from(
                    serde_json::to_vec(&json!({
                        "schema": schema_yaml,
                        "format": "yaml"
                    }))
                    .unwrap(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(upload_response.status(), StatusCode::OK);

    // 2. Get entity type
    let get_type_response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/api/v1/ontology/types/LLMAgent")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(get_type_response.status(), StatusCode::OK);
    let type_body = parse_json_response(get_type_response).await;
    assert_eq!(type_body["id"], "LLMAgent");
    assert_eq!(type_body["parent"], "Agent");

    // 3. Get subtypes
    let subtypes_response = app
        .clone()
        .oneshot(
            Request::builder()
                .uri("/api/v1/ontology/types/Agent/subtypes")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(subtypes_response.status(), StatusCode::OK);
    let subtypes_body = parse_json_response(subtypes_response).await;
    assert_eq!(subtypes_body["type_id"], "Agent");
    assert!(subtypes_body["subtypes"].as_array().unwrap().len() >= 2);

    // 4. Validate valid entity
    let validate_valid_response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/validate/entity")
                .header("content-type", "application/json")
                .body(Body::from(
                    serde_json::to_vec(&json!({
                        "entity_type": "LLMAgent",
                        "properties": {
                            "id": "agent-001",
                            "name": "TestBot",
                            "model_name": "gpt-4"
                        }
                    }))
                    .unwrap(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(validate_valid_response.status(), StatusCode::OK);
    let validate_body = parse_json_response(validate_valid_response).await;
    assert_eq!(validate_body["valid"], true);

    // 5. Validate invalid entity (missing required property)
    let validate_invalid_response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/validate/entity")
                .header("content-type", "application/json")
                .body(Body::from(
                    serde_json::to_vec(&json!({
                        "entity_type": "LLMAgent",
                        "properties": {
                            "id": "agent-001"
                            // Missing "name" and "model_name"
                        }
                    }))
                    .unwrap(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(validate_invalid_response.status(), StatusCode::OK);
    let invalid_body = parse_json_response(validate_invalid_response).await;
    assert_eq!(invalid_body["valid"], false);
    assert!(invalid_body["errors"].as_array().unwrap().len() > 0);

    // 6. Validate relation
    let validate_relation_response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/validate/relation")
                .header("content-type", "application/json")
                .body(Body::from(
                    serde_json::to_vec(&json!({
                        "relation_type": "executes",
                        "source_type": "LLMAgent",
                        "target_type": "Task"
                    }))
                    .unwrap(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(validate_relation_response.status(), StatusCode::OK);
    let relation_body = parse_json_response(validate_relation_response).await;
    assert_eq!(relation_body["valid"], true);

    // 7. Expand query
    let expand_response = app
        .clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/query/expand")
                .header("content-type", "application/json")
                .body(Body::from(
                    serde_json::to_vec(&json!({
                        "entity_type": "Agent",
                        "include_inferred_relations": true
                    }))
                    .unwrap(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(expand_response.status(), StatusCode::OK);
    let expand_body = parse_json_response(expand_response).await;
    assert_eq!(expand_body["original_type"], "Agent");
    assert!(expand_body["expanded_types"]
        .as_array()
        .unwrap()
        .contains(&json!("LLMAgent")));

    // 8. Get compatible relations
    let compatible_response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/query/compatible_relations")
                .header("content-type", "application/json")
                .body(Body::from(
                    serde_json::to_vec(&json!({
                        "source_type": "LLMAgent",
                        "target_type": "Task"
                    }))
                    .unwrap(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(compatible_response.status(), StatusCode::OK);
    let compatible_body = parse_json_response(compatible_response).await;
    assert!(compatible_body["compatible_relations"]
        .as_array()
        .unwrap()
        .contains(&json!("executes")));
}

#[tokio::test]
async fn test_get_nonexistent_type() {
    let app = create_test_app();

    // Upload a schema first
    let schema_yaml = r#"
namespace: "test://ontology"
version: "1.0.0"
entity_types:
  TestEntity:
    id: "TestEntity"
    label: "Test"
    parent: null
    properties: []
    constraints: []
    metadata: null
relation_types: {}
rules: []
"#;

    app.clone()
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/v1/ontology/schema")
                .header("content-type", "application/json")
                .body(Body::from(
                    serde_json::to_vec(&json!({
                        "schema": schema_yaml,
                        "format": "yaml"
                    }))
                    .unwrap(),
                ))
                .unwrap(),
        )
        .await
        .unwrap();

    // Try to get non-existent type
    let response = app
        .oneshot(
            Request::builder()
                .uri("/api/v1/ontology/types/NonExistent")
                .body(Body::empty())
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NOT_FOUND);
    let body = parse_json_response(response).await;
    assert_eq!(body["error"], "TypeNotFound");
}
