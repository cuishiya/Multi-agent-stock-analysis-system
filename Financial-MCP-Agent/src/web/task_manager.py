"""Web 服务使用的内存分析任务管理器。"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import suppress
from datetime import datetime
from typing import Any, AsyncIterator, Awaitable, Callable

from src.services.analysis_service import AnalysisResult, run_analysis
from src.utils.execution_logger import (
    finalize_execution_logger,
    initialize_execution_logger,
)
from src.web.models import AnalysisEvent, AnalysisTask, TaskSnapshot, TaskStatus


Runner = Callable[
    [str, Callable[[str, dict[str, Any]], Awaitable[None]]],
    Awaitable[AnalysisResult],
]
_TERMINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED}


class TaskCapacityError(RuntimeError):
    """服务中的排队任务已达到安全上限。"""


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_message(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return message[:500]


class TaskManager:
    def __init__(
        self,
        runner: Runner | None = None,
        *,
        max_pending_tasks: int = 4,
        max_stored_tasks: int = 50,
        task_timeout_seconds: float = 900.0,
    ):
        if max_pending_tasks < 1 or max_stored_tasks < max_pending_tasks:
            raise ValueError("任务容量配置无效")
        if task_timeout_seconds <= 0:
            raise ValueError("任务超时时间必须大于 0")
        self._runner = runner or run_analysis
        self._max_pending_tasks = max_pending_tasks
        self._max_stored_tasks = max_stored_tasks
        self._task_timeout_seconds = task_timeout_seconds
        self._execution_slot = asyncio.Semaphore(1)
        self._tasks: dict[str, AnalysisTask] = {}
        self._conditions: dict[str, asyncio.Condition] = {}
        self._workers: set[asyncio.Task[Any]] = set()

    async def create(self, query: str) -> AnalysisTask:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("分析内容不能为空。")
        self._prune_terminal_tasks()
        pending = sum(
            task.status not in _TERMINAL_STATUSES for task in self._tasks.values()
        )
        if pending >= self._max_pending_tasks:
            raise TaskCapacityError("当前分析任务较多，请稍后再试。")

        task_id = uuid.uuid4().hex[:12]
        created_at = _now_iso()
        task = AnalysisTask(
            task_id=task_id,
            query=normalized_query,
            status=TaskStatus.QUEUED,
            created_at=created_at,
            updated_at=created_at,
        )
        self._tasks[task_id] = task
        self._conditions[task_id] = asyncio.Condition()
        await self._append_event(task_id, "task_created", {"query": normalized_query})

        worker = asyncio.create_task(self._execute(task_id))
        self._workers.add(worker)
        worker.add_done_callback(self._workers.discard)
        return task

    def _prune_terminal_tasks(self) -> None:
        while len(self._tasks) >= self._max_stored_tasks:
            removable_id = next(
                (
                    task_id
                    for task_id, task in self._tasks.items()
                    if task.status in _TERMINAL_STATUSES
                ),
                None,
            )
            if removable_id is None:
                raise TaskCapacityError("任务存储已满，请稍后再试。")
            self._tasks.pop(removable_id, None)
            self._conditions.pop(removable_id, None)

    def snapshot(self, task_id: str) -> TaskSnapshot:
        task = self._tasks[task_id]
        return TaskSnapshot(
            task_id=task.task_id,
            query=task.query,
            status=task.status,
            created_at=task.created_at,
            updated_at=task.updated_at,
            events=tuple(task.events),
            report_markdown=task.report_markdown,
            report_path=task.report_path,
            target=dict(task.target) if task.target else None,
            error=task.error,
        )

    async def stream(
        self,
        task_id: str,
        *,
        after_id: int = 0,
    ) -> AsyncIterator[AnalysisEvent]:
        task = self._tasks[task_id]
        condition = self._conditions[task_id]
        cursor = max(after_id, 0)

        while True:
            pending = [event for event in task.events if event.id > cursor]
            if pending:
                for event in pending:
                    cursor = event.id
                    yield event
                continue
            if task.status in _TERMINAL_STATUSES:
                break
            async with condition:
                await condition.wait()

    async def wait_for_update(
        self,
        task_id: str,
        *,
        after_id: int,
        timeout: float,
    ) -> bool:
        """等待新事件或终态；超时返回 False，供 SSE 发送心跳。"""

        task = self._tasks[task_id]
        condition = self._conditions[task_id]
        async with condition:
            if any(event.id > after_id for event in task.events):
                return True
            if task.status in _TERMINAL_STATUSES:
                return True
            try:
                await asyncio.wait_for(condition.wait(), timeout=timeout)
            except TimeoutError:
                return False
        return True

    async def _append_event(
        self,
        task_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> AnalysisEvent:
        task = self._tasks[task_id]
        timestamp = _now_iso()
        event = AnalysisEvent(
            id=len(task.events) + 1,
            type=event_type,
            task_id=task_id,
            timestamp=timestamp,
            payload=payload,
        )
        task.events.append(event)
        if event_type == "report_delta":
            delta = payload.get("delta")
            if isinstance(delta, str) and delta:
                task.report_markdown = (task.report_markdown or "") + delta
        task.updated_at = timestamp
        condition = self._conditions[task_id]
        async with condition:
            condition.notify_all()
        return event

    async def _execute(self, task_id: str) -> None:
        task = self._tasks[task_id]
        async with self._execution_slot:
            task.status = TaskStatus.RUNNING
            task.updated_at = _now_iso()
            logger_initialized = False
            execution_succeeded = False
            execution_error: str | None = None

            async def emit(event_type: str, payload: dict[str, Any]) -> None:
                await self._append_event(task_id, event_type, payload)

            try:
                initialize_execution_logger()
                logger_initialized = True
                async with asyncio.timeout(self._task_timeout_seconds):
                    result = await self._runner(task.query, emit)
                task.report_markdown = result.report_markdown
                task.report_path = result.report_path
                task.target = {
                    "company_name": result.target.company_name,
                    "stock_code": result.target.raw_code,
                    "market_code": result.target.market_code,
                }
                task.status = TaskStatus.COMPLETED
                execution_succeeded = True
                if not task.events or task.events[-1].type != "report_completed":
                    await self._append_event(
                        task_id,
                        "report_completed",
                        {
                            "report_path": result.report_path,
                            "report_length": len(result.report_markdown),
                        },
                    )
            except TimeoutError:
                message = (
                    f"分析执行超时（上限 {self._task_timeout_seconds:g} 秒），"
                    "请稍后重试。"
                )
                execution_error = message
                task.error = message
                task.status = TaskStatus.FAILED
                await self._append_event(task_id, "task_failed", {"message": message})
            except Exception as exc:
                message = _safe_message(exc)
                execution_error = message
                task.error = message
                task.status = TaskStatus.FAILED
                await self._append_event(task_id, "task_failed", {"message": message})
            finally:
                if logger_initialized:
                    with suppress(Exception):
                        finalize_execution_logger(
                            success=execution_succeeded,
                            error=execution_error,
                        )
                task.updated_at = _now_iso()
                condition = self._conditions[task_id]
                async with condition:
                    condition.notify_all()
