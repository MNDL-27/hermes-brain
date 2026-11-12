"""Local SQLite read-through cache for active Memory rows (RET-02).

The file lives at ``<hermes_home>/brain_cache.db`` (default ``~/.hermes``).
Prefetch reads it with zero Notion calls. Successful cold reads populate
the cache; background writes still go to Notion and mirror accepted rows.

Schema is versioned in ``schema_meta``. A newer on-disk version is left
untouched (no destructive downgrade). Writes commit through a single
transaction so a crash cannot leave a half-applied row.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

from . import schema as S

logger = logging.getLogger(__name__)

CACHE_FILENAME = "brain_cache.db"
SCHEMA_VERSION = 3

# Kinds that belong in the pinned lane (identity, warnings, decisions).
PINNED_KINDS = frozenset(
    {
        "decision",
        "warning",
        "identity",
        "preference",
        "pinned",
        "critical",
    }
)

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_rows (
    page_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'note',
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    last_seen TEXT NOT NULL DEFAULT '',
    truth TEXT NOT NULL DEFAULT 'inferred',
    subject_key TEXT NOT NULL DEFAULT '',
    source_agent TEXT NOT NULL DEFAULT 'unknown',
    source_session TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    updated_at REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_memory_rows_active_seen
    ON memory_rows (status, last_seen DESC);
"""


def cache_path(hermes_home: str | Path | None = None) -> Path:
    """Resolve the cache file. Empty home falls back to ``~/.hermes``."""
    home = str(hermes_home or "").strip() or os.path.expanduser("~/.hermes")
    return Path(home) / CACHE_FILENAME


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=1.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=1000")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> bool:
    """Apply schema v1 once. Return False without mutation for newer schemas."""
    meta_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'"
    ).fetchone()
    if meta_exists:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()
        try:
            existing = int(row["value"]) if row is not None else 0
        except (TypeError, ValueError):
            existing = 0
        if existing > SCHEMA_VERSION:
            logger.warning(
                "brain_cache: on-disk schema %s is newer than %s; leaving file unchanged",
                existing,
                SCHEMA_VERSION,
            )
            return False
    conn.executescript(_CREATE_SQL)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(memory_rows)")}
    if "truth" not in columns:
        conn.execute("ALTER TABLE memory_rows ADD COLUMN truth TEXT NOT NULL DEFAULT 'inferred'")
        conn.commit()
    if "subject_key" not in columns:
        conn.execute("ALTER TABLE memory_rows ADD COLUMN subject_key TEXT NOT NULL DEFAULT ''")
        conn.commit()
    if "source_agent" not in columns:
        conn.execute("ALTER TABLE memory_rows ADD COLUMN source_agent TEXT NOT NULL DEFAULT 'unknown'")
        conn.commit()
    if "source_session" not in columns:
        conn.execute("ALTER TABLE memory_rows ADD COLUMN source_session TEXT NOT NULL DEFAULT ''")
        conn.commit()
    if "created_at" not in columns:
        conn.execute("ALTER TABLE memory_rows ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        conn.commit()
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'version'").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO schema_meta (key, value) VALUES ('version', ?)",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
        return True
    try:
        existing = int(row["value"])
    except (TypeError, ValueError):
        existing = 0
    if existing < SCHEMA_VERSION:
        conn.execute(
            "UPDATE schema_meta SET value = ? WHERE key = 'version'",
            (str(SCHEMA_VERSION),),
        )
        conn.commit()
    return True


def _safe(exc: BaseException) -> str:
    return S.redact_secrets(str(exc))


def list_active(
    hermes_home: str | Path | None,
    *,
    limit: int = 10,
) -> list[dict[str, Any]] | None:
    """Return active memory rows, newest ``last_seen`` first.

    ``None`` means there is no usable cache (missing file or unreadable).
    Callers fall through to Notion in that case. An empty list means a
    completed population has no active rows — that is a hit, not a miss.
    A schema-only file from interrupted initialization remains a miss.
    """
    path = cache_path(hermes_home)
    try:
        if not path.exists():
            return None
        conn = _connect(path)
    except (sqlite3.Error, OSError) as exc:
        logger.warning("brain_cache: open failed: %s", _safe(exc))
        return None
    try:
        if not _ensure_schema(conn):
            return None
        initialized = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'initialized'"
        ).fetchone()
        # Legacy caches predate the marker, but an accepted row proves that
        # a write completed. An empty schema alone does not prove a read did.
        if not (initialized and initialized["value"] == "1") and not conn.execute(
            "SELECT 1 FROM memory_rows LIMIT 1"
        ).fetchone():
            return None
        rows = conn.execute(
            """
            SELECT page_id, title, kind, content, status, last_seen, truth, subject_key,
                   source_agent, source_session, created_at
            FROM memory_rows
            WHERE status = 'active'
            ORDER BY last_seen DESC, truth = 'certified' DESC, updated_at DESC, page_id ASC
            LIMIT ?
            """,
            (max(0, int(limit)),),
        ).fetchall()
    except sqlite3.Error as exc:
        logger.warning("brain_cache: read failed: %s", _safe(exc))
        return None
    finally:
        conn.close()
    result: list[dict[str, Any]] = []
    for row in rows:
        props: dict[str, Any] = {
            "Kind": row["kind"] or "note",
            "Content": row["content"] or "",
            "Status": row["status"] or "active",
            "Last Seen": row["last_seen"] or "",
            "Truth": row["truth"] or "inferred",
        }
        if row["subject_key"]:
            props["Subject Key"] = row["subject_key"]
        if row["source_agent"] and row["source_agent"] != "unknown":
            props["Source Agent"] = row["source_agent"]
        if row["source_session"]:
            props["Source Session"] = row["source_session"]
        if row["created_at"]:
            props["Created At"] = row["created_at"]
        result.append({
            "id": row["page_id"],
            "title": row["title"] or "Untitled",
            "properties": props,
        })
    return result


def upsert_active(
    hermes_home: str | Path | None,
    *,
    page_id: str,
    title: str,
    kind: str,
    content: str,
    status: str = "active",
    last_seen: str = "",
    truth: str = "inferred",
    subject_key: str = "",
    source_agent: str = "unknown",
    source_session: str = "",
    created_at: str = "",
) -> bool:
    """Insert or replace one memory row. Returns False on a cache failure.

    Content, title and provenance are secret-redacted before they hit disk.
    Non-active status is stored so a later read of active rows drops the page.
    Empty/unknown provenance never overwrites a known stored value.
    """
    pid = (page_id or "").strip()
    if not pid:
        return False
    safe_title = S.redact_secrets(title or "")
    safe_content = S.redact_secrets(content or "")
    safe_subject_key = S.redact_secrets(subject_key or "").strip()
    safe_kind = (kind or "note").strip()[:80] or "note"
    safe_status = (status or "active").strip().lower() or "active"
    safe_source_agent = S.redact_secrets(source_agent or "").strip() or "unknown"
    safe_source_session = S.redact_secrets(source_session or "").strip()
    safe_created_at = S.redact_secrets(created_at or "").strip()
    seen = last_seen or ""
    path = cache_path(hermes_home)
    try:
        conn = _connect(path)
    except sqlite3.Error as exc:
        logger.warning("brain_cache: open for write failed: %s", _safe(exc))
        return False
    try:
        if not _ensure_schema(conn):
            return False
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO memory_rows (
                page_id, title, kind, content, status, last_seen, updated_at, truth,
                subject_key, source_agent, source_session, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(page_id) DO UPDATE SET
                title = excluded.title,
                kind = excluded.kind,
                content = excluded.content,
                status = excluded.status,
                last_seen = excluded.last_seen,
                updated_at = excluded.updated_at,
                truth = excluded.truth,
                subject_key = CASE WHEN excluded.subject_key = ''
                    THEN memory_rows.subject_key ELSE excluded.subject_key END,
                source_agent = CASE WHEN excluded.source_agent = 'unknown'
                    THEN memory_rows.source_agent ELSE excluded.source_agent END,
                source_session = CASE WHEN excluded.source_session = ''
                    THEN memory_rows.source_session ELSE excluded.source_session END,
                created_at = CASE WHEN excluded.created_at = ''
                    THEN memory_rows.created_at ELSE excluded.created_at END
            """,
            (pid, safe_title, safe_kind, safe_content, safe_status, seen, time.time(),
             truth if truth in {"inferred", "certified"} else "inferred", safe_subject_key,
             safe_source_agent, safe_source_session, safe_created_at),
        )
        conn.execute("INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('initialized', '1')")
        conn.commit()
    except sqlite3.Error as exc:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        logger.warning("brain_cache: write failed: %s", _safe(exc))
        return False
    finally:
        conn.close()
    return True


def populate_from_read(
    hermes_home: str | Path | None, entries: list[dict[str, Any]]
) -> bool:
    """Atomically cache a successful read, including an intentional empty one.

    Existing rows win over the remote snapshot: an accepted write may have
    arrived while the cold read was in progress. Neither empty snapshots nor
    insertion failures erase those writes. The initialization marker commits
    with the complete batch, so a failed first population remains a cache miss.
    """
    values = []
    now = time.time()
    for entry in entries:
        page_id = str(entry.get("id") or "").strip()
        if not page_id:
            logger.warning("brain_cache: read population skipped a result without a page id")
            return False
        props = entry.get("properties") or {}
        status = str(props.get("Status") or "active").strip().lower()
        if status != "active":
            continue
        truth = str(props.get("Truth") or "inferred").lower()
        values.append((
            S.redact_secrets(page_id),
            S.redact_secrets(str(entry.get("title") or "Untitled")),
            S.redact_secrets(str(props.get("Kind") or "note"))[:80],
            S.redact_secrets(str(props.get("Content") or props.get("Summary") or "")),
            status,
            S.redact_secrets(str(props.get("Last Seen") or entry.get("last_edited_time") or entry.get("created_time") or "")),
            now,
            truth if truth in {"inferred", "certified"} else "inferred",
            S.redact_secrets(str(props.get("Subject Key") or "")).strip(),
            S.redact_secrets(str(props.get("Source Agent") or "unknown")).strip() or "unknown",
            S.redact_secrets(str(props.get("Source Session") or "")).strip(),
            S.redact_secrets(str(entry.get("created_time") or "")).strip(),
        ))
    try:
        conn = _connect(cache_path(hermes_home))
    except (sqlite3.Error, OSError) as exc:
        logger.warning("brain_cache: open for population failed: %s", _safe(exc))
        return False
    try:
        if not _ensure_schema(conn):
            return False
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            """
            INSERT INTO memory_rows (
                page_id, title, kind, content, status, last_seen, updated_at, truth,
                subject_key, source_agent, source_session, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(page_id) DO UPDATE SET
                source_agent = CASE
                    WHEN memory_rows.source_agent = 'unknown'
                         AND excluded.source_agent != 'unknown'
                    THEN excluded.source_agent ELSE memory_rows.source_agent END,
                source_session = CASE
                    WHEN memory_rows.source_session = ''
                    THEN excluded.source_session ELSE memory_rows.source_session END,
                created_at = CASE
                    WHEN memory_rows.created_at = ''
                    THEN excluded.created_at ELSE memory_rows.created_at END
            """,
            values,
        )
        conn.execute("INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('initialized', '1')")
        conn.commit()
    except sqlite3.Error as exc:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        logger.warning("brain_cache: population failed: %s", _safe(exc))
        return False
    finally:
        conn.close()
    return True


def is_pinned_kind(kind: str | None) -> bool:
    return (kind or "").strip().lower() in PINNED_KINDS
