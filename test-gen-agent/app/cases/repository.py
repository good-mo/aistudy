# app/cases/repository.py
"""
测试用例库管理模块
==================
提供用例的 CRUD、标签、状态、搜索等功能，基于 SQLite 持久化。

用例状态: draft(草稿) / review(评审中) / approved(已批准) / deprecated(已废弃)
用例优先级: P0 / P1 / P2 / P3
"""
import json
import os
import sqlite3
import uuid
import time
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

# 变更动作常量
CHANGE_CREATED = "created"
CHANGE_UPDATED = "updated"

logger = get_logger(__name__)

# 用例状态
STATUS_DRAFT = "draft"
STATUS_REVIEW = "review"
STATUS_APPROVED = "approved"
STATUS_DEPRECATED = "deprecated"

VALID_STATUSES = {STATUS_DRAFT, STATUS_REVIEW, STATUS_APPROVED, STATUS_DEPRECATED}

# 用例优先级
PRIORITY_P0 = "P0"
PRIORITY_P1 = "P1"
PRIORITY_P2 = "P2"
PRIORITY_P3 = "P3"

VALID_PRIORITIES = {PRIORITY_P0, PRIORITY_P1, PRIORITY_P2, PRIORITY_P3}

# 统一使用 Database 连接池管理
from app.core.database import Database



def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("testcases.db")


def _init_db() -> None:
    """初始化用例库表结构（使用独立临时连接）。"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_cases (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                source_code TEXT DEFAULT '',
                test_code TEXT DEFAULT '',
                file_path TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                status TEXT DEFAULT 'draft',
                priority TEXT DEFAULT 'P2',
                requirement_ref TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL,
                last_result TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                structured_cases TEXT DEFAULT '[]'
            )
        """)
        # 迁移：为旧数据库补充缺失的列
        _ensure_column(conn, "test_cases", "structured_cases", "TEXT DEFAULT '[]'")
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_test_cases_status ON test_cases(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_test_cases_priority ON test_cases(priority)
        """)
        conn.commit()
    finally:
        # 不关闭共享连接：由 Database 连接池统一管理，避免破坏连接复用
        pass

def _ensure_column(conn, table: str, column: str, definition: str) -> None:
    """确保表中存在指定列，不存在则添加。"""
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cursor.fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except Exception:
        pass


_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """将数据库行转为 dict。"""
    data = dict(row)
    data["tags"] = json.loads(data.get("tags") or "[]")
    data["metadata"] = json.loads(data.get("metadata") or "{}")
    try:
        data["structured_cases"] = json.loads(data.get("structured_cases") or "[]")
    except (json.JSONDecodeError, TypeError):
        data["structured_cases"] = []
    # 从 metadata 中提取 test_type
    if isinstance(data.get("metadata"), dict):
        data["test_type"] = data["metadata"].get("test_type", "")
    if data.get("last_result"):
        try:
            data["last_result"] = json.loads(data["last_result"])
        except (json.JSONDecodeError, TypeError):
            pass  # 保留原始字符串
    return data


def create_case(
    title: str,
    source_code: str = "",
    test_code: str = "",
    file_path: str = "",
    description: str = "",
    tags: Optional[List[str]] = None,
    status: str = STATUS_DRAFT,
    priority: str = PRIORITY_P2,
    requirement_ref: str = "",
    test_type: str = "",
    structured_cases: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """创建新用例。"""
    case_id = uuid.uuid4().hex[:12]
    now = time.time()
    # test_type 存入 metadata
    metadata = {"test_type": test_type} if test_type else {}
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO test_cases
               (id, title, description, source_code, test_code, file_path,
                tags, status, priority, requirement_ref, created_at, updated_at, metadata, structured_cases)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, title, description, source_code, test_code, file_path,
             json.dumps(tags or []), status, priority, requirement_ref, now, now,
             json.dumps(metadata), json.dumps(structured_cases or [], ensure_ascii=False)),
        )
        conn.commit()
        logger.info("用例已创建 [id=%s, title=%s]", case_id, title)
        # 数据变更后主动清空脑图缓存
        try:
            from app.cases.management import invalidate_mindmap_cache
            invalidate_mindmap_cache()
        except Exception:
            pass
        # 记录创建变更
        try:
            from app.cases.management import _record_change, _create_version
            _record_change(case_id, CHANGE_CREATED, field="title", new_value=title)
            _create_version(case_id, created_by="system", change_desc="初始版本")
        except Exception as e:
            logger.warning("记录创建日志失败 [case=%s, err=%s]", case_id, e)
        return get_case(case_id) or {"id": case_id}
    finally:
        pass

def get_case(case_id: str) -> Optional[Dict[str, Any]]:
    """按 ID 获取用例。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM test_cases WHERE id = ? AND status != 'deprecated'", (case_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        pass

def list_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    test_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """列出用例，支持按状态/优先级/标签/关键词/测试类型过滤。"""
    conn = _get_conn()
    try:
        query = "SELECT * FROM test_cases WHERE 1=1"
        params: List = []

        if status and status in VALID_STATUSES:
            query += " AND status = ?"
            params.append(status)
        if priority and priority in VALID_PRIORITIES:
            query += " AND priority = ?"
            params.append(priority)
        if tag:
            query += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')
        if test_type:
            query += " AND metadata LIKE ?"
            params.append(f'%"test_type": "{test_type}"%')
        if search:
            query += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass

def update_case(case_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """更新用例。"""
    existing = get_case(case_id)
    if not existing:
        return None

    allowed_fields = {
        "title", "description", "source_code", "test_code", "file_path",
        "tags", "status", "priority", "requirement_ref", "metadata",
        "last_result", "structured_cases",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not updates:
        return existing

    # JSON 序列化 tags / metadata / structured_cases
    if "tags" in updates and isinstance(updates["tags"], list):
        updates["tags"] = json.dumps(updates["tags"])
    if "metadata" in updates and isinstance(updates["metadata"], dict):
        updates["metadata"] = json.dumps(updates["metadata"])
    if "structured_cases" in updates and isinstance(updates["structured_cases"], list):
        updates["structured_cases"] = json.dumps(updates["structured_cases"], ensure_ascii=False)
    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise ValueError(f"无效状态: {updates['status']}")
    if "priority" in updates and updates["priority"] not in VALID_PRIORITIES:
        raise ValueError(f"无效优先级: {updates['priority']}")

    updates["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [case_id]

    conn = _get_conn()
    try:
        conn.execute(f"UPDATE test_cases SET {set_clause} WHERE id = ?", values)
        conn.commit()
        logger.info("用例已更新 [id=%s, fields=%s]", case_id, list(updates.keys()))
        # 数据变更后主动清空脑图缓存
        try:
            from app.cases.management import invalidate_mindmap_cache
            invalidate_mindmap_cache()
        except Exception:
            pass

        # 自动记录变更日志
        try:
            from app.cases.management import _record_change, _create_version
            for field, new_val in kwargs.items():
                if field in allowed_fields and field not in ("updated_at", "metadata", "last_result"):
                    old_val = existing.get(field, "")
                    if isinstance(old_val, (list, dict)):
                        old_val = json.dumps(old_val, ensure_ascii=False)
                    if isinstance(new_val, (list, dict)):
                        new_val = json.dumps(new_val, ensure_ascii=False)
                    if str(old_val) != str(new_val):
                        _record_change(case_id, CHANGE_UPDATED, field=field,
                                       old_value=str(old_val)[:500], new_value=str(new_val)[:500])
            # 重大字段变更时自动创建版本
            significant_fields = {"title", "source_code", "test_code", "file_path"}
            if any(k in kwargs for k in significant_fields):
                _create_version(case_id, created_by="system", change_desc="自动保存")
        except Exception as e:
            logger.warning("记录变更日志失败 [case=%s, err=%s]", case_id, e)

        return get_case(case_id)
    finally:
        pass

def delete_case(case_id: str) -> bool:
    """删除用例。"""
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM test_cases WHERE id = ?", (case_id,))
        conn.commit()
        deleted = cur.rowcount > 0
        if deleted:
            logger.info("用例已删除 [id=%s]", case_id)
            # 数据变更后主动清空脑图缓存
            try:
                from app.cases.management import invalidate_mindmap_cache
                invalidate_mindmap_cache()
            except Exception:
                pass
        return deleted
    finally:
        pass

def update_case_result(case_id: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新用例的最后执行结果。"""
    return update_case(case_id, last_result=json.dumps(result, ensure_ascii=False))


def get_stats() -> Dict[str, Any]:
    """获取用例库统计信息。"""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM test_cases").fetchone()[0]
        # 一次 GROUP BY 查询代替逐状态/逐优先级 COUNT（消除 N+1）
        by_status = {s: 0 for s in VALID_STATUSES}
        for row in conn.execute("SELECT status, COUNT(*) AS cnt FROM test_cases GROUP BY status"):
            if row["status"] in by_status:
                by_status[row["status"]] = row["cnt"]
        by_priority = {p: 0 for p in VALID_PRIORITIES}
        for row in conn.execute("SELECT priority, COUNT(*) AS cnt FROM test_cases GROUP BY priority"):
            if row["priority"] in by_priority:
                by_priority[row["priority"]] = row["cnt"]
        return {"total": total, "by_status": by_status, "by_priority": by_priority}
    finally:
        pass
