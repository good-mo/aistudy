# app/api_testing/services/cases.py
"""API 测试cases服务模块。"""

from app.api_testing.services.common import *


def create_api_test_case(
    name: str,
    definition_id: Optional[str] = None,
    method: str = "GET",
    path: str = "",
    request_headers: Optional[dict] = None,
    request_params: Optional[dict] = None,
    request_body: str = "",
    request_body_type: str = "json",
    assertions: Optional[list] = None,
    pre_scripts: Optional[list] = None,
    post_scripts: Optional[list] = None,
    pre_sql: str = "",
    post_sql: str = "",
    variables: Optional[dict] = None,
    environment_id: Optional[str] = None,
    timeout: int = 30,
    retry_count: int = 0,
) -> dict:
    """创建接口测试用例。"""
    case_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO api_test_cases (
                id, name, definition_id, method, path,
                request_headers, request_params, request_body, request_body_type,
                assertions, pre_scripts, post_scripts, pre_sql, post_sql,
                variables, environment_id, timeout, retry_count,
                created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            case_id, name, definition_id, method.upper(), path,
            json.dumps(request_headers or {}), json.dumps(request_params or {}),
            request_body or '', request_body_type,
            json.dumps(assertions or []), json.dumps(pre_scripts or []),
            json.dumps(post_scripts or []), pre_sql or '', post_sql or '',
            json.dumps(variables or {}), environment_id, timeout, retry_count,
            now, now,
        ))
        conn.commit()
        return get_api_test_case(case_id)
    finally:
        pass  # shared cached conn


def get_api_test_case(case_id: str) -> Optional[dict]:
    """获取接口用例详情。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM api_test_cases WHERE id = ?", (case_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ('request_headers', 'request_params', 'assertions',
                     'pre_scripts', 'post_scripts', 'variables'):
            try:
                d[key] = json.loads(d.get(key) or '[]' if key in ('assertions', 'pre_scripts', 'post_scripts') else '{}')
            except:
                d[key] = {} if key in ('request_headers', 'request_params', 'variables') else []
        return d
    finally:
        pass  # shared cached conn


def list_api_test_cases(
    search: str = "",
    definition_id: str = "",
    environment_id: str = "",
    enabled: Optional[bool] = None,
    limit: int = 100,
) -> List[dict]:
    """列出接口用例。"""
    conn = _get_conn()
    try:
        sql = "SELECT * FROM api_test_cases WHERE 1=1"
        params = []
        if search:
            sql += " AND (name LIKE ? OR path LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if definition_id:
            sql += " AND definition_id = ?"
            params.append(definition_id)
        if environment_id:
            sql += " AND environment_id = ?"
            params.append(environment_id)
        if enabled is not None:
            sql += " AND enabled = ?"
            params.append(1 if enabled else 0)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('request_headers', 'request_params', 'assertions',
                         'pre_scripts', 'post_scripts', 'variables'):
                try:
                    d[key] = json.loads(d.get(key) or '[]' if key in ('assertions', 'pre_scripts', 'post_scripts') else '{}')
                except:
                    d[key] = {} if key in ('request_headers', 'request_params', 'variables') else []
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_api_test_case(case_id: str, **kwargs) -> Optional[dict]:
    """更新接口用例。"""
    allowed = {
        'name', 'definition_id', 'method', 'path',
        'request_headers', 'request_params', 'request_body', 'request_body_type',
        'assertions', 'pre_scripts', 'post_scripts', 'pre_sql', 'post_sql',
        'variables', 'environment_id', 'timeout', 'retry_count',
        'enabled', 'status',
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
        return get_api_test_case(case_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(case_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE api_test_cases SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_api_test_case(case_id)
    finally:
        pass  # shared cached conn


def delete_api_test_case(case_id: str, permanent: bool = False) -> bool:
    """删除接口用例。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            conn.execute("DELETE FROM api_test_cases WHERE id = ?", (case_id,))
        else:
            conn.execute(
                "UPDATE api_test_cases SET deleted = 1, deleted_at = ? WHERE id = ? AND (deleted IS NULL OR deleted = 0)",
                (time.time(), case_id),
            )
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def list_trash_cases(limit: int = 100) -> List[dict]:
    """列出回收站中的接口用例。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_test_cases WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            for key in ('request_headers', 'request_params', 'assertions',
                         'pre_scripts', 'post_scripts', 'variables'):
                try:
                    d[key] = json.loads(d.get(key) or '[]' if key in ('assertions', 'pre_scripts', 'post_scripts') else '{}')
                except:
                    d[key] = {} if key in ('request_headers', 'request_params', 'variables') else []
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def restore_case(case_id: str) -> bool:
    """从回收站恢复接口用例。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE api_test_cases SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1", (case_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 场景编排
# ════════════════════════════════════════════════════════════

