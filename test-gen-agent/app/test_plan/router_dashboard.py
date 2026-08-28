# app/test_plan/router_dashboard.py
"""工作台 Dashboard API 路由。

为 MeterSphere 前端工作台页面提供完整的 API 支持。
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.test_plan.store import test_plan_store

dashboard_router = APIRouter(tags=["dashboard"])

# ── 工作台首页数据 ───────────────────────────────────────
@dashboard_router.get("/dashboard/home")
async def dashboard_home():
    """工作台首页数据。"""
    from app.cases.repository import list_cases, get_stats
    from app.defects.tracker import list_defects, get_stats as get_defect_stats
    from app.apitest.store import list_api_cases, list_scenarios, list_definitions

    case_stats = get_stats()
    defect_stats = get_defect_stats()

    api_cases = list_api_cases(limit=999)
    scenarios = list_scenarios(limit=999)
    definitions = list_definitions(limit=999)
    plans = test_plan_store.list_plans(limit=999)

    return JSONResponse({"code": 200, "message": "success", "data": {
        "bugCount": defect_stats.get("total", 0),
        "caseCount": case_stats.get("total", 0),
        "apiCaseCount": len(api_cases),
        "scenarioCount": len(scenarios),
        "testPlanCount": len(plans),
        "definitionCount": len(definitions),
    }})


@dashboard_router.get("/dashboard/overview")
async def dashboard_overview():
    """工作台总览。"""
    from app.cases.repository import list_cases
    from app.defects.tracker import list_defects

    cases = list_cases(limit=999)
    defects = list_defects(limit=999)
    plans = test_plan_store.list_plans(limit=999)

    case_status = {"draft": 0, "review": 0, "approved": 0, "rejected": 0, "deprecated": 0}
    for c in cases:
        s = c.get("status", "draft")
        case_status[s] = case_status.get(s, 0) + 1

    defect_severity = {"critical": 0, "major": 0, "minor": 0, "trivial": 0}
    for d in defects:
        sev = d.get("severity", "major")
        defect_severity[sev] = defect_severity.get(sev, 0) + 1

    plan_status = {"prepared": 0, "running": 0, "completed": 0, "archived": 0}
    for p in plans:
        s = p.get("status", "prepared")
        plan_status[s] = plan_status.get(s, 0) + 1

    return JSONResponse({"code": 200, "message": "success", "data": {
        "projectCount": 1,
        "caseCount": len(cases),
        "caseStatus": case_status,
        "defectCount": len(defects),
        "defectSeverity": defect_severity,
        "testPlanCount": len(plans),
        "planStatus": plan_status,
    }})


@dashboard_router.get("/dashboard/execution-trend")
async def dashboard_execution_trend():
    """执行趋势数据。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "dates": [],
        "executed": [],
        "passed": [],
        "failed": [],
    }})


@dashboard_router.get("/dashboard/recent-activity")
async def dashboard_recent_activity():
    """最近活动。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# ── 工作台布局 ───────────────────────────────────────────
@dashboard_router.get("/dashboard/layout/get/{org_id}")
async def dashboard_layout_get(org_id: str):
    """获取用户 Dashboard 布局配置。"""
    # 返回默认卡片布局
    return JSONResponse({"code": 200, "message": "success", "data": [
        {
            "label": "项目概览",
            "id": "project-overview",
            "key": "PROJECT_VIEW",
            "fullScreen": False,
            "isDisabledHalfScreen": False,
            "projectIds": [],
            "handleUsers": [],
            "selectAll": True,
            "planId": "",
            "groupId": "",
            "pos": 0,
        },
        {
            "label": "用例数",
            "id": "case-count",
            "key": "CASE_COUNT",
            "fullScreen": False,
            "isDisabledHalfScreen": False,
            "projectIds": [],
            "handleUsers": [],
            "selectAll": True,
            "planId": "",
            "groupId": "",
            "pos": 1,
        },
        {
            "label": "缺陷数",
            "id": "bug-count",
            "key": "BUG_COUNT",
            "fullScreen": False,
            "isDisabledHalfScreen": False,
            "projectIds": [],
            "handleUsers": [],
            "selectAll": True,
            "planId": "",
            "groupId": "",
            "pos": 2,
        },
        {
            "label": "接口数",
            "id": "api-count",
            "key": "API_COUNT",
            "fullScreen": False,
            "isDisabledHalfScreen": False,
            "projectIds": [],
            "handleUsers": [],
            "selectAll": True,
            "planId": "",
            "groupId": "",
            "pos": 3,
        },
    ]})


@dashboard_router.post("/dashboard/layout/edit/{org_id}")
async def dashboard_layout_edit(org_id: str, request: Request):
    """更新用户 Dashboard 布局配置。"""
    try:
        body = await request.json()
    except Exception:
        body = []
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 工作台统计卡片 ───────────────────────────────────────
@dashboard_router.post("/dashboard/project_view")
async def dashboard_project_view(request: Request):
    """项目概览：按时间统计用例/缺陷/接口创建量。"""
    body = await _parse_body(request)
    day_number = body.get("dayNumber", 3)
    start_time = body.get("startTime", 0)
    end_time = body.get("endTime", 0)
    project_ids = body.get("projectIds", [])

    from app.cases.repository import list_cases
    from app.defects.tracker import list_defects
    from app.apitest.store import list_api_cases

    cases = list_cases(limit=999)
    defects = list_defects(limit=999)
    api_cases = list_api_cases(limit=999)

    # 构造时间范围
    now = time.time()
    if start_time and end_time:
        start_ts, end_ts = start_time / 1000, end_time / 1000
    else:
        start_ts = now - int(day_number or 3) * 86400
        end_ts = now

    # 生成横坐标（最近 N 天或时间段内每天的日期）
    days = int((end_ts - start_ts) / 86400) + 1
    days = max(1, min(days, 31))  # 限制最多 31 天

    xaxis = []
    case_counts = []
    defect_counts = []
    api_counts = []

    for i in range(days - 1, -1, -1):
        day_start = end_ts - i * 86400
        day_end = day_start + 86400
        day_label = time.strftime("%m-%d", time.localtime(day_start))
        xaxis.append(day_label)

        case_counts.append(sum(1 for c in cases if day_start <= c.get("created_at", 0) < day_end))
        defect_counts.append(sum(1 for d in defects if day_start <= d.get("created_at", 0) < day_end))
        api_counts.append(sum(1 for a in api_cases if day_start <= a.get("created_at", 0) < day_end))

    return JSONResponse({"code": 200, "message": "success", "data": {
        "caseCountMap": {"case": sum(case_counts), "defect": sum(defect_counts), "api": sum(api_counts)},
        "projectCountList": [
            {"id": "default", "name": "默认项目", "count": case_counts},
        ],
        "xaxis": xaxis,
        "errorCode": 0,
    }})


@dashboard_router.post("/dashboard/create_by_me")
async def dashboard_create_by_me(request: Request):
    """我创建的数据统计。"""
    body = await _parse_body(request)
    day_number = body.get("dayNumber", 3)
    start_time = body.get("startTime", 0)
    end_time = body.get("endTime", 0)

    from app.cases.repository import list_cases
    from app.defects.tracker import list_defects
    from app.apitest.store import list_api_cases

    cases = list_cases(limit=999)
    defects = list_defects(limit=999)
    api_cases = list_api_cases(limit=999)

    now = time.time()
    if start_time and end_time:
        start_ts, end_ts = start_time / 1000, end_time / 1000
    else:
        start_ts = now - int(day_number or 3) * 86400
        end_ts = now

    days = int((end_ts - start_ts) / 86400) + 1
    days = max(1, min(days, 31))

    xaxis = []
    case_counts = []
    defect_counts = []
    api_counts = []

    for i in range(days - 1, -1, -1):
        day_start = end_ts - i * 86400
        day_end = day_start + 86400
        day_label = time.strftime("%m-%d", time.localtime(day_start))
        xaxis.append(day_label)
        case_counts.append(sum(1 for c in cases if day_start <= c.get("created_at", 0) < day_end))
        defect_counts.append(sum(1 for d in defects if day_start <= d.get("created_at", 0) < day_end))
        api_counts.append(sum(1 for a in api_cases if day_start <= a.get("created_at", 0) < day_end))

    return JSONResponse({"code": 200, "message": "success", "data": {
        "caseCountMap": {"case": sum(case_counts), "defect": sum(defect_counts), "api": sum(api_counts)},
        "projectCountList": [
            {"id": "default", "name": "默认项目", "count": case_counts},
        ],
        "xaxis": xaxis,
        "errorCode": 0,
    }})


@dashboard_router.post("/dashboard/project_member_view")
async def dashboard_project_member_view(request: Request):
    """项目成员概览。"""
    body = await _parse_body(request)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "caseCountMap": {},
        "projectCountList": [],
        "xaxis": [],
        "errorCode": 0,
    }})


# ── 数量统计卡片 ─────────────────────────────────────────
def _get_pass_rate_data(cases: List[Dict], status_key: str = "status") -> Dict:
    """构造 PassRateDataType 响应。"""
    if not cases:
        return {
            "statusStatisticsMap": None,
            "statusPercentList": [],
            "errorCode": 0,
        }

    status_map = {}
    for c in cases:
        s = c.get(status_key, "draft")
        if s not in status_map:
            status_map[s] = {"name": s, "count": 0}
        status_map[s]["count"] += 1

    total = len(cases)
    status_percent = [
        {"status": v["name"], "count": v["count"], "percentValue": f"{round(v['count'] / total * 100, 1)}%"}
        for v in status_map.values()
    ]

    return {
        "statusStatisticsMap": status_map,
        "statusPercentList": status_percent,
        "errorCode": 0,
    }


@dashboard_router.post("/dashboard/case_count")
async def dashboard_case_count(request: Request):
    """用例数量统计。"""
    from app.cases.repository import list_cases
    cases = list_cases(limit=999)
    return JSONResponse({"code": 200, "message": "success", "data": _get_pass_rate_data(cases)})


@dashboard_router.post("/dashboard/associate_case_count")
async def dashboard_associate_case_count(request: Request):
    """关联用例数量统计。"""
    from app.cases.repository import list_cases
    cases = list_cases(limit=999)
    # 统计所有有关联的用例
    associated = [c for c in cases if c.get("related_ids") or c.get("relations")]
    return JSONResponse({"code": 200, "message": "success", "data": _get_pass_rate_data(associated)})


@dashboard_router.post("/dashboard/review_case_count")
async def dashboard_review_case_count(request: Request):
    """用例评审数量统计。"""
    from app.cases.repository import list_cases
    cases = list_cases(limit=999)
    # 评审中的用例
    in_review = [c for c in cases if c.get("status") in ("review", "pending", "in_review")]
    return JSONResponse({"code": 200, "message": "success", "data": _get_pass_rate_data(in_review)})


@dashboard_router.post("/dashboard/reviewing_by_me")
async def dashboard_reviewing_by_me(request: Request):
    """待我评审列表。"""
    from app.cases.repository import list_cases
    cases = list_cases(limit=999)
    # 待评审的用例
    reviews = [c for c in cases if c.get("status") in ("review", "pending", "in_review")]
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": [_case_to_review_item(c) for c in reviews[:20]],
        "total": len(reviews),
    }})


@dashboard_router.post("/dashboard/api_count")
async def dashboard_api_count(request: Request):
    """接口数量统计。"""
    from app.apitest.store import list_definitions
    definitions = list_definitions(limit=999)
    return JSONResponse({"code": 200, "message": "success", "data": _get_pass_rate_data(definitions, "protocol")})


@dashboard_router.post("/dashboard/api_case_count")
async def dashboard_api_case_count(request: Request):
    """接口用例数量统计。"""
    from app.apitest.store import list_api_cases
    cases = list_api_cases(limit=999)
    return JSONResponse({"code": 200, "message": "success", "data": _get_pass_rate_data(cases)})


@dashboard_router.post("/dashboard/scenario_count")
async def dashboard_scenario_count(request: Request):
    """场景用例数量统计。"""
    from app.apitest.store import list_scenarios
    scenarios = list_scenarios(limit=999)
    return JSONResponse({"code": 200, "message": "success", "data": _get_pass_rate_data(scenarios)})


@dashboard_router.post("/dashboard/bug_count")
async def dashboard_bug_count(request: Request):
    """缺陷数量统计。"""
    from app.defects.tracker import list_defects
    defects = list_defects(limit=999)
    return JSONResponse({"code": 200, "message": "success", "data": _get_pass_rate_data(defects)})


@dashboard_router.post("/dashboard/create_bug_by_me")
async def dashboard_create_bug_by_me(request: Request):
    """我创建的缺陷统计。"""
    from app.defects.tracker import list_defects
    defects = list_defects(limit=999)
    return JSONResponse({"code": 200, "message": "success", "data": _get_pass_rate_data(defects)})


@dashboard_router.post("/dashboard/handle_bug_by_me")
async def dashboard_handle_bug_by_me(request: Request):
    """待我处理的缺陷统计。"""
    from app.defects.tracker import list_defects
    defects = list_defects(limit=999)
    open_defects = [d for d in defects if d.get("status") in ("open", "in_progress", "reopened", "new")]
    return JSONResponse({"code": 200, "message": "success", "data": _get_pass_rate_data(open_defects)})


@dashboard_router.post("/dashboard/plan_legacy_bug")
async def dashboard_plan_legacy_bug(request: Request):
    """测试计划遗留缺陷。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "statusStatisticsMap": None,
        "statusPercentList": [],
        "errorCode": 0,
    }})


# ── 缺陷处理人 ───────────────────────────────────────────
@dashboard_router.post("/dashboard/bug_handle_user")
async def dashboard_bug_handle_user(request: Request):
    """缺陷处理人概览。"""
    return JSONResponse({"code": 200, "message": "success", "data": {
        "caseCountMap": {},
        "projectCountList": [],
        "xaxis": [],
        "errorCode": 0,
    }})


@dashboard_router.get("/dashboard/bug_handle_user/list")
async def dashboard_bug_handle_user_list():
    """缺陷处理人列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


# ── 接口变更 ─────────────────────────────────────────────
@dashboard_router.post("/dashboard/api_change")
async def dashboard_api_change(request: Request):
    """接口变更列表。"""
    from app.apitest.store import list_definitions
    definitions = list_definitions(limit=50)
    items = []
    for d in definitions:
        items.append({
            "id": d.get("id", ""),
            "name": d.get("name", ""),
            "method": d.get("method", "GET"),
            "path": d.get("path", ""),
            "protocol": d.get("protocol", "HTTP"),
            "status": d.get("status", "open"),
            "createTime": d.get("created_at", 0),
            "updateTime": d.get("updated_at", 0),
        })
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
    }})


# ── 项目成员选项 ─────────────────────────────────────────
@dashboard_router.get("/dashboard/member/get-project-member/option/{project_id}")
async def dashboard_member_option(project_id: str, keyword: str = ""):
    """获取项目成员下拉选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


@dashboard_router.get("/dashboard/plan/option/{project_id}")
async def dashboard_plan_option(project_id: str):
    """获取测试计划下拉选项。"""
    plans = test_plan_store.list_plans(limit=100)
    items = [{"id": p["id"], "name": p["name"]} for p in plans]
    return JSONResponse({"code": 200, "message": "success", "data": items})


@dashboard_router.post("/dashboard/plan_view")
async def dashboard_plan_view(request: Request):
    """测试计划概览。"""
    body = await _parse_body(request)
    plan_id = body.get("planId", "")

    if plan_id:
        plan = test_plan_store.get_plan(plan_id)
        if not plan:
            return JSONResponse({"code": 200, "message": "success", "data": {
                "caseCountMap": {}, "projectCountList": [], "xaxis": [], "errorCode": 0,
            }})
        stats = test_plan_store.get_plan_statistics(plan_id)
        xaxis = [plan.get("name", "")]
        return JSONResponse({"code": 200, "message": "success", "data": {
            "caseCountMap": {"passed": stats["passed"], "failed": stats["failed"], "pending": stats["pending"]},
            "projectCountList": [{"id": plan_id, "name": plan.get("name", ""), "count": [stats["total"]]}],
            "xaxis": xaxis,
            "errorCode": 0,
        }})

    # 没有指定计划则返回所有计划的统计
    plans = test_plan_store.list_plans(limit=50)
    xaxis = [p.get("name", "") for p in plans[:10]]
    stats_map = test_plan_store.get_plans_statistics([p["id"] for p in plans[:10]])
    counts = [stats_map.get(p["id"], {}).get("total", 0) for p in plans[:10]]

    return JSONResponse({"code": 200, "message": "success", "data": {
        "caseCountMap": {},
        "projectCountList": [{"id": "all", "name": "全部计划", "count": counts}],
        "xaxis": xaxis,
        "errorCode": 0,
    }})


# ── 工作台-我的列表 ──────────────────────────────────────
@dashboard_router.post("/dashboard/my/functional/page")
async def dashboard_my_functional_page(request: Request):
    """工作台-我的-功能用例列表。"""
    body = await _parse_body(request)
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.cases.repository import list_cases
    cases = list_cases(limit=page_size, offset=(current - 1) * page_size)

    items = []
    for c in cases:
        items.append({
            "id": c.get("id", ""),
            "name": c.get("title", ""),
            "priority": c.get("priority", "P2"),
            "status": c.get("status", "draft"),
            "testType": c.get("test_type", "functional"),
            "createTime": c.get("created_at", 0),
            "updateTime": c.get("updated_at", 0),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
        "pageSize": page_size,
        "current": current,
    }})


@dashboard_router.post("/dashboard/my/bug/page")
async def dashboard_my_bug_page(request: Request):
    """工作台-我的-缺陷列表。"""
    body = await _parse_body(request)
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
            "createTime": d.get("created_at", 0),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
        "pageSize": page_size,
        "current": current,
    }})


@dashboard_router.post("/dashboard/my/plan/page")
async def dashboard_my_plan_page(request: Request):
    """工作台-我的-测试计划列表。"""
    body = await _parse_body(request)
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    plans = test_plan_store.list_plans(limit=page_size, offset=(current - 1) * page_size)
    stats_map = test_plan_store.get_plans_statistics([p["id"] for p in plans])
    items = []
    for p in plans:
        stats = stats_map.get(p["id"], {"executionRate": 0, "passRate": 0, "total": 0})
        items.append({
            "id": p.get("id", ""),
            "name": p.get("name", ""),
            "status": p.get("status", "prepared"),
            "priority": p.get("priority", "P2"),
            "executionRate": stats["executionRate"],
            "passRate": stats["passRate"],
            "caseCount": stats["total"],
            "createTime": p.get("created_at", 0),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": test_plan_store.count_plans(),
        "pageSize": page_size,
        "current": current,
    }})


@dashboard_router.post("/dashboard/my/plan/statistics")
async def dashboard_my_plan_statistics(request: Request):
    """工作台-我的-测试计划统计。"""
    try:
        plan_ids = await request.json()
    except Exception:
        plan_ids = []

    if not isinstance(plan_ids, list):
        plan_ids = []

    stats_map = test_plan_store.get_plans_statistics(plan_ids)
    items = []
    for pid in plan_ids:
        plan = test_plan_store.get_plan(pid)
        if not plan:
            continue
        stats = stats_map.get(pid, {})
        items.append({
            "id": pid,
            "name": plan.get("name", ""),
            "passRate": stats.get("passRate", 0),
            "executionRate": stats.get("executionRate", 0),
            "total": stats.get("total", 0),
            "passed": stats.get("passed", 0),
            "failed": stats.get("failed", 0),
            "pending": stats.get("pending", 0),
        })

    return JSONResponse({"code": 200, "message": "success", "data": items})


@dashboard_router.post("/dashboard/my/review/page")
async def dashboard_my_review_page(request: Request):
    """工作台-我的-用例评审列表。"""
    body = await _parse_body(request)
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.cases.repository import list_cases
    cases = list_cases(limit=999)
    review_cases = [c for c in cases if c.get("status") in ("review", "pending", "in_review")]
    paged = review_cases[(current - 1) * page_size: current * page_size]

    items = []
    for c in paged:
        items.append(_case_to_review_item(c))

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(review_cases),
        "pageSize": page_size,
        "current": current,
    }})


@dashboard_router.post("/dashboard/my/api/page")
async def dashboard_my_api_page(request: Request):
    """工作台-我的-接口用例列表。"""
    body = await _parse_body(request)
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.apitest.store import list_api_cases
    cases = list_api_cases(limit=page_size, offset=(current - 1) * page_size)

    items = []
    for c in cases:
        items.append({
            "id": c.get("id", ""),
            "name": c.get("name", ""),
            "description": c.get("description", ""),
            "createTime": c.get("created_at", 0),
            "updateTime": c.get("updated_at", 0),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
        "pageSize": page_size,
        "current": current,
    }})


@dashboard_router.post("/dashboard/my/scenario/page")
async def dashboard_my_scenario_page(request: Request):
    """工作台-我的-场景列表。"""
    body = await _parse_body(request)
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.apitest.store import list_scenarios
    scenarios = list_scenarios(limit=page_size, offset=(current - 1) * page_size)

    items = []
    for s in scenarios:
        items.append({
            "id": s.get("id", ""),
            "name": s.get("name", ""),
            "description": s.get("description", ""),
            "createTime": s.get("created_at", 0),
            "updateTime": s.get("updated_at", 0),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
        "pageSize": page_size,
        "current": current,
    }})


# ── 工作台-待办列表 ──────────────────────────────────────
@dashboard_router.post("/dashboard/todo/plan/page")
async def dashboard_todo_plan_page(request: Request):
    """工作台-待办-测试计划列表。"""
    body = await _parse_body(request)
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    plans = test_plan_store.list_plans(limit=page_size, offset=(current - 1) * page_size)
    stats_map = test_plan_store.get_plans_statistics([p["id"] for p in plans])
    items = []
    for p in plans:
        stats = stats_map.get(p["id"], {"executionRate": 0, "passRate": 0, "total": 0})
        items.append({
            "id": p.get("id", ""),
            "name": p.get("name", ""),
            "status": p.get("status", "prepared"),
            "priority": p.get("priority", "P2"),
            "executionRate": stats["executionRate"],
            "passRate": stats["passRate"],
            "caseCount": stats["total"],
            "createTime": p.get("created_at", 0),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": test_plan_store.count_plans(),
        "pageSize": page_size,
        "current": current,
    }})


@dashboard_router.post("/dashboard/todo/review/page")
async def dashboard_todo_review_page(request: Request):
    """工作台-待办-用例评审列表。"""
    body = await _parse_body(request)
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.cases.repository import list_cases
    cases = list_cases(limit=999)
    review_cases = [c for c in cases if c.get("status") in ("review", "pending", "in_review")]
    paged = review_cases[(current - 1) * page_size: current * page_size]

    items = [_case_to_review_item(c) for c in paged]

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(review_cases),
        "pageSize": page_size,
        "current": current,
    }})


@dashboard_router.post("/dashboard/todo/bug/page")
async def dashboard_todo_bug_page(request: Request):
    """工作台-待办-缺陷列表。"""
    body = await _parse_body(request)
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
            "createTime": d.get("created_at", 0),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(items),
        "pageSize": page_size,
        "current": current,
    }})


# ── 缺陷列表自定义字段 ───────────────────────────────────
@dashboard_router.get("/dashboard/header/custom-field/{project_id}")
async def dashboard_header_custom_field(project_id: str):
    """缺陷列表自定义字段。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@dashboard_router.get("/dashboard/header/columns-option/{project_id}")
async def dashboard_header_columns_option(project_id: str):
    """缺陷列表列选项。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


# ── 接口覆盖率 ───────────────────────────────────────────
@dashboard_router.get("/api/definition/rage")
@dashboard_router.get("/api/definition/rage/{project_id}")
async def dashboard_api_coverage(project_id: str = ""):
    """接口覆盖率统计。"""
    from app.apitest.store import list_definitions, list_api_cases, list_scenarios

    definitions = list_definitions(limit=999)
    api_cases = list_api_cases(limit=999)
    scenarios = list_scenarios(limit=999)

    total_api = len(definitions)
    covered_api = min(total_api, len(api_cases))

    return JSONResponse({"code": 200, "message": "success", "data": {
        "allApiCount": total_api,
        "unCoverWithApiDefinition": max(0, total_api - covered_api),
        "coverWithApiDefinition": covered_api,
        "apiCoverage": f"{round(covered_api / total_api * 100, 1) if total_api else 0}%",
        "unCoverWithApiCase": 0,
        "coverWithApiCase": len(api_cases),
        "apiCaseCoverage": "0%",
        "unCoverWithApiScenario": 0,
        "coverWithApiScenario": len(scenarios),
        "scenarioCoverage": "0%",
    }})


# ── 测试计划数量统计 ─────────────────────────────────────
@dashboard_router.post("/test-plan/rage")
async def dashboard_test_plan_rage(request: Request):
    """测试计划数量统计。"""
    body = await _parse_body(request)
    plans = test_plan_store.list_plans(limit=999)

    status_map = {"prepared": 0, "running": 0, "completed": 0, "archived": 0}
    for p in plans:
        s = p.get("status", "prepared")
        status_map[s] = status_map.get(s, 0) + 1

    total = len(plans)
    executed = total - status_map.get("prepared", 0)
    passed = 0
    completed_ids = [p["id"] for p in plans if p.get("status") == "completed"]
    if completed_ids:
        stats_map = test_plan_store.get_plans_statistics(completed_ids)
        for pid in completed_ids:
            stats = stats_map.get(pid, {})
            passed += stats.get("passed", 0)

    return JSONResponse({"code": 200, "message": "success", "data": {
        "unExecute": status_map.get("prepared", 0),
        "executed": executed,
        "passed": passed,
        "notPassed": max(0, executed - passed),
        "finished": status_map.get("completed", 0),
        "running": status_map.get("running", 0),
        "prepared": status_map.get("prepared", 0),
        "archived": status_map.get("archived", 0),
        "errorCode": 0,
        "passedArchived": 0,
        "notPassedArchived": 0,
    }})


def _case_to_review_item(case: Dict[str, Any]) -> Dict[str, Any]:
    """将用例转为评审列表项格式。"""
    return {
        "id": case.get("id", ""),
        "name": case.get("title", ""),
        "title": case.get("title", ""),
        "priority": case.get("priority", "P2"),
        "status": case.get("status", "draft"),
        "testType": case.get("test_type", "functional"),
        "createTime": case.get("created_at", 0),
        "updateTime": case.get("updated_at", 0),
        "createUser": "admin",
    }


async def _parse_body(request: Request) -> Dict[str, Any]:
    """安全解析请求体。"""
    try:
        return await request.json()
    except Exception:
        return {}
