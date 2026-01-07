# VectaDB Plugin Quick Start

**Create a new embedding plugin in 60 seconds** ⚡

---

## TL;DR

```bash
cd vectadb
./scripts/new-plugin.sh
```

Answer 7 questions → Get production-ready plugin code

---

## What You Get

```
✓ Plugin implementation    (~200 lines, fully functional)
✓ Configuration file       (YAML with env vars)
✓ Integration tests        (Unit + API tests)
✓ Setup instructions       (5 manual steps)
```

---

## Complete Workflow

### Step 1: Generate (60 seconds)

```bash
./scripts/new-plugin.sh
```

```
? Provider name: voyage
? API endpoint: https://api.voyageai.com/v1
? Default model: voyage-2
? Dimension: 1024
? Batch size: 128
? API key var: VOYAGE_API_KEY
? Cost per 1M: 0.10

✓ Generated 3 files
```

### Step 2: Integrate (5 minutes)

**a) Export in `plugins/mod.rs`:**
```rust
pub mod voyage;
pub use voyage::VoyagePlugin;
```

**b) Add to `plugin.rs` enum:**
```rust
Voyage {
    api_key: String,
    model: String,
    base_url: String,
    dimension: usize,
    batch_size: usize,
    timeout_secs: u64,
},
```

**c) Handle in `manager.rs`:**
```rust
"voyage" => {
    let mut plugin = VoyagePlugin::new();
    plugin.initialize(plugin_config).await?;
    registry.register(Box::new(plugin));
}
```

**d) Add env var in `manager.rs`:**
```rust
let env_vars = [
    // ...
    "VOYAGE_API_KEY",
];
```

**e) Re-export in `embeddings/mod.rs`:**
```rust
pub use plugins::{..., VoyagePlugin};
```

### Step 3: Test (2 minutes)

```bash
# Unit tests
cargo test voyage

# Integration test (needs API key)
export VOYAGE_API_KEY="your-key"
cargo test --test voyage_test -- --ignored
```

### Step 4: Use (instant)

```bash
export EMBEDDING_PROVIDER="voyage"
export VOYAGE_API_KEY="your-key"
cargo run --release
```

---

## Generated Files

### 1. Plugin (`src/embeddings/plugins/voyage.rs`)

```rust
pub struct VoyagePlugin {
    client: Client,
    config: Option<VoyageConfig>,
    stats: Arc<RwLock<PluginStats>>,
}

#[async_trait]
impl EmbeddingPlugin for VoyagePlugin {
    fn name(&self) -> &'static str { "voyage" }
    async fn embed(&self, text: &str) -> Result<Vec<f32>> { /* ... */ }
    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> { /* ... */ }
    // ... all methods implemented
}
```

**Features:**
- ✅ HTTP client with timeout
- ✅ Request/response types
- ✅ Statistics tracking
- ✅ Health checks
- ✅ Error handling
- ✅ Unit tests

### 2. Config (`config/embeddings/voyage.yaml`)

```yaml
name: "voyage"
provider: "voyage"
api_key: "${VOYAGE_API_KEY}"
model: "voyage-2"
base_url: "https://api.voyageai.com/v1"
dimension: 1024
batch_size: 128
timeout_secs: 30
```

### 3. Tests (`tests/voyage_test.rs`)

```rust
#[tokio::test]
#[ignore]
async fn test_voyage_real_api() {
    // Single embedding
    let embedding = plugin.embed("Hello!").await.unwrap();
    assert_eq!(embedding.len(), 1024);

    // Batch embedding
    let embeddings = plugin.embed_batch(&texts).await.unwrap();
    assert_eq!(embeddings.len(), 3);

    // Health check
    let health = plugin.health_check().await.unwrap();
    assert!(health.healthy);
}
```

---

## Command Reference

### Generate Plugin

```bash
./scripts/new-plugin.sh
```

### Test Plugin

```bash
# Unit tests only
cargo test your_provider

# With integration tests (needs API key)
export YOUR_PROVIDER_API_KEY="key"
cargo test --test your_provider_test -- --ignored
```

### Use Plugin

```bash
export EMBEDDING_PROVIDER="your_provider"
export YOUR_PROVIDER_API_KEY="key"
cargo run --release
```

### Verify Integration

```bash
# Check compilation
cargo check

# Check specific plugin
cargo check --tests your_provider_test

# Run VectaDB
cargo run --release
```

---

## Common Providers

### Voyage AI

```bash
Provider: voyage
Endpoint: https://api.voyageai.com/v1
Model: voyage-2
Dimension: 1024
API Key: VOYAGE_API_KEY
```

### Jina AI

```bash
Provider: jina
Endpoint: https://api.jina.ai/v1
Model: jina-embeddings-v2-base-en
Dimension: 768
API Key: JINA_API_KEY
```

### Mistral

```bash
Provider: mistral
Endpoint: https://api.mistral.ai/v1
Model: mistral-embed
Dimension: 1024
API Key: MISTRAL_API_KEY
```

### Azure OpenAI

```bash
Provider: azure-openai
Endpoint: https://your-resource.openai.azure.com
Model: your-deployment-name
Dimension: 1536
API Key: AZURE_OPENAI_API_KEY
```

### Custom Local

```bash
Provider: mylocal
Endpoint: http://localhost:8000
Model: custom-model
Dimension: 384
API Key: (leave empty for local)
```

---

## Troubleshooting

### Issue: Script not executable

```bash
chmod +x scripts/new-plugin.sh
```

### Issue: Compilation error after generation

Follow the 5 manual integration steps printed by the generator.

### Issue: API test fails

```bash
# Check API key is set
echo $YOUR_PROVIDER_API_KEY

# Check network connectivity
curl https://api.yourprovider.com/v1/health

# Check API key is valid
# (test with provider's official CLI or web interface)
```

### Issue: Wrong dimensions

Update the dimension in your config file:
```yaml
dimension: 768  # Match your model's actual dimension
```

And in environment:
```bash
export EMBEDDING_DIM=768
```

---

## Customization Points

After generation, you may want to customize:

### 1. Request Format

```rust
#[derive(Debug, Serialize)]
struct MyProviderRequest {
    texts: Vec<String>,           // Changed from 'input'
    model_name: String,            // Changed from 'model'
    encoding_format: String,       // Added custom field
}
```

### 2. Authentication

```rust
// Custom auth header
.header("X-API-Key", &config.api_key)

// Or query parameter
let url = format!("{}?api_key={}", url, config.api_key);
```

### 3. Error Handling

```rust
// Provider-specific errors
if error_text.contains("rate_limit") {
    return Err(VectaDBError::RateLimited("Try again later".into()));
}
```

### 4. Rate Limiting

```rust
use tokio::time::{sleep, Duration};

// Exponential backoff
for attempt in 0..3 {
    match self.make_request(texts.clone()).await {
        Ok(r) => return Ok(r),
        Err(e) if is_rate_limit_error(&e) => {
            sleep(Duration::from_secs(2_u64.pow(attempt))).await;
        }
        Err(e) => return Err(e),
    }
}
```

---

## Resources

### Documentation

- **Complete Guide**: `CREATING_PLUGINS.md` (800+ lines)
- **Script README**: `scripts/README.md`
- **Architecture**: `EMBEDDING_PLUGINS.md`
- **Integration**: `PLUGIN_INTEGRATION_COMPLETE.md`

### Examples

- **OpenAI**: `src/embeddings/plugins/openai.rs`
- **Cohere**: `src/embeddings/plugins/cohere.rs`
- **HuggingFace**: `src/embeddings/plugins/huggingface.rs`

### API Docs

- OpenAI: https://platform.openai.com/docs/api-reference
- Cohere: https://docs.cohere.com/reference/embed
- HuggingFace: https://huggingface.co/docs/api-inference
- Voyage: https://docs.voyageai.com/embeddings
- Jina: https://jina.ai/embeddings/

---

## Checklist

Before submitting your plugin:

- [ ] Generated with `./scripts/new-plugin.sh`
- [ ] Completed 5 integration steps
- [ ] Unit tests pass: `cargo test provider`
- [ ] Integration tests pass (with API key)
- [ ] Compilation succeeds: `cargo check`
- [ ] Config file has correct settings
- [ ] Added documentation to `config/embeddings/README.md`
- [ ] Tested with VectaDB: `cargo run`
- [ ] Verified embeddings have correct dimensions
- [ ] Checked error handling

---

## Performance Tips

### Batch Processing

```rust
// Good: Batch requests
let embeddings = plugin.embed_batch(&texts).await?;

// Avoid: Individual requests in loop
for text in texts {
    let emb = plugin.embed(text).await?;  // Slow!
}
```

### Connection Pooling

```rust
// Reuse client (done by default in generated code)
let client = Client::builder()
    .pool_max_idle_per_host(10)
    .build()?;
```

### Timeouts

```rust
// Set appropriate timeouts
.timeout(Duration::from_secs(30))
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────┐
│              VectaDB Plugin Generator                │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Generate:   ./scripts/new-plugin.sh                │
│  Test:       cargo test provider                    │
│  Run:        EMBEDDING_PROVIDER=provider cargo run  │
│                                                      │
│  Files Generated:                                   │
│    • src/embeddings/plugins/provider.rs             │
│    • config/embeddings/provider.yaml                │
│    • tests/provider_test.rs                         │
│                                                      │
│  Integration Steps: 5                               │
│  Time to Complete: ~10 minutes                      │
│                                                      │
│  Docs: CREATING_PLUGINS.md                          │
│  Help: scripts/README.md                            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

**Ready to create your plugin?** Run `./scripts/new-plugin.sh` now! 🚀

*Last updated: January 7, 2026*
