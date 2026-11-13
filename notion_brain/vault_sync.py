"""Obsidian vault sync: Notion→vault bootstrap and vault→Notion ingest.

Both directions are explicit commands; nothing runs during provider startup.
The unified state file at ``$HERMES_HOME/vault_sync_state.json`` records
bootstrap page ids and ingest title hashes so re-runs are idempotent. The
legacy ``vault_notion_mirror_state.json`` is migrated on first read.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from . import bootstrap as notion_bootstrap
from . import schema as S
from . import store
from .adapters import (
    EntitlementError,
    ObsidianVaultAdapter,
    get_adapter,
    is_premium_entitled,
)

STATE_FILENAME = "vault_sync_state.json"
LEGACY_STATE_FILENAME = "vault_notion_mirror_state.json"
STATE_VERSION = 1
MAX_ERRORS = 10


def _home_path(home: str | Path) -> Path:
    return Path(home).expanduser()


def state_path(home: str | Path) -> Path:
    return _home_path(home) / STATE_FILENAME


def legacy_state_path(home: str | Path) -> Path:
    return _home_path(home) / LEGACY_STATE_FILENAME


def resolve_vault_path(vault: str | Path | None = None) -> Path | None:
    """Resolve the vault root: explicit path, HERMES_OBSIDIAN_VAULT, AGENT_BRAIN_VAULT."""
    if vault:
        return Path(vault).expanduser().resolve()
    for name in ("HERMES_OBSIDIAN_VAULT", "AGENT_BRAIN_VAULT"):
        value = os.environ.get(name, "").strip()
        if value:
            return Path(value).expanduser().resolve()
    return None


def empty_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "ingest": {"entries": {}, "last_run": ""},
        "bootstrap": {"page_ids": [], "last_bootstrap": ""},
    }


def load_state(home: str | Path) -> dict[str, Any]:
    """Load the unified state, migrating the legacy mirror state once."""
    data: dict[str, Any] = {}
    try:
        raw = json.loads(state_path(home).read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data = raw
    except (OSError, json.JSONDecodeError):
        data = {}
    if not data:
        try:
            legacy = json.loads(legacy_state_path(home).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            legacy = {}
        if isinstance(legacy, dict) and legacy:
            state = empty_state()
            state["ingest"]["entries"] = {
                str(k): str(v) for k, v in (legacy.get("entries") or {}).items()
            }
            state["ingest"]["last_run"] = str(legacy.get("last_run") or "")
            return state
    state = empty_state()
    ingest = data.get("ingest") or {}
    bootstrap = data.get("bootstrap") or {}
    if isinstance(ingest, dict):
        state["ingest"]["entries"] = {
            str(k): str(v) for k, v in (ingest.get("entries") or {}).items()
        }
        state["ingest"]["last_run"] = str(ingest.get("last_run") or "")
    if isinstance(bootstrap, dict):
        state["bootstrap"]["page_ids"] = [
            str(item) for item in (bootstrap.get("page_ids") or [])
        ]
        state["bootstrap"]["last_bootstrap"] = str(bootstrap.get("last_bootstrap") or "")
    return state


def save_state(home: str | Path, state: dict[str, Any]) -> None:
    """Atomically persist the sync state with restrictive permissions."""
    path = state_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def parse_memory_entries(text: str) -> list[dict[str, Any]]:
    """Split ``agents/memory.md`` on its ``### [YYYY-MM-DD] Title`` headings."""
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        heading = re.match(r"^###\s+(?:\[(\d{4}-\d{2}-\d{2})\]\s*)?(.+?)\s*$", line)
        if heading:
            if current and current["body"].strip():
                entries.append(current)
            current = {
                "date": heading.group(1) or "",
                "title": heading.group(2).strip(),
                "body": "",
            }
            continue
        if current is not None:
            current["body"] += line + "\n"
    if current and current["body"].strip():
        entries.append(current)
    return entries


def parse_journal_entries(text: str) -> list[dict[str, Any]]:
    """Split a journal note on its ``## [HH:MM] Agent: Title`` headings."""
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        heading = re.match(r"^##\s+(?:\[(\d{2}:\d{2})\]\s*)?(.+?)\s*$", line)
        if heading:
            if current and current["body"].strip():
                entries.append(current)
            current = {
                "time": heading.group(1) or "",
                "title": heading.group(2).strip(),
                "body": "",
            }
            continue
        if current is not None:
            current["body"] += line + "\n"
    if current and current["body"].strip():
        entries.append(current)
    return entries


def entry_hash(title: str, body: str) -> str:
    return hashlib.sha256(f"{title}\n{body}".encode("utf-8")).hexdigest()[:16]


def _is_template_stub(title: str) -> bool:
    """Skip the documented-format examples embedded in the notes themselves."""
    return "YYYY-MM-DD" in title or "HH:MM" in title


def build_ingest_entries(vault_root: str | Path) -> list[dict[str, Any]]:
    """Collect mirrorable entries with stable titles and truth levels."""
    root = Path(vault_root)
    collected: list[dict[str, Any]] = []

    memory_file = root / "agents" / "memory.md"
    if memory_file.is_file():
        for item in parse_memory_entries(memory_file.read_text(encoding="utf-8", errors="ignore")):
            prefix = f"[{item['date']}] " if item["date"] else ""
            title = f"Vault Memory · {prefix}{item['title']}"
            if _is_template_stub(title):
                continue
            collected.append({
                "title": title,
                "content": item["body"].strip(),
                "tags": ["vault", "mirror", "memory"],
                "truth": "certified",
            })

    journal_dir = root / "journal"
    if journal_dir.is_dir():
        for journal in sorted(journal_dir.glob("*.md")):
            day = journal.stem
            for item in parse_journal_entries(
                journal.read_text(encoding="utf-8", errors="ignore")
            ):
                stamp = f"{day} {item['time']}".strip()
                title = f"Vault Journal · {stamp} · {item['title']}"
                if _is_template_stub(title):
                    continue
                collected.append({
                    "title": title,
                    "content": item["body"].strip(),
                    "tags": ["vault", "mirror", "journal"],
                    "truth": "inferred",
                })

    return collected


def ingest(
    home: str | Path,
    vault_root: str | Path,
    *,
    dry_run: bool = False,
    provider: Any = None,
) -> dict[str, Any]:
    """Promote vault memory/journal entries into Notion with hash dedupe."""
    entries = build_ingest_entries(vault_root)
    state = load_state(home)
    seen: dict[str, str] = state["ingest"]["entries"]
    pending: list[tuple[dict[str, Any], str]] = []
    skipped = 0
    for item in entries:
        digest = entry_hash(item["title"], item["content"])
        if seen.get(item["title"]) == digest:
            skipped += 1
            continue
        pending.append((item, digest))

    result: dict[str, Any] = {
        "scanned": len(entries),
        "pending": len(pending),
        "skipped": skipped,
        "written": 0,
        "failed": 0,
        "errors": [],
        "dry_run": dry_run,
    }
    if dry_run or not pending:
        return result

    if provider is None:
        from .provider import NotionBrainProvider

        provider = NotionBrainProvider()
        provider.initialize("vault-sync", hermes_home=str(home), storage_adapter="notion")

    for item, digest in pending:
        try:
            entry = S.BrainEntry(
                domain="memory",
                title=item["title"],
                content=item["content"],
                kind="note",
                tags=item["tags"],
                source_session_id="vault-sync",
                truth=item["truth"],
            ).normalized()
            provider._store_entry(entry)
            seen[item["title"]] = digest
            result["written"] += 1
        except Exception as exc:
            result["failed"] += 1
            if len(result["errors"]) < MAX_ERRORS:
                result["errors"].append(
                    f"{item['title'][:60]}: {S.redact_secrets(str(exc))}"
                )

    state["ingest"]["last_run"] = datetime.now().isoformat(timespec="seconds")
    save_state(home, state)
    return result


def bootstrap(
    home: str | Path, vault_root: str | Path, *, dry_run: bool = False
) -> dict[str, Any]:
    """Export active Notion Memory rows into stable vault notes."""
    root = Path(vault_root)
    selected = get_adapter("obsidian", hermes_home=str(home), obsidian_vault=root)
    if not isinstance(selected, ObsidianVaultAdapter):
        raise EntitlementError("Obsidian vault adapter unavailable")
    adapter = selected
    cache = notion_bootstrap._load_cache(_home_path(home) / S.CACHE_FILE)
    database_id = str(cache.get("db_memory") or "")
    if not database_id:
        cache = notion_bootstrap.ensure_brain(str(home)) or {}
        database_id = str(cache.get("db_memory") or "")
    if not database_id:
        return {
            "scanned": 0,
            "exported": 0,
            "skipped": 0,
            "failed": 1,
            "errors": ["Memory database is unavailable"],
            "dry_run": dry_run,
        }

    rows = store.query_database(database_id, page_size=100)
    state = load_state(home)
    known = set(state["bootstrap"]["page_ids"])
    result: dict[str, Any] = {
        "scanned": len(rows),
        "exported": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    for row in rows:
        page_id = str(row.get("id") or "").strip()
        props = row.get("properties") or {}
        if not page_id or str(props.get("Status") or "active").casefold() != "active":
            continue
        if page_id in known or adapter.find(page_id) is not None:
            result["skipped"] += 1
            continue
        content = str(props.get("Content") or props.get("Summary") or "")
        if not content:
            try:
                content = store.page_body_text(page_id) or ""
            except Exception:
                content = ""
        payload = {
            "id": page_id,
            "title": str(row.get("title") or "Untitled"),
            "content": content,
            "subject_key": str(props.get("Subject Key") or ""),
            "status": "active",
            "truth": str(props.get("Truth") or "inferred"),
            "source_agent": str(props.get("Source Agent") or "unknown"),
            "source_session": str(props.get("Source Session") or ""),
            "created_at": str(row.get("created_time") or props.get("Last Seen") or ""),
            "domain": "memory",
            "kind": str(props.get("Kind") or "note"),
            "tags": props.get("Tags") or [],
        }
        if dry_run:
            result["exported"] += 1
            continue
        try:
            adapter.remember(payload)
            known.add(page_id)
            result["exported"] += 1
        except Exception as exc:
            result["failed"] += 1
            if len(result["errors"]) < MAX_ERRORS:
                result["errors"].append(
                    f"{page_id}: {S.redact_secrets(str(exc))}"
                )

    if not dry_run:
        state["bootstrap"]["page_ids"] = sorted(known)
        state["bootstrap"]["last_bootstrap"] = datetime.now().isoformat(timespec="seconds")
        save_state(home, state)
    return result


def status(home: str | Path, vault_root: str | Path | None = None) -> dict[str, Any]:
    """Report vault entitlement, health and last sync/bootstrap results."""
    vault = resolve_vault_path(vault_root)
    state = load_state(home)
    entitled = is_premium_entitled(home)
    result: dict[str, Any] = {
        "backend": "obsidian" if vault else "notion",
        "entitled": entitled,
        "vault_path": str(vault) if vault else "",
        "last_run": state["ingest"]["last_run"],
        "last_bootstrap": state["bootstrap"]["last_bootstrap"],
        "state_file": str(state_path(home)),
        "migrated_from_legacy": (
            legacy_state_path(home).is_file() and not state_path(home).is_file()
        ),
        "count": 0,
        "active": 0,
        "certified": 0,
        "schema_version": 0,
        "index": "",
    }
    if vault and entitled:
        try:
            adapter = get_adapter("obsidian", hermes_home=str(home), obsidian_vault=vault)
            result.update(adapter.health())
        except EntitlementError:
            result["entitled"] = False
        except Exception as exc:
            result["errors"] = [S.redact_secrets(str(exc))]
    return result
