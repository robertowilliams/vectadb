// Configuration types and YAML loader for vectadb-logflyer

use anyhow::{Context, Result};
use serde::Deserialize;
use std::path::Path;

/// Root configuration loaded from config.yaml
#[derive(Debug, Deserialize)]
pub struct AgentConfig {
    pub llm: LLMConfig,
    pub vectadb: VectaDBConfig,
    pub log_files: Vec<LogFileConfig>,
    #[serde(default)]
    pub agent: AgentBehavior,
}

/// OpenAI-compatible LLM server settings
#[derive(Debug, Deserialize)]
pub struct LLMConfig {
    /// Base URL of the OpenAI-compatible server (e.g. http://localhost:11434)
    pub base_url: String,

    /// Optional API key (empty for local servers)
    #[serde(default)]
    pub api_key: String,

    /// Model name as the server expects it (e.g. "llama3", "gpt-4o")
    pub model: String,

    /// Maximum tokens in the classification response
    #[serde(default = "default_max_tokens")]
    pub max_tokens: u32,

    /// Temperature — 0.0 = deterministic, recommended for classification
    #[serde(default)]
    pub temperature: f32,

    /// HTTP request timeout (seconds)
    #[serde(default = "default_llm_timeout")]
    pub timeout_secs: u64,

    /// Whether to send `response_format: {type: "json_object"}` to the server.
    /// Disable for older servers that reject this parameter.
    #[serde(default = "default_true")]
    pub json_mode: bool,
}

/// VectaDB REST API settings
#[derive(Debug, Deserialize)]
pub struct VectaDBConfig {
    /// VectaDB base URL
    pub endpoint: String,

    /// Optional API key
    pub api_key: Option<String>,

    /// Events per bulk ingestion request
    #[serde(default = "default_batch_size")]
    pub batch_size: usize,

    /// HTTP request timeout (seconds)
    #[serde(default = "default_vectadb_timeout")]
    pub timeout_secs: u64,
}

/// A single log file to watch
#[derive(Debug, Deserialize, Clone)]
pub struct LogFileConfig {
    /// Absolute or relative path to the log file
    pub path: String,

    /// Agent identifier embedded in every VectaDB event from this file
    pub agent_id: String,

    /// Optional fixed session ID.  If absent, the classifier tries to extract
    /// one from each log line (e.g. from JSON fields like `session_id`).
    pub session_id: Option<String>,
}

/// Agent loop behaviour
#[derive(Debug, Deserialize)]
pub struct AgentBehavior {
    /// Poll interval in seconds
    #[serde(default = "default_poll_interval")]
    pub poll_interval_secs: u64,

    /// Maximum log lines sent to the LLM in a single classification request
    #[serde(default = "default_classification_batch_size")]
    pub classification_batch_size: usize,

    /// On first startup, how many trailing lines to read from each file.
    /// 0 = start from the current end (tail only new lines).
    #[serde(default)]
    pub lookback_lines: usize,

    /// Ask VectaDB to generate vector embeddings for each event
    #[serde(default = "default_true")]
    pub generate_embeddings: bool,

    /// Ask VectaDB to auto-create trace records from session_id
    #[serde(default = "default_true")]
    pub auto_create_traces: bool,

    /// If true, errors from the LLM or VectaDB are logged but never crash
    /// the poll loop — the agent simply retries on the next cycle.
    #[serde(default = "default_true")]
    pub fail_silently: bool,
}

impl Default for AgentBehavior {
    fn default() -> Self {
        Self {
            poll_interval_secs: default_poll_interval(),
            classification_batch_size: default_classification_batch_size(),
            lookback_lines: 0,
            generate_embeddings: true,
            auto_create_traces: true,
            fail_silently: true,
        }
    }
}

// ────────────────────────────────────────────────────────────────────────────
// Loader
// ────────────────────────────────────────────────────────────────────────────

impl AgentConfig {
    /// Load config from a YAML file, then overlay any `LOGFLYER_*` env vars.
    pub fn from_file(path: impl AsRef<Path>) -> Result<Self> {
        let content = std::fs::read_to_string(path.as_ref())
            .with_context(|| format!("Cannot read config file: {}", path.as_ref().display()))?;

        let config: AgentConfig = serde_yaml::from_str(&content)
            .context("Failed to parse config YAML")?;

        Ok(config)
    }
}

// ────────────────────────────────────────────────────────────────────────────
// Defaults
// ────────────────────────────────────────────────────────────────────────────

fn default_max_tokens() -> u32 { 2048 }
fn default_llm_timeout() -> u64 { 60 }
fn default_batch_size() -> usize { 100 }
fn default_vectadb_timeout() -> u64 { 30 }
fn default_poll_interval() -> u64 { 5 }
fn default_classification_batch_size() -> usize { 30 }
fn default_true() -> bool { true }
