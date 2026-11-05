"""Shared progress data models and in-memory progress management."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Any
from uuid import uuid4


class ProgressStatus(str, Enum):
    """Lifecycle states shared by all progress items."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    STOPPED = "stopped"


_TERMINAL_STATUSES = {
    ProgressStatus.SUCCESS,
    ProgressStatus.FAILED,
    ProgressStatus.SKIPPED,
    ProgressStatus.STOPPED,
}


@dataclass(slots=True)
class ProgressInfo:
    """A single progress item; parent_id enables nested progress trees."""

    name: str
    category: str
    id: str = field(default_factory=lambda: uuid4().hex)
    parent_id: str | None = None
    account: str | None = None
    status: ProgressStatus = ProgressStatus.PENDING
    current: int = 0
    total: int = 1
    message: str = ""
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ProgressInfo.name không được để trống.")
        if not self.category.strip():
            raise ValueError("ProgressInfo.category không được để trống.")
        self.status = ProgressStatus(self.status)
        self._validate_counts()

    def _validate_counts(self) -> None:
        if self.current < 0 or self.total < 0:
            raise ValueError("current và total phải >= 0.")
        if self.total and self.current > self.total:
            raise ValueError("current không được lớn hơn total.")


class ProgressManager:
    """Thread-safe in-memory registry for progress items."""

    def __init__(self) -> None:
        self._items: dict[str, ProgressInfo] = {}
        self._lock = RLock()

    def add(self, item: ProgressInfo) -> ProgressInfo:
        """Register an item. A parent must be registered before its children."""
        with self._lock:
            if item.id in self._items:
                raise ValueError(f"Progress id đã tồn tại: {item.id}")
            if item.parent_id is not None and item.parent_id not in self._items:
                raise KeyError(f"Không tìm thấy progress cha: {item.parent_id}")
            self._items[item.id] = item
            return item

    def update(self, progress_id: str, **changes: Any) -> ProgressInfo:
        """Update an item and maintain lifecycle timestamps."""
        allowed = {
            "name", "category", "account", "status", "current", "total",
            "message", "error",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise TypeError(f"Trường ProgressInfo không được cập nhật: {', '.join(sorted(unknown))}")

        with self._lock:
            item = self._require(progress_id)
            previous_status = item.status

            if "status" in changes:
                changes["status"] = ProgressStatus(changes["status"])

            # Validate a candidate first so a bad update cannot partially mutate
            # the live progress record.
            candidate = replace(item, **changes)
            if not candidate.name.strip():
                raise ValueError("ProgressInfo.name không được để trống.")
            if not candidate.category.strip():
                raise ValueError("ProgressInfo.category không được để trống.")
            candidate._validate_counts()

            for key, value in changes.items():
                setattr(item, key, value)

            if item.status == ProgressStatus.RUNNING and previous_status != ProgressStatus.RUNNING:
                if item.started_at is None:
                    item.started_at = datetime.now()
                item.finished_at = None
            elif item.status in _TERMINAL_STATUSES:
                item.finished_at = item.finished_at or datetime.now()

            return item

    def get(self, progress_id: str) -> ProgressInfo | None:
        with self._lock:
            return self._items.get(progress_id)

    def get_children(self, parent_id: str) -> list[ProgressInfo]:
        with self._lock:
            return [
                item for item in self._items.values()
                if item.parent_id == parent_id
            ]

    def get_all(self) -> list[ProgressInfo]:
        with self._lock:
            return list(self._items.values())

    def reset(self) -> None:
        with self._lock:
            self._items.clear()

    def _require(self, progress_id: str) -> ProgressInfo:
        try:
            return self._items[progress_id]
        except KeyError:
            raise KeyError(f"Không tìm thấy progress: {progress_id}") from None
