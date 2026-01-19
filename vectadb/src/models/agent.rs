use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

/// Agent model - represents an AI agent in the system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Agent {
    /// Unique identifier (nanoid)
    pub id: String,

    /// Agent role (e.g., "researcher", "writer", "analyst")
    pub role: String,

    /// Agent's primary goal or purpose
    pub goal: String,

    /// Additional metadata (flexible JSON)
    #[serde(default)]
    pub metadata: JsonValue,

    /// Creation timestamp
    pub created_at: DateTime<Utc>,

    /// Last update timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub updated_at: Option<DateTime<Utc>>,
}

/// Request to create a new agent
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateAgentRequest {
    /// Agent role (e.g., "researcher", "writer", "analyst")
    pub role: String,

    /// Agent's primary goal or purpose
    pub goal: String,

    /// Additional metadata (flexible JSON)
    #[serde(default)]
    pub metadata: JsonValue,
}

/// Agent with all related entities (tasks, thoughts, logs)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentWithRelations {
    #[serde(flatten)]
    pub agent: Agent,

    /// Related tasks
    #[serde(default)]
    pub tasks: Vec<super::task::Task>,

    /// Related thoughts
    #[serde(default)]
    pub thoughts: Vec<super::thought::Thought>,

    /// Related logs
    #[serde(default)]
    pub logs: Vec<super::log::Log>,
}

impl Agent {
    /// Create a new agent with generated ID
    pub fn new(role: String, goal: String, metadata: JsonValue) -> Self {
        Self {
            id: nanoid::nanoid!(10),
            role,
            goal,
            metadata,
            created_at: Utc::now(),
            updated_at: None,
        }
    }

    /// Build searchable text from agent metadata for embedding
    pub fn to_searchable_text(&self) -> String {
        let mut parts = vec![
            self.role.clone(),
            self.goal.clone(),
        ];

        // Extract metadata fields if they exist
        if let Some(obj) = self.metadata.as_object() {
            for (key, value) in obj.iter() {
                if let Some(s) = value.as_str() {
                    parts.push(format!("{}: {}", key, s));
                } else if let Some(arr) = value.as_array() {
                    let items: Vec<String> = arr
                        .iter()
                        .filter_map(|v| v.as_str().map(|s| s.to_string()))
                        .collect();
                    if !items.is_empty() {
                        parts.push(format!("{}: {}", key, items.join(", ")));
                    }
                }
            }
        }

        parts.join(" | ")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_agent_creation() {
        let agent = Agent::new(
            "researcher".to_string(),
            "analyze data patterns".to_string(),
            json!({"skills": ["ML", "statistics"]}),
        );

        assert_eq!(agent.role, "researcher");
        assert_eq!(agent.goal, "analyze data patterns");
        assert_eq!(agent.id.len(), 10);
    }

    #[test]
    fn test_searchable_text() {
        let agent = Agent::new(
            "researcher".to_string(),
            "analyze data".to_string(),
            json!({
                "skills": ["ML", "statistics"],
                "specialty": "time series"
            }),
        );

        let text = agent.to_searchable_text();
        assert!(text.contains("researcher"));
        assert!(text.contains("analyze data"));
        assert!(text.contains("skills"));
        assert!(text.contains("specialty"));
    }
}
