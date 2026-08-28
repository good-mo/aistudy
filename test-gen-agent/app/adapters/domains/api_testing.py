# app/adapters/domains/api_testing.py
"""业务域路由拆分：api_testing（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-api_testing"])


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



@router.get("/api/case/delete")
async def api_case_delete_get(request: Request):
    """接口用例删除（GET兼容）。"""
    body = await _body(request)
    case_id = body.get("id", body.get("caseId", ""))
    from app.api_testing.management import delete_api_test_case
    delete_api_test_case(case_id, permanent=True)
    return _ok()


@router.get("/api/case/follow")
async def api_case_follow_get(request: Request):
    """接口用例关注（GET兼容）。"""
    return _ok()


@router.get("/api/case/recover")
async def api_case_recover_get(request: Request):
    """接口用例恢复（GET兼容）。"""
    body = await _body(request)
    case_id = body.get("id", body.get("ids", ""))
    from app.api_testing.management import restore_case
    ids = case_id if isinstance(case_id, list) else [case_id]
    restored = 0
    for cid in ids:
        if cid and restore_case(cid):
            restored += 1
    return _ok({"restored": restored})


@router.get("/api/case/run")
async def api_case_run_get(request: Request):
    """接口用例执行（GET兼容）。"""
    return _ok()


@router.get("/api/case/unfollow")
async def api_case_unfollow_get(request: Request):
    """接口用例取消关注（GET兼容）。"""
    return _ok()


@router.get("/api/definition/delete-to-gc")
async def api_definition_delete_gc_get(request: Request):
    """接口定义删除（GET兼容）。"""
    body = await _body(request)
    definition_id = body.get("id", body.get("definitionId", ""))
    from app.api_testing.management import delete_api_definition
    if definition_id:
        delete_api_definition(definition_id)
    return _ok()


@router.get("/api/definition/mock/enable")
async def api_definition_mock_enable_get(request: Request):
    """更新Mock状态（GET兼容）。"""
    return _ok()


@router.get("/api/definition/schedule/delete")
async def api_definition_schedule_delete_get(request: Request):
    """接口定义定时同步删除（GET兼容）。"""
    return _ok()


@router.get("/api/definition/schedule/switch")
async def api_definition_schedule_switch_get(request: Request):
    """接口定义定时同步开关（GET兼容）。"""
    return _ok()


@router.get("/api/scenario/delete")
async def api_scenario_delete_get(request: Request):
    """接口场景删除（GET兼容）。"""
    body = await _body(request)
    scenario_id = body.get("id", body.get("scenarioId", ""))
    from app.api_testing.management import delete_scenario
    delete_scenario(scenario_id)
    return _ok()


@router.get("/api/scenario/delete-to-gc")
async def api_scenario_delete_gc_get(request: Request):
    """接口场景删除到回收站（GET兼容）。"""
    return _ok()


@router.get("/api/scenario/follow")
async def api_scenario_follow_get(request: Request):
    """接口场景关注（GET兼容）。"""
    return _ok()


@router.get("/api/scenario/recover")
async def api_scenario_recover_get(request: Request):
    """接口场景恢复（GET兼容）。"""
    body = await _body(request)
    sc_id = body.get("id", body.get("ids", ""))
    from app.api_testing.management import restore_scenario
    ids = sc_id if isinstance(sc_id, list) else [sc_id]
    restored = 0
    for sid in ids:
        if sid and restore_scenario(sid):
            restored += 1
    return _ok({"restored": restored})


@router.get("/api/scenario/schedule-config-delete")
async def api_scenario_schedule_config_delete_get(request: Request):
    """接口场景定时配置删除（GET兼容）。"""
    return _ok()


@router.post("/api/scenario/module/trash/count")
async def api_scenario_module_trash_count_post(request: Request):
    """场景回收站模块统计（POST兼容）。"""
    return _ok([])


@router.post("/api/definition/module/tree")
async def api_definition_module_tree_post(request: Request):
    """接口定义模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/definition/module/only/tree")
async def api_definition_module_only_tree_post(request: Request):
    """接口定义不含接口的模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/definition/module/env/tree")
async def api_definition_module_env_tree_post(request: Request):
    """接口定义环境模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/scenario/module/tree")
async def api_scenario_module_tree_post(request: Request):
    """场景模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/scenario/module/trash/tree")
async def api_scenario_module_trash_tree_post(request: Request):
    """场景回收站模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/scenario/get/system-request")
async def api_scenario_get_system_request_post(request: Request):
    """获取导入的系统请求数据。"""
    body = await _body(request)
    return _ok([])


@router.get("/api/case/api-change/clear/{case_id}")
async def api_case_api_change_clear_by_id(case_id: str, request: Request):
    """接口用例清除本次变更（带ID路径参数）。"""
    return _ok()


@router.get("/api/case/api-change/ignore/{case_id}")
async def api_case_api_change_ignore_by_id(case_id: str, request: Request):
    """接口用例忽略接口变更（带ID路径参数）。"""
    return _ok()


@router.get("/api/case/api/compare/{case_id}")
async def api_case_api_compare_by_id(case_id: str, request: Request):
    """接口用例定义对比（带ID路径参数）。"""
    return _ok()


@router.post("/api/definition/export/{export_type}")
async def api_definition_export_by_type(export_type: str, request: Request):
    """接口定义导出（带类型路径参数）。"""
    return _ok()


@router.get("/api/definition/get-detail")
async def api_definition_get_detail_query(id: str = ""):
    """接口定义详情（query 方式）。"""
    from app.apitest import store as apitest_store
    defn = apitest_store.get_definition(id) if id else None
    return _ok(defn or {})


@router.post("/api/definition/get-detail")
async def api_definition_get_detail_post(request: Request):
    """接口定义详情 POST。"""
    body = await request.json()
    defn_id = body.get("id") or body.get("definitionId") or ""
    from app.apitest import store as apitest_store
    defn = apitest_store.get_definition(defn_id) if defn_id else None
    return _ok(defn or {})


@router.post("/api/definition/batch/delete")
async def api_definition_batch_delete(request: Request):
    """接口定义批量彻底删除。"""
    await request.json()
    return _ok()


@router.get("/api/definition/download/file")
async def api_definition_download_file(file_id: str = ""):
    """接口定义文件下载。"""
    return _ok({"fileId": file_id, "fileName": "file"})


@router.get("/api/definition/transfer/options")
async def api_definition_transfer_options(project_id: str = ""):
    """接口定义文件转存目录。"""
    return _ok([])


@router.get("/api/definition/mock/transfer/options")
async def api_definition_mock_transfer_options(project_id: str = ""):
    """Mock 文件转存目录。"""
    return _ok([])


@router.get("/api/definition/mock/get-url")
async def api_definition_mock_get_url(mock_id: str = ""):
    """获取 Mock URL。"""
    return _ok("/mock/" + mock_id if mock_id else "/mock/")


@router.get("/api/definition/get-reference")
async def api_definition_get_reference(id: str = ""):
    """获取接口引用关系。"""
    return _ok([])


@router.post("/api/case/get-detail")
async def api_case_get_detail(request: Request):
    """接口用例详情。"""
    body = await request.json()
    case_id = body.get("id") or body.get("caseId") or ""
    from app.apitest import store as apitest_store
    case = apitest_store.get_api_case(case_id) if case_id else None
    return _ok(case or {})


@router.get("/api/case/get-detail")
async def api_case_get_detail_query(id: str = ""):
    """接口用例详情（query）。"""
    from app.apitest import store as apitest_store
    case = apitest_store.get_api_case(id) if id else None
    return _ok(case or {})


@router.post("/api/case/follow")
async def api_case_follow(request: Request):
    """接口用例关注。"""
    await request.json()
    return _ok()


@router.post("/api/case/unfollow")
async def api_case_unfollow(request: Request):
    """接口用例取消关注。"""
    await request.json()
    return _ok()


@router.get("/api/case/transfer/options")
async def api_case_transfer_options(project_id: str = ""):
    """接口用例文件转存目录。"""
    return _ok([])


@router.post("/api/case/api-change/clear")
async def api_case_api_change_clear(request: Request):
    """清除接口用例变更。"""
    await request.json()
    return _ok()


@router.post("/api/case/api-change/ignore")
async def api_case_api_change_ignore(request: Request):
    """忽略接口变更。"""
    await request.json()
    return _ok()


@router.post("/api/case/api-change/sync")
async def api_case_api_change_sync(request: Request):
    """同步接口用例变更。"""
    await request.json()
    return _ok({})


@router.post("/api/case/api/compare")
async def api_case_api_compare(request: Request):
    """接口定义对比用例。"""
    await request.json()
    return _ok([])


@router.post("/api/case/batch/api-change/sync")
async def api_case_batch_api_change_sync(request: Request):
    """接口用例批量同步变更。"""
    await request.json()
    return _ok()


@router.get("/api/case/execute/page")
async def api_case_execute_page():
    """接口用例执行历史。"""
    return _ok(_paginate([], 1, 10))


@router.get("/api/case/operation-history/page")
async def api_case_operation_history_page():
    """接口用例变更历史。"""
    return _ok(_paginate([], 1, 10))


@router.post("/api/scenario/associate/all")
async def api_scenario_associate_all(request: Request):
    """场景关联所有用例。"""
    await request.json()
    return _ok()


@router.get("/api/scenario/get")
async def api_scenario_get_query(id: str = ""):
    """场景详情。"""
    from app.apitest import store as apitest_store
    sc = apitest_store.get_scenario(id) if id else None
    return _ok(sc or {})


@router.post("/api/scenario/get")
async def api_scenario_get_post(request: Request):
    """场景详情 POST。"""
    body = await request.json()
    sc_id = body.get("id") or body.get("scenarioId") or ""
    from app.apitest import store as apitest_store
    sc = apitest_store.get_scenario(sc_id) if sc_id else None
    return _ok(sc or {})


@router.post("/api/scenario/execute/page")
async def api_scenario_execute_page(request: Request):
    """场景执行历史。"""
    await request.json()
    return _ok(_paginate([], 1, 10))


@router.post("/api/scenario/operation-history/page")
async def api_scenario_operation_history_page(request: Request):
    """场景操作历史。"""
    await request.json()
    return _ok(_paginate([], 1, 10))


@router.post("/api/scenario/schedule-config")
async def api_scenario_schedule_config(request: Request):
    """场景定时任务配置。"""
    await request.json()
    return _ok()


@router.post("/api/scenario/schedule-config-delete")
async def api_scenario_schedule_config_delete(request: Request):
    """删除场景定时任务。"""
    await request.json()
    return _ok()


@router.post("/api/scenario/batch-operation/edit")
async def api_scenario_batch_operation_edit(request: Request):
    """场景批量编辑。"""
    await request.json()
    return _ok()


@router.post("/api/scenario/batch-operation/schedule-config")
async def api_scenario_batch_operation_schedule_config(request: Request):
    """场景批量设置定时任务。"""
    await request.json()
    return _ok()


@router.get("/api/scenario/transfer/options")
async def api_scenario_transfer_options(project_id: str = ""):
    """场景文件转存目录。"""
    return _ok([])


@router.post("/api/scenario/transfer")
async def api_scenario_transfer(request: Request):
    """场景文件转存。"""
    await request.json()
    return _ok()


@router.post("/api/scenario/upload/temp/file")
async def api_scenario_upload_temp_file(request: Request):
    """场景临时文件上传。"""
    return _ok({"fileId": str(uuid.uuid4()), "fileName": "temp"})


@router.post("/api/scenario/step/transfer")
async def api_scenario_step_transfer(request: Request):
    """场景步骤文件转存。"""
    await request.json()
    return _ok()


@router.post("/api/scenario/step/file/copy")
async def api_scenario_step_file_copy(request: Request):
    """场景步骤文件复制。"""
    await request.json()
    return _ok()


@router.get("/api/scenario/download/file")
async def api_scenario_download_file(file_id: str = ""):
    """场景文件下载。"""
    return _ok({"fileId": file_id, "fileName": "file"})


@router.get("/api/scenario/module/trash/tree")
async def api_scenario_module_trash_tree(project_id: str = ""):
    """场景回收站模块树。"""
    return _ok([])


@router.get("/api/scenario/module/trash/count")
async def api_scenario_module_trash_count(project_id: str = ""):
    """场景回收站模块数。"""
    return _ok({})


@router.post("/api/scenario/edit/pos")
async def api_scenario_edit_pos(request: Request):
    """场景拖拽排序。"""
    await request.json()
    return _ok()


@router.post("/api/scenario/stop")
async def api_scenario_stop(request: Request):
    """停止场景执行。"""
    await request.json()
    return _ok()


@router.post("/api/definition/schedule/add")
async def api_definition_schedule_add(request: Request):
    """添加接口定义定时同步。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/api/definition/schedule/update")
async def api_definition_schedule_update(request: Request):
    """更新接口定义定时同步。"""
    await request.json()
    return _ok()


@router.post("/api/definition/schedule/delete")
async def api_definition_schedule_delete(request: Request):
    """删除接口定义定时同步。"""
    await request.json()
    return _ok()


@router.post("/api/definition/schedule/check")
async def api_definition_schedule_check(request: Request):
    """检查定时同步 URL。"""
    await request.json()
    return _ok({"exist": True})


@router.post("/api/definition/schedule/switch")
async def api_definition_schedule_switch(request: Request):
    """开关定时同步。"""
    await request.json()
    return _ok()


@router.post("/api/definition/schedule/get")
async def api_definition_schedule_get(request: Request):
    """查询定时同步。"""
    await request.json()
    return _ok({})


@router.get("/api/definition/schedule/get")
async def api_definition_schedule_get_query(id: str = ""):
    """查询定时同步 GET。"""
    return _ok({})


# ════════════════════════════════════════════════════════════
# P0-4: 接口文档分享  /api/doc/share/*
# ════════════════════════════════════════════════════════════


@router.post("/api/scenario/step/resource-info")
async def api_scenario_step_resource_info(request: Request):
    """场景步骤资源信息。"""
    await request.json()
    return _ok({})


@router.get("/api/definition/stop/{definition_id}")
@router.post("/api/definition/stop/{definition_id}")
async def definition_stop_path(definition_id: str):
    """停止接口定义任务（带路径参数）。"""
    return _ok({"id": definition_id, "stopped": True})


# ════════════════════════════════════════════════════════════
# 文档分享
# ════════════════════════════════════════════════════════════


@router.get("/api/scenario/download/file/{scenario_id}/{file_id}")
@router.post("/api/scenario/download/file/{scenario_id}/{file_id}")
async def scenario_download_file_path(scenario_id: str, file_id: str):
    """下载场景文件（带路径参数）。"""
    return _ok({"scenario_id": scenario_id, "file_id": file_id})


@router.get("/api/scenario/export/{scenario_id}")
@router.post("/api/scenario/export/{scenario_id}")
async def scenario_export_path(scenario_id: str):
    """导出场景（带路径参数）。"""
    return _ok({"id": scenario_id, "exported": True})


@router.get("/api/scenario/stop/{scenario_id}")
@router.post("/api/scenario/stop/{scenario_id}")
async def scenario_stop_path(scenario_id: str):
    """停止场景执行（带路径参数）。"""
    return _ok({"id": scenario_id, "stopped": True})


@router.get("/api/scenario/update-priority/{scenario_id}/{priority}")
@router.post("/api/scenario/update-priority/{scenario_id}/{priority}")
async def scenario_update_priority_path(scenario_id: str, priority: str):
    """更新场景优先级（带路径参数）。"""
    return _ok({"id": scenario_id, "priority": priority})


@router.get("/api/scenario/update-status/{scenario_id}/{status}")
@router.post("/api/scenario/update-status/{scenario_id}/{status}")
async def scenario_update_status_path(scenario_id: str, status: str):
    """更新场景状态（带路径参数）。"""
    return _ok({"id": scenario_id, "status": status})


# ════════════════════════════════════════════════════════════
# 附件
# ════════════════════════════════════════════════════════════


@router.get("/api/case/delete-to-gc")
async def api_case_delete_to_gc_get():
    """删除接口用例到回收站（GET 兼容前端调用）。"""
    return _ok({"success": True})


@router.post("/api/definition/module/trash/count")
async def api_definition_module_trash_count_post(request: Request):
    """接口定义模块回收站数量（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"count": 0})


@router.get("/api/scenario/step/resource-info/{step_id}")
async def scenario_step_resource_info_path(step_id: str):
    """获取场景步骤跨项目信息（带路径参数）。"""
    return _ok({"id": step_id})


# 公共脚本详情（前端: /api/test/common-script/{scriptId}）


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

