# app/performance/metrics.py
"""
性能指标与 SLO（Service Level Objective）定义
=============================================
面向企业级性能测试流程：
  - 统一指标模型（响应时间 / 吞吐量 / 资源使用）
  - 可配置的 SLO 阈值校验
  - 输出结构化指标报告，供报告中心/CI 集成
"""
import time
import resource
from dataclasses import dataclass, field
from statistics import mean, median, pstdev
from typing import Any, Dict, List, Optional


@dataclass
class PerformanceMetrics:
    """一次基准测试聚合后的性能指标。"""

    name: str                          # 指标/测试名称
    total_time: float = 0.0            # 总耗时（秒）
    iterations: int = 0                # 执行次数
    min_time: float = 0.0              # 最小单次耗时
    max_time: float = 0.0              # 最大单次耗时
    avg_time: float = 0.0              # 平均单次耗时
    median_time: float = 0.0           # 中位数单次耗时
    p95_time: float = 0.0              # P95 单次耗时
    stddev: float = 0.0                # 标准差
    throughput: float = 0.0            # 吞吐量（次/秒）
    peak_memory_mb: float = 0.0        # 峰值内存（MB）
    cpu_time: float = 0.0              # CPU 时间（秒）
    extra: Dict[str, Any] = field(default_factory=dict)  # 扩展指标

    @classmethod
    def from_timings(
        cls,
        name: str,
        timings: List[float],
        peak_memory_mb: float = 0.0,
        cpu_time: float = 0.0,
        iterations: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> "PerformanceMetrics":
        """从单次耗时列表聚合出指标。"""
        if not timings:
            return cls(name=name)
        n = iterations if iterations is not None else len(timings)
        total = sum(timings)
        sorted_t = sorted(timings)
        p95_idx = max(0, int(round(0.95 * len(sorted_t))) - 1)
        return cls(
            name=name,
            total_time=total,
            iterations=n,
            min_time=min(timings),
            max_time=max(timings),
            avg_time=total / len(timings),
            median_time=median(timings),
            p95_time=sorted_t[p95_idx],
            stddev=pstdev(timings) if len(timings) > 1 else 0.0,
            throughput=(n / total) if total > 0 else 0.0,
            peak_memory_mb=peak_memory_mb,
            cpu_time=cpu_time,
            extra=extra or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "total_time": round(self.total_time, 4),
            "iterations": self.iterations,
            "min_time": round(self.min_time, 4),
            "max_time": round(self.max_time, 4),
            "avg_time": round(self.avg_time, 4),
            "median_time": round(self.median_time, 4),
            "p95_time": round(self.p95_time, 4),
            "stddev": round(self.stddev, 4),
            "throughput": round(self.throughput, 2),
            "peak_memory_mb": round(self.peak_memory_mb, 2),
            "cpu_time": round(self.cpu_time, 4),
            "extra": self.extra,
        }

    def summary_line(self) -> str:
        return (
            f"⚡ {self.name}: "
            f"avg={self.avg_time:.3f}s p95={self.p95_time:.3f}s "
            f"min={self.min_time:.3f}s max={self.max_time:.3f}s "
            f"tps={self.throughput:.2f} mem={self.peak_memory_mb:.1f}MB "
            f"iter={self.iterations}"
        )


@dataclass
class SLOThreshold:
    """单项 SLO 阈值定义。"""

    metric: str                 # 指标名：avg_time / p95_time / max_time / throughput ...
    max_value: Optional[float] = None   # 上限（对于时间类指标）
    min_value: Optional[float] = None   # 下限（对于吞吐量类指标）
    description: str = ""

    def is_satisfied(self, metrics: PerformanceMetrics) -> bool:
        """校验当前指标是否满足该 SLO。"""
        actual = getattr(metrics, self.metric, None)
        if actual is None:
            return False
        if self.max_value is not None and actual > self.max_value:
            return False
        if self.min_value is not None and actual < self.min_value:
            return False
        return True


@dataclass
class SLOValidationResult:
    """一次 SLO 校验的结果。"""

    name: str
    passed: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "checks": self.checks,
            "details": self.details,
        }

    def summary_line(self) -> str:
        status = "✅" if self.passed else "❌"
        return f"{status} SLO[{self.name}]: {self.details}"


def validate_slo(
    name: str,
    metrics: PerformanceMetrics,
    thresholds: List[SLOThreshold],
) -> SLOValidationResult:
    """针对一组 SLO 阈值校验性能指标。"""
    checks = []
    all_passed = True
    for t in thresholds:
        ok = t.is_satisfied(metrics)
        if not ok:
            all_passed = False
        actual = getattr(metrics, t.metric, None)
        bound = t.max_value if t.max_value is not None else t.min_value
        op = "≤" if t.max_value is not None else "≥"
        checks.append({
            "metric": t.metric,
            "actual": round(actual, 4) if actual is not None else None,
            "threshold": bound,
            "operator": op,
            "passed": ok,
            "description": t.description,
        })

    detail = "; ".join(
        f"{c['metric']}={c['actual']}{c['operator']}{c['threshold']}"
        if c['threshold'] is not None else c['metric']
        for c in checks
    )
    return SLOValidationResult(
        name=name,
        passed=all_passed,
        checks=checks,
        details=f"{detail} → {'通过' if all_passed else '不达标'}",
    )


def measure_memory_mb() -> float:
    """测量当前进程的峰值常驻内存（MB），跨平台兼容。"""
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # ru_maxrss 在 Linux 上单位是 KB，在 macOS 上是字节
        maxrss = usage.ru_maxrss
        if maxrss > (1 << 40):  # macOS 单位 bytes
            return maxrss / (1024 * 1024)
        return maxrss / 1024  # Linux 单位 KB
    except Exception:
        return 0.0
