"""Deterministic two-lane prompt injection budget (RET-03).

Lane 1 holds pinned identity, warnings, and decisions. Lane 2 holds the
remaining dynamic context. Each lane is capped at 400 tokens and the
combined injection is hard-capped at 800 tokens.

Token count is whitespace-delimited words. Truncation always drops from
the end of a lane, in input order, so the same lines always yield the
same prompt.
"""

from __future__ import annotations

import re

from .brain_cache import is_pinned_kind

LANE1_TOKEN_BUDGET = 400
LANE2_TOKEN_BUDGET = 400
TOTAL_TOKEN_BUDGET = 800


def count_tokens(text: str) -> int:
    """Count tokens as whitespace-delimited words. Empty text is zero."""
    if not text or not text.strip():
        return 0
    return len(text.split())


def trim_tokens(text: str, budget: int) -> str:
    """Retain a bounded prefix while preserving whitespace within that prefix."""
    if budget <= 0:
        return ""
    words = list(re.finditer(r"\S+", text))
    if len(words) <= budget:
        return text.strip()
    return text[:words[budget - 1].end()].strip()


def render_disk_context(memory_text: str, user_text: str) -> str:
    """Fit disk identity and dynamic memory into their respective lanes."""
    if not memory_text.strip() and not user_text.strip():
        return ""
    marker = "<!-- memory-context from disk -->"
    lines = [("identity", marker)]
    if user_text.strip():
        lines.append(("identity", trim_tokens(user_text, LANE1_TOKEN_BUDGET - count_tokens(marker))))
    if memory_text.strip():
        lines.append(("note", trim_tokens(memory_text, LANE2_TOKEN_BUDGET)))
    return render_injection(lines)


def _fit_lines(lines: list[str], budget: int) -> tuple[list[str], int]:
    """Keep a prefix of ``lines`` whose token sum is <= ``budget``.

    A line that would cross the budget is dropped entirely (and so is
    everything after it). Order is preserved.
    """
    if budget <= 0:
        return [], 0
    kept: list[str] = []
    used = 0
    for line in lines:
        cost = count_tokens(line)
        if cost == 0:
            continue
        if used + cost > budget:
            break
        kept.append(line)
        used += cost
    return kept, used


def render_injection(
    lines: list[tuple[str, str]],
    *,
    lane1_budget: int = LANE1_TOKEN_BUDGET,
    lane2_budget: int = LANE2_TOKEN_BUDGET,
) -> str:
    """Split ``(kind, line)`` pairs into two lanes and cap the result.

    Lane assignment uses :func:`is_pinned_kind`. Within a lane, earlier
    lines win. After each lane is trimmed to its own budget, the combined
    text is trimmed again so it never exceeds
    ``min(lane1_budget + lane2_budget, 800)`` tokens. Lane 2 is shortened
    first; Lane 1 is shortened only if Lane 2 is already empty.
    """
    lane1_cap = max(0, int(lane1_budget))
    lane2_cap = max(0, int(lane2_budget))
    hard_cap = min(lane1_cap + lane2_cap, TOTAL_TOKEN_BUDGET)

    pinned = [line for kind, line in lines if is_pinned_kind(kind)]
    dynamic = [line for kind, line in lines if not is_pinned_kind(kind)]

    # Unused room in one lane does not spill into the other. The hard
    # cap shrinks lane 2 first, then lane 1, and never exceeds 800.
    lane1, lane1_used = _fit_lines(pinned, min(lane1_cap, hard_cap))
    remaining = max(0, hard_cap - lane1_used)
    lane2, _lane2_used = _fit_lines(dynamic, min(lane2_cap, remaining))
    return "\n".join(lane1 + lane2)
