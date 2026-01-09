// Bedrock Graph Ingestion - Ingest AWS Bedrock logs as a graph structure
// Creates nodes for each event and edges for relationships between events

use serde::{Deserialize, Serialize};
use serde_json::{json, Value as JsonValue};
use std::collections::HashMap;

// ============================================================================
// Bedrock Log Models (same as bedrock_test.rs)
// ============================================================================

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct BedrockLogEntry {
    timestamp: String,
    account_id: String,
    region: String,
    request_id: String,
    operation: String,
    model_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    error_code: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    input: Option<Input>,
    #[serde(skip_serializing_if = "Option::is_none")]
    output: Option<Output>,
    #[serde(skip_serializing_if = "Option::is_none")]
    inference_region: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Input {
    input_body_json: InputBody,
    input_token_count: u32,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct InputBody {
    messages: Vec<Message>,
    #[serde(skip_serializing_if = "Option::is_none")]
    system: Option<Vec<SystemMessage>>,
}

#[derive(Debug, Deserialize, Serialize)]
struct SystemMessage {
    text: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct Message {
    role: String,
    content: Vec<Content>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Content {
    #[serde(skip_serializing_if = "Option::is_none")]
    text: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_use: Option<ToolUse>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_result: Option<ToolResult>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct ToolUse {
    tool_use_id: String,
    name: String,
    input: JsonValue,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct ToolResult {
    tool_use_id: String,
    content: Vec<ToolResultContent>,
}

#[derive(Debug, Deserialize, Serialize)]
struct ToolResultContent {
    text: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Output {
    output_body_json: OutputBody,
    output_token_count: u32,
}

#[derive(Debug, Deserialize, Serialize)]
struct OutputBody {
    output: OutputMessage,
    stop_reason: String,
    metrics: Metrics,
    usage: Usage,
}

#[derive(Debug, Deserialize, Serialize)]
struct OutputMessage {
    message: Message,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Metrics {
    latency_ms: u64,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Usage {
    input_tokens: u32,
    output_tokens: u32,
    total_tokens: u32,
}

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
}

// ============================================================================
// Graph Ingestion Engine
// ============================================================================

struct GraphIngestionEngine {
    client: VectaDBClient,
    entity_map: HashMap<String, String>, // Maps logical IDs to entity IDs
    stats: IngestionStats,
}

#[derive(Debug, Default)]
struct IngestionStats {
    requests_processed: usize,
    requests_created: usize,
    responses_created: usize,
    user_queries_created: usize,
    tool_calls_created: usize,
    tool_results_created: usize,
    errors_created: usize,
    relations_created: usize,
}

impl GraphIngestionEngine {
    fn new(client: VectaDBClient) -> Self {
        Self {
            client,
            entity_map: HashMap::new(),
            stats: IngestionStats::default(),
        }
    }

    async fn ingest_log_file(
        &mut self,
        file_path: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        println!("\n📊 Reading Bedrock log file: {}", file_path);
        let contents = std::fs::read_to_string(file_path)?;
        let log_entries: Vec<BedrockLogEntry> = serde_json::from_str(&contents)?;

        println!("📦 Found {} log entries", log_entries.len());
        println!("\n🔄 Starting graph ingestion...\n");

        for (idx, entry) in log_entries.iter().enumerate() {
            self.stats.requests_processed += 1;

            match self.process_entry(entry, idx).await {
                Ok(_) => {
                    if idx % 5 == 0 {
                        println!("   ✅ Processed entry {}/{}", idx + 1, log_entries.len());
                    }
                }
                Err(e) => {
                    eprintln!("   ⚠️  Error processing entry {}: {}", idx, e);
                }
            }
        }

        println!("\n✅ Graph ingestion complete!\n");
        Ok(())
    }

    async fn process_entry(
        &mut self,
        entry: &BedrockLogEntry,
        _idx: usize,
    ) -> Result<(), Box<dyn std::error::Error>> {
        // Skip throttling errors - they don't have useful graph structure
        if let Some(error_code) = &entry.error_code {
            if error_code == "ThrottlingException" {
                return Ok(());
            }
        }

        // Create Request node
        let request_id = self.create_request_node(entry).await?;
        self.stats.requests_created += 1;

        // Process input messages and create graph
        if let Some(input) = &entry.input {
            self.process_input_messages(input, &request_id).await?;
        }

        // Process output and create response node
        if let Some(output) = &entry.output {
            let response_id = self.create_response_node(entry, output, &request_id).await?;
            self.stats.responses_created += 1;

            // Create relation: Request → Response
            self.client
                .create_relation("produces", &request_id, &response_id, HashMap::new())
                .await?;
            self.stats.relations_created += 1;

            // Process output message content
            self.process_output_message(output, &response_id).await?;
        }

        Ok(())
    }

    async fn create_request_node(
        &mut self,
        entry: &BedrockLogEntry,
    ) -> Result<String, Box<dyn std::error::Error>> {
        let mut props = HashMap::new();
        props.insert("request_id".to_string(), json!(entry.request_id));
        props.insert("timestamp".to_string(), json!(entry.timestamp));
        props.insert("model_id".to_string(), json!(entry.model_id));
        props.insert("operation".to_string(), json!(entry.operation));
        props.insert("region".to_string(), json!(entry.region));

        if let Some(input) = &entry.input {
            props.insert("input_tokens".to_string(), json!(input.input_token_count));
        }

        let entity_id = self.client.create_entity("Request", props).await?;

        // Store mapping
        self.entity_map
            .insert(format!("request:{}", entry.request_id), entity_id.clone());

        Ok(entity_id)
    }

    async fn create_response_node(
        &mut self,
        entry: &BedrockLogEntry,
        output: &Output,
        request_id: &str,
    ) -> Result<String, Box<dyn std::error::Error>> {
        let mut props = HashMap::new();
        props.insert("request_id".to_string(), json!(entry.request_id));
        props.insert("timestamp".to_string(), json!(entry.timestamp));
        props.insert("stop_reason".to_string(), json!(output.output_body_json.stop_reason));
        props.insert("latency_ms".to_string(), json!(output.output_body_json.metrics.latency_ms));
        props.insert("input_tokens".to_string(), json!(output.output_body_json.usage.input_tokens));
        props.insert("output_tokens".to_string(), json!(output.output_body_json.usage.output_tokens));
        props.insert("total_tokens".to_string(), json!(output.output_body_json.usage.total_tokens));

        if let Some(inference_region) = &entry.inference_region {
            props.insert("inference_region".to_string(), json!(inference_region));
        }

        let entity_id = self.client.create_entity("Response", props).await?;

        // Store mapping
        self.entity_map
            .insert(format!("response:{}:{}", entry.request_id, request_id), entity_id.clone());

        Ok(entity_id)
    }

    async fn process_input_messages(
        &mut self,
        input: &Input,
        request_id: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        for message in &input.input_body_json.messages {
            match message.role.as_str() {
                "user" => {
                    self.process_user_message(message, request_id).await?;
                }
                "assistant" => {
                    // Assistant messages in input are from conversation history
                    // We can skip these or process them as context
                }
                _ => {}
            }
        }
        Ok(())
    }

    async fn process_user_message(
        &mut self,
        message: &Message,
        request_id: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        for content in &message.content {
            // Create UserQuery node for text
            if let Some(text) = &content.text {
                let mut props = HashMap::new();
                props.insert("query".to_string(), json!(text));
                props.insert("text_length".to_string(), json!(text.len()));

                let query_id = self.client.create_entity("UserQuery", props).await?;
                self.stats.user_queries_created += 1;

                // Create relation: UserQuery → Request
                self.client
                    .create_relation("triggers", &query_id, request_id, HashMap::new())
                    .await?;
                self.stats.relations_created += 1;
            }

            // Create ToolResult node
            if let Some(tool_result) = &content.tool_result {
                let result_text = tool_result.content.iter()
                    .map(|c| c.text.clone())
                    .collect::<Vec<_>>()
                    .join(" ");

                let is_error = result_text.contains("error") || result_text.contains("Error");

                let mut props = HashMap::new();
                props.insert("tool_use_id".to_string(), json!(tool_result.tool_use_id));
                props.insert("result".to_string(), json!(result_text));
                props.insert("is_error".to_string(), json!(is_error));

                let result_id = self.client.create_entity("ToolResult", props).await?;
                self.stats.tool_results_created += 1;

                // Store mapping for linking to tool calls
                self.entity_map
                    .insert(format!("tool_result:{}", tool_result.tool_use_id), result_id.clone());

                // Try to find the corresponding tool call and create relation
                if let Some(tool_call_id) = self.entity_map.get(&format!("tool_call:{}", tool_result.tool_use_id)) {
                    self.client
                        .create_relation("returns", tool_call_id, &result_id, HashMap::new())
                        .await?;
                    self.stats.relations_created += 1;
                }

                // Create relation: ToolResult → Request (provides context)
                self.client
                    .create_relation("provides_context_to", &result_id, request_id, HashMap::new())
                    .await?;
                self.stats.relations_created += 1;

                // If error, create Error node
                if is_error {
                    let mut error_props = HashMap::new();
                    error_props.insert("error_message".to_string(), json!(result_text));
                    error_props.insert("source".to_string(), json!("tool_execution"));

                    let error_id = self.client.create_entity("Error", error_props).await?;
                    self.stats.errors_created += 1;

                    // Create relation: ToolResult → Error
                    self.client
                        .create_relation("contains", &result_id, &error_id, HashMap::new())
                        .await?;
                    self.stats.relations_created += 1;
                }
            }
        }
        Ok(())
    }

    async fn process_output_message(
        &mut self,
        output: &Output,
        response_id: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let message = &output.output_body_json.output.message;

        for content in &message.content {
            // Create AssistantResponse node for text
            if let Some(text) = &content.text {
                let mut props = HashMap::new();
                props.insert("text".to_string(), json!(text));
                props.insert("text_length".to_string(), json!(text.len()));

                let response_text_id = self.client.create_entity("AssistantResponse", props).await?;

                // Create relation: Response → AssistantResponse
                self.client
                    .create_relation("contains", response_id, &response_text_id, HashMap::new())
                    .await?;
                self.stats.relations_created += 1;
            }

            // Create ToolCall node
            if let Some(tool_use) = &content.tool_use {
                let mut props = HashMap::new();
                props.insert("tool_use_id".to_string(), json!(tool_use.tool_use_id));
                props.insert("tool_name".to_string(), json!(tool_use.name));
                props.insert("tool_input".to_string(), json!(tool_use.input));

                let tool_call_id = self.client.create_entity("ToolCall", props).await?;
                self.stats.tool_calls_created += 1;

                // Store mapping for linking to tool results later
                self.entity_map
                    .insert(format!("tool_call:{}", tool_use.tool_use_id), tool_call_id.clone());

                // Create relation: Response → ToolCall
                self.client
                    .create_relation("invokes", response_id, &tool_call_id, HashMap::new())
                    .await?;
                self.stats.relations_created += 1;

                // If we already saw the result, link it now
                if let Some(result_id) = self.entity_map.get(&format!("tool_result:{}", tool_use.tool_use_id)) {
                    self.client
                        .create_relation("returns", &tool_call_id, result_id, HashMap::new())
                        .await?;
                    self.stats.relations_created += 1;
                }
            }
        }
        Ok(())
    }

    fn print_stats(&self) {
        println!("╔════════════════════════════════════════╗");
        println!("║     GRAPH INGESTION SUMMARY           ║");
        println!("╚════════════════════════════════════════╝");
        println!();
        println!("  Requests Processed: {}", self.stats.requests_processed);
        println!();
        println!("  Nodes Created:");
        println!("    - Requests:           {}", self.stats.requests_created);
        println!("    - Responses:          {}", self.stats.responses_created);
        println!("    - User Queries:       {}", self.stats.user_queries_created);
        println!("    - Tool Calls:         {}", self.stats.tool_calls_created);
        println!("    - Tool Results:       {}", self.stats.tool_results_created);
        println!("    - Errors:             {}", self.stats.errors_created);
        println!("    ─────────────────────────────────────");
        println!("    Total Nodes:          {}",
            self.stats.requests_created +
            self.stats.responses_created +
            self.stats.user_queries_created +
            self.stats.tool_calls_created +
            self.stats.tool_results_created +
            self.stats.errors_created
        );
        println!();
        println!("  Edges Created:        {}", self.stats.relations_created);
        println!();
        println!("  Graph Structure:");
        println!("    UserQuery → triggers → Request");
        println!("    Request → produces → Response");
        println!("    Response → contains → AssistantResponse");
        println!("    Response → invokes → ToolCall");
        println!("    ToolCall → returns → ToolResult");
        println!("    ToolResult → provides_context_to → Request");
        println!("    ToolResult → contains → Error");
        println!();
    }
}

// ============================================================================
// Main
// ============================================================================

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("\n╔════════════════════════════════════════╗");
    println!("║   BEDROCK GRAPH INGESTION             ║");
    println!("║   AWS Bedrock Logs → Graph Database   ║");
    println!("╚════════════════════════════════════════╝");

    let base_url =
        std::env::var("VECTADB_URL").unwrap_or_else(|_| "http://localhost:3000".to_string());

    println!("\nConfiguration:");
    println!("  VectaDB API: {}", base_url);
    println!();

    // Check VectaDB health
    let client = reqwest::Client::new();
    match client.get(format!("{}/health", base_url)).send().await {
        Ok(response) if response.status().is_success() => {
            println!("✅ VectaDB is healthy");
        }
        _ => {
            eprintln!("❌ VectaDB is not responding at {}", base_url);
            eprintln!("   Please start VectaDB first:");
            eprintln!("   cd vectadb && cargo run --release");
            std::process::exit(1);
        }
    }

    let vectadb_client = VectaDBClient::new(base_url);
    let mut engine = GraphIngestionEngine::new(vectadb_client);

    // Ingest the log file
    let log_file = "./test/bedrock_chain_of_thought_logs.json";
    match engine.ingest_log_file(log_file).await {
        Ok(_) => {
            engine.print_stats();
            println!("✨ Graph ingestion completed successfully!\n");
            std::process::exit(0);
        }
        Err(e) => {
            eprintln!("\n❌ Graph ingestion failed: {}", e);
            std::process::exit(1);
        }
    }
}
