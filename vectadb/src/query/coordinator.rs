// Query coordinator for hybrid query execution

use anyhow::{Context, Result};
use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::Instant;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

use crate::db::{Entity, QdrantClient, SurrealDBClient};
use crate::embeddings::EmbeddingManager;
use crate::intelligence::OntologyReasoner;
use super::types::*;

/// Coordinator for executing hybrid queries combining vector search,
/// graph traversal, and ontology reasoning
pub struct QueryCoordinator {
    surreal: Arc<SurrealDBClient>,
    qdrant: Arc<QdrantClient>,
    reasoner: Arc<RwLock<Option<OntologyReasoner>>>,
    embedding_service: Arc<EmbeddingManager>,
}

impl QueryCoordinator {
    /// Create a new query coordinator
    pub fn new(
        surreal: Arc<SurrealDBClient>,
        qdrant: Arc<QdrantClient>,
        reasoner: Arc<RwLock<Option<OntologyReasoner>>>,
        embedding_service: Arc<EmbeddingManager>,
    ) -> Self {
        Self {
            surreal,
            qdrant,
            reasoner,
            embedding_service,
        }
    }

    /// Execute a hybrid query
    pub async fn execute(&self, query: &HybridQuery) -> Result<QueryResult> {
        let start_time = Instant::now();

        let result = match query {
            HybridQuery::Vector(vq) => self.execute_vector_query(vq).await?,
            HybridQuery::Graph(gq) => self.execute_graph_query(gq).await?,
            HybridQuery::Combined(cq) => self.execute_combined_query(cq).await?,
        };

        // Add execution time
        let execution_time_ms = start_time.elapsed().as_millis() as u64;
        let mut result = result;
        result.metadata.execution_time_ms = execution_time_ms;

        info!(
            "Query executed in {}ms, returned {} results",
            execution_time_ms,
            result.results.len()
        );

        Ok(result)
    }

    // ============================================================================
    // Vector Search
    // ============================================================================

    /// Execute a pure vector similarity search
    async fn execute_vector_query(&self, query: &VectorQuery) -> Result<QueryResult> {
        debug!("Executing vector query for type: {}", query.entity_type);

        // Generate query embedding
        let query_vector = self
            .embedding_service
            .embed(&query.query_text)
            .await
            .context("Failed to generate query embedding")?;

        // Expand entity types if requested
        let search_types = if query.expand_types {
            self.expand_entity_types(&query.entity_type).await?
        } else {
            vec![query.entity_type.clone()]
        };

        debug!("Searching types: {:?}", search_types);

        // Search across all types
        let mut all_results: HashMap<String, f32> = HashMap::new();

        for entity_type in &search_types {
            match self
                .qdrant
                .search_similar_with_scores(entity_type, query_vector.clone(), query.limit)
                .await
            {
                Ok(results) => {
                    for (entity_id, score) in results {
                        // Apply score threshold
                        if let Some(min_score) = query.min_score {
                            if score < min_score {
                                continue;
                            }
                        }
                        all_results.insert(entity_id, score);
                    }
                }
                Err(e) => {
                    warn!("Failed to search in type {}: {}", entity_type, e);
                }
            }
        }

        // Fetch entities from SurrealDB
        let mut scored_results = Vec::new();
        for (entity_id, score) in all_results {
            if let Some(entity) = self.surreal.get_entity(&entity_id).await? {
                scored_results.push(ScoredResult {
                    entity,
                    score,
                    source: ResultSource::Vector,
                    explanation: Some(format!(
                        "Vector similarity: {:.3}",
                        score
                    )),
                });
            }
        }

        // Sort by score descending
        scored_results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap());

        // Apply limit
        let total_count = scored_results.len();
        scored_results.truncate(query.limit);

        Ok(QueryResult {
            results: scored_results,
            total_count,
            metadata: QueryMetadata {
                execution_time_ms: 0, // Will be filled by caller
                vector_count: Some(total_count),
                graph_count: None,
                searched_types: Some(search_types),
                traversed_relations: None,
                extra: HashMap::new(),
            },
        })
    }

    // ============================================================================
    // Graph Traversal
    // ============================================================================

    /// Execute a pure graph traversal query
    async fn execute_graph_query(&self, query: &GraphQuery) -> Result<QueryResult> {
        debug!(
            "Executing graph query from entity: {}",
            query.start_entity_id
        );

        // Expand relation types if requested
        let relation_types = if query.expand_relations && !query.relation_types.is_empty() {
            self.expand_relation_types(&query.relation_types).await?
        } else {
            query.relation_types.clone()
        };

        debug!("Traversing relations: {:?}", relation_types);

        // Perform traversal based on direction
        let entities = match query.direction {
            TraversalDirection::Outgoing => {
                self.traverse_outgoing(&query.start_entity_id, &relation_types, query.depth)
                    .await?
            }
            TraversalDirection::Incoming => {
                self.traverse_incoming(&query.start_entity_id, &relation_types, query.depth)
                    .await?
            }
            TraversalDirection::Both => {
                let mut outgoing = self
                    .traverse_outgoing(&query.start_entity_id, &relation_types, query.depth)
                    .await?;
                let incoming = self
                    .traverse_incoming(&query.start_entity_id, &relation_types, query.depth)
                    .await?;
                outgoing.extend(incoming);
                outgoing
            }
        };

        // Deduplicate by entity ID
        let mut seen = HashSet::new();
        let mut unique_entities = Vec::new();
        for entity in entities {
            if seen.insert(entity.id.clone()) {
                unique_entities.push(entity);
            }
        }

        // Convert to scored results (graph results don't have similarity scores)
        let total_count = unique_entities.len();
        let scored_results: Vec<ScoredResult> = unique_entities
            .into_iter()
            .enumerate()
            .map(|(i, entity)| {
                // Score based on inverse of distance from start (closer = higher score)
                let score = 1.0 / (i as f32 + 1.0);
                ScoredResult {
                    entity,
                    score,
                    source: ResultSource::Graph,
                    explanation: Some(format!("Graph distance: {}", i + 1)),
                }
            })
            .collect();

        Ok(QueryResult {
            results: scored_results,
            total_count,
            metadata: QueryMetadata {
                execution_time_ms: 0,
                vector_count: None,
                graph_count: Some(total_count),
                searched_types: None,
                traversed_relations: Some(relation_types),
                extra: HashMap::new(),
            },
        })
    }

    /// Traverse outgoing edges
    async fn traverse_outgoing(
        &self,
        start_id: &str,
        relation_types: &[String],
        depth: usize,
    ) -> Result<Vec<Entity>> {
        let mut visited = HashSet::new();
        let mut result = Vec::new();
        let mut current_level = vec![start_id.to_string()];

        for level in 0..depth {
            let mut next_level = Vec::new();

            for entity_id in current_level {
                if visited.contains(&entity_id) {
                    continue;
                }
                visited.insert(entity_id.clone());

                // Get outgoing relations
                let relations = if relation_types.is_empty() {
                    self.surreal.get_outgoing_relations(&entity_id, None).await?
                } else {
                    let mut all_relations = Vec::new();
                    for rel_type in relation_types {
                        let rels = self
                            .surreal
                            .get_outgoing_relations(&entity_id, Some(rel_type))
                            .await?;
                        all_relations.extend(rels);
                    }
                    all_relations
                };

                // Collect target entities
                for relation in relations {
                    if let Some(target) = self.surreal.get_entity(&relation.target_id).await? {
                        let target_id_string = target.id_string();
                        if !visited.contains(&target_id_string) {
                            result.push(target.clone());
                            next_level.push(target_id_string);
                        }
                    }
                }
            }

            debug!(
                "Level {}: visited {} entities, queued {}",
                level + 1,
                result.len(),
                next_level.len()
            );

            current_level = next_level;

            if current_level.is_empty() {
                break;
            }
        }

        Ok(result)
    }

    /// Traverse incoming edges
    async fn traverse_incoming(
        &self,
        start_id: &str,
        relation_types: &[String],
        depth: usize,
    ) -> Result<Vec<Entity>> {
        let mut visited = HashSet::new();
        let mut result = Vec::new();
        let mut current_level = vec![start_id.to_string()];

        for level in 0..depth {
            let mut next_level = Vec::new();

            for entity_id in current_level {
                if visited.contains(&entity_id) {
                    continue;
                }
                visited.insert(entity_id.clone());

                // Get incoming relations
                let relations = if relation_types.is_empty() {
                    self.surreal.get_incoming_relations(&entity_id, None).await?
                } else {
                    let mut all_relations = Vec::new();
                    for rel_type in relation_types {
                        let rels = self
                            .surreal
                            .get_incoming_relations(&entity_id, Some(rel_type))
                            .await?;
                        all_relations.extend(rels);
                    }
                    all_relations
                };

                // Collect source entities
                for relation in relations {
                    if let Some(source) = self.surreal.get_entity(&relation.source_id).await? {
                        let source_id_string = source.id_string();
                        if !visited.contains(&source_id_string) {
                            result.push(source.clone());
                            next_level.push(source_id_string);
                        }
                    }
                }
            }

            debug!(
                "Level {}: visited {} entities, queued {}",
                level + 1,
                result.len(),
                next_level.len()
            );

            current_level = next_level;

            if current_level.is_empty() {
                break;
            }
        }

        Ok(result)
    }

    // ============================================================================
    // Combined Queries
    // ============================================================================

    /// Execute a combined vector + graph query
    async fn execute_combined_query(&self, query: &CombinedQuery) -> Result<QueryResult> {
        debug!("Executing combined query with strategy: {:?}", query.merge_strategy);

        // Execute vector search
        let vector_result = self.execute_vector_query(&query.vector_query).await?;

        // If no graph query, return vector results
        let graph_result = if let Some(ref graph_query) = query.graph_query {
            Some(self.execute_graph_query(graph_query).await?)
        } else {
            None
        };

        // Merge results based on strategy
        let merged = self.merge_results(
            vector_result,
            graph_result,
            query.merge_strategy,
            query.vector_query.limit,
        );

        Ok(merged)
    }

    /// Merge vector and graph results using specified strategy
    fn merge_results(
        &self,
        vector_result: QueryResult,
        graph_result: Option<QueryResult>,
        strategy: MergeStrategy,
        limit: usize,
    ) -> QueryResult {
        let graph_result = match graph_result {
            Some(r) => r,
            None => return vector_result,
        };

        let mut merged_results = match strategy {
            MergeStrategy::Union => self.merge_union(vector_result.results, graph_result.results),
            MergeStrategy::Intersection => {
                self.merge_intersection(vector_result.results, graph_result.results)
            }
            MergeStrategy::RankFusion => {
                self.merge_rank_fusion(vector_result.results, graph_result.results)
            }
            MergeStrategy::VectorPriority => {
                self.merge_vector_priority(vector_result.results, graph_result.results)
            }
            MergeStrategy::GraphPriority => {
                self.merge_graph_priority(vector_result.results, graph_result.results)
            }
        };

        // Sort by score descending
        merged_results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap());

        let total_count = merged_results.len();
        merged_results.truncate(limit);

        // Merge metadata
        let mut metadata = QueryMetadata {
            execution_time_ms: 0,
            vector_count: vector_result.metadata.vector_count,
            graph_count: graph_result.metadata.graph_count,
            searched_types: vector_result.metadata.searched_types,
            traversed_relations: graph_result.metadata.traversed_relations,
            extra: HashMap::new(),
        };
        metadata.extra.insert("merge_strategy".to_string(), format!("{:?}", strategy));

        QueryResult {
            results: merged_results,
            total_count,
            metadata,
        }
    }

    /// Union merge: combine all results, deduplicate
    fn merge_union(
        &self,
        vector_results: Vec<ScoredResult>,
        graph_results: Vec<ScoredResult>,
    ) -> Vec<ScoredResult> {
        let mut result_map: HashMap<String, ScoredResult> = HashMap::new();

        for result in vector_results {
            result_map.insert(result.entity.id_string(), result);
        }

        for result in graph_results {
            let entity_id = result.entity.id_string();
            if let Some(existing) = result_map.get_mut(&entity_id) {
                // Entity exists in both - mark as hybrid and average scores
                existing.score = (existing.score + result.score) / 2.0;
                existing.source = ResultSource::Hybrid;
                existing.explanation = Some("Found in both vector and graph search".to_string());
            } else {
                result_map.insert(entity_id, result);
            }
        }

        result_map.into_values().collect()
    }

    /// Intersection merge: only entities in both result sets
    fn merge_intersection(
        &self,
        vector_results: Vec<ScoredResult>,
        graph_results: Vec<ScoredResult>,
    ) -> Vec<ScoredResult> {
        let graph_ids: HashSet<String> = graph_results
            .iter()
            .map(|r| r.entity.id_string())
            .collect();

        vector_results
            .into_iter()
            .filter(|r| graph_ids.contains(&r.entity.id_string()))
            .map(|mut r| {
                r.source = ResultSource::Hybrid;
                r.explanation = Some("Present in both vector and graph results".to_string());
                r
            })
            .collect()
    }

    /// Rank fusion merge: combine using reciprocal rank fusion
    fn merge_rank_fusion(
        &self,
        vector_results: Vec<ScoredResult>,
        graph_results: Vec<ScoredResult>,
    ) -> Vec<ScoredResult> {
        let mut scores: HashMap<String, f32> = HashMap::new();
        let mut entities: HashMap<String, Entity> = HashMap::new();

        // Reciprocal Rank Fusion constant
        const K: f32 = 60.0;

        // Add vector ranks
        for (rank, result) in vector_results.iter().enumerate() {
            let rrf_score = 1.0 / (K + rank as f32 + 1.0);
            let entity_id = result.entity.id_string();
            scores.insert(entity_id.clone(), rrf_score);
            entities.insert(entity_id, result.entity.clone());
        }

        // Add graph ranks
        for (rank, result) in graph_results.iter().enumerate() {
            let rrf_score = 1.0 / (K + rank as f32 + 1.0);
            let entity_id = result.entity.id_string();
            scores
                .entry(entity_id.clone())
                .and_modify(|s| *s += rrf_score)
                .or_insert(rrf_score);
            entities.insert(entity_id, result.entity.clone());
        }

        scores
            .into_iter()
            .map(|(entity_id, score)| ScoredResult {
                entity: entities.get(&entity_id).unwrap().clone(),
                score,
                source: ResultSource::Hybrid,
                explanation: Some("Ranked by reciprocal rank fusion".to_string()),
            })
            .collect()
    }

    /// Vector priority: filter vector results by graph connectivity
    fn merge_vector_priority(
        &self,
        vector_results: Vec<ScoredResult>,
        graph_results: Vec<ScoredResult>,
    ) -> Vec<ScoredResult> {
        let graph_ids: HashSet<String> = graph_results
            .iter()
            .map(|r| r.entity.id_string())
            .collect();

        vector_results
            .into_iter()
            .map(|mut r| {
                if graph_ids.contains(&r.entity.id_string()) {
                    r.source = ResultSource::Hybrid;
                    r.explanation =
                        Some("High similarity and graph connected".to_string());
                }
                r
            })
            .collect()
    }

    /// Graph priority: rank graph results by vector similarity
    fn merge_graph_priority(
        &self,
        vector_results: Vec<ScoredResult>,
        graph_results: Vec<ScoredResult>,
    ) -> Vec<ScoredResult> {
        let vector_scores: HashMap<String, f32> = vector_results
            .into_iter()
            .map(|r| (r.entity.id_string(), r.score))
            .collect();

        graph_results
            .into_iter()
            .map(|mut r| {
                if let Some(&vector_score) = vector_scores.get(&r.entity.id_string()) {
                    r.score = vector_score;
                    r.source = ResultSource::Hybrid;
                    r.explanation = Some("Graph connected with vector similarity".to_string());
                }
                r
            })
            .collect()
    }

    // ============================================================================
    // Ontology Helpers
    // ============================================================================

    /// Expand entity type to include all subtypes using ontology
    async fn expand_entity_types(&self, entity_type: &str) -> Result<Vec<String>> {
        let reasoner = self.reasoner.read().await;

        if let Some(ref r) = *reasoner {
            match r.expand_query(entity_type) {
                Ok(expanded) => Ok(expanded.expanded_types),
                Err(e) => {
                    warn!("Failed to expand entity type: {}", e);
                    Ok(vec![entity_type.to_string()])
                }
            }
        } else {
            Ok(vec![entity_type.to_string()])
        }
    }

    /// Expand relation types using ontology inference
    async fn expand_relation_types(&self, relation_types: &[String]) -> Result<Vec<String>> {
        let reasoner = self.reasoner.read().await;

        if let Some(ref r) = *reasoner {
            let mut expanded = HashSet::new();
            for rel_type in relation_types {
                // Add the original type
                expanded.insert(rel_type.clone());

                // Add inferred relations (symmetric, inverse, etc.)
                for entity_type in r.schema().entity_types.keys() {
                    if let Ok(expansion) = r.expand_query(entity_type) {
                        for inferred in expansion.inferred_relations {
                            if &inferred.relation_type == rel_type {
                                expanded.insert(inferred.relation_type);
                            }
                        }
                    }
                }
            }
            Ok(expanded.into_iter().collect())
        } else {
            Ok(relation_types.to_vec())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_merge_strategies() {
        // Test that merge strategies are correctly defined
        assert_eq!(MergeStrategy::default(), MergeStrategy::RankFusion);
    }
}
