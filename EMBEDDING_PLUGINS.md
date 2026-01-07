# VectaDB Embedding Plugins Architecture

## Overview

VectaDB now features a **modular plugin system** for embedding generation, allowing seamless switching between different embedding providers without code changes. Each plugin is self-contained with its own configuration file.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     VectaDB Core                             │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │          Plugin Registry                           │     │
│  │  ┌───────────┬───────────┬───────────┬─────────┐  │     │
│  │  │  OpenAI   │  Cohere   │HuggingFace│  Local  │  │     │
│  │  │  Plugin   │  Plugin   │  Plugin   │ Plugin  │  │     │
│  │  └─────┬─────┴─────┬─────┴─────┬─────┴────┬────┘  │     │
│  │        │           │           │          │       │     │
│  │        └───────────┴───────────┴──────────┘       │     │
│  │                EmbeddingPlugin Trait              │     │
│  └────────────────────────────────────────────────────┘     │
│                                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │          Configuration Loader                      │     │
│  │   config/embeddings/                               │     │
│  │     ├── openai.yaml                                │     │
│  │     ├── cohere.yaml                                │     │
│  │     ├── huggingface.yaml                           │     │
│  │     └── local.yaml                                 │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. EmbeddingPlugin Trait

Defines the interface all plugins must implement:

```rust
#[async_trait]
pub trait EmbeddingPlugin: Send + Sync {
    fn name(&self) -> &'static str;
    fn version(&self) -> &'static str;
    fn dimension(&self) -> usize;
    fn max_batch_size(&self) -> usize;

    async fn initialize(&mut self, config: PluginConfig) -> Result<()>;
    async fn embed(&self, text: &str) -> Result<Vec<f32>>;
    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;
    async fn health_check(&self) -> Result<PluginHealth>;
    fn get_stats(&self) -> PluginStats;
}
```

### 2. Plugin Implementations

#### OpenAI Plugin (`plugins/openai.rs`)
- **API**: OpenAI Embeddings API v1
- **Models**: text-embedding-3-small, text-embedding-3-large, ada-002
- **Dimensions**: 1536 or 3072
- **Batch size**: Up to 2048
- **Pricing**: $0.02-0.13 per 1M tokens

#### Cohere Plugin (`plugins/cohere.rs`)
- **API**: Cohere Embed API v1
- **Models**: embed-english-v3.0, embed-multilingual-v3.0
- **Dimensions**: 384-1024
- **Batch size**: Up to 96
- **Special**: Input type selection (document, query, classification, clustering)

#### HuggingFace Plugin (`plugins/huggingface.rs`)
- **API**: HuggingFace Inference API
- **Models**: Any sentence-transformers model
- **Dimensions**: Model-dependent (384-768 typical)
- **Batch size**: Up to 32
- **Pricing**: Free tier + Pro plans

#### Local Plugin (Future)
- **Runtime**: sentence-transformers-rs (Candle)
- **Models**: all-MiniLM-L6-v2, all-mpnet-base-v2, BGE
- **Dimensions**: 384-768
- **Batch size**: Configurable
- **Cost**: Free (CPU/GPU)

### 3. Configuration System

Each plugin has its own YAML configuration file:

```yaml
# config/embeddings/openai.yaml
name: "openai"
provider: "openai"
api_key: "${OPENAI_API_KEY}"
model: "text-embedding-3-small"
base_url: "https://api.openai.com/v1"
dimension: 1536
batch_size: 2048
timeout_secs: 30
```

**Features:**
- Environment variable substitution (`${VAR_NAME}`)
- Provider-specific settings
- Isolated from main config
- Easy to version control (without secrets)

### 4. Plugin Registry

Manages multiple plugins and provides unified access:

```rust
let mut registry = PluginRegistry::new();

// Register plugins
registry.register(Box::new(OpenAIPlugin::new()));
registry.register(Box::new(CoherePlugin::new()));

// Set active plugin
registry.set_active("openai")?;

// Use active plugin
let plugin = registry.get_active()?;
let embedding = plugin.embed("Hello, world!").await?;
```

## File Structure

```
vectadb/
├── src/
│   └── embeddings/
│       ├── mod.rs                    # Module exports
│       ├── plugin.rs                 # Trait definition & registry
│       ├── service.rs                # Legacy local service
│       └── plugins/
│           ├── mod.rs                # Plugin exports
│           ├── openai.rs             # OpenAI plugin
│           ├── cohere.rs             # Cohere plugin
│           └── huggingface.rs        # HuggingFace plugin
│
├── config/
│   └── embeddings/
│       ├── README.md                 # Documentation
│       ├── openai.yaml               # OpenAI config
│       ├── cohere.yaml               # Cohere config
│       ├── huggingface.yaml          # HuggingFace config
│       └── local.yaml                # Local config
│
└── examples/
    └── embedding_plugins.rs          # Usage example
```

## Usage

### Basic Usage

```rust
use vectadb::embeddings::{OpenAIPlugin, PluginConfig};

// Load configuration
let config: PluginConfig = serde_yaml::from_str(&config_yaml)?;

// Initialize plugin
let mut plugin = OpenAIPlugin::new();
plugin.initialize(config).await?;

// Generate embeddings
let embedding = plugin.embed("Hello, world!").await?;
let batch = plugin.embed_batch(&texts).await?;

// Health check
let health = plugin.health_check().await?;
println!("Healthy: {}", health.healthy);

// Get statistics
let stats = plugin.get_stats();
println!("Total requests: {}", stats.total_requests);
println!("Avg latency: {}ms", stats.avg_latency_ms);
```

### Switching Providers

```rust
// Start with OpenAI
let mut registry = PluginRegistry::new();
registry.register(Box::new(OpenAIPlugin::new()));
registry.set_active("openai")?;

// Generate embeddings
let embedding1 = registry.get_active()?.embed("test").await?;

// Switch to Cohere
registry.register(Box::new(CoherePlugin::new()));
registry.set_active("cohere")?;

// Generate embeddings with different provider
let embedding2 = registry.get_active()?.embed("test").await?;
```

### Configuration in VectaDB Main Config

```yaml
# config.yaml
embeddings:
  # Active plugin name
  active_plugin: "openai"

  # Directory containing plugin configs
  plugin_config_dir: "./config/embeddings"

  # Fallback behavior if plugin fails
  fallback_to_local: true
```

## Monitoring & Statistics

Each plugin tracks:
- **Total requests**: Number of API calls made
- **Total embeddings**: Number of embeddings generated
- **Total tokens**: Token usage (for billing)
- **Failed requests**: Error count
- **Average latency**: Response time in milliseconds

Access via:
```rust
let stats = plugin.get_stats();
```

Or via API endpoint:
```bash
GET /api/v1/embeddings/stats
```

## Error Handling

Plugins handle errors gracefully:

1. **Network errors**: Retry with exponential backoff
2. **Rate limits**: Return proper error, allow retry
3. **Invalid input**: Validate before sending to API
4. **Parse errors**: Log and return error with context

Example:
```rust
match plugin.embed("text").await {
    Ok(embedding) => { /* use embedding */ }
    Err(VectaDBError::Embedding(msg)) => {
        // Log error, increment failed_requests
        // Fall back to local plugin if configured
    }
    Err(e) => { /* handle other errors */ }
}
```

## Testing

### Unit Tests

Each plugin has unit tests:

```bash
cargo test -p vectadb embeddings::plugins
```

### Integration Tests

Test with real APIs (requires API keys):

```bash
export OPENAI_API_KEY="sk-..."
export COHERE_API_KEY="..."
export HF_API_KEY="hf_..."

cargo test --features integration-tests embeddings::plugins
```

### Example

Run the example to test all plugins:

```bash
cargo run --example embedding_plugins
```

## Creating Custom Plugins

### Step 1: Implement the Trait

```rust
// src/embeddings/plugins/myprovider.rs
use async_trait::async_trait;
use crate::embeddings::plugin::*;

pub struct MyProviderPlugin {
    config: Option<MyConfig>,
    stats: Arc<RwLock<PluginStats>>,
}

#[async_trait]
impl EmbeddingPlugin for MyProviderPlugin {
    fn name(&self) -> &'static str { "myprovider" }
    fn version(&self) -> &'static str { "1.0.0" }
    fn dimension(&self) -> usize { 1536 }
    fn max_batch_size(&self) -> usize { 100 }

    async fn initialize(&mut self, config: PluginConfig) -> Result<()> {
        // Load config, create HTTP client, etc.
        Ok(())
    }

    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        // Make API call
        // Update stats
        // Return embedding
        Ok(vec![])
    }

    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        // Batch API call
        Ok(vec![])
    }

    async fn health_check(&self) -> Result<PluginHealth> {
        // Test API connectivity
        Ok(PluginHealth {
            healthy: true,
            message: None,
            latency_ms: None,
        })
    }

    fn get_stats(&self) -> PluginStats {
        self.stats.read().unwrap().clone()
    }
}
```

### Step 2: Add Configuration

```yaml
# config/embeddings/myprovider.yaml
name: "myprovider"
provider: "myprovider"
api_key: "${MYPROVIDER_API_KEY}"
model: "my-embedding-model"
dimension: 1536
batch_size: 100
```

### Step 3: Register Plugin

```rust
// src/embeddings/plugins/mod.rs
pub mod myprovider;
pub use myprovider::MyProviderPlugin;

// In your main.rs or initialization code:
registry.register(Box::new(MyProviderPlugin::new()));
```

## Benefits

1. **Flexibility**: Switch providers without code changes
2. **Isolation**: Each plugin is self-contained
3. **Testability**: Easy to mock and test
4. **Extensibility**: Add new providers easily
5. **Configuration**: Provider-specific settings in separate files
6. **Monitoring**: Built-in statistics tracking
7. **Type Safety**: Rust traits ensure correctness

## Migration Path

### From Local Service

Old code:
```rust
let service = EmbeddingService::new(model, batch_size)?;
let embedding = service.encode("text")?;
```

New code:
```rust
let mut plugin = OpenAIPlugin::new();
plugin.initialize(config).await?;
let embedding = plugin.embed("text").await?;
```

### Gradual Migration

1. Keep existing `EmbeddingService` for backward compatibility
2. Add plugin system alongside
3. Migrate API endpoints to use plugins
4. Deprecate old service
5. Remove old service in next major version

## Performance Considerations

- **Batching**: Always use `embed_batch()` for multiple texts
- **Connection pooling**: Plugins reuse HTTP connections
- **Async/await**: Non-blocking I/O for better throughput
- **Statistics overhead**: Minimal (RwLock + atomic updates)

## Security

- **API keys**: Never commit to version control
- **Environment variables**: Use for sensitive data
- **HTTPS**: All plugins use encrypted connections
- **Rate limiting**: Respect provider limits
- **Error messages**: Don't leak sensitive info

## Future Enhancements

1. **Caching**: Cache embeddings to reduce API calls
2. **Retry logic**: Exponential backoff for transient errors
3. **Circuit breaker**: Fail fast when provider is down
4. **Fallback chain**: Try multiple providers in order
5. **Cost tracking**: Track spending per provider
6. **Metrics export**: Prometheus metrics
7. **Admin UI**: Web interface for managing plugins

## Conclusion

The plugin system provides a clean, extensible architecture for embedding generation in VectaDB. It allows users to:

- Choose the best provider for their use case
- Switch providers without downtime
- Add custom providers easily
- Monitor usage and costs
- Maintain clean separation of concerns

All while maintaining type safety and excellent performance.
