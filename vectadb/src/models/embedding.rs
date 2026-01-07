use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

/// Metadata for embedded items in vector database
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EmbeddingMetadata {
    /// ID of the embedded item
    pub id: String,

    /// Type of the item ("agent", "task", etc.)
    pub item_type: String,

    /// Original metadata from the item
    #[serde(default)]
    pub metadata: JsonValue,
}

/// Result from similarity search
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimilarityResult<T> {
    /// The matched item
    pub item: T,

    /// Similarity score (0.0 to 1.0)
    pub score: f32,

    /// Distance (optional, inverse of score)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub distance: Option<f32>,
}

/// Generic similarity search request
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SimilaritySearchRequest {
    /// Query text to search for
    pub query: String,

    /// Minimum similarity threshold (0.0 to 1.0)
    #[serde(default = "default_threshold")]
    pub threshold: f32,

    /// Maximum number of results
    #[serde(default = "default_limit")]
    pub limit: usize,
}

fn default_threshold() -> f32 {
    0.65
}

fn default_limit() -> usize {
    10
}

impl SimilaritySearchRequest {
    pub fn new(query: String) -> Self {
        Self {
            query,
            threshold: default_threshold(),
            limit: default_limit(),
        }
    }

    pub fn with_threshold(mut self, threshold: f32) -> Self {
        self.threshold = threshold;
        self
    }

    pub fn with_limit(mut self, limit: usize) -> Self {
        self.limit = limit;
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_similarity_search_request_defaults() {
        let req = SimilaritySearchRequest::new("test query".to_string());
        assert_eq!(req.query, "test query");
        assert_eq!(req.threshold, 0.65);
        assert_eq!(req.limit, 10);
    }

    #[test]
    fn test_similarity_search_request_builder() {
        let req = SimilaritySearchRequest::new("test query".to_string())
            .with_threshold(0.8)
            .with_limit(20);

        assert_eq!(req.threshold, 0.8);
        assert_eq!(req.limit, 20);
    }
}
