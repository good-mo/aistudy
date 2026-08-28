# app/adapters/domains/platform.py
"""业务域路由拆分：platform（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-platform"])


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


@router.get("/license/validate")
async def license_validate_get(request: Request):
    """授权验证（GET兼容）。"""
    return _ok({"valid": True})


@router.get("/setting/get/platform/info")
async def setting_get_platform_info():
    """平台信息。"""
    return _ok({})


@router.get("/setting/get/platform/param")
async def setting_get_platform_param():
    """平台参数。"""
    return _ok({})


# ════════════════════════════════════════════════════════════
# P2-7: 授权  /license/*
# ════════════════════════════════════════════════════════════


@router.post("/license/add")
async def license_add(request: Request):
    """添加授权。"""
    await request.json()
    return _ok({"success": True})


@router.post("/license/validate")
async def license_validate(request: Request):
    """校验授权。"""
    await request.json()
    return _ok({"valid": True})


# ════════════════════════════════════════════════════════════
# P2-8: 认证  /authentication/*
# ════════════════════════════════════════════════════════════

