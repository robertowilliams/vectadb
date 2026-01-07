pub mod agent;
pub mod task;
pub mod log;
pub mod thought;
pub mod embedding;

// Re-export models for convenience (currently unused but may be needed by API layer)
#[allow(unused_imports)]
pub use agent::{Agent, CreateAgentRequest, AgentWithRelations};
#[allow(unused_imports)]
pub use task::{Task, CreateTaskRequest, TaskWithRelations};
#[allow(unused_imports)]
pub use log::{Log, CreateLogRequest, LogLevel};
#[allow(unused_imports)]
pub use thought::{Thought, CreateThoughtRequest};
#[allow(unused_imports)]
pub use embedding::{EmbeddingMetadata, SimilarityResult};
