// Comprehensive test for VectaDB using AWS Bedrock chain-of-thought logs
// This test demonstrates VectaDB's observability capabilities for LLM agents

use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

// ============================================================================
// Bedrock Log Models
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
    identity: Option<Identity>,
    #[serde(skip_serializing_if = "Option::is_none")]
    input: Option<Input>,
    #[serde(skip_serializing_if = "Option::is_none")]
    output: Option<Output>,
    #[serde(skip_serializing_if = "Option::is_none")]
    inference_region: Option<String>,
    schema_type: String,
    schema_version: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct Identity {
    arn: String,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Input {
    input_content_type: String,
    input_body_json: InputBody,
    input_token_count: u32,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct InputBody {
    messages: Vec<Message>,
    #[serde(skip_serializing_if = "Option::is_none")]
    system: Option<Vec<SystemMessage>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    inference_config: Option<InferenceConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tool_config: Option<ToolConfig>,
}

#[derive(Debug, Deserialize, Serialize)]
struct SystemMessage {
    text: String,
}

#[derive(Debug, Deserialize, Serialize)]
struct InferenceConfig {
    temperature: f64,
}

#[derive(Debug, Deserialize, Serialize)]
struct ToolConfig {
    tools: Vec<Tool>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct Tool {
    tool_spec: ToolSpec,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct ToolSpec {
    name: String,
    description: String,
    input_schema: JsonValue,
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
    #[serde(rename = "type")]
    tool_type: String,
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
    output_content_type: String,
    output_body_json: OutputBody,
    output_token_count: u32,
}

#[derive(Debug, Deserialize, Serialize)]
struct OutputBody {
    output: OutputMessage,
    #[serde(rename = "stopReason")]
    stop_reason: String,
    metrics: Metrics,
    usage: Usage,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
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

    async fn health_check(&self) -> Result<JsonValue, Box<dyn std::error::Error>> {
        let url = format!("{}/health", self.base_url);
        let response = self.client.get(&url).send().await?;
        let body = response.json::<JsonValue>().await?;
        Ok(body)
    }

    async fn create_log(
        &self,
        agent_id: &str,
        message: &str,
        level: &str,
        metadata: JsonValue,
    ) -> Result<JsonValue, Box<dyn std::error::Error>> {
        let url = format!("{}/api/logs", self.base_url);
        let body = serde_json::json!({
            "agent_id": agent_id,
            "level": level,
            "message": message,
            "metadata": metadata
        });

        let response = self.client.post(&url).json(&body).send().await?;
        let result = response.json::<JsonValue>().await?;
        Ok(result)
    }

    async fn query_logs(
        &self,
        query: &str,
        limit: usize,
    ) -> Result<Vec<JsonValue>, Box<dyn std::error::Error>> {
        let url = format!("{}/api/logs/search", self.base_url);
        let body = serde_json::json!({
            "query": query,
            "limit": limit
        });

        let response = self.client.post(&url).json(&body).send().await?;
        let result = response.json::<Vec<JsonValue>>().await?;
        Ok(result)
    }

    async fn get_analytics(
        &self,
        agent_id: Option<&str>,
    ) -> Result<JsonValue, Box<dyn std::error::Error>> {
        let mut url = format!("{}/api/analytics", self.base_url);
        if let Some(agent_id) = agent_id {
            url = format!("{}?agent_id={}", url, agent_id);
        }

        let response = self.client.get(&url).send().await?;
        let result = response.json::<JsonValue>().await?;
        Ok(result)
    }
}

// ============================================================================
// Bedrock Log Processor
// ============================================================================

struct BedrockLogProcessor {
    client: VectaDBClient,
}

impl BedrockLogProcessor {
    fn new(client: VectaDBClient) -> Self {
        Self { client }
    }

    async fn process_log_file(
        &self,
        file_path: &str,
    ) -> Result<ProcessingStats, Box<dyn std::error::Error>> {
        let contents = std::fs::read_to_string(file_path)?;
        let log_entries: Vec<BedrockLogEntry> = serde_json::from_str(&contents)?;

        let mut stats = ProcessingStats::default();
        println!("📊 Processing {} Bedrock log entries...", log_entries.len());

        for (idx, entry) in log_entries.iter().enumerate() {
            match self.process_entry(entry, idx).await {
                Ok(entry_stats) => {
                    stats.merge(&entry_stats);
                }
                Err(e) => {
                    eprintln!("❌ Error processing entry {}: {}", idx, e);
                    stats.errors += 1;
                }
            }
        }

        Ok(stats)
    }

    async fn process_entry(
        &self,
        entry: &BedrockLogEntry,
        idx: usize,
    ) -> Result<ProcessingStats, Box<dyn std::error::Error>> {
        let mut stats = ProcessingStats::default();
        let agent_id = "bedrock_claude_haiku_4_5";

        // Check for throttling errors
        if let Some(error_code) = &entry.error_code {
            if error_code == "ThrottlingException" {
                stats.throttling_errors += 1;
                let message = format!(
                    "Request throttled: {} in region {}",
                    entry.request_id, entry.region
                );
                self.create_log_entry(
                    agent_id,
                    &message,
                    "WARNING",
                    serde_json::json!({
                        "error_code": error_code,
                        "request_id": entry.request_id,
                        "region": entry.region,
                        "inference_region": entry.inference_region,
                        "timestamp": entry.timestamp,
                        "operation": entry.operation,
                        "model_id": entry.model_id
                    }),
                )
                .await?;
                return Ok(stats);
            }
        }

        // Process input messages
        if let Some(input) = &entry.input {
            stats.requests += 1;

            // Extract user messages
            for message in &input.input_body_json.messages {
                if message.role == "user" {
                    for content in &message.content {
                        if let Some(text) = &content.text {
                            stats.user_messages += 1;
                            self.create_log_entry(
                                agent_id,
                                &format!("User query: {}", text),
                                "INFO",
                                serde_json::json!({
                                    "request_id": entry.request_id,
                                    "timestamp": entry.timestamp,
                                    "message_type": "user_query",
                                    "query": text,
                                    "model_id": entry.model_id,
                                    "region": entry.region
                                }),
                            )
                            .await?;
                        }
                    }
                }

                // Extract tool results
                if message.role == "user" {
                    for content in &message.content {
                        if let Some(tool_result) = &content.tool_result {
                            stats.tool_results += 1;
                            let result_text = tool_result.content.iter()
                                .map(|c| c.text.clone())
                                .collect::<Vec<_>>()
                                .join(" ");

                            let is_error = result_text.contains("error") || result_text.contains("Error");
                            if is_error {
                                stats.tool_errors += 1;
                            }

                            self.create_log_entry(
                                agent_id,
                                &format!("Tool result ({}): {}", tool_result.tool_use_id, result_text),
                                if is_error { "ERROR" } else { "INFO" },
                                serde_json::json!({
                                    "request_id": entry.request_id,
                                    "timestamp": entry.timestamp,
                                    "message_type": "tool_result",
                                    "tool_use_id": tool_result.tool_use_id,
                                    "result": result_text,
                                    "is_error": is_error
                                }),
                            )
                            .await?;
                        }
                    }
                }
            }

            // Extract system prompt
            if let Some(system) = &input.input_body_json.system {
                for sys_msg in system {
                    stats.system_prompts += 1;
                    self.create_log_entry(
                        agent_id,
                        &format!("System prompt: {}", &sys_msg.text[..sys_msg.text.len().min(200)]),
                        "INFO",
                        serde_json::json!({
                            "request_id": entry.request_id,
                            "timestamp": entry.timestamp,
                            "message_type": "system_prompt",
                            "full_text": sys_msg.text
                        }),
                    )
                    .await?;
                }
            }

            // Extract tool configurations
            if let Some(tool_config) = &input.input_body_json.tool_config {
                stats.tool_configs += 1;
                let tool_names: Vec<String> = tool_config.tools.iter()
                    .map(|t| t.tool_spec.name.clone())
                    .collect();

                self.create_log_entry(
                    agent_id,
                    &format!("Available tools: {}", tool_names.join(", ")),
                    "INFO",
                    serde_json::json!({
                        "request_id": entry.request_id,
                        "timestamp": entry.timestamp,
                        "message_type": "tool_config",
                        "tools": tool_names,
                        "tool_count": tool_names.len()
                    }),
                )
                .await?;
            }
        }

        // Process output messages
        if let Some(output) = &entry.output {
            stats.responses += 1;

            let message = &output.output_body_json.output.message;

            // Extract assistant responses
            if message.role == "assistant" {
                for content in &message.content {
                    if let Some(text) = &content.text {
                        stats.assistant_messages += 1;
                        self.create_log_entry(
                            agent_id,
                            &format!("Assistant response: {}", text),
                            "INFO",
                            serde_json::json!({
                                "request_id": entry.request_id,
                                "timestamp": entry.timestamp,
                                "message_type": "assistant_response",
                                "response": text,
                                "stop_reason": output.output_body_json.stop_reason,
                                "latency_ms": output.output_body_json.metrics.latency_ms,
                                "input_tokens": output.output_body_json.usage.input_tokens,
                                "output_tokens": output.output_body_json.usage.output_tokens,
                                "total_tokens": output.output_body_json.usage.total_tokens
                            }),
                        )
                        .await?;
                    }

                    // Extract tool calls
                    if let Some(tool_use) = &content.tool_use {
                        stats.tool_calls += 1;
                        self.create_log_entry(
                            agent_id,
                            &format!("Tool call: {} ({})", tool_use.name, tool_use.tool_use_id),
                            "INFO",
                            serde_json::json!({
                                "request_id": entry.request_id,
                                "timestamp": entry.timestamp,
                                "message_type": "tool_call",
                                "tool_name": tool_use.name,
                                "tool_use_id": tool_use.tool_use_id,
                                "tool_input": tool_use.input
                            }),
                        )
                        .await?;
                    }
                }
            }
        }

        if idx % 5 == 0 {
            println!("✅ Processed entry {}", idx);
        }

        Ok(stats)
    }

    async fn create_log_entry(
        &self,
        agent_id: &str,
        message: &str,
        level: &str,
        metadata: JsonValue,
    ) -> Result<(), Box<dyn std::error::Error>> {
        match self.client.create_log(agent_id, message, level, metadata).await {
            Ok(_) => Ok(()),
            Err(e) => {
                eprintln!("⚠️  Failed to create log entry: {}", e);
                Ok(()) // Don't fail the entire process
            }
        }
    }
}

#[derive(Debug, Default)]
struct ProcessingStats {
    requests: usize,
    responses: usize,
    user_messages: usize,
    assistant_messages: usize,
    tool_calls: usize,
    tool_results: usize,
    tool_errors: usize,
    tool_configs: usize,
    system_prompts: usize,
    throttling_errors: usize,
    errors: usize,
}

impl ProcessingStats {
    fn merge(&mut self, other: &ProcessingStats) {
        self.requests += other.requests;
        self.responses += other.responses;
        self.user_messages += other.user_messages;
        self.assistant_messages += other.assistant_messages;
        self.tool_calls += other.tool_calls;
        self.tool_results += other.tool_results;
        self.tool_errors += other.tool_errors;
        self.tool_configs += other.tool_configs;
        self.system_prompts += other.system_prompts;
        self.throttling_errors += other.throttling_errors;
        self.errors += other.errors;
    }

    fn print_summary(&self) {
        println!("\n📈 PROCESSING SUMMARY");
        println!("═══════════════════════════════════════");
        println!("Requests:             {}", self.requests);
        println!("Responses:            {}", self.responses);
        println!("User Messages:        {}", self.user_messages);
        println!("Assistant Messages:   {}", self.assistant_messages);
        println!("Tool Calls:           {}", self.tool_calls);
        println!("Tool Results:         {}", self.tool_results);
        println!("Tool Errors:          {}", self.tool_errors);
        println!("Tool Configurations:  {}", self.tool_configs);
        println!("System Prompts:       {}", self.system_prompts);
        println!("Throttling Errors:    {}", self.throttling_errors);
        println!("Processing Errors:    {}", self.errors);
        println!("═══════════════════════════════════════\n");
    }
}

// ============================================================================
// Test Queries
// ============================================================================

async fn run_test_queries(client: &VectaDBClient) -> Result<(), Box<dyn std::error::Error>> {
    println!("\n🔍 RUNNING TEST QUERIES");
    println!("═══════════════════════════════════════\n");

    // Query 1: Find error messages
    println!("1️⃣  Query: Find all error-related logs");
    let results = client.query_logs("error internal tool result", 10).await?;
    println!("   Found {} error-related logs", results.len());
    if !results.is_empty() {
        println!("   Sample: {}", results[0]);
    }

    // Query 2: Find throttling issues
    println!("\n2️⃣  Query: Find throttling errors");
    let results = client.query_logs("throttling exception rate limit", 10).await?;
    println!("   Found {} throttling errors", results.len());

    // Query 3: Find tool calls
    println!("\n3️⃣  Query: Find tool calls");
    let results = client.query_logs("tool call searchImmunization getPatient", 10).await?;
    println!("   Found {} tool call logs", results.len());

    // Query 4: Find patient-related queries
    println!("\n4️⃣  Query: Find patient PAT001 queries");
    let results = client.query_logs("patient PAT001 immunization", 10).await?;
    println!("   Found {} patient-related logs", results.len());

    // Query 5: Analyze latency patterns
    println!("\n5️⃣  Query: Find high latency responses");
    let results = client.query_logs("latency response time", 10).await?;
    println!("   Found {} latency-related logs", results.len());

    println!("\n═══════════════════════════════════════\n");
    Ok(())
}

// ============================================================================
// Main Test Runner
// ============================================================================

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("\n🚀 VectaDB Bedrock Log Test Suite");
    println!("═══════════════════════════════════════\n");

    // Initialize client
    let base_url = std::env::var("VECTADB_URL")
        .unwrap_or_else(|_| "http://localhost:3000".to_string());
    let client = VectaDBClient::new(base_url.clone());

    // Health check
    println!("🏥 Checking VectaDB health...");
    match client.health_check().await {
        Ok(health) => {
            println!("✅ VectaDB is healthy: {}", health);
        }
        Err(e) => {
            eprintln!("❌ VectaDB health check failed: {}", e);
            eprintln!("   Make sure VectaDB is running on {}", base_url);
            std::process::exit(1);
        }
    }

    // Process Bedrock logs
    let log_file = "./test/bedrock_chain_of_thought_logs.json";
    println!("\n📂 Loading Bedrock logs from: {}", log_file);

    let processor = BedrockLogProcessor::new(client);
    match processor.process_log_file(log_file).await {
        Ok(stats) => {
            stats.print_summary();
        }
        Err(e) => {
            eprintln!("❌ Failed to process log file: {}", e);
            std::process::exit(1);
        }
    }

    // Run test queries
    run_test_queries(&processor.client).await?;

    // Get analytics
    println!("\n📊 RETRIEVING ANALYTICS");
    println!("═══════════════════════════════════════\n");
    match processor.client.get_analytics(Some("bedrock_claude_haiku_4_5")).await {
        Ok(analytics) => {
            println!("Analytics: {:#}", analytics);
        }
        Err(e) => {
            eprintln!("⚠️  Could not retrieve analytics: {}", e);
        }
    }

    println!("\n✨ Test suite completed successfully!\n");
    Ok(())
}
