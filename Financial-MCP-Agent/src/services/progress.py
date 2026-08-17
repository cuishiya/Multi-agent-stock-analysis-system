"""将当前分析任务的运行事件传递给深层 Agent 调用。"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any, Awaitable, Callable


EventSink = Callable[[str, dict[str, Any]], Awaitable[None]]
_event_sink: ContextVar[EventSink | None] = ContextVar(
    "stock_analysis_event_sink",
    default=None,
)


def bind_event_sink(sink: EventSink) -> Token[EventSink | None]:
    return _event_sink.set(sink)


def reset_event_sink(token: Token[EventSink | None]) -> None:
    _event_sink.reset(token)


async def emit_runtime_event(event_type: str, payload: dict[str, Any]) -> None:
    sink = _event_sink.get()
    if sink is not None:
        await sink(event_type, payload)
