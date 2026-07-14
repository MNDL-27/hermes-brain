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

_PROPS: dict[str, dict[str, Any]] = {
    "tasks": {
        "title": {"title": {}},
        "Domain": {"select": {"options": [{"name": d, "color": "green"} for d in S.DOMAINS]}},
        "Status": {"status": {}},
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
        "Status": {"status": {}},
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
        "Status": {"status": {}},
        "Tags": {"multi_select": {}},
        "Confidence": {"select": {"options": [{"name": c, "color": "blue"} for c in S.CONFIDENCES]}},
        "Source Session": {"rich_text": {}},
        "Last Seen": {"date": {}},
    },
    "career": {
        "title": {"title": {}},
        "Domain": {"select": {"options": [{"name": d, "color": "green"} for d in S.DOMAINS]}},
        "Status": {"status": {}},
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


def ensure_brain(hermes_home: str | Path) -> dict[str, str]:
    cache_path = Path(hermes_home) / S.CACHE_FILE
    cached = _load_cache(cache_path)

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
                store.get_database(cached[cache_key])
                continue
            except Exception:
                logger.info("Cached database '%s' missing — recreating", key)

        db_id = _find_or_create_database(cached["parent_page_id"], display_name, _PROPS[key])
        cached[cache_key] = db_id
        _save_cache(cache_path, cached)

    logger.info("Notion brain ready: %d database(s)", len(S.DATABASES))
    return dict(cached)


def _load_cache(path: Path) -> dict[str, str]:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as exc:
        logger.debug("Failed to read cache: %s", exc)
    return {}


def _save_cache(path: Path, data: dict[str, str]) -> None:
    try:
        os.makedirs(path.parent, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    except Exception as exc:
        logger.warning("Failed to write cache: %s", exc)


def _find_or_create_parent(title: str) -> str:
    existing = store.search_page_by_title(title, object_type="page")
    if existing:
        return existing["id"]
    # Find any existing page to use as parent, or create under workspace root
    parent_id = _workspace_root()
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


def _workspace_root() -> str:
    """Find an existing page to use as parent for the Hermes Brain page.

    Searches for any existing page in the workspace via the Notion search API.
    """
    try:
        results = store.search_entries("", page_size=1)
        if results:
            return results[0]["id"]
    except Exception:
        pass
    raise RuntimeError(
        "No existing pages found in workspace. Create at least one page "
        "manually in Notion, or set HERMES_NOTION_PARENT_PAGE env var."
    )


def _find_or_create_database(parent_page_id: str, title: str, props: dict[str, Any]) -> str:
    existing = store.search_page_by_title(title, object_type="database")
    if existing:
        return existing["id"]
    db = store.create_database(parent_page_id, title, props)
    logger.info("Created database '%s': %s", title, db["id"])
    return db["id"]


def import_memory_files(hermes_home: str | Path, cache: dict[str, str]) -> int:
    memories_dir = Path(hermes_home) / "memories"
    imported = 0
    for fname in ("MEMORY.md", "USER.md"):
        fpath = memories_dir / fname
        if not fpath.exists():
            continue
        content = fpath.read_text(encoding="utf-8").strip()
        if not content:
            continue
        domain = "entities" if fname == "USER.md" else "memory"
        _write_entry(cache, domain, f"Imported: {fname}", content,
                     kind="note", status="active", confidence="medium",
                     tags=["imported", fname.lower().replace(".md", "")])
        imported += 1
    return imported


def _write_entry(cache: dict[str, str], domain: str, title: str,
                 content: str, **props: Any) -> None:
    db_key = f"db_{S.database_for_domain(domain)}"
    db_id = cache.get(db_key)
    if not db_id:
        logger.warning("No database for domain '%s'", domain)
        return
    store.create_database_page(
        database_id=db_id,
        properties={
            "title": store.title_property(title),
            "Domain": store.select_property(S.DOMAINS.get(domain, "Memory")),
            "Status": store.status_property(props.get("status", "active")),
            "Tags": store.multi_select_property(props.get("tags", [])),
            "Confidence": store.select_property(props.get("confidence", "medium")),
        },
    )


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
