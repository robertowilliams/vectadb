# Installing Rust for VectaDB Development

## 1. Install Rust Toolchain

Run this command in your terminal:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

When prompted:
- Select option `1` (default installation)
- This will install `rustc`, `cargo`, and `rustup`

## 2. Configure Your Shell

Add Rust to your PATH:

```bash
source $HOME/.cargo/env
```

Or add this line to your `~/.zshrc` or `~/.bashrc`:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

## 3. Verify Installation

```bash
rustc --version
cargo --version
```

You should see output like:
```
rustc 1.75.0 (or newer)
cargo 1.75.0 (or newer)
```

## 4. Install Additional Tools (Recommended)

```bash
# Rust formatter
rustup component add rustfmt

# Rust linter
rustup component add clippy

# Rust language server (for IDE support)
rustup component add rust-analyzer
```

## 5. Create VectaDB Project

```bash
cd /Users/roberto/Documents/VECTADB
cargo new vectadb --name vectadb
cd vectadb
```

## 6. Verify Project

```bash
cargo build
cargo run
```

You should see:
```
   Compiling vectadb v0.1.0
    Finished dev [unoptimized + debuginfo] target(s) in 0.5s
     Running `target/debug/vectadb`
Hello, world!
```

## 7. Set Up Docker (for databases)

Make sure Docker is installed and running, then:

```bash
cd /Users/roberto/Documents/VECTADB
# Create docker-compose.yml first (see MVP_IMPLEMENTATION_PLAN.md)
docker-compose up -d
```

## Next Steps

After Rust is installed:
1. Review `MVP_IMPLEMENTATION_PLAN.md`
2. Follow Phase 1: Foundation
3. Start implementing data models in `src/models/`

---

**Need help?** Run these commands and share the output:
```bash
rustc --version
cargo --version
echo $PATH | grep cargo
```
