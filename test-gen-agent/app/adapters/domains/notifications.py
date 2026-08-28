# app/adapters/domains/notifications.py
"""业务域路由拆分：notifications（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-notifications"])


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


@router.get("/notification/read/all")
async def notification_read_all_get(request: Request):
    """全部已读（GET兼容）。"""
    return _ok()


@router.get("/notification/read/{item_id}")
async def notification_read_item_get(item_id: str, request: Request):
    """单条消息已读（GET）。"""
    return _ok()


@router.post("/api/message/list")
async def api_message_list_post(request: Request):
    """消息列表（POST兼容）。"""
    return _ok([])


@router.post("/notification/count")
async def notification_count_post(request: Request):
    """通知数量（POST兼容）。"""
    return _ok({"count": 0})


@router.get("/notice/message/task/get")
async def notice_message_task_get():
    """消息任务配置。"""
    return _ok({})


@router.post("/notice/message/task/save")
async def notice_message_task_save(request: Request):
    """保存消息任务配置。"""
    await request.json()
    return _ok()


@router.get("/notice/message/task/get/user")
async def notice_message_task_get_user():
    """消息任务用户。"""
    return _ok([])


@router.get("/notice/message/template/detail")
async def notice_message_template_detail():
    """消息模板详情。"""
    return _ok({})


@router.get("/notice/template/get/fields")
async def notice_template_get_fields():
    """消息模板字段。"""
    return _ok([])


@router.get("/notification/count")
async def notification_count():
    """通知数量。"""
    return _ok({"count": 0})


@router.get("/notification/list/all/page")
async def notification_list_all_page():
    """通知分页列表。"""
    return _ok(_paginate([], 1, 10))


@router.post("/notification/read/all")
async def notification_read_all(request: Request):
    """全部已读。"""
    await request.json()
    return _ok()


@router.get("/notification/un-read")
async def notification_un_read():
    """未读通知。"""
    return _ok([])


@router.get("/api/message/list")
async def api_message_list():
    """消息列表。"""
    return _ok([])


@router.post("/api/message/read")
async def api_message_read(request: Request):
    """消息已读。"""
    await request.json()
    return _ok()


# ════════════════════════════════════════════════════════════
# P2-4: 操作日志  /operation/log/*  /project/log/*
# ════════════════════════════════════════════════════════════


@router.get("/notification/read/{notification_id}")
@router.post("/notification/read/{notification_id}")
async def notification_read_path(notification_id: str):
    """标记消息通知为已读（带路径参数）。"""
    return _ok({"id": notification_id, "read": True})


# ════════════════════════════════════════════════════════════
# 项目应用
# ════════════════════════════════════════════════════════════


@router.get("/notice/message/task/get/{project_id}")
async def notice_message_task_get_path(project_id: str):
    """获取消息任务配置（带路径参数）。"""
    return _ok({})


# 消息任务用户列表（前端: /notice/message/task/get/user/{projectId}）


@router.get("/notice/message/task/get/user/{project_id}")
async def notice_message_task_get_user_path(project_id: str):
    """获取消息任务用户列表（带路径参数）。"""
    return _ok([])


# 消息模板详情（前端: /notice/message/template/detail/{projectId}）


@router.get("/notice/message/template/detail/{project_id}")
async def notice_message_template_detail_path(project_id: str):
    """获取消息模板详情（带路径参数）。"""
    return _ok({})


# 消息模板字段（前端: /notice/template/get/fields/{projectId}）


@router.get("/notice/template/get/fields/{project_id}")
async def notice_template_get_fields_path(project_id: str):
    """获取消息模板字段（带路径参数）。"""
    return _ok([])


# 组织日志用户列表（前端: /organization/log/user/list/{id}）

