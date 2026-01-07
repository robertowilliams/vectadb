// Cohere embedding plugin
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

/// Cohere embedding plugin
pub struct CoherePlugin {
    client: Client,
    config: Option<CohereConfig>,
    stats: Arc<RwLock<PluginStats>>,
}

#[derive(Debug, Clone)]
struct CohereConfig {
    api_key: String,
    model: String,
    base_url: String,
    dimension: usize,
    batch_size: usize,
    timeout_secs: u64,
    input_type: String,
}

// Cohere API request/response types
#[derive(Debug, Serialize)]
struct CohereEmbedRequest {
    texts: Vec<String>,
    model: String,
    input_type: String,
    embedding_types: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct CohereEmbedResponse {
    embeddings: EmbeddingsData,
    meta: Meta,
}

#[derive(Debug, Deserialize)]
struct EmbeddingsData {
    float: Option<Vec<Vec<f32>>>,
}

#[derive(Debug, Deserialize)]
struct Meta {
    billed_units: Option<BilledUnits>,
}

#[derive(Debug, Deserialize)]
struct BilledUnits {
    input_tokens: Option<u64>,
}

impl CoherePlugin {
    pub fn new() -> Self {
        Self {
            client: Client::new(),
            config: None,
            stats: Arc::new(RwLock::new(PluginStats::default())),
        }
    }

    async fn make_request(&self, texts: Vec<String>) -> Result<CohereEmbedResponse> {
        let config = self
            .config
            .as_ref()
            .ok_or_else(|| VectaDBError::InvalidInput("Plugin not initialized".to_string()))?;

        let url = format!("{}/embed", config.base_url);

        let request = CohereEmbedRequest {
            texts: texts.clone(),
            model: config.model.clone(),
            input_type: config.input_type.clone(),
            embedding_types: vec!["float".to_string()],
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
            .map_err(|e| VectaDBError::Embedding(format!("Cohere API request failed: {}", e)))?;

        let elapsed = start.elapsed();

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            return Err(VectaDBError::Embedding(format!(
                "Cohere API error {}: {}",
                status, error_text
            )));
        }

        let result: CohereEmbedResponse = response
            .json()
            .await
            .map_err(|e| VectaDBError::Embedding(format!("Failed to parse Cohere response: {}", e)))?;

        // Update stats
        if let Ok(mut stats) = self.stats.write() {
            stats.total_requests += 1;
            if let Some(ref meta) = result.meta.billed_units {
                if let Some(tokens) = meta.input_tokens {
                    stats.total_tokens += tokens;
                }
            }
            stats.total_embeddings += texts.len() as u64;
            let total_latency = stats.avg_latency_ms * (stats.total_requests - 1) as f64;
            stats.avg_latency_ms = (total_latency + elapsed.as_millis() as f64) / stats.total_requests as f64;
        }

        Ok(result)
    }
}

impl Default for CoherePlugin {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl EmbeddingPlugin for CoherePlugin {
    fn name(&self) -> &'static str {
        "cohere"
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
            .unwrap_or(96)
    }

    async fn initialize(&mut self, config: PluginConfig) -> Result<()> {
        match config.provider {
            ProviderConfig::Cohere {
                api_key,
                model,
                base_url,
                dimension,
                batch_size,
                timeout_secs,
                input_type,
            } => {
                self.config = Some(CohereConfig {
                    api_key,
                    model,
                    base_url,
                    dimension,
                    batch_size,
                    timeout_secs,
                    input_type,
                });
                Ok(())
            }
            _ => Err(VectaDBError::InvalidInput(
                "Invalid provider config for Cohere plugin".to_string(),
            )),
        }
    }

    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let response = self.make_request(vec![text.to_string()]).await?;

        response
            .embeddings
            .float
            .and_then(|mut embeddings| embeddings.pop())
            .ok_or_else(|| VectaDBError::Embedding("No embedding returned".to_string()))
    }

    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(vec![]);
        }

        let response = self.make_request(texts.to_vec()).await?;

        response
            .embeddings
            .float
            .ok_or_else(|| VectaDBError::Embedding("No embeddings returned".to_string()))
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
        let plugin = CoherePlugin::new();
        assert_eq!(plugin.name(), "cohere");
        assert_eq!(plugin.version(), "1.0.0");
    }

    #[tokio::test]
    async fn test_plugin_initialization() {
        let mut plugin = CoherePlugin::new();

        let config = PluginConfig {
            name: "cohere".to_string(),
            provider: ProviderConfig::Cohere {
                api_key: "test-key".to_string(),
                model: "embed-english-v3.0".to_string(),
                base_url: "https://api.cohere.ai/v1".to_string(),
                dimension: 1024,
                batch_size: 96,
                timeout_secs: 30,
                input_type: "search_document".to_string(),
            },
        };

        let result = plugin.initialize(config).await;
        assert!(result.is_ok());
        assert_eq!(plugin.dimension(), 1024);
        assert_eq!(plugin.max_batch_size(), 96);
    }
}
