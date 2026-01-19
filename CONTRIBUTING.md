# Contributing to VectaDB

Thanks for your interest in contributing to **VectaDB**.

VectaDB is an open-source, early-stage project focused on building an **audit-first meta database** for AI applications by unifying:
- vector embeddings (semantic similarity),
- graph structures (provenance and lineage),
- and ontologies (typing and constraints).

This repository is intended to support experimentation, research, and practical engineering for auditable AI systems.

---

## Ways to Contribute

Contributions are welcome in many forms:

- Reporting bugs
- Suggesting features
- Improving documentation
- Adding tests
- Implementing roadmap items
- Proposing ontology modules and schemas
- Building integrations with agent/RAG frameworks

If you’re unsure where to start, open an Issue and describe what you want to do.

---

## Issues Are Welcome

**Issues are always welcome**, including:

- bug reports
- feature requests
- architectural questions
- performance concerns
- documentation gaps
- ontology/model design proposals

When opening an Issue, please include:

- what you expected vs what happened
- logs or error messages (if applicable)
- relevant environment info (OS, Python/Rust version, Docker, etc.)
- reproducible steps (if possible)

---

## Technical Discussions via Issues

VectaDB uses **GitHub Issues as the primary channel for technical discussions**.

This keeps design decisions traceable and allows the project to evolve with clarity.

Please avoid starting architecture discussions in PR threads or external chats unless the outcome is summarized in an Issue.

---

## Pull Requests: Keep Them Small

**PRs must be small and focused.**

Why:
- The project is evolving quickly
- Small PRs are easier to review and merge
- Large PRs tend to stall or require major redesigns

A good PR should ideally do one of the following:

- fix one bug
- add one feature behind a clear boundary
- improve one subsystem (docs/tests/validation)
- implement a single roadmap item

If you have a larger change in mind:
1. Open an Issue first and explain the design.
2. Break the work into smaller PRs.

---

## Contribution Workflow

1. Fork the repository
2. Create a feature branch

```bash
git checkout -b feature/my-change
```

3. Make changes with clear commits
4. Add tests when applicable
5. Update docs when behavior changes
6. Open a Pull Request with:
   - what it changes
   - why it matters
   - how to test it

---

## Coding and Style Expectations

General guidelines:

- Prefer clarity over cleverness
- Keep PR scope minimal
- Follow existing patterns in the repo
- Add comments only when needed to explain non-obvious behavior

If you introduce new modules or concepts, include:
- a short README section or doc update
- and a minimal test or validation scenario

---

## Ontology, Schema, and Provenance Contributions

VectaDB is ontology-native by design and treats AI traces as a first-class graph of auditable entities and relations.

Contributions in this area are especially welcome, including:

- entity/edge design proposals
- SHACL-inspired constraint rules
- PROV-aligned provenance relationships
- domain-specific audit schemas (finance, healthcare, legal)

If proposing schema changes:
- open an Issue first
- describe what problem it solves
- include example trace objects and relationships

---

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).  
By participating, you agree to uphold that standard.

---

## License

By contributing, you agree that your contributions will be licensed under the **Apache License 2.0**.
