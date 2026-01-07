// Embedding generation module
pub mod manager;
pub mod plugin;
pub mod plugins;
pub mod service;

// Re-export for convenience
#[allow(unused_imports)]
pub use service::{EmbeddingService, EmbeddingModel};

pub use manager::EmbeddingManager;

pub use plugin::{
    EmbeddingPlugin, PluginConfig, PluginHealth, PluginRegistry, PluginStats, ProviderConfig,
};

pub use plugins::{CoherePlugin, HuggingFacePlugin, OpenAIPlugin, VoyagePlugin};
