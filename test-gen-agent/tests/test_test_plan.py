"""测试计划模块单元测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
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


class TestTestPlan:
    """测试计划 CRUD 测试。"""

    def test_create_plan(self, client):
        """创建测试计划。"""
        r = client.post("/test-plan/add", json={
            "name": "单元测试计划",
            "description": "计划描述",
            "priority": "P1",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "单元测试计划"
        assert data["data"]["priority"] == "P1"

    def test_plan_page(self, client):
        """测试计划分页。"""
        # 先创建
        client.post("/test-plan/add", json={"name": "分页测试计划"})
        r = client.post("/test-plan/page", json={"pageSize": 10, "current": 1})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["total"] >= 1
        assert len(data["data"]["list"]) >= 1

    def test_plan_detail(self, client):
        """获取计划详情。"""
        r = client.post("/test-plan/add", json={"name": "详情测试计划"})
        plan_id = r.json()["data"]["id"]
        r = client.get(f"/test-plan/{plan_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["id"] == plan_id

    def test_plan_update(self, client):
        """更新测试计划。"""
        r = client.post("/test-plan/add", json={"name": "更新测试计划"})
        plan_id = r.json()["data"]["id"]
        r = client.post("/test-plan/update", json={"id": plan_id, "name": "更新后的计划", "status": "running"})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "更新后的计划"

    def test_plan_delete(self, client):
        """删除测试计划。"""
        r = client.post("/test-plan/add", json={"name": "删除测试计划"})
        plan_id = r.json()["data"]["id"]
        r = client.post("/test-plan/delete", json={"id": plan_id})
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_plan_module_tree(self, client):
        """获取模块树。"""
        r = client.get("/test-plan/module/tree")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert len(data["data"]) >= 1

    def test_plan_module_add(self, client):
        """添加模块。"""
        r = client.post("/test-plan/module/add", json={"name": "回归测试"})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "回归测试"

    def test_plan_association(self, client):
        """关联用例。"""
        r = client.post("/test-plan/add", json={"name": "关联测试计划"})
        plan_id = r.json()["data"]["id"]
        r = client.post("/test-plan/association/add", json={
            "planId": plan_id,
            "caseIds": ["case-1", "case-2"],
            "caseType": "functional",
        })
        assert r.status_code == 200
        assert r.json()["code"] == 200

        r = client.post("/test-plan/association/page", json={"planId": plan_id})
        assert r.status_code == 200
        data = r.json()
        assert data["data"]["total"] == 2

    def test_plan_statistics(self, client):
        """获取计划统计。"""
        r = client.post("/test-plan/add", json={"name": "统计测试计划"})
        plan_id = r.json()["data"]["id"]
        r = client.get(f"/test-plan/statistics/{plan_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert "total" in data["data"]
        assert "passRate" in data["data"]


class TestDashboard:
    """工作台测试。"""

    def test_dashboard_home(self, client):
        """工作台首页。"""
        r = client.get("/dashboard/home")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert "caseCount" in data["data"]
        assert "bugCount" in data["data"]

    def test_dashboard_overview(self, client):
        """工作台总览。"""
        r = client.get("/dashboard/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert "caseStatus" in data["data"]
        assert "defectSeverity" in data["data"]


class TestSystemSettings:
    """系统设置测试。"""

    def test_user_group_list(self, client):
        """用户组列表。"""
        r = client.get("/system/user-group/list")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert len(data["data"]) >= 2

    def test_organization_list(self, client):
        """组织列表。"""
        r = client.get("/system/organization/list")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert len(data["data"]) >= 1

    def test_organization_add(self, client):
        """添加组织。"""
        r = client.post("/system/organization/add", json={"name": "测试组织"})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "测试组织"
