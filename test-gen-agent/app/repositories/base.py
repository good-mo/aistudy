# app/repositories/base.py
"""数据访问层基类：提供统一 CRUD 基础方法。"""
from typing import Any, Dict, List, Optional
from app.core.database import Database


class BaseRepo:
    """数据访问层基类。

    所有 repository 类应继承此类，统一数据库连接和 CRUD 操作。
    """

    db_name: str = "testcases.db"
    table_name: str = ""

    @classmethod
    def get_conn(cls):
        return Database.get_conn(cls.db_name)

    @classmethod
    def query_one(cls, sql: str, params: tuple = ()) -> Optional[dict]:
        conn = cls.get_conn()
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    @classmethod
    def query_all(cls, sql: str, params: tuple = ()) -> List[dict]:
        conn = cls.get_conn()
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    @classmethod
    def execute(cls, sql: str, params: tuple = ()) -> Any:
        conn = cls.get_conn()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor

    @classmethod
    def insert(cls, data: dict) -> int:
        """插入一行，返回 lastrowid。"""
        cols = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        sql = f"INSERT INTO {cls.table_name} ({cols}) VALUES ({placeholders})"
        cursor = cls.execute(sql, tuple(data.values()))
        return cursor.lastrowid

    @classmethod
    def update(cls, record_id: Any, data: dict, id_col: str = "id") -> bool:
        """按 ID 更新。"""
        if not data:
            return False
        sets = ", ".join([f"{k}=?" for k in data.keys()])
        sql = f"UPDATE {cls.table_name} SET {sets} WHERE {id_col}=?"
        params = tuple(data.values()) + (record_id,)
        cursor = cls.execute(sql, params)
        return cursor.rowcount > 0

    @classmethod
    def delete(cls, record_id: Any, id_col: str = "id") -> bool:
        """按 ID 删除。"""
        cursor = cls.execute(
            f"DELETE FROM {cls.table_name} WHERE {id_col}=?",
            (record_id,),
        )
        return cursor.rowcount > 0

    @classmethod
    def get_by_id(cls, record_id: Any, id_col: str = "id") -> Optional[dict]:
        """按 ID 查询。"""
        return cls.query_one(
            f"SELECT * FROM {cls.table_name} WHERE {id_col}=?",
            (record_id,),
        )

    @classmethod
    def count(cls, where: str = "", params: tuple = ()) -> int:
        """统计数量。"""
        sql = f"SELECT COUNT(*) as cnt FROM {cls.table_name}"
        if where:
            sql += f" WHERE {where}"
        row = cls.query_one(sql, params)
        return row["cnt"] if row else 0
