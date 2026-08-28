# app/routers/scripts.py
"""脚本健康度路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
from typing import Optional, List, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

from pydantic import BaseModel

router = APIRouter(tags=["scripts"])


class ScriptRequest(BaseModel):
    name: str
    file_path: str = ""
    framework: str = ""
    description: str = ""
    locators: Optional[List[Dict]] = None


class ScriptUpdate(BaseModel):
    name: Optional[str] = None
    file_path: Optional[str] = None
    framework: Optional[str] = None
    description: Optional[str] = None
    locators: Optional[List[Dict]] = None
    status: Optional[str] = None


class ExecutionRecord(BaseModel):
    success: bool = True
    duration: float = 0.0
    error_type: str = ""
    error_message: str = ""
    locator_failures: Optional[List[Dict]] = None


class LocatorEvalRequest(BaseModel):
    strategy: str = ""
    selector: str = ""


@router.get("/api/scripts")
async def api_list_scripts(
    status: Optional[str] = None,
    framework: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """列出所有脚本。"""
    from app.scripthealth.monitor import list_scripts
    scripts = list_scripts(status=status, framework=framework, search=search, limit=limit, offset=offset)
    return ok({"scripts": scripts, "total": len(scripts)})


@router.post("/api/scripts")
async def api_create_script(req: ScriptRequest):
    """创建新脚本。"""
    from app.scripthealth.monitor import create_script
    script = create_script(
        name=req.name,
        file_path=req.file_path,
        framework=req.framework,
        description=req.description,
        locators=req.locators,
    )
    return JSONResponse(script)


@router.get("/api/scripts/{script_id}")
async def api_get_script(script_id: str):
    """获取脚本详情。"""
    from app.scripthealth.monitor import get_script
    script = get_script(script_id)
    if not script:
        return JSONResponse({"error": f"脚本 {script_id} 不存在"}, status_code=404)
    return JSONResponse(script)


@router.put("/api/scripts/{script_id}")
async def api_update_script(script_id: str, req: ScriptUpdate):
    """更新脚本。"""
    from app.scripthealth.monitor import update_script
    script = update_script(script_id, req.model_dump(exclude_none=True))
    if not script:
        return JSONResponse({"error": f"脚本 {script_id} 不存在"}, status_code=404)
    return JSONResponse(script)


@router.delete("/api/scripts/{script_id}")
async def api_delete_script(script_id: str):
    """删除脚本。"""
    from app.scripthealth.monitor import delete_script
    deleted = delete_script(script_id)
    if not deleted:
        return JSONResponse({"error": f"脚本 {script_id} 不存在"}, status_code=404)
    return ok({"deleted": True, "script_id": script_id})


@router.post("/api/scripts/{script_id}/executions")
async def api_record_script_execution(script_id: str, req: ExecutionRecord):
    """记录一次脚本执行。"""
    from app.scripthealth.monitor import record_execution
    result = record_execution(
        script_id=script_id,
        success=req.success,
        duration=req.duration,
        error_type=req.error_type,
        error_message=req.error_message,
        locator_failures=req.locator_failures,
    )
    return JSONResponse(result)


@router.post("/api/scripts/{script_id}/repair/{locator_name}")
async def api_repair_locator(script_id: str, locator_name: str):
    """自动修复定位器。"""
    from app.scripthealth.monitor import auto_repair_locator
    result = auto_repair_locator(script_id, locator_name)
    return JSONResponse(result)


@router.get("/api/scripts/{script_id}/executions")
async def api_list_script_executions(script_id: str, limit: int = 20):
    """列出脚本执行历史。"""
    from app.scripthealth.monitor import list_executions
    executions = list_executions(script_id, limit=limit)
    return ok({"executions": executions, "total": len(executions)})


@router.post("/api/locators/evaluate")
async def api_evaluate_locator(req: LocatorEvalRequest):
    """评估定位器策略。"""
    from app.scripthealth.monitor import evaluate_selector, recommend_stable_strategy
    evaluation = evaluate_selector(req.strategy, req.selector)
    recommendation = recommend_stable_strategy(req.selector, req.strategy)
    return ok({"evaluation": evaluation, "recommendation": recommendation})


@router.get("/api/scripthealth/stats")
async def api_script_health_stats():
    """脚本健康度整体统计。"""
    from app.scripthealth.monitor import get_stats
    return JSONResponse(await asyncio.to_thread(get_stats))
