# Architecture

How hermes-brain turns a conversation turn into a row in Notion, and the trade-offs that shaped it.

## Request flow

```
Conversation Turn
       │
       ▼
sanitize_context()    Strip PII, truncate to token budget
       │
       ▼
extract.classify_turn()   Regex matching → BrainEntry list
       │
       ▼
BrainEntry.normalized()   Domain normalize, secret redact,
                          title clean, tag dedupe
       │
       ▼
store.create_database_page()   Notion REST API: POST /pages
       │
       ▼
Notion Workspace (7 databases)
```

Each stage is a small function with a single responsibility. There is no hidden state between stages — `BrainEntry` is the only carrier.

## The four core modules

| Module | Responsibility |
|---|---|
| `notion_brain/schema.py` | `BrainEntry` dataclass, constants, normalization rules |
| `notion_brain/extract.py` | Heuristic classifier — turns text into `BrainEntry` candidates |
| `notion_brain/store.py` | Notion REST client — turns `BrainEntry` into Notion pages |
| `notion_brain/bootstrap.py` | One-time workspace setup, schema repair, health checks |

The plugin entry point in `__init__.py` wires these together and registers five tools with the Hermes agent.

## Why each design decision was made

| Decision | Rationale | Upgrade path |
|---|---|---|
| Heuristic-only classification (no LLM) | Zero token cost, zero latency, deterministic | Swap regex for an embedding classifier when coverage drops below ~70% |
| Background thread sync | Non-blocking for the agent loop | Replace with a proper task queue if failure rate exceeds 5% |
| Flat JSON cache (`notion_brain.json`) | Simple, no migration needed | Add versioning when multi-workspace support lands |
| 1900-character chunking | Notion's 2000-character block limit | Auto-upgrade when Notion raises the limit |
| `requests` over `httpx` | Already a transitive Hermes dependency | Migrate to `httpx` when async I/O becomes necessary |

## Background sync, in one paragraph

When the agent finishes a turn, the classifier emits zero or more `BrainEntry` objects. Instead of writing them inline (which would block the agent loop on a Notion round-trip), the plugin hands them to a daemon thread that flushes them in the background. The agent never waits. If Notion is unreachable, the thread retries with backoff and logs failures — the agent sees none of this.

## The seven databases

| Database | Catch |
|---|---|
| **Memory** | General notes, lessons, decisions that don't fit elsewhere |
| **Tasks** | Anything with a deadline or owner |
| **Projects** | Decisions, milestones, roadmap items |
| **Content** | Social drafts, posts in progress |
| **Research** | Sources, citations, analyses |
| **Career** | Job search, interviews, comp |
| **Entities** | People, companies, tools, preferences |

Every database shares a base property set (Title, Domain, Status, Tags, Confidence, Source Session, Last Seen). Per-database extras — Priority and Due for Tasks, Platform for Content, Kind for Entities — are added on top.

## Where secrets are scrubbed

Before a `BrainEntry` is handed to the Notion client, `normalize()` runs the redactor. Stripe, Notion, GitHub, and Slack tokens are replaced with `[REDACTED_SECRET]`. Generic `api_key=…`, `password=…`, `token=…` patterns are caught by a fallback regex.

The redactor is the **last** stage before the network call. Anything that misses it goes to Notion.
