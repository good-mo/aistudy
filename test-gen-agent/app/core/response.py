# app/core/response.py
"""
统一响应格式
============
Phase 4 重构目标：替换各路由中手写的 JSONResponse，统一输出
{code, message, data} 格式。
"""
from fastapi.responses import JSONResponse
from typing import Any, Optional


def ok(data=None, message: str = "success", code: int = 200) -> JSONResponse:
    """成功响应。"""
    return JSONResponse(
        {"code": code, "message": message, "data": data},
        status_code=code,
    )


def fail(message: str = "error", code: int = 400, data=None) -> JSONResponse:
    """失败响应。"""
    return JSONResponse(
        {"code": code, "message": message, "data": data},
        status_code=code if code >= 400 else 400,
    )


def page_result(items: list, total: int, current: int = 1, page_size: int = 10) -> JSONResponse:
    """分页结果响应。"""
    return ok({
        "list": items,
        "total": total,
        "current": current,
        "pageSize": page_size,
    })


__all__ = ["ok", "fail", "page_result"]
