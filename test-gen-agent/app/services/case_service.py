# app/services/case_service.py
"""用例业务逻辑层（Phase 3 重构）。"""
import json
from typing import Any, Dict, List, Optional

from app.repositories.case_repo import CaseRepo


class CaseService:
    """用例管理服务。"""

    def create(self, data: dict) -> dict:
        """创建用例。"""
        return CaseRepo.create(data)

    def get(self, case_id: str) -> Optional[dict]:
        """获取用例详情。"""
        return CaseRepo.get_by_id(case_id)

    def update(self, case_id: str, data: dict) -> Optional[dict]:
        """更新用例。"""
        return CaseRepo.update(case_id, data)

    def delete(self, case_id: str, soft: bool = True) -> bool:
        """删除用例。"""
        if soft:
            return CaseRepo.update(case_id, {"status": "deleted"}) is not None
        return CaseRepo.delete(case_id)

    def list(self, search: str = "", status: str = "", priority: str = "",
             test_type: str = "", limit: int = 50, offset: int = 0) -> tuple:
        """分页查询用例。"""
        where = ["status != 'deleted'"]
        params = []
        if search:
            where.append("(title LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if status:
            where.append("status = ?")
            params.append(status)
        if priority:
            where.append("priority = ?")
            params.append(priority)
        if test_type:
            where.append("test_type = ?")
            params.append(test_type)

        where_sql = " AND ".join(where)
        count_row = CaseRepo.query_one(
            f"SELECT COUNT(*) as cnt FROM test_cases WHERE {where_sql}",
            tuple(params),
        )
        total = count_row["cnt"] if count_row else 0

        rows = CaseRepo.query_all(
            f"SELECT * FROM test_cases WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        )
        # Parse JSON fields
        for r in rows:
            for field in ["tags", "metadata", "structured_cases"]:
                if field in r and isinstance(r[field], str):
                    try:
                        r[field] = json.loads(r[field])
                    except (json.JSONDecodeError, TypeError):
                        r[field] = []
        return rows, total

    def get_stats(self) -> dict:
        """获取用例统计。"""
        stats = {"total": 0, "by_status": {}, "by_priority": {}}
        total_row = CaseRepo.query_one("SELECT COUNT(*) as cnt FROM test_cases WHERE status != 'deleted'")
        stats["total"] = total_row["cnt"] if total_row else 0

        for row in CaseRepo.query_all(
            "SELECT status, COUNT(*) as cnt FROM test_cases GROUP BY status"
        ):
            stats["by_status"][row["status"]] = row["cnt"]

        for row in CaseRepo.query_all(
            "SELECT priority, COUNT(*) as cnt FROM test_cases GROUP BY priority"
        ):
            stats["by_priority"][row["priority"]] = row["cnt"]
        return stats


case_service = CaseService()
