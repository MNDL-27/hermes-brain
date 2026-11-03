---
phase: quick-260928-mli
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - .github/workflows/publish.yml
autonomous: true
requirements: [SEC-CODEQL-WORKFLOW-PERMS]
user_setup: []
---

<objective>
Resolve the CodeQL medium-severity "Workflow does not contain permissions" alerts on
`.github/workflows/publish.yml` (PR #57) by declaring an explicit least-privilege top-level
`permissions:` block. GitHub's default `GITHUB_TOKEN` permissions are broad; CodeQL flags any
workflow that never narrows them. Setting `permissions: contents: read` at the workflow root
makes every job default to read-only, which is least privilege.

Root cause (already diagnosed — do NOT re-investigate): `publish.yml` has no top-level
`permissions:` block, so the `test`, `lint`, `build`, and `smoke-test` jobs inherit the
repository/organization default token scopes. The two privileged jobs already declare their own
job-level blocks (`publish`: `id-token: write` + `contents: read` for PyPI OIDC; `release`:
`contents: write` for `gh release create`). A job-level `permissions:` block fully REPLACES the
top-level default for that job, so adding a restrictive top-level default cannot reduce the
privileges those two jobs need.

Output: one top-level `permissions:` block inserted between `concurrency:` and `jobs:`.
</objective>

<tasks>

<task type="auto" tdd="false">
  <name>Task 1: Add top-level least-privilege permissions block to publish.yml</name>
  <files>.github/workflows/publish.yml</files>
  <read_first>
    Confirm the file has no existing top-level `permissions:` key, that the `publish` job keeps
    `id-token: write` + `contents: read`, and that the `release` job keeps `contents: write`.
    These two job-level blocks override the new top-level default, so the publish pipeline is
    unaffected.
  </read_first>
  <action>
    Insert the following between the `concurrency:` block and `jobs:`:

    permissions:
      contents: read

    The four jobs with no `permissions:` block of their own (`test`, `lint`, `build`,
    `smoke-test`) only check out the repo and read files (build additionally uploads an artifact,
    which is not gated by GITHUB_TOKEN content scopes), so `contents: read` fully covers them.
  </action>
  <verify>
    <automated>python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/publish.yml')); assert d['permissions']=={'contents':'read'}, d.get('permissions'); assert d['jobs']['publish']['permissions']=={'id-token':'write','contents':'read'}; assert d['jobs']['release']['permissions']=={'contents':'write'}; print('publish.yml permissions OK')"</automated>
  </verify>
  <done>Top-level `permissions: contents: read` present; publish (OIDC) and release job-level blocks intact; YAML still parses.</done>
</task>

</tasks>

<success_criteria>
- Top-level `permissions: contents: read` block present in `.github/workflows/publish.yml`.
- `publish` job retains `id-token: write` + `contents: read`; `release` job retains `contents: write`.
- File remains valid YAML; no other workflow content changed.
- The 4 CodeQL "Workflow does not contain permissions" alerts on PR #57 are resolved on the next scan.
</success_criteria>

<output>
Create `.planning/quick/260928-mli-add-top-level-permissions-block-to-publi/260928-mli-SUMMARY.md` when done.
</output>
