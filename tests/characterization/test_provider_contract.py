"""Characterize the public Hermes memory-provider contract."""

from __future__ import annotations

import json
from typing import Any

import pytest

from notion_brain import NotionBrainProvider, bootstrap, register, schema, store


@pytest.fixture(autouse=True)
def _block_notion_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_request(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("characterization tests must not call the Notion API")

    monkeypatch.setattr(store.requests, "request", unexpected_request)


def _cache() -> dict[str, str]:
    cache = {"parent_page_id": "parent-id"}
    cache.update({f"db_{key}": f"{key}-id" for key in schema.DATABASES})
    return cache


@pytest.fixture
def initialized_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> NotionBrainProvider:
    monkeypatch.setattr(bootstrap, "ensure_brain", lambda home: _cache())
    monkeypatch.setattr(bootstrap, "read_memory_from_disk", lambda home: "")
    monkeypatch.setattr(bootstrap, "read_user_from_disk", lambda home: "")

    provider = NotionBrainProvider()
    provider.initialize("session-id", hermes_home=str(tmp_path))
    return provider


def test_register_adds_one_named_provider() -> None:
    class Context:
        def __init__(self) -> None:
            self.providers: list[object] = []

        def register_memory_provider(self, provider: object) -> None:
            self.providers.append(provider)

    context = Context()

    register(context)

    assert len(context.providers) == 1
    assert isinstance(context.providers[0], NotionBrainProvider)
    assert context.providers[0].name == "notion_brain"


def test_provider_name_is_stable() -> None:
    assert NotionBrainProvider().name == "notion_brain"


@pytest.mark.parametrize(
    ("api_key", "expected"),
    [(None, False), ("", False), ("configured-token", True)],
)
def test_is_available_only_checks_configuration(
    monkeypatch: pytest.MonkeyPatch, api_key: str | None, expected: bool
) -> None:
    monkeypatch.setattr(store, "get_api_key", lambda: api_key)

    assert NotionBrainProvider().is_available() is expected


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("notion_brain_search", {"query": "deterministic query"}),
        (
            "notion_brain_remember",
            {"title": "A stable fact", "content": "Characterization content"},
        ),
        ("notion_brain_task", {"action": "list"}),
        ("notion_brain_content", {"action": "list"}),
        ("notion_brain_research", {"action": "list"}),
    ],
)
def test_successful_public_tool_calls_return_json_objects(
    initialized_provider: NotionBrainProvider,
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    arguments: dict[str, Any],
) -> None:
    monkeypatch.setattr(store, "search_entries", lambda *args, **kwargs: [])
    monkeypatch.setattr(store, "query_database", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        store,
        "get_database",
        lambda database_id: {
            "properties": {
                "title": {"type": "title"},
                "Domain": {"type": "select"},
                "Status": {"type": "select"},
                "Tags": {"type": "multi_select"},
                "Confidence": {"type": "select"},
            }
        },
    )
    monkeypatch.setattr(
        store, "create_database_page", lambda *args, **kwargs: {"id": "page-id"}
    )

    response = initialized_provider.handle_tool_call(tool_name, arguments)

    assert isinstance(response, str)
    payload = json.loads(response)
    assert isinstance(payload, dict)
    assert isinstance(payload.get("result"), str)


def test_unknown_tool_returns_a_safe_string_error() -> None:
    response = NotionBrainProvider().handle_tool_call("notion_brain_unknown", {})

    assert isinstance(response, str)
    assert "Unknown tool" in response
    assert "notion_brain_unknown" in response


def test_initialize_honors_the_provided_hermes_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    observed: dict[str, list[str]] = {"ensure": [], "memory": [], "user": []}

    def ensure(home: str) -> dict[str, str]:
        observed["ensure"].append(home)
        return _cache()

    def read_memory(home: str) -> str:
        observed["memory"].append(home)
        return ""

    def read_user(home: str) -> str:
        observed["user"].append(home)
        return ""

    monkeypatch.setattr(bootstrap, "ensure_brain", ensure)
    monkeypatch.setattr(bootstrap, "read_memory_from_disk", read_memory)
    monkeypatch.setattr(bootstrap, "read_user_from_disk", read_user)
    home = str(tmp_path)

    NotionBrainProvider().initialize("session-id", hermes_home=home)

    assert observed == {"ensure": [home], "memory": [home], "user": [home]}


def test_initialize_maps_every_cached_database_for_filtered_search(
    initialized_provider: NotionBrainProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    queried_database_ids: list[str] = []

    def query_database(database_id: str, **kwargs: Any) -> list[dict[str, Any]]:
        queried_database_ids.append(database_id)
        return []

    monkeypatch.setattr(store, "query_database", query_database)

    for database_key in schema.DATABASES:
        response = initialized_provider.handle_tool_call(
            "notion_brain_search",
            {"query": "anything", "database": database_key},
        )
        assert isinstance(json.loads(response), dict)

    assert queried_database_ids == [f"{key}-id" for key in schema.DATABASES]


def test_initialize_failure_does_not_escape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    def fail_bootstrap(home: str) -> dict[str, str]:
        raise RuntimeError("simulated bootstrap failure")

    monkeypatch.setattr(bootstrap, "ensure_brain", fail_bootstrap)
    monkeypatch.setattr(bootstrap, "read_memory_from_disk", lambda home: "")
    monkeypatch.setattr(bootstrap, "read_user_from_disk", lambda home: "")
    provider = NotionBrainProvider()

    provider.initialize("session-id", hermes_home=str(tmp_path))

    assert provider.name == "notion_brain"


def test_shutdown_is_safe_before_initialization() -> None:
    NotionBrainProvider().shutdown()


def test_system_prompt_block_describes_the_provider_contract() -> None:
    description = NotionBrainProvider().system_prompt_block()

    assert description.startswith("# Notion Brain\n")
    assert 'Notion workspace called "Hermes Brain"' in description
    for database_name in (
        "Memory",
        "Tasks",
        "Projects",
        "Content",
        "Research",
        "Career",
        "Entities",
    ):
        assert database_name in description
    for tool_name in (
        "notion_brain_search",
        "notion_brain_remember",
        "notion_brain_task",
        "notion_brain_content",
        "notion_brain_research",
    ):
        assert tool_name in description
    assert description.endswith("Memory is automatically synced after each turn.")


@pytest.mark.parametrize(
    ("domain", "normalized", "database"),
    [
        (None, "memory", "memory"),
        ("", "memory", "memory"),
        ("task", "daily_work", "tasks"),
        ("tasks", "daily_work", "tasks"),
        ("daily", "daily_work", "tasks"),
        ("work", "daily_work", "tasks"),
        ("daily work", "daily_work", "tasks"),
        ("project", "projects", "projects"),
        ("social", "social_content", "content"),
        ("content", "social_content", "content"),
        ("social media", "social_content", "content"),
        ("job", "career", "career"),
        ("jobs", "career", "career"),
        ("career", "career", "career"),
        ("research", "research", "research"),
        ("entity", "entities", "entities"),
        ("people", "entities", "entities"),
        ("person", "entities", "entities"),
        ("user", "entities", "entities"),
        ("unknown-domain", "memory", "memory"),
    ],
)
def test_domain_aliases_keep_their_public_mapping(
    domain: str | None, normalized: str, database: str
) -> None:
    assert schema.normalize_domain(domain) == normalized
    assert schema.database_for_domain(domain) == database


@pytest.mark.parametrize(
    ("helper", "arguments", "expected"),
    [
        pytest.param(
            store.title_property,
            ("Title",),
            {"title": [{"type": "text", "text": {"content": "Title"}}]},
            id="title",
        ),
        pytest.param(
            store.rich_text_property,
            ("Body",),
            {"rich_text": [{"type": "text", "text": {"content": "Body"}}]},
            id="rich-text",
        ),
        pytest.param(
            store.select_property,
            ("active",),
            {"select": {"name": "active"}},
            id="select",
        ),
        pytest.param(
            store.multi_select_property,
            (["alpha", "", "beta"],),
            {"multi_select": [{"name": "alpha"}, {"name": "beta"}]},
            id="multi-select",
        ),
        pytest.param(
            store.status_property,
            ("done",),
            {"status": {"name": "done"}},
            id="status",
        ),
        pytest.param(
            store.date_property,
            ("2026-07-25",),
            {"date": {"start": "2026-07-25"}},
            id="date",
        ),
        pytest.param(
            store.date_property,
            (None,),
            {"date": {}},
            id="empty-date",
        ),
        pytest.param(
            store.number_property,
            (3,),
            {"number": 3},
            id="number",
        ),
    ],
)
def test_property_helpers_keep_their_public_shapes(
    helper: Any, arguments: tuple[Any, ...], expected: dict[str, Any]
) -> None:
    assert helper(*arguments) == expected
