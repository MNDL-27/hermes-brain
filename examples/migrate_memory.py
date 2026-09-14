"""Import existing MEMORY.md and USER.md files into Notion.

This is a one-time migration — it reads the legacy file-based memory format
that Claude uses and converts it into Notion entries organized by domain.

Prerequisites:
    export NOTION_API_KEY=ntn_xxxxx_xxxxx
    export HERMES_HOME=~/.hermes

Usage:
    cd hermes-brain
    python examples/migrate_memory.py

"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notion_brain import ensure_brain, remember

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    """Read a file and return its contents, or empty string if missing."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


# Domain detection — maps a heading to a hermes-brain domain.
DOMAIN_MAP = {
    "Memory": "memory",
    "Tasks": "tasks",
    "Projects": "projects",
    "Content": "social_content",
    "Research": "research",
    "Career": "career",
    "Entities": "entities",
}


def classify_line(text: str, section: str) -> dict:
    """Return a domain/kind pair for a single line of memory content."""
    tags = [section.lower().replace(" ", "_")]

    kind = "note"
    if section == "Tasks":
        kind = "task"
        if any(w in text.lower() for w in ("deadline", "due", "urgent", "must", "todo")):
            status = "active"
        else:
            status = "done"
    elif section == "Projects":
        kind = "decision" if "decided" in text.lower() else "note"
        status = "active"
    elif section == "Entities":
        kind = "preference" if "prefer" in text.lower() else "note"
        status = "active"
    elif section == "Content":
        kind = "draft"
        status = "needs_review"
    elif section == "Research":
        kind = "lesson"
        status = "done"
    else:
        status = "active"

    entities = []
    for entity in re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", text):
        if len(entity) > 2 and len(entity) < 50:
            entities.append(entity.strip())

    return {
        "kind": kind,
        "status": status,
        "tags": tags[:8],
        "entities": entities[:5],
    }


def parse_memory_md(content: str, section: str) -> list[tuple[str, str]]:
    """Parse MEMORY.md content into (title, content) pairs.

    Expects lines like:
    ## Projects
    - **Decision**: We chose PostgreSQL for ACID transactions.
    - **Timeline**: MVP by Q3 2026.
    """
    entries: list[tuple[str, str]] = []
    in_section = False
    current_title = ""
    current_body = ""

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            # Flush previous entry
            if current_title and current_body:
                entries.append((current_title, current_body))
            in_section = stripped.replace("## ", "").strip().lower() == section.lower()
            current_title = ""
            current_body = ""
        elif in_section and stripped.startswith("- **"):
            if current_title and current_body:
                entries.append((current_title, current_body))
            # Extract bold label as title
            m = re.match(r"- \*\*([^*]+)\*\*:?\s*(.*)", stripped)
            current_title = m.group(1).strip() if m else ""
            current_body = m.group(2).strip() if m else ""
        elif in_section and current_title:
            current_body += " " + stripped

    # Flush last entry
    if current_title and current_body:
        entries.append((current_title, current_body))

    return entries


def main() -> None:
    home = os.environ.get("HERMES_HOME", "~/.hermes")
    cache = ensure_brain(home)
    print(f"Hermes Brain at {cache['parent_page_id']}")

    # Look for memory files in HERMES_HOME
    memory_file = os.path.join(home, "MEMORY.md")
    user_file = os.path.join(home, "USER.md")

    total = 0
    for fname, section in [(memory_file, "Projects"), (user_file, "Entities")]:
        content = read_file(fname)
        if not content:
            print(f"\n⚠ {fname} not found — skipping")
            continue

        entries = parse_memory_md(content, section)
        domain = DOMAIN_MAP.get(section, "memory")

        if not entries:
            print(f"\n→ {section}: no entries found")
            continue

        print(f"\n→ Migrating {section} ({len(entries)} entries from {fname})")
        for title, body in entries:
            if not title or not body:
                continue
            props = classify_line(body, section)
            remember(
                title=title,
                content=f"[{section}] {body}",
                domain=domain,
                kind=props["kind"],
                status=props["status"],
                tags=props["tags"],
                entities=props["entities"],
            )
            total += 1

    print(f"\nMigrated {total} entries from {memory_file} + {user_file}")
    print("Done. Check your Notion workspace.")


if __name__ == "__main__":
    main()
