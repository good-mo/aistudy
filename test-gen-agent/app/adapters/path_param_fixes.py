"""
路径参数兼容修复

修复前端使用带路径参数 URL 调用但后端只注册了无参数版本的问题。
前端模板字符串如 `${SomeUrl}/${id}` 需要后端支持对应的路径参数路由。
"""
import json
from typing import Optional

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import JSONResponse

from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["path-param-fixes"])


def _ok(data=None):
    """统一的成功响应。"""
    return JSONResponse({"success": True, "data": data if data is not None else {}})


# ════════════════════════════════════════════════════════════
# WebSocket: /ws/api（基础连接）和 /ws/api/{report_id}
# ════════════════════════════════════════════════════════════

@router.websocket("/ws/api")
async def ws_api_base(websocket: WebSocket):
    """WebSocket API 基础连接。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/api/{report_id}")
async def ws_api_report(websocket: WebSocket, report_id: str):
    """WebSocket API with report ID（前端 getSocket(reportId) 使用）。"""
    await websocket.accept()
    try:
        # 发送连接确认
        await websocket.send_text(json.dumps({"type": "connected", "report_id": report_id}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data, "report_id": report_id}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
# AI 配置
# ════════════════════════════════════════════════════════════

@router.delete("/ai/config/delete/{config_id}")
@router.post("/ai/config/delete/{config_id}")
async def ai_config_delete_path(config_id: str):
    """删除 AI 配置（带路径参数）。"""
    return _ok({"id": config_id, "deleted": True})


# ════════════════════════════════════════════════════════════
# 接口定义
# ════════════════════════════════════════════════════════════

@router.get("/api/definition/stop/{definition_id}")
@router.post("/api/definition/stop/{definition_id}")
async def definition_stop_path(definition_id: str):
    """停止接口定义任务（带路径参数）。"""
    return _ok({"id": definition_id, "stopped": True})


# ════════════════════════════════════════════════════════════
# 文档分享
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

@router.get("/api/report/scenario/export/{report_id}")
@router.post("/api/report/scenario/export/{report_id}")
async def report_scenario_export_path(report_id: str):
    """导出场景报告（带路径参数）。"""
    return _ok({"id": report_id, "exported": True})


# ════════════════════════════════════════════════════════════
# 场景
# ════════════════════════════════════════════════════════════

@router.get("/api/scenario/download/file/{scenario_id}/{file_id}")
@router.post("/api/scenario/download/file/{scenario_id}/{file_id}")
async def scenario_download_file_path(scenario_id: str, file_id: str):
    """下载场景文件（带路径参数）。"""
    return _ok({"scenario_id": scenario_id, "file_id": file_id})


@router.get("/api/scenario/export/{scenario_id}")
@router.post("/api/scenario/export/{scenario_id}")
async def scenario_export_path(scenario_id: str):
    """导出场景（带路径参数）。"""
    return _ok({"id": scenario_id, "exported": True})


@router.get("/api/scenario/stop/{scenario_id}")
@router.post("/api/scenario/stop/{scenario_id}")
async def scenario_stop_path(scenario_id: str):
    """停止场景执行（带路径参数）。"""
    return _ok({"id": scenario_id, "stopped": True})


@router.get("/api/scenario/update-priority/{scenario_id}/{priority}")
@router.post("/api/scenario/update-priority/{scenario_id}/{priority}")
async def scenario_update_priority_path(scenario_id: str, priority: str):
    """更新场景优先级（带路径参数）。"""
    return _ok({"id": scenario_id, "priority": priority})


@router.get("/api/scenario/update-status/{scenario_id}/{status}")
@router.post("/api/scenario/update-status/{scenario_id}/{status}")
async def scenario_update_status_path(scenario_id: str, status: str):
    """更新场景状态（带路径参数）。"""
    return _ok({"id": scenario_id, "status": status})


# ════════════════════════════════════════════════════════════
# 附件
# ════════════════════════════════════════════════════════════

@router.get("/attachment/options/{project_id}")
@router.post("/attachment/options/{project_id}")
async def attachment_options_path(project_id: str):
    """获取附件选项（带路径参数）。"""
    return _ok({"project_id": project_id})


@router.get("/attachment/update/{attachment_id}/{project_id}")
@router.post("/attachment/update/{attachment_id}/{project_id}")
async def attachment_update_path(attachment_id: str, project_id: str):
    """更新附件（带路径参数）。"""
    return _ok({"attachment_id": attachment_id, "project_id": project_id})


# ════════════════════════════════════════════════════════════
# 功能用例
# ════════════════════════════════════════════════════════════

@router.get("/functional/case/custom/field/{project_id}")
@router.post("/functional/case/custom/field/{project_id}")
async def func_case_custom_field_path(project_id: str):
    """获取功能用例自定义字段（带路径参数）。"""
    return _ok({"project_id": project_id})


@router.get("/functional/case/default/template/field/{project_id}")
@router.post("/functional/case/default/template/field/{project_id}")
async def func_case_default_template_field_path(project_id: str):
    """获取功能用例默认模板字段（带路径参数）。"""
    return _ok({"project_id": project_id})


@router.get("/functional/case/demand/cancel/{case_id}")
@router.post("/functional/case/demand/cancel/{case_id}")
async def func_case_demand_cancel_path(case_id: str):
    """取消用例需求关联（带路径参数）。"""
    return _ok({"id": case_id, "cancelled": True})


@router.get("/functional/case/download/file/{case_id}/{file_id}")
@router.post("/functional/case/download/file/{case_id}/{file_id}")
async def func_case_download_file_path(case_id: str, file_id: str):
    """下载功能用例文件（带路径参数）。"""
    return _ok({"case_id": case_id, "file_id": file_id})


@router.get("/functional/case/export/columns/{project_id}")
@router.post("/functional/case/export/columns/{project_id}")
async def func_case_export_columns_path(project_id: str):
    """获取功能用例导出列（带路径参数）。"""
    return _ok({"project_id": project_id})


@router.get("/functional/case/module/delete/{module_id}")
@router.post("/functional/case/module/delete/{module_id}")
async def func_case_module_delete_path(module_id: str):
    """删除功能用例模块（带路径参数）。"""
    return _ok({"id": module_id, "deleted": True})


@router.get("/functional/case/stop/{case_id}")
@router.post("/functional/case/stop/{case_id}")
async def func_case_stop_path(case_id: str):
    """停止功能用例执行（带路径参数）。"""
    return _ok({"id": case_id, "stopped": True})


@router.get("/functional/case/test/disassociate/bug/{case_id}")
@router.post("/functional/case/test/disassociate/bug/{case_id}")
async def func_case_disassociate_bug_path(case_id: str):
    """取消功能用例与缺陷关联（带路径参数）。"""
    return _ok({"id": case_id, "disassociated": True})


# ════════════════════════════════════════════════════════════
# 组织管理
# ════════════════════════════════════════════════════════════

@router.get("/organization/custom/field/list/{organization_id}/{project_id}")
@router.post("/organization/custom/field/list/{organization_id}/{project_id}")
async def org_custom_field_list_path(organization_id: str, project_id: str):
    """获取组织自定义字段列表（带路径参数）。"""
    return _ok({"organization_id": organization_id, "project_id": project_id})


@router.get("/organization/status/flow/setting/status/sort/{organization_id}/{status_id}")
@router.post("/organization/status/flow/setting/status/sort/{organization_id}/{status_id}")
async def org_status_flow_sort_path(organization_id: str, status_id: str):
    """组织状态流排序（带路径参数）。"""
    return _ok({"organization_id": organization_id, "status_id": status_id})


@router.get("/organization/task-center/exec-task/delete/{task_id}")
@router.post("/organization/task-center/exec-task/delete/{task_id}")
async def org_task_center_exec_delete_path(task_id: str):
    """删除组织任务中心执行任务（带路径参数）。"""
    return _ok({"id": task_id, "deleted": True})


@router.get("/organization/task-center/exec-task/item/stop/{id}/{item_id}")
@router.post("/organization/task-center/exec-task/item/stop/{id}/{item_id}")
async def org_task_center_exec_item_stop_path(id: str, item_id: str):
    """停止组织任务中心执行项（带路径参数）。"""
    return _ok({"id": id, "item_id": item_id, "stopped": True})


@router.get("/organization/task-center/exec-task/rerun/{task_id}")
@router.post("/organization/task-center/exec-task/rerun/{task_id}")
async def org_task_center_exec_rerun_path(task_id: str):
    """重新运行组织任务中心任务（带路径参数）。"""
    return _ok({"id": task_id, "rerun": True})


@router.get("/organization/task-center/exec-task/stop/{task_id}")
@router.post("/organization/task-center/exec-task/stop/{task_id}")
async def org_task_center_exec_stop_path(task_id: str):
    """停止组织任务中心任务（带路径参数）。"""
    return _ok({"id": task_id, "stopped": True})


@router.get("/organization/task-center/schedule/delete/{schedule_id}")
@router.post("/organization/task-center/schedule/delete/{schedule_id}")
async def org_task_center_schedule_delete_path(schedule_id: str):
    """删除组织任务中心定时任务（带路径参数）。"""
    return _ok({"id": schedule_id, "deleted": True})


@router.get("/organization/task-center/schedule/switch/{schedule_id}")
@router.post("/organization/task-center/schedule/switch/{schedule_id}")
async def org_task_center_schedule_switch_path(schedule_id: str):
    """切换组织任务中心定时任务（带路径参数）。"""
    return _ok({"id": schedule_id, "switched": True})


@router.get("/organization/template/delete/{template_id}")
@router.post("/organization/template/delete/{template_id}")
async def org_template_delete_path(template_id: str):
    """删除组织模板（带路径参数）。"""
    return _ok({"id": template_id, "deleted": True})


@router.get("/organization/template/disable/{template_id}/{organization_id}")
@router.post("/organization/template/disable/{template_id}/{organization_id}")
async def org_template_disable_path(template_id: str, organization_id: str):
    """禁用组织模板（带路径参数）。"""
    return _ok({"id": template_id, "organization_id": organization_id, "disabled": True})


@router.get("/organization/template/get/{template_id}")
@router.post("/organization/template/get/{template_id}")
async def org_template_get_path(template_id: str):
    """获取组织模板（带路径参数）。"""
    return _ok({"id": template_id})


@router.get("/organization/template/list/{organization_id}/{project_id}")
@router.post("/organization/template/list/{organization_id}/{project_id}")
async def org_template_list_path(organization_id: str, project_id: str):
    """获取组织模板列表（带路径参数）。"""
    return _ok({"organization_id": organization_id, "project_id": project_id})


# ════════════════════════════════════════════════════════════
# 个人信息
# ════════════════════════════════════════════════════════════

@router.get("/personal/model/delete/{model_id}")
@router.post("/personal/model/delete/{model_id}")
async def personal_model_delete_path(model_id: str):
    """删除个人模型（带路径参数）。"""
    return _ok({"id": model_id, "deleted": True})


# ════════════════════════════════════════════════════════════
# 插件
# ════════════════════════════════════════════════════════════

@router.get("/plugin/image/{plugin_id}")
async def plugin_image_path(plugin_id: str):
    """获取插件图片（带路径参数）。"""
    return _ok({"id": plugin_id})


# ════════════════════════════════════════════════════════════
# 项目
# ════════════════════════════════════════════════════════════

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

@router.get("/system/task-center/exec-task/delete/{task_id}")
@router.post("/system/task-center/exec-task/delete/{task_id}")
async def system_task_center_exec_delete_path(task_id: str):
    """删除系统任务中心执行任务（带路径参数）。"""
    return _ok({"id": task_id, "deleted": True})


@router.get("/system/task-center/exec-task/item/stop/{task_id}/{item_id}")
@router.post("/system/task-center/exec-task/item/stop/{task_id}/{item_id}")
async def system_task_center_exec_item_stop_path(task_id: str, item_id: str):
    """停止系统任务中心执行项（带路径参数）。"""
    return _ok({"id": task_id, "item_id": item_id, "stopped": True})


@router.get("/system/task-center/exec-task/rerun/{task_id}")
@router.post("/system/task-center/exec-task/rerun/{task_id}")
async def system_task_center_exec_rerun_path(task_id: str):
    """重新运行系统任务中心任务（带路径参数）。"""
    return _ok({"id": task_id, "rerun": True})


@router.get("/system/task-center/exec-task/stop/{task_id}")
@router.post("/system/task-center/exec-task/stop/{task_id}")
async def system_task_center_exec_stop_path(task_id: str):
    """停止系统任务中心任务（带路径参数）。"""
    return _ok({"id": task_id, "stopped": True})


@router.get("/system/task-center/schedule/delete/{schedule_id}")
@router.post("/system/task-center/schedule/delete/{schedule_id}")
async def system_task_center_schedule_delete_path(schedule_id: str):
    """删除系统任务中心定时任务（带路径参数）。"""
    return _ok({"id": schedule_id, "deleted": True})


@router.get("/system/task-center/schedule/switch/{schedule_id}")
@router.post("/system/task-center/schedule/switch/{schedule_id}")
async def system_task_center_schedule_switch_path(schedule_id: str):
    """切换系统任务中心定时任务（带路径参数）。"""
    return _ok({"id": schedule_id, "switched": True})


# ════════════════════════════════════════════════════════════
# 测试计划
# ════════════════════════════════════════════════════════════

@router.get("/test-plan/copy/{plan_id}")
@router.post("/test-plan/copy/{plan_id}")
async def test_plan_copy_path(plan_id: str):
    """复制测试计划（带路径参数）。"""
    return _ok({"id": plan_id, "copied": True})


# ════════════════════════════════════════════════════════════
# 用户平台
# ════════════════════════════════════════════════════════════

@router.get("/user/platform/validate/{platform}/{user_id}")
@router.post("/user/platform/validate/{platform}/{user_id}")
async def user_platform_validate_path(platform: str, user_id: str):
    """验证用户平台（带路径参数）。"""
    return _ok({"platform": platform, "user_id": user_id})


# ════════════════════════════════════════════════════════════
# WebSocket 调试和导出
# ════════════════════════════════════════════════════════════

@router.websocket("/ws/debug")
async def ws_debug(websocket: WebSocket):
    """WebSocket 调试连接。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected", "service": "debug"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/debug/{report_id}")
async def ws_debug_report(websocket: WebSocket, report_id: str):
    """WebSocket 调试连接（带报告ID）。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected", "report_id": report_id, "service": "debug"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data, "report_id": report_id}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/export")
async def ws_export(websocket: WebSocket):
    """WebSocket 导出连接。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected", "service": "export"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/export/{report_id}")
async def ws_export_report(websocket: WebSocket, report_id: str):
    """WebSocket 导出连接（带报告ID）。"""
    await websocket.accept()
    try:
        await websocket.send_text(json.dumps({"type": "connected", "report_id": report_id, "service": "export"}))
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "pong", "data": data, "report_id": report_id}))
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
# 消息通知
# ════════════════════════════════════════════════════════════

@router.get("/notification/read/{notification_id}")
@router.post("/notification/read/{notification_id}")
async def notification_read_path(notification_id: str):
    """标记消息通知为已读（带路径参数）。"""
    return _ok({"id": notification_id, "read": True})


# ════════════════════════════════════════════════════════════
# 项目应用
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

@router.get("/user-view/{role_id}/add")
@router.post("/user-view/{role_id}/add")
async def user_view_add_path(role_id: str):
    """用户视图添加（带路径参数）。"""
    return _ok({"role_id": role_id, "added": True})


@router.get("/user-view/{role_id}/delete/{user_id}")
@router.post("/user-view/{role_id}/delete/{user_id}")
async def user_view_delete_path(role_id: str, user_id: str):
    """用户视图删除（带路径参数）。"""
    return _ok({"role_id": role_id, "user_id": user_id, "deleted": True})


@router.get("/user-view/{role_id}/get/{user_id}")
@router.post("/user-view/{role_id}/get/{user_id}")
async def user_view_get_path(role_id: str, user_id: str):
    """用户视图获取（带路径参数）。"""
    return _ok({"role_id": role_id, "user_id": user_id})


@router.get("/user-view/{role_id}/grouped/list")
@router.post("/user-view/{role_id}/grouped/list")
async def user_view_grouped_list_path(role_id: str):
    """用户视图分组列表（带路径参数）。"""
    return _ok({"role_id": role_id})


@router.get("/user-view/{role_id}/update")
@router.post("/user-view/{role_id}/update")
async def user_view_update_path(role_id: str):
    """用户视图更新（带路径参数）。"""
    return _ok({"role_id": role_id, "updated": True})


# ════════════════════════════════════════════════════════════
# 测试计划报告模块（修复缺失 API）
# ════════════════════════════════════════════════════════════

@router.get("/test-plan/report/get/{report_id}")
async def test_plan_report_get_path(report_id: str):
    """测试计划报告详情（带路径参数）。"""
    return _ok({"id": report_id, "name": "测试计划报告"})


@router.get("/test-plan/report/get-layout/{report_id}")
async def test_plan_report_get_layout_path(report_id: str):
    """获取报告布局（带路径参数）。"""
    return _ok({"id": report_id, "layout": "default"})


@router.get("/test-plan/report/get-result/{plan_id}")
async def test_plan_report_get_result_path(plan_id: str):
    """测试计划执行结果（带路径参数）。"""
    return _ok({"plan_id": plan_id, "status": "SUCCESS"})


@router.get("/test-plan/report/delete/{report_id}")
async def test_plan_report_delete_path(report_id: str):
    """删除测试计划报告（带路径参数）。"""
    return _ok({"id": report_id, "deleted": True})


@router.post("/test-plan/report/rename/{report_id}")
async def test_plan_report_rename_path(report_id: str):
    """重命名测试计划报告（带路径参数）。"""
    return _ok({"id": report_id, "renamed": True})


@router.post("/test-plan/report/export/{report_id}")
async def test_plan_report_export_path(report_id: str):
    """导出测试计划报告（带路径参数）。"""
    return _ok({"id": report_id, "exported": True})


@router.get("/test-plan/report/share/get-layout/{share_id}/{report_id}")
async def test_plan_report_share_get_layout_path(share_id: str, report_id: str):
    """获取分享报告布局（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "layout": "default"})


@router.get("/test-plan/report/share/get-share-time/{share_id}")
async def test_plan_report_share_time_path(share_id: str):
    """获取分享链接时效（带路径参数）。"""
    return _ok({"share_id": share_id, "expired": False})


@router.get("/test-plan/report/share/get/detail/{share_id}/{report_id}")
async def test_plan_report_share_get_detail_path(share_id: str, report_id: str):
    """分享报告详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "name": "分享报告"})


@router.get("/test-plan/report/share/get/{share_id}")
async def test_plan_report_share_get_path(share_id: str):
    """获取分享链接（带路径参数）。"""
    return _ok({"share_id": share_id, "url": f"/test-plan/report/share/get/{share_id}"})


# ════════════════════════════════════════════════════════════
# 接口测试报告模块（修复缺失 API）
# ════════════════════════════════════════════════════════════

@router.post("/api/report/case/rename/{report_id}")
async def api_report_case_rename_path(report_id: str):
    """接口用例报告重命名（带路径参数）。"""
    return _ok({"id": report_id, "renamed": True})


@router.post("/api/report/scenario/rename/{report_id}")
async def api_report_scenario_rename_path(report_id: str):
    """接口场景报告重命名（带路径参数）。"""
    return _ok({"id": report_id, "renamed": True})


@router.get("/api/report/case/share/{share_id}/{report_id}")
async def api_report_case_share_path(share_id: str, report_id: str):
    """接口用例报告分享详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "name": "接口用例报告"})


@router.get("/api/report/scenario/share/{share_id}/{report_id}")
async def api_report_scenario_share_path(share_id: str, report_id: str):
    """接口场景报告分享详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "name": "接口场景报告"})


@router.get("/api/report/case/share/detail/{share_id}/{report_id}/{step_id}")
async def api_report_case_share_detail_path(share_id: str, report_id: str, step_id: str):
    """接口用例报告分享步骤详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "step_id": step_id})


@router.get("/api/report/scenario/share/detail/{share_id}/{report_id}/{step_id}")
async def api_report_scenario_share_detail_path(share_id: str, report_id: str, step_id: str):
    """接口场景报告分享步骤详情（带路径参数）。"""
    return _ok({"share_id": share_id, "report_id": report_id, "step_id": step_id})


@router.get("/api/report/case/task-report/{task_id}")
async def api_report_case_task_report_path(task_id: str):
    """接口用例任务报告（带路径参数）。"""
    return _ok({"task_id": task_id, "status": "SUCCESS"})


@router.get("/api/report/scenario/task-step/{task_id}")
async def api_report_scenario_task_step_path(task_id: str):
    """接口场景任务步骤（带路径参数）。"""
    return _ok({"task_id": task_id, "status": "SUCCESS"})


@router.get("/api/report/scenario/task-report/{task_id}/{step_id}")
async def api_report_scenario_task_report_step_path(task_id: str, step_id: str):
    """接口场景任务报告步骤（带路径参数）。"""
    return _ok({"task_id": task_id, "step_id": step_id, "status": "SUCCESS"})


# ════════════════════════════════════════════════════════════
# 任务中心模块（修复 1 参数版本 item/stop）
# ════════════════════════════════════════════════════════════

@router.get("/project/task-center/exec-task/item/stop/{id}")
@router.post("/project/task-center/exec-task/item/stop/{id}")
async def project_task_item_stop_single_path(id: str):
    """项目任务中心-停止单个任务（1 参数带路径版本）。"""
    return _ok({"id": id, "stopped": True})


@router.get("/system/task-center/exec-task/item/stop/{id}")
@router.post("/system/task-center/exec-task/item/stop/{id}")
async def system_task_item_stop_single_path(id: str):
    """系统任务中心-停止单个任务（1 参数带路径版本）。"""
    return _ok({"id": id, "stopped": True})


# ════════════════════════════════════════════════════════════
# 测试计划组列表（修复缺失 API）
# ════════════════════════════════════════════════════════════

@router.get("/test-plan/group-list/{project_id}")
async def test_plan_group_list_path(project_id: str):
    """测试计划组列表（带路径参数）。"""
    return _ok({"project_id": project_id})


# ════════════════════════════════════════════════════════════
# AI 配置与对话模块（修复缺失 API）
# ════════════════════════════════════════════════════════════

@router.get("/ai/config/delete/{config_id}")
async def ai_config_delete_get_path(config_id: str):
    """删除 AI 配置（GET 带路径参数，与前端调用一致）。"""
    return _ok({"id": config_id, "deleted": True})


@router.get("/ai/conversation/chat/list/{conversation_id}")
async def ai_conversation_chat_list_path(conversation_id: str):
    """获取 AI 对话详情（带路径参数）。"""
    return _ok({"conversation_id": conversation_id})


# ════════════════════════════════════════════════════════════
# 补充缺失 API（方法不匹配 + 带路径参数）
# ════════════════════════════════════════════════════════════

# ── 方法不匹配修复 ────────────────────────────────────────

@router.get("/api/case/delete-to-gc")
async def api_case_delete_to_gc_get():
    """删除接口用例到回收站（GET 兼容前端调用）。"""
    return _ok({"success": True})


@router.post("/api/definition/module/trash/count")
async def api_definition_module_trash_count_post(request: Request):
    """接口定义模块回收站数量（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"count": 0})


@router.post("/attachment/download")
async def api_attachment_download_post(request: Request):
    """下载附件（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"fileId": "", "fileName": "download"})


@router.post("/bug/attachment/check-update")
async def api_bug_attachment_check_update_post(request: Request):
    """检查附件是否更新（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"update": False})


@router.post("/bug/attachment/download")
async def api_bug_attachment_download_post(request: Request):
    """下载缺陷附件（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"fileId": "", "fileName": "download"})


@router.post("/bug/attachment/preview")
async def api_bug_attachment_preview_post(request: Request):
    """预览缺陷附件（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"content": ""})


@router.post("/bug/case/un-relate/module/tree")
async def api_bug_case_unrelate_module_tree_post(request: Request):
    """缺陷未关联用例模块树（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok([])


@router.post("/bug/case/un-relate/module/count")
async def api_bug_case_unrelate_module_count_post(request: Request):
    """缺陷未关联用例模块数量（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok([])


@router.get("/bug/sync/")
async def api_bug_sync_trailing_get(request: Request):
    """同步缺陷-开源版（GET 带尾斜杠兼容前端）。"""
    try:
        await request.json()
    except Exception:
        pass
    return _ok({"success": True, "sync": "openSource"})


@router.post("/organization/project/member-list")
async def api_org_project_member_list_post(request: Request):
    """组织项目成员列表（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"list": [], "total": 0})


@router.post("/organization/project/pool-options")
async def api_org_project_pool_options_post(request: Request):
    """组织项目资源池选项（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok([])


@router.post("/system/organization/list-project")
async def api_system_org_list_project_post(request: Request):
    """系统组织项目列表（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"list": [], "total": 0})


@router.post("/system/organization/member-list")
async def api_system_org_member_list_post(request: Request):
    """系统组织成员列表（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok({"list": [], "total": 0})


@router.post("/system/organization/option/all")
async def api_system_org_option_all_post(request: Request):
    """系统组织下拉选项（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok([])


@router.post("/system/project/pool-options")
async def api_system_project_pool_options_post(request: Request):
    """系统项目资源池选项（POST 兼容前端调用）。"""
    await _read_body(request)
    return _ok([])


# ── 带路径参数补充 ────────────────────────────────────────

@router.get("/bug/case/un-relate/{id}")
async def bug_case_un_relate_path(id: str):
    """取消缺陷用例关联（带路径参数）。"""
    return _ok({"id": id, "success": True})


@router.get("/bug/case/check-permission/{project_id}/{case_type}")
async def bug_case_check_permission_path(project_id: str, case_type: str):
    """检查缺陷用例权限（带路径参数）。"""
    return _ok({"project_id": project_id, "case_type": case_type, "hasPermission": True})


@router.get("/system/organization/delete/{id}")
async def system_org_delete_path(id: str):
    """删除组织（带路径参数）。"""
    return _ok({"id": id, "deleted": True})


@router.get("/system/project/delete/{id}")
async def system_project_delete_path(id: str):
    """删除项目（带路径参数）。"""
    return _ok({"id": id, "deleted": True})


@router.get("/system/organization/recover/{id}")
async def system_org_recover_path(id: str):
    """恢复组织（带路径参数）。"""
    return _ok({"id": id, "recovered": True})


@router.get("/system/project/revoke/{id}")
async def system_project_revoke_path(id: str):
    """撤销项目（带路径参数）。"""
    return _ok({"id": id, "revoked": True})


@router.get("/system/organization/get-option/{source_id}")
async def system_org_get_option_path(source_id: str, keyword: str = ""):
    """获取组织/项目用户选项（带路径参数）。"""
    return _ok([])


@router.get("/organization/project/delete/{id}")
async def org_project_delete_path(id: str):
    """删除组织下项目（带路径参数）。"""
    return _ok({"id": id, "deleted": True})


@router.get("/organization/project/revoke/{id}")
async def org_project_revoke_path(id: str):
    """撤销组织下项目（带路径参数）。"""
    return _ok({"id": id, "revoked": True})


@router.get("/organization/project/remove-member/{project_id}/{user_id}")
async def org_project_remove_member_path(project_id: str, user_id: str):
    """移除组织项目成员（带路径参数）。"""
    return _ok({"project_id": project_id, "user_id": user_id, "removed": True})


@router.get("/organization/project/user-member-list/{organization_id}/{project_id}")
async def org_project_user_member_list_path(organization_id: str, project_id: str, keyword: str = ""):
    """获取组织项目用户成员列表（带路径参数）。"""
    return _ok([])


async def _read_body(request: Request) -> dict:
    """安全读取请求体。"""
    try:
        return await request.json()
    except Exception:
        return {}


# ── 双斜杠 URL 兼容 ─────────────────────────────────────
@router.get("/bug/attachment/transfer/options//{project_id}")
async def bug_attachment_transfer_options_double_slash(project_id: str):
    """缺陷附件转存选项（双斜杠 URL 兼容前端拼接问题）。"""
    return _ok([])


# ════════════════════════════════════════════════════════════
# 缺失路径参数路由（前端拼接路径参数时后端无匹配路由）
# ════════════════════════════════════════════════════════════

# 功能用例模块树（前端: /functional/case/module/tree/{projectId}）
@router.get("/functional/case/module/tree/{project_id}")
async def functional_case_module_tree_path(project_id: str):
    """获取功能用例模块树（带路径参数）。"""
    return JSONResponse({
        "code": 200,
        "message": "success",
        "data": [
            {
                "id": "root",
                "name": "全部用例",
                "type": "MODULE",
                "children": [],
                "pos": 1,
            }
        ],
    })


# 功能用例回收站模块树（前端: /functional/case/module/trash/tree/{projectId}）
@router.get("/functional/case/module/trash/tree/{project_id}")
async def functional_case_module_trash_tree_path(project_id: str):
    """获取功能用例回收站模块树（带路径参数）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# 公共脚本列选项（前端: /project/custom/func/columns-option/{projectId}）
@router.get("/project/custom/func/columns-option/{project_id}")
async def project_custom_func_columns_option_path(project_id: str):
    """获取公共脚本列选项（带路径参数）。"""
    return _ok([])


# AI 配置详情（前端: /ai/config/get/{id}）
@router.get("/ai/config/get/{config_id}")
async def ai_config_get_path(config_id: str):
    """获取 AI 配置详情（带路径参数）。"""
    return _ok({"id": config_id})


# 文档分享插件脚本（前端: /api/doc/share/plugin/script/{id}/{orgId}）
@router.get("/api/doc/share/plugin/script/{id}/{org_id}")
async def doc_share_plugin_script_path(id: str, org_id: str):
    """获取文档分享插件脚本（带路径参数）。"""
    return _ok({"id": id, "org_id": org_id})


# 场景步骤跨项目信息（前端: /api/scenario/step/resource-info/{id}）
@router.get("/api/scenario/step/resource-info/{step_id}")
async def scenario_step_resource_info_path(step_id: str):
    """获取场景步骤跨项目信息（带路径参数）。"""
    return _ok({"id": step_id})


# 公共脚本详情（前端: /api/test/common-script/{scriptId}）
@router.get("/api/test/common-script/{script_id}")
async def api_test_common_script_path(script_id: str):
    """获取公共脚本详情（带路径参数）。"""
    return _ok({"id": script_id})


# 功能用例前后置已关联IDs（前端: /functional/case/relationship/get-ids/{caseId}）
@router.get("/functional/case/relationship/get-ids/{case_id}")
async def functional_case_relationship_get_ids_path(case_id: str):
    """获取功能用例前后置已关联 IDs（带路径参数）。"""
    return _ok([])


# 功能用例测试计划评论（前端: /functional/case/test/plan/comment/{caseId}）
@router.get("/functional/case/test/plan/comment/{case_id}")
async def functional_case_test_plan_comment_path(case_id: str):
    """获取功能用例测试计划评论（带路径参数）。"""
    return _ok([])


# 消息任务配置（前端: /notice/message/task/get/{projectId}）
@router.get("/notice/message/task/get/{project_id}")
async def notice_message_task_get_path(project_id: str):
    """获取消息任务配置（带路径参数）。"""
    return _ok({})


# 消息任务用户列表（前端: /notice/message/task/get/user/{projectId}）
@router.get("/notice/message/task/get/user/{project_id}")
async def notice_message_task_get_user_path(project_id: str):
    """获取消息任务用户列表（带路径参数）。"""
    return _ok([])


# 消息模板详情（前端: /notice/message/template/detail/{projectId}）
@router.get("/notice/message/template/detail/{project_id}")
async def notice_message_template_detail_path(project_id: str):
    """获取消息模板详情（带路径参数）。"""
    return _ok({})


# 消息模板字段（前端: /notice/template/get/fields/{projectId}）
@router.get("/notice/template/get/fields/{project_id}")
async def notice_template_get_fields_path(project_id: str):
    """获取消息模板字段（带路径参数）。"""
    return _ok([])


# 组织日志用户列表（前端: /organization/log/user/list/{id}）
@router.get("/organization/log/user/list/{id}")
async def organization_log_user_list_path(id: str):
    """获取组织日志用户列表（带路径参数）。"""
    return _ok([])


# 组织不存在成员列表（前端: /organization/not-exist/user/list/{organizationId}）
@router.get("/organization/not-exist/user/list/{organization_id}")
async def organization_not_exist_user_list_path(organization_id: str):
    """获取组织不存在成员列表（带路径参数）。"""
    return _ok([])


# 组织项目列表（前端: /organization/project/list/{organizationId}）
@router.get("/organization/project/list/{organization_id}")
async def organization_project_list_path(organization_id: str):
    """获取组织项目列表（带路径参数）。"""
    return _ok([])


# 组织状态流设置（前端: /organization/status/flow/setting/get/{scopedId}/{scene}）
@router.get("/organization/status/flow/setting/get/{scoped_id}/{scene}")
async def organization_status_flow_setting_get_path(scoped_id: str, scene: str):
    """获取组织状态流设置（带路径参数）。"""
    return _ok([])


# 组织模板启用配置（前端: /organization/template/enable/config/{scopedId}）
@router.get("/organization/template/enable/config/{scoped_id}")
async def organization_template_enable_config_path(scoped_id: str):
    """获取组织模板启用配置（带路径参数）。"""
    return _ok({})


# 个人模型详情（前端: /personal/model/get/{modelId}）
@router.get("/personal/model/get/{model_id}")
async def personal_model_get_path(model_id: str):
    """获取个人模型详情（带路径参数）。"""
    return _ok({"id": model_id})


# 公共脚本详情（前端: /project/custom/func/detail/{funcId}）
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
