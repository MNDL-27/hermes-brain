#!/usr/bin/env python3
"""Mirror the Obsidian vault's memory + journal into the Notion Hermes Brain.

The vault is the primary write surface; Notion is the fallback. Nothing in
hermes-brain does this today: ``get_adapter()`` returns a single storage
backend, so entries written to one store never appear in the other. This runs
out of band on a timer and pushes deltas vault -> Notion only.

Scope is deliberately narrow: ``agents/memory.md`` (durable facts) and
``journal/*.md`` (daily logs). Knowledge notes and project READMEs are not
memory-shaped and would only add noise to the databases.

Writes go through ``NotionBrainProvider._store_entry`` rather than the raw
store, so entries get the same normalisation, secret redaction, subject-key
inference, and title-based dedupe as everything else in the brain.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
VAULT = Path(os.environ.get("AGENT_BRAIN_VAULT", "/mnt/hdd/appdata/agent-brain/vault"))
BRAIN_SRC = Path(os.environ.get("HERMES_BRAIN_SRC", "/home/protik/projects/hermes-brain"))
STATE_FILE = HERMES_HOME / "vault_notion_mirror_state.json"

sys.path.insert(0, str(BRAIN_SRC))


def _load_notion_key() -> None:
    if os.environ.get("NOTION_API_KEY"):
        return
    env_file = HERMES_HOME / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        match = re.match(r"^\s*NOTION_API_KEY\s*=\s*(.+)$", line)
        if match:
            os.environ["NOTION_API_KEY"] = match.group(1).strip().strip('"').strip("'")
            return


_load_notion_key()
os.environ.setdefault("HERMES_HOME", str(HERMES_HOME))

from notion_brain import schema as S  # noqa: E402
from notion_brain.provider import NotionBrainProvider  # noqa: E402


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    try:
        STATE_FILE.chmod(0o600)
    except OSError:
        pass


def parse_memory_entries(text: str) -> list[dict]:
    """Split ``agents/memory.md`` on its ``### [YYYY-MM-DD] Title`` headings."""
    entries: list[dict] = []
    current: dict | None = None
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


def parse_journal_entries(text: str) -> list[dict]:
    """Split a journal note on its ``## [HH:MM] Agent: Title`` headings."""
    entries: list[dict] = []
    current: dict | None = None
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
    """Skip the documented-format examples embedded in the notes themselves.

    ``agents/memory.md`` opens with a template block titled
    ``[YYYY-MM-DD] Memory Title``. Mirroring it would create a junk Notion row
    on every run, so anything still carrying the placeholder date is dropped.
    """
    return "YYYY-MM-DD" in title or "HH:MM" in title


def build_entries() -> list[dict]:
    """Collect mirrorable entries with stable, dedupe-friendly titles."""
    collected: list[dict] = []

    memory_file = VAULT / "agents" / "memory.md"
    if memory_file.is_file():
        for item in parse_memory_entries(memory_file.read_text(errors="ignore")):
            prefix = f"[{item['date']}] " if item["date"] else ""
            title = f"Vault Memory · {prefix}{item['title']}"
            if _is_template_stub(title):
                continue
            collected.append({
                "title": title,
                "content": item["body"].strip(),
                "tags": ["vault", "mirror", "memory"],
            })

    journal_dir = VAULT / "journal"
    if journal_dir.is_dir():
        for journal in sorted(journal_dir.glob("*.md")):
            day = journal.stem
            for item in parse_journal_entries(journal.read_text(errors="ignore")):
                stamp = f"{day} {item['time']}".strip()
                title = f"Vault Journal · {stamp} · {item['title']}"
                if _is_template_stub(title):
                    continue
                collected.append({
                    "title": title,
                    "content": item["body"].strip(),
                    "tags": ["vault", "mirror", "journal"],
                })

    return collected


def mirror(dry_run: bool = False) -> dict:
    entries = build_entries()
    state = load_state()
    seen: dict[str, str] = state.get("entries", {})

    pending = []
    skipped = 0
    for item in entries:
        digest = entry_hash(item["title"], item["content"])
        if seen.get(item["title"]) == digest:
            skipped += 1
            continue
        item["_digest"] = digest
        pending.append(item)

    result = {
        "scanned": len(entries),
        "pending": len(pending),
        "skipped": skipped,
        "written": 0,
        "failed": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    if dry_run or not pending:
        if not dry_run:
            state["last_run"] = datetime.now().isoformat(timespec="seconds")
            state["entries"] = seen
            save_state(state)
        return result

    provider = NotionBrainProvider()
    provider.initialize("vault-mirror", hermes_home=str(HERMES_HOME))

    for item in pending:
        try:
            entry = S.BrainEntry(
                domain="memory",
                title=item["title"],
                content=item["content"],
                kind="note",
                tags=item["tags"],
                source_session_id="vault-mirror",
                truth="certified",
            ).normalized()
            provider._store_entry(entry)
            seen[item["title"]] = item["_digest"]
            result["written"] += 1
        except Exception as exc:  # keep going; one bad note must not stall the run
            result["failed"] += 1
            if len(result["errors"]) < 10:
                result["errors"].append(f"{item['title'][:60]}: {type(exc).__name__}: {exc}")

    state["entries"] = seen
    state["last_run"] = datetime.now().isoformat(timespec="seconds")
    save_state(state)
    return result


if __name__ == "__main__":
    outcome = mirror(dry_run="--dry-run" in sys.argv)
    print(json.dumps(outcome, indent=2))
    raise SystemExit(1 if outcome["failed"] else 0)
