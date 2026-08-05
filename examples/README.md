# Examples

Runnable scripts demonstrating hermes-brain usage patterns.

All examples require environment variables set:

```bash
export NOTION_API_KEY=ntn_xxxxx_xxxxx
export HERMES_HOME=~/.hermes
```

Run from the repo root:

```bash
python examples/quickstart.py    # Create, search, and store entries
python examples/migrate_memory.py  # Import existing MEMORY.md into Notion
```

Each script is a standalone program — no framework needed. They install into the same `site-packages` as the main package via `pip install -e .` from the repo root, so they can `import notion_brain` without path hacks.
