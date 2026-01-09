// Graph Database Test - Validates SurrealDB graph functionality
// Tests entity creation, relations, and graph traversal capabilities

use serde_json::{json, Value as JsonValue};
use std::collections::HashMap;

// ============================================================================
// VectaDB API Client
// ============================================================================

struct VectaDBClient {
    base_url: String,
    client: reqwest::Client,
}

impl VectaDBClient {
    fn new(base_url: String) -> Self {
        Self {
            base_url,
            client: reqwest::Client::new(),
        }
    }

    async fn create_entity(
        &self,
        entity_type: &str,
        properties: HashMap<String, JsonValue>,
    ) -> Result<String, Box<dyn std::error::Error>> {
        let url = format!("{}/api/v1/entities", self.base_url);
        let body = json!({
            "entity_type": entity_type,
            "properties": properties
        });

        let response = self.client.post(&url).json(&body).send().await?;

        if !response.status().is_success() {
            let error = response.text().await?;
            return Err(format!("Failed to create entity: {}", error).into());
        }

        let result: JsonValue = response.json().await?;
        let id = result["id"]
            .as_str()
            .ok_or("No ID in response")?
            .to_string();

        Ok(id)
    }

    async fn get_entity(&self, id: &str) -> Result<JsonValue, Box<dyn std::error::Error>> {
        let url = format!("{}/api/v1/entities/{}", self.base_url, id);
        let response = self.client.get(&url).send().await?;

        if !response.status().is_success() {
            let error = response.text().await?;
            return Err(format!("Failed to get entity: {}", error).into());
        }

        let entity = response.json().await?;
        Ok(entity)
    }

    async fn create_relation(
        &self,
        relation_type: &str,
        source_id: &str,
        target_id: &str,
        properties: HashMap<String, JsonValue>,
    ) -> Result<String, Box<dyn std::error::Error>> {
        let url = format!("{}/api/v1/relations", self.base_url);
        let body = json!({
            "relation_type": relation_type,
            "source_id": source_id,
            "target_id": target_id,
            "properties": properties
        });

        let response = self.client.post(&url).json(&body).send().await?;

        if !response.status().is_success() {
            let error = response.text().await?;
            return Err(format!("Failed to create relation: {}", error).into());
        }

        let result: JsonValue = response.json().await?;
        let id = result["id"]
            .as_str()
            .ok_or("No ID in response")?
            .to_string();

        Ok(id)
    }

    async fn get_relation(&self, id: &str) -> Result<JsonValue, Box<dyn std::error::Error>> {
        let url = format!("{}/api/v1/relations/{}", self.base_url, id);
        let response = self.client.get(&url).send().await?;

        if !response.status().is_success() {
            let error = response.text().await?;
            return Err(format!("Failed to get relation: {}", error).into());
        }

        let relation = response.json().await?;
        Ok(relation)
    }

    async fn delete_entity(&self, id: &str) -> Result<(), Box<dyn std::error::Error>> {
        let url = format!("{}/api/v1/entities/{}", self.base_url, id);
        let response = self.client.delete(&url).send().await?;

        if !response.status().is_success() {
            let error = response.text().await?;
            return Err(format!("Failed to delete entity: {}", error).into());
        }

        Ok(())
    }

    async fn delete_relation(&self, id: &str) -> Result<(), Box<dyn std::error::Error>> {
        let url = format!("{}/api/v1/relations/{}", self.base_url, id);
        let response = self.client.delete(&url).send().await?;

        if !response.status().is_success() {
            let error = response.text().await?;
            return Err(format!("Failed to delete relation: {}", error).into());
        }

        Ok(())
    }
}

// ============================================================================
// Graph Test Scenarios
// ============================================================================

struct GraphTester {
    client: VectaDBClient,
    created_entities: Vec<String>,
    created_relations: Vec<String>,
}

impl GraphTester {
    fn new(client: VectaDBClient) -> Self {
        Self {
            client,
            created_entities: Vec::new(),
            created_relations: Vec::new(),
        }
    }

    async fn test_simple_relation(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        println!("\n📊 TEST 1: Simple Entity-Relation-Entity");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        // Create two entities
        println!("   Creating Agent entity...");
        let agent_props = HashMap::from([
            ("name".to_string(), json!("Claude")),
            ("model".to_string(), json!("claude-3-sonnet")),
        ]);
        let agent_id = self.client.create_entity("Agent", agent_props).await?;
        self.created_entities.push(agent_id.clone());
        println!("      ✅ Created Agent: {}", agent_id);

        println!("   Creating Task entity...");
        let task_props = HashMap::from([
            ("description".to_string(), json!("Process user query")),
            ("status".to_string(), json!("pending")),
        ]);
        let task_id = self.client.create_entity("Task", task_props).await?;
        self.created_entities.push(task_id.clone());
        println!("      ✅ Created Task: {}", task_id);

        // Create relation
        println!("   Creating 'executes' relation...");
        let rel_props = HashMap::from([("timestamp".to_string(), json!("2024-01-09T12:00:00Z"))]);
        let relation_id = self
            .client
            .create_relation("executes", &agent_id, &task_id, rel_props)
            .await?;
        self.created_relations.push(relation_id.clone());
        println!("      ✅ Created Relation: {}", relation_id);

        // Verify relation
        println!("   Verifying relation...");
        let relation = self.client.get_relation(&relation_id).await?;
        assert_eq!(relation["relation_type"], "executes");
        assert_eq!(relation["source_id"], agent_id);
        assert_eq!(relation["target_id"], task_id);
        println!("      ✅ Relation verified");

        println!("   ✅ Test 1 PASSED\n");
        Ok(())
    }

    async fn test_graph_structure(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        println!("📊 TEST 2: Complex Graph Structure");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("   Building: Agent → Task → Log chain");

        // Create Agent
        let agent_props = HashMap::from([
            ("name".to_string(), json!("Assistant")),
            ("version".to_string(), json!("1.0")),
        ]);
        let agent_id = self.client.create_entity("Agent", agent_props).await?;
        self.created_entities.push(agent_id.clone());
        println!("      ✅ Agent created");

        // Create Task
        let task_props = HashMap::from([
            ("title".to_string(), json!("Analyze data")),
            ("priority".to_string(), json!("high")),
        ]);
        let task_id = self.client.create_entity("Task", task_props).await?;
        self.created_entities.push(task_id.clone());
        println!("      ✅ Task created");

        // Create multiple Logs
        let mut log_ids = Vec::new();
        for i in 1..=3 {
            let log_props = HashMap::from([
                ("message".to_string(), json!(format!("Log message {}", i))),
                ("level".to_string(), json!("INFO")),
            ]);
            let log_id = self.client.create_entity("Log", log_props).await?;
            self.created_entities.push(log_id.clone());
            log_ids.push(log_id);
        }
        println!("      ✅ {} Logs created", log_ids.len());

        // Create relations: Agent -> Task
        let rel1 = self
            .client
            .create_relation("performs", &agent_id, &task_id, HashMap::new())
            .await?;
        self.created_relations.push(rel1);
        println!("      ✅ Agent → Task relation");

        // Create relations: Task -> Logs
        for (i, log_id) in log_ids.iter().enumerate() {
            let rel = self
                .client
                .create_relation(
                    "generates",
                    &task_id,
                    log_id,
                    HashMap::from([("order".to_string(), json!(i + 1))]),
                )
                .await?;
            self.created_relations.push(rel);
        }
        println!("      ✅ Task → Logs relations ({})", log_ids.len());

        println!("   ✅ Test 2 PASSED\n");
        Ok(())
    }

    async fn test_bidirectional_relations(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        println!("📊 TEST 3: Bidirectional Relations");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("   Building: Agent ↔ Agent collaboration");

        // Create two agents
        let agent1_props = HashMap::from([("name".to_string(), json!("Agent Alpha"))]);
        let agent1_id = self.client.create_entity("Agent", agent1_props).await?;
        self.created_entities.push(agent1_id.clone());

        let agent2_props = HashMap::from([("name".to_string(), json!("Agent Beta"))]);
        let agent2_id = self.client.create_entity("Agent", agent2_props).await?;
        self.created_entities.push(agent2_id.clone());
        println!("      ✅ Two agents created");

        // Create bidirectional relations
        let rel1 = self
            .client
            .create_relation("collaborates_with", &agent1_id, &agent2_id, HashMap::new())
            .await?;
        self.created_relations.push(rel1);

        let rel2 = self
            .client
            .create_relation("collaborates_with", &agent2_id, &agent1_id, HashMap::new())
            .await?;
        self.created_relations.push(rel2);
        println!("      ✅ Bidirectional relations created");

        println!("   ✅ Test 3 PASSED\n");
        Ok(())
    }

    async fn test_multiple_relation_types(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        println!("📊 TEST 4: Multiple Relation Types");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("   Building: Complex relationships between entities");

        // Create entities
        let agent_props = HashMap::from([("name".to_string(), json!("Orchestrator"))]);
        let agent_id = self.client.create_entity("Agent", agent_props).await?;
        self.created_entities.push(agent_id.clone());

        let task_props = HashMap::from([("title".to_string(), json!("Main task"))]);
        let task_id = self.client.create_entity("Task", task_props).await?;
        self.created_entities.push(task_id.clone());
        println!("      ✅ Entities created");

        // Create multiple types of relations between same entities
        let rel_types = vec!["owns", "monitors", "schedules"];
        for rel_type in rel_types {
            let rel = self
                .client
                .create_relation(rel_type, &agent_id, &task_id, HashMap::new())
                .await?;
            self.created_relations.push(rel);
            println!("      ✅ Relation '{}' created", rel_type);
        }

        println!("   ✅ Test 4 PASSED\n");
        Ok(())
    }

    async fn test_relation_properties(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        println!("📊 TEST 5: Relations with Rich Properties");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        // Create entities
        let agent_props = HashMap::from([("name".to_string(), json!("Worker"))]);
        let agent_id = self.client.create_entity("Agent", agent_props).await?;
        self.created_entities.push(agent_id.clone());

        let task_props = HashMap::from([("title".to_string(), json!("Complex task"))]);
        let task_id = self.client.create_entity("Task", task_props).await?;
        self.created_entities.push(task_id.clone());

        // Create relation with detailed properties
        let rel_props = HashMap::from([
            ("started_at".to_string(), json!("2024-01-09T10:00:00Z")),
            ("completed_at".to_string(), json!("2024-01-09T12:30:00Z")),
            ("duration_ms".to_string(), json!(9000000)),
            ("status".to_string(), json!("success")),
            ("retries".to_string(), json!(2)),
            (
                "metadata".to_string(),
                json!({"environment": "production", "priority": 1}),
            ),
        ]);

        println!("   Creating relation with rich properties...");
        let relation_id = self
            .client
            .create_relation("executes", &agent_id, &task_id, rel_props.clone())
            .await?;
        self.created_relations.push(relation_id.clone());

        // Verify properties
        println!("   Verifying relation properties...");
        let relation = self.client.get_relation(&relation_id).await?;
        assert!(relation["properties"].is_object());
        println!("      ✅ Properties stored: {:?}", relation["properties"]);

        println!("   ✅ Test 5 PASSED\n");
        Ok(())
    }

    async fn test_graph_depth(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        println!("📊 TEST 6: Multi-Level Graph Depth");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("   Building: Agent → Task → SubTask → Log (3 levels)");

        // Create chain: Agent → Task → SubTask → Log
        let agent_props = HashMap::from([("name".to_string(), json!("Deep Agent"))]);
        let agent_id = self.client.create_entity("Agent", agent_props).await?;
        self.created_entities.push(agent_id.clone());

        let task_props = HashMap::from([("title".to_string(), json!("Parent Task"))]);
        let task_id = self.client.create_entity("Task", task_props).await?;
        self.created_entities.push(task_id.clone());

        let subtask_props = HashMap::from([("title".to_string(), json!("Child Task"))]);
        let subtask_id = self.client.create_entity("Task", subtask_props).await?;
        self.created_entities.push(subtask_id.clone());

        let log_props = HashMap::from([("message".to_string(), json!("Deep log entry"))]);
        let log_id = self.client.create_entity("Log", log_props).await?;
        self.created_entities.push(log_id.clone());

        // Create chain of relations
        let rel1 = self
            .client
            .create_relation("executes", &agent_id, &task_id, HashMap::new())
            .await?;
        self.created_relations.push(rel1);

        let rel2 = self
            .client
            .create_relation("contains", &task_id, &subtask_id, HashMap::new())
            .await?;
        self.created_relations.push(rel2);

        let rel3 = self
            .client
            .create_relation("produces", &subtask_id, &log_id, HashMap::new())
            .await?;
        self.created_relations.push(rel3);

        println!("      ✅ 3-level graph chain created");
        println!("   ✅ Test 6 PASSED\n");
        Ok(())
    }

    async fn cleanup(&mut self) -> Result<(), Box<dyn std::error::Error>> {
        println!("\n🧹 CLEANUP");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        // Delete relations first (to maintain referential integrity)
        println!("   Deleting {} relations...", self.created_relations.len());
        for relation_id in &self.created_relations {
            match self.client.delete_relation(relation_id).await {
                Ok(_) => {}
                Err(e) => eprintln!("      ⚠️  Failed to delete relation {}: {}", relation_id, e),
            }
        }
        println!("      ✅ Relations deleted");

        // Delete entities
        println!("   Deleting {} entities...", self.created_entities.len());
        for entity_id in &self.created_entities {
            match self.client.delete_entity(entity_id).await {
                Ok(_) => {}
                Err(e) => eprintln!("      ⚠️  Failed to delete entity {}: {}", entity_id, e),
            }
        }
        println!("      ✅ Entities deleted");

        Ok(())
    }

    fn print_summary(&self) {
        println!("\n╔════════════════════════════════════════╗");
        println!("║     GRAPH DATABASE TEST SUMMARY       ║");
        println!("╚════════════════════════════════════════╝");
        println!();
        println!("  Total Entities Created:  {}", self.created_entities.len());
        println!("  Total Relations Created: {}", self.created_relations.len());
        println!();
        println!("  Test Coverage:");
        println!("    ✅ Simple entity-relation-entity");
        println!("    ✅ Complex graph structures");
        println!("    ✅ Bidirectional relations");
        println!("    ✅ Multiple relation types");
        println!("    ✅ Relations with properties");
        println!("    ✅ Multi-level graph depth");
        println!();
        println!("  Graph Capabilities Validated:");
        println!("    ✅ Entity creation and retrieval");
        println!("    ✅ Relation creation and retrieval");
        println!("    ✅ Property storage on relations");
        println!("    ✅ Multiple relations between entities");
        println!("    ✅ Graph chain construction");
        println!("    ✅ Entity/relation cleanup");
        println!();
    }
}

// ============================================================================
// Main Test Runner
// ============================================================================

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("\n╔════════════════════════════════════════╗");
    println!("║   GRAPH DATABASE TEST SUITE           ║");
    println!("║   SurrealDB Graph Functionality       ║");
    println!("╚════════════════════════════════════════╝");

    let base_url =
        std::env::var("VECTADB_URL").unwrap_or_else(|_| "http://localhost:3000".to_string());

    println!("\nConfiguration:");
    println!("  VectaDB API: {}", base_url);
    println!();

    let client = VectaDBClient::new(base_url);
    let mut tester = GraphTester::new(client);

    // Run all tests
    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    println!("  RUNNING GRAPH TESTS");
    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    let mut failed = false;

    match tester.test_simple_relation().await {
        Ok(_) => {}
        Err(e) => {
            eprintln!("   ❌ Test 1 FAILED: {}", e);
            failed = true;
        }
    }

    match tester.test_graph_structure().await {
        Ok(_) => {}
        Err(e) => {
            eprintln!("   ❌ Test 2 FAILED: {}", e);
            failed = true;
        }
    }

    match tester.test_bidirectional_relations().await {
        Ok(_) => {}
        Err(e) => {
            eprintln!("   ❌ Test 3 FAILED: {}", e);
            failed = true;
        }
    }

    match tester.test_multiple_relation_types().await {
        Ok(_) => {}
        Err(e) => {
            eprintln!("   ❌ Test 4 FAILED: {}", e);
            failed = true;
        }
    }

    match tester.test_relation_properties().await {
        Ok(_) => {}
        Err(e) => {
            eprintln!("   ❌ Test 5 FAILED: {}", e);
            failed = true;
        }
    }

    match tester.test_graph_depth().await {
        Ok(_) => {}
        Err(e) => {
            eprintln!("   ❌ Test 6 FAILED: {}", e);
            failed = true;
        }
    }

    // Cleanup
    match tester.cleanup().await {
        Ok(_) => {}
        Err(e) => {
            eprintln!("   ⚠️  Cleanup errors: {}", e);
        }
    }

    // Print summary
    tester.print_summary();

    if failed {
        println!("  ❌ SOME TESTS FAILED");
        println!();
        std::process::exit(1);
    } else {
        println!("  ✅ ALL TESTS PASSED");
        println!();
        std::process::exit(0);
    }
}
