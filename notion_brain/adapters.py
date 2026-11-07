"""Adapter implementations — CAT-03 scaffold only.

This module intentionally implements ONLY :meth:`resolve_storage_ref` for the
Notion and Obsidian adapters, per Phase 12 (CAT-03). The full adapter
behavior — ``NotionAdapter`` delegating to ``notion_brain.store``/
``bootstrap`` (ADAPT-02) and ``ObsidianVaultAdapter`` writing markdown +
SQLite index under the vault (ADAPT-04) — is Phase 11/1.3 scope and is NOT
present here. Nothing in the existing codebase imports this module yet.

``resolve_storage_ref(ref)`` maps a provider-neutral :class:`StorageRef` to a
concrete locator string, or ``None`` when the ref cannot be resolved. Accepted
locators:

- Notion ``page/<id>``, ``page:<id>``, ``page://<id>``, ``db/<id>``,
  ``database/<id>``, or a bare 32/36/38-hex page id.
- Obsidian ``note/<relative/path.md>`` (optionally with leading ``/``), or a
  bare relative path; resolved against the configured vault and verified to
  stay inside it (traversal rejected).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping

from .catalog import StorageRef

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
    """Resolve catalog StorageRefs to concrete Notion locators (CAT-03 only)."""

    def __init__(self, *, notion_api_key: str | None = None) -> None:
        # Stored for the Phase 11 wiring; never logged, never serialized.
        self.notion_api_key = notion_api_key

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
