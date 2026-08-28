# app/routers/projects_scan.py
"""项目扫描与批量生成路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["projects-scan"])


@router.post("/api/projects/scan")
async def api_scan_project(req: Request):
    """递归扫描项目目录，返回所有源文件与函数签名。"""
    from app.projects.manager import scan_project
    body = await req.json()
    project_path = body.get("project_path", "")
    try:
        result = await asyncio.to_thread(scan_project, project_path)
        return JSONResponse(result)
    except FileNotFoundError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": f"扫描失败: {e}"}, status_code=500)


@router.post("/api/projects/generate")
async def api_generate_project(request: Request, async_mode: bool = False):
    """项目级批量生成测试用例。"""
    from app.projects.manager import scan_project, collect_sources_from_paths
    from app.config import settings
    body = await request.json()
    project_path = body.get("project_path", "")

    try:
        scan_result = await asyncio.to_thread(scan_project, project_path)
        paths = [f["path"] for f in scan_result["files"]]
        sources = await asyncio.to_thread(collect_sources_from_paths, paths)
    except Exception as e:
        return JSONResponse({"error": f"扫描失败: {e}"}, status_code=500)

    graph = request.app.state.graph

    async def _process_one(src):
        config = {"configurable": {"thread_id": src["file_path"]}}
        result = await graph.ainvoke(
            {
                "source_code": src["source_code"],
                "file_path": src["file_path"],
                "test_type": "functional",
                "retry_count": 0,
            },
            config=config,
        )
        generated_tests = result.get("generated_tests", "")
        test_result = result.get("test_result", {})
        try:
            from app.runs.repository import save_run_record
            await asyncio.to_thread(
                save_run_record,
                file_path=src["file_path"],
                source_code=src["source_code"],
                generated_tests=generated_tests,
                test_result=test_result,
                coverage_report=result.get("coverage_report", {}),
                performance_report=result.get("performance_report", {}),
                retry_count=result.get("retry_count", 0),
                saved_to="",
                error="",
                source="project",
                metadata={"via": "project_batch"},
            )
        except Exception as e:
            logger.warning("项目运行记录保存失败 [err=%s]", e)
        return {
            "file_path": src["file_path"],
            "generated_tests": generated_tests,
            "test_result": test_result,
            "coverage_report": result.get("coverage_report", {}),
            "retry_count": result.get("retry_count", 0),
        }

    async def run_batch():
        sem = asyncio.Semaphore(settings.task_workers)

        async def _with_sem(src):
            async with sem:
                return await _process_one(src)

        results = await asyncio.gather(*(_with_sem(src) for src in sources))
        return list(results)

    if async_mode:
        tm = request.app.state.task_manager
        task = await tm.submit(run_batch)
        return ok({"task_id": task.task_id, "status": task.status})

    results = await run_batch()
    return ok({"results": results, "total": len(results)})
