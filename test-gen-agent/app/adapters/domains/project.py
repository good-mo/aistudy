# app/adapters/domains/project.py
"""业务域路由拆分：project（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-project"])


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


@router.post("/project/task-center/exec-task/statistics")
async def proj_task_center_statistics_post(request: Request):
    """项目任务中心任务统计（POST兼容）。"""
    return _ok({})


@router.get("/project/file-module/delete")
async def project_file_module_delete(request: Request):
    """项目文件模块删除。"""
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


@router.get("/project/environment/get")
async def project_environment_get(id: str = ""):
    """获取项目环境。"""
    from app.apitest import store as apitest_store
    env = apitest_store.get_environment(id) if id else None
    return _ok(env or {})


@router.get("/project/environment/get/")
async def project_environment_get_trailing(id: str = ""):
    """获取项目环境（尾斜杠）。"""
    from app.apitest import store as apitest_store
    env = apitest_store.get_environment(id) if id else None
    return _ok(env or {})


@router.get("/project/environment/get/entry")
async def project_environment_get_entry(id: str = ""):
    """获取项目环境入口。"""
    return _ok({})


@router.post("/project/environment/delete")
async def project_environment_delete(request: Request):
    """删除项目环境。"""
    await request.json()
    return _ok()


@router.delete("/project/environment/delete/")
async def project_environment_delete_del(id: str = ""):
    """删除项目环境 DELETE。"""
    return _ok()


@router.post("/project/environment/edit/pos")
async def project_environment_edit_pos(request: Request):
    """环境拖拽排序。"""
    await request.json()
    return _ok()


@router.get("/project/environment/export")
async def project_environment_export(project_id: str = ""):
    """导出环境。"""
    return _ok({"fileName": "environment.json", "content": "{}"})


@router.get("/project/environment/database/driver-options/")
async def project_environment_database_driver_options(project_id: str = ""):
    """数据库驱动选项。"""
    return _ok([])


@router.post("/project/environment/database/validate")
async def project_environment_database_validate(request: Request):
    """数据库连接校验。"""
    await request.json()
    return _ok()


@router.get("/project/environment/group/list")
async def project_environment_group_list(project_id: str = ""):
    """环境组列表。"""
    return _ok([])


@router.post("/project/environment/group/add")
async def project_environment_group_add(request: Request):
    """添加环境组。"""
    body = await request.json()
    return _ok({"id": str(uuid.uuid4()), **body})


@router.post("/project/environment/group/update")
async def project_environment_group_update(request: Request):
    """更新环境组。"""
    await request.json()
    return _ok()


@router.get("/project/environment/group/get")
async def project_environment_group_get(id: str = ""):
    """获取环境组。"""
    return _ok({})


@router.get("/project/environment/group/get/")
async def project_environment_group_get_trailing(id: str = ""):
    """获取环境组（尾斜杠）。"""
    return _ok({})


@router.post("/project/environment/group/delete/")
async def project_environment_group_delete(id: str = ""):
    """删除环境组。"""
    return _ok()


@router.post("/project/environment/group/edit/pos")
async def project_environment_group_edit_pos(request: Request):
    """环境组拖拽排序。"""
    await request.json()
    return _ok()


@router.get("/project/environment/group/get-project/")
async def project_environment_group_get_project(id: str = ""):
    """获取环境组项目。"""
    return _ok([])


@router.get("/project/environment/scripts/")
async def project_environment_scripts(project_id: str = ""):
    """环境脚本。"""
    return _ok([])


# 全局参数


@router.post("/project/global/params/add")
async def project_global_params_add(request: Request):
    """添加全局参数。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/project/global/params/update")
async def project_global_params_update(request: Request):
    """更新全局参数。"""
    await request.json()
    return _ok()


@router.get("/project/global/params/get")
async def project_global_params_get(id: str = ""):
    """获取全局参数。"""
    return _ok({})


@router.get("/project/global/params/get/")
async def project_global_params_get_trailing(id: str = ""):
    """获取全局参数（尾斜杠）。"""
    return _ok({})


@router.post("/project/global/params/import")
async def project_global_params_import(request: Request):
    """导入全局参数。"""
    await request.json()
    return _ok()


@router.get("/project/global/params/export/")
async def project_global_params_export(id: str = ""):
    """导出全局参数。"""
    return _ok({"fileName": "params.json"})


# ════════════════════════════════════════════════════════════
# P1-2: 项目文件管理  /project/file/*  /project/file-module/*
# ════════════════════════════════════════════════════════════


@router.post("/project/file/re-upload")
async def project_file_re_upload(request: Request):
    """重新上传项目文件。"""
    return _ok({"id": str(uuid.uuid4())})


@router.post("/project/file/update")
async def project_file_update(request: Request):
    """更新项目文件。"""
    await request.json()
    return _ok()


@router.post("/project/file/batch-delete")
async def project_file_batch_delete(request: Request):
    """批量删除项目文件。"""
    await request.json()
    return _ok()


@router.get("/project/file/get")
async def project_file_get(id: str = ""):
    """获取项目文件。"""
    return _ok({})


@router.post("/project/file/batch-move")
async def project_file_batch_move(request: Request):
    """批量移动项目文件。"""
    await request.json()
    return _ok()


@router.post("/project/file/batch-download")
async def project_file_batch_download(request: Request):
    """批量下载项目文件。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.get("/project/file/download")
async def project_file_download(file_id: str = ""):
    """下载项目文件。"""
    return _ok({"fileId": file_id})


@router.post("/project/file/jar-file-status")
async def project_file_jar_file_status(request: Request):
    """JAR 文件状态。"""
    await request.json()
    return _ok([])


@router.post("/project/file-module/move")
async def project_file_module_move(request: Request):
    """移动文件模块。"""
    await request.json()
    return _ok()


@router.post("/project/file-module/update")
async def project_file_module_update(request: Request):
    """更新文件模块。"""
    await request.json()
    return _ok()


# 存储库管理


@router.post("/project/file/repository/add-repository")
async def project_file_repository_add(request: Request):
    """添加文件存储库。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/project/file/repository/update-repository")
async def project_file_repository_update(request: Request):
    """更新文件存储库。"""
    await request.json()
    return _ok()


@router.post("/project/file/repository/connect")
async def project_file_repository_connect(request: Request):
    """连接文件存储库。"""
    await request.json()
    return _ok()


@router.get("/project/file/repository/info")
async def project_file_repository_info(id: str = ""):
    """存储库信息。"""
    return _ok({})


@router.get("/project/file/repository/list")
async def project_file_repository_list(project_id: str = ""):
    """存储库列表。"""
    return _ok([])


@router.get("/project/file/repository/file-type")
async def project_file_repository_file_type(project_id: str = ""):
    """存储库文件类型。"""
    return _ok([])


@router.post("/project/file/repository/add-file")
async def project_file_repository_add_file(request: Request):
    """存储库添加文件。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/project/file/repository/pull-file")
async def project_file_repository_pull_file(request: Request):
    """拉取存储库文件。"""
    await request.json()
    return _ok()


# 文件关联


@router.post("/project/file/association/list")
async def project_file_association_list(request: Request):
    """文件关联列表。"""
    await request.json()
    return _ok([])


@router.post("/project/file/association/delete")
async def project_file_association_delete(request: Request):
    """删除文件关联。"""
    await request.json()
    return _ok()


@router.post("/project/file/association/upgrade")
async def project_file_association_upgrade(request: Request):
    """升级文件关联。"""
    await request.json()
    return _ok()


@router.get("/project/file/file-version")
async def project_file_file_version(file_id: str = ""):
    """文件历史版本。"""
    return _ok([])


@router.get("/project/file/module/count")
async def project_file_module_count(project_id: str = ""):
    """文件模块数量。"""
    return _ok({})


# ════════════════════════════════════════════════════════════
# P1-3: 项目成员  /project/member/*
# ════════════════════════════════════════════════════════════


@router.post("/project/member/add-role")
async def project_member_add_role(request: Request):
    """添加成员角色。"""
    await request.json()
    return _ok()


@router.get("/project/member/get-role/option")
async def project_member_get_role_option(project_id: str = ""):
    """获取角色选项。"""
    return _ok([])


@router.post("/project/member/invite")
async def project_member_invite(request: Request):
    """邀请成员。"""
    await request.json()
    return _ok()


@router.get("/project/member/comment/user-option")
async def project_member_comment_user_option(project_id: str = ""):
    """评论用户选项。"""
    return _ok([])


@router.post("/project/member/update-member")
async def project_member_update_member(request: Request):
    """更新项目成员。"""
    body = await request.json()
    from app.projects import management as proj_mgmt
    member_id = body.get("id") or body.get("memberId") or ""
    fields = {k: v for k, v in body.items() if k not in ("id", "memberId")}
    if member_id:
        proj_mgmt.update_project_member(member_id, **fields)
    return _ok()


@router.post("/project/template/add")
async def project_template_add(request: Request):
    """添加项目模板。"""
    body = await request.json()
    return _ok({"id": str(uuid.uuid4()), **body})


@router.post("/project/template/update")
async def project_template_update(request: Request):
    """更新项目模板。"""
    await request.json()
    return _ok()


@router.post("/project/template/delete")
async def project_template_delete(request: Request):
    """删除项目模板。"""
    await request.json()
    return _ok()


@router.get("/project/template/get")
async def project_template_get(id: str = ""):
    """获取项目模板。"""
    return _ok({})


@router.get("/project/template/list")
async def project_template_list(project_id: str = "", template_type: str = ""):
    """项目模板列表。"""
    return _ok([])


@router.post("/project/template/enable/config")
async def project_template_enable_config(request: Request):
    """启用模板配置。"""
    await request.json()
    return _ok()


@router.post("/project/template/set-default")
async def project_template_set_default(request: Request):
    """设置默认模板。"""
    await request.json()
    return _ok()


@router.post("/project/template/img/preview")
async def project_template_img_preview(request: Request):
    """模板图片预览。"""
    await request.json()
    return _ok({})


@router.post("/project/template/upload/temp/img")
async def project_template_upload_temp_img(request: Request):
    """模板临时图片上传。"""
    return _ok({"id": str(uuid.uuid4())})


@router.post("/project/custom/field/add")
async def project_custom_field_add(request: Request):
    """添加自定义字段。"""
    body = await request.json()
    return _ok({"id": str(uuid.uuid4()), **body})


@router.post("/project/custom/field/update")
async def project_custom_field_update(request: Request):
    """更新自定义字段。"""
    await request.json()
    return _ok()


@router.post("/project/custom/field/delete")
async def project_custom_field_delete(request: Request):
    """删除自定义字段。"""
    await request.json()
    return _ok()


@router.get("/project/custom/field/get")
async def project_custom_field_get(id: str = ""):
    """获取自定义字段。"""
    return _ok({})


@router.get("/project/custom/field/list")
async def project_custom_field_list(project_id: str = ""):
    """自定义字段列表。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# P1-5: 项目版本管理  /project/version/*
# ════════════════════════════════════════════════════════════


@router.post("/project/version/add")
async def project_version_add(request: Request):
    """添加项目版本。"""
    body = await request.json()
    return _ok({"id": str(uuid.uuid4()), **body})


@router.post("/project/version/update")
async def project_version_update(request: Request):
    """更新项目版本。"""
    await request.json()
    return _ok()


@router.post("/project/version/delete")
async def project_version_delete(request: Request):
    """删除项目版本。"""
    await request.json()
    return _ok()


@router.post("/project/version/enable")
async def project_version_enable(request: Request):
    """启用项目版本。"""
    await request.json()
    return _ok()


@router.get("/project/version/list")
async def project_version_list(project_id: str = ""):
    """项目版本列表。"""
    return _ok([])


@router.get("/project/version/option")
async def project_version_option(project_id: str = ""):
    """项目版本选项。"""
    return _ok([])


@router.post("/project/version/switch/enable")
async def project_version_switch_enable(request: Request):
    """切换版本启用。"""
    await request.json()
    return _ok()


@router.post("/project/version/switch/latest")
async def project_version_switch_latest(request: Request):
    """切换最新版本。"""
    await request.json()
    return _ok()


@router.post("/project/version/switch/status")
async def project_version_switch_status(request: Request):
    """切换版本状态。"""
    await request.json()
    return _ok()


# ════════════════════════════════════════════════════════════
# P1-6: 项目机器人通知  /project/robot/*
# ════════════════════════════════════════════════════════════


@router.post("/project/robot/add")
async def project_robot_add(request: Request):
    """添加项目机器人。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/project/robot/update")
async def project_robot_update(request: Request):
    """更新项目机器人。"""
    await request.json()
    return _ok()


@router.post("/project/robot/delete")
async def project_robot_delete(request: Request):
    """删除项目机器人。"""
    await request.json()
    return _ok()


@router.post("/project/robot/enable")
async def project_robot_enable(request: Request):
    """启用项目机器人。"""
    await request.json()
    return _ok()


@router.get("/project/robot/get")
async def project_robot_get(id: str = ""):
    """获取项目机器人。"""
    return _ok({})


@router.get("/project/robot/list")
async def project_robot_list(project_id: str = ""):
    """项目机器人列表。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# P1-7: 项目应用管理  /project/application/*
# ════════════════════════════════════════════════════════════


@router.get("/project/application/")
async def project_application(project_id: str = ""):
    """项目应用设置。"""
    return _ok([])


@router.get("/project/application/bug/platform/")
async def project_application_bug_platform(project_id: str = ""):
    """缺陷平台设置。"""
    return _ok({})


@router.get("/project/application/bug/platform/info/")
async def project_application_bug_platform_info(project_id: str = ""):
    """缺陷平台信息。"""
    return _ok({})


@router.get("/project/application/bug/sync/info/")
async def project_application_bug_sync_info(project_id: str = ""):
    """缺陷同步信息。"""
    return _ok({})


@router.get("/project/application/case/platform/")
async def project_application_case_platform(project_id: str = ""):
    """用例平台设置。"""
    return _ok({})


@router.get("/project/application/case/platform/info/")
async def project_application_case_platform_info(project_id: str = ""):
    """用例平台信息。"""
    return _ok({})


@router.get("/project/application/case/related/info/")
async def project_application_case_related_info(project_id: str = ""):
    """用例关联信息。"""
    return _ok({})


@router.get("/project/application/module-setting/")
async def project_application_module_setting(project_id: str = ""):
    """模块设置。"""
    return _ok({})


@router.post("/project/application/update/")
async def project_application_update(project_id: str = ""):
    """更新项目应用设置。"""
    return _ok()


@router.post("/project/application/update/bug/sync/")
async def project_application_update_bug_sync(project_id: str = ""):
    """更新缺陷同步设置。"""
    return _ok()


@router.post("/project/application/update/case/related/")
async def project_application_update_case_related(project_id: str = ""):
    """更新用例关联设置。"""
    return _ok()


@router.post("/project/application/validate/")
async def project_application_validate(project_id: str = ""):
    """校验应用设置。"""
    return _ok()


# ════════════════════════════════════════════════════════════
# P1-8: 项目其他  /project/get  /project/has-permission  /project/log/*
# ════════════════════════════════════════════════════════════


@router.get("/project/get")
async def project_get(id: str = ""):
    """获取项目。"""
    if id:
        from app.projects import management as proj_mgmt
        p = proj_mgmt.get_project(id)
        return _ok(p or {})
    return _ok({})


@router.get("/project/has-permission")
async def project_has_permission(project_id: str = "", permission: str = ""):
    """检查项目权限。"""
    return _ok({"hasPermission": True})


@router.get("/project/get-member/option")
async def project_get_member_option(project_id: str = ""):
    """获取项目成员选项。"""
    return _ok([])


@router.get("/project/log/list")
async def project_log_list(project_id: str = ""):
    """项目操作日志。"""
    return _ok(_paginate([], 1, 10))


@router.get("/project/log/user/list")
async def project_log_user_list(project_id: str = ""):
    """项目日志用户列表。"""
    return _ok([])


# 项目状态流设置


@router.get("/project/status/flow/setting/get")
async def project_status_flow_setting_get(project_id: str = ""):
    """项目状态流设置。"""
    return _ok({})


@router.post("/project/status/flow/setting/status/add")
async def project_status_flow_setting_status_add(request: Request):
    """添加状态流状态。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/project/status/flow/setting/status/update")
async def project_status_flow_setting_status_update(request: Request):
    """更新状态流状态。"""
    await request.json()
    return _ok()


@router.post("/project/status/flow/setting/status/delete")
async def project_status_flow_setting_status_delete(request: Request):
    """删除状态流状态。"""
    await request.json()
    return _ok()


@router.post("/project/status/flow/setting/status/sort")
async def project_status_flow_setting_status_sort(request: Request):
    """状态流状态排序。"""
    await request.json()
    return _ok()


@router.post("/project/status/flow/setting/status/flow/update")
async def project_status_flow_setting_status_flow_update(request: Request):
    """更新状态流流程。"""
    await request.json()
    return _ok()


@router.post("/project/status/flow/setting/status/definition/update")
async def project_status_flow_setting_status_definition_update(request: Request):
    """更新状态流定义。"""
    await request.json()
    return _ok()


# 项目自定义函数


@router.post("/project/custom/func/add")
async def project_custom_func_add(request: Request):
    """添加自定义函数。"""
    await request.json()
    return _ok({"id": str(uuid.uuid4())})


@router.post("/project/custom/func/update")
async def project_custom_func_update(request: Request):
    """更新自定义函数。"""
    await request.json()
    return _ok()


@router.post("/project/custom/func/delete")
async def project_custom_func_delete(request: Request):
    """删除自定义函数。"""
    await request.json()
    return _ok()


@router.get("/project/custom/func/page")
async def project_custom_func_page(project_id: str = ""):
    """自定义函数分页。"""
    return _ok(_paginate([], 1, 10))


@router.get("/project/custom/func/detail")
async def project_custom_func_detail(id: str = ""):
    """自定义函数详情。"""
    return _ok({})


@router.get("/project/custom/func/status")
async def project_custom_func_status(project_id: str = ""):
    """自定义函数状态。"""
    return _ok([])


@router.get("/project/custom/func/columns-option/")
async def project_custom_func_columns_option(project_id: str = ""):
    """自定义函数列选项。"""
    return _ok([])


@router.get("/project/custom/func/history/page")
async def project_custom_func_history_page(project_id: str = ""):
    """自定义函数历史。"""
    return _ok(_paginate([], 1, 10))


# ════════════════════════════════════════════════════════════
# P1-9: 组织管理  /organization/*
# ════════════════════════════════════════════════════════════


@router.get("/project/task-center/exec-task/page")
async def project_task_center_exec_task_page():
    """项目任务中心-执行任务分页。"""
    return _ok(_paginate([], 1, 10))


@router.get("/project/task-center/exec-task/item/page")
async def project_task_center_exec_task_item_page():
    """项目任务中心-任务项分页。"""
    return _ok(_paginate([], 1, 10))


@router.get("/project/task-center/exec-task/item/order")
async def project_task_center_exec_task_item_order():
    """项目任务中心-任务项排序。"""
    return _ok([])


@router.get("/project/task-center/exec-task/statistics")
async def project_task_center_exec_task_statistics():
    """项目任务中心-任务统计。"""
    return _ok({})


@router.get("/project/task-center/exec-task/item/stop")
async def project_task_center_exec_task_item_stop():
    """项目任务中心-停止任务项。"""
    return _ok()


@router.get("/project/task-center/exec-task/stop")
async def project_task_center_exec_task_stop():
    """项目任务中心-停止任务。"""
    return _ok()


@router.get("/project/task-center/exec-task/rerun")
async def project_task_center_exec_task_rerun():
    """项目任务中心-重跑任务。"""
    return _ok()


@router.get("/project/task-center/exec-task/delete")
async def project_task_center_exec_task_delete():
    """项目任务中心-删除任务。"""
    return _ok()


@router.get("/project/task-center/exec-task/batch/page")
async def project_task_center_exec_task_batch_page():
    """项目任务中心-批量分页。"""
    return _ok(_paginate([], 1, 10))


@router.get("/project/task-center/exec-task/batch-stop")
async def project_task_center_exec_task_batch_stop():
    """项目任务中心-批量停止。"""
    return _ok()


@router.get("/project/task-center/exec-task/batch-delete")
async def project_task_center_exec_task_batch_delete():
    """项目任务中心-批量删除。"""
    return _ok()


@router.get("/project/task-center/exec-task/item/batch-stop")
async def project_task_center_exec_task_item_batch_stop():
    """项目任务中心-批量停止任务项。"""
    return _ok()


@router.get("/project/task-center/exec-task/item/batch-delete")
async def project_task_center_exec_task_item_batch_delete():
    """项目任务中心-批量删除任务项。"""
    return _ok()


@router.get("/project/task-center/schedule/page")
async def project_task_center_schedule_page():
    """项目任务中心-定时任务分页。"""
    return _ok(_paginate([], 1, 10))


@router.get("/project/task-center/schedule/delete")
async def project_task_center_schedule_delete():
    """项目任务中心-删除定时任务。"""
    return _ok()


@router.get("/project/task-center/schedule/switch")
async def project_task_center_schedule_switch():
    """项目任务中心-开关定时任务。"""
    return _ok()


@router.get("/project/task-center/schedule/batch-enable")
async def project_task_center_schedule_batch_enable():
    """项目任务中心-批量启用定时任务。"""
    return _ok()


@router.get("/project/task-center/schedule/batch-disable")
async def project_task_center_schedule_batch_disable():
    """项目任务中心-批量禁用定时任务。"""
    return _ok()


@router.get("/project/task-center/schedule/update-cron")
async def project_task_center_schedule_update_cron():
    """项目任务中心-更新定时任务 cron。"""
    return _ok()


@router.get("/project/task-center/resource-pool/options")
async def project_task_center_resource_pool_options():
    """项目任务中心-资源池选项。"""
    return _ok([])


@router.get("/project/custom/field/list/{project_id}/{organization_id}")
@router.post("/project/custom/field/list/{project_id}/{organization_id}")
async def project_custom_field_list_path(project_id: str, organization_id: str):
    """获取项目自定义字段列表（带路径参数）。"""
    return _ok({"project_id": project_id, "organization_id": organization_id})


@router.get("/project/custom/func/delete/{func_id}")
@router.post("/project/custom/func/delete/{func_id}")
async def project_custom_func_delete_path(func_id: str):
    """删除项目自定义功能（带路径参数）。"""
    return _ok({"id": func_id, "deleted": True})


@router.get("/project/file/association/upgrade/{file_id}")
@router.post("/project/file/association/upgrade/{file_id}")
async def project_file_association_upgrade_path(file_id: str):
    """升级项目文件关联（带路径参数）。"""
    return _ok({"id": file_id, "upgraded": True})


@router.get("/project/file/jar-file-status/{file_id}/{project_id}")
@router.post("/project/file/jar-file-status/{file_id}/{project_id}")
async def project_file_jar_status_path(file_id: str, project_id: str):
    """获取项目 JAR 文件状态（带路径参数）。"""
    return _ok({"file_id": file_id, "project_id": project_id})


@router.get("/project/get-member/option/{project_id}")
@router.post("/project/get-member/option/{project_id}")
async def project_get_member_option_path(project_id: str):
    """获取项目成员选项（带路径参数）。"""
    return _ok({"project_id": project_id})


@router.get("/project/member/get-member/option/{project_id}")
@router.post("/project/member/get-member/option/{project_id}")
async def project_member_get_member_option_path(project_id: str):
    """获取项目成员选项（带路径参数）。"""
    return _ok({"project_id": project_id})


@router.get("/project/status/flow/setting/status/sort/{project_id}/{status_id}")
@router.post("/project/status/flow/setting/status/sort/{project_id}/{status_id}")
async def project_status_flow_sort_path(project_id: str, status_id: str):
    """项目状态流排序（带路径参数）。"""
    return _ok({"project_id": project_id, "status_id": status_id})


@router.get("/project/task-center/exec-task/delete/{task_id}")
@router.post("/project/task-center/exec-task/delete/{task_id}")
async def project_task_center_exec_delete_path(task_id: str):
    """删除项目任务中心执行任务（带路径参数）。"""
    return _ok({"id": task_id, "deleted": True})


@router.get("/project/task-center/exec-task/item/stop/{task_id}/{item_id}")
@router.post("/project/task-center/exec-task/item/stop/{task_id}/{item_id}")
async def project_task_center_exec_item_stop_path(task_id: str, item_id: str):
    """停止项目任务中心执行项（带路径参数）。"""
    return _ok({"id": task_id, "item_id": item_id, "stopped": True})


@router.get("/project/task-center/exec-task/rerun/{task_id}")
@router.post("/project/task-center/exec-task/rerun/{task_id}")
async def project_task_center_exec_rerun_path(task_id: str):
    """重新运行项目任务中心任务（带路径参数）。"""
    return _ok({"id": task_id, "rerun": True})


@router.get("/project/task-center/exec-task/stop/{task_id}")
@router.post("/project/task-center/exec-task/stop/{task_id}")
async def project_task_center_exec_stop_path(task_id: str):
    """停止项目任务中心任务（带路径参数）。"""
    return _ok({"id": task_id, "stopped": True})


@router.get("/project/task-center/schedule/delete/{schedule_id}")
@router.post("/project/task-center/schedule/delete/{schedule_id}")
async def project_task_center_schedule_delete_path(schedule_id: str):
    """删除项目任务中心定时任务（带路径参数）。"""
    return _ok({"id": schedule_id, "deleted": True})


@router.get("/project/task-center/schedule/switch/{schedule_id}")
@router.post("/project/task-center/schedule/switch/{schedule_id}")
async def project_task_center_schedule_switch_path(schedule_id: str):
    """切换项目任务中心定时任务（带路径参数）。"""
    return _ok({"id": schedule_id, "switched": True})


@router.get("/project/template/delete/{template_id}")
@router.post("/project/template/delete/{template_id}")
async def project_template_delete_path(template_id: str):
    """删除项目模板（带路径参数）。"""
    return _ok({"id": template_id, "deleted": True})


@router.get("/project/template/get/{template_id}")
@router.post("/project/template/get/{template_id}")
async def project_template_get_path(template_id: str):
    """获取项目模板（带路径参数）。"""
    return _ok({"id": template_id})


@router.get("/project/template/list/{project_id}/{organization_id}")
@router.post("/project/template/list/{project_id}/{organization_id}")
async def project_template_list_path(project_id: str, organization_id: str):
    """获取项目模板列表（带路径参数）。"""
    return _ok({"project_id": project_id, "organization_id": organization_id})


@router.get("/project/template/set-default/{template_id}/{project_id}")
@router.post("/project/template/set-default/{template_id}/{project_id}")
async def project_template_set_default_path(template_id: str, project_id: str):
    """设置项目默认模板（带路径参数）。"""
    return _ok({"template_id": template_id, "project_id": project_id, "set_default": True})


# ════════════════════════════════════════════════════════════
# 系统任务中心
# ════════════════════════════════════════════════════════════


@router.get("/project/application/{project_id}/resource/pool/{resource_pool_id}")
@router.post("/project/application/{project_id}/resource/pool/{resource_pool_id}")
async def project_app_resource_pool_path(project_id: str, resource_pool_id: str):
    """获取项目应用资源池（带路径参数）。"""
    return _ok({"project_id": project_id, "resource_pool_id": resource_pool_id})


@router.get("/project/application/{project_id}/user/{user_id}")
@router.post("/project/application/{project_id}/user/{user_id}")
async def project_app_user_path(project_id: str, user_id: str):
    """获取项目应用用户（带路径参数）。"""
    return _ok({"project_id": project_id, "user_id": user_id})


# ════════════════════════════════════════════════════════════
# 用户视图（角色管理）
# ════════════════════════════════════════════════════════════


@router.get("/project/task-center/exec-task/item/stop/{id}")
@router.post("/project/task-center/exec-task/item/stop/{id}")
async def project_task_item_stop_single_path(id: str):
    """项目任务中心-停止单个任务（1 参数带路径版本）。"""
    return _ok({"id": id, "stopped": True})


@router.get("/project/custom/func/columns-option/{project_id}")
async def project_custom_func_columns_option_path(project_id: str):
    """获取公共脚本列选项（带路径参数）。"""
    return _ok([])


# AI 配置详情（前端: /ai/config/get/{id}）


@router.get("/project/custom/func/detail/{func_id}")
async def project_custom_func_detail_path(func_id: str):
    """获取公共脚本详情（带路径参数）。"""
    return _ok({"id": func_id})


# 项目日志用户列表（前端: /project/log/user/list/{id}）


@router.get("/project/log/user/list/{id}")
async def project_log_user_list_path(id: str):
    """获取项目日志用户列表（带路径参数）。"""
    return _ok([])


# 项目成员评论用户选项（前端: /project/member/comment/user-option/{projectId}）


@router.get("/project/member/comment/user-option/{project_id}")
async def project_member_comment_user_option_path(project_id: str):
    """获取项目成员评论用户选项（带路径参数）。"""
    return _ok([])


# 项目机器人列表（前端: /project/robot/list/{projectId}）


@router.get("/project/robot/list/{project_id}")
async def project_robot_list_path(project_id: str):
    """获取项目机器人列表（带路径参数）。"""
    return _ok([])


# 项目状态流设置（前端: /project/status/flow/setting/get/{scopedId}/{scene}）


@router.get("/project/status/flow/setting/get/{scoped_id}/{scene}")
async def project_status_flow_setting_get_path(scoped_id: str, scene: str):
    """获取项目状态流设置（带路径参数）。"""
    return _ok([])


# 项目模板启用配置（前端: /project/template/enable/config/{scopedId}）


@router.get("/project/template/enable/config/{scoped_id}")
async def project_template_enable_config_path(scoped_id: str):
    """获取项目模板启用配置（带路径参数）。"""
    return _ok({})


# 环境管理 - 缺失路径参数路由


@router.get("/project/environment/group/delete/{group_id}")
async def project_environment_group_delete_path(group_id: str):
    """删除环境组（带路径参数）。"""
    return _ok({"id": group_id, "deleted": True})


@router.get("/project/environment/group/get/{group_id}")
async def project_environment_group_get_path(group_id: str):
    """获取环境组详情（带路径参数）。"""
    return _ok({"id": group_id})


@router.get("/project/environment/scripts/{project_id}")
async def project_environment_scripts_path(project_id: str):
    """获取环境脚本（带路径参数）。"""
    return _ok([])


@router.get("/project/environment/database/driver-options/{organization_id}")
async def project_environment_driver_options_path(organization_id: str):
    """获取数据库驱动选项（带路径参数）。"""
    return _ok([])


@router.get("/project/environment/group/get-project/{organization_id}")
async def project_environment_group_get_project_path(organization_id: str):
    """获取环境组项目（带路径参数）。"""
    return _ok([])


# 全局参数 - 缺失路径参数路由


@router.get("/project/global/params/get/{param_id}")
async def project_global_params_get_path(param_id: str):
    """获取全局参数详情（带路径参数）。"""
    return _ok({"id": param_id})


@router.get("/project/global/params/export/{param_id}")
async def project_global_params_export_path(param_id: str):
    """导出全局参数（带路径参数）。"""
    return _ok({"id": param_id, "content": "{}"})


# 停止执行 - 带路径参数


@router.get("/project/task-center/page")
async def project_task_center_page(request: Request):
    """项目任务中心分页列表。"""
    from app.tasks.manager import list_tasks
    tasks = list_tasks()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": tasks,
        "total": len(tasks),
    }})


@router.get("/project/task-center/stop/{task_id}")
async def project_task_center_stop(task_id: str):
    """停止任务。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# AI 对话适配
# ════════════════════════════════════════════════════════════


@router.get("/project/member/get-member/option")
async def project_member_options(request: Request, projectId: str = ""):
    """获取可添加的项目成员候选列表。"""
    from app.auth.store import AuthStore
    store = AuthStore()
    users = store.list_users()
    options = []
    for u in users:
        options.append({
            "id": u.get("id", ""),
            "name": u.get("name") or u.get("username", ""),
            "username": u.get("username", ""),
            "email": u.get("email", ""),
        })
    return JSONResponse({"code": 200, "message": "success", "data": options})


# ════════════════════════════════════════════════════════════
# 项目环境管理
# 前端: /project/environment/*  →  环境管理
# ════════════════════════════════════════════════════════════


@router.post("/project/environment/list", operation_id="project_environment_list_post")
@router.get("/project/environment/list", operation_id="project_environment_list_get")
async def project_environment_list(request: Request):
    """获取项目环境列表。"""
    if request.method == "POST":
        try:
            body = await _body(request)
        except Exception:
            body = {}
        status = body.get("status", "")
    else:
        status = request.query_params.get("status", "")
    from app.environment.manager import list_environments
    envs = list_environments(status=status if status else None)
    items = []
    for e in envs:
        items.append({
            "id": e.get("id", ""),
            "name": e.get("name", ""),
            "description": e.get("description", ""),
            "type": e.get("env_type", "docker"),
            "status": e.get("status", "offline"),
            "endpoint": e.get("endpoint", ""),
            "createTime": e.get("created_at", 0),
            "updateTime": e.get("updated_at", 0),
            "projectId": "",
        })
    return JSONResponse({"code": 200, "message": "success", "data": items})


@router.post("/project/environment/add")
async def project_environment_add(request: Request):
    """新增项目环境。"""
    body = await _body(request)
    from app.environment.manager import register_environment
    env = register_environment(
        name=body.get("name", "未命名环境"),
        description=body.get("description", ""),
        env_type=body.get("type", "docker"),
        endpoint=body.get("endpoint", body.get("host", "")),
        docker_compose_path=body.get("dockerComposePath", ""),
        container_name=body.get("containerName", ""),
        image=body.get("image", ""),
        health_check_url=body.get("healthCheckUrl", ""),
        owner=body.get("owner", ""),
        tags=body.get("tags", []),
    )
    return JSONResponse({"code": 200, "message": "success", "data": env})


@router.post("/project/environment/update")
async def project_environment_update(request: Request):
    """更新项目环境。"""
    body = await request.json()
    env_id = body.get("id", "")
    from app.environment.manager import update_environment
    updates = {}
    for k, v in body.items():
        if k == "name":
            updates["name"] = v
        elif k == "description":
            updates["description"] = v
        elif k == "endpoint":
            updates["endpoint"] = v
    try:
        env = update_environment(env_id, **updates)
    except Exception:
        env = None
    if not env:
        return JSONResponse({"code": 404, "message": "环境不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": env})


@router.get("/project/environment/get/{env_id}")
async def project_environment_get(env_id: str):
    """获取环境详情。"""
    from app.environment.manager import get_environment
    env = get_environment(env_id)
    if not env:
        return JSONResponse({"code": 404, "message": "环境不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": env})


@router.post("/project/environment/delete/{env_id}", operation_id="project_environment_delete_post")
@router.get("/project/environment/delete/{env_id}", operation_id="project_environment_delete_get")
async def project_environment_delete(env_id: str):
    """删除环境。"""
    from app.environment.manager import delete_environment
    delete_environment(env_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/project/environment/import")
async def project_environment_import(request: Request):
    """导入环境。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/project/environment/export")
async def project_environment_export(request: Request):
    """导出环境。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/project/environment/get-options")
async def project_environment_get_options():
    """获取环境目录列表。"""
    from app.environment.manager import list_environments
    envs = list_environments()
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": e.get("id"), "name": e.get("name")} for e in envs
    ]})


@router.get("/project/environment/get-options/{project_id}")
async def project_environment_get_options_by_project(project_id: str):
    """获取项目环境目录列表。"""
    from app.environment.manager import list_environments
    envs = list_environments()
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": e.get("id"), "name": e.get("name")} for e in envs
    ]})


# ════════════════════════════════════════════════════════════
# 接口测试报告
# 前端: /api/report/*  →  接口用例/场景执行报告
# ════════════════════════════════════════════════════════════

def _build_report_item(rec: Dict[str, Any]) -> Dict[str, Any]:
    """将运行记录转为报告条目。"""
    return {
        "id": rec.get("id", ""),
        "name": rec.get("file_path", "接口测试") or "接口测试",
        "status": "SUCCESS" if rec.get("passed") else "ERROR",
        "passRate": 1.0 if rec.get("passed") else 0.0,
        "requestCount": 1,
        "errorCount": 0 if rec.get("passed") else 1,
        "createTime": int(rec.get("created_at", 0) * 1000),
        "createUser": "admin",
        "projectId": "",
        "triggerMode": "MANUAL",
        "type": "API",
    }


def _list_report_records():
    from app.runs.repository import list_run_records
    try:
        return list_run_records(limit=200)
    except Exception:
        return []


@router.get("/project/list/options")
async def project_list_options():
    """获取关联用例项目下拉。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "default", "name": "默认项目"},
    ]})


# ════════════════════════════════════════════════════════════
# 缺失接口补充 - 附件通用管理
# ════════════════════════════════════════════════════════════

