// HuggingFace Inference API embedding plugin
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

/// HuggingFace embedding plugin
pub struct HuggingFacePlugin {
    client: Client,
    config: Option<HuggingFaceConfig>,
    stats: Arc<RwLock<PluginStats>>,
}

#[derive(Debug, Clone)]
struct HuggingFaceConfig {
    api_key: String,
    model: String,
    base_url: String,
    dimension: usize,
    batch_size: usize,
    timeout_secs: u64,
}

// HuggingFace API request/response types
#[derive(Debug, Serialize)]
struct HuggingFaceRequest {
    inputs: InputType,
}

#[derive(Debug, Serialize)]
#[serde(untagged)]
enum InputType {
    Single(String),
    Batch(Vec<String>),
}

impl HuggingFacePlugin {
    pub fn new() -> Self {
        Self {
            client: Client::new(),
            config: None,
            stats: Arc::new(RwLock::new(PluginStats::default())),
        }
    }

    async fn make_request(&self, inputs: InputType) -> Result<Vec<Vec<f32>>> {
        let config = self
            .config
            .as_ref()
            .ok_or_else(|| VectaDBError::InvalidInput("Plugin not initialized".to_string()))?;

        let url = format!("{}/models/{}", config.base_url, config.model);

        let request = HuggingFaceRequest { inputs };

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
            .map_err(|e| VectaDBError::Embedding(format!("HuggingFace API request failed: {}", e)))?;

        let elapsed = start.elapsed();

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            return Err(VectaDBError::Embedding(format!(
                "HuggingFace API error {}: {}",
                status, error_text
            )));
        }

        // HuggingFace returns either Vec<f32> for single input or Vec<Vec<f32>> for batch
        let result: serde_json::Value = response
            .json()
            .await
            .map_err(|e| VectaDBError::Embedding(format!("Failed to parse HuggingFace response: {}", e)))?;

        let embeddings = match &result {
            // Single embedding: [0.1, 0.2, 0.3, ...]
            serde_json::Value::Array(ref arr) if !arr.is_empty() && arr[0].is_number() => {
                let embedding: Vec<f32> = serde_json::from_value(result)
                    .map_err(|e| VectaDBError::Embedding(format!("Failed to parse embedding: {}", e)))?;
                vec![embedding]
            }
            // Batch embeddings: [[0.1, 0.2], [0.3, 0.4], ...]
            serde_json::Value::Array(ref arr) if !arr.is_empty() && arr[0].is_array() => {
                serde_json::from_value(result)
                    .map_err(|e| VectaDBError::Embedding(format!("Failed to parse embeddings: {}", e)))?
            }
            _ => {
                return Err(VectaDBError::Embedding(
                    "Unexpected response format from HuggingFace".to_string(),
                ))
            }
        };

        // Update stats
        if let Ok(mut stats) = self.stats.write() {
            stats.total_requests += 1;
            stats.total_embeddings += embeddings.len() as u64;
            let total_latency = stats.avg_latency_ms * (stats.total_requests - 1) as f64;
            stats.avg_latency_ms = (total_latency + elapsed.as_millis() as f64) / stats.total_requests as f64;
        }

        Ok(embeddings)
    }
}

impl Default for HuggingFacePlugin {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl EmbeddingPlugin for HuggingFacePlugin {
    fn name(&self) -> &'static str {
        "huggingface"
    }

    fn version(&self) -> &'static str {
        "1.0.0"
    }

    fn dimension(&self) -> usize {
        self.config
            .as_ref()
            .map(|c| c.dimension)
            .unwrap_or(384)
    }

    fn max_batch_size(&self) -> usize {
        self.config
            .as_ref()
            .map(|c| c.batch_size)
            .unwrap_or(32)
    }

    async fn initialize(&mut self, config: PluginConfig) -> Result<()> {
        match config.provider {
            ProviderConfig::HuggingFace {
                api_key,
                model,
                base_url,
                dimension,
                batch_size,
                timeout_secs,
            } => {
                self.config = Some(HuggingFaceConfig {
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
                "Invalid provider config for HuggingFace plugin".to_string(),
            )),
        }
    }

    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let embeddings = self.make_request(InputType::Single(text.to_string())).await?;

        embeddings
            .into_iter()
            .next()
            .ok_or_else(|| VectaDBError::Embedding("No embedding returned".to_string()))
    }

    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(vec![]);
        }

        self.make_request(InputType::Batch(texts.to_vec())).await
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
        let plugin = HuggingFacePlugin::new();
        assert_eq!(plugin.name(), "huggingface");
        assert_eq!(plugin.version(), "1.0.0");
    }

    #[tokio::test]
    async fn test_plugin_initialization() {
        let mut plugin = HuggingFacePlugin::new();

        let config = PluginConfig {
            name: "huggingface".to_string(),
            provider: ProviderConfig::HuggingFace {
                api_key: "test-key".to_string(),
                model: "sentence-transformers/all-MiniLM-L6-v2".to_string(),
                base_url: "https://api-inference.huggingface.co".to_string(),
                dimension: 384,
                batch_size: 32,
                timeout_secs: 30,
            },
        };

        let result = plugin.initialize(config).await;
        assert!(result.is_ok());
        assert_eq!(plugin.dimension(), 384);
        assert_eq!(plugin.max_batch_size(), 32);
    }
}
