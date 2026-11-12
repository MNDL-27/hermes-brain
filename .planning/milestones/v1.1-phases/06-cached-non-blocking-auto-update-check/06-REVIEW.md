---
status: issues
phase: 06-cached-non-blocking-auto-update-check
depth: standard
files_reviewed: 10
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
reviewed: 2026-09-25T07:55:00Z
scope: uncommitted Phase 04-06 working-tree changes (Distribution & Updates)
---

# Code Review — Phase 06 (Phase 04–06 scope)

Standard-depth review of the uncommitted Distribution & Updates working-tree
changes. All findings below were verified against the actual source by re-reading
the cited lines. No Critical findings: the secret-redaction boundary holds on
every error/log path, the detect+instruct (no-mutation) contract is intact, and
the cache write is genuinely atomic.

## Findings

### WR-01 — `refresh()` wall-clock "timeout" does not bound wall time; it discards late results

- **Severity:** Warning
- **File:** notion_brain/update_cache.py:130-145
- **Title:** Docstring overstates the `timeout` guarantee; guard runs after the network call returns.

**Detail:** The `refresh()` docstring says it "Honors `timeout` seconds via a
wall-clock guard." In reality the guard at line 143
(`if (time.monotonic() - started) > timeout`) only executes *after*
`update_mod.check_for_update(...)` has already returned, so it can never
pre-empt a slow call — it only decides whether to **keep or discard** the
result. The worker thread's actual wall-time ceiling is the 3.0 s `urlopen`
timeout inside `bootstrap._find_latest_tag()` (bootstrap.py:632), not
`refresh`'s `timeout` (default 2.5 s).

Two concrete consequences:

1. The non-blocking property is preserved, but by a *different* mechanism
   (the 3 s urlopen cap) than the one the docstring advertises. A maintainer
   who sets `timeout=10` expecting ~10 s of network budget would in practice
   still be hard-capped at 3 s.
2. Because the default `timeout` (2.5 s) is **shorter** than the underlying
   urlopen cap (3.0 s), a check that succeeds but takes 2.5–3.0 s is silently
   discarded: `refresh` logs a debug line and returns `None` without writing
   the cache, so the good result is thrown away and re-fetched next TTL cycle.

This is a behavior/documentation mismatch, not a correctness or security bug —
the result is benign (re-check on the next init after TTL) — but it will
mislead anyone reasoning about the timeout.

**Suggested fix:** Either (a) reword the docstring to say the guard "discards
results that took longer than `timeout`" and that the hard wall-time bound is
the caller's `urlopen` timeout, or (b) set `refresh`'s default `timeout` to
`>=` the underlying urlopen cap so a valid slow result is not dropped, or (c)
pass the timeout *into* `_find_latest_tag`'s `urlopen` so the guard and the
network cap are the same knob.

---

### IN-01 — `bootstrap._check_for_update()` is dead production code after CHK-04

- **Severity:** Info
- **File:** notion_brain/bootstrap.py:642-656
- **Title:** Legacy synchronous update checker no longer called from any production path.

**Detail:** CHK-04 rewired `health_report` to read from `update_cache.load_cache`
(bootstrap.py:670) instead of calling `_check_for_update()`. A repo-wide grep
confirms the function's only remaining references are tests
(`tests/test_bootstrap_schema.py:53,69,82`) and the monkeypatch tripwires in
`tests/test_update_cache.py`. No production code path invokes it. It is a
self-contained function, so it is safe to remove — but its three tests in
`test_bootstrap_schema.py` would need to be removed/redirected first. The new
`update.check_for_update` is the canonical replacement.

**Suggested fix:** Delete `_check_for_update()` and its three tests, or add a
`# dead: superseded by update.check_for_update (CHK-04)` marker if kept
intentionally for backward-compat.

---

### IN-02 — Network failure is written to disk as a 24 h "no update" negative cache

- **Severity:** Info
- **File:** notion_brain/update_cache.py:134-157
- **Title:** A one-time offline init suppresses re-checks for the full TTL.

**Detail:** `check_for_update()` does **not** raise on network failure — it
catches the exception internally and returns a dict with `latest=None,
drift=False, error="network: <ExcType>"` (update.py:151-155). `refresh()` then
treats that as a normal result and `save_cache()`s it with a fresh
`checked_at` (update_cache.py:150-151). So if the provider initializes while
offline, `is_expired()` stays `False` for the full 24 h TTL even after
connectivity returns, and `health_report` shows `latest: unknown` throughout
that window. This is acceptable given the TTL (the next init after 24 h
re-checks), but it is a behavioral consequence worth documenting so it is not
later "fixed" into a hot-path network call.

**Suggested fix:** Document in the `refresh()` docstring that a failed check
is intentionally cached (negative cache) for the TTL, or skip the `save_cache`
when `result.get("error")` is set so a failure does not suppress the next
check.

---

### IN-03 — `detect_install_mode` uv heuristic misses uv-created `.venv` installs

- **Severity:** Info
- **File:** notion_brain/update.py:99-106
- **Title:** uv-managed virtualenvs are misclassified as `pip_venv`.

**Detail:** The uv branch keys on `"/uv/" in loc or "/.cache/uv/" in loc`. A
venv created with `uv venv` has a `Location` like
`/.venv/lib/python3.12/site-packages`, which contains neither `/uv/` nor
`/.cache/uv/`, so it falls through to `pip_venv`. The emitted upgrade command
then uses `pip install --upgrade …` instead of `uv pip install --upgrade …`.
Both commands work inside the venv, so the impact is cosmetic (wrong tooling
hint), not a failure. Note the `pip_user` check (line 101) correctly precedes
the site-packages check, so `--user` installs are still classified right.

**Suggested fix:** Detect uv by checking for a `.venv` marker (e.g. a
`pyvenv.cfg` with `uv` in it, or a `VIRTUAL_ENV` pointing at a uv-created
env) if an accurate `uv` hint matters; otherwise leave as-is and note the
limitation.

---

### IN-04 — `save_cache` except-branch performs a redundant double `os.close(fd)`

- **Severity:** Info
- **File:** notion_brain/update_cache.py:74-85
- **Title:** `os.close(fd)` in the `except BaseException` handler double-closes an fd the `with` block already released.

**Detail:** `os.fdopen(fd, "w")` transfers ownership of `fd` to the returned
file object. When an exception is raised *inside* the `with` body (e.g.
`os.fsync`), the `with`'s `__exit__` closes `fh` — and therefore the fd —
*before* control reaches the `except BaseException` block. The subsequent
`os.close(fd)` then raises `EBADF`, which is swallowed by the inner
`except OSError: pass`. The handler is only *meaningful* in the case where
`os.fdopen` itself fails (fd still open) — in the common in-body-exception
case it is a harmless no-op error. Correct today, but the comment
("os.fdopen took ownership of fd; close handles cleanup on raise") describes
a cleanup that the `with` already performed.

**Suggested fix:** Track whether `fdopen` succeeded and only call `os.close(fd)`
in the fdopen-failed path (e.g. wrap `fh = os.fdopen(fd, "w")` in its own
try/except), or simply delete the inner `os.close(fd)` and rely on the `with`
plus the process-level fd release. Behavior is unchanged; this is clarity.

---

## Verified clean (no finding)

- **Secret redaction boundary.** `update.check_for_update` stores only
  `type(exc).__name__` in the `error` field (update.py:154) — never the message.
  `refresh` redacts `str(exc)` via `S.redact_secrets` before logging
  (update_cache.py:139). `format_human`/`format_json` only ever print the
  already-sanitized `error` field. No raw token can reach a log or stdout.
- **No-mutation contract (UPD-05).** `update.py` invokes only `pip show`
  (read-only, update.py:74-79). `check_for_update` performs no install/pull/
  checkout. `_cmd_update` (`__main__.py:195-211`) is a pure formatter over
  `check_for_update`. Grep confirms no dangling references to the removed
  `_git_pull_and_install` / `_checkout_tag_and_install` / `_reinstall` helpers.
- **Atomic cache write (CHK-03).** `save_cache` writes to a `.tmp` sidecar at
  mode `0o600` via `os.open`, fsyncs, then `os.replace` onto the target —
  crash-safe and mode-correct. Corrupt/empty/missing/non-dict cache all
  degrade to `None` in `load_cache` without raising or networking.
- **Non-blocking init (CHK-01/CHK-02).** `provider.initialize` loads the cache
  synchronously (pure file I/O) *before* `bootstrap.ensure_brain`, and only
  *enqueues* `update_cache.refresh` on the existing sync worker when the cache
  is expired (provider.py:103-109). No network on the init path.
- **Thread-safety of dispatch.** `_dispatch_update_refresh` (provider.py:242-252)
  takes `self._sync_lock` around the queue put and lazy thread start, mirroring
  `_trigger_auto_disk_sync`; the worker loop redacts every exception
  (provider.py:194-197).
- **`publish.yml` GitHub-injection surface.** `github.ref_name` is
  interpolated at lines 68, 135, 136. Git refname rules forbid `"` `\` `` ` ``
  `$` `;` newline and `)` in tag names, so neither the single-quoted `<<'PY'`
  Python heredoc (line 68) nor the double-quoted `gh release` shell command
  (135-136) can be broken out of. Line 149 uses the `GITHUB_REF_NAME` env var
  (no expression expansion). Ancestry guard (`merge-base --is-ancestor`) and
  the inline `tomllib` version-match guard (61-77) both present. OIDC
  scoping (`id-token: write` only on `publish`, `contents: write` only on
  `release`) is correctly minimal. No injection finding.
