# app/runners/subprocess_runner.py
"""
测试运行器（Docker 沙箱优先）
==============================
使用 Docker 容器隔离运行 pytest，避免被测/测试代码在宿主机上执行，
提升安全性（P0）。Docker 不可用时自动降级为宿主机子进程。
"""
from app.config import settings
from app.logging_config import get_logger
from app.sandbox.docker_runner import run_in_sandbox
from app.graph.state import AgentState

logger = get_logger(__name__)


def run_tests(state: AgentState) -> dict:
    """LangGraph 节点：运行生成/修复后的测试代码（沙箱隔离）。"""
    logger.debug("开始运行 pytest（沙箱）")
    module_name = state.get("file_path", "demo").replace(".py", "").replace("/", "_")
    try:
        timeout = settings.test_timeout
        result = run_in_sandbox(
            source_code=state["source_code"],
            test_code=state["generated_tests"],
            module_name=module_name,
            timeout=timeout,
        )
        passed = result.returncode == 0
        if passed:
            logger.info("测试运行通过 ✅")
        else:
            # 失败用 WARNING（可恢复，会进入修复循环）
            logger.warning("测试运行失败 [returncode=%d]", result.returncode)
        return {
            "test_result": {
                "passed": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        }
    except Exception as e:
        logger.error("测试运行异常 [err=%s]", e, exc_info=True)
        return {"test_result": {"passed": False, "stderr": f"Runner error: {e}"}}
