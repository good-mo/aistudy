# app/api_testing/services/assertions.py
"""API 测试assertions服务模块。"""

from app.api_testing.services.common import *


def create_assertion_rule(
    name: str,
    rule_type: str = "text",
    target: str = "",
    expression: str = "",
    expected: str = "",
    description: str = "",
) -> dict:
    """创建断言规则。"""
    rule_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO assertion_rules (id, name, rule_type, target, expression, expected, description, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (rule_id, name, rule_type, target, expression, expected, description, now))
        conn.commit()
        return get_assertion_rule(rule_id)
    finally:
        pass  # shared cached conn


def get_assertion_rule(rule_id: str) -> Optional[dict]:
    """获取断言规则详情。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM assertion_rules WHERE id = ?", (rule_id,)).fetchone()
        return dict(row) if row else None
    finally:
        pass  # shared cached conn


def list_assertion_rules(limit: int = 100) -> List[dict]:
    """列出所有断言规则。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM assertion_rules ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def delete_assertion_rule(rule_id: str) -> bool:
    """删除断言规则。"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM assertion_rules WHERE id = ?", (rule_id,))
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 接口导入（Postman/Swagger）
# ════════════════════════════════════════════════════════════

