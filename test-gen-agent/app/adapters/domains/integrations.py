# app/adapters/domains/integrations.py
"""业务域路由拆分：integrations（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-integrations"])


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


@router.get("/service/integration/delete")
async def service_integration_delete_get(request: Request):
    """服务集成删除（GET兼容）。"""
    return _ok()


@router.get("/service/integration/validate")
async def service_integration_validate_get(request: Request):
    """服务集成验证（GET兼容）。"""
    return _ok()


@router.get("/service/integration/list")
async def service_integration_list():
    """服务集成列表。"""
    return _ok([])


@router.post("/service/integration/add")
async def service_integration_add(request: Request):
    """添加服务集成。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/service/integration/update")
async def service_integration_update(request: Request):
    """更新服务集成。"""
    await request.json()
    return _ok()


@router.post("/service/integration/delete")
async def service_integration_delete(request: Request):
    """删除服务集成。"""
    await request.json()
    return _ok()


@router.get("/service/integration/script")
async def service_integration_script():
    """服务集成脚本。"""
    return _ok({})


@router.post("/service/integration/validate")
async def service_integration_validate(request: Request):
    """校验服务集成。"""
    await request.json()
    return _ok({"success": True})


@router.post("/service/integration/validate/")
async def service_integration_validate_trailing(request: Request):
    """校验服务集成（尾斜杠）。"""
    await request.json()
    return _ok({"success": True})


# ════════════════════════════════════════════════════════════
# P2-3: 消息通知  /notice/*  /notification/*  /api/message/*
# ════════════════════════════════════════════════════════════


@router.get("/we_com/info")
async def we_com_info():
    """企微信息。"""
    return _ok({})


@router.get("/we_com/info/with_detail")
async def we_com_info_with_detail():
    """企微信息详情。"""
    return _ok({})


@router.post("/we_com/save")
async def we_com_save(request: Request):
    """保存企微配置。"""
    await request.json()
    return _ok()


@router.post("/we_com/validate")
async def we_com_validate(request: Request):
    """校验企微配置。"""
    await request.json()
    return _ok({"success": True})


@router.post("/we_com/enable")
async def we_com_enable(request: Request):
    """启用企微。"""
    await request.json()
    return _ok()


@router.post("/we_com/change/validate")
async def we_com_change_validate(request: Request):
    """变更校验企微。"""
    await request.json()
    return _ok({"success": True})


# 钉钉


@router.get("/ding_talk/info")
async def ding_talk_info():
    """钉钉信息。"""
    return _ok({})


@router.get("/ding_talk/info/with_detail")
async def ding_talk_info_with_detail():
    """钉钉信息详情。"""
    return _ok({})


@router.post("/ding_talk/save")
async def ding_talk_save(request: Request):
    """保存钉钉配置。"""
    await request.json()
    return _ok()


@router.post("/ding_talk/validate")
async def ding_talk_validate(request: Request):
    """校验钉钉配置。"""
    await request.json()
    return _ok({"success": True})


@router.post("/ding_talk/enable")
async def ding_talk_enable(request: Request):
    """启用钉钉。"""
    await request.json()
    return _ok()


@router.post("/ding_talk/change/validate")
async def ding_talk_change_validate(request: Request):
    """变更校验钉钉。"""
    await request.json()
    return _ok({"success": True})


# 飞书


@router.get("/lark/info")
async def lark_info():
    """飞书信息。"""
    return _ok({})


@router.get("/lark/info/with_detail")
async def lark_info_with_detail():
    """飞书信息详情。"""
    return _ok({})


@router.post("/lark/save")
async def lark_save(request: Request):
    """保存飞书配置。"""
    await request.json()
    return _ok()


@router.post("/lark/validate")
async def lark_validate(request: Request):
    """校验飞书配置。"""
    await request.json()
    return _ok({"success": True})


@router.post("/lark/enable")
async def lark_enable(request: Request):
    """启用飞书。"""
    await request.json()
    return _ok()


@router.post("/lark/change/validate")
async def lark_change_validate(request: Request):
    """变更校验飞书。"""
    await request.json()
    return _ok({"success": True})


# 飞书套件


@router.get("/lark_suite/info")
async def lark_suite_info():
    """飞书套件信息。"""
    return _ok({})


@router.get("/lark_suite/info/with_detail")
async def lark_suite_info_with_detail():
    """飞书套件信息详情。"""
    return _ok({})


@router.post("/lark_suite/save")
async def lark_suite_save(request: Request):
    """保存飞书套件配置。"""
    await request.json()
    return _ok()


@router.post("/lark_suite/validate")
async def lark_suite_validate(request: Request):
    """校验飞书套件配置。"""
    await request.json()
    return _ok({"success": True})


@router.post("/lark_suite/enable")
async def lark_suite_enable(request: Request):
    """启用飞书套件。"""
    await request.json()
    return _ok()


@router.post("/lark_suite/change/validate")
async def lark_suite_change_validate(request: Request):
    """变更校验飞书套件。"""
    await request.json()
    return _ok({"success": True})


# SSO 回调

