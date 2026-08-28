# app/routers/projects.py
"""项目管理路由（Phase 3 重构：从 main.py 拆分）。"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

router = APIRouter(tags=["projects"])


@router.get("/api/projects")
async def front_api_list_projects(search: str = "", status: str = "", limit: int = 100):
    """前端项目列表。"""
    from app.projects.management import list_projects
    projects = list_projects(search=search, status=status, limit=limit)
    return ok({"projects": projects})


@router.post("/api/projects")
async def front_api_create_project(req: Request):
    """前端创建项目。"""
    from app.projects.management import create_project
    body = await req.json()
    item = create_project(
        name=body.get("name", "未命名项目"),
        description=body.get("description", ""),
        repo_url=body.get("repo_url", ""),
        language=body.get("language", "python"),
        path=body.get("path", ""),
    )
    return JSONResponse(item)


@router.get("/api/projects/{project_id}")
async def front_api_get_project(project_id: str):
    """前端获取项目详情。"""
    from app.projects.management import get_project
    item = get_project(project_id)
    if not item:
        return JSONResponse({"error": "项目不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/projects/{project_id}")
async def front_api_update_project(project_id: str, req: Request):
    """前端更新项目。"""
    from app.projects.management import update_project
    body = await req.json()
    item = update_project(project_id, **body)
    if not item:
        return JSONResponse({"error": "项目不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/projects/{project_id}")
async def front_api_delete_project(project_id: str):
    """前端删除项目。"""
    from app.projects.management import delete_project
    delete_project(project_id)
    return ok({"success": True})


@router.get("/api/projects/{project_id}/stats")
async def front_api_project_stats(project_id: str):
    """前端获取项目统计。"""
    from app.projects.management import get_project_stats
    return JSONResponse(get_project_stats(project_id))
