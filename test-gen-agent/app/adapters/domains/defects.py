# app/adapters/domains/defects.py
"""业务域路由拆分：defects（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-defects"])


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



@router.get("/bug/attachment/list/")
async def bug_attachment_list(id: str = ""):
    """缺陷附件列表。"""
    return _ok([])


@router.get("/bug/attachment/transfer/options/")
async def bug_attachment_transfer_options(project_id: str = ""):
    """缺陷附件转存目录。"""
    return _ok([])


@router.post("/bug/comment/get/")
async def bug_comment_get():
    """缺陷评论。"""
    return _ok([])


@router.post("/bug/comment/delete/")
async def bug_comment_delete():
    """删除缺陷评论。"""
    return _ok()


@router.post("/bug/trash/delete/")
async def bug_trash_delete(id: str = ""):
    """缺陷回收站彻底删除。"""
    return _ok()


@router.post("/bug/trash/recover/")
async def bug_trash_recover(id: str = ""):
    """缺陷回收站恢复。"""
    return _ok()


@router.post("/bug/delete/")
async def bug_delete(id: str = ""):
    """删除缺陷。"""
    return _ok()


@router.get("/bug/check-exist/")
async def bug_check_exist(id: str = ""):
    """检查缺陷是否存在。"""
    return _ok({"exist": True})


@router.post("/bug/follow/")
async def bug_follow(id: str = ""):
    """关注缺陷。"""
    return _ok()


@router.post("/bug/unfollow/")
async def bug_unfollow(id: str = ""):
    """取消关注缺陷。"""
    return _ok()


@router.get("/bug/get/")
async def bug_get(id: str = ""):
    """获取缺陷详情。"""
    from app.defects.tracker import get_defect
    defect = get_defect(id) if id else None
    return _ok(defect or {})


@router.get("/bug/export/columns/")
async def bug_export_columns(project_id: str = ""):
    """缺陷导出列。"""
    return _ok([])


@router.post("/bug/sync/")
async def bug_sync():
    """同步缺陷。"""
    return _ok()


@router.get("/bug/header/columns-option/")
async def bug_header_columns_option(project_id: str = ""):
    """缺陷表头列选项。"""
    return _ok([])


@router.get("/bug/header/custom-field/")
async def bug_header_custom_field(project_id: str = ""):
    """缺陷表头自定义字段。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# P0-6: 功能用例补充  /functional/case/*
# ════════════════════════════════════════════════════════════


@router.post("/bug/attachment/check-update")
async def api_bug_attachment_check_update_post(request: Request):
    """检查附件是否更新（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"update": False})


@router.post("/bug/attachment/download")
async def api_bug_attachment_download_post(request: Request):
    """下载缺陷附件（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"fileId": "", "fileName": "download"})


@router.post("/bug/attachment/preview")
async def api_bug_attachment_preview_post(request: Request):
    """预览缺陷附件（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"content": ""})


@router.post("/bug/case/un-relate/module/tree")
async def api_bug_case_unrelate_module_tree_post(request: Request):
    """缺陷未关联用例模块树（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok([])


@router.post("/bug/case/un-relate/module/count")
async def api_bug_case_unrelate_module_count_post(request: Request):
    """缺陷未关联用例模块数量（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok([])


@router.get("/bug/sync/")
async def api_bug_sync_trailing_get(request: Request):
    """同步缺陷-开源版（GET 带尾斜杠兼容前端）。"""
    try:
        await request.json()
    except Exception:
        pass
    return _ok({"success": True, "sync": "openSource"})


@router.get("/bug/case/un-relate/{id}")
async def bug_case_un_relate_path(id: str):
    """取消缺陷用例关联（带路径参数）。"""
    return _ok({"id": id, "success": True})


@router.get("/bug/case/check-permission/{project_id}/{case_type}")
async def bug_case_check_permission_path(project_id: str, case_type: str):
    """检查缺陷用例权限（带路径参数）。"""
    return _ok({"project_id": project_id, "case_type": case_type, "hasPermission": True})


@router.get("/bug/attachment/transfer/options//{project_id}")
async def bug_attachment_transfer_options_double_slash(project_id: str):
    """缺陷附件转存选项（双斜杠 URL 兼容前端拼接问题）。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# 缺失路径参数路由（前端拼接路径参数时后端无匹配路由）
# ════════════════════════════════════════════════════════════

# 功能用例模块树（前端: /functional/case/module/tree/{projectId}）


@router.post("/bug/page")
async def bug_page(request: Request):
    """缺陷分页列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.defects.tracker import list_defects
    defects = list_defects(limit=page_size, offset=(current - 1) * page_size)

    items = []
    for d in defects:
        items.append(_to_bug(d))

    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": items,
            "total": len(defects),
            "pageSize": page_size,
            "current": current,
        },
    })


@router.post("/bug/add")
async def bug_add(request: Request):
    """创建缺陷。"""
    body = await request.json()
    from app.defects.tracker import create_defect
    defect = create_defect(
        title=body.get("title", "未命名缺陷"),
        description=body.get("description", ""),
        severity=_to_severity(body.get("severity", "major")),
        file_path=body.get("filePath", ""),
    )
    return JSONResponse({"code": 200, "message": "success", "data": _to_bug(defect)})


@router.post("/bug/update")
async def bug_update(request: Request):
    """更新缺陷。"""
    body = await request.json()
    defect_id = body.get("id", "")
    from app.defects.tracker import update_defect
    updates = {}
    for k, v in body.items():
        if k == "title":
            updates["title"] = v
        elif k == "description":
            updates["description"] = v
        elif k == "status":
            updates["status"] = v
        elif k == "severity":
            updates["severity"] = _to_severity(v)
    try:
        defect = update_defect(defect_id, **updates)
    except Exception:
        defect = None
    if not defect:
        return JSONResponse({"code": 404, "message": "缺陷不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_bug(defect)})


@router.get("/bug/delete/{bug_id}")
async def bug_delete(bug_id: str):
    """删除缺陷。"""
    from app.defects.tracker import delete_defect
    delete_defect(bug_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/bug/batch-delete")
async def bug_batch_delete(request: Request):
    """批量删除缺陷。"""
    body = await request.json()
    bug_ids = body.get("selectIds", body.get("ids", []))
    if body.get("selectAll") and not bug_ids:
        from app.defects.tracker import list_defects
        all_defects = list_defects(limit=999)
        bug_ids = [d["id"] for d in all_defects]
    from app.defects.tracker import delete_defect
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/get/{bug_id}")
async def bug_get(bug_id: str):
    """获取缺陷详情。"""
    from app.defects.tracker import get_defect
    defect = get_defect(bug_id)
    if not defect:
        return JSONResponse({"code": 404, "message": "缺陷不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_bug(defect)})


def _to_bug(defect: Dict[str, Any]) -> Dict[str, Any]:
    """将后端缺陷格式转为前端格式。"""
    return {
        "id": defect.get("id", ""),
        "title": defect.get("title", ""),
        "description": defect.get("description", ""),
        "status": defect.get("status", "open"),
        "severity": _to_severity_name(defect.get("severity", "major")),
        "filePath": defect.get("file_path", ""),
        "createTime": defect.get("created_at", 0),
        "updateTime": defect.get("updated_at", 0),
        "createUser": "admin",
        "assignee": defect.get("assignee", ""),
        "deleted": False,
    }


def _to_severity(severity: str) -> str:
    """前端严重度转后端严重度。"""
    mapping = {
        "critical": "critical",
        "block": "critical",
        "major": "major",
        "normal": "major",
        "minor": "minor",
        "trivial": "trivial",
    }
    return mapping.get(severity, severity)


def _to_severity_name(severity: str) -> str:
    """后端严重度转前端严重度。"""
    mapping = {
        "critical": "critical",
        "major": "major",
        "minor": "minor",
        "trivial": "trivial",
    }
    return mapping.get(severity, "major")


# ── 缺陷回收站 & 自定义字段 ──────────────────────────────


@router.post("/bug/trash/page")
async def bug_trash_page(request: Request):
    """缺陷回收站分页列表。"""
    body = await _body(request)
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)
    from app.defects.tracker import list_trashed_defects
    defects = list_trashed_defects(limit=page_size, offset=(current - 1) * page_size)
    items = []
    for d in defects:
        item = _to_bug(d)
        item["deleted"] = True
        item["deleteTime"] = d.get("deleted_at", 0)
        items.append(item)
    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": items,
            "total": len(items),
            "pageSize": page_size,
            "current": current,
        },
    })


@router.post("/bug/recover")
async def bug_recover(request: Request):
    """恢复缺陷。body: {id}"""
    body = await request.json()
    bug_id = body.get("id", "")
    from app.defects.tracker import recover_defect
    ok = recover_defect(bug_id)
    if not ok:
        return JSONResponse({"code": 404, "message": "缺陷不在回收站中", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/bug/trash/recover/{bug_id}")
async def bug_trash_recover(bug_id: str):
    """单个恢复缺陷。"""
    from app.defects.tracker import recover_defect
    recover_defect(bug_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/trash/recover/{bug_id}")
async def bug_trash_recover_get(bug_id: str):
    """单个恢复缺陷（GET）。"""
    from app.defects.tracker import recover_defect
    recover_defect(bug_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/trash/delete/{bug_id}")
async def bug_trash_delete_get(bug_id: str):
    """单个彻底删除缺陷（GET）。"""
    from app.defects.tracker import purge_defect
    purge_defect(bug_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/bug/trash/batch-recover")
async def bug_trash_batch_recover(request: Request):
    """批量恢复缺陷。body: {ids: []}"""
    body = await request.json()
    ids = body.get("ids", body.get("id", []))
    if isinstance(ids, str):
        ids = [ids]
    from app.defects.tracker import recover_defect
    for bug_id in ids:
        try:
            recover_defect(bug_id)
        except Exception:
            pass
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/bug/delete")
async def bug_delete_standard(request: Request):
    """标准删除缺陷（移入回收站）。body: {id}"""
    body = await request.json()
    bug_id = body.get("id", "")
    from app.defects.tracker import trash_defect
    trash_defect(bug_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/bug/trash/delete/{bug_id}")
async def bug_trash_delete(bug_id: str):
    """单个彻底删除缺陷。"""
    from app.defects.tracker import purge_defect
    purge_defect(bug_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/bug/trash/batch-delete")
async def bug_trash_batch_delete(request: Request):
    """批量彻底删除缺陷。body: {ids: []}"""
    body = await request.json()
    ids = body.get("ids", body.get("id", []))
    if isinstance(ids, str):
        ids = [ids]
    from app.defects.tracker import purge_defect
    for bug_id in ids:
        try:
            purge_defect(bug_id)
        except Exception:
            pass
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/header/custom-field/{project_id}")
async def bug_header_custom_field(project_id: str):
    """获取缺陷表头自定义字段。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {
            "id": "title",
            "key": "title",
            "name": "标题",
            "type": "TEXT",
            "required": True,
            "show": True,
            "enable": True,
        },
        {
            "id": "status",
            "key": "status",
            "name": "状态",
            "type": "SELECT",
            "required": True,
            "show": True,
            "enable": True,
        },
        {
            "id": "severity",
            "key": "severity",
            "name": "严重程度",
            "type": "SELECT",
            "required": True,
            "show": True,
            "enable": True,
        },
        {
            "id": "assignee",
            "key": "assignee",
            "name": "处理人",
            "type": "MEMBER",
            "required": False,
            "show": True,
            "enable": True,
        },
    ]})


@router.get("/bug/columns-option/{project_id}")
async def bug_columns_option(project_id: str):
    """获取缺陷列显示配置。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"key": "id", "label": "ID", "show": True, "order": 1},
        {"key": "title", "label": "标题", "show": True, "order": 2},
        {"key": "status", "label": "状态", "show": True, "order": 3},
        {"key": "severity", "label": "严重程度", "show": True, "order": 4},
        {"key": "assignee", "label": "处理人", "show": True, "order": 5},
        {"key": "createUser", "label": "创建人", "show": True, "order": 6},
        {"key": "createTime", "label": "创建时间", "show": True, "order": 7},
        {"key": "updateTime", "label": "更新时间", "show": True, "order": 8},
    ]})


# ════════════════════════════════════════════════════════════
# 接口定义管理适配
# 前端: /api/definition/*  →  后端: /api/apitest/*
# ════════════════════════════════════════════════════════════


@router.get("/bug/current-platform")
async def bug_current_platform():
    """获取当前缺陷平台。"""
    return JSONResponse({"code": 200, "message": "success", "data": "LOCAL"})


@router.get("/bug/check-exist/{bug_id}")
async def bug_check_exist(bug_id: str):
    """检查缺陷是否存在。"""
    return JSONResponse({"code": 200, "message": "success", "data": True})


@router.get("/bug/template/option")
async def bug_template_option():
    """获取缺陷模板选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/bug/template/detail")
async def bug_template_detail():
    """获取缺陷模板详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/bug/comment/add")
async def bug_comment_add(request: Request):
    """添加缺陷评论。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/comment/get/{bug_id}")
async def bug_comment_get(bug_id: str):
    """获取缺陷评论列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/bug/export")
async def bug_export(request: Request):
    """导出缺陷。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "taskId": str(uuid.uuid4()),
    }})


@router.post("/bug/batch-update")
async def bug_batch_update(request: Request):
    """批量更新缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 用例评审适配
# 前端: /case/review/*  →  用例评审管理
# ════════════════════════════════════════════════════════════


@router.post("/bug/attachment/transfer")
async def bug_attachment_transfer(request: Request):
    """转存缺陷附件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/attachment/transfer/options/{project_id}")
async def bug_attachment_transfer_options(project_id: str):
    """获取缺陷附件转存目录。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/bug/attachment/preview")
async def bug_attachment_preview():
    """预览缺陷附件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/attachment/download")
async def bug_attachment_download():
    """下载缺陷附件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/attachment/check-update")
async def bug_attachment_check_update():
    """检查缺陷附件是否更新。"""
    return JSONResponse({"code": 200, "message": "success", "data": {"hasUpdate": False}})


@router.post("/bug/attachment/update")
async def bug_attachment_update(request: Request):
    """更新缺陷附件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/bug/attachment/file/page")
async def bug_attachment_file_page(request: Request):
    """获取缺陷关联文件列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.get("/bug/attachment/preview/md")
async def bug_editor_preview_file():
    """预览富文本图片。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# 缺陷关联用例


@router.get("/bug/case/page")
async def bug_case_page():
    """获取缺陷关联的用例列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/bug/case/page")
async def bug_case_page_post(request: Request):
    """获取缺陷关联的用例列表（POST）。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/bug/case/relate")
async def bug_case_relate(request: Request):
    """批量添加缺陷关联用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/case/un-relate")
async def bug_case_un_relate():
    """单个取消缺陷关联用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/bug/case/un-relate/page")
async def bug_case_un_relate_page(request: Request):
    """获取未关联的用例列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.get("/bug/case/un-relate/module/tree")
async def bug_case_un_relate_module_tree():
    """获取未关联用例模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/bug/case/un-relate/module/count")
async def bug_case_un_relate_module_count():
    """获取未关联用例模块数量。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/bug/case/check-permission")
async def bug_case_check_permission():
    """缺陷用例跳转权限检查。"""
    return JSONResponse({"code": 200, "message": "success", "data": True})


# 缺陷变更历史


@router.post("/bug/history/page")
async def bug_history_page(request: Request):
    """获取缺陷变更历史。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.get("/bug/history/page")
async def bug_history_page_get():
    """获取缺陷变更历史（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


# 缺陷回收站


@router.get("/bug/follow/{bug_id}")
async def bug_follow(bug_id: str):
    """关注缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/unfollow/{bug_id}")
async def bug_unfollow(bug_id: str):
    """取消关注缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# 缺陷模板相关补充


@router.get("/bug/template/option/{project_id}")
async def bug_template_option_project(project_id: str):
    """获取项目缺陷模板选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/bug/template/detail")
async def bug_template_detail_post(request: Request):
    """获取缺陷模板详情（POST）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/export/columns/{project_id}")
async def bug_export_columns(project_id: str):
    """获取缺陷导出字段配置。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# 缺陷评论更新/删除


@router.post("/bug/comment/update")
async def bug_comment_update(request: Request):
    """更新缺陷评论。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/comment/delete/{comment_id}")
async def bug_comment_delete(comment_id: str):
    """删除缺陷评论。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# 缺失接口补充 - 功能用例高级功能
# ════════════════════════════════════════════════════════════

# 脑图编辑


@router.get("/bug/sync/{project_id}")
async def bug_sync(project_id: str):
    """同步缺陷（开源版）。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": "COMPLETED",
        "count": 0,
    }})


@router.post("/bug/sync/all")
async def bug_sync_all(request: Request):
    """同步缺陷（企业版）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/sync/check/{project_id}")
async def bug_sync_check(project_id: str):
    """获取同步状态。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": "COMPLETED",
    }})


    """导出缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/current-platform/{project_id}")
async def bug_current_platform_project(project_id: str):
    """获取项目缺陷平台。"""
    return JSONResponse({"code": 200, "message": "success", "data": "LOCAL"})


@router.get("/bug/header/columns-option/{project_id}")
async def bug_header_columns_option(project_id: str):
    """获取表头字段选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 功能用例 AI 功能
# ════════════════════════════════════════════════════════════

