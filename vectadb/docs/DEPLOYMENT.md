# VectaDB Deployment Guide

**Version**: 0.1.0
**Last Updated**: January 7, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Local Development Setup](#local-development-setup)
4. [Docker Deployment](#docker-deployment)
5. [Production Deployment](#production-deployment)
6. [Configuration](#configuration)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)
9. [Backup and Recovery](#backup-and-recovery)

---

## Overview

VectaDB can be deployed in several configurations:
- **Local Development**: For testing and development
- **Docker Compose**: Multi-container deployment
- **Production**: Scalable production environment

---

## System Requirements

### Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8+ GB |
| Disk | 10 GB | 50+ GB SSD |
| OS | macOS, Linux, Windows | Linux (Ubuntu 22.04+) |

### Software Dependencies

- **Rust**: 1.75 or later
- **Docker**: 20.10+ and Docker Compose 2.0+
- **Git**: For source code management

---

## Local Development Setup

### 1. Install Rust

```bash
# Install Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Verify installation
rustc --version
cargo --version
```

### 2. Clone Repository

```bash
git clone https://github.com/robertowilliams/vectadb.git
cd vectadb
```

### 3. Start Database Services

```bash
# Start SurrealDB and Qdrant
docker-compose up -d

# Verify services are running
docker-compose ps
```

Expected output:
```
NAME                  IMAGE                         STATUS
vectadb-surrealdb     surrealdb/surrealdb:v2.3.10   Up
vectadb-qdrant        qdrant/qdrant:latest          Up
```

### 4. Build VectaDB

```bash
cd vectadb

# Development build
cargo build

# Production build (optimized)
cargo build --release
```

### 5. Configure Environment

```bash
# Copy example configuration
cp config/vectadb.example.toml config/vectadb.toml

# Edit configuration
nano config/vectadb.toml
```

### 6. Run VectaDB

```bash
# Development mode
cargo run

# Production mode
cargo run --release
```

The API will be available at `http://localhost:8080`

---

## Docker Deployment

### Using Docker Compose (Recommended)

#### Step 1: Prepare Configuration

```bash
# Create docker-compose.override.yml for custom settings
cat > docker-compose.override.yml <<EOF
version: '3.8'
services:
  surrealdb:
    environment:
      - SURREAL_LOG=debug  # Optional: change log level

  qdrant:
    environment:
      - QDRANT__LOG_LEVEL=INFO
EOF
```

#### Step 2: Start All Services

```bash
# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Step 3: Verify Deployment

```bash
# Check health
curl http://localhost:8080/health

# Expected response
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| VectaDB API | 8080 | REST API |
| SurrealDB | 8000 | Database (HTTP) |
| Qdrant HTTP | 6333 | Vector search (HTTP) |
| Qdrant gRPC | 6334 | Vector search (gRPC) |

---

## Production Deployment

### Architecture Overview

```
┌─────────────────────────────────────────────┐
│          Load Balancer (nginx)              │
│               Port 443 (HTTPS)              │
└─────────────────┬───────────────────────────┘
                  │
       ┌──────────┴──────────┐
       │                     │
┌──────▼──────┐      ┌──────▼──────┐
│ VectaDB #1  │      │ VectaDB #2  │
│  (Port 8080)│      │  (Port 8080)│
└──────┬──────┘      └──────┬──────┘
       │                     │
       └──────────┬──────────┘
                  │
       ┌──────────┴──────────┐
       │                     │
┌──────▼──────┐      ┌──────▼──────┐
│ SurrealDB   │      │   Qdrant    │
│  (Cluster)  │      │  (Cluster)  │
└─────────────┘      └─────────────┘
```

### Prerequisites

- Linux server (Ubuntu 22.04 recommended)
- Domain name with DNS configured
- SSL certificate (Let's Encrypt recommended)
- Firewall configured

### Step 1: System Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y build-essential pkg-config libssl-dev \
  docker.io docker-compose nginx certbot python3-certbot-nginx

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Step 2: Install Rust

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

### Step 3: Deploy Application

```bash
# Clone repository
git clone https://github.com/robertowilliams/vectadb.git
cd vectadb

# Build release version
cd vectadb
cargo build --release

# Create systemd service
sudo nano /etc/systemd/system/vectadb.service
```

```ini
[Unit]
Description=VectaDB API Server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=vectadb
WorkingDirectory=/opt/vectadb
ExecStart=/opt/vectadb/target/release/vectadb
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable vectadb
sudo systemctl start vectadb

# Check status
sudo systemctl status vectadb
```

### Step 4: Configure Nginx

```bash
sudo nano /etc/nginx/sites-available/vectadb
```

```nginx
upstream vectadb {
    server localhost:8080;
    # Add more instances for load balancing
    # server localhost:8081;
}

server {
    listen 80;
    server_name vectadb.yourdomain.com;

    location / {
        proxy_pass http://vectadb;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint (don't log)
    location /health {
        access_log off;
        proxy_pass http://vectadb;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/vectadb /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 5: SSL Certificate

```bash
# Get SSL certificate
sudo certbot --nginx -d vectadb.yourdomain.com

# Auto-renewal is configured automatically
# Test renewal
sudo certbot renew --dry-run
```

### Step 6: Firewall Configuration

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Block direct access to services
sudo ufw deny 8080/tcp  # VectaDB
sudo ufw deny 8000/tcp  # SurrealDB
sudo ufw deny 6333/tcp  # Qdrant HTTP
sudo ufw deny 6334/tcp  # Qdrant gRPC

# Enable firewall
sudo ufw enable
```

---

## Configuration

### Environment Variables

```bash
# Database Configuration
export SURREAL_URL="http://localhost:8000"
export SURREAL_USER="root"
export SURREAL_PASS="root"
export SURREAL_NAMESPACE="vectadb"
export SURREAL_DATABASE="production"

# Qdrant Configuration
export QDRANT_URL="http://localhost:6333"
export QDRANT_API_KEY=""  # Optional
export QDRANT_COLLECTION_PREFIX="vectadb_"

# API Configuration
export API_HOST="0.0.0.0"
export API_PORT="8080"
export RUST_LOG="info,vectadb=debug"
```

### Configuration File

Edit `config/vectadb.toml`:

```toml
[server]
host = "0.0.0.0"
port = 8080

[database.surrealdb]
url = "http://localhost:8000"
namespace = "vectadb"
database = "production"
username = "root"
password = "root"

[database.qdrant]
url = "http://localhost:6333"
collection_prefix = "vectadb_"

[embeddings]
model = "local"  # or "openai", "cohere", etc.
model_path = "BAAI/bge-small-en-v1.5"
dimension = 384

[logging]
level = "info"
format = "json"  # or "pretty"
```

---

## Monitoring

### Health Checks

```bash
# API Health
curl http://localhost:8080/health

# SurrealDB Health
curl http://localhost:8000/health

# Qdrant Health
curl http://localhost:6333/healthz
```

### Logs

```bash
# VectaDB logs
journalctl -u vectadb -f

# Docker logs
docker-compose logs -f

# Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Metrics (Planned)

Prometheus metrics available at `/metrics`:
- Request count
- Response times
- Error rates
- Database connection pool status
- Embedding generation times

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u vectadb -n 50

# Check ports
sudo netstat -tulpn | grep -E '8080|8000|6333'

# Verify dependencies
docker-compose ps
```

### Database Connection Issues

```bash
# Test SurrealDB
curl -X POST http://localhost:8000/sql \
  -H "Content-Type: application/json" \
  -u root:root \
  -d '{"query": "INFO FOR DB;"}'

# Test Qdrant
curl http://localhost:6333/collections
```

### High Memory Usage

```bash
# Check memory usage
docker stats

# Restart services
docker-compose restart

# Limit memory in docker-compose.yml
services:
  surrealdb:
    mem_limit: 2g
  qdrant:
    mem_limit: 2g
```

### Performance Issues

1. **Check database indexes**:
   - Ensure entities are indexed
   - Verify vector collections are optimized

2. **Monitor resource usage**:
   ```bash
   htop  # or top
   docker stats
   ```

3. **Optimize configuration**:
   - Increase connection pool size
   - Adjust Qdrant HNSW parameters
   - Enable SurrealDB caching

---

## Backup and Recovery

### Database Backups

#### SurrealDB

```bash
# Export database
docker exec vectadb-surrealdb /surreal export \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace vectadb --database production \
  /data/backup.surql

# Copy backup from container
docker cp vectadb-surrealdb:/data/backup.surql ./backup.surql
```

#### Qdrant

```bash
# Create snapshot
curl -X POST http://localhost:6333/collections/{collection_name}/snapshots

# Download snapshot
curl http://localhost:6333/collections/{collection_name}/snapshots/{snapshot_name} \
  -o snapshot.tar
```

### Restore from Backup

#### SurrealDB

```bash
# Copy backup to container
docker cp ./backup.surql vectadb-surrealdb:/data/backup.surql

# Import database
docker exec vectadb-surrealdb /surreal import \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace vectadb --database production \
  /data/backup.surql
```

#### Qdrant

```bash
# Upload and restore snapshot
curl -X PUT "http://localhost:6333/collections/{collection_name}/snapshots/upload" \
  -H "Content-Type:application/octet-stream" \
  --data-binary @snapshot.tar
```

### Automated Backups

```bash
# Create backup script
cat > /opt/vectadb/backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/opt/vectadb/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# SurrealDB backup
docker exec vectadb-surrealdb /surreal export \
  --endpoint http://localhost:8000 \
  --username root --password root \
  --namespace vectadb --database production \
  /data/backup_${DATE}.surql

docker cp vectadb-surrealdb:/data/backup_${DATE}.surql \
  ${BACKUP_DIR}/surrealdb_${DATE}.surql

# Cleanup old backups (keep last 7 days)
find ${BACKUP_DIR} -name "*.surql" -mtime +7 -delete
EOF

chmod +x /opt/vectadb/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /opt/vectadb/backup.sh
```

---

## Scaling

### Horizontal Scaling

Deploy multiple VectaDB instances behind a load balancer:

```yaml
# docker-compose.scale.yml
services:
  vectadb-1:
    build: ./vectadb
    ports:
      - "8080:8080"

  vectadb-2:
    build: ./vectadb
    ports:
      - "8081:8080"

  nginx:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
```

### Database Clustering

- **SurrealDB**: Use TiKV backend for distributed storage
- **Qdrant**: Configure distributed deployment with sharding

---

## Security Checklist

- [ ] Enable SSL/TLS (HTTPS)
- [ ] Configure firewall
- [ ] Use strong database passwords
- [ ] Enable API authentication
- [ ] Regular security updates
- [ ] Monitor access logs
- [ ] Implement rate limiting
- [ ] Backup encryption
- [ ] Network isolation (VPC)
- [ ] Secret management (Vault, AWS Secrets Manager)

---

## Related Documentation

- [Testing Guide](./TESTING.md)
- [API Documentation](./API.md)
- [Development Guide](./DEVELOPMENT.md)

---

**Questions or Issues?**
File an issue at: https://github.com/robertowilliams/vectadb/issues
