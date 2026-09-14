"""Strict regression contracts for known durability blockers."""

from __future__ import annotations

import threading
from collections.abc import Callable
from unittest.mock import patch

import pytest

from notion_brain import NotionBrainProvider

_WAIT_TIMEOUT_SECONDS = 2.0
_CONCURRENCY_PROBE_SECONDS = 0.5


def _provider_with_databases(**database_ids: str) -> NotionBrainProvider:
    provider = NotionBrainProvider()
    provider._db_ids = database_ids
    return provider


def _join_threads(*threads: threading.Thread | None) -> None:
    seen: set[int] = set()
    alive: list[str] = []
    for thread in threads:
        if thread is None or id(thread) in seen:
            continue
        seen.add(id(thread))
        thread.join(timeout=_WAIT_TIMEOUT_SECONDS)
        if thread.is_alive():
            alive.append(thread.name)
    assert not alive, f"test cleanup could not stop threads: {alive}"


@pytest.fixture(autouse=True)
def _forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("durability regressions must not make network calls")

    monkeypatch.setattr("notion_brain.store.requests.request", unexpected_network)


@pytest.mark.xfail(
    strict=True,
    reason="Workstream 5: remember must expose a failed state when no destination database exists",
)
def test_remember_does_not_report_saved_without_destination_database() -> None:
    provider = NotionBrainProvider()

    response = provider.handle_tool_call(
        "notion_brain_remember",
        {"title": "Durable note", "content": "This write needs a destination."},
    )

    assert "saved" not in response.lower()
    assert "error" in response.lower() or "fail" in response.lower()


@pytest.mark.xfail(
    strict=True,
    reason="Workstream 3: content updates must update the existing page instead of creating a duplicate",
)
def test_content_update_calls_update_page_without_creating_duplicate() -> None:
    provider = _provider_with_databases(content="content-db")

    with (
        patch("notion_brain.store.get_database", return_value={"properties": {}}),
        patch("notion_brain.store.update_page", return_value={"id": "content-page"}) as update_page,
        patch(
            "notion_brain.store.create_database_page",
            return_value={"id": "duplicate-page"},
        ) as create_page,
    ):
        provider.handle_tool_call(
            "notion_brain_content",
            {
                "action": "update",
                "page_id": "content-page",
                "title": "Existing draft",
                "body": "Revised body",
            },
        )

    update_page.assert_called_once()
    assert update_page.call_args.args[0] == "content-page"
    create_page.assert_not_called()


@pytest.mark.xfail(
    strict=True,
    reason="Workstream 5: synchronization writes must execute through one serialized worker",
)
def test_sync_turns_do_not_execute_writes_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider_with_databases(memory="memory-db")
    first_write_entered = threading.Event()
    second_write_entered = threading.Event()
    release_first_write = threading.Event()
    call_lock = threading.Lock()
    call_count = 0
    worker_threads: list[threading.Thread | None] = []

    def blocking_store(_entry: object) -> None:
        nonlocal call_count
        with call_lock:
            call_count += 1
            this_call = call_count
        if this_call == 1:
            first_write_entered.set()
            release_first_write.wait(timeout=_WAIT_TIMEOUT_SECONDS)
        elif this_call == 2:
            second_write_entered.set()

    monkeypatch.setattr("notion_brain.extract.classify_turn", lambda *_args: [object()])
    monkeypatch.setattr(provider, "_store_entry", blocking_store)

    concurrent_execution = False
    try:
        provider.sync_turn("first user turn", "first assistant turn")
        worker_threads.append(provider._sync_thread)
        assert first_write_entered.wait(timeout=_WAIT_TIMEOUT_SECONDS)

        provider.sync_turn("second user turn", "second assistant turn")
        worker_threads.append(provider._sync_thread)
        concurrent_execution = second_write_entered.wait(
            timeout=_CONCURRENCY_PROBE_SECONDS
        )
    finally:
        release_first_write.set()
        _join_threads(*worker_threads)

    assert not concurrent_execution


@pytest.mark.parametrize(
    ("lifecycle_name", "invoke_lifecycle"),
    [
        ("session end", lambda provider: provider.on_session_end([])),
        ("shutdown", lambda provider: provider.shutdown()),
    ],
)
@pytest.mark.xfail(
    strict=True,
    reason="Workstream 5: lifecycle flushes must wait for every accepted synchronization write",
)
def test_lifecycle_waits_for_every_accepted_sync_write(
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_name: str,
    invoke_lifecycle: Callable[[NotionBrainProvider], None],
) -> None:
    provider = _provider_with_databases(memory="memory-db")
    first_write_entered = threading.Event()
    later_write_completed = threading.Event()
    release_first_write = threading.Event()
    lifecycle_completed = threading.Event()
    call_lock = threading.Lock()
    call_count = 0
    completed_writes = 0
    worker_threads: list[threading.Thread | None] = []
    lifecycle_errors: list[BaseException] = []

    def controlled_store(_entry: object) -> None:
        nonlocal call_count, completed_writes
        with call_lock:
            call_count += 1
            this_call = call_count
        if this_call == 1:
            first_write_entered.set()
            release_first_write.wait(timeout=_WAIT_TIMEOUT_SECONDS)
        with call_lock:
            completed_writes += 1
        if this_call > 1:
            later_write_completed.set()

    def run_lifecycle() -> None:
        try:
            invoke_lifecycle(provider)
        except BaseException as exc:  # pragma: no cover - cleanup reports the error
            lifecycle_errors.append(exc)
        finally:
            lifecycle_completed.set()

    monkeypatch.setattr("notion_brain.extract.classify_turn", lambda *_args: [object()])
    monkeypatch.setattr(provider, "_store_entry", controlled_store)

    lifecycle_thread = threading.Thread(
        target=run_lifecycle,
        daemon=True,
        name=f"durability-{lifecycle_name.replace(' ', '-')}",
    )
    returned_before_release = False
    try:
        provider.sync_turn("first user turn", "first assistant turn")
        worker_threads.append(provider._sync_thread)
        assert first_write_entered.wait(timeout=_WAIT_TIMEOUT_SECONDS)

        provider.sync_turn("second user turn", "second assistant turn")
        worker_threads.append(provider._sync_thread)
        later_write_completed.wait(timeout=_CONCURRENCY_PROBE_SECONDS)

        lifecycle_thread.start()
        returned_before_release = lifecycle_completed.wait(
            timeout=_CONCURRENCY_PROBE_SECONDS
        )
    finally:
        release_first_write.set()
        _join_threads(*worker_threads, lifecycle_thread)

    assert not lifecycle_errors
    assert lifecycle_completed.is_set()
    assert not returned_before_release
    assert completed_writes == 2


@pytest.mark.xfail(
    strict=True,
    reason="Workstream 5: backend exceptions must produce truthful failed operation states",
)
def test_backend_exception_produces_failure_instead_of_success() -> None:
    provider = _provider_with_databases(memory="memory-db")

    with (
        patch(
            "notion_brain.store.get_database",
            side_effect=RuntimeError("backend schema lookup failed"),
        ),
        patch(
            "notion_brain.store.create_database_page",
            return_value={"id": "partially-written-page"},
        ) as create_page,
    ):
        response = provider.handle_tool_call(
            "notion_brain_remember",
            {"title": "Backend failure", "content": "Do not report success."},
        )

    assert "saved" not in response.lower()
    assert "error" in response.lower() or "fail" in response.lower()
    create_page.assert_not_called()
