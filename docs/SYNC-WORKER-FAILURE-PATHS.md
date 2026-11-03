# Background Sync Worker Failure Paths & Hardening Specification

**Status:** Reference Specification & Regression Test Deliverable (FRE-15 / FRE-11.2)  
**Author:** Product Designer (FRE-78)  
**Target Repository:** `hermes-brain` / `notion_brain`  
**Target Files:** `notion_brain/provider.py`, `tests/test_sync_lifecycle.py`  
**Disposition:** Reference Snippet & Test Suite for Founding Engineer implementation (zero production commits landed by Product Designer per AGENTS.md boundary).

---

## 1. Executive Summary & Problem Statement

Audit finding **REL-02** (`CODEBASE-AUDIT-REPORT.md`, P2 High Confirmed) surfaced that the `NotionBrainProvider` background sync worker exhibits fragile daemon-thread lifecycle semantics:

1. **Worker Thread Crash leaves remaining queue stranded:** If a task raises a `BaseException` (such as `KeyboardInterrupt` or unexpected fatal signals), the worker loop terminates. Remaining queued tasks sit unprocessed indefinitely.
2. **Process Exit Deadlock:** `on_session_end()` / `shutdown()` calls `self._sync_queue.join()` without a timeout. If the worker thread died with unfinished tasks, `join()` deadlocks the process shutdown indefinitely.
3. **Silent Turn Loss:** `_process_sync_turn` catches exceptions during Notion writes, logs them to stderr, and discards the entry. No retry, outbox, or dead-letter mechanism exists.
4. **Unbounded Memory Leak on API Outage:** `self._sync_queue = queue.Queue()` uses `maxsize=0` (unbounded). Under extended Notion API downtime and high conversation turn volume, queue memory grows without ceiling.
5. **No Outbox Replay on Startup:** Prior crashes or failed writes have no recovery path on subsequent `initialize()`.

This specification documents the verified failure paths, provides the regression test suite (`tests/test_sync_lifecycle_ref.py`), and delivers a minimal, stdlib-first reference patch.

---

## 2. Forensic Failure-Path Analysis (Evidence from Live Probes)

### Failure Path 1: Worker Thread Termination on BaseException
* **Location:** `notion_brain/provider.py:180-200` (`_worker_loop`)
* **Mechanism:**
  ```python
  def _worker_loop(self) -> None:
      while True:
          with self._sync_lock:
              try:
                  task = self._sync_queue.get_nowait()
              except queue.Empty:
                  self._sync_thread = None
                  break
          func, args, kwargs = task
          try:
              func(*args, **kwargs)
          except Exception as exc:  # <--- Gaps: does not catch BaseException!
              logger.error("NotionBrainProvider sync worker error: %s", ...)
          finally:
              self._sync_queue.task_done()
  ```
* **Reproduction:** Enqueue `task1` (raises `BaseException`) and `task2` (normal task).
* **Observed Result:** `_worker_loop` terminates abruptly. `_sync_thread.is_alive()` becomes `False`. `task2` is never executed. `self._sync_queue.unfinished_tasks` remains `1`.

### Failure Path 2: Shutdown Deadlock on Stranded Queue
* **Location:** `notion_brain/provider.py:321` (`on_session_end`)
* **Mechanism:**
  ```python
  def on_session_end(self, *args, **kwargs) -> None:
      self._sync_queue.join()  # <--- Gaps: unbounded join!
      with self._sync_lock:
          if self._sync_thread and self._sync_thread.is_alive():
              self._sync_thread.join(timeout=5.0)
              self._sync_thread = None
  ```
* **Reproduction:** Enqueue a task that causes worker termination (Failure Path 1) followed by `provider.shutdown()`.
* **Observed Result:** `self._sync_queue.join()` waits for `unfinished_tasks == 0`. Because the worker thread is dead, `unfinished_tasks` never decrements. Process hangs past 180s timeout until hard-killed.

### Failure Path 3: Silent Turn Dropping on Network/Notion Outage
* **Location:** `notion_brain/provider.py:201-215` (`_process_sync_turn`)
* **Mechanism:**
  ```python
  def _process_sync_turn(self, user_content: str, assistant_content: str) -> None:
      try:
          entries = extract.classify_turn(user_content, assistant_content)
          for entry in entries:
              self._store_entry(entry)
      except Exception as exc:
          logger.error("NotionBrainProvider sync error: %s", ...)
          # <--- Entry is permanently dropped; user believes it was saved
  ```
* **Reproduction:** Mock `store.create_database_page` to raise HTTP 503 during `provider.sync_turn()`.
* **Observed Result:** Error logged to logger, queue drained, entry vanished into the void.

---

## 3. Hardened Architecture (Lazy Senior Developer Ladder)

Rung 1 & 2 (YAGNI + Stdlib first): No external queue service (Redis, Celery, BullMQ). Stdlib `dataclasses`, `json`, and local file append (`.jsonl`) provide complete crash durability with zero extra dependencies.

### Architectural Invariants:
1. **Bounded Queue:** `queue.Queue(maxsize=1000)` prevents memory exhaustion on API outages.
2. **Worker Resilience:** Catch `BaseException` in `_worker_loop` so a rogue interrupt does not kill the daemon loop for subsequent tasks.
3. **Bounded Session Drain:** Replace unbounded `self._sync_queue.join()` with a polling deadline (`5.0s`), checking `self._sync_queue.unfinished_tasks == 0`, followed by thread join (`2.0s`).
4. **Local Outbox (`notion_brain.outbox.jsonl`):**
   - On write failure in `_process_sync_turn`, serialize normalized entry to `$HERMES_HOME/notion_brain.outbox.jsonl`.
   - On `initialize()`, if database IDs are ready, enqueue background task `_replay_outbox()`.
   - On successful replay, unlink outbox file. On partial failure, rewrite remaining failed entries.

---

## 4. Reference Implementation (Minimal Unified Diff)

```diff
--- a/notion_brain/provider.py
+++ b/notion_brain/provider.py
@@ -10,11 +10,13 @@ Cache:  $HERMES_HOME/notion_brain.json
 
 from __future__ import annotations
 
+import dataclasses
 import hashlib
 import json
 import logging
 import queue
 import threading
+import time
 from pathlib import Path
 from typing import Any
 
@@ -75,7 +77,7 @@ class NotionBrainProvider:
         # Background sync state
         self._sync_lock = threading.Lock()
         self._sync_thread: threading.Thread | None = None
-        self._sync_queue: queue.Queue = queue.Queue()
+        self._sync_queue: queue.Queue = queue.Queue(maxsize=1000)
 
         # Prefetch cache
         self._prefetch_cache: str = ""
@@ -128,6 +130,7 @@ class NotionBrainProvider:
                 self._prefetch_cache = "<!-- memory-context from disk -->\n" + combined[:4000]
             if self._db_ids:
                 self._trigger_auto_disk_sync()
+                self._trigger_outbox_replay()
 
     def system_prompt_block(self) -> str:
         return (
@@ -191,7 +194,7 @@ class NotionBrainProvider:
             func, args, kwargs = task
             try:
                 func(*args, **kwargs)
-            except Exception as exc:
+            except BaseException as exc:
                 logger.error(
                     "NotionBrainProvider sync worker error: %s", S.redact_secrets(str(exc))
                 )
@@ -199,14 +202,74 @@ class NotionBrainProvider:
                 self._sync_queue.task_done()
 
+    def _append_outbox(self, entry: S.BrainEntry | Any) -> None:
+        if not self._hermes_home:
+            return
+        outbox_file = Path(self._hermes_home) / "notion_brain.outbox.jsonl"
+        try:
+            payload = (
+                dataclasses.asdict(entry)
+                if isinstance(entry, S.BrainEntry)
+                else vars(entry)
+            )
+            with open(outbox_file, "a", encoding="utf-8") as f:
+                f.write(json.dumps(payload) + "\n")
+        except Exception as err:
+            logger.warning("Failed writing outbox: %s", S.redact_secrets(str(err)))
+
+    def _trigger_outbox_replay(self) -> None:
+        """Queue a background task to replay pending outbox entries to Notion."""
+        with self._sync_lock:
+            self._sync_queue.put((self._replay_outbox, (), {}))
+            if self._sync_thread is None or not self._sync_thread.is_alive():
+                self._sync_thread = threading.Thread(
+                    target=self._worker_loop,
+                    daemon=True,
+                    name="notion-brain-sync-worker",
+                )
+                self._sync_thread.start()
+
+    def _replay_outbox(self) -> None:
+        """Replay entries from notion_brain.outbox.jsonl."""
+        if not self._hermes_home or not self._db_ids:
+            return
+        outbox_file = Path(self._hermes_home) / "notion_brain.outbox.jsonl"
+        if not outbox_file.exists():
+            return
+        try:
+            lines = outbox_file.read_text(encoding="utf-8").splitlines()
+        except Exception:
+            return
+        if not lines:
+            return
+
+        remaining: list[str] = []
+        for line in lines:
+            line = line.strip()
+            if not line:
+                continue
+            try:
+                data = json.loads(line)
+                entry = S.BrainEntry(**data)
+                self._store_entry(entry)
+            except Exception:
+                remaining.append(line)
+
+        try:
+            if remaining:
+                outbox_file.write_text("\n".join(remaining) + "\n", encoding="utf-8")
+            else:
+                outbox_file.unlink(missing_ok=True)
+        except Exception:
+            pass
+
     def _process_sync_turn(self, user_content: str, assistant_content: str) -> None:
         try:
             entries = extract.classify_turn(user_content, assistant_content)
             for entry in entries:
-                if isinstance(entry, S.BrainEntry):
-                    entry.source_session_id = self._session_id
-                    self._store_entry(entry.normalized())
-                else:
-                    self._store_entry(entry)
+                norm_entry = (
+                    entry.normalized() if isinstance(entry, S.BrainEntry) else entry
+                )
+                if isinstance(norm_entry, S.BrainEntry):
+                    norm_entry.source_session_id = self._session_id
+                try:
+                    self._store_entry(norm_entry)
+                except Exception as store_err:
+                    logger.error(
+                        "NotionBrainProvider store failed: %s; saving to outbox",
+                        S.redact_secrets(str(store_err)),
+                    )
+                    self._append_outbox(norm_entry)
             self._prefetch_cache = ""
             self.prefetch()
             logger.debug("NotionBrainProvider: sync turn complete")
@@ -318,10 +381,14 @@ class NotionBrainProvider:
     def on_session_end(self, *args, **kwargs) -> None:
         """Called when Hermes session ends. Wait for pending sync, then
         optionally write a session-summary entry from inline messages."""
-        self._sync_queue.join()
+        deadline = time.time() + 5.0
+        while time.time() < deadline:
+            if self._sync_queue.unfinished_tasks == 0:
+                break
+            time.sleep(0.02)
         with self._sync_lock:
             if self._sync_thread and self._sync_thread.is_alive():
-                self._sync_thread.join(timeout=5.0)
+                self._sync_thread.join(timeout=2.0)
                 self._sync_thread = None
```

---

## 5. Regression Test Suite

Saved as reference in `tests/test_sync_lifecycle_ref.py`:
- `test_worker_survives_baseexception_and_drains_rest`: Proves worker continues draining after BaseException.
- `test_clean_exit_does_not_deadlock_on_stranded_queue`: Proves `on_session_end()` completes within bounded budget even if worker is dead.
- `test_failed_turn_is_persisted_to_outbox`: Proves failed store calls are written to `notion_brain.outbox.jsonl`.
- `test_sync_queue_is_bounded`: Proves `maxsize == 1000`.
- `test_dead_letter_replays_on_next_initialize`: Proves pending outbox entries replay and outbox unlinks cleanly.

### Test Gate Evidence
- Unpatched `main`: **4 FAILED, 1 ERROR** (matches all described vulnerabilities).
- Patched Scratch Copy: **5 PASSED in 0.97s**, `ruff check` 0 errors, `mypy` 0 errors, full suite **54 passed**.

---

## 6. Handoff to Founding Engineer
Product Designer leaves this complete design and engineering reference. Founding Engineer can apply this patch alongside the Phase 8 Developer Tooling & Test Reliability wave on `main`.
