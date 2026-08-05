"""Backend-neutral core for notion_brain.

This module provides the canonical domain models, ports, and service layer
that are independent of any specific storage backend.
"""

from __future__ import annotations

from .errors import (
    BackendError,
    BrainError,
    ConflictError,
    ConfigurationError,
    MigrationError,
    NotFoundError,
    PrivacyError,
    SyncError,
    ValidationError,
)
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
from .ports import (
    BackendCapabilities,
    SearchOptions,
    StorageBackend,
    SyncResult,
)
from .service import (
    MemoryService,
    OutboxRepository,
    PrivacyEngine,
    PrivacyPolicy,
    RecordRepository,
    ValidationEngine,
)

__all__ = [
    # Errors
    "BackendError",
    "BrainError",
    "ConflictError",
    "ConfigurationError",
    "MigrationError",
    "NotFoundError",
    "PrivacyError",
    "SyncError",
    "ValidationError",
    # Models
    "BackendReference",
    "ConflictRecord",
    "ConflictResolution",
    "MemoryKind",
    "MemoryRecord",
    "MemoryStatus",
    "OutboxAction",
    "OutboxOperation",
    "OutboxState",
    "Priority",
    "Record",
    "SyncCheckpoint",
    "TaskRecord",
    "TaskStatus",
    # Ports
    "BackendCapabilities",
    "SearchOptions",
    "StorageBackend",
    "SyncResult",
    # Service
    "MemoryService",
    "OutboxRepository",
    "PrivacyEngine",
    "PrivacyPolicy",
    "RecordRepository",
    "ValidationEngine",
]