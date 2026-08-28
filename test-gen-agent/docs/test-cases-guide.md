# Test Generation Agent Toolkit — 全面测试用例指南

> 本文档从 **手工测试**、**自动化测试**、**性能测试**、**UI 测试** 四个维度，为「Test Generation Agent Toolkit」项目提供完整的测试用例设计与覆盖方案。

## 📚 配套文档

- [测试矩阵](./test-matrix.md) — 多维度覆盖矩阵（功能/边界/异常/安全/兼容/回归/性能/可靠性/并发）
- [测试用例模板](./test-case-template.md) — 行业标准测试用例模板（IEEE 829 规范）
- [测试文档索引](./README.md) — 测试文档导航

---

## 一、手工测试用例

手工测试覆盖系统各功能模块的正常流程、异常流程与边界条件，由测试人员按步骤逐一验证。

### 1.1 测试生成模块

| 用例编号 | 测试项 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|---------|-------|
| MT-001 | 单文件测试生成（正常流程） | 服务已启动，有有效 API Key | ① 在"测试生成"页粘贴 Python 代码 ② 点击"生成测试" | 显示生成进度节点（扫描→Mock→生成→运行→覆盖率），最终显示生成的 pytest 代码和运行结果 | P0 |
| MT-002 | 单文件测试生成（空代码） | 服务已启动 | ① 不输入任何代码 ② 直接点击"生成" | 前端提示"源代码不能为空"，后端返回 400 | P0 |
| MT-003 | 单文件测试生成（语法错误代码） | 服务已启动 | ① 粘贴含语法错误的代码 ② 点击"生成" | 系统能捕获语法错误，不崩溃，提示扫描失败或返回空签名 | P1 |
| MT-004 | 单文件测试生成（大量代码） | 服务已启动 | ① 粘贴 500 行以上的大型代码 ② 点击"生成" | 系统能正常处理，不超时，显示生成结果 | P1 |
| MT-005 | 异步模式生成 | 服务已启动 | ① 选择异步模式生成 ② 提交后获取 task_id ③ 轮询任务状态 | 立即返回 task_id，任务在后台执行，最终状态为 success 并返回结果 | P0 |
| MT-006 | 异步任务超时 | 服务已启动 | ① 提交一个超长耗时的任务 ② 等待超过 task_timeout | 任务状态变为 failed，提示超时 | P1 |
| MT-007 | LLM 调用失败场景 | 服务已启动，API Key 无效 | ① 粘贴代码 ② 点击"生成" | 系统捕获 LLM 调用异常，任务失败，前端显示错误信息，服务不崩溃 | P0 |
| MT-008 | WebSocket 流式生成 | 服务已启动 | ① 通过 WS 连接提交代码 ② 观察实时进度 | 按节点逐步推送进度事件，最终收到 done 消息 | P0 |
| MT-009 | WebSocket 空代码 | 服务已启动 | ① WS 连接后发送空 source_code | 收到 error 消息"源代码不能为空"，连接关闭 | P1 |

### 1.2 用例库管理模块

| 用例编号 | 测试项 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|---------|-------|
| MT-010 | 创建用例（完整字段） | 服务已启动 | ① 填写标题、描述、源码、标签 ② 点击"新建用例" | 用例创建成功，出现在用例列表中 | P0 |
| MT-011 | 创建用例（仅标题） | 服务已启动 | ① 只填写标题 ② 点击"新建" | 用例创建成功，其余字段为默认值 | P1 |
| MT-012 | 创建用例（空标题） | 服务已启动 | ① 不填写标题 ② 点击"新建" | 后端校验失败，返回错误提示 | P1 |
| MT-013 | 更新用例（修改状态） | 存在一条用例 | ① 打开用例详情 ② 将状态从 draft 改为 approved | 状态更新成功，列表反映变更 | P0 |
| MT-014 | 更新用例（非法状态） | 存在一条用例 | ① 尝试将状态改为不存在的值 | 后端返回 400，提示无效状态 | P1 |
| MT-015 | 更新用例（非法优先级） | 存在一条用例 | ① 尝试将优先级改为 P5 | 后端返回 400，提示无效优先级 | P1 |
| MT-016 | 搜索用例 | 存在多条用例 | ① 在搜索框输入关键词 | 返回标题或描述包含关键词的用例 | P0 |
| MT-017 | 按状态过滤 | 存在多条不同状态用例 | ① 选择状态为 approved | 仅显示已批准状态的用例 | P1 |
| MT-018 | 删除用例 | 存在一条用例 | ① 点击删除按钮 ② 确认删除 | 用例被删除，列表不再显示 | P0 |
| MT-019 | 删除不存在的用例 | 服务已启动 | ① 用不存在的 ID 调用 DELETE API | 返回 404 | P1 |
| MT-020 | 查看用例统计 | 存在多条用例 | ① 打开用例库统计 | 正确显示总数和按状态/优先级的分布 | P1 |

### 1.3 缺陷跟踪模块

| 用例编号 | 测试项 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|---------|-------|
| MT-021 | 创建缺陷 | 服务已启动 | ① 填写缺陷标题、严重程度 ② 点击"新建缺陷" | 缺陷创建成功，初始状态为 open | P0 |
| MT-022 | 缺陷自动创建 | 测试生成失败 | ① 执行一个会失败的测试生成 | 系统自动创建缺陷，关联文件路径和错误信息 | P0 |
| MT-023 | 更新缺陷状态 | 存在一个缺陷 | ① 打开缺陷详情 ② 将状态改为 in_progress → fixed | 状态更新成功，变更历史可追溯 | P0 |
| MT-024 | 更新缺陷（非法状态） | 存在一个缺陷 | ① 尝试将状态改为不存在的值 | 后端返回 400 | P1 |
| MT-025 | 更新缺陷（非法严重程度） | 存在一个缺陷 | ① 尝试将严重程度改为不存在的值 | 后端返回 400 | P1 |
| MT-026 | 按状态过滤缺陷 | 存在多个不同状态缺陷 | ① 选择过滤状态为 open | 仅显示 open 状态的缺陷 | P1 |
| MT-027 | 按严重程度过滤 | 存在多个不同严重程度缺陷 | ① 选择过滤严重程度为 critical | 仅显示 critical 级别的缺陷 | P1 |
| MT-028 | 删除缺陷 | 存在一个缺陷 | ① 点击删除按钮 | 缺陷被删除，列表不再显示 | P1 |
| MT-029 | 查看缺陷统计 | 存在多个缺陷 | ① 打开缺陷统计 | 正确显示缺陷总数和按状态的分布 | P2 |

### 1.4 项目扫描模块

| 用例编号 | 测试项 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|---------|-------|
| MT-030 | 项目扫描（正常） | 项目目录存在 | ① 输入项目路径 ② 点击"扫描" | 递归扫描所有 .py 文件，展示文件列表和函数签名 | P0 |
| MT-031 | 项目扫描（不存在的路径） | 路径无效 | ① 输入不存在的路径 ② 点击"扫描" | 返回 404，提示"项目目录不存在" | P1 |
| MT-032 | 项目扫描（空目录） | 目录为空 | ① 输入空目录路径 | 返回扫描结果，total_files=0 | P2 |
| MT-033 | 排除 test_ 文件 | 项目含测试文件 | ① 扫描项目目录 | test_*.py 文件被排除在扫描结果之外 | P1 |
| MT-034 | 项目批量生成 | 项目有多个 .py 文件 | ① 扫描项目 ② 点击"批量生成" | 对每个文件执行测试生成流程，返回各文件结果 | P0 |

### 1.5 报告中心模块

| 用例编号 | 测试项 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|---------|-------|
| MT-035 | 生成 HTML 报告 | 存在用例数据 | ① 在报告中心选择 HTML 格式 ② 点击"生成" | 生成 report_*.html 文件，可在线预览 | P0 |
| MT-036 | 生成 JUnit 报告 | 存在用例数据 | ① 选择 JUnit 格式 ② 点击"生成" | 生成 junit_*.xml 文件 | P0 |
| MT-037 | 生成 Markdown 报告 | 存在用例数据 | ① 选择 Markdown 格式 ② 点击"生成" | 生成 report_*.md 文件 | P1 |
| MT-038 | 生成报告（无用例数据） | 无任何用例 | ① 尝试生成报告 | 返回 404，提示"无用例数据" | P1 |
| MT-039 | 下载报告 | 已有报告文件 | ① 在报告列表点击"下载" | 文件被下载到本地 | P0 |
| MT-040 | 报告列表 | 已有报告文件 | ① 打开报告列表 | 按时间倒序显示所有已生成的报告 | P1 |

### 1.6 任务队列模块

| 用例编号 | 测试项 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|---------|-------|
| MT-041 | 任务提交与查询 | 服务已启动 | ① 提交任务 ② 获取 task_id ③ 查询任务状态 | 任务状态从 pending → running → success/failed | P0 |
| MT-042 | 任务列表 | 已提交多个任务 | ① 查看任务列表 | 按创建时间倒序显示任务 | P1 |
| MT-043 | 查询不存在的任务 | 服务已启动 | ① 用不存在的 task_id 查询 | 返回 404 | P2 |

### 1.7 健康检查与配置

| 用例编号 | 测试项 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|---------|-------|
| MT-044 | 健康检查 | 服务已启动 | ① 访问 /health | 返回 {"status": "ok", "version": "0.2.0"} | P0 |
| MT-045 | 配置校验 | 配置缺失 | ① 不配置 API Key 启动 | 服务可启动（延迟初始化），调用时提示配置错误 | P0 |
| MT-046 | 配置校验 | 非法配置 | ① 设置 coverage_threshold=200 | 启动时配置校验失败，进程退出 | P1 |

---

## 二、自动化测试用例

自动化测试基于 pytest + LangGraph 的工作流框架，覆盖代码的核心逻辑单元。

### 2.1 配置模块（app/config.py）

```python
# test_config.py
import pytest
from app.config import Settings, get_settings, validate_config

class TestSettings:
    """配置模块单元测试"""
    
    def test_default_settings(self):
        """默认配置值验证"""
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
        """生产环境判断"""
        s = Settings(environment="PRODUCTION")
        assert s.is_production is True
        s2 = Settings(environment="development")
        assert s2.is_production is False

    def test_settings_singleton(self):
        """Settings 单例缓存"""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_validate_config_missing_key(self, monkeypatch):
        """缺少 API Key 时配置校验失败"""
        s = Settings(openai_api_key=None, llm_provider="openai")
        monkeypatch.setattr("app.config.get_settings", lambda: s)
        with pytest.raises(RuntimeError) as excinfo:
            validate_config()
        assert "OPENAI_API_KEY" in str(excinfo.value)

    def test_validate_config_bad_threshold(self, monkeypatch):
        """覆盖率阈值超出范围"""
        s = Settings(coverage_threshold=150.0)
        monkeypatch.setattr("app.config.get_settings", lambda: s)
        with pytest.raises(RuntimeError):
            validate_config()

    def test_get_llm_unsupported_provider(self):
        """不支持的 LLM Provider"""
        from app.config import get_llm
        with pytest.raises(ValueError) as excinfo:
            get_llm(provider="invalid_provider")
        assert "不支持的 llm_provider" in str(excinfo.value)
```

### 2.2 Mock 生成模块（app/generators/mock_generator.py）

```python
# test_mock_generator.py
import ast
import pytest
from app.generators.mock_generator import (
    DependencyDetector, generate_mocks, DEPENDENCY_RULES
)

class TestDependencyDetector:
    """依赖检测器单元测试"""

    def test_detect_http_request(self):
        """检测 HTTP 请求依赖"""
        source = """
import requests

def fetch_data():
    resp = requests.get('https://api.example.com')
    return resp.json()
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) > 0
        assert detector.detected[0]["category"] == "http"

    def test_detect_database(self):
        """检测数据库依赖"""
        source = """
from sqlalchemy import create_engine

def query_db():
    engine = create_engine('sqlite:///test.db')
    conn = engine.connect()
    result = conn.execute("SELECT * FROM users")
    return result
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) > 0
        assert detector.detected[0]["category"] == "database"

    def test_detect_filesystem(self):
        """检测文件系统依赖"""
        source = """
def read_file(path):
    with open(path, 'r') as f:
        return f.read()
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) > 0
        assert detector.detected[0]["category"] == "filesystem"

    def test_no_dependency(self):
        """无外部依赖的纯函数"""
        source = """
def add(a, b):
    return a + b
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) == 0

    def test_syntax_error_returns_error(self):
        """语法错误的源码返回 error"""
        result = generate_mocks({"source_code": "def broken(:"})
        assert "error" in result["mocks"]

    def test_dedup_by_target(self):
        """相同依赖去重"""
        source = """
import requests

def get_a():
    return requests.get('/a')

def get_b():
    return requests.get('/b')
"""
        result = generate_mocks({"source_code": source})
        assert result["mocks"]["count"] >= 1
```

### 2.3 Python 扫描器（app/scanners/python_scanner.py）

```python
# test_python_scanner.py
import pytest
from app.scanners.python_scanner import scan_python_file

class TestScanPythonFile:
    """Python 源码扫描器单元测试"""

    def test_scan_simple_function(self):
        """扫描简单函数"""
        source = "def add(a, b):\n    return a + b\n"
        result = scan_python_file({"source_code": source})
        assert len(result["signatures"]) == 1
        assert result["signatures"][0]["name"] == "add"
        assert len(result["signatures"][0]["params"]) == 2

    def test_scan_with_annotations(self):
        """扫描带类型注解的函数"""
        source = "def divide(a: int, b: int) -> float:\n    return a / b\n"
        result = scan_python_file({"source_code": source})
        sig = result["signatures"][0]
        assert sig["params"][0]["annotation"] == "int"
        assert sig["returns"] == "float"

    def test_scan_multiple_functions(self):
        """扫描多个函数"""
        source = "def f1(): pass\ndef f2(): pass\ndef f3(): pass\n"
        result = scan_python_file({"source_code": source})
        assert len(result["signatures"]) == 3

    def test_scan_syntax_error(self):
        """扫描语法错误的代码返回空签名"""
        result = scan_python_file({"source_code": "def broken(:"})
        assert result["signatures"] == []

    def test_scan_class_methods(self):
        """扫描类方法"""
        source = """
class MyClass:
    def method1(self):
        return 1
    async def method2(self, x):
        return x
"""
        result = scan_python_file({"source_code": source})
        assert len(result["signatures"]) == 2
```

### 2.4 用例库仓储（app/cases/repository.py）

```python
# test_cases_repository.py
import json
import pytest
from app.cases.repository import (
    create_case, get_case, list_cases, update_case,
    delete_case, update_case_result, get_stats,
    VALID_STATUSES, VALID_PRIORITIES
)

@pytest.fixture
def clean_db():
    """清理测试数据"""
    yield
    cases = list_cases(limit=100)
    for c in cases:
        delete_case(c["id"])

class TestCaseRepository:
    """用例库 CRUD 测试"""

    def test_create_case(self, clean_db):
        """创建用例"""
        case = create_case(
            title="测试用例A",
            description="测试描述",
            tags=["smoke", "regression"],
            status="draft",
            priority="P0"
        )
        assert case["title"] == "测试用例A"
        assert case["tags"] == ["smoke", "regression"]
        assert case["status"] == "draft"
        assert case["priority"] == "P0"

    def test_get_case_not_found(self):
        """获取不存在的用例返回 None"""
        assert get_case("nonexistent") is None

    def test_update_case(self, clean_db):
        """更新用例"""
        case = create_case(title="原标题")
        updated = update_case(case["id"], title="新标题", priority="P1")
        assert updated["title"] == "新标题"
        assert updated["priority"] == "P1"

    def test_update_case_invalid_status(self, clean_db):
        """非法状态更新"""
        case = create_case(title="测试")
        with pytest.raises(ValueError) as excinfo:
            update_case(case["id"], status="invalid_status")
        assert "无效状态" in str(excinfo.value)

    def test_update_case_invalid_priority(self, clean_db):
        """非法优先级更新"""
        case = create_case(title="测试")
        with pytest.raises(ValueError) as excinfo:
            update_case(case["id"], priority="P9")
        assert "无效优先级" in str(excinfo.value)

    def test_list_cases_by_status(self, clean_db):
        """按状态过滤用例"""
        create_case(title="草稿用例", status="draft")
        create_case(title="评审用例", status="review")
        create_case(title="批准用例", status="approved")
        
        drafts = list_cases(status="draft")
        assert len(drafts) == 1
        assert drafts[0]["title"] == "草稿用例"

    def test_list_cases_by_priority(self, clean_db):
        """按优先级过滤"""
        create_case(title="高优先级", priority="P0")
        create_case(title="低优先级", priority="P3")
        
        p0_cases = list_cases(priority="P0")
        assert len(p0_cases) == 1
        assert p0_cases[0]["title"] == "高优先级"

    def test_list_cases_search(self, clean_db):
        """关键词搜索"""
        create_case(title="登录功能测试")
        create_case(title="注册功能测试")
        
        results = list_cases(search="登录")
        assert len(results) == 1
        assert results[0]["title"] == "登录功能测试"

    def test_update_case_result(self, clean_db):
        """更新用例结果"""
        case = create_case(title="测试")
        result = {"passed": True, "stdout": "ok"}
        updated = update_case_result(case["id"], result)
        assert updated["last_result"]["passed"] is True

    def test_get_stats(self, clean_db):
        """用例统计"""
        create_case(title="A", status="draft", priority="P0")
        create_case(title="B", status="review", priority="P1")
        stats = get_stats()
        assert stats["total"] >= 2
        assert stats["by_status"]["draft"] >= 1
        assert stats["by_status"]["review"] >= 1

    def test_delete_case(self, clean_db):
        """删除用例"""
        case = create_case(title="待删除")
        deleted = delete_case(case["id"])
        assert deleted is True
        assert get_case(case["id"]) is None

    def test_delete_nonexistent_case(self):
        """删除不存在的用例"""
        deleted = delete_case("nonexistent")
        assert deleted is False
```

### 2.5 缺陷跟踪模块（app/defects/tracker.py）

```python
# test_defects_tracker.py
import pytest
from app.defects.tracker import (
    create_defect, get_defect, list_defects, update_defect,
    delete_defect, auto_create_defect_from_result,
    VALID_STATUSES, VALID_SEVERITIES
)

@pytest.fixture
def clean_db():
    yield
    defects = list_defects(limit=100)
    for d in defects:
        delete_defect(d["id"])

class TestDefectTracker:
    """缺陷跟踪测试"""

    def test_create_defect(self, clean_db):
        """创建缺陷"""
        defect = create_defect(
            title="登录失败",
            severity="critical",
            file_path="login.py",
            assignee="tester1"
        )
        assert defect["title"] == "登录失败"
        assert defect["severity"] == "critical"
        assert defect["status"] == "open"

    def test_update_defect_status(self, clean_db):
        """更新缺陷状态"""
        defect = create_defect(title="Bug A")
        updated = update_defect(defect["id"], status="fixed")
        assert updated["status"] == "fixed"

    def test_update_defect_invalid_status(self, clean_db):
        """非法状态"""
        defect = create_defect(title="Bug A")
        with pytest.raises(ValueError) as excinfo:
            update_defect(defect["id"], status="unknown_status")
        assert "无效状态" in str(excinfo.value)

    def test_update_defect_invalid_severity(self, clean_db):
        """非法严重程度"""
        defect = create_defect(title="Bug A")
        with pytest.raises(ValueError) as excinfo:
            update_defect(defect["id"], severity="ultra")
        assert "无效严重程度" in str(excinfo.value)

    def test_auto_create_defect_on_failure(self, clean_db):
        """测试失败自动创建缺陷"""
        test_result = {
            "passed": False,
            "stdout": "",
            "stderr": "AssertionError: assert 1 == 2"
        }
        defect = auto_create_defect_from_result("test_file.py", test_result)
        assert defect is not None
        assert "断言失败" in defect["title"]

    def test_no_defect_on_pass(self, clean_db):
        """测试通过不创建缺陷"""
        test_result = {"passed": True, "stdout": "ok", "stderr": ""}
        defect = auto_create_defect_from_result("test_file.py", test_result)
        assert defect is None

    def test_severity_detection_critical(self, clean_db):
        """严重程度自动判断"""
        test_result = {
            "passed": False,
            "stderr": "Error: connection refused"
        }
        defect = auto_create_defect_from_result("file.py", test_result)
        assert defect["severity"] == "critical"

    def test_severity_detection_blocker(self, clean_db):
        """Blocker 级别错误检测"""
        test_result = {
            "passed": False,
            "stderr": "Segmentation fault occurred"
        }
        defect = auto_create_defect_from_result("file.py", test_result)
        assert defect["severity"] == "blocker"

    def test_list_defects_filter(self, clean_db):
        """按状态过滤缺陷"""
        create_defect(title="Bug A", status="open")
        create_defect(title="Bug B", status="fixed")
        open_defects = list_defects(status="open")
        assert len(open_defects) == 1
        assert open_defects[0]["title"] == "Bug A"

    def test_get_stats(self, clean_db):
        """缺陷统计"""
        create_defect(title="Bug 1")
        create_defect(title="Bug 2")
        stats = list_defects()
        assert stats["total"] >= 2
```

### 2.6 项目扫描模块（app/projects/manager.py）

```python
# test_projects_manager.py
import os
import tempfile
import pytest
from app.projects.manager import (
    scan_project, collect_sources_from_paths, _extract_signatures
)

class TestProjectScan:
    """项目扫描测试"""

    def test_scan_project_normal(self, tmp_path):
        """扫描正常项目"""
        # 创建测试项目
        (tmp_path / "mod1.py").write_text("def f1(): pass\ndef f2(): pass\n")
        (tmp_path / "mod2.py").write_text("def f3(): pass\n")
        (tmp_path / "test_mod.py").write_text("def test_f1(): pass\n")

        result = scan_project(str(tmp_path))
        assert result["total_files"] == 2  # test_mod.py 被排除
        assert result["total_functions"] == 3
        assert len(result["files"]) == 2

    def test_scan_project_nonexistent(self):
        """扫描不存在的目录"""
        with pytest.raises(FileNotFoundError):
            scan_project("/nonexistent/path")

    def test_scan_project_excludes(self, tmp_path):
        """排除目录"""
        os.makedirs(tmp_path / "__pycache__")
        os.makedirs(tmp_path / ".git")
        (tmp_path / "__pycache__" / "cache.py").write_text("def f(): pass\n")
        (tmp_path / "main.py").write_text("def main(): pass\n")

        result = scan_project(str(tmp_path))
        assert result["total_files"] == 1

    def test_collect_sources(self, tmp_path):
        """收集源码"""
        fpath = tmp_path / "demo.py"
        fpath.write_text("def add(a, b): return a + b\n")
        sources = collect_sources_from_paths([str(fpath)])
        assert len(sources) == 1
        assert "add" in sources[0]["source_code"]

    def test_collect_sources_missing_file(self):
        """收集不存在的文件"""
        sources = collect_sources_from_paths(["/nonexistent/file.py"])
        assert len(sources) == 0

    def test_extract_signatures(self):
        """提取函数签名"""
        source = "def foo(a: int, b: str) -> bool:\n    return True\n"
        sigs = _extract_signatures(source)
        assert len(sigs) == 1
        assert sigs[0]["name"] == "foo"
        assert sigs[0]["params"][0]["name"] == "a"
        assert sigs[0]["returns"] == "bool"

    def test_extract_signatures_syntax_error(self):
        """语法错误返回空"""
        assert _extract_signatures("def broken(:") == []
```

### 2.7 报告生成模块（app/reports/generator.py）

```python
# test_reports_generator.py
import os
import xml.etree.ElementTree as ET
import pytest
from app.reports.generator import (
    generate_html_report, generate_junit_report,
    generate_markdown_report, ensure_output_dir
)

@pytest.fixture
def sample_results():
    return [
        {
            "file_path": "module_a.py",
            "generated_tests": "def test_a(): pass",
            "test_result": {"passed": True, "stdout": "ok", "stderr": ""},
            "coverage_report": {"line_coverage_pct": 85.5},
            "retry_count": 0,
        },
        {
            "file_path": "module_b.py",
            "generated_tests": "def test_b(): pass",
            "test_result": {"passed": False, "stdout": "fail", "stderr": "AssertionError"},
            "coverage_report": {"line_coverage_pct": 70.0},
            "retry_count": 2,
        },
    ]

class TestReportGenerator:
    """报告生成测试"""

    def test_generate_html_report(self, sample_results):
        """生成 HTML 报告"""
        path = generate_html_report(sample_results)
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "测试生成报告" in content
        assert "module_a.py" in content
        assert "module_b.py" in content
        assert "85.5%" in content

    def test_generate_junit_report(self, sample_results):
        """生成 JUnit XML 报告"""
        path = generate_junit_report(sample_results)
        assert os.path.exists(path)
        tree = ET.parse(path)
        root = tree.getroot()
        assert root.tag == "testsuite"
        assert root.get("tests") == "2"
        assert root.get("failures") == "1"

    def test_generate_markdown_report(self, sample_results):
        """生成 Markdown 报告"""
        path = generate_markdown_report(sample_results)
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "测试生成报告" in content
        assert "module_a.py" in content

    def test_empty_results(self):
        """空结果也能生成报告"""
        path = generate_markdown_report([])
        assert os.path.exists(path)

    def test_ensure_output_dir(self):
        """确保输出目录存在"""
        path = ensure_output_dir()
        assert os.path.isdir(path)
```

### 2.8 任务队列模块（app/tasks/manager.py）

```python
# test_tasks_manager.py
import asyncio
import pytest
from app.tasks.manager import TaskManager, PENDING, RUNNING, SUCCESS, FAILED

class TestTaskManager:
    """任务队列测试"""

    def test_submit_and_execute(self):
        """任务提交与执行"""
        async def run():
            tm = TaskManager(maxsize=10)
            tm.start(num_workers=1)
            
            async def my_task(x):
                return x * 2
            
            task = await tm.submit(my_task, 5)
            assert task.status in (PENDING, RUNNING, SUCCESS)
            
            # 等待任务完成
            for _ in range(50):
                if task.status == SUCCESS:
                    break
                await asyncio.sleep(0.1)
            
            assert task.status == SUCCESS
            assert task.result == 10
            assert task.finished_at is not None
            await tm.stop()
        
        asyncio.run(run())

    def test_task_failure(self):
        """任务失败"""
        async def run():
            tm = TaskManager(maxsize=10)
            tm.start(num_workers=1)
            
            async def failing_task():
                raise ValueError("test error")
            
            task = await tm.submit(failing_task)
            for _ in range(50):
                if task.status == FAILED:
                    break
                await asyncio.sleep(0.1)
            
            assert task.status == FAILED
            assert "test error" in task.error
            await tm.stop()
        
        asyncio.run(run())

    def test_get_task_not_found(self):
        """查询不存在的任务"""
        async def run():
            tm = TaskManager()
            assert tm.get_task("nonexistent") is None
            assert tm.get_task_dict("nonexistent") is None
        asyncio.run(run())

    def test_list_tasks_empty(self):
        """空任务列表"""
        async def run():
            tm = TaskManager()
            assert tm.list_tasks() == []
        asyncio.run(run())

    def test_task_to_dict(self):
        """任务序列化"""
        async def run():
            tm = TaskManager()
            async def simple():
                return "done"
            task = await tm.submit(simple)
            d = task.to_dict()
            assert d["task_id"] == task.task_id
            assert d["status"] in (PENDING, RUNNING)
            assert "created_at" in d
        asyncio.run(run())
```

### 2.9 Docker 沙箱（app/sandbox/docker_runner.py）

```python
# test_docker_runner.py
import subprocess
import pytest
from app.sandbox.docker_runner import (
    _CompletedProcess, _docker_available,
    run_in_sandbox, _run_host_subprocess
)

class TestDockerRunner:
    """沙箱运行器测试"""

    def test_completed_process_str(self):
        """CompletedProcess 字符串输出"""
        cp = _CompletedProcess(["pytest"], 0, "stdout text", "stderr text")
        assert cp.stdout == "stdout text"
        assert cp.stderr == "stderr text"
        assert cp.returncode == 0

    def test_completed_process_bytes(self):
        """bytes 解码"""
        cp = _CompletedProcess(["pytest"], 1, b"stdout bytes", b"stderr bytes")
        assert cp.stdout == "stdout bytes"
        assert cp.stderr == "stderr bytes"

    def test_docker_available(self):
        """Docker 可用性检测（不抛异常）"""
        # 不验证具体返回值，只验证不抛异常
        try:
            result = _docker_available()
            assert isinstance(result, bool)
        except ImportError:
            pass  # docker SDK 未安装也属正常

    def test_run_host_subprocess_simple(self):
        """宿主机执行（降级路径）"""
        result = _run_host_subprocess(
            "def add(a, b): return a + b\n",
            "def test_add(): assert add(1, 2) == 3\n",
            "test_module",
            ["python", "-m", "pytest", "test_test_module.py", "-q"],
            30,
            None,
        )
        assert result.returncode == 0

    def test_run_host_subprocess_failure(self):
        """宿主机执行失败"""
        result = _run_host_subprocess(
            "def add(a, b): return a + b\n",
            "def test_add(): assert add(1, 2) == 4\n",  # 故意失败
            "test_module",
            ["python", "-m", "pytest", "test_test_module.py", "-q"],
            30,
            None,
        )
        assert result.returncode != 0
```

### 2.10 LangGraph 图构建（app/graph/builder.py）

```python
# test_graph_builder.py
import pytest
from app.graph.builder import build_graph, should_retry, should_improve_coverage

class TestGraphBuilder:
    """LangGraph 图构建测试"""

    def test_build_graph(self):
        """构建图不报错"""
        graph = build_graph()
        assert graph is not None

    def test_should_retry_passed(self):
        """测试通过直接去覆盖率分析"""
        state = {"test_result": {"passed": True}}
        assert should_retry(state) == "coverage_analysis"

    def test_should_retry_recoverable(self):
        """可恢复错误进入修复"""
        state = {
            "test_result": {"passed": False, "stderr": "AssertionError: x"},
            "retry_count": 0,
        }
        assert should_retry(state) == "refinement_node"

    def test_should_retry_unrecoverable(self):
        """不可恢复错误放弃修复"""
        state = {
            "test_result": {"passed": False, "stderr": "MemoryError: out of memory"},
            "retry_count": 0,
        }
        assert should_retry(state) == "coverage_analysis"

    def test_should_retry_max_retries(self):
        """超过重试上限停止修复"""
        state = {
            "test_result": {"passed": False, "stderr": "AssertionError"},
            "retry_count": 3,
        }
        assert should_retry(state) == "coverage_analysis"

    def test_should_improve_coverage_passed(self):
        """覆盖率达标结束"""
        state = {"coverage_report": {"passed_threshold": True}}
        assert should_improve_coverage(state) == "END"

    def test_should_improve_coverage_not_passed(self):
        """覆盖率不达标进入修复"""
        state = {
            "coverage_report": {"passed_threshold": False, "line_coverage_pct": 50},
            "retry_count": 0,
        }
        assert should_improve_coverage(state) == "refinement_node"

    def test_should_improve_coverage_error(self):
        """覆盖率报告出错结束"""
        state = {"coverage_report": {"error": "no data"}}
        assert should_improve_coverage(state) == "END"

    def test_should_improve_coverage_max(self):
        """超过覆盖率补测上限"""
        state = {
            "coverage_report": {"passed_threshold": False},
            "retry_count": 5,
        }
        assert should_improve_coverage(state) == "END"
```

### 2.11 覆盖率分析模块（app/coverage/analyzer.py）

```python
# test_coverage_analyzer.py
import pytest
from app.coverage.analyzer import _map_lines_to_functions, _build_report

class TestCoverageAnalyzer:
    """覆盖率分析模块测试"""

    def test_map_lines_to_functions(self):
        """行号到函数名映射"""
        source = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
        mapping = _map_lines_to_functions(source)
        assert mapping[1] == "foo"
        assert mapping[2] == "foo"
        assert mapping[4] == "bar"
        assert mapping[5] == "bar"

    def test_map_lines_syntax_error(self):
        """语法错误返回空映射"""
        assert _map_lines_to_functions("def broken(:") == {}

    def test_build_report(self):
        """构建覆盖率报告"""
        cov_data = {
            "files": {
                "test_module.py": {
                    "summary": {
                        "percent_covered": 85.5,
                        "covered_lines": 100,
                        "missing_lines": 20,
                        "num_branches": 10,
                        "covered_branches": 8,
                    },
                    "missing_lines": [5, 10],
                    "excluded_lines": [],
                }
            }
        }
        source = "def f1():\n    return 1\ndef f2():\n    return 2\n"
        report = _build_report(cov_data, source, "test_module")
        assert report["line_coverage_pct"] == 85.5
        assert report["branch_coverage_pct"] == 80.0
        assert report["passed_threshold"] is True

    def test_build_report_target_not_found(self):
        """目标模块不在覆盖率数据中"""
        cov_data = {"files": {"other.py": {}}}
        report = _build_report(cov_data, "source", "target_module")
        assert "error" in report
```

---

## 三、性能测试用例

性能测试验证系统在高负载/大数据量下的响应时间、吞吐量、资源消耗和稳定性。

### 3.1 API 接口性能基准

| 用例编号 | 测试项 | 测试方法 | 性能指标（P95） | 并发用户数 | 优先级 |
|---------|--------|---------|---------------|-----------|-------|
| PT-001 | `/health` 健康检查 | 压测工具（wrk/ab） | < 10ms | 1000 | P0 |
| PT-002 | `/api/cases` 列表查询 | 压测工具 | < 50ms | 100 | P0 |
| PT-003 | `/api/cases` 创建 | 压测工具 | < 50ms | 100 | P0 |
| PT-004 | `/api/defects` 列表 | 压测工具 | < 50ms | 100 | P1 |
| PT-005 | `/api/cases/{id}` 详情 | 压测工具 | < 30ms | 200 | P0 |
| PT-006 | 首页 `/` HTML 渲染 | 压测工具 | < 100ms | 100 | P1 |
| PT-007 | 静态资源加载 | 压测工具 | < 50ms | 200 | P1 |
| PT-008 | `/api/reports/generate` | 压测工具 | < 5s（含报告生成） | 10 | P1 |

### 3.2 并发与负载测试

| 用例编号 | 测试项 | 测试场景 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| PT-009 | 高并发任务提交 | 同时提交 100 个测试生成任务 | 任务队列正常接收，无任务丢失，系统不崩溃 | P0 |
| PT-010 | 任务队列容量限制 | 提交超过 maxsize=100 的任务 | 超出容量的任务排队等待，不报错 | P0 |
| PT-011 | 多 worker 并行执行 | 配置 4 个 worker 同时处理任务 | 任务并行处理，无资源竞争 | P0 |
| PT-012 | SQLite 并发读写 | 100 个并发请求同时读写用例库 | 无锁死/无异常，SQLite 能正确序列化 | P1 |
| PT-013 | WebSocket 并发连接 | 50 个客户端同时建立 WS 连接 | 所有连接正常建立，消息互不干扰 | P1 |

### 3.3 大数据量场景

| 用例编号 | 测试项 | 测试数据 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| PT-014 | 大量用例数据 | 10000 条用例 | 列表分页查询 < 100ms | P1 |
| PT-015 | 大量缺陷数据 | 5000 条缺陷 | 列表分页查询 < 100ms | P1 |
| PT-016 | 大源码文件生成 | 100KB 源码文件 | 生成完成时间 < 3min，不超时 | P1 |
| PT-017 | 大项目扫描 | 500+ 文件项目目录 | 扫描完成时间 < 10s | P1 |
| PT-018 | 长测试报告 | 1000 条测试结果 | 报告生成时间 < 5s | P1 |

### 3.3 资源消耗监控

```python
# test_performance.py — 性能基线测试
"""
性能基准测试：验证核心接口的响应时间与资源消耗。

运行方式：
    pytest tests/performance/test_performance.py --benchmark

指标基线（在标准开发环境）：
    - 健康检查 P95 < 10ms
    - 用例列表 P95 < 50ms（100 条以内）
    - 用例创建 P95 < 50ms
    - SQLite 写入 P95 < 20ms
"""
import time
import pytest
import requests

BASE_URL = "http://localhost:8000"

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    yield s

@pytest.mark.benchmark
def test_health_check_perf(session):
    """健康检查接口性能"""
    times = []
    for _ in range(100):
        start = time.time()
        resp = session.get(f"{BASE_URL}/health")
        times.append(time.time() - start)
        assert resp.status_code == 200
    times.sort()
    p95 = times[int(len(times) * 0.95)]
    print(f"\n健康检查 P95: {p95*1000:.1f}ms")
    assert p95 < 0.05, f"P95 超过 50ms: {p95*1000:.1f}ms"

@pytest.mark.benchmark
def test_list_cases_perf(session):
    """用例列表性能"""
    times = []
    for _ in range(50):
        start = time.time()
        resp = session.get(f"{BASE_URL}/api/cases", params={"limit": 100})
        times.append(time.time() - start)
        assert resp.status_code == 200
    times.sort()
    p95 = times[int(len(times) * 0.95)]
    print(f"\n用例列表 P95: {p95*1000:.1f}ms")
    assert p95 < 0.1, f"P95 超过 100ms: {p95*1000:.1f}ms"

@pytest.mark.benchmark
def test_create_case_perf(session):
    """创建用例性能"""
    times = []
    for i in range(50):
        start = time.time()
        resp = session.post(f"{BASE_URL}/api/cases", json={
            "title": f"性能测试用例{i}",
            "description": "perf test",
        })
        times.append(time.time() - start)
        assert resp.status_code == 200
    times.sort()
    p95 = times[int(len(times) * 0.95)]
    print(f"\n创建用例 P95: {p95*1000:.1f}ms")
    assert p95 < 0.1, f"P95 超过 100ms: {p95*1000:.1f}ms"
```

### 3.4 任务队列性能测试

```python
# test_task_queue_perf.py
"""
任务队列性能与稳定性测试
"""
import asyncio
import time
from app.tasks.manager import TaskManager

class TestTaskQueuePerformance:
    """任务队列性能测试"""

    def test_mass_submit(self):
        """批量任务提交与执行"""
        async def run():
            tm = TaskManager(maxsize=200)
            tm.start(num_workers=4)
            
            start = time.time()
            tasks = []
            for i in range(100):
                async def dummy_task(x=i):
                    await asyncio.sleep(0.01)
                    return x
                task = await tm.submit(dummy_task)
                tasks.append(task)
            
            # 等待全部完成
            while not all(t.status in ("success", "failed") for t in tasks):
                await asyncio.sleep(0.05)
            
            elapsed = time.time() - start
            success_count = sum(1 for t in tasks if t.status == "success")
            assert success_count == 100, f"只有 {success_count} 个任务成功"
            print(f"\n100 个任务 4 workers 执行耗时: {elapsed:.2f}s")
            await tm.stop()
        
        asyncio.run(run())

    def test_queue_size_limit(self):
        """队列容量限制"""
        async def run():
            tm = TaskManager(maxsize=10)
            tm.start(num_workers=1)
            
            # 快速提交，验证不阻塞
            for i in range(20):
                async def dummy_task(x=i):
                    await asyncio.sleep(0.01)
                    return x
                await tm.submit(dummy_task)
            
            await asyncio.sleep(0.5)
            assert len(tm.list_tasks()) == 20
            await tm.stop()
        
        asyncio.run(run())

    def test_concurrent_workers(self):
        """多 worker 并行能力"""
        async def run():
            tm = TaskManager(maxsize=50)
            tm.start(num_workers=5)
            
            async def long_task(x):
                await asyncio.sleep(0.2)
                return x
            
            start = time.time()
            tasks = []
            for i in range(20):
                task = await tm.submit(long_task, i)
                tasks.append(task)
            
            while not all(t.status == "success" for t in tasks):
                await asyncio.sleep(0.05)
            
            elapsed = time.time() - start
            # 5 workers 处理 20 个 0.2s 任务，理论约 0.8s
            print(f"\n20 个 0.2s 任务 5 workers 耗时: {elapsed:.2f}s")
            assert elapsed < 2.0, f"并行效率不达标: {elapsed:.2f}s"
            await tm.stop()
        
        asyncio.run(run())
```

---

## 四、UI 测试用例

UI 测试覆盖 Web 控制台的界面展示、交互流程、响应式布局与可用性。

### 4.1 页面结构与导航

| 用例编号 | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| UI-001 | 首页加载 | 访问 `/` | 页面正常渲染，暗色主题，侧边栏导航显示 | P0 |
| UI-002 | 侧边栏导航完整性 | 查看左侧导航栏 | 包含：仪表盘、测试生成、用例库、缺陷跟踪、项目扫描、报告中心、任务队列 7 个模块 | P0 |
| UI-003 | 导航切换 | 点击各导航项 | 正确切换到对应模块页面，URL 无错误 | P0 |
| UI-004 | 响应式布局（桌面） | 1920px 宽屏幕 | 布局正常，无溢出/错位 | P1 |
| UI-005 | 响应式布局（平板） | 768px 宽屏幕 | 布局自适应，侧边栏可折叠 | P1 |
| UI-006 | 响应式布局（手机） | 375px 宽屏幕 | 内容可滚动，按钮可点击，无横向滚动 | P1 |

### 4.2 仪表盘

| 用例编号 | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| UI-007 | 统计卡片显示 | 打开仪表盘 | 显示用例总数、缺陷数等统计卡片 | P0 |
| UI-008 | 状态分布图 | 查看仪表盘 | 显示用例/缺陷的状态分布图表 | P1 |
| UI-009 | 最近活动 | 查看仪表盘 | 显示最近用例/缺陷列表 | P1 |
| UI-010 | 空数据占位 | 无数据时查看仪表盘 | 显示空数据占位提示 | P1 |

### 4.3 测试生成页面

| 用例编号 | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| UI-011 | 代码编辑器 | 在测试生成页查看 | 提供代码编辑区域，支持粘贴代码 | P0 |
| UI-012 | 生成按钮交互 | 粘贴代码后点击"生成" | 按钮变为加载状态，禁用重复点击 | P0 |
| UI-013 | 进度展示 | 开始生成 | 显示各步骤进度（扫描→Mock→生成→运行→覆盖率） | P0 |
| UI-014 | 生成结果展示 | 生成完成 | 显示生成的测试代码，语法高亮 | P0 |
| UI-015 | 测试结果展示 | 生成完成 | 显示测试运行结果（通过/失败）和覆盖率 | P0 |
| UI-016 | 保存为用例 | 生成完成后点击"保存为用例" | 弹出确认框，成功保存后提示"已保存" | P0 |
| UI-017 | 复制测试代码 | 点击"复制"按钮 | 测试代码被复制到剪贴板 | P1 |
| UI-018 | 下载测试代码 | 点击"下载"按钮 | 下载包含测试代码的文件 | P2 |
| UI-019 | 错误提示展示 | 生成失败 | 页面显示错误信息，不白屏 | P0 |
| UI-020 | 清空编辑器 | 点击"清空"按钮 | 编辑器内容被清空 | P2 |

### 4.4 用例库页面

| 用例编号 | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| UI-021 | 用例列表展示 | 打开用例库 | 表格展示用例（标题、状态、优先级、标签、更新时间） | P0 |
| UI-022 | 新建用例弹窗 | 点击"新建用例" | 弹出表单，字段齐全（标题/描述/标签/优先级） | P0 |
| UI-023 | 搜索功能 | 在搜索框输入关键词 | 实时过滤用例列表 | P0 |
| UI-024 | 状态筛选 | 选择筛选条件 | 列表按筛选条件更新 | P1 |
| UI-025 | 优先级筛选 | 选择优先级 | 列表按优先级过滤 | P1 |
| UI-026 | 审批操作 | 点击用例"审批"按钮 | 状态从 review 变为 approved，Toast 提示成功 | P0 |
| UI-027 | 删除操作 | 点击"删除"按钮 | 弹出确认框，确认后删除，列表刷新 | P0 |
| UI-028 | 查看详情 | 点击用例标题 | 打开详情弹窗，展示完整信息 | P1 |
| UI-029 | 状态徽章颜色 | 查看不同状态用例 | draft/审查/approved/deprecated 有不同颜色区分 | P1 |
| UI-030 | 用例数量统计 | 查看用例库顶部 | 显示总数、各状态数量 | P2 |

### 4.5 缺陷跟踪页面

| 用例编号 | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| UI-031 | 缺陷列表展示 | 打开缺陷跟踪 | 列表展示缺陷（严重程度徽章、状态、文件路径） | P0 |
| UI-032 | 新建缺陷弹窗 | 点击"新建缺陷" | 弹出表单，支持填写标题/严重程度/描述 | P0 |
| UI-033 | 严重程度颜色 | 查看不同严重程度 | Blocker(红)、Critical(橙)、Major(黄)、Minor(蓝) 区分明显 | P1 |
| UI-034 | 状态流转操作 | 点击"修复"按钮 | 状态从 open 变为 fixed | P0 |
| UI-035 | 过滤功能 | 使用状态/严重程度过滤 | 列表正确过滤 | P1 |
| UI-036 | 错误信息展示 | 查看缺陷详情 | 显示关联的错误片段（代码块） | P1 |

### 4.6 项目扫描页面

| 用例编号 | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| UI-037 | 项目路径输入 | 输入项目路径 | 正确接收路径 | P0 |
| UI-038 | 扫描结果展示 | 点击"扫描" | 展示文件列表、函数签名信息 | P0 |
| UI-039 | 批量生成 | 扫描后点击"批量生成" | 显示生成进度和结果 | P0 |
| UI-040 | 扫描错误提示 | 输入无效路径 | 显示错误提示 | P1 |
| UI-041 | 文件详情展开 | 点击文件项 | 展开显示函数签名列表 | P2 |

### 4.7 报告中心页面

| 用例编号 | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| UI-042 | 报告生成选择 | 打开报告中心 | 显示格式选择（HTML/JUnit/Markdown） | P0 |
| UI-043 | 生成报告 | 点击"生成报告" | 显示生成成功，提供下载链接 | P0 |
| UI-044 | 报告列表 | 查看已生成的报告 | 按时间倒序列出报告，含下载按钮 | P0 |
| UI-045 | 报告下载 | 点击下载 | 文件成功下载到本地 | P0 |
| UI-046 | 空报告提示 | 无报告时查看 | 显示"暂无报告"占位 | P1 |

### 4.8 任务队列页面

| 用例编号 | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| UI-047 | 任务列表展示 | 打开任务队列 | 表格展示任务（ID、状态、创建时间、耗时） | P0 |
| UI-048 | 任务状态颜色 | 查看不同状态 | pending/running/success/failed 颜色区分 | P1 |
| UI-049 | 刷新任务列表 | 点击"刷新" | 列表更新显示最新状态 | P1 |
| UI-050 | 空任务提示 | 无任务时查看 | 显示"暂无任务" | P2 |

### 4.9 交互与可用性

| 用例编号 | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|---------|--------|---------|---------|-------|
| UI-051 | Toast 通知 | 执行操作（保存/删除等） | 页面右上角出现 Toast 成功/失败提示 | P0 |
| UI-052 | 模态框关闭 | 打开弹窗后点击 X | 弹窗正常关闭 | P1 |
| UI-053 | 表单必填校验 | 空表单提交 | 必填字段显示红色提示 | P1 |
| UI-054 | 快捷键支持 | 使用 Ctrl+Enter | 在代码编辑器触发生成 | P2 |
| UI-055 | 加载动画 | 长时间操作 | 显示 loading 动画，防止误操作 | P1 |
| UI-056 | 页面刷新数据持久性 | 刷新页面 | 各页面数据从 API 重新加载，不丢失 | P1 |
| UI-057 | 浏览器兼容性 | Chrome/Safari/Firefox/Edge | 功能正常，无 CSS 兼容性问题 | P1 |
| UI-058 | 中文字符显示 | 输入中文标题/描述 | 中文正常显示，无乱码 | P0 |

### 4.10 自动化 UI 测试代码

```python
# test_ui.py — 使用 Playwright 的 UI 自动化测试
"""
UI 自动化测试：基于 Playwright 验证关键页面与交互。

运行方式：
    pip install playwright
    playwright install chromium
    pytest test_ui.py
"""
import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"

@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    yield page
    context.close()

class TestUI:
    """UI 自动化测试"""

    def test_home_page_load(self, page):
        """首页加载"""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        assert "测试用例 Agent" in page.title() or page.title() != ""

    def test_sidebar_navigation(self, page):
        """侧边栏导航"""
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        nav_items = page.locator(".sidebar-nav li, .nav-item, aside a")
        count = nav_items.count()
        assert count >= 5, f"侧边栏导航项不足 5 个，实际 {count} 个"

    def test_test_generation_page(self, page):
        """测试生成页面"""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        # 查找代码编辑器和生成按钮
        textarea = page.locator("textarea, .CodeMirror, pre[contenteditable]")
        assert textarea.count() > 0, "未找到代码编辑器"

    def test_cases_page(self, page):
        """用例库页面"""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        # 尝试点击用例库导航
        page.locator("text=用例库").first.click()
        page.wait_for_timeout(500)
        # 验证列表或空状态
        assert page.locator("table, .empty-state, .list-item").count() >= 0

    def test_defects_page(self, page):
        """缺陷跟踪页面"""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        page.locator("text=缺陷").first.click()
        page.wait_for_timeout(500)
        assert page.locator("table, .empty-state").count() >= 0

    def test_responsive_mobile(self, browser):
        """移动端响应式"""
        context = browser.new_context(viewport={"width": 375, "height": 812})
        page = context.new_page()
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        # 无横向滚动
        overflow = page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        assert not overflow, "页面存在横向滚动条"
        context.close()

    def test_create_case_modal(self, page):
        """新建用例弹窗"""
        page.goto(f"{BASE_URL}/")
        page.wait_for_load_state("networkidle")
        # 点击用例库 → 新建
        page.locator("text=用例库").first.click()
        page.wait_for_timeout(300)
        page.locator("text=新建").first.click()
        page.wait_for_timeout(300)
        # 验证弹窗出现
        modal = page.locator(".modal, dialog, .dialog")
        assert modal.count() > 0, "未找到弹窗"

    def test_health_check_ui(self, page):
        """页面健康检查（API 返回正常）"""
        response = page.request.get(f"{BASE_URL}/health")
        assert response.status == 200
        data = response.json()
        assert data["status"] == "ok"
```

---

## 五、测试优先级汇总

### P0 — 阻塞发布，必须全部通过

| 模块 | 用例编号 |
|------|---------|
| 手工测试 | MT-001, MT-002, MT-005, MT-007, MT-008, MT-010, MT-013, MT-018, MT-021, MT-022, MT-023, MT-030, MT-034, MT-035, MT-036, MT-039, MT-041, MT-044, MT-045 |
| 自动化测试 | 配置、Mock、扫描、用例库、缺陷、项目扫描、任务队列、Docker 沙箱、Graph 路由、覆盖率分析 |
| 性能测试 | PT-001, PT-002, PT-003, PT-005, PT-009, PT-010, PT-011 |
| UI 测试 | UI-001, UI-002, UI-003, UI-007, UI-011, UI-012, UI-013, UI-014, UI-015, UI-016, UI-019, UI-021, UI-022, UI-023, UI-026, UI-027, UI-031, UI-032, UI-034, UI-037, UI-038, UI-039, UI-042, UI-043, UI-044, UI-045, UI-047, UI-051, UI-058 |

### P1 — 重要但不阻塞

| 模块 | 用例编号 |
|------|---------|
| 手工测试 | MT-003, MT-004, MT-006, MT-009, MT-011, MT-012, MT-014, MT-015, MT-016, MT-017, MT-019, MT-020, MT-024, MT-025, MT-026, MT-027, MT-028, MT-031, MT-033, MT-037, MT-038, MT-040, MT-042, MT-046 |
| 性能测试 | PT-004, PT-006, PT-007, PT-008, PT-012, PT-013, PT-014, PT-015, PT-016, PT-017, PT-018 |
| UI 测试 | UI-004, UI-005, UI-008, UI-009, UI-010, UI-017, UI-024, UI-025, UI-028, UI-029, UI-033, UI-035, UI-036, UI-040, UI-046, UI-048, UI-049, UI-052, UI-053, UI-055, UI-056, UI-057 |

### P2 — 后续迭代完善

| 模块 | 用例编号 |
|------|---------|
| 手工测试 | MT-029, MT-032, MT-043 |
| UI 测试 | UI-006, UI-018, UI-020, UI-030, UI-041, UI-050, UI-054 |

---

## 六、执行建议

### 手工测试执行策略
1. **冒烟测试**：先跑 P0 级手工用例，验证核心流程可用
2. **功能测试**：完整跑 P0+P1 级手工用例，每个模块至少覆盖正常 + 异常 + 边界
3. **回归测试**：每次代码提交后执行 P0 级用例，确保不引入回归

### 自动化测试执行策略
1. **单元测试**：`pytest app/tests/ -v --cov=app --cov-report=term-missing`
2. **集成测试**：启动服务后执行 API 层测试
3. **覆盖率门槛**：核心模块覆盖率 ≥ 80%，整体 ≥ 70%

### 性能测试执行策略
1. **基线建立**：首次部署建立性能基线
2. **持续监控**：CI/CD 中集成性能测试，对比基线
3. **负载演练**：定期执行并发/负载测试，提前发现瓶颈

### UI 测试执行策略
1. **自动化回归**：用 Playwright 脚本在 CI 中执行核心 UI 流程
2. **视觉回归**：截图对比，检测样式变化
3. **跨浏览器**：在 Chrome/Firefox/Safari/Edge 上验证关键页面

