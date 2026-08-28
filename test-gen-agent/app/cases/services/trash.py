from app.cases.services.common import *


def soft_delete_case(case_id: str, deleted_by: str = "",
                     reason: str = "") -> bool:
    """软删除用例：放入回收站。"""
    case = _get_base_case(case_id)
    if not case:
        return False
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO case_trash
               (id, case_id, case_data, deleted_at, deleted_by, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (_gen_id(), case_id, json.dumps(case, ensure_ascii=False),
             _now(), deleted_by, reason),
        )
        # 直接更新状态（避免嵌套连接）
        conn.execute("UPDATE test_cases SET status = ?, updated_at = ? WHERE id = ?",
                     ("deprecated", _now(), case_id))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_DELETED, operator=deleted_by, new_value=reason)
        except Exception as e:
            logger.warning("记录删除日志失败 [case=%s, err=%s]", case_id, e)
        invalidate_mindmap_cache()
        return True
    finally:
        pass  # shared cached conn


def restore_case(case_id: str, operator: str = "") -> bool:
    """从回收站恢复用例。"""
    conn = _get_conn()
    try:
        trash = conn.execute(
            "SELECT * FROM case_trash WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not trash:
            return False
        # 恢复状态为草稿
        conn.execute("UPDATE test_cases SET status = ?, updated_at = ? WHERE id = ?",
                     ("draft", _now(), case_id))
        conn.execute("DELETE FROM case_trash WHERE case_id = ?", (case_id,))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_RESTORED, operator=operator)
        except Exception as e:
            logger.warning("记录恢复日志失败 [case=%s, err=%s]", case_id, e)
        invalidate_mindmap_cache()
        return True
    finally:
        pass  # shared cached conn


def list_trash_cases() -> List[Dict[str, Any]]:
    """列出回收站中的用例。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM case_trash ORDER BY deleted_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            try:
                item["case_data"] = json.loads(item.get("case_data") or "{}")
            except json.JSONDecodeError:
                item["case_data"] = {}
            result.append(item)
        return result
    finally:
        pass  # shared cached conn


def purge_case(case_id: str) -> bool:
    """从回收站彻底删除用例（从主表和回收站都删除）。"""
    from app.cases.repository import delete_case as _delete_hard
    conn = _get_conn()
    try:
        # 删除关联数据
        conn.execute("DELETE FROM case_relations WHERE case_id = ? OR related_case_id = ?",
                     (case_id, case_id))
        conn.execute("DELETE FROM case_dependencies WHERE case_id = ? OR depends_on = ?",
                     (case_id, case_id))
        conn.execute("DELETE FROM case_reviews WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM case_versions WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM case_change_logs WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM case_requirements WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM case_trash WHERE case_id = ?", (case_id,))
        conn.commit()
    finally:
        pass  # shared cached conn
    invalidate_mindmap_cache()
    return _delete_hard(case_id)


# ════════════════════════════════════════════════════════════
# 7. 用例版本管理
# ════════════════════════════════════════════════════════════

