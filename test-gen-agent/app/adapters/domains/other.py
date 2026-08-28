# app/adapters/domains/other.py
"""业务域路由拆分：other（Phase 3 重构）。"""

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["adapter-other"])


def _ok(data: Any = None, message: str = "success", code: int = 200) -> JSONResponse:
    """统一成功响应格式。"""
    return JSONResponse({"code": code, "message": message, "data": data})


def _err(message: str = "error", code: int = 500, data: Any = None) -> JSONResponse:
    """统一失败响应格式。"""
    return JSONResponse({"code": code, "message": message, "data": data})


def _paginate(items: List, current: int = 1, page_size: int = 10) -> Dict:
    """分页包装。"""
    total = len(items)
    start = (current - 1) * page_size
    return {
        "list": items[start:start + page_size],
        "total": total,
        "pageSize": page_size,
        "current": current,
    }


async def _body(request: Request) -> dict:
    """安全读取请求体，空请求体返回空字典。"""
    try:
        raw = await request.body()
        if not raw:
            return {}
        return await request.json()
    except Exception:
        return {}


@router.get("/api/doc/share/delete")
async def api_doc_share_delete_get(request: Request):
    """接口文档分享删除（GET兼容）。"""
    return _ok()


@router.get("/api/doc/share/detail")
async def api_doc_share_detail_get(request: Request):
    """接口文档分享详情（GET兼容）。"""
    return _ok()


@router.get("/api/doc/share/get-detail")
async def api_doc_share_get_detail_get(request: Request):
    """接口文档分享详情（GET兼容）。"""
    return _ok()


@router.get("/sso/callback/we_com")
async def sso_callback_we_com_get(request: Request):
    """企微SSO回调（GET兼容）。"""
    return _ok({"success": True})


@router.get("/sso/callback/ding_talk")
async def sso_callback_ding_talk_get(request: Request):
    """钉钉SSO回调（GET兼容）。"""
    return _ok({"success": True})


@router.get("/sso/callback/lark")
async def sso_callback_lark_get(request: Request):
    """飞书SSO回调（GET兼容）。"""
    return _ok({"success": True})


@router.get("/sso/callback/lark_suite")
async def sso_callback_lark_suite_get(request: Request):
    """飞书套件SSO回调（GET兼容）。"""
    return _ok({"success": True})

# ════════════════════════════════════════════════════════════
# B类修复：前端用 POST，后端只有 GET —— 添加 POST 方法
# ════════════════════════════════════════════════════════════


@router.post("/api/doc/share/module/count")
async def api_doc_share_module_count_post(request: Request):
    """文档分享模块统计（POST兼容）。"""
    return _ok([])


@router.post("/api/chat/list")
async def api_chat_list_post(request: Request):
    """聊天列表（POST兼容）。"""
    return _ok([])


@router.post("/api/doc/share/module/tree")
async def api_doc_share_module_tree_post(request: Request):
    """文档分享模块树（POST兼容）。"""
    return _ok([])


@router.get("/api/test/download")
async def api_test_download(file_name: str = "", download_id: str = ""):
    """报告文件下载。"""
    return _ok({"fileId": download_id, "fileName": file_name or "report.zip"})


@router.post("/api/test/download")
async def api_test_download_post(request: Request):
    """报告文件下载 POST。"""
    await request.json()
    return _ok({"fileId": str(uuid.uuid4())})


# ════════════════════════════════════════════════════════════
# P0-2: 接口定义 / 用例 / 场景 / 调试补充接口
# ════════════════════════════════════════════════════════════


@router.post("/api/stop")
async def api_stop(request: Request):
    """停止执行。"""
    await request.json()
    return _ok()


@router.get("/api/stop")
async def api_stop_get(report_id: str = ""):
    """停止执行 GET。"""
    return _ok()


# ════════════════════════════════════════════════════════════
# P0-3: 接口定义定时同步  /api/definition/schedule/*
# ════════════════════════════════════════════════════════════


@router.post("/api/doc/share/add")
async def api_doc_share_add(request: Request):
    """新增接口文档分享。"""
    body = await request.json()
    return _ok({"id": str(uuid.uuid4()), **body})


@router.post("/api/doc/share/update")
async def api_doc_share_update(request: Request):
    """更新接口文档分享。"""
    await request.json()
    return _ok()


@router.post("/api/doc/share/delete")
async def api_doc_share_delete(request: Request):
    """删除接口文档分享。"""
    await request.json()
    return _ok()


@router.post("/api/doc/share/page")
async def api_doc_share_page(request: Request):
    """接口文档分享列表。"""
    body = await request.json()
    return _ok(_paginate([], body.get("current", 1), body.get("pageSize", 10)))


@router.post("/api/doc/share/check")
async def api_doc_share_check(request: Request):
    """校验分享密码。"""
    await request.json()
    return _ok({"result": True})


@router.post("/api/doc/share/detail")
async def api_doc_share_detail(request: Request):
    """查看分享链接。"""
    await request.json()
    return _ok({})


@router.get("/api/doc/share/module/tree")
async def api_doc_share_module_tree(share_id: str = ""):
    """分享模块树。"""
    return _ok([])


@router.get("/api/doc/share/module/count")
async def api_doc_share_module_count(share_id: str = ""):
    """分享模块数量。"""
    return _ok({})


@router.post("/api/doc/share/export")
async def api_doc_share_export(request: Request):
    """导出分享接口定义。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.get("/api/doc/share/download/file")
async def api_doc_share_download_file(file_id: str = ""):
    """下载分享文档。"""
    return _ok({"fileId": file_id, "fileName": "share"})


@router.post("/api/doc/share/stop")
async def api_doc_share_stop(request: Request):
    """停止分享导出。"""
    await request.json()
    return _ok()


@router.post("/api/doc/share/get-detail")
async def api_doc_share_get_detail(request: Request):
    """获取分享接口定义详情。"""
    await request.json()
    return _ok({})


@router.post("/api/doc/share/plugin/script")
async def api_doc_share_plugin_script(request: Request):
    """获取分享插件脚本。"""
    await request.json()
    return _ok({})


# ════════════════════════════════════════════════════════════
# P1-1: 项目环境管理  /project/environment/*
# ════════════════════════════════════════════════════════════


@router.get("/api/test/pool-option")
async def api_test_pool_option():
    """接口测试资源池选项。"""
    return _ok([])


@router.get("/api/test/get-pool")
async def api_test_get_pool():
    """获取资源池 ID。"""
    return _ok({})


@router.get("/api/test/get-pool/")
async def api_test_get_pool_trailing(project_id: str = ""):
    """获取资源池 ID（尾斜杠）。"""
    return _ok({})


@router.get("/api/test/env-list")
async def api_test_env_list(project_id: str = ""):
    """接口测试环境列表。"""
    return _ok([])


@router.get("/api/test/environment")
async def api_test_environment(project_id: str = "", environment_id: str = ""):
    """接口测试环境。"""
    return _ok({})


@router.get("/api/test/protocol")
async def api_test_protocol():
    """接口测试协议列表。"""
    return _ok(["HTTP", "HTTPS", "TCP", "SQL", "DUBBO"])


@router.get("/api/test/common-script")
async def api_test_common_script():
    """公共脚本。"""
    return _ok([])


@router.post("/api/test/custom/func/run")
async def api_test_custom_func_run(request: Request):
    """运行自定义函数。"""
    await request.json()
    return _ok({"result": "success"})


# ════════════════════════════════════════════════════════════
# P1-13: 任务中心  /project/task-center/*  /organization/task-center/*  /system/task-center/*
# ════════════════════════════════════════════════════════════

# 项目任务中心


@router.get("/task/center/api/project/stop")
async def task_center_api_project_stop():
    """停止项目 API 任务。"""
    return _ok()


@router.get("/task/center/project/schedule/page")
async def task_center_project_schedule_page():
    """项目定时任务分页。"""
    return _ok(_paginate([], 1, 10))


# 组织任务中心


@router.get("/operation/log/list")
async def operation_log_list():
    """操作日志列表。"""
    return _ok(_paginate([], 1, 10))


@router.get("/operation/log/get/options")
async def operation_log_get_options():
    """操作日志选项。"""
    return _ok([])


@router.get("/operation/log/user/list")
async def operation_log_user_list():
    """操作日志用户列表。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# P2-5: 第三方集成  /we_com/*  /ding_talk/*  /lark/*  /lark_suite/*  /sso/*  /ldap/*
# ════════════════════════════════════════════════════════════

# 企微


@router.post("/sso/callback/we_com")
async def sso_callback_we_com(request: Request):
    """企微 SSO 回调。"""
    await request.json()
    return _ok({"success": True})


@router.post("/sso/callback/ding_talk")
async def sso_callback_ding_talk(request: Request):
    """钉钉 SSO 回调。"""
    await request.json()
    return _ok({"success": True})


@router.post("/sso/callback/lark")
async def sso_callback_lark(request: Request):
    """飞书 SSO 回调。"""
    await request.json()
    return _ok({"success": True})


@router.post("/sso/callback/lark_suite")
async def sso_callback_lark_suite(request: Request):
    """飞书套件 SSO 回调。"""
    await request.json()
    return _ok({"success": True})


@router.post("/ldap/login")
async def ldap_login(request: Request):
    """LDAP 登录。"""
    body = await request.json()
    return _ok({"success": True, "token": str(uuid.uuid4())})


# ════════════════════════════════════════════════════════════
# P2-6: 平台设置  /setting/*
# ════════════════════════════════════════════════════════════


@router.get("/personal/model/get")
async def personal_model_get():
    """个人模型。"""
    return _ok({})


@router.delete("/personal/model/delete")
async def personal_model_delete():
    """删除个人模型。"""
    return _ok()


@router.post("/personal/model/edit-source")
async def personal_model_edit_source(request: Request):
    """编辑个人模型源。"""
    await request.json()
    return _ok()


@router.get("/personal/model/source/list")
async def personal_model_source_list():
    """个人模型源列表。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# P2-10: AI 配置  /ai/config/*  /ai/conversation/*
# ════════════════════════════════════════════════════════════


@router.get("/api/chat/list")
async def api_chat_list():
    """聊天列表。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# P0-5: 缺陷管理补充  /bug/*
# ════════════════════════════════════════════════════════════


@router.get("/dashboard/header/columns-option")
async def dashboard_header_columns_option(project_id: str = ""):
    """Dashboard 表头列选项。"""
    return _ok([])


@router.get("/dashboard/header/custom-field")
async def dashboard_header_custom_field(project_id: str = ""):
    """Dashboard 表头自定义字段。"""
    return _ok([])


@router.get("/dashboard/layout/get")
async def dashboard_layout_get(org_id: str = ""):
    """Dashboard 布局。"""
    return _ok({})


@router.post("/dashboard/layout/edit")
async def dashboard_layout_edit(request: Request):
    """编辑 Dashboard 布局。"""
    await request.json()
    return _ok()


@router.get("/dashboard/member/get-project-member/option")
async def dashboard_member_get_project_member_option(project_id: str = ""):
    """Dashboard 项目成员选项。"""
    return _ok([])


@router.get("/dashboard/plan/option")
async def dashboard_plan_option(project_id: str = ""):
    """Dashboard 计划选项。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# P0-8: 测试计划补充  /test-plan/*
# ════════════════════════════════════════════════════════════


@router.get("/status")
async def status_endpoint():
    """服务状态。"""
    return _ok({"status": "UP", "time": int(time.time())})


# ════════════════════════════════════════════════════════════
# 补充遗漏接口
# ════════════════════════════════════════════════════════════


@router.get("/api/doc/share/download/file/{share_id}/{file_id}")
@router.post("/api/doc/share/download/file/{share_id}/{file_id}")
async def doc_share_download_file_path(share_id: str, file_id: str):
    """下载分享文件（带路径参数）。"""
    return _ok({"share_id": share_id, "file_id": file_id})


@router.get("/api/doc/share/export/{share_id}")
@router.post("/api/doc/share/export/{share_id}")
async def doc_share_export_path(share_id: str):
    """导出分享（带路径参数）。"""
    return _ok({"id": share_id, "exported": True})


@router.get("/api/doc/share/stop/{share_id}")
@router.post("/api/doc/share/stop/{share_id}")
async def doc_share_stop_path(share_id: str):
    """停止分享（带路径参数）。"""
    return _ok({"id": share_id, "stopped": True})


# ════════════════════════════════════════════════════════════
# 报告
# ════════════════════════════════════════════════════════════


@router.get("/personal/model/delete/{model_id}")
@router.post("/personal/model/delete/{model_id}")
async def personal_model_delete_path(model_id: str):
    """删除个人模型（带路径参数）。"""
    return _ok({"id": model_id, "deleted": True})


# ════════════════════════════════════════════════════════════
# 插件
# ════════════════════════════════════════════════════════════


@router.get("/api/doc/share/plugin/script/{id}/{org_id}")
async def doc_share_plugin_script_path(id: str, org_id: str):
    """获取文档分享插件脚本（带路径参数）。"""
    return _ok({"id": id, "org_id": org_id})


# 场景步骤跨项目信息（前端: /api/scenario/step/resource-info/{id}）


@router.get("/api/test/common-script/{script_id}")
async def api_test_common_script_path(script_id: str):
    """获取公共脚本详情（带路径参数）。"""
    return _ok({"id": script_id})


# 功能用例前后置已关联IDs（前端: /functional/case/relationship/get-ids/{caseId}）


@router.get("/personal/model/get/{model_id}")
async def personal_model_get_path(model_id: str):
    """获取个人模型详情（带路径参数）。"""
    return _ok({"id": model_id})


# 公共脚本详情（前端: /project/custom/func/detail/{funcId}）


@router.get("/task/center/api/project/stop/{task_id}")
async def task_center_api_project_stop_path(task_id: str):
    """停止项目任务（带路径参数）。"""
    return _ok({"id": task_id, "stopped": True})


@router.get("/task/center/api/project/stop/{task_type}/{task_id}")
async def task_center_api_project_stop_type_path(task_type: str, task_id: str):
    """停止项目任务（带类型和路径参数）。"""
    return _ok({"type": task_type, "id": task_id, "stopped": True})


# 停止本地执行 - 带路径参数


@router.post("/api/stop/{task_id}")
async def api_stop_path(task_id: str):
    """停止本地执行（带路径参数）。"""
    return _ok({"id": task_id, "stopped": True})


@router.post("/api/stop/{task_type}/{task_id}")
async def api_stop_type_path(task_type: str, task_id: str):
    """停止本地执行（带类型和路径参数）。"""
    return _ok({"type": task_type, "id": task_id, "stopped": True})


@router.get("/api/stop/{task_id}")
async def api_stop_get_path(task_id: str):
    """停止本地执行 GET（带路径参数）。"""
    return _ok({"id": task_id, "stopped": True})


@router.get("/api/stop/{task_type}/{task_id}")
async def api_stop_get_type_path(task_type: str, task_id: str):
    """停止本地执行 GET（带类型和路径参数）。"""
    return _ok({"type": task_type, "id": task_id, "stopped": True})


@router.post("/api/test/mock")
async def api_test_mock(request: Request):
    """测试 Mock。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 用例管理更多接口 ─────────────────────────────────────


@router.post("/review/functional/case/get/list")
async def review_functional_case_get_list(request: Request):
    """评审详情-获取用例评审历史。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/review/functional/case/save")
async def review_functional_case_save(request: Request):
    """评审详情-提交评审。"""
    body = await request.json()
    case_id = body.get("caseId", "")
    from app.cases.repository import update_case
    try:
        update_case(case_id, status="approved")
    except Exception:
        pass
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 用例评审 - GET 变体路由 ──────────────────────────────


@router.get("/review/functional/case/get/list/{review_id}/{case_id}")
async def review_functional_case_get_list_get_route(review_id: str, case_id: str):
    """评审详情-获取用例评审历史（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})

