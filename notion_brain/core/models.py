"""Canonical domain models for the backend-neutral memory system.

These models define the stable internal representation used by the memory service,
storage backends, and synchronization coordinator. They are independent of any
specific backend (Notion, Obsidian, Markdown, etc.).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryKind(str, Enum):
    """Classification of a memory record."""

    NOTE = "note"
    FACT = "fact"
    DECISION = "decision"
    REFERENCE = "reference"
    PERSON = "person"
    PROJECT = "project"


class MemoryStatus(str, Enum):
    """Lifecycle status of a memory record."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    NEEDS_REVIEW = "needs_review"


class TaskStatus(str, Enum):
    """Lifecycle status of a task record."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Priority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class OutboxAction(str, Enum):
    """Type of outbox operation."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ARCHIVE = "archive"


class OutboxState(str, Enum):
    """State of an outbox operation."""

    QUEUED = "queued"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICTED = "conflicted"


class ConflictResolution(str, Enum):
    """How a conflict was or should be resolved."""

    KEEP_REMOTE = "keep_remote"
    APPLY_LOCAL = "apply_local"
    KEEP_BOTH = "keep_both"
    UNRESOLVED = "unresolved"


@dataclass(slots=True)
class MemoryRecord:
    """Canonical memory record — backend-neutral representation."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    body: str = ""
    kind: MemoryKind = MemoryKind.NOTE
    status: MemoryStatus = MemoryStatus.ACTIVE
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    source_type: str = "manual"
    source_reference: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Backend references (populated after sync)
    backend_refs: list["BackendReference"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            self.kind = MemoryKind(self.kind)
        if isinstance(self.status, str):
            self.status = MemoryStatus(self.status)
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.updated_at, str):
            self.updated_at = datetime.fromisoformat(self.updated_at)
        for i, ref in enumerate(self.backend_refs):
            if isinstance(ref, dict):
                self.backend_refs[i] = BackendReference(**ref)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage/transport."""
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "kind": self.kind.value,
            "status": self.status.value,
            "tags": self.tags,
            "entities": self.entities,
            "source_type": self.source_type,
            "source_reference": self.source_reference,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "backend_refs": [ref.to_dict() for ref in self.backend_refs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        """Deserialize from dictionary."""
        refs = data.pop("backend_refs", [])
        record = cls(**data)
        record.backend_refs = [BackendReference.from_dict(r) for r in refs]
        return record


@dataclass(slots=True)
class TaskRecord:
    """Canonical task record — extends memory fields with task-specific attributes."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    body: str = ""
    kind: MemoryKind = MemoryKind.NOTE
    status: MemoryStatus = MemoryStatus.ACTIVE
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    source_type: str = "manual"
    source_reference: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Task-specific fields
    priority: Priority = Priority.MEDIUM
    due_date: datetime | None = None
    project: str = ""
    task_status: TaskStatus = TaskStatus.TODO
    completed_at: datetime | None = None

    # Backend references (populated after sync)
    backend_refs: list["BackendReference"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.kind, str):
            self.kind = MemoryKind(self.kind)
        if isinstance(self.status, str):
            self.status = MemoryStatus(self.status)
        if isinstance(self.priority, str):
            self.priority = Priority(self.priority)
        if isinstance(self.task_status, str):
            self.task_status = TaskStatus(self.task_status)
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.updated_at, str):
            self.updated_at = datetime.fromisoformat(self.updated_at)
        if isinstance(self.due_date, str):
            self.due_date = datetime.fromisoformat(self.due_date)
        if isinstance(self.completed_at, str):
            self.completed_at = datetime.fromisoformat(self.completed_at)
        for i, ref in enumerate(self.backend_refs):
            if isinstance(ref, dict):
                self.backend_refs[i] = BackendReference(**ref)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage/transport."""
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "kind": self.kind.value,
            "status": self.status.value,
            "tags": self.tags,
            "entities": self.entities,
            "source_type": self.source_type,
            "source_reference": self.source_reference,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "priority": self.priority.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "project": self.project,
            "task_status": self.task_status.value,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "backend_refs": [ref.to_dict() for ref in self.backend_refs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskRecord":
        """Deserialize from dictionary."""
        refs = data.pop("backend_refs", [])
        record = cls(**data)
        record.backend_refs = [BackendReference.from_dict(r) for r in refs]
        return record


@dataclass(slots=True)
class BackendReference:
    """Reference to a record in a specific backend."""

    backend_name: str
    remote_id: str
    remote_revision: str
    last_synced_at: datetime
    remote_url: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.last_synced_at, str):
            self.last_synced_at = datetime.fromisoformat(self.last_synced_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_name": self.backend_name,
            "remote_id": self.remote_id,
            "remote_revision": self.remote_revision,
            "last_synced_at": self.last_synced_at.isoformat(),
            "remote_url": self.remote_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendReference":
        return cls(**data)


@dataclass(slots=True)
class OutboxOperation:
    """Durable outbox operation for synchronization."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    record_id: str = ""
    record_type: str = "memory"  # "memory" or "task"
    backend_name: str = ""
    action: OutboxAction = OutboxAction.CREATE
    idempotency_key: str = ""
    attempt_count: int = 0
    next_retry_at: datetime | None = None
    state: OutboxState = OutboxState.QUEUED
    error_category: str | None = None  # "retryable", "permanent", "conflict"
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if isinstance(self.action, str):
            self.action = OutboxAction(self.action)
        if isinstance(self.state, str):
            self.state = OutboxState(self.state)
        if isinstance(self.next_retry_at, str) and self.next_retry_at:
            self.next_retry_at = datetime.fromisoformat(self.next_retry_at)
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.updated_at, str):
            self.updated_at = datetime.fromisoformat(self.updated_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "record_id": self.record_id,
            "record_type": self.record_type,
            "backend_name": self.backend_name,
            "action": self.action.value,
            "idempotency_key": self.idempotency_key,
            "attempt_count": self.attempt_count,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "state": self.state.value,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutboxOperation":
        return cls(**data)


@dataclass(slots=True)
class ConflictRecord:
    """Record of a synchronization conflict between local and remote changes."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    record_id: str = ""
    record_type: str = "memory"
    backend_name: str = ""
    local_expected_revision: str = ""
    current_remote_revision: str = ""
    operation_id: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)
    resolution: ConflictResolution = ConflictResolution.UNRESOLVED
    resolved_at: datetime | None = None
    local_version: dict[str, Any] | None = None  # preserved local record
    remote_version: dict[str, Any] | None = None  # preserved remote record

    def __post_init__(self) -> None:
        if isinstance(self.resolution, str):
            self.resolution = ConflictResolution(self.resolution)
        if isinstance(self.detected_at, str):
            self.detected_at = datetime.fromisoformat(self.detected_at)
        if isinstance(self.resolved_at, str) and self.resolved_at:
            self.resolved_at = datetime.fromisoformat(self.resolved_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "record_id": self.record_id,
            "record_type": self.record_type,
            "backend_name": self.backend_name,
            "local_expected_revision": self.local_expected_revision,
            "current_remote_revision": self.current_remote_revision,
            "operation_id": self.operation_id,
            "detected_at": self.detected_at.isoformat(),
            "resolution": self.resolution.value,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "local_version": self.local_version,
            "remote_version": self.remote_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConflictRecord":
        return cls(**data)


@dataclass(slots=True)
class SyncCheckpoint:
    """Synchronization checkpoint for tracking remote change import progress."""

    backend_name: str
    profile_id: str
    cursor: str | None = None
    last_imported_at: datetime | None = None
    last_successful_sync_at: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.last_imported_at, str) and self.last_imported_at:
            self.last_imported_at = datetime.fromisoformat(self.last_imported_at)
        if isinstance(self.last_successful_sync_at, str) and self.last_successful_sync_at:
            self.last_successful_sync_at = datetime.fromisoformat(self.last_successful_sync_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_name": self.backend_name,
            "profile_id": self.profile_id,
            "cursor": self.cursor,
            "last_imported_at": self.last_imported_at.isoformat() if self.last_imported_at else None,
            "last_successful_sync_at": self.last_successful_sync_at.isoformat() if self.last_successful_sync_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncCheckpoint":
        return cls(**data)


# Type aliases for union operations
Record = MemoryRecord | TaskRecord