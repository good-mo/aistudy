"""认证模块单元测试：登录、登出、会话、用户、RSA 密钥。"""

import os
import tempfile
import unittest

import pytest
from fastapi.testclient import TestClient

# 使用临时数据库
os.environ.setdefault("AUTH_DB_PATH", "test_auth.db")

from app.main import app  # noqa: E402


@pytest.fixture
def client():
    """创建测试客户端。"""
    # 清理测试数据库
    db_path = "test_auth.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    return TestClient(app)


class TestAuthFlow:
    """认证流程测试。"""

    def test_get_public_key(self, client):
        """获取 RSA 公钥。"""
        r = client.get("/get-key")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert "BEGIN PUBLIC KEY" in data["data"]

    def test_login_success(self, client):
        """登录成功。"""
        r = client.post("/login", json={
            "username": "admin",
            "password": "admin123",
            "authenticate": "LOCAL",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["sessionId"]
        assert data["data"]["csrfToken"]
        assert data["data"]["name"]  # has name

    def test_login_fail(self, client):
        """登录失败（错误密码）。"""
        r = client.post("/login", json={
            "username": "admin",
            "password": "wrong_password",
            "authenticate": "LOCAL",
        })
        assert r.status_code == 400

    def test_login_user_not_exist(self, client):
        """登录失败（用户不存在）。"""
        r = client.post("/login", json={
            "username": "nonexistent",
            "password": "test123",
            "authenticate": "LOCAL",
        })
        assert r.status_code == 400

    def test_is_login(self, client):
        """检查登录状态。"""
        # 先登录
        r = client.post("/login", json={"username": "admin", "password": "admin123"})
        session = r.json()["data"]
        headers = {
            "X-AUTH-TOKEN": session["sessionId"],
            "CSRF-TOKEN": session["csrfToken"],
        }
        # 检查登录状态
        r = client.get("/is-login", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"]  # has name

    def test_is_login_not_authenticated(self, client):
        """未登录时检查登录状态。"""
        r = client.get("/is-login")
        assert r.status_code == 401

    def test_signout(self, client):
        """登出。"""
        # 先登录
        r = client.post("/login", json={"username": "admin", "password": "admin123"})
        session = r.json()["data"]
        headers = {
            "X-AUTH-TOKEN": session["sessionId"],
            "CSRF-TOKEN": session["csrfToken"],
        }
        # 登出
        r = client.post("/signout", headers=headers)
        assert r.status_code == 200
        # 登出后检查
        r = client.get("/is-login", headers=headers)
        assert r.status_code == 401

    def test_authentication_list(self, client):
        """获取认证方式。"""
        r = client.get("/authentication/get-list")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert "LOCAL" in data["data"]


class TestPersonalInfo:
    """个人信息测试。"""

    def _login_headers(self, client):
        r = client.post("/login", json={"username": "admin", "password": "admin123"})
        session = r.json()["data"]
        return {
            "X-AUTH-TOKEN": session["sessionId"],
            "CSRF-TOKEN": session["csrfToken"],
        }

    def test_get_personal_info(self, client):
        """获取个人信息。"""
        headers = self._login_headers(client)
        r = client.get("/personal/get", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"]  # has name

    def test_update_personal_info(self, client):
        """更新个人信息。"""
        headers = self._login_headers(client)
        r = client.post("/personal/update-info", headers=headers, json={
            "name": "New Admin",
            "email": "new@example.com",
        })
        assert r.status_code == 200
        # 验证更新
        r = client.get("/personal/get", headers=headers)
        data = r.json()["data"]
        assert data["name"] == "New Admin"
        assert data["email"] == "new@example.com"

    def test_get_personal_info_not_login(self, client):
        """未登录获取个人信息。"""
        r = client.get("/personal/get")
        assert r.status_code == 401


class TestMenuAndSystem:
    """菜单和系统信息测试。"""

    def test_get_menu_list(self, client):
        """获取菜单列表。"""
        r = client.post("/api/user/menu")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert len(data["data"]) > 0

    def _login_headers(self, client):
        r = client.post("/login", json={"username": "admin", "password": "admin123"})
        session = r.json()["data"]
        return {
            "X-AUTH-TOKEN": session["sessionId"],
            "CSRF-TOKEN": session["csrfToken"],
        }

    def test_get_system_version(self, client):
        """获取系统版本。"""
        headers = self._login_headers(client)
        r = client.get("/system/version/current", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["data"]

    def test_get_package_type(self, client):
        """获取包类型。"""
        headers = self._login_headers(client)
        r = client.get("/system/version/package-type", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["data"] in ["enterprise", "community"]

    def test_get_base_info(self, client):
        """获取基础信息。"""
        headers = self._login_headers(client)
        r = client.get("/system/parameter/get/base-info", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == 200

    def test_get_display_config(self, client):
        """获取界面配置。"""
        headers = self._login_headers(client)
        r = client.get("/display/info", headers=headers)
        assert r.status_code == 200
        assert r.json()["code"] == 200


class TestProjectManagement:
    """项目管理测试。"""

    def _login_headers(self, client):
        r = client.post("/login", json={"username": "admin", "password": "admin123"})
        session = r.json()["data"]
        return {
            "X-AUTH-TOKEN": session["sessionId"],
            "CSRF-TOKEN": session["csrfToken"],
        }

    def test_get_project(self, client):
        """获取项目详情。"""
        headers = self._login_headers(client)
        r = client.get("/project/get/test-project", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 200
        assert data["data"]["name"]
        assert data["data"]["id"] == "test-project"


class TestLocalConfig:
    """本地执行配置测试。"""

    def _login_headers(self, client):
        r = client.post("/login", json={"username": "admin", "password": "admin123"})
        session = r.json()["data"]
        return {
            "X-AUTH-TOKEN": session["sessionId"],
            "CSRF-TOKEN": session["csrfToken"],
        }

    def test_get_local_configs(self, client):
        """获取本地执行配置。"""
        headers = self._login_headers(client)
        r = client.get("/user/local/config/get", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)

    def test_add_local_config(self, client):
        """添加本地执行配置。"""
        headers = self._login_headers(client)
        r = client.post("/user/local/config/add", headers=headers, json={
            "user_url": "http://localhost:8080",
            "type": "API",
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["user_url"] == "http://localhost:8080"


class TestAPIKey:
    """API Key 管理测试。"""

    def _login_headers(self, client):
        r = client.post("/login", json={"username": "admin", "password": "admin123"})
        session = r.json()["data"]
        return {
            "X-AUTH-TOKEN": session["sessionId"],
            "CSRF-TOKEN": session["csrfToken"],
        }

    def test_list_api_keys(self, client):
        """获取 API Key 列表。"""
        headers = self._login_headers(client)
        r = client.get("/user/api/key/list", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)

    def test_create_api_key(self, client):
        """创建 API Key。"""
        headers = self._login_headers(client)
        r = client.post("/user/api/key/add", headers=headers, json={
            "description": "测试Key",
            "forever": True,
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["access_key"]
        assert data["secret_key"]

    def test_delete_api_key(self, client):
        """删除 API Key。"""
        headers = self._login_headers(client)
        # 先创建
        r = client.post("/user/api/key/add", headers=headers, json={"description": "待删除"})
        key_id = r.json()["data"]["id"]
        # 删除
        r = client.post("/user/api/key/delete", headers=headers, json={"id": key_id})
        assert r.status_code == 200
        # 验证已删除
        r = client.get("/user/api/key/list", headers=headers)
        keys = r.json()["data"]
        assert all(k["id"] != key_id for k in keys)


if __name__ == "__main__":
    unittest.main()
