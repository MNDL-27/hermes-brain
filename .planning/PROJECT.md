# hermes-brain

## What This Is

hermes-brain replaces local flat markdown memory files (`MEMORY.md` / `USER.md`) with a structured, multi-database Notion workspace under a single **Hermes Brain** parent page. Instead of an agent forgetting decisions or cluttering a single text file across long sessions, context is classified into dedicated databases with typed properties, status tracking, confidence scoring, and tag indexing for the Hermes AI agent ecosystem.

## Core Value

Persistent, structured long-term memory for Hermes agents across 7 Notion databases with strict secret redaction and zero-overhead non-blocking writes.

## Requirements

### Validated

- ✓ Seven structured Notion databases (`Memory`, `Tasks`, `Projects`, `Content`, `Research`, `Career`, `Entities`) — existing
- ✓ Heuristic & optional local LLM turn classification and extraction (`notion_brain/extract.py`) — existing
- ✓ 5 core Hermes tool schemas (`notion_brain_search`, `notion_brain_remember`, `notion_brain_task`, `notion_brain_content`, `notion_brain_research`) — existing
- ✓ Non-blocking background sync worker with thread-safe queue and graceful shutdown — existing
- ✓ Strict secret redaction for API keys, tokens, and exception boundaries (`raise ... from None`) — existing
- ✓ CLI utilities for setup wizard, health diagnostic, schema repair, database wiping, and markdown import — existing
- ✓ Full multi-block page body hydration and chunked paragraph writes for Notion limits — existing

### Active

- [ ] Complete unit test suite for `notion_brain/config_schema.py` covering schema structure, keys, types, defaults, and required vs. optional fields (#51)
- [ ] Add `.pre-commit-config.yaml` wiring ruff lint/format, mypy typechecking, and basic whitespace hooks to match CONTRIBUTING.md (#52)
- [ ] Update `scripts/install.sh` to cleanly detect macOS (Darwin), display manual install instructions pointing to the README Quickstart, and exit 0 (#53)

### Out of Scope

- Automated Homebrew package bootstrap on macOS — manual installation instructions in README Step 2 are sufficient for release polish (#53)
- PyPI automated deployment pipeline — deferred to public distribution milestone
- Real-time cloud vector database integrations — local Notion workspace remains primary storage backend

## Context

- **Ecosystem**: Python 3.11–3.13 plugin package for Hermes Agent ecosystem (`hermes-agent`).
- **Storage Layer**: Notion REST API (`api.notion.com/v1`) using internal integration tokens (`NOTION_API_KEY`).
- **Quality Gates**: Ruff linting and formatting, Mypy strict type checking, and Pytest test suite with branch coverage tracking.
- **Related Issues**: Open GitHub issues #51, #52, and #53 targeted for contributor experience and release polish.

## Constraints

- **Compatibility**: Must support Python 3.11, 3.12, and 3.13 without deprecation warnings.
- **Security**: Redact all sensitive tokens (OpenAI, Notion, GitHub, Anthropic, Bearer tokens) across all input, output, and exception vectors.
- **CI Reliability**: Unit tests must run offline without requiring live Notion API credentials or a live Hermes daemon.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Isolated unit tests for `config_schema.py` | Schema declaration is pure Python; pure unit tests verify Desktop compatibility without network mocks | — Pending |
| Match `.pre-commit-config.yaml` to CI | Ensures local contributor commits pass the exact same ruff and mypy checks as GitHub Actions | — Pending |
| Clean exit 0 with guidance for Darwin in `install.sh` | Prevents package manager script failure on macOS while guiding developers to supported pip/symlink workflows | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-20 after initialization*
