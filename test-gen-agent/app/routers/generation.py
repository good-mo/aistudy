# app/routers/generation.py
"""测试生成与任务管理路由（Phase 3 重构：从 main.py 拆分）。"""
import os
from typing import Optional

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

from app.logging_config import get_logger
from app.models.schemas import ChatRequest

logger = get_logger(__name__)
router = APIRouter(tags=["generation"])


async def run_generation(graph, req: ChatRequest) -> dict:
    """执行完整的测试生成工作流并落盘产物。"""
    config = {"configurable": {"thread_id": req.file_path}}
    result = await graph.ainvoke(
        {
            "source_code": req.source_code,
            "file_path": req.file_path,
            "test_type": req.test_type,
            "generate_script": req.generate_script,
            "retry_count": 0,
        },
        config=config,
    )

    generated_tests = result.get("generated_tests", "")
    out_path = None
    if generated_tests:
        os.makedirs("output", exist_ok=True)
        out_path = os.path.join("output", f"test_{os.path.basename(req.file_path)}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(generated_tests)

    # 保存到用例库
    try:
        from app.cases.repository import create_case, update_case_result
        test_result = result.get("test_result", {})
        case = create_case(
            title=f"测试: {req.file_path}",
            source_code=req.source_code,
            test_code=generated_tests,
            file_path=req.file_path,
            status="review" if test_result.get("passed") else "draft",
            test_type=req.test_type,
            structured_cases=result.get("structured_cases", []),
        )
        if case:
            update_case_result(case.get("id", ""), test_result)
    except Exception as e:
        logger.warning("用例入库失败 [err=%s]", e)

    # 自动创建缺陷
    try:
        test_result = result.get("test_result", {})
        if test_result and not test_result.get("passed", True):
            from app.defects.tracker import auto_create_defect_from_result
            auto_create_defect_from_result(
                file_path=req.file_path,
                test_result=test_result,
            )
    except Exception as e:
        logger.warning("缺陷自动创建失败 [err=%s]", e)

    # 保存运行记录
    try:
        from app.runs.repository import save_run_record
        save_run_record(
            file_path=req.file_path,
            source_code=req.source_code,
            generated_tests=generated_tests,
            test_result=result.get("test_result", {}),
            coverage_report=result.get("coverage_report", {}),
            performance_report=result.get("performance_report", {}),
            retry_count=result.get("retry_count", 0),
            saved_to=out_path,
            error="",
            source="single",
            metadata={"via": "run_generation", "request": req.model_dump()},
        )
    except Exception as e:
        logger.warning("运行记录保存失败 [err=%s]", e)

    # 记录测试执行追溯
    try:
        test_result = result.get("test_result", {})
        if test_result:
            passed = bool(test_result.get("passed", True))
            from app.insights.trace import record_run
            record_run(
                file_path=req.file_path,
                result="passed" if passed else "failed",
                passed_count=int(test_result.get("passed_count", 0)),
                failed_count=int(test_result.get("failed_count", 0)),
                error_count=int(test_result.get("error_count", 0)),
                coverage=float((result.get("coverage_report", {}) or {}).get("coverage_pct", 0) or 0),
                created_by="test-agent",
            )
    except Exception as e:
        logger.warning("执行追溯记录失败 [err=%s]", e)

    return {
        "file_path": req.file_path,
        "test_type": req.test_type,
        "generated_tests": generated_tests,
        "structured_cases": result.get("structured_cases", []),
        "test_result": result.get("test_result", {}),
        "coverage_report": result.get("coverage_report", {}),
        "performance_report": result.get("performance_report", {}),
        "retry_count": result.get("retry_count", 0),
        "saved_to": out_path,
    }


@router.post("/api/generate")
async def generate_tests_api(request: Request, async_mode: bool = False):
    """一次性生成测试用例并返回完整结果。"""
    body = await request.json()
    req = ChatRequest(**body)
    graph = request.app.state.graph

    if async_mode:
        tm = request.app.state.task_manager
        task = await tm.submit(run_generation, graph, req)
        return ok({"task_id": task.task_id, "status": task.status})

    result = await run_generation(graph, req)
    return JSONResponse(result)


@router.post("/api/generate/structured")
async def generate_structured_api(request: Request):
    """仅生成结构化测试用例。"""
    body = await request.json()
    req = ChatRequest(**body)

    from app.generators.test_generator import generate_structured_cases
    from app.scanners.python_scanner import scan_python_code
    from app.generators.mock_generator import generate_mocks

    try:
        scan_result = scan_python_code(req.source_code)
        signatures = scan_result.get("functions", [])
    except Exception:
        signatures = []

    mock_state = {"source_code": req.source_code}
    mocks_result = generate_mocks(mock_state)
    mocks = mocks_result.get("mocks", {})

    result = generate_structured_cases({
        "source_code": req.source_code,
        "file_path": req.file_path,
        "test_type": req.test_type,
        "signatures": signatures,
        "mocks": mocks,
    })

    return ok({
        "file_path": req.file_path,
        "test_type": result.get("test_type", req.test_type),
        "structured_cases": result.get("structured_cases", []),
    })


@router.post("/api/tasks")
async def submit_task(request: Request):
    """提交生成任务到后台队列。"""
    body = await request.json()
    req = ChatRequest(**body)
    graph = request.app.state.graph
    tm = request.app.state.task_manager
    task = await tm.submit(run_generation, graph, req)
    return ok({"task_id": task.task_id, "status": task.status})


@router.get("/api/tasks/{task_id}")
async def get_task(request: Request, task_id: str):
    """查询任务状态与结果。"""
    tm = request.app.state.task_manager
    task = tm.get_task_dict(task_id)
    if not task:
        return JSONResponse({"error": f"task {task_id} 不存在"}, status_code=404)
    return JSONResponse(task)


@router.get("/api/tasks")
async def list_tasks(request: Request, limit: int = 20):
    """列出最近的任务。"""
    tm = request.app.state.task_manager
    tasks = tm.list_tasks(limit=limit)
    return ok({"tasks": tasks, "total": len(tasks)})


@router.websocket("/ws/generate")
async def generate_ws(ws: WebSocket):
    """流式输出 LangGraph 每个节点的执行进度。"""
    await ws.accept()
    client = ws.client.host if ws.client else "unknown"
    logger.info("WebSocket 连接建立 [client=%s]", client)
    try:
        data = await ws.receive_json()
        source = data.get("source_code", "").strip()
        file_path = data.get("file_path", "demo.py")
        test_type = data.get("test_type", "functional")
        generate_script = data.get("generate_script", True)

        if not source:
            await ws.send_json({"error": "源代码不能为空"})
            await ws.close()
            return

        graph = ws.app.state.graph
        config = {"configurable": {"thread_id": file_path}}

        async for event in graph.astream(
            {"source_code": source, "file_path": file_path, "test_type": test_type,
             "generate_script": generate_script, "retry_count": 0},
            config=config,
            stream_mode="updates",
        ):
            for node_name, node_output in event.items():
                await ws.send_json({"step": {"__node": node_name, **(node_output or {})}})

        await ws.send_json({"done": True})

        try:
            final = await graph.aget_state(config)
            values = (final.values if final else {}) or {}
            from app.runs.repository import save_run_record
            save_run_record(
                file_path=file_path,
                source_code=source,
                generated_tests=values.get("generated_tests", ""),
                test_result=values.get("test_result", {}),
                coverage_report=values.get("coverage_report", {}),
                performance_report=values.get("performance_report", {}),
                retry_count=values.get("retry_count", 0),
                saved_to="",
                error="",
                source="websocket",
                metadata={"via": "ws_generate", "client": client},
            )
        except Exception as e:
            logger.warning("WS 运行记录保存失败 [err=%s]", e)

    except WebSocketDisconnect:
        logger.warning("客户端断开连接 [client=%s]", client)
    except Exception as e:
        logger.error("测试生成失败 [client=%s, err=%s]", client, e, exc_info=True)
        try:
            await ws.send_json({"error": f"生成失败: {str(e)}"})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
