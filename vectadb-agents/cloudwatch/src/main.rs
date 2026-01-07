// CloudWatch agent for VectaDB - polls CloudWatch logs and sends to VectaDB API

mod cloudwatch_client;
mod config;
mod parser;
mod vectadb_client;

use anyhow::{Context, Result};
use std::collections::HashMap;
use std::env;
use std::time::Duration;
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use cloudwatch_client::CloudWatchClient;
use config::AgentConfig;
use parser::LogParser;
use vectadb_client::VectaDBClient;

/// Agent state for tracking last poll time per log group
#[derive(Debug, Clone)]
struct AgentState {
    /// Last poll timestamp (milliseconds since epoch) per log group
    last_poll_times: HashMap<String, i64>,
}

impl AgentState {
    fn new() -> Self {
        Self {
            last_poll_times: HashMap::new(),
        }
    }

    /// Get last poll time for log group, or calculate initial lookback
    fn get_last_poll_time(&self, log_group: &str, lookback_secs: u64) -> i64 {
        self.last_poll_times
            .get(log_group)
            .copied()
            .unwrap_or_else(|| {
                // First poll: look back N seconds
                let now = chrono::Utc::now().timestamp_millis();
                now - (lookback_secs as i64 * 1000)
            })
    }

    /// Update last poll time for log group
    fn update_last_poll_time(&mut self, log_group: &str, timestamp: i64) {
        self.last_poll_times.insert(log_group.to_string(), timestamp);
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing with JSON logging
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info,vectadb_cloudwatch_agent=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer().json())
        .init();

    info!("🚀 VectaDB CloudWatch Agent starting...");

    // Load .env file if present
    dotenvy::dotenv().ok();

    // Load configuration
    let config_path = env::var("CONFIG_PATH").unwrap_or_else(|_| "config.yaml".to_string());
    info!("Loading configuration from: {}", config_path);

    let config = AgentConfig::from_file(&config_path)
        .context("Failed to load configuration")?;

    info!("Configuration loaded successfully");
    info!("AWS Region: {}", config.aws.region);
    info!("VectaDB Endpoint: {}", config.vectadb.endpoint);
    info!("Monitoring {} log group(s)", config.log_groups.len());

    // Initialize CloudWatch client
    info!("Initializing CloudWatch client...");
    let cloudwatch = CloudWatchClient::new(&config.aws.region)
        .await
        .context("Failed to create CloudWatch client")?;
    info!("CloudWatch client initialized");

    // Initialize VectaDB client
    info!("Initializing VectaDB client...");
    let vectadb = VectaDBClient::new(&config.vectadb)
        .context("Failed to create VectaDB client")?;

    // Health check VectaDB
    info!("Checking VectaDB health...");
    match vectadb.health_check().await {
        Ok(health) => {
            info!("VectaDB is healthy: {} v{}", health.status, health.version);
        }
        Err(e) => {
            error!("VectaDB health check failed: {}", e);
            return Err(e).context("VectaDB is not available");
        }
    }

    // Initialize log parser
    let parser = LogParser::new();

    // Initialize agent state
    let mut state = AgentState::new();

    info!("Agent initialized successfully");
    info!(
        "Poll interval: {} seconds",
        config.agent.poll_interval_secs
    );
    info!("Lookback window: {} seconds", config.agent.lookback_secs);

    // Main poll loop
    loop {
        info!("Starting poll cycle...");

        let now = chrono::Utc::now().timestamp_millis();

        for log_group_config in &config.log_groups {
            let log_group = &log_group_config.name;

            // Get time range for this poll
            let start_time = state.get_last_poll_time(log_group, config.agent.lookback_secs);
            let end_time = now;

            info!(
                "Polling log group: {} (start: {}, end: {})",
                log_group, start_time, end_time
            );

            // Fetch log events from CloudWatch
            let log_events = match cloudwatch
                .fetch_log_events(
                    log_group,
                    start_time,
                    end_time,
                    log_group_config.filter_pattern.as_deref(),
                    None,
                )
                .await
            {
                Ok(events) => events,
                Err(e) => {
                    error!("Failed to fetch logs from {}: {}", log_group, e);
                    continue; // Skip to next log group
                }
            };

            if log_events.is_empty() {
                info!("No new events in log group: {}", log_group);
                state.update_last_poll_time(log_group, end_time);
                continue;
            }

            info!(
                "Fetched {} events from log group: {}",
                log_events.len(),
                log_group
            );

            // Parse log events
            let parsed_events: Vec<_> = log_events
                .iter()
                .map(|event| parser.parse(event, log_group_config))
                .collect();

            info!("Parsed {} events", parsed_events.len());

            // Send to VectaDB in bulk
            match vectadb
                .ingest_events_bulk(
                    parsed_events,
                    config.agent.auto_create_traces,
                    config.agent.generate_embeddings,
                )
                .await
            {
                Ok(response) => {
                    info!(
                        "Ingestion complete: {} succeeded, {} failed, {} trace(s)",
                        response.ingested,
                        response.failed,
                        response.trace_ids.len()
                    );

                    if !response.errors.is_empty() {
                        warn!("Ingestion errors: {:?}", response.errors);
                    }

                    // Update last poll time on success
                    state.update_last_poll_time(log_group, end_time);
                }
                Err(e) => {
                    error!("Failed to ingest events for {}: {}", log_group, e);
                    // Don't update last_poll_time so we retry next cycle
                }
            }
        }

        info!("Poll cycle complete");

        // Wait before next poll
        tokio::time::sleep(Duration::from_secs(config.agent.poll_interval_secs)).await;
    }
}
