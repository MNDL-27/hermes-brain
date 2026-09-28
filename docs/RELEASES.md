# Release Guide

This runbook is the contract between the publish workflow and the human who has to debug it at 2am. Four sections: the happy automated path, the one-time PyPI setup, the offline fallback, and recovery.

See `.github/workflows/publish.yml` for the automated path and `tests/test_packaging.py::test_version_strings_match` for the version-sync guard.

## 1. Automated Release (Standard)

The happy path uses `.github/workflows/publish.yml`. The workflow triggers on any `v*` tag push to `origin`.

1. Ensure the working directory is on `main` and clean: `git status` shows no uncommitted changes.
2. Bump the version in **both** files (drift between them fails CI before the tag ever ships):
   - `pyproject.toml` — `[project].version`
   - `notion_brain/__init__.py` — `__version__`
3. Commit with the message `chore: release vX.Y.Z`.
4. Tag locally: `git tag vX.Y.Z`.
5. Push: `git push origin main --tags`.
6. Watch the **Publish to PyPI** workflow in the Actions tab.

Pre-release tags (`vX.Y.Zb1`, `vX.Y.Zrc1`) are automatically flagged on PyPI — `pip install hermes-brain` will not pick them up without `--pre`.

## 2. One-Time PyPI Trusted Publisher Setup

Required before the first tag push. The workflow uses OIDC under the `pypi` environment, which PyPI must be told to trust.

### Option A — Pending publisher (recommended)

1. Log in to [pypi.org](https://pypi.org).
2. Account settings → **Publishing** → **Add a pending publisher** → choose **GitHub**.
3. Fill the form:
   - **PyPI Project Name**: `hermes-brain`
   - **Owner**: `MNDL-27`
   - **Repository name**: `hermes-brain`
   - **Workflow filename**: `publish.yml`
   - **Environment name**: `pypi`
4. The first real publish via the workflow auto-creates the project on PyPI.

### Option B — Manual project create

1. Register `hermes-brain` on PyPI first (a placeholder upload is the standard way).
2. Then add the trusted publisher as in Option A.

### GitHub Environment

In this repo: **Settings → Environments → New environment → name it exactly `pypi`**.

The `environment: pypi` literal in `publish.yml` and the **Environment name: pypi** literal in PyPI settings must match byte-for-byte.

## 3. Emergency Manual Release (Fallback)

For when GitHub Actions or OIDC is unavailable. Run from a clone with the tag checked out locally.

```bash
rm -rf dist/ build/ *.egg-info
python -m build
twine check --strict dist/*
export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="pypi-<your-token-here>"
twine upload dist/*
```

- The pre-build `rm -rf` is mandatory: PyPI releases are immutable, and leftover `dist/` artifacts collide.
- `TWINE_PASSWORD` must be set via env var or `~/.pypirc` — never as a CLI argument and never committed.
- Generate the token at pypi.org → Account settings → API tokens; scope it to project `hermes-brain` only.
- When OIDC comes back online, revoke the manual token.

## 4. Release Recovery & Troubleshooting

Two failure branches.

### 4a. Build or test failed before publish

1. Fix the issue.
2. Delete the tag locally and remotely: `git tag -d vX.Y.Z && git push --delete origin vX.Y.Z`.
3. Commit the fix.
4. Re-tag and re-push.

### 4b. Bad package already published to PyPI

PyPI forbids re-uploading the same version.

1. Yank via pypi.org → Project → Releases → find version → Options → **Yank**.
2. Cut a `vX.Y.Z+1` patch release that supersedes it.

Yanked releases still install with `pip install --no-deps` but are hidden from default resolution.
