# Backend Swap Guide

hermes-brain registers itself as a `MemoryProvider` in the Hermes agent framework. If you want to write a custom backend — or understand how the paid backends work — this guide documents the provider contract.

## Overview

A backend is a Python class that implements the lifecycle and tool-handling methods expected by Hermes. The class is then exposed via a `register(ctx)` function that calls `ctx.register_memory_provider(provider_instance)`.

## Provider contract

Implement these methods:

### `name: str`

A unique short name for the backend, e.g. `"notion_brain"`.

### `is_available() -> bool`

Return `True` only when the runtime requirements are met. For example, Notion returns `True` when `NOTION_API_KEY` is set.

### `initialize(session_id: str, **kwargs) -> None`

Called once per agent session. Use `kwargs.get("hermes_home")` for the Hermes data directory. Set up any required databases, tables, or cache files here.

### `system_prompt_block() -> str`

Return a Markdown block describing the memory system to the agent. This text is injected into the agent's system prompt. Keep it concise: what databases exist and which tools to use.

### `prefetch(query: str, *, session_id: str = "") -> str`

Smart recall. Search the backend for entries relevant to `query` and return a short Markdown string. Should be fast — this runs before every agent turn.

Return an empty string if nothing is found or the backend is not ready.

### `sync_turn(user_content: str, assistant_content: str, *, session_id: str = "", messages=None) -> None`

Called after each conversation turn. Extract anything worth remembering and persist it. Do **not** block the agent loop; run heavy work in a background thread or queue.

### `on_session_end(messages: list[dict]) -> None`

Called when the session ends. Flush any pending writes and optionally save a session summary.

### `shutdown() -> None`

Flush pending work and close resources. Called during agent shutdown.

### `on_memory_write(action: str, target: str, content: str, metadata: dict | None) -> None`

Mirror built-in memory writes. `action` is usually `"add"`, `target` is `"memory"` or `"user"`, and `content` is the raw text the agent was told to remember.

### `get_tool_schemas() -> list[dict]`

Return JSON Schema objects defining the tools the backend exposes to the agent. These are passed directly to the agent tool dispatcher.

### `handle_tool_call(tool_name: str, args: dict, **kwargs) -> str`

Execute a tool call and return a JSON string. Dispatch on `tool_name` and map `args` to the backend's storage operations. Use `tool_error(...)` from Hermes for failures.

## Data model

Each memory entry is normalized to a `BrainEntry` dataclass before storage:

```python
@dataclass
class BrainEntry:
    domain: str          # e.g. "daily_work", "projects", "research"
    title: str           # max 120 chars
    content: str         # cleaned, secret-redacted body
    kind: str = "note"
    status: str = "active"
    confidence: str = "medium"
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    source_session_id: str = ""
    metadata: dict = field(default_factory=dict)
```

Use `BrainEntry.normalized()` to sanitize values before storage.

## Domains and databases

| Domain key | Display name | Database |
|---|---|---|
| `daily_work` | Daily Work | tasks |
| `projects` | Projects | projects |
| `social_content` | Social Content | content |
| `research` | Research | research |
| `career` | Job/Career | career |
| `entities` | People/Entities | entities |
| `memory` | Memory | memory |

Use `schema.database_for_domain(domain)` to map a domain to its canonical database key.

## Secret redaction

Always call `schema.redact_secrets()` on any text you persist. The built-in patterns cover Stripe, Notion, GitHub, and Slack tokens plus generic `api_key=...` / `password=...` patterns.

## Classification (optional)

If your backend wants automatic capture, reuse `extract.classify_turn(user_content, assistant_content)` from the core package. It returns a list of `BrainEntry` objects using zero-LLM heuristic matching.

## Example skeleton

```python
from __future__ import annotations

from hermes_brain import schema as S
from hermes_brain.extract import classify_turn
from tools.registry import tool_error

class MyBackend:
    name = "my_backend"

    def is_available(self) -> bool:
        return True  # check your env vars here

    def initialize(self, session_id: str, **kwargs) -> None:
        self.session_id = session_id
        self.hermes_home = kwargs.get("hermes_home", "")

    def system_prompt_block(self) -> str:
        return "# My Backend\nUse my_backend_search to recall context."

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        return ""

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "", messages=None):
        for entry in classify_turn(user_content, assistant_content):
            self._write(entry)

    def _write(self, entry: S.BrainEntry) -> None:
        norm = entry.normalized()
        # persist norm.domain, norm.title, norm.content, etc.

    def get_tool_schemas(self) -> list[dict]:
        return [
            {
                "name": "my_backend_search",
                "description": "Search memory.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            }
        ]

    def handle_tool_call(self, tool_name: str, args: dict, **kwargs) -> str:
        if tool_name == "my_backend_search":
            return "{}"
        return tool_error(f"Unknown tool: {tool_name}")

    def on_session_end(self, messages: list[dict]) -> None: ...
    def shutdown(self) -> None: ...
    def on_memory_write(self, action, target, content, metadata=None) -> None: ...


def register(ctx):
    ctx.register_memory_provider(MyBackend())
```

## Packaging

A custom backend is a Python package that depends on `hermes-brain`. Users install both:

```bash
pip install hermes-brain your-custom-backend
```

The companion package registers its own providers under different names, and Hermes selects whichever backend is configured.

## Need help?

Open an issue in this repo for contract questions. If you build a backend and want it listed in the README, open a PR against [`BACKENDS.md`](BACKENDS.md).
