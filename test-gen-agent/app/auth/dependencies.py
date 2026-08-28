"""统一鉴权依赖。

提供 FastAPI `Depends` 依赖，供各业务路由获取当前登录用户。
全局认证中间件负责拦截未登录请求，此依赖仅用于路由内便捷获取用户。
"""
from typing import Dict, Any, Optional

from fastapi import Depends, HTTPException, Request

from app.auth.router import get_current_user


async def get_authenticated_user(
    request: Request,
    user: Optional[Dict[str, Any]] = Depends(get_current_user),
) -> Dict[str, Any]:
    """获取当前登录用户，未登录抛出 401。"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    return user


async def require_admin(
    user: Dict[str, Any] = Depends(get_authenticated_user),
) -> Dict[str, Any]:
    """要求当前用户为管理员。"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


__all__ = ["get_authenticated_user", "require_admin", "get_current_user"]
