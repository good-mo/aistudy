# app/api_testing/services/importer.py
"""API 测试importer服务模块。"""

from app.api_testing.services.common import *


def import_from_postman(data: dict) -> dict:
    """从 Postman Collection JSON 导入接口定义。"""
    imported = 0
    errors = []
    items = data.get('item', []) if isinstance(data, dict) else []

    def walk_items(items_list):
        result = []
        for item in items_list:
            if 'item' in item:  # folder
                result.extend(walk_items(item['item']))
            elif 'request' in item:
                result.append(item)
        return result

    try:
        all_requests = walk_items(items)
        for req in all_requests:
            request = req.get('request', {})
            name = req.get('name', request.get('name', 'unnamed'))
            method = request.get('method', 'GET')
            url_obj = request.get('url', {})
            if isinstance(url_obj, dict):
                path = '/'.join(url_obj.get('path', []))
                query_params = {}
                for qp in url_obj.get('query', []):
                    if isinstance(qp, dict):
                        query_params[qp.get('key', '')] = qp.get('value', '')
            else:
                path = str(url_obj)
                query_params = {}

            body = request.get('body', {})
            body_content = ''
            if isinstance(body, dict):
                raw = body.get('raw', '')
                body_content = str(raw) if raw else ''

            headers = {}
            for h in request.get('header', []):
                if isinstance(h, dict):
                    headers[h.get('key', '')] = h.get('value', '')

            create_api_definition(
                name=name,
                method=method,
                path=path,
                request_headers=headers,
                request_params=query_params,
                request_body=body_content,
                tags=['postman-import'],
            )
            imported += 1
    except Exception as e:
        errors.append(str(e))

    return {'imported': imported, 'errors': errors}


def import_from_swagger(data: dict) -> dict:
    """从 Swagger/OpenAPI JSON 导入接口定义。"""
    imported = 0
    errors = []
    try:
        paths = data.get('paths', {})
        for path, methods in paths.items():
            for method, op in methods.items():
                if method.lower() not in ('get', 'post', 'put', 'delete', 'patch', 'head', 'options'):
                    continue
                name = op.get('summary', op.get('operationId', f"{method.upper()} {path}"))
                parameters = {}
                for p in op.get('parameters', []):
                    if isinstance(p, dict):
                        parameters[p.get('name', '')] = p.get('schema', {}).get('default', '') if isinstance(p.get('schema'), dict) else ''

                request_body = ''
                rb = op.get('requestBody', {})
                if isinstance(rb, dict):
                    content = rb.get('content', {})
                    if 'application/json' in content:
                        schema = content['application/json'].get('schema', {})
                        request_body = json.dumps(schema, ensure_ascii=False, indent=2) if schema else ''

                tags = op.get('tags', [])
                create_api_definition(
                    name=name,
                    method=method.upper(),
                    path=path,
                    description=op.get('description', ''),
                    request_params=parameters,
                    request_body=request_body,
                    tags=tags,
                )
                imported += 1
    except Exception as e:
        errors.append(str(e))

    return {'imported': imported, 'errors': errors}


# ════════════════════════════════════════════════════════════
# 接口调试
# ════════════════════════════════════════════════════════════

