use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

/// Log level enum
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum LogLevel {
    Debug,
    Info,
    Warning,
    Error,
    Critical,
}

impl Default for LogLevel {
    fn default() -> Self {
        LogLevel::Info
    }
}

impl std::fmt::Display for LogLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            LogLevel::Debug => write!(f, "DEBUG"),
            LogLevel::Info => write!(f, "INFO"),
            LogLevel::Warning => write!(f, "WARNING"),
            LogLevel::Error => write!(f, "ERROR"),
            LogLevel::Critical => write!(f, "CRITICAL"),
        }
    }
}

/// Log model - represents a log entry from an agent
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Log {
    /// Unique identifier (nanoid)
    pub id: String,

    /// ID of the agent that generated this log
    pub agent_id: String,

    /// ID of the task (if associated with a task)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_id: Option<String>,

    /// Log level
    #[serde(default)]
    pub level: LogLevel,

    /// Log message
    pub message: String,

    /// Additional metadata (flexible JSON)
    #[serde(default)]
    pub metadata: JsonValue,

    /// Timestamp
    pub timestamp: DateTime<Utc>,
}

/// Request to create a new log
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateLogRequest {
    /// ID of the agent that generated this log
    pub agent_id: String,

    /// ID of the task (if associated with a task)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_id: Option<String>,

    /// Log level (defaults to Info)
    #[serde(default)]
    pub level: LogLevel,

    /// Log message
    pub message: String,

    /// Additional metadata (flexible JSON)
    #[serde(default)]
    pub metadata: JsonValue,
}

impl Log {
    /// Create a new log with generated ID
    pub fn new(
        agent_id: String,
        task_id: Option<String>,
        level: LogLevel,
        message: String,
        metadata: JsonValue,
    ) -> Self {
        Self {
            id: nanoid::nanoid!(10),
            agent_id,
            task_id,
            level,
            message,
            metadata,
            timestamp: Utc::now(),
        }
    }

    /// Check if this is an error-level log
    pub fn is_error(&self) -> bool {
        matches!(self.level, LogLevel::Error | LogLevel::Critical)
    }

    /// Build searchable text from log for semantic error clustering
    pub fn to_searchable_text(&self) -> String {
        format!("{} | {}", self.level, self.message)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_log_creation() {
        let log = Log::new(
            "agent123".to_string(),
            Some("task456".to_string()),
            LogLevel::Info,
            "Processing data".to_string(),
            json!({"step": 1}),
        );

        assert_eq!(log.agent_id, "agent123");
        assert_eq!(log.task_id, Some("task456".to_string()));
        assert_eq!(log.level, LogLevel::Info);
        assert_eq!(log.message, "Processing data");
        assert_eq!(log.id.len(), 10);
    }

    #[test]
    fn test_is_error() {
        let info_log = Log::new(
            "agent123".to_string(),
            None,
            LogLevel::Info,
            "test".to_string(),
            json!({}),
        );
        assert!(!info_log.is_error());

        let error_log = Log::new(
            "agent123".to_string(),
            None,
            LogLevel::Error,
            "test".to_string(),
            json!({}),
        );
        assert!(error_log.is_error());

        let critical_log = Log::new(
            "agent123".to_string(),
            None,
            LogLevel::Critical,
            "test".to_string(),
            json!({}),
        );
        assert!(critical_log.is_error());
    }

    #[test]
    fn test_log_level_display() {
        assert_eq!(LogLevel::Info.to_string(), "INFO");
        assert_eq!(LogLevel::Error.to_string(), "ERROR");
    }
}
