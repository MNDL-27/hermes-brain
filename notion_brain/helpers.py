"""Shared helpers for the Notion brain provider."""

from __future__ import annotations

import re
from typing import Any


def _safe_select_value(value: str, prop_schema: dict[str, Any]) -> str | None:
    """Return ``value`` if it is a defined option on this select property, else ``None``.

    Per-DB option sets differ (memory Kind: note/preference/lesson/decision/reminder;
    entities Kind: person/company/tool/project/topic/preference). Writing a value
    that isn't a defined option makes Notion reject the whole page with a 400.
    Dropping the property is safer than guessing — Notion will leave it blank or
    fill the default option.
    """
    options = prop_schema.get("select", {}).get("options", [])
    valid = {opt.get("name", "") for opt in options}
    if not valid:
        # Schema unknown — pass through; better to attempt than silently drop
        # user data when we genuinely don't know what's allowed.
        return value
    return value if value in valid else None


def _merge_disk_only(notion_entries: list[dict], disk_text: str) -> list[dict]:
    """Merge entries from disk that aren't already in the Notion list.

    Simple heuristic: if the title from disk is not in Notion titles,
    treat it as a disk-only entry and wrap it in a flat result structure.
    """
    if not disk_text or not disk_text.strip():
        return notion_entries

    notion_titles = {e.get("title", "").lower() for e in notion_entries}

    # Basic parser for the frontmatter-style blocks we write to disk
    # Expects blocks starting with --- and having a 'name: ...' line
    # Line-anchored split only on lines that are exactly "---", so content
    # containing "---" (e.g. code fences, horizontal rules) is preserved.
    disk_entries = []
    blocks = re.split(r"(?m)^---$", disk_text)
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split("\n")
        title = None
        tags: list[str] = []
        content = []
        for line in lines:
            if line.startswith("name: "):
                title = line[6:].strip()
            elif line.startswith("tags: "):
                tags = [t.strip() for t in line[6:].split(",") if t.strip()]
            elif not line.startswith("domain: ") and not line.startswith("kind: "):
                content.append(line)

        if title and title.lower() not in notion_titles:
            disk_entries.append({
                "title": title,
                "properties": {
                    "Content": "\n".join(content).strip(),
                    "Domain": "Memory",
                    "Kind": "note",
                    "Tags": tags,
                }
            })

    return notion_entries + disk_entries


def _merge_user_disk_only(notion_entries: list[dict], disk_text: str) -> list[dict]:
    """Merge USER.md disk-only preferences into Notion user entry list.

    USER.md uses a different format from MEMORY.md:
        # User Profile
        ## Title
        content

    Splits by ``## `` headers; each section's title is the header, body is the
    content. Entries whose title is not already in ``notion_entries`` are kept
    as disk-only, wrapped in the same flat result structure as memory entries.
    """
    if not disk_text or not disk_text.strip():
        return notion_entries

    notion_titles = {e.get("title", "").lower() for e in notion_entries}

    disk_entries: list[dict] = []
    lines = disk_text.splitlines()
    title: str | None = None
    body: list[str] = []
    for line in lines[1:] if lines and lines[0].lstrip().startswith("# ") else lines:
        if line.startswith("## "):
            if title and title.lower() not in notion_titles:
                disk_entries.append(_user_disk_entry(title, body))
            title = line[3:].strip()
            body = []
        elif title is not None:
            body.append(line)
    if title and title.lower() not in notion_titles:
        disk_entries.append(_user_disk_entry(title, body))

    return notion_entries + disk_entries


def _user_disk_entry(title: str, body: list[str]) -> dict:
    return {
        "title": title,
        "properties": {
            "Content": "\n".join(body).strip(),
            "Kind": "preference",
        },
    }


def _paragraph_blocks(content: str, *, max_paras: int | None = None, chunk: int = 1900) -> list[dict]:
    """Split content into Notion paragraph children.

    Preserves every non-empty line without arbitrary truncation.
    Chunks each line to the block char limit.
    """
    if not content:
        return []
    paras = content.replace("\n\n", "\n").split("\n")
    if max_paras is not None:
        paras = paras[:max_paras]
    blocks: list[dict] = []
    for para in paras:
        para = para.strip()
        if not para:
            continue
        for i in range(0, len(para), chunk):
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": para[i:i + chunk]}}]},
            })
    return blocks
