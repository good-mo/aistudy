# app/routers/cases.py
"""用例管理路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
import json
import os
import tempfile
import time
from typing import Optional
from fastapi import APIRouter, File, Request, UploadFile

from fastapi.responses import FileResponse, JSONResponse
from app.core.response import ok, fail
router = APIRouter(tags=["cases"])


# ════════════════════════════════════════════════════════════
# 用例库管理 API
# ════════════════════════════════════════════════════════════

@router.get("/api/cases")
async def api_list_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    test_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """列出测试用例，支持按状态/优先级/标签/关键词/测试类型过滤。"""
    from app.cases.repository import list_cases
    cases = await asyncio.to_thread(
        list_cases,
        status=status, priority=priority, tag=tag,
        search=search, test_type=test_type, limit=limit, offset=offset,
    )
    return ok({"cases": cases, "total": len(cases)})


@router.get("/api/cases/stats")
async def api_case_stats():
    """获取用例库统计。"""
    from app.cases.repository import get_stats
    return JSONResponse(await asyncio.to_thread(get_stats))


@router.post("/api/cases")
async def api_create_case(req: Request):
    """创建新用例。"""
    from app.cases.repository import create_case
    body = await req.json()
    case = await asyncio.to_thread(create_case,
        title=body.get("title", ""),
        description=body.get("description", ""),
        source_code=body.get("source_code", ""),
        test_code=body.get("test_code", ""),
        file_path=body.get("file_path", ""),
        tags=body.get("tags", []),
        status=body.get("status", "draft"),
        priority=body.get("priority", "P2"),
        requirement_ref=body.get("requirement_ref", ""),
        test_type=body.get("test_type", "functional"),
        structured_cases=body.get("structured_cases", []),
    )
    return JSONResponse(case)


@router.get("/api/cases/mindmap")
async def api_get_case_mindmap_early(project_filter: str = ""):
    """获取用例脑图树形结构（优先路由）。"""
    from app.cases.management import get_case_mindmap
    tree = await asyncio.to_thread(get_case_mindmap, project_filter)
    return JSONResponse(tree)


@router.get("/api/cases/export")
async def api_export_cases_early(format: str = "excel"):
    """导出用例（优先路由）。format: excel/mindmap"""
    from app.cases.management import export_cases_excel, export_cases_mindmap
    from app.cases.repository import list_cases
    cases = await asyncio.to_thread(list_cases, limit=1000)
    if format == "excel":
        content = await asyncio.to_thread(export_cases_excel, cases)
        filename = f"test_cases_export_{int(time.time())}.csv"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
            f.write(content)
            tmp_path = f.name
        return FileResponse(tmp_path, filename=filename,
                            media_type="text/csv; charset=utf-8")
    elif format == "mindmap":
        content = await asyncio.to_thread(export_cases_mindmap, cases)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            f.write(content.encode("utf-8"))
            tmp_path = f.name
        return FileResponse(tmp_path, filename="test_cases_mindmap.json",
                            media_type="application/json")
    return JSONResponse({"error": "不支持的导出格式"}, status_code=400)


@router.get("/api/cases/trash")
async def api_list_trash_cases_early():
    """列出回收站中的用例（优先路由）。"""
    from app.cases.management import list_trash_cases
    trashes = await asyncio.to_thread(list_trash_cases)
    return ok({"trash": trashes, "total": len(trashes)})


@router.get("/api/cases/{case_id}")
async def api_get_case(case_id: str):
    """获取单个用例。"""
    from app.cases.repository import get_case
    case = await asyncio.to_thread(get_case, case_id)
    if not case:
        return JSONResponse({"error": f"case {case_id} 不存在"}, status_code=404)
    return JSONResponse(case)


@router.put("/api/cases/{case_id}")
async def api_update_case(case_id: str, req: Request):
    """更新用例。"""
    from app.cases.repository import update_case
    body = await req.json()
    updates = {k: v for k, v in body.items() if v is not None}
    if "test_type" in updates:
        from app.cases.repository import get_case
        existing = await asyncio.to_thread(get_case, case_id)
        if existing:
            meta = existing.get("metadata", {}) or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            meta["test_type"] = updates.pop("test_type")
            updates["metadata"] = json.dumps(meta, ensure_ascii=False)
    if "structured_cases" in updates and not isinstance(updates["structured_cases"], list):
        del updates["structured_cases"]
    try:
        case = update_case(case_id, **updates)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    if not case:
        return JSONResponse({"error": f"case {case_id} 不存在"}, status_code=404)
    return JSONResponse(case)


@router.delete("/api/cases/{case_id}")
async def api_delete_case(case_id: str):
    """删除用例（软删除到回收站）。"""
    from app.cases.management import soft_delete_case
    deleted = await asyncio.to_thread(soft_delete_case, case_id)
    if not deleted:
        return JSONResponse({"error": f"case {case_id} 不存在"}, status_code=404)
    return ok({"deleted": True, "trashed": True})


# ════════════════════════════════════════════════════════════
# 用例高级管理 API
# ════════════════════════════════════════════════════════════

@router.get("/api/cases/{case_id}/full")
async def api_get_case_full(case_id: str):
    """获取用例完整信息（含关联/依赖/评审/版本/变更/需求）。"""
    from app.cases.management import get_case_full_info
    case = await asyncio.to_thread(get_case_full_info, case_id)
    if not case:
        return JSONResponse({"error": f"case {case_id} 不存在"}, status_code=404)
    return JSONResponse(case)


@router.post("/api/cases/{case_id}/relations")
async def api_add_case_relation(case_id: str, req: Request):
    """添加用例关联。"""
    from app.cases.management import add_case_relation
    body = await req.json()
    try:
        rel = await asyncio.to_thread(
            add_case_relation,
            case_id,
            body.get("related_case_id", ""),
            body.get("relation_type", "related"),
        )
        return JSONResponse(rel)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.delete("/api/cases/{case_id}/relations/{related_id}")
async def api_remove_case_relation(case_id: str, related_id: str):
    """移除用例关联。"""
    from app.cases.management import remove_case_relation
    removed = await asyncio.to_thread(remove_case_relation, case_id, related_id)
    if not removed:
        return JSONResponse({"error": "关联不存在"}, status_code=404)
    return ok({"removed": True})


@router.get("/api/cases/{case_id}/relations")
async def api_list_case_relations(case_id: str):
    """列出用例的所有关联。"""
    from app.cases.management import list_case_relations
    relations = await asyncio.to_thread(list_case_relations, case_id)
    return ok({"relations": relations})


@router.post("/api/cases/import")
async def api_import_cases(req: Request):
    """导入用例。"""
    from app.cases.management import import_cases_from_excel, import_cases_from_xmind
    body = await req.json()
    fmt = body.get("format", "excel")
    content = body.get("content", "")
    operator = body.get("operator", "")
    if fmt == "excel":
        result = await asyncio.to_thread(import_cases_from_excel, content, operator)
    elif fmt == "mindmap":
        result = await asyncio.to_thread(import_cases_from_xmind, content, operator)
    else:
        return JSONResponse({"error": "不支持的导入格式"}, status_code=400)
    return JSONResponse(result)


# 用例评审流程
@router.post("/api/cases/{case_id}/reviews/submit")
async def api_submit_case_review(case_id: str, req: Request):
    """提交用例评审。"""
    from app.cases.management import submit_for_review
    body = await req.json()
    try:
        result = await asyncio.to_thread(
            submit_for_review,
            case_id,
            reviewer=body.get("reviewer", ""),
            comment=body.get("comment", ""),
        )
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/cases/{case_id}/reviews/approve")
async def api_approve_case_review(case_id: str, req: Request):
    """通过用例评审。"""
    from app.cases.management import approve_review
    body = await req.json()
    result = await asyncio.to_thread(
        approve_review,
        case_id,
        reviewer=body.get("reviewer", ""),
        comment=body.get("comment", ""),
    )
    return JSONResponse(result)


@router.post("/api/cases/{case_id}/reviews/reject")
async def api_reject_case_review(case_id: str, req: Request):
    """驳回用例评审。"""
    from app.cases.management import reject_review
    body = await req.json()
    result = await asyncio.to_thread(
        reject_review,
        case_id,
        reviewer=body.get("reviewer", ""),
        comment=body.get("comment", ""),
    )
    return JSONResponse(result)


@router.get("/api/cases/{case_id}/reviews")
async def api_get_case_reviews(case_id: str):
    """获取用例评审记录。"""
    from app.cases.management import get_case_reviews
    reviews = await asyncio.to_thread(get_case_reviews, case_id)
    return ok({"reviews": reviews})


# 用例依赖关系
@router.post("/api/cases/{case_id}/dependencies")
async def api_add_case_dependency(case_id: str, req: Request):
    """添加用例依赖。"""
    from app.cases.management import add_case_dependency
    body = await req.json()
    try:
        dep = await asyncio.to_thread(
            add_case_dependency,
            case_id,
            body.get("depends_on", ""),
            body.get("dep_type", "before"),
            body.get("description", ""),
        )
        return JSONResponse(dep)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.delete("/api/cases/{case_id}/dependencies/{depends_on}")
async def api_remove_case_dependency(case_id: str, depends_on: str):
    """移除用例依赖。"""
    from app.cases.management import remove_case_dependency
    removed = await asyncio.to_thread(remove_case_dependency, case_id, depends_on)
    if not removed:
        return JSONResponse({"error": "依赖不存在"}, status_code=404)
    return ok({"removed": True})


@router.get("/api/cases/{case_id}/dependencies")
async def api_list_case_dependencies(case_id: str):
    """列出用例的所有依赖。"""
    from app.cases.management import list_case_dependencies
    deps = await asyncio.to_thread(list_case_dependencies, case_id)
    return ok({"dependencies": deps})


# 用例回收站
@router.post("/api/cases/{case_id}/trash")
async def api_soft_delete_case(case_id: str, req: Request):
    """软删除用例到回收站。"""
    from app.cases.management import soft_delete_case
    body = await req.json()
    deleted = await asyncio.to_thread(
        soft_delete_case,
        case_id,
        deleted_by=body.get("deleted_by", ""),
        reason=body.get("reason", ""),
    )
    if not deleted:
        return JSONResponse({"error": f"case {case_id} 不存在"}, status_code=404)
    return ok({"deleted": True, "trashed": True})


@router.post("/api/cases/{case_id}/restore")
async def api_restore_case(case_id: str, req: Request):
    """从回收站恢复用例。"""
    from app.cases.management import restore_case
    body = await req.json()
    restored = await asyncio.to_thread(restore_case, case_id, operator=body.get("operator", ""))
    if not restored:
        return JSONResponse({"error": f"case {case_id} 不在回收站中"}, status_code=404)
    return ok({"restored": True})


@router.delete("/api/cases/{case_id}/purge")
async def api_purge_case(case_id: str):
    """从回收站彻底删除用例。"""
    from app.cases.management import purge_case
    purged = await asyncio.to_thread(purge_case, case_id)
    if not purged:
        return JSONResponse({"error": f"case {case_id} 不存在"}, status_code=404)
    return ok({"purged": True})


# 用例版本管理
@router.get("/api/cases/{case_id}/versions")
async def api_list_case_versions(case_id: str):
    """列出用例的所有版本。"""
    from app.cases.management import list_case_versions
    versions = await asyncio.to_thread(list_case_versions, case_id)
    return ok({"versions": versions})


@router.get("/api/cases/{case_id}/versions/{version}")
async def api_get_case_version(case_id: str, version: int):
    """获取指定版本快照。"""
    from app.cases.management import get_case_version
    version_data = await asyncio.to_thread(get_case_version, case_id, version)
    if not version_data:
        return JSONResponse({"error": f"版本 {version} 不存在"}, status_code=404)
    return JSONResponse(version_data)


@router.post("/api/cases/{case_id}/rollback")
async def api_rollback_case(case_id: str, req: Request):
    """回滚用例到指定版本。"""
    from app.cases.management import rollback_case
    body = await req.json()
    version = int(body.get("version", 0))
    rolled_back = await asyncio.to_thread(
        rollback_case,
        case_id,
        version,
        operator=body.get("operator", ""),
    )
    if not rolled_back:
        return JSONResponse({"error": f"版本 {version} 不存在"}, status_code=404)
    return ok({"rolled_back": True, "version": version})


# 用例变更记录
@router.get("/api/cases/{case_id}/changes")
async def api_list_case_changes(case_id: str, limit: int = 50):
    """列出用例的变更记录。"""
    from app.cases.management import list_case_changes
    changes = await asyncio.to_thread(list_case_changes, case_id, limit=limit)
    return ok({"changes": changes, "total": len(changes)})


# 用例关联需求
@router.post("/api/cases/{case_id}/requirements")
async def api_add_case_requirement(case_id: str, req: Request):
    """关联需求到用例。"""
    from app.cases.management import add_case_requirement
    body = await req.json()
    try:
        result = await asyncio.to_thread(
            add_case_requirement,
            case_id,
            requirement_id=body.get("requirement_id", ""),
            requirement_type=body.get("requirement_type", "jira"),
            requirement_title=body.get("requirement_title", ""),
            requirement_url=body.get("requirement_url", ""),
        )
        return JSONResponse(result)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.delete("/api/cases/{case_id}/requirements/{requirement_id}")
async def api_remove_case_requirement(case_id: str, requirement_id: str):
    """移除需求关联。"""
    from app.cases.management import remove_case_requirement
    removed = await asyncio.to_thread(remove_case_requirement, case_id, requirement_id)
    if not removed:
        return JSONResponse({"error": "需求关联不存在"}, status_code=404)
    return ok({"removed": True})


@router.get("/api/cases/{case_id}/requirements")
async def api_list_case_requirements(case_id: str):
    """列出用例关联的所有需求。"""
    from app.cases.management import list_case_requirements
    requirements = await asyncio.to_thread(list_case_requirements, case_id)
    return ok({"requirements": requirements})
