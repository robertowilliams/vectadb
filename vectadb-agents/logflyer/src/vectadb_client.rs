// VectaDB API client — bulk event ingestion for vectadb-logflyer.
// Adapted from vectadb-agents/cloudwatch/src/vectadb_client.rs.

use anyhow::{Context, Result};
use reqwest::Client;
use std::time::Duration;
use tracing::{debug, error, warn};

use crate::config::VectaDBConfig;
use crate::models::{BulkIngestionRequest, BulkIngestionResponse, HealthResponse, IngestionOptions, VectaDBEvent};

pub struct VectaDBClient {
    client: Client,
    endpoint: String,
    api_key: Option<String>,
    batch_size: usize,
}

impl VectaDBClient {
    pub fn new(config: &VectaDBConfig) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(config.timeout_secs))
            .build()
            .context("Failed to build HTTP client for VectaDB")?;

        Ok(Self {
            client,
            endpoint: config.endpoint.trim_end_matches('/').to_string(),
            api_key: config.api_key.clone(),
            batch_size: config.batch_size,
        })
    }

    // ── Health check ──────────────────────────────────────────────────────────

    pub async fn health_check(&self) -> Result<HealthResponse> {
        let url = format!("{}/health", self.endpoint);
        let resp = self
            .build_get(&url)
            .send()
            .await
            .context("VectaDB health check request failed")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            anyhow::bail!("VectaDB health check returned {}: {}", status, body);
        }

        resp.json::<HealthResponse>()
            .await
            .context("Failed to parse VectaDB health response")
    }

    // ── Bulk ingestion ────────────────────────────────────────────────────────

    /// Ingest a slice of events, splitting automatically into batches.
    pub async fn ingest_bulk(
        &self,
        events: Vec<VectaDBEvent>,
        auto_create_traces: bool,
        generate_embeddings: bool,
    ) -> Result<BulkIngestionResponse> {
        if events.is_empty() {
            return Ok(BulkIngestionResponse {
                ingested: 0,
                failed: 0,
                trace_ids: vec![],
                errors: vec![],
            });
        }

        let chunks: Vec<_> = events.chunks(self.batch_size).collect();
        let n_batches = chunks.len();

        let mut total_ingested = 0usize;
        let mut total_failed = 0usize;
        let mut all_trace_ids: Vec<String> = Vec::new();
        let mut all_errors = Vec::new();

        for (i, chunk) in chunks.into_iter().enumerate() {
            debug!("Sending batch {}/{} ({} events)", i + 1, n_batches, chunk.len());

            let request = BulkIngestionRequest {
                events: chunk.to_vec(),
                options: IngestionOptions {
                    auto_create_traces,
                    generate_embeddings,
                    extract_relationships: false,
                },
            };

            match self.send_batch(&request).await {
                Ok(resp) => {
                    total_ingested += resp.ingested;
                    total_failed += resp.failed;
                    all_trace_ids.extend(resp.trace_ids);
                    all_errors.extend(resp.errors);

                    if resp.failed > 0 {
                        warn!("Batch {}: {} events failed ingestion", i + 1, resp.failed);
                    }
                }
                Err(e) => {
                    error!("Batch {} failed entirely: {}", i + 1, e);
                    total_failed += chunk.len();
                }
            }
        }

        Ok(BulkIngestionResponse {
            ingested: total_ingested,
            failed: total_failed,
            trace_ids: all_trace_ids,
            errors: all_errors,
        })
    }

    // ── Internal helpers ──────────────────────────────────────────────────────

    async fn send_batch(&self, request: &BulkIngestionRequest) -> Result<BulkIngestionResponse> {
        let url = format!("{}/api/v1/events/batch", self.endpoint);

        let resp = self
            .build_post(&url)
            .json(request)
            .send()
            .await
            .context("Bulk ingestion request failed")?;

        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            anyhow::bail!("VectaDB batch API returned {}: {}", status, body);
        }

        resp.json::<BulkIngestionResponse>()
            .await
            .context("Failed to parse bulk ingestion response")
    }

    fn build_get(&self, url: &str) -> reqwest::RequestBuilder {
        let mut req = self.client.get(url);
        if let Some(key) = &self.api_key {
            req = req.bearer_auth(key);
        }
        req
    }

    fn build_post(&self, url: &str) -> reqwest::RequestBuilder {
        let mut req = self.client.post(url).header("Content-Type", "application/json");
        if let Some(key) = &self.api_key {
            req = req.bearer_auth(key);
        }
        req
    }
}
