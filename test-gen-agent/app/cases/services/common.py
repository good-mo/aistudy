# app/cases/services/common.py
"""用例管理共用函数。"""

"""
测试用例高级管理模块
====================
在基础用例库之上提供：
  - 用例关联（接口/场景/性能用例互相关联）
  - 用例脑图视图（树形结构导出）
  - 用例导入/导出（Excel / XMind JSON）
  - 用例评审流程（提交评审/通过/驳回）
  - 用例依赖关系（前置/后置依赖）
  - 用例回收站（软删除/恢复/彻底删除）
  - 用例版本管理（快照/回滚）
  - 用例变更记录（审计日志）
  - 用例关联需求（JIRA/TAPD 工单号）
"""
import json
import os
import sqlite3
import uuid
import time
import csv
import io
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from app.logging_config import get_logger

logger = get_logger(__name__)

# 复用基础库的连接函数
from app.cases.repository import (
    _get_conn as _get_base_conn,
    get_case as _get_base_case,
    update_case as _update_base_case,
    list_cases as _list_base_cases,
)

# 评审状态
REVIEW_STATUS_PENDING = "pending"      # 待评审
REVIEW_STATUS_APPROVED = "approved"    # 已通过
REVIEW_STATUS_REJECTED = "rejected"    # 已驳回
REVIEW_STATUS_NEED_REVISE = "need_revise"  # 需修改

# 变更动作
CHANGE_CREATED = "created"
CHANGE_UPDATED = "updated"
CHANGE_DELETED = "deleted"
CHANGE_RESTORED = "restored"
CHANGE_VERSION_CREATED = "version_created"
CHANGE_VERSION_ROLLED_BACK = "version_rolled_back"
CHANGE_REVIEW_SUBMITTED = "review_submitted"
CHANGE_REVIEW_APPROVED = "review_approved"
CHANGE_REVIEW_REJECTED = "review_rejected"
CHANGE_IMPORTED = "imported"
CHANGE_EXPORTED = "exported"



def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（复用基础库的连接）。"""
    return _get_base_conn()


def _init_management_tables() -> None:
    """初始化高级管理相关的表结构。"""
    conn = _get_conn()
    try:
        # 用例关联表：用例之间的关联关系（接口/场景/性能等）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_relations (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                related_case_id TEXT NOT NULL,
                relation_type TEXT DEFAULT 'related',
                created_at REAL,
                FOREIGN KEY (case_id) REFERENCES test_cases(id),
                FOREIGN KEY (related_case_id) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_relations_case_id
            ON case_relations(case_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_relations_related_id
            ON case_relations(related_case_id)
        """)

        # 用例依赖表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_dependencies (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                depends_on TEXT NOT NULL,
                dep_type TEXT DEFAULT 'before',  -- before=前置, after=后置
                description TEXT DEFAULT '',
                created_at REAL,
                FOREIGN KEY (case_id) REFERENCES test_cases(id),
                FOREIGN KEY (depends_on) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_dependencies_case_id
            ON case_dependencies(case_id)
        """)

        # 用例评审记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_reviews (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                review_status TEXT DEFAULT 'pending',
                reviewer TEXT DEFAULT '',
                comment TEXT DEFAULT '',
                created_at REAL,
                reviewed_at REAL,
                FOREIGN KEY (case_id) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_reviews_case_id
            ON case_reviews(case_id)
        """)

        # 用例版本表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_versions (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                snapshot TEXT NOT NULL,
                created_at REAL,
                created_by TEXT DEFAULT '',
                change_desc TEXT DEFAULT '',
                FOREIGN KEY (case_id) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_versions_case_id
            ON case_versions(case_id)
        """)

        # 用例变更记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_change_logs (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                action TEXT NOT NULL,
                field TEXT DEFAULT '',
                old_value TEXT DEFAULT '',
                new_value TEXT DEFAULT '',
                operator TEXT DEFAULT '',
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_change_logs_case_id
            ON case_change_logs(case_id)
        """)

        # 用例回收站（软删除）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_trash (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                case_data TEXT NOT NULL,
                deleted_at REAL,
                deleted_by TEXT DEFAULT '',
                reason TEXT DEFAULT ''
            )
        """)

        # 用例关联需求表（JIRA/TAPD）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_requirements (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,   -- JIRA/TAPD 工单号
                requirement_type TEXT DEFAULT 'jira',  -- jira/tapd
                requirement_title TEXT DEFAULT '',
                requirement_url TEXT DEFAULT '',
                created_at REAL,
                FOREIGN KEY (case_id) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_requirements_case_id
            ON case_requirements(case_id)
        """)

        conn.commit()
        logger.info("用例高级管理表初始化完成")
    finally:
        pass  # shared cached conn


# 初始化表结构
_init_management_tables()


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════


def _now() -> float:
    return time.time()


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


def _record_change(case_id: str, action: str, field: str = "",
                   old_value: str = "", new_value: str = "",
                   operator: str = "") -> None:
    """记录用例变更日志。"""
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO case_change_logs
               (id, case_id, action, field, old_value, new_value, operator, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (_gen_id(), case_id, action, field, old_value, new_value, operator, _now()),
        )
        conn.commit()
    except Exception as e:
        logger.warning("记录变更日志失败 [case=%s, err=%s]", case_id, e)
    finally:
        pass  # shared cached conn


def _create_version(case_id: str, created_by: str = "", change_desc: str = "") -> int:
    """为用例创建版本快照，返回版本号。"""
    case = _get_base_case(case_id)
    if not case:
        return 0
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT MAX(version) as max_v FROM case_versions WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        version = (row["max_v"] or 0) + 1
        # 序列化快照（排除动态字段）
        snapshot = json.dumps({
            "title": case.get("title", ""),
            "description": case.get("description", ""),
            "source_code": case.get("source_code", ""),
            "test_code": case.get("test_code", ""),
            "file_path": case.get("file_path", ""),
            "tags": case.get("tags", []),
            "status": case.get("status", "draft"),
            "priority": case.get("priority", "P2"),
            "requirement_ref": case.get("requirement_ref", ""),
            "test_type": case.get("test_type", ""),
            "structured_cases": case.get("structured_cases", []),
        }, ensure_ascii=False)
        conn.execute(
            """INSERT INTO case_versions
               (id, case_id, version, snapshot, created_at, created_by, change_desc)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (_gen_id(), case_id, version, snapshot, _now(), created_by, change_desc),
        )
        conn.commit()
        _record_change(case_id, CHANGE_VERSION_CREATED,
                       old_value="", new_value=f"v{version}",
                       operator=created_by, field="version")
        return version
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 1. 用例关联（接口/场景/性能用例互相关联）
# ════════════════════════════════════════════════════════════

