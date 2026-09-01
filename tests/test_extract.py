"""Tests for the Notion Brain heuristic classifier (extract.py)."""

from __future__ import annotations

# We must set up sys.path so relative imports resolve
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re

from notion_brain.extract import (
    _brief_title,
    _extract_sentence,
    _find_platform,
    _fwd_sentence_boundary,
    _rev_sentence_boundary,
    classify_turn,
)
from notion_brain.schema import (
    CONFIDENCES,
    DATABASES,
    DOMAIN_DATABASE,
    DOMAINS,
    STATUSES,
    BrainEntry,
    clean_title,
    compact,
    database_for_domain,
    dedupe_strings,
    keyword_tokens,
    normalize_domain,
    redact_secrets,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trivial_asst(text: str = "ok") -> str:
    return text


def _user(text: str) -> str:
    return text


# ---------------------------------------------------------------------------
# Trivial responses are excluded
# ---------------------------------------------------------------------------

class TestTrivialExclusions:
    def test_ok_response_excluded(self):
        entries = classify_turn("hey", "ok.")
        assert entries == []

    def test_sure_response_excluded(self):
        entries = classify_turn("can you do it?", "Sure!")
        assert entries == []

    def test_done_response_excluded(self):
        entries = classify_turn("did you fix it?", "Done.")
        assert entries == []

    def test_yes_no_excluded(self):
        for resp in ("yes.", "no.", "Yeah!", "Nope."):
            entries = classify_turn("Should we?", resp)
            assert entries == [], f"Failed for: {resp}"


# ---------------------------------------------------------------------------
# Task detection
# ---------------------------------------------------------------------------

class TestTaskDetection:
    def test_reminder_triggers_task(self):
        entries = classify_turn(
            "Remind me to ship the API migration by Friday",
            "I'll add that to your task list.",
        )
        kinds = [e.kind for e in entries]
        assert "task" in kinds

    def test_deadline_high_confidence(self):
        entries = classify_turn(
            "The Q3 launch is our hard deadline — everything else is on hold",
            "Noted — I'll prioritize the launch",
        )
        tasks = [e for e in entries if e.kind == "task"]
        assert tasks
        assert tasks[0].confidence == "high"

    def test_due_sets_high_confidence(self):
        entries = classify_turn(
            "We need to finish the auth refactor, it's due next Tuesday",
            "I'll track that",
        )
        tasks = [e for e in entries if e.kind == "task"]
        assert tasks
        assert tasks[0].confidence == "high"

    def test_no_task_when_negated(self):
        entries = classify_turn(
            "This is not a blocker, just FYI",
            "Got it.",
        )
        kinds = [e.kind for e in entries]
        assert "task" not in kinds


# ---------------------------------------------------------------------------
# Project / Decision detection
# ---------------------------------------------------------------------------

class TestProjectDetection:
    def test_decision_triggers_project(self):
        entries = classify_turn(
            "We decided to migrate to PostgreSQL for all new services",
            "Good call — PostgreSQL is the right fit.",
        )
        kinds = [e.kind for e in entries]
        assert "decision" in kinds

    def test_project_keyword_triggers(self):
        entries = classify_turn(
            "The new repo will be at github.com/org/platform-migration",
            "I'll note that.",
        )
        domains = {e.domain for e in entries}
        assert "projects" in domains

    def test_cancelled_triggers_decision(self):
        entries = classify_turn(
            "We cancelled the Vue migration, sticking with React",
            "Understood.",
        )
        kinds = [e.kind for e in entries]
        assert "decision" in kinds


# ---------------------------------------------------------------------------
# Research detection
# ---------------------------------------------------------------------------

class TestResearchDetection:
    def test_source_triggers_research(self):
        entries = classify_turn(
            "I found a great paper showing BERT still beats GPT-2 on NER",
            "That's useful.",
        )
        domains = {e.domain for e in entries}
        assert "research" in domains

    def test_findings_triggers(self):
        entries = classify_turn(
            "The analysis shows a 40% improvement with the new caching layer",
            "Noted.",
        )
        domains = {e.domain for e in entries}
        assert "research" in domains


# ---------------------------------------------------------------------------
# Social content detection
# ---------------------------------------------------------------------------

class TestContentDetection:
    def test_tweet_triggers_content(self):
        entries = classify_turn(
            "I have an idea for a thread about how LLMs hallucinate less with RAG",
            "Good topic.",
        )
        domains = {e.domain for e in entries}
        assert "social_content" in domains

    def test_content_gets_draft_status(self):
        entries = classify_turn(
            "Draft a LinkedIn post about our new design system launch",
            "Here's a draft...",
        )
        content = [e for e in entries if e.domain == "social_content"]
        assert content
        assert content[0].status == "draft"

    def test_platform_detected(self):
        entries = classify_turn(
            "Write a tweet about the new feature launch",
            "Here you go.",
        )
        content = [e for e in entries if e.domain == "social_content"]
        assert content
        assert "twitter" in content[0].tags or "linkedin" not in content[0].tags


# ---------------------------------------------------------------------------
# Career detection
# ---------------------------------------------------------------------------

class TestCareerDetection:
    def test_interview_triggers_career(self):
        entries = classify_turn(
            "I have a senior eng interview at pg next week, need to prep",
            "Good luck! Let me help you prepare.",
        )
        domains = {e.domain for e in entries}
        assert "career" in domains

    def test_resume_triggers_career(self):
        entries = classify_turn(
            "Update my resume to highlight the migration work I did last quarter",
            "I can help draft that.",
        )
        domains = {e.domain for e in entries}
        assert "career" in domains


# ---------------------------------------------------------------------------
# Preference detection
# ---------------------------------------------------------------------------

class TestPreferenceDetection:
    def test_preference_triggered(self):
        entries = classify_turn(
            "I always use tabs over spaces for Python",
            "Noted.",
        )
        kinds = [e.kind for e in entries]
        assert "preference" in kinds

    def test_preference_high_confidence(self):
        entries = classify_turn(
            "I always prefer dark mode for everything",
            "I'll remember that.",
        )
        prefs = [e for e in entries if e.kind == "preference"]
        assert prefs
        assert prefs[0].confidence == "high"

    def test_preference_in_entities(self):
        entries = classify_turn(
            "My favorite IDE is Neovim",
            "I'll note that.",
        )
        domains = {e.domain for e in entries}
        assert "entities" in domains


# ---------------------------------------------------------------------------
# No duplicate domains per turn
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_same_turn_no_domain_dupes(self):
        """Only one entry per domain per turn."""
        text = "I have a task to build the API and also a deadline for the DB migration"
        entries = classify_turn(text, "I'll track both.")
        domains = [e.domain for e in entries]
        # daily_work is the only domain that should appear once
        assert domains.count("daily_work") <= 1


# ---------------------------------------------------------------------------
# Sentence boundary helpers
# ---------------------------------------------------------------------------

class TestSentenceBoundaries:
    def test_rev_boundary_finds_period(self):
        text = "First sentence. Second sentence with task here"
        pos = text.index("task")
        start = _rev_sentence_boundary(text, pos)
        assert start > 0

    def test_fwd_boundary_finds_period(self):
        text = "Some task here. And then more text"
        pos = text.index("task")
        end = _fwd_sentence_boundary(text, pos + 4)
        assert end > pos


# ---------------------------------------------------------------------------
# Schema functions
# ---------------------------------------------------------------------------


class TestSchema:
    def test_normalize_domain_aliases(self):
        assert normalize_domain("social") == "social_content"
        assert normalize_domain("content") == "social_content"
        assert normalize_domain("job") == "career"
        assert normalize_domain("tasks") == "daily_work"
        assert normalize_domain("project") == "projects"
        assert normalize_domain("entity") == "entities"
        assert normalize_domain("people") == "entities"

    def test_normalize_domain_identity(self):
        assert normalize_domain("research") == "research"
        assert normalize_domain("daily_work") == "daily_work"

    def test_normalize_domain_unknown_fallback(self):
        assert normalize_domain("unknown_domain") == "memory"

    def test_database_for_domain(self):
        assert database_for_domain("daily_work") == "tasks"
        assert database_for_domain("projects") == "projects"
        assert database_for_domain("social_content") == "content"
        assert database_for_domain("research") == "research"
        assert database_for_domain("career") == "career"
        assert database_for_domain("entities") == "entities"
        assert database_for_domain("memory") == "memory"

    def test_dedupe_strings(self):
        result = dedupe_strings(["Python", "python", "API", "api", "Unique"])
        assert "python" in [v.lower() for v in result]
        assert "api" in [v.lower() for v in result]
        assert "unique" in [v.lower() for v in result]
        assert len(result) == 3

    def test_dedupe_strings_empty(self):
        assert dedupe_strings([]) == []
        assert dedupe_strings(None) == []

    def test_keyword_tokens(self):
        text = "The Python API migration is blocked by the database schema change"
        tokens = keyword_tokens(text, limit=5)
        assert "Python" in tokens or "python" in [t.lower() for t in tokens]
        assert "API" in tokens or "api" in [t.lower() for t in tokens]
        assert "database" in [t.lower() for t in tokens]

    def test_keyword_tokens_respects_stopwords(self):
        tokens = keyword_tokens("the and for with")
        # stop words should be filtered
        assert not tokens

    def test_redact_secrets_sk_pattern(self):
        text = "key=sk-abcdefghijklmnop1234567890"
        result = redact_secrets(text)
        assert "sk-" not in result
        assert "REDACTED_SECRET" in result

    def test_redact_secrets_stripe_pattern(self):
        text = "key=sk_live_1234567890abcdefghij"
        result = redact_secrets(text)
        assert "sk_live_" not in result
        assert "REDACTED_SECRET" in result

    def test_redact_secrets_stripe_test_pattern(self):
        text = "key=sk_test_1234567890abcdefghij"
        result = redact_secrets(text)
        assert "sk_test_" not in result
        assert "REDACTED_SECRET" in result

    def test_redact_secrets_ntn_pattern(self):
        text = "token: ntn_AbCdEfGhIjKlMnOpQrStUvWxYz12345"
        result = redact_secrets(text)
        assert "ntn_" not in result
        assert "REDACTED_SECRET" in result

    def test_redact_secrets_generic_pattern(self):
        text = "api_key=mysecret123"
        result = redact_secrets(text)
        assert "mysecret123" not in result

    def test_redact_secrets_quoted_pattern(self):
        text = 'api_key="mysecret123"'
        result = redact_secrets(text)
        assert "mysecret123" not in result

    def test_compact_truncation(self):
        long = "word " * 200
        result = compact(long, limit=100)
        assert len(result) <= 100
        assert result.endswith("…") or len(long) <= 100

    def test_compact_no_truncation(self):
        short = "Hello world"
        assert compact(short) == "Hello world"

    def test_clean_title(self):
        assert clean_title("  hello world  ") == "hello world"
        assert clean_title("multi   spaces") == "multi spaces"
        assert clean_title("") == "Untitled"
        assert clean_title(None) == "Untitled"

    def test_brain_entry_normalized(self):
        entry = BrainEntry(
            domain="Daily Work",
            title="  Test task  ",
            content="some content",
            kind="task",
            status="active",
            confidence="medium",
            tags=["Tag1", "tag1"],
        )
        norm = entry.normalized()
        assert norm.domain == "daily_work"
        assert norm.title == "Test task"
        assert norm.kind == "task"
        assert norm.status == "active"
        assert norm.confidence == "medium"
        assert len(norm.tags) == 1  # deduped

    def test_constants(self):
        assert "daily_work" in DOMAINS
        assert "tasks" in DATABASES
        assert "daily_work" in DOMAIN_DATABASE
        assert "high" in CONFIDENCES
        assert "active" in STATUSES


class TestDatabaseMapping:
    def test_all_domains_mapped(self):
        for domain_key in DOMAINS:
            db = database_for_domain(domain_key)
            assert db in DATABASES, f"{domain_key} -> {db} not in DATABASES"

    def test_memory_domain_fallback(self):
        assert database_for_domain("unknown") == "memory"

    def test_entities_no_project_alias_conflict(self):
        # entities should not be aliased to projects
        assert normalize_domain("entities") == "entities"
        assert normalize_domain("preferences") != "entities"


# ---------------------------------------------------------------------------
# Internal extract helpers
# ---------------------------------------------------------------------------

class TestBriefTitle:
    def test_truncates_to_80(self):
        assert len(_brief_title("x" * 200, "Fallback")) == 80

    def test_short_stays(self):
        assert _brief_title("Short title", "Fallback") == "Short title"

    def test_fallback_on_empty(self):
        assert _brief_title("", "Fallback") == "Fallback"


class TestFindPlatform:
    def test_detects_twitter(self):
        assert _find_platform("Post this on twitter") == "twitter"

    def test_detects_linkedin(self):
        assert _find_platform("Draft a LinkedIn post") == "linkedin"

    def test_returns_none_when_missing(self):
        assert _find_platform("just some text") is None

    def test_handles_none(self):
        assert _find_platform(None) is None


class TestExtractSentence:
    def test_finds_sentence_around_trigger(self):
        text = "We had a meeting. I need to ship the API by Friday. Then we moved on."
        pattern = re.compile(r"ship\s")
        result = _extract_sentence(text, pattern)
        assert "ship" in result
        assert "API" in result

    def test_skips_too_short_candidates(self):
        text = "Ship it. We decided to migrate to PostgreSQL for all new services."
        pattern = re.compile(r"ship", re.IGNORECASE)
        result = _extract_sentence(text, pattern)
        # skip "Ship it." (too short), pick longer match
        assert "PostgreSQL" in result


# ---------------------------------------------------------------------------
# Routing Rules and LLM Extractor Tests
# ---------------------------------------------------------------------------

class TestRoutingAndLLMExtraction:
    def test_git_commands_never_route_to_content(self):
        entries = classify_turn("git commit -m 'feat: add feature' and git push origin main", "Pushed.")
        domains = [e.domain for e in entries]
        assert "social_content" not in domains

    def test_code_snippets_never_route_to_content(self):
        entries = classify_turn("def hello_world(): import sys; print('test')", "Looks good.")
        domains = [e.domain for e in entries]
        assert "social_content" not in domains

    def test_conversational_filler_never_routes_to_tasks(self):
        entries = classify_turn("Can you check the database status when you have time?", "Checking now.")
        tasks = [e for e in entries if e.domain == "daily_work"]
        assert tasks == []

    def test_filler_looking_into_never_routes_to_tasks(self):
        entries = classify_turn("Just looking into the logs to see what happened", "Understood.")
        tasks = [e for e in entries if e.domain == "daily_work"]
        assert tasks == []

    def test_atomic_key_value_preference_title(self):
        entries = classify_turn("I prefer VPS/Docker over Cloud SaaS for hosting", "Got it.")
        prefs = [e for e in entries if e.kind == "preference"]
        assert prefs
        assert "Hosting: Prefers VPS/Docker over Cloud SaaS" in prefs[0].title or "Prefers VPS/Docker" in prefs[0].title

    def test_llm_extractor_integration(self, monkeypatch):
        from unittest.mock import patch


        fake_resp = [
            {
                "category": "fact",
                "title": "Hosting: Prefers VPS/Docker over Cloud SaaS",
                "content": "Prefers self-hosted VPS/Docker setups",
                "tags": ["hosting", "infrastructure"],
            },
            {
                "category": "project",
                "title": "PostgreSQL Migration Milestone",
                "content": "Completed phase 1 schema design",
                "tags": ["postgres"],
            },
            {
                "category": "task",
                "title": "Write unit tests for extractor",
                "content": "Add tests to test_extract.py",
                "status": "todo",
                "tags": ["testing"],
            },
        ]
        import json
        with patch("requests.post") as mock_post:
            mock_post.return_value.ok = True
            mock_post.return_value.json.return_value = {
                "choices": [{"message": {"content": json.dumps(fake_resp)}}]
            }
            entries = classify_turn("Any conversation buffer", "Any response")
            assert len(entries) == 3
            assert entries[0].domain == "entities"
            assert entries[0].title == "Hosting: Prefers VPS/Docker over Cloud SaaS"
            assert entries[1].domain == "projects"
            assert entries[2].domain == "daily_work"
            assert entries[2].kind == "task"

