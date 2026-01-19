// VectaDB API client for event ingestion

use anyhow::{Context, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, error, info, warn};

use crate::config::VectaDBConfig;

/// VectaDB API client
pub struct VectaDBClient {
    client: Client,
    endpoint: String,
    api_key: Option<String>,
    batch_size: usize,
}

/// Event ingestion request matching VectaDB API schema
#[derive(Debug, Clone, Serialize)]
pub struct EventIngestionRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trace_id: Option<String>,
    pub timestamp: chrono::DateTime<chrono::Utc>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub event_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub agent_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub session_id: Option<String>,
    pub properties: serde_json::Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source: Option<LogSource>,
}

/// Log source metadata
#[derive(Debug, Clone, Serialize)]
pub struct LogSource {
    pub system: String,
    pub log_group: String,
    pub log_stream: String,
    pub log_id: String,
}

/// Bulk event ingestion request
#[derive(Debug, Serialize)]
struct BulkEventIngestionRequest {
    events: Vec<EventIngestionRequest>,
    options: IngestionOptions,
}

/// Ingestion options
#[derive(Debug, Serialize)]
struct IngestionOptions {
    auto_create_traces: bool,
    generate_embeddings: bool,
}

/// Event ingestion response
#[derive(Debug, Deserialize)]
pub struct EventIngestionResponse {
    pub event_id: String,
    pub trace_id: String,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

/// Bulk ingestion response
#[derive(Debug, Deserialize)]
pub struct BulkEventIngestionResponse {
    pub ingested: usize,
    pub failed: usize,
    pub trace_ids: Vec<String>,
    pub errors: Vec<IngestionError>,
}

/// Ingestion error details
#[derive(Debug, Deserialize)]
pub struct IngestionError {
    pub index: usize,
    pub error: String,
}

/// Health check response
#[derive(Debug, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub version: String,
    pub ontology_loaded: bool,
}

impl VectaDBClient {
    /// Create a new VectaDB client
    pub fn new(config: &VectaDBConfig) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(config.timeout_secs))
            .build()
            .context("Failed to create HTTP client")?;

        Ok(Self {
            client,
            endpoint: config.endpoint.clone(),
            api_key: config.api_key.clone(),
            batch_size: config.batch_size,
        })
    }

    /// Check VectaDB health
    pub async fn health_check(&self) -> Result<HealthResponse> {
        let url = format!("{}/health", self.endpoint);

        debug!("Health check: {}", url);

        let response = self
            .client
            .get(&url)
            .send()
            .await
            .context("Failed to send health check request")?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            anyhow::bail!("Health check failed: {} - {}", status, body);
        }

        let health: HealthResponse = response
            .json()
            .await
            .context("Failed to parse health response")?;

        Ok(health)
    }

    /// Ingest events in bulk with automatic batching and retry
    pub async fn ingest_events_bulk(
        &self,
        events: Vec<EventIngestionRequest>,
        auto_create_traces: bool,
        generate_embeddings: bool,
    ) -> Result<BulkEventIngestionResponse> {
        if events.is_empty() {
            return Ok(BulkEventIngestionResponse {
                ingested: 0,
                failed: 0,
                trace_ids: vec![],
                errors: vec![],
            });
        }

        let url = format!("{}/api/v1/events/batch", self.endpoint);

        // Split into batches if needed
        let batches: Vec<_> = events.chunks(self.batch_size).collect();

        info!(
            "Ingesting {} events in {} batch(es)",
            events.len(),
            batches.len()
        );

        let mut total_ingested = 0;
        let mut total_failed = 0;
        let mut all_trace_ids = Vec::new();
        let mut all_errors = Vec::new();

        for (batch_idx, batch) in batches.iter().enumerate() {
            debug!("Processing batch {}/{}", batch_idx + 1, batches.len());

            let request = BulkEventIngestionRequest {
                events: batch.to_vec(),
                options: IngestionOptions {
                    auto_create_traces,
                    generate_embeddings,
                },
            };

            // Retry logic: try up to 3 times
            let mut attempts = 0;
            let max_attempts = 3;
            let mut last_error = None;

            while attempts < max_attempts {
                attempts += 1;

                match self.send_bulk_request(&url, &request).await {
                    Ok(response) => {
                        total_ingested += response.ingested;
                        total_failed += response.failed;

                        // Merge trace IDs (deduplicate)
                        for trace_id in response.trace_ids {
                            if !all_trace_ids.contains(&trace_id) {
                                all_trace_ids.push(trace_id);
                            }
                        }

                        // Adjust error indices for global batch
                        for mut error in response.errors {
                            error.index += batch_idx * self.batch_size;
                            all_errors.push(error);
                        }

                        break; // Success
                    }
                    Err(e) => {
                        warn!(
                            "Batch {} attempt {}/{} failed: {}",
                            batch_idx + 1,
                            attempts,
                            max_attempts,
                            e
                        );
                        last_error = Some(e);

                        if attempts < max_attempts {
                            // Exponential backoff: 1s, 2s, 4s
                            let delay = Duration::from_secs(2u64.pow(attempts - 1));
                            tokio::time::sleep(delay).await;
                        }
                    }
                }
            }

            // If all retries failed, mark entire batch as failed
            if attempts >= max_attempts {
                error!(
                    "Batch {} failed after {} attempts: {:?}",
                    batch_idx + 1,
                    max_attempts,
                    last_error
                );
                total_failed += batch.len();

                // Add error for each event in failed batch
                for i in 0..batch.len() {
                    all_errors.push(IngestionError {
                        index: batch_idx * self.batch_size + i,
                        error: format!(
                            "Batch failed after {} retries: {}",
                            max_attempts,
                            last_error.as_ref().map(|e| e.to_string()).unwrap_or_default()
                        ),
                    });
                }
            }
        }

        Ok(BulkEventIngestionResponse {
            ingested: total_ingested,
            failed: total_failed,
            trace_ids: all_trace_ids,
            errors: all_errors,
        })
    }

    /// Send bulk ingestion request (internal helper)
    async fn send_bulk_request(
        &self,
        url: &str,
        request: &BulkEventIngestionRequest,
    ) -> Result<BulkEventIngestionResponse> {
        let mut req_builder = self.client.post(url).json(request);

        // Add API key header if configured
        if let Some(ref api_key) = self.api_key {
            req_builder = req_builder.header("X-API-Key", api_key);
        }

        let response = req_builder
            .send()
            .await
            .context("Failed to send bulk ingestion request")?;

        let status = response.status();

        if !status.is_success() {
            let body = response.text().await.unwrap_or_default();
            anyhow::bail!("Bulk ingestion failed: {} - {}", status, body);
        }

        let bulk_response: BulkEventIngestionResponse = response
            .json()
            .await
            .context("Failed to parse bulk ingestion response")?;

        if bulk_response.failed > 0 {
            warn!(
                "Bulk ingestion partial failure: {} succeeded, {} failed",
                bulk_response.ingested, bulk_response.failed
            );
        }

        Ok(bulk_response)
    }

    /// Get batch size
    pub fn batch_size(&self) -> usize {
        self.batch_size
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::VectaDBConfig;

    #[test]
    fn test_client_creation() {
        let config = VectaDBConfig {
            endpoint: "http://localhost:8080".to_string(),
            api_key: None,
            batch_size: 100,
            timeout_secs: 30,
        };

        let client = VectaDBClient::new(&config);
        assert!(client.is_ok());

        let client = client.unwrap();
        assert_eq!(client.batch_size(), 100);
    }

    #[test]
    fn test_event_serialization() {
        let event = EventIngestionRequest {
            trace_id: None,
            timestamp: chrono::Utc::now(),
            event_type: Some("test".to_string()),
            agent_id: Some("agent-001".to_string()),
            session_id: Some("session-123".to_string()),
            properties: serde_json::json!({"message": "test event"}),
            source: Some(LogSource {
                system: "cloudwatch".to_string(),
                log_group: "/test".to_string(),
                log_stream: "stream-1".to_string(),
                log_id: "event-1".to_string(),
            }),
        };

        let json = serde_json::to_string(&event);
        assert!(json.is_ok());
    }
}
