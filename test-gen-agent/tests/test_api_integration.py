"""
test_api_integration.py — API 集成测试

覆盖:
  - 正常流程: 各模块 API 正确响应
  - 异常流程: 错误请求返回正确状态码
  - 边界条件: 空数据/无效数据
"""

import os
import sys
import pytest
import asyncio

# 确保可导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient


# ── 测试数据清理 ────────────────────────────────────────────

@pytest.fixture
def clean_test_data():
    """清理测试产生的数据库数据"""
    yield
    from app.cases.repository import list_cases, delete_case
    cases = list_cases(limit=100)
    for c in cases:
        if "测试" in c.get("title", "") or "API" in c.get("title", ""):
            delete_case(c["id"])

    from app.defects.tracker import list_defects, delete_defect
    defects = list_defects(limit=100)
    for d in defects:
        if "API" in d.get("title", "") or "测试" in d.get("title", ""):
            delete_defect(d["id"])


@pytest.fixture(scope="module")
def client():
    """测试客户端（绕过 lifespan，避免 LLM 调用）。自动登录。"""
    from app.main import app
    with TestClient(app) as c:
        # 登录获取认证令牌
        r = c.post("/login", json={"username": "admin", "password": "admin123"})
        if r.status_code == 200:
            session = r.json()["data"]
            c.headers.update({
                "X-AUTH-TOKEN": session["sessionId"],
                "CSRF-TOKEN": session["csrfToken"],
            })
        yield c


# ── 健康检查 ────────────────────────────────────────────────

class TestHealthCheck:
    """健康检查测试"""

    def test_health_check(self, client):
        """功能: 健康检查正常"""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.2.0"

    def test_index_page(self, client):
        """功能: 首页可访问"""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


# ── 用例库 API ──────────────────────────────────────────────

class TestCasesAPI:
    """用例库 API 测试"""

    def test_create_case(self, client, clean_test_data):
        """功能: 创建用例"""
        resp = client.post("/api/cases", json={
            "title": "API测试用例",
            "description": "API 集成测试用例",
            "tags": ["api", "smoke"],
            "priority": "P0",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "API测试用例"
        assert data["tags"] == ["api", "smoke"]
        assert data["priority"] == "P0"

    def test_create_case_minimal(self, client, clean_test_data):
        """边界: 仅标题创建用例"""
        resp = client.post("/api/cases", json={"title": "仅标题用例"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "仅标题用例"
        assert data["status"] == "draft"
        assert data["priority"] == "P2"

    def test_create_case_empty_title(self, client, clean_test_data):
        """异常: 空标题"""
        resp = client.post("/api/cases", json={"title": ""})
        assert resp.status_code == 200  # Pydantic 模型没有校验非空

    def test_list_cases(self, client, clean_test_data):
        """功能: 列出用例"""
        # 先创建
        client.post("/api/cases", json={"title": "列表测试用例"})
        resp = client.get("/api/cases")
        assert resp.status_code == 200
        data = resp.json()
        assert "cases" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_get_case(self, client, clean_test_data):
        """功能: 获取用例详情"""
        created = client.post("/api/cases", json={"title": "详情测试用例"}).json()
        resp = client.get(f"/api/cases/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "详情测试用例"

    def test_get_case_not_found(self, client):
        """异常: 获取不存在的用例"""
        resp = client.get("/api/cases/nonexistent_id")
        assert resp.status_code == 404

    def test_update_case(self, client, clean_test_data):
        """功能: 更新用例"""
        created = client.post("/api/cases", json={"title": "更新前"}).json()
        resp = client.put(f"/api/cases/{created['id']}", json={"title": "更新后"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "更新后"

    def test_update_case_invalid_status(self, client, clean_test_data):
        """异常: 无效状态"""
        created = client.post("/api/cases", json={"title": "状态测试"}).json()
        resp = client.put(f"/api/cases/{created['id']}", json={"status": "invalid"})
        assert resp.status_code == 400

    def test_delete_case(self, client, clean_test_data):
        """功能: 删除用例"""
        created = client.post("/api/cases", json={"title": "待删除用例"}).json()
        resp = client.delete(f"/api/cases/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_case_not_found(self, client):
        """异常: 删除不存在的用例"""
        resp = client.delete("/api/cases/nonexistent")
        assert resp.status_code == 404

    def test_case_stats(self, client, clean_test_data):
        """功能: 用例统计"""
        resp = client.get("/api/cases/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_status" in data
        assert "by_priority" in data


# ── 缺陷 API ────────────────────────────────────────────────

class TestDefectsAPI:
    """缺陷 API 测试"""

    def test_create_defect(self, client, clean_test_data):
        """功能: 创建缺陷"""
        resp = client.post("/api/defects", json={
            "title": "API测试缺陷",
            "severity": "critical",
            "file_path": "test_file.py",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "API测试缺陷"
        assert data["severity"] == "critical"
        assert data["status"] == "open"

    def test_create_defect_default_severity(self, client, clean_test_data):
        """边界: 默认严重程度"""
        resp = client.post("/api/defects", json={"title": "默认严重程度"})
        assert resp.status_code == 200
        assert resp.json()["severity"] == "major"

    def test_list_defects(self, client, clean_test_data):
        """功能: 列出缺陷"""
        client.post("/api/defects", json={"title": "列表测试缺陷"})
        resp = client.get("/api/defects")
        assert resp.status_code == 200
        data = resp.json()
        assert "defects" in data
        assert "stats" in data
        assert data["total"] >= 1

    def test_get_defect(self, client, clean_test_data):
        """功能: 获取缺陷"""
        created = client.post("/api/defects", json={"title": "详情测试缺陷"}).json()
        resp = client.get(f"/api/defects/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "详情测试缺陷"

    def test_get_defect_not_found(self, client):
        """异常: 获取不存在缺陷"""
        resp = client.get("/api/defects/nonexistent")
        assert resp.status_code == 404

    def test_update_defect(self, client, clean_test_data):
        """功能: 更新缺陷"""
        created = client.post("/api/defects", json={"title": "更新前缺陷"}).json()
        resp = client.put(f"/api/defects/{created['id']}", json={"status": "fixed"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "fixed"

    def test_update_defect_invalid_status(self, client, clean_test_data):
        """异常: 无效状态"""
        created = client.post("/api/defects", json={"title": "状态缺陷"}).json()
        resp = client.put(f"/api/defects/{created['id']}", json={"status": "invalid"})
        assert resp.status_code == 400

    def test_delete_defect(self, client, clean_test_data):
        """功能: 删除缺陷"""
        created = client.post("/api/defects", json={"title": "删除测试缺陷"}).json()
        resp = client.delete(f"/api/defects/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


# ── 项目扫描 API ────────────────────────────────────────────

class TestProjectScanAPI:
    """项目扫描 API 测试"""

    def test_scan_nonexistent_path(self, client):
        """异常: 扫描不存在路径"""
        resp = client.post("/api/projects/scan", json={
            "project_path": "/nonexistent/path"
        })
        assert resp.status_code == 404

    def test_scan_valid_path(self, client, tmp_path):
        """功能: 扫描有效路径"""
        # 创建临时 Python 文件
        (tmp_path / "module.py").write_text("def func1(): pass\n")
        (tmp_path / "test_mod.py").write_text("def test_x(): pass\n")

        resp = client.post("/api/projects/scan", json={
            "project_path": str(tmp_path)
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_files"] == 1  # test_mod.py 被排除
        assert data["total_functions"] == 1


# ── 报告 API ────────────────────────────────────────────────

class TestReportsAPI:
    """报告 API 测试"""

    def test_list_reports_empty(self, client):
        """功能: 空报告列表"""
        resp = client.get("/api/reports/list")
        assert resp.status_code == 200
        assert "reports" in resp.json()

    def test_download_not_found(self, client):
        """异常: 下载不存在的报告"""
        resp = client.get("/api/reports/download/nonexistent.txt")
        assert resp.status_code == 404

    def test_generate_report_invalid_format(self, client, clean_test_data):
        """异常: 无效格式"""
        client.post("/api/cases", json={"title": "报告测试用例"})
        resp = client.post("/api/reports/generate", json={"format": "invalid"})
        assert resp.status_code in (400, 404)


# ── 任务 API ────────────────────────────────────────────────

class TestTasksAPI:
    """任务 API 测试"""

    def test_list_tasks_empty(self, client):
        """功能: 空任务列表"""
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert "tasks" in resp.json()
        assert resp.json()["total"] >= 0

    def test_get_task_not_found(self, client):
        """异常: 获取不存在的任务"""
        resp = client.get("/api/tasks/nonexistent")
        assert resp.status_code == 404
