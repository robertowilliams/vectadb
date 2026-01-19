// Test SurrealDB CRUD operations to understand serialization/deserialization
use anyhow::Result;
use serde::{Deserialize, Serialize};
use surrealdb::engine::remote::http::Http;
use surrealdb::opt::auth::Root;
use surrealdb::sql::{Datetime, Thing};
use surrealdb::Surreal;
use std::collections::HashMap;

// Entity struct with Thing type for ID (matches SurrealDB's return format)
#[derive(Debug, Clone, Serialize, Deserialize)]
struct TestEntity {
    pub id: Thing,
    pub entity_type: String,
    pub properties: HashMap<String, serde_json::Value>,
    pub created_at: Datetime,
    pub updated_at: Datetime,
}

// Relation struct for testing
#[derive(Debug, Clone, Serialize, Deserialize)]
struct TestRelation {
    pub id: Thing,
    pub relation_type: String,
    pub source_id: String,
    pub target_id: String,
    pub properties: HashMap<String, serde_json::Value>,
    pub created_at: Datetime,
}

// Simplified Entity struct for production queries (with optional fields)
#[derive(Debug, Clone, Serialize, Deserialize)]
struct ProductionEntity {
    pub id: Thing,
    pub entity_type: String,
    pub properties: HashMap<String, serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding: Option<Vec<f32>>,
    pub created_at: Datetime,
    pub updated_at: Datetime,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, String>>,
}

#[tokio::test]
async fn test_entity_crud() -> Result<()> {
    println!("\n========================================");
    println!("Test 1: Basic Entity CRUD");
    println!("========================================\n");

    // Connect to SurrealDB
    let db = Surreal::new::<Http>("localhost:8000").await?;

    db.signin(Root {
        username: "root",
        password: "root",
    })
    .await?;

    db.use_ns("vectadb").use_db("test").await?;

    // Define test table
    db.query(
        "DEFINE TABLE IF NOT EXISTS test_entity SCHEMAFULL;
         DEFINE FIELD IF NOT EXISTS entity_type ON test_entity TYPE string;
         DEFINE FIELD IF NOT EXISTS properties ON test_entity FLEXIBLE TYPE object;
         DEFINE FIELD IF NOT EXISTS created_at ON test_entity TYPE datetime DEFAULT time::now();
         DEFINE FIELD IF NOT EXISTS updated_at ON test_entity TYPE datetime DEFAULT time::now();"
    )
    .await?;

    println!("✓ Table schema defined");

    // Test 1: Create using query with explicit time::now()
    println!("\nTest 1a: CREATE with explicit time::now()");
    let test_id = "test_001";

    // Use inline JSON instead of bind to avoid serialization issues
    db.query(format!(
        "CREATE test_entity:⟨{}⟩ SET entity_type = 'BedrockRequest', properties = {{'request_id': 'req-123'}}, created_at = time::now(), updated_at = time::now()",
        test_id
    ))
    .await?;

    println!("✓ Entity created with ID: {}", test_id);

    // Test 2: Read entity back using query SELECT
    println!("\nTest 1b: SELECT entity using query");
    let mut response = db
        .query(format!("SELECT * FROM test_entity:{}", test_id))
        .await?;

    // Use take with Value type
    match response.take::<Option<serde_json::Value>>(0) {
        Ok(Some(entity)) => {
            println!("✓ Entity retrieved:");
            println!("  {}", serde_json::to_string_pretty(&entity)?);

            // Check the id field type
            if let Some(id) = entity.get("id") {
                println!("\n  ID field type: {:?}", id);
            }
        }
        Ok(None) => println!("✗ Entity not found"),
        Err(e) => println!("✗ Query error: {:?}", e),
    }

    // Test 3: Try to deserialize into struct
    println!("\nTest 1c: Deserialize into TestEntity struct");
    match db.select::<Option<TestEntity>>(("test_entity", test_id)).await {
        Ok(Some(entity)) => {
            println!("✓ Successfully deserialized:");
            println!("  ID Thing: {:?}", entity.id);
            println!("  ID.tb: {}", entity.id.tb);
            println!("  ID.id: {:?}", entity.id.id);
            println!("  ID as string: {}", entity.id.to_string());
            println!("  Type: {}", entity.entity_type);
            println!("  Created: {:?}", entity.created_at);

            // Test converting Thing to just the ID part
            let id_only = entity.id.id.to_string();
            println!("  ID only (without table): {}", id_only);
        }
        Ok(None) => println!("✗ Entity not found"),
        Err(e) => println!("✗ Deserialization error: {:?}", e),
    }

    // Test 4: Create entity and return String ID (like API would do)
    println!("\nTest 1d: Create entity and return String ID");
    let new_id = "test_002";

    db.query(format!(
        "CREATE test_entity:⟨{}⟩ SET entity_type = 'ToolUse', properties = {{}}, created_at = time::now(), updated_at = time::now()",
        new_id
    ))
    .await?;
    println!("  Created entity with ID: {}", new_id);

    // Retrieve it and extract String ID
    if let Some(entity) = db.select::<Option<TestEntity>>(("test_entity", new_id)).await? {
        let id_string = entity.id.id.to_string();
        println!("  Retrieved entity, extracted ID: {}", id_string);
        println!("  Full Thing: {}", entity.id);
    }

    // Cleanup
    db.query("DELETE FROM test_entity").await?;
    println!("\n✓ Cleanup complete");

    Ok(())
}

#[tokio::test]
async fn test_thing_id_handling() -> Result<()> {
    println!("\n========================================");
    println!("Test 2: Thing ID Handling");
    println!("========================================\n");

    let db = Surreal::new::<Http>("localhost:8000").await?;
    db.signin(Root { username: "root", password: "root" }).await?;
    db.use_ns("vectadb").use_db("test").await?;

    // Create entity with special characters in ID
    println!("Test 2a: Create entity with special chars in ID");
    let special_id = "agent_with-special.chars_123";

    db.query(format!(
        "CREATE test_entity:⟨{}⟩ SET entity_type = 'Agent', properties = {{}}, created_at = time::now(), updated_at = time::now()",
        special_id
    ))
    .await?;

    println!("✓ Created entity with ID: {}", special_id);

    // Try to read it back
    println!("\nTest 2b: Read entity with special ID");
    let result: Option<TestEntity> = db
        .select(("test_entity", special_id))
        .await?;

    if let Some(entity) = result {
        println!("✓ Successfully retrieved entity");
        println!("  ID field: {}", entity.id);
        println!("  ID (string): {}", entity.id.id.to_string());
        println!("  Entity type: {}", entity.entity_type);
    }

    // Cleanup
    db.query("DELETE FROM test_entity").await?;

    Ok(())
}

#[tokio::test]
async fn test_relation_creation() -> Result<()> {
    println!("\n========================================");
    println!("Test 3: Relation Creation");
    println!("========================================\n");

    let db = Surreal::new::<Http>("localhost:8000").await?;
    db.signin(Root { username: "root", password: "root" }).await?;
    db.use_ns("vectadb").use_db("test").await?;

    // Define relation table
    db.query(
        "DEFINE TABLE IF NOT EXISTS test_relation SCHEMAFULL;
         DEFINE FIELD IF NOT EXISTS relation_type ON test_relation TYPE string;
         DEFINE FIELD IF NOT EXISTS source_id ON test_relation TYPE string;
         DEFINE FIELD IF NOT EXISTS target_id ON test_relation TYPE string;
         DEFINE FIELD IF NOT EXISTS properties ON test_relation FLEXIBLE TYPE object;
         DEFINE FIELD IF NOT EXISTS created_at ON test_relation TYPE datetime DEFAULT time::now();"
    )
    .await?;

    // Create two test entities
    println!("Creating source and target entities...");
    db.query("CREATE test_entity:source SET entity_type = 'BedrockRequest', properties = {}, created_at = time::now(), updated_at = time::now()").await?;
    db.query("CREATE test_entity:target SET entity_type = 'Agent', properties = {}, created_at = time::now(), updated_at = time::now()").await?;
    println!("✓ Entities created");

    // Create relation
    println!("\nCreating relation...");
    let relation_id = "rel_001";
    db.query(format!(
        "CREATE test_relation:⟨{}⟩ SET relation_type = 'MADE_BY', source_id = 'source', target_id = 'target', properties = {{}}, created_at = time::now()",
        relation_id
    ))
    .await?;
    println!("✓ Relation created");

    // Read relation back
    println!("\nReading relation...");
    let result: Option<TestRelation> = db
        .select(("test_relation", relation_id))
        .await?;

    if let Some(rel) = result {
        println!("✓ Relation retrieved:");
        println!("  ID: {}", rel.id);
        println!("  Type: {}", rel.relation_type);
        println!("  Source: {}", rel.source_id);
        println!("  Target: {}", rel.target_id);
        println!("  Created: {:?}", rel.created_at);
    }

    // Cleanup
    db.query("DELETE FROM test_entity").await?;
    db.query("DELETE FROM test_relation").await?;

    Ok(())
}

#[tokio::test]
async fn test_actual_vectadb_schema() -> Result<()> {
    println!("\n========================================");
    println!("Test 4: Real VectaDB Schema");
    println!("========================================\n");

    let db = Surreal::new::<Http>("localhost:8000").await?;
    db.signin(Root { username: "root", password: "root" }).await?;
    db.use_ns("vectadb").use_db("production").await?;

    // Count existing entities
    println!("Querying existing entities...");
    let mut response = db.query("SELECT count() FROM entity GROUP ALL").await?;
    let counts: Vec<serde_json::Value> = response.take(0)?;
    println!("✓ Total entities: {:?}", counts);

    // Try to get a BedrockRequest entity
    println!("\nQuerying BedrockRequest entities...");
    let mut response = db
        .query("SELECT * FROM entity WHERE entity_type = 'BedrockRequest' LIMIT 1")
        .await?;

    let entities: Vec<ProductionEntity> = response.take(0)?;
    if let Some(entity) = entities.first() {
        println!("✓ Found BedrockRequest:");
        println!("  ID Thing: {}", entity.id);
        println!("  ID (string): {}", entity.id.id.to_string());
        println!("  Entity type: {}", entity.entity_type);
        println!("  Properties: {} keys", entity.properties.len());
        println!("  Has embedding: {}", entity.embedding.is_some());

        // Try to use the ID to get the entity
        println!("\n  Attempting SELECT with ID...");
        let clean_id = entity.id.id.to_string();
        println!("  Clean ID: {}", clean_id);

        match db.select::<Option<ProductionEntity>>(("entity", clean_id.as_str())).await {
            Ok(Some(_e)) => println!("  ✓ Successfully retrieved entity using clean ID"),
            Ok(None) => println!("  ✗ Entity not found with clean ID"),
            Err(e) => println!("  ✗ Error: {:?}", e),
        }
    } else {
        println!("  No BedrockRequest entities found");
    }

    Ok(())
}
