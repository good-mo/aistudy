# app/adapters/domains/debug.py
"""业务域路由拆分：debug（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-debug"])


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


@router.get("/api/debug/delete")
async def api_debug_delete_get(request: Request):
    """接口调试删除（GET兼容）。"""
    return _ok()


@router.get("/api/debug/get")
async def api_debug_get(id: str = ""):
    """接口调试详情。"""
    return _ok({})


@router.post("/api/debug/get")
async def api_debug_get_post(request: Request):
    """接口调试详情 POST。"""
    await request.json()
    return _ok({})


@router.post("/api/debug/edit/pos")
async def api_debug_edit_pos(request: Request):
    """接口调试拖拽排序。"""
    await request.json()
    return _ok()


@router.post("/api/debug/transfer")
async def api_debug_transfer(request: Request):
    """调试文件转存。"""
    await request.json()
    return _ok()


@router.get("/api/debug/transfer/options")
async def api_debug_transfer_options(project_id: str = ""):
    """调试文件转存目录。"""
    return _ok([])


@router.post("/api/debug/upload/temp/file")
async def api_debug_upload_temp_file(request: Request):
    """调试临时文件上传。"""
    return _ok({"fileId": str(uuid.uuid4()), "fileName": "temp"})


@router.post("/api/debug")
async def api_debug(request: Request):
    """接口调试。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": 200,
        "body": {},
        "headers": {},
        "duration": 0,
        "success": True,
    }})


@router.post("/api/debug/import-curl")
async def api_debug_import_curl(request: Request):
    """导入 Curl 命令。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 任务中心适配
# ════════════════════════════════════════════════════════════


@router.post("/api/debug/debug")
async def api_debug_execute(request: Request):
    """执行调试。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": 200,
        "success": True,
        "body": {},
    }})


@router.post("/api/debug/add")
async def api_debug_add(request: Request):
    """新增调试。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/debug/update")
async def api_debug_update(request: Request):
    """更新调试。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/debug/get/{debug_id}")
async def api_debug_get(debug_id: str):
    """获取调试详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/debug/delete")
async def api_debug_delete(request: Request):
    """删除调试。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/debug/module/tree")
async def api_debug_module_tree():
    """获取调试模块树。"""
    from app.apitest.module_store import build_module_tree
    return JSONResponse({"code": 200, "message": "success", "data": build_module_tree("debug")})


@router.post("/api/debug/module/add")
async def api_debug_module_add(request: Request):
    """添加调试模块。"""
    body = await request.json()
    from app.apitest.module_store import add_module
    module = add_module(
        scope="debug",
        name=body.get("name", "新模块"),
        parent_id=body.get("parentId", "root"),
        project_id=body.get("projectId", ""),
    )
    return JSONResponse({"code": 200, "message": "success", "data": module})


@router.post("/api/debug/module/count", operation_id="api_debug_module_count_post")
@router.get("/api/debug/module/count", operation_id="api_debug_module_count_get")
async def api_debug_module_count():
    """获取调试模块数量。"""
    from app.apitest.module_store import list_modules
    modules = list_modules("debug")
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": m.get("id"), "name": m.get("name"), "count": 0} for m in modules
    ]})


@router.post("/api/debug/module/update")
async def api_debug_module_update(request: Request):
    """更新调试模块。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": body.get("id", ""),
        "name": body.get("name", ""),
        "type": "MODULE",
        "parentId": body.get("parentId", "root"),
        "children": [],
        "count": 0,
    }})


@router.get("/api/debug/module/delete")
async def api_debug_module_delete(id: str = ""):
    """删除调试模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/debug/module/move")
async def api_debug_module_move(request: Request):
    """移动调试模块。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})



# ════════════════════════════════════════════════════════════
# 缺失接口补充 - Mock 管理
# ════════════════════════════════════════════════════════════


@router.post("/api/debug/file/copy")
async def api_debug_file_copy(request: Request):
    """接口调试文件复制。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})

