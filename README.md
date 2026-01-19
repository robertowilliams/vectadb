# VectaDB 
## Early Stage Project

**An Ontology-Native Vector and Graph Database for Auditable AI Systems**


[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub Stars](https://img.shields.io/github/stars/robertowilliams/VectaDB?style=social)](https://github.com/robertowilliams/VectaDB)

---

## Overview

VectaDB is an open-source meta database system that unifies **vector embeddings**, **graph structures**, and **typed ontologies** to provide audit-first infrastructure for AI applications. Designed specifically for modern LLM-based systems and agentic workflows, VectaDB enables teams to trace, explain, and audit AI behavior with evidence-centric queries and semantic investigations.
Meta database system: acting as an abstraction and provenance layer over vector and graph stores

### Why VectaDB?

Large language models and autonomous agents are increasingly deployed in high-stakes workflows requiring accountability and transparency. Traditional logging falls short when you need to:

- **Reconstruct decision chains**: Trace every step in an agent run as queryable, linked events
- **Track evidence sources**: Identify which documents, memories, or tool outputs influenced an answer
- **Investigate incidents semantically**: Find prior similar cases using vector similarity
- **Ensure compliance**: Validate that traces contain required fields and align with policies
- **Enable reproducibility**: Store versioned prompts, retrieval parameters, and tool interactions

VectaDB addresses these needs by combining three paradigms in a single substrate: vector search for semantic similarity, graph structure for explicit relationships and provenance, and ontologies for typing, constraints, and interpretability.

---

## Key Features

###  **Hybrid Retrieval (initial support)**
- Vector similarity search for semantic queries
- Graph traversal for multi-hop relationship analysis
- Metadata filtering and structured queries
- Reciprocal Rank Fusion (RRF) for hybrid ranking

###  **Audit-First Architecture (core primitives)**
- Provenance tracking for all AI artifacts (prompts, retrievals, tool calls, outputs)
- Evidence traceability with typed relationships
- Semantic incident response via similarity search
- Schema validation and policy alignment

###  **Ontology-Native Data Model (foundational)**
- Typed entities and relationships based on RDF/OWL principles
- Constraint validation using SHACL-inspired patterns
- First-class support for W3C PROV provenance standard
- Extensible schemas for domain-specific requirements

###  **Roadmap for Modern AI Stacks **
- Native integration with RAG (Retrieval-Augmented Generation) pipelines
- Memory systems for conversational and agentic applications
- Tool-use tracking and decision lineage
- Panned compatibility with LangChain, LangSmith, and observability frameworks

---

## Architecture

VectaDB's current implementation leverages:

- **[SurrealDB](https://surrealdb.com/)**: Multi-model database for graph and document storage
- **[Qdrant](https://qdrant.tech/)**: High-performance vector search with HNSW indexing
- **Hybrid Query Engine**: Combines symbolic traversal and semantic similarity

```
┌─────────────────────────────────────────────────┐
│              Application Layer                  │
│   (RAG Pipelines, Agents, Observability)        │
└─────────────────────────────────────────────────┘
                      │
┌─────────────────────────────────────────────────┐
│              VectaDB API Layer                  │
│  • Ingestion API  • Query API  • Audit API      │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼────────┐         ┌────────▼────────┐
│   SurrealDB    │         │     Qdrant      │
│  (Graph Store) │◄────────►│ (Vector Store)  │
│   Ontologies   │         │   Embeddings    │
└────────────────┘         └─────────────────┘
```

This architecture prioritizes decoupling semantic similarity from provenance and constraints, allowing each subsystem to evolve independently.

---

## Installation

### Prerequisites

- Python 3.9 or higher
- Docker and Docker Compose (for local deployment)
- Node.js 16+ (optional, for frontend tools)

### Quick Start for infrastructure with Docker

```bash
# Clone the repository
git clone https://github.com/robertowilliams/VectaDB.git
cd VectaDB

# Start services with Docker Compose
docker-compose up -d

# Verify services are running
docker-compose ps
```

---

## Use Cases

###  **Healthcare AI Systems**
- Track clinical decision support evidence chains
- Audit model predictions against patient data sources
- Ensure HIPAA compliance with provenance trails
- Retrieve similar diagnostic cases for review

###  **Financial Services**
- Document loan approval decision factors
- Trace trading algorithm reasoning paths
- Support regulatory audit requirements
- Detect and analyze algorithmic bias patterns

###  **Legal AI Applications**
- Record document retrieval for legal reasoning
- Audit case law citations and precedents
- Validate compliance with evidentiary standards
- Reproduce attorney-client interaction traces

###  **Industrial Automation**
- Log autonomous agent decision chains
- Track safety-critical command sequences
- Maintain detailed operational audit trails
- Analyze incident patterns with semantic search

---

## Documentation

Comprehensive documentation is available in the `/docs` folder:

- **[Getting Started Guide](docs/getting-started.md)**: Installation and basic usage
- **[Data Model Reference](docs/data-model.md)**: Ontology and schema details
- **[API Documentation](docs/api-reference.md)**: Complete API reference
- **[Integration Guides](docs/integrations/)**: RAG, agents, and observability
- **[Deployment Guide](docs/deployment.md)**: Production deployment patterns
- **[Contributing Guidelines](CONTRIBUTING.md)**: How to contribute

---

## Roadmap

### Current Status (v0.1.0)
- ✅ Core ontology and data model
- ✅ SurrealDB + Qdrant integration
- ✅ Basic ingestion and query APIs
- ✅ Provenance tracking primitives
- ✅ Python client library

### Upcoming Features
- 🔄 LangChain and LangSmith integration
- 🔄 OpenTelemetry trace ingestion
- 🔄 Web-based audit dashboard
- 🔄 Advanced SHACL constraint validation
- 🔄 RDF/OWL export for semantic-web stacks
- 🔄 Automated policy compliance checking

### Future Exploration
- Multi-tenant isolation and access controls
- Federated query across distributed deployments
- Real-time anomaly detection on trace patterns
- Integration with model monitoring platforms (MLflow, Weights & Biases)

---

## Academic Paper

The current implementation represents an evolving, partial realization of the concepts described in the paper.

VectaDB is described in detail in the accompanying academic paper:

**VectaDB: An Ontology-Native Vector and Graph Database for Auditable AI Systems**  
*Roberto Williams Batista*  
Independent Researcher

The paper covers:
- Audit-first design principles for AI systems
- Ontology-native data model specifications
- Hybrid retrieval and graph traversal algorithms
- Case studies in healthcare, finance, and industrial domains

📄 **[Read the full paper](docs/VectaDB_Paper.pdf)**

### Citation

If you use VectaDB in your research or application, please cite:

```bibtex
@article{batista2025vectordb,
  title={VectaDB: An Ontology-Native Vector and Graph Database for Auditable AI Systems},
  author={Batista, Roberto Williams},
  year={2025},
  note={Open-source project, Apache License 2.0},
  url={https://github.com/robertowilliams/VectaDB}
}
```

---

## Contributing

We welcome contributions from the community! VectaDB aims to become the standard infrastructure for auditable AI systems.

### How to Contribute

1. **Fork the repository** and create a feature branch
2. **Write tests** for new functionality
3. **Follow code style guidelines** (see `.editorconfig`)
4. **Submit a pull request** with a clear description

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Areas for Contribution

- 🐛 Bug reports and fixes
- 📝 Documentation improvements
- 🧪 Test coverage expansion
- 🔌 Integration with AI frameworks (CrewAI, AutoGen, etc.)
- 🎨 UI/UX for audit dashboard
- 📊 Benchmark development and optimization

---

## Community and Support

- **GitHub Discussions**: Ask questions and share ideas
- **Issue Tracker**: Report bugs and request features
- **Discord**: Join our community (coming soon)
- **Email**: robertowilliams@gmail.com

---

## License

VectaDB is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE) for details.

```
Copyright 2025 Roberto Williams Batista

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

## Acknowledgments

VectaDB builds upon excellent open-source projects:
- [SurrealDB](https://surrealdb.com/) - Multi-model database platform
- [Qdrant](https://qdrant.tech/) - Vector similarity search engine
- [LangChain](https://langchain.com/) - LLM application framework
- [Apache Jena](https://jena.apache.org/) - Semantic web framework

Special thanks to the broader AI safety and observability communities for inspiring this work.

---

## Related Projects

- **[mem0ai/mem0](https://github.com/mem0ai/mem0)**: Memory layer for AI agents
- **[topoteretes/cognee](https://github.com/topoteretes/cognee)**: Memory system with knowledge graphs
- **[Neo4j Vector Indexes](https://neo4j.com/docs/)**: Graph database with vector search
- **[LangSmith](https://docs.smith.langchain.com/)**: LLM observability platform

---

**Star this repository** if you find VectaDB useful! ⭐

**Questions?** Open an issue or start a discussion. We're here to help build more accountable AI systems together.
