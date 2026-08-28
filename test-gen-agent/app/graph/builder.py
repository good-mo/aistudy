# app/graph/builder.py
"""
LangGraph 工作流组装
====================
把测试用例 Agent 的各个节点组装成一张有状态的状态图（StateGraph）。

工作流：
    START
      → scan_code            (AST 提取函数签名)
      → generate_mocks       (规则驱动生成 Mock 配置)
      → generate_tests       (LLM 生成 pytest 测试)
      → test_runner          (子进程沙箱运行测试)
          ⇄ refinement_node  (失败时定向修复，条件重试)
      → coverage_analysis    (覆盖率差距分析)
          ⇄ refinement_node  (覆盖率不达标时可补测，可选)
      → performance_test     (企业级性能基准测试 + SLO 校验)
      → END
"""

from langgraph.graph import StateGraph, START, END
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.config import settings
from app.graph.state import AgentState
from app.graph.refinement import refine_tests, is_recoverable

from app.scanners.python_scanner import scan_python_file
from app.generators.mock_generator import generate_mocks
from app.generators.test_generator import generate_tests
from app.runners.subprocess_runner import run_tests
from app.coverage.analyzer import analyze_coverage
from app.performance.runner import run_performance_tests
from app.logging_config import get_logger

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════
# 1. 条件路由函数
# ════════════════════════════════════════════════════════════

def should_generate_script(state: AgentState) -> str:
    """
    generate_tests 之后的路由：
        - generate_script=True  → test_runner（继续运行测试）
        - generate_script=False → END（仅生成结构化用例，跳过执行）
    """
    if state.get("generate_script", True):
        return "test_runner"
    return END


def should_retry(state: AgentState) -> str:
    """
    test_runner 之后的路由：
        - 测试通过           → coverage_analysis
        - 不可恢复的致命错误 → coverage_analysis（放弃修复）
        - 超过修复重试上限   → coverage_analysis
        - 否则               → refinement_node（继续修复）
    """
    test_result = state.get("test_result", {}) or {}

    if test_result.get("passed"):
        return "coverage_analysis"

    if not is_recoverable(test_result):
        logger.info("[Router] 检测到不可恢复的致命错误，停止修复。")
        return "coverage_analysis"

    if state.get("retry_count", 0) >= settings.max_retries:
        logger.info(f"[Router] 已达修复重试上限({settings.max_retries})，进入覆盖率分析。")
        return "coverage_analysis"

    return "refinement_node"


def should_improve_coverage(state: AgentState) -> str:
    """
    coverage_analysis 之后的路由（可选的覆盖率补测循环）：
        - 覆盖率达标         → performance_test（企业级性能基准测试）
        - 报告出错           → END
        - 超过总重试上限     → END
        - 否则               → refinement_node（补测以提高覆盖率）
    """
    report = state.get("coverage_report", {}) or {}

    # 报告出错或已达标，直接结束
    if report.get("error"):
        return END
    if report.get("passed_threshold", True):
        # 性能测试默认可选，通过配置启用
        if settings.perf_enabled:
            return "performance_test"
        return END

    # 防止无限循环：受总重试上限约束
    if state.get("retry_count", 0) >= settings.max_coverage_retries:
        logger.info(f"[Router] 已达覆盖率补测总上限({settings.max_coverage_retries})，结束。")
        return END

    logger.info(
        f"[Router] 覆盖率 "
        f"{report.get('line_coverage_pct', 0)}% < "
        f"{settings.coverage_threshold}%，尝试补测。"
    )
    return "refinement_node"


# ════════════════════════════════════════════════════════════
# 2. 图组装
# ════════════════════════════════════════════════════════════

def build_graph(checkpointer=None):
    """
    构建并编译 LangGraph 状态图。

    Args:
        checkpointer: 可选的检查点存储；默认使用 SQLite。

    Returns:
        已编译的 graph（支持 invoke / astream）
    """
    builder = StateGraph(AgentState)

    # ── 注册节点 ──────────────────────────────────
    builder.add_node("scan_code", scan_python_file)
    builder.add_node("generate_mocks", generate_mocks)
    builder.add_node("generate_tests", generate_tests)
    builder.add_node("test_runner", run_tests)
    builder.add_node("refinement_node", refine_tests)
    builder.add_node("coverage_analysis", analyze_coverage)
    builder.add_node("performance_test", run_performance_tests)

    # ── 线性主流程 ────────────────────────────────
    builder.add_edge(START, "scan_code")
    builder.add_edge("scan_code", "generate_mocks")
    builder.add_edge("generate_mocks", "generate_tests")

    # generate_tests 之后条件路由：
    # - generate_script=True  → 进入 test_runner 运行测试
    # - generate_script=False → 跳过测试直接进入 coverage_analysis
    builder.add_conditional_edges(
        "generate_tests",
        should_generate_script,
        {
            "test_runner": "test_runner",
            END: END,
        },
    )

    # ── 测试失败 → 修复循环（条件边）─────────────
    builder.add_conditional_edges(
        "test_runner",
        should_retry,
        {
            "refinement_node": "refinement_node",
            "coverage_analysis": "coverage_analysis",
        },
    )
    # 修复后回到 test_runner 重新验证
    builder.add_edge("refinement_node", "test_runner")

    # ── 覆盖率不达标 → 补测循环（可选条件边）─────
    builder.add_conditional_edges(
        "coverage_analysis",
        should_improve_coverage,
        {
            "refinement_node": "refinement_node",
            "performance_test": "performance_test",
            END: END,
        },
    )
    builder.add_edge("performance_test", END)

    # ── 检查点（状态持久化，支持跨请求/故障恢复）──
    if checkpointer is None:
        conn = sqlite3.connect(settings.checkpoint_db, check_same_thread=False)
        checkpointer = SqliteSaver(conn)

    return builder.compile(checkpointer=checkpointer)


# ════════════════════════════════════════════════════════════
# 3. 模块级单例（供 main.py / cli.py 直接导入）
# ════════════════════════════════════════════════════════════

# 延迟初始化 graph，避免模块导入时就触发 LLM 初始化
_graph = None


def get_graph():
    """延迟获取全局 graph 实例。"""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# 兼容旧接口：模块级 graph 属性（延迟初始化）
def __getattr__(name):
    if name == "graph":
        return get_graph()
    raise AttributeError(f"module {__name__} has no attribute {name}")


# ════════════════════════════════════════════════════════════
# 4. 本地自测（python -m app.graph.builder）
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sample_code = (
        "def divide(a: int, b: int) -> float:\n"
        "    if b == 0:\n"
        "        raise ValueError('除数不能为 0')\n"
        "    return a / b\n"
    )

    config = {"configurable": {"thread_id": "demo_test"}}
    result = build_graph().invoke(
        {
            "source_code": sample_code,
            "file_path": "demo.py",
            "test_type": "functional",
            "retry_count": 0,
        },
        config=config,
    )

    logger.info("\n===== 生成的测试代码 =====")
    logger.info(result.get("generated_tests", "（无）"))

    logger.info("\n===== 测试运行结果 =====")
    logger.info(result.get("test_result", {}))

    logger.info("\n===== 覆盖率报告 =====")
    cov = result.get("coverage_report", {})
    logger.info(cov.get("human_summary", cov))

    logger.info(f"\n总重试次数: {result.get('retry_count', 0)}")
