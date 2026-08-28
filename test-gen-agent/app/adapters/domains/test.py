# app/adapters/domains/test.py
"""业务域路由拆分：test（Phase 3 重构）。"""

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["adapter-test"])


def _ok(data: Any = None, message: str = "success", code: int = 200) -> JSONResponse:
    """统一成功响应格式。"""
    return JSONResponse({"code": code, "message": message, "data": data})


def _err(message: str = "error", code: int = 500, data: Any = None) -> JSONResponse:
    """统一失败响应格式。"""
    return JSONResponse({"code": code, "message": message, "data": data})


def _paginate(items: List, current: int = 1, page_size: int = 10) -> Dict:
    """分页包装。"""
    total = len(items)
    start = (current - 1) * page_size
    return {
        "list": items[start:start + page_size],
        "total": total,
        "pageSize": page_size,
        "current": current,
    }


async def _body(request: Request) -> dict:
    """安全读取请求体，空请求体返回空字典。"""
    try:
        raw = await request.body()
        if not raw:
            return {}
        return await request.json()
    except Exception:
        return {}


@router.get("/fake/error/list")
async def fake_error_list():
    """错误注入列表。"""
    return _ok([])


@router.post("/fake/error/add")
async def fake_error_add(request: Request):
    """添加错误注入。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/fake/error/update")
async def fake_error_update(request: Request):
    """更新错误注入。"""
    await request.json()
    return _ok()


@router.post("/fake/error/delete")
async def fake_error_delete(request: Request):
    """删除错误注入。"""
    await request.json()
    return _ok()


@router.post("/fake/error/update/enable")
async def fake_error_update_enable(request: Request):
    """启用/禁用错误注入。"""
    await request.json()
    return _ok()


# ════════════════════════════════════════════════════════════
# P0-9: WebSocket（基础 /ws/api 已移至 path_param_fixes.py）


# ════════════════════════════════════════════════════════════
# P0-10: 通用状态
# ════════════════════════════════════════════════════════════

