"""Domain errors for the backend-neutral memory system.

These errors are raised by the memory service, backends, and sync coordinator.
They are independent of any specific backend implementation.
"""

from __future__ import annotations


class BrainError(Exception):
    """Base error for all notion_brain domain errors."""

    def __init__(self, message: str, *, category: str = "unknown", safe: bool = True) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.safe = safe  # True means safe to log without redaction


class ValidationError(BrainError):
    """Raised when a record fails validation or normalization."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message, category="validation", safe=True)
        self.field = field


class BackendError(BrainError):
    """Raised when a storage backend operation fails."""

    def __init__(
        self,
        message: str,
        *,
        backend_name: str | None = None,
        retryable: bool = False,
        original: Exception | None = None,
    ) -> None:
        super().__init__(message, category="backend", safe=False)
        self.backend_name = backend_name
        self.retryable = retryable
        self.original = original


class NotFoundError(BrainError):
    """Raised when a requested record does not exist."""

    def __init__(self, message: str, *, record_id: str | None = None, record_type: str | None = None) -> None:
        super().__init__(message, category="not_found", safe=True)
        self.record_id = record_id
        self.record_type = record_type


class ConflictError(BrainError):
    """Raised when a synchronization conflict is detected."""

    def __init__(
        self,
        message: str,
        *,
        record_id: str | None = None,
        local_revision: str | None = None,
        remote_revision: str | None = None,
    ) -> None:
        super().__init__(message, category="conflict", safe=True)
        self.record_id = record_id
        self.local_revision = local_revision
        self.remote_revision = remote_revision


class PrivacyError(BrainError):
    """Raised when a privacy policy violation is detected."""

    def __init__(self, message: str, *, policy: str | None = None) -> None:
        super().__init__(message, category="privacy", safe=False)
        self.policy = policy


class SyncError(BrainError):
    """Raised when a synchronization operation fails."""

    def __init__(
        self,
        message: str,
        *,
        backend_name: str | None = None,
        operation_id: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message, category="sync", safe=False)
        self.backend_name = backend_name
        self.operation_id = operation_id
        self.retryable = retryable


class ConfigurationError(BrainError):
    """Raised when configuration is missing or invalid."""

    def __init__(self, message: str, *, key: str | None = None) -> None:
        super().__init__(message, category="configuration", safe=True)
        self.key = key


class MigrationError(BrainError):
    """Raised when a migration operation fails."""

    def __init__(
        self,
        message: str,
        *,
        from_version: str | None = None,
        to_version: str | None = None,
    ) -> None:
        super().__init__(message, category="migration", safe=False)
        self.from_version = from_version
        self.to_version = to_version