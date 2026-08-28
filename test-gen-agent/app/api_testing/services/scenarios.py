# app/api_testing/services/scenarios.py
"""API 测试scenarios服务模块。"""

from app.api_testing.services.common import *


def create_scenario(
    name: str,
    description: str = "",
    steps: Optional[list] = None,
    environment_id: Optional[str] = None,
) -> dict:
    """创建场景。steps: [{case_id, order, enabled, variables}]"""
    sc_id = str(uuid.uuid4())
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO api_scenarios (id, name, description, steps, environment_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
        """, (sc_id, name, description, json.dumps(steps or []), environment_id, now, now))
        conn.commit()
        return get_scenario(sc_id)
    finally:
        pass  # shared cached conn


def get_scenario(sc_id: str) -> Optional[dict]:
    """获取场景详情。"""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM api_scenarios WHERE id = ?", (sc_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['steps'] = json.loads(d.get('steps') or '[]')
        except:
            d['steps'] = []
        return d
    finally:
        pass  # shared cached conn


def list_scenarios(limit: int = 100) -> List[dict]:
    """列出所有场景。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_scenarios WHERE (deleted IS NULL OR deleted = 0) ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['steps'] = json.loads(d.get('steps') or '[]')
            except:
                d['steps'] = []
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def update_scenario(sc_id: str, **kwargs) -> Optional[dict]:
    """更新场景。"""
    allowed = {'name', 'description', 'steps', 'status', 'environment_id'}
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return get_scenario(sc_id)
    updates.append("updated_at = ?")
    params.append(time.time())
    params.append(sc_id)
    conn = _get_conn()
    try:
        conn.execute(f"UPDATE api_scenarios SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return get_scenario(sc_id)
    finally:
        pass  # shared cached conn


def delete_scenario(sc_id: str, permanent: bool = False) -> bool:
    """删除场景。默认软删除（进入回收站），permanent=True 时彻底删除。"""
    conn = _get_conn()
    try:
        if permanent:
            conn.execute("DELETE FROM api_scenarios WHERE id = ?", (sc_id,))
        else:
            conn.execute(
                "UPDATE api_scenarios SET deleted = 1, deleted_at = ? WHERE id = ? AND (deleted IS NULL OR deleted = 0)",
                (time.time(), sc_id),
            )
        conn.commit()
        return True
    finally:
        pass  # shared cached conn


def list_trash_scenarios(limit: int = 100) -> List[dict]:
    """列出回收站中的场景。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_scenarios WHERE deleted = 1 ORDER BY deleted_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['steps'] = json.loads(d.get('steps') or '[]')
            except:
                d['steps'] = []
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def restore_scenario(sc_id: str) -> bool:
    """从回收站恢复场景。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE api_scenarios SET deleted = 0, deleted_at = NULL WHERE id = ? AND deleted = 1", (sc_id,)
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# Mock 服务
# ════════════════════════════════════════════════════════════


def execute_scenario(scenario_id: str, environment_id: Optional[str] = None) -> dict:
    """执行场景中的各接口用例。"""
    scenario = get_scenario(scenario_id)
    if not scenario:
        return {'success': False, 'error': '场景不存在'}

    env = None
    if environment_id:
        env = get_environment(environment_id)
    elif scenario.get('environment_id'):
        env = get_environment(scenario['environment_id'])

    steps = scenario.get('steps', [])
    results = []
    all_success = True

    for step in sorted(steps, key=lambda x: x.get('order', 0)):
        if not step.get('enabled', True):
            continue
        case_id = step.get('case_id')
        case = get_api_test_case(case_id) if case_id else None
        if not case:
            results.append({
                'step': step.get('order', 0),
                'case_id': case_id,
                'success': False,
                'error': '用例不存在',
            })
            all_success = False
            continue

        # 构建完整 URL
        base_url = env.get('base_url', '') if env else ''
        path = case.get('path', '')
        url = f"{base_url.rstrip('/')}/{path.lstrip('/')}" if base_url else path

        result = debug_api_call(
            method=case.get('method', 'GET'),
            url=url,
            headers=case.get('request_headers', {}),
            params=case.get('request_params', {}),
            body=case.get('request_body', ''),
            timeout=case.get('timeout', 30),
        )
        results.append({
            'step': step.get('order', 0),
            'case_id': case_id,
            'case_name': case.get('name', ''),
            'method': case.get('method', ''),
            'url': url,
            'success': result['success'],
            'response_code': result['response_code'],
            'duration_ms': result['duration_ms'],
            'error': result.get('error', ''),
        })
        if not result['success']:
            all_success = False

    return {
        'scenario_id': scenario_id,
        'scenario_name': scenario.get('name', ''),
        'success': all_success,
        'total_steps': len(results),
        'passed': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success']),
        'results': results,
    }

