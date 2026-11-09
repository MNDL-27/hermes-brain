"""NotionBrainProvider — persistent long-term memory via a Notion workspace brain.

7 Notion databases (Memory, Tasks, Projects, Content, Research, Career, Entities)
are organized under a "Hermes Brain" parent page. Background sync threads classify
conversation turns using heuristics and write entries to the correct database.

Auth:   NOTION_API_KEY env var
Cache:  $HERMES_HOME/notion_brain.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import queue
import threading
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from . import bootstrap, brain_cache, extract, helpers, injection, store, update_cache
from . import catalog as semantic_catalog
from . import schema as S
from .helpers import _merge_disk_only, _safe_select_value
from .schemas import ALL_TOOL_SCHEMAS

logger = logging.getLogger(__name__)


def _message_content_text(content: Any) -> str:
    """Extract plain text from a message ``content`` field.

    Hermes/OpenAI tool-call messages encode ``content`` as a list of block
    dicts (``{"type": "text", "text": {"content": ...}}``); plain chat
    messages use a plain string. Returns ``""`` for ``None``/missing content
    so callers can safely pass the result to ``redact_secrets``.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, dict):
                    texts.append(t.get("content", ""))
            elif isinstance(block.get("content"), str):
                texts.append(block["content"])
        return "\n".join(texts)
    return str(content) if content else ""


def _coerce_str_list(value: Any) -> list[str]:
    """Coerce LLM tool args to list[str] — LLMs sometimes send a bare string."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v is not None and str(v).strip()]
    return [str(value)]


def _redact_payload(value: Any) -> Any:
    """Recursively redact secrets from tool-result payloads before JSON serialization."""
    if isinstance(value, str):
        return S.redact_secrets(value)
    if isinstance(value, dict):
        return {k: _redact_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_payload(item) for item in value)
    return value


class NotionBrainProvider:
    """Notion-backed long-term memory for Hermes."""

    def __init__(self) -> None:
        # Set by initialize()
        self._session_id: str = ""
        self._hermes_home: str = ""
        self._db_ids: dict[str, str] = {}
        self._parent_page_id: str = ""

        # Background sync state
        self._sync_lock = threading.Lock()
        self._sync_thread: threading.Thread | None = None
        self._sync_queue: queue.Queue = queue.Queue()

        # Prefetch cache
        self._prefetch_cache: str = ""
        self._prefetch_lock = threading.Lock()

        # Update-check cache (CHK-01..CHK-05); populated in initialize()
        self._update_cache: dict[str, Any] | None = None

    def _catalog_path(self) -> Path:
        """Keep catalog reads and writes in the initialized provider's home."""
        if self._hermes_home:
            return Path(self._hermes_home) / "brain_catalog.json"
        return semantic_catalog.catalog_path()

    # Core lifecycle

    @property
    def name(self) -> str:
        return "notion_brain"

    def is_available(self) -> bool:
        return bool(store.get_api_key())

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._hermes_home = str(kwargs.get("hermes_home", ""))

        if not self._hermes_home:
            logger.warning("NotionBrainProvider: no hermes_home — limited functionality")

        # CHK-01: load the update-check cache synchronously before any network work.
        if self._hermes_home:
            self._update_cache = update_cache.load_cache(self._hermes_home)
            # CHK-02: stale or missing → enqueue a background refresh on the
            # existing sync worker; do NOT block init on the network.
            if update_cache.is_expired(self._update_cache):
                self._dispatch_update_refresh()

        # Bootstrap workspace (idempotent)
        try:
            cache = bootstrap.ensure_brain(self._hermes_home)
            self._parent_page_id = cache.get("parent_page_id", "")
            for key in S.get_all_databases():
                self._db_ids[key] = cache.get(f"db_{key}", "")
            logger.info("Notion brain initialized: %d databases", len(self._db_ids))
        except Exception as exc:
            logger.error("NotionBrainProvider bootstrap failed: %s", S.redact_secrets(str(exc)))

        # Pre-load memory files from disk as fallback context and trigger auto-sync
        if self._hermes_home:
            mem_text = bootstrap.read_memory_from_disk(self._hermes_home)
            user_text = bootstrap.read_user_from_disk(self._hermes_home)
            combined = "\n".join(filter(None, [mem_text, user_text])).strip()
            if combined:
                # Bound only the injected view; the worker receives the full snapshot.
                self._prefetch_cache = injection.render_disk_context(
                    S.redact_secrets(mem_text), S.redact_secrets(user_text)
                )
            if self._db_ids:
                # Pass the snapshot read for this initialization to the worker.
                # A delayed worker must not re-read through module globals after
                # another provider (or test) has installed different state.
                self._trigger_auto_disk_sync(mem_text, user_text)

    def system_prompt_block(self) -> str:
        return (
            "# Notion Brain\n"
            "Your long-term memory lives in a Notion workspace called "
            '"Hermes Brain" with 7 databases: '
            "Memory (general notes + preferences), Tasks, Projects, Content "
            "(social media drafts), Research, Career, and Entities (people, "
            "companies, tools, topics). "
            "Use notion_brain_search to recall context, notion_brain_remember "
            "to save important facts, notion_brain_task for task management, "
            "notion_brain_content for social content ideas, and "
            "notion_brain_research for research findings. "
            "Memory is automatically synced after each turn."
        )

    def prefetch(self, **kwargs) -> str:
        with self._prefetch_lock:
            if self._prefetch_cache:
                return self._prefetch_cache

            # Query memory database for recent entries
            if not self._db_ids.get("memory"):
                return ""

            try:
                entries = self._prefetch_entries()
                if not entries:
                    return ""

                contradictions = self._contradictions(entries)

                # Cold reads hydrate before caching. Rendering a cache hit is offline,
                # including rows whose source body was empty or unavailable.
                tagged: list[tuple[str, str]] = []
                for entry in entries[:10]:
                    title = entry.get("title", "Untitled")
                    props = entry.get("properties", {}) or {}
                    content = props.get("Content") or props.get("Summary") or ""
                    kind = str(props.get("Kind") or "note")
                    safe_title = S.redact_secrets(str(title))
                    safe_content = S.redact_secrets(str(content)[:200])
                    provenance = self._provenance(entry)
                    tag = f"[fact:{provenance['truth']}:{provenance['source_agent']}]"
                    tagged.append((kind, f"- [{kind}] {safe_title}: {safe_content} {tag}"))

                if contradictions:
                    conflict_lines = [("warning", "CONTRADICTION: active memories disagree for the same subject key.")]
                    for conflict in contradictions:
                        for item in conflict["entries"]:
                            snippet = injection.trim_tokens(item["value"][:200], 24)
                            conflict_lines.append((
                                "warning",
                                f"- {item['subject_key'][:80]}: {snippet} "
                                f"(timestamp: {item['timestamp'][:40]}; certification: {item['certification'][:20]})",
                            ))
                    # Keep the warning and short conflicting values before other pinned facts.
                    tagged = conflict_lines + tagged
                self._prefetch_cache = S.redact_secrets(injection.render_injection(tagged))
                return self._prefetch_cache
            except Exception as exc:
                logger.warning(
                    "NotionBrainProvider prefetch failed: %s", S.redact_secrets(str(exc))
                )
                return ""

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
            except Exception as exc:
                logger.error(
                    "NotionBrainProvider sync worker error: %s", S.redact_secrets(str(exc))
                )
            finally:
                self._sync_queue.task_done()

    def _process_sync_turn(self, user_content: str, assistant_content: str) -> None:
        try:
            entries = extract.classify_turn(user_content, assistant_content)
            for entry in entries:
                if isinstance(entry, S.BrainEntry):
                    entry.source_session_id = self._session_id
                    self._store_entry(entry.normalized())
                else:
                    self._store_entry(entry)
            self._prefetch_cache = ""
            self.prefetch()
            logger.debug("NotionBrainProvider: sync turn complete")
        except Exception as exc:
            logger.error("NotionBrainProvider sync error: %s", S.redact_secrets(str(exc)))

    def sync_turn(self, *args, **kwargs) -> None:
        """Background sync after a turn. Called by Hermes after each response."""
        user_content = args[0] if len(args) > 0 else kwargs.get("user_content", "")
        assistant_content = args[1] if len(args) > 1 else kwargs.get("assistant_content", "")
        with self._sync_lock:
            self._sync_queue.put((self._process_sync_turn, (user_content, assistant_content), {}))
            if self._sync_thread is None or not self._sync_thread.is_alive():
                self._sync_thread = threading.Thread(
                    target=self._worker_loop,
                    daemon=True,
                    name="notion-brain-sync-worker",
                )
                self._sync_thread.start()

    def _trigger_auto_disk_sync(self, mem_text: str = "", user_text: str = "") -> None:
        """Queue a background task to sync local disk memory files to Notion."""
        with self._sync_lock:
            self._sync_queue.put(
                (self._sync_disk_memories, (mem_text, user_text), {})
            )
            if self._sync_thread is None or not self._sync_thread.is_alive():
                self._sync_thread = threading.Thread(
                    target=self._worker_loop,
                    daemon=True,
                    name="notion-brain-sync-worker",
                )
                self._sync_thread.start()

    def _dispatch_update_refresh(self) -> None:
        """Queue a background update-check refresh on the existing sync worker (CHK-02)."""
        with self._sync_lock:
            self._sync_queue.put((update_cache.refresh, (self._hermes_home,), {}))
            if self._sync_thread is None or not self._sync_thread.is_alive():
                self._sync_thread = threading.Thread(
                    target=self._worker_loop,
                    daemon=True,
                    name="notion-brain-sync-worker",
                )
                self._sync_thread.start()

    def _sync_disk_memories(self, mem_text: str | None = None, user_text: str | None = None) -> None:
        """Read local disk memories and persist them to Notion if modified."""
        if not self._hermes_home or not self._db_ids:
            return

        if mem_text is None:
            mem_text = bootstrap.read_memory_from_disk(self._hermes_home)
        if user_text is None:
            user_text = bootstrap.read_user_from_disk(self._hermes_home)
        combined = "\n".join(filter(None, [mem_text, user_text])).strip()
        if not combined:
            return

        content_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]
        cache_path = Path(self._hermes_home) / S.CACHE_FILE
        cached = bootstrap._load_cache(cache_path)
        if cached.get("disk_sync_hash") == content_hash:
            logger.debug("Disk memories unchanged (hash=%s); skipping auto-sync", content_hash)
            return

        logger.info("Auto-syncing local memory files to Notion (hash=%s)...", content_hash)
        entries: list[S.BrainEntry] = []
        if mem_text:
            for item in helpers.parse_disk_memory_text(mem_text, default_domain="memory"):
                entries.append(
                    S.BrainEntry(
                        domain=item["domain"],
                        title=item["title"],
                        content=item["content"],
                        kind=item.get("kind", "note"),
                        tags=item.get("tags", []),
                        source_session_id=self._session_id or "disk-sync",
                    ).normalized()
                )
        if user_text:
            for item in helpers.parse_disk_memory_text(user_text, default_domain="entities"):
                entries.append(
                    S.BrainEntry(
                        domain=item["domain"],
                        title=item["title"],
                        content=item["content"],
                        kind=item.get("kind", "preference"),
                        tags=item.get("tags", []),
                        source_session_id=self._session_id or "disk-sync",
                    ).normalized()
                )

        synced = 0
        for entry in entries:
            try:
                self._store_entry(entry)
                synced += 1
            except Exception as exc:
                logger.warning(
                    "Failed to auto-sync entry '%s': %s",
                    entry.title[:40],
                    S.redact_secrets(str(exc)),
                )

        cached["disk_sync_hash"] = content_hash
        bootstrap._save_cache(cache_path, cached)
        logger.info("Auto-synced %d disk memories to Notion", synced)

        with self._prefetch_lock:
            self._prefetch_cache = ""

    def on_session_end(self, *args, **kwargs) -> None:
        """Called when Hermes session ends. Wait for pending sync, then
        optionally write a session-summary entry from inline messages."""
        self._sync_queue.join()
        with self._sync_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=5.0)
                self._sync_thread = None

        messages = args[0] if args else kwargs.get("messages")
        if messages:
            try:
                self._write_session_summary(messages)
            except Exception as exc:
                logger.error(
                    "NotionBrainProvider session summary failed: %s",
                    S.redact_secrets(str(exc)),
                )

    def _write_session_summary(self, messages: list[dict[str, Any]]) -> None:
        """Write conversation messages as a redacted session-summary entry."""
        parts = [
            f"{msg.get('role', '')}: {S.redact_secrets(_message_content_text(msg.get('content')))}"
            for msg in messages
        ]
        text = "\n".join(parts)
        entry = S.BrainEntry(
            domain="memory",
            title="Session summary",
            content=text,
            kind="note",
            source_session_id=self._session_id,
        ).normalized()
        self._store_entry(entry)

    def shutdown(self) -> None:
        """Clean shutdown."""
        self.on_session_end()

    def on_memory_write(self, text: str, **kwargs) -> None:
        """Called when Hermes writes memory. Classify and store."""
        if not text.strip():
            return

        # Classify using heuristics
        classification = extract.classify_text(text)
        domain = classification.get("domain", "memory")
        kind = classification.get("kind", "note")

        # Scrub raw text BEFORE classification and storage so secrets never
        # travel through classification helpers, caches, or the outbox path.
        safe_text = S.redact_secrets(text)
        safe_title = S.clean_title(classification.get("title", "Untitled"))

        entry = S.BrainEntry(
            domain=domain,
            title=safe_title,
            content=safe_text,
            kind=kind,
            source_session_id=self._session_id,
        ).normalized()

        self._store_entry(entry)

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        import copy

        domains = list(S.get_all_domains().keys())
        dbs = list(S.get_all_databases().keys())
        schemas = copy.deepcopy(ALL_TOOL_SCHEMAS)
        for s in schemas:
            if s.get("name") == "notion_brain_remember":
                s["parameters"]["properties"]["domain"]["description"] = (
                    f"Which domain: {'|'.join(domains)}."
                )
            elif s.get("name") == "notion_brain_search":
                s["parameters"]["properties"]["database"]["description"] = (
                    f"Optional database filter: {'|'.join(dbs)}. Omit to search all."
                )
        return schemas

    def handle_tool_call(
        self, tool_name: str, arguments: dict[str, Any], *, user_confirmed: bool = False
    ) -> str:
        """Run a tool; trusted callers may confirm this exact certification call."""
        handlers = {
            "notion_brain_search": self._tool_search,
            "notion_brain_check_answerable": self._tool_check_answerable,
            "notion_brain_search_terms": self._tool_search_terms,
            "notion_brain_remember": self._tool_remember,
            "notion_brain_certify": self._tool_certify,
            "notion_brain_task": self._tool_task,
            "notion_brain_content": self._tool_content,
            "notion_brain_research": self._tool_research,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return json.dumps(
                {
                    "result": S.redact_secrets(f"Unknown tool: {tool_name}"),
                    "error": True,
                }
            )

        try:
            result: str | tuple[str, dict[str, Any]]
            if tool_name == "notion_brain_certify":
                result = self._tool_certify(arguments, user_confirmed=user_confirmed)
            else:
                result = handler(arguments)
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
                text_result, extra = result
                payload: dict[str, Any] = {
                    "result": text_result,
                    "error": False,
                    **extra,
                }
            else:
                payload = {"result": result, "error": False}
            # ponytail: recursive redaction covers strings inside result, extra, and nested lists/dicts.
            return json.dumps(_redact_payload(payload))
        except Exception as exc:
            logger.error(
                "Tool call %s failed: %s",
                S.redact_secrets(str(tool_name)),
                S.redact_secrets(str(exc)),
            )
            return json.dumps(
                {
                    "result": S.redact_secrets(f"Tool error: {exc}"),
                    "error": True,
                }
            )

    def _store_entry(self, entry: S.BrainEntry) -> None:
        """Store a normalized entry in the appropriate database.

        Raises ``RuntimeError`` when the destination database is missing
        so that callers surface a real error instead of silently dropping
        the write.
        """
        database_key = S.database_for_domain(entry.domain)
        database_id = self._db_ids.get(database_key)

        if not database_id:
            raise RuntimeError(
                f"No database available for domain '{entry.domain}' "
                f"(via '{database_key}'). Run `python -m notion_brain reset` to bootstrap."
            )

        entry = self._resolve_memory_subject(entry, database_key)
        self._write_entry_raw(database_id, entry)

    def _resolve_memory_subject(
        self, entry: S.BrainEntry, database_key: str
    ) -> S.BrainEntry:
        """Resolve the Subject Key for Memory writes that lack an explicit one.

        Background ingestion and explicit ``remember`` share this boundary so
        the same deterministic key lands on the Notion property and the SQLite
        mirror. A nonblank redacted explicit override wins; unrecognized content
        stays keyless. Non-Memory writes are returned unchanged and never
        acquire inference or supersession behavior. The caller's metadata
        dictionary is never mutated in place.
        """
        if database_key != "memory":
            return entry
        raw = str((entry.metadata or {}).get("subject_key") or "").strip()
        key = S.redact_secrets(raw).strip() if raw else S.infer_subject_key(entry.title, entry.content)
        if not key:
            if not raw:
                return entry
            new_metadata = dict(entry.metadata or {})
            new_metadata.pop("subject_key", None)
            return replace(entry, metadata=new_metadata)
        if key == raw:
            return entry
        new_metadata = dict(entry.metadata or {})
        new_metadata["subject_key"] = key
        return replace(entry, metadata=new_metadata)

    def _write_entry_raw(
        self,
        database_id: str | None = None,
        entry: S.BrainEntry | None = None,
        *,
        domain: str = "memory",
        title: str = "Untitled",
        content: str = "",
        kind: str = "note",
        status: str = "active",
        confidence: str = "medium",
        tags: list[str] | None = None,
        entities: list[str] | None = None,
        db_id: str | None = None,
    ) -> None:
        """Write entry to Notion database, updating an existing page when one
        matches the title. Accepts either a BrainEntry object or keyword arguments.
        Raises ``RuntimeError`` on failure so callers can surface real errors.
        """
        # Resolve target database ID
        target_db_id = database_id or db_id
        if not target_db_id:
            db_key = S.database_for_domain(domain)
            target_db_id = self._db_ids.get(db_key) or ""

        # Build normalized entry from either source
        if entry is None:
            entry = S.BrainEntry(
                domain=domain,
                title=title,
                content=content,
                kind=kind,
                status=status,
                confidence=confidence,
                tags=tags or [],
                entities=entities or [],
                source_session_id=self._session_id,
            ).normalized()

        properties = self._database_properties(target_db_id, entry)

        database_key = S.database_for_domain(entry.domain)
        page_id = ""
        reused = False
        try:
            if database_key == "memory":
                page_id, reused = self._reuse_or_create_memory(target_db_id, entry, properties)
            else:
                # Legacy title-dedup path: non-Memory databases update an
                # existing same-title page in place rather than versioning.
                existing_id = ""
                if entry.title and target_db_id:
                    try:
                        existing = store.search_page_by_title(entry.title, object_type="page")
                    except Exception:
                        existing = None
                    if (
                        existing
                        and store.normalize_id(existing.get("parent", {}).get("database_id"))
                        == store.normalize_id(target_db_id)
                    ):
                        existing_id = existing["id"]
                page_id = existing_id
                if existing_id:
                    store.update_page(existing_id, properties, expected_database_id=target_db_id)
                    logger.debug("Updated entry in %s: %s", target_db_id, entry.title)
                else:
                    created = store.create_database_page(
                        database_id=target_db_id, properties=properties
                    )
                    page_id = str((created or {}).get("id") or "")
                    logger.debug("Stored entry in %s: %s", target_db_id, entry.title)
        except Exception:
            # Never echo the failure detail or entry fields back into log
            # streams — the exception may carry the full user payload.
            logger.error("Failed to store entry to Notion")
            raise RuntimeError("Failed to save entry to Notion") from None
        else:
            if reused:
                return
            self._mirror_memory_cache(page_id, entry, target_db_id)
            self._supersede_matching_active(page_id, entry, target_db_id)
            if database_key == "memory":
                # Invalidate the in-memory prefetch snapshot so a same-provider
                # next read observes the accepted cache mutation instead of a
                # stale rendered string.
                with self._prefetch_lock:
                    self._prefetch_cache = ""
            if self._hermes_home and page_id and entry.entities:
                graph = semantic_catalog.Catalog().load(self._catalog_path())
                known_entities = {entity.name.casefold() for entity in graph.list_entities()}
                for entity_name in entry.entities:
                    clean_entity = S.redact_secrets(entity_name)
                    if clean_entity.casefold() not in known_entities:
                        graph.add_entity(semantic_catalog.Entity(name=clean_entity))
                        known_entities.add(clean_entity.casefold())
                    graph.add_relation(semantic_catalog.Relation(
                        subject=clean_entity, predicate="related", object=page_id,
                        relation_type="edge",
                    ))
                graph.save(self._catalog_path())

    def _reuse_or_create_memory(
        self, target_db_id: str, entry: S.BrainEntry, properties: dict[str, Any]
    ) -> tuple[str, bool]:
        """Return ``(page_id, reused)`` for a Memory write.

        An eligible active exact fact — same normalized title, same nonblank
        subject key, and equal content — is reused idempotently without a
        Notion mutation, status transition, or duplicate edge. A title
        collision with a changed value or different subject creates a new page
        so the prior value is retained. A blank subject or a failed/truncated
        candidate inspection never authorizes an in-place overwrite; the
        non-destructive create path is taken instead.
        """
        entry_subject = str(entry.metadata.get("subject_key") or "").strip()
        reuse_id = ""
        if entry_subject and entry.title:
            try:
                rows = store.query_database(target_db_id, page_size=100)
            except Exception:
                rows = []
            cache_index = self._memory_cache_index()
            norm_title = entry.title.strip().casefold()
            for row in rows:
                old_id = str(row.get("id") or "")
                if not old_id:
                    continue
                props = row.get("properties") or {}
                if str(props.get("Status") or "active").casefold() != "active":
                    continue
                row_title = str(row.get("title") or "").strip().casefold()
                if row_title != norm_title:
                    continue
                row_subject = str(props.get("Subject Key") or "").strip()
                if row_subject.casefold() != entry_subject.casefold():
                    continue
                row_content = str(props.get("Content") or props.get("Summary") or "")
                cache_content = cache_index.get(store.normalize_id(old_id))
                if self._memory_content_equal(entry.content, row_content, cache_content):
                    reuse_id = old_id
                    break
        if reuse_id:
            logger.debug("Idempotent reuse of memory entry %s: %s", reuse_id, entry.title)
            return reuse_id, True
        created = store.create_database_page(database_id=target_db_id, properties=properties)
        page_id = str((created or {}).get("id") or "")
        logger.debug("Stored memory entry in %s: %s", target_db_id, entry.title)
        return page_id, False

    def _memory_cache_index(self) -> dict[str, str]:
        """Map normalized Memory page ids to their trusted full cached content."""
        if not self._hermes_home:
            return {}
        rows = brain_cache.list_active(self._hermes_home, limit=100) or []
        index: dict[str, str] = {}
        for row in rows:
            page_id = store.normalize_id(str(row.get("id") or ""))
            if page_id:
                index[page_id] = str((row.get("properties") or {}).get("Content") or "")
        return index

    @staticmethod
    def _memory_content_equal(
        new_content: str, remote_content: str, cache_content: str | None
    ) -> bool:
        """Compare Memory content accounting for Notion's 2,000-char truncation.

        Remote ``Content`` is truncated to 2,000 chars, so two full values
        sharing that prefix are not proven equal. A trusted full cached row
        may establish equality only while the remote prefix still agrees.
        When full equality cannot be established, return ``False`` so the
        caller favors a new retained version over unsafe reuse.
        """
        if new_content == remote_content:
            return True
        if (
            len(new_content) > 2000
            and len(remote_content) >= 2000
            and new_content[:2000] == remote_content
        ):
            if cache_content is not None and cache_content[:2000] == remote_content:
                return new_content == cache_content
        return False

    def _prefetch_entries(self) -> list[dict[str, Any]]:
        """Read active memory rows from the local cache, else Notion.

        The cache is consulted only after ``initialize`` set a hermes home,
        so callers that never configure one keep the Notion path and never
        touch ``~/.hermes``. A present cache file is a hit even when it
        holds no active rows. A missing or unreadable cache falls through
        to Notion.
        """
        if self._hermes_home:
            cached = brain_cache.list_active(self._hermes_home, limit=10)
            if cached is not None:
                cached.sort(key=self._truth_recency_key, reverse=True)
                return cached
        entries = store.query_database(
            self._db_ids["memory"],
            sorts=[{"property": "Last Seen", "direction": "descending"}],
            page_size=10,
        )
        entries = [
            entry for entry in entries
            if str((entry.get("properties") or {}).get("Status") or "active").strip().casefold() == "active"
        ]
        entries.sort(key=self._truth_recency_key, reverse=True)
        hydrated_bodies: dict[str, str] = {}
        hydrated: list[dict[str, Any]] = []
        for entry in entries[:10]:
            props = dict(entry.get("properties") or {})
            content = props.get("Content") or props.get("Summary") or ""
            page_id = str(entry.get("id") or "")
            if not content and page_id:
                if page_id not in hydrated_bodies:
                    try:
                        hydrated_bodies[page_id] = store.page_body_text(page_id) or ""
                    except Exception as exc:
                        logger.warning(
                            "NotionBrainProvider prefetch body hydration failed for %s: %s",
                            S.redact_secrets(page_id), S.redact_secrets(str(exc)),
                        )
                        hydrated_bodies[page_id] = ""
                content = hydrated_bodies[page_id]
            props["Content"] = S.redact_secrets(str(content))
            hydrated.append({**entry, "properties": props})
        if self._hermes_home:
            try:
                brain_cache.populate_from_read(self._hermes_home, hydrated)
            except Exception as exc:
                logger.warning("NotionBrainProvider cache population failed: %s", S.redact_secrets(str(exc)))
        return hydrated

    def _mirror_memory_cache(
        self, page_id: str, entry: S.BrainEntry, database_id: str
    ) -> None:
        """Write-through the Memory row after Notion accepts it.

        Failures are logged and swallowed so a cache problem never fails
        the Notion write. Non-memory databases are not mirrored.
        """
        memory_id = self._db_ids.get("memory") or ""
        if not self._hermes_home or not page_id or not memory_id:
            return
        if store.normalize_id(database_id) != store.normalize_id(memory_id):
            return
        try:
            brain_cache.upsert_active(
                self._hermes_home or None,
                page_id=page_id,
                title=entry.title,
                kind=entry.kind,
                content=entry.content,
                status=entry.status,
                last_seen=date.today().isoformat(),
                truth=entry.truth,
                subject_key=str(entry.metadata.get("subject_key") or ""),
            )
        except Exception as exc:
            logger.warning(
                "NotionBrainProvider cache mirror failed: %s", S.redact_secrets(str(exc))
            )

    def _database_properties(self, database_id: str, entry: S.BrainEntry) -> dict[str, Any]:
        """Build Notion properties from a BrainEntry."""
        props: dict[str, Any] = {
            "title": store.title_property(entry.title),
        }

        # Get database schema to know available properties
        try:
            db = store.get_database(database_id)
            schema_props = db.get("properties", {})
        except Exception as exc:
            logger.warning(
                "Could not get database schema for %s: %s", database_id, S.redact_secrets(str(exc))
            )
            raise

        if "Domain" in schema_props:
            props["Domain"] = store.select_property(entry.domain)
        if "Truth" in schema_props and store.normalize_id(database_id) == store.normalize_id(self._db_ids.get("memory", "")):
            props["Truth"] = store.select_property(entry.truth)
        if "Subject Key" in schema_props and entry.metadata.get("subject_key"):
            props["Subject Key"] = store.rich_text_property(str(entry.metadata["subject_key"]))
        if "Status" in schema_props:
            status_payload = self._status_property(entry.status, schema_props)
            if status_payload:
                props["Status"] = status_payload
        if "Kind" in schema_props:
            kind_value = _safe_select_value(entry.kind, schema_props["Kind"])
            if kind_value is not None:
                props["Kind"] = store.select_property(kind_value)
        if "Confidence" in schema_props:
            props["Confidence"] = store.select_property(entry.confidence)
        if "Tags" in schema_props:
            props["Tags"] = store.multi_select_property(entry.tags)
        if "Entities" in schema_props:
            props["Entities"] = store.multi_select_property(entry.entities)
        if "Content" in schema_props:
            props["Content"] = store.rich_text_property(entry.content)
        if "Source Session" in schema_props and entry.source_session_id:
            props["Source Session"] = store.rich_text_property(entry.source_session_id)

        # Map any custom fields defined on the database from entry.metadata
        for m_key, m_val in (entry.metadata or {}).items():
            if m_key in schema_props and m_key not in props:
                prop_type = schema_props[m_key].get("type")
                if prop_type == "number" and isinstance(m_val, (int, float)):
                    props[m_key] = store.number_property(float(m_val))
                elif prop_type == "select":
                    props[m_key] = store.select_property(str(m_val))
                elif prop_type == "multi_select":
                    val_list = [str(x) for x in m_val] if isinstance(m_val, list) else [str(m_val)]
                    props[m_key] = store.multi_select_property(val_list)
                elif prop_type in ("rich_text", "text"):
                    props[m_key] = store.rich_text_property(str(m_val))
                elif prop_type == "date":
                    props[m_key] = store.date_property(str(m_val))
                elif prop_type == "checkbox":
                    props[m_key] = {"checkbox": bool(m_val)}

        return props

    def _status_property(
        self,
        status: str,
        schema_props: dict[str, Any],
        *,
        strict: bool = False,
    ) -> dict[str, Any]:
        """Map status to a valid Notion Status option, respecting the DB's actual type.

        ``Status`` in our content DB is a ``select`` type (draft/published/scheduled/idea);
        everywhere else it's a ``status`` type (active/done/needs_review). We read the
        options out of whichever shape the DB actually uses and emit the matching
        payload. When ``strict=True`` an unknown status returns ``{}`` so callers
        can surface the error instead of silently coercing.
        """
        status_prop = schema_props.get("Status", {})
        # Notion puts option lists under the property type key — ``status`` or ``select``.
        options = (
            status_prop.get("status", {}).get("options")
            or status_prop.get("select", {}).get("options")
            or []
        )
        valid_names = {opt.get("name", "") for opt in options if isinstance(opt, dict)}
        use_select = "select" in status_prop and "status" not in status_prop

        if status in valid_names:
            target = status
        elif strict:
            # Caller asked for strict mode — return empty so it can surface the error.
            return {}
        elif valid_names:
            # Deterministic fallback — pick the lowest option alphabetically.
            target = min(valid_names)
        else:
            # No options at all — nothing safe to write; omit the property.
            return {}

        if use_select:
            return store.select_property(target)
        return store.status_property(target)

    def _tool_search(self, args: dict[str, Any]) -> str | tuple[str, dict[str, Any]]:
        """Search across brain databases, honoring the query when provided."""
        action = str(args.get("action") or "search").lower()
        if action == "related":
            return self._tool_related(args)
        if action == "timeline":
            return self._tool_timeline(args)
        query = (args.get("query") or "").strip()
        database = args.get("database")
        max_results = min(args.get("max_results", 8), 20)

        # Resolve answerability before retrieving rows or merging disk context.
        catalog = None
        if query:
            try:
                catalog = semantic_catalog.Catalog().load(self._catalog_path())
                coverage = semantic_catalog.check_answerable(query, catalog)
                if coverage["coverage"] == 0.0:
                    safe_query = S.redact_secrets(query)
                    missing = ", ".join(coverage["missing_terms"])
                    answer = (
                        f"No known semantic terms for {safe_query} were found in the catalog; "
                        f"unable to verify answerability. Missing terms: {missing}."
                    )
                    return S.redact_secrets(answer), {"items": [], "contradiction": []}
            except Exception:
                catalog = None

        # Merge disk context
        disk_text = ""
        if self._hermes_home:
            disk_text = bootstrap.read_memory_from_disk(self._hermes_home)

        # Deterministic search: the Notion database-query endpoint cannot be
        # trusted to filter titles for us — a ``title.contains`` filter is
        # case-sensitive, and a ``rich_text`` filter on a title property is
        # rejected outright.  Both modes therefore share ONE filter path: fetch
        # every row (``query_database`` walks cursor pagination to exhaustion)
        # and apply the case-insensitive title match client-side below, so a
        # query narrows results identically with and without ``database``.
        entry_databases: dict[str, str] = {}
        if database:
            # Search specific database
            db_id = self._db_ids.get(database)
            if not db_id:
                return S.redact_secrets(f"No database found for: {database}")

            entries = store.query_database(db_id, page_size=max_results)
            entry_databases.update({
                store.normalize_id(str(row.get("id") or "")): store.normalize_id(db_id)
                for row in entries if row.get("id")
            })
            entries = _merge_disk_only(entries, disk_text)
        else:
            # Search all databases
            all_entries: list[dict] = []
            for db_id in self._db_ids.values():
                try:
                    results = store.query_database(db_id, page_size=max_results)
                    entry_databases.update({
                        store.normalize_id(str(row.get("id") or "")): store.normalize_id(db_id)
                        for row in results if row.get("id")
                    })
                    all_entries.extend(results)
                except Exception:
                    pass
            entries = _merge_disk_only(all_entries, disk_text)

        # Resolve catalog terms deterministically before refining rows. Catalog
        # failures are intentionally non-fatal: ordinary search remains intact.
        definitions: list[dict[str, Any]] = []
        expanded_needles: set[str] = set()
        resolved_page_ids: set[str] = set()
        resolved_database_ids: set[str] = set()
        if query:
            try:
                if catalog is None:
                    catalog = semantic_catalog.Catalog().load(self._catalog_path())
                matches = catalog.match_definitions(query)
                for definition in matches:
                    expanded_needles.add(definition.name)
                    if isinstance(definition, semantic_catalog.Term):
                        expanded_needles.update(definition.synonyms)
                if matches:
                    from . import adapters
                    notion_adapter = adapters.NotionAdapter(hermes_home=self._hermes_home)
                    import os
                    vault_path = os.environ.get("HERMES_OBSIDIAN_VAULT", "").strip()
                    obsidian_adapter = adapters.ObsidianVaultAdapter(vault_path) if vault_path else None
                    for definition in matches:
                        resolved: list[str] = []
                        for ref in definition.storage_refs:
                            adapter_name = str(ref.adapter_name).casefold()
                            locator = None
                            if adapter_name.startswith("notion"):
                                locator = notion_adapter.resolve_storage_ref(ref)
                                if locator is not None:
                                    if ref.locator.casefold().startswith(("db/", "db:", "database/", "database:")):
                                        resolved_database_ids.add(store.normalize_id(locator))
                                    else:
                                        resolved_page_ids.add(store.normalize_id(locator))
                            elif adapter_name.startswith("obsidian") and obsidian_adapter is not None:
                                locator = obsidian_adapter.resolve_storage_ref(ref)
                            if locator is not None:
                                safe_locator = S.redact_secrets(str(locator))
                                if safe_locator not in resolved:
                                    resolved.append(safe_locator)
                        definitions.append({
                            "name": S.redact_secrets(str(definition.name)),
                            "description": S.redact_secrets(str(definition.description)),
                            "storage_refs": resolved,
                        })
            except Exception:
                definitions = []
                expanded_needles.clear()
                resolved_page_ids.clear()
                resolved_database_ids.clear()

        # Current recall excludes superseded history; timeline/related expose it.
        entries = [
            entry for entry in entries
            if str((entry.get("properties") or {}).get("Status") or "active").casefold() != "superseded"
        ]

        # Concrete references select only rows from the queried databases.
        # Alias text matching remains available for definitions without refs.
        if query:
            needles = {query.casefold(), *(needle.casefold() for needle in expanded_needles)}
            entries = [
                e for e in entries
                if store.normalize_id(str(e.get("id") or "")) in resolved_page_ids
                or entry_databases.get(store.normalize_id(str(e.get("id") or ""))) in resolved_database_ids
                or any(needle in (str(e.get("title") or "") + " " + str((e.get("properties") or {}).get("Content") or "")).casefold()
                       for needle in needles)
            ]

        entries.sort(key=self._truth_recency_key, reverse=True)
        contradictions = self._contradictions(entries)

        # ``max_results`` caps the returned rows regardless of mode, so the
        # limit does not depend on how many databases were scanned.
        entries = entries[:max_results]

        # Format results
        if not entries:
            payload = {"items": [], "contradiction": contradictions}
            if definitions:
                payload["definitions"] = definitions
            return ("No results found.", payload)

        lines: list[str] = []
        structured_items: list[dict[str, Any]] = []
        for entry in entries:
            title = entry.get("title", "Untitled")
            content = entry.get("properties", {}).get("Content", "")[:200]
            kind = entry.get("properties", {}).get("Kind", "note")
            provenance = self._provenance(entry)
            lines.append(f"- [{kind}] {title}: {content} [fact:{provenance['truth']}:{provenance['source_agent']}]")
            structured_items.append(
                {
                    "title": title,
                    "content": content,
                    "kind": kind,
                    "id": entry.get("id"),
                    "properties": entry.get("properties", {}),
                    "provenance": provenance,
                }
            )

        payload = {"items": structured_items, "contradiction": contradictions}
        if definitions:
            payload["definitions"] = definitions
        return ("\n".join(lines), payload)

    @staticmethod
    def _contradictions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            props = entry.get("properties", {}) or {}
            subject = str(props.get("Subject Key") or "")
            if not subject or str(props.get("Status") or "active").casefold() != "active":
                continue
            value = str(props.get("Content") or props.get("Summary") or "")
            if value:
                grouped.setdefault(subject, []).append({
                    "subject_key": S.redact_secrets(subject),
                    "value": S.redact_secrets(value),
                    "timestamp": S.redact_secrets(str(entry.get("created_time") or entry.get("created_at") or "")),
                    "certification": S.redact_secrets(str(props.get("Truth") or "inferred").casefold()),
                })
        conflicts = []
        for subject, items in grouped.items():
            if len({item["value"] for item in items}) > 1:
                conflicts.append({"subject_key": S.redact_secrets(subject), "entries": items})
        return conflicts

    def _tool_check_answerable(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        query = S.redact_secrets(str(args.get("query") or ""))
        catalog = semantic_catalog.Catalog().load(self._catalog_path())
        result = semantic_catalog.check_answerable(query, catalog)
        if result["coverage"] == 0.0:
            missing = ", ".join(result["missing_terms"])
            message = (
                f"No known semantic terms for {query} were found in the catalog; "
                f"unable to verify answerability. Missing terms: {missing}."
            )
        else:
            message = f"Catalog term coverage: {result['coverage']:.2f}."
        return message, result

    def _tool_search_terms(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        query = S.redact_secrets(str(args.get("query") or ""))
        terms = semantic_catalog.Catalog().load(self._catalog_path()).search_terms(query)
        return ("\n".join(terms) if terms else "No glossary terms found.", {"terms": terms})

    @staticmethod
    def _provenance(entry: dict[str, Any]) -> dict[str, str]:
        props = entry.get("properties", {}) or {}
        status = str(props.get("Status") or "active").lower()
        return {
            "source_agent": S.redact_secrets(str(props.get("Source Agent") or "unknown")),
            "session_id": S.redact_secrets(str(props.get("Source Session") or "")),
            "created_at": S.redact_secrets(str(entry.get("created_time") or entry.get("created_at") or "unknown")),
            "truth": str(props.get("Truth") or "inferred").lower() if str(props.get("Truth") or "inferred").lower() in {"certified", "inferred"} else "inferred",
            "status": "superseded" if status == "superseded" else "active",
        }

    def _tool_related(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        start = S.redact_secrets(str(args.get("start_id") or args.get("query") or "").strip())
        if not start:
            return ("A memory id or name is required.", {"items": []})
        graph = semantic_catalog.Catalog().load(self._catalog_path())
        resolved = start
        db_id = self._db_ids.get("memory")
        rows = store.query_database(db_id, page_size=100) if db_id else []
        exact = next((r for r in rows if str(r.get("id", "")).lower() == start.lower() or str(r.get("title", "")).lower() == start.lower()), None)
        if exact:
            resolved = str(exact.get("id") or start)
        ids = graph.graph_traverse(resolved, predicate=args.get("predicate"), max_depth=min(int(args.get("max_depth", 3)), 10))
        id_set = {i.lower() for i in ids}
        items = []
        for row in rows:
            if str(row.get("id") or "").lower() in id_set:
                props = row.get("properties", {}) or {}
                items.append({"id": row.get("id"), "title": row.get("title"), "content": props.get("Content", ""), "provenance": self._provenance(row)})
        return ("\n".join(f"- {i['title']}: {i['content']}" for i in items) or "No related memories found.", {"items": items})

    def _tool_timeline(self, args: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        subject_key = S.redact_secrets(str(args.get("subject_key") or "")).strip()
        if not subject_key:
            return ("A subject_key is required for timeline.", {"items": []})
        db_id = self._db_ids.get("memory")
        if not db_id:
            return ("Memory database is unavailable.", {"items": []})
        rows = store.query_database(db_id, page_size=100)
        matching = [
            row for row in rows
            if str((row.get("properties") or {}).get("Subject Key") or "").strip() == subject_key
        ]
        matching.sort(
            key=lambda row: str(
                row.get("created_time")
                or (row.get("properties") or {}).get("Last Seen")
                or row.get("last_edited_time") or ""
            ),
            reverse=True,
        )
        items = []
        for row in matching:
            props = row.get("properties") or {}
            timestamp = str(
                props.get("Last Seen") or row.get("last_edited_time") or row.get("created_time") or ""
            )
            items.append({
                "id": row.get("id", ""),
                "title": row.get("title", "Untitled"),
                "content": props.get("Content") or props.get("Summary") or "",
                "subject_key": subject_key,
                "status": str(props.get("Status") or "active"),
                "timestamp": timestamp,
                "created_time": row.get("created_time", ""),
                "last_edited_time": row.get("last_edited_time", ""),
            })
        lines = [f"- [{item['status']}] {item['timestamp']} {item['title']}: {item['content']}" for item in items]
        return ("\n".join(lines) or "No history found for this subject key.", {"items": items})

    def _supersede_matching_active(
        self, page_id: str, entry: S.BrainEntry, database_id: str
    ) -> None:
        """Best-effort history flip after the successful current-row write.

        Only an active inferred input may supersede active inferred
        predecessors with the same nonblank subject. Certified facts are
        never demoted by an ordinary write; a conflicting inferred fact
        coexists and surfaces through contradiction reporting.
        """
        if (not page_id or not entry.metadata.get("subject_key")
                or str(entry.status or "").casefold() != "active"
                or store.normalize_id(database_id) != store.normalize_id(self._db_ids.get("memory", ""))):
            return
        subject_key = S.redact_secrets(str(entry.metadata.get("subject_key") or "")).strip()
        if not subject_key:
            return
        try:
            rows = store.query_database(database_id, page_size=100)
            schema_props = store.get_database(database_id).get("properties", {})
            status_property = self._status_property("Superseded", schema_props, strict=True)
            if not status_property:
                logger.warning("NotionBrainProvider supersession skipped: Superseded status unavailable")
                return
            for row in rows:
                old_id = str(row.get("id") or "")
                props = row.get("properties") or {}
                if (not old_id or old_id == page_id
                        or str(props.get("Subject Key") or "").strip() != subject_key
                        or str(props.get("Status") or "active").casefold() != "active"
                        or str(props.get("Truth") or "inferred").casefold() == "certified"):
                    continue
                store.update_page(old_id, {"Status": status_property}, expected_database_id=database_id)
                if "Superseded Page ID" in schema_props:
                    try:
                        store.update_page(
                            page_id,
                            {"Superseded Page ID": store.rich_text_property(old_id)},
                            expected_database_id=database_id,
                        )
                    except Exception as exc:
                        logger.warning("Supersession predecessor link failed: %s", S.redact_secrets(str(exc)))
                try:
                    graph = semantic_catalog.Catalog().load(self._catalog_path())
                    graph.add_relation(semantic_catalog.Relation(
                        subject=page_id, predicate="supersedes", object=old_id,
                        relation_type="edge",
                    ))
                    graph.save(self._catalog_path())
                except Exception as exc:
                    logger.warning("Supersession catalog update failed: %s", S.redact_secrets(str(exc)))
                if self._hermes_home:
                    brain_cache.upsert_active(
                        self._hermes_home, page_id=old_id,
                        title=str(row.get("title") or "Untitled"),
                        kind=str(props.get("Kind") or "note"),
                        content=str(props.get("Content") or props.get("Summary") or ""),
                        status="Superseded", last_seen=str(props.get("Last Seen") or ""),
                        truth=str(props.get("Truth") or "inferred"),
                        subject_key=subject_key,
                    )
        except Exception as exc:
            logger.warning("NotionBrainProvider supersession failed: %s", S.redact_secrets(str(exc)))

    @staticmethod
    def _truth_recency_key(entry: dict[str, Any]) -> tuple[str, int]:
        props = entry.get("properties", {}) or {}
        recency = str(props.get("Last Seen") or entry.get("last_edited_time") or entry.get("created_time") or "")
        return recency, int(str(props.get("Truth") or "inferred").lower() == "certified")

    def _tool_certify(self, args: dict[str, Any], *, user_confirmed: bool = False) -> str:
        """Certify one memory only with explicit confirmation for this invocation."""
        if user_confirmed is not True:
            return "Error: orchestrator confirmation is required"
        db_id = self._db_ids.get("memory")
        if not db_id:
            return "Error: Memory database is unavailable"
        memory_id = S.redact_secrets(str(args.get("memory_id") or "").strip())
        title = S.clean_title(str(args.get("title") or "").strip()) if args.get("title") else ""
        rows = store.query_database(db_id, page_size=100)
        row = next((item for item in rows if memory_id and store.normalize_id(str(item.get("id"))) == store.normalize_id(memory_id)), None)
        if row is None and title:
            row = next((item for item in rows if str(item.get("title", "")).casefold() == title.casefold()), None)
        if row is None:
            return "Error: memory not found"
        properties = row.get("properties", {}) or {}
        page_id = str(row.get("id") or "")
        try:
            store.update_page(page_id, {"Truth": store.select_property("certified")}, expected_database_id=db_id)
            if self._hermes_home:
                try:
                    brain_cache.upsert_active(
                        self._hermes_home, page_id=page_id,
                        title=str(row.get("title") or "Untitled"),
                        kind=str(properties.get("Kind") or "note"),
                        content=str(properties.get("Content") or ""),
                        status=str(properties.get("Status") or "active"),
                        last_seen=str(properties.get("Last Seen") or ""), truth="certified",
                        subject_key=str(properties.get("Subject Key") or ""),
                    )
                except Exception as exc:
                    logger.warning(
                        "NotionBrainProvider cache mirror failed: %s",
                        S.redact_secrets(str(exc)),
                    )
            subject_key = str(properties.get("Subject Key") or "")
            if subject_key:
                for older in rows:
                    older_props = older.get("properties", {}) or {}
                    if (str(older.get("id")) == page_id or
                        str(older_props.get("Subject Key") or "") != subject_key or
                        str(older_props.get("Status") or "active").lower() != "active" or
                        str(older_props.get("Truth") or "inferred").lower() != "inferred"):
                        continue
                    status = self._status_property("Superseded", store.get_database(db_id).get("properties", {}), strict=True)
                    if status:
                        store.update_page(str(older.get("id") or ""), {"Status": status}, expected_database_id=db_id)
                        predecessor_id = str(older.get("id") or "")
                        db_props = store.get_database(db_id).get("properties", {})
                        if "Superseded Page ID" in db_props:
                            store.update_page(
                                page_id,
                                {"Superseded Page ID": store.rich_text_property(predecessor_id)},
                                expected_database_id=db_id,
                            )
                        graph = semantic_catalog.Catalog().load(self._catalog_path())
                        graph.add_relation(semantic_catalog.Relation(
                            subject=page_id, predicate="supersedes", object=predecessor_id,
                            relation_type="edge",
                        ))
                        graph.save(self._catalog_path())
                        if self._hermes_home:
                            brain_cache.upsert_active(
                                self._hermes_home, page_id=str(older.get("id") or ""),
                                title=str(older.get("title") or "Untitled"),
                                kind=str(older_props.get("Kind") or "note"),
                                content=str(older_props.get("Content") or ""),
                                status="Superseded",
                                last_seen=str(older_props.get("Last Seen") or ""),
                                truth="inferred",
                            )
        except Exception as exc:
            logger.warning("Certification update failed: %s", S.redact_secrets(str(exc)))
            return "Error: certification update failed"
        return f"Certified: {S.redact_secrets(str(row.get('title') or 'memory'))}"

    def _tool_remember(self, args: dict[str, Any]) -> str:
        """Explicitly remember something."""
        title = args.get("title", "").strip()
        content = args.get("content", "").strip()
        domain = args.get("domain", "memory")
        kind = args.get("kind", "note")
        status = args.get("status", "active")
        tags = _coerce_str_list(args.get("tags", []))
        entities = _coerce_str_list(args.get("entities", []))

        if not title:
            return "Error: title is required"
        if not content:
            return "Error: content is required"

        # Scrub user-supplied fields before they reach the BrainEntry so the
        # secret policy applies even when callers bypass BrainEntry.normalized().
        entry = S.BrainEntry(
            domain=domain,
            title=S.clean_title(title),
            content=S.redact_secrets(content),
            kind=S.redact_secrets(kind),
            status=S.redact_secrets(status),
            tags=[S.redact_secrets(t) for t in tags],
            entities=[S.redact_secrets(e) for e in entities],
            source_session_id=self._session_id,
            metadata={"subject_key": S.redact_secrets(str(args.get("subject_key") or "")).strip()
                      or S.infer_subject_key(title, content)},
        ).normalized()

        try:
            self._store_entry(entry)
        except RuntimeError as exc:
            return f"Error: {S.redact_secrets(str(exc))}"
        return f"Saved: {entry.title}"

    def _tool_task(self, args: dict[str, Any]) -> str:
        """Manage tasks."""
        action = args.get("action", "list")

        if action == "create":
            title = args.get("title", "").strip()
            if not title:
                return "Error: task title is required"

            entry = S.BrainEntry(
                domain="daily_work",
                title=S.clean_title(title),
                content=S.redact_secrets(args.get("content", "")),
                kind="task",
                status=S.redact_secrets(args.get("status", "active")),
                tags=[S.redact_secrets(t) for t in _coerce_str_list(args.get("tags", []))],
                source_session_id=self._session_id,
            ).normalized()

            try:
                self._store_entry(entry)
            except RuntimeError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            return f"Task created: {entry.title}"

        elif action == "list":
            db_id = self._db_ids.get("tasks")
            if not db_id:
                return "No Tasks database found."

            entries = store.query_database(db_id, page_size=20)
            if not entries:
                return "No tasks found."

            lines: list[str] = []
            for item in entries:
                title = item.get("title", "Untitled")
                status = item.get("properties", {}).get("Status", "")
                lines.append(f"- [{status}] {title}")

            return "\n".join(lines)

        elif action == "update":
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required for update"
            if err := self._check_page_in_db(page_id, "tasks"):
                return err

            properties: dict[str, Any] = {}
            if "title" in args:
                properties["title"] = store.title_property(S.clean_title(args["title"]))
            if "status" in args:
                status_payload, status_err = self._validated_status(args["status"], "tasks")
                if status_err:
                    return status_err
                if status_payload:
                    properties["Status"] = status_payload

            store.update_page(
                page_id, properties, expected_database_id=self._db_ids.get("tasks")
            )
            return "Task updated."

        elif action == "complete":
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required"
            if err := self._check_page_in_db(page_id, "tasks"):
                return err

            status_payload, status_err = self._validated_status("done", "tasks")
            if status_err:
                return status_err
            properties = {"Status": status_payload} if status_payload else {}
            store.update_page(
                page_id, properties, expected_database_id=self._db_ids.get("tasks")
            )
            return "Task completed."

        return S.redact_secrets(f"Unknown task action: {action}")

    def _validated_status(self, status: str, db_key: str) -> tuple[dict[str, Any], str | None]:
        """Build a Status payload validated against ``db_key``'s real options.

        Returns (payload, None) on success, ({}, error_message) if ``status``
        is not a defined option. Falls back to a plain status_property write
        if the schema can't be read — matching create-path behavior.
        """
        db_id = self._db_ids.get(db_key)
        if not db_id:
            return store.status_property(status), None
        try:
            db = store.get_database(db_id)
            schema_props = db.get("properties", {})
        except Exception as exc:
            logger.warning("Could not read schema for %s: %s", db_key, S.redact_secrets(str(exc)))
            return store.status_property(status), None

        payload = self._status_property(status, schema_props, strict=True)
        if payload:
            return payload, None
        # _status_property returns {} only when the value isn't a valid option
        # (and it can't fall back). Surface that so the user knows.
        status_prop = schema_props.get("Status", {})
        options = (
            status_prop.get("status", {}).get("options")
            or status_prop.get("select", {}).get("options")
            or []
        )
        valid = sorted({opt.get("name", "") for opt in options if isinstance(opt, dict)})
        return {}, f"Error: status '{status}' is not valid for {db_key}. Valid: {valid}"

    def _check_page_in_db(self, page_id: str, db_key: str) -> str | None:
        """Return an error string if page_id is not in the expected DB; else None.

        Fails closed: any verification failure, containment mismatch, or API
        error denies authorization.
        """
        db_id = self._db_ids.get(db_key)
        if not db_id:
            return None
        authorized, reason = store.verify_page_in_database(page_id, db_id)
        if not authorized:
            return (
                f"Error: page {S.redact_secrets(str(page_id))} does not belong to {db_key} database"
            )
        return None

    def _tool_content(self, args: dict[str, Any]) -> str:
        """Manage social content."""
        action = args.get("action", "list")

        if action == "create":
            title = args.get("title", "").strip()
            body = args.get("body", "").strip()
            if not title:
                return "Error: content title is required"

            entry = S.BrainEntry(
                domain="social_content",
                title=S.clean_title(title),
                content=S.redact_secrets(body),
                kind="draft",
                status=S.redact_secrets(args.get("status", "draft")),
                tags=[S.redact_secrets(t) for t in _coerce_str_list(args.get("tags", []))],
                source_session_id=self._session_id,
            ).normalized()

            try:
                self._store_entry(entry)
            except RuntimeError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            return f"Content saved: {entry.title}"

        elif action == "update":
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required for update"
            if err := self._check_page_in_db(page_id, "content"):
                return err

            updates: dict[str, Any] = {}

            if "title" in args:
                updates["title"] = store.title_property(S.clean_title(args["title"]))
            if "body" in args:
                updates["Content"] = store.rich_text_property(args["body"])
            if "tags" in args:
                updates["Tags"] = store.multi_select_property(args["tags"])

            if not updates:
                return "Error: No fields provided for update."

            try:
                db_id = self._db_ids.get("content")
                store.update_page(page_id, updates, expected_database_id=db_id)
                return f"Content updated for page ID: {S.redact_secrets(str(page_id))}"
            except store.AuthorizationError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            except Exception as exc:
                return f"Error updating content: {S.redact_secrets(str(exc))}"

        elif action == "publish":
            # For social content, changing status to published requires updating the status field
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required for update"
            if err := self._check_page_in_db(page_id, "content"):
                return err

            try:
                # Attempt to complete the status field change
                status_payload, status_err = self._validated_status("published", "content")
                if status_err:
                    return status_err

                properties = {"Status": status_payload} if status_payload else {}
                db_id = self._db_ids.get("content")
                store.update_page(page_id, properties, expected_database_id=db_id)
                return "Content successfully marked as published."
            except store.AuthorizationError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            except Exception as exc:
                return f"Error publishing content: {S.redact_secrets(str(exc))}"

        elif action == "archive":
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required for update"
            if err := self._check_page_in_db(page_id, "content"):
                return err

            try:
                # Archive/cleanup status field (assuming 'archived' is a valid status option)
                status_payload, status_err = self._validated_status("archived", "content")
                if status_err:
                    return status_err

                properties = {"Status": status_payload} if status_payload else {}
                db_id = self._db_ids.get("content")
                store.update_page(page_id, properties, expected_database_id=db_id)
                return "Content successfully marked as archived."
            except store.AuthorizationError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            except Exception as exc:
                return f"Error archiving content: {S.redact_secrets(str(exc))}"

        elif action == "list":
            db_id = self._db_ids.get("content")
            if not db_id:
                return "No Content database found."

            entries = store.query_database(db_id, page_size=20)
            if not entries:
                return "No content found."

            lines: list[str] = []
            for item in entries:
                title = item.get("title", "Untitled")
                status = item.get("properties", {}).get("Status", "")
                lines.append(f"- [{status}] {title}")

            return "\n".join(lines)

        return S.redact_secrets(f"Unknown content action: {action}")

    def _tool_research(self, args: dict[str, Any]) -> str:
        """Manage research findings."""
        action = args.get("action", "save")

        if action == "save":
            title = args.get("title", "").strip()
            content = args.get("content", "").strip()
            if not title:
                return "Error: research title is required"

            entry = S.BrainEntry(
                domain="research",
                title=S.clean_title(title),
                content=S.redact_secrets(content),
                kind="reference",
                status=S.redact_secrets(args.get("status", "active")),
                tags=[S.redact_secrets(t) for t in _coerce_str_list(args.get("tags", []))],
                source_session_id=self._session_id,
            ).normalized()

            try:
                self._store_entry(entry)
            except RuntimeError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            return f"Research saved: {entry.title}"

        elif action == "update":
            page_id = args.get("page_id")
            if not page_id:
                return "Error: page_id is required for update"
            if err := self._check_page_in_db(page_id, "research"):
                return err

            updates: dict[str, Any] = {}
            if "title" in args:
                updates["title"] = store.title_property(S.clean_title(args["title"]))
            if "content" in args:
                updates["Content"] = store.rich_text_property(args["content"])
            if "tags" in args:
                updates["Tags"] = store.multi_select_property(args["tags"])
            if "status" in args:
                status_payload, status_err = self._validated_status(args["status"], "research")
                if status_err:
                    return status_err
                if status_payload:
                    updates["Status"] = status_payload

            if not updates:
                return "Error: No fields provided for update."

            try:
                db_id = self._db_ids.get("research")
                store.update_page(page_id, updates, expected_database_id=db_id)
                return f"Research updated for page ID: {S.redact_secrets(str(page_id))}"
            except store.AuthorizationError as exc:
                return f"Error: {S.redact_secrets(str(exc))}"
            except Exception as exc:
                return f"Error updating research: {S.redact_secrets(str(exc))}"

        elif action == "list":
            db_id = self._db_ids.get("research")
            if not db_id:
                return "No Research database found."

            entries = store.query_database(db_id, page_size=20)
            if not entries:
                return "No research findings found."

            lines: list[str] = []
            for item in entries:
                title = item.get("title", "Untitled")
                lines.append(f"- {title}")

            return "\n".join(lines)

        return S.redact_secrets(f"Unknown research action: {action}")


# Registration


def register(context: Any) -> None:
    """Register the NotionBrainProvider with Hermes."""
    context.register_memory_provider(NotionBrainProvider())
