# app/main.py
"""应用装配入口（Phase 3 重构：仅做应用装配，不含路由定义）。

所有业务路由已拆分至 app/routers/ 和 app/adapters/domains/ 目录。
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭钩子。"""
    logger.info("🚀 应用启动中…")
    # 预热 RSA 密钥：登录接口首次调用无需现场生成，避免首次登录卡顿
    from app.auth.store import _ensure_rsa_keys
    _ensure_rsa_keys()
    async with AsyncSqliteSaver.from_conn_string(settings.checkpoint_db) as checkpointer:
        from app.graph.builder import build_graph
        app.state.graph = build_graph(checkpointer=checkpointer)
        from app.tasks.manager import manager
        manager.start(num_workers=settings.task_workers)
        app.state.task_manager = manager
        logger.info("✅ 应用启动完成")
        yield
        try:
            await manager.stop()
        except Exception as e:
            logger.warning("停止任务队列失败: %s", e)
        logger.info("👋 应用关闭")


def _generate_unique_operation_id(route):
    """生成唯一 operation ID，避免同函数名路由冲突。"""
    path = route.path.replace('/', '_').replace('{', '').replace('}', '')
    method = ','.join(sorted(route.methods or []))
    return f"{method.lower()}_{path}_v1"


app = FastAPI(
    title="Test Generation Agent Toolkit",
    description="基于 FastAPI + LangGraph 的测试用例生成 Agent，开箱即用",
    version="0.2.0",
    lifespan=lifespan,
    generate_unique_id_function=_generate_unique_operation_id,
)

# ── 统一异常处理 / 中间件 ──────────────────────────────────
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middleware
register_exception_handlers(app)
register_middleware(app)

# ── MeterSphere 前端 /front/ 前缀路径重写 ────────────────────
# 使用 BaseHTTPMiddleware 确保在路由匹配前进行路径重写
from starlette.middleware.base import BaseHTTPMiddleware

class FrontPrefixMiddleware(BaseHTTPMiddleware):
    """将 /front/ 前缀的请求路径重写为 /api/ 或根路径。"""
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path.startswith("/front/"):
            new_path = "/" + path[len("/front/"):]
            from starlette.requests import Request as SR
            scope = request.scope.copy()
            scope["path"] = new_path
            new_request = SR(scope, receive=request._receive)
            return await call_next(new_request)
        elif path == "/front":
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/")
        return await call_next(request)

app.add_middleware(FrontPrefixMiddleware)


# ── 认证与基础模块路由 ────────────────────────────────────
from app.auth.router import router as auth_router
from app.test_plan.router import router as test_plan_router
from app.test_plan.router_dashboard import dashboard_router
from app.test_plan.router_system import system_router
from app.file_mgmt.router import router as file_router
from app.routers.missing_admin import router as missing_admin_router

app.include_router(auth_router)
app.include_router(test_plan_router)
app.include_router(dashboard_router)
app.include_router(system_router)
app.include_router(file_router)
app.include_router(missing_admin_router)

# ── 业务域适配路由（按业务域拆分）─────────────────────────
from app.adapters.domains import (
    functional_cases_router,
    defects_adapter_router,
    api_testing_adapter_router,
    case_reviews_router,
    project_adapter_router,
    system_adapter_router,
    reports_adapter_router,
    debug_adapter_router,
    ai_config_router,
    attachment_router,
    integrations_router,
    notifications_router,
    plugins_router,
    test_resources_router,
    websocket_adapter_router,
    auth_adapter_router,
    platform_router,
    test_router,
    other_router,
)

for r in [
    functional_cases_router,
    defects_adapter_router,
    api_testing_adapter_router,
    case_reviews_router,
    project_adapter_router,
    system_adapter_router,
    reports_adapter_router,
    debug_adapter_router,
    ai_config_router,
    attachment_router,
    integrations_router,
    notifications_router,
    plugins_router,
    test_resources_router,
    websocket_adapter_router,
    auth_adapter_router,
    platform_router,
    test_router,
    other_router,
]:
    app.include_router(r)

# ── 业务域路由（Phase 3 拆分）─────────────────────────────
from app.routers import (
    cases_router, defects_router, apitest_router, projects_router,
    environments_router, reports_router, insights_router,
    generation_router, runs_router, scripts_router,
    projects_scan_router, datafactory_router, system_router,
    frontend_router, environments_extra_router,
)

for r in [
    cases_router, defects_router, apitest_router, projects_router,
    environments_router, reports_router, insights_router,
    generation_router, runs_router, scripts_router,
    projects_scan_router, datafactory_router, system_router,
    frontend_router, environments_extra_router,
]:
    app.include_router(r)


# ── 前端缺失的额外 API 路由补充 ─────────────────────────────
# 占位接口统一返回 501 Not Implemented，明确标注「未实现」，
# 避免前端误以为功能可用。待功能真实实现后替换。
from fastapi import APIRouter as _APIRouter
from fastapi.responses import JSONResponse as _JSONResponse
_extra_router = _APIRouter(tags=["extra-frontend-apis"])

def _not_implemented(message: str = "功能尚未实现") -> _JSONResponse:
    """返回 501 Not Implemented。"""
    return _JSONResponse(
        {"code": 501, "message": message, "data": None},
        status_code=501,
    )

@_extra_router.get("/notification/un-read/{project_id}")
async def _extra_notification_unread(project_id: str):
    """未读通知（带项目ID）。"""
    return _not_implemented("通知功能尚未实现")

@_extra_router.get("/project/application/case/related/info/{project_id}")
async def _extra_case_related_info(project_id: str):
    """用例关联信息（带项目ID）。"""
    return _not_implemented("用例关联功能尚未实现")

@_extra_router.get("/project/application/bug/platform/{org_id}")
async def _extra_bug_platform(org_id: str):
    """缺陷平台配置。"""
    return _not_implemented("缺陷平台功能尚未实现")

@_extra_router.get("/project/application/bug/platform/info/{project_id}")
async def _extra_bug_platform_info(project_id: str):
    """缺陷平台信息。"""
    return _not_implemented("缺陷平台信息尚未实现")

@_extra_router.get("/project/application/bug/sync/info/{project_id}")
async def _extra_bug_sync_info(project_id: str):
    """缺陷同步信息。"""
    return _not_implemented("缺陷同步功能尚未实现")

@_extra_router.get("/project/application/case/platform/{project_id}")
async def _extra_case_platform(project_id: str):
    """用例平台。"""
    return _not_implemented("用例平台功能尚未实现")

@_extra_router.get("/project/application/case/platform/info/{project_id}")
async def _extra_case_platform_info(project_id: str):
    """用例平台信息。"""
    return _not_implemented("用例平台信息尚未实现")

@_extra_router.get("/project/application/module-setting/{project_id}")
async def _extra_module_setting(project_id: str):
    """模块设置。"""
    return _not_implemented("模块设置功能尚未实现")

@_extra_router.get("/project/application/{project_id}")
async def _extra_project_application(project_id: str):
    """项目应用配置。"""
    return _not_implemented("项目应用配置尚未实现")

@_extra_router.post("/project/application/update/{project_id}")
async def _extra_project_application_update(project_id: str, request: Request):
    """更新项目应用配置。"""
    try:
        await request.json()
    except Exception:
        pass
    return _not_implemented("项目应用配置更新尚未实现")

@_extra_router.post("/project/application/update/bug/sync/{project_id}")
async def _extra_project_bug_sync_update(project_id: str, request: Request):
    """更新缺陷同步。"""
    try:
        await request.json()
    except Exception:
        pass
    return _not_implemented("缺陷同步更新尚未实现")

@_extra_router.post("/project/application/update/case/related/{project_id}")
async def _extra_project_case_related_update(project_id: str, request: Request):
    """更新用例关联。"""
    try:
        await request.json()
    except Exception:
        pass
    return _not_implemented("用例关联更新尚未实现")

@_extra_router.post("/project/application/validate/{project_id}")
async def _extra_project_application_validate(project_id: str, request: Request):
    """验证项目应用。"""
    try:
        await request.json()
    except Exception:
        pass
    return _not_implemented("项目应用验证尚未实现")

app.include_router(_extra_router)

# ── 静态文件 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "..", "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "..", "templates")

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ── MeterSphere 前端（构建产物）服务 ─────────────────────────
# 当仓库中存在 frontend/dist 构建产物时，通过 /ms/ 前缀对外提供。
MS_FRONTEND_DIST = os.path.join(BASE_DIR, "..", "frontend", "dist")

if os.path.isdir(MS_FRONTEND_DIST):
    # 同时挂载 /assets 和 /ms/assets，兼容绝对路径与相对路径引用
    app.mount("/ms/assets", StaticFiles(directory=os.path.join(MS_FRONTEND_DIST, "assets")), name="ms_assets")
    app.mount("/assets", StaticFiles(directory=os.path.join(MS_FRONTEND_DIST, "assets")), name="assets")
    app.mount("/ms/images", StaticFiles(directory=os.path.join(MS_FRONTEND_DIST, "images")), name="ms_images")
    app.mount("/images", StaticFiles(directory=os.path.join(MS_FRONTEND_DIST, "images")), name="images")
    app.mount("/ms/templates", StaticFiles(directory=os.path.join(MS_FRONTEND_DIST, "templates")), name="ms_templates")

    @app.get("/ms", response_class=HTMLResponse)
    @app.get("/ms/{full_path:path}", response_class=HTMLResponse)
    async def ms_frontend(full_path: str = ""):
        """服务 MeterSphere 前端（SPA，路由回退到 index.html）。

        前端以 /front/ 前缀发起的 API 请求由部署层（nginx/Vite 代理）
        重写转发到现有后端 /api/，此处仅提供前端页面与静态资源。
        """
        index_file = os.path.join(MS_FRONTEND_DIST, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as fh:
                html = fh.read()
                # 将绝对路径 /assets/ 和 /images/ 重写为 /ms/assets/ 和 /ms/images/
                html = html.replace('src="/assets/', 'src="/ms/assets/')
                html = html.replace('href="/assets/', 'href="/ms/assets/')
                html = html.replace('srcset="/assets/', 'srcset="/ms/assets/')
                html = html.replace('"/assets/', '"/ms/assets/')
                return HTMLResponse(html)
        return JSONResponse({"error": "frontend not built"}, status_code=404)

