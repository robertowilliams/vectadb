// Shared data types for vectadb-logflyer

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;
use std::collections::HashMap;

// ────────────────────────────────────────────────────────────────────────────
// Raw log line (produced by the tailer)
// ────────────────────────────────────────────────────────────────────────────

/// A single line read from a watched log file.
#[derive(Debug, Clone)]
pub struct LogLine {
    /// Absolute path of the source file.
    pub file_path: String,

    /// Agent identifier from the log file config.
    pub agent_id: String,

    /// Optional session ID from config (may be overridden by extracted value).
    pub session_id: Option<String>,

    /// Zero-based byte offset of the first byte of this line in the file.
    pub byte_offset: u64,

    /// Raw text content (newline stripped).
    pub raw: String,

    /// Wall-clock time when the line was read (not necessarily log timestamp).
    pub read_at: DateTime<Utc>,
}

// ────────────────────────────────────────────────────────────────────────────
// LLM classification result (produced by the classifier)
// ────────────────────────────────────────────────────────────────────────────

/// Classification of a single log line by the LLM.
#[derive(Debug, Clone)]
pub struct ClassifiedEvent {
    /// The original log line.
    pub log_line: LogLine,

    /// Whether the LLM judged this line as containing agentic / LLM activity.
    pub is_agentic: bool,

    /// Fine-grained event type (see `EventType` enum).
    pub event_type: EventType,

    /// LLM confidence in the classification [0.0, 1.0].
    pub confidence: f32,

    /// Key-value pairs extracted by the LLM (model name, token count, etc.).
    pub extracted: HashMap<String, JsonValue>,

    /// Whether this classification came from the LLM or the pattern fallback.
    pub source: ClassificationSource,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum EventType {
    LlmCall,
    ToolCall,
    AgentDecision,
    Retrieval,
    Error,
    SessionStart,
    SessionEnd,
    OtherAgentic,
    NotAgentic,
}

impl EventType {
    pub fn as_str(&self) -> &'static str {
        match self {
            EventType::LlmCall => "llm_call",
            EventType::ToolCall => "tool_call",
            EventType::AgentDecision => "agent_decision",
            EventType::Retrieval => "retrieval",
            EventType::Error => "error",
            EventType::SessionStart => "session_start",
            EventType::SessionEnd => "session_end",
            EventType::OtherAgentic => "other_agentic",
            EventType::NotAgentic => "not_agentic",
        }
    }

    pub fn from_str(s: &str) -> Self {
        match s {
            "llm_call" => EventType::LlmCall,
            "tool_call" => EventType::ToolCall,
            "agent_decision" => EventType::AgentDecision,
            "retrieval" => EventType::Retrieval,
            "error" => EventType::Error,
            "session_start" => EventType::SessionStart,
            "session_end" => EventType::SessionEnd,
            _ => EventType::OtherAgentic,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ClassificationSource {
    Llm,
    PatternFallback,
}

// ────────────────────────────────────────────────────────────────────────────
// VectaDB event shapes (mirrors API types)
// ────────────────────────────────────────────────────────────────────────────

/// Single event for POST /api/v1/events (and bulk equivalent).
#[derive(Debug, Clone, Serialize)]
pub struct VectaDBEvent {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trace_id: Option<String>,

    pub timestamp: DateTime<Utc>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_type: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub agent_id: Option<String>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,

    pub properties: serde_json::Map<String, JsonValue>,

    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<VectaDBSource>,
}

#[derive(Debug, Clone, Serialize)]
pub struct VectaDBSource {
    pub system: String,
    pub log_group: String,
    pub log_stream: String,
    pub log_id: String,
}

/// Bulk ingestion request body.
#[derive(Debug, Serialize)]
pub struct BulkIngestionRequest {
    pub events: Vec<VectaDBEvent>,
    pub options: IngestionOptions,
}

#[derive(Debug, Serialize)]
pub struct IngestionOptions {
    pub auto_create_traces: bool,
    pub generate_embeddings: bool,
    pub extract_relationships: bool,
}

/// Bulk ingestion response.
#[derive(Debug, Deserialize)]
pub struct BulkIngestionResponse {
    pub ingested: usize,
    pub failed: usize,
    pub trace_ids: Vec<String>,
    #[serde(default)]
    pub errors: Vec<IngestionError>,
}

#[derive(Debug, Deserialize)]
pub struct IngestionError {
    pub index: usize,
    pub error: String,
}

/// Health check response.
#[derive(Debug, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
}

// ────────────────────────────────────────────────────────────────────────────
// Conversion: ClassifiedEvent → VectaDBEvent
// ────────────────────────────────────────────────────────────────────────────

impl From<ClassifiedEvent> for VectaDBEvent {
    fn from(ev: ClassifiedEvent) -> Self {
        let log = &ev.log_line;

        let mut props = serde_json::Map::new();
        props.insert("raw_log".into(), JsonValue::String(log.raw.clone()));
        props.insert("file_path".into(), JsonValue::String(log.file_path.clone()));
        props.insert(
            "byte_offset".into(),
            JsonValue::Number(log.byte_offset.into()),
        );
        props.insert(
            "confidence".into(),
            JsonValue::Number(
                serde_json::Number::from_f64(ev.confidence as f64)
                    .unwrap_or(serde_json::Number::from(0)),
            ),
        );
        props.insert(
            "classification_source".into(),
            JsonValue::String(match ev.source {
                ClassificationSource::Llm => "llm".into(),
                ClassificationSource::PatternFallback => "pattern_fallback".into(),
            }),
        );
        props.insert("framework".into(), JsonValue::String("logflyer".into()));

        // Merge extracted fields from LLM
        for (k, v) in &ev.extracted {
            props.insert(k.clone(), v.clone());
        }

        VectaDBEvent {
            trace_id: None,
            timestamp: log.read_at,
            event_type: Some(ev.event_type.as_str().to_string()),
            agent_id: Some(log.agent_id.clone()),
            session_id: log.session_id.clone().or_else(|| {
                ev.extracted
                    .get("session_id")
                    .and_then(|v| v.as_str())
                    .map(str::to_string)
            }),
            properties: props,
            source: Some(VectaDBSource {
                system: "logflyer".into(),
                log_group: log.file_path.clone(),
                log_stream: log.agent_id.clone(),
                log_id: uuid::Uuid::new_v4().to_string(),
            }),
        }
    }
}
