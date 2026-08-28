# app/apitest/store.py
"""接口测试数据持久化层（基于 SQLite）

统一管理接口定义、接口用例、场景编排、Mock 服务、环境配置等数据的存储。
"""
import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 统一使用 Database 连接池管理
from app.core.database import Database


# 模块级缓存连接，避免每次操作新建/关闭 SQLite 连接

def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("apitest.db")


def _init_db() -> None:
    """初始化接口测试库表结构（使用独立临时连接）。"""
    conn = _get_conn()
    try:
        # 接口定义
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_definitions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                protocol TEXT DEFAULT 'HTTP',      -- HTTP/TCP/SQL/DUBBO
                method TEXT DEFAULT 'GET',
                path TEXT DEFAULT '',
                headers TEXT DEFAULT '{}',
                body TEXT DEFAULT '',
                query TEXT DEFAULT '{}',
                params TEXT DEFAULT '{}',
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                created_at REAL,
                updated_at REAL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        # 接口用例
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_cases (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_definition_id TEXT DEFAULT '',
                request TEXT DEFAULT '{}',        -- 请求体（覆盖定义）
                asserts TEXT DEFAULT '[]',        -- 断言规则列表
                pre_scripts TEXT DEFAULT '[]',    -- 前置脚本
                post_scripts TEXT DEFAULT '[]',   -- 后置脚本
                pre_sql TEXT DEFAULT '[]',        -- 前置 SQL
                post_sql TEXT DEFAULT '[]',       -- 后置 SQL
                variables TEXT DEFAULT '[]',      -- 变量提取
                logic_controllers TEXT DEFAULT '[]',  -- 逻辑控制器
                environment_id TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                priority TEXT DEFAULT 'P2',
                description TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        # 接口场景
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_scenarios (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                steps TEXT DEFAULT '[]',          -- 编排步骤（有序）
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                environment_id TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        # Mock 服务
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_mocks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_definition_id TEXT DEFAULT '',
                method TEXT DEFAULT 'GET',
                path TEXT DEFAULT '',
                status_code INTEGER DEFAULT 200,
                response_body TEXT DEFAULT '',
                response_headers TEXT DEFAULT '{}',
                delay_ms INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                description TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL
            )
        """)
        # 环境管理
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_environments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_url TEXT DEFAULT '',
                headers TEXT DEFAULT '{}',
                variables TEXT DEFAULT '{}',
                description TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.commit()
    finally:
        # 不关闭共享连接：由 Database 连接池统一管理，避免破坏连接复用
        pass


_init_db()


def _now() -> float:
    return time.time()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    for key in ("headers", "query", "params", "metadata", "response_headers", "variables"):
        if key in data and isinstance(data[key], str):
            try:
                data[key] = json.loads(data[key])
            except (json.JSONDecodeError, TypeError):
                data[key] = {}
    for key in ("tags", "asserts", "pre_scripts", "post_scripts", "pre_sql",
                "post_sql", "variables", "logic_controllers", "steps"):
        if key in data and isinstance(data[key], str):
            try:
                data[key] = json.loads(data[key])
            except (json.JSONDecodeError, TypeError):
                data[key] = []
    return data


# ── 通用 CRUD 辅助 ─────────────────────────────────────────
def _insert(table: str, data: Dict[str, Any]) -> Dict[str, Any]:
    cols = ", ".join(data.keys())
    marks = ", ".join(["?"] * len(data))
    conn = _get_conn()
    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(data.values()))
    conn.commit()
    return data


def _update(table: str, item_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    sets = ", ".join([f"{k} = ?" for k in data.keys()])
    conn = _get_conn()
    cur = conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?",
                       list(data.values()) + [item_id])
    conn.commit()
    if cur.rowcount == 0:
        return None
    return data


def _delete(table: str, item_id: str) -> bool:
    conn = _get_conn()
    cur = conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
    conn.commit()
    return cur.rowcount > 0


def _get(table: str, item_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone()
    return _row_to_dict(row) if row else None


def _list(table: str, keyword: str = "", limit: int = 100, offset: int = 0,
          order_by: str = "created_at DESC") -> List[Dict[str, Any]]:
    conn = _get_conn()
    if keyword:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE name LIKE ? ORDER BY {order_by} LIMIT ? OFFSET ?",
            (f"%{keyword}%", limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT * FROM {table} ORDER BY {order_by} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _count(table: str) -> int:
    conn = _get_conn()
    row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
    return row["c"]
def create_definition(name: str, protocol: str = "HTTP", method: str = "GET",
                      path: str = "", headers: dict = None, body: str = "",
                      query: dict = None, params: dict = None,
                      description: str = "", tags: list = None) -> Dict[str, Any]:
    data = {
        "id": _new_id(), "name": name, "protocol": protocol, "method": method,
        "path": path, "headers": json.dumps(headers or {}, ensure_ascii=False),
        "body": body, "query": json.dumps(query or {}, ensure_ascii=False),
        "params": json.dumps(params or {}, ensure_ascii=False),
        "description": description, "tags": json.dumps(tags or [], ensure_ascii=False),
        "created_at": _now(), "updated_at": _now(), "metadata": "{}",
    }
    _insert("api_definitions", data)
    return _row_to_dict(_get("api_definitions", data["id"]))


def list_definitions(keyword: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    return _list("api_definitions", keyword, limit, offset)


def count_definitions() -> int:
    return _count("api_definitions")


def get_definition(definition_id: str) -> Optional[Dict[str, Any]]:
    return _get("api_definitions", definition_id)


def update_definition(definition_id: str, **fields) -> Optional[Dict[str, Any]]:
    for k in ("headers", "query", "params", "tags"):
        if k in fields and isinstance(fields[k], (dict, list)):
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
    fields["updated_at"] = _now()
    if not _update("api_definitions", definition_id, fields):
        return None
    return _get("api_definitions", definition_id)


def delete_definition(definition_id: str) -> bool:
    return _delete("api_definitions", definition_id)


# ── 接口用例 ───────────────────────────────────────────────
def create_api_case(name: str, api_definition_id: str = "", request: dict = None,
                    asserts: list = None, pre_scripts: list = None,
                    post_scripts: list = None, pre_sql: list = None,
                    post_sql: list = None, variables: list = None,
                    logic_controllers: list = None, environment_id: str = "",
                    status: str = "draft", priority: str = "P2",
                    description: str = "") -> Dict[str, Any]:
    data = {
        "id": _new_id(), "name": name, "api_definition_id": api_definition_id,
        "request": json.dumps(request or {}, ensure_ascii=False),
        "asserts": json.dumps(asserts or [], ensure_ascii=False),
        "pre_scripts": json.dumps(pre_scripts or [], ensure_ascii=False),
        "post_scripts": json.dumps(post_scripts or [], ensure_ascii=False),
        "pre_sql": json.dumps(pre_sql or [], ensure_ascii=False),
        "post_sql": json.dumps(post_sql or [], ensure_ascii=False),
        "variables": json.dumps(variables or [], ensure_ascii=False),
        "logic_controllers": json.dumps(logic_controllers or [], ensure_ascii=False),
        "environment_id": environment_id, "status": status, "priority": priority,
        "description": description, "created_at": _now(), "updated_at": _now(),
        "metadata": "{}",
    }
    _insert("api_cases", data)
    return _get("api_cases", data["id"])


def list_api_cases(keyword: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    return _list("api_cases", keyword, limit, offset)


def count_api_cases() -> int:
    return _count("api_cases")


def get_api_case(case_id: str) -> Optional[Dict[str, Any]]:
    return _get("api_cases", case_id)


def update_api_case(case_id: str, **fields) -> Optional[Dict[str, Any]]:
    for k in ("request", "asserts", "pre_scripts", "post_scripts", "pre_sql",
              "post_sql", "variables", "logic_controllers"):
        if k in fields and isinstance(fields[k], (dict, list)):
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
    fields["updated_at"] = _now()
    if not _update("api_cases", case_id, fields):
        return None
    return _get("api_cases", case_id)


def delete_api_case(case_id: str) -> bool:
    return _delete("api_cases", case_id)


# ── 接口场景 ───────────────────────────────────────────────
def create_scenario(name: str, steps: list = None, description: str = "",
                    status: str = "draft", environment_id: str = "") -> Dict[str, Any]:
    data = {
        "id": _new_id(), "name": name, "steps": json.dumps(steps or [], ensure_ascii=False),
        "description": description, "status": status, "environment_id": environment_id,
        "created_at": _now(), "updated_at": _now(), "metadata": "{}",
    }
    _insert("api_scenarios", data)
    return _get("api_scenarios", data["id"])


def list_scenarios(keyword: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    return _list("api_scenarios", keyword, limit, offset)


def count_scenarios() -> int:
    return _count("api_scenarios")


def get_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    return _get("api_scenarios", scenario_id)


def update_scenario(scenario_id: str, **fields) -> Optional[Dict[str, Any]]:
    if "steps" in fields and isinstance(fields["steps"], list):
        fields["steps"] = json.dumps(fields["steps"], ensure_ascii=False)
    fields["updated_at"] = _now()
    if not _update("api_scenarios", scenario_id, fields):
        return None
    return _get("api_scenarios", scenario_id)


def delete_scenario(scenario_id: str) -> bool:
    return _delete("api_scenarios", scenario_id)


# ── Mock 服务 ──────────────────────────────────────────────
def create_mock(name: str, api_definition_id: str = "", method: str = "GET",
                path: str = "", status_code: int = 200, response_body: str = "",
                response_headers: dict = None, delay_ms: int = 0,
                active: int = 1, description: str = "") -> Dict[str, Any]:
    data = {
        "id": _new_id(), "name": name, "api_definition_id": api_definition_id,
        "method": method, "path": path, "status_code": status_code,
        "response_body": response_body,
        "response_headers": json.dumps(response_headers or {}, ensure_ascii=False),
        "delay_ms": delay_ms, "active": active, "description": description,
        "created_at": _now(), "updated_at": _now(),
    }
    _insert("api_mocks", data)
    return _get("api_mocks", data["id"])


def list_mocks(keyword: str = "", limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    return _list("api_mocks", keyword, limit, offset)


def count_mocks() -> int:
    return _count("api_mocks")


def get_mock(mock_id: str) -> Optional[Dict[str, Any]]:
    return _get("api_mocks", mock_id)


def update_mock(mock_id: str, **fields) -> Optional[Dict[str, Any]]:
    if "response_headers" in fields and isinstance(fields["response_headers"], dict):
        fields["response_headers"] = json.dumps(fields["response_headers"], ensure_ascii=False)
    fields["updated_at"] = _now()
    if not _update("api_mocks", mock_id, fields):
        return None
    return _get("api_mocks", mock_id)


def delete_mock(mock_id: str) -> bool:
    return _delete("api_mocks", mock_id)


# ── 环境管理 ───────────────────────────────────────────────
def create_environment(name: str, base_url: str = "", headers: dict = None,
                       variables: dict = None, description: str = "") -> Dict[str, Any]:
    data = {
        "id": _new_id(), "name": name, "base_url": base_url,
        "headers": json.dumps(headers or {}, ensure_ascii=False),
        "variables": json.dumps(variables or {}, ensure_ascii=False),
        "description": description, "created_at": _now(), "updated_at": _now(),
    }
    _insert("api_environments", data)
    return _get("api_environments", data["id"])


def list_environments() -> List[Dict[str, Any]]:
    return _list("api_environments", "", 100, 0, "created_at ASC")


def count_environments() -> int:
    return _count("api_environments")


def get_environment(env_id: str) -> Optional[Dict[str, Any]]:
    return _get("api_environments", env_id)


def update_environment(env_id: str, **fields) -> Optional[Dict[str, Any]]:
    for k in ("headers", "variables"):
        if k in fields and isinstance(fields[k], dict):
            fields[k] = json.dumps(fields[k], ensure_ascii=False)
    fields["updated_at"] = _now()
    if not _update("api_environments", env_id, fields):
        return None
    return _get("api_environments", env_id)


def delete_environment(env_id: str) -> bool:
    return _delete("api_environments", env_id)
