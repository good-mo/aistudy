# app/test_plan/router_system.py
"""系统设置 API 路由。"""

import json
import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

system_router = APIRouter(tags=["system"])


# ── 用户组管理 ────────────────────────────────────────
@system_router.get("/system/user-group/list")
async def user_group_list():
    """获取用户组列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {
            "id": "admin",
            "name": "管理员",
            "description": "系统管理员",
            "scope": "SYSTEM",
            "type": "BUILT_IN",
        },
        {
            "id": "user",
            "name": "普通用户",
            "description": "普通用户",
            "scope": "SYSTEM",
            "type": "BUILT_IN",
        },
    ]})


# ── 模板管理 ──────────────────────────────────────────
@system_router.get("/template/list/{project_id}/{type}")
async def template_list(project_id: str, type: str):
    """获取模板列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {
            "id": "default",
            "name": "默认模板",
            "type": type,
            "enable": True,
            "projectId": project_id,
        }
    ]})


@system_router.get("/template/option/{project_id}/{type}")
async def template_option(project_id: str, type: str):
    """获取模板选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "default", "name": "默认模板"}
    ]})


# ── 资源池管理 ────────────────────────────────────────
@system_router.get("/resource/pool/list")
async def resource_pool_list():
    """获取资源池列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# ── 插件管理 ─────────────────────────────────────────
@system_router.get("/system/plugin/list")
async def plugin_list():
    """获取插件列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# ── 操作日志 ──────────────────────────────────────────
@system_router.get("/system/operation-log/page")
async def operation_log_page():
    """获取操作日志。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


# ── 项目管理 ──────────────────────────────────────────
@system_router.post("/system/project/add")
async def system_project_add(request: Request):
    """添加项目。"""
    body = await request.json()
    project = {
        "id": str(uuid.uuid4()),
        "name": body.get("name", "新项目"),
        "description": body.get("description", ""),
        "organizationId": body.get("organizationId", ""),
        "enable": True,
        "createTime": time.time(),
    }
    return JSONResponse({"code": 200, "message": "success", "data": project})


@system_router.get("/system/project/list")
async def system_project_list():
    """获取项目列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# ── 组织管理 ──────────────────────────────────────────
@system_router.get("/system/organization/list")
async def system_organization_list():
    """获取组织列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {
            "id": "default-org",
            "name": "默认组织",
            "description": "默认组织",
            "createTime": 0,
            "enable": True,
        }
    ]})


@system_router.post("/system/organization/add")
async def system_organization_add(request: Request):
    """添加组织。"""
    body = await request.json()
    org = {
        "id": str(uuid.uuid4()),
        "name": body.get("name", "新组织"),
        "description": body.get("description", ""),
        "createTime": time.time(),
        "enable": True,
    }
    return JSONResponse({"code": 200, "message": "success", "data": org})
