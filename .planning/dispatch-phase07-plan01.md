You are implementing v1.2 Phase 7 Plan 01 in repository /home/protik/projects/hermes-brain.

Read before editing:
- /home/protik/projects/hermes-brain/AGENTS.md
- .planning/phases/07-update-ux-commit-level-drift-release-notes-link/07-01-PLAN.md
- notion_brain/update.py
- notion_brain/__main__.py
- tests/test_update.py

Scope only:
- Implement UPD-06 commit drift detection in notion_brain/update.py.
- Implement UPD-07 canonical release URL and output/exit-code behavior as specified in the plan.
- Add/update tests in tests/test_update.py.
- Do not work on Phase 7 Plan 02, Phase 8, v1.3, or v1.4.
- Do not modify planning files.
- Do not commit.

Constraints:
- Preserve detect+instruct only: never git fetch, git pull, pip install, or environment mutation in check paths.
- Non-main branch/detached HEAD skips commit drift.
- Use existing project style and stdlib/native dependencies only.
- Keep all tests hermetic under repository socket-deny fixture.

Verification:
1. export PATH=/home/protik/.hermes/tools/uv-0.13.5-linux-x64:$PATH
2. cd /home/protik/projects/hermes-brain
3. uv run --no-sync pytest tests/test_update.py -q
4. uv run --no-sync ruff check notion_brain/update.py notion_brain/__main__.py tests/test_update.py
5. uv run --no-sync mypy notion_brain

Return exact files changed, commands run, outputs, and any blocker. Leave working tree changes uncommitted for coordinator review.