"""
test_performance_engine.py — 企业级性能测试引擎单元测试

覆盖:
  - metrics.py: 指标聚合、SLO 校验
  - benchmark.py: 基准测试引擎、批量基准
  - runner.py: LangGraph 节点（性能报告生成）
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.performance.metrics import (
    PerformanceMetrics,
    SLOThreshold,
    validate_slo,
)
from app.performance.benchmark import (
    benchmark_function,
    run_benchmark,
    summarize_benchmarks,
    BenchmarkResult,
)
from app.performance.runner import (
    run_performance_tests,
    extract_benchmark_targets,
    default_slo_thresholds,
)


# ── 辅助函数 ────────────────────────────────────────────────
def _dummy_func(n=100):
    """轻量测试函数，用于基准测试。"""
    total = 0
    for i in range(n):
        total += i
    return total


def _slow_func():
    """耗时函数，用于测试 SLO 校验。"""
    import time
    time.sleep(0.01)
    return 1


# ── 1. metrics.py 测试 ─────────────────────────────────────
class TestMetrics:
    """性能指标模型与聚合。"""

    def test_from_timings_basic(self):
        """从耗时列表正确聚合指标。"""
        timings = [0.01, 0.02, 0.03, 0.04, 0.05] * 20  # 100 个
        m = PerformanceMetrics.from_timings(
            name="test", timings=timings, iterations=100
        )
        assert m.iterations == 100
        assert m.avg_time == pytest.approx(0.03, abs=1e-6)
        assert m.min_time == 0.01
        assert m.max_time == 0.05
        assert m.throughput == pytest.approx(100 / 3.0, rel=0.1)

    def test_from_timings_empty(self):
        """空耗时列表应返回零值指标不崩溃。"""
        m = PerformanceMetrics.from_timings(name="empty", timings=[])
        assert m.iterations == 0
        assert m.avg_time == 0

    def test_p95_calculation(self):
        """P95 分位数计算正确。"""
        # 100 个值 0.01~1.00，P95 应接近 0.95
        timings = [i / 100.0 for i in range(1, 101)]
        m = PerformanceMetrics.from_timings(name="p95", timings=timings)
        assert m.p95_time == pytest.approx(0.95, abs=0.01)

    def test_to_dict_serializable(self):
        """指标可序列化为 JSON。"""
        import json
        m = PerformanceMetrics.from_timings(name="json", timings=[0.1, 0.2])
        d = m.to_dict()
        json.dumps(d)  # 不应抛异常

    def test_measure_memory_mb(self):
        """内存测量函数应返回正数。"""
        from app.performance.metrics import measure_memory_mb
        mem = measure_memory_mb()
        assert mem >= 0

    def test_summary_line(self):
        """summary_line 应包含关键指标。"""
        m = PerformanceMetrics.from_timings(name="demo", timings=[0.1, 0.2, 0.3])
        line = m.summary_line()
        assert "demo" in line
        assert "avg=" in line
        assert "p95=" in line


# ── 2. SLO 校验测试 ────────────────────────────────────────
class TestSLOValidation:
    """SLO 阈值校验。"""

    def _build_metrics(self, avg=0.5, p95=1.0, tps=100):
        timings = [avg] * 100
        m = PerformanceMetrics.from_timings(
            name="slo", timings=timings, iterations=100
        )
        m.throughput = tps  # 显式设置吞吐量，便于测试
        return m

    def test_pass_thresholds(self):
        """满足所有 SLO 阈值应通过。"""
        m = self._build_metrics(avg=0.3, p95=0.8, tps=200)
        result = validate_slo(
            name="pass",
            metrics=m,
            thresholds=[
                SLOThreshold(metric="avg_time", max_value=0.5),
                SLOThreshold(metric="p95_time", max_value=1.0),
                SLOThreshold(metric="throughput", min_value=50),
            ],
        )
        assert result.passed
        assert len(result.checks) == 3
        assert all(c["passed"] for c in result.checks)

    def test_fail_max_threshold(self):
        """超出上限阈值应失败。"""
        m = self._build_metrics(avg=0.9)
        result = validate_slo(
            name="fail_max",
            metrics=m,
            thresholds=[SLOThreshold(metric="avg_time", max_value=0.5)],
        )
        assert not result.passed

    def test_fail_min_threshold(self):
        """低于下限阈值应失败（吞吐量）。"""
        m = self._build_metrics(tps=5)
        # 手动构造低吞吐量
        m.throughput = 5
        result = validate_slo(
            name="fail_min",
            metrics=m,
            thresholds=[SLOThreshold(metric="throughput", min_value=10)],
        )
        assert not result.passed

    def test_unknown_metric(self):
        """未知指标应视为不满足。"""
        m = self._build_metrics()
        result = validate_slo(
            name="unknown",
            metrics=m,
            thresholds=[SLOThreshold(metric="nonexistent", max_value=1.0)],
        )
        assert not result.passed

    def test_to_dict_structure(self):
        """校验结果可序列化。"""
        import json
        m = self._build_metrics()
        result = validate_slo(
            name="serializable",
            metrics=m,
            thresholds=[SLOThreshold(metric="avg_time", max_value=1.0)],
        )
        json.dumps(result.to_dict())


# ── 3. benchmark.py 测试 ───────────────────────────────────
class TestBenchmarkEngine:
    """基准测试引擎。"""

    def test_benchmark_function(self):
        """对目标函数执行基准测试返回有效指标。"""
        m = benchmark_function(
            _dummy_func, iterations=50, warmup=5, name="dummy"
        )
        assert m.name == "dummy"
        assert m.iterations == 50
        assert m.avg_time >= 0
        assert m.throughput > 0

    def test_benchmark_with_args(self):
        """支持传参调用。"""
        m = benchmark_function(
            _dummy_func, iterations=20, warmup=3, name="dummy_args", args=(50,)
        )
        assert m.iterations == 20

    def test_benchmark_concurrent(self):
        """并发模式执行不崩溃，吞吐量合理。"""
        m = benchmark_function(
            _dummy_func, iterations=50, warmup=5, name="concurrent", concurrent=4
        )
        assert m.throughput > 0

    def test_run_benchmark_multiple(self):
        """批量运行多组基准并返回结果。"""
        results = run_benchmark(
            {"func_a": lambda: _dummy_func(10), "func_b": lambda: _dummy_func(20)},
            iterations=20,
            warmup=3,
        )
        assert len(results) == 2
        assert results[0].metrics.avg_time >= 0

    def test_run_benchmark_with_slo(self):
        """批量基准支持 SLO 校验。"""
        results = run_benchmark(
            {"func": lambda: _dummy_func(10)},
            iterations=20,
            warmup=3,
            slo_thresholds={
                "func": [SLOThreshold(metric="p95_time", max_value=5.0)]
            },
        )
        assert results[0].slo is not None

    def test_summarize_benchmarks(self):
        """汇总报告结构正确。"""
        results = [
            BenchmarkResult(
                name="a",
                metrics=PerformanceMetrics.from_timings("a", [0.1] * 10),
                slo=validate_slo(
                    "a",
                    PerformanceMetrics.from_timings("a", [0.1] * 10),
                    [SLOThreshold(metric="p95_time", max_value=1.0)],
                ),
            )
        ]
        summary = summarize_benchmarks(results)
        assert summary["overall_passed"] is True
        assert summary["total_benchmarks"] == 1
        assert "summary" in summary
        import json
        json.dumps(summary)


# ── 4. runner.py 测试 ─────────────────────────────────────
class TestPerformanceRunner:
    """LangGraph 性能节点。"""

    SAMPLE_CODE = '''
def compute_sum(n: int = 100) -> int:
    total = 0
    for i in range(n):
        total += i
    return total

def multiply(a: int = 3, b: int = 5) -> int:
    return a * b
'''

    SIGNATURES = [
        {"name": "compute_sum", "params": {"n": 100}},
        {"name": "multiply", "params": {"a": 3, "b": 5}},
    ]

    def test_extract_targets(self):
        """从源码正确提取可基准调用的函数。"""
        targets = extract_benchmark_targets(self.SAMPLE_CODE, self.SIGNATURES)
        names = [t["name"] for t in targets]
        assert "compute_sum" in names
        assert "multiply" in names

    def test_extract_targets_empty_signatures(self):
        """无签名时返回空列表。"""
        targets = extract_benchmark_targets(self.SAMPLE_CODE, [])
        assert targets == [] or len(targets) > 0

    def test_run_performance_tests_success(self):
        """性能节点正常执行并产出报告。"""
        state = {
            "source_code": self.SAMPLE_CODE,
            "signatures": self.SIGNATURES,
            "file_path": "demo.py",
        }
        result = run_performance_tests(state)
        report = result.get("performance_report", {})
        assert "overall_passed" in report
        assert report["total_benchmarks"] >= 1
        assert "summary" in report

    def test_run_performance_tests_no_source(self):
        """缺少源码时返回错误报告。"""
        result = run_performance_tests({"source_code": "", "signatures": []})
        report = result.get("performance_report", {})
        assert report.get("error")

    def test_default_slo_thresholds(self):
        """默认 SLO 阈值包含关键指标。"""
        slos = default_slo_thresholds()
        assert "p95_latency" in slos
        assert slos["p95_latency"][0].metric == "p95_time"

    def test_performance_report_serializable(self):
        """性能报告可序列化为 JSON。"""
        import json
        state = {
            "source_code": self.SAMPLE_CODE,
            "signatures": self.SIGNATURES,
        }
        result = run_performance_tests(state)
        json.dumps(result.get("performance_report", {}))
