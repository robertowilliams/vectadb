// Embedding manager - Unified interface over plugin system and local service
use crate::config::EmbeddingConfig;
use crate::embeddings::plugin::{EmbeddingPlugin, PluginConfig, PluginRegistry, ProviderConfig};
use crate::embeddings::plugins::{CoherePlugin, HuggingFacePlugin, OpenAIPlugin, VoyagePlugin};
use crate::embeddings::service::{EmbeddingModel, EmbeddingService};
use crate::error::{Result, VectaDBError};
use std::fs;
use std::sync::Arc;
use tracing::{debug, info, warn};

/// Embedding manager that handles both plugin-based and local embeddings
pub struct EmbeddingManager {
    registry: Option<PluginRegistry>,
    local_service: Option<Arc<EmbeddingService>>,
    config: EmbeddingConfig,
}

impl EmbeddingManager {
    /// Create a new embedding manager
    pub async fn new(config: EmbeddingConfig) -> Result<Self> {
        info!("Initializing embedding manager with provider: {}", config.provider);

        let mut manager = Self {
            registry: None,
            local_service: None,
            config: config.clone(),
        };

        // Initialize based on provider
        if config.provider == "local" {
            manager.init_local_service()?;
        } else {
            manager.init_plugin_system().await?;
        }

        Ok(manager)
    }

    /// Initialize local embedding service
    fn init_local_service(&mut self) -> Result<()> {
        info!("Initializing local embedding service");

        let model = match self.config.model.as_str() {
            "all-MiniLM-L6-v2" | "sentence-transformers/all-MiniLM-L6-v2" => {
                EmbeddingModel::AllMiniLML6v2
            }
            "all-MiniLM-L12-v2" | "sentence-transformers/all-MiniLM-L12-v2" => {
                EmbeddingModel::AllMiniLML12v2
            }
            "all-mpnet-base-v2" | "sentence-transformers/all-mpnet-base-v2" => {
                EmbeddingModel::AllMpnetBaseV2
            }
            "BAAI/bge-small-en-v1.5" => EmbeddingModel::BgeSmallEnV1_5,
            _ => {
                warn!(
                    "Unknown model '{}', defaulting to all-MiniLM-L6-v2",
                    self.config.model
                );
                EmbeddingModel::AllMiniLML6v2
            }
        };

        let service = EmbeddingService::new(model, Some(32))?;
        self.local_service = Some(Arc::new(service));

        info!("Local embedding service initialized successfully");
        Ok(())
    }

    /// Initialize plugin system
    async fn init_plugin_system(&mut self) -> Result<()> {
        info!("Initializing embedding plugin system");

        let mut registry = PluginRegistry::new();

        // Load plugin configuration
        let config_path = format!(
            "{}/{}.yaml",
            self.config.plugin_config_dir, self.config.provider
        );

        debug!("Loading plugin config from: {}", config_path);

        let plugin_config = self.load_plugin_config(&config_path)?;

        // Create and initialize appropriate plugin
        match self.config.provider.as_str() {
            "openai" => {
                let mut plugin = OpenAIPlugin::new();
                plugin.initialize(plugin_config).await?;
                registry.register(Box::new(plugin));
            }
            "cohere" => {
                let mut plugin = CoherePlugin::new();
                plugin.initialize(plugin_config).await?;
                registry.register(Box::new(plugin));
            }
            "huggingface" => {
                let mut plugin = HuggingFacePlugin::new();
                plugin.initialize(plugin_config).await?;
                registry.register(Box::new(plugin));
            }
            "voyage" => {
                let mut plugin = VoyagePlugin::new();
                plugin.initialize(plugin_config).await?;
                registry.register(Box::new(plugin));
            }
            _ => {
                return Err(VectaDBError::Config(format!(
                    "Unknown embedding provider: {}",
                    self.config.provider
                )));
            }
        }

        registry.set_active(&self.config.provider)?;

        info!(
            "Plugin '{}' initialized successfully",
            self.config.provider
        );

        self.registry = Some(registry);

        // Initialize local service as fallback if configured
        if self.config.fallback_to_local {
            info!("Initializing local service as fallback");
            self.init_local_service().ok(); // Don't fail if fallback init fails
        }

        Ok(())
    }

    /// Load plugin configuration from YAML file
    fn load_plugin_config(&self, path: &str) -> Result<PluginConfig> {
        let config_content = fs::read_to_string(path)
            .map_err(|e| VectaDBError::Config(format!("Failed to read plugin config: {}", e)))?;

        // Expand environment variables
        let config_content = self.expand_env_vars(&config_content);

        // Parse YAML
        let config: PluginConfig = serde_yaml::from_str(&config_content)
            .map_err(|e| VectaDBError::Config(format!("Failed to parse plugin config: {}", e)))?;

        // Validate API key is set
        self.validate_api_key(&config)?;

        Ok(config)
    }

    /// Expand environment variables in config
    fn expand_env_vars(&self, content: &str) -> String {
        let mut result = content.to_string();

        // Common environment variables
        let env_vars = [
            "OPENAI_API_KEY",
            "COHERE_API_KEY",
            "HF_API_KEY",
            "VOYAGE_API_KEY",
            "JINA_API_KEY",
        ];

        for var_name in &env_vars {
            let pattern = format!("${{{}}}", var_name);
            if let Ok(value) = std::env::var(var_name) {
                result = result.replace(&pattern, &value);
            }
        }

        result
    }

    /// Validate API key is properly set
    fn validate_api_key(&self, config: &PluginConfig) -> Result<()> {
        let has_valid_key = match &config.provider {
            ProviderConfig::OpenAI { api_key, .. }
            | ProviderConfig::Cohere { api_key, .. }
            | ProviderConfig::HuggingFace { api_key, .. }
            | ProviderConfig::Voyage { api_key, .. } => {
                !api_key.is_empty() && !api_key.starts_with("${")
            }
            ProviderConfig::Local { .. } => true,
        };

        if !has_valid_key {
            return Err(VectaDBError::Config(format!(
                "API key not set for provider '{}'. Set the appropriate environment variable.",
                config.name
            )));
        }

        Ok(())
    }

    /// Generate embedding for a single text
    pub async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        // Try plugin first
        if let Some(ref registry) = self.registry {
            match registry.get_active()?.embed(text).await {
                Ok(embedding) => return Ok(embedding),
                Err(e) => {
                    warn!("Plugin embedding failed: {}", e);
                    if !self.config.fallback_to_local {
                        return Err(e);
                    }
                }
            }
        }

        // Fall back to local service
        if let Some(ref service) = self.local_service {
            debug!("Using local embedding service");
            return service.encode(text);
        }

        Err(VectaDBError::Embedding(
            "No embedding service available".to_string(),
        ))
    }

    /// Generate embeddings for multiple texts
    pub async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(vec![]);
        }

        // Try plugin first
        if let Some(ref registry) = self.registry {
            match registry.get_active()?.embed_batch(texts).await {
                Ok(embeddings) => return Ok(embeddings),
                Err(e) => {
                    warn!("Plugin batch embedding failed: {}", e);
                    if !self.config.fallback_to_local {
                        return Err(e);
                    }
                }
            }
        }

        // Fall back to local service
        if let Some(ref service) = self.local_service {
            debug!("Using local embedding service for batch");
            return service.encode_batch(texts);
        }

        Err(VectaDBError::Embedding(
            "No embedding service available".to_string(),
        ))
    }

    /// Get embedding dimension
    pub fn dimension(&self) -> usize {
        if let Some(ref registry) = self.registry {
            if let Ok(plugin) = registry.get_active() {
                return plugin.dimension();
            }
        }

        if let Some(ref service) = self.local_service {
            return service.dimension();
        }

        self.config.dim
    }

    /// Get current provider name
    pub fn provider(&self) -> &str {
        &self.config.provider
    }

    /// Check if manager is healthy
    pub async fn health_check(&self) -> Result<bool> {
        if let Some(ref registry) = self.registry {
            match registry.get_active()?.health_check().await {
                Ok(health) => return Ok(health.healthy),
                Err(_) => {
                    if self.local_service.is_some() {
                        return Ok(true); // Fallback available
                    }
                    return Ok(false);
                }
            }
        }

        Ok(self.local_service.is_some())
    }

    /// Get usage statistics (if using plugin)
    pub fn get_stats(&self) -> Option<crate::embeddings::plugin::PluginStats> {
        self.registry
            .as_ref()
            .and_then(|r| r.get_active().ok())
            .map(|p| p.get_stats())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_local_manager_creation() {
        let config = EmbeddingConfig {
            model: "all-MiniLM-L6-v2".to_string(),
            dim: 384,
            provider: "local".to_string(),
            plugin_config_dir: "./config/embeddings".to_string(),
            fallback_to_local: false,
        };

        let rt = tokio::runtime::Runtime::new().unwrap();
        let manager = rt.block_on(EmbeddingManager::new(config));

        assert!(manager.is_ok());
        let manager = manager.unwrap();
        assert_eq!(manager.provider(), "local");
        assert_eq!(manager.dimension(), 384);
    }
}
