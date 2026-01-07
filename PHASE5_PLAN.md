# VectaDB Phase 5 - Agent Observability via Log Integration

**Date**: January 7, 2026
**Status**: Planning
**Duration**: 5 days (Week 1 of MVP)

---

## Strategic Vision

**Core Concept**: VectaDB ingests logs from existing systems (CloudWatch, DataDog, etc.) and transforms them into structured, searchable agent execution traces using:
- **Ontology**: Type-safe event schemas
- **Vector embeddings**: Semantic search on log content
- **Graph relationships**: Causal event chains
- **Temporal indexing**: Time-series analysis

**Key Insight**: Zero code changes required - works with existing logs immediately.

## Confirmed Decisions

1. ✅ **CloudWatch Agent in Rust** - Performance and consistency with core
2. ✅ **Polling-based** - Start with polling (simple, reliable)
3. ✅ **Built-in Patterns** - Include LangChain, LlamaIndex parsers out of the box
4. ✅ **Single-tenant** - No multi-tenancy initially (open-source focus)
5. ✅ **Resilient Trace Detection** - Use session_id, request_id, AND agent_id
6. ✅ **Open Source First** - MIT/Apache 2.0, managed service is future consideration

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 Agent Systems (LangChain, etc.)             │
│                        ↓ logs to                            │
│                    AWS CloudWatch                           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│           VectaDB CloudWatch Agent (Rust)                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  1. Subscribe to CloudWatch log groups              │   │
│  │  2. Poll for new log events (10s interval)          │   │
│  │  3. Parse logs → structured events                  │   │
│  │  4. Detect traces from session/request IDs          │   │
│  │  5. Bulk send to VectaDB API                        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           ↓
                POST /api/v1/events/batch
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    VectaDB Core API                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  • Flexible event ingestion                         │   │
│  │  • Auto-trace detection & creation                  │   │
│  │  • Vector embedding generation                      │   │
│  │  • Graph relationship extraction                    │   │
│  │  • Temporal indexing (timestamp-based)              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Day-by-Day Implementation Plan

### Day 1: Event Ingestion API (VectaDB Core)

#### Task 1.1: Event Schema Design
**File**: `vectadb/src/api/types.rs`

```rust
// Flexible event structure for log ingestion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventIngestionRequest {
    /// Optional: Link to existing trace
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trace_id: Option<String>,

    /// Required: Event timestamp
    pub timestamp: chrono::DateTime<chrono::Utc>,

    /// Optional: Event classification (tool_call, decision, error, etc.)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_type: Option<String>,

    /// Optional: Agent identifier
    #[serde(skip_serializing_if = "Option::is_none")]
    pub agent_id: Option<String>,

    /// Optional: Session/request identifier (for trace grouping)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,

    /// Required: Event properties (flexible JSON)
    pub properties: serde_json::Value,

    /// Optional: Original log source metadata
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<LogSource>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogSource {
    pub system: String,        // "cloudwatch", "datadog", etc.
    pub log_group: String,     // CloudWatch log group name
    pub log_stream: String,    // CloudWatch log stream name
    pub log_id: String,        // Original log event ID
}

// Bulk ingestion for efficiency
#[derive(Debug, Deserialize)]
pub struct BulkEventIngestionRequest {
    pub events: Vec<EventIngestionRequest>,

    #[serde(default)]
    pub options: IngestionOptions,
}

#[derive(Debug, Deserialize, Default)]
pub struct IngestionOptions {
    /// Auto-create traces from session_id if not exists
    #[serde(default = "default_true")]
    pub auto_create_traces: bool,

    /// Generate embeddings for semantic search
    #[serde(default = "default_true")]
    pub generate_embeddings: bool,

    /// Extract event relationships (causality)
    #[serde(default)]
    pub extract_relationships: bool,
}

fn default_true() -> bool { true }

// Response types
#[derive(Debug, Serialize)]
pub struct EventIngestionResponse {
    pub event_id: String,
    pub trace_id: String,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

#[derive(Debug, Serialize)]
pub struct BulkEventIngestionResponse {
    pub ingested: usize,
    pub failed: usize,
    pub trace_ids: Vec<String>,
    pub errors: Vec<IngestionError>,
}

#[derive(Debug, Serialize)]
pub struct IngestionError {
    pub index: usize,
    pub error: String,
}
```

#### Task 1.2: Ingestion Handler
**File**: `vectadb/src/api/handlers.rs`

```rust
// Single event ingestion
pub async fn ingest_event(
    State(state): State<AppState>,
    Json(req): Json<EventIngestionRequest>,
) -> Result<Json<EventIngestionResponse>, ErrorResponse> {
    // 1. Determine or create trace
    let trace_id = if let Some(tid) = req.trace_id {
        tid
    } else if let Some(sid) = &req.session_id {
        get_or_create_trace_by_session(&state, sid).await?
    } else {
        create_standalone_trace(&state, &req).await?
    };

    // 2. Create event entity
    let event_id = create_event_entity(&state, &req, &trace_id).await?;

    // 3. Generate embedding if needed
    if let Some(embedding_service) = &state.embedding_service {
        if should_embed(&req) {
            let text = extract_embeddable_text(&req);
            let embedding = embedding_service.encode(&text).await?;

            if let Some(qdrant) = &state.qdrant {
                store_event_vector(qdrant, &event_id, embedding).await?;
            }
        }
    }

    // 4. Link event to trace
    create_trace_event_relation(&state, &trace_id, &event_id).await?;

    Ok(Json(EventIngestionResponse {
        event_id,
        trace_id,
        created_at: req.timestamp,
    }))
}

// Bulk event ingestion
pub async fn ingest_events_bulk(
    State(state): State<AppState>,
    Json(req): Json<BulkEventIngestionRequest>,
) -> Result<Json<BulkEventIngestionResponse>, ErrorResponse> {
    let mut ingested = 0;
    let mut failed = 0;
    let mut trace_ids = HashSet::new();
    let mut errors = Vec::new();

    // Process events in parallel (batches of 100)
    for (chunk_idx, chunk) in req.events.chunks(100).enumerate() {
        let futures: Vec<_> = chunk.iter().enumerate().map(|(idx, event)| {
            let state = state.clone();
            let event = event.clone();
            async move {
                match ingest_single_event(&state, event, &req.options).await {
                    Ok((event_id, trace_id)) => {
                        Ok((event_id, trace_id))
                    }
                    Err(e) => Err((chunk_idx * 100 + idx, e.to_string()))
                }
            }
        }).collect();

        let results = futures::future::join_all(futures).await;

        for result in results {
            match result {
                Ok((_, trace_id)) => {
                    ingested += 1;
                    trace_ids.insert(trace_id);
                }
                Err((idx, error)) => {
                    failed += 1;
                    errors.push(IngestionError { index: idx, error });
                }
            }
        }
    }

    Ok(Json(BulkEventIngestionResponse {
        ingested,
        failed,
        trace_ids: trace_ids.into_iter().collect(),
        errors,
    }))
}
```

#### Task 1.3: Trace Auto-Creation Logic
**File**: `vectadb/src/api/handlers.rs`

```rust
// Resilient trace detection using session_id AND agent_id
async fn get_or_create_trace_by_session(
    state: &AppState,
    session_id: &str,
    agent_id: Option<&str>,
) -> Result<String> {
    let surreal = state.surreal.as_ref()
        .ok_or_else(|| anyhow!("Database not available"))?;

    // Strategy 1: Try exact session_id match first
    let query = r#"
        SELECT id FROM agent_trace
        WHERE session_id = $session_id
        ORDER BY start_time DESC
        LIMIT 1
    "#;

    let mut result = surreal.db.query(query)
        .bind(("session_id", session_id))
        .await?;

    let traces: Vec<TraceRecord> = result.take(0)?;

    if let Some(trace) = traces.first() {
        // Found existing trace by session_id
        debug!("Found trace {} by session_id {}", trace.id, session_id);
        return Ok(trace.id.to_string());
    }

    // Strategy 2: If agent_id provided, check for recent trace with same agent_id
    // (useful when session_id changes but agent continues)
    if let Some(aid) = agent_id {
        let query = r#"
            SELECT id FROM agent_trace
            WHERE agent_id = $agent_id
              AND status = 'running'
              AND start_time > time::now() - 1h
            ORDER BY start_time DESC
            LIMIT 1
        "#;

        let mut result = surreal.db.query(query)
            .bind(("agent_id", aid))
            .await?;

        let traces: Vec<TraceRecord> = result.take(0)?;

        if let Some(trace) = traces.first() {
            // Found recent running trace with same agent_id
            debug!("Found trace {} by agent_id {} (within 1h)", trace.id, aid);
            return Ok(trace.id.to_string());
        }
    }

    // Strategy 3: No existing trace found - create new one
    create_trace_for_session(state, session_id, agent_id).await
}

async fn create_trace_for_session(
    state: &AppState,
    session_id: &str,
    agent_id: Option<&str>,
) -> Result<String> {
    let trace_id = format!("trace_{}", nanoid::nanoid!(16));

    let trace = json!({
        "id": trace_id.clone(),
        "session_id": session_id,
        "agent_id": agent_id,  // Store agent_id for resilient lookup
        "status": "running",
        "start_time": chrono::Utc::now(),
        "created_at": chrono::Utc::now(),
    });

    let surreal = state.surreal.as_ref().unwrap();

    let _: Vec<serde_json::Value> = surreal.db
        .create("agent_trace")
        .content(trace)
        .await?;

    info!("Created new trace {} for session {} (agent: {:?})",
          trace_id, session_id, agent_id);

    Ok(trace_id)
}
```

#### Task 1.4: Add Routes
**File**: `vectadb/src/api/routes.rs`

```rust
// Add to create_router_with_state()
.route("/api/v1/events", post(handlers::ingest_event))
.route("/api/v1/events/batch", post(handlers::ingest_events_bulk))
```

---

### Day 2: Agent Framework Foundation

#### Task 2.1: Create Agent Project Structure
```bash
mkdir -p vectadb-agents/cloudwatch
cd vectadb-agents/cloudwatch
cargo init --name vectadb-cloudwatch-agent
```

#### Task 2.2: Agent Cargo.toml
**File**: `vectadb-agents/cloudwatch/Cargo.toml`

```toml
[package]
name = "vectadb-cloudwatch-agent"
version = "0.1.0"
edition = "2021"

[dependencies]
# AWS SDK
aws-config = { version = "1.1", features = ["behavior-version-latest"] }
aws-sdk-cloudwatchlogs = "1.13"

# Async runtime
tokio = { version = "1", features = ["full"] }

# HTTP client for VectaDB API
reqwest = { version = "0.11", features = ["json"] }

# Serialization
serde = { version = "1", features = ["derive"] }
serde_json = "1"
serde_yaml = "0.9"

# Logging
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json"] }

# Error handling
anyhow = "1"
thiserror = "1"

# Utilities
chrono = { version = "0.4", features = ["serde"] }
regex = "1"
```

#### Task 2.3: Agent Configuration Schema
**File**: `vectadb-agents/cloudwatch/src/config.rs`

```rust
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Deserialize)]
pub struct AgentConfig {
    /// AWS region
    pub aws_region: String,

    /// CloudWatch log groups to monitor
    pub log_groups: Vec<LogGroupConfig>,

    /// VectaDB endpoint
    pub vectadb_endpoint: String,

    /// VectaDB API key
    pub vectadb_api_key: String,

    /// Poll interval in seconds
    #[serde(default = "default_poll_interval")]
    pub poll_interval_seconds: u64,

    /// Batch size for sending to VectaDB
    #[serde(default = "default_batch_size")]
    pub batch_size: usize,

    /// Parser rules
    pub parser_rules: Vec<ParserRule>,
}

fn default_poll_interval() -> u64 { 10 }
fn default_batch_size() -> usize { 100 }

#[derive(Debug, Clone, Deserialize)]
pub struct LogGroupConfig {
    /// Log group name
    pub name: String,

    /// Optional: specific log streams to monitor
    #[serde(default)]
    pub log_streams: Vec<String>,

    /// Optional: filter pattern (CloudWatch filter syntax)
    pub filter_pattern: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ParserRule {
    /// Rule name
    pub name: String,

    /// Regex pattern to match log lines
    pub pattern: String,

    /// Event type to assign
    pub event_type: String,

    /// Field extraction mappings (regex group name -> property name)
    pub field_mappings: HashMap<String, String>,

    /// Optional: only apply if log matches this condition
    pub condition: Option<String>,
}

impl AgentConfig {
    pub fn from_file(path: &str) -> anyhow::Result<Self> {
        let content = std::fs::read_to_string(path)?;
        let config: AgentConfig = serde_yaml::from_str(&content)?;
        Ok(config)
    }
}
```

#### Task 2.4: VectaDB Client Library
**File**: `vectadb-agents/cloudwatch/src/vectadb_client.rs`

```rust
use reqwest::Client as HttpClient;
use serde::{Deserialize, Serialize};
use anyhow::{Context, Result};

#[derive(Clone)]
pub struct VectaDBClient {
    http_client: HttpClient,
    base_url: String,
    api_key: String,
}

impl VectaDBClient {
    pub fn new(base_url: String, api_key: String) -> Self {
        Self {
            http_client: HttpClient::new(),
            base_url,
            api_key,
        }
    }

    pub async fn ingest_events_bulk(
        &self,
        events: Vec<EventIngestionRequest>,
    ) -> Result<BulkEventIngestionResponse> {
        let url = format!("{}/api/v1/events/batch", self.base_url);

        let request = BulkEventIngestionRequest {
            events,
            options: IngestionOptions::default(),
        };

        let response = self.http_client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&request)
            .send()
            .await
            .context("Failed to send events to VectaDB")?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await?;
            anyhow::bail!("VectaDB API error {}: {}", status, body);
        }

        let result = response.json().await
            .context("Failed to parse VectaDB response")?;

        Ok(result)
    }

    pub async fn health_check(&self) -> Result<bool> {
        let url = format!("{}/health", self.base_url);

        let response = self.http_client
            .get(&url)
            .send()
            .await?;

        Ok(response.status().is_success())
    }
}

// Re-use types from VectaDB core
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventIngestionRequest {
    pub trace_id: Option<String>,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    pub event_type: Option<String>,
    pub agent_id: Option<String>,
    pub session_id: Option<String>,
    pub properties: serde_json::Value,
    pub source: Option<LogSource>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LogSource {
    pub system: String,
    pub log_group: String,
    pub log_stream: String,
    pub log_id: String,
}

#[derive(Debug, Serialize)]
pub struct BulkEventIngestionRequest {
    pub events: Vec<EventIngestionRequest>,
    pub options: IngestionOptions,
}

#[derive(Debug, Serialize, Default)]
pub struct IngestionOptions {
    pub auto_create_traces: bool,
    pub generate_embeddings: bool,
    pub extract_relationships: bool,
}

#[derive(Debug, Deserialize)]
pub struct BulkEventIngestionResponse {
    pub ingested: usize,
    pub failed: usize,
    pub trace_ids: Vec<String>,
    pub errors: Vec<IngestionError>,
}

#[derive(Debug, Deserialize)]
pub struct IngestionError {
    pub index: usize,
    pub error: String,
}
```

---

### Day 3: CloudWatch Integration

#### Task 3.1: CloudWatch Client
**File**: `vectadb-agents/cloudwatch/src/cloudwatch_client.rs`

```rust
use aws_sdk_cloudwatchlogs as cloudwatch;
use chrono::{DateTime, Utc};
use anyhow::{Context, Result};

pub struct CloudWatchClient {
    client: cloudwatch::Client,
}

impl CloudWatchClient {
    pub async fn new(region: &str) -> Result<Self> {
        let config = aws_config::from_env()
            .region(aws_config::Region::new(region.to_string()))
            .load()
            .await;

        let client = cloudwatch::Client::new(&config);

        Ok(Self { client })
    }

    pub async fn fetch_log_events(
        &self,
        log_group_name: &str,
        log_stream_names: &[String],
        start_time: DateTime<Utc>,
        filter_pattern: Option<&str>,
    ) -> Result<Vec<LogEvent>> {
        let start_ms = start_time.timestamp_millis();

        let mut all_events = Vec::new();

        // If specific streams provided, query each
        if !log_stream_names.is_empty() {
            for stream_name in log_stream_names {
                let events = self.fetch_from_stream(
                    log_group_name,
                    stream_name,
                    start_ms,
                ).await?;
                all_events.extend(events);
            }
        } else {
            // Otherwise, use filter_log_events to query all streams
            let events = self.filter_logs(
                log_group_name,
                start_ms,
                filter_pattern,
            ).await?;
            all_events.extend(events);
        }

        Ok(all_events)
    }

    async fn fetch_from_stream(
        &self,
        log_group_name: &str,
        log_stream_name: &str,
        start_ms: i64,
    ) -> Result<Vec<LogEvent>> {
        let response = self.client
            .get_log_events()
            .log_group_name(log_group_name)
            .log_stream_name(log_stream_name)
            .start_time(start_ms)
            .start_from_head(true)
            .send()
            .await
            .context("Failed to fetch log events from CloudWatch")?;

        let events = response.events()
            .iter()
            .map(|event| LogEvent {
                log_group: log_group_name.to_string(),
                log_stream: log_stream_name.to_string(),
                timestamp: event.timestamp().unwrap_or(0),
                message: event.message().unwrap_or("").to_string(),
                ingestion_time: event.ingestion_time().unwrap_or(0),
            })
            .collect();

        Ok(events)
    }

    async fn filter_logs(
        &self,
        log_group_name: &str,
        start_ms: i64,
        filter_pattern: Option<&str>,
    ) -> Result<Vec<LogEvent>> {
        let mut request = self.client
            .filter_log_events()
            .log_group_name(log_group_name)
            .start_time(start_ms);

        if let Some(pattern) = filter_pattern {
            request = request.filter_pattern(pattern);
        }

        let response = request.send().await
            .context("Failed to filter log events from CloudWatch")?;

        let events = response.events()
            .iter()
            .map(|event| LogEvent {
                log_group: log_group_name.to_string(),
                log_stream: event.log_stream_name().unwrap_or("").to_string(),
                timestamp: event.timestamp().unwrap_or(0),
                message: event.message().unwrap_or("").to_string(),
                ingestion_time: event.ingestion_time().unwrap_or(0),
            })
            .collect();

        Ok(events)
    }
}

#[derive(Debug, Clone)]
pub struct LogEvent {
    pub log_group: String,
    pub log_stream: String,
    pub timestamp: i64,
    pub message: String,
    pub ingestion_time: i64,
}
```

#### Task 3.2: Log Parser with Built-in Patterns
**File**: `vectadb-agents/cloudwatch/src/parser.rs`

```rust
use regex::Regex;
use serde_json::{json, Value};
use crate::config::ParserRule;
use crate::cloudwatch_client::LogEvent;
use crate::vectadb_client::{EventIngestionRequest, LogSource};
use chrono::{DateTime, Utc, TimeZone};

pub struct LogParser {
    rules: Vec<CompiledRule>,
    builtin_patterns: BuiltInPatterns,
}

struct CompiledRule {
    name: String,
    pattern: Regex,
    event_type: String,
    field_mappings: std::collections::HashMap<String, String>,
}

// Built-in patterns for common frameworks
struct BuiltInPatterns {
    langchain_tool: Regex,
    langchain_chain: Regex,
    langchain_agent: Regex,
    llamaindex_query: Regex,
    llamaindex_retrieve: Regex,
    generic_error: Regex,
    request_id: Regex,
}

impl BuiltInPatterns {
    fn new() -> Self {
        Self {
            // LangChain patterns
            langchain_tool: Regex::new(
                r"(?i)(?:Entering new|Finished|Running) (?P<tool_name>\w+)(?: tool)?.*?(?:input[:\s]+)?(?P<input>\{.*?\}|[^\n]+)"
            ).unwrap(),
            langchain_chain: Regex::new(
                r"(?i)Entering new (?P<chain_type>\w+) chain.*"
            ).unwrap(),
            langchain_agent: Regex::new(
                r"(?i)(?P<agent_name>\w+Agent).*?(?:Thought|Action|Observation)[:\s]+(?P<content>.*)"
            ).unwrap(),

            // LlamaIndex patterns
            llamaindex_query: Regex::new(
                r"(?i)query[:\s]+(?P<query>.*?)(?:\n|$)"
            ).unwrap(),
            llamaindex_retrieve: Regex::new(
                r"(?i)retrieved (?P<count>\d+) nodes.*"
            ).unwrap(),

            // Generic patterns
            generic_error: Regex::new(
                r"(?i)(?:ERROR|Exception|Failed)[:\s]+(?P<error_message>.*)"
            ).unwrap(),

            // Request/session ID patterns (resilient)
            request_id: Regex::new(
                r"(?i)(?:request_id|session_id|trace_id|correlation_id|transaction_id)[:\s=]+['\"]?(?P<id>[a-zA-Z0-9_-]+)['\"]?"
            ).unwrap(),
        }
    }
}

impl LogParser {
    pub fn new(rules: Vec<ParserRule>) -> anyhow::Result<Self> {
        let mut compiled_rules = Vec::new();

        for rule in rules {
            let pattern = Regex::new(&rule.pattern)?;
            compiled_rules.push(CompiledRule {
                name: rule.name,
                pattern,
                event_type: rule.event_type,
                field_mappings: rule.field_mappings,
            });
        }

        Ok(Self {
            rules: compiled_rules,
            builtin_patterns: BuiltInPatterns::new(),
        })
    }

    pub fn parse(&self, log_event: &LogEvent) -> Option<EventIngestionRequest> {
        // Try JSON parsing first
        if let Some(event) = self.try_parse_json(log_event) {
            return Some(event);
        }

        // Try built-in patterns (LangChain, LlamaIndex)
        if let Some(event) = self.try_builtin_patterns(log_event) {
            return Some(event);
        }

        // Try custom regex rules
        for rule in &self.rules {
            if let Some(captures) = rule.pattern.captures(&log_event.message) {
                return Some(self.build_event_from_captures(
                    log_event,
                    rule,
                    &captures,
                ));
            }
        }

        // Fallback: create unstructured event
        Some(self.create_fallback_event(log_event))
    }

    fn try_builtin_patterns(&self, log_event: &LogEvent) -> Option<EventIngestionRequest> {
        let msg = &log_event.message;

        // Extract session/request ID first (used across all patterns)
        let session_id = self.extract_session_id(msg);
        let agent_id = self.extract_agent_id(msg);

        // Try LangChain tool pattern
        if let Some(caps) = self.builtin_patterns.langchain_tool.captures(msg) {
            return Some(self.create_event(
                log_event,
                "tool_call",
                json!({
                    "framework": "langchain",
                    "tool_name": caps.name("tool_name").map(|m| m.as_str()),
                    "tool_input": caps.name("input").map(|m| m.as_str()),
                    "raw_message": msg,
                }),
                session_id,
                agent_id,
            ));
        }

        // Try LangChain agent pattern
        if let Some(caps) = self.builtin_patterns.langchain_agent.captures(msg) {
            return Some(self.create_event(
                log_event,
                "agent_decision",
                json!({
                    "framework": "langchain",
                    "agent_name": caps.name("agent_name").map(|m| m.as_str()),
                    "content": caps.name("content").map(|m| m.as_str()),
                    "raw_message": msg,
                }),
                session_id,
                agent_id,
            ));
        }

        // Try LlamaIndex query pattern
        if let Some(caps) = self.builtin_patterns.llamaindex_query.captures(msg) {
            return Some(self.create_event(
                log_event,
                "query",
                json!({
                    "framework": "llamaindex",
                    "query": caps.name("query").map(|m| m.as_str()),
                    "raw_message": msg,
                }),
                session_id,
                agent_id,
            ));
        }

        // Try generic error pattern
        if let Some(caps) = self.builtin_patterns.generic_error.captures(msg) {
            return Some(self.create_event(
                log_event,
                "error",
                json!({
                    "error_message": caps.name("error_message").map(|m| m.as_str()),
                    "raw_message": msg,
                }),
                session_id,
                agent_id,
            ));
        }

        None
    }

    // Resilient session ID extraction - tries multiple patterns
    fn extract_session_id(&self, message: &str) -> Option<String> {
        if let Some(caps) = self.builtin_patterns.request_id.captures(message) {
            caps.name("id").map(|m| m.as_str().to_string())
        } else {
            None
        }
    }

    // Resilient agent ID extraction
    fn extract_agent_id(&self, message: &str) -> Option<String> {
        // Try to extract agent_id from various patterns
        let patterns = [
            r"(?i)agent[_\s]*id[:\s=]+['\"]?(?P<id>[a-zA-Z0-9_-]+)['\"]?",
            r"(?i)agent[:\s]+(?P<id>[a-zA-Z0-9_-]+)",
            r"(?P<id>\w+Agent)", // Pattern like "GPT4Agent", "SearchAgent"
        ];

        for pattern_str in &patterns {
            if let Ok(pattern) = Regex::new(pattern_str) {
                if let Some(caps) = pattern.captures(message) {
                    if let Some(id) = caps.name("id") {
                        return Some(id.as_str().to_string());
                    }
                }
            }
        }

        None
    }

    fn create_event(
        &self,
        log_event: &LogEvent,
        event_type: &str,
        mut properties: Value,
        session_id: Option<String>,
        agent_id: Option<String>,
    ) -> EventIngestionRequest {
        let timestamp = Utc.timestamp_millis_opt(log_event.timestamp)
            .single()
            .unwrap_or_else(Utc::now);

        // Add agent_id to properties if found
        if let Some(ref aid) = agent_id {
            properties["detected_agent_id"] = json!(aid);
        }

        EventIngestionRequest {
            trace_id: None,
            timestamp,
            event_type: Some(event_type.to_string()),
            agent_id,
            session_id,
            properties,
            source: Some(LogSource {
                system: "cloudwatch".to_string(),
                log_group: log_event.log_group.clone(),
                log_stream: log_event.log_stream.clone(),
                log_id: format!("{}-{}", log_event.log_stream, log_event.timestamp),
            }),
        }
    }

    fn try_parse_json(&self, log_event: &LogEvent) -> Option<EventIngestionRequest> {
        let value: Value = serde_json::from_str(&log_event.message).ok()?;

        let timestamp = if let Some(ts_str) = value["timestamp"].as_str() {
            DateTime::parse_from_rfc3339(ts_str).ok()?.with_timezone(&Utc)
        } else {
            Utc.timestamp_millis_opt(log_event.timestamp).single()?
        };

        Some(EventIngestionRequest {
            trace_id: value["trace_id"].as_str().map(String::from),
            timestamp,
            event_type: value["event_type"].as_str().map(String::from),
            agent_id: value["agent_id"].as_str().map(String::from),
            session_id: value["session_id"]
                .as_str()
                .or(value["request_id"].as_str())
                .map(String::from),
            properties: value,
            source: Some(LogSource {
                system: "cloudwatch".to_string(),
                log_group: log_event.log_group.clone(),
                log_stream: log_event.log_stream.clone(),
                log_id: format!("{}-{}", log_event.log_stream, log_event.timestamp),
            }),
        })
    }

    fn build_event_from_captures(
        &self,
        log_event: &LogEvent,
        rule: &CompiledRule,
        captures: &regex::Captures,
    ) -> EventIngestionRequest {
        let mut properties = json!({
            "raw_message": log_event.message,
            "matched_rule": rule.name,
        });

        // Extract fields based on mappings
        for (group_name, property_name) in &rule.field_mappings {
            if let Some(value) = captures.name(group_name) {
                properties[property_name] = json!(value.as_str());
            }
        }

        let timestamp = Utc.timestamp_millis_opt(log_event.timestamp)
            .single()
            .unwrap_or_else(Utc::now);

        EventIngestionRequest {
            trace_id: None,
            timestamp,
            event_type: Some(rule.event_type.clone()),
            agent_id: properties["agent_id"].as_str().map(String::from),
            session_id: properties["session_id"]
                .as_str()
                .or(properties["request_id"].as_str())
                .map(String::from),
            properties,
            source: Some(LogSource {
                system: "cloudwatch".to_string(),
                log_group: log_event.log_group.clone(),
                log_stream: log_event.log_stream.clone(),
                log_id: format!("{}-{}", log_event.log_stream, log_event.timestamp),
            }),
        }
    }

    fn create_fallback_event(&self, log_event: &LogEvent) -> EventIngestionRequest {
        let timestamp = Utc.timestamp_millis_opt(log_event.timestamp)
            .single()
            .unwrap_or_else(Utc::now);

        EventIngestionRequest {
            trace_id: None,
            timestamp,
            event_type: Some("log".to_string()),
            agent_id: None,
            session_id: None,
            properties: json!({
                "message": log_event.message,
                "raw": true,
            }),
            source: Some(LogSource {
                system: "cloudwatch".to_string(),
                log_group: log_event.log_group.clone(),
                log_stream: log_event.log_stream.clone(),
                log_id: format!("{}-{}", log_event.log_stream, log_event.timestamp),
            }),
        }
    }
}
```

---

### Day 4: Agent Main Loop

#### Task 4.1: Agent State Management
**File**: `vectadb-agents/cloudwatch/src/state.rs`

```rust
use std::collections::HashMap;
use chrono::{DateTime, Utc};

/// Tracks last poll time for each log group
pub struct AgentState {
    last_poll_times: HashMap<String, DateTime<Utc>>,
}

impl AgentState {
    pub fn new() -> Self {
        Self {
            last_poll_times: HashMap::new(),
        }
    }

    pub fn get_last_poll(&self, log_group: &str) -> DateTime<Utc> {
        self.last_poll_times
            .get(log_group)
            .copied()
            .unwrap_or_else(|| Utc::now() - chrono::Duration::minutes(5))
    }

    pub fn update_last_poll(&mut self, log_group: &str, time: DateTime<Utc>) {
        self.last_poll_times.insert(log_group.to_string(), time);
    }
}
```

#### Task 4.2: Main Agent Loop
**File**: `vectadb-agents/cloudwatch/src/main.rs`

```rust
mod config;
mod cloudwatch_client;
mod parser;
mod vectadb_client;
mod state;

use anyhow::{Context, Result};
use chrono::Utc;
use std::time::Duration;
use tracing::{info, warn, error};

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .json()
        .init();

    info!("Starting VectaDB CloudWatch Agent");

    // Load configuration
    let config_path = std::env::var("CONFIG_PATH")
        .unwrap_or_else(|_| "config.yaml".to_string());
    let config = config::AgentConfig::from_file(&config_path)
        .context("Failed to load configuration")?;

    info!("Configuration loaded: {} log groups to monitor", config.log_groups.len());

    // Initialize clients
    let cloudwatch_client = cloudwatch_client::CloudWatchClient::new(&config.aws_region)
        .await
        .context("Failed to create CloudWatch client")?;

    let vectadb_client = vectadb_client::VectaDBClient::new(
        config.vectadb_endpoint.clone(),
        config.vectadb_api_key.clone(),
    );

    // Verify VectaDB connectivity
    if !vectadb_client.health_check().await? {
        anyhow::bail!("VectaDB health check failed");
    }
    info!("Connected to VectaDB at {}", config.vectadb_endpoint);

    // Initialize parser
    let parser = parser::LogParser::new(config.parser_rules.clone())
        .context("Failed to initialize parser")?;

    // Initialize state
    let mut state = state::AgentState::new();

    // Main polling loop
    let poll_interval = Duration::from_secs(config.poll_interval_seconds);

    loop {
        let poll_start = Utc::now();
        info!("Starting poll cycle");

        for log_group_config in &config.log_groups {
            let log_group_name = &log_group_config.name;

            // Get last poll time for this log group
            let last_poll = state.get_last_poll(log_group_name);

            info!("Fetching logs from {} since {}", log_group_name, last_poll);

            // Fetch new logs
            let log_events = match cloudwatch_client.fetch_log_events(
                log_group_name,
                &log_group_config.log_streams,
                last_poll,
                log_group_config.filter_pattern.as_deref(),
            ).await {
                Ok(events) => events,
                Err(e) => {
                    error!("Failed to fetch logs from {}: {}", log_group_name, e);
                    continue;
                }
            };

            if log_events.is_empty() {
                info!("No new logs from {}", log_group_name);
                state.update_last_poll(log_group_name, poll_start);
                continue;
            }

            info!("Fetched {} log events from {}", log_events.len(), log_group_name);

            // Parse logs into events
            let mut events = Vec::new();
            for log_event in &log_events {
                if let Some(event) = parser.parse(log_event) {
                    events.push(event);
                }
            }

            if events.is_empty() {
                warn!("No events parsed from {} log entries", log_events.len());
                state.update_last_poll(log_group_name, poll_start);
                continue;
            }

            info!("Parsed {} events from {} logs", events.len(), log_events.len());

            // Send to VectaDB in batches
            for chunk in events.chunks(config.batch_size) {
                match vectadb_client.ingest_events_bulk(chunk.to_vec()).await {
                    Ok(response) => {
                        info!(
                            "Ingested {} events ({} failed) into {} traces",
                            response.ingested,
                            response.failed,
                            response.trace_ids.len()
                        );

                        if !response.errors.is_empty() {
                            for err in &response.errors {
                                warn!("Ingestion error at index {}: {}", err.index, err.error);
                            }
                        }
                    }
                    Err(e) => {
                        error!("Failed to send events to VectaDB: {}", e);
                    }
                }
            }

            // Update last poll time
            state.update_last_poll(log_group_name, poll_start);
        }

        let poll_duration = Utc::now().signed_duration_since(poll_start);
        info!("Poll cycle completed in {}ms", poll_duration.num_milliseconds());

        // Sleep until next poll
        tokio::time::sleep(poll_interval).await;
    }
}
```

---

### Day 5: Configuration & Documentation

#### Task 5.1: Example Configuration
**File**: `vectadb-agents/cloudwatch/config.example.yaml`

```yaml
# AWS Configuration
aws_region: us-east-1

# CloudWatch Log Groups to Monitor
log_groups:
  - name: /aws/lambda/langchain-agent-prod
    # Optional: specific log streams
    log_streams: []
    # Optional: CloudWatch filter pattern
    filter_pattern: null

  - name: /ecs/agent-service
    log_streams: []
    filter_pattern: null

# VectaDB Configuration
vectadb_endpoint: http://localhost:8080
vectadb_api_key: your-api-key-here

# Polling Configuration
poll_interval_seconds: 10
batch_size: 100

# Parser Rules
parser_rules:
  # LangChain tool call pattern
  - name: langchain_tool_call
    pattern: '.*Tool:\s+(?P<tool>\w+).*Input:\s+(?P<input>\{.*?\})'
    event_type: tool_call
    field_mappings:
      tool: tool_name
      input: tool_input

  # Generic error pattern
  - name: error_log
    pattern: '.*ERROR.*:\s+(?P<message>.*)'
    event_type: error
    field_mappings:
      message: error_message

  # LangChain agent decision
  - name: langchain_decision
    pattern: '.*Agent.*:\s+(?P<decision>.*)'
    event_type: decision
    field_mappings:
      decision: agent_decision

  # Request ID extraction (for trace grouping)
  - name: request_id
    pattern: '.*request_id[:=]\s*["\']?(?P<request_id>[a-zA-Z0-9-]+)["\']?'
    event_type: log
    field_mappings:
      request_id: session_id
```

#### Task 5.2: Dockerfile
**File**: `vectadb-agents/cloudwatch/Dockerfile`

```dockerfile
FROM rust:1.75 as builder

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src

RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/target/release/vectadb-cloudwatch-agent /usr/local/bin/

WORKDIR /app

CMD ["vectadb-cloudwatch-agent"]
```

#### Task 5.3: README
**File**: `vectadb-agents/cloudwatch/README.md`

```markdown
# VectaDB CloudWatch Agent

Ingests logs from AWS CloudWatch and sends structured events to VectaDB for agent observability.

## Features

- Polls CloudWatch log groups at configurable intervals
- Parses logs using regex patterns or JSON
- Auto-detects traces from session/request IDs
- Bulk ingestion for efficiency
- Handles AWS credentials via standard AWS SDK methods

## Quick Start

### 1. Configure AWS Credentials

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
```

### 2. Create Configuration

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your settings
```

### 3. Run Agent

```bash
cargo run --release
```

### Docker

```bash
docker build -t vectadb-cloudwatch-agent .

docker run -d \
  -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  -e AWS_REGION=$AWS_REGION \
  -v $(pwd)/config.yaml:/app/config.yaml \
  vectadb-cloudwatch-agent
```

## Configuration

See `config.example.yaml` for all options.

### Parser Rules

Parser rules use named regex groups to extract fields:

```yaml
parser_rules:
  - name: my_rule
    pattern: 'Agent (?P<agent_name>\w+) used tool (?P<tool_name>\w+)'
    event_type: tool_call
    field_mappings:
      agent_name: agent_id
      tool_name: tool_name
```

### Trace Detection

The agent automatically groups events into traces based on:
1. Explicit `trace_id` in log (if JSON)
2. `session_id` or `request_id` in log
3. Time-based grouping (future enhancement)

## Architecture

```
CloudWatch Logs → Agent (poll) → Parse → Batch → VectaDB API
```

## Performance

- Processes 1000+ log events/second
- Batch size: 100 events per request
- Memory usage: ~50MB

## Troubleshooting

### "Failed to fetch logs from CloudWatch"

- Check AWS credentials
- Verify IAM permissions: `logs:FilterLogEvents`, `logs:GetLogEvents`
- Confirm log group name is correct

### "VectaDB health check failed"

- Verify VectaDB is running: `curl http://localhost:8080/health`
- Check `vectadb_endpoint` in config
- Verify API key is correct

## License

Apache 2.0
```

---

## Testing Strategy

### Unit Tests
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_json_log() {
        let parser = LogParser::new(vec![]).unwrap();
        let log_event = LogEvent {
            message: r#"{"timestamp":"2026-01-07T16:50:00Z","event_type":"tool_call","tool":"search"}"#.to_string(),
            // ... other fields
        };

        let event = parser.parse(&log_event).unwrap();
        assert_eq!(event.event_type, Some("tool_call".to_string()));
    }

    #[test]
    fn test_parse_regex_log() {
        let rule = ParserRule {
            pattern: r"Tool: (?P<tool>\w+)".to_string(),
            event_type: "tool_call".to_string(),
            // ...
        };

        let parser = LogParser::new(vec![rule]).unwrap();
        // ... test regex parsing
    }
}
```

### Integration Tests
```bash
# Test with real CloudWatch (requires AWS credentials)
cargo test --test integration_tests -- --ignored
```

---

## Deployment Checklist

- [ ] Day 1: Event ingestion API in VectaDB core
- [ ] Day 2: Agent framework foundation
- [ ] Day 3: CloudWatch integration
- [ ] Day 4: Main agent loop with error handling
- [ ] Day 5: Configuration, documentation, Docker

## Success Criteria

- [ ] Agent successfully connects to CloudWatch
- [ ] Parses 100+ log events correctly
- [ ] Sends batches to VectaDB API
- [ ] Auto-creates traces from session IDs
- [ ] Handles errors gracefully (retry, logging)
- [ ] Docker image builds and runs
- [ ] Documentation complete with examples

---

**Next Phase**: Week 2 - Security & Performance
