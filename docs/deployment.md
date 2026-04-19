# Deployment Guide

## Options

| Model | When to Use | Effort |
|---|---|---|
| Docker Compose (dev) | Development, testing | Low |
| Docker Compose (server) | Single-server up to ~100K agents | Medium |
| Kubernetes | High availability, multi-server | High |

## Docker Compose — Development

```yaml
version: '3.8'

services:
  surrealdb:
    image: surrealdb/surrealdb:v2.3.10
    container_name: vectadb-surrealdb
    user: "0:0"
    ports:
      - "8000:8000"
    command: start --log info --user root --pass root --bind 0.0.0.0:8000 file:///data/vectadb.db
    volumes:
      - surrealdb_data:/data
    networks:
      - vectadb-network

  qdrant:
    image: qdrant/qdrant:latest
    container_name: vectadb-qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
    networks:
      - vectadb-network

volumes:
  surrealdb_data:
  qdrant_data:

networks:
  vectadb-network:
    driver: bridge
```

```bash
docker-compose up -d      # Start
docker-compose ps         # Verify
docker-compose down       # Stop (preserve data)
docker-compose down -v    # Stop + delete data
```

## Docker Compose — Production

Add a `.env` file (never commit this):
```
SURREAL_USER=vectadb_admin
SURREAL_PASS=<strong-random-password>
VECTADB_API_KEY=<strong-random-api-key>
```

Key changes for production:
- Use `surrealkv://` storage (not deprecated `file://`)
- Set `--log warn` instead of `--log info`
- Add `restart: unless-stopped` to all services
- Mount qdrant config for auth

## Kubernetes — Resource Allocations

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---|---|---|---|---|
| VectaDB API | 500m | 2000m | 512Mi | 2Gi |
| SurrealDB | 1000m | 4000m | 2Gi | 8Gi |
| Qdrant | 1000m | 4000m | 4Gi | 16Gi |

## Production Checklist

**Security**

- [ ] Change all default passwords
- [ ] Enable TLS on external endpoints
- [ ] Restrict SurrealDB and Qdrant to internal network only
- [ ] Rotate API keys on schedule
- [ ] Enable Qdrant API key authentication

**Storage**

- [ ] Use `surrealkv://` storage engine
- [ ] Configure persistent volumes with backup policies
- [ ] Set RocksDB cache size appropriate to RAM

**Monitoring**

- [ ] Enable Prometheus metrics export
- [ ] Set up Grafana dashboards
- [ ] Configure alerting for error rate and latency

## Capacity Planning

| Metric | Small (<10K agents) | Medium (10K–100K) | Large (>100K) |
|---|---|---|---|
| SurrealDB storage | 10–50 GB | 50–500 GB | 500 GB+ |
| Qdrant storage | 5–20 GB | 20–200 GB | 200 GB+ |
| VectaDB instances | 1 | 2–3 | 5+ |

## Backup

```bash
# SurrealDB
surreal export --conn http://localhost:8000 \
  --user root --pass $SURREAL_PASS \
  --ns vectadb --db production \
  backup_$(date +%Y%m%d).surql

# Qdrant snapshot
curl -X POST "http://localhost:6333/collections/agents/snapshots"
```
