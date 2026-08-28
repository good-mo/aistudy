# app/routers/environments_extra.py
"""环境管理补充路由（回收站相关）。

注意：/api/environments/trash/list 和 /api/environments/{env_id}/restore
已在 app/routers/environments.py 中定义，此处仅保留补充的回收站操作。
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

router = APIRouter(tags=["environments-extra"])


@router.post("/api/environments/{env_id}/trash")
async def api_trash_environment(env_id: str):
    """将环境移入回收站。"""
    from app.environment.manager import trash_environment
    result = trash_environment(env_id)
    if not result:
        return JSONResponse({"error": f"环境 {env_id} 不存在"}, status_code=404)
    return ok({"trashed": True, "env_id": env_id})


@router.delete("/api/environments/trash/{env_id}")
async def api_purge_environment(env_id: str):
    """从回收站彻底删除环境。"""
    from app.environment.manager import purge_environment
    result = purge_environment(env_id)
    if not result:
        return JSONResponse({"error": f"环境 {env_id} 不存在"}, status_code=404)
    return ok({"purged": True, "env_id": env_id})
