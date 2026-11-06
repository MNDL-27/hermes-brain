You are implementing v1.2 Phase 8 Plan 02 (developer tooling) in repository /home/protik/projects/hermes-brain.

Read before editing:
- /home/protik/projects/hermes-brain/AGENTS.md
- .planning/phases/08-developer-tooling-test-reliability/08-02-PLAN.md
- CONTRIBUTING.md

Scope:
Task 1 (TOOL-01) — scripts/pre-push opt-in hook:
- Create executable bash script `scripts/pre-push` with shebang `#!/usr/bin/env bash` and `set -euo pipefail`.
- Must check environment variable `HERMES_BRAIN_SKIP_PRE_PUSH`: if non-empty, print "hermes-brain: pre-push hook skipped (HERMES_BRAIN_SKIP_PRE_PUSH set)" and exit 0.
- Must run under 300-second timeout: `timeout 300 uv run --no-sync pytest -q` (fall back to python -m pytest if uv is not on path).
- Never mutates the environment: no pip install, no git pull, no uv sync.
- Make it executable (chmod +x scripts/pre-push).
- Document in CONTRIBUTING.md: installation is opt-in via `cp scripts/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push`; escape hatch is `HERMES_BRAIN_SKIP_PRE_PUSH=1 git push`.

Task 2 (TOOL-02) — .github/workflows/pre-commit-autoupdate.yml:
- Create scheduled GitHub Action running on cron `17 6 * * 1` (Mondays 06:17 UTC) and workflow_dispatch.
- Least privilege permissions: workflow-level `permissions: contents: read`; job overrides to `contents: write` and `pull-requests: write`.
- Runs `pre-commit autoupdate` on Ubuntu latest, Python 3.12, using uv.
- Opens a PR via peter-evans/create-pull-request@v6 if .pre-commit-config.yaml changed; includes timestamp in branch suffix (`pre-commit-autoupdate-` prefix) and sets `delete-branch: true`.
- If no diff, prints a summary and exits cleanly with zero PR creation.

Verification:
1. export PATH=/home/protik/.hermes/tools/uv-0.13.5-linux-x64:$PATH
2. cd /home/protik/projects/hermes-brain
3. test -x scripts/pre-push
4. bash -n scripts/pre-push
5. HERMES_BRAIN_SKIP_PRE_PUSH=1 ./scripts/pre-push   (must exit 0 with skip message)
6. Python/YAML linting: check syntax of .github/workflows/pre-commit-autoupdate.yml
7. uv run --no-sync ruff check notion_brain tests

Do not commit. Return files created, verify output, blockers.