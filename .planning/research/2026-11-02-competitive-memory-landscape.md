# Research: Agent Memory Competitive Landscape (2026-11-02)

**Question:** What do other agent-memory systems do, and how does hermes-brain get better?
**Sources:** Live web retrieval 2026-11-02. URLs inline. Citation-check: not_observed (dossier notes carry URLs + retrieval date).
**Confidence:** Medium-high for feature facts (vendor READMEs, multiple independent comparisons). Low for benchmark claims (vendor-reported).

## Direct competitors / adjacent implementations

1. **Lore — Notion official** (github.com/makenotion/lore, MIT, npm @notionhq/lore, 172★, 17 releases, created 2026-04-15)
   - 5 DBs: Projects, Topics, Memories, Entities, Facts (subject-predicate-object assertions).
   - First-class relations: `supersedes`, `conflicts_with`, `scoped`.
   - Facts **expire by default**; must be re-reinforced. Memory-debt CLI (orphans, dupes).
   - MCP server + CLI + hooks (session-start context load, session-end autosave + auto-digest).
   - Per-operator auth (ntn PAT) → independent rate-limit buckets vs shared `secret_` integration.
   - Repo-local AGENTS.md "Memory and note-taking" section pattern.
   - Monorepo directory-prefix scoping in `.lore.yaml`.

2. **9thLevelSoftware/hermes-brain** (MemoryProvider plugin, competitor, 2026-07-17)
   - Local SQLite (FTS5 + EmbeddingGemma-300M vectors + ColBERT rerank; tiers full/lite/fts-only).
   - Hard 800-token injection budget split lane1 (pinned/warnings/decisions) 400 + lane2 (dynamic) 400.
   - Dream cycle (idle/cron): consolidation, ReasoningBank strategy distillation, skill forging, outcome-ledger reweighting.
   - Supersession: corrections append successor version; never destructive delete; `restore` from history.
   - Profile linking with RRF fusion, labeled `@profile`, read-only cross-profile.
   - stdio MCP server for external agents. `brain doctor`, `brain eval` retrieval measurement.
   - Sync: ciphertext-only relay (Argon2id/PBKDF2→Fernet), surface-only deny-list.

3. **RohiRIK/hermes-brain** (OpenLTM-based) — SQLite schema w/ embeddings (Gemini), relations graph, deterministic regex extraction (3-layer gating, no LLM calls), `openltm_recall/learn/forget/context`.

4. **mistrysiddh/hermes-brain-template** — Obsidian vault; staged memory review (human approves before promotion), dedupe + secret scrub, usage Dashboard.md. Positioning vs Mem0: human-in-the-loop vs opaque auto-embed.

5. **shahjalal2313/notion-memory-mcp** — 3-tier framing: L1 context / RAM vector / DISK Notion. Upsert-by-title (agents think in names). Write-scoped, NO delete tool (destructive ops human-only). stdlib+httpx.

6. **zoro-jiro-san/hermes-second-brain** — Karpathy LLM-wiki; GraphRAG traversal + semantic search; provenance per claim; hourly health checks, daily sync, weekly digests; inotify→git push daemon.

7. **maxtechera/memory** — HOT/WARM/COLD tiers in Obsidian; session hooks; weekly dream cycle; TTL audit; wiki sync → Notion publish.

8. **Notion hosted MCP memory** (2026-10-19 release) — `notion-memory-search` (≤500 chars query, ≤50 results), `notion-fetch` id `memory`, `notion://docs/memory` resource. Notion Agent Memories portable across MCP clients.

9. **skkeoriw/hermes-brain** — git single-writer multi-machine brain sync (push/pull roles, machine-id).

10. General market: **Mem0** (extraction + decay + "Dream" v2.2.1; OpenMemory MCP sunset Apr 2026), **Zep/Graphiti** (bi-temporal KG: `created_at/valid_at/invalid_at/expired_at`; community edition deprecated), **Letta** (agent self-edited MemFS + blocks; sleep-time compute), **Hindsight** (Postgres, 4 parallel retrieval strategies + RRF + cross-encoder rerank, retain/recall/reflect), **Cognee** (KG+vectors, Kuzu/LanceDB), **mcp-memory-service** (ONNX local embeddings, typed edges `causes`/`contradicts`, consolidation, X-Agent-ID tagging), **Supermemory** (spaces, resolution, selective forgetting), **OMEM** (no LLM in write path; accountability).

## Research/theory findings

- **TTL is a trap** (gist Jakedismo; arXiv 2605.27366 "In Defense of Forgotten"): staleness is event-driven (supersession, dependency expiry, utility decay), not temporal.
- **Belief not assertion**: provenance + confidence + scope + dependencies + status (active/superseded/needs-verification).
- **Store deixis, not datum**: high re-derivation cost → store claim; low cost → store pointer+recipe.
- **Utility-scored pruning**: log which claims entered briefs, score load-bearing vs dead weight from task outcomes. 9thLevel implements closest (outcome ledger).
- **Sleep-time consolidation** consensus: retrieval of raw fragments happens locally/instantly; heavy distillation offline (arXiv 2504.13171 Letta sleep-time; LightMem arXiv:2510.18866).
- **RSPM** (arXiv 2610.25561): rule promotion (3 contexts → category, 5 → universal), ~93% fewer retry loops, ~30% less memory.
- **LongMemEval** (arXiv:2410.10813): knowledge-update + temporal reasoning worst abilities (frontier models drop 21–30%) — supersession is the gap.

## What hermes-brain (ours) lacks today

1. Prefetch bug: reads `properties["Content"]` which has no DB column → blank prompt lines (provider.py:177).
2. No `Subject Key` → supersession: conflicting truths co-exist (both phone rows active).
3. Prefetch over Notion API = latency + rate-limit coupling; no local cache read path.
4. No token budget on injection; no lane split.
5. No Obsidian adapter; no freemium entitlement gate.
6. No search rerank across DBs; no retrieval-quality eval harness.

## Plan feed

- Decision drivers: latency, truth-conflict safety, token cost, human visibility, freemium split.
- Viable patterns (evidence-backed): Summary property + prefetch column fix; SQLite write-through cache (read local / write-through async); subject_key supersession columns→Notion props; 800-token two-lane injection; premium Obsidian adapter behind license check.
- Rejected for now: temporal KG (Neo4j infra weight), vector embeddings (Notion API has no vector search; defer to optional local FTS later), LLM-in-write-path extraction (keeps heuristics).
- Open questions: feature flag source for premium tier (LicenseGate?); Notion webhook availability on integration plan.
