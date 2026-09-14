# Backends

hermes-brain writes your agent's long-term memory into a structured workspace. **Today there is exactly one backend — Notion — and it is free to use.**

If you want a different storage backend (Obsidian, SQLite, Logseq, local Markdown vault, etc.) you have two paths:

1. **Roll your own.** See [`BACKEND_SWAP_GUIDE.md`](BACKEND_SWAP_GUIDE.md). The `MemoryProvider` interface is documented, and a custom backend is a few hundred lines.
2. **Sponsor the project.** Sponsorships pay for the time to build, test, and document additional backends. When a second backend exists, it will live in this repository and the README will list it. There is no separate paid package today, so do not look for one.

## Why the wait

Other backends need a real implementation, not a demo:

- **Obsidian** — must handle local file writes, YAML frontmatter, links, and graph metadata without corrupting the user's vault.
- **SQLite** — FTS search, schema migrations, concurrency-safe writes, backup guidance.
- **Logseq** — block-format quirks and graph conventions.
- **Markdown vault** — consistent naming, frontmatter parsing, cross-platform path handling.

Backends are not added until someone has the bandwidth to maintain them properly. Until then, the channel for requesting one is an issue.

## What is not happening (yet)

- No `hermes-brain-backends` companion package exists. There is nothing to buy.
- No commercial license terms are attached to this repository. See `LICENSE`.
- No Stripe, Gumroad, or other payment integration is configured.
