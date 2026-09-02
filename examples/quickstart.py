"""Quick examples for hermes-brain — persistent memory for AI agents.

These are standalone scripts to demonstrate API usage. They all require
environment variables set (see Setup section of the README).

    export NOTION_API_KEY=ntn_xxxxx_xxxxx
    export HERMES_HOME=~/.hermes

Run from the repo root:

    python examples/quickstart.py

"""

from __future__ import annotations

import os
import sys

# Ensure the installed package is importable
# (examples live in the repo root next to the package)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notion_brain import ensure_brain, search_entries, remember

# ---------------------------------------------------------------------------
# 1. Bootstrap — one-time setup (creates "Hermes Brain" page + 7 databases)
# ---------------------------------------------------------------------------
print("1. Bootstrapping…")
cache = ensure_brain(os.environ.get("HERMES_HOME", "~/.hermes"))
print(f"   parent_page_id = {cache['parent_page_id']}")
print(f"   databases: {len(cache)}")

# ---------------------------------------------------------------------------
# 2. Remember something explicit
# ---------------------------------------------------------------------------
print("\n2. Remembering a decision…")
entry = remember(
    title="Tech stack decision: PostgreSQL over MongoDB",
    content="Team agreed on PostgreSQL for the project. ACID transactions, strong type system, mature ORM ecosystem. MongoDB is an alternative for unstructured data but not for core business logic.",
    domain="projects",
    kind="decision",
    status="active",
    tags=["database", "postgresql", "architecture"],
    entities=["Sarah", "Engineering Team"],
)
print(f"   stored page: {entry.get('page_id', 'pending…')}")

# ---------------------------------------------------------------------------
# 3. Search for what we just stored
# ---------------------------------------------------------------------------
print("\n3. Searching…")
results = search_entries("PostgreSQL decision")
for r in results:
    print(f"   • {r['title']}  [{r.get('confidence', 'n/a')}]")

# ---------------------------------------------------------------------------
# 4. Create a task
# ---------------------------------------------------------------------------
print("\n4. Creating a task…")
task = remember(
    title="Set up DB migrations with Alembic",
    content="Initial schema: users, projects, memories. Add Alembic to track migrations.",
    domain="daily_work",
    kind="note",
    status="active",
    tags=["database", "setup"],
    entities=["Engineering Team"],
)
print(f"   stored page: {task.get('page_id', 'pending…')}")

print("\nDone. Check your Notion workspace for all 3 entries.")
