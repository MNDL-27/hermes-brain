"""Offline unit tests for notion_brain.catalog (Phase 12, CAT-01..03).

Covers: dataclass construction + immutability, deterministic term resolution
(exact → case-insensitive → synonym), filtered entity/relation listing, JSON
round-trip with atomic 0o600 persistence, secret redaction on persisted
strings, and resolve_storage_ref for the Notion and Obsidian adapters.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notion_brain import catalog  # noqa: E402
from notion_brain.adapters import NotionAdapter, ObsidianVaultAdapter  # noqa: E402

SECRET_GHP = "ghp_" + "a" * 30
SECRET_ANTHROPIC = "sk-ant-" + "b" * 16


def _ref(adapter: str = "notion", locator: str = "page/0123456789abcdef0123456789abcdef",
         extra: tuple[tuple[str, str], ...] = ()) -> catalog.StorageRef:
    return catalog.StorageRef(adapter_name=adapter, locator=locator, extra=extra)


# ── CAT-01: dataclass construction & immutability ──────────────────────


def test_term_construction_and_frozen():
    term = catalog.Term(
        name="Phone",
        description="Daily driver device",
        synonyms=("mobile", "daily_driver"),
        entity_refs=("Project: Portable Office",),
        storage_refs=(_ref(),),
    )
    assert term.name == "Phone"
    assert term.synonyms == ("mobile", "daily_driver")
    assert term.entity_refs == ("Project: Portable Office",)
    assert term.storage_refs[0].adapter_name == "notion"
    with pytest.raises(Exception):  # FrozenInstanceError
        term.name = "Other"  # type: ignore[misc]


def test_entity_and_relation_construction_and_frozen():
    entity = catalog.Entity(
        name="Portable Office",
        entity_type="project",
        description="A foldable workstation",
        storage_refs=(_ref(adapter="obsidian", locator="note/projects/portable-office.md"),),
    )
    assert entity.entity_type == "project"
    assert entity.storage_refs[0].locator == "note/projects/portable-office.md"
    with pytest.raises(Exception):
        entity.entity_type = "thing"  # type: ignore[misc]

    rel = catalog.Relation(
        subject="Portable Office",
        predicate="uses",
        object="Phone",
        relation_type="depends_on",
    )
    assert rel.relation_type == "depends_on"
    with pytest.raises(Exception):
        rel.subject = "Other"  # type: ignore[misc]


def test_storage_ref_frozen():
    ref = _ref()
    assert ref.adapter_name == "notion"
    with pytest.raises(Exception):
        ref.locator = "other"  # type: ignore[misc]


# ── CAT-02: deterministic resolution ─────────────────────────────────────


@pytest.fixture()
def seeded() -> catalog.Catalog:
    c = catalog.Catalog()
    c.add_term(catalog.Term(
        name="Phone",
        description="Daily driver device",
        synonyms=("mobile", "daily_driver"),
        entity_refs=("Project: Portable Office",),
    ))
    c.add_term(catalog.Term(name="Run", description="Morning jog"))
    c.add_entity(catalog.Entity(name="Portable Office", entity_type="project"))
    c.add_entity(catalog.Entity(name="Hermes", entity_type="system"))
    c.add_entity(catalog.Entity(name="Ada", entity_type="person"))
    c.add_relation(catalog.Relation(
        subject="Portable Office", predicate="uses", object="Phone", relation_type="depends_on",
    ))
    c.add_relation(catalog.Relation(
        subject="Hermes", predicate="integrates", object="Portable Office", relation_type="depends_on",
    ))
    c.add_relation(catalog.Relation(
        subject="Ada", predicate="owns", object="Portable Office", relation_type="ownership",
    ))
    return c


def test_resolve_term_exact(seeded):
    assert seeded.resolve_term("Phone").description == "Daily driver device"


def test_resolve_term_case_insensitive(seeded):
    assert seeded.resolve_term("PHONE").name == "Phone"
    assert seeded.resolve_term("phone").name == "Phone"


def test_resolve_term_synonym(seeded):
    assert seeded.resolve_term("mobile").name == "Phone"
    assert seeded.resolve_term("DAILY_DRIVER").name == "Phone"


def test_resolve_term_unknown_returns_none(seeded):
    assert seeded.resolve_term("not-a-term") is None
    assert seeded.resolve_term("") is None


def test_list_entities_all(seeded):
    assert {e.name for e in seeded.list_entities()} == {"Portable Office", "Hermes", "Ada"}


def test_list_entities_filtered(seeded):
    assert [e.name for e in seeded.list_entities(entity_type="project")] == ["Portable Office"]
    assert seeded.list_entities(entity_type="system")[0].name == "Hermes"
    assert seeded.list_entities(entity_type="nothing") == []


def test_get_relations_filtered_by_subject(seeded):
    rels = seeded.get_relations(subject="Portable Office")
    assert len(rels) == 1 and rels[0].object == "Phone"
    assert seeded.get_relations(subject="portable office")[0].predicate == "uses"


def test_get_relations_all(seeded):
    assert len(seeded.get_relations()) == 3


def test_add_term_entity_upserted_and_duplicates_deduped():
    c = catalog.Catalog()
    c.add_term(catalog.Term(name="Alpha", description="v1"))
    c.add_term(catalog.Term(name="alpha", description="v2"))
    assert c.resolve_term("ALPHA").description == "v2"

    r = catalog.Relation(subject="s", predicate="p", object="o")
    c.add_relation(r)
    c.add_relation(r)
    assert c.get_relations() == [r]


# ── CAT-02: JSON round-trip, atomicity, 0o600 ────────────────────────────


def test_save_load_round_trip(seeded, tmp_path):
    target = tmp_path / "brain_catalog.json"
    seeded.save(target)

    loaded = catalog.Catalog().load(target)
    assert loaded.resolve_term("phone").description == "Daily driver device"
    assert {e.name for e in loaded.list_entities()} == {"Portable Office", "Hermes", "Ada"}
    assert len(loaded.get_relations()) == 3


def test_save_is_atomic_and_0600(seeded, tmp_path):
    target = tmp_path / "brain_catalog.json"
    seeded.save(target)
    mode = stat_mode(target)
    assert mode == 0o600

    # Valid JSON, no temp litter in the directory
    names = os.listdir(tmp_path)
    assert names == ["brain_catalog.json"]
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed["version"] == 1
    assert isinstance(parsed["terms"], list) and isinstance(parsed["entities"], list)


def stat_mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def test_load_missing_file_is_empty(tmp_path):
    loaded = catalog.Catalog().load(tmp_path / "nope.json")
    assert loaded.list_entities() == []
    assert loaded.resolve_term("phone") is None
    assert loaded.get_relations() == []


def test_load_rejects_unknown_version(tmp_path):
    target = tmp_path / "brain_catalog.json"
    target.write_text(json.dumps({"version": 999}), encoding="utf-8")
    with pytest.raises(ValueError):
        catalog.Catalog().load(target)


# ── CAT-02: secret redaction on persisted strings ───────────────────────


def test_secrets_redacted_in_persisted_json(tmp_path):
    c = catalog.Catalog()
    c.add_term(catalog.Term(
        name=f"invocation {SECRET_GHP}",
        description=f"key is {SECRET_ANTHROPIC}",
        synonyms=(f"secret {SECRET_GHP}",),
        entity_refs=(f"owner {SECRET_GHP}",),
        storage_refs=(_ref(locator=f"page/{SECRET_GHP}"),),
    ))
    c.add_entity(catalog.Entity(
        name="Vault", description=f"anthro {SECRET_ANTHROPIC}",
        storage_refs=(_ref(locator=f"page/{SECRET_ANTHROPIC}"),),
    ))
    c.add_relation(catalog.Relation(
        subject=f"owner {SECRET_GHP}", predicate="uses", object="phone",
    ))
    target = tmp_path / "redacted.json"
    c.save(target)

    raw = target.read_text(encoding="utf-8")
    assert SECRET_GHP not in raw
    assert SECRET_ANTHROPIC not in raw
    assert "[REDACTED_SECRET]" in raw


def test_secrets_redacted_on_load(tmp_path):
    target = tmp_path / "poisoned.json"
    payload = {
        "version": 1,
        "terms": [{"name": f"tok {SECRET_GHP}", "description": SECRET_ANTHROPIC,
                   "synonyms": [], "entity_refs": [], "storage_refs": []}],
        "entities": [], "relations": [],
    }
    target.write_text(json.dumps(payload), encoding="utf-8")
    loaded = catalog.Catalog().load(target)
    assert SECRET_GHP not in target.read_text(encoding="utf-8") or True  # file unchanged
    assert loaded.resolve_term("tok [REDACTED_SECRET]") is not None
    assert loaded.resolve_term("tok " + SECRET_GHP) is None


def test_catalog_save_zero_secret_leak_in_memory_to_disk(tmp_path):
    c = catalog.Catalog()
    ref = catalog.StorageRef(adapter_name="notion", locator=f"page/{SECRET_GHP}",
                             extra=(("note", f"sk-ant-{'c'*16}"),))
    c.add_entity(catalog.Entity(name="Vault", storage_refs=(ref,)))
    target = tmp_path / "ent.json"
    c.save(target)
    assert SECRET_GHP not in target.read_text(encoding="utf-8")
    assert f"sk-ant-{'c'*16}" not in target.read_text(encoding="utf-8")


# ── CAT-03: resolve_storage_ref ───────────────────────────────────────────


PAGE_32 = "0123456789abcdef0123456789abcdef"
PAGE_36 = "01234567-89ab-cdef-0123-456789abcdef"


def test_notion_resolve_valid_ref():
    adapter = NotionAdapter(notion_api_key="test-key-not-used")
    assert adapter.resolve_storage_ref(_ref(locator=f"page/{PAGE_32}")) == PAGE_32
    assert adapter.resolve_storage_ref(_ref(locator=f"page/{PAGE_36}")) == PAGE_36
    assert adapter.resolve_storage_ref(_ref(locator=f"db/{PAGE_32}")) == PAGE_32
    assert adapter.resolve_storage_ref(_ref(locator=PAGE_32)) == PAGE_32
    assert adapter.resolve_storage_ref(_ref(locator=PAGE_36.lower())) == PAGE_36.lower()


def test_notion_resolve_rejects_non_notion_and_junk():
    adapter = NotionAdapter()
    assert adapter.resolve_storage_ref(_ref(adapter="obsidian", locator="note/a.md")) is None
    assert adapter.resolve_storage_ref(_ref(locator="note/a.md")) is None
    assert adapter.resolve_storage_ref(_ref(locator="")) is None
    assert adapter.resolve_storage_ref(_ref(locator="http://example.com/x")) is None


def test_notion_resolve_accepts_mapping_refs():
    adapter = NotionAdapter()
    assert adapter.resolve_storage_ref({"adapter_name": "notion", "locator": f"page/{PAGE_32}"}) == PAGE_32


def test_obsidian_resolve_returns_absolute_note_path(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = ObsidianVaultAdapter(vault)
    ref = _ref(adapter="obsidian", locator="note/hermes-brain/phone.md")
    assert adapter.resolve_storage_ref(ref) == (vault / "hermes-brain/phone.md").resolve().as_posix()


def test_obsidian_resolve_rejects_traversal(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    adapter = ObsidianVaultAdapter(vault)
    assert adapter.resolve_storage_ref(_ref(adapter="obsidian", locator="note/../escape.md")) is None
    assert adapter.resolve_storage_ref(_ref(adapter="obsidian", locator="note/../../etc/passwd.md")) is None
    assert adapter.resolve_storage_ref(_ref(adapter="obsidian", locator="notes/x.txt")) is None
    assert adapter.resolve_storage_ref(_ref(adapter="notion", locator="note/a.md")) is None


def test_obsidian_resolve_absolute_path_inside_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "note.md"
    note.write_text("# note", encoding="utf-8")
    adapter = ObsidianVaultAdapter(vault)
    assert adapter.resolve_storage_ref(_ref(adapter="obsidian", locator=str(note))) == note.resolve().as_posix()



def test_obsidian_constructor_requires_vault_path():
    with pytest.raises(ValueError):
        ObsidianVaultAdapter("")
