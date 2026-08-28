from app.cases.services.common import *


def list_case_versions(case_id: str) -> List[Dict[str, Any]]:
    """列出用例的所有版本。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM case_versions WHERE case_id = ? ORDER BY version DESC",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def get_case_version(case_id: str, version: int) -> Optional[Dict[str, Any]]:
    """获取指定版本。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM case_versions WHERE case_id = ? AND version = ?",
            (case_id, version),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["snapshot"] = json.loads(item.get("snapshot") or "{}")
        return item
    finally:
        pass  # shared cached conn


def rollback_case(case_id: str, version: int, operator: str = "") -> bool:
    """将用例回滚到指定版本。"""
    version_data = get_case_version(case_id, version)
    if not version_data:
        return False
    snapshot = version_data["snapshot"]
    # 记录当前版本
    _create_version(case_id, created_by=operator, change_desc="回滚前自动保存")
    # 恢复快照内容
    _update_base_case(
        case_id,
        title=snapshot.get("title", ""),
        description=snapshot.get("description", ""),
        source_code=snapshot.get("source_code", ""),
        test_code=snapshot.get("test_code", ""),
        file_path=snapshot.get("file_path", ""),
        tags=snapshot.get("tags", []),
        status=snapshot.get("status", "draft"),
        priority=snapshot.get("priority", "P2"),
        requirement_ref=snapshot.get("requirement_ref", ""),
        structured_cases=snapshot.get("structured_cases", []),
    )
    _record_change(case_id, CHANGE_VERSION_ROLLED_BACK, operator=operator,
                   old_value=f"v{version}", new_value="current")
    return True


# ════════════════════════════════════════════════════════════
# 8. 用例变更记录
# ════════════════════════════════════════════════════════════


def list_case_changes(case_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """列出用例的变更记录。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM case_change_logs
               WHERE case_id = ? ORDER BY created_at DESC LIMIT ?""",
            (case_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 9. 用例关联需求（JIRA/TAPD）
# ════════════════════════════════════════════════════════════

