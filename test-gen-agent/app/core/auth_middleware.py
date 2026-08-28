"""全局认证中间件。

为所有业务接口提供统一鉴权保护，仅放行白名单路径（登录、公钥获取等）。
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 认证模块自身的公开接口
AUTH_PUBLIC_PATHS = {
    "/login": {"POST"},
    "/get-key": {"GET"},
    "/is-login": {"GET"},
    "/signout": {"POST", "GET"},
    "/authentication/get-list": {"GET"},
    "/authentication/get/by/type": {"GET"},
    "/api/user/menu": {"POST"},
    "/health": {"GET", "HEAD"},
}

# 静态文件/前端资源/WebSocket 路径不鉴权
# 注：WebSocket 在握手阶段难以携带自定义 Header，故暂放行；
#     具体业务 WebSocket 可自行校验 query/cookie 中的 token。
STATIC_PREFIXES = [
    "/static/",
    "/assets/",
    "/images/",
    "/ms/",
    "/front/",
    "/ws/",
    "/favicon.ico",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """全局认证中间件：所有业务路由需携带有效会话令牌。"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        # 1. 静态资源和前端入口放行
        for prefix in STATIC_PREFIXES:
            if path.startswith(prefix) or path == prefix.rstrip("/"):
                return await call_next(request)

        # 2. 认证公开接口放行
        if path in AUTH_PUBLIC_PATHS:
            if method in AUTH_PUBLIC_PATHS[path]:
                return await call_next(request)

        # 3. 检查会话令牌
        token = request.headers.get("X-AUTH-TOKEN", "")
        if not token:
            token = request.cookies.get("sessionId", "")
        if not token:
            return self._unauthorized()

        from app.auth.store import auth_store
        user = auth_store.get_session_user(token)
        if not user:
            return self._unauthorized()

        # 将用户信息注入 request.state，供各路由使用
        request.state.user = user
        return await call_next(request)

    @staticmethod
    def _unauthorized():
        return JSONResponse(
            {"code": 401, "message": "未登录或会话已过期", "data": None},
            status_code=401,
        )


__all__ = ["AuthMiddleware"]
