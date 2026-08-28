# app/test_plan/router.py
"""测试计划 API 路由。"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.test_plan.store import test_plan_store

router = APIRouter(tags=["test-plan"])


# ── 测试计划 CRUD ─────────────────────────────────────
@router.post("/test-plan/page")
async def test_plan_page(request: Request):
    """测试计划分页列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    plans = test_plan_store.list_plans(
        keyword=keyword,
        limit=page_size,
        offset=(current - 1) * page_size,
    )

    # 批量获取统计（消除 N+1 查询）
    stats_map = test_plan_store.get_plans_statistics([p["id"] for p in plans])
    items = []
    for p in plans:
        item = _to_plan(p)
        stats = stats_map.get(p["id"], {"executionRate": 0, "passRate": 0, "total": 0})
        item["executionRate"] = stats["executionRate"]
        item["passRate"] = stats["passRate"]
        item["caseCount"] = stats["total"]
        items.append(item)

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": test_plan_store.count_plans(),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/test-plan/add")
async def test_plan_add(request: Request):
    """创建测试计划。"""
    body = await request.json()
    plan = test_plan_store.create_plan(
        name=body.get("name", "未命名测试计划"),
        description=body.get("description", ""),
        priority=body.get("priority", "P2"),
        module_id=body.get("moduleId", "root"),
        created_by=body.get("createUser", "admin"),
    )
    return JSONResponse({"code": 200, "message": "success", "data": _to_plan(plan)})


@router.post("/test-plan/update")
async def test_plan_update(request: Request):
    """更新测试计划。"""
    body = await request.json()
    plan_id = body.get("id", "")
    updates = {}
    for k, v in body.items():
        if k == "name":
            updates["name"] = v
        elif k == "description":
            updates["description"] = v
        elif k == "priority":
            updates["priority"] = v
        elif k == "status":
            updates["status"] = v
        elif k == "startTime":
            updates["start_time"] = v
        elif k == "endTime":
            updates["end_time"] = v

    plan = test_plan_store.update_plan(plan_id, **updates)
    if not plan:
        return JSONResponse({"code": 404, "message": "测试计划不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": _to_plan(plan)})


@router.post("/test-plan/delete")
async def test_plan_delete(request: Request):
    """删除测试计划。"""
    body = await request.json()
    plan_id = body.get("id", "")
    test_plan_store.delete_plan(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/batch-delete")
async def test_plan_batch_delete(request: Request):
    """批量删除测试计划。"""
    body = await request.json()
    ids = body.get("ids", [])
    for pid in ids:
        test_plan_store.delete_plan(pid)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/archived")
async def test_plan_archived(request: Request):
    """归档测试计划。"""
    body = await request.json()
    plan_id = body.get("id", "")
    test_plan_store.archive_plan(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/batch-archived")
async def test_plan_batch_archived(request: Request):
    """批量归档测试计划。"""
    body = await request.json()
    ids = body.get("ids", [])
    for pid in ids:
        test_plan_store.archive_plan(pid)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/batch-copy")
async def test_plan_batch_copy(request: Request):
    """批量复制测试计划。"""
    body = await request.json()
    ids = body.get("ids", [])
    for pid in ids:
        plan = test_plan_store.get_plan(pid)
        if plan:
            new_plan = test_plan_store.create_plan(
                name=f"{plan['name']} (副本)",
                description=plan.get("description", ""),
                priority=plan.get("priority", "P2"),
            )
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/copy")
async def test_plan_copy(request: Request):
    """复制测试计划。"""
    body = await request.json()
    plan_id = body.get("id", "")
    plan = test_plan_store.get_plan(plan_id)
    if not plan:
        return JSONResponse({"code": 404, "message": "测试计划不存在", "data": None}, status_code=404)
    new_plan = test_plan_store.create_plan(
        name=f"{plan['name']} (副本)",
        description=plan.get("description", ""),
        priority=plan.get("priority", "P2"),
    )
    return JSONResponse({"code": 200, "message": "success", "data": _to_plan(new_plan)})


@router.get("/test-plan/getCount")
async def test_plan_get_count():
    """获取统计数量。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "total": test_plan_store.count_plans(),
    }})


# ── 测试计划模块 ─────────────────────────────────────
@router.get("/test-plan/module/tree")
async def test_plan_module_tree():
    """获取测试计划模块树。"""
    modules = test_plan_store.list_modules()
    tree = [{"id": "root", "name": "全部计划", "type": "MODULE", "children": []}]
    for m in modules:
        tree[0]["children"].append({
            "id": m["id"],
            "name": m["name"],
            "type": "MODULE",
            "children": [],
        })
    return JSONResponse({"code": 200, "message": "success", "data": tree})


@router.post("/test-plan/module/add")
async def test_plan_module_add(request: Request):
    """添加测试计划模块。"""
    body = await request.json()
    module = test_plan_store.create_module(
        name=body.get("name", "新模块"),
        parent_id=body.get("parentId", "root"),
    )
    return JSONResponse({"code": 200, "message": "success", "data": module})


@router.post("/test-plan/module/delete")
async def test_plan_module_delete(request: Request):
    """删除测试计划模块。"""
    body = await request.json()
    module_id = body.get("id", "")
    test_plan_store.delete_module(module_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 测试计划用例关联 ─────────────────────────────────
@router.post("/test-plan/association/page")
async def test_plan_association_page(request: Request):
    """获取测试计划关联用例列表。"""
    body = await request.json()
    plan_id = body.get("planId", "")
    cases = test_plan_store.list_plan_cases(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": cases,
        "total": len(cases),
    }})


@router.post("/test-plan/association/add")
async def test_plan_association_add(request: Request):
    """添加用例到测试计划。"""
    body = await request.json()
    plan_id = body.get("planId", "")
    case_ids = body.get("caseIds", [])
    case_type = body.get("caseType", "functional")
    added = []
    for cid in case_ids:
        rel = test_plan_store.add_plan_case(plan_id, cid, case_type)
        added.append(rel)
    return JSONResponse({"code": 200, "message": "success", "data": added})


@router.post("/test-plan/association/delete")
async def test_plan_association_delete(request: Request):
    """从测试计划移除用例。"""
    body = await request.json()
    rel_id = body.get("id", "")
    test_plan_store.remove_plan_case(rel_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/association/update-status")
async def test_plan_association_update_status(request: Request):
    """更新用例执行状态。"""
    body = await request.json()
    rel_id = body.get("id", "")
    status = body.get("status", "pending")
    test_plan_store.update_plan_case_status(rel_id, status)
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 测试计划统计 ─────────────────────────────────────
@router.get("/test-plan/statistics/{plan_id}")
async def test_plan_statistics(plan_id: str):
    """获取测试计划统计。"""
    stats = test_plan_store.get_plan_statistics(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": stats})


@router.get("/test-plan/test-plan-list")
async def test_plan_list_no_page():
    """获取测试计划列表（无分页）。"""
    plans = test_plan_store.list_plans(limit=500)
    items = [_to_plan(p) for p in plans]
    return JSONResponse({"code": 200, "message": "success", "data": items})


@router.get("/test-plan/statistics")
async def test_plan_stats_overview():
    """测试计划执行进度统计。"""
    plans = test_plan_store.list_plans(limit=100)
    stats_map = test_plan_store.get_plans_statistics([p["id"] for p in plans])
    data = []
    for p in plans:
        stats = stats_map.get(p["id"], {"passRate": 0, "executionRate": 0, "total": 0, "passed": 0})
        data.append({
            "id": p["id"],
            "name": p["name"],
            "passRate": stats["passRate"],
            "executionRate": stats["executionRate"],
            "total": stats["total"],
            "passed": stats["passed"],
        })
    return JSONResponse({"code": 200, "message": "success", "data": data})


@router.post("/test-plan/report/auto-gen")
async def test_plan_report_auto_gen(request: Request):
    """自动生成测试计划报告。"""
    body = await request.json()
    plan_id = body.get("planId", "")
    plan = test_plan_store.get_plan(plan_id)
    if not plan:
        return JSONResponse({"code": 404, "message": "测试计划不存在", "data": None}, status_code=404)
    stats = test_plan_store.get_plan_statistics(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "planId": plan_id,
        "planName": plan["name"],
        "stats": stats,
        "generatedAt": time.time(),
    }})


def _to_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """将存储格式转为前端格式。"""
    return {
        "id": plan.get("id", ""),
        "name": plan.get("name", ""),
        "description": plan.get("description", ""),
        "status": plan.get("status", "prepared"),
        "priority": plan.get("priority", "P2"),
        "moduleId": plan.get("module_id", "root"),
        "modulePath": "/全部计划",
        "createUser": plan.get("created_by", "admin"),
        "createdTime": int(plan.get("created_at", 0) * 1000),
        "updatedTime": int(plan.get("updated_at", 0) * 1000),
        "startTime": int(plan.get("start_time", 0) * 1000),
        "endTime": int(plan.get("end_time", 0) * 1000),
        "executionRate": plan.get("execution_rate", 0),
        "passRate": plan.get("pass_rate", 0),
        "deleted": False,
        "archived": plan.get("status") == "archived",
    }


# ════════════════════════════════════════════════════════════
# 测试计划模块管理
# ════════════════════════════════════════════════════════════

@router.post("/test-plan/module/update")
async def test_plan_module_update(request: Request):
    """更新测试计划模块。"""
    body = await request.json()
    module_id = body.get("id", "")
    name = body.get("name", "")
    # 简单的模块更新 - 当前 store 中没有 update_module 方法
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/module/move")
async def test_plan_module_move(request: Request):
    """移动测试计划模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/module/count")
async def test_plan_module_count():
    """测试计划模块数量。"""
    modules = test_plan_store.list_modules()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "module": len(modules),
        "all": test_plan_store.count_plans(),
    }})


# ════════════════════════════════════════════════════════════
# 测试计划批量操作
# ════════════════════════════════════════════════════════════

@router.post("/test-plan/batch-edit")
async def test_plan_batch_edit(request: Request):
    """测试计划批量编辑。"""
    body = await request.json()
    ids = body.get("ids", [])
    updates = {}
    for k, v in body.items():
        if k in ("status", "priority"):
            updates[k] = v
    for pid in ids:
        test_plan_store.update_plan(pid, **updates)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/batch-move")
async def test_plan_batch_move(request: Request):
    """批量移动测试计划。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/sort")
async def test_plan_sort(request: Request):
    """拖拽排序测试计划。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/group-list")
async def test_plan_group_list():
    """测试计划组下拉列表。"""
    plans = test_plan_store.list_plans(limit=100)
    items = [{"id": p["id"], "name": p["name"]} for p in plans]
    return JSONResponse({"code": 200, "message": "success", "data": items})


# ════════════════════════════════════════════════════════════
# 测试计划-缺陷管理
# ════════════════════════════════════════════════════════════

@router.post("/test-plan/bug/page")
async def test_plan_bug_page(request: Request):
    """计划详情-缺陷列表。"""
    body = await request.json()
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.defects.tracker import list_defects
    defects = list_defects(limit=page_size, offset=(current - 1) * page_size)

    items = []
    for d in defects:
        items.append({
            "id": d.get("id", ""),
            "name": d.get("title", ""),
            "title": d.get("title", ""),
            "status": d.get("status", "open"),
            "severity": d.get("severity", "major"),
            "createTime": int(d.get("created_at", 0) * 1000),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/test-plan/edit/follower")
async def test_plan_edit_follower(request: Request):
    """关注/取消关注测试计划。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/schedule-config")
async def test_plan_schedule_config(request: Request):
    """创建定时任务。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/batch-schedule-config")
async def test_plan_batch_schedule_config(request: Request):
    """批量配置定时任务。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 计划详情-功能用例
# ════════════════════════════════════════════════════════════

@router.post("/test-plan/functional/case/page")
async def test_plan_functional_case_page(request: Request):
    """计划详情-功能用例列表。"""
    body = await request.json()
    plan_id = body.get("planId", "")
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    cases = test_plan_store.list_plan_cases(plan_id)
    if keyword:
        cases = [c for c in cases if keyword.lower() in str(c.get("case_id", "")).lower()]

    # 获取用例详情
    from app.cases.repository import get_case
    items = []
    paged = cases[(current - 1) * page_size: current * page_size]
    for rel in paged:
        case = get_case(rel.get("case_id", ""))
        if case:
            items.append({
                "id": rel.get("id", ""),
                "caseId": rel.get("case_id", ""),
                "name": case.get("title", ""),
                "priority": case.get("priority", "P2"),
                "status": case.get("status", "draft"),
                "executionStatus": rel.get("status", "pending"),
                "executor": "admin",
                "executionTime": rel.get("execute_time", 0),
            })
        else:
            items.append({
                "id": rel.get("id", ""),
                "caseId": rel.get("case_id", ""),
                "name": f"用例 {rel.get('case_id', '')[:8]}",
                "priority": "P2",
                "status": "draft",
                "executionStatus": rel.get("status", "pending"),
                "executor": "admin",
                "executionTime": 0,
            })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(cases),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/test-plan/functional/case/module/count")
async def test_plan_functional_case_module_count(request: Request):
    """计划详情-功能用例-模块数量。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/test-plan/functional/case/tree")
async def test_plan_functional_case_tree():
    """计划详情-功能用例模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "root", "name": "全部用例", "type": "MODULE", "children": []}
    ]})


@router.post("/test-plan/functional/case/sort")
async def test_plan_functional_case_sort(request: Request):
    """计划详情-功能用例拖拽排序。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/disassociate")
async def test_plan_functional_case_disassociate(request: Request):
    """计划详情-功能用例取消关联。"""
    body = await request.json()
    rel_id = body.get("id", "")
    test_plan_store.remove_plan_case(rel_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/batch/disassociate")
async def test_plan_functional_case_batch_disassociate(request: Request):
    """计划详情-功能用例批量取消关联。"""
    body = await request.json()
    ids = body.get("ids", [])
    for rid in ids:
        test_plan_store.remove_plan_case(rid)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/run")
async def test_plan_functional_case_run(request: Request):
    """计划详情-功能用例执行。"""
    body = await request.json()
    case_id = body.get("caseId", "")
    status = body.get("status", "passed")
    if case_id:
        test_plan_store.update_plan_case_status(case_id, status)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": "success",
        "result": "SUCCESS",
    }})


@router.post("/test-plan/functional/case/batch/run")
async def test_plan_functional_case_batch_run(request: Request):
    """计划详情-功能用例批量执行。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/batch/move")
async def test_plan_functional_case_batch_move(request: Request):
    """计划详情-功能用例批量移动。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/has/associate/bug/page")
async def test_plan_functional_case_associate_bug_page(request: Request):
    """测试计划-用例详情-缺陷列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/test-plan/functional/case/detail")
async def test_plan_functional_case_detail(request: Request):
    """测试计划-用例详情。"""
    body = await request.json()
    case_id = body.get("caseId", "")
    from app.cases.repository import get_case
    case = get_case(case_id)
    if not case:
        return JSONResponse({"code": 404, "message": "用例不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": case.get("id", ""),
        "name": case.get("title", ""),
        "description": case.get("description", ""),
        "priority": case.get("priority", "P2"),
        "status": case.get("status", "draft"),
        "steps": case.get("structured_cases", []),
    }})


@router.post("/test-plan/functional/case/associate/bug")
async def test_plan_functional_case_associate_bug(request: Request):
    """测试计划-用例详情-关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/disassociate/bug")
async def test_plan_functional_case_disassociate_bug(request: Request):
    """测试计划-用例详情-取消关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/functional/case/user-option")
async def test_plan_functional_case_user_option():
    """计划详情-功能用例-获取用户列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


@router.post("/test-plan/functional/case/batch/update/executor")
async def test_plan_functional_case_batch_update_executor(request: Request):
    """计划详情-功能用例-批量更新执行人。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/exec/history")
async def test_plan_functional_case_exec_history(request: Request):
    """计划详情-功能用例-执行历史。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


@router.post("/test-plan/his/page")
async def test_plan_his_page(request: Request):
    """计划详情-执行历史。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [],
        "total": 0,
    }})


# ════════════════════════════════════════════════════════════
# 计划详情-关联接口用例
# ════════════════════════════════════════════════════════════

@router.post("/test-plan/association/api/page")
async def test_plan_association_api_page(request: Request):
    """功能用例-关联接口列表。"""
    from app.apitest.store import list_definitions
    definitions = list_definitions(limit=100)
    items = [{
        "id": d.get("id", ""),
        "name": d.get("name", ""),
        "method": d.get("method", "GET"),
        "path": d.get("path", ""),
    } for d in definitions]
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
    }})


@router.post("/test-plan/association/api/case/page")
async def test_plan_association_api_case_page(request: Request):
    """功能用例-关联接口用例列表。"""
    from app.apitest.store import list_api_cases
    cases = list_api_cases(limit=100)
    items = [{
        "id": c.get("id", ""),
        "name": c.get("name", ""),
    } for c in cases]
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
    }})


@router.post("/test-plan/association/api/scenario/page")
async def test_plan_association_api_scenario_page(request: Request):
    """功能用例-关联场景列表。"""
    from app.apitest.store import list_scenarios
    scenarios = list_scenarios(limit=100)
    items = [{
        "id": s.get("id", ""),
        "name": s.get("name", ""),
    } for s in scenarios]
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
    }})


# ════════════════════════════════════════════════════════════
# 测试计划-报告管理
# ════════════════════════════════════════════════════════════

@router.post("/test-plan/report/page")
async def test_plan_report_page(request: Request):
    """报告列表。"""
    body = await request.json()
    plan_id = body.get("planId", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    if plan_id:
        plan = test_plan_store.get_plan(plan_id)
        if not plan:
            return JSONResponse({"code": 200, "message": "success", "data": {
                "list": [], "total": 0, "pageSize": page_size, "current": current,
            }})
        stats = test_plan_store.get_plan_statistics(plan_id)
        report = {
            "id": plan_id,
            "name": f"{plan.get('name', '')} 报告",
            "planName": plan.get("name", ""),
            "status": "COMPLETED",
            "createTime": int(plan.get("created_at", 0) * 1000),
            "createUser": "admin",
            "passRate": stats["passRate"],
            "executionRate": stats["executionRate"],
            "total": stats["total"],
            "passed": stats["passed"],
            "failed": stats["failed"],
        }
        return JSONResponse({"code": 200, "message": "success", "data": {
            "list": [report],
            "total": 1,
            "pageSize": page_size,
            "current": current,
        }})

    # 无 planId 时返回所有计划的报告
    plans = test_plan_store.list_plans(limit=100)
    stats_map = test_plan_store.get_plans_statistics([p["id"] for p in plans])
    items = []
    for p in plans:
        stats = stats_map.get(p["id"], {"passRate": 0, "executionRate": 0})
        items.append({
            "id": p["id"],
            "name": f"{p.get('name', '')} 报告",
            "planName": p.get("name", ""),
            "status": "COMPLETED" if p.get("status") == "completed" else "PREPARED",
            "createTime": int(p.get("created_at", 0) * 1000),
            "createUser": "admin",
            "passRate": stats["passRate"],
            "executionRate": stats["executionRate"],
        })

    paged = items[(current - 1) * page_size: current * page_size]
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": paged,
        "total": len(items),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/test-plan/report/rename")
async def test_plan_report_rename(request: Request):
    """报告重命名。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/report/delete")
async def test_plan_report_delete(request: Request):
    """删除报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/report/batch-delete")
async def test_plan_report_batch_delete(request: Request):
    """批量删除报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/report/get")
async def test_plan_report_get(request: Request):
    """报告详情。"""
    body = await request.json()
    report_id = body.get("id", "")
    plan = test_plan_store.get_plan(report_id)
    if not plan:
        return JSONResponse({"code": 200, "message": "success", "data": None})
    stats = test_plan_store.get_plan_statistics(report_id)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": report_id,
        "name": f"{plan.get('name', '')} 报告",
        "planName": plan.get("name", ""),
        "status": "COMPLETED",
        "createTime": int(plan.get("created_at", 0) * 1000),
        "createUser": "admin",
        "passRate": stats["passRate"],
        "executionRate": stats["executionRate"],
        "total": stats["total"],
        "passed": stats["passed"],
        "failed": stats["failed"],
        "pending": stats["pending"],
        "blocked": stats["blocked"],
    }})


@router.post("/test-plan/report/manual-gen")
async def test_plan_report_manual_gen(request: Request):
    """手动生成报告。"""
    body = await request.json()
    plan_id = body.get("planId", "")
    plan = test_plan_store.get_plan(plan_id) if plan_id else None
    if not plan:
        return JSONResponse({"code": 404, "message": "测试计划不存在", "data": None}, status_code=404)
    stats = test_plan_store.get_plan_statistics(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": plan_id,
        "name": f"{plan.get('name', '')} 报告",
        "planId": plan_id,
        "planName": plan.get("name", ""),
        "status": "COMPLETED",
        "createTime": int(time.time() * 1000),
        "stats": stats,
    }})


@router.post("/test-plan/report/get-layout")
async def test_plan_report_get_layout(request: Request):
    """获取报告布局。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/test-plan/report/share/get-layout")
async def test_plan_report_share_get_layout(request: Request):
    """获取分享报告布局。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/test-plan/report/share/gen")
async def test_plan_report_share_gen(request: Request):
    """生成分享链接。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "shareId": str(uuid.uuid4()),
        "shareUrl": f"/test-plan/report/share/get/detail",
    }})


@router.get("/test-plan/report/share/get")
async def test_plan_report_share_get():
    """获取分享链接详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/report/share/get/detail")
async def test_plan_report_share_get_detail():
    """获取分享详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/report/share/get-share-time")
async def test_plan_report_share_get_share_time():
    """获取分享时效。"""
    return JSONResponse({"code": 200, "message": "success", "data": 86400})


@router.post("/test-plan/report/detail/edit")
async def test_plan_report_detail_edit(request: Request):
    """更新报告内容。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/report/detail/bug/page")
async def test_plan_report_detail_bug_page(request: Request):
    """报告详情-缺陷分页。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/detail/functional/case/page")
async def test_plan_report_detail_functional_case_page(request: Request):
    """报告详情-功能用例分页。"""
    body = await request.json()
    report_id = body.get("reportId", "")
    cases = test_plan_store.list_plan_cases(report_id) if report_id else []
    items = []
    for rel in cases:
        items.append({
            "id": rel.get("id", ""),
            "caseId": rel.get("case_id", ""),
            "name": f"用例 {rel.get('case_id', '')[:8]}",
            "status": rel.get("status", "pending"),
        })
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
    }})


@router.post("/test-plan/report/detail/api/case/page")
async def test_plan_report_detail_api_case_page(request: Request):
    """报告详情-接口用例分页。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/detail/scenario/case/page")
async def test_plan_report_detail_scenario_case_page(request: Request):
    """报告详情-场景用例分页。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/detail/plan/report/page")
async def test_plan_report_detail_plan_report_page(request: Request):
    """聚合报告-报告明细。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/detail/functional/case/step")
async def test_plan_report_detail_functional_case_step(request: Request):
    """报告详情-功能用例步骤。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/test-plan/report/export")
async def test_plan_report_export(request: Request):
    """导出报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/report/batch-export")
async def test_plan_report_batch_export(request: Request):
    """批量导出报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/report/batch-param")
async def test_plan_report_batch_param(request: Request):
    """批量导出获取报告 ID。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/test-plan/report/get-result")
async def test_plan_report_get_result(request: Request):
    """测试计划执行结果。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/report/preview/md")
async def test_plan_report_preview_md(request: Request):
    """报告富文本预览。"""
    return JSONResponse({"code": 200, "message": "success", "data": ""})


@router.get("/test-plan/report/preview/md")
async def test_plan_report_preview_md_get():
    """报告富文本预览（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": ""})


@router.post("/test-plan/report/upload/md/file")
async def test_plan_report_upload_md_file(request: Request):
    """富文本编辑器上传图片。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})

@router.get("/test-plan/{plan_id}")
async def test_plan_detail(plan_id: str):
    """获取测试计划详情。"""
    plan = test_plan_store.get_plan(plan_id)
    if not plan:
        return JSONResponse({"code": 404, "message": "测试计划不存在", "data": None}, status_code=404)
    item = _to_plan(plan)
    stats = test_plan_store.get_plan_statistics(plan_id)
    item.update(stats)
    return JSONResponse({"code": 200, "message": "success", "data": item})


# ════════════════════════════════════════════════════════════
# GET 变体路由（前端使用 GET 方法的操作）
# ════════════════════════════════════════════════════════════

@router.get("/test-plan/module/tree/{project_id}")
async def test_plan_module_tree_get(project_id: str):
    """获取测试计划模块树（带项目 ID）。"""
    modules = test_plan_store.list_modules()
    tree = [{"id": "root", "name": "全部计划", "type": "MODULE", "children": []}]
    for m in modules:
        tree[0]["children"].append({
            "id": m["id"],
            "name": m["name"],
            "type": "MODULE",
            "children": [],
        })
    return JSONResponse({"code": 200, "message": "success", "data": tree})


@router.get("/test-plan/module/delete/{module_id}")
async def test_plan_module_delete_get(module_id: str):
    """删除测试计划模块（GET 方式）。"""
    test_plan_store.delete_module(module_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/test-plan-list/{project_id}")
async def test_plan_list_no_page_get(project_id: str):
    """获取测试计划列表无分页（带项目 ID）。"""
    plans = test_plan_store.list_plans(limit=500)
    items = []
    for p in plans:
        item = {
            "id": p.get("id", ""),
            "name": p.get("name", ""),
            "status": p.get("status", "prepared"),
            "priority": p.get("priority", "P2"),
        }
        items.append(item)
    return JSONResponse({"code": 200, "message": "success", "data": items})


@router.get("/test-plan/delete/{plan_id}")
async def test_plan_delete_get(plan_id: str):
    """删除测试计划（GET 方式）。"""
    test_plan_store.delete_plan(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/getCount/{plan_id}")
async def test_plan_get_count_get(plan_id: str):
    """获取统计数量（带计划 ID）。"""
    plan = test_plan_store.get_plan(plan_id)
    if not plan:
        return JSONResponse({"code": 200, "message": "success", "data": {
            "total": 0, "caseCount": 0, "executionRate": 0, "passRate": 0,
        }})
    stats = test_plan_store.get_plan_statistics(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "total": 1,
        "caseCount": stats["total"],
        "executionRate": stats["executionRate"],
        "passRate": stats["passRate"],
    }})


@router.get("/test-plan/archived/{plan_id}")
async def test_plan_archived_get(plan_id: str):
    """归档测试计划（GET 方式）。"""
    test_plan_store.archive_plan(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/functional/case/user-option/{project_id}")
async def test_plan_functional_case_user_option_get(project_id: str):
    """计划详情-功能用例-获取用户列表（带项目 ID）。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


@router.get("/test-plan/functional/case/detail/{case_id}")
async def test_plan_functional_case_detail_get(case_id: str):
    """测试计划-用例详情（GET 方式）。"""
    from app.cases.repository import get_case
    case = get_case(case_id)
    if not case:
        return JSONResponse({"code": 404, "message": "用例不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": case.get("id", ""),
        "name": case.get("title", ""),
        "description": case.get("description", ""),
        "priority": case.get("priority", "P2"),
        "status": case.get("status", "draft"),
        "steps": case.get("structured_cases", []),
    }})


@router.get("/test-plan/functional/case/disassociate/bug/{rel_id}")
async def test_plan_functional_case_disassociate_bug_get(rel_id: str):
    """测试计划-用例详情-取消关联缺陷（GET 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/api/case/run/{case_id}")
async def test_plan_api_case_run_get(case_id: str, reportId: str = ""):
    """运行接口用例（GET 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": "success",
        "result": "SUCCESS",
    }})


# ════════════════════════════════════════════════════════════
# 计划详情-接口用例管理
# ════════════════════════════════════════════════════════════

@router.post("/test-plan/api/case/page")
async def test_plan_api_case_page(request: Request):
    """计划详情-接口用例列表。"""
    body = await request.json()
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.apitest.store import list_api_cases
    cases = list_api_cases(limit=page_size, offset=(current - 1) * page_size)

    items = [{
        "id": c.get("id", ""),
        "name": c.get("name", ""),
        "description": c.get("description", ""),
        "createTime": c.get("created_at", 0),
    } for c in cases]

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/test-plan/api/case/tree")
async def test_plan_api_case_tree(request: Request):
    """计划详情-接口用例模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "root", "name": "全部接口用例", "type": "MODULE", "children": []}
    ]})


@router.post("/test-plan/api/case/module/count")
async def test_plan_api_case_module_count(request: Request):
    """计划详情-接口用例模块数量。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/test-plan/api/case/sort")
async def test_plan_api_case_sort(request: Request):
    """计划详情-接口用例拖拽排序。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/case/disassociate")
async def test_plan_api_case_disassociate(request: Request):
    """计划详情-接口用例取消关联。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/case/batch/disassociate")
async def test_plan_api_case_batch_disassociate(request: Request):
    """计划详情-接口用例批量取消关联。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/case/batch/run")
async def test_plan_api_case_batch_run(request: Request):
    """计划详情-接口用例批量执行。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/case/batch/move")
async def test_plan_api_case_batch_move(request: Request):
    """计划详情-接口用例批量移动。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/api/case/report/get/{report_id}")
async def test_plan_api_case_report_get(report_id: str):
    """计划详情-接口用例报告详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/api/case/report/get/detail/{report_id}/{step_id}")
async def test_plan_api_case_report_detail(report_id: str, step_id: str):
    """计划详情-接口用例步骤详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 计划详情-接口场景管理
# ════════════════════════════════════════════════════════════

@router.post("/test-plan/api/scenario/page")
async def test_plan_api_scenario_page(request: Request):
    """计划详情-接口场景列表。"""
    body = await request.json()
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.apitest.store import list_scenarios
    scenarios = list_scenarios(limit=page_size, offset=(current - 1) * page_size)

    items = [{
        "id": s.get("id", ""),
        "name": s.get("name", ""),
        "description": s.get("description", ""),
        "createTime": s.get("created_at", 0),
    } for s in scenarios]

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/test-plan/api/scenario/tree")
async def test_plan_api_scenario_tree(request: Request):
    """计划详情-接口场景模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "root", "name": "全部场景", "type": "MODULE", "children": []}
    ]})


@router.post("/test-plan/api/scenario/module/count")
async def test_plan_api_scenario_module_count(request: Request):
    """计划详情-接口场景模块数量。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/test-plan/api/scenario/sort")
async def test_plan_api_scenario_sort(request: Request):
    """计划详情-接口场景拖拽排序。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/api/scenario/run/{scenario_id}")
async def test_plan_api_scenario_run_get(scenario_id: str, reportId: str = ""):
    """运行接口场景（GET 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "status": "success",
        "result": "SUCCESS",
    }})


@router.post("/test-plan/api/scenario/disassociate")
async def test_plan_api_scenario_disassociate(request: Request):
    """计划详情-接口场景取消关联。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/scenario/batch/disassociate")
async def test_plan_api_scenario_batch_disassociate(request: Request):
    """计划详情-接口场景批量取消关联。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/scenario/batch/run")
async def test_plan_api_scenario_batch_run(request: Request):
    """计划详情-接口场景批量执行。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/scenario/batch/move")
async def test_plan_api_scenario_batch_move(request: Request):
    """计划详情-接口场景批量移动。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/api/scenario/report/get/{report_id}")
async def test_plan_api_scenario_report_get(report_id: str):
    """计划详情-接口场景报告详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/api/scenario/report/get/detail/{report_id}/{step_id}")
async def test_plan_api_scenario_report_detail(report_id: str, step_id: str):
    """计划详情-接口场景步骤详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ════════════════════════════════════════════════════════════
# 测试计划-执行与脑图
# ════════════════════════════════════════════════════════════

@router.post("/test-plan-execute/single")
async def test_plan_execute_single(request: Request):
    """执行单个测试计划。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan-execute/batch")
async def test_plan_execute_batch(request: Request):
    """批量执行测试计划。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/schedule-config-delete/{test_plan_id}")
async def test_plan_schedule_config_delete(test_plan_id: str):
    """删除定时任务。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/mind/data")
async def test_plan_mind_data(testPlanId: str = ""):
    """获取测试规划脑图数据。"""
    from app.cases.repository import list_cases
    cases = list_cases(limit=100)
    tree = []
    for c in cases:
        node = {
            "id": c.get("id", ""),
            "text": c.get("title", ""),
            "resource": {
                "status": c.get("status", "draft"),
                "priority": c.get("priority", "P2"),
            },
            "children": [],
        }
        tree.append(node)
    return JSONResponse({"code": 200, "message": "success", "data": tree})


@router.post("/test-plan/mind/data/edit")
async def test_plan_mind_data_edit(request: Request):
    """修改测试规划脑图。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/association/api/case/module/count")
async def test_plan_association_api_case_module_count(request: Request):
    """获取测试计划-关联用例-接口模块数量。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/test-plan-execute/user-option/{project_id}")
async def test_plan_execute_user_option(project_id: str, keyword: str = ""):
    """获取执行人下拉选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


@router.post("/test-plan/functional/case/associate/bug/page")
async def test_plan_functional_case_associate_bug_page(request: Request):
    """获取测试计划未关联缺陷列表。"""
    from app.defects.tracker import list_defects
    defects = list_defects(limit=100)
    items = [{
        "id": d.get("id", ""),
        "name": d.get("title", ""),
        "title": d.get("title", ""),
        "status": d.get("status", "open"),
    } for d in defects]
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
    }})


@router.post("/test-plan/api/case/associate/bug/page")
async def test_plan_api_case_associate_bug_page(request: Request):
    """获取接口用例未关联缺陷列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/api/scenario/associate/bug/page")
async def test_plan_api_scenario_associate_bug_page(request: Request):
    """获取场景用例未关联缺陷列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/api/case/associate/bug")
async def test_plan_api_case_associate_bug(request: Request):
    """接口用例关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/scenario/associate/bug")
async def test_plan_api_scenario_associate_bug(request: Request):
    """场景用例关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/api/case/disassociate/bug/{rel_id}")
async def test_plan_api_case_disassociate_bug_get(rel_id: str):
    """接口用例取消关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/api/scenario/disassociate/bug/{rel_id}")
async def test_plan_api_scenario_disassociate_bug_get(rel_id: str):
    """场景用例取消关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/batch/associate-bug")
async def test_plan_functional_case_batch_associate_bug(request: Request):
    """功能用例批量关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/batch/add-bug")
async def test_plan_functional_case_batch_add_bug(request: Request):
    """功能用例批量新建缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/case/batch/add-bug")
async def test_plan_api_case_batch_add_bug(request: Request):
    """接口用例批量新建缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/scenario/batch/add-bug")
async def test_plan_api_scenario_batch_add_bug(request: Request):
    """场景用例批量新建缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/case/batch/associate-bug")
async def test_plan_api_case_batch_associate_bug(request: Request):
    """接口用例批量关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/scenario/batch/associate-bug")
async def test_plan_api_scenario_batch_associate_bug(request: Request):
    """场景用例批量关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/minder/batch/associate-bug")
async def test_plan_functional_case_minder_batch_associate_bug(request: Request):
    """脑图批量关联缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/functional/case/minder/batch/add-bug")
async def test_plan_functional_case_minder_batch_add_bug(request: Request):
    """脑图批量新建缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/report/get-task/{plan_id}")
async def test_plan_report_get_task(plan_id: str):
    """测试计划执行结果。"""
    plan = test_plan_store.get_plan(plan_id)
    if not plan:
        return JSONResponse({"code": 200, "message": "success", "data": None})
    stats = test_plan_store.get_plan_statistics(plan_id)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": plan_id,
        "name": plan.get("name", ""),
        "status": "SUCCESS",
        "executionRate": stats["executionRate"],
        "passRate": stats["passRate"],
        "caseCount": stats["total"],
        "passedCount": stats["passed"],
        "failedCount": stats["failed"],
    }})


@router.post("/test-plan/report/share/detail/bug/page")
async def test_plan_report_share_detail_bug_page(request: Request):
    """分享报告缺陷分页。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/share/detail/functional/case/page")
async def test_plan_report_share_detail_functional_case_page(request: Request):
    """分享报告功能用例分页。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/share/detail/api/case/page")
async def test_plan_report_share_detail_api_case_page(request: Request):
    """分享报告接口用例分页。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/share/detail/scenario/case/page")
async def test_plan_report_share_detail_scenario_case_page(request: Request):
    """分享报告场景用例分页。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/share/detail/plan/report/page")
async def test_plan_report_share_detail_plan_report_page(request: Request):
    """分享聚合报告明细。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/share/detail/functional/case/step")
async def test_plan_report_share_detail_functional_case_step(request: Request):
    """分享报告功能用例步骤。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/test-plan/report/share/detail/api-report")
async def test_plan_report_share_detail_api_report():
    """分享接口报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/report/share/detail/api-report/get")
async def test_plan_report_share_detail_api_report_get():
    """分享接口报告详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/report/share/detail/scenario-report")
async def test_plan_report_share_detail_scenario_report():
    """分享场景报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/test-plan/report/share/detail/scenario-report/get")
async def test_plan_report_share_detail_scenario_report_get():
    """分享场景报告详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/case/report/get")
async def test_plan_api_case_report_get_post(request: Request):
    """接口报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/case/report/get/detail")
async def test_plan_api_case_report_get_detail_post(request: Request):
    """接口报告详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/scenario/report/get")
async def test_plan_api_scenario_report_get_post(request: Request):
    """场景报告。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/api/scenario/report/get/detail")
async def test_plan_api_scenario_report_get_detail_post(request: Request):
    """场景报告详情。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/test-plan/report/detail/functional/collection/page")
async def test_plan_report_detail_functional_collection_page(request: Request):
    """报告-功能用例测试点。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/detail/api/collection/page")
async def test_plan_report_detail_api_collection_page(request: Request):
    """报告-接口用例测试点。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/detail/scenario/collection/page")
async def test_plan_report_detail_scenario_collection_page(request: Request):
    """报告-场景用例测试点。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/share/detail/functional/collection/page")
async def test_plan_report_share_detail_functional_collection_page(request: Request):
    """分享报告-功能用例测试点。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/share/detail/api/collection/page")
async def test_plan_report_share_detail_api_collection_page(request: Request):
    """分享报告-接口用例测试点。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})


@router.post("/test-plan/report/share/detail/scenario/collection/page")
async def test_plan_report_share_detail_scenario_collection_page(request: Request):
    """分享报告-场景用例测试点。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [], "total": 0,
    }})
