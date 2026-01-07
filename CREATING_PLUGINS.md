# Creating Custom Embedding Plugins for VectaDB

This guide walks you through creating a custom embedding plugin for VectaDB. You'll learn how to integrate any embedding provider into VectaDB's modular plugin system.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Plugin Architecture](#plugin-architecture)
4. [Step-by-Step Tutorial](#step-by-step-tutorial)
5. [Testing Your Plugin](#testing-your-plugin)
6. [Best Practices](#best-practices)
7. [Real-World Examples](#real-world-examples)
8. [Troubleshooting](#troubleshooting)

---

## Overview

VectaDB's plugin system allows you to integrate any embedding provider by implementing the `EmbeddingPlugin` trait. Once implemented, users can switch to your provider with a single environment variable change.

**What you'll build:**
- A Rust module implementing the `EmbeddingPlugin` trait
- A YAML configuration file for your provider
- Tests to verify functionality
- Documentation for users

**Time to complete:** 1-2 hours

---

## Prerequisites

### Knowledge Required
- Basic Rust programming
- HTTP/REST API concepts
- Async/await in Rust
- JSON serialization/deserialization

### Tools Needed
```bash
# Rust toolchain
rustc --version  # Should be 1.70+
cargo --version

# Optional: API key from your embedding provider
```

### Project Setup
```bash
cd vectadb
git checkout -b feature/add-my-provider-plugin
```

---

## Plugin Architecture

### The EmbeddingPlugin Trait

All plugins implement this trait:

```rust
#[async_trait]
pub trait EmbeddingPlugin: Send + Sync {
    // Identification
    fn name(&self) -> &'static str;
    fn version(&self) -> &'static str;

    // Capabilities
    fn dimension(&self) -> usize;
    fn max_batch_size(&self) -> usize;

    // Lifecycle
    async fn initialize(&mut self, config: PluginConfig) -> Result<()>;

    // Core functionality
    async fn embed(&self, text: &str) -> Result<Vec<f32>>;
    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;

    // Monitoring
    async fn health_check(&self) -> Result<PluginHealth>;
    fn get_stats(&self) -> PluginStats;
}
```

### Plugin Structure

```
src/embeddings/plugins/
├── mod.rs              # Export your plugin here
├── myprovider.rs       # Your plugin implementation
├── openai.rs           # Reference implementation
├── cohere.rs
└── huggingface.rs

config/embeddings/
└── myprovider.yaml     # Configuration file
```

---

## Step-by-Step Tutorial

Let's create a plugin for **Voyage AI** as an example.

### Step 1: Create the Plugin File

Create `src/embeddings/plugins/voyage.rs`:

```rust
// Voyage AI embedding plugin
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

/// Voyage AI embedding plugin
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

// API request/response types
#[derive(Debug, Serialize)]
struct VoyageRequest {
    input: Vec<String>,
    model: String,
}

#[derive(Debug, Deserialize)]
struct VoyageResponse {
    data: Vec<EmbeddingData>,
    usage: Usage,
}

#[derive(Debug, Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
    index: usize,
}

#[derive(Debug, Deserialize)]
struct Usage {
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
            stats.total_tokens += result.usage.total_tokens;
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
        // Extract Voyage-specific config
        // You'll need to add Voyage to the ProviderConfig enum first
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

    #[tokio::test]
    async fn test_plugin_initialization() {
        let mut plugin = VoyagePlugin::new();

        let config = PluginConfig {
            name: "voyage".to_string(),
            provider: ProviderConfig::Voyage {
                api_key: "test-key".to_string(),
                model: "voyage-2".to_string(),
                base_url: "https://api.voyageai.com/v1".to_string(),
                dimension: 1024,
                batch_size: 128,
                timeout_secs: 30,
            },
        };

        let result = plugin.initialize(config).await;
        assert!(result.is_ok());
        assert_eq!(plugin.dimension(), 1024);
        assert_eq!(plugin.max_batch_size(), 128);
    }
}
```

### Step 2: Update ProviderConfig Enum

Edit `src/embeddings/plugin.rs` to add your provider:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "provider", rename_all = "lowercase")]
pub enum ProviderConfig {
    OpenAI { /* ... */ },
    Cohere { /* ... */ },
    HuggingFace { /* ... */ },
    Local { /* ... */ },

    // Add your provider here
    Voyage {
        api_key: String,
        model: String,
        #[serde(default = "default_voyage_base_url")]
        base_url: String,
        #[serde(default = "default_dimension")]
        dimension: usize,
        #[serde(default = "default_batch_size")]
        batch_size: usize,
        #[serde(default = "default_timeout")]
        timeout_secs: u64,
    },
}

// Add default function
fn default_voyage_base_url() -> String {
    "https://api.voyageai.com/v1".to_string()
}
```

### Step 3: Register the Plugin

Update `src/embeddings/plugins/mod.rs`:

```rust
// Embedding provider plugins
pub mod cohere;
pub mod huggingface;
pub mod openai;
pub mod voyage;  // Add this line

pub use cohere::CoherePlugin;
pub use huggingface::HuggingFacePlugin;
pub use openai::OpenAIPlugin;
pub use voyage::VoyagePlugin;  // Add this line
```

### Step 4: Export from Main Module

Update `src/embeddings/mod.rs`:

```rust
pub use plugins::{CoherePlugin, HuggingFacePlugin, OpenAIPlugin, VoyagePlugin};
```

### Step 5: Update EmbeddingManager

Edit `src/embeddings/manager.rs` to handle your provider:

```rust
// In init_plugin_system() method, add:
match self.config.provider.as_str() {
    "openai" => { /* ... */ }
    "cohere" => { /* ... */ }
    "huggingface" => { /* ... */ }
    "voyage" => {
        let mut plugin = VoyagePlugin::new();
        plugin.initialize(plugin_config).await?;
        registry.register(Box::new(plugin));
    }
    _ => { /* ... */ }
}
```

### Step 6: Create Configuration File

Create `config/embeddings/voyage.yaml`:

```yaml
# Voyage AI Embedding Plugin Configuration
#
# Usage:
#   1. Get API key from: https://dash.voyageai.com/
#   2. Set environment variable: export VOYAGE_API_KEY="..."
#
# Models available:
#   - voyage-2 (1024 dimensions) - Best quality
#   - voyage-lite-02-instruct (1024 dimensions) - Instruction-tuned
#   - voyage-code-2 (1536 dimensions) - For code search
#
# Pricing: $0.10/1M tokens

name: "voyage"
provider: "voyage"
api_key: "${VOYAGE_API_KEY}"
model: "voyage-2"
base_url: "https://api.voyageai.com/v1"
dimension: 1024
batch_size: 128
timeout_secs: 30
```

### Step 7: Update Documentation

Add your provider to `config/embeddings/README.md`:

```markdown
### Voyage AI

**Best for:** High-quality retrieval, production use

**Models:**
- `voyage-2` (1024d) - Best quality
- `voyage-lite-02-instruct` (1024d) - Instruction-tuned
- `voyage-code-2` (1536d) - Code search

**Configuration:**
```yaml
name: "voyage"
provider: "voyage"
api_key: "${VOYAGE_API_KEY}"
model: "voyage-2"
dimension: 1024
```

**Pricing:** $0.10/1M tokens
```

### Step 8: Update Environment Variables

Add to `src/embeddings/manager.rs` in `expand_env_vars()`:

```rust
let env_vars = [
    "OPENAI_API_KEY",
    "COHERE_API_KEY",
    "HF_API_KEY",
    "VOYAGE_API_KEY",  // Add this
    "JINA_API_KEY",
];
```

---

## Testing Your Plugin

### Unit Tests

Run the built-in tests:

```bash
cargo test voyage
```

### Integration Test

Create a test file `tests/voyage_integration.rs`:

```rust
#[cfg(test)]
mod voyage_tests {
    use vectadb::embeddings::{EmbeddingManager, PluginConfig, ProviderConfig};

    #[tokio::test]
    #[ignore] // Only run with real API key
    async fn test_voyage_real_api() {
        let api_key = std::env::var("VOYAGE_API_KEY").expect("VOYAGE_API_KEY not set");

        let config = PluginConfig {
            name: "voyage".to_string(),
            provider: ProviderConfig::Voyage {
                api_key,
                model: "voyage-2".to_string(),
                base_url: "https://api.voyageai.com/v1".to_string(),
                dimension: 1024,
                batch_size: 128,
                timeout_secs: 30,
            },
        };

        let mut plugin = vectadb::embeddings::VoyagePlugin::new();
        plugin.initialize(config).await.unwrap();

        // Test single embedding
        let embedding = plugin.embed("Hello, world!").await.unwrap();
        assert_eq!(embedding.len(), 1024);

        // Test batch
        let texts = vec!["Text 1".to_string(), "Text 2".to_string()];
        let embeddings = plugin.embed_batch(&texts).await.unwrap();
        assert_eq!(embeddings.len(), 2);
        assert_eq!(embeddings[0].len(), 1024);

        // Test health check
        let health = plugin.health_check().await.unwrap();
        assert!(health.healthy);

        // Check stats
        let stats = plugin.get_stats();
        assert!(stats.total_requests > 0);
        assert!(stats.total_embeddings >= 3);
    }
}
```

Run with:
```bash
export VOYAGE_API_KEY="your-key"
cargo test --test voyage_integration -- --ignored
```

### Manual Testing

Create a test script `test_voyage.sh`:

```bash
#!/bin/bash

export VOYAGE_API_KEY="your-key-here"
export EMBEDDING_PROVIDER="voyage"

# Start VectaDB
cargo run --release &
PID=$!

# Wait for startup
sleep 5

# Test health endpoint
curl http://localhost:8080/health

# Test embedding generation
curl -X POST http://localhost:8080/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "test",
    "agent_id": "test-agent",
    "properties": {"text": "Hello from Voyage!"}
  }'

# Check stats
curl http://localhost:8080/api/v1/embeddings/stats

# Cleanup
kill $PID
```

---

## Best Practices

### Error Handling

```rust
// ✅ Good: Specific error messages
return Err(VectaDBError::Embedding(format!(
    "Voyage API error {}: {}",
    status, error_text
)));

// ❌ Bad: Generic errors
return Err(VectaDBError::Embedding("API error".to_string()));
```

### Rate Limiting

```rust
// Add rate limiting for providers with limits
use tokio::time::{sleep, Duration};

async fn make_request_with_retry(&self, texts: Vec<String>, retries: u32) -> Result<Response> {
    for attempt in 0..retries {
        match self.make_request(texts.clone()).await {
            Ok(response) => return Ok(response),
            Err(e) if e.to_string().contains("rate_limit") => {
                if attempt < retries - 1 {
                    let backoff = Duration::from_secs(2_u64.pow(attempt));
                    tracing::warn!("Rate limited, retrying in {:?}", backoff);
                    sleep(backoff).await;
                    continue;
                }
                return Err(e);
            }
            Err(e) => return Err(e),
        }
    }
    unreachable!()
}
```

### Connection Pooling

```rust
// Use reqwest's built-in connection pooling
impl MyPlugin {
    pub fn new() -> Self {
        let client = Client::builder()
            .pool_max_idle_per_host(10)  // Reuse connections
            .timeout(Duration::from_secs(30))
            .build()
            .unwrap();

        Self {
            client,
            // ...
        }
    }
}
```

### Logging

```rust
use tracing::{debug, info, warn, error};

async fn make_request(&self, texts: Vec<String>) -> Result<Response> {
    debug!("Making request with {} texts", texts.len());

    match self.client.post(&url).send().await {
        Ok(response) => {
            info!("Request successful, status: {}", response.status());
            Ok(response)
        }
        Err(e) => {
            error!("Request failed: {}", e);
            Err(e.into())
        }
    }
}
```

### Statistics Tracking

```rust
// Always update stats for monitoring
if let Ok(mut stats) = self.stats.write() {
    stats.total_requests += 1;
    stats.total_embeddings += embeddings.len() as u64;

    // Update average latency
    let total_latency = stats.avg_latency_ms * (stats.total_requests - 1) as f64;
    stats.avg_latency_ms = (total_latency + elapsed.as_millis() as f64) / stats.total_requests as f64;

    // Track errors
    if is_error {
        stats.failed_requests += 1;
    }
}
```

---

## Real-World Examples

### Example 1: Jina AI Plugin

For providers with OpenAI-compatible APIs:

```rust
// Jina AI uses OpenAI-compatible format
pub struct JinaPlugin {
    client: Client,
    config: Option<JinaConfig>,
    stats: Arc<RwLock<PluginStats>>,
}

// Can reuse OpenAI request/response types
#[derive(Debug, Serialize)]
struct JinaRequest {
    input: Vec<String>,
    model: String,
}

// Implementation is similar to OpenAI plugin
```

### Example 2: Azure OpenAI Plugin

For Azure-hosted services:

```rust
pub struct AzureOpenAIPlugin {
    // Azure uses different authentication
    api_key: String,
    endpoint: String,  // Custom endpoint
    deployment_name: String,  // Azure-specific
    api_version: String,  // e.g., "2023-05-15"
}

async fn make_request(&self, texts: Vec<String>) -> Result<Response> {
    // Azure uses query parameters for version
    let url = format!(
        "{}/openai/deployments/{}/embeddings?api-version={}",
        self.endpoint, self.deployment_name, self.api_version
    );

    // Azure uses api-key header
    self.client
        .post(&url)
        .header("api-key", &self.api_key)
        .json(&request)
        .send()
        .await
}
```

### Example 3: Local Model Plugin (via HTTP)

For self-hosted models:

```rust
pub struct LocalHTTPPlugin {
    base_url: String,  // e.g., "http://localhost:8000"
    model_name: String,
}

// No authentication needed for local models
async fn make_request(&self, texts: Vec<String>) -> Result<Response> {
    let url = format!("{}/embed", self.base_url);

    self.client
        .post(&url)
        .json(&json!({
            "texts": texts,
            "model": self.model_name
        }))
        .send()
        .await
}
```

---

## Troubleshooting

### Common Issues

#### 1. Plugin Not Found

**Error:**
```
Unknown embedding provider: voyage
```

**Solution:**
- Check `src/embeddings/plugins/mod.rs` exports your plugin
- Check `src/embeddings/manager.rs` handles your provider name
- Rebuild: `cargo clean && cargo build`

#### 2. API Key Not Recognized

**Error:**
```
API key not set for provider 'voyage'
```

**Solution:**
```bash
export VOYAGE_API_KEY="your-key"
# Verify it's set
echo $VOYAGE_API_KEY
```

#### 3. Dimension Mismatch

**Error:**
```
Embedding dimension mismatch: expected 384, got 1024
```

**Solution:**
Update `EMBEDDING_DIM` in config:
```bash
export EMBEDDING_DIM=1024
```

#### 4. Async/Await Errors

**Error:**
```
cannot use `.await` in sync context
```

**Solution:**
- All plugin methods must be `async`
- Add `#[async_trait]` to implementation
- Use `.await` on async calls

#### 5. Serialization Errors

**Error:**
```
Failed to parse response: missing field `data`
```

**Solution:**
- Verify API response format matches your structs
- Add `#[serde(rename = "...")]` for different field names
- Use `Option<T>` for optional fields

---

## Checklist

Before submitting your plugin:

### Code Quality
- [ ] Implements all `EmbeddingPlugin` methods
- [ ] Handles errors gracefully with descriptive messages
- [ ] Updates statistics in all code paths
- [ ] Uses `tracing` for logging
- [ ] Follows Rust naming conventions

### Testing
- [ ] Unit tests pass (`cargo test your_plugin`)
- [ ] Integration test with real API (manually tested)
- [ ] Health check works correctly
- [ ] Batch embedding maintains order
- [ ] Error cases tested

### Documentation
- [ ] Configuration file created (`config/embeddings/yourprovider.yaml`)
- [ ] README.md updated with provider details
- [ ] Code comments explain non-obvious parts
- [ ] Example usage provided

### Integration
- [ ] Added to `ProviderConfig` enum
- [ ] Exported in `plugins/mod.rs`
- [ ] Handled in `EmbeddingManager`
- [ ] Environment variable added to `expand_env_vars()`
- [ ] `.env.example` updated

### Performance
- [ ] Uses connection pooling
- [ ] Implements rate limiting if needed
- [ ] Batches requests efficiently
- [ ] No blocking I/O in async functions

---

## Submitting Your Plugin

### 1. Create Pull Request

```bash
git add .
git commit -m "Add Voyage AI embedding plugin"
git push origin feature/add-voyage-plugin
```

### 2. PR Description Template

```markdown
## Add [Provider Name] Embedding Plugin

### Summary
Adds support for [Provider Name] embeddings via their API.

### Features
- Single and batch embedding generation
- Health checks and statistics
- Configurable via YAML
- Full async/await support

### Testing
- [x] Unit tests pass
- [x] Manually tested with real API key
- [x] Health check works
- [x] Statistics tracking verified

### Configuration
Provider: `provider_name`
Dimensions: 1024
Max batch size: 128
API key: `PROVIDER_API_KEY`

### Documentation
- [x] Config file created
- [x] README updated
- [x] Code documented
```

### 3. Review Process

Your plugin will be reviewed for:
- Code quality and Rust best practices
- Error handling
- Documentation completeness
- Test coverage
- Performance considerations

---

## Additional Resources

### API Documentation
- OpenAI: https://platform.openai.com/docs/api-reference/embeddings
- Cohere: https://docs.cohere.com/reference/embed
- HuggingFace: https://huggingface.co/docs/api-inference
- Voyage: https://docs.voyageai.com/embeddings

### Rust Libraries
- `reqwest`: HTTP client - https://docs.rs/reqwest
- `async-trait`: Async traits - https://docs.rs/async-trait
- `serde`: Serialization - https://docs.rs/serde
- `tokio`: Async runtime - https://docs.rs/tokio

### VectaDB Resources
- Architecture: `EMBEDDING_PLUGINS.md`
- Existing plugins: `src/embeddings/plugins/`
- Integration guide: `PLUGIN_INTEGRATION_COMPLETE.md`

---

## Support

Need help creating your plugin?

1. **Check existing plugins** - Use OpenAI plugin as reference
2. **Read the docs** - See `EMBEDDING_PLUGINS.md`
3. **Ask questions** - Open a GitHub discussion
4. **Report issues** - Create a GitHub issue

---

## Conclusion

You've learned how to:
- ✅ Implement the `EmbeddingPlugin` trait
- ✅ Create configuration files
- ✅ Integrate with VectaDB's manager
- ✅ Test your implementation
- ✅ Follow best practices

Your plugin allows VectaDB users to leverage your embedding provider with zero code changes - just an environment variable!

**Happy coding!** 🚀

---

*Last updated: January 7, 2026*
*VectaDB Version: 0.1.0*
