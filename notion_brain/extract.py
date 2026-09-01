"""Extractor and classifier for the Notion brain provider.

Extracts structured memories (Fact/Preference, Project State, Task) from conversation turns.
Supports LLM extraction with fallback to heuristic classification and strict routing rules.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

from .schema import BrainEntry, compact, dedupe_strings, keyword_tokens, redact_secrets

logger = logging.getLogger(__name__)

_CLEAN = re.compile(r"[`\"'”“‘’]")
_MERGE_WS = re.compile(r"\s+")

# ─── Routing Guards ─────────────────────────────────────────────────────────

_GIT_OR_CODE = re.compile(
    r"(?i)(\b(git\s+(commit|push|pull|status|checkout|branch|merge|rebase|clone|diff|add|log|stash|fetch|reset|init|remote))\b"
    r"|\b(npm|pnpm|yarn|pip|cargo|docker|kubectl|chmod|curl|wget|pytest|ruff|mypy)\s+[a-z0-9_./-]+"
    r"|^\s*(diff\s+--git|@@\s+-\d+|index\s+[0-9a-f]{7,})"
    r"|\b(def\s+\w+\(|function\s+\w+\(|import\s+\w+|const\s+\w+\s*=|class\s+\w+[:{])"
    r"|```)"
)

_CONVERSATIONAL_FILLER = re.compile(
    r"(?i)^(\s*(can you|could you|please|let me|let's|just|checking|looking|checking in|checking on|will check|will look|on it|one moment|thanks|thank you|sounds good|cool|nice|great|got it|awesome|sure thing|no problem)\b"
    r"|.*\b(can you check|could you check|let me check|just checking|looking into|checking out|will check|need to check)\b.*$)"
)

_TRIGGERS_TASK = re.compile(
    r"(?i)(\b(remind\s+me|todo|to-do|task|action\.item|deadline|due\s+date|due\s+(?:on|by|next|this|\d)|blocker)\b"
    r"|\b(must|have to|need to|gotta)\s+(create|make|build|fix|setup|send|add|update|implement|deploy|ship|write|refactor)\b"
    r"|\b(pending|waiting\.on)\b)"
)
_TRIGGERS_DECISION = re.compile(
    r"(?i)(\b(decided|chosen|elect|going.with|moving.forward|cancelled|pivot)\b"
    r"|(we.re) (using|going|sticking|rolling)\b"
    r"|(approved|rejected|greenlit|deprecated)\b)"
)
_TRIGGERS_PREFERENCE = re.compile(
    r"(?i)(\b(i|we|the.user|user)\s+(prefer|like|want|love|hate|use)\b"
    r"|(always|never|preferred|favorite|preference)\b"
    r"|(personality|style|habit|routine)\b)"
)
_TRIGGERS_RESEARCH = re.compile(
    r"(?i)(\b(source|citation|cited|according\s*\.?\s*to|reference|found\s+that|shows\s+that|paper|papers)\b"
    r"|(findings|conclusion|results\s+suggest|analysis\s+show|analysis\s+shows)\b"
    r"|(researched|studied|investigated|explored)\b)"
)
_TRIGGERS_CONTENT = re.compile(
    r"(?i)(\b(draft|post|tweet|linkedin|twitter|thread|hook|headline|caption)\b"
    r"|(content.idea|content.calendar|editorial|copy)\b"
    r"|(publish|launch|release|promote|share)\b)"
)
_TRIGGERS_CAREER = re.compile(
    r"(?i)(\b(interview|application|resume|cv|cover.letter|job.posting|hiring)\b"
    r"|(salary|offer|negotiate|relocate|remote|hybrid)\b"
    r"|(role|position|opportunity|career|promotion)\b)"
)
_TRIGGERS_PROJECT = re.compile(
    r"(?i)(\b(project|repo|repository|sprint|milestone|roadmap)\b"
    r"|(build|architectur|refactor|migration|deployment)\b"
    r"|(MVP|POC|prototype|iteration)\b)"
)

_EXCLUDE_RESPONSE = re.compile(
    r"(?i)^(yes|no|ok|okay|sure|done|got.it|will.do|on.it|checking|looking|one.moment)\s*[.!]?\s*$"
)

_PLATFORM_HINTS = re.compile(r"(?i)(\b(twitter|linkedin|instagram|tiktok|facebook|youtube|threads|bluesky|mastodon)\b)")

# ─── LLM Extractor ─────────────────────────────────────────────────────────

DEFAULT_LLM_URL = os.environ.get("OPENAI_BASE_URL", os.environ.get("OPENAI_API_BASE", "http://localhost:11434/v1"))
DEFAULT_LLM_MODEL = os.environ.get("HERMES_MODEL", os.environ.get("OPENAI_MODEL", "qwen3-coder-30b:latest"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("NOTION_BRAIN_LLM_TIMEOUT", "5.0"))

EXTRACTION_PROMPT = """You are a memory extractor for an AI assistant.
Analyze the conversation buffer and extract ONLY entries for these 3 categories:
1. 'fact' / 'entity' (Fact/Preference): Atomic key-value (e.g. 'Hosting: Prefers VPS/Docker over Cloud SaaS', 'Language: Prefers Python', 'IDE: Neovim').
2. 'project' (Project State): Specific milestone, architecture decision, or blocker.
3. 'task' (Task): Concrete actionable item with status 'todo' | 'in_progress' | 'done'.

Do NOT extract:
- Git or shell commands (e.g. git commit, git push, npm install)
- Conversational filler or pleasantries (e.g. 'can you check', 'let me know', 'thanks')
- Temporary chat questions or ephemeral status messages

Return a JSON array of objects matching this schema:
[
  {
    "category": "entity|task|fact|project",
    "title": "Concise Label (atomic key-value for facts/preferences)",
    "content": "Clean summary",
    "status": "todo|in_progress|done|active",
    "tags": ["tag1", "tag2"]
  }
]
If nothing should be remembered, return [].
Return ONLY the raw JSON array, without markdown formatting or commentary."""


def extract_with_llm(
    user_content: str,
    assistant_content: str,
    *,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = LLM_TIMEOUT_SECONDS,
) -> list[BrainEntry] | None:
    """Pass conversation buffer to LLM to extract structured memories.

    Returns list of BrainEntry on success, or None to fall back to heuristics.
    """
    # Privacy: scrub secrets and cap size before exfiltrating to an LLM
    # (even localhost Ollama). Without this, Notion tokens / private keys
    # pasted in a turn are POSTed to OPENAI_BASE_URL verbatim.
    raw_buffer = f"User: {user_content}\nAssistant: {assistant_content}".strip()
    if not raw_buffer:
        return []
    buffer = redact_secrets(compact(raw_buffer, 4000))

    url = (base_url or os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE") or DEFAULT_LLM_URL).rstrip("/")
    endpoint = f"{url}/chat/completions"
    model_name = model or os.environ.get("HERMES_MODEL") or os.environ.get("OPENAI_MODEL") or DEFAULT_LLM_MODEL
    key = api_key or os.environ.get("OPENAI_API_KEY", "dummy-key")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": buffer},
        ],
        "temperature": 0.0,
    }

    try:
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
        if not resp.ok:
            return None
        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"].strip()
        clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
        items = json.loads(clean_json)
        if not isinstance(items, list):
            return None

        entries: list[BrainEntry] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            cat = str(item.get("category", "")).lower()
            title = str(item.get("title", "")).strip()
            content = str(item.get("content", "")).strip() or title
            tags = [str(t) for t in item.get("tags", []) if t]
            status = str(item.get("status", "active")).lower()

            if not title:
                continue

            if cat in ("entity", "fact", "preference"):
                is_pref = any(w in title.lower() or w in content.lower() for w in ("prefer", "preference", "like", "favorite", "hate", "always", "never"))
                kind = "preference" if is_pref else "topic"
                entries.append(BrainEntry(
                    domain="entities",
                    title=title[:120],
                    content=compact(content, 600),
                    kind=kind,
                    tags=dedupe_strings(["preference" if kind == "preference" else "entity"] + tags),
                    confidence="high",
                ))
            elif cat in ("project", "project state", "project_state"):
                is_dec = "decision" in title.lower() or "decided" in content.lower() or "chosen" in content.lower()
                entries.append(BrainEntry(
                    domain="projects",
                    title=title[:120],
                    content=compact(content, 900),
                    kind="decision" if is_dec else "note",
                    tags=dedupe_strings(tags),
                    confidence="high",
                ))
            elif cat in ("task", "daily_work"):
                st = "done" if status in ("done", "completed") else "active"
                entries.append(BrainEntry(
                    domain="daily_work",
                    title=title[:120],
                    content=compact(content, 900),
                    kind="task",
                    status=st,
                    tags=dedupe_strings(tags),
                    confidence="high",
                ))

        return entries
    except Exception as exc:
        logger.debug("LLM extraction skipped/failed: %s", redact_secrets(str(exc)))
        return None


def _format_atomic_title(snippet: str, fallback: str) -> str:
    """Format preference/fact as an atomic key-value title."""
    cleaned = _CLEAN.sub("", _MERGE_WS.sub(" ", snippet).strip())
    if not cleaned:
        return fallback
    if ":" in cleaned and len(cleaned.split(":", 1)[0].split()) <= 3:
        return cleaned[:80]
    m = re.search(r"(?i)\b(?:always|never)?\s*(?:prefer|like|use)\s+(.+?)(?:\s+over\s+(.+?))?(?:\s+for\s+(.+?))?$", cleaned)
    if m:
        item = m.group(1).strip()
        over = m.group(2).strip() if m.group(2) else ""
        for_what = m.group(3).strip() if m.group(3) else ""
        if for_what and over:
            return f"{for_what.capitalize()}: Prefers {item} over {over}"[:80]
        if for_what:
            return f"{for_what.capitalize()}: Prefers {item}"[:80]
        if over:
            return f"Preference: {item} over {over}"[:80]
        return f"Preference: {item}"[:80]
    m_fav = re.search(r"(?i)\bfavorite\s+([a-z0-9_-]+)\s+is\s+(.+)", cleaned)
    if m_fav:
        return f"{m_fav.group(1).capitalize()}: {m_fav.group(2).strip()}"[:80]
    return _brief_title(cleaned, fallback)


def classify_turn(user_content: str, assistant_content: str) -> list[BrainEntry]:
    """Extract memory entries from a single turn.

    Runs LLM summarizer if available; falls back to heuristic classification with strict routing rules.
    """
    user = _CLEAN.sub("", user_content or "").strip()
    assistant = _CLEAN.sub("", assistant_content or "").strip()
    combined = f"{user} {assistant}"

    if not combined:
        return []
    if _EXCLUDE_RESPONSE.match(_MERGE_WS.sub("", assistant.strip())):
        return []

    # Try LLM extraction first
    llm_entries = extract_with_llm(user, assistant)
    if llm_entries is not None:
        return llm_entries

    entries: list[BrainEntry] = []
    seen_kinds: set[str] = set()
    tokens = keyword_tokens(combined, limit=5)

    # Daily work tasks (enforce: conversational filler and git/code NEVER route to Tasks)
    if _TRIGGERS_TASK.search(combined):
        snippet = _extract_sentence(user, _TRIGGERS_TASK) or _extract_sentence(assistant, _TRIGGERS_TASK) or combined
        user_lower = (user or "").lower()
        is_negated = "not a" in user_lower
        is_code = bool(_GIT_OR_CODE.search(snippet))
        is_filler = bool(_CONVERSATIONAL_FILLER.match(user.strip()) or _CONVERSATIONAL_FILLER.search(snippet))
        if not is_negated and not is_code and not is_filler:
            entries.append(BrainEntry(
                domain="daily_work", title=_brief_title(snippet, "Task"),
                content=compact(snippet, 900), kind="task",
                tags=tokens,
                status="active", confidence="high" if "deadline" in combined.lower() or "due" in combined.lower() else "medium",
            ))
            seen_kinds.add("task")

    # Projects and decisions (Project State)
    project_pattern = _TRIGGERS_PROJECT if _TRIGGERS_PROJECT.search(combined) else _TRIGGERS_DECISION if _TRIGGERS_DECISION.search(combined) else None
    if project_pattern and "project" not in seen_kinds:
        snippet = _extract_sentence(combined, project_pattern)
        entries.append(BrainEntry(
            domain="projects", title=_brief_title(snippet, "Project"),
            content=compact(snippet, 900), kind="decision" if _TRIGGERS_DECISION.search(snippet) else "note",
            tags=tokens,
            confidence="high" if _TRIGGERS_DECISION.search(snippet) else "medium",
        ))
        seen_kinds.add("project")

    # Research
    if _TRIGGERS_RESEARCH.search(combined) and "research" not in seen_kinds:
        snippet = _extract_sentence(combined, _TRIGGERS_RESEARCH)
        entries.append(BrainEntry(
            domain="research", title=_brief_title(snippet, "Research"),
            content=compact(snippet, 900), kind="source_note",
            tags=dedupe_strings(tokens + ["research"]),
        ))
        seen_kinds.add("research")

    # Social content (enforce: git/code commands NEVER route to Content)
    if _TRIGGERS_CONTENT.search(combined) and "content" not in seen_kinds:
        if not _GIT_OR_CODE.search(combined):
            snippet = _extract_sentence(combined, _TRIGGERS_CONTENT)
            platform = _find_platform(user) or _find_platform(assistant) or None
            entries.append(BrainEntry(
                domain="social_content", title=_brief_title(snippet, "Content"),
                content=compact(snippet, 900), kind="draft",
                tags=dedupe_strings(tokens + ([platform] if platform else [])),
                status="draft",
            ))
            seen_kinds.add("content")

    # Career
    if _TRIGGERS_CAREER.search(combined) and "career" not in seen_kinds:
        snippet = _extract_sentence(combined, _TRIGGERS_CAREER)
        entries.append(BrainEntry(
            domain="career", title=_brief_title(snippet, "Career"),
            content=compact(snippet, 900),
            tags=tokens,
        ))
        seen_kinds.add("career")

    # User preferences / facts (Fact/Preference: atomic key-value)
    if _TRIGGERS_PREFERENCE.search(combined):
        snippet = _extract_sentence(combined, _TRIGGERS_PREFERENCE)
        snip_lower = snippet.lower()
        title = _format_atomic_title(snippet, "Preference")
        entries.append(BrainEntry(
            domain="entities", title=title,
            content=compact(snippet, 600),
            kind="preference", tags=["preference"] + tokens,
            confidence="high" if ("always" in snip_lower or "prefer" in snip_lower or "favorite" in snip_lower) else "medium",
        ))

    return entries


def _extract_sentence(text: str, trigger: re.Pattern) -> str:
    text = _MERGE_WS.sub(" ", text).strip()
    best = text[:400]
    for match in trigger.finditer(text):
        start = match.start()
        sent_start = max(0, _rev_sentence_boundary(text, start))
        sent_end = _fwd_sentence_boundary(text, start + match.end())
        candidate = text[sent_start:sent_end].strip()
        if len(candidate) < 30:
            continue
        if len(candidate) > len(best):
            best = candidate
    return best[:900]


def _rev_sentence_boundary(text: str, pos: int) -> int:
    for i in range(pos - 1, max(pos - 400, -1), -1):
        if text[i] in ".!?" and (i + 2 >= len(text) or text[i + 1] == " "):
            return i + 1
    return max(0, pos - 300)


def _fwd_sentence_boundary(text: str, pos: int) -> int:
    for i in range(min(pos, len(text) - 1), min(pos + 400, len(text))):
        if text[i] in ".!?":
            return i + 1
    return len(text)


def _brief_title(snippet: str, fallback: str) -> str:
    snippet = _CLEAN.sub("", _MERGE_WS.sub(" ", snippet).strip())
    return snippet[:80] or fallback


def _find_platform(text: str) -> str | None:
    m = _PLATFORM_HINTS.search(text or "")
    if m:
        return m.group(1).lower()
    return None


def classify_text(text: str) -> dict[str, str]:
    """Classify arbitrary text for on_memory_write extraction.

    Runs classify_turn with empty assistant context and falls back to a generic
    memory note if no specific triggers match.
    """
    entries = classify_turn(text, "")
    if entries:
        top = entries[0]
        return {
            "domain": top.domain,
            "title": top.title,
            "kind": top.kind,
        }
    return {
        "domain": "memory",
        "title": _brief_title(text, "Note"),
        "kind": "note",
    }

