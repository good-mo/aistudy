"""
统一数据库连接管理模块（Phase 6：合并后统一使用 tga.db）
=======================
集中管理 SQLite 数据库连接，提供：
  - 线程本地连接池（每个线程独立连接，替代单连接+全局锁）
  - 线程安全（check_same_thread=False + 每线程锁）
  - 事务管理（transaction 上下文管理器）
  - 统一路径解析（全部基于项目根目录）
"""
import os
import sqlite3
import threading
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator, Optional

from app.db import PROJECT_ROOT, db_path as resolve_db_path, resolve_db_name, TGA_DB


# ── 数据库连接管理 ─────────────────────────────────────────────

class Database:
    """统一数据库连接管理器（线程本地连接池）。

    Phase 6：所有业务数据统一存于 tga.db。
    旧模块传入的 "testcases.db"、"auth.db" 等会路由到 tga.db。

    采用「线程本地连接」方案，解决原「单连接+全局锁」的串行化瓶颈：
      - 每个线程持有独立 sqlite3.Connection + 独立锁，读写互不阻塞
      - 同一线程内连接复用（避免频繁打开/关闭）
      - 不同线程之间互不干扰，由 SQLite WAL 模式保证并发读安全

    用法:
        conn = Database.get_conn("testcases.db")
        with Database.transaction("testcases.db") as conn:
            conn.execute("INSERT INTO ...", ...)
    """

    # 线程本地存储：每个线程独立维护连接和锁
    _local = threading.local()
    # 全局记录所有已创建的连接（用于 close_all）
    _all_conns: dict = {}
    _lock = threading.RLock()

    @classmethod
    def get_conn(cls, db_name: str) -> sqlite3.Connection:
        """获取当前线程对应的连接。同一线程内连接复用。"""
        real_name = resolve_db_name(db_name)
        # 初始化线程本地状态
        if not hasattr(cls._local, "_conns"):
            cls._local._conns = {}
            cls._local._locks = {}
        conn = cls._local._conns.get(real_name)
        if conn is None or cls._is_closed(conn):
            conn = cls._create_conn(real_name)
            cls._local._conns[real_name] = conn
            cls._local._locks[real_name] = threading.RLock()
            with cls._lock:
                cls._all_conns.setdefault(real_name, set()).add(conn)
        return conn

    @classmethod
    def get_lock(cls, db_name: str) -> threading.RLock:
        """获取当前线程对应数据库的锁。"""
        cls.get_conn(db_name)  # 确保已初始化
        return cls._local._locks.get(resolve_db_name(db_name))

    @classmethod
    def _create_conn(cls, real_name: str) -> sqlite3.Connection:
        """创建新数据库连接并配置。"""
        path = resolve_db_path(real_name)
        conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    @staticmethod
    def _is_closed(conn: sqlite3.Connection) -> bool:
        """检查连接是否已关闭。"""
        try:
            conn.execute("SELECT 1")
            return False
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            return True

    @classmethod
    @contextmanager
    def transaction(cls, db_name: str) -> Iterator[sqlite3.Connection]:
        """事务上下文管理器：自动 commit/rollback。"""
        real_name = resolve_db_name(db_name)
        conn = cls.get_conn(real_name)
        lock = cls.get_lock(real_name)
        with lock:
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    @classmethod
    def close_all(cls) -> None:
        """关闭所有连接（用于测试或应用退出）。"""
        with cls._lock:
            for real_name, conns in cls._all_conns.items():
                for conn in conns:
                    try:
                        conn.close()
                    except Exception:
                        pass
            cls._all_conns.clear()
            # 清空线程本地状态
            if hasattr(cls._local, "_conns"):
                cls._local._conns = {}
            if hasattr(cls._local, "_locks"):
                cls._local._locks = {}


# ── 向后兼容：获取连接（各模块逐步迁移）──────────────────────

def get_conn(db_name: str = "testcases.db") -> sqlite3.Connection:
    """兼容旧调用方式，获取连接。"""
    return Database.get_conn(db_name)


def execute(db_name: str, sql: str, params: tuple = ()) -> sqlite3.Cursor:
    """便捷执行单条 SQL（自动提交）。"""
    real_name = resolve_db_name(db_name)
    conn = Database.get_conn(real_name)
    with Database.get_lock(real_name):
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor


def query_one(db_name: str, sql: str, params: tuple = ()) -> Optional[dict]:
    """查询单行结果。"""
    real_name = resolve_db_name(db_name)
    conn = Database.get_conn(real_name)
    with Database.get_lock(real_name):
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def query_all(db_name: str, sql: str, params: tuple = ()) -> list:
    """查询多行结果。"""
    real_name = resolve_db_name(db_name)
    conn = Database.get_conn(real_name)
    with Database.get_lock(real_name):
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


# ── 便捷导入 ────────────────────────────────────────────────

__all__ = [
    "Database",
    "get_conn",
    "execute",
    "query_one",
    "query_all",
    "resolve_db_path",
    "resolve_db_name",
    "TGA_DB",
]
