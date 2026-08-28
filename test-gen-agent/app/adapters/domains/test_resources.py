# app/adapters/domains/test_resources.py
"""业务域路由拆分：test_resources（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-test_resources"])


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


@router.get("/test/resource/pool/delete")
async def test_resource_pool_delete_get(request: Request):
    """测试资源池删除（GET兼容）。"""
    return _ok()


@router.post("/test/resource/pool/capacity/detail")
async def test_resource_pool_capacity_detail_post(request: Request):
    """测试资源池容量详情（POST兼容）。"""
    return _ok({})


@router.post("/test-plan/statistics")
async def test_plan_statistics_post(request: Request):
    """测试计划统计（POST兼容）。"""
    return _ok({})


@router.post("/test-plan/functional/case/tree")
async def test_plan_functional_case_tree_post(request: Request):
    """测试计划功能用例树（POST兼容）。"""
    return _ok([])


@router.post("/test-plan/module/count")
async def test_plan_module_count(request: Request):
    """测试计划模块统计。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# 用户 API Key 和本地执行配置
# ════════════════════════════════════════════════════════════


@router.post("/test/resource/pool/add")
async def test_resource_pool_add(request: Request):
    """添加资源池。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/test/resource/pool/update")
async def test_resource_pool_update(request: Request):
    """更新资源池。"""
    await request.json()
    return _ok()


@router.post("/test/resource/pool/delete")
async def test_resource_pool_delete(request: Request):
    """删除资源池。"""
    await request.json()
    return _ok()


@router.post("/test/resource/pool/page")
async def test_resource_pool_page(request: Request):
    """资源池分页。"""
    body = await request.json()
    return _ok(_paginate([], body.get("current", 1), body.get("pageSize", 10)))


@router.get("/test/resource/pool/detail")
async def test_resource_pool_detail(id: str = ""):
    """资源池详情。"""
    return _ok({})


@router.post("/test/resource/pool/set/enable/")
async def test_resource_pool_set_enable(id: str = "", enable: bool = True):
    """设置资源池启用。"""
    return _ok()


@router.get("/test/resource/pool/capacity/detail")
async def test_resource_pool_capacity_detail(id: str = ""):
    """资源池容量详情。"""
    return _ok({})


@router.get("/test/resource/pool/capacity/task/list")
async def test_resource_pool_capacity_task_list(id: str = ""):
    """资源池容量任务列表。"""
    return _ok([])


# 接口测试资源池


@router.get("/test-plan")
async def test_plan_get(id: str = ""):
    """测试计划详情。"""
    try:
        from app.test_plan.store import test_plan_store
        plan = test_plan_store.get_plan(id) if id else None
        return _ok(plan or {})
    except Exception:
        return _ok({})


@router.get("/test-plan-execute/user-option")
async def test_plan_execute_user_option(project_id: str = ""):
    """测试计划执行用户选项。"""
    return _ok([])


@router.post("/test-plan/api/case/run")
async def test_plan_api_case_run(request: Request):
    """测试计划接口用例执行。"""
    await request.json()
    return _ok()


@router.post("/test-plan/api/case/disassociate/bug")
async def test_plan_api_case_disassociate_bug(request: Request):
    """测试计划接口用例取消关联缺陷。"""
    await request.json()
    return _ok()


@router.post("/test-plan/api/scenario/run")
async def test_plan_api_scenario_run(request: Request):
    """测试计划场景执行。"""
    await request.json()
    return _ok()


@router.post("/test-plan/api/scenario/disassociate/bug")
async def test_plan_api_scenario_disassociate_bug(request: Request):
    """测试计划场景取消关联缺陷。"""
    await request.json()
    return _ok()


@router.post("/test-plan/report/get-task")
async def test_plan_report_get_task(request: Request):
    """测试计划报告任务。"""
    await request.json()
    return _ok({})


# ════════════════════════════════════════════════════════════
# P2-11: 错误注入  /fake/error/*
# ════════════════════════════════════════════════════════════


@router.get("/test-plan/copy/{plan_id}")
@router.post("/test-plan/copy/{plan_id}")
async def test_plan_copy_path(plan_id: str):
    """复制测试计划（带路径参数）。"""
    return _ok({"id": plan_id, "copied": True})


# ════════════════════════════════════════════════════════════
# 用户平台
# ════════════════════════════════════════════════════════════


@router.get("/test-plan/report/get/{report_id}")
async def test_plan_report_get_path(report_id: str):
    """测试计划报告详情（带路径参数）。"""
    return _ok({"id": report_id, "name": "测试计划报告"})


@router.get("/test-plan/report/get-layout/{report_id}")
async def test_plan_report_get_layout_path(report_id: str):
    """获取报告布局（带路径参数）。"""
    return _ok({"id": report_id, "layout": "default"})


@router.get("/test-plan/report/get-result/{plan_id}")
async def test_plan_report_get_result_path(plan_id: str):
    """测试计划执行结果（带路径参数）。"""
    return _ok({"plan_id": plan_id, "status": "SUCCESS"})


@router.get("/test-plan/report/delete/{report_id}")
async def test_plan_report_delete_path(report_id: str):
    """删除测试计划报告（带路径参数）。"""
    return _ok({"id": report_id, "deleted": True})


@router.post("/test-plan/report/rename/{report_id}")
async def test_plan_report_rename_path(report_id: str):
    """重命名测试计划报告（带路径参数）。"""
    return _ok({"id": report_id, "renamed": True})


@router.post("/test-plan/report/export/{report_id}")
async def test_plan_report_export_path(report_id: str):
    """导出测试计划报告（带路径参数）。"""
    return _ok({"id": report_id, "exported": True})


@router.get("/test-plan/report/share/get-layout/{share_id}/{report_id}")
async def test_plan_report_share_get_layout_path(share_id: str, report_id: str):
    """获取分享报告布局（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "layout": "default"})


@router.get("/test-plan/report/share/get-share-time/{share_id}")
async def test_plan_report_share_time_path(share_id: str):
    """获取分享链接时效（带路径参数）。"""
    return _ok({"share_id": share_id, "expired": False})


@router.get("/test-plan/report/share/get/detail/{share_id}/{report_id}")
async def test_plan_report_share_get_detail_path(share_id: str, report_id: str):
    """分享报告详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "name": "分享报告"})


@router.get("/test-plan/report/share/get/{share_id}")
async def test_plan_report_share_get_path(share_id: str):
    """获取分享链接（带路径参数）。"""
    return _ok({"share_id": share_id, "url": f"/test-plan/report/share/get/{share_id}"})


# ════════════════════════════════════════════════════════════
# 接口测试报告模块（修复缺失 API）
# ════════════════════════════════════════════════════════════


@router.get("/test-plan/group-list/{project_id}")
async def test_plan_group_list_path(project_id: str):
    """测试计划组列表（带路径参数）。"""
    return _ok({"project_id": project_id})


# ════════════════════════════════════════════════════════════
# AI 配置与对话模块（修复缺失 API）
# ════════════════════════════════════════════════════════════

