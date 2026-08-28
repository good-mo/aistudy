"""
接口测试管理模块
================
提供：
  - 接口定义管理（API Definition）
  - 接口用例管理（Interface Test Cases）
  - 接口场景编排（Scenario Orchestration）
  - Mock 服务
  - 断言规则管理
  - 前置/后置脚本
  - 变量提取
  - 逻辑控制器
  - 接口导入（Postman/Swagger）
  - 环境管理（多环境切换）
  - 接口调试
"""
import json
import os
import sqlite3
import uuid
import time
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.logging_config import get_logger

logger = get_logger(__name__)

# 统一使用 apitest.db（与 app/apitest/store.py 共用同一数据库）
from app.core.database import Database


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("apitest.db")



def _ensure_api_columns(conn, table: str, columns: dict) -> None:
    """确保表中存在指定列，不存在则添加。"""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cursor.fetchall()}
    for col, definition in columns.items():
        if col not in existing:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            except Exception:
                pass

def _init_tables() -> None:
    """初始化所有接口测试相关的表结构。"""
    conn = _get_conn()
    try:
        # 接口定义表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_definitions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                method TEXT NOT NULL DEFAULT 'GET',
                path TEXT NOT NULL,
                protocol TEXT DEFAULT 'HTTP',  -- HTTP/TCP/SQL/DUBBO
                description TEXT DEFAULT '',
                request_headers TEXT DEFAULT '{}',
                request_params TEXT DEFAULT '{}',
                request_body TEXT DEFAULT '',
                request_body_type TEXT DEFAULT 'json',  -- json/form/xml/raw
                response_code TEXT DEFAULT '200',
                response_headers TEXT DEFAULT '{}',
                response_body TEXT DEFAULT '',
                response_body_type TEXT DEFAULT 'json',
                tags TEXT DEFAULT '[]',
                created_at REAL,
                updated_at REAL,
                created_by TEXT DEFAULT 'system',
                deleted INTEGER DEFAULT 0,
                deleted_at REAL
            )
        """)
        # 确保 api_definitions 表有 management.py 所需的列
        _ensure_api_columns(conn, "api_definitions", {
            "request_headers": "TEXT DEFAULT '{}'",
            "request_params": "TEXT DEFAULT '{}'",
            "request_body": "TEXT DEFAULT ''",
            "request_body_type": "TEXT DEFAULT 'json'",
            "response_code": "TEXT DEFAULT '200'",
            "response_headers": "TEXT DEFAULT '{}'",
            "response_body": "TEXT DEFAULT ''",
            "response_body_type": "TEXT DEFAULT 'json'",
            "created_by": "TEXT DEFAULT 'system'",
            "deleted": "INTEGER DEFAULT 0",
            "deleted_at": "REAL",
        })
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_defs_name ON api_definitions(name)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_defs_path ON api_definitions(path)
        """)

        # 接口用例表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_test_cases (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                definition_id TEXT,
                method TEXT NOT NULL DEFAULT 'GET',
                path TEXT NOT NULL,
                request_headers TEXT DEFAULT '{}',
                request_params TEXT DEFAULT '{}',
                request_body TEXT DEFAULT '',
                request_body_type TEXT DEFAULT 'json',
                assertions TEXT DEFAULT '[]',      -- JSON 数组: [{type, field, value}]
                pre_scripts TEXT DEFAULT '[]',      -- JSON 数组
                post_scripts TEXT DEFAULT '[]',     -- JSON 数组
                pre_sql TEXT DEFAULT '',
                post_sql TEXT DEFAULT '',
                variables TEXT DEFAULT '{}',        -- JSON 对象: {name: {type, value}}
                enabled INTEGER DEFAULT 1,
                status TEXT DEFAULT 'draft',        -- draft/approved/deprecated
                environment_id TEXT,
                timeout INTEGER DEFAULT 30,
                retry_count INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL,
                created_by TEXT DEFAULT 'system',
                deleted INTEGER DEFAULT 0,
                deleted_at REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_cases_name ON api_test_cases(name)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_cases_def ON api_test_cases(definition_id)
        """)

        # 场景编排表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_scenarios (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                steps TEXT DEFAULT '[]',           -- JSON 数组: [{case_id, order, enabled, variables}]
                status TEXT DEFAULT 'draft',
                environment_id TEXT,
                created_at REAL,
                updated_at REAL,
                created_by TEXT DEFAULT 'system',
                deleted INTEGER DEFAULT 0,
                deleted_at REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_scenarios_name ON api_scenarios(name)
        """)

        # Mock 服务表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mock_services (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                method TEXT NOT NULL DEFAULT 'GET',
                path TEXT NOT NULL,
                response_code INTEGER DEFAULT 200,
                response_headers TEXT DEFAULT '{}',
                response_body TEXT DEFAULT '{}',
                delay_ms INTEGER DEFAULT 0,
                enabled INTEGER DEFAULT 1,
                created_at REAL,
                updated_at REAL,
                created_by TEXT DEFAULT 'system',
                deleted INTEGER DEFAULT 0,
                deleted_at REAL
            )
        """)

        # 环境管理表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS environments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                base_url TEXT DEFAULT '',
                headers TEXT DEFAULT '{}',
                variables TEXT DEFAULT '{}',
                is_default INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL,
                created_by TEXT DEFAULT 'system'
            )
        """)

        # 断言规则模板表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assertion_rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                rule_type TEXT NOT NULL,   -- text/regex/jsonpath/xpath/status_code/header
                target TEXT DEFAULT '',
                expression TEXT DEFAULT '',
                expected TEXT DEFAULT '',
                description TEXT DEFAULT '',
                created_at REAL
            )
        """)

        # 调试日志表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_debug_logs (
                id TEXT PRIMARY KEY,
                case_id TEXT,
                method TEXT DEFAULT 'GET',
                path TEXT DEFAULT '',
                request_data TEXT DEFAULT '{}',
                response_code INTEGER DEFAULT 0,
                response_data TEXT DEFAULT '',
                duration_ms REAL DEFAULT 0,
                success INTEGER DEFAULT 0,
                error TEXT DEFAULT '',
                created_at REAL
            )
        """)

        # 迁移：为历史库补充软删除列
        for table in ('api_definitions', 'api_test_cases', 'api_scenarios', 'mock_services'):
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if "deleted" not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN deleted INTEGER DEFAULT 0")
                conn.execute(f"ALTER TABLE {table} ADD COLUMN deleted_at REAL")
        conn.commit()
    finally:
        pass  # shared cached conn


_init_tables()


# ════════════════════════════════════════════════════════════
# 接口定义管理
# ════════════════════════════════════════════════════════════

def create_api_definition(
    name: str,
    method: str = "GET",
    path: str = "",
    protocol: str = "HTTP",
    description: str = "",
    request_headers: Optional[dict] = None,
    request_params: Optional[dict] = None,
    request_body: str = "",
    request_body_type: str = "json",
    response_code: str = "200",
    response_headers: Optional[dict] = None,
    response_body: str = "",
    response_body_type: str = "json",
    tags: Optional[list] = None,
) -> dict:
    """创建接口定义。"""
    def_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO api_definitions (
                id, name, method, path, protocol, description,
                request_headers, request_params, request_body, request_body_type,
                response_code, response_headers, response_body, response_body_type,
                tags, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            def_id, name, method.upper(), path, protocol, description,
            json.dumps(request_headers or {}), json.dumps(request_params or {}),
            request_body or '', request_body_type,
            response_code, json.dumps(response_headers or {}), response_body or '', response_body_type,
            json.dumps(tags or []), now, now,
        ))
        conn.commit()
        return get_api_definition(def_id)
    finally:
        pass  # shared cached conn


def get_api_definition(def_id: str) -> Optional[dict]:
    """获取接口定义详情。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM api_definitions WHERE id = ?", (def_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ('request_headers', 'request_params', 'response_headers', 'tags'):
            try:
                d[key] = json.loads(d.get(key) or '{}')
            except:
                d[key] = {}
        return d
    finally:
        pass  # shared cached conn


def list_api_definitions(
    search: str = "",
    method: str = "",
    protocol: str = "",
    limit: int = 100,
) -> List[dict]:
    """列出接口定义。"""
    conn = _get_conn()
    try:
        sql = "SELECT * FROM api_definitions WHERE 1=1"
        params = []
        if search:
            sql += " AND (name LIKE ? OR path LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if method:
            sql += " AND method = ?"
            params.append(method.upper())
        if protocol:
            sql += " AND protocol = ?"
            params.append(protocol)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('request_headers', 'request_params', 'response_headers', 'tags'):
                try:
                    d[key] = json.loads(d.get(key) or '{}')
                except:
                    d[key] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_api_definition(def_id: str, **kwargs) -> Optional[dict]:
    """更新接口定义。"""
    allowed = {
        'name', 'method', 'path', 'protocol', 'description',
        'request_headers', 'request_params', 'request_body', 'request_body_type',
        'response_code', 'response_headers', 'response_body', 'response_body_type',
        'tags',
    }
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_api_definition(def_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(def_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE api_definitions SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_api_definition(def_id)
    finally:
        pass  # shared cached conn


def delete_api_definition(def_id: str, permanent: bool = False) -> bool:
    """删除接口定义。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            conn.execute("DELETE FROM api_definitions WHERE id = ?", (def_id,))
        else:
            conn.execute(
                "UPDATE api_definitions SET deleted = 1, deleted_at = ? WHERE id = ? AND (deleted IS NULL OR deleted = 0)",
                (time.time(), def_id),
            )
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def list_trash_definitions(limit: int = 100) -> List[dict]:
    """列出回收站中的接口定义。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_definitions WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('request_headers', 'request_params', 'response_headers', 'tags'):
                try:
                    d[key] = json.loads(d.get(key) or '{}')
                except:
                    d[key] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def restore_definition(def_id: str) -> bool:
    """从回收站恢复接口定义。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE api_definitions SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1", (def_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 接口用例管理
# ════════════════════════════════════════════════════════════

def create_api_test_case(
    name: str,
    definition_id: Optional[str] = None,
    method: str = "GET",
    path: str = "",
    request_headers: Optional[dict] = None,
    request_params: Optional[dict] = None,
    request_body: str = "",
    request_body_type: str = "json",
    assertions: Optional[list] = None,
    pre_scripts: Optional[list] = None,
    post_scripts: Optional[list] = None,
    pre_sql: str = "",
    post_sql: str = "",
    variables: Optional[dict] = None,
    environment_id: Optional[str] = None,
    timeout: int = 30,
    retry_count: int = 0,
) -> dict:
    """创建接口测试用例。"""
    case_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO api_test_cases (
                id, name, definition_id, method, path,
                request_headers, request_params, request_body, request_body_type,
                assertions, pre_scripts, post_scripts, pre_sql, post_sql,
                variables, environment_id, timeout, retry_count,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            case_id, name, definition_id, method.upper(), path,
            json.dumps(request_headers or {}), json.dumps(request_params or {}),
            request_body or '', request_body_type,
            json.dumps(assertions or []), json.dumps(pre_scripts or []),
            json.dumps(post_scripts or []), pre_sql or '', post_sql or '',
            json.dumps(variables or {}), environment_id, timeout, retry_count,
            now, now,
        ))
        conn.commit()
        return get_api_test_case(case_id)
    finally:
        pass  # shared cached conn


def get_api_test_case(case_id: str) -> Optional[dict]:
    """获取接口用例详情。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM api_test_cases WHERE id = ?", (case_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ('request_headers', 'request_params', 'assertions',
                     'pre_scripts', 'post_scripts', 'variables'):
            try:
                d[key] = json.loads(d.get(key) or '[]' if key in ('assertions', 'pre_scripts', 'post_scripts') else '{}')
            except:
                d[key] = {} if key in ('request_headers', 'request_params', 'variables') else []
        return d
    finally:
        pass  # shared cached conn


def list_api_test_cases(
    search: str = "",
    definition_id: str = "",
    environment_id: str = "",
    enabled: Optional[bool] = None,
    limit: int = 100,
) -> List[dict]:
    """列出接口用例。"""
    conn = _get_conn()
    try:
        sql = "SELECT * FROM api_test_cases WHERE 1=1"
        params = []
        if search:
            sql += " AND (name LIKE ? OR path LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if definition_id:
            sql += " AND definition_id = ?"
            params.append(definition_id)
        if environment_id:
            sql += " AND environment_id = ?"
            params.append(environment_id)
        if enabled is not None:
            sql += " AND enabled = ?"
            params.append(1 if enabled else 0)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('request_headers', 'request_params', 'assertions',
                         'pre_scripts', 'post_scripts', 'variables'):
                try:
                    d[key] = json.loads(d.get(key) or '[]' if key in ('assertions', 'pre_scripts', 'post_scripts') else '{}')
                except:
                    d[key] = {} if key in ('request_headers', 'request_params', 'variables') else []
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_api_test_case(case_id: str, **kwargs) -> Optional[dict]:
    """更新接口用例。"""
    allowed = {
        'name', 'definition_id', 'method', 'path',
        'request_headers', 'request_params', 'request_body', 'request_body_type',
        'assertions', 'pre_scripts', 'post_scripts', 'pre_sql', 'post_sql',
        'variables', 'environment_id', 'timeout', 'retry_count',
        'enabled', 'status',
    }
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_api_test_case(case_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(case_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE api_test_cases SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_api_test_case(case_id)
    finally:
        pass  # shared cached conn


def delete_api_test_case(case_id: str, permanent: bool = False) -> bool:
    """删除接口用例。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            conn.execute("DELETE FROM api_test_cases WHERE id = ?", (case_id,))
        else:
            conn.execute(
                "UPDATE api_test_cases SET deleted = 1, deleted_at = ? WHERE id = ? AND (deleted IS NULL OR deleted = 0)",
                (time.time(), case_id),
            )
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def list_trash_cases(limit: int = 100) -> List[dict]:
    """列出回收站中的接口用例。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_test_cases WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('request_headers', 'request_params', 'assertions',
                         'pre_scripts', 'post_scripts', 'variables'):
                try:
                    d[key] = json.loads(d.get(key) or '[]' if key in ('assertions', 'pre_scripts', 'post_scripts') else '{}')
                except:
                    d[key] = {} if key in ('request_headers', 'request_params', 'variables') else []
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def restore_case(case_id: str) -> bool:
    """从回收站恢复接口用例。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE api_test_cases SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1", (case_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 场景编排
# ════════════════════════════════════════════════════════════

def create_scenario(
    name: str,
    description: str = "",
    steps: Optional[list] = None,
    environment_id: Optional[str] = None,
) -> dict:
    """创建场景。steps: [{case_id, order, enabled, variables}]"""
    sc_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO api_scenarios (id, name, description, steps, environment_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
        """, (sc_id, name, description, json.dumps(steps or []), environment_id, now, now))
        conn.commit()
        return get_scenario(sc_id)
    finally:
        pass  # shared cached conn


def get_scenario(sc_id: str) -> Optional[dict]:
    """获取场景详情。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM api_scenarios WHERE id = ?", (sc_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['steps'] = json.loads(d.get('steps') or '[]')
        except:
            d['steps'] = []
        return d
    finally:
        pass  # shared cached conn


def list_scenarios(limit: int = 100) -> List[dict]:
    """列出所有场景。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_scenarios WHERE (deleted IS NULL OR deleted = 0) ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['steps'] = json.loads(d.get('steps') or '[]')
            except:
                d['steps'] = []
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_scenario(sc_id: str, **kwargs) -> Optional[dict]:
    """更新场景。"""
    allowed = {'name', 'description', 'steps', 'status', 'environment_id'}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_scenario(sc_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(sc_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE api_scenarios SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_scenario(sc_id)
    finally:
        pass  # shared cached conn


def delete_scenario(sc_id: str, permanent: bool = False) -> bool:
    """删除场景。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            conn.execute("DELETE FROM api_scenarios WHERE id = ?", (sc_id,))
        else:
            conn.execute(
                "UPDATE api_scenarios SET deleted = 1, deleted_at = ? WHERE id = ? AND (deleted IS NULL OR deleted = 0)",
                (time.time(), sc_id),
            )
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def list_trash_scenarios(limit: int = 100) -> List[dict]:
    """列出回收站中的场景。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_scenarios WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['steps'] = json.loads(d.get('steps') or '[]')
            except:
                d['steps'] = []
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def restore_scenario(sc_id: str) -> bool:
    """从回收站恢复场景。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE api_scenarios SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1", (sc_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# Mock 服务
# ════════════════════════════════════════════════════════════

def create_mock_service(
    name: str,
    method: str = "GET",
    path: str = "",
    response_code: int = 200,
    response_headers: Optional[dict] = None,
    response_body: str = "{}",
    delay_ms: int = 0,
) -> dict:
    """创建 Mock 服务。"""
    mock_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO mock_services (id, name, method, path, response_code,
                response_headers, response_body, delay_ms, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (mock_id, name, method.upper(), path, response_code,
              json.dumps(response_headers or {}), response_body, delay_ms, now, now))
        conn.commit()
        return get_mock_service(mock_id)
    finally:
        pass  # shared cached conn


def get_mock_service(mock_id: str) -> Optional[dict]:
    """获取 Mock 服务详情。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM mock_services WHERE id = ?", (mock_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['response_headers'] = json.loads(d.get('response_headers') or '{}')
        except:
            d['response_headers'] = {}
        return d
    finally:
        pass  # shared cached conn


def list_mock_services(limit: int = 100) -> List[dict]:
    """列出所有 Mock 服务。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM mock_services WHERE (deleted IS NULL OR deleted = 0) ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['response_headers'] = json.loads(d.get('response_headers') or '{}')
            except:
                d['response_headers'] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_mock_service(mock_id: str, **kwargs) -> Optional[dict]:
    """更新 Mock 服务。"""
    allowed = {'name', 'method', 'path', 'response_code', 'response_headers',
               'response_body', 'delay_ms', 'enabled'}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if isinstance(v, dict):
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_mock_service(mock_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(mock_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE mock_services SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_mock_service(mock_id)
    finally:
        pass  # shared cached conn


def delete_mock_service(mock_id: str, permanent: bool = False) -> bool:
    """删除 Mock 服务。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            conn.execute("DELETE FROM mock_services WHERE id = ?", (mock_id,))
        else:
            conn.execute(
                "UPDATE mock_services SET deleted = 1, deleted_at = ? WHERE id = ? AND (deleted IS NULL OR deleted = 0)",
                (time.time(), mock_id),
            )
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def list_trash_mocks(limit: int = 100) -> List[dict]:
    """列出回收站中的 Mock 服务。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM mock_services WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['response_headers'] = json.loads(d.get('response_headers') or '{}')
            except:
                d['response_headers'] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def restore_mock(mock_id: str) -> bool:
    """从回收站恢复 Mock 服务。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE mock_services SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1", (mock_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 环境管理
# ════════════════════════════════════════════════════════════

def create_environment(
    name: str,
    description: str = "",
    base_url: str = "",
    headers: Optional[dict] = None,
    variables: Optional[dict] = None,
) -> dict:
    """创建环境。"""
    env_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO environments (id, name, description, base_url, headers, variables, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (env_id, name, description, base_url,
              json.dumps(headers or {}), json.dumps(variables or {}), now, now))
        conn.commit()
        return get_environment(env_id)
    finally:
        pass  # shared cached conn


def get_environment(env_id: str) -> Optional[dict]:
    """获取环境详情。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM environments WHERE id = ?", (env_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ('headers', 'variables'):
            try:
                d[key] = json.loads(d.get(key) or '{}')
            except:
                d[key] = {}
        return d
    finally:
        pass  # shared cached conn


def list_environments(limit: int = 100) -> List[dict]:
    """列出所有环境。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM environments ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('headers', 'variables'):
                try:
                    d[key] = json.loads(d.get(key) or '{}')
                except:
                    d[key] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_environment(env_id: str, **kwargs) -> Optional[dict]:
    """更新环境。"""
    allowed = {'name', 'description', 'base_url', 'headers', 'variables', 'is_default'}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if isinstance(v, dict):
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_environment(env_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(env_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE environments SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_environment(env_id)
    finally:
        pass  # shared cached conn


def delete_environment(env_id: str) -> bool:
    """删除环境。"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM environments WHERE id = ?", (env_id,))
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 断言规则管理
# ════════════════════════════════════════════════════════════

def create_assertion_rule(
    name: str,
    rule_type: str = "text",
    target: str = "",
    expression: str = "",
    expected: str = "",
    description: str = "",
) -> dict:
    """创建断言规则。"""
    rule_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO assertion_rules (id, name, rule_type, target, expression, expected, description, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (rule_id, name, rule_type, target, expression, expected, description, now))
        conn.commit()
        return get_assertion_rule(rule_id)
    finally:
        pass  # shared cached conn


def get_assertion_rule(rule_id: str) -> Optional[dict]:
    """获取断言规则详情。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM assertion_rules WHERE id = ?", (rule_id,)).fetchone()
        return dict(row) if row else None
    finally:
        pass  # shared cached conn


def list_assertion_rules(limit: int = 100) -> List[dict]:
    """列出所有断言规则。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM assertion_rules ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def delete_assertion_rule(rule_id: str) -> bool:
    """删除断言规则。"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM assertion_rules WHERE id = ?", (rule_id,))
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 接口导入（Postman/Swagger）
# ════════════════════════════════════════════════════════════

def import_from_postman(data: dict) -> dict:
    """从 Postman Collection JSON 导入接口定义。"""
    imported = 0
    errors = []
    items = data.get('item', []) if isinstance(data, dict) else []

    def walk_items(items_list):
        result = []
        for item in items_list:
            if 'item' in item:  # folder
                result.extend(walk_items(item['item']))
            elif 'request' in item:
                result.append(item)
        return result

    try:
        all_requests = walk_items(items)
        for req in all_requests:
            request = req.get('request', {})
            name = req.get('name', request.get('name', 'unnamed'))
            method = request.get('method', 'GET')
            url_obj = request.get('url', {})
            if isinstance(url_obj, dict):
                path = '/'.join(url_obj.get('path', []))
                query_params = {}
                for qp in url_obj.get('query', []):
                    if isinstance(qp, dict):
                        query_params[qp.get('key', '')] = qp.get('value', '')
            else:
                path = str(url_obj)
                query_params = {}

            body = request.get('body', {})
            body_content = ''
            if isinstance(body, dict):
                raw = body.get('raw', '')
                body_content = str(raw) if raw else ''

            headers = {}
            for h in request.get('header', []):
                if isinstance(h, dict):
                    headers[h.get('key', '')] = h.get('value', '')

            create_api_definition(
                name=name,
                method=method,
                path=path,
                request_headers=headers,
                request_params=query_params,
                request_body=body_content,
                tags=['postman-import'],
            )
            imported += 1
    except Exception as e:
        errors.append(str(e))

    return {'imported': imported, 'errors': errors}


def import_from_swagger(data: dict) -> dict:
    """从 Swagger/OpenAPI JSON 导入接口定义。"""
    imported = 0
    errors = []
    try:
        paths = data.get('paths', {})
        for path, methods in paths.items():
            for method, op in methods.items():
                if method.lower() not in ('get', 'post', 'put', 'delete', 'patch', 'head', 'options'):
                    continue
                name = op.get('summary', op.get('operationId', f"{method.upper()} {path}"))
                parameters = {}
                for p in op.get('parameters', []):
                    if isinstance(p, dict):
                        parameters[p.get('name', '')] = p.get('schema', {}).get('default', '') if isinstance(p.get('schema'), dict) else ''

                request_body = ''
                rb = op.get('requestBody', {})
                if isinstance(rb, dict):
                    content = rb.get('content', {})
                    if 'application/json' in content:
                        schema = content['application/json'].get('schema', {})
                        request_body = json.dumps(schema, ensure_ascii=False, indent=2) if schema else ''

                tags = op.get('tags', [])
                create_api_definition(
                    name=name,
                    method=method.upper(),
                    path=path,
                    description=op.get('description', ''),
                    request_params=parameters,
                    request_body=request_body,
                    tags=tags,
                )
                imported += 1
    except Exception as e:
        errors.append(str(e))

    return {'imported': imported, 'errors': errors}


# ════════════════════════════════════════════════════════════
# 接口调试
# ════════════════════════════════════════════════════════════

def debug_api_call(
    method: str = "GET",
    url: str = "",
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    body: str = "",
    body_type: str = "json",
    timeout: int = 30,
) -> dict:
    """执行接口调试请求。"""
    import time as t
    start = t.time()
    result = {
        'method': method.upper(),
        'url': url,
        'success': False,
        'response_code': 0,
        'response_data': '',
        'duration_ms': 0,
        'error': '',
    }
    try:
        import urllib.request
        import urllib.parse

        # 构建 URL
        if params:
            qs = urllib.parse.urlencode(params)
            sep = '&' if '?' in url else '?'
            url = f"{url}{sep}{qs}"

        # 构建请求
        req_headers = dict(headers or {})
        data_bytes = None
        if body and method.upper() in ('POST', 'PUT', 'PATCH'):
            data_bytes = body.encode('utf-8')
            if body_type == 'json' and 'Content-Type' not in req_headers:
                req_headers['Content-Type'] = 'application/json'

        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_data = resp.read().decode('utf-8', errors='replace')
                result.update({
                    'success': True,
                    'response_code': resp.status,
                    'response_data': resp_data[:5000],
                })
        except urllib.error.HTTPError as e:
            body_data = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else ''
            result.update({
                'response_code': e.code,
                'response_data': body_data[:5000],
                'error': f'HTTP {e.code}: {e.reason}',
            })
        except Exception as e:
            result['error'] = str(e)

        result['duration_ms'] = round((t.time() - start) * 1000, 2)

        # 记录调试日志
        _log_debug_call(case_id=None, method=method.upper(), path=url,
                       request_data=json.dumps({'headers': headers, 'params': params, 'body': body}),
                       response_code=result['response_code'], response_data=result['response_data'],
                       duration_ms=result['duration_ms'], success=result['success'], error=result['error'])
        return result
    except Exception as e:
        result['error'] = str(e)
        result['duration_ms'] = round((t.time() - start) * 1000, 2)
        _log_debug_call(case_id=None, method=method.upper(), path=url,
                       request_data='', response_code=0, response_data='',
                       duration_ms=result['duration_ms'], success=False, error=str(e))
        return result


def _log_debug_call(case_id, method, path, request_data, response_code,
                    response_data, duration_ms, success, error) -> None:
    """记录调试日志。"""
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO api_debug_logs (id, case_id, method, path, request_data,
                response_code, response_data, duration_ms, success, error, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (str(uuid.uuid4()), case_id, method, path, request_data,
              response_code, response_data, duration_ms, 1 if success else 0, error, time.time()))
        conn.commit()
        pass  # shared cached conn
    except:
        pass


def list_debug_logs(limit: int = 100) -> List[dict]:
    """列出调试日志。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_debug_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['request_data'] = json.loads(d.get('request_data') or '{}')
            except:
                pass
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def clear_debug_logs() -> int:
    """清空调试日志。"""
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM api_debug_logs")
        conn.commit()
        return cur.rowcount
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 场景执行
# ════════════════════════════════════════════════════════════

def execute_scenario(scenario_id: str, environment_id: Optional[str] = None) -> dict:
    """执行场景中的各接口用例。"""
    scenario = get_scenario(scenario_id)
    if not scenario:
        return {'success': False, 'error': '场景不存在'}

    env = None
    if environment_id:
        env = get_environment(environment_id)
    elif scenario.get('environment_id'):
        env = get_environment(scenario['environment_id'])

    steps = scenario.get('steps', [])
    results = []
    all_success = True

    for step in sorted(steps, key=lambda x: x.get('order', 0)):
        if not step.get('enabled', True):
            continue
        case_id = step.get('case_id')
        case = get_api_test_case(case_id) if case_id else None
        if not case:
            results.append({
                'step': step.get('order', 0),
                'case_id': case_id,
                'success': False,
                'error': '用例不存在',
            })
            all_success = False
            continue

        # 构建完整 URL
        base_url = env.get('base_url', '') if env else ''
        path = case.get('path', '')
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}" if base_url else path

        result = debug_api_call(
            method=case.get('method', 'GET'),
            url=url,
            headers=case.get('request_headers', {}),
            params=case.get('request_params', {}),
            body=case.get('request_body', ''),
            timeout=case.get('timeout', 30),
        )
        results.append({
            'step': step.get('order', 0),
            'case_id': case_id,
            'case_name': case.get('name', ''),
            'method': case.get('method', ''),
            'url': url,
            'success': result['success'],
            'response_code': result['response_code'],
            'duration_ms': result['duration_ms'],
            'error': result.get('error', ''),
        })
        if not result['success']:
            all_success = False

    return {
        'scenario_id': scenario_id,
        'scenario_name': scenario.get('name', ''),
        'success': all_success,
        'total_steps': len(results),
        'passed': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'results': results,
    }
