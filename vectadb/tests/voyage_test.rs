// Integration tests for Voyage plugin
#[cfg(test)]
mod voyage_tests {
    use vectadb::embeddings::{VoyagePlugin, EmbeddingPlugin, PluginConfig, ProviderConfig};

    #[tokio::test]
    #[ignore] // Only run with real API key: cargo test -- --ignored
    async fn test_voyage_real_api() {
        let api_key = std::env::var("VOYAGE_API_KEY")
            .expect("VOYAGE_API_KEY not set. Run: export VOYAGE_API_KEY=your-key");

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

        let mut plugin = VoyagePlugin::new();
        plugin.initialize(config).await.expect("Failed to initialize plugin");

        // Test single embedding
        let embedding = plugin.embed("Hello, world!").await.expect("Failed to generate embedding");
        assert_eq!(embedding.len(), 1024, "Embedding dimension mismatch");

        // Test batch embedding
        let texts = vec!["Text 1".to_string(), "Text 2".to_string(), "Text 3".to_string()];
        let embeddings = plugin.embed_batch(&texts).await.expect("Failed to generate batch embeddings");
        assert_eq!(embeddings.len(), 3, "Should generate 3 embeddings");
        assert_eq!(embeddings[0].len(), 1024, "Embedding dimension mismatch");

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
    fn test_voyage_plugin_creation() {
        let plugin = VoyagePlugin::new();
        assert_eq!(plugin.name(), "voyage");
        assert_eq!(plugin.version(), "1.0.0");
        assert_eq!(plugin.dimension(), 1024);
        assert_eq!(plugin.max_batch_size(), 128);
    }
}
