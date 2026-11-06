# Research: Semantic Layer Architecture (NVIDIA Auto Ontology -> Hermes Brain)

**Date:** 2026-11-06  
**Source:** NVIDIA/auto-ontology (Apache-2.0, github.com/NVIDIA/auto-ontology)  
**Applicability:** hermes-brain v1.4 Semantic Brain Layer (Phases 12-15)

## 1. Problem Statement
Agents querying flat databases or note vaults frequently hallucinate because they perform fuzzy keyword/vector search directly against raw data without a shared definition of terms, relationships, or truth status. A metric or personal fact answered with high confidence is harmful if contradictory or fabricated.

## 2. Auto Ontology Core Pattern
NVIDIA Auto Ontology solves this with three distinct stages and a semantic catalog:
1. **Generate**: Ingestion extracts terms, profiles entities, and infers relationships.
2. **Certify**: Human operators review and certify terms, relations, and measures.
3. **Answer**: The agent resolves questions through the certified semantic layer, verifies coverage via `check_answerable`, and executes only when groundable, returning provenance alongside the answer.

## 3. Adaptation to hermes-brain

### A. Semantic Catalog (Phase 12)
- Provider-neutral core classes: `Term`, `Entity`, `Relation`, `LocationMapping`.
- Deterministic read path: `catalog.resolve_term("phone")` returns definition, synonyms (`["daily_driver", "mobile"]`), and storage mapping.
- Both Notion and Obsidian adapters map the catalog to their concrete storage without altering the core semantic graph.

### B. Certification & Truth Tiers (Phase 13)
- Auto Ontology's `certify` stage translates to Hermes Brain truth tiers:
  - `Status: Inferred` (default for agent-extracted facts)
  - `Status: Certified` (user-confirmed facts)
- Rule: Agents cannot self-certify. Only user explicit confirmation or corrections promote a fact.
- Certified facts take precedence during retrieval regardless of recency and supersede contradictory inferred facts immediately.

### C. Graph Provenance & Supersession Edges (Phase 14)
- Memories carry provenance: `source_agent`, `session_id`, `created_at`, `certified_at`, `status`.
- Supersession is recorded as an explicit relation edge (`Fact_B supersedes Fact_A`), not just a status flip.
- Recall allows graph traversal across related entities (e.g., all decisions linked to Project X).

### D. Answerability Gate & MCP Tools (Phase 15)
Borrow Auto Ontology's read-only MCP tool pattern:
- `brain_check_readiness()`: validates storage adapter health and cache status.
- `brain_search_terms(query)`: searches the semantic glossary before querying notes.
- `brain_check_answerable(query)`: scores term coverage; returns deterministic unsupported response if coverage is 0.
- `brain_ask(query)`: returns answer, certified status, source facts, and provenance trace.
