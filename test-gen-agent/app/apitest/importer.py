# app/apitest/importer.py
"""接口导入模块

支持从 Postman Collection 与 Swagger/OpenAPI 定义导入接口定义与用例。
"""
import json
import re
from typing import Any, Dict, List

from app.logging_config import get_logger
from app.apitest import store

logger = get_logger(__name__)


# ── Postman 导入 ───────────────────────────────────────────
def _postman_build_request(item: Dict[str, Any], base_url: str = "") -> Dict[str, Any]:
    req = item.get("request", {})
    method = req.get("method", "GET")
    url_obj = req.get("url", {})
    if isinstance(url_obj, str):
        raw_url = url_obj
        query = {}
    else:
        raw_url = url_obj.get("raw", "")
        query = {}
        if url_obj.get("query"):
            for q in url_obj["query"]:
                if q.get("key"):
                    query[q["key"]] = q.get("value", "")

    headers = {}
    for h in req.get("header", []) or []:
        if h.get("key"):
            headers[h["key"]] = h.get("value", "")

    body = ""
    body_obj = req.get("body", {})
    if isinstance(body_obj, dict):
        if body_obj.get("raw"):
            body = body_obj["raw"]
        elif body_obj.get("urlencoded"):
            pairs = []
            for kv in body_obj["urlencoded"]:
                if kv.get("key"):
                    pairs.append(f"{kv['key']}={kv.get('value','')}")
            body = "&".join(pairs)
        elif body_obj.get("formdata"):
            body = json.dumps(body_obj.get("formdata"), ensure_ascii=False)

    # 去掉 base_url 前缀，保留 path
    path = raw_url
    if base_url and raw_url.startswith(base_url):
        path = raw_url[len(base_url):]

    return {
        "name": item.get("name", "未命名接口"),
        "method": method, "path": path, "headers": headers,
        "body": body, "query": query,
    }


def import_postman(content: str) -> Dict[str, Any]:
    """从 Postman Collection JSON 导入接口定义。"""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析失败: {e}", "imported": 0}

    base_url = ""
    # 尝试提取 baseUrl
    if data.get("variable"):
        for v in data["variable"]:
            if v.get("key", "").lower() in ("baseurl", "base_url", "host"):
                base_url = v.get("value", "")
                break

    items = data.get("item", [])
    imported = 0
    errors = []

    def _walk(items, folder=""):
        nonlocal imported
        for it in items:
            if it.get("item"):
                # 文件夹
                _walk(it["item"], folder + it.get("name", "") + "/")
            elif it.get("request"):
                try:
                    r = _postman_build_request(it, base_url)
                    name = folder + r["name"]
                    store.create_definition(
                        name=name, protocol="HTTP", method=r["method"], path=r["path"],
                        headers=r["headers"], body=r["body"], query=r["query"],
                        description=f"来自 Postman 导入", tags=["postman"],
                    )
                    imported += 1
                except Exception as ex:
                    errors.append(str(ex))

    _walk(items)
    return {"success": True, "imported": imported, "errors": errors, "base_url": base_url}


# ── Swagger / OpenAPI 导入 ─────────────────────────────────
def import_swagger(content: str) -> Dict[str, Any]:
    """从 Swagger 2.0 / OpenAPI 3.x JSON 导入接口定义。"""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析失败: {e}", "imported": 0}

    paths = data.get("paths", {})
    servers = data.get("servers", [])
    base_url = servers[0].get("url", "") if servers else ""
    if not base_url and data.get("host"):
        base_url = f"{'https' if data.get('schemes') and 'https' in data['schemes'] else 'http'}://{data['host']}"
        base_path = data.get("basePath", "")
        base_url += base_path

    imported = 0
    errors = []
    for path, methods in (paths or {}).items():
        for method, op in (methods or {}).items():
            if method.lower() not in ("get", "post", "put", "delete", "patch", "head", "options"):
                continue
            try:
                summary = op.get("summary", "") or op.get("operationId", "") or path
                tags = list(op.get("tags", [])) or ["swagger"]
                query = {}
                if op.get("parameters"):
                    for p in op["parameters"]:
                        if p.get("in") == "query":
                            query[p.get("name", "")] = p.get("example", "")
                store.create_definition(
                    name=summary, protocol="HTTP", method=method.upper(), path=path,
                    headers={"Content-Type": "application/json"}, query=query,
                    description=f"来自 Swagger/OpenAPI 导入", tags=tags,
                )
                imported += 1
            except Exception as ex:
                errors.append(str(ex))
    return {"success": True, "imported": imported, "errors": errors, "base_url": base_url}


def import_content(content: str, format: str = "auto") -> Dict[str, Any]:
    """自动识别格式导入。"""
    f = format.lower()
    if f == "auto":
        try:
            data = json.loads(content)
            if "paths" in data and ("swagger" in data or "openapi" in data):
                return import_swagger(content)
            if "item" in data and ("info" in data or "variable" in data):
                return import_postman(content)
            return {"success": False, "error": "无法识别的接口文档格式", "imported": 0}
        except json.JSONDecodeError:
            return {"success": False, "error": "请输入有效的 JSON 内容", "imported": 0}
    if f in ("swagger", "openapi", "openapi3"):
        return import_swagger(content)
    if f == "postman":
        return import_postman(content)
    return {"success": False, "error": f"不支持的导入格式: {f}", "imported": 0}
