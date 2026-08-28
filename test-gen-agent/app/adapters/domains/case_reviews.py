# app/adapters/domains/case_reviews.py
"""业务域路由拆分：case_reviews（Phase 3 重构）。"""

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
router = APIRouter(tags=["adapter-case_reviews"])


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


@router.post("/case/review/page")
async def case_review_page(request: Request):
    """获取评审列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.cases.repository import list_cases
    cases = list_cases(limit=999)

    # 筛选评审中的用例
    reviews = [c for c in cases if c.get("status") in ("review", "pending", "in_review", "under_review")]
    if keyword:
        reviews = [c for c in reviews if keyword.lower() in c.get("title", "").lower()]

    paged = reviews[(current - 1) * page_size: current * page_size]

    items = []
    for c in paged:
        items.append({
            "id": c.get("id", ""),
            "name": c.get("title", ""),
            "num": 1,
            "moduleId": "root",
            "status": "UNDERWAY",
            "reviewPassRule": "SINGLE",
            "startTime": c.get("created_at", 0) * 1000,
            "endTime": None,
            "createUser": c.get("created_by", "admin"),
            "createTime": int(c.get("created_at", 0) * 1000),
            "updateTime": int(c.get("updated_at", 0) * 1000),
            "updateUser": "admin",
            "pos": 0,
            "description": c.get("description", ""),
            "tags": None,
            "caseCount": 1,
            "passRate": 0,
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(reviews),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/case/review/add")
async def case_review_add(request: Request):
    """新增评审。"""
    body = await request.json()
    from app.cases.repository import create_case

    case = create_case(
        title=body.get("name", "新评审"),
        description=body.get("description", ""),
        status="review",
        priority="P2",
    )
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": case.get("id", "") if case else str(uuid.uuid4()),
        "name": body.get("name", "新评审"),
        "status": "UNDERWAY",
    }})


@router.post("/case/review/edit")
async def case_review_edit(request: Request):
    """编辑评审。"""
    body = await request.json()
    review_id = body.get("id", "")
    from app.cases.repository import update_case
    updates = {}
    if "name" in body:
        updates["title"] = body["name"]
    if "description" in body:
        updates["description"] = body["description"]
    try:
        case = update_case(review_id, **updates)
    except Exception:
        case = None
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/delete")
async def case_review_delete(request: Request):
    """删除用例评审。"""
    body = await request.json()
    review_id = body.get("id", "")
    from app.cases.repository import delete_case
    delete_case(review_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/copy")
async def case_review_copy(request: Request):
    """复制评审。"""
    body = await request.json()
    copy_id = body.get("copyId", "")
    from app.cases.repository import get_case
    case = get_case(copy_id)
    if case:
        from app.cases.repository import create_case
        new_case = create_case(
            title=f"{case.get('title', '')} (副本)",
            description=case.get("description", ""),
            status="review",
        )
        return JSONResponse({"code": 200, "message": "success", "data": {
            "id": new_case.get("id", "") if new_case else str(uuid.uuid4()),
            "name": f"{case.get('title', '')} (副本)",
            "caseCount": 1,
            "createTime": int(time.time() * 1000),
            "createUser": "admin",
        }})
    return JSONResponse({"code": 404, "message": "评审不存在", "data": None}, status_code=404)


@router.post("/case/review/batch/move")
async def case_review_batch_move(request: Request):
    """移动评审。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/edit/pos")
async def case_review_edit_pos(request: Request):
    """评审拖拽排序。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/edit/follower")
async def case_review_edit_follower(request: Request):
    """关注/取消关注评审。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/associate")
async def case_review_associate(request: Request):
    """关联用例到评审。"""
    body = await request.json()
    review_id = body.get("reviewId", "")
    case_ids = body.get("baseAssociateCaseRequest", {}).get("selectIds", [])
    if not case_ids and body.get("baseAssociateCaseRequest", {}).get("selectAll"):
        # 全选模式下关联所有用例
        from app.cases.repository import list_cases
        all_cases = list_cases(limit=999)
        case_ids = [c["id"] for c in all_cases]
    return JSONResponse({"code": 200, "message": "success", "data": {
        "reviewId": review_id,
        "caseCount": len(case_ids),
    }})


@router.post("/case/review/disassociate")
async def case_review_disassociate(request: Request):
    """取消关联用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail")
async def case_review_detail(request: Request):
    """获取评审详情。"""
    body = await request.json()
    review_id = body.get("id", "")
    from app.cases.repository import get_case
    case = get_case(review_id) if review_id else None
    if not case:
        return JSONResponse({"code": 404, "message": "评审不存在", "data": None}, status_code=404)
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": case.get("id", ""),
        "name": case.get("title", ""),
        "num": 1,
        "moduleId": "root",
        "status": "UNDERWAY",
        "reviewPassRule": "SINGLE",
        "startTime": int(case.get("created_at", 0) * 1000),
        "endTime": None,
        "createUser": "admin",
        "createTime": int(case.get("created_at", 0) * 1000),
        "updateTime": int(case.get("updated_at", 0) * 1000),
        "description": case.get("description", ""),
    }})


@router.get("/case/review/detail")
async def case_review_detail_get(request: Request):
    """获取评审详情（GET 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/page")
async def case_review_detail_page(request: Request):
    """评审详情-获取已关联用例列表。"""
    body = await request.json()
    review_id = body.get("reviewId", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    from app.cases.repository import list_cases
    all_cases = list_cases(limit=999)

    # 如果 reviewId 本身就是一个 case_id，返回该用例
    review_cases = [c for c in all_cases if c.get("id") == review_id]
    if not review_cases:
        # 否则返回所有评审状态的用例
        review_cases = [c for c in all_cases if c.get("status") in ("review", "pending", "in_review")]

    paged = review_cases[(current - 1) * page_size: current * page_size]
    items = []
    for c in paged:
        items.append({
            "id": c.get("id", ""),
            "name": c.get("title", ""),
            "priority": c.get("priority", "P2"),
            "status": "UN_REVIEWED",
            "reviewer": [],
            "createUser": "admin",
            "createTime": int(c.get("created_at", 0) * 1000),
        })

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": items,
        "total": len(review_cases),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/case/review/user-option")
async def case_review_user_option(request: Request):
    """获取评审人员列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


@router.get("/case/review/user-option")
async def case_review_user_option_get():
    """获取评审人员列表（GET 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


# ── 评审模块管理 ─────────────────────────────────────────


@router.get("/case/review/module/tree")
async def case_review_module_tree():
    """获取评审模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {
            "id": "root",
            "name": "全部评审",
            "type": "MODULE",
            "parentId": "",
            "children": [],
            "count": 0,
        }
    ]})


@router.post("/case/review/module/add")
async def case_review_module_add(request: Request):
    """新增评审模块。"""
    body = await request.json()
    return JSONResponse({"code": 200, "message": "success", "data": {
        "id": str(uuid.uuid4()),
        "name": body.get("name", "新模块"),
        "type": "MODULE",
        "parentId": body.get("parentId", "root"),
        "children": [],
        "count": 0,
    }})


@router.post("/case/review/module/update")
async def case_review_module_update(request: Request):
    """更新评审模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/module/delete")
async def case_review_module_delete(request: Request):
    """删除评审模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/module/move")
async def case_review_module_move(request: Request):
    """移动评审模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/module/count")
async def case_review_module_count(request: Request):
    """模块下用例数量统计。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/module/delete")
async def case_review_module_delete_get(id: str = ""):
    """删除评审模块（GET 方式）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 评审详情操作 ─────────────────────────────────────────


@router.post("/case/review/detail/edit/pos")
async def case_review_detail_edit_pos(request: Request):
    """评审详情-已关联用例拖拽排序。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/batch/review")
async def case_review_detail_batch_review(request: Request):
    """评审详情-批量评审。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/batch/disassociate")
async def case_review_detail_batch_disassociate(request: Request):
    """评审详情-批量取消关联用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/batch/edit/reviewers")
async def case_review_detail_batch_edit_reviewers(request: Request):
    """评审详情-批量修改评审人。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/case/review/detail/get-ids")
async def case_review_detail_get_ids(request: Request):
    """获取已关联用例id集合。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/case/review/detail/module/count")
async def case_review_detail_module_count(request: Request):
    """评审详情-模块下用例数量统计。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/case/review/detail/tree")
async def case_review_detail_tree(request: Request):
    """评审详情-已关联用例模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/detail/reviewer/list")
async def case_review_detail_reviewer_list():
    """评审详情-获取用例的评审人。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/case/review/detail/reviewer/status/total")
async def case_review_detail_reviewer_status_total(request: Request):
    """脑图-获取用例评审最终结果。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/case/review/detail/mind/multiple/review")
async def case_review_detail_mind_multiple_review(request: Request):
    """评审详情-脑图评审用例。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/case/review/user-option/{project_id}")
async def case_review_user_option_get_route(project_id: str, keyword: str = ""):
    """获取评审人员列表（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "admin", "name": "admin"},
    ]})


@router.get("/case/review/disassociate/{review_id}/{case_id}")
async def case_review_disassociate_get_route(review_id: str, case_id: str):
    """取消关联用例（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/case/review/delete/{project_id}/{review_id}")
async def case_review_delete_get_route(project_id: str, review_id: str):
    """删除评审（GET）。"""
    from app.cases.repository import delete_case
    delete_case(review_id)
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/case/review/detail/get-ids/{review_id}")
async def case_review_detail_get_ids_get_route(review_id: str):
    """获取已关联用例id集合（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/detail/tree/{review_id}")
async def case_review_detail_tree_get_route(review_id: str):
    """评审详情-模块树（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/detail/reviewer/list/{review_id}/{case_id}")
async def case_review_detail_reviewer_list_get_route(review_id: str, case_id: str):
    """评审详情-获取用例的评审人（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.get("/case/review/detail/reviewer/status/total/{review_id}/{case_id}")
async def case_review_detail_reviewer_status_total_get_route(review_id: str, case_id: str):
    """脑图-获取用例评审结果（GET）。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})

