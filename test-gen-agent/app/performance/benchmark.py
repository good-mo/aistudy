# app/performance/benchmark.py
"""
企业级基准测试引擎
==================
提供：
  - `benchmark_function`: 对单个可调用对象进行计时基准测试
  - `run_benchmark`:     对一组（函数名 → 可调用对象）批量跑基准，并做 SLO 校验
  - 自动采集响应时间分位数 / 吞吐量 / 峰值内存
企业级特性：
  - 预热（warmup）消除 JIT/缓存冷启动影响
  - 多轮采样并聚合分位数（min/max/avg/median/p95/stddev）
  - 可并发执行（可选 ThreadPoolExecutor）模拟真实负载
"""
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.performance.metrics import (
    PerformanceMetrics,
    SLOThreshold,
    SLOValidationResult,
    validate_slo,
    measure_memory_mb,
)


@dataclass
class BenchmarkResult:
    """一次基准测试的完整结果。"""

    name: str
    metrics: PerformanceMetrics
    slo: Optional[SLOValidationResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "metrics": self.metrics.to_dict(),
            "slo": self.slo.to_dict() if self.slo else None,
        }

    def summary_line(self) -> str:
        line = self.metrics.summary_line()
        if self.slo:
            line += " | " + self.slo.summary_line()
        return line


def benchmark_function(
    func: Callable[[], Any],
    *,
    iterations: int = 100,
    warmup: int = 5,
    name: str = "benchmark",
    concurrent: int = 1,
    args: Optional[tuple] = None,
    kwargs: Optional[dict] = None,
) -> PerformanceMetrics:
    """
    对目标函数执行基准测试。

    Args:
        func: 待测的可调用对象（无参或有 args/kwargs）
        iterations: 采样次数
        warmup: 预热次数
        name: 指标名称
        concurrent: 并发线程数（>1 时用线程池模拟并发负载）
        args / kwargs: 传给 func 的参数

    Returns:
        PerformanceMetrics 聚合指标
    """
    args = args or ()
    kwargs = kwargs or {}

    # 预热（消除冷启动/缓存抖动）
    for _ in range(warmup):
        func(*args, **kwargs)

    mem_before = measure_memory_mb()

    if concurrent <= 1:
        timings = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            func(*args, **kwargs)
            timings.append(time.perf_counter() - t0)
        cpu_time = time.process_time()
    else:
        # 并发执行：将 iterations 拆成 concurrent 个线程各自执行
        per_thread = max(1, iterations // concurrent)
        timings: List[float] = []
        lock = threading.Lock()

        def worker():
            local_timings = []
            for _ in range(per_thread):
                t0 = time.perf_counter()
                func(*args, **kwargs)
                local_timings.append(time.perf_counter() - t0)
            with lock:
                timings.extend(local_timings)

        threads = [threading.Thread(target=worker) for _ in range(concurrent)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=max(60, iterations * 2))
        cpu_time = time.process_time()

    mem_after = measure_memory_mb()
    peak_mem = max(mem_before, mem_after)

    return PerformanceMetrics.from_timings(
        name=name,
        timings=timings,
        peak_memory_mb=peak_mem,
        cpu_time=cpu_time,
        iterations=iterations,
    )


def run_benchmark(
    benchmarks: Dict[str, Callable[[], Any]],
    *,
    iterations: int = 100,
    warmup: int = 5,
    concurrent: int = 1,
    slo_thresholds: Optional[Dict[str, List[SLOThreshold]]] = None,
) -> List[BenchmarkResult]:
    """
    批量运行一组基准测试并做 SLO 校验。

    Args:
        benchmarks: {基准名称: 可调用对象}
        slo_thresholds: {基准名称: [SLOThreshold, ...]}

    Returns:
        按输入顺序排列的 BenchmarkResult 列表
    """
    results: List[BenchmarkResult] = []
    slo_thresholds = slo_thresholds or {}

    for name, func in benchmarks.items():
        metrics = benchmark_function(
            func,
            iterations=iterations,
            warmup=warmup,
            name=name,
            concurrent=concurrent,
        )
        slo = None
        thresholds = slo_thresholds.get(name)
        if thresholds:
            slo = validate_slo(name=name, metrics=metrics, thresholds=thresholds)
        results.append(BenchmarkResult(name=name, metrics=metrics, slo=slo))

    return results


def summarize_benchmarks(results: List[BenchmarkResult]) -> Dict[str, Any]:
    """汇总基准测试结果为结构化报告。"""
    all_passed = all(r.slo is None or r.slo.passed for r in results)
    return {
        "overall_passed": all_passed,
        "total_benchmarks": len(results),
        "passed": sum(1 for r in results if r.slo is None or r.slo.passed),
        "failed": sum(1 for r in results if r.slo and not r.slo.passed),
        "benchmarks": [r.to_dict() for r in results],
        "summary": "\n".join(r.summary_line() for r in results),
    }
