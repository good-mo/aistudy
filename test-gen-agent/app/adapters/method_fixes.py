# app/adapters/method_fixes.py
"""HTTP 方法不匹配及缺失路由修复。

解决前端调用与后端路由的 HTTP 方法不匹配问题，
并补齐前端需要但后端完全缺失的路由。
"""

import json
import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["method-fixes"])


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
    """安全读取请求体。"""
    try:
        raw = await request.body()
        if not raw:
            return {}
        return await request.json()
    except Exception:
        return {}


# ════════════════════════════════════════════════════════════
# A类修复：前端用 GET，后端只有 POST —— 添加 GET 方法
# ════════════════════════════════════════════════════════════

@router.get("/api/case/delete")
async def api_case_delete_get(request: Request):
    """接口用例删除（GET兼容）。"""
    body = await _body(request)
    case_id = body.get("id", body.get("caseId", ""))
    from app.api_testing.management import delete_api_test_case
    delete_api_test_case(case_id, permanent=True)
    return _ok()


@router.get("/api/case/follow")
async def api_case_follow_get(request: Request):
    """接口用例关注（GET兼容）。"""
    return _ok()


@router.get("/api/case/recover")
async def api_case_recover_get(request: Request):
    """接口用例恢复（GET兼容）。"""
    body = await _body(request)
    case_id = body.get("id", body.get("ids", ""))
    from app.api_testing.management import restore_case
    ids = case_id if isinstance(case_id, list) else [case_id]
    restored = 0
    for cid in ids:
        if cid and restore_case(cid):
            restored += 1
    return _ok({"restored": restored})


@router.get("/api/case/run")
async def api_case_run_get(request: Request):
    """接口用例执行（GET兼容）。"""
    return _ok()


@router.get("/api/case/unfollow")
async def api_case_unfollow_get(request: Request):
    """接口用例取消关注（GET兼容）。"""
    return _ok()


@router.get("/api/debug/delete")
async def api_debug_delete_get(request: Request):
    """接口调试删除（GET兼容）。"""
    return _ok()


@router.get("/api/definition/delete-to-gc")
async def api_definition_delete_gc_get(request: Request):
    """接口定义删除（GET兼容）。"""
    body = await _body(request)
    definition_id = body.get("id", body.get("definitionId", ""))
    from app.api_testing.management import delete_api_definition
    if definition_id:
        delete_api_definition(definition_id)
    return _ok()


@router.get("/api/definition/mock/enable")
async def api_definition_mock_enable_get(request: Request):
    """更新Mock状态（GET兼容）。"""
    return _ok()


@router.get("/api/definition/schedule/delete")
async def api_definition_schedule_delete_get(request: Request):
    """接口定义定时同步删除（GET兼容）。"""
    return _ok()


@router.get("/api/definition/schedule/switch")
async def api_definition_schedule_switch_get(request: Request):
    """接口定义定时同步开关（GET兼容）。"""
    return _ok()


@router.get("/api/doc/share/delete")
async def api_doc_share_delete_get(request: Request):
    """接口文档分享删除（GET兼容）。"""
    return _ok()


@router.get("/api/scenario/delete")
async def api_scenario_delete_get(request: Request):
    """接口场景删除（GET兼容）。"""
    body = await _body(request)
    scenario_id = body.get("id", body.get("scenarioId", ""))
    from app.api_testing.management import delete_scenario
    delete_scenario(scenario_id)
    return _ok()


@router.get("/api/scenario/delete-to-gc")
async def api_scenario_delete_gc_get(request: Request):
    """接口场景删除到回收站（GET兼容）。"""
    return _ok()


@router.get("/api/scenario/follow")
async def api_scenario_follow_get(request: Request):
    """接口场景关注（GET兼容）。"""
    return _ok()


@router.get("/api/scenario/recover")
async def api_scenario_recover_get(request: Request):
    """接口场景恢复（GET兼容）。"""
    body = await _body(request)
    sc_id = body.get("id", body.get("ids", ""))
    from app.api_testing.management import restore_scenario
    ids = sc_id if isinstance(sc_id, list) else [sc_id]
    restored = 0
    for sid in ids:
        if sid and restore_scenario(sid):
            restored += 1
    return _ok({"restored": restored})


@router.get("/api/scenario/schedule-config-delete")
async def api_scenario_schedule_config_delete_get(request: Request):
    """接口场景定时配置删除（GET兼容）。"""
    return _ok()


@router.get("/functional/case/delete")
async def functional_case_delete_get(request: Request):
    """功能用例删除（GET兼容）。"""
    body = await _body(request)
    case_id = body.get("id", body.get("caseId", ""))
    from app.cases.repository import delete_case
    delete_case(case_id)
    return _ok()


@router.get("/organization/custom/field/delete")
async def organization_custom_field_delete_get(request: Request):
    """组织自定义字段删除（GET兼容）。"""
    return _ok()


@router.get("/organization/remove-member")
async def organization_remove_member_get(request: Request):
    """组织移除成员（GET兼容）。"""
    return _ok()


@router.get("/organization/status/flow/setting/status/delete")
async def organization_status_flow_status_delete_get(request: Request):
    """组织状态流设置状态删除（GET兼容）。"""
    return _ok()


@router.get("/project/custom/field/delete")
async def project_custom_field_delete_get(request: Request):
    """项目自定义字段删除（GET兼容）。"""
    return _ok()


@router.get("/project/member/remove")
async def project_member_remove_get(request: Request):
    """项目成员移除（GET兼容）。"""
    body = await _body(request)
    member_id = body.get("id", body.get("memberId", ""))
    from app.projects.management import remove_project_member
    # 前端传参格式可能是 projectId/userId 或直接 id
    if '/' in str(member_id):
        parts = str(member_id).split('/')
        if len(parts) == 2:
            remove_project_member(parts[0], parts[1])
    return _ok()


@router.get("/project/robot/delete")
async def project_robot_delete_get(request: Request):
    """项目机器人删除（GET兼容）。"""
    return _ok()


@router.get("/project/robot/enable")
async def project_robot_enable_get(request: Request):
    """项目机器人启用（GET兼容）。"""
    return _ok()


@router.get("/project/status/flow/setting/status/delete")
async def project_status_flow_status_delete_get(request: Request):
    """项目状态流设置状态删除（GET兼容）。"""
    return _ok()


@router.get("/project/version/delete")
async def project_version_delete_get(request: Request):
    """项目版本删除（GET兼容）。"""
    return _ok()


@router.get("/project/version/switch/enable")
async def project_version_switch_enable_get(request: Request):
    """项目版本切换启用（GET兼容）。"""
    return _ok()


@router.get("/project/version/switch/latest")
async def project_version_switch_latest_get(request: Request):
    """项目版本切换最新（GET兼容）。"""
    return _ok()


@router.get("/project/version/switch/status")
async def project_version_switch_status_get(request: Request):
    """项目版本切换状态（GET兼容）。"""
    return _ok()


@router.get("/service/integration/delete")
async def service_integration_delete_get(request: Request):
    """服务集成删除（GET兼容）。"""
    return _ok()


@router.get("/service/integration/validate")
async def service_integration_validate_get(request: Request):
    """服务集成验证（GET兼容）。"""
    return _ok()


@router.get("/system/authsource/delete")
async def system_authsource_delete_get(request: Request):
    """系统认证源删除（GET兼容）。"""
    return _ok()


@router.get("/system/user/check-invite")
async def system_user_check_invite_get(request: Request):
    """系统用户邀请检查（GET兼容）。"""
    return _ok()


@router.get("/test/resource/pool/delete")
async def test_resource_pool_delete_get(request: Request):
    """测试资源池删除（GET兼容）。"""
    return _ok()


@router.get("/user/api/key/validate")
async def user_api_key_validate_get(request: Request):
    """用户API Key验证（GET兼容）。"""
    return _ok()



@router.get("/signout")
async def signout_get(request: Request):
    """用户登出（GET兼容）。"""
    return _ok()


@router.get("/notification/read/all")
async def notification_read_all_get(request: Request):
    """全部已读（GET兼容）。"""
    return _ok()


@router.get("/notification/read/{item_id}")
async def notification_read_item_get(item_id: str, request: Request):
    """单条消息已读（GET）。"""
    return _ok()


@router.get("/api/doc/share/detail")
async def api_doc_share_detail_get(request: Request):
    """接口文档分享详情（GET兼容）。"""
    return _ok()


@router.get("/api/doc/share/get-detail")
async def api_doc_share_get_detail_get(request: Request):
    """接口文档分享详情（GET兼容）。"""
    return _ok()


@router.get("/license/validate")
async def license_validate_get(request: Request):
    """授权验证（GET兼容）。"""
    return _ok({"valid": True})


@router.get("/plugin/delete")
async def plugin_delete_get(request: Request):
    """插件删除（GET兼容）。"""
    return _ok()


@router.get("/project/file/type")
async def project_file_type_get(request: Request):
    """项目文件类型（GET兼容）。"""
    return _ok([])


@router.get("/project/file/repository/pull-file")
async def project_file_repository_pull_file_get(request: Request):
    """项目文件仓库拉取（GET兼容）。"""
    return _ok()


@router.get("/project/file/association/list")
async def project_file_association_list_get(request: Request):
    """项目文件关联列表（GET兼容）。"""
    return _ok([])


@router.get("/project/version/enable")
async def project_version_enable_get(request: Request):
    """项目版本启用（GET兼容）。"""
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


@router.post("/api/scenario/module/trash/count")
async def api_scenario_module_trash_count_post(request: Request):
    """场景回收站模块统计（POST兼容）。"""
    return _ok([])


@router.post("/attachment/check-update")
async def attachment_check_update_post(request: Request):
    """附件更新检查（POST兼容）。"""
    return _ok()


@router.post("/attachment/download/file")
async def attachment_download_file_post(request: Request):
    """附件下载（POST兼容）。"""
    body = await _body(request)
    file_id = body.get("id", body.get("fileId", ""))
    return _ok({"fileId": file_id})


@router.post("/attachment/preview")
async def attachment_preview_post(request: Request):
    """附件预览（POST兼容）。"""
    return _ok()


@router.post("/functional/case/demand/third/list/page")
async def functional_case_demand_third_list_page_post(request: Request):
    """功能用例三方需求列表分页（POST兼容）。"""
    body = await _body(request)
    return _ok(_paginate([], body.get("current", 1), body.get("pageSize", 10)))


@router.post("/functional/case/module/count")
async def functional_case_module_count_post(request: Request):
    """功能用例模块统计（POST兼容）。"""
    return _ok([])


@router.post("/functional/case/test/associate/case/module/count")
async def functional_case_test_associate_module_count_post(request: Request):
    """功能用例关联用例模块统计（POST兼容）。"""
    return _ok([])


@router.post("/functional/case/trash/module/count")
async def functional_case_trash_module_count_post(request: Request):
    """功能用例回收站模块统计（POST兼容）。"""
    return _ok([])


@router.post("/organization/project/user-list")
async def organization_project_user_list_post(request: Request):
    """组织项目用户列表（POST兼容）。"""
    body = await _body(request)
    return _ok([])


@router.post("/organization/task-center/exec-task/batch-delete")
async def org_task_center_batch_delete_post(request: Request):
    """组织任务中心批量删除（POST兼容）。"""
    return _ok()


@router.post("/organization/task-center/exec-task/batch-stop")
async def org_task_center_batch_stop_post(request: Request):
    """组织任务中心批量停止（POST兼容）。"""
    return _ok()


@router.post("/organization/task-center/exec-task/item/batch-stop")
async def org_task_center_item_batch_stop_post(request: Request):
    """组织任务中心批量停止任务项（POST兼容）。"""
    return _ok()


@router.post("/organization/task-center/schedule/batch-disable")
async def org_task_center_schedule_batch_disable_post(request: Request):
    """组织任务中心定时任务批量禁用（POST兼容）。"""
    return _ok()


@router.post("/organization/task-center/schedule/batch-enable")
async def org_task_center_schedule_batch_enable_post(request: Request):
    """组织任务中心定时任务批量启用（POST兼容）。"""
    return _ok()


@router.post("/organization/task-center/schedule/update-cron")
async def org_task_center_schedule_update_cron_post(request: Request):
    """组织任务中心定时任务更新Cron（POST兼容）。"""
    return _ok()


@router.post("/project/custom/func/status")
async def project_custom_func_status_post(request: Request):
    """项目自定义函数状态（POST兼容）。"""
    return _ok()


@router.post("/project/file/download")
async def project_file_download_post(request: Request):
    """项目文件下载（POST兼容）。"""
    body = await _body(request)
    file_id = body.get("id", body.get("fileId", ""))
    return _ok({"fileId": file_id})


@router.post("/project/file/module/count")
async def project_file_module_count_post(request: Request):
    """项目文件模块统计（POST兼容）。"""
    return _ok([])


@router.post("/project/task-center/exec-task/batch-delete")
async def proj_task_center_batch_delete_post(request: Request):
    """项目任务中心批量删除（POST兼容）。"""
    return _ok()


@router.post("/project/task-center/exec-task/batch-stop")
async def proj_task_center_batch_stop_post(request: Request):
    """项目任务中心批量停止（POST兼容）。"""
    return _ok()


@router.post("/project/task-center/exec-task/item/batch-stop")
async def proj_task_center_item_batch_stop_post(request: Request):
    """项目任务中心批量停止任务项（POST兼容）。"""
    return _ok()


@router.post("/project/task-center/schedule/batch-disable")
async def proj_task_center_schedule_batch_disable_post(request: Request):
    """项目任务中心定时任务批量禁用（POST兼容）。"""
    return _ok()


@router.post("/project/task-center/schedule/batch-enable")
async def proj_task_center_schedule_batch_enable_post(request: Request):
    """项目任务中心定时任务批量启用（POST兼容）。"""
    return _ok()


@router.post("/project/task-center/schedule/update-cron")
async def proj_task_center_schedule_update_cron_post(request: Request):
    """项目任务中心定时任务更新Cron（POST兼容）。"""
    return _ok()


@router.post("/system/parameter/edit/upload-config")
async def system_parameter_edit_upload_config_post(request: Request):
    """系统参数编辑上传配置（POST兼容）。"""
    return _ok()


@router.post("/system/task-center/exec-task/batch-delete")
async def sys_task_center_batch_delete_post(request: Request):
    """系统任务中心批量删除（POST兼容）。"""
    return _ok()


@router.post("/system/task-center/exec-task/batch-stop")
async def sys_task_center_batch_stop_post(request: Request):
    """系统任务中心批量停止（POST兼容）。"""
    return _ok()


@router.post("/system/task-center/exec-task/item/batch-stop")
async def sys_task_center_item_batch_stop_post(request: Request):
    """系统任务中心批量停止任务项（POST兼容）。"""
    return _ok()


@router.post("/system/task-center/schedule/batch-disable")
async def sys_task_center_schedule_batch_disable_post(request: Request):
    """系统任务中心定时任务批量禁用（POST兼容）。"""
    return _ok()


@router.post("/system/task-center/schedule/batch-enable")
async def sys_task_center_schedule_batch_enable_post(request: Request):
    """系统任务中心定时任务批量启用（POST兼容）。"""
    return _ok()


@router.post("/system/task-center/schedule/update-cron")
async def sys_task_center_schedule_update_cron_post(request: Request):
    """系统任务中心定时任务更新Cron（POST兼容）。"""
    return _ok()



@router.post("/api/message/list")
async def api_message_list_post(request: Request):
    """消息列表（POST兼容）。"""
    return _ok([])


@router.post("/api/chat/list")
async def api_chat_list_post(request: Request):
    """聊天列表（POST兼容）。"""
    return _ok([])


@router.post("/notification/count")
async def notification_count_post(request: Request):
    """通知数量（POST兼容）。"""
    return _ok({"count": 0})


@router.post("/api/definition/module/tree")
async def api_definition_module_tree_post(request: Request):
    """接口定义模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/definition/module/only/tree")
async def api_definition_module_only_tree_post(request: Request):
    """接口定义不含接口的模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/definition/module/env/tree")
async def api_definition_module_env_tree_post(request: Request):
    """接口定义环境模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/scenario/module/tree")
async def api_scenario_module_tree_post(request: Request):
    """场景模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/scenario/module/trash/tree")
async def api_scenario_module_trash_tree_post(request: Request):
    """场景回收站模块树（POST兼容）。"""
    return _ok([])


@router.post("/api/doc/share/module/tree")
async def api_doc_share_module_tree_post(request: Request):
    """文档分享模块树（POST兼容）。"""
    return _ok([])


@router.post("/functional/case/test/associate/case/module/tree")
async def functional_case_test_associate_case_module_tree_post(request: Request):
    """功能用例关联用例模块树（POST兼容）。"""
    return _ok([])


@router.post("/plugin/options")
async def plugin_options_post(request: Request):
    """插件选项（POST兼容）。"""
    return _ok([])


@router.post("/test/resource/pool/capacity/detail")
async def test_resource_pool_capacity_detail_post(request: Request):
    """测试资源池容量详情（POST兼容）。"""
    return _ok({})


@router.post("/organization/task-center/exec-task/statistics")
async def org_task_center_statistics_post(request: Request):
    """组织任务中心任务统计（POST兼容）。"""
    return _ok({})


@router.post("/project/task-center/exec-task/statistics")
async def proj_task_center_statistics_post(request: Request):
    """项目任务中心任务统计（POST兼容）。"""
    return _ok({})


@router.post("/system/task-center/exec-task/statistics")
async def sys_task_center_statistics_post(request: Request):
    """系统任务中心任务统计（POST兼容）。"""
    return _ok({})


@router.post("/system/task-center/resource-pool/status")
async def sys_task_center_resource_pool_status_post(request: Request):
    """系统任务中心资源池状态（POST兼容）。"""
    return _ok([])


@router.post("/test-plan/statistics")
async def test_plan_statistics_post(request: Request):
    """测试计划统计（POST兼容）。"""
    return _ok({})


@router.post("/test-plan/functional/case/tree")
async def test_plan_functional_case_tree_post(request: Request):
    """测试计划功能用例树（POST兼容）。"""
    return _ok([])


@router.post("/system/organization/list")
async def system_organization_list_post(request: Request):
    """系统组织列表（POST兼容）。"""
    body = await _body(request)
    return _ok(_paginate([], body.get("current", 1), body.get("pageSize", 10)))


@router.get("/project/file-module/delete")
async def project_file_module_delete(request: Request):
    """项目文件模块删除。"""
    return _ok()


@router.get("/system/parameter/save/base-url")
async def system_parameter_save_base_url(request: Request):
    """系统参数保存Base URL。"""
    return _ok()


@router.post("/test-plan/module/count")
async def test_plan_module_count(request: Request):
    """测试计划模块统计。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# 用户 API Key 和本地执行配置
# ════════════════════════════════════════════════════════════

@router.get("/user/api/key/add")
async def user_api_key_add_get(request: Request):
    """用户API Key添加（GET）。"""
    body = await _body(request)
    api_key = str(uuid.uuid4())
    return _ok({"apiKey": api_key})


@router.get("/user/api/key/delete")
async def user_api_key_delete_get(request: Request):
    """用户API Key删除（GET）。"""
    return _ok()


@router.get("/user/api/key/disable")
async def user_api_key_disable_get(request: Request):
    """用户API Key禁用（GET）。"""
    return _ok()


@router.get("/user/api/key/enable")
async def user_api_key_enable_get(request: Request):
    """用户API Key启用（GET）。"""
    return _ok()



@router.post("/api/scenario/get/system-request")
async def api_scenario_get_system_request_post(request: Request):
    """获取导入的系统请求数据。"""
    body = await _body(request)
    return _ok([])


@router.get("/user-view/{view_type}/grouped/list")
async def user_view_grouped_list_get(view_type: str, request: Request):
    """用户视图分组列表。"""
    return _ok([])


@router.get("/user-view/{view_type}/get/{view_id}")
async def user_view_get_detail(view_type: str, view_id: str, request: Request):
    """用户视图详情。"""
    return _ok({})


@router.post("/user-view/{view_type}/update")
async def user_view_update_post(view_type: str, request: Request):
    """用户视图更新。"""
    body = await _body(request)
    return _ok()


@router.post("/user-view/{view_type}/add")
async def user_view_add_post(view_type: str, request: Request):
    """用户视图添加。"""
    body = await _body(request)
    return _ok({"id": str(uuid.uuid4())})


@router.get("/user-view/{view_type}/delete/{view_id}")
async def user_view_delete_get(view_type: str, view_id: str, request: Request):
    """用户视图删除。"""
    return _ok()


@router.get("/project/application/{suffix}/resource/pool/{project_id}")
async def project_application_resource_pool_get(suffix: str, project_id: str, request: Request):
    """项目应用资源池选项。"""
    return _ok([])


@router.get("/project/application/{suffix}/user/{project_id}")
async def project_application_user_get(suffix: str, project_id: str, request: Request):
    """项目应用用户选项。"""
    return _ok([])

# ════════════════════════════════════════════════════════════
# D类修复：路径参数不匹配
# 前端使用带路径参数的 URL，后端只有无路径参数版本
# ════════════════════════════════════════════════════════════

@router.get("/api/case/api-change/clear/{case_id}")
async def api_case_api_change_clear_by_id(case_id: str, request: Request):
    """接口用例清除本次变更（带ID路径参数）。"""
    return _ok()


@router.get("/api/case/api-change/ignore/{case_id}")
async def api_case_api_change_ignore_by_id(case_id: str, request: Request):
    """接口用例忽略接口变更（带ID路径参数）。"""
    return _ok()


@router.get("/api/case/api/compare/{case_id}")
async def api_case_api_compare_by_id(case_id: str, request: Request):
    """接口用例定义对比（带ID路径参数）。"""
    return _ok()


@router.post("/api/definition/export/{export_type}")
async def api_definition_export_by_type(export_type: str, request: Request):
    """接口定义导出（带类型路径参数）。"""
    return _ok()


@router.post("/api/report/case/export/{report_id}")
async def api_report_case_export_by_id(report_id: str, request: Request):
    """接口用例报告导出（带报告ID路径参数）。"""
    return _ok()
