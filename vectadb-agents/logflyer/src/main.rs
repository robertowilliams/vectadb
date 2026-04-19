// vectadb-logflyer — LLM-powered agentic log ingestion daemon
//
// Poll loop:
//   for each watched log file
//     1. Tail new lines since last poll  (tailer.rs)
//     2. Classify lines in batches       (classifier.rs)
//     3. Keep only agentic events        (is_agentic == true)
//     4. Convert to VectaDB events       (models.rs)
//     5. Bulk-ingest into VectaDB        (vectadb_client.rs)
//
// Configuration is loaded from a YAML file (default: config.yaml).
// Override the path with the CONFIG_PATH environment variable.

mod classifier;
mod config;
mod models;
mod tailer;
mod vectadb_client;

use anyhow::{Context, Result};
use std::env;
use std::path::Path;
use std::time::Duration;
use tracing::{error, info, warn};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use classifier::LLMClassifier;
use config::AgentConfig;
use models::VectaDBEvent;
use tailer::FileTailer;
use vectadb_client::VectaDBClient;

#[tokio::main]
async fn main() -> Result<()> {
    // ── Tracing / logging ────────────────────────────────────────────────────
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info,vectadb_logflyer=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer().json())
        .init();

    info!("🪰  VectaDB LogFlyer starting…");

    // Load .env if present
    dotenvy::dotenv().ok();

    // ── Configuration ────────────────────────────────────────────────────────
    let config_path = env::var("CONFIG_PATH").unwrap_or_else(|_| "config.yaml".to_string());
    info!("Loading config from: {}", config_path);

    let config = AgentConfig::from_file(&config_path)
        .context("Failed to load configuration")?;

    info!("LLM server   : {}", config.llm.base_url);
    info!("LLM model    : {}", config.llm.model);
    info!("VectaDB      : {}", config.vectadb.endpoint);
    info!("Watching {} file(s)", config.log_files.len());
    for f in &config.log_files {
        info!("  → {} (agent_id={})", f.path, f.agent_id);
    }

    // ── Clients ──────────────────────────────────────────────────────────────
    let vectadb = VectaDBClient::new(&config.vectadb)
        .context("Failed to create VectaDB client")?;

    // Health-check VectaDB before starting the loop
    match vectadb.health_check().await {
        Ok(h) => info!("VectaDB healthy: {} v{}", h.status, h.version),
        Err(e) => {
            if config.agent.fail_silently {
                warn!("VectaDB health check failed (continuing anyway): {}", e);
            } else {
                return Err(e).context("VectaDB is not available");
            }
        }
    }

    let classifier = LLMClassifier::new(config.llm)
        .context("Failed to create LLM classifier")?;

    let mut tailer = FileTailer::new(config.agent.lookback_lines);

    let poll_interval = Duration::from_secs(config.agent.poll_interval_secs);
    let batch_size = config.agent.classification_batch_size;
    let auto_create_traces = config.agent.auto_create_traces;
    let generate_embeddings = config.agent.generate_embeddings;
    let fail_silently = config.agent.fail_silently;

    info!(
        "Poll interval: {}s | Classification batch: {} lines | Lookback: {} lines",
        config.agent.poll_interval_secs, batch_size, config.agent.lookback_lines
    );

    // ── Main poll loop ───────────────────────────────────────────────────────
    loop {
        for file_cfg in &config.log_files {
            let path = Path::new(&file_cfg.path);

            // 1. Tail new lines
            let new_lines = match tailer.poll(path, &file_cfg.agent_id, file_cfg.session_id.as_deref()) {
                Ok(lines) => lines,
                Err(e) => {
                    if fail_silently {
                        warn!("Error reading {}: {}", file_cfg.path, e);
                        continue;
                    } else {
                        return Err(e).with_context(|| format!("Error tailing {}", file_cfg.path));
                    }
                }
            };

            if new_lines.is_empty() {
                continue;
            }

            info!(
                "Tailed {} new line(s) from {} [agent={}]",
                new_lines.len(),
                file_cfg.path,
                file_cfg.agent_id
            );

            // 2. Classify in batches
            let mut agentic_events: Vec<VectaDBEvent> = Vec::new();
            let total_lines = new_lines.len();
            let mut agentic_count = 0usize;

            for chunk in new_lines.chunks(batch_size) {
                let classified = classifier.classify(chunk.to_vec()).await;

                for event in classified {
                    if event.is_agentic {
                        agentic_count += 1;
                        agentic_events.push(event.into());
                    }
                }
            }

            info!(
                "{} of {} line(s) identified as agentic [agent={}]",
                agentic_count, total_lines, file_cfg.agent_id
            );

            if agentic_events.is_empty() {
                continue;
            }

            // 3. Ingest agentic events into VectaDB
            match vectadb
                .ingest_bulk(agentic_events, auto_create_traces, generate_embeddings)
                .await
            {
                Ok(resp) => {
                    info!(
                        "Ingested {} event(s), {} failed, {} trace(s) [agent={}]",
                        resp.ingested,
                        resp.failed,
                        resp.trace_ids.len(),
                        file_cfg.agent_id
                    );
                    if !resp.errors.is_empty() {
                        warn!("Ingestion errors: {:?}", resp.errors);
                    }
                }
                Err(e) => {
                    error!("VectaDB ingestion failed for {}: {}", file_cfg.path, e);
                    if !fail_silently {
                        return Err(e);
                    }
                }
            }
        }

        tokio::time::sleep(poll_interval).await;
    }
}
