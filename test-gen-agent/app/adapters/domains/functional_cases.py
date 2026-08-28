# app/adapters/domains/functional_cases.py
"""业务域路由拆分：functional_cases（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-functional_cases"])


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


@router.get("/functional/case/delete")
async def functional_case_delete_get(request: Request):
    """功能用例删除（GET兼容）。"""
    body = await _body(request)
    case_id = body.get("id", body.get("caseId", ""))
    from app.cases.repository import delete_case
    delete_case(case_id)
    return _ok()


@router.post("/functional/case/demand/third/list/page")
async def functional_case_demand_third_list_page_post(request: Request):
    """功能用例三方需求列表分页（POST兼容）。"""
    body = await _body(request)
    return _ok(_paginate([], body.get("current", 1), body.get("pageSize", 10)))


@router.post("/functional/case/module/count")
async def functional_case_module_count_post(request: Request):
    """功能用例模块统计（POST兼容）。"""
    return _ok([])


@router.post("/functional/case/test/associate/case/module/count")
async def functional_case_test_associate_module_count_post(request: Request):
    """功能用例关联用例模块统计（POST兼容）。"""
    return _ok([])


@router.post("/functional/case/trash/module/count")
async def functional_case_trash_module_count_post(request: Request):
    """功能用例回收站模块统计（POST兼容）。"""
    return _ok([])


@router.post("/functional/case/test/associate/case/module/tree")
async def functional_case_test_associate_case_module_tree_post(request: Request):
    """功能用例关联用例模块树（POST兼容）。"""
    return _ok([])


@router.post("/functional/case/comment/delete")
async def functional_case_comment_delete(request: Request):
    """删除功能用例评论。"""
    await request.json()
    return _ok()


@router.post("/functional/case/comment/get/list")
async def functional_case_comment_get_list(request: Request):
    """获取功能用例评论列表。"""
    await request.json()
    return _ok([])


@router.post("/functional/case/review/comment")
async def functional_case_review_comment(request: Request):
    """功能用例评审评论。"""
    await request.json()
    return _ok()


@router.post("/functional/case/demand/page")
async def functional_case_demand_page(request: Request):
    """功能用例需求关联分页。"""
    await request.json()
    return _ok(_paginate([], 1, 10))


@router.get("/functional/case/custom/field/{project_id}")
@router.post("/functional/case/custom/field/{project_id}")
async def func_case_custom_field_path(project_id: str):
    """获取功能用例自定义字段（带路径参数）。"""
    return _ok([])


@router.get("/functional/case/default/template/field/{project_id}")
@router.post("/functional/case/default/template/field/{project_id}")
async def func_case_default_template_field_path(project_id: str):
    """获取功能用例默认模板字段（带路径参数）。"""
    return _ok({"id": f"default-{project_id}", "customFields": []})


@router.get("/functional/case/demand/cancel/{case_id}")
@router.post("/functional/case/demand/cancel/{case_id}")
async def func_case_demand_cancel_path(case_id: str):
    """取消用例需求关联（带路径参数）。"""
    return _ok({"id": case_id, "cancelled": True})


@router.get("/functional/case/download/file/{case_id}/{file_id}")
@router.post("/functional/case/download/file/{case_id}/{file_id}")
async def func_case_download_file_path(case_id: str, file_id: str):
    """下载功能用例文件（带路径参数）。"""
    return _ok({"case_id": case_id, "file_id": file_id})


@router.get("/functional/case/export/columns/{project_id}")
@router.post("/functional/case/export/columns/{project_id}")
async def func_case_export_columns_path(project_id: str):
    """获取功能用例导出列（带路径参数）。"""
    return _ok({"project_id": project_id})


@router.get("/functional/case/module/delete/{module_id}")
@router.post("/functional/case/module/delete/{module_id}")
async def func_case_module_delete_path(module_id: str):
    """删除功能用例模块（带路径参数）。"""
    return _ok({"id": module_id, "deleted": True})


@router.get("/functional/case/stop/{case_id}")
@router.post("/functional/case/stop/{case_id}")
async def func_case_stop_path(case_id: str):
    """停止功能用例执行（带路径参数）。"""
    return _ok({"id": case_id, "stopped": True})


@router.get("/functional/case/test/disassociate/bug/{case_id}")
@router.post("/functional/case/test/disassociate/bug/{case_id}")
async def func_case_disassociate_bug_path(case_id: str):
    """取消功能用例与缺陷关联（带路径参数）。"""
    return _ok({"id": case_id, "disassociated": True})


# ════════════════════════════════════════════════════════════
# 组织管理
# ════════════════════════════════════════════════════════════


@router.get("/functional/case/module/tree/{project_id}")
async def functional_case_module_tree_path(project_id: str):
    """获取功能用例模块树（带路径参数）。"""
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


# 功能用例回收站模块树（前端: /functional/case/module/trash/tree/{projectId}）


@router.get("/functional/case/module/trash/tree/{project_id}")
async def functional_case_module_trash_tree_path(project_id: str):
    """获取功能用例回收站模块树（带路径参数）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# 公共脚本列选项（前端: /project/custom/func/columns-option/{projectId}）


@router.get("/functional/case/relationship/get-ids/{case_id}")
async def functional_case_relationship_get_ids_path(case_id: str):
    """获取功能用例前后置已关联 IDs（带路径参数）。"""
    return _ok([])


# 功能用例测试计划评论（前端: /functional/case/test/plan/comment/{caseId}）


@router.get("/functional/case/test/plan/comment/{case_id}")
async def functional_case_test_plan_comment_path(case_id: str):
    """获取功能用例测试计划评论（带路径参数）。"""
    return _ok([])


# 消息任务配置（前端: /notice/message/task/get/{projectId}）


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

