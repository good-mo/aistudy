# app/api_testing/services/common.py
"""API 测试管理共用函数。"""

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

