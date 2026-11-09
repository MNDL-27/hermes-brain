from __future__ import annotations

import json
from copy import deepcopy

from notion_brain import bootstrap, brain_cache, catalog, extract, store
from notion_brain.provider import NotionBrainProvider
from notion_brain.schema import BrainEntry, infer_subject_key


def _memory_schema() -> dict:
    return {
        "Status": {"type": "status", "status": {"options": [{"name": "active"}, {"name": "Superseded"}]}},
        "Subject Key": {"type": "rich_text"},
        "Truth": {"type": "select"},
        "Kind": {"type": "select"},
        "Content": {"type": "rich_text"},
    }


def _write_entry(monkeypatch, *, old_rows: list[dict], update=None) -> tuple[NotionBrainProvider, list]:
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "memory-db"}
    monkeypatch.setattr(store, "search_page_by_title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(store, "get_database", lambda *_: {"properties": _memory_schema()})
    monkeypatch.setattr(store, "create_database_page", lambda **_kwargs: {"id": "new-page"})
    monkeypatch.setattr(store, "query_database", lambda *_args, **_kwargs: old_rows)
    calls = []
    monkeypatch.setattr(store, "update_page", update or (lambda *args, **kwargs: calls.append((args, kwargs))))
    provider._store_entry(BrainEntry(
        domain="memory", title="Current phone", content="My daily phone is Pixel 9",
        metadata={"subject_key": "device.daily_phone"},
    ).normalized())
    return provider, calls


def test_infers_subject_key_from_fact_content_and_title():
    assert infer_subject_key("Phone", "My daily phone is Pixel") == "device.daily_phone"
    assert infer_subject_key("Engine preference", "I prefer a 650cc engine") == "preferences.engine_cc"
    assert infer_subject_key("Unrelated", "A fact with no recognized slot") == ""


def test_remember_subject_key_inference_and_override(monkeypatch):
    provider = NotionBrainProvider()
    captured = []
    monkeypatch.setattr(provider, "_store_entry", captured.append)
    provider._tool_remember({"title": "Phone", "content": "My daily phone is Pixel"})
    provider._tool_remember({
        "title": "Phone", "content": "My daily phone is Pixel", "subject_key": "custom.phone",
    })
    assert captured[0].metadata["subject_key"] == "device.daily_phone"
    assert captured[1].metadata["subject_key"] == "custom.phone"


def test_same_subject_write_supersedes_prior_active_row(monkeypatch):
    rows = [
        {"id": "new-page", "properties": {"Subject Key": "device.daily_phone", "Status": "active"}},
        {"id": "old-page", "title": "Old phone", "properties": {"Subject Key": "device.daily_phone", "Status": "active"}},
    ]
    _, calls = _write_entry(monkeypatch, old_rows=rows)
    assert len(calls) == 1
    assert calls[0][0][0] == "old-page"
    assert calls[0][0][1] == {"Status": {"status": {"name": "Superseded"}}}


def test_different_or_blank_subject_does_not_supersede(monkeypatch):
    rows = [{"id": "old-page", "properties": {"Subject Key": "device.car", "Status": "active"}}]
    _, calls = _write_entry(monkeypatch, old_rows=rows)
    assert calls == []

    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "memory-db"}
    provider._supersede_matching_active("new-page", BrainEntry(domain="memory", title="x", content="y"), "memory-db")
    assert calls == []


def test_timeline_orders_rows_newest_first_with_status(monkeypatch):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "memory-db"}
    rows = [
        {"id": "old", "title": "Old", "created_time": "2024-01-01", "properties": {"Subject Key": "device.phone", "Status": "Superseded", "Last Seen": "2024-01-01"}},
        {"id": "new", "title": "New", "created_time": "2025-01-01", "properties": {"Subject Key": "device.phone", "Status": "active", "Last Seen": "2025-01-01"}},
        {"id": "other", "title": "Other", "properties": {"Subject Key": "device.car", "Status": "active"}},
    ]
    monkeypatch.setattr(store, "query_database", lambda *_args, **_kwargs: rows)
    result = provider._tool_search({"action": "timeline", "subject_key": "device.phone"})
    assert [item["id"] for item in result[1]["items"]] == ["new", "old"]
    assert [item["status"] for item in result[1]["items"]] == ["active", "Superseded"]


def test_supersession_failure_is_fail_soft_and_redacted(monkeypatch, caplog):
    provider = NotionBrainProvider()
    provider._db_ids = {"memory": "memory-db"}
    monkeypatch.setattr(store, "search_page_by_title", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(store, "get_database", lambda *_: {"properties": _memory_schema()})
    created = []
    monkeypatch.setattr(store, "create_database_page", lambda **kwargs: created.append(kwargs) or {"id": "new-page"})

    def fail_query(*_args, **_kwargs):
        raise RuntimeError("failed token=sk-proj-12345678901234567890")

    monkeypatch.setattr(store, "query_database", fail_query)
    result = provider._tool_remember({
        "title": "Phone", "content": "My daily phone is Pixel", "subject_key": "device.daily_phone",
    })
    assert result == "Saved: Phone"
    assert created
    assert "sk-proj-12345678901234567890" not in caplog.text
    assert "[REDACTED_SECRET]" in caplog.text


def test_memory_schema_match_includes_subject_key_and_status_superset():
    expected = bootstrap._PROPS["memory"]
    db = {"properties": {
        name: {"type": next(iter(spec)), next(iter(spec)): deepcopy(spec[next(iter(spec))])}
        for name, spec in expected.items()
    }}
    db["properties"]["Status"]["status"]["options"].append({"name": "user-option"})
    assert bootstrap._database_schema_matches(db, expected) is False
    db["properties"]["Status"]["status"]["options"].pop()
    db["properties"]["Domain"]["select"]["options"].append({"name": "user-option"})
    assert bootstrap._database_schema_matches(db, expected)
    assert expected["Subject Key"] == {"rich_text": {}}


def test_cache_mirrors_subject_key(tmp_path):
    assert brain_cache.upsert_active(
        tmp_path, page_id="phone", title="Phone", kind="preference", content="Pixel",
        subject_key="device.daily_phone",
    )
    rows = brain_cache.list_active(tmp_path)
    assert rows is not None
    assert rows[0]["properties"]["Subject Key"] == "device.daily_phone"


# --- Phase 10 Task 1: background Memory ingestion through shared subject resolution ---


def _sync_provider(monkeypatch, tmp_path, entries):
    """Drive the real ``_process_sync_turn`` write pipeline with mocked storage."""
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {"memory": "memory-db"}
    provider._session_id = "sync-session"
    created: list[dict] = []

    def _create(*, database_id, properties, **_kw):
        page = {"id": f"page-{len(created) + 1}", "parent": {"database_id": database_id}}
        created.append(properties)
        return page

    monkeypatch.setattr(store, "search_page_by_title", lambda *_a, **_kw: None)
    monkeypatch.setattr(store, "get_database", lambda *_a: {"properties": _memory_schema()})
    monkeypatch.setattr(store, "create_database_page", _create)
    monkeypatch.setattr(store, "query_database", lambda *_a, **_kw: [])
    monkeypatch.setattr(store, "update_page", lambda *_a, **_kw: {})
    monkeypatch.setattr(provider, "prefetch", lambda *a, **kw: "")
    monkeypatch.setattr(extract, "classify_turn", lambda user, assistant: entries)
    return provider, created


def test_background_memory_write_infers_subject_key_to_property_and_cache(monkeypatch, tmp_path):
    entry = BrainEntry(domain="memory", title="Phone", content="My daily phone is Pixel 9")
    provider, created = _sync_provider(monkeypatch, tmp_path, entries=[entry])
    provider._process_sync_turn("My daily phone is Pixel 9", "")
    assert created
    assert created[0].get("Subject Key") == store.rich_text_property("device.daily_phone")
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None
    assert cached[0]["properties"]["Subject Key"] == "device.daily_phone"


def test_background_explicit_subject_override_wins_over_inference(monkeypatch, tmp_path):
    entry = BrainEntry(
        domain="memory", title="Phone", content="My daily phone is Pixel",
        metadata={"subject_key": "custom.phone"},
    )
    provider, created = _sync_provider(monkeypatch, tmp_path, entries=[entry])
    provider._process_sync_turn("My daily phone is Pixel", "")
    assert created
    assert created[0].get("Subject Key") == store.rich_text_property("custom.phone")


def test_background_blank_subject_override_falls_back_to_inference(monkeypatch, tmp_path):
    entry = BrainEntry(
        domain="memory", title="Phone", content="My daily phone is Pixel",
        metadata={"subject_key": ""},
    )
    provider, created = _sync_provider(monkeypatch, tmp_path, entries=[entry])
    provider._process_sync_turn("My daily phone is Pixel", "")
    assert created
    assert created[0].get("Subject Key") == store.rich_text_property("device.daily_phone")


def test_background_unrecognized_content_stays_keyless(monkeypatch, tmp_path):
    entry = BrainEntry(domain="memory", title="Unrelated", content="A fact with no recognized slot")
    provider, created = _sync_provider(monkeypatch, tmp_path, entries=[entry])
    provider._process_sync_turn("A fact with no recognized slot", "")
    assert created
    assert "Subject Key" not in created[0]
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None
    assert "Subject Key" not in cached[0]["properties"]


def test_background_secret_bearing_subject_override_is_redacted(monkeypatch, tmp_path):
    secret = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    entry = BrainEntry(
        domain="memory", title="Phone", content="My daily phone is Pixel",
        metadata={"subject_key": f"key {secret}"},
    )
    provider, created = _sync_provider(monkeypatch, tmp_path, entries=[entry])
    provider._process_sync_turn("My daily phone is Pixel", "")
    assert created
    subject_prop = created[0].get("Subject Key")
    assert subject_prop is not None
    assert secret not in json.dumps(subject_prop)
    assert "[REDACTED_SECRET]" in json.dumps(subject_prop)


def test_background_non_memory_write_does_not_infer_subject_key(monkeypatch, tmp_path):
    entry = BrainEntry(domain="daily_work", title="Phone note", content="My daily phone is Pixel")
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {"memory": "memory-db", "tasks": "tasks-db"}
    created: list[dict] = []
    monkeypatch.setattr(store, "search_page_by_title", lambda *_a, **_kw: None)
    monkeypatch.setattr(store, "get_database", lambda *_a: {"properties": _memory_schema()})
    monkeypatch.setattr(
        store, "create_database_page",
        lambda *, database_id, properties, **_kw: created.append(properties)
        or {"id": "tasks-page", "parent": {"database_id": database_id}},
    )
    monkeypatch.setattr(store, "query_database", lambda *_a, **_kw: [])
    monkeypatch.setattr(store, "update_page", lambda *_a, **_kw: {})
    monkeypatch.setattr(provider, "prefetch", lambda *a, **kw: "")
    monkeypatch.setattr(extract, "classify_turn", lambda u, a: [entry])
    provider._process_sync_turn("My daily phone is Pixel", "")
    assert created
    assert "Subject Key" not in created[0]


# --- Phase 10 Task 2: non-destructive same-title versioning and certified protection ---


def _versioning_provider(monkeypatch, tmp_path, rows, *, search=None):
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {"memory": "memory-db"}
    created: list[dict] = []
    updates: list[tuple] = []

    def _create(*, database_id, properties, **_kw):
        page = {"id": f"new-{len(created) + 1}", "parent": {"database_id": database_id}}
        created.append(properties)
        return page

    monkeypatch.setattr(store, "search_page_by_title", lambda *_a, **_kw: search)
    monkeypatch.setattr(store, "get_database", lambda *_a: {"properties": _memory_schema()})
    monkeypatch.setattr(store, "create_database_page", _create)
    monkeypatch.setattr(store, "query_database", lambda *_a, **_kw: rows)
    monkeypatch.setattr(store, "update_page", lambda *args, **kwargs: updates.append((args, kwargs)))
    return provider, created, updates


def _status_targets(updates):
    return [args[0] for args, _kw in updates if "Status" in (args[1] if len(args) > 1 else {})]


def _content_targets(updates):
    return [args[0] for args, _kw in updates if "Content" in (args[1] if len(args) > 1 else {})]


def test_changed_same_title_value_creates_new_page_without_overwrite(monkeypatch, tmp_path):
    rows = [{"id": "old", "title": "Phone", "properties": {
        "Subject Key": "device.phone", "Status": "active", "Content": "Pixel 8", "Truth": "inferred"}}]
    search_hit = {"id": "old", "parent": {"database_id": "memory-db"}}
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows, search=search_hit)
    assert provider._tool_remember(
        {"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"}) == "Saved: Phone"
    assert created  # new page created, not an in-place overwrite
    assert _content_targets(updates) == []  # old Content never rewritten
    assert _status_targets(updates) == ["old"]  # predecessor status-only flip


def test_identical_active_replay_reuses_without_page_or_supersession(monkeypatch, tmp_path):
    rows = [{"id": "existing", "title": "Phone", "properties": {
        "Subject Key": "device.phone", "Status": "active", "Content": "Pixel 9", "Truth": "inferred"}}]
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    assert created == []
    assert updates == []


def test_superseded_title_hit_preceding_active_match_reuses_active(monkeypatch, tmp_path):
    rows = [
        {"id": "old-sup", "title": "Phone", "properties": {
            "Subject Key": "device.phone", "Status": "Superseded", "Content": "Pixel 8"}},
        {"id": "active", "title": "Phone", "properties": {
            "Subject Key": "device.phone", "Status": "active", "Content": "Pixel 9", "Truth": "inferred"}},
    ]
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    assert created == []
    assert updates == []


def test_normalized_title_case_match_reuses(monkeypatch, tmp_path):
    rows = [{"id": "existing", "title": "Current Phone", "properties": {
        "Subject Key": "device.phone", "Status": "active", "Content": "Pixel 9", "Truth": "inferred"}}]
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({"title": "current phone", "content": "Pixel 9", "subject_key": "device.phone"})
    assert created == []
    assert updates == []


def test_different_subject_key_under_same_title_is_distinct(monkeypatch, tmp_path):
    rows = [{"id": "car", "title": "Phone", "properties": {
        "Subject Key": "device.car", "Status": "active", "Content": "Pixel 9", "Truth": "inferred"}}]
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    assert created  # distinct subject → new page
    assert _status_targets(updates) == []  # different subject → no supersession


def test_blank_subject_never_reuses_or_supersedes(monkeypatch, tmp_path):
    rows = [{"id": "other", "title": "Phone", "properties": {
        "Subject Key": "", "Status": "active", "Content": "Pixel 9"}}]
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({"title": "Phone", "content": "Pixel 9"})  # unrecognized → keyless
    assert created  # keyless → new page
    assert updates == []


def test_correction_back_to_superseded_value_creates_new_version(monkeypatch, tmp_path):
    rows = [
        {"id": "active", "title": "Phone", "properties": {
            "Subject Key": "device.phone", "Status": "active", "Content": "Pixel 9", "Truth": "inferred"}},
        {"id": "old-sup", "title": "Phone", "properties": {
            "Subject Key": "device.phone", "Status": "Superseded", "Content": "Pixel 8"}},
    ]
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({"title": "Phone", "content": "Pixel 8", "subject_key": "device.phone"})
    assert created  # superseded match not resurrected → new version
    assert _status_targets(updates) == ["active"]


def test_inactive_input_does_not_supersede_active_predecessor(monkeypatch, tmp_path):
    rows = [{"id": "old", "title": "Phone", "properties": {
        "Subject Key": "device.phone", "Status": "active", "Content": "Pixel 8", "Truth": "inferred"}}]
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({
        "title": "Phone", "content": "Pixel 9", "subject_key": "device.phone", "status": "Superseded"})
    assert _status_targets(updates) == []  # inactive input does not supersede


def test_distinct_long_values_sharing_prefix_create_new_version(monkeypatch, tmp_path):
    prefix = "x" * 2000
    rows = [{"id": "long", "title": "Long", "properties": {
        "Subject Key": "device.phone", "Status": "active", "Content": prefix, "Truth": "inferred"}}]
    assert brain_cache.upsert_active(
        tmp_path, page_id="long", title="Long", kind="note",
        content=prefix + "ORIGINAL", subject_key="device.phone")
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({"title": "Long", "content": prefix + "DIFFERENT", "subject_key": "device.phone"})
    assert created  # not equal → new version


def test_identical_long_replay_with_trusted_cache_reuses(monkeypatch, tmp_path):
    prefix = "x" * 2000
    full = prefix + "ORIGINAL"
    rows = [{"id": "long", "title": "Long", "properties": {
        "Subject Key": "device.phone", "Status": "active", "Content": prefix, "Truth": "inferred"}}]
    assert brain_cache.upsert_active(
        tmp_path, page_id="long", title="Long", kind="note",
        content=full, subject_key="device.phone")
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({"title": "Long", "content": full, "subject_key": "device.phone"})
    assert created == []
    assert updates == []


def test_long_replay_without_trusted_cache_creates_new_version(monkeypatch, tmp_path):
    prefix = "x" * 2000
    full = prefix + "ORIGINAL"
    rows = [{"id": "long", "title": "Long", "properties": {
        "Subject Key": "device.phone", "Status": "active", "Content": prefix, "Truth": "inferred"}}]
    provider, created, updates = _versioning_provider(monkeypatch, tmp_path, rows)
    provider._tool_remember({"title": "Long", "content": full, "subject_key": "device.phone"})
    assert created  # conservative: cannot prove equality from truncated remote → new version


# --- Phase 10 Task 3: stateful timeline/cache/graph regressions and failure isolation ---


class _FakeMemoryNotion:
    """Stateful in-memory Memory database.

    ``create`` assigns distinct ids and distinct fixed same-day creation
    times; ``update`` mutates only supplied properties (preserving
    Content/created_time unless explicitly written) and advances
    ``last_edited_time`` so a status-only edit on a predecessor can be ordered
    later than its successor. Every mutation verifies the expected database.
    """

    def __init__(self, schema: dict) -> None:
        self._schema = schema
        self.pages: dict[str, dict] = {}
        self._seq = 0
        self.mutations: list[tuple[str, str]] = []

    def _tick(self) -> str:
        self._seq += 1
        return f"2026-11-09T10:00:{self._seq:02d}"

    def _flat(self, value):
        if not isinstance(value, dict):
            return value
        if "rich_text" in value:
            return "".join(t.get("text", {}).get("content", "") for t in (value["rich_text"] or []))
        if "status" in value:
            s = value["status"]
            return s.get("name") if isinstance(s, dict) else None
        if "select" in value:
            s = value["select"]
            return s.get("name") if isinstance(s, dict) else None
        if "multi_select" in value:
            return [s.get("name") for s in (value["multi_select"] or [])]
        return value

    def _title(self, properties):
        prop = properties.get("title") or {}
        texts = prop.get("title") or []
        return "".join(t.get("text", {}).get("content", "") for t in texts) or "Untitled"

    def get_database(self, _db_id):
        return {"properties": self._schema}

    def search_page_by_title(self, *_a, **_kw):
        return None

    def page_body_text(self, *_a, **_kw):
        return ""

    def create_database_page(self, *, database_id, properties, **_kw):
        pid = f"page-{len(self.pages) + 1}"
        created = self._tick()
        self.pages[pid] = {
            "id": pid,
            "parent": {"type": "database_id", "database_id": database_id},
            "created_time": created,
            "last_edited_time": created,
            "title": self._title(properties),
            "properties": {k: self._flat(v) for k, v in properties.items() if k != "title"},
        }
        return self.pages[pid]

    def update_page(self, page_id, properties, *, expected_database_id=None, **_kw):
        page = self.pages[page_id]
        if expected_database_id is not None:
            assert store.normalize_id(page["parent"]["database_id"]) == store.normalize_id(
                expected_database_id
            ), "mutation targeted the wrong database"
        self.mutations.append((page_id, page["parent"]["database_id"]))
        for key, val in properties.items():
            if key == "title":
                page["title"] = self._title({"title": val})
            else:
                page["properties"][key] = self._flat(val)
        page["last_edited_time"] = self._tick()
        return page

    def query_database(self, database_id, page_size=100, **_kw):
        return [
            {
                "id": p["id"],
                "title": p["title"],
                "created_time": p["created_time"],
                "last_edited_time": p["last_edited_time"],
                "properties": dict(p["properties"]),
            }
            for p in self.pages.values()
            if store.normalize_id(p["parent"]["database_id"]) == store.normalize_id(database_id)
        ]


def _stateful_provider(monkeypatch, tmp_path):
    fake = _FakeMemoryNotion(_memory_schema())
    provider = NotionBrainProvider()
    provider._hermes_home = str(tmp_path)
    provider._db_ids = {"memory": "memory-db"}
    provider._session_id = "stateful-session"
    monkeypatch.setattr(store, "search_page_by_title", fake.search_page_by_title)
    monkeypatch.setattr(store, "get_database", fake.get_database)
    monkeypatch.setattr(store, "create_database_page", fake.create_database_page)
    monkeypatch.setattr(store, "update_page", fake.update_page)
    monkeypatch.setattr(store, "query_database", fake.query_database)
    monkeypatch.setattr(store, "page_body_text", fake.page_body_text)
    return provider, fake


def test_stateful_correction_retains_both_values_and_orders_timeline_by_creation(monkeypatch, tmp_path):
    provider, fake = _stateful_provider(monkeypatch, tmp_path)
    provider._tool_remember({"title": "Phone", "content": "Pixel 8", "subject_key": "device.phone"})
    provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    contents = {p["properties"].get("Content") for p in fake.pages.values()}
    assert contents == {"Pixel 8", "Pixel 9"}
    by_content = {p["properties"]["Content"]: pid for pid, p in fake.pages.items()}
    a_id, b_id = by_content["Pixel 8"], by_content["Pixel 9"]
    assert fake.pages[a_id]["properties"]["Status"] == "Superseded"
    assert fake.pages[b_id]["properties"]["Status"] == "active"
    # predecessor's last-edited advanced past the successor's creation (adverse ordering)
    assert fake.pages[a_id]["last_edited_time"] > fake.pages[b_id]["created_time"]
    # timeline prefers immutable creation time: B before A despite the adverse last-edited
    result = provider._tool_search({"action": "timeline", "subject_key": "device.phone"})
    items = result[1]["items"]
    assert [i["content"] for i in items] == ["Pixel 9", "Pixel 8"]
    assert [i["status"] for i in items] == ["active", "Superseded"]


def test_stateful_correction_updates_active_cache_for_same_and_fresh_provider(monkeypatch, tmp_path):
    provider, _fake = _stateful_provider(monkeypatch, tmp_path)
    provider._tool_remember({"title": "Phone", "content": "Pixel 8", "subject_key": "device.phone"})
    assert "Pixel 8" in provider.prefetch()  # populate the in-memory prefetch snapshot
    provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None
    assert [r["properties"]["Content"] for r in cached] == ["Pixel 9"]
    # same provider's next prefetch reflects the accepted correction, not the stale snapshot
    assert "Pixel 9" in provider.prefetch()
    assert "Pixel 8" not in provider.prefetch()
    # a fresh offline provider recalls the active fact from the cache alone
    fresh = NotionBrainProvider()
    fresh._hermes_home = str(tmp_path)
    fresh._db_ids = {"memory": "memory-db"}
    output = fresh.prefetch()
    assert "Pixel 9" in output
    assert "Pixel 8" not in output


def test_stateful_graph_preserves_chain_across_corrections(monkeypatch, tmp_path):
    provider, fake = _stateful_provider(monkeypatch, tmp_path)
    for value in ("v1", "v2", "v3"):
        provider._tool_remember({"title": "Phone", "content": value, "subject_key": "device.phone"})
    by_content = {p["properties"]["Content"]: pid for pid, p in fake.pages.items()}
    graph = catalog.Catalog().load(tmp_path / "brain_catalog.json")
    assert graph.graph_traverse(by_content["v3"], predicate="supersedes") == [
        by_content["v2"], by_content["v1"]]


def test_stateful_replay_is_idempotent(monkeypatch, tmp_path):
    provider, fake = _stateful_provider(monkeypatch, tmp_path)
    provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    pages_after_first = len(fake.pages)
    mutations_after_first = len(fake.mutations)
    provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    assert len(fake.pages) == pages_after_first  # no new page
    assert len(fake.mutations) == mutations_after_first  # no status transition or edge


def test_stateful_background_correction_retains_history(monkeypatch, tmp_path):
    provider, fake = _stateful_provider(monkeypatch, tmp_path)
    monkeypatch.setattr(
        extract, "classify_turn",
        lambda user, assistant: [BrainEntry(domain="memory", title="Phone", content=user)])
    provider._process_sync_turn("My daily phone is Pixel 8", "")
    provider._process_sync_turn("My daily phone is Pixel 9", "")
    contents = {p["properties"].get("Content") for p in fake.pages.values()}
    assert contents == {"My daily phone is Pixel 8", "My daily phone is Pixel 9"}
    result = provider._tool_search({"action": "timeline", "subject_key": "device.daily_phone"})
    assert [i["content"] for i in result[1]["items"]] == [
        "My daily phone is Pixel 9", "My daily phone is Pixel 8"]


def test_creation_failure_leaves_predecessor_state_untouched(monkeypatch, tmp_path):
    provider, fake = _stateful_provider(monkeypatch, tmp_path)
    provider._tool_remember({"title": "Phone", "content": "Pixel 8", "subject_key": "device.phone"})
    a_id = next(iter(fake.pages))
    snapshot = deepcopy(fake.pages[a_id])
    monkeypatch.setattr(
        store, "create_database_page",
        lambda **_kw: (_ for _ in ()).throw(RuntimeError("create unavailable")))
    result = provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    assert result.startswith("Error:")
    assert fake.pages[a_id] == snapshot  # predecessor untouched
    assert len(fake.pages) == 1  # no new page
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None
    assert [r["properties"]["Content"] for r in cached] == ["Pixel 8"]


def test_cache_mirror_failure_preserves_accepted_write(monkeypatch, tmp_path):
    provider, fake = _stateful_provider(monkeypatch, tmp_path)
    monkeypatch.setattr(brain_cache, "upsert_active", lambda *a, **k: (_ for _ in ()).throw(OSError("cache unavailable")))
    result = provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    assert result == "Saved: Phone"  # accepted write survives a cache failure
    assert any(p["properties"].get("Content") == "Pixel 9" for p in fake.pages.values())


def test_predecessor_status_failure_records_no_cache_flip_or_edge(monkeypatch, tmp_path):
    provider, fake = _stateful_provider(monkeypatch, tmp_path)
    provider._tool_remember({"title": "Phone", "content": "Pixel 8", "subject_key": "device.phone"})
    a_id = next(iter(fake.pages))
    assert brain_cache.upsert_active(
        tmp_path, page_id=a_id, title="Phone", kind="note",
        content="Pixel 8", subject_key="device.phone")
    real_update = fake.update_page

    def fail_status(page_id, properties, *, expected_database_id=None, **_kw):
        if "Status" in properties:
            raise RuntimeError("status update unavailable")
        return real_update(page_id, properties, expected_database_id=expected_database_id)

    monkeypatch.setattr(store, "update_page", fail_status)
    provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None
    assert a_id in {r["id"] for r in cached}  # predecessor NOT flipped to superseded
    graph = catalog.Catalog().load(tmp_path / "brain_catalog.json")
    assert graph.graph_traverse("page-2", predicate="supersedes") == []


def test_catalog_failure_preserves_accepted_write_and_cache(monkeypatch, tmp_path):
    provider, _fake = _stateful_provider(monkeypatch, tmp_path)
    provider._tool_remember({"title": "Phone", "content": "Pixel 8", "subject_key": "device.phone"})
    (tmp_path / "brain_catalog.json").write_bytes(b'{"relations": ')
    provider._tool_remember({"title": "Phone", "content": "Pixel 9", "subject_key": "device.phone"})
    cached = brain_cache.list_active(tmp_path)
    assert cached is not None
    assert [r["properties"]["Content"] for r in cached] == ["Pixel 9"]  # B active, A superseded
