# VectaDB Plugin Generator

Quick-start tools for creating new embedding plugins.

## Quick Start

Generate a new plugin in under 60 seconds:

```bash
cd vectadb
./scripts/new-plugin.sh
```

## Usage

### Interactive Mode

Run the wizard and answer the prompts:

```bash
./scripts/new-plugin.sh
```

**Example session:**

```
╔════════════════════════════════════════╗
║  VectaDB Plugin Generator           ║
║  Create new embedding plugins       ║
╚════════════════════════════════════════╝

ℹ This wizard will help you create a new embedding plugin

? Provider name (e.g., voyage, jina, mistral): voyage
? API endpoint (https://api.voyage.com/v1):
? Default model name (voyage-v1): voyage-2
? Embedding dimension (1536): 1024
? Max batch size (100): 128
? API key environment variable (VOYAGE_API_KEY):
? Cost per 1M tokens (USD) (0.10):

ℹ Configuration Summary:
  Provider: Voyage
  Endpoint: https://api.voyage.com/v1
  Model: voyage-2
  Dimensions: 1024
  Batch size: 128
  API Key: $VOYAGE_API_KEY

? Generate plugin with these settings? (y/n): y

ℹ Generating plugin files...
✓ Created src/embeddings/plugins/voyage.rs
✓ Created config/embeddings/voyage.yaml
✓ Created tests/voyage_test.rs

✓ Plugin generated successfully!
```

## What Gets Generated

The generator creates three files:

### 1. Plugin Implementation (`src/embeddings/plugins/PROVIDER.rs`)

A complete Rust implementation including:
- Plugin struct with HTTP client
- Request/response types
- `EmbeddingPlugin` trait implementation
- Statistics tracking
- Health checks
- Unit tests

**~200 lines of production-ready code**

### 2. Configuration File (`config/embeddings/PROVIDER.yaml`)

YAML configuration with:
- Provider settings
- API endpoint
- Model name
- Dimensions and batch size
- Environment variable placeholders
- Usage instructions

### 3. Integration Tests (`tests/PROVIDER_test.rs`)

Comprehensive test suite with:
- Real API integration test
- Single embedding test
- Batch embedding test
- Health check test
- Statistics verification
- Unit tests

## After Generation

### Required Manual Steps

The generator provides instructions for 5 manual steps:

1. **Update `plugins/mod.rs`** - Export your plugin
2. **Update `embeddings/mod.rs`** - Re-export for convenience
3. **Update `plugin.rs`** - Add `ProviderConfig` variant
4. **Update `manager.rs`** - Handle provider initialization
5. **Update `manager.rs`** - Add API key to env var list

### Testing Your Plugin

```bash
# Set API key
export YOUR_PROVIDER_API_KEY="your-key"

# Run unit tests
cargo test your_provider

# Run integration tests
cargo test --test your_provider_test -- --ignored

# Test with VectaDB
export EMBEDDING_PROVIDER="your_provider"
cargo run --release
```

## Examples

### Example 1: Voyage AI

```bash
$ ./scripts/new-plugin.sh
? Provider name: voyage
? API endpoint: https://api.voyageai.com/v1
? Default model name: voyage-2
? Embedding dimension: 1024
? Max batch size: 128
? API key environment variable: VOYAGE_API_KEY
? Cost per 1M tokens: 0.10
```

**Generates:**
- `src/embeddings/plugins/voyage.rs`
- `config/embeddings/voyage.yaml`
- `tests/voyage_test.rs`

### Example 2: Jina AI

```bash
$ ./scripts/new-plugin.sh
? Provider name: jina
? API endpoint: https://api.jina.ai/v1
? Default model name: jina-embeddings-v2-base-en
? Embedding dimension: 768
? Max batch size: 64
? API key environment variable: JINA_API_KEY
? Cost per 1M tokens: 0.02
```

### Example 3: Custom Local Server

```bash
$ ./scripts/new-plugin.sh
? Provider name: mylocal
? API endpoint: http://localhost:8000
? Default model name: custom-bert
? Embedding dimension: 384
? Max batch size: 32
? API key environment variable: LOCAL_API_KEY
? Cost per 1M tokens: 0.00
```

## Generated Code Features

### Automatic Features

✅ **HTTP Client** - Pre-configured with timeouts and retries
✅ **Error Handling** - Comprehensive error messages
✅ **Statistics Tracking** - Requests, tokens, latency
✅ **Health Checks** - API connectivity verification
✅ **Batch Support** - Efficient multi-text embedding
✅ **Async/Await** - Non-blocking I/O
✅ **Type Safety** - Full Rust type checking
✅ **Tests** - Unit and integration tests included

### Customization Points

You may want to customize:

1. **Request Format** - Adjust for your API's structure
2. **Authentication** - Add custom auth headers
3. **Rate Limiting** - Add provider-specific limits
4. **Error Handling** - Handle provider-specific errors
5. **Response Parsing** - Handle different response formats

## Troubleshooting

### Script Won't Run

```bash
# Make executable
chmod +x scripts/new-plugin.sh

# Run from project root
cd vectadb
./scripts/new-plugin.sh
```

### Files Not Generated

Check that you have write permissions:

```bash
ls -la src/embeddings/plugins/
ls -la config/embeddings/
ls -la tests/
```

### Compilation Errors

The generated code requires manual integration steps. Follow the printed instructions after generation.

## Advanced Usage

### Non-Interactive Mode

For automation, you can pipe answers:

```bash
echo -e "myprovider\nhttps://api.example.com/v1\nmy-model\n768\n100\nMY_API_KEY\n0.05\ny" | ./scripts/new-plugin.sh
```

### Customize Templates

Edit `scripts/new-plugin.sh` to modify the generated code templates.

## File Structure

```
vectadb/
├── scripts/
│   ├── new-plugin.sh       # Plugin generator
│   └── README.md           # This file
│
├── src/embeddings/plugins/
│   └── [provider].rs       # Generated plugin
│
├── config/embeddings/
│   └── [provider].yaml     # Generated config
│
└── tests/
    └── [provider]_test.rs  # Generated tests
```

## Next Steps

After generating your plugin:

1. **Review generated code** - Make necessary customizations
2. **Complete integration** - Follow the 5 manual steps
3. **Test locally** - Verify with unit tests
4. **Test with API** - Run integration tests
5. **Document** - Add to `config/embeddings/README.md`
6. **Submit PR** - Share with the community!

## Tips

### Best Practices

- Use descriptive provider names (lowercase, hyphens ok)
- Follow the existing plugin patterns (see OpenAI plugin)
- Add comprehensive error messages
- Track statistics for monitoring
- Include health checks

### Common Patterns

**OpenAI-Compatible APIs:**
- Use similar request/response format
- Bearer token authentication
- Standard error codes

**Custom APIs:**
- Adjust request/response structs
- Add custom authentication
- Handle provider-specific errors

**Local Services:**
- No API key needed
- Use `http://localhost:port`
- Simplified error handling

## Support

Need help?

1. **Check examples** - See `src/embeddings/plugins/`
2. **Read the guide** - See `CREATING_PLUGINS.md`
3. **Ask questions** - Open a GitHub discussion
4. **Report bugs** - Create a GitHub issue

## Contributing

Improve the generator:

1. Fork the repository
2. Edit `scripts/new-plugin.sh`
3. Test with different providers
4. Submit a pull request

## License

Apache 2.0 - Same as VectaDB

---

**Happy plugin building!** 🚀

*Last updated: January 7, 2026*
