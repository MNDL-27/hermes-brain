<div align="center">
  <a href="https://github.com/MNDL-27/hermes-brain">
    <img src=".github/assets/hero.png" alt="hermes-brain" width="600"/>
  </a>
</div>

> Notion-backed persistent memory for the Hermes AI agent ecosystem. Organizes notes, tasks, projects, research, and custom domains across structured Notion databases.

<div align="center">

  [![GitHub Release](https://img.shields.io/github/v/release/MNDL-27/hermes-brain?color=0073FF&labelColor=black&style=flat-square)](https://github.com/MNDL-27/hermes-brain/releases)
  [![GitHub Contributors](https://img.shields.io/github/contributors/MNDL-27/hermes-brain?color=0073FF&labelColor=black&style=flat-square)](https://github.com/MNDL-27/hermes-brain/graphs/contributors)
  [![GitHub Stars](https://img.shields.io/github/stars/MNDL-27/hermes-brain?color=0073FF&labelColor=black&style=flat-square)](https://github.com/MNDL-27/hermes-brain/stargazers)
  [![GitHub Issues](https://img.shields.io/github/issues/MNDL-27/hermes-brain?color=0073FF&labelColor=black&style=flat-square)](https://github.com/MNDL-27/hermes-brain/issues)
  [![License](https://img.shields.io/badge/license-MIT-green?labelColor=black&style=flat-square)](https://github.com/MNDL-27/hermes-brain/blob/main/LICENSE)
</div>

---

## Quickstart

### 1. Prerequisites

- Python 3.11 to 3.13
- Notion internal integration token ([create one at notion.so/my-integrations](https://www.notion.so/my-integrations))
- [Hermes Agent](https://hermes-agent.nousresearch.com/)

### 2. Install

Install the package into the Hermes Agent virtual environment:

```bash
~/.hermes/hermes-agent/venv/bin/pip install -e /path/to/hermes-brain
```

Or symlink into your Hermes user plugins directory:

```bash
mkdir -p ~/.hermes/plugins
ln -s /path/to/hermes-brain/notion_brain ~/.hermes/plugins/notion_brain
```

### 3. Configure Credentials

Add your Notion API token to `~/.hermes/.env`:

```bash
echo "NOTION_API_KEY=ntn_your_notion_token_here" >> ~/.hermes/.env
chmod 600 ~/.hermes/.env
```

### 4. Run Interactive Onboarding

Run the setup wizard to choose your databases:

```bash
hermes-brain setup
```

The wizard guides you through:
1. **Selecting standard databases** (`Memory`, `Tasks`, `Projects`, `Content`, `Research`, `Career`, `Entities`).
2. **Configuring custom databases** (define custom keys, Notion display titles, purpose, and field types such as `Reps:number`, `Exercise:select`).
3. **Automatic Notion bootstrapping** (creates the parent page and chosen databases).

Share the newly created **Hermes Brain** parent page in Notion with your integration (`•••` -> `Connections` -> add your integration).

### 5. Enable in Hermes Config

Update `~/.hermes/config.yaml`:

```yaml
memory:
  memory_enabled: true
  provider: notion_brain
```

Make sure `memory` is removed from `disabled_toolsets` if present.

---

## Databases & Schemas

### Standard Starter Databases

| Database | Domain Key | Default Kind | Tracked Fields |
|---|---|---|---|
| **Memory** | `memory` | note, lesson, decision | Title, Domain, Kind, Status, Tags, Confidence, Source Session, Last Seen |
| **Tasks** | `daily_work` | task | Title, Status, Priority (`urgent`, `high`, `med`, `low`), Due Date, Project, Tags |
| **Projects** | `projects` | decision, note | Title, Status, Decision Rationale, Tags, Confidence, Last Seen |
| **Content** | `social_content` | draft, idea | Title, Status (`draft`, `published`, `scheduled`), Platform, Tags |
| **Research** | `research` | source_note | Title, Findings Body, Sources, Tags, Status |
| **Career** | `career` | application | Title, Role, Company, Compensation, Status, Tags |
| **Entities** | `entities` | preference, person, tool | Title (Key-value), Kind, Tags, Confidence |

### Custom User Databases

You can add custom databases during onboarding (`hermes-brain setup`) or via non-interactive automation:

```bash
hermes-brain setup --standard-dbs 1,2,3 --custom-json '[{"key":"fitness","title":"Fitness & Workouts","fields":{"Reps":"number","Exercise":"select"}}]' --non-interactive
```

Every custom database automatically inherits the base audit schema (`Title`, `Domain`, `Status`, `Tags`, `Confidence`, `Source Session`, `Last Seen`) plus your specified custom properties.

---

## How It Works

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

1. **Non-Blocking Sync**: Conversation turns are classified and written to Notion using a background worker thread. The agent never waits on Notion HTTP round-trips.
2. **Prompt-Cache Safe**: Base system prompt blocks remain static. Recalled entries are dynamically injected via `prefetch()` and tool responses, preventing prompt-cache invalidation.
3. **Automatic Secret Redaction**: All outgoing text passes through regex sanitizers that redact Stripe, Notion, GitHub, Slack, AWS, and generic API keys before network transmission.
4. **Heuristic & LLM Extraction**: Uses zero-cost regex heuristics to extract tasks, decisions, and preferences. Supports optional local LLM extraction when `OPENAI_BASE_URL` is set.

---

## Tool Interfaces

Hermes has access to 5 dedicated tools when `notion_brain` is active:

### 1. `notion_brain_search`
Search across all Notion databases or filter by a specific database.
- `query` (required): Search text
- `database` (optional): `memory`, `tasks`, `projects`, `content`, `research`, `career`, `entities`, or custom database key
- `max_results` (optional): Number of records (default 8, max 20)

### 2. `notion_brain_remember`
Explicitly save a memory entry when auto-capture does not apply.
- `title` (required): Summary title
- `content` (required): Full description
- `domain` (optional): Target domain or custom database key
- `kind` (optional): `note`, `task`, `decision`, `preference`, `lesson`, `reminder`
- `status` (optional): `active`, `done`, `needs_review`
- `tags` (optional): List of tag strings
- `entities` (optional): People or organizations involved

### 3. `notion_brain_task`
Manage tasks in the Tasks database.
- `action`: `create`, `list`, `update`, `complete`
- `title`: Task description
- `priority`: `urgent`, `high`, `medium`, `low`
- `due`: ISO date (`YYYY-MM-DD`)
- `project`: Associated project name
- `page_id`: Target Notion page ID for updates

### 4. `notion_brain_content`
Track social media post ideas and drafts.
- `action`: `create`, `list`, `update`, `publish`, `archive`
- `title`: Headline or working title
- `body`: Post copy, captions, or draft text
- `platform`: `twitter`, `linkedin`, `instagram`, `youtube`, `bluesky`
- `status`: `draft`, `published`, `scheduled`, `idea`

### 5. `notion_brain_research`
Store research papers, articles, and citations.
- `action`: `save`, `list`
- `title`: Research topic or paper title
- `content`: Key findings, quotes, or notes
- `tags`: Topic tags

---

## CLI Management

The `hermes-brain` CLI provides workspace maintenance commands:

```bash
hermes-brain setup     # Run interactive database onboarding wizard
hermes-brain health    # Check database status, schema matches, and row counts
hermes-brain url       # Print Notion URL for the parent page (use --all for databases)
hermes-brain reset     # Recreate databases with schema mismatches
hermes-brain wipe      # Clear rows from specified databases (use --dry-run to test)
hermes-brain import    # Import local MEMORY.md and USER.md files into Notion
hermes-brain update    # Check for and install updates from GitHub
```

---

## Development & Testing

Run the test suite:

```bash
pytest
```

Run linting and type checks:

```bash
ruff check .
mypy notion_brain
```

---

## Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and add tests
4. Ensure tests and lints pass: `pytest && ruff check .`
5. Open a Pull Request

---

## Acknowledgments

- [Notion API](https://developers.notion.com/) — persistent database backend
- [Hermes Agent](https://hermes-agent.nousresearch.com/) — autonomous AI agent framework
- All contributors and users

---

## License

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
