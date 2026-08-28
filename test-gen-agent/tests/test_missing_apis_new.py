"""测试新增的缺失 API 补充模块（app/adapters/missing_apis.py）。"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
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


def test_status_endpoint(client):
    r = client.get("/status")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "UP"


def test_api_report_case_page(client):
    r = client.post("/api/report/case/page", json={"current": 1, "pageSize": 10})
    assert r.status_code == 200
    assert r.json()["code"] == 200


def test_api_report_scenario_page(client):
    r = client.post("/api/report/scenario/page", json={"current": 1, "pageSize": 10})
    assert r.status_code == 200
    assert r.json()["code"] == 200


def test_api_definition_schedule_add(client):
    r = client.post("/api/definition/schedule/add", json={"name": "test"})
    assert r.status_code == 200
    assert "id" in r.json()["data"]


def test_api_doc_share_page(client):
    r = client.post("/api/doc/share/page", json={"current": 1, "pageSize": 10})
    assert r.status_code == 200


def test_project_environment_list(client):
    r = client.get("/project/environment/list")
    assert r.status_code == 200


def test_project_member_get_role_option(client):
    r = client.get("/project/member/get-role/option")
    assert r.status_code == 200


def test_project_version_list(client):
    r = client.get("/project/version/list")
    assert r.status_code == 200


def test_organization_project_page(client):
    r = client.post("/organization/project/page", json={"current": 1, "pageSize": 10})
    assert r.status_code == 200


def test_system_user_get_organization(client):
    r = client.get("/system/user/get/organization")
    assert r.status_code == 200


def test_user_role_project_list(client):
    r = client.get("/user/role/project/list")
    assert r.status_code == 200


def test_test_resource_pool_page(client):
    r = client.post("/test/resource/pool/page", json={"current": 1, "pageSize": 10})
    assert r.status_code == 200


def test_plugin_list(client):
    r = client.get("/plugin/list")
    assert r.status_code == 200


def test_service_integration_list(client):
    r = client.get("/service/integration/list")
    assert r.status_code == 200


def test_notification_count(client):
    r = client.get("/notification/count")
    assert r.status_code == 200
    assert "count" in r.json()["data"]


def test_we_com_info(client):
    r = client.get("/we_com/info")
    assert r.status_code == 200


def test_ding_talk_save(client):
    r = client.post("/ding_talk/save", json={"enabled": True})
    assert r.status_code == 200


def test_lark_info(client):
    r = client.get("/lark/info")
    assert r.status_code == 200


def test_operation_log_list(client):
    r = client.get("/operation/log/list")
    assert r.status_code == 200


def test_authentication_get_by_type(client):
    r = client.get("/authentication/get/by/type")
    assert r.status_code == 200


def test_license_validate(client):
    r = client.post("/license/validate", json={})
    assert r.status_code == 200


def test_personal_model_get(client):
    r = client.get("/personal/model/get")
    assert r.status_code == 200


def test_ai_config_get(client):
    r = client.get("/ai/config/get")
    assert r.status_code == 200


def test_ai_conversation_chat(client):
    r = client.post("/ai/conversation/chat", json={"message": "hi"})
    assert r.status_code == 200


def test_bug_attachment_list(client):
    r = client.get("/bug/attachment/list/")
    assert r.status_code == 200


def test_functional_case_comment_get_list(client):
    r = client.post("/functional/case/comment/get/list", json={})
    assert r.status_code == 200


def test_test_plan_get(client):
    r = client.get("/test-plan?id=test")
    assert r.status_code == 200


def test_project_application(client):
    r = client.get("/project/application/")
    assert r.status_code == 200


def test_system_parameter_get_email_info(client):
    r = client.get("/system/parameter/get/email-info")
    assert r.status_code == 200


def test_system_authsource_list(client):
    r = client.get("/system/authsource/list")
    assert r.status_code == 200


def test_project_task_center_page(client):
    r = client.get("/project/task-center/exec-task/page")
    assert r.status_code == 200


def test_organization_task_center_page(client):
    r = client.get("/organization/task-center/exec-task/page")
    assert r.status_code == 200


def test_system_task_center_page(client):
    r = client.get("/system/task-center/exec-task/page")
    assert r.status_code == 200


def test_fake_error_list(client):
    r = client.get("/fake/error/list")
    assert r.status_code == 200


def test_project_global_params_add(client):
    r = client.post("/project/global/params/add", json={"name": "p1"})
    assert r.status_code == 200


def test_project_file_repository_list(client):
    r = client.get("/project/file/repository/list")
    assert r.status_code == 200


def test_project_custom_field_list(client):
    r = client.get("/project/custom/field/list")
    assert r.status_code == 200


def test_project_robot_list(client):
    r = client.get("/project/robot/list")
    assert r.status_code == 200


def test_project_status_flow_setting_get(client):
    r = client.get("/project/status/flow/setting/get")
    assert r.status_code == 200
