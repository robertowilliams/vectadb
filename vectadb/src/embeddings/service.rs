use crate::error::{Result, VectaDBError};
use sentence_transformers_rs::sentence_transformer::{SentenceTransformerBuilder, Which};
use std::sync::Arc;

/// Supported embedding models
#[derive(Debug, Clone, Copy)]
pub enum EmbeddingModel {
    /// all-MiniLM-L6-v2 (384 dimensions) - Fast and efficient
    AllMiniLML6v2,
    /// all-MiniLM-L12-v2 (384 dimensions) - Better quality
    AllMiniLML12v2,
    /// all-mpnet-base-v2 (768 dimensions) - High quality
    AllMpnetBaseV2,
    /// BGE Small English (384 dimensions) - Good balance
    BgeSmallEnV1_5,
}

impl EmbeddingModel {
    /// Get the dimension size for this model
    pub fn dimension(&self) -> usize {
        match self {
            EmbeddingModel::AllMiniLML6v2 => 384,
            EmbeddingModel::AllMiniLML12v2 => 384,
            EmbeddingModel::AllMpnetBaseV2 => 768,
            EmbeddingModel::BgeSmallEnV1_5 => 384,
        }
    }

    /// Convert to sentence-transformers-rs Which enum
    fn to_which(&self) -> Which {
        match self {
            EmbeddingModel::AllMiniLML6v2 => Which::AllMiniLML6v2,
            EmbeddingModel::AllMiniLML12v2 => Which::AllMiniLML12v2,
            EmbeddingModel::AllMpnetBaseV2 => Which::AllMpnetBaseV2,
            EmbeddingModel::BgeSmallEnV1_5 => Which::BgeSmallEnV1_5,
        }
    }

    /// Get model name as string
    pub fn name(&self) -> &'static str {
        match self {
            EmbeddingModel::AllMiniLML6v2 => "all-MiniLM-L6-v2",
            EmbeddingModel::AllMiniLML12v2 => "all-MiniLM-L12-v2",
            EmbeddingModel::AllMpnetBaseV2 => "all-mpnet-base-v2",
            EmbeddingModel::BgeSmallEnV1_5 => "BAAI/bge-small-en-v1.5",
        }
    }
}

/// Embedding service for generating text embeddings
pub struct EmbeddingService {
    model: Arc<sentence_transformers_rs::sentence_transformer::SentenceTransformer>,
    model_type: EmbeddingModel,
    batch_size: usize,
}

impl EmbeddingService {
    /// Create a new embedding service with the specified model
    pub fn new(model: EmbeddingModel, batch_size: Option<usize>) -> Result<Self> {
        let batch_size = batch_size.unwrap_or(32);

        // Use CPU device for now (can be extended to support GPU)
        let device = candle_core::Device::Cpu;

        let transformer = SentenceTransformerBuilder::with_sentence_transformer(&model.to_which())
            .batch_size(batch_size)
            .with_device(&device)
            .build()
            .map_err(|e| VectaDBError::Embedding(format!("Failed to build model: {}", e)))?;

        Ok(Self {
            model: Arc::new(transformer),
            model_type: model,
            batch_size,
        })
    }

    /// Generate embedding for a single text
    pub fn encode(&self, text: &str) -> Result<Vec<f32>> {
        let embeddings = self
            .model
            .embed(&[text])
            .map_err(|e| VectaDBError::Embedding(format!("Failed to generate embedding: {}", e)))?;

        if embeddings.is_empty() {
            return Err(VectaDBError::Embedding(
                "No embeddings generated".to_string(),
            ));
        }

        Ok(embeddings[0].clone())
    }

    /// Generate embeddings for multiple texts in batch
    pub fn encode_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(vec![]);
        }

        let text_refs: Vec<&str> = texts.iter().map(|s| s.as_str()).collect();
        let embeddings = self
            .model
            .embed(&text_refs)
            .map_err(|e| VectaDBError::Embedding(format!("Failed to generate embeddings: {}", e)))?;

        Ok(embeddings)
    }

    /// Get the dimension of embeddings produced by this model
    pub fn dimension(&self) -> usize {
        self.model_type.dimension()
    }

    /// Get the model name
    pub fn model_name(&self) -> &'static str {
        self.model_type.name()
    }

    /// Get the batch size
    pub fn batch_size(&self) -> usize {
        self.batch_size
    }

    /// Calculate cosine similarity between two embeddings
    pub fn cosine_similarity(&self, a: &[f32], b: &[f32]) -> Result<f32> {
        if a.len() != b.len() {
            return Err(VectaDBError::InvalidInput(
                "Embeddings must have the same dimension".to_string(),
            ));
        }

        let similarity = sentence_transformers_rs::utils::cosine_similarity(a, b)
            .map_err(|e| VectaDBError::Embedding(format!("Failed to calculate similarity: {}", e)))?;

        Ok(similarity)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_embedding_model_dimensions() {
        assert_eq!(EmbeddingModel::AllMiniLML6v2.dimension(), 384);
        assert_eq!(EmbeddingModel::AllMiniLML12v2.dimension(), 384);
        assert_eq!(EmbeddingModel::AllMpnetBaseV2.dimension(), 768);
        assert_eq!(EmbeddingModel::BgeSmallEnV1_5.dimension(), 384);
    }

    #[test]
    fn test_embedding_model_names() {
        assert_eq!(EmbeddingModel::AllMiniLML6v2.name(), "all-MiniLM-L6-v2");
        assert_eq!(EmbeddingModel::AllMiniLML12v2.name(), "all-MiniLM-L12-v2");
        assert_eq!(EmbeddingModel::AllMpnetBaseV2.name(), "all-mpnet-base-v2");
        assert_eq!(EmbeddingModel::BgeSmallEnV1_5.name(), "BAAI/bge-small-en-v1.5");
    }

    #[test]
    #[ignore] // Ignore by default as it downloads models
    fn test_embedding_service_creation() {
        let service = EmbeddingService::new(EmbeddingModel::AllMiniLML6v2, Some(32));
        assert!(service.is_ok());

        let service = service.unwrap();
        assert_eq!(service.dimension(), 384);
        assert_eq!(service.batch_size(), 32);
        assert_eq!(service.model_name(), "all-MiniLM-L6-v2");
    }

    #[test]
    #[ignore] // Ignore by default as it downloads models
    fn test_encode_single() {
        let service = EmbeddingService::new(EmbeddingModel::AllMiniLML6v2, Some(32)).unwrap();
        let embedding = service.encode("Hello, world!");

        assert!(embedding.is_ok());
        let embedding = embedding.unwrap();
        assert_eq!(embedding.len(), 384);
    }

    #[test]
    #[ignore] // Ignore by default as it downloads models
    fn test_encode_batch() {
        let service = EmbeddingService::new(EmbeddingModel::AllMiniLML6v2, Some(32)).unwrap();
        let texts = vec![
            "Hello, world!".to_string(),
            "Rust is awesome".to_string(),
            "VectaDB for LLM observability".to_string(),
        ];

        let embeddings = service.encode_batch(&texts);
        assert!(embeddings.is_ok());

        let embeddings = embeddings.unwrap();
        assert_eq!(embeddings.len(), 3);
        assert_eq!(embeddings[0].len(), 384);
        assert_eq!(embeddings[1].len(), 384);
        assert_eq!(embeddings[2].len(), 384);
    }

    #[test]
    #[ignore] // Ignore by default as it downloads models
    fn test_cosine_similarity() {
        let service = EmbeddingService::new(EmbeddingModel::AllMiniLML6v2, Some(32)).unwrap();

        let embedding1 = service.encode("The cat sat on the mat").unwrap();
        let embedding2 = service.encode("A cat was sitting on a mat").unwrap();
        let embedding3 = service.encode("The weather is sunny today").unwrap();

        let sim_12 = service.cosine_similarity(&embedding1, &embedding2).unwrap();
        let sim_13 = service.cosine_similarity(&embedding1, &embedding3).unwrap();

        // Similar sentences should have higher similarity
        assert!(sim_12 > sim_13);
        assert!(sim_12 > 0.8); // Very similar sentences
        assert!(sim_13 < 0.5); // Different topics
    }

    #[test]
    fn test_cosine_similarity_dimension_mismatch() {
        let service = EmbeddingService::new(EmbeddingModel::AllMiniLML6v2, Some(32)).unwrap();

        let a = vec![1.0; 384];
        let b = vec![1.0; 128];

        let result = service.cosine_similarity(&a, &b);
        assert!(result.is_err());
    }

    #[test]
    #[ignore] // Ignore by default as it downloads models
    fn test_empty_batch() {
        let service = EmbeddingService::new(EmbeddingModel::AllMiniLML6v2, Some(32)).unwrap();
        let embeddings = service.encode_batch(&[]);

        assert!(embeddings.is_ok());
        assert_eq!(embeddings.unwrap().len(), 0);
    }
}
