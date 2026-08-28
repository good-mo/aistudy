# app/core/__init__.py
"""
核心基础设施模块
=================
Phase 1/2/4 重构目标：

| 模块 | 职责 | 阶段 |
|------|------|------|
| `database.py` | 统一数据库连接池 + 事务管理 | Phase 1 |
| `exceptions.py` | 全局异常定义 + 处理器 | Phase 4 |
| `response.py` | 统一响应格式 {code, message, data} | Phase 4 |
| `router.py` | 表驱动路由注册 | Phase 2 |
| `middleware.py` | 请求日志/鉴权中间件 | Phase 4 |
| `config.py` | 统一配置管理 | Phase 1 |
"""
from app.core.database import Database, get_conn, execute, query_one, query_all
from app.core.exceptions import (
    AppError, NotFoundError, AuthError, ForbiddenError,
    ValidationError, ConflictError, register_exception_handlers,
)
from app.core.response import ok, fail, page_result
from app.core.router import (
    api_route, register_alias, build_api_router,
    route_count, list_routes, check_duplicate_paths,
)

__all__ = [
    "Database", "get_conn", "execute", "query_one", "query_all",
    "AppError", "NotFoundError", "AuthError", "ForbiddenError",
    "ValidationError", "ConflictError", "register_exception_handlers",
    "ok", "fail", "page_result",
    "api_route", "register_alias", "build_api_router",
    "route_count", "list_routes", "check_duplicate_paths",
]
