# tests/test_apitest.py
"""接口测试模块单元测试

覆盖：接口定义、接口用例、场景编排、Mock、断言、变量提取、逻辑控制器、
环境管理、接口导入（Postman/Swagger）、接口调试 API。
"""
import json
import pytest
from fastapi.testclient import TestClient

from app.apitest import store, engine, importer


@pytest.fixture
def client():
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


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清理 apitest 数据，保证隔离。"""
    for d in store.list_definitions():
        store.delete_definition(d["id"])
    for c in store.list_api_cases():
        store.delete_api_case(c["id"])
    for s in store.list_scenarios():
        store.delete_scenario(s["id"])
    for m in store.list_mocks():
        store.delete_mock(m["id"])
    for e in store.list_environments():
        store.delete_environment(e["id"])
    yield


# ── 断言引擎 ─────────────────────────────────────────────
def test_assert_status():
    resp = {"status_code": 200, "body": ""}
    passed, msg = engine.evaluate_assert({"type": "status", "expected": "200"}, resp)
    assert passed


def test_assert_jsonpath():
    resp = {"status_code": 200, "body": '{"code": "200", "data": {"id": 1}}'}
    passed, _ = engine.evaluate_assert(
        {"type": "jsonpath", "expr": "$.data.id", "expected": "1"}, resp)
    assert passed


def test_assert_regex():
    resp = {"status_code": 200, "body": "hello world"}
    passed, _ = engine.evaluate_assert({"type": "regex", "expected": r"wor\w+"}, resp)
    assert passed


def test_assert_contains():
    resp = {"status_code": 200, "body": "server is ok"}
    passed, _ = engine.evaluate_assert({"type": "contains", "expected": "ok"}, resp)
    assert passed


def test_assert_failed():
    resp = {"status_code": 500, "body": ""}
    passed, _ = engine.evaluate_assert({"type": "status", "expected": "200"}, resp)
    assert not passed


# ── 变量提取 ─────────────────────────────────────────────
def test_extract_variables_jsonpath():
    resp = {"status_code": 200, "body": '{"token": "abc123"}'}
    extracted = engine.extract_variables_from_response(
        resp, [{"name": "token", "type": "jsonpath", "expr": "$.token"}])
    assert extracted.get("token") == "abc123"


def test_extract_variables_regex():
    resp = {"status_code": 200, "body": "Session: ABC-999"}
    extracted = engine.extract_variables_from_response(
        resp, [{"name": "sid", "type": "regex", "expr": r"Session: ([\w-]+)"}])
    assert extracted.get("sid") == "ABC-999"


# ── 逻辑控制器 ───────────────────────────────────────────
def test_logic_loop():
    r = engine.evaluate_logic_controller({"type": "loop", "count": 3}, {"vars": {}})
    assert r["iterations"] == 3


def test_logic_condition():
    r = engine.evaluate_logic_controller({"type": "condition", "expr": "1 < 2"}, {"vars": {}})
    assert r["passed"] is True


def test_logic_wait():
    r = engine.evaluate_logic_controller({"type": "wait", "delay_ms": 5}, {"vars": {}})
    assert r["message"].startswith("等待")


# ── 脚本执行 ─────────────────────────────────────────────
def test_python_script():
    ctx = {"vars": {}}
    r = engine.execute_script({"type": "python", "code": "1 + 2"}, ctx)
    assert r["output"] == "3"


def test_python_script_exec():
    ctx = {"vars": {}}
    r = engine.execute_script({"type": "python", "code": "_vars['x'] = 10"}, ctx)
    assert ctx["vars"].get("x") == 10


# ── 环境变量渲染 ─────────────────────────────────────────
def test_merge_environment():
    env = {"base_url": "https://prod.example.com", "headers": {"X-Key": "k"}, "variables": {"uid": "1"}}
    req = {"method": "GET", "path": "/users/{{ uid }}", "headers": {"Content-Type": "application/json"}}
    merged = engine.merge_environment(req, env)
    assert merged["path"] == "https://prod.example.com/users/1"
    assert merged["headers"]["X-Key"] == "k"


# ── 数据层 CRUD ──────────────────────────────────────────
def test_definition_crud():
    d = store.create_definition("登录接口", protocol="HTTP", method="POST", path="/login")
    assert d["id"]
    got = store.get_definition(d["id"])
    assert got["name"] == "登录接口"
    store.update_definition(d["id"], path="/v2/login")
    assert store.get_definition(d["id"])["path"] == "/v2/login"
    assert store.delete_definition(d["id"])
    assert store.get_definition(d["id"]) is None


def test_case_crud_with_asserts():
    c = store.create_api_case("用例1", asserts=[{"type": "status", "expected": "200"}])
    got = store.get_api_case(c["id"])
    assert got["asserts"][0]["expected"] == "200"
    assert store.delete_api_case(c["id"])


def test_scenario_crud():
    s = store.create_scenario("场景1", steps=[{"type": "controller", "controller": {"type": "loop", "count": 2}}])
    got = store.get_scenario(s["id"])
    assert got["steps"][0]["controller"]["count"] == 2
    assert store.delete_scenario(s["id"])


def test_mock_and_env_crud():
    m = store.create_mock("Mock1", method="GET", path="/users", response_body="{}")
    assert store.get_mock(m["id"])["path"] == "/users"
    e = store.create_environment("生产", base_url="https://a.com", variables={"k": "v"})
    assert store.get_environment(e["id"])["variables"]["k"] == "v"


# ── 接口导入 ─────────────────────────────────────────────
def test_import_postman():
    pm = json.dumps({
        "info": {"name": "demo"},
        "variable": [{"key": "baseUrl", "value": "https://api.example.com"}],
        "item": [
            {"name": "登录", "request": {"method": "POST",
             "url": {"raw": "https://api.example.com/login", "query": []},
             "header": [], "body": {"raw": "{}"}}}
        ],
    })
    r = importer.import_postman(pm)
    assert r["success"] and r["imported"] == 1


def test_import_swagger():
    sw = json.dumps({"openapi": "3.0.0", "paths": {
        "/users": {"get": {"summary": "列表"}}, "/orders": {"post": {"summary": "创建"}}}})
    r = importer.import_swagger(sw)
    assert r["success"] and r["imported"] == 2


def test_import_auto():
    sw = '{"openapi":"3.0.0","paths":{"/ping":{"get":{"summary":"ping"}}}}'
    r = importer.import_content(sw, "auto")
    assert r["success"] and r["imported"] == 1


# ── API 集成 ─────────────────────────────────────────────
def test_api_stats_and_meta(client):
    r = client.get("/api/apitest/stats")
    assert r.status_code == 200
    assert "definitions" in r.json()
    r = client.get("/api/apitest/meta")
    assert r.status_code == 200
    assert "assert_types" in r.json()


def test_api_definition_flow(client):
    r = client.post("/api/apitest/definitions", json={"name": "接口A", "method": "GET", "path": "/a"})
    assert r.status_code == 200
    did = r.json()["id"]
    r = client.get("/api/apitest/definitions")
    assert any(d["id"] == did for d in r.json()["items"])
    r = client.delete(f"/api/apitest/definitions/{did}")
    assert r.json()["success"]


def test_api_case_flow(client):
    r = client.post("/api/apitest/cases", json={
        "name": "用例A", "asserts": [{"type": "status", "expected": "200"}]})
    assert r.status_code == 200
    cid = r.json()["id"]
    r = client.get("/api/apitest/cases")
    assert any(c["id"] == cid for c in r.json()["items"])
    r = client.delete(f"/api/apitest/cases/{cid}")
    assert r.json()["success"]


def test_api_scenario_flow(client):
    r = client.post("/api/apitest/scenarios", json={
        "name": "场景A", "steps": [{"type": "controller", "controller": {"type": "wait", "delay_ms": 1}}]})
    assert r.status_code == 200
    sid = r.json()["id"]
    r = client.delete(f"/api/apitest/scenarios/{sid}")
    assert r.json()["success"]


def test_api_mock_and_call(client):
    client.post("/api/apitest/mocks", json={
        "name": "MockA", "method": "GET", "path": "/ping",
        "status_code": 200, "response_body": '{"pong":true}'})
    r = client.get("/mock/ping")
    assert r.status_code == 200
    assert r.json()["pong"] is True


def test_api_environment_flow(client):
    r = client.post("/api/apitest/environments", json={"name": "测试", "base_url": "https://t.com"})
    assert r.status_code == 200
    eid = r.json()["id"]
    r = client.get("/api/apitest/environments")
    assert any(e["id"] == eid for e in r.json()["items"])
    r = client.delete(f"/api/apitest/environments/{eid}")
    assert r.json()["success"]


def test_api_import(client):
    sw = '{"openapi":"3.0.0","paths":{"/x":{"get":{"summary":"x"}}}}'
    r = client.post("/api/apitest/import", json={"content": sw, "format": "swagger"})
    assert r.status_code == 200
    assert r.json()["imported"] == 1


def test_api_debug_error_handling(client):
    # 非法请求应返回错误而非崩溃
    r = client.post("/api/apitest/debug", json={"method": "GET", "path": "not-a-valid-url"})
    assert r.status_code == 200
    assert r.json()["response"]["ok"] is False
