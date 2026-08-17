"""Web API 与后台任务共享的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AnalysisEvent:
    id: int
    type: str
    task_id: str
    timestamp: str
    payload: dict[str, Any]


@dataclass(slots=True)
class AnalysisTask:
    task_id: str
    query: str
    status: TaskStatus
    created_at: str
    updated_at: str
    events: list[AnalysisEvent] = field(default_factory=list)
    report_markdown: str | None = None
    report_path: str | None = None
    target: dict[str, Any] | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    task_id: str
    query: str
    status: TaskStatus
    created_at: str
    updated_at: str
    events: tuple[AnalysisEvent, ...]
    report_markdown: str | None
    report_path: str | None
    target: dict[str, Any] | None
    error: str | None
