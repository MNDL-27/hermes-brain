"""Tests for notion_brain.store: property helpers and Notion response parsing."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notion_brain.store import (
    date_property,
    number_property,
    rich_text_property,
    search_page_by_title,
    select_property,
    multi_select_property,
    _page_title,
    _flatten_result,
    _rich_text,
)


# ---------------------------------------------------------------------------
# Property helpers
# ---------------------------------------------------------------------------

class TestDateProperty:
    def test_with_date(self):
        prop = date_property("2026-07-22")
        assert prop["date"]["start"] == "2026-07-22"

    def test_none_returns_empty_date(self):
        # Notion rejects {"date": None}; the documented absence shape is {"date": {}}.
        assert date_property(None) == {"date": {}}

    def test_empty_string_still_empty(self):
        # empty string is falsy, so we still emit the empty-date shape.
        assert date_property("") == {"date": {}}


class TestNumberProperty:
    def test_int(self):
        assert number_property(5) == {"number": 5}

    def test_float(self):
        assert number_property(3.14) == {"number": 3.14}

    def test_none(self):
        assert number_property(None) == {"number": None}


class TestRichTextTruncation:
    def test_rich_text_truncates_at_2000(self):
        prop = rich_text_property("x" * 3000)
        assert len(prop["rich_text"][0]["text"]["content"]) == 2000

    def test_rich_text_short(self):
        prop = rich_text_property("hi")
        assert prop["rich_text"][0]["text"]["content"] == "hi"

    def test_rich_text_helper_structure(self):
        rt = _rich_text("abc")
        assert rt == [{"type": "text", "text": {"content": "abc"}}]


# ---------------------------------------------------------------------------
# _page_title — extract title from raw Notion page
# ---------------------------------------------------------------------------

def _page(props):
    return {"properties": props}


class TestPageTitle:
    def test_extracts_title(self):
        page = _page({"Name": {"type": "title",
                               "title": [{"text": {"content": "My Page"}}]}})
        assert _page_title(page) == "My Page"

    def test_falls_back_to_lowercase(self):
        page = _page({"Name": {"type": "title",
                               "title": [{"text": {"content": "  lower  "}}]}})
        assert _page_title(page) == "lower"

    def test_returns_none_when_empty(self):
        page = _page({"Name": {"type": "title", "title": []}})
        assert _page_title(page) is None

    def test_returns_none_on_no_properties(self):
        assert _page_title({}) is None
        assert _page_title({"properties": {}}) is None

    def test_swallows_exception(self):
        # non-dict properties values trigger exception inside loop, caught
        page = _page({"Name": "not a dict"})
        assert _page_title(page) is None


# ---------------------------------------------------------------------------
# _flatten_result — pull usable props out of Notion result
# ---------------------------------------------------------------------------

def _result(props):
    return {
        "object": "page",
        "id": "abc123",
        "created_time": "2026-01-01T00:00:00Z",
        "last_edited_time": "2026-01-02T00:00:00Z",
        "properties": props,
    }


class TestFlattenResult:
    def test_basic_fields(self):
        flat = _flatten_result(_result({}))
        assert flat["id"] == "abc123"
        assert flat["type"] == "page"
        assert flat["created_time"] == "2026-01-01T00:00:00Z"
        assert flat["last_edited_time"] == "2026-01-02T00:00:00Z"
        assert flat["properties"] == {}
        assert flat["raw"]["id"] == "abc123"

    def test_title_uses_page_title(self):
        props = {"Name": {"type": "title",
                          "title": [{"text": {"content": "Hello"}}]}}
        assert _flatten_result(_result(props))["title"] == "Hello"

    def test_title_fallback_to_id_prefix(self):
        # no title property -> first 36 chars of id
        flat = _flatten_result(_result({}))
        assert flat["title"] == "abc123"[:36]

    def test_rich_text_prop(self):
        props = {"Notes": {"type": "rich_text",
                           "rich_text": [{"text": {"content": "note"}}]}}
        assert _flatten_result(_result(props))["properties"]["Notes"] == "note"

    def test_select_prop(self):
        props = {"Domain": {"type": "select", "select": {"name": "Memory"}}}
        assert _flatten_result(_result(props))["properties"]["Domain"] == "Memory"

    def test_select_null(self):
        props = {"Domain": {"type": "select", "select": None}}
        assert _flatten_result(_result(props))["properties"]["Domain"] is None

    def test_multi_select_prop(self):
        props = {"Tags": {"type": "multi_select",
                          "multi_select": [{"name": "a"}, {"name": "b"}]}}
        assert _flatten_result(_result(props))["properties"]["Tags"] == ["a", "b"]

    def test_status_prop(self):
        props = {"Status": {"type": "status", "status": {"name": "done"}}}
        assert _flatten_result(_result(props))["properties"]["Status"] == "done"

    def test_date_prop(self):
        props = {"Due": {"type": "date", "date": {"start": "2026-07-22"}}}
        assert _flatten_result(_result(props))["properties"]["Due"] == "2026-07-22"

    def test_date_null(self):
        props = {"Due": {"type": "date", "date": None}}
        assert _flatten_result(_result(props))["properties"]["Due"] is None

    def test_number_prop(self):
        props = {"Count": {"type": "number", "number": 42}}
        assert _flatten_result(_result(props))["properties"]["Count"] == 42

    def test_checkbox_prop(self):
        props = {"Done": {"type": "checkbox", "checkbox": True}}
        assert _flatten_result(_result(props))["properties"]["Done"] is True

    def test_url_prop(self):
        props = {"Link": {"type": "url", "url": "https://example.com"}}
        assert _flatten_result(_result(props))["properties"]["Link"] == "https://example.com"

    def test_email_prop(self):
        props = {"Email": {"type": "email", "email": "a@b.com"}}
        assert _flatten_result(_result(props))["properties"]["Email"] == "a@b.com"

    def test_unknown_type_skipped(self):
        props = {"Weird": {"type": "files", "files": []}}
        assert "Weird" not in _flatten_result(_result(props))["properties"]

    def test_handles_no_properties_key(self):
        flat = _flatten_result({"object": "page", "id": "x"})
        assert flat["properties"] == {}


# ---------------------------------------------------------------------------
# search_page_by_title — exact case-insensitive match filtering
# ---------------------------------------------------------------------------

class TestSearchPageByTitle:
    def _resp(self, results):
        import requests
        resp = requests.Response()
        resp.status_code = 200
        import json
        resp._content = json.dumps({"results": results}).encode()
        return resp

    def test_matches_case_insensitive(self, monkeypatch):
        results = [
            {"object": "page", "id": "p1",
             "properties": {"Name": {"type": "title",
                                     "title": [{"text": {"content": "hermes brain"}}]}}},
        ]
        import notion_brain.store as store_mod
        monkeypatch.setattr(store_mod, "_request",
                            lambda *a, **k: {"results": results})
        found = search_page_by_title("Hermes Brain")
        assert found is not None
        assert found["id"] == "p1"

    def test_skips_non_matching_title(self, monkeypatch):
        results = [
            {"object": "page", "id": "p1",
             "properties": {"Name": {"type": "title",
                                     "title": [{"text": {"content": "Other"}}]}}},
        ]
        import notion_brain.store as store_mod
        monkeypatch.setattr(store_mod, "_request",
                            lambda *a, **k: {"results": results})
        assert search_page_by_title("Hermes Brain") is None

    def test_skips_wrong_object_type(self, monkeypatch):
        results = [
            {"object": "database", "id": "d1",
             "properties": {}},
        ]
        import notion_brain.store as store_mod
        monkeypatch.setattr(store_mod, "_request",
                            lambda *a, **k: {"results": results})
        assert search_page_by_title("Hermes Brain", object_type="page") is None

    def test_returns_none_empty_results(self, monkeypatch):
        import notion_brain.store as store_mod
        monkeypatch.setattr(store_mod, "_request",
                            lambda *a, **k: {"results": []})
        assert search_page_by_title("Hermes Brain") is None


# ---------------------------------------------------------------------------
# Defensive Secret Redaction Coverage on Properties
# ---------------------------------------------------------------------------

class TestSecretRedactionCoverage:
    def test_rich_text_redacts_secrets(self):
        rt = _rich_text("key: sk-12345678901234567890")
        assert rt == [{"type": "text", "text": {"content": "key: [REDACTED_SECRET]"}}]

    def test_select_property_redacts_secrets(self):
        prop = select_property("token: ntn_12345678901234567890")
        assert prop == {"select": {"name": "[REDACTED_SECRET]"}}

    def test_multi_select_property_redacts_secrets(self):
        prop = multi_select_property(["secret: ghp_12345678901234567890"])
        assert prop == {"multi_select": [{"name": "[REDACTED_SECRET]"}]}

