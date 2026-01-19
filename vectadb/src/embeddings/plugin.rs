// Plugin trait definition for embedding providers
use crate::error::Result;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

/// Embedding plugin trait - all providers must implement this
#[async_trait]
pub trait EmbeddingPlugin: Send + Sync {
    /// Plugin name (e.g., "openai", "cohere")
    fn name(&self) -> &'static str;

    /// Plugin version
    fn version(&self) -> &'static str;

    /// Embedding dimension size
    fn dimension(&self) -> usize;

    /// Maximum batch size supported
    fn max_batch_size(&self) -> usize;

    /// Initialize the plugin with configuration
    async fn initialize(&mut self, config: PluginConfig) -> Result<()>;

    /// Generate embedding for a single text
    async fn embed(&self, text: &str) -> Result<Vec<f32>>;

    /// Generate embeddings for multiple texts
    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;

    /// Check if plugin is healthy (can make API calls, etc.)
    async fn health_check(&self) -> Result<PluginHealth>;

    /// Get usage statistics (tokens, requests, etc.)
    fn get_stats(&self) -> PluginStats;
}

/// Plugin configuration (loaded from YAML)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginConfig {
    /// Plugin name
    pub name: String,

    /// Provider-specific configuration
    #[serde(flatten)]
    pub provider: ProviderConfig,
}

/// Provider-specific configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "provider", rename_all = "lowercase")]
pub enum ProviderConfig {
    OpenAI {
        api_key: String,
        model: String,
        #[serde(default = "default_openai_base_url")]
        base_url: String,
        #[serde(default = "default_dimension")]
        dimension: usize,
        #[serde(default = "default_batch_size")]
        batch_size: usize,
        #[serde(default = "default_timeout")]
        timeout_secs: u64,
    },
    Cohere {
        api_key: String,
        model: String,
        #[serde(default = "default_cohere_base_url")]
        base_url: String,
        #[serde(default = "default_dimension")]
        dimension: usize,
        #[serde(default = "default_batch_size")]
        batch_size: usize,
        #[serde(default = "default_timeout")]
        timeout_secs: u64,
        #[serde(default = "default_input_type")]
        input_type: String,
    },
    HuggingFace {
        api_key: String,
        model: String,
        #[serde(default = "default_hf_base_url")]
        base_url: String,
        #[serde(default = "default_dimension")]
        dimension: usize,
        #[serde(default = "default_batch_size")]
        batch_size: usize,
        #[serde(default = "default_timeout")]
        timeout_secs: u64,
    },
    Voyage {
        api_key: String,
        model: String,
        base_url: String,
        dimension: usize,
        batch_size: usize,
        timeout_secs: u64,
    },
    Local {
        model: String,
        #[serde(default = "default_dimension")]
        dimension: usize,
        #[serde(default = "default_batch_size")]
        batch_size: usize,
    },
}

// Default values
fn default_openai_base_url() -> String {
    "https://api.openai.com/v1".to_string()
}

fn default_cohere_base_url() -> String {
    "https://api.cohere.ai/v1".to_string()
}

fn default_hf_base_url() -> String {
    "https://api-inference.huggingface.co".to_string()
}

fn default_dimension() -> usize {
    1536
}

fn default_batch_size() -> usize {
    100
}

fn default_timeout() -> u64 {
    30
}

fn default_input_type() -> String {
    "search_document".to_string()
}

/// Plugin health status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginHealth {
    pub healthy: bool,
    pub message: Option<String>,
    pub latency_ms: Option<u64>,
}

/// Plugin usage statistics
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct PluginStats {
    pub total_requests: u64,
    pub total_tokens: u64,
    pub total_embeddings: u64,
    pub failed_requests: u64,
    pub avg_latency_ms: f64,
}

/// Plugin registry for managing multiple embedding providers
pub struct PluginRegistry {
    plugins: std::collections::HashMap<String, Box<dyn EmbeddingPlugin>>,
    active_plugin: Option<String>,
}

impl PluginRegistry {
    /// Create a new plugin registry
    pub fn new() -> Self {
        Self {
            plugins: std::collections::HashMap::new(),
            active_plugin: None,
        }
    }

    /// Register a plugin
    pub fn register(&mut self, plugin: Box<dyn EmbeddingPlugin>) {
        let name = plugin.name().to_string();
        self.plugins.insert(name.clone(), plugin);

        // Set as active if it's the first plugin
        if self.active_plugin.is_none() {
            self.active_plugin = Some(name);
        }
    }

    /// Set the active plugin
    pub fn set_active(&mut self, name: &str) -> Result<()> {
        if self.plugins.contains_key(name) {
            self.active_plugin = Some(name.to_string());
            Ok(())
        } else {
            Err(crate::error::VectaDBError::InvalidInput(
                format!("Plugin '{}' not found", name),
            ))
        }
    }

    /// Get the active plugin
    pub fn get_active(&self) -> Result<&dyn EmbeddingPlugin> {
        let name = self.active_plugin.as_ref().ok_or_else(|| {
            crate::error::VectaDBError::InvalidInput("No active plugin set".to_string())
        })?;

        self.plugins.get(name).map(|p| p.as_ref()).ok_or_else(|| {
            crate::error::VectaDBError::InvalidInput(format!("Plugin '{}' not found", name))
        })
    }

    /// Get a plugin by name
    pub fn get(&self, name: &str) -> Option<&dyn EmbeddingPlugin> {
        self.plugins.get(name).map(|p| p.as_ref())
    }

    /// List all registered plugins
    pub fn list_plugins(&self) -> Vec<String> {
        self.plugins.keys().cloned().collect()
    }
}

impl Default for PluginRegistry {
    fn default() -> Self {
        Self::new()
    }
}
