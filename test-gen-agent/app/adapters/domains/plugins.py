# app/adapters/domains/plugins.py
"""业务域路由拆分：plugins（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-plugins"])


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


@router.get("/plugin/delete")
async def plugin_delete_get(request: Request):
    """插件删除（GET兼容）。"""
    return _ok()


@router.post("/plugin/options")
async def plugin_options_post(request: Request):
    """插件选项（POST兼容）。"""
    return _ok([])


@router.get("/plugin/list")
async def plugin_list():
    """插件列表。"""
    return _ok([])


@router.post("/plugin/add")
async def plugin_add(request: Request):
    """添加插件。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/plugin/update")
async def plugin_update(request: Request):
    """更新插件。"""
    await request.json()
    return _ok()


@router.post("/plugin/delete")
async def plugin_delete(request: Request):
    """删除插件。"""
    await request.json()
    return _ok()


@router.get("/plugin/options")
async def plugin_options():
    """插件选项。"""
    return _ok([])


@router.get("/plugin/script/get")
async def plugin_script_get(id: str = ""):
    """获取插件脚本。"""
    return _ok({})


@router.get("/plugin/image/")
async def plugin_image(id: str = ""):
    """插件图片。"""
    return _ok({})


# ════════════════════════════════════════════════════════════
# P2-2: 服务集成  /service/integration/*
# ════════════════════════════════════════════════════════════


@router.get("/plugin/image/{plugin_id}")
async def plugin_image_path(plugin_id: str):
    """获取插件图片（带路径参数）。"""
    return _ok({"id": plugin_id})


# ════════════════════════════════════════════════════════════
# 项目
# ════════════════════════════════════════════════════════════

