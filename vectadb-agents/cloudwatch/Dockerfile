# Multi-stage build for VectaDB CloudWatch Agent

# Stage 1: Builder
FROM rust:1.75-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y pkg-config libssl-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy manifests
COPY Cargo.toml Cargo.lock* ./

# Copy source code
COPY src ./src

# Build release binary
RUN cargo build --release

# Stage 2: Runtime
FROM debian:bookworm-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y ca-certificates libssl3 && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 agent && \
    chown -R agent:agent /app

# Copy binary from builder
COPY --from=builder /build/target/release/vectadb-cloudwatch-agent /app/vectadb-cloudwatch-agent

# Switch to non-root user
USER agent

# Health check (checks if process is running)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD pgrep -f vectadb-cloudwatch-agent || exit 1

# Run agent
ENTRYPOINT ["/app/vectadb-cloudwatch-agent"]
