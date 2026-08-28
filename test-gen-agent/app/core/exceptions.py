# app/core/exceptions.py
"""
统一异常定义与全局异常处理
==========================
Phase 4 重构目标：替换各路由函数中冗余的 try-except，统一错误响应格式。
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.logging_config import get_logger

logger = get_logger(__name__)


# ── 业务异常类 ──────────────────────────────────────────────

class AppError(Exception):
    """应用业务异常基类。"""

    def __init__(self, message: str = "操作失败", code: int = 400, data=None):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(message)


class NotFoundError(AppError):
    """资源不存在。"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code=404)


class AuthError(AppError):
    """未授权。"""

    def __init__(self, message: str = "未授权"):
        super().__init__(message, code=401)


class ForbiddenError(AppError):
    """无权限。"""

    def __init__(self, message: str = "无权限访问"):
        super().__init__(message, code=403)


class ValidationError(AppError):
    """参数验证失败。"""

    def __init__(self, message: str = "参数验证失败"):
        super().__init__(message, code=400)


class ConflictError(AppError):
    """资源冲突。"""

    def __init__(self, message: str = "资源冲突"):
        super().__init__(message, code=409)


# ── 全局异常处理器 ──────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """在 FastAPI 应用上注册全局异常处理器。"""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        logger.warning("[%s %s] AppError: %s", request.method, request.url.path, exc.message)
        return JSONResponse(
            {
                "code": exc.code,
                "message": exc.message,
                "data": exc.data,
            },
            status_code=exc.code,
        )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(
            {"code": 404, "message": exc.message, "data": None},
            status_code=404,
        )

    @app.exception_handler(AuthError)
    async def auth_error_handler(request: Request, exc: AuthError):
        return JSONResponse(
            {"code": 401, "message": exc.message, "data": None},
            status_code=401,
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            {"code": 400, "message": exc.message, "data": None},
            status_code=400,
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            "[%s %s] 未捕获异常: %s",
            request.method, request.url.path, exc, exc_info=True,
        )
        return JSONResponse(
            {"code": 500, "message": f"服务器内部错误: {str(exc)[:200]}", "data": None},
            status_code=500,
        )


__all__ = [
    "AppError",
    "NotFoundError",
    "AuthError",
    "ForbiddenError",
    "ValidationError",
    "ConflictError",
    "register_exception_handlers",
]
