# app/routers/frontend.py
"""前端 API 测试页面路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

router = APIRouter(tags=["frontend"])


@router.post("/api/api-definitions/import")
async def front_api_import_definitions(req: Request):
    """前端导入接口定义 Postman/Swagger。"""
    from app.api_testing.management import import_from_postman, import_from_swagger
    body = await req.json()
    fmt = body.get("format", "auto")
    data = body.get("data", body)
    if fmt in ("postman", "auto"):
        result = await asyncio.to_thread(import_from_postman, data)
        if result.get("imported", 0) > 0:
            return JSONResponse(result)
    if fmt in ("swagger", "auto"):
        result = await asyncio.to_thread(import_from_swagger, data)
        return JSONResponse(result)
    return ok({"imported": 0, "errors": ["无法识别导入格式"]})


@router.get("/api/api-definitions")
async def front_api_list_definitions(
    search: str = "", method: str = "", protocol: str = "", limit: int = 100,
):
    """前端接口定义列表。"""
    from app.api_testing.management import list_api_definitions
    defs = list_api_definitions(search=search, method=method, protocol=protocol, limit=limit)
    return ok({"definitions": defs})


@router.post("/api/api-definitions")
async def front_api_create_definition(req: Request):
    """前端创建接口定义。"""
    from app.api_testing.management import create_api_definition
    body = await req.json()
    item = create_api_definition(
        name=body.get("name", ""), method=body.get("method", "GET"),
        path=body.get("path", ""), protocol=body.get("protocol", "HTTP"),
        description=body.get("description", ""),
        request_headers=body.get("request_headers"),
        request_params=body.get("request_params"),
        request_body=body.get("request_body", ""),
        request_body_type=body.get("request_body_type", "json"),
        response_code=body.get("response_code", "200"),
        response_headers=body.get("response_headers"),
        response_body=body.get("response_body", ""),
        response_body_type=body.get("response_body_type", "json"),
        tags=body.get("tags"),
    )
    return JSONResponse(item)


@router.get("/api/api-definitions/{definition_id}")
async def front_api_get_definition(definition_id: str):
    """前端获取接口定义详情。"""
    from app.api_testing.management import get_api_definition
    item = get_api_definition(definition_id)
    if not item:
        return JSONResponse({"error": "接口定义不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/api-definitions/{definition_id}")
async def front_api_update_definition(definition_id: str, req: Request):
    """前端更新接口定义。"""
    from app.api_testing.management import update_api_definition
    body = await req.json()
    item = update_api_definition(definition_id, **body)
    if not item:
        return JSONResponse({"error": "接口定义不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/api-definitions/{definition_id}")
async def front_api_delete_definition(definition_id: str):
    """前端删除接口定义。"""
    from app.api_testing.management import delete_api_definition
    ok = delete_api_definition(definition_id)
    if not ok:
        return JSONResponse({"error": "接口定义不存在"}, status_code=404)
    return ok({"success": True})


# ── 接口用例管理（前端）───────────────────────────────────
@router.get("/api/api-test-cases")
async def front_api_list_test_cases(search: str = "", limit: int = 100):
    """前端接口用例列表。"""
    from app.api_testing.management import list_api_test_cases
    cases = list_api_test_cases(search=search, limit=limit)
    return ok({"cases": cases})


@router.post("/api/api-test-cases")
async def front_api_create_test_case(req: Request):
    """前端创建接口用例。"""
    from app.api_testing.management import create_api_test_case
    body = await req.json()
    item = create_api_test_case(
        name=body.get("name", ""),
        definition_id=body.get("definition_id", ""),
        method=body.get("method", "GET"),
        path=body.get("path", ""),
        request_headers=body.get("request_headers"),
        request_params=body.get("request_params"),
        request_body=body.get("request_body", ""),
        request_body_type=body.get("request_body_type", "json"),
        assertions=body.get("assertions", []),
        pre_scripts=body.get("pre_scripts", []),
        post_scripts=body.get("post_scripts", []),
        pre_sql=body.get("pre_sql", ""),
        post_sql=body.get("post_sql", ""),
        variables=body.get("variables"),
        environment_id=body.get("environment_id"),
        timeout=body.get("timeout", 30),
        retry_count=body.get("retry_count", 0),
    )
    return JSONResponse(item)


@router.get("/api/api-test-cases/{case_id}")
async def front_api_get_test_case(case_id: str):
    """前端获取接口用例。"""
    from app.api_testing.management import get_api_test_case
    item = get_api_test_case(case_id)
    if not item:
        return JSONResponse({"error": "接口用例不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/api-test-cases/{case_id}")
async def front_api_update_test_case(case_id: str, req: Request):
    """前端更新接口用例。"""
    from app.api_testing.management import update_api_test_case
    body = await req.json()
    item = update_api_test_case(case_id, **body)
    if not item:
        return JSONResponse({"error": "接口用例不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/api-test-cases/{case_id}")
async def front_api_delete_test_case(case_id: str):
    """前端删除接口用例。"""
    from app.api_testing.management import delete_api_test_case
    ok = delete_api_test_case(case_id)
    if not ok:
        return JSONResponse({"error": "接口用例不存在"}, status_code=404)
    return ok({"success": True})


# ── 场景管理（前端）───────────────────────────────────────
@router.get("/api/scenarios")
async def front_api_list_scenarios(limit: int = 100):
    """前端场景列表。"""
    from app.api_testing.management import list_scenarios
    scenarios = list_scenarios(limit=limit)
    return ok({"scenarios": scenarios})


@router.post("/api/scenarios")
async def front_api_create_scenario(req: Request):
    """前端创建场景。"""
    from app.api_testing.management import create_scenario
    body = await req.json()
    item = create_scenario(
        name=body.get("name", ""),
        steps=body.get("steps", []),
        description=body.get("description", ""),
        environment_id=body.get("environment_id"),
    )
    return JSONResponse(item)


@router.post("/api/scenarios/{scenario_id}/execute")
async def front_api_execute_scenario(scenario_id: str):
    """前端执行场景。"""
    from app.api_testing.management import execute_scenario
    result = execute_scenario(scenario_id)
    return JSONResponse(result)


@router.get("/api/scenarios/{scenario_id}")
async def front_api_get_scenario(scenario_id: str):
    """前端获取场景。"""
    from app.api_testing.management import get_scenario
    item = get_scenario(scenario_id)
    if not item:
        return JSONResponse({"error": "场景不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/scenarios/{scenario_id}")
async def front_api_update_scenario(scenario_id: str, req: Request):
    """前端更新场景。"""
    from app.api_testing.management import update_scenario
    body = await req.json()
    item = update_scenario(scenario_id, **body)
    if not item:
        return JSONResponse({"error": "场景不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/scenarios/{scenario_id}")
async def front_api_delete_scenario(scenario_id: str):
    """前端删除场景。"""
    from app.api_testing.management import delete_scenario
    ok = delete_scenario(scenario_id)
    if not ok:
        return JSONResponse({"error": "场景不存在"}, status_code=404)
    return ok({"success": True})


# ── Mock 服务管理（前端）──────────────────────────────────
@router.get("/api/mock-services")
async def front_api_list_mock_services(limit: int = 100):
    """前端 Mock 服务列表。"""
    from app.api_testing.management import list_mock_services
    mocks = list_mock_services(limit=limit)
    return ok({"mocks": mocks})


@router.post("/api/mock-services")
async def front_api_create_mock_service(req: Request):
    """前端创建 Mock 服务。"""
    from app.api_testing.management import create_mock_service
    body = await req.json()
    item = create_mock_service(
        name=body.get("name", ""),
        method=body.get("method", "GET"),
        path=body.get("path", ""),
        response_code=body.get("response_code", 200),
        response_headers=body.get("response_headers"),
        response_body=body.get("response_body", ""),
        delay_ms=body.get("delay_ms", 0),
    )
    return JSONResponse(item)


@router.get("/api/mock-services/{mock_id}")
async def front_api_get_mock_service(mock_id: str):
    """前端获取 Mock 服务。"""
    from app.api_testing.management import get_mock_service
    item = get_mock_service(mock_id)
    if not item:
        return JSONResponse({"error": "Mock 服务不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/mock-services/{mock_id}")
async def front_api_update_mock_service(mock_id: str, req: Request):
    """前端更新 Mock 服务。"""
    from app.api_testing.management import update_mock_service
    body = await req.json()
    item = update_mock_service(mock_id, **body)
    if not item:
        return JSONResponse({"error": "Mock 服务不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/mock-services/{mock_id}")
async def front_api_delete_mock_service(mock_id: str):
    """前端删除 Mock 服务。"""
    from app.api_testing.management import delete_mock_service
    ok = delete_mock_service(mock_id)
    if not ok:
        return JSONResponse({"error": "Mock 服务不存在"}, status_code=404)
    return ok({"success": True})


# ── 定义/用例回收站（前端）────────────────────────────────
@router.get("/api/definition/trash/page")
async def front_api_definition_trash_page(req: Request):
    """接口定义回收站分页。"""
    from app.api_testing.management import list_trashed_definitions
    body = await req.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)
    items = list_trashed_definitions(keyword=keyword, limit=page_size, offset=(current-1)*page_size)
    return ok({"list": items, "total": len(items)})


@router.get("/api/definition/delete")
async def front_api_definition_delete(id: str = ""):
    """接口定义删除（GET 兼容）。"""
    from app.api_testing.management import delete_api_definition
    ok = delete_api_definition(id)
    return JSONResponse({"code": 200, "message": "success", "data": {"deleted": ok}})


@router.post("/api/definition/batch-delete")
async def front_api_definition_batch_delete(req: Request):
    """批量删除接口定义。"""
    body = await req.json()
    ids = body.get("ids", [])
    from app.api_testing.management import delete_api_definition
    deleted = 0
    for iid in ids:
        if delete_api_definition(iid):
            deleted += 1
    return ok({"deleted": deleted})


@router.post("/api/case/recover")
async def front_api_case_recover(req: Request):
    """恢复接口用例。"""
    body = await req.json()
    case_id = body.get("id", "")
    from app.api_testing.management import recover_api_test_case
    result = recover_api_test_case(case_id)
    return JSONResponse(result)


@router.post("/api/scenario/trash/page")
async def front_api_scenario_trash_page(req: Request):
    """场景回收站分页。"""
    body = await req.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)
    from app.api_testing.management import list_trashed_scenarios
    items = list_trashed_scenarios(keyword=keyword, limit=page_size, offset=(current-1)*page_size)
    return ok({"list": items, "total": len(items)})


@router.post("/api/scenario/recover")
async def front_api_scenario_recover(req: Request):
    """恢复场景。"""
    body = await req.json()
    scenario_id = body.get("id", "")
    from app.api_testing.management import recover_scenario
    result = recover_scenario(scenario_id)
    return JSONResponse(result)


@router.post("/api/scenario/batch-operation/recover-gc")
async def front_api_scenario_batch_recover_gc(req: Request):
    """批量恢复/回收场景。"""
    body = await req.json()
    ids = body.get("ids", [])
    from app.api_testing.management import recover_scenario
    recovered = 0
    for sid in ids:
        if recover_scenario(sid):
            recovered += 1
    return ok({"recovered": recovered})


@router.post("/api/scenario/batch-operation/delete")
async def front_api_scenario_batch_delete(req: Request):
    """批量删除场景。"""
    body = await req.json()
    ids = body.get("ids", [])
    from app.api_testing.management import delete_scenario
    deleted = 0
    for sid in ids:
        if delete_scenario(sid):
            deleted += 1
    return ok({"deleted": deleted})


@router.get("/mock/{path:path}", operation_id="mock_call_get_front")
@router.post("/mock/{path:path}", operation_id="mock_call_post_front")
@router.put("/mock/{path:path}", operation_id="mock_call_put_front")
@router.delete("/mock/{path:path}", operation_id="mock_call_delete_front")
@router.patch("/mock/{path:path}", operation_id="mock_call_patch_front")
async def mock_call_front(path: str):
    """Mock 服务调用。"""
    from app.apitest.engine import handle_mock_request
    return handle_mock_request(path)
