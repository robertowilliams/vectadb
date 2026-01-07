# VectaDB Embedding Plugins

VectaDB uses a modular plugin system for embedding generation, allowing you to easily switch between different providers without changing code.

## Quick Start

### 1. Choose Your Provider

VectaDB supports multiple embedding providers:

| Provider | Dimensions | Cost | Best For |
|----------|-----------|------|----------|
| **OpenAI** | 1536/3072 | $0.02-0.13/1M tokens | Production, best quality |
| **Cohere** | 384-1024 | $0.10/1M tokens | Multilingual, specialized tasks |
| **HuggingFace** | 384-768 | Free/Pro | Open source models |
| **Local** | 384-768 | Free (CPU/GPU) | Privacy, offline use |

### 2. Configure Your Plugin

Each provider has its own configuration file in this directory:

- `openai.yaml` - OpenAI embeddings
- `cohere.yaml` - Cohere embeddings
- `huggingface.yaml` - HuggingFace Inference API
- `local.yaml` - Local sentence-transformers

### 3. Set Environment Variables

```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."

# For Cohere
export COHERE_API_KEY="..."

# For HuggingFace
export HF_API_KEY="hf_..."

# For Local (no key needed)
# Models auto-download to ~/.cache/huggingface/
```

### 4. Select Active Plugin

In your main `config.yaml`:

```yaml
embeddings:
  # Choose: "openai", "cohere", "huggingface", or "local"
  active_plugin: "openai"

  # Path to plugin configs
  plugin_config_dir: "./config/embeddings"
```

## Provider Details

### OpenAI

**Best for:** Production deployments requiring high-quality embeddings

**Models:**
- `text-embedding-3-small` (1536d) - Fast, $0.02/1M tokens
- `text-embedding-3-large` (3072d) - Best quality, $0.13/1M tokens
- `text-embedding-ada-002` (1536d) - Legacy

**Configuration:**
```yaml
name: "openai"
provider: "openai"
api_key: "${OPENAI_API_KEY}"
model: "text-embedding-3-small"
dimension: 1536
batch_size: 2048
```

### Cohere

**Best for:** Multilingual support, specialized use cases

**Models:**
- `embed-english-v3.0` (1024d) - English
- `embed-multilingual-v3.0` (1024d) - 100+ languages
- `embed-english-light-v3.0` (384d) - Faster

**Configuration:**
```yaml
name: "cohere"
provider: "cohere"
api_key: "${COHERE_API_KEY}"
model: "embed-english-v3.0"
dimension: 1024
input_type: "search_document"  # or "search_query", "classification", "clustering"
```

### HuggingFace

**Best for:** Open source models, free tier available

**Popular Models:**
- `sentence-transformers/all-MiniLM-L6-v2` (384d) - Fast
- `sentence-transformers/all-mpnet-base-v2` (768d) - Quality
- `BAAI/bge-small-en-v1.5` (384d) - Retrieval

**Configuration:**
```yaml
name: "huggingface"
provider: "huggingface"
api_key: "${HF_API_KEY}"
model: "sentence-transformers/all-MiniLM-L6-v2"
dimension: 384
```

### Local

**Best for:** Privacy, offline use, no API costs

**Models:**
- `all-MiniLM-L6-v2` (384d) - Fast, ~80MB
- `all-mpnet-base-v2` (768d) - Quality, ~400MB
- `BAAI/bge-small-en-v1.5` (384d) - Retrieval

**Configuration:**
```yaml
name: "local"
provider: "local"
model: "all-MiniLM-L6-v2"
dimension: 384
```

## Switching Providers

You can switch providers at any time:

1. Stop VectaDB
2. Update `active_plugin` in `config.yaml`
3. Set required API keys
4. Restart VectaDB

**Note:** Existing embeddings won't change. Re-index data if you need consistent embeddings.

## Creating Custom Plugins

To add a new provider:

1. Create `vectadb/src/embeddings/plugins/myprovider.rs`
2. Implement the `EmbeddingPlugin` trait
3. Add config file: `config/embeddings/myprovider.yaml`
4. Register in `plugins/mod.rs`

Example trait implementation:

```rust
use async_trait::async_trait;
use crate::embeddings::plugin::EmbeddingPlugin;

pub struct MyProvider { /* ... */ }

#[async_trait]
impl EmbeddingPlugin for MyProvider {
    fn name(&self) -> &'static str { "myprovider" }
    fn version(&self) -> &'static str { "1.0.0" }
    fn dimension(&self) -> usize { 1536 }
    fn max_batch_size(&self) -> usize { 100 }

    async fn initialize(&mut self, config: PluginConfig) -> Result<()> { /* ... */ }
    async fn embed(&self, text: &str) -> Result<Vec<f32>> { /* ... */ }
    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> { /* ... */ }
    async fn health_check(&self) -> Result<PluginHealth> { /* ... */ }
    fn get_stats(&self) -> PluginStats { /* ... */ }
}
```

## Monitoring & Stats

Each plugin tracks usage statistics:

```rust
pub struct PluginStats {
    pub total_requests: u64,
    pub total_tokens: u64,
    pub total_embeddings: u64,
    pub failed_requests: u64,
    pub avg_latency_ms: f64,
}
```

Access via API: `GET /api/v1/embeddings/stats`

## Troubleshooting

### Plugin fails to initialize

- Check API key is set correctly
- Verify network connectivity
- Check provider status page

### Embeddings are slow

- Increase `batch_size` in config
- Use a faster model
- Consider local provider for high throughput

### Different providers give different results

- Each model has different dimensions and training
- Re-index your data when switching providers
- Dimension must match Qdrant collection config

## Support

- Documentation: https://github.com/your-org/vectadb
- Issues: https://github.com/your-org/vectadb/issues
- Discord: https://discord.gg/vectadb
