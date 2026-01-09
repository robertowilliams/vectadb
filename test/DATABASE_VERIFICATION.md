# Database Verification Test

This test verifies that data has been properly ingested into both **SurrealDB** (graph database) and **Qdrant** (vector database) by directly querying each database system.

## Purpose

The database verification test is a critical system functionality test that:

1. **Verifies SurrealDB Health & Data**
   - Checks database connectivity
   - Queries entity table for stored records
   - Queries relation table for graph connections
   - Counts records by type
   - Validates data structure

2. **Verifies Qdrant Health & Data**
   - Checks vector database connectivity
   - Lists all collections
   - Retrieves collection statistics (point counts, vector dimensions)
   - Validates vector storage
   - Tests vector similarity search

3. **Validates System Integration**
   - Confirms both databases are properly connected
   - Verifies data consistency
   - Tests end-to-end data flow

## Architecture

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  VectaDB    │─────▶│  SurrealDB  │      │   Qdrant    │
│  (API)      │      │  (Graph DB) │      │ (Vector DB) │
└─────────────┘      └─────────────┘      └─────────────┘
                            ▲                     ▲
                            │                     │
                            └─────────┬───────────┘
                                      │
                              ┌───────▼────────┐
                              │  Verification  │
                              │      Test      │
                              └────────────────┘
```

The verification test bypasses VectaDB's API and directly queries both databases to ensure data was actually persisted.

## Prerequisites

### Database Services Must Be Running

1. **SurrealDB** (default: `http://localhost:8000`)
2. **Qdrant** (default: `http://localhost:6333`)

### Starting the Databases

If using Docker:

```bash
# SurrealDB
docker run -d --name surrealdb \
  -p 8000:8000 \
  surrealdb/surrealdb:latest \
  start --log trace --user root --pass root memory

# Qdrant
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  qdrant/qdrant:latest
```

Or start VectaDB which includes both:

```bash
cd vectadb
cargo run --release
```

## Running the Verification Test

### Quick Start

```bash
./verify_databases.sh
```

### Manual Execution

```bash
cargo run --release --bin database_verification
```

### Custom Database URLs

```bash
SURREALDB_URL=http://custom-host:8000 \
QDRANT_URL=http://custom-host:6333 \
  ./verify_databases.sh
```

## Expected Output

### With No Data

```
╔════════════════════════════════════════╗
║  DATABASE VERIFICATION TEST SUITE     ║
╚════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SURREALDB VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Checking SurrealDB health...
   ✅ SurrealDB is healthy

🔍 Gathering SurrealDB statistics...
📊 Querying SurrealDB table: entity
   ⚠️  No records found in entity
📊 Querying SurrealDB table: relation
   ⚠️  No records found in relation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QDRANT VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Checking Qdrant health...
   ✅ Qdrant is healthy

🔍 Gathering Qdrant statistics...
📊 Listing Qdrant collections...
   ⚠️  No collections found

╔════════════════════════════════════════╗
║     VERIFICATION REPORT SUMMARY       ║
╚════════════════════════════════════════╝

📊 SURREALDB STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Status: ✅ HEALTHY

   Entities:  0

   Relations: 0

📊 QDRANT STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Status: ✅ HEALTHY

   Collections: 0
   Total Vectors: 0

📊 VECTOR SEARCH TEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Status: ⚠️  NOT TESTED (no data or unavailable)

╔════════════════════════════════════════╗
║         OVERALL STATUS                ║
╚════════════════════════════════════════╝

   ✅ ALL SYSTEMS OPERATIONAL
   ⚠️  NO DATA FOUND - Run bedrock_test first to ingest data
```

### With Data Ingested

```
╔════════════════════════════════════════╗
║  DATABASE VERIFICATION TEST SUITE     ║
╚════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SURREALDB VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Checking SurrealDB health...
   ✅ SurrealDB is healthy

🔍 Gathering SurrealDB statistics...
📊 Querying SurrealDB table: entity
   ✅ Found 45 records in entity
📊 Querying SurrealDB table: relation
   ✅ Found 12 records in relation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QDRANT VERIFICATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Checking Qdrant health...
   ✅ Qdrant is healthy

🔍 Gathering Qdrant statistics...
📊 Listing Qdrant collections...
   ✅ Found 3 collections
      - vectadb_log
      - vectadb_agent
      - vectadb_task

📊 Getting info for collection: vectadb_log
   ✅ Points: 45, Vectors: 45, Dimension: 384

📊 Getting info for collection: vectadb_agent
   ✅ Points: 3, Vectors: 3, Dimension: 384

📊 Getting info for collection: vectadb_task
   ✅ Points: 8, Vectors: 8, Dimension: 384

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VECTOR SEARCH TEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 Searching collection: vectadb_log
   ✅ Vector search successful
      1. ID: log_abc123 (score: 0.8234)
      2. ID: log_def456 (score: 0.7891)
      3. ID: log_ghi789 (score: 0.7456)

╔════════════════════════════════════════╗
║     VERIFICATION REPORT SUMMARY       ║
╚════════════════════════════════════════╝

📊 SURREALDB STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Status: ✅ HEALTHY

   Entities:  45
      - log: 38
      - agent: 3
      - task: 4

   Relations: 12
      - belongs_to: 8
      - triggers: 4

📊 QDRANT STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Status: ✅ HEALTHY

   Collections: 3
   Total Vectors: 56

   Collection Details:
      - vectadb_log
        Points: 45
        Vectors: 45
        Dimension: 384
        Distance: Cosine

      - vectadb_agent
        Points: 3
        Vectors: 3
        Dimension: 384
        Distance: Cosine

      - vectadb_task
        Points: 8
        Vectors: 8
        Dimension: 384
        Distance: Cosine

📊 VECTOR SEARCH TEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Status: ✅ PASSED
   Results Found: 5

╔════════════════════════════════════════╗
║         OVERALL STATUS                ║
╚════════════════════════════════════════╝

   ✅ ALL SYSTEMS OPERATIONAL
   ✅ DATA SUCCESSFULLY INGESTED
```

## What The Test Validates

### SurrealDB Checks

1. **Connectivity**: Can connect to SurrealDB HTTP endpoint
2. **Authentication**: Can authenticate with root credentials
3. **Entity Storage**: Records exist in the `entity` table
4. **Relation Storage**: Records exist in the `relation` table
5. **Data Structure**: Records have expected fields (entity_type, properties, etc.)
6. **Type Distribution**: Count of entities by type

### Qdrant Checks

1. **Connectivity**: Can connect to Qdrant HTTP endpoint
2. **Collection Creation**: Collections exist with proper naming
3. **Vector Storage**: Points/vectors are stored in collections
4. **Vector Dimensions**: Vector size matches configuration (typically 384 for embeddings)
5. **Distance Metric**: Collections use correct distance metric (Cosine)
6. **Search Functionality**: Can perform similarity searches and retrieve results

## Integration with Bedrock Test

The database verification test is designed to work with the Bedrock log test:

```bash
# 1. First, ingest data using bedrock test
./run_test.sh

# 2. Then verify the data was stored
./verify_databases.sh
```

## Troubleshooting

### SurrealDB Connection Failed

**Error**: `❌ SurrealDB connection failed`

**Solutions**:
1. Check if SurrealDB is running: `curl http://localhost:8000/health`
2. Verify port 8000 is not blocked
3. Check SurrealDB logs for errors
4. Try custom URL: `SURREALDB_URL=http://different-host:8000 ./verify_databases.sh`

### Qdrant Connection Failed

**Error**: `❌ Qdrant connection failed`

**Solutions**:
1. Check if Qdrant is running: `curl http://localhost:6333/healthz`
2. Verify port 6333 is not blocked
3. Check Qdrant logs for errors
4. Try custom URL: `QDRANT_URL=http://different-host:6333 ./verify_databases.sh`

### No Data Found

**Message**: `⚠️  NO DATA FOUND - Run bedrock_test first to ingest data`

This is expected if you haven't run the bedrock test yet. Run:

```bash
./run_test.sh
```

Then run the verification again.

### Query Failed Errors

**Error**: `❌ Query failed with status 400`

This might indicate:
1. Wrong namespace/database combination
2. Missing tables (not initialized)
3. Permission issues
4. SurrealDB version incompatibility

**Solution**: Restart SurrealDB and VectaDB to reinitialize the schema.

## Exit Codes

- `0`: All systems healthy and operational
- `1`: One or more systems unhealthy or verification failed

## API Reference

### Direct Database Queries

The test performs direct HTTP queries to both databases:

#### SurrealDB Query

```bash
curl -X POST http://localhost:8000/sql \
  -H "Accept: application/json" \
  -H "Authorization: Basic $(echo -n 'root:root' | base64)" \
  -H "NS: vectadb" \
  -H "DB: main" \
  -d '{"query": "SELECT * FROM entity"}'
```

#### Qdrant Collections List

```bash
curl http://localhost:6333/collections
```

#### Qdrant Collection Info

```bash
curl http://localhost:6333/collections/vectadb_log
```

#### Qdrant Vector Search

```bash
curl -X POST http://localhost:6333/collections/vectadb_log/points/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, ...],
    "limit": 5,
    "with_payload": true
  }'
```

## Use Cases

1. **CI/CD Integration**: Run after data ingestion to verify success
2. **Health Monitoring**: Periodic checks of database status
3. **Debugging**: Diagnose data storage issues
4. **Performance Testing**: Measure query response times
5. **Data Validation**: Ensure data integrity after migrations

## Implementation Details

The test is implemented in pure Rust with minimal dependencies:

- **reqwest**: HTTP client for API calls
- **serde_json**: JSON parsing
- **tokio**: Async runtime
- **base64**: Authentication encoding
- **rand**: Random test vector generation

No VectaDB dependencies are used to ensure independent validation.

## Future Enhancements

Potential additions:
- [ ] Data consistency checks (SurrealDB entity count == Qdrant point count)
- [ ] Schema validation (verify entity structure matches ontology)
- [ ] Performance benchmarks (query latency measurements)
- [ ] Detailed error reporting with recovery suggestions
- [ ] Support for authentication (API keys, tokens)
- [ ] Export verification report to JSON/CSV

## Related Documentation

- [README.md](README.md) - Overall test suite documentation
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide
- [bedrock_test.rs](bedrock_test.rs) - Data ingestion test source
- [database_verification.rs](database_verification.rs) - Verification test source
