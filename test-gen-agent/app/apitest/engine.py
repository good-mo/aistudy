# app/apitest/engine.py
"""接口测试运行时引擎

负责：
- 断言规则评估（文本 / 正则 / JSONPath / XPath）
- 前置 / 后置脚本执行（Python / Groovy / BeanShell 兼容）
- 变量提取（JSONPath / 正则）
- 逻辑控制器（循环 / 条件 / 等待 / 事务）
- Mock 响应生成
- 环境变量与多环境替换
- 接口调试（真实发送请求）
"""
import json
import re
import time
import socket
import urllib.request
import urllib.parse
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

from app.logging_config import get_logger

logger = get_logger(__name__)


# ── 变量 / 环境替换 ─────────────────────────────────────────
def _extract_vars(text: str) -> List[str]:
    """提取形如 {{ var }} 的变量引用。"""
    if not text:
        return []
    return re.findall(r"\{\{\s*([^}]+?)\s*\}\}", text)


def render_template(text: str, variables: Dict[str, Any]) -> str:
    """将文本中的 {{ var }} 替换为实际值。"""
    if not text:
        return text
    def _repl(m):
        name = m.group(1).strip()
        return str(variables.get(name, m.group(0)))
    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", _repl, text)


def merge_environment(request: Dict[str, Any], env: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """将环境变量注入请求，并解析请求中的 {{ var }} 引用。"""
    req = json.loads(json.dumps(request))
    variables = dict(env.get("variables") or {}) if env else {}
    if env and env.get("base_url"):
        path = req.get("path", "")
        # 相对路径拼接 base_url
        if path and not path.startswith("http"):
            req["path"] = env["base_url"].rstrip("/") + "/" + path.lstrip("/")
    # 注入环境 headers
    env_headers = dict(env.get("headers") or {}) if env else {}
    req_headers = dict(req.get("headers") or {})
    env_headers.update(req_headers)
    req["headers"] = env_headers
    # 解析所有引用变量
    for key in ("path", "body", "query", "headers", "params"):
        if key == "headers":
            for k, v in (req.get("headers") or {}).items():
                if isinstance(v, str):
                    req["headers"][k] = render_template(v, variables)
        elif key in req and isinstance(req[key], (str, dict)):
            if isinstance(req[key], dict):
                req[key] = {k: render_template(v, variables) if isinstance(v, str) else v
                            for k, v in req[key].items()}
            else:
                req[key] = render_template(req[key], variables)
    return req


# ── JSONPath / 取值 ─────────────────────────────────────────
def _get_jsonpath(obj: Any, expr: str) -> Optional[Any]:
    """简化版 JSONPath，支持 $.a.b[0].c 与 $.a.b.*。"""
    if not expr:
        return None
    expr = expr.strip()
    if expr.startswith("$"):
        expr = expr[1:]
    parts = re.findall(r"([^.\[\]]+)|\[(\d+|\*)\]", expr)
    cur = obj
    for name, idx in parts:
        if name and cur is not None:
            cur = cur.get(name) if isinstance(cur, dict) else None
        elif idx:
            if idx == "*":
                # 收集数组元素
                if isinstance(cur, list):
                    return cur
                return None
            if isinstance(cur, list) and idx.isdigit():
                i = int(idx)
                cur = cur[i] if i < len(cur) else None
            else:
                return None
    return cur


def extract_jsonpath(obj: Any, expr: str) -> Optional[Any]:
    return _get_jsonpath(obj, expr)


def _get_xpath(xml_text: str, expr: str) -> Optional[Any]:
    """简易 XPath 支持（无需外部库）：//tag、/tag、文本匹配。"""
    if not xml_text or not expr:
        return None
    expr = expr.strip()
    # 提取所有标签文本
    if expr.startswith("//"):
        tag = expr[2:].split("/")[0].strip()
        if tag == "*":
            texts = re.findall(r">([^<>]+)<", xml_text)
            return [t.strip() for t in texts if t.strip()]
        matches = re.findall(r"<%s[^>]*>([^<>]+)</%s>" % (tag, tag), xml_text)
        return matches[0] if len(matches) == 1 else (matches or None)
    if expr.startswith("/"):
        tag = expr[1:].split("/")[0].strip()
        matches = re.findall(r"<%s[^>]*>([^<>]+)</%s>" % (tag, tag), xml_text)
        return matches[0] if len(matches) == 1 else (matches or None)
    return None


# ── 断言评估 ────────────────────────────────────────────────
ASSERT_TYPES = {
    "text": "文本匹配",
    "regex": "正则表达式",
    "jsonpath": "JSONPath",
    "xpath": "XPath",
    "status": "状态码",
    "contains": "包含",
}


def evaluate_assert(assert_rule: Dict[str, Any], response: Dict[str, Any]) -> Tuple[bool, str]:
    """执行单条断言规则，返回 (是否通过, 说明)。"""
    atype = assert_rule.get("type", "text")
    expected = assert_rule.get("expected", "")
    expr = assert_rule.get("expr", "")
    actual_value = assert_rule.get("actual", None)

    # 获取实际值
    body = response.get("body", "")
    if isinstance(body, str):
        try:
            body_json = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body_json = None
    else:
        body_json = body

    if atype == "status":
        actual = response.get("status_code")
        passed = str(actual) == str(expected)
        return passed, f"状态码 {actual} {'==' if passed else '!='} {expected}"

    if atype == "jsonpath":
        actual = extract_jsonpath(body_json, expr)
        if actual is None and expr:
            return False, f"JSONPath '{expr}' 未匹配到值"
        passed = str(actual) == str(expected)
        return passed, f"JSONPath '{expr}' = {actual} {'==' if passed else '!='} {expected}"

    if atype == "xpath":
        actual = _get_xpath(body, expr)
        if actual is None:
            return False, f"XPath '{expr}' 未匹配到值"
        passed = str(actual) == str(expected)
        return passed, f"XPath '{expr}' = {actual} {'==' if passed else '!='} {expected}"

    if atype == "regex":
        try:
            found = re.search(str(expected), body if isinstance(body, str) else str(body))
            passed = found is not None
            return passed, f"正则 '{expected}' {'匹配' if passed else '未匹配'}"
        except re.error as e:
            return False, f"正则表达式错误: {e}"

    if atype == "contains":
        passed = str(expected) in str(body)
        return passed, f"包含 '{expected}' {'是' if passed else '否'}"

    # text 默认
    if actual_value is not None:
        actual = actual_value
    else:
        actual = body if isinstance(body, str) else str(body)
    passed = str(actual) == str(expected)
    return passed, f"文本 {actual[:50]} {'==' if passed else '!='} {expected}"


def evaluate_asserts(asserts: List[Dict[str, Any]], response: Dict[str, Any]) -> Dict[str, Any]:
    """执行全部断言，汇总结果。"""
    results = []
    for i, rule in enumerate(asserts):
        passed, msg = evaluate_assert(rule, response)
        results.append({"index": i, "type": rule.get("type", "text"),
                        "expr": rule.get("expr", ""), "expected": rule.get("expected", ""),
                        "passed": passed, "message": msg})
    all_passed = all(r["passed"] for r in results)
    return {"passed": all_passed, "total": len(results), "passed_count": sum(1 for r in results if r["passed"]),
            "results": results}


# ── 变量提取 ────────────────────────────────────────────────
def extract_variables_from_response(response: Dict[str, Any], rules: List[Dict[str, Any]]) -> Dict[str, str]:
    """根据提取规则从响应中提取变量。规则: {name, type: jsonpath/regex, expr}"""
    extracted = {}
    body = response.get("body", "")
    if isinstance(body, str):
        try:
            body_json = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            body_json = None
    else:
        body_json = body

    for rule in rules:
        name = rule.get("name", "")
        atype = rule.get("type", "jsonpath")
        expr = rule.get("expr", "")
        if not name or not expr:
            continue
        if atype == "jsonpath":
            val = extract_jsonpath(body_json, expr)
            if val is not None:
                extracted[name] = str(val)
        elif atype == "regex":
            m = re.search(expr, body if isinstance(body, str) else str(body))
            if m:
                extracted[name] = m.group(1) if m.groups() else m.group(0)
    return extracted


# ── 脚本执行（前置/后置）────────────────────────────────────
def execute_script(script: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """执行脚本。支持 Python / Groovy / BeanShell（兼容）。

    script: {type: python/groovy/beanshell, code: str, name: str}
    返回更新后的 context，脚本可用 context 变量，并可将结果写入 context['vars']。
    """
    stype = script.get("type", "python")
    code = script.get("code", "")
    name = script.get("name", "script")
    result = {"status": "success", "output": "", "error": ""}

    if stype == "python":
        # Python 脚本：提供 context 字典，可执行表达式或语句
        try:
            # 内置上下文
            namespace = dict(context.get("vars", {}))
            namespace["_vars"] = context.get("vars", {})
            namespace["request"] = context.get("request", {})
            namespace["response"] = context.get("response", {})
            namespace["exec"] = exec
            # 支持单行表达式（返回求值结果）
            compiled = compile(code, f"<{name}>", "eval")
            result["output"] = str(eval(compiled, namespace))
        except SyntaxError:
            try:
                ns = {"_vars": context.get("vars", {}), "request": context.get("request", {}),
                      "response": context.get("response", {})}
                exec(code, ns)
                result["output"] = "执行成功"
                # 提取脚本中写入的变量
                context["vars"].update(ns.get("_vars", {}))
            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
    else:
        # Groovy / BeanShell：仅做语法占位，实际执行由运行时决定
        # 提供简单表达式求值（数值/布尔运算）以兼容常见用例
        try:
            # 尝试作为 Python 表达式求值，作为兼容回退
            namespace = dict(context.get("vars", {}))
            result["output"] = str(eval(code, namespace))
        except Exception:
            result["status"] = "info"
            result["output"] = f"[{stype} 脚本已登记，需在目标运行时执行]"
    return result


# ── 逻辑控制器 ──────────────────────────────────────────────
def evaluate_logic_controller(controller: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """执行逻辑控制器。controller: {type: loop/condition/wait/transaction, ...}"""
    ctype = controller.get("type", "loop")
    result = {"type": ctype, "iterations": 0, "passed": True, "message": ""}

    if ctype == "loop":
        count = int(controller.get("count", 1))
        result["iterations"] = count
        result["message"] = f"循环执行 {count} 次"
    elif ctype == "condition":
        expr = controller.get("expr", "")
        vars_map = dict(context.get("vars", {}))
        try:
            passed = bool(eval(expr, vars_map))
            result["passed"] = passed
            result["message"] = f"条件 '{expr}' → {'通过' if passed else '不通过'}"
        except Exception as e:
            result["passed"] = False
            result["message"] = f"条件求值失败: {e}"
    elif ctype == "wait":
        ms = int(controller.get("delay_ms", 0))
        result["message"] = f"等待 {ms}ms"
    elif ctype == "transaction":
        result["message"] = f"事务控制器: {controller.get('name', '')}"
    else:
        result["message"] = f"未知控制器类型: {ctype}"
    return result


# ── 实际发送 HTTP 请求（接口调试 / 执行）────────────────────
def send_http_request(request: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    """发送真实 HTTP 请求。

    request: {method, path, headers, body, query, params}
    """
    method = (request.get("method") or "GET").upper()
    path = request.get("path") or ""
    headers = request.get("headers") or {}
    body = request.get("body") or ""
    query = request.get("query") or {}

    # 拼接 query
    if query:
        qs = urllib.parse.urlencode(query)
        path = path + ("&" if "?" in path else "?") + qs

    data = None
    if method in ("POST", "PUT", "PATCH"):
        data = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")

    start = time.time()
    try:
        req = urllib.request.Request(path, data=data, method=method)
        for k, v in (headers or {}).items():
            if v:
                req.add_header(k, str(v))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            resp_body = raw.decode("utf-8", errors="replace")
            response_headers = dict(resp.headers)
            elapsed = round((time.time() - start) * 1000, 2)
            return {
                "status_code": resp.status, "body": resp_body,
                "headers": response_headers, "elapsed_ms": elapsed, "ok": True,
            }
    except urllib.error.HTTPError as e:
        raw = e.read()
        resp_body = raw.decode("utf-8", errors="replace") if raw else ""
        elapsed = round((time.time() - start) * 1000, 2)
        return {
            "status_code": e.code, "body": resp_body, "headers": dict(e.headers),
            "elapsed_ms": elapsed, "ok": e.code < 400,
        }
    except Exception as e:
        return {"status_code": 0, "body": "", "headers": {}, "elapsed_ms": 0,
                "ok": False, "error": str(e)}


def send_tcp_request(request: Dict[str, Any], timeout: int = 5) -> Dict[str, Any]:
    """发送 TCP 请求。request: {host, port, payload}"""
    host = request.get("host", "127.0.0.1")
    port = int(request.get("port", 80))
    payload = request.get("payload", "")
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        if payload:
            sock.sendall(payload.encode("utf-8"))
        data = b""
        sock.settimeout(timeout)
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        except socket.timeout:
            pass
        sock.close()
        return {"status_code": 200, "body": data.decode("utf-8", errors="replace"),
                "headers": {}, "ok": True}
    except Exception as e:
        return {"status_code": 0, "body": "", "headers": {}, "ok": False, "error": str(e)}


def execute_request(request: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    """根据协议执行请求。protocol: HTTP/TCP/SQL/DUBBO。"""
    protocol = (request.get("protocol") or "HTTP").upper()
    if protocol == "TCP":
        return send_tcp_request(request, timeout)
    # HTTP / SQL / DUBBO 走 HTTP（SQL/DUBBO 需要服务端支持，此处归并为 HTTP）
    return send_http_request(request, timeout)


# ── Mock 响应生成 ───────────────────────────────────────────
def generate_mock_response(mock: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
    """根据 Mock 规则生成响应（含延迟）。"""
    delay_ms = int(mock.get("delay_ms", 0))
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
    body = mock.get("response_body", "")
    return {
        "status_code": int(mock.get("status_code", 200)),
        "body": body,
        "headers": mock.get("response_headers") or {},
        "ok": True,
    }


def render_request_vars(request: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """渲染请求中的 {{ var }} 引用（不合并环境，仅变量替换）。"""
    req = json.loads(json.dumps(request))
    for key in ("path", "body", "query", "params"):
        if key in req and isinstance(req[key], str):
            req[key] = render_template(req[key], variables)
        elif key in req and isinstance(req[key], dict):
            req[key] = {k: render_template(v, variables) if isinstance(v, str) else v
                        for k, v in req[key].items()}
    if req.get("headers"):
        req["headers"] = {k: render_template(v, variables) if isinstance(v, str) else v
                          for k, v in req["headers"].items()}
    return req
