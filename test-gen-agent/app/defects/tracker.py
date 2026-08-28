# app/defects/tracker.py
"""
缺陷跟踪模块
============
测试失败自动记录缺陷，支持状态流转、关联用例、优先级管理。
"""
import json
import os
import sqlite3
import time
import uuid
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 缺陷状态
STATUS_OPEN = "open"
STATUS_IN_PROGRESS = "in_progress"
STATUS_FIXED = "fixed"
STATUS_CLOSED = "closed"
STATUS_WONT_FIX = "wont_fix"

VALID_STATUSES = {STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_FIXED, STATUS_CLOSED, STATUS_WONT_FIX}

# 缺陷严重程度
SEVERITY_BLOCKER = "blocker"
SEVERITY_CRITICAL = "critical"
SEVERITY_MAJOR = "major"
SEVERITY_MINOR = "minor"

VALID_SEVERITIES = {SEVERITY_BLOCKER, SEVERITY_CRITICAL, SEVERITY_MAJOR, SEVERITY_MINOR}

# 统一使用 Database 连接池管理
from app.core.database import Database



def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("defects.db")


def _init_db() -> None:
    """初始化表结构（使用独立临时连接）。"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS defects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                severity TEXT DEFAULT 'major',
                status TEXT DEFAULT 'open',
                file_path TEXT DEFAULT '',
                test_case_id TEXT DEFAULT '',
                error_snippet TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL,
                assignee TEXT DEFAULT '',
                deleted INTEGER DEFAULT 0,
                deleted_at REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_defects_status ON defects(status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_defects_severity ON defects(severity)
        """)
        # 迁移：为历史库补充软删除列
        cols = [r[1] for r in conn.execute("PRAGMA table_info(defects)").fetchall()]
        if "deleted" not in cols:
            conn.execute("ALTER TABLE defects ADD COLUMN deleted INTEGER DEFAULT 0")
            conn.execute("ALTER TABLE defects ADD COLUMN deleted_at REAL")
        conn.commit()
    finally:
        pass  # shared cached conn


_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def create_defect(
    title: str,
    description: str = "",
    severity: str = SEVERITY_MAJOR,
    file_path: str = "",
    test_case_id: str = "",
    error_snippet: str = "",
    assignee: str = "",
) -> Dict[str, Any]:
    """创建新缺陷。"""
    defect_id = uuid.uuid4().hex[:12]
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO defects
               (id, title, description, severity, status, file_path,
                test_case_id, error_snippet, created_at, updated_at, assignee)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (defect_id, title, description, severity, STATUS_OPEN, file_path,
             test_case_id, error_snippet, now, now, assignee),
        )
        conn.commit()
        logger.info("缺陷已创建 [id=%s, title=%s]", defect_id, title)
        return get_defect(defect_id) or {"id": defect_id}
    finally:
        pass  # shared cached conn


def get_defect(defect_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM defects WHERE id = ?", (defect_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        pass  # shared cached conn


def list_defects(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    include_deleted: bool = False,
) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        query = "SELECT * FROM defects WHERE 1=1"
        params: List = []
        if not include_deleted:
            query += " AND (deleted IS NULL OR deleted = 0)"
        if status and status in VALID_STATUSES:
            query += " AND status = ?"
            params.append(status)
        if severity and severity in VALID_SEVERITIES:
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def update_defect(defect_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """更新缺陷。"""
    existing = get_defect(defect_id)
    if not existing:
        return None

    allowed = {"title", "description", "severity", "status", "file_path",
               "test_case_id", "error_snippet", "assignee"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}

    if "status" in updates and updates["status"] not in VALID_STATUSES:
        raise ValueError(f"无效状态: {updates['status']}")
    if "severity" in updates and updates["severity"] not in VALID_SEVERITIES:
        raise ValueError(f"无效严重程度: {updates['severity']}")

    if not updates:
        return existing

    updates["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [defect_id]

    conn = _get_conn()
    try:
        conn.execute(f"UPDATE defects SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return get_defect(defect_id)
    finally:
        pass  # shared cached conn


def delete_defect(defect_id: str, permanent: bool = False) -> bool:
    """删除缺陷。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            cur = conn.execute("DELETE FROM defects WHERE id = ?", (defect_id,))
        else:
            cur = conn.execute(
                "UPDATE defects SET deleted = 1, deleted_at = ? WHERE id = ?",
                (time.time(), defect_id),
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def soft_delete_defect(defect_id: str) -> bool:
    """软删除缺陷，移入回收站。"""
    return delete_defect(defect_id, permanent=False)


def list_trash_defects(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """列出回收站中的缺陷。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM defects WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def count_trash_defects() -> int:
    """统计回收站中缺陷数量。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) FROM defects WHERE deleted = 1").fetchone()
        return row[0] if row else 0
    finally:
        pass  # shared cached conn


def restore_defect(defect_id: str) -> bool:
    """从回收站恢复缺陷。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE defects SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1",
            (defect_id,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def purge_defect(defect_id: str) -> bool:
    """从回收站彻底删除缺陷。"""
    return delete_defect(defect_id, permanent=True)


def auto_create_defect_from_result(
    file_path: str,
    test_result: Dict[str, Any],
    test_case_id: str = "",
) -> Optional[Dict[str, Any]]:
    """
    测试失败时自动创建缺陷。

    Args:
        file_path: 被测文件路径
        test_result: 测试结果 {passed, stdout, stderr}
        test_case_id: 关联的用例 ID
    """
    if test_result.get("passed"):
        return None

    stderr = test_result.get("stderr", "") or ""
    stdout = test_result.get("stdout", "") or ""
    combined = stderr + "\n" + stdout

    # 根据错误类型判断严重程度
    severity = SEVERITY_MAJOR
    if any(k in combined.lower() for k in ("error", "traceback", "failed")):
        severity = SEVERITY_CRITICAL
    if any(k in combined.lower() for k in ("exception", "segmentation")):
        severity = SEVERITY_BLOCKER

    # 提取错误摘要
    title = f"测试失败: {file_path}"
    if "AssertionError" in combined:
        title = f"断言失败: {file_path}"
    elif "ImportError" in combined or "ModuleNotFoundError" in combined:
        title = f"导入错误: {file_path}"
    elif "TypeError" in combined:
        title = f"类型错误: {file_path}"
    elif "SyntaxError" in combined:
        title = f"语法错误: {file_path}"

    return create_defect(
        title=title,
        description=f"测试自动检测到失败。\n\n文件: {file_path}\n\n输出:\n```\n{combined[:2000]}\n```",
        severity=severity,
        file_path=file_path,
        test_case_id=test_case_id,
        error_snippet=combined[:500],
    )


def get_stats() -> Dict[str, Any]:
    """获取缺陷统计。"""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM defects WHERE (deleted IS NULL OR deleted = 0)").fetchone()[0]
        trash = conn.execute("SELECT COUNT(*) FROM defects WHERE deleted = 1").fetchone()[0]
        # 一次 GROUP BY 查询代替逐状态 COUNT（消除 N+1）
        by_status = {s: 0 for s in VALID_STATUSES}
        for row in conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM defects "
            "WHERE (deleted IS NULL OR deleted = 0) GROUP BY status"
        ):
            if row["status"] in by_status:
                by_status[row["status"]] = row["cnt"]
        return {"total": total, "trash": trash, "by_status": by_status}
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════════
# 回收站支持（软删除）
# ════════════════════════════════════════════════════════════════

def _ensure_column(conn, table: str, column: str, definition: str) -> None:
    """确保表中存在指定列，不存在则添加。"""
    try:
        cursor = conn.execute(f"PRAGMA table_info({table})")
        cols = [row[1] for row in cursor.fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except Exception:
        pass


def _init_recycle() -> None:
    conn = _get_conn()
    try:
        _ensure_column(conn, "defects", "deleted", "INTEGER DEFAULT 0")
        _ensure_column(conn, "defects", "deleted_at", "REAL DEFAULT 0")
        conn.commit()
    finally:
        pass  # shared cached conn


_init_recycle()


def trash_defect(defect_id: str, deleted_by: str = "", reason: str = "") -> bool:
    """软删除缺陷到回收站。"""
    existing = get_defect(defect_id)
    if not existing:
        return False
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE defects SET deleted = 1, deleted_at = ?, updated_at = ? WHERE id = ?",
            (time.time(), time.time(), defect_id),
        )
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def recover_defect(defect_id: str) -> bool:
    """从回收站恢复缺陷。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE defects SET deleted = 0, deleted_at = 0, updated_at = ? WHERE id = ? AND deleted = 1",
            (time.time(), defect_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def list_trashed_defects(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """列出回收站中的缺陷。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM defects WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def purge_defect(defect_id: str) -> bool:
    """从回收站彻底删除缺陷。"""
    return delete_defect(defect_id, permanent=True)
