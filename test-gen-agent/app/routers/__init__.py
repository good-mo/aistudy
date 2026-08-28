# app/routers/__init__.py
"""路由层：按业务域拆分的 FastAPI 路由（Phase 3 目标架构）。

每个路由文件对应一个业务域，替代 main.py 中的内联路由。
迁移完成前，main.py 中的内联路由仍然有效（向后兼容）。
"""
from app.routers.cases import router as cases_router
from app.routers.defects import router as defects_router
from app.routers.apitest import router as apitest_router
from app.routers.projects import router as projects_router
from app.routers.environments import router as environments_router
from app.routers.reports import router as reports_router
from app.routers.insights import router as insights_router
from app.routers.generation import router as generation_router
from app.routers.runs import router as runs_router
from app.routers.scripts import router as scripts_router
from app.routers.projects_scan import router as projects_scan_router
from app.routers.datafactory import router as datafactory_router
from app.routers.system import router as system_router
from app.routers.frontend import router as frontend_router
from app.routers.environments_extra import router as environments_extra_router

__all__ = [
    "cases_router",
    "defects_router",
    "apitest_router",
    "projects_router",
    "environments_router",
    "reports_router",
    "insights_router",
    "generation_router",
    "runs_router",
    "scripts_router",
    "projects_scan_router",
    "datafactory_router",
    "system_router",
    "frontend_router",
    "environments_extra_router",
]
