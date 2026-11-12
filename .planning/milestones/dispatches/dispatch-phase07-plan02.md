You are implementing v1.2 Phase 7 Plan 02 in repository /home/protik/projects/hermes-brain.

Read before editing:
- /home/protik/projects/hermes-brain/AGENTS.md
- .planning/phases/07-update-ux-commit-level-drift-release-notes-link/07-02-PLAN.md
- notion_brain/update.py (already contains Phase 7 Plan 01 drift detection — extend, do not rewrite)
- notion_brain/update_cache.py
- tests/test_update_cache.py

Scope only:
- Persist commit-drift fields (drift_type, behind_commits, ahead_commits, release_url) in $HERMES_HOME/.update_cache.json via refresh().
- Keep atomic tempfile write + os.replace + 0o600 + fsync exactly as today.
- Cache load path stays synchronous <1ms with zero network; stale-TTL refresh stays on the background worker.
- Offline/rate-limited degradation: no unhandled exceptions.
- Add tests in tests/test_update_cache.py: serialization round-trip of drift fields, silent degradation when git/network fail, atomic write preserved.
- Do not commit.

Verification:
1. export PATH=/home/protik/.hermes/tools/uv-0.13.5-linux-x64:$PATH
2. cd /home/protik/projects/hermes-brain
3. uv run --no-sync pytest tests/test_update_cache.py tests/test_update.py -q
4. uv run --no-sync ruff check notion_brain tests
5. uv run --no-sync mypy notion_brain

Return files changed, commands run, outputs, blockers. Leave changes uncommitted.