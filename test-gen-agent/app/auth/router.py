# app/auth/router.py
"""认证 API 路由：登录、登出、会话、用户、个人信息。"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.store import (
    auth_store,
    get_rsa_public_key,
    rsa_decrypt,
)


# ── 请求模型 ────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str
    authenticate: str = "LOCAL"


class LogoutRequest(BaseModel):
    pass


class UserCreateRequest(BaseModel):
    username: str
    password: str
    name: str = ""
    email: str = ""
    phone: str = ""
    role: str = "user"


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    role: Optional[str] = None
    language: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class LocalConfigRequest(BaseModel):
    user_url: str
    type: str = "API"


class LocalConfigUpdateRequest(BaseModel):
    user_url: str


class APIKeyRequest(BaseModel):
    description: str = ""
    forever: bool = False
    expire_time: int = 0


class APIKeyUpdateRequest(BaseModel):
    description: Optional[str] = None
    expire_time: Optional[int] = None


# ── 依赖：从请求头获取会话用户 ─────────────────────────────
def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """从请求中获取当前用户。

    优先从全局认证中间件注入的 request.state.user 获取；
    若中间件未注入（如公开路由），则手动从令牌中解析。
    """
    # 中间件已将用户注入 request.state
    user = getattr(request.state, "user", None)
    if user:
        return user
    # 兜底：手动解析令牌（兼容直接调用场景）
    token = request.headers.get("X-AUTH-TOKEN", "")
    if not token:
        token = request.cookies.get("sessionId", "")
    if not token:
        return None
    return auth_store.get_session_user(token)


def require_user(request: Request) -> Dict[str, Any]:
    """FastAPI 依赖：要求用户已登录，否则返回 None。

    全局认证中间件已拦截未登录请求，此依赖仅用于路由内便捷获取用户。
    若直接调用（中间件未生效时），未登录返回 401 响应。
    """
    user = getattr(request.state, "user", None)
    if not user:
        # 兜底：尝试从请求头解析
        user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="未登录或会话已过期")
    return user


# ── 路由 ───────────────────────────────────────────────────
router = APIRouter(tags=["auth"])


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """用户登录。

    前端使用 RSA 公钥加密密码后发送，后端解密后验证。
    """
    # 解密用户名和密码（前端使用 RSA 公钥加密）
    username = rsa_decrypt(req.username)
    password = rsa_decrypt(req.password)

    user = auth_store.authenticate(username, password)
    if not user:
        return JSONResponse(
            {"code": 400, "message": "用户名或密码错误", "data": None},
            status_code=400,
        )

    client_ip = request.client.host if request.client else ""
    session = auth_store.create_session(user["id"], client_ip)

    # 构建登录响应
    # 如果用户没有项目，自动关联一个默认项目
    if not user.get("last_project_id"):
        from app.projects.management import list_projects, create_project
        projects = list_projects()
        if projects:
            default_project_id = projects[0]["id"]
        else:
            # 自动创建默认项目
            proj = create_project(name="默认项目", description="系统自动创建")
            default_project_id = proj["id"] if proj else ""
        if default_project_id:
            auth_store.update_user(user["id"], last_project_id=default_project_id)
            user["last_project_id"] = default_project_id
    if not user.get("last_organization_id"):
        auth_store.update_user(user["id"], last_organization_id="default-org")
        user["last_organization_id"] = "default-org"

    response_data = {
        "sessionId": session["sessionId"],
        "csrfToken": session["csrfToken"],
        "token": session["sessionId"],
        "id": user["id"],
        "name": user.get("name") or user["username"],
        "username": user["username"],
        "email": user.get("email", ""),
        "phone": user.get("phone", ""),
        "avatar": user.get("avatar", ""),
        "role": user.get("role", "user"),
        "lastOrganizationId": user.get("last_organization_id", "default-org"),
        "lastProjectId": user.get("last_project_id", ""),
        "loginType": ["LOCAL"],
        "userRoleRelations": [
            {
                "id": str(uuid.uuid4()),
                "userId": user["id"],
                "roleId": user.get("role", "user"),
                "sourceId": "global",
                "organizationId": "",
                "createTime": int(user.get("create_time", 0) * 1000),
                "createUser": "system",
                "userRolePermissions": [
                    {
                        "id": str(uuid.uuid4()),
                        "permissionId": "*",
                        "roleId": user.get("role", "user"),
                    }
                ],
                "userRole": {
                    "id": user.get("role", "user"),
                    "name": "管理员" if user.get("role") == "admin" else "普通用户",
                    "scopeId": "global",
                    "type": "SYSTEM",
                },
            }
        ],
        "userRolePermissions": [
            {
                "id": str(uuid.uuid4()),
                "userRole": {
                    "id": user.get("role", "user"),
                    "name": "管理员" if user.get("role") == "admin" else "普通用户",
                    "scopeId": "global",
                    "type": "SYSTEM",
                },
                "userRolePermissions": [
                    {
                        "id": str(uuid.uuid4()),
                        "permissionId": "*",
                        "roleId": user.get("role", "user"),
                    }
                ],
            }
        ],
        "userRoles": [
            {
                "id": user.get("role", "user"),
                "name": "管理员" if user.get("role") == "admin" else "普通用户",
                "scopeId": "global",
                "type": "SYSTEM",
            }
        ],
    }
    return JSONResponse({"code": 200, "message": "success", "data": response_data})


@router.get("/is-login")
async def is_login(request: Request):
    """检查当前是否已登录。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse(
            {"code": 401, "message": "未登录", "data": None},
            status_code=401,
        )

    session_id = request.headers.get("X-AUTH-TOKEN", "") or request.cookies.get("sessionId", "")
    session = auth_store.get_session_user(session_id)

    # 如果用户没有项目，自动关联一个默认项目
    if not user.get("last_project_id"):
        from app.projects.management import list_projects, create_project
        projects = list_projects()
        if projects:
            default_project_id = projects[0]["id"]
        else:
            proj = create_project(name="默认项目", description="系统自动创建")
            default_project_id = proj["id"] if proj else ""
        if default_project_id:
            auth_store.update_user(user["id"], last_project_id=default_project_id)
            user["last_project_id"] = default_project_id
    if not user.get("last_organization_id"):
        auth_store.update_user(user["id"], last_organization_id="default-org")
        user["last_organization_id"] = "default-org"

    response_data = {
        "sessionId": session_id,
        "csrfToken": request.headers.get("CSRF-TOKEN", "") or request.cookies.get("csrfToken", ""),
        "token": session_id,
        "id": user["id"],
        "name": user.get("name") or user.get("username", ""),
        "username": user.get("username", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone", ""),
        "avatar": user.get("avatar", ""),
        "role": user.get("role", "user"),
        "lastOrganizationId": user.get("last_organization_id", "default-org"),
        "lastProjectId": user.get("last_project_id", ""),
        "loginType": ["LOCAL"],
        "userRoleRelations": [
            {
                "id": str(uuid.uuid4()),
                "userId": user["id"],
                "roleId": user.get("role", "user"),
                "sourceId": "global",
                "organizationId": "",
                "createTime": int(user.get("create_time", 0) * 1000),
                "createUser": "system",
                "userRolePermissions": [
                    {
                        "id": str(uuid.uuid4()),
                        "permissionId": "*",
                        "roleId": user.get("role", "user"),
                    }
                ],
                "userRole": {
                    "id": user.get("role", "user"),
                    "name": "管理员" if user.get("role") == "admin" else "普通用户",
                    "scopeId": "global",
                    "type": "SYSTEM",
                },
            }
        ],
        "userRolePermissions": [
            {
                "id": str(uuid.uuid4()),
                "userRole": {
                    "id": user.get("role", "user"),
                    "name": "管理员" if user.get("role") == "admin" else "普通用户",
                    "scopeId": "global",
                    "type": "SYSTEM",
                },
                "userRolePermissions": [
                    {
                        "id": str(uuid.uuid4()),
                        "permissionId": "*",
                        "roleId": user.get("role", "user"),
                    }
                ],
            }
        ],
        "userRoles": [
            {
                "id": user.get("role", "user"),
                "name": "管理员" if user.get("role") == "admin" else "普通用户",
                "scopeId": "global",
                "type": "SYSTEM",
            }
        ],
    }
    return JSONResponse({"code": 200, "message": "success", "data": response_data})


@router.post("/signout")
async def signout(request: Request):
    """用户登出。"""
    token = request.headers.get("X-AUTH-TOKEN", "") or request.cookies.get("sessionId", "")
    if token:
        auth_store.delete_session(token)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/get-key")
async def get_key():
    """返回 RSA 公钥（前端用于密码加密）。"""
    return JSONResponse({"code": 200, "message": "success", "data": get_rsa_public_key()})


@router.get("/authentication/get-list")
async def get_authentication_list():
    """返回可用的认证方式。"""
    return JSONResponse({"code": 200, "message": "success", "data": ["LOCAL"]})


@router.post("/api/user/menu")
async def get_menu_list():
    """返回前端菜单列表。"""
    menus = _build_menu_list()
    return JSONResponse({"code": 200, "message": "success", "data": menus})


def _build_menu_list() -> List[Dict[str, Any]]:
    """构建前端菜单列表（与路由结构对应）。"""
    return [
        {
            "path": "/workstation",
            "name": "workbench",
            "component": "DEFAULT_LAYOUT",
            "redirect": "/workstation/home",
            "meta": {
                "locale": "menu.workbench",
                "icon": "icon-icon_home_filled",
                "order": 0,
                "hideChildrenInMenu": True,
                "roles": ["*"],
            },
            "children": [
                {
                    "path": "home",
                    "name": "workbenchIndex",
                    "component": "/workbench/homePage/index.vue",
                    "meta": {"locale": "menu.workbenchHome", "roles": ["*"]},
                },
            ],
        },
        {
            "path": "/case",
            "name": "caseManagement",
            "component": "DEFAULT_LAYOUT",
            "redirect": "/case/featureCase",
            "meta": {
                "locale": "menu.caseManagement",
                "icon": "icon-icon_test-tracking_filled",
                "order": 1,
                "roles": ["*"],
            },
            "children": [
                {
                    "path": "featureCase",
                    "name": "caseManagementFeatureCase",
                    "component": "/case-management/featureCase/index.vue",
                    "meta": {"locale": "menu.featureCase", "roles": ["*"]},
                },
            ],
        },
        {
            "path": "/api-test",
            "name": "apiTest",
            "component": "DEFAULT_LAYOUT",
            "redirect": "/api-test/definition",
            "meta": {
                "locale": "menu.apiTest",
                "icon": "icon-icon_api-test_filled",
                "order": 2,
                "roles": ["*"],
            },
            "children": [
                {
                    "path": "definition",
                    "name": "apiTestDefinition",
                    "component": "/api-test/management/index.vue",
                    "meta": {"locale": "menu.apiDefinition", "roles": ["*"]},
                },
            ],
        },
        {
            "path": "/test-plan",
            "name": "testPlan",
            "component": "DEFAULT_LAYOUT",
            "redirect": "/test-plan/testPlanIndex",
            "meta": {
                "locale": "menu.testPlan",
                "icon": "icon-icon_test-plan_filled",
                "order": 3,
                "roles": ["*"],
            },
            "children": [
                {
                    "path": "testPlanIndex",
                    "name": "testPlanIndex",
                    "component": "/test-plan/testPlan/index.vue",
                    "meta": {"locale": "menu.testPlanIndex", "roles": ["*"]},
                },
            ],
        },
        {
            "path": "/bug-management",
            "name": "bugManagement",
            "component": "DEFAULT_LAYOUT",
            "redirect": "/bug-management/bugManagementIndex",
            "meta": {
                "locale": "menu.bugManagement",
                "icon": "icon-icon_bug_filled",
                "order": 4,
                "roles": ["*"],
            },
            "children": [
                {
                    "path": "bugManagementIndex",
                    "name": "bugManagementIndex",
                    "component": "/bug-management/bug/index.vue",
                    "meta": {"locale": "menu.bugManagement", "roles": ["*"]},
                },
            ],
        },
        {
            "path": "/setting",
            "name": "setting",
            "component": "DEFAULT_LAYOUT",
            "redirect": "/setting/system/user",
            "meta": {
                "locale": "menu.setting",
                "icon": "icon-icon_setting_filled",
                "order": 10,
                "roles": ["*"],
            },
            "children": [
                {
                    "path": "system/user",
                    "name": "systemUser",
                    "component": "/setting/system/user/index.vue",
                    "meta": {"locale": "menu.systemUser", "roles": ["*"]},
                },
            ],
        },
    ]


# ── 个人信息 ───────────────────────────────────────────────
@router.get("/personal/get")
async def get_personal_info(request: Request):
    """获取当前用户个人信息。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录", "data": None}, status_code=401)

    data = {
        "id": user["id"],
        "name": user.get("name") or user.get("username", ""),
        "email": user.get("email", ""),
        "phone": user.get("phone", ""),
        "language": user.get("language", "zh-CN"),
        "lastOrganizationId": user.get("last_organization_id", ""),
        "lastProjectId": user.get("last_project_id", ""),
        "source": "LOCAL",
        "enable": True,
        "deleted": False,
        "avatar": user.get("avatar", ""),
        "createTime": int(user.get("create_time", 0) * 1000),
        "updateTime": int(user.get("update_time", 0) * 1000),
        "orgProjectList": [],
    }
    return JSONResponse({"code": 200, "message": "success", "data": data})


@router.post("/personal/update-info")
async def update_personal_info(request: Request):
    """更新当前用户个人信息。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录", "data": None}, status_code=401)

    body = await request.json()
    updates = {}
    if "name" in body:
        updates["name"] = body["name"]
    if "email" in body:
        updates["email"] = body["email"]
    if "phone" in body:
        updates["phone"] = body["phone"]
    if "avatar" in body:
        updates["avatar"] = body["avatar"]
    if "language" in body:
        updates["language"] = body["language"]

    updated = auth_store.update_user(user["id"], **updates)
    return JSONResponse({"code": 200, "message": "success", "data": updated})


@router.post("/personal/update-password")
async def update_password(request: Request):
    """修改密码。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录", "data": None}, status_code=401)

    body = await request.json()
    old_pwd = rsa_decrypt(body.get("oldPassword", ""))
    new_pwd = rsa_decrypt(body.get("newPassword", ""))

    if auth_store.change_password(user["id"], old_pwd, new_pwd):
        return JSONResponse({"code": 200, "message": "success", "data": None})
    return JSONResponse({"code": 400, "message": "旧密码错误", "data": None}, status_code=400)


@router.post("/personal/update-locale")
async def update_locale(request: Request):
    """更新语言偏好。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录", "data": None}, status_code=401)

    body = await request.json()
    lang = body.get("language", "zh-CN")
    auth_store.update_user(user["id"], language=lang)
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 本地执行配置 ──────────────────────────────────────────
@router.get("/user/local/config/get")
async def get_local_configs(request: Request):
    """获取本地执行配置列表。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录", "data": []}, status_code=401)
    configs = auth_store.get_local_configs(user["id"])
    return JSONResponse({"code": 200, "message": "success", "data": configs})


@router.post("/user/local/config/add")
async def add_local_config(request: Request):
    """添加本地执行配置。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录", "data": None}, status_code=401)

    body = await request.json()
    user_url = body.get("user_url", "")
    cfg_type = body.get("type", "API")
    config = auth_store.add_local_config(user["id"], user_url, cfg_type)
    return JSONResponse({"code": 200, "message": "success", "data": config})


@router.post("/user/local/config/update")
async def update_local_config(request: Request):
    """更新本地执行配置。"""
    body = await request.json()
    cfg_id = body.get("id", "")
    user_url = body.get("user_url", "")
    auth_store.update_local_config(cfg_id, user_url)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/user/local/config/enable")
async def enable_local_config(request: Request, id: str = ""):
    """启用本地执行配置。"""
    auth_store.toggle_local_config(id, True)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/user/local/config/disable")
async def disable_local_config(request: Request, id: str = ""):
    """禁用本地执行配置。"""
    auth_store.toggle_local_config(id, False)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/user/local/config/default-locale")
async def get_default_locale():
    """获取默认语言。"""
    return JSONResponse({"code": 200, "message": "success", "data": "zh-CN"})


# ── API Key 管理 ──────────────────────────────────────────
@router.get("/user/api/key/list")
async def list_api_keys(request: Request):
    """获取当前用户 API Key 列表。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录", "data": []}, status_code=401)
    keys = auth_store.list_api_keys(user["id"])
    return JSONResponse({"code": 200, "message": "success", "data": keys})


@router.post("/user/api/key/add")
async def add_api_key(request: Request):
    """创建 API Key。"""
    user = get_current_user(request)
    if not user:
        return JSONResponse({"code": 401, "message": "未登录", "data": None}, status_code=401)

    body = await request.json()
    description = body.get("description", "")
    forever = body.get("forever", False)
    expire_time = body.get("expire_time", 0)
    key = auth_store.create_api_key(user["id"], description, forever, expire_time)
    return JSONResponse({"code": 200, "message": "success", "data": key})


@router.post("/user/api/key/enable")
async def enable_api_key(request: Request):
    """启用 API Key。"""
    body = await request.json()
    key_id = body.get("id", "")
    auth_store.toggle_api_key(key_id, True)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/user/api/key/disable")
async def disable_api_key(request: Request):
    """禁用 API Key。"""
    body = await request.json()
    key_id = body.get("id", "")
    auth_store.toggle_api_key(key_id, False)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/user/api/key/delete")
async def delete_api_key(request: Request):
    """删除 API Key。"""
    body = await request.json()
    key_id = body.get("id", "")
    auth_store.delete_api_key(key_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 用户管理（管理员） ────────────────────────────────────
@router.get("/system/user/list")
async def list_users(request: Request):
    """获取用户列表。"""
    users = auth_store.list_users()
    return JSONResponse({"code": 200, "message": "success", "data": users})


@router.post("/system/user/page", operation_id="system_user_page_post")
@router.get("/system/user/page", operation_id="system_user_page_get")
async def system_user_page(request: Request):
    """系统用户分页列表。"""
    if request.method == "POST":
        try:
            raw = await request.body()
            body = await request.json() if raw else {}
        except Exception:
            body = {}
        current = int(body.get("current", 1))
        pageSize = int(body.get("pageSize", 10))
        keyword = body.get("keyword", "")
    else:
        current = int(request.query_params.get("current", 1))
        pageSize = int(request.query_params.get("pageSize", 10))
        keyword = request.query_params.get("keyword", "")
    users = auth_store.list_users()
    if keyword:
        users = [u for u in users if keyword.lower() in u.get("username", "").lower()
                 or keyword.lower() in u.get("name", "").lower()
                 or keyword.lower() in u.get("email", "").lower()]
    total = len(users)
    start = (current - 1) * pageSize
    items = users[start:start + pageSize]
    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": {
            "list": items,
            "total": total,
            "pageSize": pageSize,
            "current": current,
        },
    })


@router.get("/system/user/get")
async def system_user_get(request: Request, id: str = "", username: str = "", keyword: str = ""):
    """获取系统用户详情。keyword 可为邮箱或用户 ID。"""
    user = None
    search = keyword or username or id
    if search:
        user = auth_store.get_user_by_id(search)
        if not user:
            user = auth_store.get_user_by_username(search)
    if not user:
        return JSONResponse({"code": 404, "message": "用户不存在", "data": None}, status_code=404)
    if user:
        user.pop("password_hash", None)
    return JSONResponse({"code": 200, "message": "success", "data": user})


@router.post("/system/user/add")
async def add_user(request: Request):
    """添加用户。"""
    body = await request.json()
    username = body.get("username", "")
    password = rsa_decrypt(body.get("password", ""))
    if not username or not password:
        return JSONResponse({"code": 400, "message": "用户名和密码不能为空", "data": None}, status_code=400)

    if auth_store.get_user_by_username(username):
        return JSONResponse({"code": 400, "message": "用户名已存在", "data": None}, status_code=400)

    user = auth_store.create_user(
        username=username,
        password=password,
        name=body.get("name", username),
        email=body.get("email", ""),
        phone=body.get("phone", ""),
        role=body.get("role", "user"),
    )
    return JSONResponse({"code": 200, "message": "success", "data": user})


@router.post("/system/user/update")
async def update_user(request: Request):
    """更新用户。"""
    body = await request.json()
    user_id = body.get("id", "")
    updates = {}
    for field in ["name", "email", "phone", "avatar", "role", "language"]:
        if field in body:
            updates[field] = body[field]
    user = auth_store.update_user(user_id, **updates)
    if not user:
        return JSONResponse({"code": 404, "message": "用户不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": user})


@router.post("/system/user/delete")
async def delete_user(request: Request):
    """删除用户。"""
    body = await request.json()
    user_id = body.get("id", "")
    auth_store.delete_user(user_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})




# ── 系统用户管理（分页/详情/启停/导入/角色/重置密码）────────



@router.post("/system/user/update/enable")
async def toggle_user_enabled(request: Request):
    """启用/禁用用户。"""
    body = await request.json()
    user_id = body.get("id", "")
    enable = body.get("enable", body.get("status", "enable") == "enable")
    ok = auth_store.set_user_enabled(user_id, bool(enable))
    if not ok:
        return JSONResponse({"code": 404, "message": "用户不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/system/user/reset/password")
async def reset_user_password(request: Request):
    """重置用户密码。"""
    body = await request.json()
    user_id = body.get("id", "")
    password = rsa_decrypt(body.get("password", ""))
    if not password:
        return JSONResponse({"code": 400, "message": "密码不能为空", "data": None}, status_code=400)
    ok = auth_store.reset_password(user_id, password)
    if not ok:
        return JSONResponse({"code": 404, "message": "用户不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/system/user/import")
async def import_users(request: Request):
    """导入用户（支持 JSON/表单数组）。"""
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = {}
        import json as _json
        for k in form:
            if k == "userList":
                try:
                    body["users"] = _json.loads(form[k])
                except Exception:
                    body["users"] = []
    users = body.get("users", body.get("userList", []))
    created = 0
    for u in users:
        username = u.get("username", "")
        password = rsa_decrypt(u.get("password", "")) or "123456"
        if not username or auth_store.get_user_by_username(username):
            continue
        auth_store.create_user(
            username=username, password=password,
            name=u.get("name", username), email=u.get("email", ""),
            phone=u.get("phone", ""), role=u.get("role", "user"),
        )
        created += 1
    return JSONResponse({"code": 200, "message": "success", "data": {"successCount": created}})


@router.get("/system/user/get/global/system/role")
async def get_system_roles():
    """获取全局系统角色。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "系统管理员"},
        {"id": "user", "name": "普通用户"},
    ]})


# ── 项目成员管理 ─────────────────────────────────────────
@router.get("/project/member/list", operation_id="project_member_list_get")
@router.post("/project/member/list", operation_id="project_member_list_post")
async def project_member_list(request: Request):
    """项目成员列表。"""
    from app.projects.management import list_project_members
    if request.method == "POST":
        try:
            raw = await request.body()
            body = await request.json() if raw else {}
        except Exception:
            body = {}
    else:
        body = dict(request.query_params)
    project_id = body.get("projectId", body.get("project_id", ""))
    keyword = body.get("keyword", "")
    members = list_project_members(project_id, keyword)
    return JSONResponse({"code": 200, "message": "success",
                         "data": {"list": members, "total": len(members)}})


@router.post("/project/member/add")
async def project_member_add(request: Request):
    """添加项目成员。"""
    from app.projects.management import add_project_member
    body = await request.json()
    project_id = body.get("projectId", body.get("project_id", ""))
    member_ids = body.get("memberIds", body.get("userIds", []))
    if isinstance(member_ids, str):
        member_ids = [member_ids]
    if not member_ids:
        member_ids = [body.get("userId", body.get("user_id", ""))]
    role = body.get("role", "member")
    from app.projects.management import get_project, create_project, list_projects
    if not get_project(project_id):
        # Try to find by name first
        found = list_projects(search=project_id)
        if not found:
            create_project(name=project_id, description="auto-created")
    added = []
    for uid in member_ids:
        if not uid:
            continue
        member = add_project_member(
            project_id=project_id,
            user_id=str(uid),
            username=body.get("username", ""),
            name=body.get("name", ""),
            email=body.get("email", ""),
            role=role,
            user_group=body.get("userRoleId", body.get("user_group", "")),
        )
        if member:
            added.append(member)
    if not added:
        # 成员可能已存在，视为操作成功
        from app.projects.management import list_project_members
        existing = list_project_members(project_id)
        return JSONResponse({"code": 200, "message": "success", "data": existing})
    return JSONResponse({"code": 200, "message": "success", "data": added})


@router.post("/project/member/update")
async def project_member_update(request: Request):
    """更新项目成员。"""
    from app.projects.management import update_project_member
    body = await request.json()
    member_id = body.get("id", body.get("memberId", ""))
    member = update_project_member(member_id, **{
        k: body[k] for k in ("username", "name", "email", "role", "user_group") if k in body
    })
    if not member:
        return JSONResponse({"code": 404, "message": "成员不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": member})


@router.post("/project/member/remove", operation_id="project_member_remove_post")
async def project_member_remove_post(request: Request):
    """移除项目成员。body: {projectId, userId}"""
    body = await request.json()
    project_id = body.get("projectId", body.get("project_id", ""))
    user_id = body.get("userId", body.get("user_id", ""))
    from app.projects.management import remove_project_member
    ok = remove_project_member(project_id, user_id)
    return JSONResponse({"code": 200 if ok else 404, "message": "success" if ok else "成员不存在",
                         "data": None}, status_code=200 if ok else 404)


@router.get("/project/member/remove/{project_id}/{user_id}")
async def project_member_remove(project_id: str, user_id: str):
    """移除项目成员。"""
    from app.projects.management import remove_project_member
    ok = remove_project_member(project_id, user_id)
    return JSONResponse({"code": 200 if ok else 404, "message": "success" if ok else "成员不存在",
                         "data": None}, status_code=200 if ok else 404)


@router.post("/project/member/batch/remove")
async def project_member_batch_remove(request: Request):
    """批量移除项目成员。"""
    from app.projects.management import remove_project_member
    body = await request.json()
    project_id = body.get("projectId", body.get("project_id", ""))
    user_ids = body.get("userIds", body.get("memberIds", []))
    removed = 0
    for uid in user_ids:
        if remove_project_member(project_id, uid):
            removed += 1
    return JSONResponse({"code": 200, "message": "success", "data": {"removed": removed}})


# ── 系统信息 ─────────────────────────────────────────────
@router.get("/system/version/current")
async def get_system_version():
    """获取系统版本。"""
    return JSONResponse({"code": 200, "message": "success", "data": "v0.2.0"})


@router.get("/system/version/package-type")
async def get_package_type():
    """获取包类型。"""
    return JSONResponse({"code": 200, "message": "success", "data": "enterprise"})


@router.get("/system/organization/switch-option")
async def get_org_switch_options():
    """获取组织切换选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/system/organization/switch")
async def switch_org(request: Request):
    """切换组织。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/project/has-permission/{user_id}")
async def user_has_project_permission(user_id: str):
    """检查用户是否有项目权限。"""
    return JSONResponse({"code": 200, "message": "success", "data": True})


# ── 组织 & 项目管理 ───────────────────────────────────────
@router.get("/project/list/options/{organization_id}")
async def project_list_options(organization_id: str = ""):
    """获取项目列表选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/project/switch")
async def project_switch(request: Request):
    """切换项目。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/project/get/{project_id}")
async def project_get(project_id: str):
    """获取项目详情。"""
    data = {
        "id": project_id,
        "num": 1,
        "organizationId": "default-org",
        "name": "默认项目",
        "description": "AI 测试生成平台默认项目",
        "createTime": 0,
        "updateTime": 0,
        "updateUser": "system",
        "createUser": "system",
        "deleteTime": 0,
        "deleted": False,
        "deleteUser": "",
        "enable": True,
        "moduleSetting": "",
        "memberCount": 1,
        "organizationName": "默认组织",
        "adminList": [],
        "projectCreateUserIsAdmin": True,
        "moduleIds": ["apiTest", "caseManagement", "testPlan", "bugManagement"],
        "resourcePoolList": [],
    }
    return JSONResponse({"code": 200, "message": "success", "data": data})


@router.post("/project/update")
async def project_update(request: Request):
    """更新项目。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/project/list/options/{org_id}/{module}")
async def project_list_by_org_module(org_id: str, module: str):
    """按组织和模块获取项目列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/system/get/{module}")
async def system_get_module(module: str):
    """获取系统模块信息。"""
    return JSONResponse({"code": 200, "message": "success", "data": {}})


# ── 系统设置 ──────────────────────────────────────────────
@router.get("/system/parameter/get/base-info")
async def get_base_info():
    """获取系统基础信息。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "name": "Test Generation Agent",
        "description": "AI 驱动的测试用例生成平台",
        "url": "",
        "language": "zh-CN",
    }})


@router.post("/system/parameter/save/base-info")
async def save_base_info(request: Request):
    """保存系统基础信息。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/system/parameter/save/base-url")
async def save_base_url(request: Request):
    """保存站点 URL。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/display/info")
async def get_page_config():
    """获取界面配置。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/display/save")
async def save_page_config(request: Request):
    """保存界面配置。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# 图标/Logo 资源
@router.get("/base-display/get/logo-platform")
async def get_logo_platform():
    """获取平台 Logo。"""
    return JSONResponse({"code": 200, "message": "success", "data": {"url": "", "name": ""}})


@router.get("/base-display/get/login-logo")
async def get_login_logo():
    """获取登录 Logo。"""
    return JSONResponse({"code": 200, "message": "success", "data": {"url": "", "name": ""}})


@router.get("/base-display/get/login-image")
async def get_login_image():
    """获取登录大图。"""
    return JSONResponse({"code": 200, "message": "success", "data": {"url": "", "name": ""}})


@router.get("/base-display/get/icon")
async def get_platform_icon():
    """获取平台标签图标。"""
    return JSONResponse({"code": 200, "message": "success", "data": {"url": "", "name": ""}})


# ── 环境管理 ──────────────────────────────────────────────
@router.get("/api/test/environment/list/{project_id}")
async def get_env_list(project_id: str = ""):
    """获取项目环境列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/api/test/environment/get")
async def get_env_detail():
    """获取环境详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── AI 配置 ───────────────────────────────────────────────
@router.get("/ai/config/source/name/list")
async def get_ai_source_name_list():
    """获取 AI 模型名称列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/ai/config/source/list")
async def get_ai_source_list():
    """获取 AI 模型源列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# ── 接口测试环境 ──────────────────────────────────────────
@router.get("/api/test/protocol/{organization_id}")
async def get_protocol_list(organization_id: str = ""):
    """获取协议列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "HTTP", "name": "HTTP"},
        {"id": "HTTPS", "name": "HTTPS"},
        {"id": "TCP", "name": "TCP"},
        {"id": "SQL", "name": "SQL"},
        {"id": "DUBBO", "name": "DUBBO"},
    ]})


@router.get("/api/test/env-list/{project_id}")
async def get_env_list_api(project_id: str = ""):
    """获取接口测试环境列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/api/test/environment/{env_id}")
async def get_environment(env_id: str = ""):
    """获取环境详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": env_id,
        "name": "默认环境",
        "config": {},
    }})


@router.get("/api/test/plugin/form/option")
async def get_plugin_options():
    """获取插件表单选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/api/test/plugin/script")
async def get_plugin_script():
    """获取插件配置脚本。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})
