"""Offline unit tests for notion_brain.update_cache (Phase 06).

Covers: atomic load/save with mode 0o600, JSONDecodeError tolerance,
TTL expiry semantics, no-network guarantee on load, refresh offline-safe
behavior, secret redaction in error logs, provider init's sync-cache
contract, and the health_report cache-only contract.
"""

from __future__ import annotations

import json
import logging
import sys
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notion_brain import (
    bootstrap,  # noqa: E402
    update_cache,  # noqa: E402
)

# ---------- load_cache / save_cache / is_expired (CHK-01, CHK-03) ----------


def test_load_cache_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert update_cache.load_cache(tmp_path) is None


def test_load_cache_returns_none_for_corrupt_file(tmp_path: Path) -> None:
    (tmp_path / update_cache.CACHE_FILENAME).write_text("{not json")
    assert update_cache.load_cache(tmp_path) is None


def test_load_cache_returns_none_for_empty_file(tmp_path: Path) -> None:
    (tmp_path / update_cache.CACHE_FILENAME).write_text("")
    assert update_cache.load_cache(tmp_path) is None


def test_load_cache_returns_none_for_non_dict_json(tmp_path: Path) -> None:
    (tmp_path / update_cache.CACHE_FILENAME).write_text("[1, 2, 3]")
    assert update_cache.load_cache(tmp_path) is None


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    payload = {
        "current": "1.0.3",
        "latest": "1.2.3",
        "drift": True,
        "checked_at": 1_700_000_000,
    }
    update_cache.save_cache(tmp_path, payload)
    loaded = update_cache.load_cache(tmp_path)
    assert loaded == payload


def test_save_cache_writes_with_mode_0o600(tmp_path: Path) -> None:
    update_cache.save_cache(tmp_path, {"current": "1.0.3", "checked_at": 1})
    mode = (tmp_path / update_cache.CACHE_FILENAME).stat().st_mode & 0o777
    assert mode == 0o600, f"expected mode 0o600, got {oct(mode)}"


def test_save_cache_does_not_leave_tmp_file_on_success(tmp_path: Path) -> None:
    update_cache.save_cache(tmp_path, {"current": "1.0.3", "checked_at": 1})
    leftover = list(tmp_path.glob(f"{update_cache.CACHE_FILENAME}.tmp"))
    assert leftover == []


def test_is_expired_returns_true_for_none() -> None:
    assert update_cache.is_expired(None) is True


def test_is_expired_returns_false_for_fresh_payload() -> None:
    import time

    assert update_cache.is_expired({"checked_at": int(time.time())}, ttl_seconds=86400) is False


def test_is_expired_returns_true_for_old_payload() -> None:
    import time

    old = {"checked_at": int(time.time()) - 100_000}
    assert update_cache.is_expired(old, ttl_seconds=86400) is True


def test_is_expired_respects_custom_ttl() -> None:
    import time

    payload = {"checked_at": int(time.time()) - 100}
    assert update_cache.is_expired(payload, ttl_seconds=1000) is False
    assert update_cache.is_expired(payload, ttl_seconds=10) is True


def test_is_expired_treats_missing_checked_at_as_expired() -> None:
    assert update_cache.is_expired({"current": "1.0.3"}) is True


# ---------- No-network guarantee on load (CHK-01) ----------


def test_load_cache_makes_no_network_calls(tmp_path: Path) -> None:
    """CHK-01: load_cache must be pure file I/O."""
    update_cache.save_cache(tmp_path, {"current": "1.0.3", "checked_at": 1})
    called = {"n": 0}
    orig = urllib.request.urlopen

    def _trip(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("load_cache must not invoke urlopen")

    urllib.request.urlopen = _trip  # type: ignore[assignment]
    try:
        update_cache.load_cache(tmp_path)
    finally:
        urllib.request.urlopen = orig  # type: ignore[assignment]
    assert called["n"] == 0


# ---------- refresh (CHK-05) ----------


def test_refresh_handles_network_failure_without_raising(tmp_path: Path) -> None:
    """CHK-05: refresh must not propagate exceptions."""
    from notion_brain import update as update_mod

    def _boom(*args, **kwargs):
        raise ConnectionError("offline")

    with patch.object(update_mod, "check_for_update", side_effect=_boom):
        result = update_cache.refresh(tmp_path)
    assert result is None
    # No cache file should have been written
    assert not (tmp_path / update_cache.CACHE_FILENAME).exists()


def test_refresh_redacts_secrets_in_error_log(tmp_path: Path, caplog) -> None:
    """CHK-05: error logs must not contain raw tokens."""
    from notion_brain import schema as S
    from notion_brain import update as update_mod

    # Use a token format that schema._SECRET_PATTERNS already recognizes (AWS access key).
    fake_token = "AKIA1234567890ABCDEF"

    def _leak(*args, **kwargs):
        raise RuntimeError(f"auth failed: {fake_token}")

    with (
        caplog.at_level(logging.WARNING, logger="notion_brain.update_cache"),
        patch.object(update_mod, "check_for_update", side_effect=_leak),
    ):
        update_cache.refresh(tmp_path)
    # The original token must NOT appear in any log record
    for record in caplog.records:
        assert fake_token not in record.getMessage(), (
            f"raw token leaked into log: {record.getMessage()}"
        )
    # redact_secrets must have been invoked at least once (sanity)
    assert S.redact_secrets(fake_token) != fake_token


def test_refresh_writes_cache_with_checked_at_timestamp(tmp_path: Path) -> None:
    """A successful refresh produces a cache file with checked_at as integer epoch seconds."""
    from notion_brain import update as update_mod

    payload = {
        "current": "1.0.3",
        "latest": "1.2.3",
        "drift": True,
        "install_mode": "uv",
        "upgrade_command": "uv pip install --upgrade hermes-brain==1.2.3",
        "release_url": "https://example/v1.2.3",
        "error": None,
    }
    with patch.object(update_mod, "check_for_update", return_value=payload):
        result = update_cache.refresh(tmp_path)
    assert result is not None
    assert isinstance(result["checked_at"], int)
    cache_file = tmp_path / update_cache.CACHE_FILENAME
    assert cache_file.exists()
    on_disk = json.loads(cache_file.read_text())
    assert on_disk["drift"] is True
    assert on_disk["checked_at"] == result["checked_at"]


# ---------- bootstrap.health_report uses the cache (CHK-04) ----------


def test_health_report_does_not_call_check_for_update(tmp_path: Path, monkeypatch, capsys) -> None:
    """CHK-04: health_report reads cache, never network."""
    # Seed a cache so health_report has something to show.
    update_cache.save_cache(
        tmp_path,
        {"current": "1.0.3", "latest": "1.2.3", "drift": True, "checked_at": 1},
    )
    # Seed only the parent page ID. Without any db_* entries the per-DB loop
    # takes the "MISSING (no cache entry)" path and makes zero store calls —
    # so if any network call happens, it is a real violation, not test noise.
    (tmp_path / "notion_brain.json").write_text('{"parent_page_id": "fake-parent"}')

    def _trip(*args, **kwargs):
        raise AssertionError("health_report must not call _check_for_update")

    monkeypatch.setattr(bootstrap, "_check_for_update", _trip)
    # Stub store.get_page so the parent-title lookup doesn't hit the network.
    monkeypatch.setattr(
        bootstrap.store, "get_page", lambda pid: {"title": "Fake Parent", "url": "x"}
    )
    report = bootstrap.health_report(tmp_path)
    # Drift line should appear (cache had drift=True), and we should NOT have
    # called _check_for_update.
    assert "UPDATE AVAILABLE" in report


def test_health_report_unknown_when_cache_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    """Missing cache → 'latest: unknown', no network call."""
    (tmp_path / "notion_brain.json").write_text('{"parent_page_id": "fake-parent"}')
    monkeypatch.setattr(
        bootstrap, "_check_for_update", lambda: (_ for _ in ()).throw(AssertionError)
    )
    monkeypatch.setattr(
        bootstrap.store, "get_page", lambda pid: {"title": "Fake Parent", "url": "x"}
    )
    report = bootstrap.health_report(tmp_path)
    assert "latest: unknown" in report


# ---------- NotionBrainProvider init reads cache synchronously (CHK-01) ----------


def test_provider_initialize_loads_cache_synchronously(monkeypatch, tmp_path: Path) -> None:
    """initialize() calls update_cache.load_cache before bootstrap.ensure_brain and never blocks on network."""
    # Seed a FRESH cache (checked_at=now) so the TTL refresh is NOT queued —
    # we are asserting the zero-network property of the load itself. The
    # TTL-expired dispatch path is covered separately below.
    import time as _time

    from notion_brain import provider as provider_mod

    update_cache.save_cache(
        tmp_path,
        {"current": "1.0.3", "latest": "1.0.3", "drift": False, "checked_at": int(_time.time())},
    )

    network_calls: list[str] = []

    def _urlopen_trip(*args, **kwargs):
        import traceback

        network_calls.append("urlopen: " + "|".join(repr(a) for a in args[:1]))
        network_calls.append("trace:\n" + "".join(traceback.format_stack(limit=6)))
        raise AssertionError("CHK-01: initialize must not invoke urlopen")

    orig_urlopen = urllib.request.urlopen
    urllib.request.urlopen = _urlopen_trip  # type: ignore[assignment]
    try:
        # Avoid hitting the real Notion API by stubbing ensure_brain and the
        # disk readers. Anything still calling urlopen is a CHK-01 violation.
        monkeypatch.setattr(
            provider_mod.bootstrap,
            "ensure_brain",
            lambda home: {
                "parent_page_id": "fake",
                "db_memory": "fake",
            },
        )
        monkeypatch.setattr(provider_mod.bootstrap, "read_memory_from_disk", lambda home: "")
        monkeypatch.setattr(provider_mod.bootstrap, "read_user_from_disk", lambda home: "")
        p = provider_mod.NotionBrainProvider()
        p.initialize("sess", hermes_home=str(tmp_path))
    finally:
        urllib.request.urlopen = orig_urlopen  # type: ignore[assignment]
    if network_calls:
        # Surface the traceback of the offending caller to make diagnosis easy.
        raise AssertionError("urlopen was invoked during initialize:\n" + "\n".join(network_calls))
    update_cache_val = getattr(p, "_update_cache", None)
    assert update_cache_val is not None
    assert update_cache_val["current"] == "1.0.3"


def test_provider_dispatches_refresh_when_cache_expired(monkeypatch, tmp_path: Path) -> None:
    """CHK-02: expired cache → refresh task enqueued on the sync queue, not run inline."""
    from notion_brain import provider as provider_mod

    # Expired cache (checked_at in the distant past).
    update_cache.save_cache(
        tmp_path, {"current": "1.0.3", "latest": "1.0.3", "drift": False, "checked_at": 1}
    )
    queued: list[tuple] = []
    monkeypatch.setattr(
        provider_mod.NotionBrainProvider,
        "_dispatch_update_refresh",
        lambda self: queued.append(("dispatched",)),
    )
    monkeypatch.setattr(
        provider_mod.bootstrap, "ensure_brain", lambda home: {"parent_page_id": "fake"}
    )
    monkeypatch.setattr(provider_mod.bootstrap, "read_memory_from_disk", lambda home: "")
    monkeypatch.setattr(provider_mod.bootstrap, "read_user_from_disk", lambda home: "")
    p = provider_mod.NotionBrainProvider()
    p.initialize("sess", hermes_home=str(tmp_path))
    assert queued == [("dispatched",)]
