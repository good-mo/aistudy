# app/routers/insights.py
"""测试洞察路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

router = APIRouter(tags=["insights"])


@router.get("/api/insights/value")
async def api_insights_value():
    """价值量化：缺陷价值 / 覆盖价值 / 避免事故估算。"""
    from app.insights.value import summarize_value, estimate_incident_avoidance
    value = summarize_value()
    incidents = estimate_incident_avoidance()
    return ok({"value": value, "incident_avoidance": incidents})


@router.get("/api/insights/trace")
async def api_list_trace(
    file_path: Optional[str] = None,
    result: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """列出测试执行追溯记录。"""
    from app.insights.trace import list_runs, stats, ATTRIBUTIONS
    runs = list_runs(file_path=file_path, result=result, limit=limit, offset=offset)
    return ok({
        "runs": runs,
        "stats": stats(),
        "total": len(runs),
        "attributions": ATTRIBUTIONS,
    })


@router.post("/api/insights/trace")
async def api_record_trace(req: Request):
    """手动记录一次执行追溯。"""
    from app.insights.trace import record_run
    body = await req.json()
    rec = record_run(
        file_path=body.get("file_path", ""),
        result=body.get("result", "unknown"),
        passed_count=int(body.get("passed_count", 0)),
        failed_count=int(body.get("failed_count", 0)),
        error_count=int(body.get("error_count", 0)),
        coverage=float(body.get("coverage", 0) or 0),
        attribution=body.get("attribution", ""),
        note=body.get("note", ""),
        created_by=body.get("created_by", "manual"),
    )
    return JSONResponse(rec)


@router.get("/api/insights/trace/prove")
async def api_prove_coverage(file_path: str):
    """自证清白：针对某文件调出历史执行记录。"""
    from app.insights.trace import prove_coverage
    return JSONResponse(prove_coverage(file_path))


@router.get("/api/insights/risk")
async def api_risk(project_path: str = ""):
    """高风险模块预警。"""
    from app.insights.risk import assess_risk
    if project_path:
        from app.projects.manager import scan_project
        scan = await asyncio.to_thread(scan_project, project_path)
        result = await asyncio.to_thread(assess_risk, source_files=scan["files"])
    else:
        from app.cases.repository import list_cases
        cases = await asyncio.to_thread(list_cases, limit=200)
        files = []
        for c in cases:
            fp = c.get("file_path", "")
            if fp:
                files.append({"relative_path": fp, "source_code": c.get("source_code", "")})
        result = await asyncio.to_thread(assess_risk, source_files=files)
    return JSONResponse(result)


@router.post("/api/insights/lowcode")
async def api_lowcode(req: Request):
    """低代码生成：用自然语言描述测试意图。"""
    from app.insights.lowcode import generate_from_description
    body = await req.json()
    description = (body.get("description") or "").strip()
    if not description:
        return JSONResponse({"error": "请描述你想测试什么"}, status_code=400)
    result = generate_from_description(description)
    return JSONResponse(result)


@router.get("/api/insights/skill-path")
async def api_skill_path():
    """职业发展路径。"""
    from app.insights.lowcode import skill_path
    return JSONResponse(skill_path())
