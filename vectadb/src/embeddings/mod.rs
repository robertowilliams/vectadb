// Embedding generation module
pub mod service;

// Re-export for convenience (currently unused but needed by future API layer)
#[allow(unused_imports)]
pub use service::{EmbeddingService, EmbeddingModel};
