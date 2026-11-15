# Phase 19: Section-Aware References - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-11-13
**Phase:** 19-section-aware-references
**Areas discussed:** Ref API, Retrieval, Heading match, Duplicates

---

## Ref API

| Option | Description | Selected |
|--------|-------------|----------|
| Path + separate section | Keep `resolve_storage_ref` path-only; add a section resolver. | ✓ |
| Return path#section | Existing method returns a fragment; all consumers must strip it. | |
| Structured object | Dataclass with path and section; changes the string contract. | |

**User's choice:** Path + separate section
**Notes:** Existing path consumers stay unchanged.

---

## Retrieval

| Option | Description | Selected |
|--------|-------------|----------|
| Section text only | Replace row content with the referenced section. | ✓ |
| Whole note + excerpt | Return the full note plus a separate section field. | |
| Whole note only | Use the section only for selection. | |

**User's choice:** Section text only
**Notes:** Precise recall; the note is still selected by path.

---

## Heading match

| Option | Description | Selected |
|--------|-------------|----------|
| Literal + slug, insensitive | Match text case-insensitively and accept slugs. | ✓ |
| Literal only | Case-insensitive exact heading text. | |
| Exact case-sensitive | Strict literal match. | |

**User's choice:** Literal + slug, insensitive
**Notes:** `#section-name` and `## Section Name` are equivalent.

---

## Duplicates

| Option | Description | Selected |
|--------|-------------|----------|
| Concatenate matches | Join all matching sections in document order. | ✓ |
| First match only | Use the first occurrence. | |
| Fall back to whole note | Treat duplicates as ambiguous. | |

**User's choice:** Concatenate matches
**Notes:** Deterministic and lossless.

---

## Claude's Discretion

- Heading normalization and nested-section boundaries.
- Method naming and output formatting.
- Missing-section warning text.

## Deferred Ideas

- Section-level write targets.
- Frontmatter property references.
- Whole-vault heading index.
