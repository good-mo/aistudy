# app/core/middleware.py
"""
统一中间件
==========
Phase 4 重构目标：CORS / 日志 / 请求ID / 认证。

性能优化：
    - 通过 contextvars 将 request_id 注入日志，实现 trace_id 贯穿业务日志。
    - 请求访问日志在 DEBUG 模式下记录每次请求，在生产模式仅记录慢请求
      （>阈值）与 5xx 错误，避免同步文件 I/O 拖慢事件循环。
"""
import time
import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import FastAPI, Request, Response

from app.config import settings
from app.logging_config import get_logger, set_request_id

logger = get_logger(__name__)

# 生产模式下：仅记录耗时超过该阈值的慢请求（毫秒）
SLOW_REQUEST_MS = 500


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件：记录方法、路径、耗时、状态码，并贯穿 trace_id。"""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        set_request_id(request_id)  # 注入日志 trace_id，供业务日志贯穿

        start = time.time()
        is_debug = settings.debug

        # DEBUG 模式下记录每个请求的进入日志，便于开发排查
        if is_debug:
            logger.info("[%s] → %s %s", request_id, request.method, request.url.path)

        try:
            response = await call_next(request)
            duration = (time.time() - start) * 1000
            status = response.status_code

            # 生产模式：仅记录慢请求与 5xx 错误，降低文件 I/O 阻塞
            if is_debug or duration >= SLOW_REQUEST_MS or status >= 500:
                logger.info(
                    "[%s] %s %s -> %s (%dms)",
                    request_id, request.method, request.url.path,
                    status, round(duration, 1),
                )

            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(
                "[%s] %s %s -> 500 (%dms) err=%s",
                request_id, request.method, request.url.path,
                round(duration, 1), e, exc_info=True,
            )
            raise


def register_middleware(app: FastAPI) -> None:
    """在 FastAPI 应用上注册统一中间件。

    注册顺序（后注册的先执行）：
      1. CORS（若需要）
      2. 全局认证中间件（所有业务路由需登录）
      3. 请求日志中间件（最外层，记录所有请求）
    """
    # CORS 中间件
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应配置为具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 认证中间件：先注册（后执行顺序中它先于日志执行）
    from app.core.auth_middleware import AuthMiddleware
    app.add_middleware(AuthMiddleware)
    # 请求日志中间件
    app.add_middleware(RequestLoggingMiddleware)


__all__ = ["RequestLoggingMiddleware", "register_middleware"]
