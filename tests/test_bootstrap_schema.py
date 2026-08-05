"""Bootstrap/schema consistency checks."""

from __future__ import annotations

from copy import deepcopy

from notion_brain import bootstrap
from notion_brain.schema import STATUSES


def _notion_db_from_expected(expected):
    props = {}
    for name, spec in expected.items():
        prop_type = next(iter(spec))
        props[name] = {"type": prop_type, prop_type: deepcopy(spec[prop_type])}
    return {"properties": props}


def test_status_property_options_match_schema_statuses():
    for db_name, props in bootstrap._PROPS.items():
        status = props.get("Status") or {}
        if "status" not in status:
            continue
        names = {o["name"] for o in status["status"].get("options", [])}
        assert names == STATUSES, db_name


def test_database_schema_matches_expected_schema():
    db = _notion_db_from_expected(bootstrap._PROPS["memory"])
    assert bootstrap._database_schema_matches(db, bootstrap._PROPS["memory"])


def test_database_schema_mismatch_detects_zombie_status_options():
    db = _notion_db_from_expected(bootstrap._PROPS["memory"])
    db["properties"]["Status"]["status"]["options"].append({"name": "Not started"})
    assert not bootstrap._database_schema_matches(db, bootstrap._PROPS["memory"])


def test_database_schema_mismatch_detects_missing_property():
    db = _notion_db_from_expected(bootstrap._PROPS["memory"])
    # remove a required property
    del db["properties"]["Status"]
    assert not bootstrap._database_schema_matches(db, bootstrap._PROPS["memory"])


def test_database_schema_mismatch_detects_wrong_type():
    db = _notion_db_from_expected(bootstrap._PROPS["memory"])
    # change type from 'status' to 'select'
    db["properties"]["Status"] = {"type": "select", "select": {}}
    assert not bootstrap._database_schema_matches(db, bootstrap._PROPS["memory"])

