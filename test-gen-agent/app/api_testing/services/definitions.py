# app/api_testing/services/definitions.py
"""API 测试definitions服务模块。"""

from app.api_testing.services.common import *


def create_api_definition(
    name: str,
    method: str = "GET",
    path: str = "",
    protocol: str = "HTTP",
    description: str = "",
    request_headers: Optional[dict] = None,
    request_params: Optional[dict] = None,
    request_body: str = "",
    request_body_type: str = "json",
    response_code: str = "200",
    response_headers: Optional[dict] = None,
    response_body: str = "",
    response_body_type: str = "json",
    tags: Optional[list] = None,
) -> dict:
    """创建接口定义。"""
    def_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO api_definitions (
                id, name, method, path, protocol, description,
                request_headers, request_params, request_body, request_body_type,
                response_code, response_headers, response_body, response_body_type,
                tags, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            def_id, name, method.upper(), path, protocol, description,
            json.dumps(request_headers or {}), json.dumps(request_params or {}),
            request_body or '', request_body_type,
            response_code, json.dumps(response_headers or {}), response_body or '', response_body_type,
            json.dumps(tags or []), now, now,
        ))
        conn.commit()
        return get_api_definition(def_id)
    finally:
        pass  # shared cached conn


def get_api_definition(def_id: str) -> Optional[dict]:
    """获取接口定义详情。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM api_definitions WHERE id = ?", (def_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ('request_headers', 'request_params', 'response_headers', 'tags'):
            try:
                d[key] = json.loads(d.get(key) or '{}')
            except:
                d[key] = {}
        return d
    finally:
        pass  # shared cached conn


def list_api_definitions(
    search: str = "",
    method: str = "",
    protocol: str = "",
    limit: int = 100,
) -> List[dict]:
    """列出接口定义。"""
    conn = _get_conn()
    try:
        sql = "SELECT * FROM api_definitions WHERE 1=1"
        params = []
        if search:
            sql += " AND (name LIKE ? OR path LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        if method:
            sql += " AND method = ?"
            params.append(method.upper())
        if protocol:
            sql += " AND protocol = ?"
            params.append(protocol)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('request_headers', 'request_params', 'response_headers', 'tags'):
                try:
                    d[key] = json.loads(d.get(key) or '{}')
                except:
                    d[key] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_api_definition(def_id: str, **kwargs) -> Optional[dict]:
    """更新接口定义。"""
    allowed = {
        'name', 'method', 'path', 'protocol', 'description',
        'request_headers', 'request_params', 'request_body', 'request_body_type',
        'response_code', 'response_headers', 'response_body', 'response_body_type',
        'tags',
    }
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_api_definition(def_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(def_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE api_definitions SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_api_definition(def_id)
    finally:
        pass  # shared cached conn


def delete_api_definition(def_id: str, permanent: bool = False) -> bool:
    """删除接口定义。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            conn.execute("DELETE FROM api_definitions WHERE id = ?", (def_id,))
        else:
            conn.execute(
                "UPDATE api_definitions SET deleted = 1, deleted_at = ? WHERE id = ? AND (deleted IS NULL OR deleted = 0)",
                (time.time(), def_id),
            )
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def list_trash_definitions(limit: int = 100) -> List[dict]:
    """列出回收站中的接口定义。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_definitions WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('request_headers', 'request_params', 'response_headers', 'tags'):
                try:
                    d[key] = json.loads(d.get(key) or '{}')
                except:
                    d[key] = {}
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def restore_definition(def_id: str) -> bool:
    """从回收站恢复接口定义。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE api_definitions SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1", (def_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 接口用例管理
# ════════════════════════════════════════════════════════════

