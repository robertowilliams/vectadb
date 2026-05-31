# Changelog

All notable changes to VectaDB will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-alpha] - 2025-05-31

### Added
- Core ontology and data model based on RDF/OWL principles
- SurrealDB integration for graph and document storage
- Qdrant integration for high-performance vector search with HNSW indexing
- Hybrid query engine combining vector similarity and graph traversal
- Reciprocal Rank Fusion (RRF) for hybrid ranking
- Basic ingestion API for AI artifacts (prompts, retrievals, tool calls, outputs)
- Basic query API with metadata filtering and structured queries
- Audit API with provenance tracking primitives
- Evidence traceability with typed relationships
- W3C PROV provenance standard support
- SHACL-inspired constraint validation patterns
- Python client library
- Docker Compose setup for local deployment
- CloudWatch agent integration (vectadb-agents/cloudwatch)
- Vue-based UI scaffold (vectadb-ui)
- Bedrock schema definitions

### Architecture
- Decoupled vector store (Qdrant) and graph/document store (SurrealDB)
- Multi-model query engine supporting symbolic traversal and semantic similarity
- Extensible ontology schemas for domain-specific requirements

---

## Upcoming

### [0.2.0] - Planned
- LangChain and LangSmith integration
- OpenTelemetry trace ingestion
- Web-based audit dashboard
- Advanced SHACL constraint validation
- RDF/OWL export for semantic-web stacks
- Automated policy compliance checking

### [0.3.0] - Planned
- Multi-tenant isolation and access controls
- Federated query across distributed deployments
- Real-time anomaly detection on trace patterns
- Integration with model monitoring platforms (MLflow, Weights & Biases)
- CrewAI and AutoGen integration

---

> **Note:** VectaDB is in early-stage development. APIs may change significantly before v1.0. No backwards compatibility guarantees until a stable release is announced.
