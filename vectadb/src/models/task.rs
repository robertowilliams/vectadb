use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

/// Task status enum
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum TaskStatus {
    Pending,
    Running,
    Completed,
    Failed,
    Cancelled,
}

impl Default for TaskStatus {
    fn default() -> Self {
        TaskStatus::Pending
    }
}

/// Task model - represents a task assigned to an agent
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    /// Unique identifier (nanoid)
    pub id: String,

    /// ID of the agent this task belongs to
    pub agent_id: String,

    /// Task name/title
    pub name: String,

    /// Task status
    #[serde(default)]
    pub status: TaskStatus,

    /// Task duration in milliseconds (if completed)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration_ms: Option<i64>,

    /// Additional metadata (flexible JSON)
    #[serde(default)]
    pub metadata: JsonValue,

    /// Creation timestamp
    pub created_at: DateTime<Utc>,

    /// Completion timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub completed_at: Option<DateTime<Utc>>,

    /// Last update timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub updated_at: Option<DateTime<Utc>>,
}

/// Request to create a new task
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateTaskRequest {
    /// ID of the agent this task belongs to
    pub agent_id: String,

    /// Task name/title
    pub name: String,

    /// Task status (optional, defaults to Pending)
    #[serde(default)]
    pub status: TaskStatus,

    /// Additional metadata (flexible JSON)
    #[serde(default)]
    pub metadata: JsonValue,
}

/// Task with all related entities (thoughts, logs)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskWithRelations {
    #[serde(flatten)]
    pub task: Task,

    /// Related thoughts
    #[serde(default)]
    pub thoughts: Vec<super::thought::Thought>,

    /// Related logs
    #[serde(default)]
    pub logs: Vec<super::log::Log>,
}

impl Task {
    /// Create a new task with generated ID
    pub fn new(agent_id: String, name: String, metadata: JsonValue) -> Self {
        Self {
            id: nanoid::nanoid!(10),
            agent_id,
            name,
            status: TaskStatus::Pending,
            duration_ms: None,
            metadata,
            created_at: Utc::now(),
            completed_at: None,
            updated_at: None,
        }
    }

    /// Mark task as completed and calculate duration
    pub fn complete(&mut self) {
        self.status = TaskStatus::Completed;
        self.completed_at = Some(Utc::now());
        self.updated_at = Some(Utc::now());

        // Calculate duration
        if let Some(completed) = self.completed_at {
            self.duration_ms = Some((completed - self.created_at).num_milliseconds());
        }
    }

    /// Mark task as failed
    pub fn fail(&mut self) {
        self.status = TaskStatus::Failed;
        self.completed_at = Some(Utc::now());
        self.updated_at = Some(Utc::now());

        // Calculate duration even for failed tasks
        if let Some(completed) = self.completed_at {
            self.duration_ms = Some((completed - self.created_at).num_milliseconds());
        }
    }

    /// Build searchable text from task metadata for embedding
    pub fn to_searchable_text(&self) -> String {
        let mut parts = vec![
            self.name.clone(),
            format!("status: {:?}", self.status),
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
    fn test_task_creation() {
        let task = Task::new(
            "agent123".to_string(),
            "analyze_dataset".to_string(),
            json!({"dataset": "Q4_earnings"}),
        );

        assert_eq!(task.agent_id, "agent123");
        assert_eq!(task.name, "analyze_dataset");
        assert_eq!(task.status, TaskStatus::Pending);
        assert_eq!(task.id.len(), 10);
    }

    #[test]
    fn test_task_completion() {
        let mut task = Task::new(
            "agent123".to_string(),
            "test_task".to_string(),
            json!({}),
        );

        task.complete();

        assert_eq!(task.status, TaskStatus::Completed);
        assert!(task.completed_at.is_some());
        assert!(task.duration_ms.is_some());
        assert!(task.duration_ms.unwrap() >= 0);
    }

    #[test]
    fn test_task_failure() {
        let mut task = Task::new(
            "agent123".to_string(),
            "test_task".to_string(),
            json!({}),
        );

        task.fail();

        assert_eq!(task.status, TaskStatus::Failed);
        assert!(task.completed_at.is_some());
        assert!(task.duration_ms.is_some());
    }
}
