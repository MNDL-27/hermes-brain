"""Heuristic capture classifier for the Notion brain provider.

Extracts structured memories from conversation turns without an LLM call.
Uses stdlib string matching only.
"""

from __future__ import annotations

import re
from typing import Any

from .schema import BrainEntry, compact, dedupe_strings, keyword_tokens, redact_secrets

_CLEAN = re.compile(r"[`\"'”“‘’]")
_MERGE_WS = re.compile(r"\s+")

_TRIGGERS_TASK = re.compile(
    r"(?i)(\b(remind|todo|to-do|task|follow.up|deadline|due|blocker|schedule)\b"
    r"|(will|need|must|have to|gotta)\s+(create|make|build|fix|setup|send|add|update|check)\b"
    r"|(pending|in.progress|waiting.on|action.item)\b)"
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


def classify_turn(user_content: str, assistant_content: str) -> list[BrainEntry]:
    """Extract memory entries from a single turn.

    Returns empty list when nothing memorable is found.
    No LLM call — pure heuristic classification.
    """
    user = _CLEAN.sub("", user_content or "").strip()
    assistant = _CLEAN.sub("", assistant_content or "").strip()
    combined = f"{user} {assistant}"

    if not combined:
        return []
    if _EXCLUDE_RESPONSE.match(_MERGE_WS.sub("", assistant.strip())):
        return []

    entries: list[BrainEntry] = []
    seen_kinds: set[str] = set()
    tokens = keyword_tokens(combined, limit=5)

    # Daily work tasks
    if _TRIGGERS_TASK.search(combined):
        snippet = _extract_sentence(user, _TRIGGERS_TASK) or _extract_sentence(assistant, _TRIGGERS_TASK) or combined
        user_lower = (user or "").lower()
        if "not a" not in user_lower:
            entries.append(BrainEntry(
                domain="daily_work", title=_brief_title(snippet, "Task"),
                content=compact(snippet, 900), kind="task",
                tags=tokens,
                status="active", confidence="high" if "deadline" in combined.lower() or "due" in combined.lower() else "medium",
            ))
            seen_kinds.add("task")

    # Projects and decisions
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

    # Social content
    if _TRIGGERS_CONTENT.search(combined) and "content" not in seen_kinds:
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

    # User preferences (always capture when triggered)
    if _TRIGGERS_PREFERENCE.search(combined):
        snippet = _extract_sentence(combined, _TRIGGERS_PREFERENCE)
        entries.append(BrainEntry(
            domain="entities", title=_brief_title(snippet, "Preference"),
            content=compact(snippet, 600),
            kind="preference", tags=["preference"] + tokens,
            confidence="high" if ("always" in combined.lower() and ("prefer" in combined.lower() or "favorite" in combined.lower() or "use" in combined.lower())) or "prefer" in combined.lower() else "medium",
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