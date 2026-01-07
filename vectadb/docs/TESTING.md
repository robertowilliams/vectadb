# VectaDB Testing Guide

**Version**: 0.1.0
**Last Updated**: January 7, 2026

---

## Overview

VectaDB has a comprehensive test suite covering unit tests, integration tests, and examples. This guide explains how to run tests, write new tests, and understand test coverage.

## Test Structure

```
vectadb/
├── src/                    # Source files with inline unit tests
│   ├── api/               # API handlers (2 tests)
│   ├── db/                # Database clients (6 tests)
│   ├── embeddings/        # Embedding services (17 tests)
│   ├── intelligence/      # Reasoning engine (8 tests)
│   ├── models/            # Data models (10 tests)
│   ├── ontology/          # Ontology system (19 tests)
│   └── query/             # Query coordination (4 tests)
├── tests/                 # Integration tests
│   ├── api_tests.rs      # API endpoint tests (7 tests)
│   └── voyage_test.rs    # Voyage plugin tests (2 tests)
└── examples/              # Runnable examples
    └── embedding_plugins.rs
```

## Current Test Coverage

| Component | Unit Tests | Integration Tests | Total |
|-----------|-----------|-------------------|-------|
| API Handlers | 2 | 7 | 9 |
| Database Clients | 6 | 0 | 6 |
| Embeddings | 17 | 2 | 19 |
| Intelligence | 8 | 0 | 8 |
| Data Models | 10 | 0 | 10 |
| Ontology System | 19 | 0 | 19 |
| Query Coordination | 4 | 0 | 4 |
| **Total** | **66** | **9** | **75** |

---

## Running Tests

### All Tests

```bash
cargo test
```

### Unit Tests Only

```bash
cargo test --lib
```

### Integration Tests Only

```bash
cargo test --test '*'
```

### Specific Test

```bash
cargo test test_name
```

### With Output

```bash
cargo test -- --nocapture
```

### Ignored Tests (Require Services)

Some tests are marked with `#[ignore]` because they require external services:

```bash
# Run all tests including ignored ones
cargo test -- --ignored --include-ignored
```

---

## Test Categories

### 1. Unit Tests

**Location**: Inline with source code using `#[cfg(test)]` modules

**Purpose**: Test individual functions and methods in isolation

**Example**:
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_entity_type_creation() {
        let entity_type = EntityType::new(
            "Person".to_string(),
            "A human person".to_string()
        );
        assert_eq!(entity_type.id, "Person");
    }
}
```

### 2. Integration Tests

**Location**: `tests/` directory

**Purpose**: Test interactions between components and external services

**Running Integration Tests**:
```bash
# Requires Docker services running
docker-compose up -d
cargo test --test api_tests
```

### 3. Ignored Tests

Tests marked `#[ignore]` require:
- External API keys (OpenAI, Voyage, etc.)
- Running database services
- Network connectivity

**Example**:
```rust
#[tokio::test]
#[ignore] // Requires Qdrant running
async fn test_connection() {
    // Test code
}
```

---

## Writing Tests

### Unit Test Template

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_function_name() {
        // Arrange
        let input = setup_test_data();

        // Act
        let result = function_under_test(input);

        // Assert
        assert_eq!(result, expected_value);
    }

    #[test]
    #[should_panic(expected = "error message")]
    fn test_error_case() {
        // Test that should panic
    }
}
```

### Async Test Template

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_async_function() {
        let result = async_function().await;
        assert!(result.is_ok());
    }
}
```

### Integration Test Template

```rust
// tests/my_integration_test.rs
use vectadb::*;

#[tokio::test]
async fn test_end_to_end_workflow() {
    // Setup
    let config = test_config();
    let client = Client::new(&config).await.unwrap();

    // Test workflow
    let result = client.perform_operation().await;

    // Verify
    assert!(result.is_ok());
}
```

---

## Test Requirements

### Prerequisites

1. **Rust Toolchain**: 1.75+
2. **Docker**: For database services
3. **Environment Variables**: Optional API keys for external services

### Starting Test Services

```bash
# Start required databases
docker-compose up -d

# Verify services are running
docker-compose ps

# Check logs if needed
docker logs vectadb-surrealdb
docker logs vectadb-qdrant
```

### Environment Variables for External Tests

Create `.env` file (optional, for external API tests):

```bash
OPENAI_API_KEY=your_key_here
VOYAGE_API_KEY=your_key_here
COHERE_API_KEY=your_key_here
HUGGINGFACE_API_KEY=your_key_here
```

---

## Test Best Practices

### 1. Test Naming

- Use descriptive names: `test_entity_creation_with_valid_data`
- Follow pattern: `test_<what>_<condition>_<expected_result>`

### 2. Test Organization

- Group related tests in the same module
- One assertion per test when possible
- Use helper functions to reduce duplication

### 3. Test Data

- Use realistic but minimal test data
- Create helper functions for common test fixtures
- Clean up test data after tests (esp. in integration tests)

### 4. Async Testing

- Use `#[tokio::test]` for async tests
- Always `.await` async calls
- Handle timeouts appropriately

### 5. Error Testing

- Test both success and failure paths
- Use `assert!(result.is_err())` for error cases
- Test specific error types when relevant

---

## Common Test Patterns

### Testing Database Operations

```rust
#[tokio::test]
#[ignore] // Requires running database
async fn test_database_operation() {
    let config = test_config();
    let client = DatabaseClient::new(&config).await.unwrap();

    // Insert test data
    let entity = create_test_entity();
    client.store(&entity).await.unwrap();

    // Verify retrieval
    let retrieved = client.get(&entity.id).await.unwrap();
    assert_eq!(retrieved.id, entity.id);

    // Cleanup
    client.delete(&entity.id).await.ok();
}
```

### Testing API Endpoints

```rust
#[tokio::test]
async fn test_health_endpoint() {
    let response = reqwest::get("http://localhost:8080/health")
        .await
        .unwrap();

    assert_eq!(response.status(), 200);
    let body: HealthResponse = response.json().await.unwrap();
    assert_eq!(body.status, "healthy");
}
```

### Testing Embeddings

```rust
#[test]
fn test_embedding_generation() {
    let service = EmbeddingService::new_local().unwrap();
    let text = "test sentence";

    let embedding = service.encode(text).unwrap();

    assert_eq!(embedding.len(), 384); // BGE Small dimension
    assert!(embedding.iter().all(|&x| x.is_finite()));
}
```

---

## Continuous Integration

### GitHub Actions (Planned)

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions-rs/toolchain@v1
      - run: docker-compose up -d
      - run: cargo test --lib
      - run: cargo test --test '*'
```

---

## Coverage Analysis

### Using Tarpaulin (Optional)

```bash
# Install tarpaulin
cargo install cargo-tarpaulin

# Generate coverage report
cargo tarpaulin --out Html --output-dir coverage/
```

---

## Troubleshooting

### Tests Fail with "Connection Refused"

**Solution**: Start Docker services
```bash
docker-compose up -d
sleep 5  # Wait for services to be ready
cargo test
```

### Tests Hang or Timeout

**Cause**: Database services not responding

**Solution**: Check service health
```bash
docker-compose ps
docker logs vectadb-surrealdb
docker logs vectadb-qdrant
```

### Ignored Tests Won't Run

**Solution**: Include ignored tests explicitly
```bash
cargo test -- --ignored --include-ignored
```

### Embedding Tests Fail

**Cause**: Model files not downloaded

**Solution**: Run once to download models
```rust
let _ = EmbeddingService::new_local();  // Downloads on first run
```

---

## Test Metrics

### Current Status (January 7, 2026)

- ✅ **64 unit tests** passing
- ✅ **7 integration tests** passing
- ✅ **10 tests** ignored (require external services)
- ✅ **0 failures**
- ✅ **100% pass rate** on available tests

### Coverage Goals

| Component | Current | Target |
|-----------|---------|--------|
| Core Logic | ~80% | 90% |
| API Handlers | ~60% | 85% |
| Database | ~40% | 70% |
| Models | ~70% | 90% |

---

## Contributing Tests

When adding new features:

1. ✅ Add unit tests for new functions
2. ✅ Add integration tests for new APIs
3. ✅ Update this guide if adding new test patterns
4. ✅ Ensure `cargo test` passes before committing

---

## Related Documentation

- [API Documentation](./API.md)
- [Development Guide](./DEVELOPMENT.md)
- [Deployment Guide](./DEPLOYMENT.md)

---

**Questions or Issues?**
File an issue at: https://github.com/robertowilliams/vectadb/issues
