// Example: Using VectaDB Embedding Plugins
//
// This example demonstrates:
// 1. Loading plugin configurations from YAML files
// 2. Initializing different embedding providers
// 3. Switching between providers
// 4. Generating embeddings with each provider
// 5. Monitoring usage statistics
//
// Run with: cargo run --example embedding_plugins

use std::fs;
use vectadb::embeddings::{
    CoherePlugin, EmbeddingPlugin, HuggingFacePlugin, OpenAIPlugin, PluginConfig, PluginRegistry,
};

#[tokio::main]
async fn main() {
    println!("{}", "=".repeat(80));
    println!("VectaDB Embedding Plugins Example");
    println!("{}", "=".repeat(80));
    println!();

    // Create plugin registry
    let mut registry = PluginRegistry::new();

    // Example 1: OpenAI Plugin
    println!("📦 Example 1: OpenAI Plugin");
    println!("{}", "-".repeat(80));

    match load_and_test_plugin::<OpenAIPlugin>("config/embeddings/openai.yaml").await {
        Ok(plugin) => {
            registry.register(Box::new(plugin));
            println!("✅ OpenAI plugin registered successfully");
        }
        Err(e) => {
            println!("⚠️  OpenAI plugin failed: {}", e);
            println!("   (This is expected if OPENAI_API_KEY is not set)");
        }
    }
    println!();

    // Example 2: Cohere Plugin
    println!("📦 Example 2: Cohere Plugin");
    println!("{}", "-".repeat(80));

    match load_and_test_plugin::<CoherePlugin>("config/embeddings/cohere.yaml").await {
        Ok(plugin) => {
            registry.register(Box::new(plugin));
            println!("✅ Cohere plugin registered successfully");
        }
        Err(e) => {
            println!("⚠️  Cohere plugin failed: {}", e);
            println!("   (This is expected if COHERE_API_KEY is not set)");
        }
    }
    println!();

    // Example 3: HuggingFace Plugin
    println!("📦 Example 3: HuggingFace Plugin");
    println!("{}", "-".repeat(80));

    match load_and_test_plugin::<HuggingFacePlugin>("config/embeddings/huggingface.yaml").await {
        Ok(plugin) => {
            registry.register(Box::new(plugin));
            println!("✅ HuggingFace plugin registered successfully");
        }
        Err(e) => {
            println!("⚠️  HuggingFace plugin failed: {}", e);
            println!("   (This is expected if HF_API_KEY is not set)");
        }
    }
    println!();

    // Example 4: List all registered plugins
    println!("📋 Registered Plugins");
    println!("{}", "-".repeat(80));
    let plugins = registry.list_plugins();
    if plugins.is_empty() {
        println!("No plugins registered. Set API keys to test plugins:");
        println!("  export OPENAI_API_KEY=\"sk-...\"");
        println!("  export COHERE_API_KEY=\"...\"");
        println!("  export HF_API_KEY=\"hf_...\"");
    } else {
        for plugin_name in plugins {
            println!("  - {}", plugin_name);
        }
    }
    println!();

    // Example 5: Use active plugin
    if let Ok(active_plugin) = registry.get_active() {
        println!("🚀 Using Active Plugin: {}", active_plugin.name());
        println!("{}", "-".repeat(80));

        let test_texts = vec![
            "VectaDB is an observability database for LLM agents",
            "It stores traces, events, and embeddings",
            "The plugin system allows switching between providers",
        ];

        println!("Generating embeddings for {} texts...", test_texts.len());

        match active_plugin
            .embed_batch(&test_texts.iter().map(|s| s.to_string()).collect::<Vec<_>>())
            .await
        {
            Ok(embeddings) => {
                println!("✅ Generated {} embeddings", embeddings.len());
                println!("   Dimensions: {}", embeddings[0].len());

                // Show stats
                let stats = active_plugin.get_stats();
                println!();
                println!("📊 Plugin Statistics");
                println!("   Total requests: {}", stats.total_requests);
                println!("   Total embeddings: {}", stats.total_embeddings);
                println!("   Total tokens: {}", stats.total_tokens);
                println!("   Avg latency: {:.2}ms", stats.avg_latency_ms);
                println!("   Failed requests: {}", stats.failed_requests);
            }
            Err(e) => {
                println!("❌ Failed to generate embeddings: {}", e);
            }
        }
        println!();

        // Example 6: Health check
        println!("🏥 Health Check");
        println!("{}", "-".repeat(80));

        match active_plugin.health_check().await {
            Ok(health) => {
                println!("Health: {}", if health.healthy { "✅ Healthy" } else { "❌ Unhealthy" });
                if let Some(msg) = health.message {
                    println!("Message: {}", msg);
                }
                if let Some(latency) = health.latency_ms {
                    println!("Latency: {}ms", latency);
                }
            }
            Err(e) => {
                println!("❌ Health check failed: {}", e);
            }
        }
    } else {
        println!("⚠️  No active plugin available");
        println!("Set environment variables and run again:");
        println!("  export OPENAI_API_KEY=\"sk-...\"");
    }

    println!();
    println!("{}", "=".repeat(80));
    println!("Example complete!");
    println!("{}", "=".repeat(80));
}

/// Load plugin configuration from YAML and test initialization
async fn load_and_test_plugin<P: EmbeddingPlugin + Default>(
    config_path: &str,
) -> anyhow::Result<P> {
    // Load configuration
    let config_content = fs::read_to_string(config_path)
        .map_err(|e| anyhow::anyhow!("Failed to read config file: {}", e))?;

    // Replace environment variables
    let config_content = expand_env_vars(&config_content);

    // Parse YAML
    let mut config: PluginConfig = serde_yaml::from_str(&config_content)
        .map_err(|e| anyhow::anyhow!("Failed to parse YAML: {}", e))?;

    println!("Loaded config: {}", config.name);

    // Check if API key is set (not just placeholder)
    let has_real_key = match &config.provider {
        vectadb::embeddings::ProviderConfig::OpenAI { api_key, .. }
        | vectadb::embeddings::ProviderConfig::Cohere { api_key, .. }
        | vectadb::embeddings::ProviderConfig::HuggingFace { api_key, .. }
        | vectadb::embeddings::ProviderConfig::Voyage { api_key, .. } => {
            !api_key.starts_with("${") && !api_key.is_empty()
        }
        vectadb::embeddings::ProviderConfig::Local { .. } => true,
    };

    if !has_real_key {
        return Err(anyhow::anyhow!("API key not set (still has placeholder)"));
    }

    // Initialize plugin
    let mut plugin = P::default();
    plugin
        .initialize(config)
        .await
        .map_err(|e| anyhow::anyhow!("Failed to initialize plugin: {}", e))?;

    println!("  Name: {}", plugin.name());
    println!("  Version: {}", plugin.version());
    println!("  Dimensions: {}", plugin.dimension());
    println!("  Max batch size: {}", plugin.max_batch_size());

    Ok(plugin)
}

/// Simple environment variable expansion
fn expand_env_vars(content: &str) -> String {
    let mut result = content.to_string();

    // Find all ${VAR_NAME} patterns
    for env_var in ["OPENAI_API_KEY", "COHERE_API_KEY", "HF_API_KEY"] {
        let pattern = format!("${{{}}}", env_var);
        if let Ok(value) = std::env::var(env_var) {
            result = result.replace(&pattern, &value);
        }
    }

    result
}
