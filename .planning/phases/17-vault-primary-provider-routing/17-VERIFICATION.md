---
phase: 17-vault-primary-provider-routing
verified: 2026-11-13
status: passed
source_snapshot: cc75283
score: "2/2 requirements verified; OBS-03 and SYNC-03 closed"
fingerprint: "Phase 17 closure: premium Memory writes, certification and supersession route through the vault with fail-closed errors and no Notion mutation; search is vault-first with a Notion fallback; vault path resolution and vault_status are wired. 28 adapter tests pass; full suite 596 passed, 1 deselected; ruff and mypy clean."
gaps: []
covered_files:
  - notion_brain/adapters.py
  - notion_brain/provider.py
  - tests/test_adapters.py
  - .planning/phases/17-vault-primary-provider-routing/17-01-PLAN.md
  - .planning/phases/17-vault-primary-provider-routing/17-01-SUMMARY.md
covered_digest: "v4:sha256:5e1440820226d406115da384448465cd6f49b55cb7032e04518aaf00d545c6e5"
closed:
  - truth: Premium-selected Memory writes, certification and supersession use the vault and never mutate Notion.
    requirements: [OBS-03]
    resolution: "`_write_entry_raw` branches Memory writes to `_store_vault_entry`; exact matches reuse, changed subjects use certified-safe supersede, graph edges are written after acceptance, and failures raise a redacted RuntimeError with no Notion fallback. `_tool_certify` branches to `_certify_vault` after the confirmation gate."
    evidence: "tests/test_adapters.py::test_provider_vault_primary_remember_writes_note_not_notion, test_provider_vault_write_failure_fails_closed, test_provider_vault_supersede_retains_history_and_edge, test_provider_vault_certify_flips_truth_and_supersedes_inferred_peer, test_obsidian_supersede_skips_certified_peer"
  - truth: Vault path configuration and health/status are available at the provider boundary.
    requirements: [SYNC-03]
    resolution: "initialize resolves `obsidian_vault` then `HERMES_OBSIDIAN_VAULT`; `vault_status()` reports backend, entitlement, path, note counts, schema version, index and `last_sync=not_run`. Search is vault-first with a Notion fallback."
    evidence: "tests/test_adapters.py::test_provider_vault_search_prefers_vault_and_falls_back, test_provider_vault_status_and_env_path"
---

# Phase 17 verification record

Phase 17 is verified. OBS-03 and SYNC-03 are closed; bidirectional sync, section refs and the signed license remain in Phases 18–20.

## Verification scope

- Adapter suite: **28 passed in 0.42s** (eight new regressions).
- Full repository gate: **596 passed, 1 deselected in 5.73s**.
- Ruff, mypy and CRLF-aware whitespace checks clean.
- No live Notion call or external service required.

## Closure evidence

`notion_brain/adapters.py`: `find`, `list_active`, `supersede_inferred`, certified-safe `supersede` with `superseded_ids`.

`notion_brain/provider.py`: `_vault_enabled`, `_store_vault_entry`, `_write_vault_graph`, `_certify_vault`, vault-first search, prefetch allowance, env path resolution and `vault_status`.

`tests/test_adapters.py`: eight regressions cover routing, fail-closed errors, supersession edges, certification, certified protection, search fallback, env config and status.

## Scope note

Notion is untouched while premium is selected. Migration/bootstrap and `last_sync` persistence are Phase 18; section refs and signing are Phases 19–20.

## Remaining scope

Phases 18–20. Phase 17 does not mark the milestone released or merged.
