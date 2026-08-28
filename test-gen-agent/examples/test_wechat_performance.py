"""
test_wechat_performance.py — 企业级性能测试套件（微信上传图片）

覆盖企业级性能测试流程的各个维度：
  - 纯函数基准（响应时间 / 吞吐量）
  - 文件 I/O 场景（MD5 计算 / 压缩）
  - 并发负载测试（模拟多用户）
  - SLO（Service Level Objective）阈值校验

运行方式:
    cd examples
    python -m pytest test_wechat_performance.py -v
"""
import os
import sys
import time
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wechat_upload import (
    validate_dimensions,
    calculate_md5,
    MAX_DIMENSION,
)

from app.performance.benchmark import benchmark_function, BenchmarkResult
from app.performance.metrics import SLOThreshold, validate_slo, PerformanceMetrics

# 将项目根目录加入 sys.path 以便导入 app 模块
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ── 测试数据辅助 ─────────────────────────────────────────────
def make_temp_image(size_kb: int = 1024) -> str:
    """生成指定大小的临时测试图片文件（返回路径）。"""
    fd, path = tempfile.mkstemp(suffix=".jpg")
    with os.fdopen(fd, "wb") as f:
        f.write(b"\xff\xd8\xff" + b"\x00" * (size_kb * 1024))
    return path


# ── 1. 纯函数基准测试（响应时间 / 吞吐量 / SLO 校验）─────────
class TestPureFunctionBenchmark:
    """纯函数性能基准：不依赖文件系统，适合 CI 稳定执行。"""

    def test_validate_dimensions_benchmark(self):
        """基准: validate_dimensions 调用性能。"""
        metrics = benchmark_function(
            lambda: validate_dimensions(100, 200),
            iterations=500,
            warmup=20,
            name="validate_dimensions()",
        )
        # 断言基本性能（宽松阈值，避免环境波动误报）
        assert metrics.avg_time < 0.05, f"avg 响应过慢: {metrics.avg_time:.4f}s"
        assert metrics.throughput > 10, f"吞吐量过低: {metrics.throughput:.2f}"

    def test_validate_dimensions_slo(self):
        """SLO 校验: 平均响应时间 ≤ 10ms, P95 ≤ 20ms。"""
        metrics = benchmark_function(
            lambda: validate_dimensions(800, 1200),
            iterations=200,
            warmup=10,
            name="validate_dimensions()",
        )
        slo = validate_slo(
            name="validate_dimensions",
            metrics=metrics,
            thresholds=[
                SLOThreshold(metric="avg_time", max_value=0.01, description="平均 ≤ 10ms"),
                SLOThreshold(metric="p95_time", max_value=0.02, description="P95 ≤ 20ms"),
            ],
        )
        assert slo.passed, slo.summary_line()

    def test_validate_dimensions_boundary_benchmark(self):
        """边界尺寸性能: 最大允许尺寸不应显著退化。"""
        metrics = benchmark_function(
            lambda: validate_dimensions(MAX_DIMENSION, MAX_DIMENSION),
            iterations=200,
            warmup=10,
            name="validate_dimensions(max)",
        )
        assert metrics.avg_time < 0.05, f"边界尺寸响应过慢: {metrics.avg_time:.4f}s"


# ── 2. 文件 I/O 基准测试（MD5 计算）─────────────────────────
class TestFileIOBenchmark:
    """文件 I/O 场景性能：模拟真实大数据量处理。"""

    def test_md5_1mb_file(self):
        """1MB 文件 MD5 计算: 应 < 1s。"""
        path = make_temp_image(size_kb=1024)
        try:
            metrics = benchmark_function(
                lambda: calculate_md5(path),
                iterations=20,
                warmup=3,
                name="md5_1mb",
            )
            assert metrics.avg_time < 1.0, f"1MB MD5 过慢: {metrics.avg_time:.3f}s"
        finally:
            os.unlink(path)

    def test_md5_10mb_file(self):
        """10MB 文件 MD5 计算: 应 < 3s。"""
        path = make_temp_image(size_kb=10 * 1024)
        try:
            metrics = benchmark_function(
                lambda: calculate_md5(path),
                iterations=10,
                warmup=2,
                name="md5_10mb",
            )
            assert metrics.avg_time < 3.0, f"10MB MD5 过慢: {metrics.avg_time:.3f}s"
        finally:
            os.unlink(path)


# ── 3. 并发负载测试（模拟多用户场景）────────────────────────
class TestConcurrencyLoad:
    """并发负载: 模拟多用户同时调用，验证系统稳定性。"""

    def test_validate_dimensions_concurrent_100(self):
        """100 并发调用 validate_dimensions，验证线程安全与稳定性。"""
        errors = []
        lock = threading.Lock()

        def worker():
            try:
                for _ in range(100):
                    validate_dimensions(100, 100)
            except Exception as e:  # pragma: no cover
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(100)]
        t0 = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        elapsed = time.time() - t0

        assert not errors, f"并发下发生异常: {errors[:3]}"
        assert elapsed < 10, f"100 并发 × 100 次耗时过长: {elapsed:.2f}s"

    def test_md5_concurrent_10_files(self):
        """10 并发分别计算不同文件 MD5，模拟批量上传性能。"""
        paths = [make_temp_image(size_kb=256) for _ in range(10)]
        try:
            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = [pool.submit(calculate_md5, p) for p in paths]
                results = [f.result(timeout=10) for f in futures]
            assert len(results) == 10
            assert all(len(r) == 32 for r in results)  # MD5 是 32 位 hex
        finally:
            for p in paths:
                os.unlink(p)


# ── 4. 吞吐量与资源消耗监控 ─────────────────────────────────
class TestThroughputAndResource:
    """吞吐量与内存资源监控。"""

    def test_throughput_validate_dimensions(self):
        """validate_dimensions 吞吐量: ≥ 1000 次/秒。"""
        metrics = benchmark_function(
            lambda: validate_dimensions(640, 480),
            iterations=1000,
            warmup=50,
            name="validate_dimensions_tps",
        )
        assert metrics.throughput > 1000, f"吞吐量过低: {metrics.throughput:.2f} 次/秒"

    def test_peak_memory_bounded(self):
        """峰值内存应保持在合理范围内（< 256MB）。"""
        metrics = benchmark_function(
            lambda: calculate_md5(make_temp_image(size_kb=512)),
            iterations=5,
            warmup=1,
            name="md5_mem",
        )
        assert metrics.peak_memory_mb < 256, f"峰值内存过高: {metrics.peak_memory_mb:.1f}MB"


# ── 5. 企业级性能报告示例 ───────────────────────────────────
class TestEnterpriseReport:
    """生成结构化性能报告（供报告中心/CI 集成）。"""

    def test_build_performance_report(self):
        """构造企业级性能报告 JSON 结构。"""
        from app.performance.benchmark import summarize_benchmarks

        results = []
        # 采集两个关键指标
        for name, fn in [
            ("validate_dimensions", lambda: validate_dimensions(640, 480)),
            ("md5_256k", lambda: calculate_md5(make_temp_image(size_kb=256))),
        ]:
            metrics = benchmark_function(fn, iterations=50, warmup=5, name=name)
            slo = validate_slo(
                name=name,
                metrics=metrics,
                thresholds=[SLOThreshold(metric="p95_time", max_value=5.0)],
            )
            results.append(BenchmarkResult(name=name, metrics=metrics, slo=slo))

        report = summarize_benchmarks(results)
        assert "overall_passed" in report
        assert "summary" in report
        assert report["total_benchmarks"] == 2
        # 报告应为 JSON 可序列化
        import json
        json.dumps(report)
