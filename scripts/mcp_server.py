#!/usr/bin/env python3
"""Read-only MCP server exposing the Hermes Brain (Notion) to other agents.

Command Code has no notion of hermes-brain's provider interface, so this wraps
the parts of ``notion_brain.store`` that are safe to call out of band: search,
database listing, and single-page reads.

It is deliberately read-only. Writes go through the Hermes agent, which owns
classification, dedupe, and the background sync worker; letting a second agent
write rows directly would race that pipeline and bypass its secret redaction.

Auth comes from NOTION_API_KEY (read from ~/.hermes/.env if not already set).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
BRAIN_SRC = Path(os.environ.get("HERMES_BRAIN_SRC", "/home/protik/projects/hermes-brain"))


def _load_env() -> None:
    """Pull NOTION_API_KEY out of the Hermes env file when not exported."""
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


_load_env()
os.environ.setdefault("HERMES_HOME", str(HERMES_HOME))
sys.path.insert(0, str(BRAIN_SRC))

from notion_brain import bootstrap, store  # noqa: E402

DBS = ("memory", "tasks", "projects", "content", "research", "career", "entities")
_db_ids: dict[str, str] | None = None


def db_ids() -> dict[str, str]:
    """Resolve (and cache) the live Notion database ids under the brain page."""
    global _db_ids
    if _db_ids is None:
        resolved = bootstrap.ensure_brain(str(HERMES_HOME))
        _db_ids = {k: resolved[f"db_{k}"] for k in DBS if f"db_{k}" in resolved}
    return _db_ids


def _row_title(row: dict) -> str:
    props = row.get("properties") or {}
    for key in ("Name", "Title", "title", "Summary", "Content"):
        value = props.get(key)
        if isinstance(value, list):
            return " ".join(str(part) for part in value)
        if isinstance(value, str) and value.strip():
            return value
    return str(row.get("title") or row.get("id", ""))


def search(query: str, limit: int = 8) -> list[dict]:
    return [
        {
            "id": row.get("id"),
            "title": _row_title(row)[:200],
            "content": str((row.get("properties") or {}).get("Content") or row.get("content") or "")[:1500],
        }
        for row in store.search_entries(query, page_size=max(1, min(limit, 25)))
    ]


def list_entries(database: str, limit: int = 50) -> list[dict]:
    ids = db_ids()
    if database not in ids:
        raise ValueError(f"unknown database '{database}'; expected one of {', '.join(sorted(ids))}")
    rows = store.query_database(ids[database], page_size=100)
    return [{"id": r.get("id"), "title": _row_title(r)[:200]} for r in rows[:limit]]


def read_page(page_id: str, limit: int = 6000) -> str:
    return store.page_body_text(page_id)[:limit]


# --- Obsidian vault (second brain) ----------------------------------------
# A separate, git-versioned Obsidian vault on the same machine. It holds the
# homelab topology, service maps, and per-project notes. Read from disk rather
# than the Obsidian REST API: the container is often down, the files are not.
VAULT = Path(os.environ.get("AGENT_BRAIN_VAULT", "/mnt/hdd/appdata/agent-brain/vault"))


def _vault_notes() -> list[Path]:
    if not VAULT.is_dir():
        return []
    return sorted(
        p for p in VAULT.rglob("*.md")
        if not any(part.startswith(".") for part in p.relative_to(VAULT).parts)
    )


def vault_search(query: str, limit: int = 8) -> list[dict]:
    terms = [t for t in re.split(r"\s+", query.lower()) if t]
    if not terms:
        return []
    hits = []
    for path in _vault_notes():
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        low = text.lower()
        score = sum(low.count(term) for term in terms)
        if score:
            first = next((i for i, line in enumerate(text.splitlines()) if any(t in line.lower() for t in terms)), 0)
            lines = text.splitlines()
            excerpt = "\n".join(lines[first:first + 6])[:800]
            hits.append({
                "path": str(path.relative_to(VAULT)),
                "score": score,
                "excerpt": excerpt,
            })
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:limit]


def vault_read(rel_path: str, limit: int = 12000) -> str:
    target = (VAULT / rel_path).resolve()
    if not str(target).startswith(str(VAULT.resolve())):
        raise ValueError("path escapes the vault")
    if not target.is_file():
        raise FileNotFoundError(f"no such note: {rel_path}")
    return target.read_text(errors="ignore")[:limit]


def vault_list(prefix: str = "", limit: int = 200) -> list[str]:
    return [
        str(p.relative_to(VAULT))
        for p in _vault_notes()
        if str(p.relative_to(VAULT)).startswith(prefix)
    ][:limit]


TOOLS = [
    {
        "name": "brain_search",
        "description": (
            "Search the user's Hermes Brain (Notion) for durable facts about them, their "
            "projects, infrastructure, preferences, and past decisions. Use this before "
            "assuming the user's environment or stack."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for"},
                "limit": {"type": "integer", "description": "Max results (default 8)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "brain_list",
        "description": (
            "List entries from one Hermes Brain (Notion) database. Databases: memory, tasks, "
            "projects, content, research, career, entities."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "database": {"type": "string", "description": "Database key"},
                "limit": {"type": "integer", "description": "Max rows (default 50)"},
            },
            "required": ["database"],
        },
    },
    {
        "name": "brain_read",
        "description": "Read the full body text of a single Hermes Brain (Notion) page by its id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "string", "description": "Notion page id"},
                "limit": {"type": "integer", "description": "Max characters (default 6000)"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "vault_search",
        "description": (
            "Search the user's Obsidian second brain vault. Holds homelab topology, service "
            "maps, Proxmox/LXC inventory, server docs, and per-project notes. Prefer this "
            "over brain_search for infrastructure and hosts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for"},
                "limit": {"type": "integer", "description": "Max results (default 8)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "vault_read",
        "description": "Read one Obsidian vault note by its vault-relative path.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "e.g. knowledge/homeserver/proxmox-hypervisor.md"},
                "limit": {"type": "integer", "description": "Max characters (default 12000)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "vault_list",
        "description": "List Obsidian vault note paths, optionally filtered by a path prefix.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prefix": {"type": "string", "description": "e.g. knowledge/homeserver/"},
                "limit": {"type": "integer", "description": "Max paths (default 200)"},
            },
        },
    },
]


def handle(request: dict) -> dict:
    method = request.get("method")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": request.get("params", {}).get("protocolVersion", "2024-11-05"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hermes-brain", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "brain_search":
                payload = search(args.get("query", ""), int(args.get("limit", 8)))
            elif name == "brain_list":
                payload = list_entries(args.get("database", ""), int(args.get("limit", 50)))
            elif name == "brain_read":
                payload = read_page(args["page_id"], int(args.get("limit", 6000)))
            elif name == "vault_search":
                payload = vault_search(args.get("query", ""), int(args.get("limit", 8)))
            elif name == "vault_read":
                payload = vault_read(args["path"], int(args.get("limit", 12000)))
            elif name == "vault_list":
                payload = vault_list(args.get("prefix", ""), int(args.get("limit", 200)))
            else:
                raise ValueError(f"unknown tool '{name}'")
            text = payload if isinstance(payload, str) else json.dumps(payload, indent=2, default=str)
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"content": [{"type": "text", "text": text[:12000]}]}}
        except Exception as exc:  # surface the reason, never crash the server
            return {"jsonrpc": "2.0", "id": req_id,
                    "result": {"isError": True,
                               "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}]}}

    if method in ("notifications/initialized", "initialized"):
        return {}

    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(request)
        if response:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
