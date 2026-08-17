"""Web 服务使用的内存分析任务管理器。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Awaitable, Callable

from src.services.analysis_service import AnalysisResult, run_analysis
from src.web.models import AnalysisEvent, AnalysisTask, TaskSnapshot, TaskStatus


Runner = Callable[
    [str, Callable[[str, dict[str, Any]], Awaitable[None]]],
    Awaitable[AnalysisResult],
]
_TERMINAL_STATUSES = {TaskStatus.COMPLETED, TaskStatus.FAILED}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_message(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return message[:500]


class TaskManager:
    def __init__(self, runner: Runner | None = None):
        self._runner = runner or run_analysis
        self._tasks: dict[str, AnalysisTask] = {}
        self._conditions: dict[str, asyncio.Condition] = {}
        self._workers: set[asyncio.Task[Any]] = set()

    async def create(self, query: str) -> AnalysisTask:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("分析内容不能为空。")

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
        task.updated_at = timestamp
        condition = self._conditions[task_id]
        async with condition:
            condition.notify_all()
        return event

    async def _execute(self, task_id: str) -> None:
        task = self._tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.updated_at = _now_iso()

        async def emit(event_type: str, payload: dict[str, Any]) -> None:
            await self._append_event(task_id, event_type, payload)

        try:
            result = await self._runner(task.query, emit)
            task.report_markdown = result.report_markdown
            task.report_path = result.report_path
            task.target = {
                "company_name": result.target.company_name,
                "stock_code": result.target.raw_code,
                "market_code": result.target.market_code,
            }
            task.status = TaskStatus.COMPLETED
            if not task.events or task.events[-1].type != "report_completed":
                await self._append_event(
                    task_id,
                    "report_completed",
                    {
                        "report_path": result.report_path,
                        "report_length": len(result.report_markdown),
                    },
                )
        except Exception as exc:
            message = _safe_message(exc)
            task.error = message
            task.status = TaskStatus.FAILED
            await self._append_event(task_id, "task_failed", {"message": message})
        finally:
            task.updated_at = _now_iso()
            condition = self._conditions[task_id]
            async with condition:
                condition.notify_all()
