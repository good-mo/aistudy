# 企业级性能测试流程

> 本文档定义 Test Generation Agent Toolkit 的企业级性能测试流程，覆盖
> **性能基准建立、SLO 校验、并发负载、资源监控、CI 集成** 等环节，
> 与 `app/performance/` 引擎和 `examples/` 示例配套使用。

---

## 一、概述

企业级性能测试确保被测代码在**真实负载**下满足既定的性能指标（SLO），
帮助团队提前发现性能退化，保障生产稳定。

### 性能测试维度

| 维度 | 指标 | 目标 |
|------|------|------|
| **响应时间** | avg / min / max / median / P95 | 单次调用耗时达标 |
| **吞吐量** | 次/秒（tps） | 单位时间处理能力 |
| **资源消耗** | 峰值内存 / CPU 时间 | 资源占用有界 |
| **并发能力** | 并发线程下稳定性 | 高并发不崩溃、无竞态 |
| **稳定性** | 长时间/大批量运行 | 不 OOM、不退化 |

---

## 二、性能测试引擎架构

性能测试引擎位于 `app/performance/`，提供可复用的企业级基准测试能力：

```
app/performance/
├── __init__.py      # 对外导出
├── metrics.py       # 指标模型 + SLO 阈值校验
├── benchmark.py     # 基准测试引擎（计时/采样/并发）
└── runner.py        # LangGraph 节点（集成进生成工作流）
```

### 2.1 metrics.py — 指标模型

- `PerformanceMetrics`：聚合后的性能指标（响应时间分位数、吞吐量、峰值内存）
- `SLOThreshold`：可配置的 SLO 阈值（`max_value` 上限 / `min_value` 下限）
- `validate_slo()`：校验指标是否满足 SLO

### 2.2 benchmark.py — 基准测试引擎

- `benchmark_function()`：对单个可调用对象计时基准
  - 支持预热（warmup）消除冷启动
  - 支持并发线程模拟真实负载
  - 自动采集 min/max/avg/median/p95/stddev/吞吐量/峰值内存
- `run_benchmark()`：批量跑多组基准并做 SLO 校验
- `summarize_benchmarks()`：生成结构化汇总报告

### 2.3 runner.py — LangGraph 节点

在企业级测试生成工作流中，测试通过、覆盖率达标后自动执行性能基准：
```
扫描 → Mock → 生成测试 → 运行 → 覆盖率 → 【性能基准 + SLO 校验】→ 报告
```

---

## 三、SLO 基线（企业级默认阈值）

| 指标 | 默认阈值 | 说明 |
|------|---------|------|
| P95 响应时间 | ≤ 1s | 单次调用 95 分位耗时 |
| 平均响应时间 | ≤ 500ms | 单次调用平均耗时 |
| 吞吐量 | ≥ 10 次/秒 | 单位时间处理能力 |
| 峰值内存 | ≤ 512MB | 单次基准峰值常驻内存 |

> 阈值可通过 `app/config.py` 的 `perf_*` 配置项覆盖。

---

## 四、企业级性能测试执行流程

### 4.1 建立性能基线（首次部署）

```python
from app.performance.benchmark import benchmark_function

# 对关键函数建立基线
metrics = benchmark_function(
    lambda: target_func(),
    iterations=100,
    warmup=10,
    name="target_func",
)
print(metrics.summary_line())
```

### 4.2 持续集成（每次提交）

在 CI 流水线中运行性能测试并对比基线：

```bash
cd examples
python -m pytest test_wechat_performance.py -v
```

### 4.3 性能门禁（SLO 校验）

性能测试结果不满足 SLO 时，视为测试失败（性能退化）。

---

## 五、运行示例

### 5.1 运行内置性能测试套件

```bash
cd examples
python -m pytest test_wechat_performance.py -v
```

### 5.2 在生成工作流中自动执行

测试通过 + 覆盖率达标后，工作流自动执行性能基准，结果写入
`performance_report`，可从 API 响应中获取：

```json
{
  "performance_report": {
    "overall_passed": true,
    "total_benchmarks": 2,
    "summary": "...",
    "benchmarks": [...]
  }
}
```

---

## 六、性能测试用例模板

参考 `docs/test-case-template.md` 的 **性能测试模板**，结合 `app/performance/`
引擎，可快速编写面向任意函数的企业级性能测试。

### 6.1 模板示例

```python
def test_function_performance():
    """基准: 目标函数性能 + SLO 校验。"""
    from app.performance.benchmark import benchmark_function
    from app.performance.metrics import SLOThreshold, validate_slo

    metrics = benchmark_function(
        lambda: target_func(),
        iterations=200,
        warmup=10,
        name="target_func()",
    )
    slo = validate_slo(
        name="target_func",
        metrics=metrics,
        thresholds=[
            SLOThreshold(metric="p95_time", max_value=0.5),
            SLOThreshold(metric="throughput", min_value=50),
        ],
    )
    assert slo.passed, slo.summary_line()
```

### 6.2 并发负载模板

```python
def test_concurrent_load():
    """100 并发调用验证稳定性。"""
    import threading, time
    errors, lock = [], threading.Lock()

    def worker():
        try:
            for _ in range(100):
                target_func()
        except Exception as e:
            with lock:
                errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(100)]
    t0 = time.time()
    [t.start() for t in threads]
    [t.join(timeout=30) for t in threads]

    assert not errors
    assert time.time() - t0 < 10
```

---

## 七、与报告中心集成

性能测试结果可直接写入报告中心，生成包含性能维度的测试报告：

```bash
python -m app.cli generate --source-file app/foo.py --report
```

---

## 八、最佳实践

1. **预热**：正式采样前先 warmup，消除 JIT/缓存冷启动影响
2. **多次采样**：至少 50 次迭代取分位数，避免单次抖动
3. **并发真实**：用线程池模拟真实用户并发，而非串行
4. **SLO 有界**：阈值要留余量（如目标 100ms 则 SLO 设 80ms）
5. **环境一致**：在固定规格的 CI runner 上运行，保证可复现
6. **基线对比**：每次发布对比历史基线，识别性能退化

---

## 九、相关文档

| 文档 | 说明 |
|------|------|
| [test-matrix.md](./test-matrix.md) | 全面测试矩阵（含性能维度） |
| [test-cases-guide.md](./test-cases-guide.md) | 详细测试用例指南（含性能） |
| [test-case-template.md](./test-case-template.md) | 行业标准测试模板 |
| [test-gap-coverage.md](./test-gap-coverage.md) | 10% 差距补齐测试（含非功能性） |
