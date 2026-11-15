from __future__ import annotations

import json
import stat

import pytest

from notion_brain import store, vault_sync
from notion_brain.__main__ import main
from notion_brain.adapters import ObsidianVaultAdapter, get_adapter
from notion_brain.entitlement import EntitlementError


def _home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return home


def _vault(tmp_path):
    vault = tmp_path / "vault"
    (vault / "agents").mkdir(parents=True)
    (vault / "journal").mkdir()
    return vault


def test_build_ingest_entries_parses_memory_and_journal(tmp_path):
    vault = _vault(tmp_path)
    (vault / "agents" / "memory.md").write_text(
        "# Memory\n\n"
        "### [2026-01-02] Device\nPixel 8\n\n"
        "### [YYYY-MM-DD] Memory Title\nExample body\n",
        encoding="utf-8",
    )
    (vault / "journal" / "2026-01-02.md").write_text(
        "# Journal\n\n"
        "## [10:30] Agent: Deploy\nShipped cache\n\n"
        "## [HH:MM] Agent: Title\nExample body\n",
        encoding="utf-8",
    )

    entries = vault_sync.build_ingest_entries(vault)

    assert [entry["title"] for entry in entries] == [
        "Vault Memory · [2026-01-02] Device",
        "Vault Journal · 2026-01-02 10:30 · Agent: Deploy",
    ]
    assert entries[0]["truth"] == "certified"
    assert entries[1]["truth"] == "inferred"
    assert entries[0]["tags"] == ["vault", "mirror", "memory"]


def test_legacy_state_migrates_to_unified_shape(tmp_path):
    home = _home(tmp_path)
    (home / "vault_notion_mirror_state.json").write_text(
        json.dumps({
            "entries": {"Vault Memory · X": "abc"},
            "last_run": "2026-01-01T00:00:00",
        }),
        encoding="utf-8",
    )

    state = vault_sync.load_state(home)

    assert state["version"] == 1
    assert state["ingest"]["entries"] == {"Vault Memory · X": "abc"}
    assert state["ingest"]["last_run"] == "2026-01-01T00:00:00"
    assert state["bootstrap"] == {"page_ids": [], "last_bootstrap": ""}


def test_ingest_writes_pending_then_noop(monkeypatch, tmp_path):
    home = _home(tmp_path)
    vault = _vault(tmp_path)
    (vault / "agents" / "memory.md").write_text(
        "### [2026-01-01] Fact\nBody\n", encoding="utf-8"
    )
    (vault / "journal" / "2026-01-01.md").write_text(
        "## [09:00] Agent: Log\nEntry\n", encoding="utf-8"
    )
    captured = []
    monkeypatch.setattr(
        "notion_brain.provider.NotionBrainProvider.initialize",
        lambda self, *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "notion_brain.provider.NotionBrainProvider._store_entry",
        lambda self, entry: captured.append(entry),
    )

    first = vault_sync.ingest(home, vault)

    assert first["written"] == 2 and first["failed"] == 0
    assert {entry.truth for entry in captured} == {"certified", "inferred"}

    second = vault_sync.ingest(home, vault)

    assert second["written"] == 0 and second["skipped"] == 2
    state_file = home / "vault_sync_state.json"
    assert state_file.is_file()
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600


def test_ingest_dry_run_writes_nothing(tmp_path):
    home = _home(tmp_path)
    vault = _vault(tmp_path)
    (vault / "agents" / "memory.md").write_text(
        "### [2026-01-01] Fact\nBody\n", encoding="utf-8"
    )

    result = vault_sync.ingest(home, vault, dry_run=True)

    assert result["pending"] == 1 and result["written"] == 0
    assert not (home / "vault_sync_state.json").exists()


def test_ingest_error_isolation_and_redaction(monkeypatch, tmp_path):
    secret = "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
    home = _home(tmp_path)
    vault = _vault(tmp_path)
    (vault / "agents" / "memory.md").write_text(
        "### [2026-01-01] Good\nSafe body\n\n"
        "### [2026-01-02] Bad\nBroken body\n",
        encoding="utf-8",
    )
    written = []
    monkeypatch.setattr(
        "notion_brain.provider.NotionBrainProvider.initialize",
        lambda self, *args, **kwargs: None,
    )

    def store_entry(self, entry):
        if "Bad" in entry.title:
            raise RuntimeError(f"boom {secret}")
        written.append(entry)

    monkeypatch.setattr(
        "notion_brain.provider.NotionBrainProvider._store_entry", store_entry
    )

    result = vault_sync.ingest(home, vault)

    assert result["written"] == 1 and result["failed"] == 1
    assert secret not in str(result["errors"])
    assert "[REDACTED_SECRET]" in result["errors"][0]


def test_bootstrap_exports_and_skips(monkeypatch, tmp_path):
    home = _home(tmp_path)
    vault = _vault(tmp_path)
    (home / "hermes_brain.license").write_text("stub", encoding="utf-8")
    monkeypatch.setattr(
        "notion_brain.bootstrap._load_cache", lambda path: {"db_memory": "db1"}
    )
    rows = [
        {
            "id": "page-1", "title": "Phone", "created_time": "2026-01-01",
            "properties": {
                "Content": "Pixel", "Status": "active", "Truth": "certified",
                "Subject Key": "device.phone", "Source Session": "s1",
                "Kind": "note", "Tags": ["device"],
            },
        },
        {"id": "page-old", "title": "Old", "properties": {"Content": "x", "Status": "Superseded"}},
    ]
    monkeypatch.setattr(store, "query_database", lambda *a, **k: rows)

    first = vault_sync.bootstrap(home, vault)

    assert first["exported"] == 1 and first["failed"] == 0
    adapter = get_adapter("obsidian", hermes_home=str(home), obsidian_vault=vault)
    note = adapter.find("page-1")
    assert note is not None
    assert note["truth"] == "certified" and note["source_session"] == "s1"

    second = vault_sync.bootstrap(home, vault)

    assert second["exported"] == 0 and second["skipped"] == 1
    state = json.loads((home / "vault_sync_state.json").read_text(encoding="utf-8"))
    assert state["bootstrap"]["page_ids"] == ["page-1"]


def test_bootstrap_dry_run_writes_nothing(monkeypatch, tmp_path):
    home = _home(tmp_path)
    vault = _vault(tmp_path)
    (home / "hermes_brain.license").write_text("stub", encoding="utf-8")
    monkeypatch.setattr(
        "notion_brain.bootstrap._load_cache", lambda path: {"db_memory": "db1"}
    )
    monkeypatch.setattr(store, "query_database", lambda *a, **k: [{
        "id": "page-1", "title": "Phone",
        "properties": {"Content": "Pixel", "Status": "active"},
    }])

    result = vault_sync.bootstrap(home, vault, dry_run=True)

    assert result["exported"] == 1
    adapter = get_adapter("obsidian", hermes_home=str(home), obsidian_vault=vault)
    assert adapter.find("page-1") is None
    assert not (home / "vault_sync_state.json").exists()


def test_bootstrap_requires_entitlement(tmp_path):
    home = _home(tmp_path)
    vault = _vault(tmp_path)

    with pytest.raises(EntitlementError):
        vault_sync.bootstrap(home, vault)


def test_status_reports_health_and_state(tmp_path):
    home = _home(tmp_path)
    vault = _vault(tmp_path)
    (home / "hermes_brain.license").write_text("stub", encoding="utf-8")
    adapter = ObsidianVaultAdapter(vault)
    adapter.remember({"title": "Fact", "content": "Body"})
    state = vault_sync.empty_state()
    state["ingest"]["last_run"] = "2026-01-01T00:00:00"
    vault_sync.save_state(home, state)

    result = vault_sync.status(home, vault)

    assert result["backend"] == "obsidian"
    assert result["entitled"] is True
    assert result["count"] == 1
    assert result["last_run"] == "2026-01-01T00:00:00"
    assert result["schema_version"] == 2


def test_cli_vault_status_json(tmp_path, capsys):
    home = _home(tmp_path)
    vault = _vault(tmp_path)

    code = main([
        "--home", str(home), "vault", "status", "--json", "--vault", str(vault),
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["backend"] == "obsidian"
    assert payload["vault_path"] == str(vault.resolve())


def test_cli_vault_sync_dry_run(monkeypatch, tmp_path, capsys):
    home = _home(tmp_path)
    vault = _vault(tmp_path)
    (vault / "agents" / "memory.md").write_text(
        "### [2026-01-01] Fact\nBody\n", encoding="utf-8"
    )
    monkeypatch.setattr(store, "get_api_key", lambda: "token")

    code = main([
        "--home", str(home), "vault", "sync", "--dry-run", "--json",
        "--vault", str(vault),
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True and payload["pending"] == 1
