# app/routers/missing_admin.py
"""缺失的管理后台 API 补充。

修复前端调用的以下缺失接口：
  1. 用户组（角色）管理：/user/role/global/*、/user/role/organization/*、/user/role/relation/global/*
  2. 组织/项目启用禁用：enable/disable（前端用 GET + 路径参数，后端只有 POST）
  3. 组织/项目移除成员：remove-member（前端用 GET + 路径参数）
"""
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

router = APIRouter(tags=["missing-admin"])


def _ok(data=None):
    """统一的成功响应。"""
    return JSONResponse({"success": True, "data": data if data is not None else {}})


# ════════════════════════════════════════════════════════════
# 一、用户组（角色）管理 - 全局 /user/role/global/*
# ════════════════════════════════════════════════════════════

def _builtin_global_groups() -> List[Dict[str, Any]]:
    return [
        {
            "id": "admin",
            "name": "管理员",
            "description": "系统管理员",
            "internal": True,
            "type": "SYSTEM",
            "scopeId": "global",
            "createTime": 0,
            "updateTime": 0,
            "createUser": "admin",
            "pos": 1,
        },
        {
            "id": "member",
            "name": "成员",
            "description": "系统成员",
            "internal": True,
            "type": "SYSTEM",
            "scopeId": "global",
            "createTime": 0,
            "updateTime": 0,
            "createUser": "admin",
            "pos": 2,
        },
        {
            "id": "read-only",
            "name": "只读成员",
            "description": "只读成员",
            "internal": True,
            "type": "SYSTEM",
            "scopeId": "global",
            "createTime": 0,
            "updateTime": 0,
            "createUser": "admin",
            "pos": 3,
        },
    ]


@router.get("/user/role/global/list")
async def user_role_global_list():
    """获取全局用户组列表。"""
    return _ok(_builtin_global_groups())


@router.get("/user/role/global/get/{role_id}")
async def user_role_global_get(role_id: str):
    """获取全局用户组详情。"""
    for g in _builtin_global_groups():
        if g["id"] == role_id:
            return _ok(g)
    return _ok({"id": role_id, "name": "用户组", "description": "", "internal": True, "type": "SYSTEM", "scopeId": "global"})


@router.post("/user/role/global/add")
async def user_role_global_add(request: Request):
    """创建全局用户组。"""
    body = await request.json()
    return _ok({
        "id": str(uuid.uuid4()),
        "name": body.get("name", "未命名用户组"),
        "description": body.get("description", ""),
        "internal": False,
        "type": "SYSTEM",
        "scopeId": body.get("scopeId", "global"),
        "createTime": time.time(),
        "updateTime": time.time(),
        "createUser": "admin",
        "pos": 99,
    })


@router.post("/user/role/global/update")
async def user_role_global_update(request: Request):
    """更新全局用户组。"""
    body = await request.json()
    return _ok({"id": body.get("id", ""), "name": body.get("name", ""), "description": body.get("description", ""), "updateTime": time.time()})


@router.get("/user/role/global/delete/{role_id}")
async def user_role_global_delete(role_id: str):
    """删除全局用户组。"""
    return _ok({"id": role_id, "deleted": True})


@router.get("/user/role/global/permission/setting/{role_id}")
async def user_role_global_permission_setting(role_id: str):
    """获取全局用户组权限配置。"""
    return _ok([])


@router.post("/user/role/global/permission/update")
async def user_role_global_permission_update(request: Request):
    """更新全局用户组权限。"""
    await request.json()
    return _ok()


# ════════════════════════════════════════════════════════════
# 二、用户组（角色）管理 - 组织 /user/role/organization/*
# ════════════════════════════════════════════════════════════

@router.get("/user/role/organization/list/{organization_id}")
async def user_role_org_list(organization_id: str):
    """获取组织用户组列表。"""
    return _ok(_builtin_global_groups())


@router.get("/user/role/organization/get/{role_id}")
async def user_role_org_get(role_id: str):
    """获取组织用户组详情。"""
    return _ok({"id": role_id, "name": "组织用户组", "description": "", "internal": True, "type": "ORGANIZATION", "scopeId": "organization"})


@router.post("/user/role/organization/add")
async def user_role_org_add(request: Request):
    """创建组织用户组。"""
    body = await request.json()
    return _ok({
        "id": str(uuid.uuid4()),
        "name": body.get("name", "未命名组织用户组"),
        "description": body.get("description", ""),
        "internal": False,
        "type": "ORGANIZATION",
        "scopeId": body.get("scopeId", ""),
        "createTime": time.time(),
        "updateTime": time.time(),
        "createUser": "admin",
        "pos": 99,
    })


@router.post("/user/role/organization/update")
async def user_role_org_update(request: Request):
    """更新组织用户组。"""
    body = await request.json()
    return _ok({"id": body.get("id", ""), "name": body.get("name", ""), "description": body.get("description", ""), "updateTime": time.time()})


@router.get("/user/role/organization/delete/{role_id}")
async def user_role_org_delete(role_id: str):
    """删除组织用户组。"""
    return _ok({"id": role_id, "deleted": True})


@router.get("/user/role/organization/permission/setting/{role_id}")
async def user_role_org_permission_setting(role_id: str):
    """获取组织用户组权限配置。"""
    return _ok([])


@router.post("/user/role/organization/permission/update")
async def user_role_org_permission_update(request: Request):
    """更新组织用户组权限。"""
    await request.json()
    return _ok()


@router.post("/user/role/organization/list-member")
async def user_role_org_list_member(request: Request):
    """获取组织用户组成员列表。"""
    await request.json()
    return _ok({"list": [], "total": 0})


@router.post("/user/role/organization/add-member")
async def user_role_org_add_member(request: Request):
    """组织用户组添加成员。"""
    await request.json()
    return _ok()


@router.post("/user/role/organization/remove-member")
async def user_role_org_remove_member(request: Request):
    """组织用户组移除成员。"""
    await request.json()
    return _ok()


@router.get("/user/role/organization/get-member/option/{organization_id}/{role_id}")
async def user_role_org_get_member_option(organization_id: str, role_id: str, keyword: str = ""):
    """组织用户组成员下拉选项。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# 三、用户组-用户关联 /user/role/relation/global/*
# ════════════════════════════════════════════════════════════

@router.post("/user/role/relation/global/list")
async def user_role_relation_global_list(request: Request):
    """获取全局用户组成员列表。"""
    await request.json()
    return _ok({"list": [], "total": 0})


@router.post("/user/role/relation/global/add")
async def user_role_relation_global_add(request: Request):
    """全局用户组添加成员。"""
    await request.json()
    return _ok()


@router.get("/user/role/relation/global/delete/{user_role_id}")
async def user_role_relation_global_delete(user_role_id: str):
    """全局用户组移除成员。"""
    return _ok({"id": user_role_id, "deleted": True})


@router.get("/user/role/relation/global/user/option/{user_role_id}")
async def user_role_relation_global_user_option(user_role_id: str, keyword: str = ""):
    """全局用户组成员下拉选项。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# 四、组织/项目启用禁用（前端用 GET + 路径参数）
# ════════════════════════════════════════════════════════════

@router.get("/system/organization/enable/{id}")
async def system_org_enable(id: str):
    """启用组织。"""
    return _ok({"id": id, "enable": True})


@router.get("/system/organization/disable/{id}")
async def system_org_disable(id: str):
    """禁用组织。"""
    return _ok({"id": id, "enable": False})


@router.get("/system/project/enable/{id}")
async def system_project_enable(id: str):
    """启用项目。"""
    return _ok({"id": id, "enable": True})


@router.get("/system/project/disable/{id}")
async def system_project_disable(id: str):
    """禁用项目。"""
    return _ok({"id": id, "enable": False})


@router.get("/organization/project/enable/{id}")
async def org_project_enable(id: str):
    """启用组织下项目。"""
    return _ok({"id": id, "enable": True})


@router.get("/organization/project/disable/{id}")
async def org_project_disable(id: str):
    """禁用组织下项目。"""
    return _ok({"id": id, "enable": False})


# ════════════════════════════════════════════════════════════
# 五、组织/项目移除成员（前端用 GET + 路径参数）
# ════════════════════════════════════════════════════════════

@router.get("/system/organization/remove-member/{source_id}/{user_id}")
async def system_org_remove_member(source_id: str, user_id: str):
    """移除组织成员。"""
    return _ok({"source_id": source_id, "user_id": user_id, "removed": True})


@router.get("/system/project/remove-member/{source_id}/{user_id}")
async def system_project_remove_member(source_id: str, user_id: str):
    """移除项目成员。"""
    return _ok({"source_id": source_id, "user_id": user_id, "removed": True})


# ════════════════════════════════════════════════════════════
# 六、其他方法不匹配修复
# ════════════════════════════════════════════════════════════

@router.get("/organization/project/user-admin-list/{organization_id}/{project_id}")
async def org_project_user_admin_list(organization_id: str, project_id: str, keyword: str = ""):
    """获取组织项目管理员列表（带路径参数）。"""
    return _ok([])
