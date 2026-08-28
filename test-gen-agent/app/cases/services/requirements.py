from app.cases.services.common import *


def add_case_requirement(case_id: str, requirement_id: str,
                         requirement_type: str = "jira",
                         requirement_title: str = "",
                         requirement_url: str = "") -> Dict[str, Any]:
    """关联需求到用例。"""
    if not _get_base_case(case_id):
        raise ValueError("用例不存在")
    conn = _get_conn()
    try:
        existing = conn.execute(
            """SELECT id FROM case_requirements
               WHERE case_id = ? AND requirement_id = ?""",
            (case_id, requirement_id),
        ).fetchone()
        if existing:
            return {"id": existing["id"], "duplicated": True}
        req_id = _gen_id()
        conn.execute(
            """INSERT INTO case_requirements
               (id, case_id, requirement_id, requirement_type,
                requirement_title, requirement_url, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (req_id, case_id, requirement_id, requirement_type,
             requirement_title, requirement_url, _now()),
        )
        # 同时更新 requirement_ref 字段
        conn.execute("UPDATE test_cases SET requirement_ref = ?, updated_at = ? WHERE id = ?",
                     (requirement_id, _now(), case_id))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_UPDATED, field="requirement",
                           new_value=f"{requirement_type}: {requirement_id}")
        except Exception as e:
            logger.warning("记录需求日志失败 [case=%s, err=%s]", case_id, e)
        return {"id": req_id, "duplicated": False}
    finally:
        pass  # shared cached conn


def remove_case_requirement(case_id: str, requirement_id: str) -> bool:
    """移除需求关联。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM case_requirements WHERE case_id = ? AND requirement_id = ?",
            (case_id, requirement_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def list_case_requirements(case_id: str) -> List[Dict[str, Any]]:
    """列出用例关联的所有需求。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM case_requirements WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn

