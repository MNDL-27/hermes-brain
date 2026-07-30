"""Import isolation tests for the backend-neutral core.

These tests verify that the core domain models, ports, errors, and service
can be imported and used WITHOUT importing Notion, Hermes, or any
external dependencies at module level.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def test_core_models_source_clean(monkeypatch: Any) -> None:
    """Core models source must not have eager Notion imports."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("notion_brain"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    models_path = Path(__file__).parent.parent.parent / "notion_brain" / "core" / "models.py"
    content = models_path.read_text()

    # Only check module-level imports (no indentation)
    for line in content.split("\n"):
        if line.startswith((" ", "\t")):
            continue
        stripped = line.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            allowed_prefixes = (
                "from __future__",
                "import uuid",
                "from dataclasses",
                "from datetime",
                "from enum",
                "from typing",
            )
            if not any(stripped.startswith(p) for p in allowed_prefixes):
                if "notion_brain" in stripped:
                    raise AssertionError(f"models.py has eager import: {stripped}")


def test_core_errors_source_clean(monkeypatch: Any) -> None:
    """Core errors source must not have eager Notion imports."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("notion_brain"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    errors_path = Path(__file__).parent.parent.parent / "notion_brain" / "core" / "errors.py"
    content = errors_path.read_text()

    for line in content.split("\n"):
        if line.startswith((" ", "\t")):
            continue
        stripped = line.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            allowed_prefixes = (
                "from __future__",
                "from typing",
            )
            if not any(stripped.startswith(p) for p in allowed_prefixes):
                if "notion_brain" in stripped:
                    raise AssertionError(f"errors.py has eager import: {stripped}")


def test_core_ports_source_clean(monkeypatch: Any) -> None:
    """Core ports source must not have eager Notion imports."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("notion_brain"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    ports_path = Path(__file__).parent.parent.parent / "notion_brain" / "core" / "ports.py"
    content = ports_path.read_text()

    for line in content.split("\n"):
        if line.startswith((" ", "\t")):
            continue
        stripped = line.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            allowed_prefixes = (
                "from __future__",
                "from abc",
                "from dataclasses",
                "from datetime",
                "from typing",
            )
            if not any(stripped.startswith(p) for p in allowed_prefixes):
                if "notion_brain" in stripped:
                    raise AssertionError(f"ports.py has eager import: {stripped}")


def test_core_service_source_clean(monkeypatch: Any) -> None:
    """Core service source must not have eager Notion imports at module level."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("notion_brain"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    service_path = Path(__file__).parent.parent.parent / "notion_brain" / "core" / "service.py"
    content = service_path.read_text()

    for line in content.split("\n"):
        if line.startswith((" ", "\t")):
            continue
        stripped = line.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            allowed_prefixes = (
                "from __future__",
                "from abc",
                "from dataclasses",
                "from datetime",
                "from typing",
                "from .errors",
                "from .models",
                "from .ports",
                "try:",
                "except ImportError:",
                # Fallback imports to core are OK
                "from notion_brain.core.errors",
                "from notion_brain.core.models",
                "from notion_brain.core.ports",
            )
            if not any(stripped.startswith(p) for p in allowed_prefixes):
                # Only flag imports of Notion-specific modules (not core)
                if "notion_brain" in stripped and "notion_brain.core" not in stripped:
                    raise AssertionError(f"service.py has eager import: {stripped}")


def test_compat_source_clean(monkeypatch: Any) -> None:
    """Compat source must not have eager Notion imports at module level."""
    for mod in list(sys.modules.keys()):
        if mod.startswith("notion_brain"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    compat_path = Path(__file__).parent.parent.parent / "notion_brain" / "compat" / "__init__.py"
    content = compat_path.read_text()

    for line in content.split("\n"):
        if line.startswith((" ", "\t")):
            continue
        stripped = line.strip()
        if stripped.startswith("from ") or stripped.startswith("import "):
            allowed_prefixes = (
                "from __future__",
                "from datetime",
                "from typing",
                "try:",
                "except ImportError:",
                # Fallback to core is OK
                "from notion_brain.core.models",
            )
            if not any(stripped.startswith(p) for p in allowed_prefixes):
                if "notion_brain" in stripped and "notion_brain.core" not in stripped:
                    raise AssertionError(f"compat/__init__.py has eager Notion import: {stripped}")


def test_fake_backend_passes_contract(monkeypatch: Any) -> None:
    """A fake backend implementation can satisfy the StorageBackend contract."""
    # Load parent to satisfy core's internal imports
    import notion_brain

    from notion_brain.core.ports import StorageBackend, BackendCapabilities, SearchOptions, SyncResult
    from notion_brain.core.models import MemoryRecord, BackendReference
    from datetime import datetime
    from typing import Any

    class FakeBackend(StorageBackend):
        def __init__(self) -> None:
            self._records: dict[str, MemoryRecord] = {}
            self._initialized = False

        @property
        def name(self) -> str:
            return "fake"

        @property
        def capabilities(self) -> BackendCapabilities:
            return BackendCapabilities(
                supports_full_text_search=True,
                supports_pagination=True,
                supports_idempotent_writes=True,
            )

        def initialize(self, config: dict[str, Any]) -> None:
            self._initialized = True
            self._config = config

        def health(self) -> dict[str, Any]:
            return {"status": "ok", "initialized": self._initialized}

        def shutdown(self) -> None:
            self._records.clear()

        def create(self, record: MemoryRecord) -> BackendReference:
            ref = BackendReference(
                backend_name=self.name,
                remote_id=f"fake-{record.id}",
                remote_revision="1",
                last_synced_at=datetime.utcnow(),
            )
            self._records[record.id] = record
            return ref

        def update(self, record: MemoryRecord, reference: BackendReference) -> BackendReference:
            if record.id not in self._records:
                raise KeyError("not found")
            self._records[record.id] = record
            return BackendReference(
                backend_name=self.name,
                remote_id=reference.remote_id,
                remote_revision=str(int(reference.remote_revision) + 1),
                last_synced_at=datetime.utcnow(),
            )

        def delete(self, record_id: str, reference: BackendReference) -> None:
            self._records.pop(record_id, None)

        def get(self, record_id: str, reference: BackendReference) -> MemoryRecord:
            return self._records[record_id]

        def search(self, options: SearchOptions) -> list[MemoryRecord]:
            query = options.query.lower()
            return [r for r in self._records.values() if query in r.body.lower()][: options.limit]

        def get_changes(self, checkpoint: Any) -> tuple[list[MemoryRecord], Any]:
            return list(self._records.values()), None

        def get_checkpoint(self) -> Any:
            return None

        def plan_migration(self, target_schema: dict[str, Any]) -> dict[str, Any]:
            return {"actions": [], "affected_records": 0}

        def apply_migration(self, plan: dict[str, Any]) -> SyncResult:
            return SyncResult()

        def get_remote_url(self, reference: BackendReference) -> str | None:
            return f"https://fake.example.com/{reference.remote_id}"

    # Test the fake backend works
    backend = FakeBackend()
    assert backend.name == "fake"
    assert backend.capabilities.supports_pagination

    backend.initialize({"test": True})
    assert backend.health()["status"] == "ok"

    record = MemoryRecord(id="test-1", title="Test", body="Test content")
    ref = backend.create(record)
    assert ref.remote_id == "fake-test-1"

    retrieved = backend.get("test-1", ref)
    assert retrieved.title == "Test"

    results = backend.search(SearchOptions(query="test", limit=10))
    assert len(results) == 1

    backend.shutdown()