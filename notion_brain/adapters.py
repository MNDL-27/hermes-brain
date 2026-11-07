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

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
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
    """Resolve catalog StorageRefs to Obsidian note paths (CAT-03 only).

    The constructor takes the user's vault path; note paths are returned as
    absolute paths contained within the vault. Absolute locators are accepted
    only when they point inside the vault.
    """

    def __init__(self, vault_path: str | Path) -> None:
        if not vault_path:
            raise ValueError("vault_path must be a non-empty path")
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.storage_path = self.vault_path / "hermes-brain"
        self.index_path = self.storage_path / "index.db"

    def _connect(self) -> sqlite3.Connection:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.index_path)
        conn.execute("CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, path TEXT NOT NULL, title TEXT NOT NULL, subject_key TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, body TEXT NOT NULL)")
        conn.commit()
        return conn

    @staticmethod
    def _clean_entry(entry: dict[str, Any]) -> dict[str, Any]:
        return _redact_value(entry)

    def remember(self, entry: dict[str, Any]) -> dict[str, Any]:
        data = self._clean_entry(entry)
        title = str(data.get("title") or "Untitled")
        subject_key = str(data.get("subject_key") or data.get("metadata", {}).get("subject_key") or "")
        status = str(data.get("status") or "active")
        created_at = str(data.get("created_at") or datetime.now(timezone.utc).isoformat())
        body = str(data.get("content") or data.get("body") or "")
        memory_id = str(data.get("id") or uuid.uuid4().hex)
        filename = f"{memory_id}.md"
        note = self.storage_path / filename
        self.storage_path.mkdir(parents=True, exist_ok=True)
        note.write_text("---\n" + "\n".join((f"title: {json.dumps(title)}", f"subject_key: {json.dumps(subject_key)}", f"status: {json.dumps(status)}", f"created_at: {json.dumps(created_at)}")) + f"\n---\n\n{body}\n", encoding="utf-8")
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO memories VALUES (?, ?, ?, ?, ?, ?, ?)", (memory_id, filename, title, subject_key, status, created_at, body))
        return _redact_value({"id": memory_id, "title": title, "subject_key": subject_key, "status": status, "created_at": created_at, "content": body, "path": note.as_posix()})

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        needle = S.redact_secrets(query).casefold()
        with self._connect() as conn:
            rows = conn.execute("SELECT id, path, title, subject_key, status, created_at, body FROM memories ORDER BY created_at DESC").fetchall()
        found = []
        for memory_id, path, title, key, status, created, body in rows:
            note_text = (self.storage_path / path).read_text(encoding="utf-8")
            if needle in note_text.casefold():
                found.append({"id": memory_id, "title": title, "subject_key": key, "status": status, "created_at": created, "content": body, "path": (self.storage_path / path).as_posix()})
        return _redact_value(found[:max(0, limit)])

    def prefetch(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, path, title, subject_key, status, created_at, body FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return _redact_value([{"id": r[0], "title": r[2], "subject_key": r[3], "status": r[4], "created_at": r[5], "content": r[6], "path": (self.storage_path / r[1]).as_posix()} for r in rows])

    def supersede(self, subject_key: str, entry: dict[str, Any]) -> dict[str, Any]:
        key = S.redact_secrets(subject_key)
        with self._connect() as conn:
            rows = conn.execute("SELECT id, path, title, subject_key, status, created_at, body FROM memories WHERE subject_key=? AND lower(status)='active'", (key,)).fetchall()
            for r in rows:
                note = self.storage_path / r[1]
                content = note.read_text(encoding="utf-8")
                content = re.sub(r'(?m)^status: .*$', 'status: "Superseded"', content, count=1)
                note.write_text(S.redact_secrets(content), encoding="utf-8")
                conn.execute("UPDATE memories SET status='Superseded' WHERE id=?", (r[0],))
        data = dict(entry)
        data["subject_key"] = key
        return self.remember(_redact_value(data))

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
        return {"status": "ok", "count": count, "index": S.redact_secrets(self.index_path.as_posix())}


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
