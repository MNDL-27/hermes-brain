"""Small data model helpers for the Notion brain provider."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

PROVIDER_NAME = "notion_brain"
CACHE_FILE = "notion_brain.json"
DEFAULT_PARENT_PAGE = "Hermes Brain"
NOTION_API_VERSION = "2022-06-28"

DOMAINS = {
    "daily_work": "Daily Work",
    "projects": "Projects",
    "social_content": "Social Content",
    "research": "Research",
    "career": "Job/Career",
    "entities": "People/Entities",
    "memory": "Memory",
}

DATABASES = {
    "memory": "Memory",
    "tasks": "Tasks",
    "projects": "Projects",
    "content": "Content",
    "research": "Research",
    "career": "Career",
    "entities": "Entities",
}

DOMAIN_DATABASE = {
    "daily_work": "tasks",
    "projects": "projects",
    "social_content": "content",
    "research": "research",
    "career": "career",
    "entities": "entities",
    "memory": "memory",
}

STATUSES = {"active", "done", "needs_review"}
CONFIDENCES = {"high", "medium", "low"}

_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bntn_[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*(?:[\"\'`][^\"\'`\r\n]+[\"\'`]|[^\s\"\'`]+)"),
]


@dataclass
class BrainEntry:
    """Normalized memory item before storage."""

    domain: str
    title: str
    content: str
    kind: str = "note"
    status: str = "active"
    confidence: str = "medium"
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    source_session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def normalized(self) -> "BrainEntry":
        domain = normalize_domain(self.domain)
        status = self.status if self.status in STATUSES else "active"
        confidence = self.confidence if self.confidence in CONFIDENCES else "medium"
        return BrainEntry(
            domain=domain,
            title=clean_title(self.title),
            content=redact_secrets(self.content).strip(),
            kind=(self.kind or "note").strip()[:80],
            status=status,
            confidence=confidence,
            tags=dedupe_strings(self.tags),
            entities=dedupe_strings(self.entities),
            source_session_id=self.source_session_id,
            metadata=dict(self.metadata or {}),
        )


def normalize_domain(domain: str | None) -> str:
    raw = (domain or "memory").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "task": "daily_work",
        "tasks": "daily_work",
        "daily": "daily_work",
        "work": "daily_work",
        "project": "projects",
        "social": "social_content",
        "content": "social_content",
        "social_media": "social_content",
        "job": "career",
        "jobs": "career",
        "career": "career",
        "research": "research",
        "entity": "entities",
        "people": "entities",
        "person": "entities",
        "user": "entities",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in DOMAIN_DATABASE else "memory"


def database_for_domain(domain: str | None) -> str:
    return DOMAIN_DATABASE[normalize_domain(domain)]


def clean_title(title: str) -> str:
    text = re.sub(r"\s+", " ", (title or "Untitled").strip())
    return text[:120] or "Untitled"


def dedupe_strings(values: list[str] | tuple[str, ...] | None) -> list[str]:
    seen = set()
    out: list[str] = []
    for value in values or []:
        item = re.sub(r"\s+", " ", str(value).strip())
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item[:80])
    return out


def redact_secrets(text: str) -> str:
    redacted = text or ""
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def compact(text: str, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", redact_secrets(text).strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def keyword_tokens(text: str, *, limit: int = 8) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text or "")
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "what", "when", "where",
        "about", "should", "could", "would", "have", "has", "into", "your", "you",
        "are", "was", "were", "will", "can", "how", "why", "all", "our", "my",
    }
    out: list[str] = []
    seen = set()
    for word in words:
        key = word.lower()
        if key in stop or key in seen:
            continue
        seen.add(key)
        out.append(word[:40])
        if len(out) >= limit:
            break
    return out
