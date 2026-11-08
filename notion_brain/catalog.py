"""Provider-neutral semantic catalog (CAT-01..CAT-03).

Core, provider-independent semantic layer: Terms, typed Entities, and
Relations. Deterministic — no LLM, no network, no filesystem access except
explicit save/load. Any adapter can map this layer into its concrete store.

Storage
-------
Catalog lives in memory on a :class:`Catalog` instance. It can be persisted
to ``$HERMES_HOME/brain_catalog.json`` via :meth:`Catalog.save` and reloaded
via :meth:`Catalog.load`. Writes are atomic (fsync + ``os.replace``) and the
file is chmod ``0o600``. Every string written to (and read back from) the
catalog JSON passes through :func:`notion_brain.schema.redact_secrets`.

Missing catalog file on load is not an error — the catalog starts empty.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import schema as S

_CATALOG_FILENAME = "brain_catalog.json"
_CATALOG_VERSION = 1

_QUERY_STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "by", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "me", "my", "of", "on",
    "or", "our", "please", "tell", "that", "the", "their", "them",
    "this", "to", "was", "we", "what", "when", "where", "which",
    "who", "why", "with", "you", "your",
}


def _query_words(query: str) -> list[str]:
    """Keep name punctuation (C++, C#, .NET), excluding sentence punctuation."""
    return [
        clean for word in re.findall(r"[\w'+#./:@-]+", query, flags=re.UNICODE)
        if (clean := word.strip("'").rstrip(".:"))
    ]


def _candidate_terms(query: str, known_words: set[str]) -> list[str]:
    """Extract deterministic word candidates, excluding common question glue."""
    words = _query_words(query)
    return list(dict.fromkeys(
        w for w in words
        if (len(w) > 1 and w.lower() not in _QUERY_STOPWORDS) or w.casefold() in known_words
    ))


def _matching_name_words(query: str, names: tuple[str, ...]) -> set[str]:
    """Return words covered by complete catalog names or aliases in the query."""
    query_words = _query_words(query.casefold())
    matched: set[str] = set()
    for name in names:
        words = _query_words(name.casefold())
        if words and any(
            query_words[start:start + len(words)] == words
            for start in range(len(query_words) - len(words) + 1)
        ):
            matched.update(words)
    return matched


def check_answerable(query: str, catalog: "Catalog | None" = None) -> dict[str, Any]:
    """Score query-term coverage in the semantic catalog, with redacted output."""
    safe_query = _redact(str(query or ""))
    catalog = catalog if catalog is not None else Catalog().load()
    known: set[str] = set()
    for term in catalog._terms.values():
        known.update(_matching_name_words(safe_query, (term.name, *term.synonyms)))
    for entity in catalog._entities.values():
        known.update(_matching_name_words(safe_query, (entity.name,)))
    candidates = _candidate_terms(safe_query, known)
    matched: list[str] = []
    missing: list[str] = []
    for candidate in candidates:
        (matched if candidate.casefold() in known else missing).append(candidate)
    coverage = len(matched) / len(candidates) if candidates else 0.0
    return {
        "answerable": bool(candidates) and coverage > 0.0,
        "coverage": coverage,
        "matched_terms": [_redact(t) for t in matched],
        "missing_terms": [_redact(t) for t in missing],
    }


def catalog_path() -> Path:
    """Return the canonical catalog path: ``$HERMES_HOME/brain_catalog.json``."""
    home = os.environ.get("HERMES_HOME", "").strip() or str(Path.home() / ".hermes")
    return Path(home) / _CATALOG_FILENAME


@dataclass(frozen=True)
class StorageRef:
    """Provider-neutral pointer to where content physically lives.

    ``adapter_name`` — which adapter resolves it ("notion", "obsidian", …).
    ``locator``       — adapter-specific path/id fragment ("page/<id>",
                        "note/<relative/path.md>", "db/<database_id>", …).
    ``extra``         — optional string metadata (kind, e.g. "page" / "db");
                        never inspects for semantic meaning.
    """

    adapter_name: str
    locator: str
    extra: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Term:
    """A defined term in the shared semantic vocabulary."""

    name: str
    description: str = ""
    synonyms: tuple[str, ...] = ()
    entity_refs: tuple[str, ...] = ()
    storage_refs: tuple[StorageRef, ...] = ()


@dataclass(frozen=True)
class Entity:
    """A typed entity (person, project, system, …) in the catalog."""

    name: str
    entity_type: str = "thing"
    description: str = ""
    storage_refs: tuple[StorageRef, ...] = ()


@dataclass(frozen=True)
class Relation:
    """A directed fact edge: ``subject predicate object``."""

    subject: str
    predicate: str
    object: str
    relation_type: str = "related"


# ── normalization helpers ────────────────────────────────────────────────

def _norm_names(items: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """Dedupe (case-insensitive) and drop empties, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in items or ():
        s = str(raw).strip()
        if not s:
            continue
        key = s.lower()
        if key not in seen:
            seen.add(key)
            out.append(s)
    return tuple(out)


def _redact(value: str | None) -> str:
    return S.redact_secrets(value) if value else ""


def _redact_seq(items: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_redact(str(i)) for i in items if str(i))


def _redact_refs(refs: tuple[StorageRef, ...]) -> tuple[StorageRef, ...]:
    out: list[StorageRef] = []
    for ref in refs:
        out.append(StorageRef(
            adapter_name=_redact(ref.adapter_name),
            locator=_redact(ref.locator),
            extra=tuple((_redact(k), _redact(v)) for k, v in (ref.extra or ())),
        ))
    return tuple(out)


def _require_name(raw: object, field: str) -> str:
    name = _redact(str(raw or "")).strip()
    if not name:
        raise ValueError(f"{field} must be a non-empty string")
    return name


# ── serialisation ──────────────────────────────────────────────────────

def _ref_to_json(ref: StorageRef) -> dict[str, Any]:
    return {
        "adapter_name": _redact(ref.adapter_name),
        "locator": _redact(ref.locator),
        "extra": dict(ref.extra or ()),
    }


def _ref_from_json(data: Any) -> StorageRef:
    if not isinstance(data, dict):
        raise ValueError("storage_ref must be an object")
    adapter = _require_name(data.get("adapter_name"), "storage_ref.adapter_name")
    locator = _require_name(data.get("locator"), "storage_ref.locator")
    extra = data.get("extra") or {}
    if not isinstance(extra, dict):
        raise ValueError("storage_ref.extra must be an object")
    return StorageRef(
        adapter_name=_redact(adapter),
        locator=_redact(locator),
        extra=tuple((_redact(str(k)), _redact(str(v))) for k, v in extra.items()),
    )


def _term_to_json(term: Term) -> dict[str, Any]:
    return {
        "name": _redact(term.name),
        "description": _redact(term.description),
        "synonyms": list(_redact_seq(tuple(term.synonyms))),
        "entity_refs": list(_redact_seq(tuple(term.entity_refs))),
        "storage_refs": [_ref_to_json(r) for r in term.storage_refs],
    }


def _term_from_json(data: Any) -> Term:
    if not isinstance(data, dict):
        raise ValueError("term entry must be an object")
    name = _require_name(data.get("name"), "term.name")
    synonyms = tuple(_redact(str(s)) for s in (data.get("synonyms") or []))
    entity_refs = tuple(_redact(str(s)) for s in (data.get("entity_refs") or []))
    refs = tuple(_ref_from_json(r) for r in (data.get("storage_refs") or []))
    return Term(
        name=name,
        description=_redact(str(data.get("description") or "")),
        synonyms=_norm_names(synonyms),
        entity_refs=_norm_names(entity_refs),
        storage_refs=_redact_refs(refs),
    )


def _entity_to_json(entity: Entity) -> dict[str, Any]:
    return {
        "name": _redact(entity.name),
        "entity_type": _redact(entity.entity_type),
        "description": _redact(entity.description),
        "storage_refs": [_ref_to_json(r) for r in entity.storage_refs],
    }


def _entity_from_json(data: Any) -> Entity:
    if not isinstance(data, dict):
        raise ValueError("entity entry must be an object")
    name = _require_name(data.get("name"), "entity.name")
    refs = tuple(_ref_from_json(r) for r in (data.get("storage_refs") or []))
    return Entity(
        name=name,
        entity_type=_redact(str(data.get("entity_type") or "thing")) or "thing",
        description=_redact(str(data.get("description") or "")),
        storage_refs=_redact_refs(refs),
    )


def _relation_to_json(rel: Relation) -> dict[str, Any]:
    return {
        "subject": _redact(rel.subject),
        "predicate": _redact(rel.predicate),
        "object": _redact(rel.object),
        "relation_type": _redact(rel.relation_type),
    }


def _relation_from_json(data: Any) -> Relation:
    if not isinstance(data, dict):
        raise ValueError("relation entry must be an object")
    return Relation(
        subject=_require_name(data.get("subject"), "relation.subject"),
        predicate=_require_name(data.get("predicate"), "relation.predicate"),
        object=_require_name(data.get("object"), "relation.object"),
        relation_type=_redact(str(data.get("relation_type") or "related")) or "related",
    )


class Catalog:
    """In-memory semantic catalog with deterministic queries and JSON persistence."""

    def __init__(self) -> None:
        self._terms: dict[str, Term] = {}   # lowered name -> Term
        self._entities: dict[str, Entity] = {}  # lowered name -> Entity
        self._relations: list[Relation] = []

    # ── ingest ────────────────────────────────────────────────────────

    def add_term(self, term: Term) -> Term:
        """Upsert a term. Persisted form is secret-redacted."""
        if not isinstance(term, Term):
            raise TypeError("add_term() expects a Term")
        clean = Term(
            name=_require_name(term.name, "term.name"),
            description=_redact(term.description),
            synonyms=_norm_names(tuple(_redact_seq(tuple(term.synonyms)))),
            entity_refs=_norm_names(tuple(_redact_seq(tuple(term.entity_refs)))),
            storage_refs=_redact_refs(tuple(term.storage_refs)),
        )
        self._terms[clean.name.lower()] = clean
        return clean

    def add_entity(self, entity: Entity) -> Entity:
        """Upsert an entity. Persisted form is secret-redacted."""
        if not isinstance(entity, Entity):
            raise TypeError("add_entity() expects an Entity")
        clean = Entity(
            name=_require_name(entity.name, "entity.name"),
            entity_type=_redact(entity.entity_type or "thing") or "thing",
            description=_redact(entity.description),
            storage_refs=_redact_refs(tuple(entity.storage_refs)),
        )
        self._entities[clean.name.lower()] = clean
        return clean

    def add_relation(self, relation: Relation) -> Relation:
        """Add a relation edge; exact duplicates are ignored."""
        if not isinstance(relation, Relation):
            raise TypeError("add_relation() expects a Relation")
        clean = Relation(
            subject=_require_name(relation.subject, "relation.subject"),
            predicate=_require_name(relation.predicate, "relation.predicate"),
            object=_require_name(relation.object, "relation.object"),
            relation_type=_redact(relation.relation_type or "related") or "related",
        )
        if clean not in self._relations:
            self._relations.append(clean)
        return clean

    # ── query ─────────────────────────────────────────────────────────

    def match_definitions(self, query: str) -> list[Term | Entity]:
        """Match complete names or synonyms, including phrases, in a query."""
        safe_query = _redact(str(query or ""))
        matches: list[Term | Entity] = []
        for term in self._terms.values():
            if _matching_name_words(safe_query, (term.name, *term.synonyms)):
                matches.append(term)
        for entity in self._entities.values():
            if _matching_name_words(safe_query, (entity.name,)):
                matches.append(entity)
        return matches

    def resolve_term(self, name: str) -> Term | None:
        """Resolve a term by exact match, then case-insensitively, then by synonym."""
        query = (name or "").strip()
        if not query:
            return None
        hit = self._terms.get(query.lower())
        if hit is not None:
            return hit
        needle = query.lower()
        for term in self._terms.values():
            if needle in (s.lower() for s in term.synonyms):
                return term
        return None

    def search_terms(self, query: str) -> list[str]:
        """Search defined terms, synonyms, and entities without reading notes."""
        needle = _redact(str(query or "")).strip().casefold()
        if not needle:
            return []
        hits: list[str] = []
        for term in self._terms.values():
            if any(needle in value.casefold() for value in (term.name, *term.synonyms, term.description)):
                hits.append(_redact(term.name))
        for entity in self._entities.values():
            if any(needle in value.casefold() for value in (entity.name, entity.description, entity.entity_type)):
                hits.append(_redact(entity.name))
        return list(dict.fromkeys(hits))

    def list_entities(self, entity_type: str | None = None) -> list[Entity]:
        """List entities, optionally filtered to one entity_type (case-insensitive)."""
        items = list(self._entities.values())
        if entity_type is None:
            return items
        needle = str(entity_type).strip().lower()
        return [e for e in items if (e.entity_type or "thing").lower() == needle]

    def get_relations(self, subject: str | None = None) -> list[Relation]:
        """List relations, optionally filtered to one subject (case-insensitive)."""
        if subject is None:
            return list(self._relations)
        needle = str(subject).strip().lower()
        return [r for r in self._relations if r.subject.lower() == needle]

    def graph_traverse(
        self, start_id: str, predicate: str | None = None, max_depth: int = 3
    ) -> list[str]:
        """Return reachable relation endpoints in breadth-first order.

        Edges are traversed in both directions so callers can follow a chain
        from either endpoint. ``max_depth`` counts edges from ``start_id``.
        """
        start = _require_name(start_id, "start_id")
        if max_depth < 0:
            return []
        needle = predicate.lower() if predicate else None
        visited = {start.lower()}
        found: list[str] = []
        frontier = [(start, 0)]
        while frontier:
            current, depth = frontier.pop(0)
            if depth >= max_depth:
                continue
            for rel in self._relations:
                if needle and rel.predicate.lower() != needle:
                    continue
                if rel.subject.lower() == current.lower():
                    neighbor = rel.object
                elif rel.object.lower() == current.lower():
                    neighbor = rel.subject
                else:
                    continue
                key = neighbor.lower()
                if key in visited:
                    continue
                visited.add(key)
                safe_neighbor = _redact(neighbor)
                found.append(safe_neighbor)
                frontier.append((safe_neighbor, depth + 1))
        return found

    # ── persistence ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": _CATALOG_VERSION,
            "terms": [_term_to_json(t) for t in self._terms.values()],
            "entities": [_entity_to_json(e) for e in self._entities.values()],
            "relations": [_relation_to_json(r) for r in self._relations],
        }

    def save(self, path: Path | str | None = None) -> Path:
        """Atomically persist the catalog (fsync + os.replace), mode 0o600."""
        target = Path(path) if path is not None else catalog_path()
        data = self.to_dict()
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".catalog.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.chmod(tmp, 0o600)
            os.replace(tmp, target)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return target

    def load(self, path: Path | str | None = None) -> "Catalog":
        """Load a catalog from disk. Missing file leaves the catalog empty."""
        target = Path(path) if path is not None else catalog_path()
        try:
            raw = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            return self
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"catalog at {target} is not valid JSON: {exc}") from None
        if not isinstance(data, dict):
            raise ValueError(f"catalog at {target} must contain a JSON object")
        version = data.get("version", _CATALOG_VERSION)
        if version != _CATALOG_VERSION:
            raise ValueError(f"unsupported catalog version: {version!r}")

        for raw_term in data.get("terms", []):
            self.add_term(_term_from_json(raw_term))
        for raw_entity in data.get("entities", []):
            self.add_entity(_entity_from_json(raw_entity))
        for raw_relation in data.get("relations", []):
            self.add_relation(_relation_from_json(raw_relation))
        return self


def graph_traverse(
    start_id: str, predicate: str | None = None, max_depth: int = 3
) -> list[str]:
    """Traverse the persisted catalog from ``start_id`` in either direction."""
    return Catalog().load().graph_traverse(start_id, predicate, max_depth)
