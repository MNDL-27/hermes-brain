---
quick_id: 260928-mli
slug: add-top-level-permissions-block-to-publi
status: complete
date: 2026-09-28
files_modified:
  - .github/workflows/publish.yml
---

# Quick Task 260928-mli — Add top-level permissions block to publish.yml (CodeQL hardening)

## Objective

Resolve the CodeQL medium-severity **"Workflow does not contain permissions"** alerts on
`.github/workflows/publish.yml` (PR #57) by declaring an explicit least-privilege top-level
`permissions:` block.

## What changed

`.github/workflows/publish.yml` — inserted a top-level block between `concurrency:` and `jobs:`:

```yaml
permissions:
  contents: read
```

## Why this is safe (job-level overrides)

A job-level `permissions:` block fully **replaces** the top-level default for that job, so the
privileged jobs are unaffected:

- `publish` job — keeps `id-token: write` + `contents: read` (PyPI OIDC trusted publishing).
- `release` job — keeps `contents: write` (`gh release create`).

The four jobs that had no `permissions:` block of their own now inherit the read-only default:

- `test`, `lint`, `smoke-test` — only checkout/read; `contents: read` is sufficient.
- `build` — checks out and uploads an artifact via `actions/upload-artifact`; artifact upload is
  not gated by `GITHUB_TOKEN` content scopes, so `contents: read` is sufficient.

## Verification

```
python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/publish.yml')); \
  assert d['permissions']=={'contents':'read'}; \
  assert d['jobs']['publish']['permissions']=={'id-token':'write','contents':'read'}; \
  assert d['jobs']['release']['permissions']=={'contents':'write'}"
# => publish.yml permissions OK
```

Confirmed: top-level `permissions: contents: read` present; publish (OIDC) and release job-level
blocks intact; `test`/`lint`/`build`/`smoke-test` carry no job-level block (inherit read-only);
file still parses as valid YAML.

## Result

- The 4 CodeQL "Workflow does not contain permissions" alerts should clear on the next CodeQL scan
  of PR #57.
- The PyPI publish/release pipeline is functionally unchanged.

## Notes

- Pushing this change re-triggers PR #57 CI, which includes a fresh **OrcaCode Review** run. That
  check is failing independently of this change — its own log shows
  `all 14 file review(s) failed — check your LLM configuration and API key` → the bot "fails
  closed" with zero code findings. Resolving it is a repo-secrets/LLM-config matter on the
  OrcaCode workflow side, not a code issue in this PR.
