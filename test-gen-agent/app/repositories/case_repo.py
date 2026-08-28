# app/repositories/case_repo.py
"""用例数据访问层（Phase 3 重构）。"""
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from app.repositories.base import BaseRepo
from app.core.database import Database


class CaseRepo(BaseRepo):
    db_name = "testcases.db"
    table_name = "test_cases"

    @classmethod
    def create(cls, data: dict) -> dict:
        """创建用例。

        注意：test_cases 表没有独立 test_type 列，
        test_type 存储在 metadata JSON 中。
        """
        case_id = data.get("id") or str(uuid.uuid4())
        now = time.time()

        # 合并 test_type 到 metadata 中
        metadata = data.get("metadata") or "{}"
        if isinstance(metadata, str):
            try:
                metadata_dict = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata_dict = {}
        elif isinstance(metadata, dict):
            metadata_dict = dict(metadata)
        else:
            metadata_dict = {}

        test_type = data.get("test_type", "functional")
        if test_type:
            metadata_dict["test_type"] = test_type

        record = {
            "id": case_id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "source_code": data.get("source_code", ""),
            "test_code": data.get("test_code", ""),
            "file_path": data.get("file_path", ""),
            "tags": json.dumps(data.get("tags", []), ensure_ascii=False),
            "status": data.get("status", "draft"),
            "priority": data.get("priority", "P2"),
            "requirement_ref": data.get("requirement_ref", ""),
            "created_at": now,
            "updated_at": now,
            "last_result": data.get("last_result", ""),
            "metadata": json.dumps(metadata_dict, ensure_ascii=False),
            "structured_cases": json.dumps(data.get("structured_cases", []), ensure_ascii=False),
        }

        # Ensure table exists (无 test_type 列)
        conn = Database.get_conn(cls.db_name)
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
        conn.commit()

        cols = list(record.keys())
        placeholders = ", ".join(["?"] * len(cols))
        sql = f"INSERT INTO test_cases ({', '.join(cols)}) VALUES ({placeholders})"
        cls.execute(sql, tuple(record.values()))
        return cls.get_by_id(case_id) or record

    @classmethod
    def update(cls, case_id: str, data: dict) -> Optional[dict]:
        """更新用例。"""
        updates = dict(data)
        updates["updated_at"] = time.time()

        # 处理 tags
        if "tags" in updates and isinstance(updates["tags"], list):
            updates["tags"] = json.dumps(updates["tags"], ensure_ascii=False)
        if "structured_cases" in updates and isinstance(updates["structured_cases"], list):
            updates["structured_cases"] = json.dumps(updates["structured_cases"], ensure_ascii=False)

        # test_type 合并到 metadata
        if "test_type" in updates:
            test_type = updates.pop("test_type")
            existing = cls.get_by_id(case_id)
            if existing:
                try:
                    meta = json.loads(existing.get("metadata") or "{}")
                except (json.JSONDecodeError, TypeError):
                    meta = {}
                meta["test_type"] = test_type
                updates["metadata"] = json.dumps(meta, ensure_ascii=False)

        # Build SET clause
        allowed = [
            "title", "description", "source_code", "test_code", "file_path",
            "tags", "status", "priority", "requirement_ref",
            "last_result", "metadata", "structured_cases", "updated_at",
        ]
        set_pairs = []
        values = []
        for k, v in updates.items():
            if k in allowed:
                set_pairs.append(f"{k}=?")
                values.append(v)
        if not set_pairs:
            return cls.get_by_id(case_id)
        values.append(case_id)
        sql = f"UPDATE test_cases SET {', '.join(set_pairs)} WHERE id=?"
        cls.execute(sql, tuple(values))
        return cls.get_by_id(case_id)


# 兼容旧接口
case_repo = CaseRepo
