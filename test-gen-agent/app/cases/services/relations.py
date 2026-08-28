from app.cases.services.common import *


def add_case_relation(case_id: str, related_case_id: str,
                      relation_type: str = "related") -> Dict[str, Any]:
    """为用例添加关联。relation_type: related/interface/scenario/performance"""
    if case_id == related_case_id:
        raise ValueError("不能关联自身")
    if not _get_base_case(case_id) or not _get_base_case(related_case_id):
        raise ValueError("用例不存在")
    conn = _get_conn()
    try:
        existing = conn.execute(
            """SELECT id FROM case_relations
               WHERE case_id = ? AND related_case_id = ? AND relation_type = ?""",
            (case_id, related_case_id, relation_type),
        ).fetchone()
        if existing:
            return {"id": existing["id"], "duplicated": True}
        rel_id = _gen_id()
        conn.execute(
            """INSERT INTO case_relations (id, case_id, related_case_id, relation_type, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (rel_id, case_id, related_case_id, relation_type, _now()),
        )
        conn.commit()
        _record_change(case_id, CHANGE_UPDATED, field="relation",
                       new_value=f"关联[{relation_type}]: {related_case_id}")
        return {"id": rel_id, "duplicated": False}
    finally:
        pass  # shared cached conn


def remove_case_relation(case_id: str, related_case_id: str,
                         relation_type: str = "related") -> bool:
    """移除用例关联。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """DELETE FROM case_relations
               WHERE case_id = ? AND related_case_id = ? AND relation_type = ?""",
            (case_id, related_case_id, relation_type),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def list_case_relations(case_id: str) -> List[Dict[str, Any]]:
    """列出用例的所有关联。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT r.*, c.title as related_title
               FROM case_relations r
               LEFT JOIN test_cases c ON c.id = r.related_case_id
               WHERE r.case_id = ?""",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 2. 用例脑图视图
# ════════════════════════════════════════════════════════════

_mindmap_cache: Dict[str, tuple] = {}  # cache_key -> (timestamp, data)
_MINDMAP_CACHE_TTL = 10.0  # 秒

