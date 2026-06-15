<div align="center">
<img sizes="50%" src='./dragon-lychee-50.png'><br>
<i>image generated via Gemini.</i>
</div>

# Lychee AI Vision — Developer Documentation

Welcome to the developer documentation for **Lychee AI Vision**, the facial recognition microservice for [Lychee](https://github.com/LycheeOrg/Lychee).
This folder covers the internal workings of the service: its architecture, API design, data flows, and operational considerations. It is intended for contributors and operators who want to understand or extend the service.

Key folders at the root level of the repository:

```
./
├── app/        # FastAPI application — routes, detection, embeddings, clustering, matching, queue
├── data/       # Runtime data directory (embeddings DB, photos mount — gitignored)
├── docs/       # Developer documentation (this folder)
│   ├── 0-overview/      # Project overview and goals
│   ├── 1-concepts/      # Conceptual explanations (embeddings, clustering, matching)
│   ├── 2-how-to/        # Practical how-to guides
│   ├── 3-reference/     # Technical reference (API, config, env vars)
│   ├── 4-architecture/  # Architecture decisions and designs
│   ├── Contribute.md    # Contribution guide
│   └── openapi.json     # OpenAPI schema
├── tests/      # Pytest test suite
├── Dockerfile
├── Makefile
└── pyproject.toml
```


## Documentation Structure

Documentation is organized following the [Diátaxis framework](https://diataxis.fr/) in the `docs/` directory:

- **[0-overview](specs/0-overview/)** - High-level project documentation
- **[1-concepts](specs/1-concepts/)** - Conceptual explanations (domain model, photos, albums, permissions)
- **[2-how-to](specs/2-how-to/)** - Practical how-to guides
- **[3-reference](specs/3-reference/)** - Technical reference documentation
- **[4-architecture](specs/4-architecture/)** - Architecture decisions and designs

### Contributing
- [Contribution Guide](Contribute.md) - How to contribute to Lychee
- [Coding Conventions](3-reference/coding-conventions.md) - PHP and Vue3 coding standards
- [AI/Claude Guidelines](Contribute.md#using-aiclaude-for-contributions) - Guidelines for AI-assisted development
- [AGENTS.md](../AGENTS.md) - Instructions for AI agents working on this codebase

## Additional Resources

For more information about Lychee:
- [Main Repository](https://github.com/LycheeOrg/Lychee)
- [Official Website](https://lycheeorg.dev/)
- [Admin Documentation](https://lycheeorg.dev/docs/)

---

*Last updated: January 21, 2026*