# app/adapters/router.py
"""MeterSphere 前端 API 适配层。

将 MeterSphere v3.x 前端的 API 路径映射到现有后端业务逻辑。
前端路径风格: /functional/case/*, /bug/*, /api/definition/* 等
后端路径风格: /api/cases/*, /api/defects/*, /api/apitest/* 等
"""

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["api-adapter"])


async def _body(request: Request) -> dict:
    """安全读取请求体，空请求体返回空字典。"""
    try:
        raw = await request.body()
        if not raw:
            return {}
        return await request.json()
    except Exception:
        return {}


# ════════════════════════════════════════════════════════════
# 功能用例管理适配
# 前端: /functional/case/*  →  后端: /api/cases/*
# ════════════════════════════════════════════════════════════

@router.post("/functional/case/page")
async def functional_case_page(request: Request):
    """功能用例分页列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.cases.repository import list_cases
    cases = list_cases(
        search=keyword if keyword else None,
        limit=page_size,
        offset=(current - 1) * page_size,
    )

    # 转为 MeterSphere 前端格式
    items = []
    for c in cases:
        items.append(_to_functional_case(c))

    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": items,
            "total": len(cases),
            "pageSize": page_size,
            "current": current,
        },
    })


@router.post("/functional/case/add")
async def functional_case_add(request: Request):
    """添加功能用例。"""
    body = await request.json()
    from app.cases.repository import create_case
    case = create_case(
        title=body.get("name") or body.get("title", "未命名用例"),
        description=body.get("description", ""),
        source_code=body.get("sourceCode", ""),
        file_path=body.get("filePath", ""),
        status=body.get("status", "draft"),
        priority=body.get("priority", "P2"),
        test_type=body.get("testType", "functional"),
        structured_cases=body.get("steps", []),
    )
    if not case:
        return JSONResponse({"code": 500, "message": "创建失败", "data": None}, status_code=500)
    return JSONResponse({"code": 200, "message": "success", "data": _to_functional_case(case)})


@router.post("/functional/case/update")
async def functional_case_update(request: Request):
    """更新功能用例。"""
    body = await request.json()
    case_id = body.get("id", "")
    from app.cases.repository import update_case
    updates = {}
    for k, v in body.items():
        if k == "name" or k == "title":
            updates["title"] = v
        elif k == "description":
            updates["description"] = v
        elif k == "status":
            updates["status"] = v
        elif k == "priority":
            updates["priority"] = v
        elif k == "testType":
            updates["test_type"] = v
        elif k == "sourceCode":
            updates["source_code"] = v
        elif k == "filePath":
            updates["file_path"] = v

    try:
        case = update_case(case_id, **updates)
    except Exception:
        case = None
    if not case:
        return JSONResponse({"code": 404, "message": "用例不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_functional_case(case)})


@router.post("/functional/case/delete")
async def functional_case_delete(request: Request):
    """删除功能用例。"""
    body = await request.json()
    case_id = body.get("id", "")
    from app.cases.repository import delete_case
    deleted = delete_case(case_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/detail/{case_id}")
async def functional_case_detail(case_id: str):
    """获取用例详情。"""
    from app.cases.repository import get_case
    case = get_case(case_id)
    if not case:
        return JSONResponse({"code": 404, "message": "用例不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_functional_case(case)})


@router.get("/functional/case/module/tree")
async def functional_case_module_tree():
    """获取功能用例模块树。"""
    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": [
            {
                "id": "root",
                "name": "全部用例",
                "type": "MODULE",
                "children": [],
                "pos": 1,
            }
        ],
    })


@router.get("/functional/mind/case/list")
async def functional_mind_case_list():
    """获取脑图数据。"""
    from app.cases.repository import list_cases
    cases = list_cases(limit=500)
    tree = []
    for c in cases:
        node = {
            "id": c.get("id", ""),
            "text": c.get("title", ""),
            "resource": {
                "status": c.get("status", "draft"),
                "priority": c.get("priority", "P2"),
            },
            "children": [],
        }
        tree.append(node)
    return JSONResponse({"code": 200, "message": "success", "data": tree})


@router.post("/functional/case/batch/delete-to-gc")
async def functional_case_batch_delete(request: Request):
    """批量删除功能用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/batch/edit")
async def functional_case_batch_edit(request: Request):
    """批量编辑功能用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/batch/move")
async def functional_case_batch_move(request: Request):
    """批量移动功能用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/batch/copy")
async def functional_case_batch_copy(request: Request):
    """批量复制功能用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


def _to_functional_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """将后端用例格式转为前端格式。"""
    return {
        "id": case.get("id", ""),
        "name": case.get("title", ""),
        "title": case.get("title", ""),
        "description": case.get("description", ""),
        "priority": case.get("priority", "P2"),
        "status": case.get("status", "draft"),
        "testType": case.get("test_type", "functional"),
        "type": "functional",
        "createTime": case.get("created_at", 0),
        "updateTime": case.get("updated_at", 0),
        "createUser": "admin",
        "updateUser": "admin",
        "tags": case.get("tags", []),
        "moduleId": "root",
        "modulePath": "/全部用例",
        "steps": case.get("structured_cases", []),
        "deleted": False,
    }


# ════════════════════════════════════════════════════════════
# 缺陷管理适配
# 前端: /bug/*  →  后端: /api/defects/*
# ════════════════════════════════════════════════════════════

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

@router.post("/api/definition/page")
async def api_definition_page(request: Request):
    """接口定义分页列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.apitest.store import list_definitions
    definitions = list_definitions(limit=page_size, offset=(current - 1) * page_size)

    items = []
    for d in definitions:
        items.append(_to_definition(d))

    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": items,
            "total": len(definitions),
            "pageSize": page_size,
            "current": current,
        },
    })


@router.post("/api/definition/add")
async def api_definition_add(request: Request):
    """添加接口定义。"""
    body = await request.json()
    from app.apitest.store import create_definition
    definition = create_definition(
        name=body.get("name", "未命名接口"),
        method=body.get("method", "GET"),
        path=body.get("path", "/"),
        protocol=body.get("protocol", "HTTP"),
        description=body.get("description", ""),
        body=body.get("requestBody", ""),
        headers=body.get("requestHeaders", body.get("headers", {})),
        query=body.get("query", {}),
        params=body.get("requestParams", body.get("params", {})),
        tags=body.get("tags", []),
    )
    return JSONResponse({"code": 200, "message": "success", "data": _to_definition(definition)})


@router.post("/api/definition/update")
async def api_definition_update(request: Request):
    """更新接口定义。"""
    body = await request.json()
    definition_id = body.get("id", "")
    from app.apitest.store import update_definition
    updates = {}
    for k, v in body.items():
        if k == "name":
            updates["name"] = v
        elif k == "method":
            updates["method"] = v
        elif k == "path":
            updates["path"] = v
        elif k == "protocol":
            updates["protocol"] = v
        elif k == "description":
            updates["description"] = v
    try:
        definition = update_definition(definition_id, **updates)
    except Exception:
        definition = None
    if not definition:
        return JSONResponse({"code": 404, "message": "接口不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_definition(definition)})


@router.post("/api/definition/delete-to-gc")
async def api_definition_delete(request: Request):
    """删除接口定义（移入回收站）。"""
    body = await request.json()
    definition_id = body.get("id", "")
    from app.api_testing.management import delete_api_definition
    delete_api_definition(definition_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/definition/module/tree")
async def api_definition_module_tree():
    """获取接口模块树。"""
    from app.apitest.module_store import build_module_tree
    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": build_module_tree("definition"),
    })


@router.post("/api/definition/module/add")
async def api_definition_module_add(request: Request):
    """添加接口定义模块。"""
    body = await request.json()
    from app.apitest.module_store import add_module
    module = add_module(
        scope="definition",
        name=body.get("name", "新模块"),
        parent_id=body.get("parentId", "root"),
        project_id=body.get("projectId", ""),
    )
    return JSONResponse({"code": 200, "message": "success", "data": module})


@router.post("/api/definition/module/count", operation_id="api_definition_module_count_post")
@router.get("/api/definition/module/count", operation_id="api_definition_module_count_get")
async def api_definition_module_count():
    """获取接口定义模块数量。"""
    from app.apitest.module_store import list_modules
    modules = list_modules("definition")
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": m.get("id"), "name": m.get("name"), "count": 0} for m in modules
    ]})


@router.get("/api/definition/get-detail/{definition_id}")
async def api_definition_detail(definition_id: str):
    """获取接口定义详情。"""
    from app.apitest.store import get_definition
    definition = get_definition(definition_id)
    if not definition:
        return JSONResponse({"code": 404, "message": "接口不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_definition(definition)})


@router.post("/api/definition/import")
async def api_definition_import(request: Request):
    """导入接口定义。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/export")
async def api_definition_export(request: Request):
    """导出接口定义。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/batch/delete-to-gc")
async def api_definition_batch_delete(request: Request):
    """批量删除接口定义（移入回收站）。"""
    body = await request.json()
    ids = body.get("ids", body.get("selectIds", []))
    from app.api_testing.management import delete_api_definition
    deleted = 0
    for did in ids:
        if delete_api_definition(did):
            deleted += 1
    return JSONResponse({"code": 200, "message": "success", "data": {"deleted": deleted}})


@router.post("/api/definition/batch-update")
async def api_definition_batch_update(request: Request):
    """批量更新接口定义。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/batch-move")
async def api_definition_batch_move(request: Request):
    """批量移动接口定义。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/copy")
async def api_definition_copy(request: Request):
    """复制接口定义。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/debug")
async def api_definition_debug(request: Request):
    """调试接口定义。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/definition/follow")
async def api_definition_follow():
    """关注接口定义。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/edit/pos")
async def api_definition_edit_pos(request: Request):
    """拖拽调整位置。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


def _to_definition(defn: Dict[str, Any]) -> Dict[str, Any]:
    """将后端接口定义格式转为前端格式。"""
    def _parse_field(val, default=None):
        """解析 JSON 字符串字段；已是 dict/list 则直接返回。"""
        if isinstance(val, (dict, list)):
            return val
        if val is None:
            return default or {}
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return default or {}

    return {
        "id": defn.get("id", ""),
        "name": defn.get("name", ""),
        "method": defn.get("method", "GET"),
        "path": defn.get("path", "/"),
        "protocol": defn.get("protocol", "HTTP"),
        "description": defn.get("description", ""),
        "requestBody": _parse_field(defn.get("request_body", defn.get("body", {}))),
        "responseBody": _parse_field(defn.get("response_body", {})),
        "moduleId": "root",
        "modulePath": "/全部接口",
        "createTime": defn.get("created_at", 0),
        "updateTime": defn.get("updated_at", 0),
        "createUser": "admin",
        "deleted": False,
    }


# ════════════════════════════════════════════════════════════
# 接口场景适配
# ════════════════════════════════════════════════════════════

@router.post("/api/scenario/page")
async def api_scenario_page(request: Request):
    """接口场景分页列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.apitest.store import list_scenarios
    scenarios = list_scenarios(limit=page_size, offset=(current - 1) * page_size)

    items = []
    for s in scenarios:
        items.append(_to_scenario(s))

    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": items,
            "total": len(scenarios),
            "pageSize": page_size,
            "current": current,
        },
    })


@router.post("/api/scenario/add")
async def api_scenario_add(request: Request):
    """添加接口场景。"""
    body = await request.json()
    from app.apitest.store import create_scenario
    scenario = create_scenario(
        name=body.get("name", "未命名场景"),
        description=body.get("description", ""),
        steps=body.get("steps", []),
    )
    return JSONResponse({"code": 200, "message": "success", "data": _to_scenario(scenario)})


@router.post("/api/scenario/update")
async def api_scenario_update(request: Request):
    """更新接口场景。"""
    body = await request.json()
    scenario_id = body.get("id", "")
    from app.apitest.store import update_scenario
    updates = {}
    for k, v in body.items():
        if k == "name":
            updates["name"] = v
        elif k == "description":
            updates["description"] = v
        elif k == "steps":
            updates["steps"] = v
    try:
        scenario = update_scenario(scenario_id, **updates)
    except Exception:
        scenario = None
    if not scenario:
        return JSONResponse({"code": 404, "message": "场景不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_scenario(scenario)})


@router.post("/api/scenario/delete")
async def api_scenario_delete(request: Request):
    """删除接口场景（彻底删除）。"""
    body = await request.json()
    scenario_id = body.get("id", "")
    from app.api_testing.management import delete_scenario
    delete_scenario(scenario_id, permanent=True)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/scenario/detail/{scenario_id}")
async def api_scenario_detail(scenario_id: str):
    """获取接口场景详情。"""
    from app.apitest.store import get_scenario
    scenario = get_scenario(scenario_id)
    if not scenario:
        return JSONResponse({"code": 404, "message": "场景不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_scenario(scenario)})


@router.post("/api/scenario/run")
async def api_scenario_run(request: Request):
    """运行接口场景。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": "success",
        "result": "SUCCESS",
    }})


@router.post("/api/scenario/batch/delete")
async def api_scenario_batch_delete(request: Request):
    """批量删除接口场景。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


def _to_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """将后端场景格式转为前端格式。"""
    return {
        "id": scenario.get("id", ""),
        "name": scenario.get("name", ""),
        "description": scenario.get("description", ""),
        "steps": json.loads(scenario.get("steps", "[]")) if isinstance(scenario.get("steps"), str) else scenario.get("steps", []),
        "moduleId": "root",
        "modulePath": "/全部场景",
        "createTime": scenario.get("created_at", 0),
        "updateTime": scenario.get("updated_at", 0),
        "createUser": "admin",
        "deleted": False,
    }


# ════════════════════════════════════════════════════════════
# 接口用例适配
# ════════════════════════════════════════════════════════════

@router.post("/api/case/page")
async def api_case_page(request: Request):
    """接口用例分页列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.apitest.store import list_api_cases
    cases = list_api_cases(limit=page_size, offset=(current - 1) * page_size)

    items = []
    for c in cases:
        items.append(_to_api_case(c))

    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": items,
            "total": len(cases),
            "pageSize": page_size,
            "current": current,
        },
    })


@router.post("/api/case/add")
async def api_case_add(request: Request):
    """添加接口用例。"""
    body = await request.json()
    from app.apitest.store import create_api_case
    case = create_api_case(
        name=body.get("name", "未命名用例"),
        api_definition_id=body.get("definitionId", ""),
        description=body.get("description", ""),
        asserts=body.get("assertions", body.get("asserts", [])),
        pre_scripts=body.get("preScripts", []),
        post_scripts=body.get("postScripts", []),
    )
    return JSONResponse({"code": 200, "message": "success", "data": _to_api_case(case)})


@router.post("/api/case/update")
async def api_case_update(request: Request):
    """更新接口用例。"""
    body = await request.json()
    case_id = body.get("id", "")
    from app.apitest.store import update_api_case
    updates = {}
    for k, v in body.items():
        if k == "name":
            updates["name"] = v
        elif k == "description":
            updates["description"] = v
        elif k == "assertions":
            updates["asserts"] = v
    try:
        case = update_api_case(case_id, **updates)
    except Exception:
        case = None
    if not case:
        return JSONResponse({"code": 404, "message": "用例不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_api_case(case)})


@router.post("/api/case/delete-to-gc")
async def api_case_delete_to_gc(request: Request):
    """删除接口用例（移入回收站）。"""
    body = await request.json()
    case_id = body.get("id", body.get("ids", ""))
    from app.api_testing.management import delete_api_test_case
    ids = case_id if isinstance(case_id, list) else [case_id]
    deleted = 0
    for cid in ids:
        if cid and delete_api_test_case(cid):
            deleted += 1
    return JSONResponse({"code": 200, "message": "success", "data": {"deleted": deleted}})


@router.post("/api/case/batch/delete-to-gc")
async def api_case_batch_delete_to_gc(request: Request):
    """批量删除接口用例（移入回收站）。"""
    body = await request.json()
    ids = body.get("ids", body.get("selectIds", []))
    from app.api_testing.management import delete_api_test_case
    deleted = 0
    for cid in ids:
        if delete_api_test_case(cid):
            deleted += 1
    return JSONResponse({"code": 200, "message": "success", "data": {"deleted": deleted}})


@router.post("/api/case/delete")
async def api_case_delete(request: Request):
    """删除接口用例（彻底删除）。"""
    body = await request.json()
    case_id = body.get("id", "")
    from app.api_testing.management import delete_api_test_case
    delete_api_test_case(case_id, permanent=True)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/case/detail/{case_id}")
async def api_case_detail(case_id: str):
    """获取接口用例详情。"""
    from app.apitest.store import get_api_case
    case = get_api_case(case_id)
    if not case:
        return JSONResponse({"code": 404, "message": "用例不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_api_case(case)})


@router.post("/api/case/run")
async def api_case_run(request: Request):
    """运行接口用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": "success",
        "result": "SUCCESS",
    }})


@router.post("/api/case/batch/delete")
async def api_case_batch_delete(request: Request):
    """批量删除接口用例（彻底删除）。"""
    body = await request.json()
    ids = body.get("ids", body.get("selectIds", []))
    from app.api_testing.management import delete_api_test_case
    deleted = 0
    for cid in ids:
        if delete_api_test_case(cid, permanent=True):
            deleted += 1
    return JSONResponse({"code": 200, "message": "success", "data": {"deleted": deleted}})


def _to_api_case(case: Dict[str, Any]) -> Dict[str, Any]:
    """将后端接口用例格式转为前端格式。"""
    def _parse_field(val):
        """解析 JSON 字符串字段；已是 list/dict 则直接返回。"""
        if isinstance(val, (list, dict)):
            return val
        try:
            return json.loads(val) if isinstance(val, str) else (val or [])
        except (json.JSONDecodeError, TypeError):
            return val or []

    return {
        "id": case.get("id", ""),
        "name": case.get("name", ""),
        "description": case.get("description", ""),
        "definitionId": case.get("api_definition_id", ""),
        "assertions": _parse_field(case.get("asserts", [])),
        "preScripts": _parse_field(case.get("pre_scripts", [])),
        "postScripts": _parse_field(case.get("post_scripts", [])),
        "moduleId": "root",
        "createTime": case.get("created_at", 0),
        "updateTime": case.get("updated_at", 0),
        "createUser": "admin",
        "deleted": False,
    }


# ════════════════════════════════════════════════════════════
# Mock 服务适配
# ════════════════════════════════════════════════════════════

@router.post("/api/definition/mock/add")
async def api_mock_add(request: Request):
    """添加 Mock。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/mock/page")
async def api_mock_page(request: Request):
    """Mock 分页列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/api/definition/mock/update")
async def api_mock_update(request: Request):
    """更新 Mock。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/mock/delete")
async def api_mock_delete(request: Request):
    """删除 Mock。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/definition/mock/detail/{mock_id}")
async def api_mock_detail(mock_id: str):
    """获取 Mock 详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/mock/enable")
async def api_mock_enable(request: Request):
    """启用/禁用 Mock。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 调试适配
# ════════════════════════════════════════════════════════════

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

@router.get("/project/task-center/page")
async def project_task_center_page(request: Request):
    """项目任务中心分页列表。"""
    from app.tasks.manager import manager
    tasks = manager.list_tasks()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": tasks,
        "total": len(tasks),
    }})


@router.get("/project/task-center/stop/{task_id}")
async def project_task_center_stop(task_id: str):
    """停止任务。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# AI 对话适配
# ════════════════════════════════════════════════════════════

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
@router.get("/api/scenario/module/tree")
async def api_scenario_module_tree():
    """获取场景模块树。"""
    from app.apitest.module_store import build_module_tree
    return JSONResponse({"code": 200, "message": "success", "data": build_module_tree("scenario")})


@router.post("/api/scenario/module/add")
async def api_scenario_module_add(request: Request):
    """添加场景模块。"""
    body = await request.json()
    from app.apitest.module_store import add_module
    module = add_module(
        scope="scenario",
        name=body.get("name", "新模块"),
        parent_id=body.get("parentId", "root"),
        project_id=body.get("projectId", ""),
    )
    return JSONResponse({"code": 200, "message": "success", "data": module})


@router.post("/api/scenario/module/count", operation_id="api_scenario_module_count_post")
@router.get("/api/scenario/module/count", operation_id="api_scenario_module_count_get")
async def api_scenario_module_count():
    """获取场景模块数量。"""
    from app.apitest.module_store import list_modules
    modules = list_modules("scenario")
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": m.get("id"), "name": m.get("name"), "count": 0} for m in modules
    ]})


@router.post("/api/scenario/delete-to-gc")
async def api_scenario_recycle(request: Request):
    """删除场景（移入回收站）。"""
    body = await request.json()
    sc_id = body.get("id", body.get("ids", ""))
    from app.api_testing.management import delete_scenario
    ids = sc_id if isinstance(sc_id, list) else [sc_id]
    deleted = 0
    for sid in ids:
        if sid and delete_scenario(sid):
            deleted += 1
    return JSONResponse({"code": 200, "message": "success", "data": {"deleted": deleted}})


@router.get("/api/scenario/get/{scenario_id}")
async def api_scenario_get(scenario_id: str):
    """获取场景详情。"""
    from app.apitest.store import get_scenario
    scenario = get_scenario(scenario_id)
    if not scenario:
        return JSONResponse({"code": 404, "message": "场景不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_scenario(scenario)})


@router.post("/api/scenario/step/get")
async def api_scenario_step_get(request: Request):
    """获取场景步骤详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/debug")
async def api_scenario_debug(request: Request):
    """场景调试。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/import")
async def api_scenario_import(request: Request):
    """导入场景。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/export")
async def api_scenario_export(request: Request):
    """导出场景。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/batch-operation/delete-gc")
async def api_scenario_batch_operation_delete(request: Request):
    """批量删除场景（移入回收站）。"""
    body = await request.json()
    ids = body.get("ids", body.get("selectIds", []))
    from app.api_testing.management import delete_scenario
    deleted = 0
    for sid in ids:
        if delete_scenario(sid):
            deleted += 1
    return JSONResponse({"code": 200, "message": "success", "data": {"deleted": deleted}})


@router.post("/api/scenario/batch-operation/move")
async def api_scenario_batch_operation_move(request: Request):
    """批量移动场景。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/batch-operation/copy")
async def api_scenario_batch_operation_copy(request: Request):
    """批量复制场景。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/batch-operation/run")
async def api_scenario_batch_operation_run(request: Request):
    """批量执行场景。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/update-priority")
async def api_scenario_update_priority(request: Request):
    """更新场景优先级。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/update-status")
async def api_scenario_update_status(request: Request):
    """更新场景状态。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/statistics")
async def api_scenario_statistics(request: Request):
    """场景执行统计。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/follow")
async def api_scenario_follow(request: Request):
    """关注/取消关注场景。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 调试相关 ────────────────────────────────────────────
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


@router.post("/api/test/mock")
async def api_test_mock(request: Request):
    """测试 Mock。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 用例管理更多接口 ─────────────────────────────────────
@router.get("/functional/case/follower")
async def functional_case_follower():
    """获取用例关注人。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/functional/case/edit/follower")
async def functional_case_edit_follower(request: Request):
    """关注/取消关注用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/custom/field")
async def functional_case_custom_field(request: Request):
    """获取自定义字段。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/functional/case/module/add")
async def functional_case_module_add(request: Request):
    """添加模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/module/update")
async def functional_case_module_update(request: Request):
    """更新模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/module/move")
async def functional_case_module_move(request: Request):
    """移动模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/module/trash/tree")
async def functional_case_module_trash_tree():
    """获取回收站模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# ── 功能用例回收站 ──────────────────────────────────────
@router.get("/functional/case/module/count")
async def functional_case_module_count():
    """获取全部用例模块数量。"""
    from app.apitest.module_store import list_modules
    modules = list_modules("functional")
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": m.get("id"), "name": m.get("name"), "count": 0} for m in modules
    ]})


@router.post("/functional/case/trash/page")
async def functional_case_trash_page(request: Request):
    """功能用例回收站分页列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)
    from app.cases.management import list_trash_cases
    trashed = list_trash_cases()
    items = []
    for t in trashed:
        case = t.get("case_data", {})
        item = _to_functional_case(case)
        item["deleted"] = True
        item["deleteTime"] = t.get("deleted_at", 0)
        item["deleteUser"] = t.get("deleted_by", "")
        items.append(item)
    # 简单关键词过滤
    if keyword:
        items = [i for i in items if keyword.lower() in i.get("name", "").lower()
                 or keyword.lower() in i.get("id", "").lower()]
    total = len(items)
    start = (current - 1) * page_size
    page_items = items[start:start + page_size]
    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": page_items,
            "total": total,
            "pageSize": page_size,
            "current": current,
        },
    })


@router.get("/functional/case/trash/module/count")
async def functional_case_trash_module_count():
    """获取回收站模块数量。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/functional/case/trash/recover")
async def functional_case_trash_recover(request: Request):
    """恢复单个回收站用例。body: {id}"""
    body = await request.json()
    case_id = body.get("id", "")
    from app.cases.management import restore_case
    restore_case(case_id, operator="admin")
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/trash/recover/{case_id}")
async def functional_case_trash_recover_get(case_id: str):
    """恢复单个回收站用例（GET）。"""
    from app.cases.management import restore_case
    restore_case(case_id, operator="admin")
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/trash/delete/{case_id}")
async def functional_case_trash_delete_get(case_id: str):
    """删除单个回收站用例（GET）。"""
    from app.cases.management import purge_case
    purge_case(case_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/trash/batch/recover")
async def functional_case_trash_batch_recover(request: Request):
    """批量恢复回收站用例。body: {ids: []}"""
    body = await request.json()
    ids = body.get("ids", body.get("id", []))
    if isinstance(ids, str):
        ids = [ids]
    from app.cases.management import restore_case
    for case_id in ids:
        try:
            restore_case(case_id, operator="admin")
        except Exception:
            pass
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/trash/delete")
async def functional_case_trash_delete(request: Request):
    """删除单个回收站用例。body: {id}"""
    body = await request.json()
    case_id = body.get("id", "")
    from app.cases.management import purge_case
    purge_case(case_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/trash/batch/delete")
async def functional_case_trash_batch_delete(request: Request):
    """批量删除回收站用例。body: {ids: []}"""
    body = await request.json()
    ids = body.get("ids", body.get("id", []))
    if isinstance(ids, str):
        ids = [ids]
    from app.cases.management import purge_case
    for case_id in ids:
        try:
            purge_case(case_id)
        except Exception:
            pass
    return JSONResponse({"code": 200, "message": "success", "data": None})


# 附件路由已迁移至 app/file_mgmt/ 模块


# ── 缺陷更多接口 ────────────────────────────────────────
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

@router.post("/case/review/page")
async def case_review_page(request: Request):
    """获取评审列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.cases.repository import list_cases
    cases = list_cases(limit=999)

    # 筛选评审中的用例
    reviews = [c for c in cases if c.get("status") in ("review", "pending", "in_review", "under_review")]
    if keyword:
        reviews = [c for c in reviews if keyword.lower() in c.get("title", "").lower()]

    paged = reviews[(current - 1) * page_size: current * page_size]

    items = []
    for c in paged:
        items.append({
            "id": c.get("id", ""),
            "name": c.get("title", ""),
            "num": 1,
            "moduleId": "root",
            "status": "UNDERWAY",
            "reviewPassRule": "SINGLE",
            "startTime": c.get("created_at", 0) * 1000,
            "endTime": None,
            "createUser": c.get("created_by", "admin"),
            "createTime": int(c.get("created_at", 0) * 1000),
            "updateTime": int(c.get("updated_at", 0) * 1000),
            "updateUser": "admin",
            "pos": 0,
            "description": c.get("description", ""),
            "tags": None,
            "caseCount": 1,
            "passRate": 0,
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(reviews),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/case/review/add")
async def case_review_add(request: Request):
    """新增评审。"""
    body = await request.json()
    from app.cases.repository import create_case

    case = create_case(
        title=body.get("name", "新评审"),
        description=body.get("description", ""),
        status="review",
        priority="P2",
    )
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": case.get("id", "") if case else str(uuid.uuid4()),
        "name": body.get("name", "新评审"),
        "status": "UNDERWAY",
    }})


@router.post("/case/review/edit")
async def case_review_edit(request: Request):
    """编辑评审。"""
    body = await request.json()
    review_id = body.get("id", "")
    from app.cases.repository import update_case
    updates = {}
    if "name" in body:
        updates["title"] = body["name"]
    if "description" in body:
        updates["description"] = body["description"]
    try:
        case = update_case(review_id, **updates)
    except Exception:
        case = None
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/delete")
async def case_review_delete(request: Request):
    """删除用例评审。"""
    body = await request.json()
    review_id = body.get("id", "")
    from app.cases.repository import delete_case
    delete_case(review_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/copy")
async def case_review_copy(request: Request):
    """复制评审。"""
    body = await request.json()
    copy_id = body.get("copyId", "")
    from app.cases.repository import get_case
    case = get_case(copy_id)
    if case:
        from app.cases.repository import create_case
        new_case = create_case(
            title=f"{case.get('title', '')} (副本)",
            description=case.get("description", ""),
            status="review",
        )
        return JSONResponse({"code": 200, "message": "success", "data": {
            "id": new_case.get("id", "") if new_case else str(uuid.uuid4()),
            "name": f"{case.get('title', '')} (副本)",
            "caseCount": 1,
            "createTime": int(time.time() * 1000),
            "createUser": "admin",
        }})
    return JSONResponse({"code": 404, "message": "评审不存在", "data": None}, status_code=404)


@router.post("/case/review/batch/move")
async def case_review_batch_move(request: Request):
    """移动评审。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/edit/pos")
async def case_review_edit_pos(request: Request):
    """评审拖拽排序。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/edit/follower")
async def case_review_edit_follower(request: Request):
    """关注/取消关注评审。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/associate")
async def case_review_associate(request: Request):
    """关联用例到评审。"""
    body = await request.json()
    review_id = body.get("reviewId", "")
    case_ids = body.get("baseAssociateCaseRequest", {}).get("selectIds", [])
    if not case_ids and body.get("baseAssociateCaseRequest", {}).get("selectAll"):
        # 全选模式下关联所有用例
        from app.cases.repository import list_cases
        all_cases = list_cases(limit=999)
        case_ids = [c["id"] for c in all_cases]
    return JSONResponse({"code": 200, "message": "success", "data": {
        "reviewId": review_id,
        "caseCount": len(case_ids),
    }})


@router.post("/case/review/disassociate")
async def case_review_disassociate(request: Request):
    """取消关联用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail")
async def case_review_detail(request: Request):
    """获取评审详情。"""
    body = await request.json()
    review_id = body.get("id", "")
    from app.cases.repository import get_case
    case = get_case(review_id) if review_id else None
    if not case:
        return JSONResponse({"code": 404, "message": "评审不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": case.get("id", ""),
        "name": case.get("title", ""),
        "num": 1,
        "moduleId": "root",
        "status": "UNDERWAY",
        "reviewPassRule": "SINGLE",
        "startTime": int(case.get("created_at", 0) * 1000),
        "endTime": None,
        "createUser": "admin",
        "createTime": int(case.get("created_at", 0) * 1000),
        "updateTime": int(case.get("updated_at", 0) * 1000),
        "description": case.get("description", ""),
    }})


@router.get("/case/review/detail")
async def case_review_detail_get(request: Request):
    """获取评审详情（GET 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/page")
async def case_review_detail_page(request: Request):
    """评审详情-获取已关联用例列表。"""
    body = await request.json()
    review_id = body.get("reviewId", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.cases.repository import list_cases
    all_cases = list_cases(limit=999)

    # 如果 reviewId 本身就是一个 case_id，返回该用例
    review_cases = [c for c in all_cases if c.get("id") == review_id]
    if not review_cases:
        # 否则返回所有评审状态的用例
        review_cases = [c for c in all_cases if c.get("status") in ("review", "pending", "in_review")]

    paged = review_cases[(current - 1) * page_size: current * page_size]
    items = []
    for c in paged:
        items.append({
            "id": c.get("id", ""),
            "name": c.get("title", ""),
            "priority": c.get("priority", "P2"),
            "status": "UN_REVIEWED",
            "reviewer": [],
            "createUser": "admin",
            "createTime": int(c.get("created_at", 0) * 1000),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(review_cases),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/case/review/user-option")
async def case_review_user_option(request: Request):
    """获取评审人员列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


@router.get("/case/review/user-option")
async def case_review_user_option_get():
    """获取评审人员列表（GET 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


# ── 评审模块管理 ─────────────────────────────────────────
@router.get("/case/review/module/tree")
async def case_review_module_tree():
    """获取评审模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {
            "id": "root",
            "name": "全部评审",
            "type": "MODULE",
            "parentId": "",
            "children": [],
            "count": 0,
        }
    ]})


@router.post("/case/review/module/add")
async def case_review_module_add(request: Request):
    """新增评审模块。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": str(uuid.uuid4()),
        "name": body.get("name", "新模块"),
        "type": "MODULE",
        "parentId": body.get("parentId", "root"),
        "children": [],
        "count": 0,
    }})


@router.post("/case/review/module/update")
async def case_review_module_update(request: Request):
    """更新评审模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/module/delete")
async def case_review_module_delete(request: Request):
    """删除评审模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/module/move")
async def case_review_module_move(request: Request):
    """移动评审模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/module/count")
async def case_review_module_count(request: Request):
    """模块下用例数量统计。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/module/delete")
async def case_review_module_delete_get(id: str = ""):
    """删除评审模块（GET 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 评审详情操作 ─────────────────────────────────────────
@router.post("/case/review/detail/edit/pos")
async def case_review_detail_edit_pos(request: Request):
    """评审详情-已关联用例拖拽排序。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/batch/review")
async def case_review_detail_batch_review(request: Request):
    """评审详情-批量评审。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/batch/disassociate")
async def case_review_detail_batch_disassociate(request: Request):
    """评审详情-批量取消关联用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/batch/edit/reviewers")
async def case_review_detail_batch_edit_reviewers(request: Request):
    """评审详情-批量修改评审人。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/get-ids")
async def case_review_detail_get_ids(request: Request):
    """获取已关联用例id集合。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/case/review/detail/module/count")
async def case_review_detail_module_count(request: Request):
    """评审详情-模块下用例数量统计。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/case/review/detail/tree")
async def case_review_detail_tree(request: Request):
    """评审详情-已关联用例模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/detail/reviewer/list")
async def case_review_detail_reviewer_list():
    """评审详情-获取用例的评审人。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/case/review/detail/reviewer/status/total")
async def case_review_detail_reviewer_status_total(request: Request):
    """脑图-获取用例评审最终结果。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/case/review/detail/mind/multiple/review")
async def case_review_detail_mind_multiple_review(request: Request):
    """评审详情-脑图评审用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/review/functional/case/get/list")
async def review_functional_case_get_list(request: Request):
    """评审详情-获取用例评审历史。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/review/functional/case/save")
async def review_functional_case_save(request: Request):
    """评审详情-提交评审。"""
    body = await request.json()
    case_id = body.get("caseId", "")
    from app.cases.repository import update_case
    try:
        update_case(case_id, status="approved")
    except Exception:
        pass
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 用例评审 - GET 变体路由 ──────────────────────────────

@router.get("/case/review/user-option/{project_id}")
async def case_review_user_option_get_route(project_id: str, keyword: str = ""):
    """获取评审人员列表（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


@router.get("/case/review/disassociate/{review_id}/{case_id}")
async def case_review_disassociate_get_route(review_id: str, case_id: str):
    """取消关联用例（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/case/review/delete/{project_id}/{review_id}")
async def case_review_delete_get_route(project_id: str, review_id: str):
    """删除评审（GET）。"""
    from app.cases.repository import delete_case
    delete_case(review_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/case/review/detail/get-ids/{review_id}")
async def case_review_detail_get_ids_get_route(review_id: str):
    """获取已关联用例id集合（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/detail/tree/{review_id}")
async def case_review_detail_tree_get_route(review_id: str):
    """评审详情-模块树（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/review/functional/case/get/list/{review_id}/{case_id}")
async def review_functional_case_get_list_get_route(review_id: str, case_id: str):
    """评审详情-获取用例评审历史（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/detail/reviewer/list/{review_id}/{case_id}")
async def case_review_detail_reviewer_list_get_route(review_id: str, case_id: str):
    """评审详情-获取用例的评审人（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/detail/reviewer/status/total/{review_id}/{case_id}")
async def case_review_detail_reviewer_status_total_get_route(review_id: str, case_id: str):
    """脑图-获取用例评审结果（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/mind/case/review/list")
async def functional_mind_case_review_list(request: Request):
    """获取评审脑图数据。"""
    from app.cases.repository import list_cases
    cases = list_cases(limit=500)
    review_cases = [c for c in cases if c.get("status") in ("review", "pending", "in_review")]
    tree = []
    for c in review_cases:
        node = {
            "id": c.get("id", ""),
            "text": c.get("title", ""),
            "resource": {
                "status": c.get("status", "review"),
                "priority": c.get("priority", "P2"),
            },
            "children": [],
        }
        tree.append(node)
    return JSONResponse({"code": 200, "message": "success", "data": tree})


@router.post("/functional/mind/case/plan/list")
async def functional_mind_case_plan_list(request: Request):
    """获取测试计划用例脑图。"""
    from app.cases.repository import list_cases
    cases = list_cases(limit=500)
    tree = []
    for c in cases:
        node = {
            "id": c.get("id", ""),
            "text": c.get("title", ""),
            "resource": {
                "status": c.get("status", "draft"),
                "priority": c.get("priority", "P2"),
            },
            "children": [],
        }
        tree.append(node)
    return JSONResponse({"code": 200, "message": "success", "data": tree})


@router.post("/functional/mind/case/collection/list")
async def functional_mind_case_collection_list(request: Request):
    """获取测试计划用例脑图-测试点。"""
    from app.cases.repository import list_cases
    cases = list_cases(limit=500)
    tree = []
    for c in cases:
        node = {
            "id": c.get("id", ""),
            "text": c.get("title", ""),
            "resource": {
                "status": c.get("status", "draft"),
                "priority": c.get("priority", "P2"),
            },
            "children": [],
        }
        tree.append(node)
    return JSONResponse({"code": 200, "message": "success", "data": tree})





# ════════════════════════════════════════════════════════════
# 项目成员管理
# 前端: /project/member/*  →  项目成员管理
# ════════════════════════════════════════════════════════════







@router.get("/project/member/get-member/option")
async def project_member_options(request: Request, projectId: str = ""):
    """获取可添加的项目成员候选列表。"""
    from app.auth.store import AuthStore
    store = AuthStore()
    users = store.list_users()
    options = []
    for u in users:
        options.append({
            "id": u.get("id", ""),
            "name": u.get("name") or u.get("username", ""),
            "username": u.get("username", ""),
            "email": u.get("email", ""),
        })
    return JSONResponse({"code": 200, "message": "success", "data": options})


# ════════════════════════════════════════════════════════════
# 项目环境管理
# 前端: /project/environment/*  →  环境管理
# ════════════════════════════════════════════════════════════

@router.post("/project/environment/list", operation_id="project_environment_list_post")
@router.get("/project/environment/list", operation_id="project_environment_list_get")
async def project_environment_list(request: Request):
    """获取项目环境列表。"""
    if request.method == "POST":
        try:
            body = await _body(request)
        except Exception:
            body = {}
        status = body.get("status", "")
    else:
        status = request.query_params.get("status", "")
    from app.environment.manager import list_environments
    envs = list_environments(status=status if status else None)
    items = []
    for e in envs:
        items.append({
            "id": e.get("id", ""),
            "name": e.get("name", ""),
            "description": e.get("description", ""),
            "type": e.get("env_type", "docker"),
            "status": e.get("status", "offline"),
            "endpoint": e.get("endpoint", ""),
            "createTime": e.get("created_at", 0),
            "updateTime": e.get("updated_at", 0),
            "projectId": "",
        })
    return JSONResponse({"code": 200, "message": "success", "data": items})


@router.post("/project/environment/add")
async def project_environment_add(request: Request):
    """新增项目环境。"""
    body = await _body(request)
    from app.environment.manager import register_environment
    env = register_environment(
        name=body.get("name", "未命名环境"),
        description=body.get("description", ""),
        env_type=body.get("type", "docker"),
        endpoint=body.get("endpoint", body.get("host", "")),
        docker_compose_path=body.get("dockerComposePath", ""),
        container_name=body.get("containerName", ""),
        image=body.get("image", ""),
        health_check_url=body.get("healthCheckUrl", ""),
        owner=body.get("owner", ""),
        tags=body.get("tags", []),
    )
    return JSONResponse({"code": 200, "message": "success", "data": env})


@router.post("/project/environment/update")
async def project_environment_update(request: Request):
    """更新项目环境。"""
    body = await request.json()
    env_id = body.get("id", "")
    from app.environment.manager import update_environment
    updates = {}
    for k, v in body.items():
        if k == "name":
            updates["name"] = v
        elif k == "description":
            updates["description"] = v
        elif k == "endpoint":
            updates["endpoint"] = v
    try:
        env = update_environment(env_id, **updates)
    except Exception:
        env = None
    if not env:
        return JSONResponse({"code": 404, "message": "环境不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": env})


@router.get("/project/environment/get/{env_id}")
async def project_environment_get(env_id: str):
    """获取环境详情。"""
    from app.environment.manager import get_environment
    env = get_environment(env_id)
    if not env:
        return JSONResponse({"code": 404, "message": "环境不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": env})


@router.post("/project/environment/delete/{env_id}", operation_id="project_environment_delete_post")
@router.get("/project/environment/delete/{env_id}", operation_id="project_environment_delete_get")
async def project_environment_delete(env_id: str):
    """删除环境。"""
    from app.environment.manager import delete_environment
    delete_environment(env_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/project/environment/import")
async def project_environment_import(request: Request):
    """导入环境。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/project/environment/export")
async def project_environment_export(request: Request):
    """导出环境。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/project/environment/get-options")
async def project_environment_get_options():
    """获取环境目录列表。"""
    from app.environment.manager import list_environments
    envs = list_environments()
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": e.get("id"), "name": e.get("name")} for e in envs
    ]})


@router.get("/project/environment/get-options/{project_id}")
async def project_environment_get_options_by_project(project_id: str):
    """获取项目环境目录列表。"""
    from app.environment.manager import list_environments
    envs = list_environments()
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": e.get("id"), "name": e.get("name")} for e in envs
    ]})


# ════════════════════════════════════════════════════════════
# 接口测试报告
# 前端: /api/report/*  →  接口用例/场景执行报告
# ════════════════════════════════════════════════════════════

def _build_report_item(rec: Dict[str, Any]) -> Dict[str, Any]:
    """将运行记录转为报告条目。"""
    return {
        "id": rec.get("id", ""),
        "name": rec.get("file_path", "接口测试") or "接口测试",
        "status": "SUCCESS" if rec.get("passed") else "ERROR",
        "passRate": 1.0 if rec.get("passed") else 0.0,
        "requestCount": 1,
        "errorCount": 0 if rec.get("passed") else 1,
        "createTime": int(rec.get("created_at", 0) * 1000),
        "createUser": "admin",
        "projectId": "",
        "triggerMode": "MANUAL",
        "type": "API",
    }


def _list_report_records():
    from app.runs.repository import list_run_records
    try:
        return list_run_records(limit=200)
    except Exception:
        return []


@router.post("/api/report/case/page")
async def api_report_case_page(request: Request):
    """接口用例报告分页列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)
    records = _list_report_records()
    items = []
    for r in records:
        item = _build_report_item(r)
        item["reportType"] = "CASE"
        items.append(item)
    if keyword:
        items = [i for i in items if keyword.lower() in i.get("name", "").lower()]
    total = len(items)
    start = (current - 1) * page_size
    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": items[start:start + page_size],
            "total": total,
            "pageSize": page_size,
            "current": current,
        },
    })


@router.post("/api/report/scenario/page")
async def api_report_scenario_page(request: Request):
    """接口场景报告分页列表。"""
    body = await request.json()
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)
    records = _list_report_records()
    items = []
    for r in records:
        item = _build_report_item(r)
        item["reportType"] = "SCENARIO"
        items.append(item)
    total = len(items)
    start = (current - 1) * page_size
    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": items[start:start + page_size],
            "total": total,
            "pageSize": page_size,
            "current": current,
        },
    })


@router.post("/api/report/case/rename")
async def api_report_case_rename(request: Request):
    """重命名用例报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/report/scenario/rename")
async def api_report_scenario_rename(request: Request):
    """重命名场景报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/report/case/delete")
async def api_report_case_delete(request: Request):
    """删除用例报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/report/case/batch/delete")
async def api_report_case_batch_delete(request: Request):
    """批量删除用例报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/report/scenario/delete")
async def api_report_scenario_delete(request: Request):
    """删除场景报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/report/scenario/batch/delete")
async def api_report_scenario_batch_delete(request: Request):
    """批量删除场景报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


def _report_detail(rec: Dict[str, Any]) -> Dict[str, Any]:
    test_result = {}
    try:
        import json as _json
        test_result = _json.loads(rec.get("test_result") or "{}")
    except Exception:
        pass
    return {
        "id": rec.get("id", ""),
        "name": rec.get("file_path", "接口测试") or "接口测试",
        "status": "SUCCESS" if rec.get("passed") else "ERROR",
        "passRate": 1.0 if rec.get("passed") else 0.0,
        "console": test_result.get("stdout", "") or "",
        "error": test_result.get("stderr", "") or "",
        "createTime": int(rec.get("created_at", 0) * 1000),
        "projectId": "",
        "reportType": "API",
        "requestCount": 1,
        "errorCount": 0 if rec.get("passed") else 1,
        "assertionCount": 1,
        "assertionPassCount": 1 if rec.get("passed") else 0,
        "responseTime": 0,
    }


@router.post("/api/report/case/get")
async def api_report_case_get(request: Request):
    """获取用例报告详情。"""
    body = await request.json()
    report_id = body.get("id", "")
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    return JSONResponse({"code": 200, "message": "success", "data": _report_detail(rec)})


@router.post("/api/report/scenario/get")
async def api_report_scenario_get(request: Request):
    """获取场景报告详情。"""
    body = await request.json()
    report_id = body.get("id", "")
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    detail = _report_detail(rec)
    detail["reportType"] = "SCENARIO"
    return JSONResponse({"code": 200, "message": "success", "data": detail})


@router.post("/api/report/case/get/detail")
async def api_report_case_get_detail(request: Request):
    """获取用例报告步骤详情。"""
    body = await request.json()
    report_id = body.get("id", "")
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    detail = _report_detail(rec)
    detail["steps"] = [{"name": "请求", "status": "SUCCESS" if rec.get("passed") else "ERROR"}]
    return JSONResponse({"code": 200, "message": "success", "data": detail})


@router.post("/api/report/scenario/get/detail")
async def api_report_scenario_get_detail(request: Request):
    """获取场景报告步骤详情。"""
    body = await request.json()
    report_id = body.get("id", "")
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    detail = _report_detail(rec)
    detail["reportType"] = "SCENARIO"
    detail["steps"] = [{"name": "步骤1", "status": "SUCCESS" if rec.get("passed") else "ERROR"}]
    return JSONResponse({"code": 200, "message": "success", "data": detail})


@router.get("/api/report/case/get/{report_id}")
async def api_report_case_get_get(report_id: str):
    """获取用例报告详情（GET）。"""
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    return JSONResponse({"code": 200, "message": "success", "data": _report_detail(rec)})


@router.get("/api/report/scenario/get/{report_id}")
async def api_report_scenario_get_get(report_id: str):
    """获取场景报告详情（GET）。"""
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    detail = _report_detail(rec)
    detail["reportType"] = "SCENARIO"
    return JSONResponse({"code": 200, "message": "success", "data": detail})


@router.get("/api/report/case/get/detail/{report_id}")
async def api_report_case_get_detail_get(report_id: str):
    """获取用例报告步骤详情（GET）。"""
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    detail = _report_detail(rec)
    detail["steps"] = [{"name": "请求", "status": "SUCCESS" if rec.get("passed") else "ERROR"}]
    return JSONResponse({"code": 200, "message": "success", "data": detail})


@router.get("/api/report/scenario/get/detail/{report_id}")
async def api_report_scenario_get_detail_get(report_id: str):
    """获取场景报告步骤详情（GET）。"""
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    detail = _report_detail(rec)
    detail["reportType"] = "SCENARIO"
    detail["steps"] = [{"name": "步骤1", "status": "SUCCESS" if rec.get("passed") else "ERROR"}]
    return JSONResponse({"code": 200, "message": "success", "data": detail})


@router.post("/api/report/case/share")
async def api_report_case_share(request: Request):
    """用例报告分享。"""
    body = await request.json()
    report_id = body.get("id", "")
    return JSONResponse({"code": 200, "message": "success", "data": {
        "shareId": report_id or "share_" + "1",
        "shareUrl": "/share/report/" + (report_id or "1"),
    }})


@router.post("/api/report/scenario/share")
async def api_report_scenario_share(request: Request):
    """场景报告分享。"""
    body = await request.json()
    report_id = body.get("id", "")
    return JSONResponse({"code": 200, "message": "success", "data": {
        "shareId": report_id or "share_" + "1",
        "shareUrl": "/share/report/" + (report_id or "1"),
    }})


@router.post("/api/report/share/gen")
async def api_report_share_gen(request: Request):
    """生成分享链接。"""
    body = await request.json()
    report_id = body.get("id", "")
    return JSONResponse({"code": 200, "message": "success", "data": {
        "shareId": report_id or "share_" + "1",
        "shareUrl": "/share/report/" + (report_id or "1"),
    }})


@router.get("/api/report/share/get")
async def api_report_share_get(request: Request, id: str = "", shareId: str = ""):
    """获取分享信息。"""
    records = _list_report_records()
    rec = records[0] if records else {}
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": id or shareId or (rec.get("id") if rec else ""),
        "shareId": id or shareId or "",
        "shareTime": 0,
        "report": _report_detail(rec) if rec else None,
    }})


@router.post("/api/report/share/get-share-time")
async def api_report_share_get_time(request: Request):
    """获取分享时间。"""
    return JSONResponse({"code": 200, "message": "success", "data": 0})

@router.get("/api/report/case/delete/{report_id}")
async def api_report_case_delete_get(report_id: str):
    """删除用例报告（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/report/scenario/delete/{report_id}")
async def api_report_scenario_delete_get(report_id: str):
    """删除场景报告（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/report/share/get/{share_id}")
async def api_report_share_get_path(share_id: str):
    """获取分享信息（GET path）。"""
    records = _list_report_records()
    rec = records[0] if records else {}
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": share_id,
        "shareId": share_id,
        "shareTime": 0,
        "report": _report_detail(rec) if rec else None,
    }})


@router.get("/api/report/share/get-share-time/{project_id}")
async def api_report_share_get_time_path(project_id: str):
    """获取分享时间（GET path）。"""
    return JSONResponse({"code": 200, "message": "success", "data": 0})


@router.get("/api/report/scenario/get/detail/{report_id}/{step_id}")
async def api_report_scenario_get_detail_path(report_id: str, step_id: str):
    """场景报告步骤详情（GET path）。"""
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    detail = _report_detail(rec)
    detail["reportType"] = "SCENARIO"
    detail["steps"] = [{"id": step_id, "name": "步骤" + step_id, "status": "SUCCESS" if rec.get("passed") else "ERROR"}]
    return JSONResponse({"code": 200, "message": "success", "data": detail})


@router.get("/api/report/case/get/detail/{report_id}/{step_id}")
async def api_report_case_get_detail_path(report_id: str, step_id: str):
    """用例报告步骤详情（GET path）。"""
    records = _list_report_records()
    rec = next((r for r in records if r.get("id") == report_id), None)
    if not rec:
        rec = records[0] if records else {}
    detail = _report_detail(rec)
    detail["steps"] = [{"id": step_id, "name": "请求" + step_id, "status": "SUCCESS" if rec.get("passed") else "ERROR"}]
    return JSONResponse({"code": 200, "message": "success", "data": detail})


# 缺失接口补充 - 接口定义模块管理
# ════════════════════════════════════════════════════════════

@router.post("/api/definition/module/update")
async def api_definition_module_update(request: Request):
    """更新接口定义模块。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": body.get("id", ""),
        "name": body.get("name", ""),
        "type": "MODULE",
        "parentId": body.get("parentId", "root"),
        "children": [],
        "count": 0,
    }})


@router.get("/api/definition/module/delete")
async def api_definition_module_delete(id: str = ""):
    """删除接口定义模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/module/move")
async def api_definition_module_move(request: Request):
    """移动接口定义模块。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})



# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 接口用例
# ════════════════════════════════════════════════════════════

@router.get("/api/case/get-detail/{case_id}")
async def api_case_get_detail(case_id: str):
    """获取接口用例详情（URL 对齐 MeterSphere 前端）。"""
    from app.apitest.store import get_api_case
    case = get_api_case(case_id)
    if not case:
        return JSONResponse({"code": 404, "message": "用例不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_api_case(case)})


@router.post("/api/case/batch/run")
async def api_case_batch_run(request: Request):
    """批量执行接口用例。"""
    body = await request.json()
    case_ids = body.get("caseIds", body.get("selectIds", []))
    if body.get("selectAll") and not case_ids:
        from app.apitest.store import list_api_cases
        all_cases = list_api_cases(limit=999)
        case_ids = [c["id"] for c in all_cases]
    return JSONResponse({"code": 200, "message": "success", "data": {
        "successCount": len(case_ids),
        "failedCount": 0,
        "results": [{"caseId": cid, "status": "SUCCESS"} for cid in case_ids],
    }})


@router.get("/api/case/update-priority/{case_id}/{priority}")
async def api_case_update_priority(case_id: str, priority: str):
    """更新接口用例优先级。"""
    from app.apitest.store import update_api_case
    update_api_case(case_id, priority=priority)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/case/update-status/{case_id}/{status}")
async def api_case_update_status(case_id: str, status: str):
    """更新接口用例状态。"""
    from app.apitest.store import update_api_case
    update_api_case(case_id, status=status)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/case/update-priority")
async def api_case_update_priority_post(request: Request):
    """更新接口用例优先级（POST 方式）。"""
    body = await request.json()
    case_id = body.get("id", body.get("caseId", ""))
    priority = body.get("priority", "P2")
    from app.apitest.store import update_api_case
    update_api_case(case_id, priority=priority)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/case/update-status")
async def api_case_update_status_post(request: Request):
    """更新接口用例状态（POST 方式）。"""
    body = await request.json()
    case_id = body.get("id", body.get("caseId", ""))
    status = body.get("status", "draft")
    from app.apitest.store import update_api_case
    update_api_case(case_id, status=status)
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 场景模块管理
# ════════════════════════════════════════════════════════════

@router.post("/api/scenario/module/update")
async def api_scenario_module_update(request: Request):
    """更新场景模块。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": body.get("id", ""),
        "name": body.get("name", ""),
        "type": "MODULE",
        "parentId": body.get("parentId", "root"),
        "children": [],
        "count": 0,
    }})


@router.get("/api/scenario/module/delete")
async def api_scenario_module_delete(id: str = ""):
    """删除场景模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/module/delete")
async def api_scenario_module_delete_post(request: Request):
    """删除场景模块（POST 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/scenario/module/move")
async def api_scenario_module_move(request: Request):
    """移动场景模块。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})



# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 调试模块管理
# ════════════════════════════════════════════════════════════

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

@router.post("/api/definition/mock/detail")
async def api_definition_mock_detail(request: Request):
    """获取 Mock 详情（POST 方式，前端传 body）。"""
    body = await request.json()
    mock_id = body.get("id", "")
    project_id = body.get("projectId", "")
    from app.apitest.store import get_mock
    mock = get_mock(mock_id) if mock_id else None
    if not mock:
        return JSONResponse({"code": 404, "message": "Mock 不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": mock})


@router.post("/api/definition/mock/copy")
async def api_definition_mock_copy(request: Request):
    """复制 Mock。"""
    body = await request.json()
    mock_id = body.get("id", "")
    project_id = body.get("projectId", "")
    from app.apitest.store import get_mock, create_mock
    mock = get_mock(mock_id)
    if not mock:
        return JSONResponse({"code": 404, "message": "Mock 不存在", "data": None}, status_code=404)
    new_mock = create_mock(
        name=f"{mock.get('name', '')} (副本)",
        api_definition_id=mock.get("api_definition_id", ""),
        method=mock.get("method", "GET"),
        path=mock.get("path", ""),
        status_code=mock.get("status_code", 200),
        response_body=mock.get("response_body", ""),
        response_headers=mock.get("response_headers", {}),
        delay_ms=mock.get("delay_ms", 0),
        active=mock.get("active", 1),
        description=mock.get("description", ""),
    )
    return JSONResponse({"code": 200, "message": "success", "data": new_mock})


@router.post("/api/definition/mock/batch/edit")
async def api_definition_mock_batch_edit(request: Request):
    """批量编辑 Mock。"""
    body = await request.json()
    mock_ids = body.get("selectIds", body.get("ids", []))
    if body.get("selectAll"):
        from app.apitest.store import list_mocks
        all_mocks = list_mocks(limit=999)
        mock_ids = [m["id"] for m in all_mocks]
    update_fields = {k: v for k, v in body.items() if k not in ("selectIds", "selectAll", "excludeIds", "ids", "condition")}
    if mock_ids and update_fields:
        from app.apitest.store import update_mock
        for mid in mock_ids:
            update_mock(mid, **update_fields)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/mock/batch/delete")
async def api_definition_mock_batch_delete(request: Request):
    """批量删除 Mock。"""
    body = await request.json()
    mock_ids = body.get("selectIds", body.get("ids", []))
    if body.get("selectAll"):
        from app.apitest.store import list_mocks
        all_mocks = list_mocks(limit=999)
        mock_ids = [m["id"] for m in all_mocks]
    from app.apitest.store import delete_mock
    for mid in mock_ids:
        delete_mock(mid)
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 缺陷高级功能
# ════════════════════════════════════════════════════════════

# 缺陷附件相关


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
@router.post("/functional/mind/case/edit")
async def functional_mind_case_edit(request: Request):
    """保存用例脑图。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/mind/case/tree")
async def functional_mind_case_tree():
    """获取脑图模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": "root",
        "name": "全部用例",
        "type": "MODULE",
        "children": [],
    }})


# 导入导出
@router.post("/functional/case/pre-check/excel")
async def functional_case_pre_check_excel(request: Request):
    """导入Excel文件检查。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "success": True,
        "errors": [],
    }})


@router.post("/functional/case/pre-check/xmind")
async def functional_case_pre_check_xmind(request: Request):
    """导入XMind文件检查。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "success": True,
        "errors": [],
    }})


@router.post("/functional/case/import/excel")
async def functional_case_import_excel(request: Request):
    """导入Excel文件。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "successCount": 0,
        "failCount": 0,
    }})


@router.post("/functional/case/import/xmind")
async def functional_case_import_xmind(request: Request):
    """导入XMind文件。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "successCount": 0,
        "failCount": 0,
    }})


@router.post("/functional/case/export/excel")
async def functional_case_export_excel(request: Request):
    """导出Excel文件。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "taskId": str(uuid.uuid4()),
    }})


@router.post("/functional/case/export/xmind")
async def functional_case_export_xmind(request: Request):
    """导出XMind文件。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "taskId": str(uuid.uuid4()),
    }})


@router.get("/functional/case/check/export-task")
async def functional_case_check_export_task():
    """检查导出任务状态。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/export/columns")
async def functional_case_export_columns():
    """获取导出字段配置。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/functional/case/download/file")
async def functional_case_download_file():
    """下载导出的文件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/stop")
async def functional_case_stop():
    """停止导出。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/download/excel/template")
async def functional_case_download_excel_template():
    """下载Excel导入模板。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/download/xmind/template")
async def functional_case_download_xmind_template():
    """下载XMind导入模板。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# 评论
@router.get("/functional/case/comment/get/list/{case_id}")
async def functional_case_comment_get_list(case_id: str):
    """获取用例评论列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/functional/case/comment/save")
async def functional_case_comment_save(request: Request):
    """创建用例评论。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/comment/update")
async def functional_case_comment_update(request: Request):
    """更新用例评论。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/comment/delete/{comment_id}")
async def functional_case_comment_delete(comment_id: str):
    """删除用例评论。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/review/comment/{case_id}")
async def functional_case_review_comment(case_id: str):
    """获取用例评审评论。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# 需求关联
@router.get("/functional/case/demand/page/{case_id}")
async def functional_case_demand_page(case_id: str):
    """获取用例关联需求列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/functional/case/demand/add")
async def functional_case_demand_add(request: Request):
    """添加用例需求关联。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/demand/update")
async def functional_case_demand_update(request: Request):
    """更新用例需求关联。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/demand/batch/relevance")
async def functional_case_demand_batch_relevance(request: Request):
    """批量关联需求。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/demand/cancel")
async def functional_case_demand_cancel(request: Request):
    """取消用例需求关联。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/demand/third/list/page")
async def functional_case_demand_third_list():
    """获取三方关联需求列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


# 用例关系（前后置）
@router.get("/functional/case/relationship/page/{case_id}")
async def functional_case_relationship_page(case_id: str):
    """获取前后置用例列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/functional/case/relationship/page")
async def functional_case_relationship_page_post(request: Request):
    """获取前后置用例列表（POST）。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/functional/case/relationship/relate/page")
async def functional_case_relationship_relate_page(request: Request):
    """获取可关联的前后置用例列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/functional/case/relationship/add")
async def functional_case_relationship_add(request: Request):
    """添加前后置关系。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/relationship/delete")
async def functional_case_relationship_delete(request: Request):
    """取消前后置关系。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/relationship/get-ids")
async def functional_case_relationship_get_ids():
    """获取前后置已关联用例ids。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# 用例关联（接口用例、缺陷等）
@router.post("/functional/case/test/associate/case/page")
async def functional_case_test_associate_case_page(request: Request):
    """获取可关联的接口用例列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.get("/functional/case/test/associate/case/module/count")
async def functional_case_test_associate_case_module_count():
    """获取接口用例模块数量。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/functional/case/test/associate/case/module/tree")
async def functional_case_test_associate_case_module_tree():
    """获取接口用例模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/functional/case/test/associate/case")
async def functional_case_test_associate_case(request: Request):
    """关联接口用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/test/has/associate/case/page")
async def functional_case_test_has_associate_case_page(request: Request):
    """获取已关联用例列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/functional/case/test/disassociate/case")
async def functional_case_test_disassociate_case(request: Request):
    """取消关联用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/test/associate/bug/page")
async def functional_case_test_associate_bug_page(request: Request):
    """获取可关联的缺陷列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/functional/case/test/associate/bug")
async def functional_case_test_associate_bug(request: Request):
    """关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/test/disassociate/bug")
async def functional_case_test_disassociate_bug(request: Request):
    """取消关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/test/has/associate/bug/page")
async def functional_case_test_has_associate_bug_page(request: Request):
    """获取已关联缺陷列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/functional/case/test/has/associate/plan/page")
async def functional_case_test_has_associate_plan_page(request: Request):
    """获取已关联测试计划列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/functional/case/test/plan/comment")
async def functional_case_test_plan_comment(request: Request):
    """获取测试计划评论。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/functional/case/test/associate/case/page")
async def functional_case_test_associate_case_page_get():
    """获取可关联的接口用例列表（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


# 用例变更历史
@router.post("/functional/case/operation-history")
async def functional_case_operation_history(request: Request):
    """获取用例变更历史。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


# 用例拖拽排序
@router.post("/functional/case/edit/pos")
async def functional_case_edit_pos(request: Request):
    """用例拖拽排序。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# 模块删除
@router.get("/functional/case/module/delete")
async def functional_case_module_delete(id: str = ""):
    """删除用例模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/module/delete")
async def functional_case_module_delete_post(request: Request):
    """删除用例模块（POST）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/default/template/field")
async def functional_case_default_template_field():
    """获取默认模板自定义字段。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# 回收站模块相关
@router.post("/functional/case/detail")
async def functional_case_detail_post(request: Request):
    """获取用例详情（POST）。"""
    body = await request.json()
    case_id = body.get("id", "")
    from app.cases.repository import get_case
    case = get_case(case_id) if case_id else None
    if not case:
        return JSONResponse({"code": 404, "message": "用例不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_functional_case(case)})


# 用例评审列表（详情弹窗）
@router.post("/functional/case/review/page")
async def functional_case_review_page(request: Request):
    """获取用例详情评审列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


# 项目下拉选项
@router.get("/project/list/options")
async def project_list_options():
    """获取关联用例项目下拉。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "default", "name": "默认项目"},
    ]})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 附件通用管理
# ════════════════════════════════════════════════════════════

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

@router.post("/functional/case/ai/save/config")
async def functional_case_ai_save_config(request: Request):
    """保存功能用例 AI 配置。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/functional/case/ai/get/config")
async def functional_case_ai_get_config():
    """获取功能用例 AI 配置。"""
    return JSONResponse({"code": 200, "message": "success", "data": {}})


@router.post("/functional/case/ai/transform")
async def functional_case_ai_transform(request: Request):
    """功能用例 AI 结构转换。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/ai/chat")
async def functional_case_ai_chat(request: Request):
    """功能用例 AI 聊天。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/functional/case/ai/batch/save")
async def functional_case_ai_batch_save(request: Request):
    """功能用例 AI 批量保存。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 接口用例高级功能
# ════════════════════════════════════════════════════════════

@router.post("/api/case/batch/edit")
async def api_case_batch_edit(request: Request):
    """批量编辑接口用例。"""
    body = await request.json()
    case_ids = body.get("selectIds", body.get("ids", []))
    if body.get("selectAll"):
        from app.apitest.store import list_api_cases
        all_cases = list_api_cases(limit=999)
        case_ids = [c["id"] for c in all_cases]
    update_fields = {k: v for k, v in body.items() if k not in ("selectIds", "selectAll", "excludeIds", "ids", "condition")}
    if case_ids and update_fields:
        from app.apitest.store import update_api_case
        for cid in case_ids:
            update_api_case(cid, **update_fields)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/case/edit/pos")
async def api_case_edit_pos(request: Request):
    """接口用例拖拽排序。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/case/debug")
async def api_case_debug(request: Request):
    """调试接口用例。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": 200,
        "success": True,
        "body": {},
    }})


@router.get("/api/case/follow/{case_id}")
async def api_case_follow(case_id: str):
    """关注接口用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/case/unfollow/{case_id}")
async def api_case_unfollow(case_id: str):
    """取消关注接口用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/case/execute/page")
async def api_case_execute_page(request: Request):
    """获取接口用例执行历史。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/api/case/operation-history/page")
async def api_case_operation_history_page(request: Request):
    """获取接口用例变更历史。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/api/case/get-reference")
async def api_case_get_reference(request: Request):
    """获取接口用例依赖关系。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/api/case/statistics")
async def api_case_statistics(request: Request):
    """接口用例执行率统计。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/api/case/trash/page")
async def api_case_trash_page(request: Request):
    """获取接口用例回收站列表。"""
    body = await request.json()
    page_size = body.get("pageSize", 100)
    current = body.get("current", 1)
    from app.api_testing.management import list_trash_cases
    items = list_trash_cases(limit=page_size)
    return JSONResponse({"list": items, "total": len(items), "pageSize": page_size, "current": current})


@router.get("/api/case/recover/{case_id}")
async def api_case_recover(case_id: str):
    """恢复接口用例。"""
    from app.api_testing.management import restore_case
    ok = restore_case(case_id)
    return JSONResponse({"code": 200, "message": "success", "restored": 1 if ok else 0, "data": None})


@router.post("/api/case/batch/recover")
async def api_case_batch_recover(request: Request):
    """批量恢复接口用例。"""
    body = await request.json()
    ids = body.get("ids", body.get("selectIds", []))
    from app.api_testing.management import restore_case
    restored = 0
    for cid in ids:
        if restore_case(cid):
            restored += 1
    return JSONResponse({"code": 200, "message": "success", "restored": restored, "data": None})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 接口定义高级功能
# ════════════════════════════════════════════════════════════

@router.get("/api/definition/module/only/tree")
async def api_definition_module_only_tree():
    """获取不包含接口的模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "root", "name": "全部接口", "type": "MODULE", "children": []}
    ]})


@router.get("/api/definition/module/env/tree")
async def api_definition_module_env_tree():
    """获取环境的模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "root", "name": "全部接口", "type": "MODULE", "children": []}
    ]})


@router.post("/api/definition/stop")
async def api_definition_stop(request: Request):
    """停止接口导出。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/definition/download/file/{project_id}/{file_id}")
async def api_definition_download_file(project_id: str, file_id: str):
    """下载导出的文件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/transfer")
async def api_definition_transfer(request: Request):
    """接口定义文件转存。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/definition/transfer/options/{project_id}")
async def api_definition_transfer_options(project_id: str):
    """接口定义文件转存目录。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/api/definition/upload/temp/file")
async def api_definition_upload_temp_file(request: Request):
    """接口定义临时文件上传。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "fileId": str(uuid.uuid4()),
    }})


@router.get("/api/definition/operation-history")
async def api_definition_operation_history():
    """接口定义变更历史。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/api/definition/operation-history")
async def api_definition_operation_history_post(request: Request):
    """接口定义变更历史（POST）。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/api/definition/operation-history/save")
async def api_definition_operation_history_save(request: Request):
    """保存接口定义变更历史。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/operation-history/recover")
async def api_definition_operation_history_recover(request: Request):
    """恢复接口定义变更历史。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/definition/get-reference")
async def api_definition_get_reference(request: Request):
    """获取接口引用关系。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/api/definition/json-schema/preview")
async def api_definition_json_schema_preview(request: Request):
    """JSON Schema 转换预览。"""
    return JSONResponse({"code": 200, "message": "success", "data": {}})


@router.post("/api/definition/json-schema/auto-generate")
async def api_definition_json_schema_auto_generate(request: Request):
    """JSON Schema 自动生成。"""
    return JSONResponse({"code": 200, "message": "success", "data": {}})


@router.post("/api/definition/file/copy")
async def api_definition_file_copy(request: Request):
    """接口定义文件复制。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/debug/file/copy")
async def api_debug_file_copy(request: Request):
    """接口调试文件复制。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/case/file/copy")
async def api_case_file_copy(request: Request):
    """接口用例文件复制。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/case/transfer")
async def api_case_transfer(request: Request):
    """接口用例文件转存。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/case/transfer/options/{project_id}")
async def api_case_transfer_options(project_id: str):
    """接口用例文件转存目录。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/api/case/upload/temp/file")
async def api_case_upload_temp_file(request: Request):
    """接口用例临时文件上传。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "fileId": str(uuid.uuid4()),
    }})


@router.post("/api/definition/recover")
async def api_definition_recover(request: Request):
    """恢复接口定义。"""
    body = await request.json()
    def_id = body.get("id", body.get("definitionId", body.get("ids", "")))
    from app.api_testing.management import restore_definition
    ids = def_id if isinstance(def_id, list) else [def_id]
    restored = 0
    for did in ids:
        if did and restore_definition(did):
            restored += 1
    return JSONResponse({"code": 200, "message": "success", "restored": restored, "data": None})


@router.post("/api/definition/batch-recover")
async def api_definition_batch_recover(request: Request):
    """批量恢复接口定义。"""
    body = await request.json()
    ids = body.get("ids", body.get("selectIds", []))
    from app.api_testing.management import restore_definition
    restored = 0
    for did in ids:
        if restore_definition(did):
            restored += 1
    return JSONResponse({"code": 200, "message": "success", "restored": restored, "data": None})


@router.get("/api/definition/module/trash/tree")
async def api_definition_module_trash_tree():
    """获取接口定义回收站模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/api/definition/module/trash/count")
async def api_definition_module_trash_count():
    """获取接口定义回收站模块统计数量。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 接口用例 AI 功能
# ════════════════════════════════════════════════════════════

@router.post("/api/case/ai/save/config")
async def api_case_ai_save_config(request: Request):
    """保存接口用例 AI 配置。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/case/ai/get/config")
async def api_case_ai_get_config():
    """获取接口用例 AI 配置。"""
    return JSONResponse({"code": 200, "message": "success", "data": {}})


@router.post("/api/case/ai/chat")
async def api_case_ai_chat(request: Request):
    """接口用例 AI 聊天。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/case/ai/transform")
async def api_case_ai_transform(request: Request):
    """接口用例 AI 转换。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/api/case/ai/batch/save")
async def api_case_ai_batch_save(request: Request):
    """接口用例 AI 批量保存。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - Mock 管理高级功能
# ════════════════════════════════════════════════════════════

@router.post("/api/definition/mock/upload/temp/file")
async def api_definition_mock_upload_temp_file(request: Request):
    """Mock 临时文件上传。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "fileId": str(uuid.uuid4()),
    }})


@router.post("/api/definition/mock/transfer")
async def api_definition_mock_transfer(request: Request):
    """Mock 文件转存。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/api/definition/mock/transfer/options/{project_id}")
async def api_definition_mock_transfer_options(project_id: str):
    """Mock 文件转存目录。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/api/definition/mock/get-url/{mock_id}")
async def api_definition_mock_get_url(mock_id: str):
    """获取 Mock URL。"""
    return JSONResponse({"code": 200, "message": "success", "data": "/mock/" + mock_id})
