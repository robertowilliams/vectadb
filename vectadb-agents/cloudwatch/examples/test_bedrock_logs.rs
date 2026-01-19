// Example: Test CloudWatch agent with real Bedrock logs
//
// This example:
// 1. Loads real Bedrock logs from JSON file
// 2. Simulates CloudWatch events
// 3. Parses them using the agent's parser
// 4. Displays parsed events and trace grouping
//
// Run with: cargo run --example test_bedrock_logs

use chrono::{DateTime, Utc};
use serde_json::Value as JsonValue;
use std::collections::HashMap;
use std::fs;

/// Simulated CloudWatch log event
#[derive(Debug, Clone)]
struct CloudWatchEvent {
    log_group: String,
    log_stream: String,
    event_id: String,
    message: String,
    timestamp: DateTime<Utc>,
}

/// Event after parsing
#[derive(Debug, Clone)]
struct ParsedEvent {
    request_id: Option<String>,
    event_type: String,
    operation: Option<String>,
    model_id: Option<String>,
    error_code: Option<String>,
    tool_name: Option<String>,
    latency_ms: Option<i64>,
    input_tokens: Option<i64>,
    output_tokens: Option<i64>,
    timestamp: DateTime<Utc>,
    properties: JsonValue,
}

fn main() {
    println!("{}", "=".repeat(80));
    println!("CloudWatch Agent - Bedrock Log Parsing Test");
    println!("{}", "=".repeat(80));
    println!();

    // Load real Bedrock logs
    let bedrock_logs_path = "../../notes/bedrock_chain_of_thought_logs.json";

    println!("Loading Bedrock logs from: {}", bedrock_logs_path);

    let logs_content = match fs::read_to_string(bedrock_logs_path) {
        Ok(content) => content,
        Err(e) => {
            eprintln!("Error reading Bedrock logs: {}", e);
            eprintln!("Make sure you run this from the cloudwatch agent directory");
            return;
        }
    };

    let logs: Vec<JsonValue> = match serde_json::from_str(&logs_content) {
        Ok(logs) => logs,
        Err(e) => {
            eprintln!("Error parsing JSON: {}", e);
            return;
        }
    };

    println!("Loaded {} Bedrock log events", logs.len());
    println!();

    // Convert to CloudWatch events
    let mut cw_events: Vec<CloudWatchEvent> = Vec::new();

    for (idx, log) in logs.iter().enumerate() {
        // Parse timestamp
        let timestamp_str = log["timestamp"].as_str().unwrap_or("2025-01-01T00:00:00Z");
        let timestamp = DateTime::parse_from_rfc3339(timestamp_str)
            .map(|dt| dt.with_timezone(&Utc))
            .unwrap_or_else(|_| Utc::now());

        // Serialize back to JSON string (this is what CloudWatch would send)
        let message = serde_json::to_string(log).unwrap_or_default();

        cw_events.push(CloudWatchEvent {
            log_group: "/aws/bedrock/agent/invocations".to_string(),
            log_stream: "2025-12-17".to_string(),
            event_id: format!("event-{}", idx),
            message,
            timestamp,
        });
    }

    // Parse events
    println!("Parsing {} CloudWatch events...", cw_events.len());
    println!();

    let mut parsed_events: Vec<ParsedEvent> = Vec::new();
    let mut parse_errors = 0;

    for event in &cw_events {
        match parse_bedrock_event(event) {
            Ok(parsed) => parsed_events.push(parsed),
            Err(e) => {
                eprintln!("Parse error for event {}: {}", event.event_id, e);
                parse_errors += 1;
            }
        }
    }

    println!("Parsing complete:");
    println!("  - Successfully parsed: {}", parsed_events.len());
    println!("  - Parse errors: {}", parse_errors);
    println!();

    // Analyze parsed events
    analyze_events(&parsed_events);

    // Group by trace (requestId)
    group_by_trace(&parsed_events);
}

fn parse_bedrock_event(event: &CloudWatchEvent) -> Result<ParsedEvent, String> {
    let log: JsonValue = serde_json::from_str(&event.message)
        .map_err(|e| format!("JSON parse error: {}", e))?;

    // Extract key fields
    let request_id = log["requestId"].as_str().map(String::from);
    let operation = log["operation"].as_str().map(String::from);
    let model_id = log["modelId"].as_str().map(String::from);
    let error_code = log["errorCode"].as_str().map(String::from);

    // Extract tool use if present
    let tool_name = extract_tool_name(&log);

    // Extract metrics
    let latency_ms = log["output"]["outputBodyJson"]["metrics"]["latencyMs"].as_i64();
    let input_tokens = log["output"]["outputBodyJson"]["usage"]["inputTokens"].as_i64()
        .or_else(|| log["input"]["inputTokenCount"].as_i64());
    let output_tokens = log["output"]["outputBodyJson"]["usage"]["outputTokens"].as_i64()
        .or_else(|| log["output"]["outputTokenCount"].as_i64());

    // Determine event type
    let event_type = if error_code.is_some() {
        "bedrock_error".to_string()
    } else if tool_name.is_some() {
        "bedrock_tool_use".to_string()
    } else {
        "bedrock_invocation".to_string()
    };

    Ok(ParsedEvent {
        request_id,
        event_type,
        operation,
        model_id,
        error_code,
        tool_name,
        latency_ms,
        input_tokens,
        output_tokens,
        timestamp: event.timestamp,
        properties: log,
    })
}

fn extract_tool_name(log: &JsonValue) -> Option<String> {
    // Try to find tool use in the output
    let content = &log["output"]["outputBodyJson"]["output"]["message"]["content"];

    if let Some(array) = content.as_array() {
        for item in array {
            if let Some(tool_use) = item.get("toolUse") {
                if let Some(name) = tool_use["name"].as_str() {
                    return Some(name.to_string());
                }
            }
        }
    }

    None
}

fn analyze_events(events: &[ParsedEvent]) {
    println!("{}", "=".repeat(80));
    println!("Event Analysis");
    println!("{}", "=".repeat(80));
    println!();

    // Count by event type
    let mut type_counts: HashMap<String, usize> = HashMap::new();
    for event in events {
        *type_counts.entry(event.event_type.clone()).or_insert(0) += 1;
    }

    println!("Events by type:");
    for (event_type, count) in &type_counts {
        println!("  - {}: {}", event_type, count);
    }
    println!();

    // Count errors
    let errors: Vec<_> = events.iter().filter(|e| e.error_code.is_some()).collect();
    println!("Error events: {}", errors.len());
    if !errors.is_empty() {
        let mut error_counts: HashMap<String, usize> = HashMap::new();
        for event in &errors {
            if let Some(ref code) = event.error_code {
                *error_counts.entry(code.clone()).or_insert(0) += 1;
            }
        }
        for (error_code, count) in &error_counts {
            println!("  - {}: {}", error_code, count);
        }
    }
    println!();

    // Count tool uses
    let tool_uses: Vec<_> = events.iter().filter(|e| e.tool_name.is_some()).collect();
    println!("Tool use events: {}", tool_uses.len());
    if !tool_uses.is_empty() {
        let mut tool_counts: HashMap<String, usize> = HashMap::new();
        for event in &tool_uses {
            if let Some(ref tool) = event.tool_name {
                *tool_counts.entry(tool.clone()).or_insert(0) += 1;
            }
        }
        for (tool_name, count) in &tool_counts {
            println!("  - {}: {}", tool_name, count);
        }
    }
    println!();

    // Token statistics
    let token_events: Vec<_> = events
        .iter()
        .filter(|e| e.input_tokens.is_some() && e.output_tokens.is_some())
        .collect();

    if !token_events.is_empty() {
        let total_input: i64 = token_events.iter().filter_map(|e| e.input_tokens).sum();
        let total_output: i64 = token_events.iter().filter_map(|e| e.output_tokens).sum();

        println!("Token usage:");
        println!("  - Total input tokens: {}", total_input);
        println!("  - Total output tokens: {}", total_output);
        println!("  - Total tokens: {}", total_input + total_output);
        println!("  - Average input: {}", total_input / token_events.len() as i64);
        println!("  - Average output: {}", total_output / token_events.len() as i64);
    }
    println!();

    // Latency statistics
    let latency_events: Vec<_> = events.iter().filter_map(|e| e.latency_ms).collect();
    if !latency_events.is_empty() {
        let total_latency: i64 = latency_events.iter().sum();
        let avg_latency = total_latency / latency_events.len() as i64;
        let min_latency = *latency_events.iter().min().unwrap();
        let max_latency = *latency_events.iter().max().unwrap();

        println!("Latency statistics:");
        println!("  - Average: {}ms", avg_latency);
        println!("  - Min: {}ms", min_latency);
        println!("  - Max: {}ms", max_latency);
    }
    println!();
}

fn group_by_trace(events: &[ParsedEvent]) {
    println!("{}", "=".repeat(80));
    println!("Trace Grouping (by requestId)");
    println!("{}", "=".repeat(80));
    println!();

    let mut traces: HashMap<String, Vec<&ParsedEvent>> = HashMap::new();

    for event in events {
        if let Some(ref request_id) = event.request_id {
            traces
                .entry(request_id.clone())
                .or_insert_with(Vec::new)
                .push(event);
        }
    }

    println!("Total traces: {}", traces.len());
    println!();

    // Show sample traces
    println!("Sample traces (first 5):");
    println!();

    for (idx, (request_id, trace_events)) in traces.iter().enumerate() {
        if idx >= 5 {
            break;
        }

        println!("Trace #{}: {} ({}events)", idx + 1, request_id, trace_events.len());
        for (event_idx, event) in trace_events.iter().enumerate() {
            print!("  {}. [{}] {}", event_idx + 1, event.timestamp.format("%H:%M:%S"), event.event_type);

            if let Some(ref tool) = event.tool_name {
                print!(" - Tool: {}", tool);
            }
            if let Some(ref error) = event.error_code {
                print!(" - Error: {}", error);
            }
            if let Some(latency) = event.latency_ms {
                print!(" ({}ms)", latency);
            }

            println!();
        }
        println!();
    }

    // Show trace size distribution
    let mut size_distribution: HashMap<usize, usize> = HashMap::new();
    for (_, trace_events) in &traces {
        *size_distribution.entry(trace_events.len()).or_insert(0) += 1;
    }

    println!("Trace size distribution:");
    let mut sizes: Vec<_> = size_distribution.iter().collect();
    sizes.sort_by_key(|(size, _)| *size);

    for (size, count) in sizes {
        println!("  - {} event(s): {} trace(s)", size, count);
    }
    println!();
}
