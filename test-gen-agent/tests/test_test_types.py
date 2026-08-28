"""
test_test_types.py — 测试类型注册表与 Prompt 模板测试

覆盖:
  - 功能: 测试类型注册表完整性
  - 功能: 各类型 Prompt 模板包含特定内容
  - 边界: 未知类型回退到功能测试
  - 功能: API 端点可列出所有测试类型
"""
import pytest

from app.generators.test_types import (
    TestType,
    TEST_TYPES,
    get_test_type_info,
    get_default_test_type,
    is_valid_test_type,
    list_test_types,
)
from app.generators.prompts import get_prompt


class TestTestTypes:
    """测试类型注册表测试"""

    def test_all_seven_types_present(self):
        """功能: 应包含 7 种行业标准测试类型"""
        assert len(TEST_TYPES) == 7
        assert set(TEST_TYPES.keys()) == {
            "functional", "api", "ui", "performance",
            "security", "compatibility", "reliability",
        }

    def test_type_labels(self):
        """功能: 各类型有正确的中文标签"""
        expected = {
            "functional": "功能测试",
            "api": "接口测试",
            "ui": "UI 测试",
            "performance": "性能测试",
            "security": "安全测试",
            "compatibility": "兼容性测试",
            "reliability": "可靠性测试",
        }
        for key, label in expected.items():
            assert get_test_type_info(key)["label"] == label

    def test_default_is_functional(self):
        """功能: 默认测试类型应为 functional"""
        assert get_default_test_type() == "functional"

    def test_is_valid_test_type(self):
        """功能: 校验合法/非法测试类型"""
        assert is_valid_test_type("api") is True
        assert is_valid_test_type("functional") is True
        assert is_valid_test_type("unknown") is False
        assert is_valid_test_type("") is False

    def test_unknown_type_falls_back(self):
        """边界: 未知类型应回退到功能测试"""
        info = get_test_type_info("not_a_real_type")
        assert info["key"] == "functional"

    def test_list_test_types_has_seven(self):
        """功能: list_test_types 返回全部类型"""
        types = list_test_types()
        assert len(types) == 7
        keys = [t["key"] for t in types]
        assert "functional" in keys
        assert "reliability" in keys


class TestPrompts:
    """Prompt 模板测试"""

    def test_all_prompts_have_base_requirements(self):
        """功能: 所有 Prompt 包含通用要求"""
        for test_type in TEST_TYPES:
            prompt = get_prompt(test_type)
            assert "测试用例" in prompt
            assert "{signatures}" in prompt
            assert "{mocks}" in prompt
            assert "JSON" in prompt
            assert "test_steps" in prompt
            assert "expected" in prompt

    def test_functional_prompt_has_type_specific(self):
        """功能: 功能测试 Prompt 包含对应测试重点"""
        prompt = get_prompt("functional")
        assert "功能测试" in prompt
        assert "正常流程" in prompt
        assert "边界条件" in prompt
        assert "异常处理" in prompt

    def test_api_prompt_has_type_specific(self):
        """功能: 接口测试 Prompt 包含对应测试重点"""
        prompt = get_prompt("api")
        assert "接口测试" in prompt
        assert "请求契约" in prompt
        assert "响应契约" in prompt
        assert "状态码" in prompt

    def test_ui_prompt_has_type_specific(self):
        """功能: UI 测试 Prompt 包含对应测试重点"""
        prompt = get_prompt("ui")
        assert "UI 测试" in prompt
        assert "元素定位" in prompt
        assert "交互流程" in prompt

    def test_performance_prompt_has_type_specific(self):
        """功能: 性能测试 Prompt 包含对应测试重点"""
        prompt = get_prompt("performance")
        assert "性能测试" in prompt
        assert "响应时间" in prompt
        assert "吞吐量" in prompt

    def test_security_prompt_has_type_specific(self):
        """功能: 安全测试 Prompt 包含对应测试重点"""
        prompt = get_prompt("security")
        assert "安全测试" in prompt
        assert "SQL 注入" in prompt
        assert "越权" in prompt

    def test_compatibility_prompt_has_type_specific(self):
        """功能: 兼容性测试 Prompt 包含对应测试重点"""
        prompt = get_prompt("compatibility")
        assert "兼容性测试" in prompt
        assert "版本兼容" in prompt
        assert "平台兼容" in prompt

    def test_reliability_prompt_has_type_specific(self):
        """功能: 可靠性测试 Prompt 包含对应测试重点"""
        prompt = get_prompt("reliability")
        assert "可靠性测试" in prompt
        assert "幂等性" in prompt
        assert "容错性" in prompt

    def test_unknown_prompt_falls_back(self):
        """边界: 未知类型 Prompt 回退到功能测试"""
        prompt = get_prompt("not_real")
        assert "功能测试" in prompt

    def test_script_generation_prompt(self):
        """功能: 脚本生成 Prompt 包含结构化用例输入"""
        from app.generators.prompts import get_script_generation_prompt
        prompt = get_script_generation_prompt()
        assert "pytest" in prompt
        assert "{structured_cases}" in prompt
        assert "{signatures}" in prompt
        assert "{mocks}" in prompt


class TestTestTypesAPI:
    """API 端点测试"""

    @pytest.fixture(scope="module")
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        c = TestClient(app)
        # 登录获取认证令牌
        r = c.post("/login", json={"username": "admin", "password": "admin123"})
        if r.status_code == 200:
            session = r.json()["data"]
            c.headers.update({
                "X-AUTH-TOKEN": session["sessionId"],
                "CSRF-TOKEN": session["csrfToken"],
            })
        return c

    def test_list_test_types_endpoint(self, client):
        """功能: GET /api/test-types 返回所有测试类型"""
        resp = client.get("/api/test-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "types" in data
        types = data["types"]
        assert len(types) == 7
        keys = [t["key"] for t in types]
        assert set(keys) == {
            "functional", "api", "ui", "performance",
            "security", "compatibility", "reliability",
        }

    def test_test_types_have_labels_and_icons(self, client):
        """功能: 每个测试类型包含 label 和 icon"""
        resp = client.get("/api/test-types")
        data = resp.json()
        for t in data["types"]:
            assert t.get("label")
            assert t.get("icon")
            assert t.get("description")


class TestCaseTestType:
    """用例库 test_type 集成测试"""

    @pytest.fixture()
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        c = TestClient(app)
        # 登录获取认证令牌
        r = c.post("/login", json={"username": "admin", "password": "admin123"})
        if r.status_code == 200:
            session = r.json()["data"]
            c.headers.update({
                "X-AUTH-TOKEN": session["sessionId"],
                "CSRF-TOKEN": session["csrfToken"],
            })
        return c

    def test_create_case_with_test_type(self, client):
        """功能: 创建用例时可指定 test_type"""
        resp = client.post("/api/cases", json={
            "title": "test_type_api_case",
            "source_code": "def add(a, b): return a + b",
            "test_code": "def test_add(): assert add(1, 2) == 3",
            "file_path": "test_type_demo.py",
            "status": "review",
            "priority": "P2",
            "test_type": "api",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("test_type") == "api"

        # 清理
        client.delete(f"/api/cases/{data['id']}")

    def test_filter_cases_by_test_type(self, client):
        """功能: 按测试类型筛选用例"""
        # 创建一个 API 类型用例
        resp = client.post("/api/cases", json={
            "title": "filter_api_case",
            "source_code": "def foo(): pass",
            "file_path": "filter_demo.py",
            "status": "draft",
            "test_type": "api",
        })
        assert resp.status_code == 200
        case_id = resp.json()["id"]

        try:
            # 按 api 类型筛选
            resp = client.get("/api/cases?test_type=api")
            assert resp.status_code == 200
            cases = resp.json()["cases"]
            assert any(c["id"] == case_id for c in cases)

            # 按 functional 类型筛选（不应包含 api 类型用例）
            resp = client.get("/api/cases?test_type=functional")
            assert resp.status_code == 200
            cases = resp.json()["cases"]
            assert not any(c["id"] == case_id for c in cases)
        finally:
            client.delete(f"/api/cases/{case_id}")

    def test_case_test_type_default(self, client):
        """功能: 未指定 test_type 时默认为 functional"""
        resp = client.post("/api/cases", json={
            "title": "default_type_case",
            "source_code": "def bar(): pass",
            "file_path": "default_demo.py",
            "status": "draft",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("test_type") == "functional"

        # 清理
        client.delete(f"/api/cases/{data['id']}")
