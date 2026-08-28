# app/api_testing/services/environments.py
"""API 测试environments服务模块。"""

from app.api_testing.services.common import *


def create_environment(
    name: str,
    description: str = "",
    base_url: str = "",
    headers: Optional[dict] = None,
    variables: Optional[dict] = None,
) -> dict:
    """创建环境。"""
    env_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO environments (id, name, description, base_url, headers, variables, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (env_id, name, description, base_url,
              json.dumps(headers or {}), json.dumps(variables or {}), now, now))
        conn.commit()
        return get_environment(env_id)
    finally:
        pass  # shared cached conn


def get_environment(env_id: str) -> Optional[dict]:
    """获取环境详情。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM environments WHERE id = ?", (env_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ('headers', 'variables'):
            try:
                d[key] = json.loads(d.get(key) or '{}')
            except:
                d[key] = {}
        return d
    finally:
        pass  # shared cached conn


def list_environments(limit: int = 100) -> List[dict]:
    """列出所有环境。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM environments ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('headers', 'variables'):
                try:
                    d[key] = json.loads(d.get(key) or '{}')
                except:
                    d[key] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_environment(env_id: str, **kwargs) -> Optional[dict]:
    """更新环境。"""
    allowed = {'name', 'description', 'base_url', 'headers', 'variables', 'is_default'}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if isinstance(v, dict):
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_environment(env_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(env_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE environments SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_environment(env_id)
    finally:
        pass  # shared cached conn


def delete_environment(env_id: str) -> bool:
    """删除环境。"""
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM environments WHERE id = ?", (env_id,))
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 断言规则管理
# ════════════════════════════════════════════════════════════

