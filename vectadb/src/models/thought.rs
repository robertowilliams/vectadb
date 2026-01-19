use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

/// Thought model - represents a chain-of-thought entry from an agent
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Thought {
    /// Unique identifier (nanoid)
    pub id: String,

    /// ID of the agent that generated this thought
    pub agent_id: String,

    /// ID of the task (if associated with a task)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_id: Option<String>,

    /// The thought content (reasoning step)
    pub content: String,

    /// Sequence number in the chain of thoughts (optional)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sequence: Option<i32>,

    /// Additional metadata (flexible JSON)
    #[serde(default)]
    pub metadata: JsonValue,

    /// Timestamp
    pub timestamp: DateTime<Utc>,
}

/// Request to create a new thought
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateThoughtRequest {
    /// ID of the agent that generated this thought
    pub agent_id: String,

    /// ID of the task (if associated with a task)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub task_id: Option<String>,

    /// The thought content (reasoning step)
    pub content: String,

    /// Sequence number in the chain of thoughts (optional)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sequence: Option<i32>,

    /// Additional metadata (flexible JSON)
    #[serde(default)]
    pub metadata: JsonValue,
}

impl Thought {
    /// Create a new thought with generated ID
    pub fn new(
        agent_id: String,
        task_id: Option<String>,
        content: String,
        sequence: Option<i32>,
        metadata: JsonValue,
    ) -> Self {
        Self {
            id: nanoid::nanoid!(10),
            agent_id,
            task_id,
            content,
            sequence,
            metadata,
            timestamp: Utc::now(),
        }
    }

    /// Build searchable text from thought for semantic analysis
    pub fn to_searchable_text(&self) -> String {
        if let Some(seq) = self.sequence {
            format!("Step {}: {}", seq, self.content)
        } else {
            self.content.clone()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_thought_creation() {
        let thought = Thought::new(
            "agent123".to_string(),
            Some("task456".to_string()),
            "I need to analyze the dataset first".to_string(),
            Some(1),
            json!({"reasoning_type": "planning"}),
        );

        assert_eq!(thought.agent_id, "agent123");
        assert_eq!(thought.task_id, Some("task456".to_string()));
        assert_eq!(thought.content, "I need to analyze the dataset first");
        assert_eq!(thought.sequence, Some(1));
        assert_eq!(thought.id.len(), 10);
    }

    #[test]
    fn test_searchable_text() {
        let thought_with_seq = Thought::new(
            "agent123".to_string(),
            None,
            "Analyzing data".to_string(),
            Some(3),
            json!({}),
        );
        assert_eq!(
            thought_with_seq.to_searchable_text(),
            "Step 3: Analyzing data"
        );

        let thought_without_seq = Thought::new(
            "agent123".to_string(),
            None,
            "Analyzing data".to_string(),
            None,
            json!({}),
        );
        assert_eq!(thought_without_seq.to_searchable_text(), "Analyzing data");
    }
}
