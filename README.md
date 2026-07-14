# hermes-brain

A Python plugin that turns a [Notion](https://www.notion.so) workspace into persistent long-term memory for the [Hermes](https://github.com/agentinc-ai) AI agent ecosystem.

Instead of an agent forgetting what it learned at the end of a conversation, hermes-brain captures facts, decisions, tasks, research notes, content ideas, and preferences into a structured Notion workspace. Those memories are recalled on demand — so the agent never starts from zero.

## What it does

When you chat with a Hermes-connected AI agent, hermes-brain silently watches the conversation. It extracts anything worth remembering and writes it into one of **7 Notion databases**:

| Database | What it stores | Example |
|---|---|---|
| **Memory** | General notes, lessons learned, decisions | "We decided to use PostgreSQL" |
| **Tasks** | To-dos, reminders, deadlines | "Ship the auth refactor by Friday" |
| **Projects** | Project context, milestones, roadmap notes | "MVP is launching in October" |
| **Content** | Social media drafts, content ideas | "Draft a Twitter thread about agent memory" |
| **Research** | Sources, citations, analysis notes | "BERT outperforms RoBERTa on XNLI" |
| **Career** | Job search notes, interview prep, salary talks | "Salary negotiation target: $180k" |
| **Entities** | People, companies, tools, topics, preferences | "Sarah prefers async communication" |

Two ways to save memories:
- **Automatic** — the agent detects tasks, decisions, research, content ideas, and preferences from your conversation using keyword matching
- **Manual** — ask the agent explicitly: "Remember that I like dark mode"

Two ways to recall:
- **Prefetch** — before each conversation, the agent searches relevant databases and loads context into its working memory
- **Search** — ask the agent to recall anything: "What did we decide about the database?"

## Installation

```bash
pip install -e .
```

This installs the plugin as an editable package. It's designed to be a dependency of a larger project (the Hermes agent framework), not used standalone.

## Setup

### 1. Get a Notion API key

1. Go to [my integrations](https://www.notion.so/my-integrations) and create a new integration
2. Give it a name like "Hermes Brain"
3. Under "Capabilities", enable all 4: Search, Read content, Update content, Insert content
4. Copy the internal integration token (starts with `ntn_`)

### 2. Set your environment variables

```bash
export NOTION_API_KEY=ntn_xxxxx_xxxxx
export HERMES_HOME=~/.hermes
```

- `NOTION_API_KEY` — your Notion integration token
- `HERMES_HOME` — directory where cache files are stored (the plugin needs at least one existing Notion page to use as a parent)

### 3. Bootstrap your workspace

On first run, the plugin creates a **"Hermes Brain"** page in your Notion workspace and the 7 databases inside it. This happens automatically — just call:

```python
from hermes_brain import bootstrap, store

s = store.Store()
bootstrap.init(s)
```

If you don't have any existing pages in your Notion workspace, create one manually first (or set `HERMES_NOTION_PARENT_PAGE` to a page ID).

## Usage

The plugin registers 5 tools with the Hermes agent:

### Search all memories

```
notion_brain_search(query="database migration plan")
notion_brain_search(query="Sarah", database="entities", max_results=5)
```

Searches across all 7 databases. Optional `database` filter narrows to one. Default returns 8 results, max 20.

### Remember something explicitly

```
notion_brain_remember(
    title="Design review notes",
    content="Team agreed on Material Design 3 for the new dashboard",
    domain="projects",
    tags=["design", "dashboard"]
)
```

Valid domains: `daily_work`, `projects`, `social_content`, `research`, `career`, `entities`

### Manage tasks

```
# Create
notion_brain_task(action="create", title="Fix auth bug", priority="urgent", due="2026-08-01")

# List active tasks
notion_brain_task(action="list", status="active")

# Complete a task
notion_brain_task(action="complete", page_id="<notion_page_id>")

# Update task status
notion_brain_task(action="update", page_id="<id>", status="needs_review", priority="high")
```

### Manage content ideas

```
# Create a draft
notion_brain_content(action="create", title="Thread on AI memory", body="Thread draft text...", platform="twitter", tags=["AI", "memory"])

# List drafts
notion_brain_content(action="list")

# Publish an approved draft
notion_brain_content(action="publish", page_id="<id>")

# Archive old content
notion_brain_content(action="archive", page_id="<id>")
```

Valid platforms: `twitter`, `linkedin`, `instagram`, `tiktok`, `facebook`, `youtube`, `bluesky`

### Save research findings

```
# Save a research note
notion_brain_research(action="save", title="LLM benchmarks 2026", content="Summary of findings...", tags=["LLM", "benchmarks"])

# List research entries
notion_brain_research(action="list")
```

## Automatic capture

The plugin watches every conversation turn in the background. It detects these patterns automatically:

| Pattern | Database | Trigger keywords |
|---|---|---|
| **Tasks** | Tasks | "remind me", "todo", "deadline", "due", "blocker", "gotta", "need to" |
| **Decisions** | Projects | "decided", "going with", "moving forward", "approved", "greenlit" |
| **Research** | Research | "source", "according to", "findings", "researched", "cited" |
| **Content** | Content | "draft", "thread", "tweet", "publish", "campaign" |
| **Career** | Career | "interview", "resume", "salary", "promotion", "job" |
| **Preferences** | Entities | "I prefer", "I like", "I hate", "always", "never" |

Everything is saved in a background thread — it never blocks your conversation.

## What gets stored per entry

Every memory entry in Notion has these common properties:

- **Title** — extracted from the triggering sentence (max 120 chars)
- **Domain** — which category the entry belongs to
- **Status** — `active`, `done`, `draft`, `published`, `archived`, `needs_review`, `conflict`
- **Tags** — keyword tags extracted from the text (up to 8 tokens)
- **Confidence** — `high`, `medium`, or `low` (auto-assessed based on context)
- **Source Session** — the Hermes session ID this came from
- **Last Seen** — when this entry was last updated

Some databases have extra properties:

| Database | Extra properties |
|---|---|
| Tasks | Priority, Due date, Project |
| Content | Platform (Twitter, LinkedIn, etc.) |
| Entities | Kind (person, company, tool, project, topic, preference) |
| Memory | Kind (note, preference, lesson, decision, reminder) |

## Secret redaction

The plugin automatically redacts common API key patterns before storing anything:

- Stripe keys (`sk-...`)
- Notion tokens (`ntn_...`)
- GitHub tokens (`ghp_`, `gho_`, `ghu_`, `ghu_`, `ghs_`)
- Slack tokens (`xoxb-`, `xoxp-`, etc.)
- Generic patterns like `api_key=...`, `secret=...`, `password=...`

Redacted secrets appear as `[REDACTED_SECRET]` in the stored content.

## How it works

```
Conversation → extract.classify_turn → BrainEntry.normalized → store.create_database_page → Notion
```

1. **Extract** — regex patterns match keywords in the conversation to classify what kind of memory it is
2. **Normalize** — domain names are standardized, titles are cleaned, secrets are redacted, tags are deduplicated
3. **Store** — entries are written to the correct Notion database as pages with structured properties

Everything happens in a background thread. If the Notion API fails, the error is logged but the conversation continues uninterrupted.

## Cache

The plugin stores a local cache file (`$HERMES_HOME/notion_brain.json`) that maps database display names to their Notion IDs. This avoids querying Notion to find the right databases on every run. The cache is auto-generated and auto-updated.

## Project structure

```
__init__.py          # Plugin entry point, tool schemas, provider implementation (850 lines)
schema.py            # Data model (BrainEntry), constants, normalization helpers (169 lines)
extract.py           # Heuristic classifier — detects memory patterns (187 lines)
store.py             # Notion REST API client — search, query, create, update (260 lines)
bootstrap.py         # Workspace setup — creates parent page + databases (249 lines)
plugin.yaml          # Plugin manifest
README.md            # This file
```

Total: ~1,715 lines of Python.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT — see [LICENSE](LICENSE).
