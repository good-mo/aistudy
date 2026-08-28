# app/adapters/domains/attachment.py
"""业务域路由拆分：attachment（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-attachment"])


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

async def _read_body(request: Request) -> dict:
    """安全读取请求体。"""
    try:
        return await request.json()
    except Exception:
        return {}



@router.post("/attachment/check-update")
async def attachment_check_update_post(request: Request):
    """附件更新检查（POST兼容）。"""
    return _ok()


@router.post("/attachment/download/file")
async def attachment_download_file_post(request: Request):
    """附件下载（POST兼容）。"""
    body = await _body(request)
    file_id = body.get("id", body.get("fileId", ""))
    return _ok({"fileId": file_id})


@router.post("/attachment/preview")
async def attachment_preview_post(request: Request):
    """附件预览（POST兼容）。"""
    return _ok()


@router.get("/attachment/options/{project_id}")
@router.post("/attachment/options/{project_id}")
async def attachment_options_path(project_id: str):
    """获取附件选项（带路径参数）。"""
    return _ok({"project_id": project_id})


@router.get("/attachment/update/{attachment_id}/{project_id}")
@router.post("/attachment/update/{attachment_id}/{project_id}")
async def attachment_update_path(attachment_id: str, project_id: str):
    """更新附件（带路径参数）。"""
    return _ok({"attachment_id": attachment_id, "project_id": project_id})


# ════════════════════════════════════════════════════════════
# 功能用例
# ════════════════════════════════════════════════════════════


@router.post("/attachment/download")
async def api_attachment_download_post(request: Request):
    """下载附件（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"fileId": "", "fileName": "download"})


@router.post("/attachment/upload/file")
async def attachment_upload_file(request: Request):
    """上传文件并关联用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "fileId": str(uuid.uuid4()),
        "fileName": "uploaded_file",
    }})


@router.post("/attachment/transfer")
async def attachment_transfer(request: Request):
    """转存文件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/attachment/preview")
async def attachment_preview():
    """预览文件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/attachment/download")
async def attachment_download():
    """下载文件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/attachment/delete/file")
async def attachment_delete_file(request: Request):
    """删除文件或取消关联。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/attachment/options")
async def attachment_options():
    """获取转存目录。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/attachment/update")
async def attachment_update(request: Request):
    """更新附件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/attachment/check-update")
async def attachment_check_update():
    """检查附件是否更新。"""
    return JSONResponse({"code": 200, "message": "success", "data": {"hasUpdate": False}})


@router.post("/attachment/upload/temp/file")
async def attachment_upload_temp_file(request: Request):
    """富文本所需资源上传。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "fileId": str(uuid.uuid4()),
    }})


@router.get("/attachment/download/file")
async def attachment_download_file():
    """富文本资源详情预览压缩图。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 缺陷同步与导出
# ════════════════════════════════════════════════════════════

