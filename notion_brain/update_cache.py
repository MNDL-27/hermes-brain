"""Update-check TTL cache for the NotionBrainProvider.

Public surface: `load_cache`, `save_cache`, `is_expired`, `refresh`.

Satisfies CHK-01..CHK-05:
- CHK-01: load_cache is sync file I/O, no network.
- CHK-02: caller decides when to enqueue `refresh` on the sync worker.
- CHK-03: save_cache writes atomically (tempfile + os.replace, mode 0o600);
  load_cache silently degrades on missing or corrupt cache.
- CHK-04: bootstrap.health_report() reads from this cache (no network).
- CHK-05: refresh redacts secrets from all error/log paths and never raises;
  the GitHub API call runs unauthenticated with a short timeout enforced by
  the caller (bootstrap._find_latest_tag uses a 3s urlopen cap). refresh's
  `timeout` (default 3.0s) is only a wall-clock discard threshold checked
  after the call returns -- it never bounds wall time.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CACHE_FILENAME = ".update_cache.json"
DEFAULT_TTL_SECONDS = 86400  # 24h


def _cache_path(hermes_home: str | Path) -> Path:
    return Path(hermes_home) / CACHE_FILENAME


def load_cache(hermes_home: str | Path) -> dict[str, Any] | None:
    """Synchronously read the cached update payload. Never raises, never makes a network call.

    Returns None if the file is missing, empty, or unparseable.
    """
    path = _cache_path(hermes_home)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.debug("update_cache: cannot read %s: %s", path, exc)
        return None
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Corrupt or interrupted write — degrade silently (CHK-03).
        logger.warning("update_cache: corrupt cache at %s, ignoring (%s)", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    return data


def save_cache(hermes_home: str | Path, payload: dict[str, Any]) -> Path:
    """Atomically write the cache payload. Returns the final path."""
    path = _cache_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        # Write to temp file with mode 0o600 (CHK-03).
        fd = os.open(
            str(tmp),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            0o600,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, sort_keys=True, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
        except BaseException:
            # os.fdopen took ownership of fd; close handles cleanup on raise.
            try:
                os.close(fd)
            except OSError:
                pass
            raise
        os.replace(tmp, path)
    except OSError as exc:
        # Leave any pre-existing cache file untouched (CHK-03).
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        logger.warning(
            "update_cache: failed to write %s: %s",
            path,
            _safe(exc),
        )
        raise
    return path


def is_expired(
    cache: dict[str, Any] | None,
    *,
    now: float | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> bool:
    """True when the cache is missing, has no `checked_at`, or is older than TTL."""
    if not cache:
        return True
    checked_at = cache.get("checked_at")
    if not isinstance(checked_at, (int, float)):
        return True
    current = now if now is not None else time.time()
    return (current - float(checked_at)) > ttl_seconds


def refresh(
    hermes_home: str | Path,
    *,
    repo_dir: Path | None = None,
    timeout: float = 3.0,
) -> dict[str, Any] | None:
    """Background-refresh the cache. Never raises. Returns the new payload or None.

    ``timeout`` is a wall-clock *discard* threshold, not a hard cap: the guard
    runs after ``check_for_update`` returns and drops the result if the elapsed
    time exceeded ``timeout`` (returns ``None``, writes no cache, so the next
    TTL cycle re-fetches). It cannot pre-empt a slow call. The hard wall-time
    bound is the caller's ``urlopen`` timeout -- 3.0 s in
    ``bootstrap._find_latest_tag`` (CHK-05). Errors are logged with secret
    redaction and swallowed so the worker thread never sees an exception.
    """
    from . import schema as S
    from . import update as update_mod

    started = time.monotonic()
    try:
        result = update_mod.check_for_update(repo_dir=repo_dir)
    except Exception as exc:  # noqa: BLE001 — must not escape worker
        logger.warning("update_cache: refresh failed: %s", S.redact_secrets(str(exc)))
        return None

    if (time.monotonic() - started) > timeout:
        logger.debug("update_cache: refresh exceeded %.2fs budget", timeout)
        return None

    if not isinstance(result, dict):
        return None

    payload = dict(result)
    payload["checked_at"] = int(time.time())
    try:
        save_cache(hermes_home, payload)
    except OSError:
        # save_cache already logs; nothing to do here.
        return None
    return payload


def _safe(exc: BaseException) -> str:
    """Format an exception message without leaking secrets."""
    from . import schema as S

    return S.redact_secrets(str(exc))
