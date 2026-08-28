# app/api_testing/services/mocks.py
"""API 测试mocks服务模块。"""

from app.api_testing.services.common import *


def create_mock_service(
    name: str,
    method: str = "GET",
    path: str = "",
    response_code: int = 200,
    response_headers: Optional[dict] = None,
    response_body: str = "{}",
    delay_ms: int = 0,
) -> dict:
    """创建 Mock 服务。"""
    mock_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO mock_services (id, name, method, path, response_code,
                response_headers, response_body, delay_ms, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (mock_id, name, method.upper(), path, response_code,
              json.dumps(response_headers or {}), response_body, delay_ms, now, now))
        conn.commit()
        return get_mock_service(mock_id)
    finally:
        pass  # shared cached conn


def get_mock_service(mock_id: str) -> Optional[dict]:
    """获取 Mock 服务详情。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM mock_services WHERE id = ?", (mock_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['response_headers'] = json.loads(d.get('response_headers') or '{}')
        except:
            d['response_headers'] = {}
        return d
    finally:
        pass  # shared cached conn


def list_mock_services(limit: int = 100) -> List[dict]:
    """列出所有 Mock 服务。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM mock_services WHERE (deleted IS NULL OR deleted = 0) ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['response_headers'] = json.loads(d.get('response_headers') or '{}')
            except:
                d['response_headers'] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_mock_service(mock_id: str, **kwargs) -> Optional[dict]:
    """更新 Mock 服务。"""
    allowed = {'name', 'method', 'path', 'response_code', 'response_headers',
               'response_body', 'delay_ms', 'enabled'}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if isinstance(v, dict):
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_mock_service(mock_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(mock_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE mock_services SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_mock_service(mock_id)
    finally:
        pass  # shared cached conn


def delete_mock_service(mock_id: str, permanent: bool = False) -> bool:
    """删除 Mock 服务。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            conn.execute("DELETE FROM mock_services WHERE id = ?", (mock_id,))
        else:
            conn.execute(
                "UPDATE mock_services SET deleted = 1, deleted_at = ? WHERE id = ? AND (deleted IS NULL OR deleted = 0)",
                (time.time(), mock_id),
            )
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def list_trash_mocks(limit: int = 100) -> List[dict]:
    """列出回收站中的 Mock 服务。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM mock_services WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['response_headers'] = json.loads(d.get('response_headers') or '{}')
            except:
                d['response_headers'] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def restore_mock(mock_id: str) -> bool:
    """从回收站恢复 Mock 服务。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE mock_services SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1", (mock_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 环境管理
# ════════════════════════════════════════════════════════════

