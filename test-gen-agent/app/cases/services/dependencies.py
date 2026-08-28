from app.cases.services.common import *


def add_case_dependency(case_id: str, depends_on: str,
                        dep_type: str = "before",
                        description: str = "") -> Dict[str, Any]:
    """添加用例依赖。dep_type: before=前置依赖, after=后置依赖"""
    if case_id == depends_on:
        raise ValueError("不能依赖自身")
    if not _get_base_case(case_id) or not _get_base_case(depends_on):
        raise ValueError("用例不存在")
    conn = _get_conn()
    try:
        existing = conn.execute(
            """SELECT id FROM case_dependencies
               WHERE case_id = ? AND depends_on = ?""",
            (case_id, depends_on),
        ).fetchone()
        if existing:
            return {"id": existing["id"], "duplicated": True}
        dep_id = _gen_id()
        conn.execute(
            """INSERT INTO case_dependencies
               (id, case_id, depends_on, dep_type, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (dep_id, case_id, depends_on, dep_type, description, _now()),
        )
        conn.commit()
        _record_change(case_id, CHANGE_UPDATED, field="dependency",
                       new_value=f"依赖[{dep_type}]: {depends_on}")
        return {"id": dep_id, "duplicated": False}
    finally:
        pass  # shared cached conn


def remove_case_dependency(case_id: str, depends_on: str) -> bool:
    """移除用例依赖。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM case_dependencies WHERE case_id = ? AND depends_on = ?",
            (case_id, depends_on),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def list_case_dependencies(case_id: str) -> List[Dict[str, Any]]:
    """列出用例的所有依赖。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT d.*, c.title as dep_title
               FROM case_dependencies d
               LEFT JOIN test_cases c ON c.id = d.depends_on
               WHERE d.case_id = ?""",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 6. 用例回收站（软删除）
# ════════════════════════════════════════════════════════════

