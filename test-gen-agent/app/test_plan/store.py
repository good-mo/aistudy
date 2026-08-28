# app/test_plan/store.py
"""测试计划数据存储（SQLite 持久化）。"""

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from app import db as _db


from app.core.database import Database


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("test_plans.db")



def _init_db() -> None:
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_plans (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'prepared',  -- prepared/running/completed/archived
                priority TEXT DEFAULT 'P2',
                module_id TEXT DEFAULT 'root',
                created_by TEXT DEFAULT 'admin',
                created_at REAL,
                updated_at REAL,
                start_time REAL DEFAULT 0,
                end_time REAL DEFAULT 0,
                execution_rate REAL DEFAULT 0,
                pass_rate REAL DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_plan_cases (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                case_type TEXT DEFAULT 'functional',
                status TEXT DEFAULT 'pending',  -- pending/passed/failed/blocked
                execute_time REAL DEFAULT 0,
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_plan_modules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_id TEXT DEFAULT 'root',
                project_id TEXT DEFAULT '',
                pos INTEGER DEFAULT 0,
                created_at REAL
            )
        """)
        conn.commit()
    finally:
        # 不关闭共享连接：由 Database 连接池统一管理，避免破坏连接复用
        pass


_init_db()


class TestPlanStore:
    """测试计划存储。"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or _db.db_path(_db.TEST_PLANS_DB)
        self._lock = threading.RLock()

    def _conn(self) -> sqlite3.Connection:
        """获取数据库连接（统一使用 Database 连接池）。"""
        return Database.get_conn("test_plans.db")


    # ── 测试计划 CRUD ─────────────────────────────────
    def create_plan(self, name: str, description: str = "", priority: str = "P2",
                    module_id: str = "root", created_by: str = "admin") -> Dict[str, Any]:
        plan_id = str(uuid.uuid4())
        now = time.time()
        with self._lock, self._conn() as conn:
            conn.execute(
                """INSERT INTO test_plans (id, name, description, priority, module_id,
                   created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (plan_id, name, description, priority, module_id, created_by, now, now),
            )
        return self.get_plan(plan_id) or {}

    def get_plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock, self._conn() as conn:
            cursor = conn.execute("SELECT * FROM test_plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()
            if not row:
                return None
            plan = dict(row)
            plan["metadata"] = json.loads(plan.get("metadata", "{}"))
            return plan

    def list_plans(self, keyword: str = "", status: str = "",
                   limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        query = "SELECT * FROM test_plans WHERE 1=1"
        params = []
        if keyword:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._lock, self._conn() as conn:
            cursor = conn.execute(query, params)
            plans = []
            for row in cursor.fetchall():
                plan = dict(row)
                plan["metadata"] = json.loads(plan.get("metadata", "{}"))
                plans.append(plan)
            return plans

    def count_plans(self) -> int:
        with self._lock, self._conn() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM test_plans")
            return cursor.fetchone()[0]

    def update_plan(self, plan_id: str, **fields) -> Optional[Dict[str, Any]]:
        allowed = {"name", "description", "status", "priority", "module_id",
                   "start_time", "end_time", "execution_rate", "pass_rate"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_plan(plan_id)
        updates["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [plan_id]
        with self._lock, self._conn() as conn:
            conn.execute(f"UPDATE test_plans SET {set_clause} WHERE id = ?", values)
        return self.get_plan(plan_id)

    def delete_plan(self, plan_id: str) -> bool:
        with self._lock, self._conn() as conn:
            conn.execute("DELETE FROM test_plan_cases WHERE plan_id = ?", (plan_id,))
            cursor = conn.execute("DELETE FROM test_plans WHERE id = ?", (plan_id,))
            return cursor.rowcount > 0

    def archive_plan(self, plan_id: str) -> bool:
        plan = self.update_plan(plan_id, status="archived")
        return plan is not None

    # ── 测试计划用例关联 ──────────────────────────────
    def add_plan_case(self, plan_id: str, case_id: str, case_type: str = "functional") -> Dict[str, Any]:
        rel_id = str(uuid.uuid4())
        now = time.time()
        with self._lock, self._conn() as conn:
            conn.execute(
                """INSERT INTO test_plan_cases (id, plan_id, case_id, case_type, status, created_at)
                   VALUES (?, ?, ?, ?, 'pending', ?)""",
                (rel_id, plan_id, case_id, case_type, now),
            )
        return {"id": rel_id, "plan_id": plan_id, "case_id": case_id,
                "case_type": case_type, "status": "pending"}

    def list_plan_cases(self, plan_id: str) -> List[Dict[str, Any]]:
        with self._lock, self._conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM test_plan_cases WHERE plan_id = ?", (plan_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_plan_case_status(self, rel_id: str, status: str) -> bool:
        with self._lock, self._conn() as conn:
            cursor = conn.execute(
                "UPDATE test_plan_cases SET status = ? WHERE id = ?",
                (status, rel_id),
            )
            return cursor.rowcount > 0

    def remove_plan_case(self, rel_id: str) -> bool:
        with self._lock, self._conn() as conn:
            cursor = conn.execute("DELETE FROM test_plan_cases WHERE id = ?", (rel_id,))
            return cursor.rowcount > 0

    def get_plan_statistics(self, plan_id: str) -> Dict[str, Any]:
        """获取单个测试计划统计（单次查询）。"""
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT "
                "COUNT(*) AS total, "
                "SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passed, "
                "SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed, "
                "SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked, "
                "SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending "
                "FROM test_plan_cases WHERE plan_id = ?", (plan_id,)
            ).fetchone()
        total = row["total"] if row and row["total"] else 0
        passed = row["passed"] if row and row["passed"] else 0
        failed = row["failed"] if row and row["failed"] else 0
        blocked = row["blocked"] if row and row["blocked"] else 0
        pending = row["pending"] if row and row["pending"] else 0
        executed = total - pending
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "blocked": blocked,
            "pending": pending,
            "executionRate": round((executed / total * 100) if total else 0, 1),
            "passRate": round((passed / total * 100) if total else 0, 1),
        }

    def get_plans_statistics(self, plan_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """批量获取多个测试计划的统计（单次查询代替 N+1）。"""
        if not plan_ids:
            return {}
        placeholders = ",".join(["?"] * len(plan_ids))
        with self._lock, self._conn() as conn:
            rows = conn.execute(
                f"SELECT plan_id, "
                f"COUNT(*) AS total, "
                f"SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) AS passed, "
                f"SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed, "
                f"SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked, "
                f"SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending "
                f"FROM test_plan_cases WHERE plan_id IN ({placeholders}) "
                f"GROUP BY plan_id", plan_ids,
            ).fetchall()
        result = {}
        for r in rows:
            total = r["total"] or 0
            passed = r["passed"] or 0
            failed = r["failed"] or 0
            blocked = r["blocked"] or 0
            pending = r["pending"] or 0
            executed = total - pending
            result[r["plan_id"]] = {
                "total": total,
                "passed": passed,
                "failed": failed,
                "blocked": blocked,
                "pending": pending,
                "executionRate": round((executed / total * 100) if total else 0, 1),
                "passRate": round((passed / total * 100) if total else 0, 1),
            }
        return result

    # ── 测试计划模块 ─────────────────────────────────
    def create_module(self, name: str, parent_id: str = "root") -> Dict[str, Any]:
        module_id = str(uuid.uuid4())
        with self._lock, self._conn() as conn:
            conn.execute(
                """INSERT INTO test_plan_modules (id, name, parent_id, created_at)
                   VALUES (?, ?, ?, ?)""",
                (module_id, name, parent_id, time.time()),
            )
        return {"id": module_id, "name": name, "parent_id": parent_id}

    def list_modules(self) -> List[Dict[str, Any]]:
        with self._lock, self._conn() as conn:
            cursor = conn.execute("SELECT * FROM test_plan_modules ORDER BY pos")
            return [dict(row) for row in cursor.fetchall()]

    def delete_module(self, module_id: str) -> bool:
        with self._lock, self._conn() as conn:
            cursor = conn.execute("DELETE FROM test_plan_modules WHERE id = ?", (module_id,))
            return cursor.rowcount > 0


test_plan_store = TestPlanStore()
