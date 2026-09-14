# Changelog

All notable changes to this project are documented in this file.

## [v1.0.1] — 2026-08-05

### Added
- "First 5 Minutes" quickstart section in README — guided walkthrough to first memory in under 5 minutes.
- `docs/troubleshooting.md` — 6 common failure modes with fixes.
- `examples/` directory with `quickstart.py` and `migrate_memory.py`.
- `SECURITY.md` — security policy and reporting channel.
- `docs/architecture.md` — system design and data flow.

### Changed
- README restructured to surface quickstart before detailed installation.

### Fixed
- Quoted secret redaction regex false negatives.
- API key leakage via direct tool calls.
- Bootstrap schema mismatch recovery.
- CI workflow updated with stricter linting and test coverage gates.

## [v1.0.0] — 2026-07-25

### Added
- Initial release: 7 structured Notion databases (Memory, Tasks, Projects, Content, Research, Career, Entities).
- Heuristic auto-capture using regex keyword patterns.
- 5 tool interfaces: `search`, `remember`, `task`, `content`, `research`.
- Background sync daemon thread.
- Secret redaction for Stripe, Notion, GitHub, Slack tokens.
- Prefetch context loading.
- Session summaries.
- Disk import for `MEMORY.md` and `USER.md`.
- Idempotent bootstrap.
- Cross-platform Linux support (Ubuntu, Debian, Fedora, RHEL).
