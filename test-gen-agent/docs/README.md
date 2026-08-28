# 测试文档中心

本目录包含 Test Generation Agent Toolkit 的完整测试文档体系。

## 📚 文档导航

| 文档 | 说明 |
|------|------|
| [test-cases-guide.md](./test-cases-guide.md) | **详细测试用例指南** — 手工/自动化/性能/UI 具体用例 |
| [test-matrix.md](./test-matrix.md) | **全面测试矩阵** — 多维度覆盖矩阵（功能/边界/异常/安全/兼容/回归） |
| [test-case-template.md](./test-case-template.md) | **行业标准测试模板** — IEEE 829 标准用例模板（手工/自动化/性能/UI/安全/API/冒烟） |
| [test-gap-coverage.md](./test-gap-coverage.md) | **10% 差距补齐测试** — 并发/系统集成/非功能性测试方案 |
| [api-testing-guide.md](./api-testing-guide.md) | **企业级接口测试指南** — 八大层次 API 测试方法论 + 全量端点覆盖 |
| [performance-testing-guide.md](./performance-testing-guide.md) | **企业级性能测试指南** — 基准/负载/压力/容量/稳定性/峰值六维度 |
| [enterprise-performance-testing.md](./enterprise-performance-testing.md) | **企业级性能测试流程** — 性能基准/SLO/并发负载/资源监控 |

## 🔗 使用指引

1. **查找具体测试用例** → 查看 `test-cases-guide.md`
2. **了解整体测试覆盖** → 查看 `test-matrix.md`
3. **创建新的测试用例** → 参考 `test-case-template.md` 的模板
4. **补齐真实环境测试** → 参考 `test-gap-coverage.md` 的并发/集成/非功能性方案
5. **接口测试（企业级）** → 参考 `api-testing-guide.md`，执行 `tests/test_api_enterprise.py`
6. **性能测试（企业级）** → 参考 `performance-testing-guide.md`，执行 `tests/performance/`

## 📁 自动化测试代码

自动化测试代码位于项目根目录的 `tests/` 目录：

```
tests/
├── test_config.py                  # 配置模块测试
├── test_mock_generator.py          # Mock 生成基础测试
├── test_mock_generator_extended.py # Mock 生成扩展测试
├── test_python_scanner.py          # Python 扫描器测试
├── test_cases_repository.py        # 用例库测试
├── test_defects_tracker.py         # 缺陷跟踪测试
├── test_projects_manager.py        # 项目扫描测试
├── test_reports_generator.py       # 报告生成基础测试
├── test_reports_generator_extended.py # 报告生成扩展测试
├── test_tasks_manager.py           # 任务队列测试
├── test_docker_runner.py           # Docker 沙箱测试
├── test_graph_builder.py           # LangGraph 路由测试
├── test_graph_refinement.py        # 测试修复模块测试
├── test_coverage_analyzer.py       # 覆盖率分析测试
├── test_cli.py                     # CLI 命令测试
├── test_api_integration.py         # API 集成测试
└── test_api_enterprise.py          # 企业级接口测试（契约/功能/边界/异常/安全/幂等/并发/兼容）

# 性能测试
tests/performance/
├── test_api_benchmark.py           # 接口性能基准测试
└── test_api_concurrency.py         # 并发/负载/压力/峰值测试
```

运行全部自动化测试：

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

运行特定模块测试：

```bash
pytest tests/test_config.py -v
pytest tests/test_mock_generator_extended.py -v
pytest tests/test_api_integration.py -v
```

## 🧩 真实环境补齐测试（10% 差距）

针对 AI 生成测试在**并发、系统集成、非功能性**场景的差距，
`examples/` 目录提供基于微信上传图片功能的补齐测试：

```
examples/
├── wechat_upload.py                  # 示例被测模块（微信上传图片）
├── test_wechat_concurrency.py        # 并发测试（9 个场景）
├── test_wechat_integration.py        # 系统集成测试（16 个场景）
└── test_wechat_nonfunctional.py      # 非功能性测试（18 个场景）
```

运行补齐测试：

```bash
cd examples
python -m pytest test_wechat_concurrency.py test_wechat_integration.py test_wechat_nonfunctional.py -v
```

> 详细方案见 [test-gap-coverage.md](./test-gap-coverage.md)
