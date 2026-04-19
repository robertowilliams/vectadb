# QA & Testing

## Test Coverage

**Total:** 75 tests — 66 unit tests, 9 integration tests

## Running Tests

```bash
# Unit tests (no Docker required)
cd vectadb
cargo test --lib

# All tests (Docker must be running)
docker-compose up -d
cargo test
```

### Test Binaries

```bash
cd test
./ingest_as_graph.sh          # Ingest 27 Bedrock log entries as graph
./verify_databases.sh         # Verify SurrealDB + Qdrant data
./test_graph.sh               # Test graph operations

cargo run --release --bin bedrock_test
cargo run --release --bin database_verification
cargo run --release --bin graph_database_test
cargo run --release --bin bedrock_graph_ingestion
```

## Test Scenarios

### Quick Start

| Step | Command | Expected |
|---|---|---|
| Clone | `git clone .../VectaDB.git` | Clones successfully |
| Start | `docker-compose up -d` | 2 services running |
| Verify | `docker-compose ps` | Both show "Up" |
| SurrealDB | `curl localhost:8000/health` | Health response |
| Qdrant | `curl localhost:6333/` | API response |

### Build & Run

| Step | Command | Expected |
|---|---|---|
| Build | `cargo build --release` | No errors |
| Run | `cargo run --release` | Server on port 3000 |
| Health | `curl localhost:3000/health` | JSON response |

### Ingestion Test

Expected output from `./ingest_as_graph.sh`:
```
✅ VectaDB is healthy
Processing 27 log entries...
✅ Created 17 nodes and 15 edges
✅ Embeddings generated automatically
```

## Known Issues

!!! warning "Critical"
    The following are known gaps that will affect first-time users:

    - `/docs/getting-started.md` referenced in README but missing
    - `/docs/data-model.md` referenced in README but missing
    - `/docs/api-reference.md` referenced in README but missing
    - Port inconsistency: some docs say 8080, server runs on 3000
    - VectaDB API is commented out in `docker-compose.yml`

## Recommendations

**Fix README links** — Update to point to existing files.

**Standardize port** — All documentation should reference port 3000.

**Complete Docker setup** — Create a `Dockerfile` and uncomment the VectaDB service in `docker-compose.yml`.

**Add build time warning** — First `cargo build --release` takes 5–10 minutes.

## Quick Reference

```bash
# Infrastructure
docker-compose up -d && docker-compose ps

# Build + run
cd vectadb && cargo build --release && cargo run --release

# Tests
cargo test --lib      # Unit only
cargo test            # All

# Scenarios
cd test
./ingest_as_graph.sh && ./verify_databases.sh && ./test_graph.sh

# Health checks
curl http://localhost:3000/health
curl http://localhost:8000/health
curl http://localhost:6333/
```
