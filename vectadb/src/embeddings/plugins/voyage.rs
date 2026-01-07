// Voyage embedding plugin
use crate::embeddings::plugin::{
    EmbeddingPlugin, PluginConfig, PluginHealth, PluginStats, ProviderConfig,
};
use crate::error::{Result, VectaDBError};
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::sync::RwLock;
use std::time::Instant;

/// Voyage embedding plugin
pub struct VoyagePlugin {
    client: Client,
    config: Option<VoyageConfig>,
    stats: Arc<RwLock<PluginStats>>,
}

#[derive(Debug, Clone)]
struct VoyageConfig {
    api_key: String,
    model: String,
    base_url: String,
    dimension: usize,
    batch_size: usize,
    timeout_secs: u64,
}

// Voyage API request/response types
#[derive(Debug, Serialize)]
struct VoyageRequest {
    input: Vec<String>,
    model: String,
}

#[derive(Debug, Deserialize)]
struct VoyageResponse {
    data: Vec<EmbeddingData>,
    #[serde(default)]
    usage: Option<Usage>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
    index: usize,
}

#[derive(Debug, Deserialize)]
struct Usage {
    #[serde(alias = "prompt_tokens")]
    total_tokens: u64,
}

impl VoyagePlugin {
    pub fn new() -> Self {
        Self {
            client: Client::new(),
            config: None,
            stats: Arc::new(RwLock::new(PluginStats::default())),
        }
    }

    async fn make_request(&self, texts: Vec<String>) -> Result<VoyageResponse> {
        let config = self
            .config
            .as_ref()
            .ok_or_else(|| VectaDBError::InvalidInput("Plugin not initialized".to_string()))?;

        let url = format!("{}/embeddings", config.base_url);

        let request = VoyageRequest {
            input: texts.clone(),
            model: config.model.clone(),
        };

        let start = Instant::now();

        let response = self
            .client
            .post(&url)
            .header("Authorization", format!("Bearer {}", config.api_key))
            .header("Content-Type", "application/json")
            .timeout(std::time::Duration::from_secs(config.timeout_secs))
            .json(&request)
            .send()
            .await
            .map_err(|e| VectaDBError::Embedding(format!("Voyage API request failed: {}", e)))?;

        let elapsed = start.elapsed();

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            return Err(VectaDBError::Embedding(format!(
                "Voyage API error {}: {}",
                status, error_text
            )));
        }

        let result: VoyageResponse = response
            .json()
            .await
            .map_err(|e| VectaDBError::Embedding(format!("Failed to parse Voyage response: {}", e)))?;

        // Update statistics
        if let Ok(mut stats) = self.stats.write() {
            stats.total_requests += 1;
            if let Some(ref usage) = result.usage {
                stats.total_tokens += usage.total_tokens;
            }
            stats.total_embeddings += texts.len() as u64;
            let total_latency = stats.avg_latency_ms * (stats.total_requests - 1) as f64;
            stats.avg_latency_ms = (total_latency + elapsed.as_millis() as f64) / stats.total_requests as f64;
        }

        Ok(result)
    }
}

impl Default for VoyagePlugin {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl EmbeddingPlugin for VoyagePlugin {
    fn name(&self) -> &'static str {
        "voyage"
    }

    fn version(&self) -> &'static str {
        "1.0.0"
    }

    fn dimension(&self) -> usize {
        self.config
            .as_ref()
            .map(|c| c.dimension)
            .unwrap_or(1024)
    }

    fn max_batch_size(&self) -> usize {
        self.config
            .as_ref()
            .map(|c| c.batch_size)
            .unwrap_or(128)
    }

    async fn initialize(&mut self, config: PluginConfig) -> Result<()> {
        // TODO: Update this to match your ProviderConfig variant
        match config.provider {
            ProviderConfig::Voyage {
                api_key,
                model,
                base_url,
                dimension,
                batch_size,
                timeout_secs,
            } => {
                self.config = Some(VoyageConfig {
                    api_key,
                    model,
                    base_url,
                    dimension,
                    batch_size,
                    timeout_secs,
                });
                Ok(())
            }
            _ => Err(VectaDBError::InvalidInput(
                "Invalid provider config for Voyage plugin".to_string(),
            )),
        }
    }

    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let response = self.make_request(vec![text.to_string()]).await?;

        response
            .data
            .into_iter()
            .next()
            .map(|d| d.embedding)
            .ok_or_else(|| VectaDBError::Embedding("No embedding returned".to_string()))
    }

    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(vec![]);
        }

        let response = self.make_request(texts.to_vec()).await?;

        // Sort by index to ensure correct order
        let mut data = response.data;
        data.sort_by_key(|d| d.index);

        Ok(data.into_iter().map(|d| d.embedding).collect())
    }

    async fn health_check(&self) -> Result<PluginHealth> {
        if self.config.is_none() {
            return Ok(PluginHealth {
                healthy: false,
                message: Some("Plugin not initialized".to_string()),
                latency_ms: None,
            });
        }

        // Try a simple embedding request
        let start = Instant::now();
        match self.embed("health check").await {
            Ok(_) => Ok(PluginHealth {
                healthy: true,
                message: Some("API is responsive".to_string()),
                latency_ms: Some(start.elapsed().as_millis() as u64),
            }),
            Err(e) => Ok(PluginHealth {
                healthy: false,
                message: Some(format!("Health check failed: {}", e)),
                latency_ms: Some(start.elapsed().as_millis() as u64),
            }),
        }
    }

    fn get_stats(&self) -> PluginStats {
        self.stats.read().unwrap().clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_plugin_creation() {
        let plugin = VoyagePlugin::new();
        assert_eq!(plugin.name(), "voyage");
        assert_eq!(plugin.version(), "1.0.0");
    }

    #[test]
    fn test_default_dimensions() {
        let plugin = VoyagePlugin::new();
        assert_eq!(plugin.dimension(), 1024);
        assert_eq!(plugin.max_batch_size(), 128);
    }

    // Add more tests as needed
}
