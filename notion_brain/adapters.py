"""Storage adapters: Notion + Obsidian backends and CAT-03 locator resolution.

``StorageAdapter`` (ADAPT-01) is the provider-neutral protocol; both adapters
implement ``search``/``remember``/``supersede``/``prefetch``/``health`` in
addition to the Phase 12 ``resolve_storage_ref`` mapping:

- ``NotionAdapter`` (ADAPT-02) delegates to :mod:`notion_brain.store` and
  :mod:`notion_brain.bootstrap`; ``NotionBrainProvider`` untouched.
- ``ObsidianVaultAdapter`` (ADAPT-04) writes markdown notes with YAML
  frontmatter under ``<vault>/hermes-brain/`` plus a stdlib sqlite3 index at
  ``<vault>/hermes-brain/index.db``. Premium only — construct via the
  entitlement-checked :func:`get_adapter` factory (ADAPT-03, see
  ``notion_brain.entitlement``).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol

from . import bootstrap, store
from . import schema as S
from .catalog import StorageRef
from .entitlement import EntitlementError, is_premium_entitled

logger = logging.getLogger(__name__)


class StorageAdapter(Protocol):
    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]: ...
    def remember(self, entry: dict[str, Any]) -> dict[str, Any]: ...
    def supersede(self, subject_key: str, entry: dict[str, Any]) -> dict[str, Any]: ...
    def prefetch(self, limit: int = 10) -> list[dict[str, Any]]: ...
    def health(self) -> dict[str, Any]: ...

_NOTION_ID_RE = re.compile(r"^[0-9a-fA-F]{8}(-?[0-9a-fA-F]{4}){3}-?[0-9a-fA-F]{12}$", re.IGNORECASE)
_NOTION_PLAIN_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_SAFE_NOTE_RE = re.compile(r"^[A-Za-z0-9._/-]+\.md$", re.IGNORECASE)

_OBSIDIAN_SCHEMA_VERSION = 2
_NOTE_FIELDS = (
    "id",
    "title",
    "subject_key",
    "status",
    "truth",
    "source_agent",
    "source_session",
    "created_at",
    "updated_at",
    "superseded_page_id",
    "domain",
    "kind",
    "tags",
)
_OBSIDIAN_COLUMNS = {
    "truth": "TEXT NOT NULL DEFAULT 'inferred'",
    "source_agent": "TEXT NOT NULL DEFAULT 'unknown'",
    "source_session": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
    "superseded_page_id": "TEXT NOT NULL DEFAULT ''",
    "domain": "TEXT NOT NULL DEFAULT 'memory'",
    "kind": "TEXT NOT NULL DEFAULT 'note'",
    "tags": "TEXT NOT NULL DEFAULT '[]'",
}


def _render_obsidian_note(meta: Mapping[str, Any], body: str) -> str:
    lines = [f"{key}: {json.dumps(meta.get(key, ''))}" for key in _NOTE_FIELDS]
    return "---\n" + "\n".join(lines) + f"\n---\n\n{body}\n"


def _parse_obsidian_note(text: str) -> tuple[dict[str, Any], str]:
    """Parse the leading frontmatter block without a YAML dependency."""
    meta: dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            for line in parts[1].replace("\r\n", "\n").splitlines():
                if ":" not in line:
                    continue
                key, raw = line.split(":", 1)
                key = key.strip()
                raw = raw.strip()
                if not key:
                    continue
                try:
                    meta[key] = json.loads(raw)
                except (TypeError, ValueError):
                    meta[key] = raw.strip('"')
            body = parts[2].lstrip("\r\n")
    return meta, body


def _obsidian_note_meta(
    entry: Mapping[str, Any], *, existing: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    data = _redact_value(dict(entry))
    old = dict(existing or {})
    metadata = data.get("metadata") or {}
    tags_raw = data.get("tags") or old.get("tags") or []
    if isinstance(tags_raw, str):
        tags_raw = [tags_raw]
    now = datetime.now(timezone.utc).isoformat()
    meta: dict[str, Any] = {
        "id": str(data.get("id") or old.get("id") or uuid.uuid4().hex),
        "title": str(data.get("title") or old.get("title") or "Untitled"),
        "subject_key": str(
            data.get("subject_key") or metadata.get("subject_key") or old.get("subject_key") or ""
        ),
        "status": str(data.get("status") or old.get("status") or "active").lower(),
        "truth": str(data.get("truth") or old.get("truth") or "inferred").lower(),
        "source_agent": str(data.get("source_agent") or old.get("source_agent") or "unknown"),
        "source_session": str(
            data.get("source_session")
            or data.get("source_session_id")
            or old.get("source_session")
            or ""
        ),
        "created_at": str(data.get("created_at") or old.get("created_at") or now),
        "updated_at": now,
        "superseded_page_id": str(
            data.get("superseded_page_id") or old.get("superseded_page_id") or ""
        ),
        "domain": str(data.get("domain") or old.get("domain") or "memory"),
        "kind": str(data.get("kind") or old.get("kind") or "note"),
        "tags": list(tags_raw),
    }
    if meta["truth"] not in {"inferred", "certified"}:
        meta["truth"] = "inferred"
    if old.get("truth") == "certified" and data.get("truth") != "certified":
        meta["truth"] = "certified"
    status = str(meta["status"]).casefold()
    meta["status"] = "Superseded" if status == "superseded" else "active"
    tags_value = meta["tags"]
    if isinstance(tags_value, str):
        tags_value = [tags_value]
    meta["tags"] = [
        S.redact_secrets(str(tag)) for tag in tags_value if str(tag).strip()
    ]
    for key in _NOTE_FIELDS:
        if key != "tags":
            meta[key] = S.redact_secrets(str(meta[key]))
    return meta


def _obsidian_row_to_entry(row: Any, storage_path: Path) -> dict[str, Any]:
    try:
        tags = json.loads(row["tags"] or "[]")
    except (TypeError, ValueError):
        tags = []
    if not isinstance(tags, list):
        tags = [str(tags)]
    return _redact_value({
        "id": row["id"],
        "title": row["title"] or "Untitled",
        "subject_key": row["subject_key"] or "",
        "status": row["status"] or "active",
        "truth": row["truth"] or "inferred",
        "source_agent": row["source_agent"] or "unknown",
        "source_session": row["source_session"] or "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
        "superseded_page_id": row["superseded_page_id"] or "",
        "domain": row["domain"] or "memory",
        "kind": row["kind"] or "note",
        "tags": tags,
        "content": row["body"] or "",
        "path": (storage_path / row["path"]).as_posix(),
    })


def _adapter_name(ref: StorageRef | Mapping[str, object]) -> str | None:
    value = getattr(ref, "adapter_name", None)
    if value is None and isinstance(ref, Mapping):
        value = ref.get("adapter_name")
    return str(value).strip().lower() if value is not None else None


def _locator(ref: StorageRef | Mapping[str, object]) -> str | None:
    value = getattr(ref, "locator", None)
    if value is None and isinstance(ref, Mapping):
        value = ref.get("locator")
    loc = str(value).strip() if value is not None else ""
    return loc or None


def _is_notion_id(value: str) -> bool:
    return bool(_NOTION_ID_RE.match(value) or _NOTION_PLAIN_RE.match(value))


def _strip_notion_locator(locator: str) -> str | None:
    for prefix in ("page/", "page:", "page://", "db/", "db:", "database/", "database:"):
        if locator.lower().startswith(prefix):
            candidate = locator[len(prefix):].strip().strip("/")
            return candidate if _is_notion_id(candidate) else None
    return locator if _is_notion_id(locator) else None


class NotionAdapter:
    """Notion storage operations and catalog locator resolution."""

    def __init__(self, *, notion_api_key: str | None = None, hermes_home: str | Path = "") -> None:
        # Stored for the Phase 11 wiring; never logged, never serialized.
        self.notion_api_key = notion_api_key
        self.hermes_home = Path(hermes_home).expanduser() if hermes_home else Path.home() / ".hermes"

    def search(
        self, query: str, limit: int = 8, *, database_id: str | None = None
    ) -> list[dict[str, Any]]:
        if database_id:
            return [_redact_value(row) for row in store.query_database(database_id, page_size=limit)]
        return [_redact_value(row) for row in store.search_entries(S.redact_secrets(query), page_size=limit)]

    def remember(self, entry: dict[str, Any]) -> dict[str, Any]:
        clean = _redact_value(entry)
        clean.setdefault("domain", "memory")
        cache = bootstrap._load_cache(self.hermes_home / S.CACHE_FILE)
        domain = S.normalize_domain(str(clean.get("domain") or "memory"))
        database_id = cache.get(f"db_{S.database_for_domain(domain)}")
        if not database_id:
            raise RuntimeError("Notion database unavailable; free tier fallback: use the Notion workspace adapter.")
        values = {k: clean[k] for k in S.BrainEntry.__dataclass_fields__ if k in clean}
        values.setdefault("domain", domain)
        brain_entry = S.BrainEntry(**values).normalized()
        properties = self._database_properties(database_id, brain_entry)
        result = store.create_database_page(database_id, properties)
        return _redact_value(result)

    def _database_properties(self, database_id: str, entry: S.BrainEntry) -> dict[str, Any]:
        props: dict[str, Any] = {"title": store.title_property(entry.title)}
        schema_props = store.get_database(database_id).get("properties", {})
        if "Domain" in schema_props:
            props["Domain"] = store.select_property(entry.domain)
        if "Content" in schema_props:
            props["Content"] = store.rich_text_property(entry.content)
        if "Status" in schema_props:
            status_options = schema_props["Status"]
            options = (status_options.get("status", {}).get("options")
                       or status_options.get("select", {}).get("options") or [])
            names = {opt.get("name", "") for opt in options if isinstance(opt, dict)}
            if entry.status in names:
                status_name = entry.status
            elif "active" in names:
                status_name = "active"
            else:
                status_name = min(names) if names else ""
            if status_name:
                props["Status"] = (store.status_property(status_name) if "status" in status_options
                                    else store.select_property(status_name))
        if "Subject Key" in schema_props and entry.metadata.get("subject_key"):
            props["Subject Key"] = store.rich_text_property(str(entry.metadata["subject_key"]))
        return props

    def supersede(self, subject_key: str, entry: dict[str, Any]) -> dict[str, Any]:
        key = S.redact_secrets(subject_key).strip()
        clean = _redact_value(entry)
        clean["domain"] = "memory"
        metadata = dict(clean.get("metadata") or {})
        metadata["subject_key"] = key
        clean["metadata"] = metadata
        # Save replacement as active first, matching provider write-path order.
        replacement = self.remember(clean)
        cache = bootstrap._load_cache(self.hermes_home / S.CACHE_FILE)
        database_id = cache.get("db_memory")
        if not database_id or not key:
            return replacement
        try:
            schema_props = store.get_database(database_id).get("properties", {})
            options = schema_props.get("Status", {}).get("status", {}).get("options", [])
            if not any(opt.get("name") == "Superseded" for opt in options if isinstance(opt, dict)):
                return replacement
            rows = store.query_database(database_id, page_size=100)
            for row in rows:
                row_id = str(row.get("id") or "")
                props = row.get("properties", {}) or {}
                if (not row_id or row_id == replacement.get("id")
                        or str(props.get("Subject Key") or "").strip() != key
                        or str(props.get("Status") or "active").casefold() != "active"):
                    continue
                store.update_page(row_id, {"Status": store.status_property("Superseded")}, expected_database_id=database_id)
        except Exception as exc:
            logger.warning("NotionAdapter supersession failed: %s", S.redact_secrets(str(exc)))
        return replacement

    def prefetch(self, limit: int = 10) -> list[dict[str, Any]]:
        cache = bootstrap._load_cache(self.hermes_home / S.CACHE_FILE)
        db_id = cache.get("db_memory")
        if not db_id:
            return []
        return [_redact_value(row) for row in store.query_database(db_id, page_size=limit)]

    def health(self) -> dict[str, Any]:
        return {"status": S.redact_secrets(bootstrap.health_report(self.hermes_home))}

    def resolve_storage_ref(self, ref: StorageRef | Mapping[str, object]) -> str | None:
        """Return a concrete Notion page/database id for ``ref``, else None."""
        name = _adapter_name(ref)
        if name is None or (name != "notion" and not name.startswith("notion")):
            return None
        locator = _locator(ref)
        if locator is None:
            return None
        return _strip_notion_locator(locator)


class ObsidianVaultAdapter:
    """Premium markdown + SQLite memory store inside the user's vault.

    Notes live under ``<vault>/hermes-brain/`` with YAML-style frontmatter;
    the SQLite index mirrors every field for offline prefetch and search.
    Catalog ``StorageRef`` locators resolve to absolute paths inside the
    vault, and traversal outside it is rejected.
    """

    def __init__(self, vault_path: str | Path) -> None:
        if not vault_path:
            raise ValueError("vault_path must be a non-empty path")
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.storage_path = self.vault_path / "hermes-brain"
        self.index_path = self.storage_path / "index.db"

    def _connect(self) -> sqlite3.Connection:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.index_path))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                title TEXT NOT NULL,
                subject_key TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                body TEXT NOT NULL,
                truth TEXT NOT NULL DEFAULT 'inferred',
                source_agent TEXT NOT NULL DEFAULT 'unknown',
                source_session TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT '',
                superseded_page_id TEXT NOT NULL DEFAULT '',
                domain TEXT NOT NULL DEFAULT 'memory',
                kind TEXT NOT NULL DEFAULT 'note',
                tags TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
        for name, ddl in _OBSIDIAN_COLUMNS.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {name} {ddl}")
        meta = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        try:
            current = int(meta["value"]) if meta is not None else 0
        except (TypeError, ValueError):
            current = 0
        if current < _OBSIDIAN_SCHEMA_VERSION:
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
                (str(_OBSIDIAN_SCHEMA_VERSION),),
            )
        conn.commit()
        return conn

    @staticmethod
    def _clean_entry(entry: dict[str, Any]) -> dict[str, Any]:
        return _redact_value(entry)

    def _find_by_id(self, memory_id: str) -> sqlite3.Row | None:
        if not memory_id:
            return None
        with self._connect() as conn:
            return conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()

    def _find_active_match(self, title: str, subject_key: str, body: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT * FROM memories
                WHERE lower(title)=lower(?) AND subject_key=? AND body=?
                  AND lower(status)='active'
                ORDER BY created_at ASC, id ASC LIMIT 1
                """,
                (title, subject_key, body),
            ).fetchone()

    def _row_values(self, meta: dict[str, Any], path: str, body: str) -> tuple[Any, ...]:
        return (
            meta["id"], path, meta["title"], meta["subject_key"], meta["status"],
            meta["truth"], meta["source_agent"], meta["source_session"],
            meta["created_at"], meta["updated_at"], meta["superseded_page_id"],
            meta["domain"], meta["kind"], json.dumps(meta["tags"]), body,
        )

    def remember(self, entry: dict[str, Any]) -> dict[str, Any]:
        data = self._clean_entry(entry)
        memory_id = str(data.get("id") or "").strip()
        existing_row = self._find_by_id(memory_id) if memory_id else None
        existing = dict(existing_row) if existing_row is not None else None
        body = S.redact_secrets(str(
            data.get("content")
            or data.get("body")
            or (existing or {}).get("content")
            or (existing or {}).get("body")
            or ""
        ))
        if existing is None and not memory_id:
            title = str(data.get("title") or "Untitled")
            subject_key = str(
                data.get("subject_key") or (data.get("metadata") or {}).get("subject_key") or ""
            )
            match = self._find_active_match(title, subject_key, body)
            if match is not None:
                return _obsidian_row_to_entry(match, self.storage_path)
        meta = _obsidian_note_meta(data, existing=existing)
        filename = f"{meta['id']}.md"
        note = self.storage_path / filename
        self.storage_path.mkdir(parents=True, exist_ok=True)
        note.write_text(_render_obsidian_note(meta, body), encoding="utf-8")
        values = self._row_values(meta, filename, body)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id, path, title, subject_key, status, truth, source_agent,
                    source_session, created_at, updated_at, superseded_page_id,
                    domain, kind, tags, body
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            conn.commit()
        row = dict(zip(
            ("id", "path", "title", "subject_key", "status", "truth", "source_agent",
             "source_session", "created_at", "updated_at", "superseded_page_id",
             "domain", "kind", "tags", "body"),
            values,
        ))
        return _obsidian_row_to_entry(row, self.storage_path)

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        needle = S.redact_secrets(query).casefold()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC, id ASC"
            ).fetchall()
        found: list[dict[str, Any]] = []
        for row in rows:
            note_text = (self.storage_path / row["path"]).read_text(encoding="utf-8")
            if needle in note_text.casefold():
                found.append(_obsidian_row_to_entry(row, self.storage_path))
        return found[:max(0, limit)]

    def prefetch(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC, id ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_obsidian_row_to_entry(row, self.storage_path) for row in rows]

    def get_note(self, path: str | Path) -> dict[str, Any] | None:
        """Return one indexed note by absolute path inside this adapter's store.

        Catalog references resolve to absolute note paths; this lets retrieval
        load a referenced note even when its text does not match the query.
        Paths outside ``<vault>/hermes-brain/`` and unknown notes return None.
        """
        try:
            target = Path(path).expanduser().resolve()
            relative = target.relative_to(self.storage_path).as_posix()
        except (ValueError, OSError):
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE path=?",
                (relative,),
            ).fetchone()
        if row is None:
            return None
        return _obsidian_row_to_entry(row, self.storage_path)

    def find(self, memory_id: str) -> dict[str, Any] | None:
        """Return one note by id, else None."""
        target = S.redact_secrets(str(memory_id or "")).strip()
        if not target:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id=?", (target,)).fetchone()
        return _obsidian_row_to_entry(row, self.storage_path) if row is not None else None

    def list_active(self, subject_key: str | None = None) -> list[dict[str, Any]]:
        """List active notes, optionally scoped to one subject key."""
        query = "SELECT * FROM memories WHERE lower(status)='active'"
        params: list[Any] = []
        key = S.redact_secrets(str(subject_key or "")).strip()
        if key:
            query += " AND subject_key=?"
            params.append(key)
        query += " ORDER BY created_at DESC, id ASC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_obsidian_row_to_entry(row, self.storage_path) for row in rows]

    def _flip_superseded(self, row: sqlite3.Row, now: str) -> None:
        note = self.storage_path / row["path"]
        meta, body = _parse_obsidian_note(note.read_text(encoding="utf-8"))
        meta = _obsidian_note_meta(meta, existing=meta)
        meta["status"] = "Superseded"
        meta["updated_at"] = now
        note.write_text(_render_obsidian_note(meta, body), encoding="utf-8")

    def supersede(self, subject_key: str, entry: dict[str, Any]) -> dict[str, Any]:
        key = S.redact_secrets(str(subject_key or "")).strip()
        now = datetime.now(timezone.utc).isoformat()
        superseded_ids: list[str] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE subject_key=? AND lower(status)='active' "
                "ORDER BY created_at ASC, id ASC",
                (key,),
            ).fetchall()
            for row in rows:
                if str(row["truth"] or "inferred").casefold() == "certified":
                    continue
                self._flip_superseded(row, now)
                conn.execute(
                    "UPDATE memories SET status='Superseded', updated_at=? WHERE id=?",
                    (now, row["id"]),
                )
                superseded_ids.append(str(row["id"]))
            conn.commit()
        data = dict(entry)
        data["subject_key"] = key
        if superseded_ids and not data.get("superseded_page_id"):
            data["superseded_page_id"] = superseded_ids[0]
        replacement = self.remember(_redact_value(data))
        replacement["superseded_ids"] = superseded_ids
        return replacement

    def supersede_inferred(self, subject_key: str, *, keep_id: str = "") -> list[str]:
        """Mark active inferred notes for a subject Superseded, excluding ``keep_id``."""
        key = S.redact_secrets(str(subject_key or "")).strip()
        if not key:
            return []
        keep = str(keep_id or "").strip()
        now = datetime.now(timezone.utc).isoformat()
        superseded: list[str] = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE subject_key=? AND lower(status)='active' "
                "ORDER BY created_at ASC, id ASC",
                (key,),
            ).fetchall()
            for row in rows:
                memory_id = str(row["id"])
                if keep and memory_id == keep:
                    continue
                if str(row["truth"] or "inferred").casefold() == "certified":
                    continue
                self._flip_superseded(row, now)
                conn.execute(
                    "UPDATE memories SET status='Superseded', updated_at=? WHERE id=?",
                    (now, memory_id),
                )
                superseded.append(memory_id)
            conn.commit()
        return superseded

    def certify(self, memory_id: str, *, truth: str = "certified") -> dict[str, Any] | None:
        """Set a note's truth status; the provider confirmation gate is external."""
        target = S.redact_secrets(str(memory_id or "")).strip()
        if not target or truth not in {"inferred", "certified"}:
            return None
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM memories WHERE id=?", (target,)).fetchone()
            if row is None:
                return None
            note = self.storage_path / row["path"]
            meta, body = _parse_obsidian_note(note.read_text(encoding="utf-8"))
            meta = _obsidian_note_meta(meta, existing=meta)
            meta["truth"] = truth
            meta["updated_at"] = now
            note.write_text(_render_obsidian_note(meta, body), encoding="utf-8")
            conn.execute(
                "UPDATE memories SET truth=?, updated_at=? WHERE id=?",
                (truth, now, target),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM memories WHERE id=?", (target,)).fetchone()
        return _obsidian_row_to_entry(row, self.storage_path) if row is not None else None

    def resolve_storage_ref(self, ref: StorageRef | Mapping[str, object]) -> str | None:
        """Return an absolute note path inside the vault for ``ref``, else None."""
        name = _adapter_name(ref)
        if name != "obsidian":
            return None
        locator = _locator(ref)
        if locator is None:
            return None

        raw = locator
        for prefix in ("note/", "notes/", "note:", "notes:", "obsidian://note/"):
            if raw.lower().startswith(prefix):
                raw = raw[len(prefix):]
                break
        if not _SAFE_NOTE_RE.match(raw):  # .md files only, no "..", no URLs
            return None

        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.vault_path / raw
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.vault_path)
        except ValueError:
            return None  # traversal outside the vault — rejected
        return resolved.as_posix()

    def health(self) -> dict[str, Any]:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE lower(status)='active'"
            ).fetchone()[0]
            certified = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE truth='certified'"
            ).fetchone()[0]
            meta = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        try:
            schema_version = int(meta["value"]) if meta is not None else _OBSIDIAN_SCHEMA_VERSION
        except (TypeError, ValueError):
            schema_version = _OBSIDIAN_SCHEMA_VERSION
        return {
            "status": "ok",
            "count": count,
            "active": active,
            "certified": certified,
            "schema_version": schema_version,
            "index": S.redact_secrets(self.index_path.as_posix()),
        }


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return S.redact_secrets(value)
    if isinstance(value, dict):
        return {S.redact_secrets(str(k)): _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def get_adapter(name: str = "notion", *, hermes_home: str | Path, obsidian_vault: str | Path | None = None) -> StorageAdapter:
    if name == "notion":
        return NotionAdapter(hermes_home=hermes_home)
    if name == "obsidian":
        if not is_premium_entitled(hermes_home):
            raise EntitlementError("Obsidian storage requires premium. Free tier fallback: Notion storage.")
        if obsidian_vault is None:
            return NotionAdapter(hermes_home=hermes_home)
        return ObsidianVaultAdapter(obsidian_vault)
    raise ValueError(f"Unknown storage adapter: {S.redact_secrets(name)}")
