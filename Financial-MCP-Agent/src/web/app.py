"""股票分析 Agent 系统的 FastAPI 入口。"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from src.services.query_parser import parse_stock_target
from src.tools.mcp_config import MCP_SERVER_PATH
from src.utils.environment import configure_deepseek_environment
from src.web.models import AnalysisEvent, TaskSnapshot, TaskStatus
from src.web.task_manager import TaskCapacityError, TaskManager


EXAMPLES = [
    {
        "label": "贵州茅台",
        "code": "600519",
        "query": "分析贵州茅台 600519 的投资价值，关注中长期风险",
    },
    {
        "label": "宁德时代",
        "code": "300750",
        "query": "分析宁德时代 300750 的基本面、估值与行业风险",
    },
    {
        "label": "中国平安",
        "code": "601318",
        "query": "分析中国平安 601318 的长期投资价值",
    },
]
WEB_DIST_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

load_dotenv(ENV_FILE, override=False)
configure_deepseek_environment()


class AnalysisRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


def _event_payload(event: AnalysisEvent) -> str:
    data = json.dumps(asdict(event), ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.id}\nevent: {event.type}\ndata: {data}\n\n"


def _snapshot_payload(snapshot: TaskSnapshot) -> dict:
    payload = {
        "task_id": snapshot.task_id,
        "query": snapshot.query,
        "status": snapshot.status.value,
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
        "target": snapshot.target,
        "report_markdown": snapshot.report_markdown,
        "report_path": snapshot.report_path,
        "report_download_url": None,
        "error": snapshot.error,
        "events": [asdict(event) for event in snapshot.events],
    }
    if snapshot.status is TaskStatus.COMPLETED and snapshot.report_markdown:
        payload["report_download_url"] = (
            f"/api/analyses/{snapshot.task_id}/report"
        )
    return payload


def create_app(
    manager: TaskManager | None = None,
    *,
    heartbeat_interval: float = 15.0,
) -> FastAPI:
    task_manager = manager or TaskManager()
    api = FastAPI(title="股票分析 Agent 系统", version="1.0.0")
    api.state.task_manager = task_manager

    @api.get("/api/health")
    async def health():
        configure_deepseek_environment()
        return {
            "web": {"status": "online"},
            "model": {
                "configured": bool(os.getenv("OPENAI_COMPATIBLE_API_KEY")),
                "model": os.getenv("OPENAI_COMPATIBLE_MODEL"),
            },
            "mcp": {
                "configured": Path(MCP_SERVER_PATH).is_file(),
                "server": "A 股 MCP Server",
            },
        }

    @api.get("/api/examples")
    async def examples():
        return EXAMPLES

    @api.post("/api/analyses", status_code=status.HTTP_202_ACCEPTED)
    async def create_analysis(request: AnalysisRequest):
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=422, detail="分析内容不能为空。")
        target = parse_stock_target(query)
        if not target.company_name and not target.raw_code:
            raise HTTPException(
                status_code=422,
                detail="无法识别股票，请输入股票名称或六位股票代码。",
            )
        try:
            task = await task_manager.create(query)
        except TaskCapacityError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        return _snapshot_payload(task_manager.snapshot(task.task_id))

    @api.get("/api/analyses/{task_id}")
    async def get_analysis(task_id: str):
        try:
            snapshot = task_manager.snapshot(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="分析任务不存在。") from exc
        return _snapshot_payload(snapshot)

    @api.get("/api/analyses/{task_id}/events")
    async def analysis_events(
        task_id: str,
        after: int = Query(default=0, ge=0),
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ):
        try:
            task_manager.snapshot(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="分析任务不存在。") from exc

        cursor = after
        if last_event_id and last_event_id.isdigit():
            cursor = max(cursor, int(last_event_id))

        async def generate():
            yield ": connected\n\n"
            event_cursor = cursor
            while True:
                snapshot = task_manager.snapshot(task_id)
                pending = [
                    event for event in snapshot.events if event.id > event_cursor
                ]
                for event in pending:
                    event_cursor = event.id
                    yield _event_payload(event)
                if snapshot.status in {TaskStatus.COMPLETED, TaskStatus.FAILED}:
                    break
                updated = await task_manager.wait_for_update(
                    task_id,
                    after_id=event_cursor,
                    timeout=heartbeat_interval,
                )
                if not updated:
                    heartbeat = json.dumps(
                        {"type": "heartbeat", "task_id": task_id},
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    yield f"event: heartbeat\ndata: {heartbeat}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @api.get("/api/analyses/{task_id}/report")
    async def download_report(task_id: str):
        try:
            snapshot = task_manager.snapshot(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="分析任务不存在。") from exc
        if snapshot.status is not TaskStatus.COMPLETED or not snapshot.report_markdown:
            raise HTTPException(status_code=409, detail="报告尚未生成完成。")

        filename = f"stock-analysis-{task_id}.md"
        return Response(
            content=snapshot.report_markdown,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    index_file = WEB_DIST_DIR / "index.html"
    assets_dir = WEB_DIST_DIR / "assets"
    if index_file.is_file():
        if assets_dir.is_dir():
            api.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")

        @api.get("/{full_path:path}", include_in_schema=False)
        async def web_app(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")
            requested = (WEB_DIST_DIR / full_path).resolve()
            if (
                full_path
                and requested.is_file()
                and WEB_DIST_DIR.resolve() in requested.parents
            ):
                return FileResponse(requested)
            return FileResponse(index_file)

    return api


app = create_app()
