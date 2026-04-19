# Getting Started

## Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| Docker | 20.10+ | Run SurrealDB and Qdrant containers |
| Docker Compose | 2.x | Orchestrate the infrastructure stack |
| Rust | 1.75+ | Build and run the VectaDB API server |
| Git | Any | Clone the repository |
| Python | 3.9+ | Run test ingestion scripts |
| Node.js | 16+ | Optional — UI dashboard only |

**Available ports required:** `3000` (VectaDB), `6333`, `6334` (Qdrant), `8000` (SurrealDB)

## Step 1: Clone the Repository

```bash
git clone https://github.com/robertowilliams/VectaDB.git
cd VectaDB
```

## Step 2: Start Infrastructure Services

```bash
docker-compose up -d
docker-compose ps
```

Test connectivity:

```bash
curl -s http://localhost:8000/health   # SurrealDB
curl -s http://localhost:6333/         # Qdrant
```

## Step 3: Build and Run the VectaDB API

```bash
cd vectadb
cargo build --release
cargo run --release
```

!!! note "First build time"
    The initial `cargo build --release` downloads and compiles all dependencies. This typically takes **5–10 minutes**. Subsequent builds are incremental and much faster.

**Expected startup:**
```
🚀 VectaDB server listening on 0.0.0.0:3000
✅ Connected to SurrealDB at ws://localhost:8000
✅ Connected to Qdrant at http://localhost:6333
```

Verify:
```bash
curl http://localhost:3000/health
```

## Step 4: Run the Quick Test Suite

```bash
cd test
./ingest_as_graph.sh     # Ingest 27 Bedrock log entries
./verify_databases.sh    # Verify data in both databases
./test_graph.sh          # Test graph operations
```

Expected output from ingestion:
```
✅ VectaDB is healthy
Processing 27 log entries...
✅ Created 17 nodes and 15 edges
✅ Embeddings generated automatically
```

## Step 5: Try Your First Queries

```bash
# List all agents
curl http://localhost:3000/agents

# Semantic search
curl -X POST http://localhost:3000/agents/search \
  -H "Content-Type: application/json" \
  -d '{"query": "researcher analyzing data", "threshold": 0.8, "limit": 5}'

# Get execution trace
curl http://localhost:3000/agents/{agent_id}/trace
```

## Optional: UI Dashboard

```bash
cd vectadb-ui
npm install
npm run dev
```

Open `http://localhost:5173`.

## Port Reference

| Service | Port | Protocol |
|---|---|---|
| VectaDB API | 3000 | HTTP/WebSocket |
| SurrealDB | 8000 | HTTP/WebSocket |
| Qdrant HTTP | 6333 | HTTP |
| Qdrant gRPC | 6334 | gRPC |
| VectaDB UI | 5173 | HTTP |

## Troubleshooting

**Port already in use:**
```bash
lsof -i :3000  # Find what's using the port
```

**Docker services not reachable:**
```bash
docker-compose ps
docker-compose logs surrealdb
docker-compose logs qdrant
```

**Clean rebuild:**
```bash
cd vectadb
cargo clean && cargo build --release
```

**Stop all services:**
```bash
docker-compose down       # Preserve data
docker-compose down -v    # Delete all data (full reset)
```
