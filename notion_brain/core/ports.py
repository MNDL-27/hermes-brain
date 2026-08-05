"""Backend-neutral port interfaces for the memory system.

This module defines the contracts that storage backends must implement.
The core depends only on these interfaces, not on any specific backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class BackendCapabilities:
    """Declares what a storage backend can do.

    Used by the memory service and sync coordinator to adapt behavior
    without coupling to backend-specific details.
    """

    supports_full_text_search: bool = True
    supports_pagination: bool = True
    supports_remote_changes: bool = False
    supports_revisions: bool = False
    supports_idempotent_writes: bool = False
    supports_soft_delete: bool = False
    max_page_size: int = 100
    default_page_size: int = 20
    rate_limit_seconds: float = 0.0  # minimum seconds between requests


@dataclass(slots=True)
class SearchOptions:
    """Options for searching records in a backend."""

    query: str
    database_id: str | None = None
    limit: int = 20
    offset: int = 0
    filters: dict[str, Any] = field(default_factory=dict)
    sort_by: str | None = None
    sort_order: str = "desc"  # "asc" or "desc"


@dataclass(slots=True)
class SyncResult:
    """Result of a synchronization operation."""

    created: int = 0
    updated: int = 0
    deleted: int = 0
    conflicts: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    checkpoint: Any | None = None  # backend-specific cursor


class StorageBackend(ABC):
    """Contract that all storage backends must implement.

    The core memory service depends only on this interface.
    Backend-specific details (Notion properties, Obsidian vaults, etc.)
    stay inside the implementation.
    """

    # ─── Identity ──────────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this backend (e.g. 'notion', 'obsidian')."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> BackendCapabilities:
        """Declare what this backend can do."""
        ...

    # ─── Lifecycle ─────────────────────────────────────────────────────

    @abstractmethod
    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the backend with configuration.

        Args:
            config: Backend-specific configuration dict.

        Raises:
            ConfigurationError: If configuration is missing or invalid.
        """
        ...

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return backend health status.

        Returns:
            Dict with 'status' (ok/degraded/error), 'message', and backend-specific details.
        """
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Clean up resources."""
        ...

    # ─── CRUD Operations ───────────────────────────────────────────────

    @abstractmethod
    def create(self, record: Any) -> Any:
        """Create a new record in the backend.

        Args:
            record: A canonical MemoryRecord or TaskRecord.

        Returns:
            A BackendReference with the remote ID and revision.

        Raises:
            BackendError: If creation fails.
        """
        ...

    @abstractmethod
    def update(self, record: Any, reference: Any) -> Any:
        """Update an existing record.

        Args:
            record: The updated canonical record.
            reference: The BackendReference from a previous create/update.

        Returns:
            Updated BackendReference with new revision.

        Raises:
            NotFoundError: If the remote record no longer exists.
            ConflictError: If the revision does not match.
            BackendError: If update fails.
        """
        ...

    @abstractmethod
    def delete(self, record_id: str, reference: Any) -> None:
        """Delete a record from the backend.

        Args:
            record_id: The canonical record ID.
            reference: The BackendReference.

        Raises:
            NotFoundError: If the remote record no longer exists.
            BackendError: If deletion fails.
        """
        ...

    @abstractmethod
    def get(self, record_id: str, reference: Any) -> Any:
        """Retrieve a single record by its backend reference.

        Args:
            record_id: The canonical record ID.
            reference: The BackendReference.

        Returns:
            The canonical record as retrieved from the backend.

        Raises:
            NotFoundError: If the record does not exist.
            BackendError: If retrieval fails.
        """
        ...

    # ─── Search ────────────────────────────────────────────────────────

    @abstractmethod
    def search(self, options: SearchOptions) -> list[Any]:
        """Search for records matching the query.

        Args:
            options: SearchOptions with query, filters, pagination.

        Returns:
            List of canonical records matching the search.

        Raises:
            BackendError: If search fails.
        """
        ...

    # ─── Synchronization ───────────────────────────────────────────────

    @abstractmethod
    def get_changes(self, checkpoint: Any) -> tuple[list[Any], Any]:
        """Retrieve changes since the last checkpoint.

        Args:
            checkpoint: The last known SyncCheckpoint (or None for full import).

        Returns:
            Tuple of (list of changed canonical records, new checkpoint).

        Raises:
            BackendError: If change import fails.
        """
        ...

    @abstractmethod
    def get_checkpoint(self) -> Any:
        """Return the current synchronization checkpoint.

        Returns:
            A SyncCheckpoint for this backend/profile.
        """
        ...

    # ─── Migration ─────────────────────────────────────────────────────

    @abstractmethod
    def plan_migration(self, target_schema: dict[str, Any]) -> dict[str, Any]:
        """Plan a migration to a new schema without making changes.

        Args:
            target_schema: The target schema definition.

        Returns:
            A migration plan dict with 'actions', 'affected_records', 'warnings'.
        """
        ...

    @abstractmethod
    def apply_migration(self, plan: dict[str, Any]) -> SyncResult:
        """Apply a previously planned migration.

        Args:
            plan: The migration plan from plan_migration().

        Returns:
            SyncResult with counts of migrated records.

        Raises:
            MigrationError: If migration fails.
        """
        ...

    # ─── Backend References ──────────────────────────────────────────────

    @abstractmethod
    def get_remote_url(self, reference: Any) -> str | None:
        """Return a human-readable URL for a backend reference.

        Args:
            reference: A BackendReference.

        Returns:
            URL string or None if not supported.
        """
        ...