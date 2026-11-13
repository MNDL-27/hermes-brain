# Phase 19: Section-Aware References - Context

**Gathered:** 2026-11-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver REF-01: catalog storage references may target a markdown section (`note.md#section`). The vault adapter resolves the path and section separately, retrieval replaces the row content with the referenced section text, heading matching is case-insensitive and accepts slugs, duplicate headings are concatenated, and a missing section falls back to the whole note with a warning. No other phase scope changes.

</domain>

<decisions>
## Implementation Decisions

### Reference API
- **D-01:** Keep `ObsidianVaultAdapter.resolve_storage_ref` returning the absolute note path (now accepting and stripping a `#section` fragment). Add a separate section resolver returning `(path, section)`. Existing path consumers and tests stay unchanged. — **Reversibility:** reversible — an additional method is additive.

### Retrieval content
- **D-02:** When a definition points at a section, the retrieved row's `Content` becomes that section's markdown only. The note is still selected by path. — **Reversibility:** reversible — the full note remains available and the behavior is per-row.

### Heading matching
- **D-03:** Match the literal heading text case-insensitively and also accept its slug (`#section-name` ↔ `## Section Name`). — **Reversibility:** reversible — matching is a read-time concern.

### Duplicate headings
- **D-04:** Concatenate all matching sections in document order rather than picking the first. — **Reversibility:** reversible — deterministic and lossless.

### Claude's Discretion
- Heading normalization (whitespace collapse, punctuation-to-slug rules).
- Whether a section includes nested subheadings until the next same-or-higher heading (recommended: yes).
- Adapter method naming (`resolve_storage_section`, `section_text`).
- How the catalog's `storage_refs` output represents the section (recommended: `absolute_path#Section`).
- Warning text and redaction boundaries for a missing section.

### Folded Todos
None.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase contract
- `.planning/ROADMAP.md` § Phase 19 — goal and success criteria (REF-01).
- `.planning/REQUIREMENTS.md` — REF-01 and scope fences.
- `.planning/research/2026-11-13-obsidian-vault-backend.md` — section-locator design and fallback.
- `.planning/phases/17-vault-primary-provider-routing/17-VERIFICATION.md` — current vault ref selection behavior.

### Code
- `notion_brain/adapters.py` — `resolve_storage_ref`, `_SAFE_NOTE_RE`, `get_note`, `search`.
- `notion_brain/provider.py` — catalog ref resolution loop, `_tool_search` row selection, `_adapter_entry`.
- `notion_brain/catalog.py` — `StorageRef` and definition matching.
- `tests/test_catalog.py` — existing locator resolution and traversal tests.
- `tests/test_catalog_search.py` — reference-driven selection tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `resolve_storage_ref` already strips prefixes and enforces in-vault paths.
- `get_note` reads an indexed note; section extraction can read the same file.
- Catalog resolution already maps obsidian refs to absolute paths and selects rows by `path`.

### Established Patterns
- Invalid refs return `None`, never raise.
- Traversal outside the vault is rejected.
- Provider diagnostics redact values.

### Integration Points
- Adapter path/section resolvers.
- Provider catalog loop for `storage_refs` output and a path→section map.
- Provider `_tool_search` post-filter content replacement.

</code_context>

<specifics>
## Specific Ideas

- `note.md#Section Name` and `note.md#section-name` both resolve.
- A missing heading logs a redacted warning and keeps the whole-note content.
- `definitions[].storage_refs` shows `absolute_path#section` so the caller sees the target.
- Nested content belongs to the section until the next same-or-higher heading.

</specifics>

<deferred>
## Deferred Ideas

- Section-level write targets (remember/supersede into a section) — not in REF-01.
- Frontmatter property references — out of scope.
- Whole-vault heading index — parse at read time.

</deferred>

---

*Phase: 19-Section-Aware References*
*Context gathered: 2026-11-13*
