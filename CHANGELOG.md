# Changelog

All notable changes to this project are documented in this file.

## [v1.0.6] — 2026-10-26

### Security
- Closed FRE-141 (false positive): audited `scripts/install.sh` `validate_notion_token` — the `Authorization: Bearer $token` header is wired correctly; the "Bearer ***" literal reported by the watch agent was terminal-output redaction of its own logs, not the script source.
- Added regression test `test_validate_notion_token_sends_token_parameter` (tests/test_install_guard.py) asserting the installed script interpolates `$token` into the Bearer header, guarding against future restore/regression.

## [v1.0.5] — 2026-10-14

### Security
- Centralized authorization and containment verification for mutable Notion operations (`store.verify_page_in_database`, `store.update_page`, `store.get_page`, `store.delete_page`) (FRE-11.3 / FRE-16 / API-02)
- Added IDOR defense across `notion_brain_task`, `notion_brain_content`, and `notion_brain_research` update/publish/archive tools, rejecting operations on unverified, cross-database, or parent pages
- Fail-closed security posture: any retrieval failure, parent mismatch, or missing container denies authorization with secret-redacted error messages
- Added `update` action support to `notion_brain_research` tool and schema with containment enforcement
- Added comprehensive IDOR regression test suite (`tests/regressions/test_authorization_idor.py`)

## [v1.0.4] — 2026-10-14

### Fixed

- `provider` tool-error path and unknown-tool handling now redact secrets
  before JSON serialization across all direct tool branches (FRE-11.1 / FRE-13)
- `provider` success-path payloads now pass through recursive `_redact_payload()`
  at the JSON serialization boundary — secrets inside tuples, `extra` dicts, and
  nested lists/dicts are redacted (replaces the fragile `startswith` heuristic) (FRE-13)
- **Search never used server-side title filter** (FRE-17 / FRE-11.4): `query_filter`
  was undefined (referenced before assignment after a prior revert).  Server-side
  filter removed entirely — Notion's `title.contains` is case-sensitive and a
  `rich_text` filter on a title property is rejected.  All search now goes
  through the single case-insensitive client-side title refinement path.
- **Deterministic behavior across database/all-databases modes**: both paths
  now call `query_database(..., filter_obj=None)` and apply the query
  client-side after merging disk-only entries; `max_results` caps the final
  result set in both modes.
- **Pagination documentation**: `query_database` docstring now clarifies that
  `page_size` is a per-request batch size, not a cap — pagination continues
  until `has_more` is false.

### Tests added (5 regressions)

- `test_database_filtered_search_matches_case_insensitively` — query case
  variation does not change result set; asserts no server-side filter sent.
- `test_database_filtered_search_empty_query_returns_all_rows` — empty string
  query returns every row, not none.
- `test_all_databases_search_applies_same_query_semantics` — both modes return
  the same matched results for a given query.
- `test_search_limit_applies_after_query_refinement` — `max_results` caps
  matched rows, not raw DB rows.
- `test_database_filtered_search_max_results_capped_at_20` — caller-supplied
  `max_results` above 20 is clamped.
- Expanded regression coverage for secret redaction across all direct tool
  branches, direct error returns, and nested payloads (FRE-13)

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
