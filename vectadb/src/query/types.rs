// Query types for hybrid query execution

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::db::Entity;

/// Hybrid query request combining multiple search strategies
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum HybridQuery {
    /// Pure vector similarity search
    Vector(VectorQuery),

    /// Pure graph traversal
    Graph(GraphQuery),

    /// Combined vector + graph search
    Combined(CombinedQuery),
}

/// Vector similarity search query
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorQuery {
    /// Entity type to search
    pub entity_type: String,

    /// Query text to embed and search
    pub query_text: String,

    /// Maximum number of results
    #[serde(default = "default_limit")]
    pub limit: usize,

    /// Expand to include subtypes using ontology
    #[serde(default)]
    pub expand_types: bool,

    /// Minimum similarity score threshold
    #[serde(default)]
    pub min_score: Option<f32>,
}

/// Graph traversal query
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphQuery {
    /// Starting entity ID
    pub start_entity_id: String,

    /// Relation types to traverse (empty = all relations)
    #[serde(default)]
    pub relation_types: Vec<String>,

    /// Maximum traversal depth
    #[serde(default = "default_depth")]
    pub depth: usize,

    /// Expand relation types using ontology reasoning
    #[serde(default)]
    pub expand_relations: bool,

    /// Direction of traversal
    #[serde(default)]
    pub direction: TraversalDirection,
}

/// Combined vector and graph query
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CombinedQuery {
    /// Vector search component
    pub vector_query: VectorQuery,

    /// Optional graph traversal from vector results
    pub graph_query: Option<GraphQuery>,

    /// How to merge results
    #[serde(default)]
    pub merge_strategy: MergeStrategy,
}

/// Direction for graph traversal
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum TraversalDirection {
    /// Follow outgoing edges
    Outgoing,

    /// Follow incoming edges
    Incoming,

    /// Follow both directions
    Both,
}

impl Default for TraversalDirection {
    fn default() -> Self {
        TraversalDirection::Outgoing
    }
}

/// Strategy for merging multiple result sets
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum MergeStrategy {
    /// Union of all results (deduplicated)
    Union,

    /// Intersection of results
    Intersection,

    /// Rank fusion - combine scores from multiple sources
    RankFusion,

    /// Vector results only, filtered by graph connectivity
    VectorPriority,

    /// Graph results only, ranked by vector similarity
    GraphPriority,
}

impl Default for MergeStrategy {
    fn default() -> Self {
        MergeStrategy::RankFusion
    }
}

/// Query execution result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryResult {
    /// Matching entities with scores
    pub results: Vec<ScoredResult>,

    /// Total number of results before limit
    pub total_count: usize,

    /// Query execution metadata
    pub metadata: QueryMetadata,
}

/// Entity with relevance score
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoredResult {
    /// The entity
    pub entity: Entity,

    /// Relevance score (0.0 - 1.0)
    pub score: f32,

    /// Source of this result
    pub source: ResultSource,

    /// Optional explanation of why this was returned
    #[serde(skip_serializing_if = "Option::is_none")]
    pub explanation: Option<String>,
}

/// Source of a query result
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum ResultSource {
    /// From vector similarity search
    Vector,

    /// From graph traversal
    Graph,

    /// From both sources (hybrid)
    Hybrid,
}

/// Query execution metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryMetadata {
    /// Total execution time in milliseconds
    pub execution_time_ms: u64,

    /// Number of entities from vector search
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vector_count: Option<usize>,

    /// Number of entities from graph traversal
    #[serde(skip_serializing_if = "Option::is_none")]
    pub graph_count: Option<usize>,

    /// Types that were searched (after ontology expansion)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub searched_types: Option<Vec<String>>,

    /// Relations that were traversed (after ontology expansion)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub traversed_relations: Option<Vec<String>>,

    /// Additional metadata
    #[serde(flatten)]
    pub extra: HashMap<String, String>,
}

// Default values
fn default_limit() -> usize {
    10
}

fn default_depth() -> usize {
    2
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_vector_query_defaults() {
        let json = r#"{
            "entity_type": "Agent",
            "query_text": "test"
        }"#;

        let query: VectorQuery = serde_json::from_str(json).unwrap();
        assert_eq!(query.limit, 10);
        assert!(!query.expand_types);
        assert!(query.min_score.is_none());
    }

    #[test]
    fn test_graph_query_defaults() {
        let json = r#"{
            "start_entity_id": "agent-001"
        }"#;

        let query: GraphQuery = serde_json::from_str(json).unwrap();
        assert_eq!(query.depth, 2);
        assert_eq!(query.direction, TraversalDirection::Outgoing);
        assert!(!query.expand_relations);
    }

    #[test]
    fn test_merge_strategy_default() {
        let strategy = MergeStrategy::default();
        assert_eq!(strategy, MergeStrategy::RankFusion);
    }
}
