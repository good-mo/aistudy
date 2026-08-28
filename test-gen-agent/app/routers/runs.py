# app/routers/runs.py
"""运行记录路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

router = APIRouter(tags=["runs"])


@router.get("/api/runs")
async def api_list_runs(
    file_path: Optional[str] = None,
    source: Optional[str] = None,
    passed: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """列出所有运行记录。"""
    from app.runs.repository import list_run_records
    records = list_run_records(
        file_path=file_path, source=source, passed=passed,
        search=search, limit=limit, offset=offset,
    )
    return ok({"records": records, "total": len(records)})


@router.get("/api/runs/stats")
async def api_run_stats():
    """运行记录统计。"""
    from app.runs.repository import get_run_stats
    return JSONResponse(await asyncio.to_thread(get_run_stats))


@router.get("/api/runs/{record_id}")
async def api_get_run(record_id: str):
    """获取单条运行记录详情。"""
    from app.runs.repository import get_run_record
    record = get_run_record(record_id)
    if not record:
        return JSONResponse({"error": f"记录 {record_id} 不存在"}, status_code=404)
    return JSONResponse(record)


@router.delete("/api/runs")
async def api_clear_runs(source: Optional[str] = None):
    """清空运行记录。"""
    from app.runs.repository import clear_run_records
    cleared = clear_run_records(source=source)
    return ok({"cleared": cleared})
