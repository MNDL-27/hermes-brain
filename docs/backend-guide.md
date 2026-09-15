# Backend Guide

hermes-brain stores agent memory in structured Notion databases. This guide shows
how the backend is wired and how to add your own snippet or database on top.

## Architecture in one paragraph

The Hermes Agent loads `notion_brain` as a memory provider plugin
(`plugin.yaml`, entry via `register()` in `notion_brain/provider.py`).
`NotionBrainProvider` implements the lifecycle hooks Hermes calls
(`initialize`, `prefetch`, `sync_turn`, `get_tool_schemas`, `handle_tool_call`).
Classification of a turn into a domain happens in `extract.py` (regex heuristics,
optional LLM). Writing goes through `store.py` (thin Notion REST client).
The workspace layout — parent page, databases, properties — is defined in
`bootstrap.py` and `schema.py`.

```
Hermes turn
  └─ provider.sync_turn()            notion_brain/provider.py
       └─ extract.classify_turn()    notion_brain/extract.py
            └─ BrainEntry           notion_brain/schema.py
                 └─ store writes    notion_brain/store.py
```

## Recipe: add a custom database

Custom databases don't require code. `hermes-brain setup` lets you define them
interactively (e.g. `fitness` with `Reps:number`, `Exercise:select`), or declare
them in `~/.hermes/config.yaml` — see the custom database section in the README.
`prefetch` and search pick them up automatically.

## Recipe: add a new heuristic trigger

Want turns about meeting notes to land in `Tasks`? Three edits, one test:

1. In `notion_brain/extract.py`, add a pattern next to the existing
   `_TRIGGERS_*` regexes:

   ```python
   _TRIGGERS_MEETING = re.compile(r"\b(meeting|standup|1:1)\b", re.IGNORECASE)
   ```

2. Add a branch in `classify_turn()` returning the target database key.
3. Add a case to `tests/test_extract.py`.

This is the smallest meaningful code contribution — good first PR material.

## Recipe: add a new tool

1. Schema dict in `notion_brain/schemas.py`, appended to `ALL_TOOL_SCHEMAS`.
2. Handler `_tool_yourname()` + dispatch entry in
   `notion_brain/provider.py` `handle_tool_call()`.
3. Tests in `tests/test_provider.py` (mock the Notion API; never hit it live).

See `examples/quickstart.py` for how the public helpers
(`ensure_brain`, `remember`, `search_entries`) are called from outside Hermes.

## Scope note

Notion is the only backend today. Other backends (Obsidian, SQLite, local
Markdown) are in-project when they land — no separate or paid companion repo.
Open an issue before starting a backend PR so scope is agreed.
