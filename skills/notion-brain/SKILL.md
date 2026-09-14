---
name: notion-brain
description: "Notion-backed long-term memory for Hermes. Captures and recalls daily work, projects, social content, research, and career context across structured Notion databases — persists across sessions."
version: 1.0.0
metadata:
  hermes:
    tags: [notion, memory, brain, persistent, recall, tasks, projects, research, career]
    related_skills: [research, social-media, github]
triggers:
  - "recall what we discussed about"
  - "remember that"
  - "save this"
  - "what tasks do I have"
  - "show my tasks"
  - "content idea"
  - "research on"
  - "application status"
  - "what did we decide"
  - "past decisions"
  - "find in my brain"
  - "create task"
  - "save research"
---

# Notion Brain

Persistent cross-session memory stored in the Hermes Brain Notion workspace (7 databases, 5 domains). Unlike built-in memory, this provides structured recall with tags, confidence levels, status tracking, and entity linking. Use Notion brain when context needs to survive across sessions or span multiple domains.

## Domains

| Domain key | Label | Database | Purpose |
|---|---|---|---|
| `daily_work` | Daily Work | Tasks | Task tracking, deadlines, follow-ups |
| `projects` | Projects | Projects | Milestones, architecture decisions, deployment notes |
| `social_content` | Social Content | Content | Draft ideas, platform targeting, publishing |
| `research` | Research | Research | Sources, findings, analysis conclusions |
| `career` | Job/Career | Career | Job applications, interviews, skills development |

Aliases are normalized automatically: `task` → `daily_work`, `content` → `social_content`, `job` → `career`, etc.

## How It Works

**Automatic capture.** `classify_turn` runs on every conversation turn using stdlib regex heuristics. Matched content is classified into the right domain and written to Notion in the background — no blocking. Secrets are redacted before storage.

**Smart recall.** `prefetch()` runs on every user message, searching Notion for relevant entries and injecting a `<memory-context>` block into the system prompt. No manual recall needed for routine queries.

**Session summaries.** On session end, a summary is saved to the Memory database with session ID and topic keywords.

## When to Use the Tools

Use Notion tools when:
- The user explicitly asks to recall something from a previous session
- The user says "remember" or wants to save something for later
- You need structured task management (create, list, update, complete tasks)
- The user is building social content and wants to track drafts and publishing status
- Saving research findings, sources, or citations worth referencing later
- Any situation where context should persist beyond the current session

You do NOT need to manually save routine facts — capture is automatic. Use `notion_brain_remember` only for things the heuristics miss (personal preferences, one-off notes without trigger keywords).

## Tool Usage

### notion_brain_search

Semantic-text search across all Notion brain databases.

**When:** User asks "what did we discuss about X", "find past decisions on Y", "recall..." or any need to surface stored context.

**Parameters:**
- `query` (required): Search string
- `database` (optional): Filter to one DB — `memory|tasks|projects|content|research|career|entities`
- `max_results` (optional): 1–20, default 8

### notion_brain_remember

Explicitly save a memory entry to any domain.

**When:** User says "remember X", "save this for later", or when automatic capture will miss something important.

**Parameters:**
- `title` (required): Short title, max 120 chars
- `content` (required): Full content, up to 900 chars
- `domain` (optional): `daily_work|projects|social_content|research|career|entities`
- `kind` (optional): `note|task|decision|preference|source_note|draft|lesson|reminder`
- `status` (optional): `active|done|draft|published|archived|needs_review`
- `tags` / `entities` (optional): Arrays for filtering and linking

### notion_brain_task

CRUD for the Tasks database (daily_work).

**Actions:**
- `create`: title (required), priority, due date `YYYY-MM-DD`, project, tags
- `list`: optional status filter
- `update` / `complete`: page_id + fields

### notion_brain_content

CRUD for the Content database (social_content).

**Actions:**
- `create`: title (required), body, status (`draft|published|scheduled|idea`), platform, tags
- `list`: newest entries first
- `publish` / `archive`: page_id → changes status
- `update`: page_id + fields

### notion_brain_research

Save and list research findings.

**Actions:**
- `save`: title (required), content, tags, status
- `list`: recent research entries

## Domain Best Practices

**daily_work.** Tasks auto-classify from "need to", "remind me", "deadline", "follow up". Use `notion_brain_task` for structured management. Set priority and due date when the user mentions urgency or a date.

**projects.** Architecture decisions get `kind=decision`, confidence `high` — highest-value entries. Include rationale, not just the decision. Tag with repo/module names.

**social_content.** Always tag with platform — Notion Brain auto-detects Twitter/LinkedIn/TikTok/etc. from text. Status flow: `idea` → `draft` → `published` / `archived`.

**research.** Store sources with key findings in the content body. Tag with topic areas ("ml", "papers", "benchmark"). Confidence `high` for peer-reviewed sources, `medium` for blogs.

**career.** Track applications: title = company + role, tags include company name. Interview prep and feedback go in content.

## Key Rules

1. **Never dump full databases** into context — search with a specific query.
2. **Trust the auto-capture** — it runs after every turn via heuristic classification.
3. **Cross-reference entities**: tag tasks/decisions with people and project names for better recall.
4. **Use explicit saves sparingly** — `notion_brain_remember` is for things heuristics miss; routine facts are captured automatically.
5. **Prefetch is automatic.** Smart recall runs on every message — you don't need to search unless prefetch returned nothing relevant.
6. **Secrets are redacted.** Content matching token/key/secret patterns is stripped before storage.
