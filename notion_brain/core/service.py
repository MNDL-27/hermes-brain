"""Memory service — stable boundary for memory operations.

This module provides the core service layer that coordinates validation,
privacy, local transactions, and synchronization requests. It depends only
on canonical models and the StorageBackend port, not on any specific backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    from .errors import BrainError, ConflictError, NotFoundError, PrivacyError, ValidationError
except ImportError:
    from notion_brain.core.errors import BrainError, ConflictError, NotFoundError, PrivacyError, ValidationError

try:
    from .models import (
        BackendReference,
        ConflictRecord,
        ConflictResolution,
        MemoryKind,
        MemoryRecord,
        MemoryStatus,
        OutboxAction,
        OutboxOperation,
        OutboxState,
        Priority,
        Record,
        SyncCheckpoint,
        TaskRecord,
        TaskStatus,
    )
except ImportError:
    from notion_brain.core.models import (
        BackendReference,
        ConflictRecord,
        ConflictResolution,
        MemoryKind,
        MemoryRecord,
        MemoryStatus,
        OutboxAction,
        OutboxOperation,
        OutboxState,
        Priority,
        Record,
        SyncCheckpoint,
        TaskRecord,
        TaskStatus,
    )

try:
    from .ports import BackendCapabilities, SearchOptions, StorageBackend, SyncResult
except ImportError:
    from notion_brain.core.ports import BackendCapabilities, SearchOptions, StorageBackend, SyncResult


@dataclass(slots=True)
class PrivacyPolicy:
    """Configurable privacy policy for secret handling."""

    class Mode(str):
        REDACT = "redact"
        BLOCK = "block"
        ALLOW = "allow"

    mode: Mode = Mode.REDACT
    # Secret patterns to detect - extendable by backend
    additional_patterns: list[str] = field(default_factory=list)
    # Fields that are never redacted/blocked
    allowlisted_fields: set[str] = field(default_factory=lambda: {"title", "tags", "entities", "kind"})


class PrivacyEngine:
    """Applies privacy policy to record content."""

    def __init__(self, policy: PrivacyPolicy) -> None:
        self.policy = policy

    def apply(self, record: Record) -> Record:
        """Return a new record with privacy policy applied to body/content."""
        if self.policy.mode == PrivacyPolicy.Mode.ALLOW:
            return record

        # Check body for secrets
        if self._contains_secret(record.body):
            if self.policy.mode == PrivacyPolicy.Mode.BLOCK:
                raise PrivacyError(
                    "Record contains secrets and privacy policy is set to block",
                    policy=self.policy.mode.value,
                )
            # REDACT mode - return redacted copy
            record = self._redacted_copy(record, record.body)

        return record

    def _contains_secret(self, text: str) -> bool:
        """Check if text contains secret patterns."""
        from notion_brain.schema import _SECRET_PATTERNS

        for pattern in _SECRET_PATTERNS:
            if pattern.search(text):
                return True
        # Check additional patterns
        import re

        for pattern_str in self.policy.additional_patterns:
            if re.search(pattern_str, text):
                return True
        return False

    def _redacted_copy(self, record: Record, original_body: str) -> Record:
        """Create a copy with secrets redacted."""
        from notion_brain.schema import redact_secrets

        redacted_body = redact_secrets(original_body)
        if isinstance(record, MemoryRecord):
            return MemoryRecord(
                id=record.id,
                title=record.title,
                body=redacted_body,
                kind=record.kind,
                status=record.status,
                tags=record.tags,
                entities=record.entities,
                source_type=record.source_type,
                source_reference=record.source_reference,
                created_at=record.created_at,
                updated_at=record.updated_at,
                metadata=record.metadata,
                backend_refs=record.backend_refs,
            )
        else:  # TaskRecord
            return TaskRecord(
                id=record.id,
                title=record.title,
                body=redacted_body,
                kind=record.kind,
                status=record.status,
                tags=record.tags,
                entities=record.entities,
                source_type=record.source_type,
                source_reference=record.source_reference,
                created_at=record.created_at,
                updated_at=record.updated_at,
                metadata=record.metadata,
                priority=record.priority,
                due_date=record.due_date,
                project=record.project,
                task_status=record.task_status,
                completed_at=record.completed_at,
                backend_refs=record.backend_refs,
            )


class ValidationEngine:
    """Validates and normalizes records before persistence."""

    def validate_memory(self, record: MemoryRecord) -> MemoryRecord:
        """Validate and return normalized MemoryRecord."""
        if not record.title.strip():
            raise ValidationError("Memory title cannot be empty", field="title")
        if not record.body.strip():
            raise ValidationError("Memory body cannot be empty", field="body")
        if len(record.title) > 120:
            raise ValidationError("Memory title exceeds 120 characters", field="title")
        return record.normalized()

    def validate_task(self, record: TaskRecord) -> TaskRecord:
        """Validate and return normalized TaskRecord."""
        if not record.title.strip():
            raise ValidationError("Task title cannot be empty", field="title")
        if len(record.title) > 120:
            raise ValidationError("Task title exceeds 120 characters", field="title")
        if record.due_date and record.due_date < datetime.utcnow():
            # Allow but could warn
            pass
        return record

    def normalize_memory(self, record: MemoryRecord) -> MemoryRecord:
        """Normalize a memory record (domain alias mapping, etc.)."""
        from notion_brain.schema import normalize_domain

        # Apply domain normalization to tags/entities if needed
        normalized = record.normalized()
        # Could add more normalization here
        return normalized

    def normalize_task(self, record: TaskRecord) -> TaskRecord:
        """Normalize a task record."""
        from notion_brain.schema import normalize_domain

        return record


class MemoryService:
    """Stable service boundary for memory operations.

    This is the single point of interaction for CLI, Hermes adapters,
    and experimental features. It coordinates:
    - Validation and privacy
    - Local persistence (via repository)
    - Outbox management for durability
    - Synchronization requests
    """

    def __init__(
        self,
        backend: StorageBackend,
        repository: "RecordRepository",
        outbox: "OutboxRepository",
        privacy_engine: PrivacyEngine,
        validation_engine: ValidationEngine,
    ) -> None:
        self._backend = backend
        self._repository = repository
        self._outbox = outbox
        self._privacy = privacy_engine
        self._validation = validation_engine

    # ─── Memory Operations ─────────────────────────────────────────────

    def remember(self, record: MemoryRecord) -> MemoryRecord:
        """Persist a memory record locally and queue for sync."""
        validated = self._validation.validate_memory(record)
        private = self._privacy.apply(validated)

        # Store locally
        self._repository.save_memory(private)

        # Queue for sync
        operation = OutboxOperation(
            record_id=private.id,
            record_type="memory",
            backend_name=self._backend.name,
            action=OutboxAction.CREATE,
            idempotency_key=f"create:{private.id}",
        )
        self._outbox.enqueue(operation)

        return private

    def update_memory(self, record: MemoryRecord) -> MemoryRecord:
        """Update an existing memory record."""
        validated = self._validation.validate_memory(record)
        private = self._privacy.apply(validated)

        # Store locally
        self._repository.save_memory(private)

        # Queue for sync
        operation = OutboxOperation(
            record_id=private.id,
            record_type="memory",
            backend_name=self._backend.name,
            action=OutboxAction.UPDATE,
            idempotency_key=f"update:{private.id}:{private.updated_at.isoformat()}",
        )
        self._outbox.enqueue(operation)

        return private

    def delete_memory(self, record_id: str) -> None:
        """Delete a memory record."""
        self._repository.delete_memory(record_id)

        operation = OutboxOperation(
            record_id=record_id,
            record_type="memory",
            backend_name=self._backend.name,
            action=OutboxAction.DELETE,
            idempotency_key=f"delete:{record_id}",
        )
        self._outbox.enqueue(operation)

    def get_memory(self, record_id: str) -> MemoryRecord | None:
        """Retrieve a memory record by ID."""
        return self._repository.get_memory(record_id)

    def search_memories(self, query: str, **filters: Any) -> list[MemoryRecord]:
        """Search memories locally (SQLite FTS) and remotely if needed."""
        # First try local FTS
        local_results = self._repository.search_memories(query, **filters)
        if local_results:
            return local_results

        # Fall back to backend search
        options = SearchOptions(query=query, limit=filters.get("limit", 20))
        remote_results = self._backend.search(options)
        # Convert to canonical records
        return [self._to_memory_record(r) for r in remote_results]

    def list_memories(
        self,
        *,
        domain: str | None = None,
        status: MemoryStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        """List memories with filters."""
        return self._repository.list_memories(
            domain=domain, status=status, limit=limit, offset=offset
        )

    # ─── Task Operations ───────────────────────────────────────────────

    def create_task(self, record: TaskRecord) -> TaskRecord:
        """Persist a task record locally and queue for sync."""
        validated = self._validation.validate_task(record)
        private = self._privacy.apply(validated)

        self._repository.save_task(private)

        operation = OutboxOperation(
            record_id=private.id,
            record_type="task",
            backend_name=self._backend.name,
            action=OutboxAction.CREATE,
            idempotency_key=f"create:{private.id}",
        )
        self._outbox.enqueue(operation)

        return private

    def update_task(self, record: TaskRecord) -> TaskRecord:
        """Update an existing task record."""
        validated = self._validation.validate_task(record)
        private = self._privacy.apply(validated)

        self._repository.save_task(private)

        operation = OutboxOperation(
            record_id=private.id,
            record_type="task",
            backend_name=self._backend.name,
            action=OutboxAction.UPDATE,
            idempotency_key=f"update:{private.id}:{private.updated_at.isoformat()}",
        )
        self._outbox.enqueue(operation)

        return private

    def complete_task(self, record_id: str) -> TaskRecord | None:
        """Mark a task as complete."""
        task = self._repository.get_task(record_id)
        if not task:
            return None

        task.task_status = TaskStatus.DONE
        task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()

        return self.update_task(task)

    def get_task(self, record_id: str) -> TaskRecord | None:
        """Retrieve a task record by ID."""
        return self._repository.get_task(record_id)

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        project: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskRecord]:
        """List tasks with filters."""
        return self._repository.list_tasks(status=status, project=project, limit=limit, offset=offset)

    # ─── Synchronization ───────────────────────────────────────────────

    def sync(self) -> SyncResult:
        """Trigger a synchronization cycle.

        Skipped: full sync coordinator — it would orchestrate outbox
        flush + remote pull + conflict resolution, none of which are
        implemented yet. Return a zero-result so the API surface stays
        stable. Add when [Y] the coordinator exists.
        """
        return SyncResult()

    def get_outbox_status(self) -> list[OutboxOperation]:
        """Get all pending outbox operations."""
        return self._outbox.all()

    def get_conflicts(self) -> list[ConflictRecord]:
        """Get all unresolved conflicts."""
        return self._repository.get_conflicts()

    def resolve_conflict(self, conflict_id: str, resolution: ConflictResolution) -> None:
        """Resolve a synchronization conflict."""
        conflict = self._repository.get_conflict(conflict_id)
        if not conflict:
            raise NotFoundError(f"Conflict not found: {conflict_id}")

        # Apply resolution
        if resolution == ConflictResolution.APPLY_LOCAL:
            # Push local version
            pass  # TODO: implement
        elif resolution == ConflictResolution.KEEP_REMOTE:
            # Keep remote, discard local
            pass
        elif resolution == ConflictResolution.KEEP_BOTH:
            # Create both as separate records
            pass

        conflict.resolution = resolution
        conflict.resolved_at = datetime.utcnow()
        self._repository.save_conflict(conflict)

    # ─── Conversion Helpers ────────────────────────────────────────────

    def _to_memory_record(self, backend_record: Any) -> MemoryRecord:
        """Convert a backend-specific record to canonical MemoryRecord."""
        # This is a placeholder - actual conversion happens in backend adapter
        raise NotImplementedError("Backend adapter must implement conversion")

    def _to_task_record(self, backend_record: Any) -> TaskRecord:
        """Convert a backend-specific record to canonical TaskRecord."""
        raise NotImplementedError("Backend adapter must implement conversion")


# ─── Repository Ports ───────────────────────────────────────────────────


class RecordRepository(ABC):
    """Abstract repository for canonical records.

    Implementations provide local persistence (SQLite, etc.).
    """

    @abstractmethod
    def save_memory(self, record: MemoryRecord) -> None:
        ...

    @abstractmethod
    def save_task(self, record: TaskRecord) -> None:
        ...

    @abstractmethod
    def get_memory(self, record_id: str) -> MemoryRecord | None:
        ...

    @abstractmethod
    def get_task(self, record_id: str) -> TaskRecord | None:
        ...

    @abstractmethod
    def delete_memory(self, record_id: str) -> None:
        ...

    @abstractmethod
    def delete_task(self, record_id: str) -> None:
        ...

    @abstractmethod
    def list_memories(
        self,
        *,
        domain: str | None = None,
        status: MemoryStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        ...

    @abstractmethod
    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        project: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskRecord]:
        ...

    @abstractmethod
    def search_memories(self, query: str, **filters: Any) -> list[MemoryRecord]:
        ...

    @abstractmethod
    def save_conflict(self, conflict: ConflictRecord) -> None:
        ...

    @abstractmethod
    def get_conflict(self, conflict_id: str) -> ConflictRecord | None:
        ...

    @abstractmethod
    def get_conflicts(self) -> list[ConflictRecord]:
        ...


class OutboxRepository(ABC):
    """Abstract outbox repository for durable operation queue."""

    @abstractmethod
    def enqueue(self, operation: OutboxOperation) -> None:
        ...

    @abstractmethod
    def get_pending(self, limit: int = 50) -> list[OutboxOperation]:
        ...

    @abstractmethod
    def mark_syncing(self, operation_id: str) -> None:
        ...

    @abstractmethod
    def mark_synced(self, operation_id: str, backend_ref: BackendReference) -> None:
        ...

    @abstractmethod
    def mark_failed(
        self,
        operation_id: str,
        error_category: str,
        error_message: str,
        next_retry_at: datetime | None = None,
    ) -> None:
        ...

    @abstractmethod
    def mark_conflicted(self, operation_id: str, conflict: ConflictRecord) -> None:
        ...

    @abstractmethod
    def all(self) -> list[OutboxOperation]:
        ...

    @abstractmethod
    def get_by_idempotency_key(self, key: str) -> OutboxOperation | None:
        ...