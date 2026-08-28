# app/repositories/defect_repo.py
"""缺陷数据访问层（Phase 3 重构）。"""
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from app.repositories.base import BaseRepo
from app.core.database import Database


class DefectRepo(BaseRepo):
    db_name = "defects.db"
    table_name = "defects"

    @classmethod
    def create(cls, data: dict) -> dict:
        """创建缺陷。"""
        defect_id = data.get("id") or uuid.uuid4().hex[:12]
        now = time.time()
        record = {
            "id": defect_id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "severity": data.get("severity", "major"),
            "status": data.get("status", "open"),
            "file_path": data.get("file_path", ""),
            "test_case_id": data.get("test_case_id", ""),
            "error_snippet": data.get("error_snippet", ""),
            "created_at": now,
            "updated_at": now,
            "assignee": data.get("assignee", ""),
            "deleted": 0,
        }

        # Ensure table exists
        conn = Database.get_conn(cls.db_name)
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
                deleted_at REAL,
                deleted_by TEXT DEFAULT '',
                delete_reason TEXT DEFAULT ''
            )
        """)
        conn.commit()

        cls.execute(
            """INSERT INTO defects
               (id, title, description, severity, status, file_path,
                test_case_id, error_snippet, created_at, updated_at, assignee, deleted)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            tuple(record.values())
        )
        return cls.get_by_id(defect_id) or record


# 兼容旧接口
defect_repo = DefectRepo
