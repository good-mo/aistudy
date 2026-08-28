"""API 适配层单元测试：验证 MeterSphere 前端路径映射到后端业务逻辑。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """创建测试客户端。自动登录。"""
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


class TestFunctionalCaseAdapter:
    """功能用例适配测试。"""

    def test_case_page(self, client):
        """用例分页列表。"""
        r = client.post("/functional/case/page", json={
            "keyword": "", "pageSize": 10, "current": 1,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert "list" in data["data"]
        assert "total" in data["data"]

    def test_case_add(self, client):
        """添加用例。"""
        r = client.post("/functional/case/add", json={
            "name": "API适配测试用例",
            "description": "测试用例描述",
            "priority": "P1",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"] == "API适配测试用例"

    def test_case_detail(self, client):
        """获取用例详情。"""
        # 先创建
        r = client.post("/functional/case/add", json={"name": "详情测试用例"})
        case_id = r.json()["data"]["id"]
        # 再查询
        r = client.get(f"/functional/case/detail/{case_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["id"] == case_id

    def test_case_module_tree(self, client):
        """获取模块树。"""
        r = client.get("/functional/case/module/tree")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert len(data["data"]) > 0

    def test_mind_case_list(self, client):
        """获取脑图数据。"""
        r = client.get("/functional/mind/case/list")
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestBugAdapter:
    """缺陷管理适配测试。"""

    def test_bug_page(self, client):
        """缺陷分页列表。"""
        r = client.post("/bug/page", json={"keyword": "", "pageSize": 10})
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_bug_add(self, client):
        """添加缺陷。"""
        r = client.post("/bug/add", json={
            "title": "适配测试缺陷",
            "description": "缺陷描述",
        })
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_bug_get(self, client):
        """获取缺陷详情。"""
        r = client.post("/bug/add", json={"title": "详情测试缺陷"})
        bug_id = r.json()["data"]["id"]
        r = client.get(f"/bug/get/{bug_id}")
        assert r.status_code == 200
        assert r.json()["data"]["id"] == bug_id

    def test_bug_delete(self, client):
        """删除缺陷。"""
        r = client.post("/bug/add", json={"title": "删除测试缺陷"})
        bug_id = r.json()["data"]["id"]
        r = client.get(f"/bug/delete/{bug_id}")
        assert r.status_code == 200


class TestAPIDefinitionAdapter:
    """接口定义适配测试。"""

    def test_definition_page(self, client):
        """接口定义分页。"""
        r = client.post("/api/definition/page", json={})
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_definition_module_tree(self, client):
        """接口定义模块树。"""
        r = client.get("/api/definition/module/tree")
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestScenarioAdapter:
    """场景适配测试。"""

    def test_scenario_page(self, client):
        """场景分页。"""
        r = client.post("/api/scenario/page", json={})
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_scenario_module_tree(self, client):
        """场景模块树。"""
        r = client.get("/api/scenario/module/tree")
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestAPICaseAdapter:
    """接口用例适配测试。"""

    def test_api_case_page(self, client):
        """接口用例分页。"""
        r = client.post("/api/case/page", json={})
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestDebugAdapter:
    """调试适配测试。"""

    def test_debug(self, client):
        """接口调试。"""
        r = client.post("/api/debug", json={"url": "/api/test"})
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_debug_module_tree(self, client):
        """调试模块树。"""
        r = client.get("/api/debug/module/tree")
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestDashboardAdapter:
    """工作台适配测试。"""

    def test_dashboard_home(self, client):
        """工作台首页。"""
        r = client.get("/dashboard/home")
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestTestPlanAdapter:
    """测试计划适配测试。"""

    def test_test_plan_page(self, client):
        """测试计划分页。"""
        r = client.post("/test-plan/page", json={})
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestAIAdapter:
    """AI 对话适配测试。"""

    def test_ai_conversation(self, client):
        """AI 对话。"""
        r = client.post("/ai/conversation", json={"prompt": "hello"})
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestBugRecycleAdapter:
    """缺陷回收站适配测试。"""

    def test_bug_trash_page(self, client):
        """缺陷回收站分页。"""
        r = client.post("/bug/trash/page", json={"pageSize": 10, "current": 1})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert "list" in data["data"]

    def test_bug_recover_delete(self, client):
        """缺陷删除入回收站与恢复。"""
        # 创建缺陷
        r = client.post("/bug/add", json={"title": "回收站测试缺陷", "severity": "major"})
        bug_id = r.json()["data"]["id"]
        # 删除入回收站
        r = client.post("/bug/delete", json={"id": bug_id})
        assert r.json()["code"] == 200
        # 回收站应包含
        r = client.post("/bug/trash/page", json={"pageSize": 100, "current": 1})
        ids = [i["id"] for i in r.json()["data"]["list"]]
        assert bug_id in ids
        # 恢复
        r = client.post("/bug/recover", json={"id": bug_id})
        assert r.json()["code"] == 200
        r = client.post("/bug/trash/page", json={"pageSize": 100, "current": 1})
        ids = [i["id"] for i in r.json()["data"]["list"]]
        assert bug_id not in ids

    def test_bug_custom_field_header(self, client):
        """缺陷表头自定义字段。"""
        r = client.get("/bug/header/custom-field/proj1")
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_bug_columns_option(self, client):
        """缺陷列配置。"""
        r = client.get("/bug/columns-option/proj1")
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestModuleApiAdapter:
    """接口模块 add/count 适配测试。"""

    def test_definition_module_add(self, client):
        r = client.post("/api/definition/module/add", json={"name": "模块X"})
        assert r.status_code == 200
        assert r.json()["code"] == 200
        assert r.json()["data"]["name"] == "模块X"

    def test_definition_module_count(self, client):
        r = client.get("/api/definition/module/count")
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_scenario_module_count(self, client):
        r = client.get("/api/scenario/module/count")
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_debug_module_add_count(self, client):
        r = client.post("/api/debug/module/add", json={"name": "调试模块"})
        assert r.json()["code"] == 200
        r = client.get("/api/debug/module/count")
        assert r.json()["code"] == 200

    def test_case_batch_delete_to_gc(self, client):
        r = client.post("/api/case/batch/delete-to-gc", json={"ids": []})
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestProjectEnvironmentAdapter:
    """项目环境管理适配测试。"""

    def test_environment_list(self, client):
        r = client.get("/project/environment/list")
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_environment_add_get_delete(self, client):
        r = client.post("/project/environment/add", json={"name": "环境A"})
        assert r.json()["code"] == 200
        env_id = r.json()["data"]["id"]
        r = client.get(f"/project/environment/get/{env_id}")
        assert r.json()["code"] == 200
        r = client.post(f"/project/environment/delete/{env_id}")
        assert r.json()["code"] == 200


class TestReportApiAdapter:
    """接口测试报告适配测试。"""

    def test_case_report_page(self, client):
        r = client.post("/api/report/case/page", json={"pageSize": 10, "current": 1})
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_scenario_report_page(self, client):
        r = client.post("/api/report/scenario/page", json={"pageSize": 10, "current": 1})
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_report_share(self, client):
        r = client.post("/api/report/share/gen", json={"id": "x"})
        assert r.json()["code"] == 200
        r = client.get("/api/report/share/get?shareId=x")
        assert r.json()["code"] == 200


class TestFunctionalCaseTrashAdapter:
    """功能用例回收站适配测试。"""

    def test_trash_page(self, client):
        r = client.post("/functional/case/trash/page", json={"pageSize": 10, "current": 1})
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_trash_module_count(self, client):
        r = client.get("/functional/case/trash/module/count")
        assert r.json()["code"] == 200
        r = client.get("/functional/case/module/count")
        assert r.json()["code"] == 200


class TestSystemUserAdapter:
    """系统用户 page/get 适配测试。"""

    def test_user_page(self, client):
        r = client.get("/system/user/page?current=1&pageSize=10")
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_user_get(self, client):
        r = client.get("/system/user/get?username=admin")
        assert r.status_code == 200


class TestProjectMemberAdapter:
    """项目成员适配测试。"""

    def test_member_add_list_remove(self, client):
        r = client.post("/project/member/add", json={
            "projectId": "proj_member", "memberIds": ["admin"], "role": "MEMBER",
        })
        assert r.json()["code"] == 200
        r = client.get("/project/member/list?projectId=proj_member")
        assert r.json()["code"] == 200
        r = client.post("/project/member/remove", json={
            "projectId": "proj_member", "userId": "admin",
        })
        assert r.json()["code"] == 200
