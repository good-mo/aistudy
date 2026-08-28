# app/apitest/module_store.py
"""
接口测试模块树存储
===================
为接口定义 / 场景 / 调试提供模块树（增删改查、数量统计）。
模块数据持久化到 apitest.db 的 modules 表。
"""
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

# 统一使用 Database 连接池管理
from app.core.database import Database

# 模块级缓存连接，避免每次操作新建/关闭 SQLite 连接

def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("apitest.db")


def _init_db() -> None:
    """初始化表结构（使用独立临时连接，不影响共享连接）。"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,          -- definition / scenario / debug / functional
                name TEXT NOT NULL,
                parent_id TEXT DEFAULT 'root',
                pos INTEGER DEFAULT 1,
                project_id TEXT DEFAULT '',
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_modules_scope ON modules(scope)
        """)
        conn.commit()
    finally:
        # 不关闭共享连接：由 Database 连接池统一管理，避免破坏连接复用
        pass


_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def add_module(scope: str, name: str, parent_id: str = "root",
               project_id: str = "") -> Dict[str, Any]:
    """新增模块。"""
    mod_id = uuid.uuid4().hex[:12]
    now = time.time()
    conn = _get_conn()
    conn.execute(
        """INSERT INTO modules
           (id, scope, name, parent_id, pos, project_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (mod_id, scope, name, parent_id, 1, project_id, now, now),
    )
    conn.commit()
    return get_module(mod_id) or {"id": mod_id}


def get_module(mod_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM modules WHERE id = ?", (mod_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_modules(scope: str) -> List[Dict[str, Any]]:
    """列出指定作用域的全部模块。"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM modules WHERE scope = ? ORDER BY pos ASC", (scope,)
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_module(mod_id: str, name: str) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE modules SET name = ?, updated_at = ? WHERE id = ?",
        (name, time.time(), mod_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_module(mod_id: str) -> bool:
    conn = _get_conn()
    cur = conn.execute("DELETE FROM modules WHERE id = ?", (mod_id,))
    conn.commit()
    return cur.rowcount > 0


def count_modules(scope: str) -> int:
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) FROM modules WHERE scope = ?", (scope,)
    ).fetchone()
    return row[0] if row else 0


def build_module_tree(scope: str) -> List[Dict[str, Any]]:
    """构建模块树（含根节点和计数）。"""
    modules = list_modules(scope)
    root = {
        "id": "root",
        "name": "全部模块",
        "type": "MODULE",
        "parentId": "",
        "children": [],
        "count": count_modules(scope),
    }
    for m in modules:
        node = {
            "id": m.get("id", ""),
            "name": m.get("name", ""),
            "type": "MODULE",
            "parentId": m.get("parent_id", "root"),
            "children": [],
            "pos": m.get("pos", 1),
        }
        root["children"].append(node)
    return [root]
