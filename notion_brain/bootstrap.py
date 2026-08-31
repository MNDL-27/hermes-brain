"""One-time Notion workspace bootstrap for the Hermes brain.

Creates the ``Hermes Brain`` parent page and the required databases under it.
Caches page/database IDs in ``$HERMES_HOME/notion_brain.json``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from . import schema as S
from . import store

logger = logging.getLogger(__name__)

# Single source of truth: every Status option created across our 7 DBs must
# be a name listed in S.STATUSES. ``_STATUS_OPTIONS`` here must stay ⊆
# S.STATUSES — see ``_validate_status_options`` below.
_STATUS_OPTIONS = [{"name": "active", "color": "blue"},
                   {"name": "done", "color": "green"},
                   {"name": "needs_review", "color": "yellow"}]

_PROPS: dict[str, dict[str, Any]] = {
    "tasks": {
        "title": {"title": {}},
        "Domain": {"select": {"options": [{"name": d, "color": "green"} for d in S.DOMAINS]}},
        "Status": {"status": {"options": list(_STATUS_OPTIONS)}},
        "Priority": {"select": {"options": [
            {"name": "urgent", "color": "red"}, {"name": "high", "color": "orange"},
            {"name": "medium", "color": "yellow"}, {"name": "low", "color": "green"},
        ]}},
        "Tags": {"multi_select": {}},
        "Due": {"date": {}},
        "Project": {"rich_text": {}},
        "Confidence": {"select": {"options": [{"name": c, "color": "blue"} for c in S.CONFIDENCES]}},
        "Source Session": {"rich_text": {}},
        "Last Seen": {"date": {}},
    },
    "projects": {
        "title": {"title": {}},
        "Domain": {"select": {"options": [{"name": d, "color": "green"} for d in S.DOMAINS]}},
        "Status": {"status": {"options": list(_STATUS_OPTIONS)}},
        "Tags": {"multi_select": {}},
        "Confidence": {"select": {"options": [{"name": c, "color": "blue"} for c in S.CONFIDENCES]}},
        "Source Session": {"rich_text": {}},
        "Last Seen": {"date": {}},
    },
    "content": {
        "title": {"title": {}},
        "Domain": {"select": {"options": [{"name": d, "color": "green"} for d in S.DOMAINS]}},
        "Status": {"select": {"options": [
            {"name": "draft", "color": "blue"}, {"name": "published", "color": "green"},
            {"name": "scheduled", "color": "orange"}, {"name": "idea", "color": "purple"},
        ]}},
        "Platform": {"select": {}},
        "Tags": {"multi_select": {}},
        "Confidence": {"select": {"options": [{"name": c, "color": "blue"} for c in S.CONFIDENCES]}},
        "Source Session": {"rich_text": {}},
        "Last Seen": {"date": {}},
    },
    "research": {
        "title": {"title": {}},
        "Domain": {"select": {"options": [{"name": d, "color": "green"} for d in S.DOMAINS]}},
        "Status": {"status": {"options": list(_STATUS_OPTIONS)}},
        "Tags": {"multi_select": {}},
        "Confidence": {"select": {"options": [{"name": c, "color": "blue"} for c in S.CONFIDENCES]}},
        "Source Session": {"rich_text": {}},
        "Last Seen": {"date": {}},
    },
    "career": {
        "title": {"title": {}},
        "Domain": {"select": {"options": [{"name": d, "color": "green"} for d in S.DOMAINS]}},
        "Status": {"status": {"options": list(_STATUS_OPTIONS)}},
        "Tags": {"multi_select": {}},
        "Confidence": {"select": {"options": [{"name": c, "color": "blue"} for c in S.CONFIDENCES]}},
        "Source Session": {"rich_text": {}},
        "Last Seen": {"date": {}},
    },
    "entities": {
        "title": {"title": {}},
        "Kind": {"select": {"options": [
            {"name": "person", "color": "blue"}, {"name": "company", "color": "green"},
            {"name": "tool", "color": "purple"}, {"name": "project", "color": "orange"},
            {"name": "topic", "color": "pink"}, {"name": "preference", "color": "yellow"},
        ]}},
        "Tags": {"multi_select": {}},
        "Confidence": {"select": {"options": [{"name": c, "color": "blue"} for c in S.CONFIDENCES]}},
        "Source Session": {"rich_text": {}},
        "Last Seen": {"date": {}},
    },
    "memory": {
        "title": {"title": {}},
        "Domain": {"select": {"options": [{"name": d, "color": "green"} for d in S.DOMAINS]}},
        "Status": {"status": {"options": list(_STATUS_OPTIONS)}},
        "Kind": {"select": {"options": [
            {"name": "note", "color": "blue"}, {"name": "preference", "color": "yellow"},
            {"name": "lesson", "color": "green"}, {"name": "decision", "color": "orange"},
            {"name": "reminder", "color": "red"},
        ]}},
        "Tags": {"multi_select": {}},
        "Confidence": {"select": {"options": [{"name": c, "color": "blue"} for c in S.CONFIDENCES]}},
        "Source Session": {"rich_text": {}},
        "Last Seen": {"date": {}},
    },
}

SCHEMA_VERSION = 2

def _validate_status_options() -> None:
    """Fail loudly if a Status option name isn't in S.STATUSES.

    Notion's status-property writes reject unknown names with a 400 and the
    provider used to swallow those as "Saved" → silent failure. Catch the
    mistake at bootstrap time, before it costs a write.
    """
    for key, props in _PROPS.items():
        status = props.get("Status") or {}
        kind = next(iter(status), "")
        if kind != "status":
            continue
        opts = status.get(kind, {}).get("options")
        if not opts:
            continue
        bad = [o["name"] for o in opts if o.get("name") not in S.STATUSES]
        if bad:
            raise RuntimeError(
                f"bootstrap._PROPS['{key}']['Status'] has options {bad} "
                f"not in schema.STATUSES ({sorted(S.STATUSES)}). "
                f"Update _STATUS_OPTIONS or schema.STATUSES so they agree."
            )

_validate_status_options()

def ensure_brain(hermes_home: str | Path) -> dict[str, str]:
    home_expanded = Path(os.path.expanduser(str(hermes_home)))
    cache_path = home_expanded / S.CACHE_FILE
    cached = _load_cache(cache_path)
    try:
        cached_version = int(cached.get("schema_version") or 0)
    except (ValueError, TypeError):
        cached_version = 0
    if cached_version < SCHEMA_VERSION:
        logger.info("Cache is at schema_version=%d (current=%d); updating cache version",
                    cached_version, SCHEMA_VERSION)
        cached["schema_version"] = str(SCHEMA_VERSION)
        _save_cache(cache_path, cached)

    if cached.get("parent_page_id"):
        try:
            store.get_page(cached["parent_page_id"])
        except Exception:
            logger.info("Cached parent page missing — recreating")
            cached.clear()

    if not cached.get("parent_page_id"):
        parent = _find_or_create_parent(S.DEFAULT_PARENT_PAGE)
        cached["parent_page_id"] = parent
        _save_cache(cache_path, cached)

    db_prefix = "db_"
    for key, display_name in S.DATABASES.items():
        cache_key = f"{db_prefix}{key}"
        if cached.get(cache_key):
            try:
                db = store.get_database(cached[cache_key])
                _repair_database_schema(db, _PROPS[key], key)
                continue
            except Exception:
                logger.info("Cached database '%s' missing or unreachable — resolving live ID", key)
                cached.pop(cache_key, None)

        db_id = _find_existing_database(cached["parent_page_id"], display_name)
        if not db_id:
            raise RuntimeError(
                f"Cannot find existing '{display_name}' database. "
                "No data was changed. Open that database in Notion, choose "
                "••• → Connections, add your integration, then rerun the installer."
            )
        cached[cache_key] = db_id
        _save_cache(cache_path, cached)

    logger.info("Notion brain ready: %d database(s)", len(S.DATABASES))
    return dict(cached)

def reset_databases(
    hermes_home: str | Path,
    *,
    only: set[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> list[str]:
    """Archive/recreate cached DBs whose schema does not match _PROPS.

    This removes stale Notion status options that PATCH cannot delete. It does
    not migrate pages; Notion keeps them under archived DBs.
    """
    cache_path = Path(hermes_home) / S.CACHE_FILE
    cached = _load_cache(cache_path)
    parent_id = cached.get("parent_page_id") or ""
    reset: list[str] = []
    to_replace: list[tuple[str, str, str]] = []  # (key, old_db_id, display_name)

    for key, display_name in S.DATABASES.items():
        if only and key not in only:
            continue
        db_id = cached.get(f"db_{key}")
        if not db_id:
            continue
        try:
            db = store.get_database(db_id)
        except Exception:
            logger.info("Cached database '%s' unreachable — recreating", key)
            cached.pop(f"db_{key}", None)
            reset.append(key)
            continue
        if force or not _database_schema_matches(db, _PROPS[key]):
            reset.append(key)
            if not dry_run:
                to_replace.append((key, db_id, display_name))

    if to_replace and not dry_run:
        # Create replacements BEFORE archiving old databases
        # so failure leaves original intact
        for key, old_db_id, display_name in to_replace:
            new_db_id = _find_or_create_database(parent_id, display_name, _PROPS[key])
            try:
                store.archive_database(old_db_id)
            except Exception as exc:
                logger.warning("Could not archive old database %s: %s", old_db_id, S.redact_secrets(str(exc)))
            cached[f"db_{key}"] = new_db_id

        cached["schema_version"] = str(SCHEMA_VERSION)
        _save_cache(cache_path, cached)
    elif reset and not dry_run:
        cached["schema_version"] = str(SCHEMA_VERSION)
        _save_cache(cache_path, cached)
        ensure_brain(hermes_home)
    return reset

def _database_schema_matches(db: dict[str, Any], expected: dict[str, Any]) -> bool:
    actual = db.get("properties") or {}
    for name, spec in expected.items():
        current = actual.get(name)
        if not current:
            return False
        expected_type = next(iter(spec))
        if current.get("type") != expected_type:
            return False
        expected_opts = spec.get(expected_type, {}).get("options")
        if expected_opts is not None:
            actual_opts = current.get(expected_type, {}).get("options", [])
            if {o.get("name") for o in actual_opts} != {o.get("name") for o in expected_opts}:
                return False
    return True

def get_url(hermes_home: str | Path, *, db: bool = False) -> str:
    """Print Notion URL(s) for the parent page and (optionally) every DB.

    Reads ``$HERMES_HOME/notion_brain.json``, fetches each ID, and returns the
    ``url`` field Notion returns alongside the resource.
    """
    cache_path = Path(hermes_home) / S.CACHE_FILE
    cached = _load_cache(cache_path)
    lines: list[str] = []
    parent_id = cached.get("parent_page_id", "")
    if parent_id:
        try:
            page = store.get_page(parent_id)
            url = page.get("url") or ""
            if url:
                title = page.get("title") or "Hermes Brain"
                lines.append(f"{title}\t{url}")
        except Exception as exc:
            logger.debug("Could not fetch parent page %s: %s", parent_id, S.redact_secrets(str(exc)))
    if db:
        for key, db_id in cached.items():
            if not key.startswith("db_") or not db_id:
                continue
            try:
                d = store.get_database(db_id)
                url = d.get("url", "")
                title = (d.get("title") or [{}])[0].get("plain_text", key)
                if url:
                    lines.append(f"{title}\t{url}")
            except Exception as exc:
                logger.debug("Could not fetch database %s: %s", db_id, S.redact_secrets(str(exc)))
    return "\n".join(lines)

def wipe_database_rows(
    hermes_home: str | Path,
    *,
    databases: set[str] | None = None,
    filter_fn: Any | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Wipe / purge rows from specified Notion databases to prevent prompt pollution.

    Targets noisy entries in Entities, Tasks, and Projects (or custom selection).
    """
    target_dbs = databases or {"entities", "tasks", "projects"}
    cached = _load_cache(Path(hermes_home) / S.CACHE_FILE)
    deleted_counts: dict[str, int] = {}

    for key in target_dbs:
        db_id = cached.get(f"db_{key}")
        if not db_id:
            continue
        try:
            entries = store.query_database(db_id, page_size=100)
        except Exception as exc:
            logger.warning("Could not query DB %s during wipe: %s", key, S.redact_secrets(str(exc)))
            continue

        count = 0
        for entry in entries:
            page_id = entry.get("id")
            if not page_id:
                continue
            if filter_fn and not filter_fn(entry):
                continue
            if not dry_run:
                try:
                    store.delete_page(page_id)
                except Exception as exc:
                    logger.warning("Could not delete page %s: %s", page_id, S.redact_secrets(str(exc)))
                    continue
            count += 1
        deleted_counts[key] = count

    return deleted_counts


def health_report(hermes_home: str | Path) -> str:
    """One-line-per-DB summary: schema match, entry count, last entry, latest sync."""
    cached = _load_cache(Path(hermes_home) / S.CACHE_FILE)
    parent_id = cached.get("parent_page_id", "")
    lines: list[str] = []
    if not parent_id:
        return "error: no parent page cached; run `python -m notion_brain reset`"
    try:
        parent = store.get_page(parent_id)
        title = parent.get("title") or "Hermes Brain"
        lines.append(f"parent: {title}  url={parent.get('url','')}")
    except Exception as exc:
        lines.append(f"parent: ERROR fetching {parent_id}: {S.redact_secrets(str(exc))}")
    for key in S.DATABASES:
        db_id = cached.get(f"db_{key}")
        if not db_id:
            lines.append(f"  {key:<10}  MISSING (no cache entry)")
            continue
        try:
            db = store.get_database(db_id)
            match = _database_schema_matches(db, _PROPS[key])
            schema = "schema=ok" if match else "schema=MISMATCH"
            entries = store.query_database(db_id, page_size=100, sorts=[{"property": "Last Seen", "direction": "descending"}])
            count = len(entries)
            last = entries[0].get("created_time", "")[:19] if entries else "(empty)"
            url = db.get("url", "")
            lines.append(f"  {key:<10}  {schema}  entries={count:<3}  last={last}  {url}")
        except Exception as exc:
            msg = S.redact_secrets(str(exc))
            if "404" in msg and "shared with your integration" in msg:
                bot = store.get_bot_name()
                lines.append(
                    f"  {key:<10}  NOT SHARED: integration \"{bot}\" cannot see this database. "
                    f"Fix: open the DB in Notion → ••• → Connections → add \"{bot}\"."
                )
            else:
                lines.append(f"  {key:<10}  ERROR: {msg}")
    return "\n".join(lines)

def _repair_database_schema(db: dict, expected: dict[str, Any], key: str) -> None:
    """Add any properties that are missing from an existing Notion database.

    PATCH /databases can only ADD properties — it cannot rename, remove, or
    change a property's type. So this is a one-way best-effort: existing
    broken DBs gain the props they're missing, but the Notion defaults that
    ``{"status": {}}`` produced (e.g. "Not started"/"In progress"/"Done")
    stay alongside our explicit options. The provider always writes its
    canonical names, so the extra defaults are inert clutter, not a bug.
    """
    actual = (db.get("properties") or {})
    missing = {pname: spec for pname, spec in expected.items() if pname not in actual}
    if not missing:
        return
    try:
        store.update_database(db["id"], missing)
        logger.info("Repaired '%s' database schema: added %d missing prop(s) (%s)",
                    key, len(missing), ", ".join(missing))
    except Exception as exc:
        logger.warning("Could not repair '%s' database schema: %s", key, S.redact_secrets(str(exc)))

def _load_cache(path: Path) -> dict[str, str]:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as exc:
        logger.debug("Failed to read cache: %s", S.redact_secrets(str(exc)))
    return {}

def _save_cache(path: Path, data: dict[str, str]) -> None:
    try:
        os.makedirs(path.parent, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    except Exception as exc:
        logger.warning("Failed to write cache: %s", S.redact_secrets(str(exc)))

def _find_or_create_parent(title: str) -> str:
    existing = store.search_page_by_title(title, object_type="page")
    if existing:
        return existing["id"]
    parent_override = os.environ.get("HERMES_NOTION_PARENT_PAGE", "").strip()
    if parent_override:
        parent_id = parent_override
    else:
        parent_id = _workspace_root_or_fail()
    page = store.create_page(
        parent_id,
        properties=store.title_property(title),
        children=[{
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": "Long-term memory store for Hermes agent."}}]},
        }],
    )
    page_id = page["id"]
    logger.info("Created parent page '%s': %s", title, page_id)
    return page_id

def _workspace_root_or_fail() -> str:
    """Pick the parent page for the Hermes Brain page.

    Resolution order:
      1. ``HERMES_NOTION_PARENT_PAGE`` env var (UUID/ID of any page).
      2. Search for existing "Hermes Brain" page by exact title.
      3. Raise with a message to create a parent page manually.
    """
    env = os.environ.get("HERMES_NOTION_PARENT_PAGE", "").strip()
    if env:
        return env
    # Search for existing Hermes Brain page by exact title
    try:
        existing = store.search_page_by_title("Hermes Brain", object_type="page")
        if existing:
            return existing["id"]
    except Exception:
        pass
    raise RuntimeError(
        "Notion brain needs an existing parent page in your workspace but none "
        "was found via search. Either: (1) create any page in Notion, then rerun; "
        "(2) set HERMES_NOTION_PARENT_PAGE to the page ID; or (3) invite the "
        "notion_brain integration to a page first so search can see it."
    )

def _find_existing_database(parent_page_id: str, title: str) -> str:
    """Locate an existing database WITHOUT creating one.

    Resolution order:
      1. Children of the parent page (deterministic, no search index).
      2. Workspace /search by title (case-insensitive exact match).
    Returns "" when nothing is found.
    """
    try:
        for block in store.get_block_children(parent_page_id, page_size=100):
            if block.get("type") == "child_database":
                db_title = ((block.get("child_database") or {}).get("title") or "").strip()
                if db_title.lower() == title.strip().lower():
                    return block["id"]
    except Exception as exc:
        logger.debug("Child-block scan for '%s' failed: %s", title, S.redact_secrets(str(exc)))

    try:
        existing = store.search_page_by_title(title, object_type="database")
        if existing:
            return existing["id"]
    except Exception as exc:
        logger.debug("Search for database '%s' failed: %s", title, S.redact_secrets(str(exc)))
    return ""


def _find_or_create_database(parent_page_id: str, title: str, props: dict[str, Any]) -> str:
    # Deterministic first: scan the parent page's children for a
    # child_database block with a matching title. Notion's /search index
    # misses databases (indexing delay / relevance ranking), which made
    # re-bootstrap create duplicates ("Projects 1", "Projects 2").
    db_id = _find_existing_database(parent_page_id, title)
    if db_id:
        return db_id
    db = store.create_database(parent_page_id, title, props)
    logger.info("Created database '%s': %s", title, db["id"])
    return db["id"]

def read_memory_from_disk(hermes_home: str | Path) -> str:
    fpath = Path(hermes_home) / "memories" / "MEMORY.md"
    if fpath.exists():
        return fpath.read_text(encoding="utf-8")
    return ""

def read_user_from_disk(hermes_home: str | Path) -> str:
    fpath = Path(hermes_home) / "memories" / "USER.md"
    if fpath.exists():
        return fpath.read_text(encoding="utf-8")
    return ""

def write_memory_to_disk(hermes_home: str | Path, entries: list[dict[str, Any]]) -> None:
    """Rebuild MEMORY.md from a list of entries.

    Entries should be flattened results from Notion.
    """
    memories_dir = Path(hermes_home) / "memories"
    memories_dir.mkdir(parents=True, exist_ok=True)
    fpath = memories_dir / "MEMORY.md"

    lines = ["# Memory\n"]
    for e in entries:
        title = e.get("title", "Untitled")
        props = e.get("properties", {})
        domain = props.get("Domain", "Memory")
        kind = props.get("Kind", "note")
        tags = props.get("Tags", [])
        # Defensive: tolerate str, None items, or non-list shapes from Notion
        if not isinstance(tags, list):
            tags = [tags] if tags else []
        tags = [str(t) for t in tags if t]
        content = props.get("Content", "") or title

        # Simple frontmatter-like block for each entry
        lines.append("---")
        lines.append(f"name: {title}")
        lines.append(f"domain: {domain}")
        lines.append(f"kind: {kind}")
        lines.append(f"tags: {', '.join(tags)}")
        lines.append("---")
        lines.append(f"{content}\n")

    fpath.write_text("\n".join(lines), encoding="utf-8")

def write_user_to_disk(hermes_home: str | Path, entries: list[dict[str, Any]]) -> None:
    """Rebuild USER.md from a list of entries (usually entities with Kind=preference)."""
    memories_dir = Path(hermes_home) / "memories"
    memories_dir.mkdir(parents=True, exist_ok=True)
    fpath = memories_dir / "USER.md"

    lines = ["# User Profile\n"]
    for e in entries:
        title = e.get("title", "User Preference")
        props = e.get("properties", {})
        content = props.get("Content", "") or title

        lines.append(f"## {title}")
        lines.append(f"{content}\n")

    fpath.write_text("\n".join(lines), encoding="utf-8")
