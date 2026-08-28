from app.cases.services.common import *


def submit_for_review(case_id: str, reviewer: str = "",
                      comment: str = "") -> Dict[str, Any]:
    """提交用例进入评审流程。"""
    case = _get_base_case(case_id)
    if not case:
        raise ValueError("用例不存在")
    conn = _get_conn()
    try:
        rev_id = _gen_id()
        conn.execute(
            """INSERT INTO case_reviews
               (id, case_id, review_status, reviewer, comment, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (rev_id, case_id, REVIEW_STATUS_PENDING, reviewer, comment, _now()),
        )
        conn.commit()
        # 更新用例状态为评审中
        _update_base_case(case_id, status="review")
        _record_change(case_id, CHANGE_REVIEW_SUBMITTED, operator=reviewer,
                       new_value=comment)
        return {"id": rev_id, "case_id": case_id, "review_status": REVIEW_STATUS_PENDING}
    finally:
        pass  # shared cached conn


def approve_review(case_id: str, reviewer: str = "", comment: str = "") -> Dict[str, Any]:
    """通过评审。"""
    conn = _get_conn()
    try:
        conn.execute(
            """UPDATE case_reviews
               SET review_status = ?, reviewer = ?, comment = ?, reviewed_at = ?
               WHERE case_id = ?""",
            (REVIEW_STATUS_APPROVED, reviewer, comment, _now(), case_id),
        )
        # 直接更新状态（避免嵌套连接）
        conn.execute("UPDATE test_cases SET status = ?, updated_at = ? WHERE id = ?",
                     ("approved", _now(), case_id))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_REVIEW_APPROVED, operator=reviewer)
        except Exception as e:
            logger.warning("记录评审日志失败 [case=%s, err=%s]", case_id, e)
        return {"case_id": case_id, "review_status": REVIEW_STATUS_APPROVED}
    finally:
        pass  # shared cached conn


def reject_review(case_id: str, reviewer: str = "",
                  comment: str = "") -> Dict[str, Any]:
    """驳回评审。"""
    conn = _get_conn()
    try:
        conn.execute(
            """UPDATE case_reviews
               SET review_status = ?, reviewer = ?, comment = ?, reviewed_at = ?
               WHERE case_id = ?""",
            (REVIEW_STATUS_REJECTED, reviewer, comment, _now(), case_id),
        )
        # 直接更新状态（避免嵌套连接）
        conn.execute("UPDATE test_cases SET status = ?, updated_at = ? WHERE id = ?",
                     ("draft", _now(), case_id))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_REVIEW_REJECTED, operator=reviewer,
                           new_value=comment)
        except Exception as e:
            logger.warning("记录驳回日志失败 [case=%s, err=%s]", case_id, e)
        return {"case_id": case_id, "review_status": REVIEW_STATUS_REJECTED}
    finally:
        pass  # shared cached conn


def get_case_reviews(case_id: str) -> List[Dict[str, Any]]:
    """获取用例的评审记录。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM case_reviews WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 5. 用例依赖关系
# ════════════════════════════════════════════════════════════

