#!/bin/bash
# VectaDB Plugin Generator
# Generates a complete embedding plugin scaffold from templates

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

# Print banner
print_banner() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  VectaDB Plugin Generator           ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  Create new embedding plugins       ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
}

# Convert provider name to different cases
to_pascal_case() {
    # Convert first character to uppercase, then handle underscores
    local input="$1"
    local first_char=$(echo "${input:0:1}" | tr '[:lower:]' '[:upper:]')
    local rest="${input:1}"
    # Replace _x with X
    rest=$(echo "$rest" | sed 's/_\(.\)/\U\1/g')
    echo "${first_char}${rest}"
}

to_snake_case() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | sed 's/-/_/g'
}

to_upper_case() {
    echo "$1" | tr '[:lower:]' '[:upper:]' | sed 's/-/_/g'
}

# Prompt for user input
prompt_input() {
    local prompt="$1"
    local default="$2"
    local varname="$3"

    if [ -n "$default" ]; then
        echo -ne "${YELLOW}?${NC} $prompt ${BLUE}($default)${NC}: "
    else
        echo -ne "${YELLOW}?${NC} $prompt: "
    fi

    read -r value
    if [ -z "$value" ] && [ -n "$default" ]; then
        value="$default"
    fi

    eval "$varname='$value'"
}

# Prompt for confirmation
confirm() {
    local prompt="$1"
    echo -ne "${YELLOW}?${NC} $prompt ${BLUE}(y/n)${NC}: "
    read -r response
    case "$response" in
        [yY][eE][sS]|[yY]) return 0 ;;
        *) return 1 ;;
    esac
}

# Main function
main() {
    print_banner

    print_info "This wizard will help you create a new embedding plugin"
    echo ""

    # Gather information
    prompt_input "Provider name (e.g., voyage, jina, mistral)" "" PROVIDER_NAME

    if [ -z "$PROVIDER_NAME" ]; then
        print_error "Provider name is required"
        exit 1
    fi

    # Convert to different cases
    PROVIDER_SNAKE=$(to_snake_case "$PROVIDER_NAME")
    PROVIDER_PASCAL=$(to_pascal_case "$PROVIDER_NAME")
    PROVIDER_UPPER=$(to_upper_case "$PROVIDER_NAME")

    prompt_input "API endpoint" "https://api.$PROVIDER_SNAKE.com/v1" API_ENDPOINT
    prompt_input "Default model name" "${PROVIDER_SNAKE}-v1" MODEL_NAME
    prompt_input "Embedding dimension" "1536" DIMENSION
    prompt_input "Max batch size" "100" BATCH_SIZE
    prompt_input "API key environment variable" "${PROVIDER_UPPER}_API_KEY" API_KEY_VAR
    prompt_input "Cost per 1M tokens (USD)" "0.10" COST

    echo ""
    print_info "Configuration Summary:"
    echo "  Provider: $PROVIDER_PASCAL"
    echo "  Endpoint: $API_ENDPOINT"
    echo "  Model: $MODEL_NAME"
    echo "  Dimensions: $DIMENSION"
    echo "  Batch size: $BATCH_SIZE"
    echo "  API Key: \$$API_KEY_VAR"
    echo ""

    if ! confirm "Generate plugin with these settings?"; then
        print_warning "Cancelled"
        exit 0
    fi

    echo ""
    print_info "Generating plugin files..."

    # Create plugin Rust file
    generate_rust_plugin

    # Create configuration file
    generate_config_file

    # Create test file
    generate_test_file

    # Update integration files
    update_integration_files

    echo ""
    print_success "Plugin generated successfully!"
    echo ""
    print_info "Next steps:"
    echo "  1. Review generated files:"
    echo "     - src/embeddings/plugins/${PROVIDER_SNAKE}.rs"
    echo "     - config/embeddings/${PROVIDER_SNAKE}.yaml"
    echo "     - tests/${PROVIDER_SNAKE}_test.rs"
    echo ""
    echo "  2. Update ProviderConfig enum in src/embeddings/plugin.rs"
    echo ""
    echo "  3. Add your provider to EmbeddingManager in src/embeddings/manager.rs"
    echo ""
    echo "  4. Test your plugin:"
    echo "     export ${API_KEY_VAR}=\"your-key\""
    echo "     cargo test ${PROVIDER_SNAKE}"
    echo ""
    echo "  5. Run VectaDB with your plugin:"
    echo "     export EMBEDDING_PROVIDER=\"${PROVIDER_SNAKE}\""
    echo "     cargo run --release"
    echo ""

    print_info "See CREATING_PLUGINS.md for detailed instructions"
}

# Generate Rust plugin file
generate_rust_plugin() {
    local output_file="$PROJECT_ROOT/src/embeddings/plugins/${PROVIDER_SNAKE}.rs"

    cat > "$output_file" << EOF
// ${PROVIDER_PASCAL} embedding plugin
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

/// ${PROVIDER_PASCAL} embedding plugin
pub struct ${PROVIDER_PASCAL}Plugin {
    client: Client,
    config: Option<${PROVIDER_PASCAL}Config>,
    stats: Arc<RwLock<PluginStats>>,
}

#[derive(Debug, Clone)]
struct ${PROVIDER_PASCAL}Config {
    api_key: String,
    model: String,
    base_url: String,
    dimension: usize,
    batch_size: usize,
    timeout_secs: u64,
}

// ${PROVIDER_PASCAL} API request/response types
#[derive(Debug, Serialize)]
struct ${PROVIDER_PASCAL}Request {
    input: Vec<String>,
    model: String,
}

#[derive(Debug, Deserialize)]
struct ${PROVIDER_PASCAL}Response {
    data: Vec<EmbeddingData>,
    #[serde(default)]
    usage: Option<Usage>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
    index: usize,
}

#[derive(Debug, Deserialize)]
struct Usage {
    #[serde(alias = "prompt_tokens")]
    total_tokens: u64,
}

impl ${PROVIDER_PASCAL}Plugin {
    pub fn new() -> Self {
        Self {
            client: Client::new(),
            config: None,
            stats: Arc::new(RwLock::new(PluginStats::default())),
        }
    }

    async fn make_request(&self, texts: Vec<String>) -> Result<${PROVIDER_PASCAL}Response> {
        let config = self
            .config
            .as_ref()
            .ok_or_else(|| VectaDBError::InvalidInput("Plugin not initialized".to_string()))?;

        let url = format!("{}/embeddings", config.base_url);

        let request = ${PROVIDER_PASCAL}Request {
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
            .map_err(|e| VectaDBError::Embedding(format!("${PROVIDER_PASCAL} API request failed: {}", e)))?;

        let elapsed = start.elapsed();

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            return Err(VectaDBError::Embedding(format!(
                "${PROVIDER_PASCAL} API error {}: {}",
                status, error_text
            )));
        }

        let result: ${PROVIDER_PASCAL}Response = response
            .json()
            .await
            .map_err(|e| VectaDBError::Embedding(format!("Failed to parse ${PROVIDER_PASCAL} response: {}", e)))?;

        // Update statistics
        if let Ok(mut stats) = self.stats.write() {
            stats.total_requests += 1;
            if let Some(ref usage) = result.usage {
                stats.total_tokens += usage.total_tokens;
            }
            stats.total_embeddings += texts.len() as u64;
            let total_latency = stats.avg_latency_ms * (stats.total_requests - 1) as f64;
            stats.avg_latency_ms = (total_latency + elapsed.as_millis() as f64) / stats.total_requests as f64;
        }

        Ok(result)
    }
}

impl Default for ${PROVIDER_PASCAL}Plugin {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl EmbeddingPlugin for ${PROVIDER_PASCAL}Plugin {
    fn name(&self) -> &'static str {
        "${PROVIDER_SNAKE}"
    }

    fn version(&self) -> &'static str {
        "1.0.0"
    }

    fn dimension(&self) -> usize {
        self.config
            .as_ref()
            .map(|c| c.dimension)
            .unwrap_or(${DIMENSION})
    }

    fn max_batch_size(&self) -> usize {
        self.config
            .as_ref()
            .map(|c| c.batch_size)
            .unwrap_or(${BATCH_SIZE})
    }

    async fn initialize(&mut self, config: PluginConfig) -> Result<()> {
        // TODO: Update this to match your ProviderConfig variant
        match config.provider {
            ProviderConfig::${PROVIDER_PASCAL} {
                api_key,
                model,
                base_url,
                dimension,
                batch_size,
                timeout_secs,
            } => {
                self.config = Some(${PROVIDER_PASCAL}Config {
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
                "Invalid provider config for ${PROVIDER_PASCAL} plugin".to_string(),
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
        let plugin = ${PROVIDER_PASCAL}Plugin::new();
        assert_eq!(plugin.name(), "${PROVIDER_SNAKE}");
        assert_eq!(plugin.version(), "1.0.0");
    }

    #[test]
    fn test_default_dimensions() {
        let plugin = ${PROVIDER_PASCAL}Plugin::new();
        assert_eq!(plugin.dimension(), ${DIMENSION});
        assert_eq!(plugin.max_batch_size(), ${BATCH_SIZE});
    }

    // Add more tests as needed
}
EOF

    print_success "Created src/embeddings/plugins/${PROVIDER_SNAKE}.rs"
}

# Generate configuration file
generate_config_file() {
    local output_file="$PROJECT_ROOT/config/embeddings/${PROVIDER_SNAKE}.yaml"

    cat > "$output_file" << EOF
# ${PROVIDER_PASCAL} Embedding Plugin Configuration
#
# Usage:
#   1. Get API key from your ${PROVIDER_PASCAL} account
#   2. Set environment variable: export ${API_KEY_VAR}="your-key"
#   3. Or replace \${${API_KEY_VAR}} below with your key (not recommended for production)
#
# Models available:
#   - ${MODEL_NAME} (${DIMENSION} dimensions) - Default model
#
# Pricing: \$${COST}/1M tokens

name: "${PROVIDER_SNAKE}"
provider: "${PROVIDER_SNAKE}"
api_key: "\${${API_KEY_VAR}}"
model: "${MODEL_NAME}"
base_url: "${API_ENDPOINT}"
dimension: ${DIMENSION}
batch_size: ${BATCH_SIZE}
timeout_secs: 30
EOF

    print_success "Created config/embeddings/${PROVIDER_SNAKE}.yaml"
}

# Generate test file
generate_test_file() {
    local output_file="$PROJECT_ROOT/tests/${PROVIDER_SNAKE}_test.rs"

    cat > "$output_file" << EOF
// Integration tests for ${PROVIDER_PASCAL} plugin
#[cfg(test)]
mod ${PROVIDER_SNAKE}_tests {
    use vectadb::embeddings::{${PROVIDER_PASCAL}Plugin, EmbeddingPlugin, PluginConfig, ProviderConfig};

    #[tokio::test]
    #[ignore] // Only run with real API key: cargo test -- --ignored
    async fn test_${PROVIDER_SNAKE}_real_api() {
        let api_key = std::env::var("${API_KEY_VAR}")
            .expect("${API_KEY_VAR} not set. Run: export ${API_KEY_VAR}=your-key");

        let config = PluginConfig {
            name: "${PROVIDER_SNAKE}".to_string(),
            provider: ProviderConfig::${PROVIDER_PASCAL} {
                api_key,
                model: "${MODEL_NAME}".to_string(),
                base_url: "${API_ENDPOINT}".to_string(),
                dimension: ${DIMENSION},
                batch_size: ${BATCH_SIZE},
                timeout_secs: 30,
            },
        };

        let mut plugin = ${PROVIDER_PASCAL}Plugin::new();
        plugin.initialize(config).await.expect("Failed to initialize plugin");

        // Test single embedding
        let embedding = plugin.embed("Hello, world!").await.expect("Failed to generate embedding");
        assert_eq!(embedding.len(), ${DIMENSION}, "Embedding dimension mismatch");

        // Test batch embedding
        let texts = vec!["Text 1".to_string(), "Text 2".to_string(), "Text 3".to_string()];
        let embeddings = plugin.embed_batch(&texts).await.expect("Failed to generate batch embeddings");
        assert_eq!(embeddings.len(), 3, "Should generate 3 embeddings");
        assert_eq!(embeddings[0].len(), ${DIMENSION}, "Embedding dimension mismatch");

        // Test health check
        let health = plugin.health_check().await.expect("Health check failed");
        assert!(health.healthy, "Plugin should be healthy");
        assert!(health.latency_ms.is_some(), "Should report latency");

        // Check statistics
        let stats = plugin.get_stats();
        assert!(stats.total_requests > 0, "Should have made requests");
        assert!(stats.total_embeddings >= 4, "Should have generated at least 4 embeddings");
        assert!(stats.avg_latency_ms > 0.0, "Should have non-zero latency");

        println!("✓ All tests passed!");
        println!("  Total requests: {}", stats.total_requests);
        println!("  Total embeddings: {}", stats.total_embeddings);
        println!("  Avg latency: {:.2}ms", stats.avg_latency_ms);
    }

    #[test]
    fn test_${PROVIDER_SNAKE}_plugin_creation() {
        let plugin = ${PROVIDER_PASCAL}Plugin::new();
        assert_eq!(plugin.name(), "${PROVIDER_SNAKE}");
        assert_eq!(plugin.version(), "1.0.0");
        assert_eq!(plugin.dimension(), ${DIMENSION});
        assert_eq!(plugin.max_batch_size(), ${BATCH_SIZE});
    }
}
EOF

    print_success "Created tests/${PROVIDER_SNAKE}_test.rs"
}

# Update integration files
update_integration_files() {
    print_info "Manual steps required:"
    echo ""
    echo "  1. Add to src/embeddings/plugins/mod.rs:"
    echo "     pub mod ${PROVIDER_SNAKE};"
    echo "     pub use ${PROVIDER_SNAKE}::${PROVIDER_PASCAL}Plugin;"
    echo ""
    echo "  2. Add to src/embeddings/mod.rs:"
    echo "     pub use plugins::{..., ${PROVIDER_PASCAL}Plugin};"
    echo ""
    echo "  3. Add to src/embeddings/plugin.rs (ProviderConfig enum):"
    echo "     ${PROVIDER_PASCAL} {"
    echo "         api_key: String,"
    echo "         model: String,"
    echo "         base_url: String,"
    echo "         dimension: usize,"
    echo "         batch_size: usize,"
    echo "         timeout_secs: u64,"
    echo "     },"
    echo ""
    echo "  4. Add to src/embeddings/manager.rs (init_plugin_system):"
    echo "     \"${PROVIDER_SNAKE}\" => {"
    echo "         let mut plugin = ${PROVIDER_PASCAL}Plugin::new();"
    echo "         plugin.initialize(plugin_config).await?;"
    echo "         registry.register(Box::new(plugin));"
    echo "     }"
    echo ""
    echo "  5. Add to src/embeddings/manager.rs (expand_env_vars):"
    echo "     \"${API_KEY_VAR}\","
    echo ""
}

# Run main
main
EOF

chmod +x "$output_file"
print_success "Created executable script"
}

# Execute
main "$@"
