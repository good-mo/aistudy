# app/adapters/domains/websocket.py
"""业务域路由拆分：websocket（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-websocket"])


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


@router.websocket("/ws/api")
async def ws_api_base(websocket: WebSocket):
    """WebSocket API 基础连接。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/api/{report_id}")
async def ws_api_report(websocket: WebSocket, report_id: str):
    """WebSocket API with report ID（前端 getSocket(reportId) 使用）。"""
    await websocket.accept()
    try:
        # 发送连接确认
        await websocket.send_text(json.dumps({"type": "connected", "report_id": report_id}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data, "report_id": report_id}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
# AI 配置
# ════════════════════════════════════════════════════════════


@router.websocket("/ws/debug")
async def ws_debug(websocket: WebSocket):
    """WebSocket 调试连接。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected", "service": "debug"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/debug/{report_id}")
async def ws_debug_report(websocket: WebSocket, report_id: str):
    """WebSocket 调试连接（带报告ID）。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected", "report_id": report_id, "service": "debug"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data, "report_id": report_id}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/export")
async def ws_export(websocket: WebSocket):
    """WebSocket 导出连接。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected", "service": "export"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/export/{report_id}")
async def ws_export_report(websocket: WebSocket, report_id: str):
    """WebSocket 导出连接（带报告ID）。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected", "report_id": report_id, "service": "export"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data, "report_id": report_id}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
# 消息通知
# ════════════════════════════════════════════════════════════

