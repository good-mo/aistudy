# app/routers/apitest.py
"""接口测试路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

from app.apitest import store, service, importer, scenario_runner, engine

router = APIRouter(tags=["apitest"])


@router.get("/api/apitest/stats")
async def api_apitest_stats():
    """接口测试统计。"""
    return JSONResponse(service.dashboard_stats())


# ── 接口定义管理 ──────────────────────────────────────────

@router.get("/api/apitest/definitions")
async def api_list_definitions(keyword: str = "", limit: int = 100, offset: int = 0):
    items = store.list_definitions(keyword, limit, offset)
    return ok({"items": items, "total": store.count_definitions()})


@router.post("/api/apitest/definitions")
async def api_create_definition(req: Request):
    body = await req.json()
    item = store.create_definition(**body)
    return JSONResponse(item)


@router.get("/api/apitest/definitions/{definition_id}")
async def api_get_definition(definition_id: str):
    item = store.get_definition(definition_id)
    if not item:
        return JSONResponse({"error": "接口定义不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/apitest/definitions/{definition_id}")
async def api_update_definition(definition_id: str, req: Request):
    body = await req.json()
    item = store.update_definition(definition_id, **body)
    if not item:
        return JSONResponse({"error": "接口定义不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/apitest/definitions/{definition_id}")
async def api_delete_definition(definition_id: str):
    ok = store.delete_definition(definition_id)
    return ok({"success": ok})


# ── 接口用例管理 ──────────────────────────────────────────

@router.get("/api/apitest/cases")
async def api_list_api_cases(keyword: str = "", limit: int = 100, offset: int = 0):
    items = store.list_api_cases(keyword, limit, offset)
    return ok({"items": items, "total": store.count_api_cases()})


@router.post("/api/apitest/cases")
async def api_create_api_case(req: Request):
    body = await req.json()
    item = store.create_api_case(**body)
    return JSONResponse(item)


@router.get("/api/apitest/cases/{case_id}")
async def api_get_api_case(case_id: str):
    item = store.get_api_case(case_id)
    if not item:
        return JSONResponse({"error": "接口用例不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/apitest/cases/{case_id}")
async def api_update_api_case(case_id: str, req: Request):
    body = await req.json()
    item = store.update_api_case(case_id, **body)
    if not item:
        return JSONResponse({"error": "接口用例不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/apitest/cases/{case_id}")
async def api_delete_api_case(case_id: str):
    ok = store.delete_api_case(case_id)
    return ok({"success": ok})


@router.post("/api/apitest/cases/{case_id}/run")
async def api_run_api_case(case_id: str, req: dict = None):
    env_id = (req or {}).get("environment_id", "")
    result = service.run_case(case_id, env_id)
    return JSONResponse(result)


# ── 接口场景编排 ──────────────────────────────────────────

@router.get("/api/apitest/scenarios")
async def api_list_scenarios(keyword: str = "", limit: int = 100, offset: int = 0):
    items = store.list_scenarios(keyword, limit, offset)
    return ok({"items": items, "total": store.count_scenarios()})


@router.post("/api/apitest/scenarios")
async def api_create_scenario(req: Request):
    body = await req.json()
    item = store.create_scenario(**body)
    return JSONResponse(item)


@router.get("/api/apitest/scenarios/{scenario_id}")
async def api_get_scenario(scenario_id: str):
    item = store.get_scenario(scenario_id)
    if not item:
        return JSONResponse({"error": "接口场景不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/apitest/scenarios/{scenario_id}")
async def api_update_scenario(scenario_id: str, req: Request):
    body = await req.json()
    item = store.update_scenario(scenario_id, **body)
    if not item:
        return JSONResponse({"error": "接口场景不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/apitest/scenarios/{scenario_id}")
async def api_delete_scenario(scenario_id: str):
    ok = store.delete_scenario(scenario_id)
    return ok({"success": ok})


@router.post("/api/apitest/scenarios/{scenario_id}/run")
async def api_run_scenario(scenario_id: str, req: dict = None):
    sc = store.get_scenario(scenario_id)
    if not sc:
        return JSONResponse({"error": "接口场景不存在"}, status_code=404)
    env_id = (req or {}).get("environment_id", "")
    result = scenario_runner.run_scenario(sc, env_override=env_id)
    return JSONResponse(result)


# ── Mock 服务 ─────────────────────────────────────────────

@router.get("/api/apitest/mocks")
async def api_list_mocks(keyword: str = "", limit: int = 100, offset: int = 0):
    items = store.list_mocks(keyword, limit, offset)
    return ok({"items": items, "total": store.count_mocks()})


@router.post("/api/apitest/mocks")
async def api_create_mock(req: Request):
    body = await req.json()
    item = store.create_mock(**body)
    return JSONResponse(item)


@router.get("/api/apitest/mocks/{mock_id}")
async def api_get_mock(mock_id: str):
    """获取 Mock 详情。"""
    item = store.get_mock(mock_id)
    if not item:
        return JSONResponse({"error": "Mock 不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/apitest/mocks/{mock_id}")
async def api_update_mock(mock_id: str, req: Request):
    body = await req.json()
    item = store.update_mock(mock_id, **body)
    if not item:
        return JSONResponse({"error": "Mock 不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/apitest/mocks/{mock_id}")
async def api_delete_mock(mock_id: str):
    ok = store.delete_mock(mock_id)
    return ok({"success": ok})


# ── 环境管理 ─────────────────────────────────────────────

@router.get("/api/apitest/environments")
async def api_list_environments():
    items = store.list_environments()
    return ok({"items": items, "total": store.count_environments()})


@router.post("/api/apitest/environments")
async def api_create_environment(req: Request):
    body = await req.json()
    item = store.create_environment(**body)
    return JSONResponse(item)


@router.get("/api/apitest/environments/{env_id}")
async def api_get_environment(env_id: str):
    """获取环境详情。"""
    item = store.get_environment(env_id)
    if not item:
        return JSONResponse({"error": "环境不存在"}, status_code=404)
    return JSONResponse(item)


@router.put("/api/apitest/environments/{env_id}")
async def api_update_environment(env_id: str, req: Request):
    body = await req.json()
    item = store.update_environment(env_id, **body)
    if not item:
        return JSONResponse({"error": "环境不存在"}, status_code=404)
    return JSONResponse(item)


@router.delete("/api/apitest/environments/{env_id}")
async def api_delete_environment(env_id: str):
    ok = store.delete_environment(env_id)
    return ok({"success": ok})


# ── 接口导入与调试 ────────────────────────────────────────

@router.post("/api/apitest/import")
async def api_import_api(req: Request):
    body = await req.json()
    content = body.get("content", "")
    fmt = body.get("format", "auto")
    result = await asyncio.to_thread(importer.import_content, content, fmt)
    return JSONResponse(result)


@router.post("/api/apitest/debug")
async def api_debug(req: Request):
    body = await req.json()
    result = await asyncio.to_thread(service.run_debug, body)
    return JSONResponse(result)


@router.get("/api/apitest/meta")
async def api_apitest_meta():
    return ok({
        "assert_types": list(engine.ASSERT_TYPES.items()),
        "protocols": ["HTTP", "TCP", "SQL", "DUBBO"],
        "script_languages": ["python", "groovy", "beanshell"],
        "logic_controllers": ["loop", "condition", "wait", "transaction"],
        "import_formats": ["auto", "postman", "swagger"],
    })
