// Database Verification Test - Checks data ingestion in SurrealDB and Qdrant
// This test verifies that data is properly stored and retrievable from both databases

use serde_json::Value as JsonValue;

// ============================================================================
// Database Verification Client
// ============================================================================

struct DatabaseVerifier {
    surrealdb_url: String,
    qdrant_url: String,
    http_client: reqwest::Client,
}

impl DatabaseVerifier {
    fn new(surrealdb_url: String, qdrant_url: String) -> Self {
        Self {
            surrealdb_url,
            qdrant_url,
            http_client: reqwest::Client::new(),
        }
    }

    // ========================================================================
    // SurrealDB Verification
    // ========================================================================

    async fn verify_surrealdb_health(&self) -> Result<JsonValue, Box<dyn std::error::Error>> {
        println!("🔍 Checking SurrealDB health...");
        let url = format!("{}/health", self.surrealdb_url);

        match self.http_client.get(&url).send().await {
            Ok(response) => {
                let status = response.status();
                if status.is_success() {
                    println!("   ✅ SurrealDB is healthy");
                    Ok(serde_json::json!({"status": "healthy"}))
                } else {
                    println!("   ⚠️  SurrealDB returned status: {}", status);
                    Ok(serde_json::json!({"status": "unhealthy", "code": status.as_u16()}))
                }
            }
            Err(e) => {
                println!("   ❌ SurrealDB connection failed: {}", e);
                Err(Box::new(e))
            }
        }
    }

    async fn query_surrealdb_entities(
        &self,
        table: &str,
    ) -> Result<Vec<JsonValue>, Box<dyn std::error::Error>> {
        println!("📊 Querying SurrealDB table: {}", table);

        let auth = format!(
            "Basic {}",
            general_purpose::STANDARD.encode("root:root")
        );

        let query = format!("SELECT * FROM {}", table);
        let body = serde_json::json!({
            "query": query
        });

        let response = self.http_client
            .post(format!("{}/sql", self.surrealdb_url))
            .header("Accept", "application/json")
            .header("Authorization", auth)
            .header("NS", "vectadb")
            .header("DB", "main")
            .json(&body)
            .send()
            .await?;

        if response.status().is_success() {
            let result = response.json::<JsonValue>().await?;
            // SurrealDB returns array of results
            if let Some(arr) = result.as_array() {
                if let Some(first) = arr.first() {
                    if let Some(result_obj) = first.get("result") {
                        if let Some(entities) = result_obj.as_array() {
                            println!("   ✅ Found {} records in {}", entities.len(), table);
                            return Ok(entities.clone());
                        }
                    }
                }
            }
            println!("   ⚠️  No records found in {}", table);
            Ok(vec![])
        } else {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            println!("   ❌ Query failed with status {}: {}", status, error_text);
            Err(format!("SurrealDB query failed: {}", status).into())
        }
    }

    async fn get_surrealdb_stats(&self) -> Result<DatabaseStats, Box<dyn std::error::Error>> {
        println!("\n🔍 Gathering SurrealDB statistics...");

        let mut stats = DatabaseStats::default();

        // Query entity table
        match self.query_surrealdb_entities("entity").await {
            Ok(entities) => {
                stats.entity_count = entities.len();

                // Count by entity type
                for entity in &entities {
                    if let Some(entity_type) = entity.get("entity_type").and_then(|v| v.as_str()) {
                        *stats.entities_by_type.entry(entity_type.to_string()).or_insert(0) += 1;
                    }
                }
            }
            Err(e) => {
                println!("   ⚠️  Could not query entities: {}", e);
            }
        }

        // Query relation table
        match self.query_surrealdb_entities("relation").await {
            Ok(relations) => {
                stats.relation_count = relations.len();

                // Count by relation type
                for relation in &relations {
                    if let Some(rel_type) = relation.get("relation_type").and_then(|v| v.as_str()) {
                        *stats.relations_by_type.entry(rel_type.to_string()).or_insert(0) += 1;
                    }
                }
            }
            Err(e) => {
                println!("   ⚠️  Could not query relations: {}", e);
            }
        }

        Ok(stats)
    }

    // ========================================================================
    // Qdrant Verification
    // ========================================================================

    async fn verify_qdrant_health(&self) -> Result<bool, Box<dyn std::error::Error>> {
        println!("🔍 Checking Qdrant health...");
        let url = format!("{}/healthz", self.qdrant_url);

        match self.http_client.get(&url).send().await {
            Ok(response) => {
                if response.status().is_success() {
                    println!("   ✅ Qdrant is healthy");
                    Ok(true)
                } else {
                    println!("   ⚠️  Qdrant returned status: {}", response.status());
                    Ok(false)
                }
            }
            Err(e) => {
                println!("   ❌ Qdrant connection failed: {}", e);
                Err(Box::new(e))
            }
        }
    }

    async fn list_qdrant_collections(&self) -> Result<Vec<String>, Box<dyn std::error::Error>> {
        println!("📊 Listing Qdrant collections...");

        let url = format!("{}/collections", self.qdrant_url);
        let response = self.http_client.get(&url).send().await?;

        if response.status().is_success() {
            let result = response.json::<JsonValue>().await?;

            if let Some(collections_obj) = result.get("result") {
                if let Some(collections_arr) = collections_obj.get("collections") {
                    if let Some(arr) = collections_arr.as_array() {
                        let names: Vec<String> = arr.iter()
                            .filter_map(|c| c.get("name").and_then(|n| n.as_str()).map(|s| s.to_string()))
                            .collect();

                        println!("   ✅ Found {} collections", names.len());
                        for name in &names {
                            println!("      - {}", name);
                        }
                        return Ok(names);
                    }
                }
            }
            println!("   ⚠️  No collections found");
            Ok(vec![])
        } else {
            Err(format!("Failed to list collections: {}", response.status()).into())
        }
    }

    async fn get_collection_info(
        &self,
        collection_name: &str,
    ) -> Result<CollectionInfo, Box<dyn std::error::Error>> {
        println!("📊 Getting info for collection: {}", collection_name);

        let url = format!("{}/collections/{}", self.qdrant_url, collection_name);
        let response = self.http_client.get(&url).send().await?;

        if response.status().is_success() {
            let result = response.json::<JsonValue>().await?;

            let mut info = CollectionInfo {
                name: collection_name.to_string(),
                ..Default::default()
            };

            if let Some(result_obj) = result.get("result") {
                if let Some(points_count) = result_obj.get("points_count").and_then(|v| v.as_u64()) {
                    info.points_count = points_count as usize;
                }
                if let Some(vectors_count) = result_obj.get("vectors_count").and_then(|v| v.as_u64()) {
                    info.vectors_count = vectors_count as usize;
                }
                if let Some(config) = result_obj.get("config") {
                    if let Some(params) = config.get("params") {
                        if let Some(vectors) = params.get("vectors") {
                            if let Some(size) = vectors.get("size").and_then(|v| v.as_u64()) {
                                info.vector_size = size as usize;
                            }
                            if let Some(distance) = vectors.get("distance").and_then(|v| v.as_str()) {
                                info.distance_metric = distance.to_string();
                            }
                        }
                    }
                }
            }

            println!("   ✅ Points: {}, Vectors: {}, Dimension: {}",
                     info.points_count, info.vectors_count, info.vector_size);
            Ok(info)
        } else {
            Err(format!("Failed to get collection info: {}", response.status()).into())
        }
    }

    async fn search_qdrant_collection(
        &self,
        collection_name: &str,
        query_vector: Vec<f32>,
        limit: usize,
    ) -> Result<Vec<SearchResult>, Box<dyn std::error::Error>> {
        println!("🔍 Searching collection: {}", collection_name);

        let url = format!("{}/collections/{}/points/search", self.qdrant_url, collection_name);
        let body = serde_json::json!({
            "vector": query_vector,
            "limit": limit,
            "with_payload": true,
            "with_vector": false
        });

        let response = self.http_client.post(&url)
            .json(&body)
            .send()
            .await?;

        if response.status().is_success() {
            let result = response.json::<JsonValue>().await?;

            let mut results = vec![];
            if let Some(result_arr) = result.get("result").and_then(|v| v.as_array()) {
                for item in result_arr {
                    let score = item.get("score").and_then(|v| v.as_f64()).unwrap_or(0.0);
                    let id = item.get("id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("unknown")
                        .to_string();

                    results.push(SearchResult { id, score });
                }
            }

            println!("   ✅ Found {} results", results.len());
            Ok(results)
        } else {
            Err(format!("Search failed: {}", response.status()).into())
        }
    }

    async fn get_qdrant_stats(&self) -> Result<VectorStats, Box<dyn std::error::Error>> {
        println!("\n🔍 Gathering Qdrant statistics...");

        let mut stats = VectorStats::default();

        let collections = self.list_qdrant_collections().await?;
        stats.collection_count = collections.len();

        for collection_name in &collections {
            match self.get_collection_info(collection_name).await {
                Ok(info) => {
                    stats.total_vectors += info.vectors_count;
                    stats.collections.push(info);
                }
                Err(e) => {
                    println!("   ⚠️  Could not get info for {}: {}", collection_name, e);
                }
            }
        }

        Ok(stats)
    }

    // ========================================================================
    // Comprehensive Verification
    // ========================================================================

    async fn run_full_verification(&self) -> Result<VerificationReport, Box<dyn std::error::Error>> {
        println!("\n╔════════════════════════════════════════╗");
        println!("║  DATABASE VERIFICATION TEST SUITE     ║");
        println!("╚════════════════════════════════════════╝\n");

        let mut report = VerificationReport::default();

        // Verify SurrealDB
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("  SURREALDB VERIFICATION");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        match self.verify_surrealdb_health().await {
            Ok(_) => {
                report.surrealdb_healthy = true;

                match self.get_surrealdb_stats().await {
                    Ok(stats) => {
                        report.surrealdb_stats = Some(stats);
                    }
                    Err(e) => {
                        println!("⚠️  Could not gather SurrealDB stats: {}", e);
                    }
                }
            }
            Err(e) => {
                report.surrealdb_healthy = false;
                println!("❌ SurrealDB verification failed: {}", e);
            }
        }

        // Verify Qdrant
        println!("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        println!("  QDRANT VERIFICATION");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

        match self.verify_qdrant_health().await {
            Ok(healthy) => {
                report.qdrant_healthy = healthy;

                if healthy {
                    match self.get_qdrant_stats().await {
                        Ok(stats) => {
                            report.qdrant_stats = Some(stats);
                        }
                        Err(e) => {
                            println!("⚠️  Could not gather Qdrant stats: {}", e);
                        }
                    }
                }
            }
            Err(e) => {
                report.qdrant_healthy = false;
                println!("❌ Qdrant verification failed: {}", e);
            }
        }

        // Test vector search if data exists
        if report.qdrant_healthy {
            if let Some(stats) = &report.qdrant_stats {
                if !stats.collections.is_empty() {
                    println!("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                    println!("  VECTOR SEARCH TEST");
                    println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

                    let test_collection = &stats.collections[0];
                    if test_collection.vectors_count > 0 {
                        // Create a random test vector
                        let test_vector: Vec<f32> = (0..test_collection.vector_size)
                            .map(|_| rand::random::<f32>() * 2.0 - 1.0)
                            .collect();

                        match self.search_qdrant_collection(&test_collection.name, test_vector, 5).await {
                            Ok(results) => {
                                report.search_test_passed = true;
                                report.search_results_count = results.len();
                                println!("   ✅ Vector search successful");

                                for (i, result) in results.iter().take(3).enumerate() {
                                    println!("      {}. ID: {} (score: {:.4})", i + 1, result.id, result.score);
                                }
                            }
                            Err(e) => {
                                println!("   ❌ Vector search failed: {}", e);
                            }
                        }
                    }
                }
            }
        }

        Ok(report)
    }
}

// ============================================================================
// Data Structures
// ============================================================================

#[derive(Debug, Default)]
struct DatabaseStats {
    entity_count: usize,
    relation_count: usize,
    entities_by_type: std::collections::HashMap<String, usize>,
    relations_by_type: std::collections::HashMap<String, usize>,
}

#[derive(Debug, Default, Clone)]
struct CollectionInfo {
    name: String,
    points_count: usize,
    vectors_count: usize,
    vector_size: usize,
    distance_metric: String,
}

#[derive(Debug, Default)]
struct VectorStats {
    collection_count: usize,
    total_vectors: usize,
    collections: Vec<CollectionInfo>,
}

#[derive(Debug)]
struct SearchResult {
    id: String,
    score: f64,
}

#[derive(Debug, Default)]
struct VerificationReport {
    surrealdb_healthy: bool,
    qdrant_healthy: bool,
    surrealdb_stats: Option<DatabaseStats>,
    qdrant_stats: Option<VectorStats>,
    search_test_passed: bool,
    search_results_count: usize,
}

impl VerificationReport {
    fn print_summary(&self) {
        println!("\n╔════════════════════════════════════════╗");
        println!("║     VERIFICATION REPORT SUMMARY       ║");
        println!("╚════════════════════════════════════════╝\n");

        // SurrealDB Summary
        println!("📊 SURREALDB STATUS");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        if self.surrealdb_healthy {
            println!("   Status: ✅ HEALTHY");

            if let Some(stats) = &self.surrealdb_stats {
                println!("\n   Entities:  {}", stats.entity_count);
                if !stats.entities_by_type.is_empty() {
                    for (entity_type, count) in &stats.entities_by_type {
                        println!("      - {}: {}", entity_type, count);
                    }
                }

                println!("\n   Relations: {}", stats.relation_count);
                if !stats.relations_by_type.is_empty() {
                    for (rel_type, count) in &stats.relations_by_type {
                        println!("      - {}: {}", rel_type, count);
                    }
                }
            }
        } else {
            println!("   Status: ❌ UNHEALTHY");
        }

        // Qdrant Summary
        println!("\n📊 QDRANT STATUS");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        if self.qdrant_healthy {
            println!("   Status: ✅ HEALTHY");

            if let Some(stats) = &self.qdrant_stats {
                println!("\n   Collections: {}", stats.collection_count);
                println!("   Total Vectors: {}", stats.total_vectors);

                if !stats.collections.is_empty() {
                    println!("\n   Collection Details:");
                    for collection in &stats.collections {
                        println!("      - {}", collection.name);
                        println!("        Points: {}", collection.points_count);
                        println!("        Vectors: {}", collection.vectors_count);
                        println!("        Dimension: {}", collection.vector_size);
                        println!("        Distance: {}", collection.distance_metric);
                    }
                }
            }
        } else {
            println!("   Status: ❌ UNHEALTHY");
        }

        // Vector Search Test
        println!("\n📊 VECTOR SEARCH TEST");
        println!("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        if self.search_test_passed {
            println!("   Status: ✅ PASSED");
            println!("   Results Found: {}", self.search_results_count);
        } else {
            println!("   Status: ⚠️  NOT TESTED (no data or unavailable)");
        }

        // Overall Status
        println!("\n╔════════════════════════════════════════╗");
        println!("║         OVERALL STATUS                ║");
        println!("╚════════════════════════════════════════╝\n");

        let overall_healthy = self.surrealdb_healthy && self.qdrant_healthy;

        if overall_healthy {
            println!("   ✅ ALL SYSTEMS OPERATIONAL");

            let has_data = self.surrealdb_stats.as_ref().map(|s| s.entity_count > 0).unwrap_or(false)
                || self.qdrant_stats.as_ref().map(|s| s.total_vectors > 0).unwrap_or(false);

            if has_data {
                println!("   ✅ DATA SUCCESSFULLY INGESTED");
            } else {
                println!("   ⚠️  NO DATA FOUND - Run bedrock_test first to ingest data");
            }
        } else {
            println!("   ❌ SOME SYSTEMS UNHEALTHY");
            if !self.surrealdb_healthy {
                println!("      - SurrealDB: Not responding");
            }
            if !self.qdrant_healthy {
                println!("      - Qdrant: Not responding");
            }
        }

        println!();
    }
}

// ============================================================================
// Main
// ============================================================================

use base64::{Engine as _, engine::general_purpose};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let surrealdb_url = std::env::var("SURREALDB_URL")
        .unwrap_or_else(|_| "http://localhost:8000".to_string());

    let qdrant_url = std::env::var("QDRANT_URL")
        .unwrap_or_else(|_| "http://localhost:6333".to_string());

    let verifier = DatabaseVerifier::new(surrealdb_url.clone(), qdrant_url.clone());

    println!("Configuration:");
    println!("  SurrealDB: {}", surrealdb_url);
    println!("  Qdrant:    {}", qdrant_url);
    println!();

    match verifier.run_full_verification().await {
        Ok(report) => {
            report.print_summary();

            // Exit with appropriate code
            if report.surrealdb_healthy && report.qdrant_healthy {
                std::process::exit(0);
            } else {
                std::process::exit(1);
            }
        }
        Err(e) => {
            eprintln!("❌ Verification failed: {}", e);
            std::process::exit(1);
        }
    }
}
