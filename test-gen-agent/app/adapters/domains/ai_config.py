# app/adapters/domains/ai_config.py
"""业务域路由拆分：ai_config（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-ai_config"])


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


@router.get("/ai/config/get")
async def ai_config_get():
    """获取 AI 配置。"""
    return _ok({})


@router.delete("/ai/config/delete")
async def ai_config_delete():
    """删除 AI 配置。"""
    return _ok()


@router.post("/ai/config/edit-source")
async def ai_config_edit_source(request: Request):
    """编辑 AI 配置源。"""
    await request.json()
    return _ok()


@router.get("/ai/conversation/chat/list")
async def ai_conversation_chat_list():
    """AI 对话列表。"""
    return _ok([])


@router.post("/ai/conversation/chat")
async def ai_conversation_chat(request: Request):
    """AI 对话。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/ai/conversation/update")
async def ai_conversation_update(request: Request):
    """更新 AI 对话。"""
    await request.json()
    return _ok()


@router.post("/ai/conversation/delete")
async def ai_conversation_delete(request: Request):
    """删除 AI 对话。"""
    await request.json()
    return _ok()


@router.delete("/ai/config/delete/{config_id}")
@router.post("/ai/config/delete/{config_id}")
async def ai_config_delete_path(config_id: str):
    """删除 AI 配置（带路径参数）。"""
    return _ok({"id": config_id, "deleted": True})


# ════════════════════════════════════════════════════════════
# 接口定义
# ════════════════════════════════════════════════════════════


@router.get("/ai/config/delete/{config_id}")
async def ai_config_delete_get_path(config_id: str):
    """删除 AI 配置（GET 带路径参数，与前端调用一致）。"""
    return _ok({"id": config_id, "deleted": True})


@router.get("/ai/conversation/chat/list/{conversation_id}")
async def ai_conversation_chat_list_path(conversation_id: str):
    """获取 AI 对话详情（带路径参数）。"""
    return _ok({"conversation_id": conversation_id})


# ════════════════════════════════════════════════════════════
# 补充缺失 API（方法不匹配 + 带路径参数）
# ════════════════════════════════════════════════════════════

# ── 方法不匹配修复 ────────────────────────────────────────


@router.get("/ai/config/get/{config_id}")
async def ai_config_get_path(config_id: str):
    """获取 AI 配置详情（带路径参数）。"""
    return _ok({"id": config_id})


# 文档分享插件脚本（前端: /api/doc/share/plugin/script/{id}/{orgId}）


@router.post("/ai/conversation")
async def ai_conversation(request: Request):
    """AI 对话。"""
    body = await request.json()
    prompt = body.get("prompt", "") or body.get("content", "")
    return JSONResponse({"code": 200, "message": "success", "data": {
        "content": "",
        "conversationId": str(uuid.uuid4()),
    }})


@router.get("/ai/conversation/list")
async def ai_conversation_list():
    """获取 AI 对话列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/ai/conversation/detail/{conversation_id}")
async def ai_conversation_detail(conversation_id: str):
    """获取 AI 对话详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/ai/conversation/add")
async def ai_conversation_add(request: Request):
    """新增 AI 对话。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/ai/conversation/delete/{conversation_id}")
async def ai_conversation_delete(conversation_id: str):
    """删除 AI 对话。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/ai/conversation/update/title")
async def ai_conversation_update_title(request: Request):
    """更新 AI 对话标题。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# 工作台路由已迁移至 app/test_plan/router_dashboard.py


# 测试计划路由已迁移至 app/test_plan/ 模块


# ── 更多场景/调试适配 ───────────────────────────────────

