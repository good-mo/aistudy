# app/routers/environments.py
"""环境管理路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

router = APIRouter(tags=["environments"])


@router.get("/api/environments")
async def api_list_environments(
    search: str = "",
    status: str = "",
    env_type: str = "",
):
    """列出环境。"""
    from app.environment.manager import list_environments
    envs = list_environments(search=search, status=status, env_type=env_type)
    return ok({"environments": envs, "total": len(envs)})


@router.post("/api/environments")
async def api_register_environment(req: Request):
    """注册新环境。"""
    from app.environment.manager import register_environment
    body = await req.json()
    env = register_environment(**body)
    return JSONResponse(env)


@router.get("/api/environments/{env_id}")
async def api_get_environment(env_id: str):
    """获取环境详情。"""
    from app.environment.manager import get_environment
    env = get_environment(env_id)
    if not env:
        return JSONResponse({"error": "环境不存在"}, status_code=404)
    return JSONResponse(env)


@router.put("/api/environments/{env_id}")
async def api_update_environment(env_id: str, req: Request):
    """更新环境。"""
    from app.environment.manager import update_environment
    body = await req.json()
    env = update_environment(env_id, **body)
    if not env:
        return JSONResponse({"error": "环境不存在"}, status_code=404)
    return JSONResponse(env)


@router.delete("/api/environments/{env_id}")
async def api_delete_environment(env_id: str):
    """删除环境。"""
    from app.environment.manager import delete_environment
    ok = delete_environment(env_id)
    return ok({"success": ok})


@router.post("/api/environments/{env_id}/launch")
async def api_launch_environment(env_id: str):
    """启动环境（Docker 容器）。"""
    from app.environment.manager import launch_environment
    result = await asyncio.to_thread(launch_environment, env_id)
    return JSONResponse(result)


@router.post("/api/environments/{env_id}/stop")
async def api_stop_environment(env_id: str):
    """停止环境。"""
    from app.environment.manager import stop_environment
    result = await asyncio.to_thread(stop_environment, env_id)
    return JSONResponse(result)


@router.post("/api/environments/{env_id}/health")
async def api_check_env_health(env_id: str):
    """检查环境健康状态。"""
    from app.environment.manager import check_environment_health
    result = await asyncio.to_thread(check_environment_health, env_id)
    return JSONResponse(result)


@router.post("/api/environments/check-all")
async def api_check_all_envs():
    """检查所有环境健康状态。"""
    from app.environment.manager import check_all_environments
    result = await asyncio.to_thread(check_all_environments)
    return JSONResponse(result)


@router.get("/api/environments/trash/list")
async def api_list_env_trash():
    """列出回收站中的环境。"""
    from app.environment.manager import list_trash_environments
    items = list_trash_environments()
    return ok({"items": items, "total": len(items)})


@router.post("/api/environments/{env_id}/restore")
async def api_restore_environment(env_id: str):
    """从回收站恢复环境。"""
    from app.environment.manager import restore_environment
    ok = restore_environment(env_id)
    return ok({"success": ok})


@router.delete("/api/environments/{env_id}")
async def api_purge_environment(env_id: str):
    """彻底删除环境。"""
    from app.environment.manager import delete_environment
    ok = delete_environment(env_id, permanent=True)
    return ok({"success": ok})
