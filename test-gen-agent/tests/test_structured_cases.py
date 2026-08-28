"""
test_structured_cases.py — 结构化测试用例（方案A）测试

覆盖:
  - 功能: JSON 数组提取函数
  - 功能: 结构化用例数据模型
  - 功能: API 支持 structured_cases 字段
  - 功能: 用例库结构化字段存取
"""
import json
import pytest

from app.generators.test_generator import _extract_json_array, _extract_code, _parse_test_type


class TestJsonArrayExtraction:
    """JSON 数组提取测试"""

    def test_direct_json(self):
        """功能: 直接解析纯 JSON 数组"""
        text = '[{"title": "test", "test_steps": []}]'
        result = _extract_json_array(text)
        assert isinstance(result, list)
        assert result[0]["title"] == "test"

    def test_markdown_fenced_json(self):
        """功能: 解析 markdown 代码块包裹的 JSON"""
        text = '```json\n[{"title": "test", "priority": "P1"}]\n```'
        result = _extract_json_array(text)
        assert isinstance(result, list)
        assert result[0]["priority"] == "P1"

    def test_embedded_json_in_text(self):
        """功能: 从文本中提取 JSON 数组"""
        text = '这里是说明\n[{"title": "test"}]\n请查看'
        result = _extract_json_array(text)
        assert isinstance(result, list)
        assert result[0]["title"] == "test"

    def test_invalid_json_raises(self):
        """边界: 无法解析 JSON 时抛出 ValueError"""
        with pytest.raises(ValueError):
            _extract_json_array("这不是 JSON")


class TestCodeExtraction:
    """代码提取测试"""

    def test_python_fenced_code(self):
        """功能: 提取 python 代码块"""
        text = '```python\ndef test_x():\n    pass\n```'
        result = _extract_code(text)
        assert "def test_x()" in result

    def test_plain_text_returns_as_is(self):
        """边界: 无代码块时原样返回"""
        text = "def test_x():\n    pass"
        result = _extract_code(text)
        assert result == text


class TestParseTestType:
    """测试类型解析测试"""

    def test_valid_type_passthrough(self):
        """功能: 合法类型原样返回"""
        assert _parse_test_type("api") == "api"
        assert _parse_test_type("security") == "security"

    def test_invalid_type_falls_back(self):
        """边界: 非法类型回退到 functional"""
        assert _parse_test_type("invalid") == "functional"


class TestStructuredCaseAPI:
    """结构化用例 API 测试"""

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

    def test_create_case_with_structured_cases(self, client):
        """功能: 创建用例时可指定 structured_cases"""
        structured = [
            {
                "title": "测试用例1",
                "description": "测试功能",
                "preconditions": ["系统可用"],
                "test_steps": [
                    {"step": "输入参数", "data": "1,2", "expected": "返回3"}
                ],
                "test_data": {"a": 1, "b": 2},
                "priority": "P1",
                "risk_level": "low",
                "execution_type": "manual"
            }
        ]
        resp = client.post("/api/cases", json={
            "title": "structured_case_test",
            "source_code": "def add(a, b): return a + b",
            "test_code": "def test_add(): assert add(1, 2) == 3",
            "file_path": "structured_demo.py",
            "status": "review",
            "test_type": "functional",
            "structured_cases": structured,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("test_type") == "functional"
        assert data.get("structured_cases")
        assert data["structured_cases"][0]["title"] == "测试用例1"
        assert data["structured_cases"][0]["test_steps"][0]["expected"] == "返回3"

        # 清理
        client.delete(f"/api/cases/{data['id']}")

    def test_get_case_returns_structured_cases(self, client):
        """功能: 获取用例时返回 structured_cases"""
        structured = [{
            "title": "用例",
            "test_steps": [{"step": "操作", "expected": "结果"}]
        }]
        resp = client.post("/api/cases", json={
            "title": "get_structured_test",
            "source_code": "def x(): pass",
            "file_path": "get_structured.py",
            "status": "draft",
            "structured_cases": structured,
        })
        assert resp.status_code == 200
        case_id = resp.json()["id"]

        try:
            resp = client.get(f"/api/cases/{case_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["structured_cases"]) == 1
            assert data["structured_cases"][0]["title"] == "用例"
        finally:
            client.delete(f"/api/cases/{case_id}")

    def test_update_case_structured_cases(self, client):
        """功能: 更新用例的 structured_cases"""
        resp = client.post("/api/cases", json={
            "title": "update_structured_test",
            "source_code": "def y(): pass",
            "file_path": "update_structured.py",
            "status": "draft",
        })
        assert resp.status_code == 200
        case_id = resp.json()["id"]

        try:
            new_structured = [{
                "title": "更新后的用例",
                "preconditions": ["新前置"],
                "test_steps": [{"step": "新步骤", "expected": "新预期"}]
            }]
            resp = client.put(f"/api/cases/{case_id}", json={
                "structured_cases": new_structured,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["structured_cases"][0]["title"] == "更新后的用例"
            assert data["structured_cases"][0]["preconditions"] == ["新前置"]
        finally:
            client.delete(f"/api/cases/{case_id}")

    def test_generate_script_flag_in_request(self):
        """功能: ChatRequest 支持 generate_script 字段"""
        from app.main import ChatRequest
        req = ChatRequest(source_code="def a(): pass", generate_script=False)
        assert req.generate_script is False

        req2 = ChatRequest(source_code="def b(): pass")
        assert req2.generate_script is True
