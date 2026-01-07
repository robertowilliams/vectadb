# VectaDB Development Guide

**Version**: 0.1.0
**Last Updated**: January 7, 2026

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Project Structure](#project-structure)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Testing](#testing)
6. [Contributing](#contributing)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

- **Rust**: 1.75 or later
- **Docker & Docker Compose**: For database services
- **Git**: For version control
- **IDE**: VS Code with rust-analyzer recommended

### Initial Setup

```bash
# Clone repository
git clone https://github.com/robertowilliams/vectadb.git
cd vectadb/vectadb

# Install Rust dependencies
cargo fetch

# Start databases
cd ..
docker-compose up -d

# Run tests to verify setup
cd vectadb
cargo test
```

### IDE Setup (VS Code)

Install recommended extensions:
- `rust-lang.rust-analyzer` - Rust language support
- `vadimcn.vscode-lldb` - Debugging support
- `serayuzgur.crates` - Cargo.toml management
- `tamasfe.even-better-toml` - TOML syntax highlighting

#### VS Code Settings

Create `.vscode/settings.json`:
```json
{
  "rust-analyzer.checkOnSave.command": "clippy",
  "rust-analyzer.cargo.features": "all",
  "editor.formatOnSave": true,
  "[rust]": {
    "editor.defaultFormatter": "rust-lang.rust-analyzer"
  }
}
```

---

## Project Structure

```
vectadb/
├── Cargo.toml              # Dependencies and metadata
├── Cargo.lock              # Locked dependency versions
├── src/
│   ├── main.rs             # Application entry point
│   ├── lib.rs              # Library root
│   ├── config.rs           # Configuration management
│   ├── error.rs            # Error types
│   ├── api/                # REST API layer
│   │   ├── mod.rs
│   │   ├── routes.rs       # Route definitions
│   │   ├── handlers.rs     # Request handlers
│   │   └── types.rs        # API request/response types
│   ├── db/                 # Database clients
│   │   ├── mod.rs
│   │   ├── surrealdb_client.rs  # Graph database
│   │   ├── qdrant_client.rs     # Vector database
│   │   └── types.rs        # Database types
│   ├── embeddings/         # Embedding services
│   │   ├── mod.rs
│   │   ├── service.rs      # Local embedding service
│   │   ├── manager.rs      # Embedding manager
│   │   ├── plugin.rs       # Plugin trait
│   │   └── plugins/        # Provider implementations
│   ├── intelligence/       # Reasoning engine
│   │   └── ontology_reasoner.rs
│   ├── models/             # Data models
│   │   ├── agent.rs
│   │   ├── task.rs
│   │   ├── log.rs
│   │   └── ...
│   ├── ontology/           # Ontology system
│   │   ├── schema.rs       # Schema management
│   │   ├── validator.rs    # Validation logic
│   │   ├── entity_type.rs
│   │   └── relation_type.rs
│   └── query/              # Query coordination
│       ├── coordinator.rs
│       └── types.rs
├── tests/                  # Integration tests
│   ├── api_tests.rs
│   └── voyage_test.rs
├── examples/               # Example programs
│   └── embedding_plugins.rs
├── config/                 # Configuration files
│   └── vectadb.example.toml
└── docs/                   # Documentation
    ├── API.md
    ├── TESTING.md
    ├── DEPLOYMENT.md
    └── DEVELOPMENT.md
```

---

## Development Workflow

### 1. Branch Strategy

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Create bugfix branch
git checkout -b fix/bug-description
```

### 2. Making Changes

```bash
# Make your changes
edit src/...

# Format code
cargo fmt

# Run clippy
cargo clippy --all-targets -- -D warnings

# Run tests
cargo test

# Build
cargo build
```

### 3. Commit Messages

Follow conventional commits:
```
feat: add hybrid query endpoint
fix: resolve database connection timeout
docs: update API documentation
test: add tests for ontology validation
refactor: improve error handling
```

### 4. Pull Request Process

1. Ensure all tests pass
2. Update documentation if needed
3. Add changelog entry if applicable
4. Create PR with clear description
5. Wait for review

---

## Coding Standards

### Rust Style Guide

Follow the official [Rust Style Guide](https://doc.rust-lang.org/1.0.0/style/):

- Use `cargo fmt` for formatting
- Use `cargo clippy` for linting
- Maximum line length: 100 characters
- Use snake_case for variables and functions
- Use PascalCase for types and traits

### Code Organization

```rust
// 1. Imports (grouped by: std, external crates, internal modules)
use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use crate::error::Result;

// 2. Type definitions
pub struct MyStruct {
    field: String,
}

// 3. Implementation blocks
impl MyStruct {
    pub fn new(field: String) -> Self {
        Self { field }
    }
}

// 4. Tests (at bottom of file)
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_my_struct() {
        // Test code
    }
}
```

### Error Handling

```rust
// Use anyhow::Result for functions
use anyhow::{Context, Result};

pub fn my_function() -> Result<String> {
    let value = some_operation()
        .context("Failed to perform operation")?;

    Ok(value)
}

// Custom errors for public APIs
#[derive(Debug, thiserror::Error)]
pub enum MyError {
    #[error("Not found: {0}")]
    NotFound(String),

    #[error("Validation failed: {0}")]
    ValidationError(String),
}
```

### Documentation

```rust
/// Brief description of the function.
///
/// More detailed explanation if needed, including:
/// - What the function does
/// - Important parameters
/// - Return value meaning
/// - Possible errors
///
/// # Examples
///
/// ```
/// use vectadb::MyStruct;
///
/// let instance = MyStruct::new("value".to_string());
/// assert_eq!(instance.field, "value");
/// ```
///
/// # Errors
///
/// Returns error if:
/// - Parameter is empty
/// - Database connection fails
pub fn documented_function(param: String) -> Result<MyStruct> {
    // Implementation
}
```

---

## Testing

### Running Tests

```bash
# All tests
cargo test

# Specific test
cargo test test_name

# With output
cargo test -- --nocapture

# Integration tests only
cargo test --test '*'

# Unit tests only
cargo test --lib
```

### Writing Tests

See [TESTING.md](./TESTING.md) for detailed testing guide.

**Quick Reference**:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_function_name() {
        // Arrange
        let input = setup();

        // Act
        let result = function_under_test(input);

        // Assert
        assert_eq!(result, expected);
    }

    #[tokio::test]
    async fn test_async_function() {
        let result = async_function().await;
        assert!(result.is_ok());
    }
}
```

---

## Contributing

### First Time Contributors

1. **Find an Issue**: Look for issues labeled `good first issue`
2. **Ask Questions**: Comment on the issue if you need clarification
3. **Fork & Clone**: Fork the repo and clone your fork
4. **Make Changes**: Create a branch and make your changes
5. **Test**: Ensure all tests pass
6. **Submit PR**: Create a pull request

### Code Review Process

All PRs require:
- ✅ All tests passing
- ✅ Code formatted with `cargo fmt`
- ✅ No clippy warnings
- ✅ Documentation updated
- ✅ At least one approving review

### Communication

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and general discussion
- **Pull Requests**: Code contributions

---

## Common Development Tasks

### Adding a New API Endpoint

1. **Define route** in `src/api/routes.rs`:
```rust
.route("/api/v1/my-endpoint", post(handlers::my_handler))
```

2. **Implement handler** in `src/api/handlers.rs`:
```rust
pub async fn my_handler(
    State(state): State<AppState>,
    Json(payload): Json<MyRequest>,
) -> Result<Json<MyResponse>, StatusCode> {
    // Implementation
}
```

3. **Add types** in `src/api/types.rs`:
```rust
#[derive(Debug, Serialize, Deserialize)]
pub struct MyRequest {
    pub field: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct MyResponse {
    pub result: String,
}
```

4. **Add tests** in `tests/api_tests.rs`:
```rust
#[tokio::test]
async fn test_my_endpoint() {
    // Test implementation
}
```

5. **Update documentation** in `docs/API.md`

### Adding a New Database Model

1. **Create model** in `src/models/my_model.rs`:
```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MyModel {
    pub id: String,
    pub field: String,
}
```

2. **Add database methods** in appropriate client

3. **Add tests**:
```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_my_model_creation() {
        let model = MyModel::new("test".to_string());
        assert!(model.id.len() > 0);
    }
}
```

### Adding an Embedding Plugin

1. **Create plugin** in `src/embeddings/plugins/my_plugin.rs`:
```rust
use async_trait::async_trait;
use crate::embeddings::plugin::{EmbeddingPlugin, PluginConfig};

pub struct MyPlugin {
    // Configuration
}

#[async_trait]
impl EmbeddingPlugin for MyPlugin {
    // Implement required methods
}
```

2. **Register plugin** in `src/embeddings/manager.rs`

3. **Add tests**

4. **Update documentation**

---

## Debugging

### Enable Debug Logging

```bash
# Set log level
export RUST_LOG=debug

# Run with logging
cargo run
```

### Use Rust Debugger

**VS Code** (with CodeLLDB extension):

Create `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "lldb",
      "request": "launch",
      "name": "Debug VectaDB",
      "cargo": {
        "args": ["build", "--bin=vectadb"]
      },
      "args": [],
      "cwd": "${workspaceFolder}/vectadb"
    }
  ]
}
```

### Common Debug Techniques

```rust
// Print debugging
dbg!(&my_variable);

// Conditional compilation
#[cfg(debug_assertions)]
println!("Debug info: {:?}", data);

// Pretty printing
eprintln!("{:#?}", complex_struct);
```

---

## Troubleshooting

### Build Errors

**Error**: `linking with cc failed`
```bash
# macOS
xcode-select --install

# Linux
sudo apt-get install build-essential
```

**Error**: `could not find OpenSSL`
```bash
# macOS
brew install openssl
export OPENSSL_DIR=$(brew --prefix openssl)

# Linux
sudo apt-get install libssl-dev pkg-config
```

### Test Failures

```bash
# Clean and rebuild
cargo clean
cargo build

# Update dependencies
cargo update

# Check Docker services
docker-compose ps
docker-compose logs
```

### Performance Issues

```bash
# Build with optimizations
cargo build --release

# Profile with flamegraph
cargo install flamegraph
cargo flamegraph --bin vectadb
```

---

## Useful Commands

```bash
# Check code
cargo check                    # Fast compile check
cargo clippy                   # Linter
cargo fmt                      # Format code

# Build
cargo build                    # Debug build
cargo build --release          # Optimized build

# Test
cargo test                     # All tests
cargo test --lib              # Unit tests only
cargo test --doc              # Documentation tests

# Documentation
cargo doc --open               # Generate and open docs
cargo doc --no-deps           # Without dependencies

# Dependencies
cargo tree                     # Show dependency tree
cargo outdated                 # Check for updates
cargo audit                    # Security audit

# Clean
cargo clean                    # Remove build artifacts
```

---

## Best Practices

### Performance

- ✅ Use `&str` over `String` when possible
- ✅ Clone only when necessary
- ✅ Use iterators instead of loops
- ✅ Prefer `Arc` over `Mutex` when read-heavy
- ✅ Use `tokio::spawn` for concurrent tasks

### Security

- ✅ Validate all user input
- ✅ Use prepared statements for database queries
- ✅ Sanitize error messages (no sensitive data)
- ✅ Keep dependencies updated
- ✅ Run `cargo audit` regularly

### Code Quality

- ✅ Write tests for new features
- ✅ Document public APIs
- ✅ Handle errors explicitly
- ✅ Use meaningful variable names
- ✅ Keep functions small and focused

---

## Related Documentation

- [Testing Guide](./TESTING.md)
- [API Documentation](./API.md)
- [Deployment Guide](./DEPLOYMENT.md)

---

**Questions or Issues?**
File an issue at: https://github.com/robertowilliams/vectadb/issues
