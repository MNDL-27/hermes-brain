<div align="center">
  <a href="https://github.com/MNDL-27/hermes-brain">
    <img src=".github/assets/hero.png" alt="hermes-brain" width="600"/>
  </a>
</div>

> Notion-backed persistent long-term memory for the Hermes AI agent ecosystem. Organizes decisions, tasks, projects, research, and custom domains across structured Notion databases.

<div align="center">

  [![GitHub Release](https://img.shields.io/github/v/release/MNDL-27/hermes-brain?color=0073FF&labelColor=black&style=flat-square)](https://github.com/MNDL-27/hermes-brain/releases)
  [![GitHub Contributors](https://img.shields.io/github/contributors/MNDL-27/hermes-brain?color=0073FF&labelColor=black&style=flat-square)](https://github.com/MNDL-27/hermes-brain/graphs/contributors)
  [![GitHub Stars](https://img.shields.io/github/stars/MNDL-27/hermes-brain?color=0073FF&labelColor=black&style=flat-square)](https://github.com/MNDL-27/hermes-brain/stargazers)
  [![GitHub Issues](https://img.shields.io/github/issues/MNDL-27/hermes-brain?color=0073FF&labelColor=black&style=flat-square)](https://github.com/MNDL-27/hermes-brain/issues)
  [![License](https://img.shields.io/badge/license-MIT-green?labelColor=black&style=flat-square)](LICENSE)
</div>

---

## Overview

**hermes-brain** replaces local flat markdown memory files (`MEMORY.md` / `USER.md`) with a structured, multi-database Notion workspace under a single **Hermes Brain** parent page. 

Instead of an agent forgetting decisions or cluttering a single text file across long sessions, context is classified into dedicated databases with typed properties, status tracking, confidence scoring, and tag indexing.

```
Conversation Turn (User / Assistant)
       │
       ├──────────────────────────────────────────────┐
[Synchronous Execution]                        [Asynchronous Background Worker]
       │                                              │
1. prefetch()                                  1. sync_turn()
   - Injects relevant memory context              - Pushes turn to daemon queue
2. Tool Calls                                  2. extract.classify_turn()
   - notion_brain_search                          - Regex heuristics / optional local LLM
   - notion_brain_remember                     3. BrainEntry.normalized()
   - notion_brain_task                            - Secret redaction (sk-, ntn-, ghp-, keys)
   - notion_brain_content                      4. store.create_database_page()
   - notion_brain_research                        - Writes to Notion API (1900-char blocks)
```

---

## Quickstart

### 1. Prerequisites

- Python 3.11 to 3.13
- Notion integration token ([create one at notion.so/my-integrations](https://www.notion.so/my-integrations))
- [Hermes Agent](https://hermes-agent.nousresearch.com/)

### 2. Installation

Install into the Hermes Agent virtual environment:

```bash
~/.hermes/hermes-agent/venv/bin/pip install -e /path/to/hermes-brain
```

Or symlink into your Hermes user plugins directory:

```bash
mkdir -p ~/.hermes/plugins
ln -s /path/to/hermes-brain/notion_brain ~/.hermes/plugins/notion_brain
```

Symlink the companion skill so Hermes knows when to trigger explicit memory actions:

```bash
mkdir -p ~/.hermes/skills
ln -s /path/to/hermes-brain/skills/notion-brain ~/.hermes/skills/notion-brain
```

### 3. Configure Credentials

Add your Notion integration token to `~/.hermes/.env`:

```bash
echo "NOTION_API_KEY=ntn_your_notion_token_here" >> ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

### 4. Interactive Onboarding & Database Setup

Run the setup wizard to choose your workspace structure:

```bash
hermes-brain setup
```

The wizard prompts you for:
1. **Standard databases to create**: Select from the 7 starter templates (`Memory`, `Tasks`, `Projects`, `Content`, `Research`, `Career`, `Entities`).
2. **Custom databases**: Add application-specific databases (e.g. `fitness`, `finance`) with custom typed fields (`Reps:number`, `Exercise:select`).
3. **Workspace bootstrap**: Creates the **Hermes Brain** parent page and builds the chosen databases in Notion.

*Important:* Open your **Hermes Brain** page in Notion and share it with your integration (`•••` -> `Connections` -> add your integration).

### 5. Verify Standalone

Run the standalone verification script without launching Hermes:

```bash
python examples/quickstart.py
```

### 6. Enable in Hermes Agent

In `~/.hermes/config.yaml`:

```yaml
memory:
  memory_enabled: true
  provider: notion_brain
```

Ensure `memory` is removed from `disabled_toolsets` if present.

---

## Databases & Schemas

### Starter Databases

| Database | Domain Key | Default Kind | Tracked Fields | Example |
|---|---|---|---|---|
| **Memory** | `memory` | note, lesson, decision | Title, Domain, Kind, Status, Tags, Confidence, Last Seen | "Team agreed on PostgreSQL for timeseries storage" |
| **Tasks** | `daily_work` | task | Title, Status, Priority (`urgent`, `high`, `med`, `low`), Due, Project, Tags | "Deploy updated docker dashboard by Friday" |
| **Projects** | `projects` | decision, note | Title, Status, Decision Rationale, Tags, Confidence, Last Seen | "Architecture migration roadmap Q4" |
| **Content** | `social_content` | draft, idea | Title, Content Body, Platform (`twitter`, `linkedin`, ...), Status, Tags | "Draft technical thread on local agent memory" |
| **Research** | `research` | source_note | Title, Findings Body, Sources, Tags, Status | "Analysis of latency bottlenecks in WebSockets" |
| **Career** | `career` | application | Title, Role, Company, Compensation, Status, Tags | "Staff Engineer application status and notes" |
| **Entities** | `entities` | preference, person, tool | Title (Atomic key-value), Kind, Tags, Confidence | "Sarah: Prefers asynchronous Slack updates" |

### Custom User Databases

You can configure custom databases during interactive setup or via command-line flags for automation:

```bash
hermes-brain setup --standard-dbs 1,2,3 --custom-json '[{"key":"fitness","title":"Workouts","fields":{"Reps":"number","Exercise":"select"}}]' --non-interactive
```

Custom databases automatically inherit the base audit properties (`Title`, `Domain`, `Status`, `Tags`, `Confidence`, `Source Session`, `Last Seen`) in addition to your custom fields.

---

## Common Pitfalls

| Symptom | Cause | Solution |
|---|---|---|
| `unauthorized` from Notion | Integration not connected to page | Open "Hermes Brain" in Notion -> `•••` -> `Connections` -> add your integration |
| Search returns nothing right after writing | Notion search indexing delay | Notion search index takes 3 to 5 seconds to index newly created pages |
| 404 on database write | Database removed or unshared | Run `hermes-brain health` to diagnose and rebind database IDs |
| Stale cache IDs | Inconsistent `notion_brain.json` | Run `hermes-brain reset` to refresh database bindings without deleting page data |
| Missing module error in Hermes | Installed in wrong Python environment | Install directly into `~/.hermes/hermes-agent/venv/bin/pip` |

---

## Architectural Guarantees

- **Non-Blocking Background Worker**: Writes are pushed to an in-memory queue and processed by a dedicated daemon thread. Notion API latency never delays conversation turns.
- **Prompt-Cache Integrity**: Base system prompt text remains static across sessions. Dynamic memories are injected via `prefetch()` and tool responses, preventing prompt-cache invalidation.
- **Strict Secret Redaction**: All text passes through `redact_secrets()` before leaving the machine. OpenAI (`sk-`), Notion (`ntn_`), GitHub (`ghp_`), Slack (`xoxb-`), AWS tokens, and private keys are scrubbed.
- **Safe Exception Boundaries**: Exceptions raised during API calls suppress raw stack traces (`raise ... from None`) to prevent unredacted tokens from leaking into error logs.
- **Page Deduplication**: Title checks verify existing entries before writing, executing a `PATCH` update rather than creating duplicate pages.
- **Full Block Body Hydration**: Recursive cursor pagination retrieves full multi-paragraph page bodies from `/blocks/{id}/children`, bypassing the 200-character property truncation limit.
- **Block Chunking**: Long content is automatically divided into 1900-character paragraph blocks to respect Notion's 2000-character block boundary.

---

## Available Tools

When active, Hermes has access to 5 dedicated tools:

- **`notion_brain_search`**: Search across all databases or filter by a specific database (`memory`, `tasks`, `projects`, `content`, `research`, `career`, `entities`, or custom keys).
- **`notion_brain_remember`**: Save explicit notes, decisions, or facts when heuristic capture does not apply.
- **`notion_brain_task`**: Manage tasks (`create`, `list`, `update`, `complete`).
- **`notion_brain_content`**: Manage social media drafts and post ideas by platform and publishing status.
- **`notion_brain_research`**: Log and list research citations, summaries, and findings.

---

## CLI Commands

The `hermes-brain` CLI provides maintenance utilities:

```bash
hermes-brain setup     # Run interactive database onboarding wizard
hermes-brain health    # Check database status, schema matches, and row counts
hermes-brain url       # Print Notion URL for the parent page (use --all for databases)
hermes-brain reset     # Recreate databases with schema mismatches
hermes-brain wipe      # Clear rows from specified databases (use --dry-run to test)
hermes-brain import    # Import legacy local MEMORY.md and USER.md files into Notion
hermes-brain update    # Check for and install updates from GitHub
```

---

## Development & Testing

Run unit tests:

```bash
pytest
```

Run linter and type checks:

```bash
ruff check .
mypy notion_brain
```

For project documentation, policies, and guidelines, see:
- [Architecture Details](docs/architecture.md)
- [Troubleshooting Guide](docs/troubleshooting.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Security Policy](SECURITY.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Changelog](CHANGELOG.md)

---

<p align="center">
  <a href="https://github.com/MNDL-27">
    <img src=".github/assets/labtocat.png" width="200" alt="Labtocat"/>
  </a>
</p>

<p align="center">
  <strong>MIT License © <a href="https://github.com/MNDL-27">MNDL-27</a></strong>
</p>

<p align="center">
  If you find this project useful, <strong>please consider starring it ⭐</strong> 
  or <a href="https://github.com/MNDL-27">following</a> for more AI infrastructure tools.
</p>

<p align="center">
  Built with ❤️ from <img src=".github/assets/twemoji-bd.svg" width="18" height="18" alt="Bangladesh" />
</p>
