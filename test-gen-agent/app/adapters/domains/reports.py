# app/adapters/domains/reports.py
"""业务域路由拆分：reports（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-reports"])


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


@router.post("/api/report/case/export/{report_id}")
async def api_report_case_export_by_id(report_id: str, request: Request):
    """接口用例报告导出（带报告ID路径参数）。"""
    return _ok()


@router.post("/api/report/case/get/")
async def api_report_case_get_trailing(request: Request):
    """接口用例报告详情（尾斜杠）。"""
    await request.json()
    return _ok({"id": "", "name": "接口用例报告", "status": "SUCCESS"})


@router.post("/api/report/case/get/detail/")
async def api_report_case_get_detail_trailing(request: Request):
    """接口用例报告详情步骤（尾斜杠）。"""
    await request.json()
    return _ok({"steps": []})


@router.post("/api/report/case/share/detail")
async def api_report_case_share_detail(request: Request):
    """接口用例报告分享详情。"""
    await request.json()
    return _ok({"steps": []})


@router.post("/api/report/scenario/share/detail")
async def api_report_scenario_share_detail(request: Request):
    """场景报告分享详情。"""
    await request.json()
    return _ok({"steps": []})


@router.post("/api/report/share/get")
async def api_report_share_get(request: Request):
    """获取分享信息。"""
    await request.json()
    return _ok({})


@router.post("/api/report/case/task-report")
async def api_report_case_task_report(request: Request):
    """接口用例任务报告。"""
    await request.json()
    return _ok([])


@router.post("/api/report/scenario/task-report")
async def api_report_scenario_task_report(request: Request):
    """场景任务报告。"""
    await request.json()
    return _ok([])


@router.post("/api/report/scenario/task-step")
async def api_report_scenario_task_step(request: Request):
    """场景任务报告步骤。"""
    await request.json()
    return _ok([])


@router.post("/api/report/case/export")
async def api_report_case_export(request: Request):
    """接口用例报告导出。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4()), "fileName": "report.zip"})


@router.post("/api/report/case/batch-export")
async def api_report_case_batch_export(request: Request):
    """接口用例报告批量导出。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/api/report/case/batch-param")
async def api_report_case_batch_param(request: Request):
    """接口用例批量导出参数。"""
    await request.json()
    return _ok([])


@router.post("/api/report/scenario/export")
async def api_report_scenario_export(request: Request):
    """场景报告导出。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/api/report/scenario/batch-export")
async def api_report_scenario_batch_export(request: Request):
    """场景报告批量导出。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/api/report/scenario/batch-param")
async def api_report_scenario_batch_param(request: Request):
    """场景报告批量导出参数。"""
    await request.json()
    return _ok([])


@router.get("/api/report/scenario/export/{report_id}")
@router.post("/api/report/scenario/export/{report_id}")
async def report_scenario_export_path(report_id: str):
    """导出场景报告（带路径参数）。"""
    return _ok({"id": report_id, "exported": True})


# ════════════════════════════════════════════════════════════
# 场景
# ════════════════════════════════════════════════════════════


@router.post("/api/report/case/rename/{report_id}")
async def api_report_case_rename_path(report_id: str):
    """接口用例报告重命名（带路径参数）。"""
    return _ok({"id": report_id, "renamed": True})


@router.post("/api/report/scenario/rename/{report_id}")
async def api_report_scenario_rename_path(report_id: str):
    """接口场景报告重命名（带路径参数）。"""
    return _ok({"id": report_id, "renamed": True})


@router.get("/api/report/case/share/{share_id}/{report_id}")
async def api_report_case_share_path(share_id: str, report_id: str):
    """接口用例报告分享详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "name": "接口用例报告"})


@router.get("/api/report/scenario/share/{share_id}/{report_id}")
async def api_report_scenario_share_path(share_id: str, report_id: str):
    """接口场景报告分享详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "name": "接口场景报告"})


@router.get("/api/report/case/share/detail/{share_id}/{report_id}/{step_id}")
async def api_report_case_share_detail_path(share_id: str, report_id: str, step_id: str):
    """接口用例报告分享步骤详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "step_id": step_id})


@router.get("/api/report/scenario/share/detail/{share_id}/{report_id}/{step_id}")
async def api_report_scenario_share_detail_path(share_id: str, report_id: str, step_id: str):
    """接口场景报告分享步骤详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "step_id": step_id})


@router.get("/api/report/case/task-report/{task_id}")
async def api_report_case_task_report_path(task_id: str):
    """接口用例任务报告（带路径参数）。"""
    return _ok({"task_id": task_id, "status": "SUCCESS"})


@router.get("/api/report/scenario/task-step/{task_id}")
async def api_report_scenario_task_step_path(task_id: str):
    """接口场景任务步骤（带路径参数）。"""
    return _ok({"task_id": task_id, "status": "SUCCESS"})


@router.get("/api/report/scenario/task-report/{task_id}/{step_id}")
async def api_report_scenario_task_report_step_path(task_id: str, step_id: str):
    """接口场景任务报告步骤（带路径参数）。"""
    return _ok({"task_id": task_id, "step_id": step_id, "status": "SUCCESS"})


# ════════════════════════════════════════════════════════════
# 任务中心模块（修复 1 参数版本 item/stop）
# ════════════════════════════════════════════════════════════


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


