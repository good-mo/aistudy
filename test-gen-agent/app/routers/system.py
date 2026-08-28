# app/routers/system.py
"""系统级路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Request, WebSocket
from app.core.response import ok, fail
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse

from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["system"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """返回前端控制台 HTML。"""
    import os
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "static")
    index_file = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Test Generation Agent Toolkit</h1><p>API is running.</p>")


@router.get("/health")
async def health():
    """健康检查。"""
    return ok({
        "status": "ok",
        "version": "0.2.0",
        "service": "tga",
    })


@router.get("/api/test-types")
async def api_test_types():
    """返回支持的测试类型。"""
    return JSONResponse({
        "test_types": [
            {"key": "functional", "label": "功能测试", "desc": "验证业务功能正确性"},
            {"key": "api", "label": "接口测试", "desc": "验证 API 请求/响应契约"},
            {"key": "ui", "label": "UI 测试", "desc": "验证用户界面交互"},
            {"key": "performance", "label": "性能测试", "desc": "验证响应时间与吞吐量"},
            {"key": "security", "label": "安全测试", "desc": "验证注入/越权/敏感信息"},
            {"key": "compatibility", "label": "兼容性测试", "desc": "验证跨版本/跨平台"},
            {"key": "reliability", "label": "可靠性测试", "desc": "验证幂等性/容错性"},
        ]
    })


@router.get("/ms")
@router.get("/ms/{full_path:path}")
async def ms_passthrough(full_path: str = ""):
    """MeterSphere 前端路径透传。"""
    return ok({"code": 200, "message": "success", "data": None})


@router.get("/api/debug/logs")
async def api_debug_logs(limit: int = 100, level: Optional[str] = None):
    """调试日志查询。"""
    logs_dir = "logs"
    import os
    if not os.path.isdir(logs_dir):
        return ok({"logs": []})
    files = sorted(os.listdir(logs_dir), reverse=True)
    logs = []
    for f in files[:3]:
        path = os.path.join(logs_dir, f)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                lines = fh.readlines()[-limit:]
                for line in lines:
                    logs.append({"file": f, "line": line.strip()})
        except Exception:
            pass
    return ok({"logs": logs, "total": len(logs)})


@router.delete("/api/debug/logs")
async def api_clear_debug_logs():
    """清空调试日志。"""
    import os
    logs_dir = "logs"
    if not os.path.isdir(logs_dir):
        return ok({"cleared": 0})
    count = 0
    for f in os.listdir(logs_dir):
        path = os.path.join(logs_dir, f)
        try:
            os.remove(path)
            count += 1
        except Exception:
            pass
    return ok({"cleared": count})


@router.get("/api/alerts")
async def api_list_alerts(limit: int = 50, severity: Optional[str] = None):
    """告警列表。"""
    from app.environment.manager import list_alerts
    alerts = list_alerts(limit=limit, severity=severity)
    return ok({"alerts": alerts, "total": len(alerts)})


@router.post("/api/alerts/{alert_id}/resolve")
async def api_resolve_alert(alert_id: str):
    """解决告警。"""
    from app.environment.manager import resolve_alert
    result = resolve_alert(alert_id)
    if not result:
        return JSONResponse({"error": f"告警 {alert_id} 不存在"}, status_code=404)
    return ok({"resolved": True, "alert_id": alert_id})
