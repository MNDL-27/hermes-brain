"""Backward-compatibility converters between legacy and canonical models.

This module provides thin conversion functions that allow existing code
using ``BrainEntry`` and Notion-specific payloads to interoperate with
the new backend-neutral core models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

try:
    from ..core.models import MemoryKind, MemoryRecord, MemoryStatus, Priority, TaskRecord, TaskStatus
except ImportError:
    from notion_brain.core.models import MemoryKind, MemoryRecord, MemoryStatus, Priority, TaskRecord, TaskStatus


def brain_entry_to_memory_record(entry: Any) -> MemoryRecord:
    """Convert a legacy BrainEntry to a canonical MemoryRecord.

    Args:
        entry: A BrainEntry instance (from schema.BrainEntry).

    Returns:
        A canonical MemoryRecord with equivalent fields.
    """
    # Map legacy kind strings to MemoryKind enum
    kind_map = {
        "note": MemoryKind.NOTE,
        "fact": MemoryKind.FACT,
        "decision": MemoryKind.DECISION,
        "reference": MemoryKind.REFERENCE,
        "person": MemoryKind.PERSON,
        "project": MemoryKind.PROJECT,
        "task": MemoryKind.NOTE,  # tasks use TaskRecord
        "preference": MemoryKind.NOTE,
        "source_note": MemoryKind.REFERENCE,
        "draft": MemoryKind.NOTE,
        "lesson": MemoryKind.FACT,
        "reminder": MemoryKind.NOTE,
    }

    # Map legacy status strings to MemoryStatus enum
    status_map = {
        "active": MemoryStatus.ACTIVE,
        "done": MemoryStatus.ACTIVE,  # "done" is valid for memories
        "draft": MemoryStatus.ACTIVE,
        "published": MemoryStatus.ACTIVE,
        "archived": MemoryStatus.ARCHIVED,
        "needs_review": MemoryStatus.NEEDS_REVIEW,
    }

    kind_str = getattr(entry, "kind", "note") or "note"
    status_str = getattr(entry, "status", "active") or "active"

    return MemoryRecord(
        id="",  # Will be assigned on save
        title=getattr(entry, "title", "Untitled") or "Untitled",
        body=getattr(entry, "content", "") or "",
        kind=kind_map.get(kind_str, MemoryKind.NOTE),
        status=status_map.get(status_str, MemoryStatus.ACTIVE),
        tags=list(getattr(entry, "tags", []) or []),
        entities=list(getattr(entry, "entities", []) or []),
        source_type="manual",
        source_reference=getattr(entry, "source_session_id", "") or "",
        metadata=dict(getattr(entry, "metadata", {}) or {}),
    )


def memory_record_to_brain_entry(record: MemoryRecord) -> Any:
    """Convert a canonical MemoryRecord to a legacy BrainEntry.

    Args:
        record: A canonical MemoryRecord.

    Returns:
        A BrainEntry instance (from schema.BrainEntry).
    """
    from ..schema import BrainEntry

    # Map MemoryKind to legacy kind strings
    kind_map = {
        MemoryKind.NOTE: "note",
        MemoryKind.FACT: "fact",
        MemoryKind.DECISION: "decision",
        MemoryKind.REFERENCE: "reference",
        MemoryKind.PERSON: "person",
        MemoryKind.PROJECT: "project",
    }

    # Map MemoryStatus to legacy status strings
    status_map = {
        MemoryStatus.ACTIVE: "active",
        MemoryStatus.ARCHIVED: "archived",
        MemoryStatus.NEEDS_REVIEW: "needs_review",
    }

    return BrainEntry(
        domain="memory",  # Domain is inferred from tags/context
        title=record.title,
        content=record.body,
        kind=kind_map.get(record.kind, "note"),
        status=status_map.get(record.status, "active"),
        tags=record.tags,
        entities=record.entities,
        source_session_id=record.source_reference,
        metadata=record.metadata,
    )


def brain_entry_to_task_record(entry: Any) -> TaskRecord:
    """Convert a legacy BrainEntry (task) to a canonical TaskRecord.

    Args:
        entry: A BrainEntry instance with task-specific metadata.

    Returns:
        A canonical TaskRecord with equivalent fields.
    """
    # Map legacy priority strings to Priority enum
    priority_map = {
        "urgent": Priority.URGENT,
        "high": Priority.HIGH,
        "medium": Priority.MEDIUM,
        "low": Priority.LOW,
    }

    # Map legacy status strings to TaskStatus enum
    task_status_map = {
        "todo": TaskStatus.TODO,
        "in_progress": TaskStatus.IN_PROGRESS,
        "done": TaskStatus.DONE,
        "blocked": TaskStatus.BLOCKED,
        "active": TaskStatus.TODO,
    }

    metadata = dict(getattr(entry, "metadata", {}) or {})
    priority_str = metadata.get("priority", "medium") or "medium"
    task_status_str = getattr(entry, "status", "active") or "active"

    due_date = None
    due_str = metadata.get("due")
    if due_str:
        try:
            due_date = datetime.fromisoformat(due_str)
        except ValueError:
            pass

    completed_at = None
    completed_str = metadata.get("completed_at")
    if completed_str:
        try:
            completed_at = datetime.fromisoformat(completed_str)
        except ValueError:
            pass

    return TaskRecord(
        id="",
        title=getattr(entry, "title", "Untitled") or "Untitled",
        body=getattr(entry, "content", "") or "",
        kind=MemoryKind.PROJECT if metadata.get("is_project") else MemoryKind.NOTE,
        status=MemoryStatus.ACTIVE,
        tags=list(getattr(entry, "tags", []) or []),
        entities=list(getattr(entry, "entities", []) or []),
        source_type="manual",
        source_reference=getattr(entry, "source_session_id", "") or "",
        priority=priority_map.get(priority_str, Priority.MEDIUM),
        due_date=due_date,
        project=metadata.get("project", "") or "",
        task_status=task_status_map.get(task_status_str, TaskStatus.TODO),
        completed_at=completed_at,
        metadata=metadata,
    )


def task_record_to_brain_entry(record: TaskRecord) -> Any:
    """Convert a canonical TaskRecord to a legacy BrainEntry.

    Args:
        record: A canonical TaskRecord.

    Returns:
        A BrainEntry instance (from schema.BrainEntry).
    """
    from ..schema import BrainEntry

    # Map Priority to legacy priority strings
    priority_map = {
        Priority.URGENT: "urgent",
        Priority.HIGH: "high",
        Priority.MEDIUM: "medium",
        Priority.LOW: "low",
    }

    # Map TaskStatus to legacy status strings
    task_status_map = {
        TaskStatus.TODO: "active",
        TaskStatus.IN_PROGRESS: "active",
        TaskStatus.DONE: "done",
        TaskStatus.BLOCKED: "active",
    }

    metadata = {
        "priority": priority_map.get(record.priority, "medium"),
        "due": record.due_date.isoformat() if record.due_date else None,
        "project": record.project,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
    }
    metadata.update(record.metadata)

    return BrainEntry(
        domain="daily_work",
        title=record.title,
        content=record.body,
        kind="task",
        status=task_status_map.get(record.task_status, "active"),
        tags=record.tags,
        entities=record.entities,
        source_session_id=record.source_reference,
        metadata=metadata,
    )


def notion_result_to_memory_record(notion_entry: dict[str, Any]) -> MemoryRecord:
    """Convert a raw Notion API result to a canonical MemoryRecord.

    This is used by the Notion backend adapter to convert API responses
    into canonical records.

    Args:
        notion_entry: A dict from the Notion API (page object).

    Returns:
        A canonical MemoryRecord.
    """
    props = notion_entry.get("properties", {})
    title = notion_entry.get("title", "Untitled")

    # Extract content from properties
    content = ""
    for key, val in props.items():
        if isinstance(val, dict):
            t = val.get("type", "")
            if t in ("title", "rich_text"):
                texts = val.get(t) or []
                if key == "title":
                    title = "".join(v.get("text", {}).get("content", "") for v in texts)
                else:
                    content = "".join(v.get("text", {}).get("content", "") for v in texts)

    # Extract tags
    tags = []
    for key, val in props.items():
        if isinstance(val, dict) and val.get("type") == "multi_select":
            ms = val.get("multi_select") or []
            tags.extend(s.get("name", "") for s in ms if isinstance(s, dict))

    # Extract entities
    entities = []
    for key, val in props.items():
        if isinstance(val, dict) and val.get("type") == "multi_select" and key.lower() in ("entities", "people"):
            ms = val.get("multi_select") or []
            entities.extend(s.get("name", "") for s in ms if isinstance(s, dict))

    # Extract status
    status = MemoryStatus.ACTIVE
    for key, val in props.items():
        if isinstance(val, dict) and val.get("type") == "status":
            s = val.get("status")
            if isinstance(s, dict):
                status_str = s.get("name", "active")
                status = {
                    "active": MemoryStatus.ACTIVE,
                    "done": MemoryStatus.ACTIVE,
                    "archived": MemoryStatus.ARCHIVED,
                    "needs review": MemoryStatus.NEEDS_REVIEW,
                }.get(status_str.lower(), MemoryStatus.ACTIVE)

    # Extract kind
    kind = MemoryKind.NOTE
    for key, val in props.items():
        if isinstance(val, dict) and val.get("type") == "select" and key.lower() == "kind":
            kind_str = val.get("select", {}).get("name", "note")
            kind = {
                "note": MemoryKind.NOTE,
                "fact": MemoryKind.FACT,
                "decision": MemoryKind.DECISION,
                "reference": MemoryKind.REFERENCE,
                "person": MemoryKind.PERSON,
                "project": MemoryKind.PROJECT,
            }.get(kind_str.lower(), MemoryKind.NOTE)

    return MemoryRecord(
        id=notion_entry.get("id", ""),
        title=title,
        body=content,
        kind=kind,
        status=status,
        tags=tags,
        entities=entities,
        source_type="notion",
        source_reference=notion_entry.get("id", ""),
    )


def memory_record_to_notion_properties(record: MemoryRecord) -> dict[str, Any]:
    """Convert a canonical MemoryRecord to Notion page properties.

    This is used by the Notion backend adapter to convert canonical records
    into Notion API payloads.

    Args:
        record: A canonical MemoryRecord.

    Returns:
        A dict of Notion page properties.
    """
    from ..store import multi_select_property, rich_text_property, select_property, status_property, title_property

    props: dict[str, Any] = {
        "title": title_property(record.title),
    }

    # Map MemoryKind to legacy kind string
    kind_map = {
        MemoryKind.NOTE: "note",
        MemoryKind.FACT: "fact",
        MemoryKind.DECISION: "decision",
        MemoryKind.REFERENCE: "reference",
        MemoryKind.PERSON: "person",
        MemoryKind.PROJECT: "project",
    }

    # Map MemoryStatus to legacy status string
    status_map = {
        MemoryStatus.ACTIVE: "active",
        MemoryStatus.ARCHIVED: "archived",
        MemoryStatus.NEEDS_REVIEW: "needs_review",
    }

    props["Kind"] = select_property(kind_map.get(record.kind, "note"))
    props["Status"] = status_property(status_map.get(record.status, "active"))
    props["Content"] = rich_text_property(record.body)

    if record.tags:
        props["Tags"] = multi_select_property(record.tags)
    if record.entities:
        props["Entities"] = multi_select_property(record.entities)

    return props


def memory_record_to_notion_task_properties(record: TaskRecord) -> dict[str, Any]:
    """Convert a canonical TaskRecord to Notion page properties.

    Args:
        record: A canonical TaskRecord.

    Returns:
        A dict of Notion page properties for a task.
    """
    from ..store import multi_select_property, rich_text_property, select_property, status_property, title_property

    props: dict[str, Any] = {
        "title": title_property(record.title),
    }

    # Map Priority to legacy priority string
    priority_map = {
        "urgent": "urgent",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }

    # Map TaskStatus to legacy status string
    task_status_map = {
        TaskStatus.TODO: "active",
        TaskStatus.IN_PROGRESS: "active",
        TaskStatus.DONE: "done",
        TaskStatus.BLOCKED: "active",
    }

    props["Kind"] = select_property("task")
    props["Status"] = status_property(task_status_map.get(record.task_status, "active"))
    props["Priority"] = select_property(priority_map.get(record.priority.value, "medium"))
    props["Content"] = rich_text_property(record.body)

    if record.tags:
        props["Tags"] = multi_select_property(record.tags)
    if record.entities:
        props["Entities"] = multi_select_property(record.entities)
    if record.project:
        props["Project"] = select_property(record.project)
    if record.due_date:
        from ..store import date_property

        props["Due Date"] = date_property(record.due_date.isoformat())

    return props