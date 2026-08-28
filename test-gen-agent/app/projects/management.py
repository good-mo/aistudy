"""
项目管理模块
============
提供项目级别的管理功能：
  - 项目 CRUD
  - 项目环境关联
  - 项目成员管理（简化版）
"""
import json
import os
import sqlite3
import uuid
import time
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 统一使用 Database 连接池管理
from app.core.database import Database



def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("projects.db")


def _init_tables() -> None:
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                repo_url TEXT DEFAULT '',
                language TEXT DEFAULT 'python',
                path TEXT DEFAULT '',
                status TEXT DEFAULT 'active',  -- active/archived
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_envs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                env_id TEXT NOT NULL,
                created_at REAL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_members (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT DEFAULT '',
                name TEXT DEFAULT '',
                email TEXT DEFAULT '',
                role TEXT DEFAULT 'member',  -- admin/member/guest
                user_group TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_members_project ON project_members(project_id)
        """)
        conn.commit()
    finally:
        pass  # shared cached conn


_init_tables()


def create_project(name, description="", repo_url="", language="python", path="") -> dict:
    """创建项目。"""
    pid = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO projects (id, name, description, repo_url, language, path, status, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (pid, name, description, repo_url, language, path, 'active', now, now))
        conn.commit()
        return get_project(pid)
    finally:
        pass  # shared cached conn


def get_project(pid: str) -> Optional[dict]:
    """获取项目详情。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        return dict(row) if row else None
    finally:
        pass  # shared cached conn


def list_projects(search="", status="", limit=100) -> List[dict]:
    """列出项目。"""
    conn = _get_conn()
    try:
        sql = "SELECT * FROM projects WHERE 1=1"
        params = []
        if search:
            sql += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def update_project(pid: str, **kwargs) -> Optional[dict]:
    """更新项目。"""
    allowed = {'name', 'description', 'repo_url', 'language', 'path', 'status'}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_project(pid)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(pid)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_project(pid)
    finally:
        pass  # shared cached conn


def delete_project(pid: str) -> bool:
    """删除项目。"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
        conn.execute("DELETE FROM project_envs WHERE project_id = ?", (pid,))
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def get_project_stats(pid: str) -> dict:
    """获取项目统计信息。"""
    conn = _get_conn()
    try:
        env_count = conn.execute(
            "SELECT COUNT(*) FROM project_envs WHERE project_id = ?", (pid,)
        ).fetchone()[0]
        return {'project_id': pid, 'env_count': env_count}
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 项目成员管理
# ════════════════════════════════════════════════════════════

def add_project_member(
    project_id: str,
    user_id: str = "",
    username: str = "",
    name: str = "",
    email: str = "",
    role: str = "member",
    user_group: str = "",
) -> Optional[dict]:
    """添加项目成员。"""
    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id or username),
        ).fetchone()
        if existing:
            return None
        mid = str(uuid.uuid4())
        now = time.time()
        conn.execute("""
            INSERT INTO project_members
            (id, project_id, user_id, username, name, email, role, user_group, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (mid, project_id, user_id or username, username, name or username,
                email, role, user_group, now, now))
        conn.commit()
        return get_project_member(mid)
    finally:
        pass  # shared cached conn


def get_project_member(member_id: str) -> Optional[dict]:
    """获取单个项目成员。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM project_members WHERE id = ?", (member_id,)).fetchone()
        return dict(row) if row else None
    finally:
        pass  # shared cached conn


def list_project_members(project_id: str, keyword: str = "") -> List[dict]:
    """列出项目成员。"""
    conn = _get_conn()
    try:
        sql = "SELECT * FROM project_members WHERE project_id = ?"
        params = [project_id]
        if keyword:
            sql += " AND (username LIKE ? OR name LIKE ? OR email LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])
        sql += " ORDER BY created_at ASC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def update_project_member(member_id: str, **kwargs) -> Optional[dict]:
    """更新项目成员。"""
    allowed = {'username', 'name', 'email', 'role', 'user_group'}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_project_member(member_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(member_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE project_members SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_project_member(member_id)
    finally:
        pass  # shared cached conn


def remove_project_member(project_id: str, user_id: str) -> bool:
    """移除项目成员。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def batch_remove_project_members(project_id: str, user_ids: List[str]) -> int:
    """批量移除项目成员。"""
    count = 0
    for uid in user_ids:
        if remove_project_member(project_id, uid):
            count += 1
    return count
