# 行业标准测试用例模板

> 本文档提供覆盖各测试级别的行业标准测试用例模板，包括通用手工用例模板、自动化用例模板、
> 性能用例模板、UI 用例模板、安全用例模板，以及完整参考示例。
> 遵循 IEEE 829、ISO/IEC/IEEE 29119 等国际测试标准的最佳实践。

---

## 一、通用手工测试用例模板（功能/回归）

### 模板结构

```markdown
### 用例基本信息

| 字段 | 内容 |
|------|------|
| 用例编号 | TC-{模块}-{序号} |
| 用例名称 | {简短描述测试目标} |
| 需求编号 | REQ-{编号}（可选） |
| 测试级别 | 功能/回归/冒烟 |
| 测试类型 | 正向/负向/边界/异常 |
| 优先级 | P0/P1/P2/P3 |
| 用例作者 | {姓名} |
| 创建日期 | {YYYY-MM-DD} |
| 最后更新 | {YYYY-MM-DD} |

### 前置条件

- {条件 1：系统状态/环境要求}
- {条件 2：数据准备}
- {条件 3：权限要求}

### 测试步骤

| 步骤 | 操作描述 | 测试数据 | 预期结果 |
|------|---------|---------|---------|
| 1 | {执行操作} | {输入数据} | {预期结果} |
| 2 | {执行操作} | {输入数据} | {预期结果} |
| 3 | {执行操作} | {输入数据} | {预期结果} |

### 实际结果

- 实际结果: {测试后的实际表现}
- 是否通过: ✅ 通过 / ❌ 失败

### 附件与备注

- {截图/日志/录像等}
- {备注信息}
```

### 完整示例

```markdown
### 用例基本信息

| 字段 | 内容 |
|------|------|
| 用例编号 | TC-GEN-001 |
| 用例名称 | 单文件测试生成-正常流程 |
| 测试级别 | 功能测试 |
| 测试类型 | 正向 |
| 优先级 | P0 |
| 创建日期 | 2025-01-15 |

### 前置条件

- 服务已启动，可访问 http://localhost:8000
- 已配置有效的 OPENAI_API_KEY
- 已准备一份标准 Python 测试源码

### 测试步骤

| 步骤 | 操作描述 | 测试数据 | 预期结果 |
|------|---------|---------|---------|
| 1 | 打开"测试生成"页面 | 访问 http://localhost:8000 | 页面正常渲染，包含代码编辑器 |
| 2 | 在编辑器中粘贴源码 | `def add(a, b): return a + b` | 代码正确显示在编辑器中 |
| 3 | 点击"生成测试"按钮 | — | 按钮变为加载状态，禁用重复点击 |
| 4 | 等待生成完成 | — | 显示进度节点，最终生成 pytest 代码 |
| 5 | 查看生成结果 | — | 测试代码包含正向/边界/异常用例 |

### 实际结果

- 实际结果: TBD
- 是否通过: ⏳ 待执行
```

---

## 二、自动化测试用例模板（pytest 单元测试）

### 模板结构

```python
"""
模块名: test_{module_name}.py
模块说明: {模块名称} 的单元测试

测试覆盖:
  - 功能测试: 正常流程
  - 边界测试: 空值/极值/边界条件
  - 异常测试: 非法输入/错误状态
  - 回归测试: 关键路径保护
"""

import pytest
from unittest.mock import MagicMock, patch

# ─── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def setup_fixture():
    """测试前置准备"""
    # Arrange
    data = {"key": "value"}
    yield data
    # Cleanup


# ─── 功能测试 ─────────────────────────────────────────────

class Test{ClassName}:
    """{ClassName} 功能测试"""

    def test_normal_flow(self, setup_fixture):
        """正常流程: 预期输入应返回预期结果"""
        # Arrange
        # Act
        result = self._call_method(setup_fixture)
        # Assert
        assert result == expected_value


# ─── 边界测试 ─────────────────────────────────────────────

class Test{ClassName}Boundary:
    """{ClassName} 边界测试"""

    def test_empty_input(self):
        """边界: 空输入应被正确处理"""
        # Arrange
        empty_data = ""
        # Act
        result = self._call_method(empty_data)
        # Assert
        assert result is not None
        assert not result

    def test_maximum_value(self):
        """边界: 最大值输入"""
        # Arrange
        max_value = sys.maxsize
        # Act
        result = self._call_method(max_value)
        # Assert
        assert result is not None

    def test_zero_value(self):
        """边界: 零值输入"""
        # Arrange
        zero_value = 0
        # Act
        result = self._call_method(zero_value)
        # Assert
        assert result == 0


# ─── 异常测试 ─────────────────────────────────────────────

class Test{ClassName}Exception:
    """{ClassName} 异常测试"""

    def test_invalid_input_raises(self):
        """异常: 非法输入应抛出异常"""
        with pytest.raises(ValueError) as excinfo:
            self._call_method(invalid_data)
        assert "错误信息关键词" in str(excinfo.value)

    def test_none_input(self):
        """异常: None 输入"""
        with pytest.raises(TypeError):
            self._call_method(None)

    def test_mock_external_dependency(self):
        """异常: 外部依赖不可用时的处理"""
        with patch("module.external_func") as mock_func:
            mock_func.side_effect = ConnectionError("mock connection error")
            with pytest.raises(ConnectionError):
                self._call_method()
```

### 完整示例

```python
"""
test_config.py — 配置模块单元测试

测试覆盖:
  - 功能: 默认配置值验证
  - 功能: 环境判断
  - 功能: Settings 单例
  - 异常: 缺失 API Key
  - 边界: 覆盖率阈值边界
  - 异常: 不支持的 LLM Provider
"""

import pytest
from app.config import Settings, get_settings, validate_config, get_llm


class TestSettings:
    """配置模块功能测试"""

    def test_default_settings(self):
        """功能: 默认配置值验证"""
        s = Settings()
        assert s.app_name == "Test Generation Toolkit"
        assert s.environment == "development"
        assert s.debug is True
        assert s.llm_provider == "openai"
        assert s.llm_model == "gpt-4o"
        assert s.coverage_threshold == 80.0
        assert s.max_retries == 3
        assert s.task_workers == 2
        assert s.sandbox_enabled is True

    def test_is_production_property(self):
        """功能: 生产环境判断"""
        assert Settings(environment="PRODUCTION").is_production is True
        assert Settings(environment="development").is_production is False

    def test_settings_singleton(self):
        """功能: Settings 单例缓存"""
        assert get_settings() is get_settings()


class TestConfigValidation:
    """配置校验测试"""

    def test_validate_missing_openai_key(self, monkeypatch):
        """异常: 缺少 OpenAI API Key"""
        s = Settings(openai_api_key=None, llm_provider="openai")
        monkeypatch.setattr("app.config.get_settings", lambda: s)
        with pytest.raises(RuntimeError) as excinfo:
            validate_config()
        assert "OPENAI_API_KEY" in str(excinfo.value)

    def test_validate_missing_azure_key(self, monkeypatch):
        """异常: 缺少 Azure 配置"""
        s = Settings(llm_provider="azure")
        monkeypatch.setattr("app.config.get_settings", lambda: s)
        with pytest.raises(RuntimeError) as excinfo:
            validate_config()
        assert "AZURE_API_KEY" in str(excinfo.value)


class TestCoverageThreshold:
    """覆盖率阈值边界测试"""

    def test_threshold_zero(self):
        """边界: 覆盖率阈值最小边界 0%"""
        s = Settings(coverage_threshold=0)
        assert 0 <= s.coverage_threshold <= 100

    def test_threshold_hundred(self):
        """边界: 覆盖率阈值最大边界 100%"""
        s = Settings(coverage_threshold=100)
        assert 0 <= s.coverage_threshold <= 100

    def test_threshold_negative_raises(self, monkeypatch):
        """边界: 负数阈值导致校验失败"""
        s = Settings(coverage_threshold=-1)
        monkeypatch.setattr("app.config.get_settings", lambda: s)
        with pytest.raises(RuntimeError):
            validate_config()

    def test_threshold_above_hundred_raises(self, monkeypatch):
        """边界: 超 100 阈值导致校验失败"""
        s = Settings(coverage_threshold=150)
        monkeypatch.setattr("app.config.get_settings", lambda: s)
        with pytest.raises(RuntimeError):
            validate_config()


class TestLLMFactory:
    """LLM 工厂测试"""

    def test_unsupported_provider_raises(self):
        """异常: 不支持的 LLM Provider"""
        with pytest.raises(ValueError) as excinfo:
            get_llm(provider="invalid_provider")
        assert "不支持的 llm_provider" in str(excinfo.value)

    def test_openai_provider_returns_llm(self, monkeypatch):
        """功能: OpenAI provider 返回 LLM 实例"""
        s = Settings(openai_api_key="test-key")
        monkeypatch.setattr("app.config.get_settings", lambda: s)
        llm = get_llm(provider="openai")
        assert llm is not None

    def test_local_provider_with_base_url(self, monkeypatch):
        """功能: 本地兼容端点"""
        s = Settings(
            openai_api_key="sk-local",
            openai_api_base="http://localhost:11434/v1",
        )
        monkeypatch.setattr("app.config.get_settings", lambda: s)
        llm = get_llm(provider="local")
        assert llm is not None
```

---

## 三、性能测试用例模板

### 模板结构

```markdown
### 性能用例基本信息

| 字段 | 内容 |
|------|------|
| 用例编号 | PT-{模块}-{序号} |
| 用例名称 | {性能测试目标} |
| 测试工具 | wrk/ab/locust/pytest-benchmark |
| 测试环境 | {硬件配置、软件版本} |
| 并发用户数 | {N} |
| 测试时长 | {N} 秒/分钟 |
| 吞吐量指标 | {N} req/s |
| P95 响应时间 | < {N} ms |

### 性能指标

| 指标名称 | 指标值 | 说明 |
|---------|--------|------|
| 并发用户数 | {N} | 同时发起请求的用户数 |
| 吞吐量 | {N} req/s | 每秒请求数 |
| P50 响应时间 | < {N} ms | 中位数响应时间 |
| P95 响应时间 | < {N} ms | 95 分位响应时间 |
| P99 响应时间 | < {N} ms | 99 分位响应时间 |
| 错误率 | < 0.1% | 失败请求占比 |
| CPU 使用率 | < {N}% | 服务端 CPU 使用 |
| 内存使用率 | < {N}% | 服务端内存使用 |

### 测试步骤

1. {准备测试数据}
2. {启动性能测试工具}
3. {设置并发和时长参数}
4. {执行压测}
5. {收集和分析结果}
6. {对比性能基线，判断是否达标}

### 测试结果

| 指标 | 基线 | 本次结果 | 是否达标 |
|------|------|---------|---------|
| P95 响应时间 | {N}ms | {N}ms | ✅/❌ |
| 吞吐量 | {N} req/s | {N} req/s | ✅/❌ |
```

### 完整示例

```markdown
### 性能用例基本信息

| 字段 | 内容 |
|------|------|
| 用例编号 | PT-API-001 |
| 用例名称 | 健康检查接口高并发压测 |
| 测试工具 | wrk |
| 并发用户数 | 1000 |
| 测试时长 | 60 秒 |
| P95 响应时间 | < 10ms |

### 性能指标

| 指标名称 | 指标值 | 说明 |
|---------|--------|------|
| 并发用户数 | 1000 | 同时 1000 个连接 |
| 吞吐量 | ≥ 5000 req/s | 每秒请求数 |
| P95 响应时间 | < 10 ms | 95 分位响应时间 |
| 错误率 | < 0.01% | 失败请求占比 |
| CPU 使用率 | < 50% | 服务端 CPU 使用 |

### 测试步骤

1. 启动服务: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. 执行压测: `wrk -t8 -c1000 -d60s http://localhost:8000/health`
3. 收集结果: `wrk` 输出各项指标
4. 对比基线，判断是否达标

### 测试结果

| 指标 | 基线 | 本次结果 | 是否达标 |
|------|------|---------|---------|
| P95 响应时间 | 5ms | 8ms | ✅ |
| 吞吐量 | 8000 req/s | 6500 req/s | ✅ |
```

---

## 四、UI 测试用例模板

### 模板结构

```markdown
### UI 用例基本信息

| 字段 | 内容 |
|------|------|
| 用例编号 | UI-{模块}-{序号} |
| 用例名称 | {UI 测试目标} |
| 页面/路由 | /{页面路径} |
| 测试浏览器 | Chrome 120+ / Firefox / Safari / Edge |
| 视口尺寸 | 1920x1080 / 768x1024 / 375x812 |
| 优先级 | P0/P1/P2 |

### 前置条件

- 服务已启动
- 浏览器环境正常
- {必要的数据准备}

### UI 操作步骤

| 步骤 | 操作 | 预期 UI 表现 |
|------|------|-------------|
| 1 | {点击/输入/导航} | {界面响应} |
| 2 | {点击/输入/导航} | {界面响应} |
| 3 | {点击/输入/导航} | {界面响应} |

### UI 验证点

- [ ] 元素可见性
- [ ] 文案正确性
- [ ] 样式一致性
- [ ] 交互响应
- [ ] 状态切换
- [ ] 错误提示

### 截图记录

- 操作前截图:
- 操作后截图:
- 错误状态截图:

### 自动化脚本（Playwright）

```python
def test_{ui_name}(page):
    """{UI 测试描述}"""
    page.goto("{url}")
    page.wait_for_load_state("networkidle")
    # 执行操作
    page.click("text={按钮文本}")
    page.fill("input[placeholder='{占位符}']", "{输入内容}")
    # 验证
    assert page.locator("text={预期文本}").is_visible()
    # 截图
    page.screenshot(path="{截图路径}")
```

---

## 五、安全测试用例模板

### 模板结构

```markdown
### 安全用例基本信息

| 字段 | 内容 |
|------|------|
| 用例编号 | ST-{类型}-{序号} |
| 用例名称 | {安全测试目标} |
| 安全类别 | OWASP Top 10 / 认证 / 授权 / 注入 / 数据保护 |
| 严重程度 | Critical/High/Medium/Low |
| 优先级 | P0/P1/P2 |

### 测试描述

{详细描述该安全测试的目的和风险}

### 攻击向量

| 向量 | 描述 |
|------|------|
| {攻击类型} | {注入路径和方式} |
| {攻击负载} | {payload 示例} |

### 测试步骤

1. {设置测试环境}
2. {发送攻击请求}
3. {观察系统响应}
4. {分析漏洞影响}

### 安全验证清单

- [ ] 输入验证
- [ ] 输出编码
- [ ] 访问控制
- [ ] 会话管理
- [ ] 敏感数据保护
- [ ] 安全配置
- [ ] 错误处理

### 风险等级

- 影响范围: {数据泄露/服务中断/权限提升等}
- 利用难度: {容易/中等/困难}
- 风险等级: {Critical/High/Medium/Low}

### 修复建议

- {建议 1}
- {建议 2}
```

---

## 六、API 集成测试用例模板

### 模板结构

```python
"""
test_api_{module_name}.py — {模块名} API 集成测试

覆盖:
  - 正常流程: 标准请求返回正确响应
  - 异常流程: 错误参数返回正确状态码
  - 边界条件: 空值/极值/分页
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class Test{Module}API:
    """{模块} API 集成测试"""

    def test_{endpoint}_success(self):
        """正常: {endpoint} 成功返回"""
        # Arrange
        request_data = {...}
        # Act
        resp = client.post("/api/{endpoint}", json=request_data)
        # Assert
        assert resp.status_code == 200
        data = resp.json()
        assert data["{key}"] == {expected_value}

    def test_{endpoint}_validation_error(self):
        """异常: 参数校验失败"""
        # Arrange
        invalid_data = {...}
        # Act
        resp = client.post("/api/{endpoint}", json=invalid_data)
        # Assert
        assert resp.status_code == 422  # FastAPI validation error

    def test_{endpoint}_not_found(self):
        """异常: 资源不存在"""
        # Arrange
        non_existent_id = "nonexistent"
        # Act
        resp = client.get(f"/api/{endpoint}/{non_existent_id}")
        # Assert
        assert resp.status_code == 404

    def test_{endpoint}_boundary(self):
        """边界: 空数据/极值"""
        # Arrange
        empty_data = {}
        # Act
        resp = client.post("/api/{endpoint}", json=empty_data)
        # Assert
        assert resp.status_code in (400, 422)
```

---

## 七、冒烟测试用例模板

### 模板结构

```markdown
### 冒烟用例基本信息

| 字段 | 内容 |
|------|------|
| 用例编号 | SMK-{版本}-{序号} |
| 用例名称 | {核心流程冒烟} |
| 执行时机 | 每次构建后 |
| 执行时长 | < 5 分钟 |
| 执行人员 | 自动/QA |

### 冒烟范围（P0 核心功能）

| 模块 | 冒烟内容 | 优先级 |
|------|---------|-------|
| 服务健康 | /health 返回 200 | P0 |
| 测试生成 | 简单代码能生成测试 | P0 |
| 用例库 | 创建/查询用例 | P0 |
| 缺陷跟踪 | 创建/查询缺陷 | P0 |
| 报告生成 | 能生成报告 | P0 |

### 冒烟执行清单

- [ ] 服务正常启动
- [ ] 健康检查通过
- [ ] 首页可访问
- [ ] 核心 API 响应正常
- [ ] 数据库操作正常

### 冒烟结果

| 用例 | 结果 | 备注 |
|------|------|------|
| 服务健康 | ✅/❌ | |
| 测试生成 | ✅/❌ | |
| 用例库 | ✅/❌ | |
| 缺陷跟踪 | ✅/❌ | |
| 报告生成 | ✅/❌ | |

### 结论

- 冒烟测试: ✅ 通过（可进入详细测试） / ❌ 失败（阻塞发布）
```

---

## 八、测试用例质量评审清单

### 通用检查项

- [ ] 用例编号唯一且可追踪
- [ ] 用例名称简洁明了，能概括测试目标
- [ ] 前置条件清晰完整
- [ ] 测试步骤可执行、无歧义
- [ ] 测试数据明确具体
- [ ] 预期结果可验证
- [ ] 优先级分配合理
- [ ] 覆盖了正常、边界、异常三类场景

### 功能测试检查项

- [ ] 每个功能模块都有对应用例
- [ ] 正常流程覆盖完整
- [ ] 异常流程覆盖充分
- [ ] 边界条件被覆盖

### 安全测试检查项

- [ ] 输入注入防护被验证
- [ ] 权限控制被验证
- [ ] 敏感数据保护被验证
- [ ] 路径穿越防护被验证

### 性能测试检查项

- [ ] 有明确的性能指标基线
- [ ] 包含并发/负载/压力场景
- [ ] 资源消耗指标可测量
- [ ] 有性能回归阈值

---

## 九、测试用例命名规范

### 手工用例编号规则

```
TC-{模块缩写}-{序号}
     │          │
     │          └── 3 位数字序号（001~999）
     └── 模块缩写（GEN/CASE/DEFECT/SCAN/REPORT/TASK/API/UI/PERF/SEC）
```

### 自动化测试命名规则

```
test_{模块名}_{测试场景}_{期望结果}.py

示例:
  test_config_default_settings.py     → 配置默认值
  test_cases_repository_crud.py       → 用例库 CRUD
  test_defects_tracker_lifecycle.py   → 缺陷生命周期
  test_mock_generator_detection.py    → Mock 依赖检测
  test_reports_generator_formats.py   → 报告格式
  test_tasks_manager_state_machine.py → 任务状态机
```

### pytest 函数命名规则

```
test_{场景描述}_{期望结果}
```

| 场景 | 命名 | 示例 |
|------|------|------|
| 正常流程 | test_{功能}_{结果} | test_create_case_success |
| 边界条件 | test_{功能}_boundary_{值} | test_threshold_boundary_zero |
| 异常场景 | test_{功能}_raises_{错误} | test_invalid_input_raises_valueerror |
| 空值场景 | test_{功能}_empty | test_list_empty_returns_empty_list |
| Mock 场景 | test_{功能}_with_mock | test_external_call_mocked |

---

> 本模板与 `docs/test-matrix.md`（测试矩阵）和
> `docs/test-cases-guide.md`（具体测试用例）配套使用。
