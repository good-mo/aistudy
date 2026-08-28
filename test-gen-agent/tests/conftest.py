"""
pytest 共享夹具。

提供已认证的 TestClient，使业务接口测试自动携带登录凭证。
"""
import os
import sys

import pytest

# 确保可导入 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient


def make_auth_headers(client) -> dict:
    """登录并返回认证请求头。"""
    r = client.post("/login", json={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        raise RuntimeError(f"登录失败: {r.status_code} {r.text}")
    session = r.json()["data"]
    return {
        "X-AUTH-TOKEN": session["sessionId"],
        "CSRF-TOKEN": session["csrfToken"],
    }


@pytest.fixture
def auth_client():
    """返回已登录的 TestClient。"""
    from app.main import app
    client = TestClient(app)
    headers = make_auth_headers(client)
    # 注入默认 headers
    client.headers.update(headers)
    yield client


@pytest.fixture
def anon_client():
    """返回未登录的 TestClient。"""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_headers(auth_client) -> dict:
    """返回认证请求头字典。"""
    return {
        "X-AUTH-TOKEN": auth_client.headers.get("X-AUTH-TOKEN", ""),
        "CSRF-TOKEN": auth_client.headers.get("CSRF-TOKEN", ""),
    }
