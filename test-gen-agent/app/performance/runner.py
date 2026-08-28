# app/performance/runner.py
"""
企业级性能测试 LangGraph 节点
=============================
在测试通过、覆盖率达标后，对被测函数执行性能基准测试并校验 SLO，
产出 `performance_report` 供下游/报告中心使用。

企业级流程：
  测试通过 → 覆盖率达标 → 【性能基准】→ 性能 SLO 校验 → 输出报告
"""
import ast
import inspect
import tempfile
import subprocess
import os
import json
import shutil
from typing import Any, Dict, List

from app.config import settings
from app.logging_config import get_logger
from app.performance.benchmark import benchmark_function, summarize_benchmarks
from app.performance.metrics import SLOThreshold

logger = get_logger(__name__)


# ── 默认 SLO 阈值模板（企业级基线）────────────────────────────
def default_slo_thresholds() -> Dict[str, List[SLOThreshold]]:
    """提供面向被测函数的默认 SLO 基线（可按需覆盖）。"""
    return {
        # 单次调用响应时间 P95 ≤ 1s
        "p95_latency": [SLOThreshold(metric="p95_time", max_value=1.0, description="P95 响应时间 ≤ 1s")],
        # 平均响应时间 ≤ 500ms
        "avg_latency": [SLOThreshold(metric="avg_time", max_value=0.5, description="平均响应时间 ≤ 500ms")],
        # 吞吐量 ≥ 10 次/秒
        "throughput": [SLOThreshold(metric="throughput", min_value=10.0, description="吞吐量 ≥ 10 次/秒")],
        # 峰值内存 ≤ 512MB
        "peak_memory": [SLOThreshold(metric="peak_memory_mb", max_value=512.0, description="峰值内存 ≤ 512MB")],
    }


# ── 从被测源码提取可基准调用的函数 ─────────────────────────────
def extract_benchmark_targets(
    source_code: str,
    signatures: List[Dict[str, Any]],
    max_functions: int = 5,
) -> List[Dict[str, Any]]:
    """
    从被测源码中挑选适合基准测试的函数（有参函数使用默认参数值构造调用）。

    返回:
        [{"name": func_name, "callable": <可调用对象>, "params": {...}}]
    """
    targets = []
    # 优先选择有默认参数、非私有、非魔法方法的函数
    candidates = [
        sig for sig in (signatures or [])
        if sig.get("params") is not None
        and not sig.get("name", "").startswith("_")
    ]
    # 如果都没参数，退化为取普通函数
    if not candidates:
        candidates = [
            sig for sig in (signatures or [])
            if not sig.get("name", "").startswith("_")
        ][:max_functions]

    # 解析源码 AST 获取函数定义
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return targets

    func_defs = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    ns: Dict[str, Any] = {}
    exec(compile(source_code, "<perf>", "exec"), ns)

    for sig in candidates[:max_functions]:
        name = sig.get("name", "")
        if name not in ns or not callable(ns[name]):
            continue
        func = ns[name]
        if inspect.iscoroutinefunction(func):
            continue  # 异步函数不直接基准（需事件循环），跳过
        # 收集默认参数
        params = _collect_default_params(func_defs.get(name))
        targets.append({"name": name, "callable": func, "params": params})

    return targets


def _collect_default_params(node) -> Dict[str, Any]:
    """从函数定义 AST 提取默认参数值（用于构造无外部依赖的基准调用）。"""
    params = {}
    if node is None or not isinstance(node.args, ast.arguments):
        return params
    args = list(node.args.args)
    defaults = list(node.args.defaults)
    # defaults 从右向左对齐到 args 末尾
    offset = len(args) - len(defaults)
    for i, default in enumerate(defaults):
        arg_name = args[offset + i].arg
        try:
            value = ast.literal_eval(default)
            params[arg_name] = value
        except (ValueError, SyntaxError):
            # 无法静态求值的默认值（如函数调用/类实例），跳过该参数
            continue
    return params


def _build_target_callable(func, params: Dict[str, Any]):
    """构造可调用对象：优先无参，其次用默认参数。"""
    if not params:
        return lambda: func()
    return lambda: func(**params)


def run_performance_tests(state: dict) -> dict:
    """
    LangGraph 节点：执行企业级性能基准测试。

    输入:
        state["source_code"], state["signatures"], state["file_path"]

    输出:
        state["performance_report"] = {
            "overall_passed": bool,
            "total_benchmarks": int,
            "summary": str,
            "benchmarks": [...],
            ...
        }
    """
    source = state.get("source_code", "")
    signatures = state.get("signatures", [])
    if not source or not signatures:
        return {
            "performance_report": {
                "error": "缺少被测源码或函数签名，无法执行性能测试。",
                "overall_passed": False,
            }
        }

    logger.info("⚡ 开始企业级性能基准测试…")
    targets = extract_benchmark_targets(source, signatures)

    if not targets:
        return {
            "performance_report": {
                "error": "未提取到可基准测试的函数（需为同步函数）。",
                "overall_passed": False,
                "skipped": True,
            }
        }

    benchmarks = {}
    slo_map = {}
    for t in targets:
        name = t["name"]
        benchmarks[f"{name}()"] = _build_target_callable(t["callable"], t["params"])
        # 应用默认 SLO 阈值
        slo_map[f"{name}()"] = default_slo_thresholds()["p95_latency"]

    try:
        results = []
        for name, func in benchmarks.items():
            from app.performance.benchmark import benchmark_function, BenchmarkResult
            from app.performance.metrics import validate_slo
            metrics = benchmark_function(
                func,
                iterations=settings.perf_iterations,
                warmup=settings.perf_warmup,
                name=name,
            )
            slo = validate_slo(name=name, metrics=metrics, thresholds=slo_map[name])
            results.append(BenchmarkResult(name=name, metrics=metrics, slo=slo))

        report = summarize_benchmarks(results)
        logger.info("性能测试完成: %s", report["summary"])
        return {"performance_report": report}
    except Exception as e:
        logger.error("性能测试失败 [err=%s]", e, exc_info=True)
        return {
            "performance_report": {
                "error": f"性能测试异常: {e}",
                "overall_passed": False,
            }
        }
