# Changelog

All notable changes to this project are documented in this file.

## [v1.0.3] — 2026-09-01

### Fixed (audit wave 1 — 9 findings)
- `provider` title filter `rich_text` → `title` — database-filtered search was silently returning 0 rows
- `extract` LLM buffer now `redact_secrets(compact(...,4000))` before POST — prevents secret exfiltration
- `scripts/install.sh` `Bearer ***` → `Bearer $token` — token validation was dead code
- Ruff/mypy green: removed 3 unused imports/vars, fixed `extract` payload typing, fixed `tests/test_coverage_gaps` append misuse
- `tests/test_provider.test_api_key_env` isolation via `patch(_load_env_file)` — was flaky with host `~/.hermes/.env`
- `provider` tags/entities now `_coerce_str_list` — bare-string from LLM no longer explodes into chars
- `bootstrap` cache write atomic (`tmp → replace`) + `chmod 600` — was truncatable `644`
- `store` 429 now honors `Retry-After` (capped 60s) — was fixed 1s backoff
- `provider` page-ownership guard on `task update/complete` + `content update/publish/archive` — prevents cross-DB writes via guessed page_id

### Changed
- Audit deliverable `CODEBASE-AUDIT-REPORT.md` — full 2026-09-01 deep audit (P1×2, P2×6, P3×1)

## [v1.0.2] — 2026-08-15

### Added
- `hermes-brain` console command (`python -m notion_brain` exposed as a pip entry point) — `reset`, `url`, and `health` subcommands are now available immediately after `pip install hermes-brain`.
- `notion_brain.__version__` attribute — verify your install with `import notion_brain; notion_brain.__version__`.

### Fixed
- Version mismatch between `pyproject.toml` (1.0.0), `plugin.yaml` (1.0.0), and `CHANGELOG.md` (v1.0.1) — all three now report 1.0.2.

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
