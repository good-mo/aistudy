# app/services/defect_service.py
"""缺陷业务逻辑层（Phase 3 重构）。"""
import time
import json
from typing import Any, Dict, List, Optional

from app.repositories.defect_repo import DefectRepo


class DefectService:
    """缺陷管理服务。"""

    def create(self, data: dict) -> dict:
        """创建缺陷。"""
        return DefectRepo.create(data)

    def get(self, defect_id: str) -> Optional[dict]:
        """获取缺陷。"""
        return DefectRepo.get_by_id(defect_id)

    def update(self, defect_id: str, data: dict) -> Optional[dict]:
        """更新缺陷。"""
        updates = dict(data)
        updates["updated_at"] = time.time()
        return DefectRepo.update(defect_id, updates)

    def list(self, status: str = "", severity: str = "", limit: int = 100,
             offset: int = 0) -> tuple:
        """分页查询缺陷。"""
        where = ["(deleted IS NULL OR deleted = 0)"]
        params = []
        if status:
            where.append("status = ?")
            params.append(status)
        if severity:
            where.append("severity = ?")
            params.append(severity)

        where_sql = " AND ".join(where)
        count_row = DefectRepo.query_one(
            f"SELECT COUNT(*) as cnt FROM defects WHERE {where_sql}",
            tuple(params),
        )
        total = count_row["cnt"] if count_row else 0

        rows = DefectRepo.query_all(
            f"SELECT * FROM defects WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            tuple(params + [limit, offset]),
        )
        return rows, total

    def get_stats(self) -> dict:
        """获取缺陷统计。"""
        stats = {"total": 0, "by_status": {}, "by_severity": {}}
        total_row = DefectRepo.query_one(
            "SELECT COUNT(*) as cnt FROM defects WHERE (deleted IS NULL OR deleted = 0)"
        )
        stats["total"] = total_row["cnt"] if total_row else 0

        for row in DefectRepo.query_all(
            "SELECT status, COUNT(*) as cnt FROM defects GROUP BY status"
        ):
            stats["by_status"][row["status"]] = row["cnt"]

        for row in DefectRepo.query_all(
            "SELECT severity, COUNT(*) as cnt FROM defects GROUP BY severity"
        ):
            stats["by_severity"][row["severity"]] = row["cnt"]
        return stats


defect_service = DefectService()
