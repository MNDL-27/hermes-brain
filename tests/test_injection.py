"""Offline coverage for the RET-03 deterministic two-lane budget."""

from __future__ import annotations

from notion_brain.brain_cache import is_pinned_kind
from notion_brain.injection import count_tokens, render_injection


def test_lane_budgets_and_combined_hard_cap() -> None:
    lines = (
        [("identity", f"p{i}") for i in range(401)]
        + [("fact", f"d{i}") for i in range(401)]
    )
    rendered = render_injection(lines)
    words = rendered.splitlines()

    assert len(words) == 800
    assert all(word.startswith("p") for word in words[:400])
    assert all(word.startswith("d") for word in words[400:])
    assert count_tokens(" ".join(words[:400])) == 400
    assert count_tokens(" ".join(words[400:])) == 400
    assert count_tokens(rendered) <= 800


def test_truncation_is_deterministic() -> None:
    lines = [("warning", "keep this"), ("fact", "and this"), ("fact", "drop later")]
    assert render_injection(lines, lane1_budget=2, lane2_budget=3) == render_injection(
        lines, lane1_budget=2, lane2_budget=3,
    )


def test_overflow_drops_from_lane_end_in_order() -> None:
    rendered = render_injection(
        [("fact", "first two"), ("fact", "this line overflows"), ("fact", "later line")],
        lane1_budget=0, lane2_budget=3,
    )
    assert rendered == "first two"


def test_pinned_kinds_are_honored() -> None:
    for kind in ("decision", "warning", "identity", "preference", "pinned", "critical"):
        assert is_pinned_kind(kind)
    assert is_pinned_kind("IDENTITY")
    assert not is_pinned_kind("fact")

    rendered = render_injection(
        [("fact", "dynamic"), ("identity", "pinned")], lane1_budget=1, lane2_budget=1,
    )
    assert rendered.splitlines() == ["pinned", "dynamic"]
