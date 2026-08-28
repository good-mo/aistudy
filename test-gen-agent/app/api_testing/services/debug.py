# app/api_testing/services/debug.py
"""API 测试debug服务模块。"""

from app.api_testing.services.common import *


def debug_api_call(
    method: str = "GET",
    url: str = "",
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    body: str = "",
    body_type: str = "json",
    timeout: int = 30,
) -> dict:
    """执行接口调试请求。"""
    import time as t
    start = t.time()
    result = {
        'method': method.upper(),
        'url': url,
        'success': False,
        'response_code': 0,
        'response_data': '',
        'duration_ms': 0,
        'error': '',
    }
    try:
        import urllib.request
        import urllib.parse

        # 构建 URL
        if params:
            qs = urllib.parse.urlencode(params)
            sep = '&' if '?' in url else '?'
            url = f"{url}{sep}{qs}"

        # 构建请求
        req_headers = dict(headers or {})
        data_bytes = None
        if body and method.upper() in ('POST', 'PUT', 'PATCH'):
            data_bytes = body.encode('utf-8')
            if body_type == 'json' and 'Content-Type' not in req_headers:
                req_headers['Content-Type'] = 'application/json'

        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_data = resp.read().decode('utf-8', errors='replace')
                result.update({
                    'success': True,
                    'response_code': resp.status,
                    'response_data': resp_data[:5000],
                })
        except urllib.error.HTTPError as e:
            body_data = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else ''
            result.update({
                'response_code': e.code,
                'response_data': body_data[:5000],
                'error': f'HTTP {e.code}: {e.reason}',
            })
        except Exception as e:
            result['error'] = str(e)

        result['duration_ms'] = round((t.time() - start) * 1000, 2)

        # 记录调试日志
        _log_debug_call(case_id=None, method=method.upper(), path=url,
                       request_data=json.dumps({'headers': headers, 'params': params, 'body': body}),
                       response_code=result['response_code'], response_data=result['response_data'],
                       duration_ms=result['duration_ms'], success=result['success'], error=result['error'])
        return result
    except Exception as e:
        result['error'] = str(e)
        result['duration_ms'] = round((t.time() - start) * 1000, 2)
        _log_debug_call(case_id=None, method=method.upper(), path=url,
                       request_data='', response_code=0, response_data='',
                       duration_ms=result['duration_ms'], success=False, error=str(e))
        return result


def _log_debug_call(case_id, method, path, request_data, response_code,
                    response_data, duration_ms, success, error) -> None:
    """记录调试日志。"""
    try:
        conn = _get_conn()
        conn.execute("""
            INSERT INTO api_debug_logs (id, case_id, method, path, request_data,
                response_code, response_data, duration_ms, success, error, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (str(uuid.uuid4()), case_id, method, path, request_data,
              response_code, response_data, duration_ms, 1 if success else 0, error, time.time()))
        conn.commit()
        pass  # shared cached conn
    except:
        pass


def list_debug_logs(limit: int = 100) -> List[dict]:
    """列出调试日志。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM api_debug_logs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d['request_data'] = json.loads(d.get('request_data') or '{}')
            except:
                pass
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def clear_debug_logs() -> int:
    """清空调试日志。"""
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM api_debug_logs")
        conn.commit()
        return cur.rowcount
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 场景执行
# ════════════════════════════════════════════════════════════

