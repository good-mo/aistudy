# app/routers/reports.py
"""报告中心路由（Phase 3 重构：从 main.py 拆分）。"""
import json
import os
from typing import Optional

from fastapi import APIRouter
from app.core.response import ok, fail
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(tags=["reports"])


@router.post("/api/reports/generate")
async def api_generate_report(req: Optional[dict] = None):
    """生成测试报告。"""
    from app.reports.generator import (
        generate_html_report,
        generate_junit_report,
        generate_markdown_report,
    )
    from app.cases.repository import list_cases

    format_type = "html"
    if req and isinstance(req, dict):
        format_type = req.get("format", "html")
    elif hasattr(req, 'format'):
        format_type = req.format

    cases = list_cases(limit=50)
    results = []
    for c in cases:
        last_result = c.get("last_result", "")
        try:
            last_result_data = json.loads(last_result) if last_result else {}
        except:
            last_result_data = {}
        results.append({
            "file_path": c.get("file_path", "unknown"),
            "generated_tests": c.get("test_code", ""),
            "test_result": last_result_data,
            "coverage_report": {},
            "retry_count": 0,
        })

    if not results:
        return JSONResponse({"error": "无用例数据，无法生成报告"}, status_code=404)

    if format_type == "html":
        path = generate_html_report(results)
    elif format_type == "junit":
        path = generate_junit_report(results)
    elif format_type == "markdown":
        path = generate_markdown_report(results)
    else:
        return JSONResponse({"error": f"不支持的格式: {format_type}"}, status_code=400)

    return ok({"report_path": path})


@router.get("/api/reports/list")
async def api_list_reports():
    """列出已生成的报告。"""
    report_dir = "reports"
    if not os.path.isdir(report_dir):
        return ok({"reports": []})
    files = sorted(os.listdir(report_dir), reverse=True)
    reports = [{"name": f, "path": f"/api/reports/download/{f}"} for f in files]
    return ok({"reports": reports})


@router.get("/api/reports/download/{filename}")
async def api_download_report(filename: str):
    """下载报告文件。"""
    report_path = os.path.join("reports", filename)
    if not os.path.isfile(report_path):
        return JSONResponse({"error": f"报告 {filename} 不存在"}, status_code=404)
    return FileResponse(report_path, filename=filename)


@router.post("/api/reports/{filename}/trash")
async def api_trash_report(filename: str):
    """将报告移入回收站。"""
    report_path = os.path.join("reports", filename)
    if not os.path.isfile(report_path):
        return JSONResponse({"error": f"报告 {filename} 不存在"}, status_code=404)
    trash_dir = os.path.join("reports", ".trash")
    os.makedirs(trash_dir, exist_ok=True)
    os.rename(report_path, os.path.join(trash_dir, filename))
    return ok({"trashed": True, "filename": filename})


@router.get("/api/reports/trash/list")
async def api_list_trash_reports():
    """列出回收站中的报告。"""
    trash_dir = os.path.join("reports", ".trash")
    if not os.path.isdir(trash_dir):
        return ok({"reports": []})
    files = sorted(os.listdir(trash_dir), reverse=True)
    return ok({"reports": files, "total": len(files)})


@router.post("/api/reports/trash/{filename}/restore")
async def api_restore_report(filename: str):
    """从回收站恢复报告。"""
    trash_dir = os.path.join("reports", ".trash")
    if not os.path.isfile(os.path.join(trash_dir, filename)):
        return JSONResponse({"error": f"报告 {filename} 不在回收站"}, status_code=404)
    os.rename(os.path.join(trash_dir, filename), os.path.join("reports", filename))
    return ok({"restored": True, "filename": filename})


@router.delete("/api/reports/trash/{filename}")
async def api_purge_report(filename: str):
    """从回收站彻底删除报告。"""
    trash_dir = os.path.join("reports", ".trash")
    path = os.path.join(trash_dir, filename)
    if not os.path.isfile(path):
        return JSONResponse({"error": f"报告 {filename} 不存在"}, status_code=404)
    os.remove(path)
    return ok({"purged": True, "filename": filename})
