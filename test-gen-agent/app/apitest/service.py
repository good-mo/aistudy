# app/apitest/service.py
"""接口测试 API 服务层

封装接口测试各功能模块，供 main.py 路由调用。
"""
from typing import Any, Dict, List, Optional
import json
from threading import Lock

from app.apitest import store, engine, importer, scenario_runner
from app.logging_config import get_logger

logger = get_logger(__name__)

_dashboard_cache: Optional[Dict[str, Any]] = None
_dashboard_cache_time: float = 0.0
_dashboard_cache_lock = Lock()
_DASHBOARD_CACHE_TTL = 5.0  # 秒


def dashboard_stats() -> Dict[str, Any]:
    """接口测试模块仪表盘统计（带 5s 缓存）。"""
    import time as _t
    global _dashboard_cache, _dashboard_cache_time
    now = _t.time()
    with _dashboard_cache_lock:
        if _dashboard_cache is not None and (now - _dashboard_cache_time) < _DASHBOARD_CACHE_TTL:
            return _dashboard_cache
    stats = {
        "definitions": store.count_definitions(),
        "cases": store.count_api_cases(),
        "scenarios": store.count_scenarios(),
        "mocks": store.count_mocks(),
        "environments": store.count_environments(),
    }
    with _dashboard_cache_lock:
        _dashboard_cache = stats
        _dashboard_cache_time = now
    return stats


def run_debug(req: Dict[str, Any]) -> Dict[str, Any]:
    """接口调试：发送请求并执行断言、变量提取。"""
    request = dict(req)
    env_id = request.pop("environment_id", "")
    asserts = request.pop("asserts", [])
    variables_rules = request.pop("variables", [])

    # 解析请求
    api_req = {
        "protocol": request.get("protocol", "HTTP"),
        "method": request.get("method", "GET"),
        "path": request.get("path", ""),
        "headers": request.get("headers") or {},
        "body": request.get("body", ""),
        "query": request.get("query") or {},
        "params": request.get("params") or {},
    }
    if request.get("host"):
        api_req["host"] = request["host"]
        api_req["port"] = request.get("port", 80)
        api_req["payload"] = request.get("payload", "")

    # 应用环境
    env = store.get_environment(env_id) if env_id else None
    api_req = engine.merge_environment(api_req, env)

    # 执行请求
    resp = engine.execute_request(api_req)

    # 断言
    assert_result = engine.evaluate_asserts(asserts, resp) if asserts else None

    # 变量提取
    extracted = {}
    if variables_rules:
        extracted = engine.extract_variables_from_response(resp, variables_rules)

    return {
        "request": api_req,
        "response": resp,
        "asserts": assert_result,
        "extracted_variables": extracted,
    }


def run_mock_request(method: str, path: str, base_path: str = "") -> Optional[Dict[str, Any]]:
    """根据请求方法+路径匹配启用的 Mock，返回响应。"""
    mocks = store.list_mocks()
    # 规范化请求路径：去掉 base_path 前缀
    req_path = path
    if base_path and req_path.startswith(base_path.rstrip("/")):
        req_path = req_path[len(base_path.rstrip("/")):] or "/"
    for m in mocks:
        if not m.get("active"):
            continue
        m_path = m.get("path", "")
        # 兼容：mock path 可能带 base_path 前缀，也可能不带
        m_norm = m_path
        if base_path and m_norm.startswith(base_path.rstrip("/")):
            m_norm = m_norm[len(base_path.rstrip("/")):] or "/"
        if m.get("method", "").upper() == method.upper() and m_norm.lstrip("/") == req_path.lstrip("/"):
            return engine.generate_mock_response(m, {"method": method, "path": path})
    return None


def run_case(case_id: str, environment_id: str = "") -> Dict[str, Any]:
    """单独执行一个接口用例。"""
    case = store.get_api_case(case_id)
    if not case:
        return {"success": False, "error": "用例不存在"}

    definition = None
    if case.get("api_definition_id"):
        definition = store.get_definition(case["api_definition_id"])

    variables = {}
    # 前置脚本
    for sp in (case.get("pre_scripts") or []):
        engine.execute_script(sp, {"vars": variables})

    # 解析请求
    env = store.get_environment(environment_id or case.get("environment_id")) if (environment_id or case.get("environment_id")) else None
    req = {}
    if case.get("request"):
        req = json.loads(case["request"])
    elif definition:
        req = {
            "protocol": definition.get("protocol", "HTTP"),
            "method": definition.get("method", "GET"),
            "path": definition.get("path", ""),
            "headers": definition.get("headers", {}),
            "body": definition.get("body", ""),
            "query": definition.get("query", {}),
        }
    req.setdefault("protocol", "HTTP")
    req = engine.render_request_vars(req, variables)
    req = engine.merge_environment(req, env)

    resp = engine.execute_request(req)

    # 断言
    assert_result = engine.evaluate_asserts(case.get("asserts") or [], resp)

    # 变量提取
    extracted = engine.extract_variables_from_response(resp, case.get("variables") or [])

    # 后置脚本
    for sp in (case.get("post_scripts") or []):
        engine.execute_script(sp, {"vars": variables, "response": resp})

    return {
        "success": True,
        "case_id": case_id,
        "name": case.get("name"),
        "request": req,
        "response": resp,
        "asserts": assert_result,
        "extracted_variables": extracted,
    }
