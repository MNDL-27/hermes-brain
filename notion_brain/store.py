"""Lightweight Notion REST API client for the notion_brain provider.

Uses ``requests`` (already a Hermes dependency) against the Notion API.
Credentials come from the ``NOTION_API_KEY`` env var (set in ``~/.hermes/.env``).

All methods operate synchronously and return dicts parsed from the JSON body.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from .schema import NOTION_API_VERSION

logger = logging.getLogger(__name__)

BASE_URL = "https://api.notion.com/v1"
_MAX_RETRIES = 3
_RETRY_DELAY_S = 1.0


def get_api_key() -> str | None:
    return os.environ.get("NOTION_API_KEY", "").strip() or None


def _headers() -> dict[str, str]:
    token = get_api_key()
    if not token:
        raise RuntimeError("NOTION_API_KEY not set")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_API_VERSION,
    }


def _request(method: str, path: str, json_body: dict | None = None) -> dict[str, Any] | list[Any]:
    url = f"{BASE_URL}{path}"
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.request(method, url, headers=_headers(),
                                    json=json_body, timeout=30)
            if resp.ok:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt < _MAX_RETRIES:
                    time.sleep(_RETRY_DELAY_S * attempt)
                    continue
            # Non-retryable error or retries exhausted: parse body safely
            try:
                data = resp.json()
                msg = data.get("message", resp.reason or "unknown error")
            except requests.exceptions.JSONDecodeError:
                msg = resp.text[:200] if resp.text else resp.reason or "unknown error"
            raise RuntimeError(f"Notion API {resp.status_code} on {method} {path}: {msg}")
        except requests.Timeout:
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_S * attempt)
                continue
            raise RuntimeError(f"Notion API timeout on {method} {path}")
        except requests.ConnectionError:
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_S * attempt)
                continue
            raise RuntimeError(f"Notion API connection error on {method} {path}")


# ─── Search ──────────────────────────────────────────────────────────────


def search_page_by_title(title: str, object_type: str = "page") -> dict[str, Any] | None:
    """Find the first page whose title matches exactly (case-insensitive)."""
    body: dict[str, Any] = {"query": title, "filter": {"value": object_type, "property": "object"}}
    data = _request("POST", "/search", body)
    for result in data.get("results", []):
        obj_type = result.get("object")
        if object_type and obj_type != object_type:
            continue
        candidate = _page_title(result)
        if candidate and candidate.strip().lower() == title.strip().lower():
            return result
    return None


def search_entries(query: str, *, page_size: int = 8) -> list[dict[str, Any]]:
    """Search Notion and return results with extracted metadata."""
    body: dict[str, Any] = {"query": query, "page_size": min(page_size, 100)}
    data = _request("POST", "/search", body)
    return [_flatten_result(r) for r in (data.get("results") or [])]


def query_database(database_id: str, *, page_size: int = 100,
                   sorts: list[dict] | None = None,
                   filter_obj: dict | None = None) -> list[dict[str, Any]]:
    """Query a Notion database and return flat results."""
    body: dict[str, Any] = {"page_size": min(page_size, 100)}
    if sorts:
        body["sorts"] = sorts
    if filter_obj:
        body["filter"] = filter_obj
    data = _request("POST", f"/databases/{database_id}/query", body)
    return [_flatten_result(r) for r in (data.get("results") or [])]


# ─── Pages ───────────────────────────────────────────────────────────────


def create_page(parent_page_id: str, properties: dict[str, Any],
                children: list[dict] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "properties": properties,
    }
    if children:
        body["children"] = children
    return _request("POST", "/pages", body)


def create_database_page(database_id: str, properties: dict[str, Any],
                         children: list[dict] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "parent": {"type": "database_id", "database_id": database_id},
        "properties": properties,
    }
    if children:
        body["children"] = children
    return _request("POST", "/pages", body)


def update_page(page_id: str, properties: dict[str, Any]) -> dict[str, Any]:
    return _request("PATCH", f"/pages/{page_id}", {"properties": properties})


def get_page(page_id: str) -> dict[str, Any]:
    return _request("GET", f"/pages/{page_id}")


# ─── Databases ───────────────────────────────────────────────────────────


def create_database(parent_page_id: str, title: str,
                    properties: dict[str, Any]) -> dict[str, Any]:
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": _rich_text(title),
        "properties": properties,
    }
    return _request("POST", "/databases", body)


def get_database(database_id: str) -> dict[str, Any]:
    return _request("GET", f"/databases/{database_id}")


def update_database(database_id: str, properties: dict[str, Any]) -> dict[str, Any]:
    return _request("PATCH", f"/databases/{database_id}", {"properties": properties})


def archive_database(database_id: str) -> dict[str, Any]:
    """Archive (soft-delete) a database. Call before recreate to drop zombie options."""
    return _request("PATCH", f"/databases/{database_id}", {"archived": True})


# ─── Rich text / property helpers ────────────────────────────────────────


from .schema import redact_secrets


def _rich_text(content: str) -> list[dict]:
    redacted = redact_secrets(content)
    return [{"type": "text", "text": {"content": redacted[:2000]}}]


def title_property(text: str) -> dict[str, Any]:
    return {"title": _rich_text(text)}


def rich_text_property(text: str) -> dict[str, Any]:
    return {"rich_text": _rich_text(text)}


def select_property(name: str) -> dict[str, Any]:
    return {"select": {"name": redact_secrets(name)}}


def multi_select_property(names: list[str]) -> dict[str, Any]:
    options = [{"name": redact_secrets(n)[:80]} for n in names if n.strip()] if names else []
    return {"multi_select": options}


def date_property(date_str: str | None) -> dict[str, Any]:
    """Build a Notion date property payload.

    Returns a payload with an empty ``date`` object (Notion's documented
    "no value" shape) rather than ``{"date": null}``, which the API rejects.
    Callers that want to omit the property entirely should do so themselves.
    """
    if date_str:
        return {"date": {"start": date_str}}
    return {"date": {}}


def number_property(value: float | None) -> dict[str, Any]:
    return {"number": value}


def status_property(name: str) -> dict[str, Any]:
    return {"status": {"name": name}}


def _page_title(page: dict[str, Any]) -> str | None:
    try:
        props = page.get("properties") or {}
        for val in props.values():
            if isinstance(val, dict) and val.get("type") == "title":
                texts = val.get("title") or []
                return "".join(t.get("text", {}).get("content", "") for t in texts).strip() or None
    except Exception:
        pass
    return None


def _flatten_result(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key metadata from a Notion API result."""
    obj_type = raw.get("object", "unknown")
    result_id = raw.get("id", "")
    title = _page_title(raw) or raw.get("id", "")[:36]
    created = raw.get("created_time", "")
    edited = raw.get("last_edited_time", "")
    # Pull usable properties
    props: dict[str, Any] = {}
    for key, val in (raw.get("properties") or {}).items():
        if isinstance(val, dict):
            t = val.get("type", "")
            if t in ("title", "rich_text"):
                texts = val.get(t) or []
                props[key] = "".join(v.get("text", {}).get("content", "") for v in texts)
            elif t == "select":
                s = val.get("select")
                props[key] = s.get("name") if isinstance(s, dict) else None
            elif t == "multi_select":
                ms = val.get("multi_select")
                props[key] = [s.get("name") for s in (ms if isinstance(ms, list) else [])]
            elif t == "status":
                s = val.get("status")
                props[key] = s.get("name") if isinstance(s, dict) else None
            elif t == "date":
                d = val.get("date")
                props[key] = d.get("start") if isinstance(d, dict) else None
            elif t == "number":
                props[key] = val.get("number")
            elif t == "checkbox":
                props[key] = val.get("checkbox")
            elif t == "url":
                props[key] = val.get("url")
            elif t == "email":
                props[key] = val.get("email")
    return {
        "id": result_id,
        "type": obj_type,
        "title": title,
        "created_time": created,
        "last_edited_time": edited,
        "properties": props,
        "raw": raw,
    }