# app/routers/defects.py
"""缺陷管理路由（Phase 3 重构：从 main.py 拆分）。"""
from typing import Optional
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

router = APIRouter(tags=["defects"])


@router.get("/api/defects")
async def api_list_defects(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """列出缺陷。"""
    from app.defects.tracker import list_defects, get_stats
    defects = list_defects(status=status, severity=severity, limit=limit, offset=offset)
    stats = get_stats()
    return ok({"defects": defects, "stats": stats, "total": len(defects)})


@router.post("/api/defects")
async def api_create_defect(req: Request):
    """创建缺陷。"""
    from app.defects.tracker import create_defect
    body = await req.json()
    defect = create_defect(
        title=body.get("title", ""),
        description=body.get("description", ""),
        severity=body.get("severity", "major"),
        file_path=body.get("file_path", ""),
        test_case_id=body.get("test_case_id", ""),
        error_snippet=body.get("error_snippet", ""),
        assignee=body.get("assignee", ""),
    )
    return JSONResponse(defect)


@router.get("/api/defects/trash")
async def api_list_defect_trash(limit: int = 100, offset: int = 0):
    """列出回收站中的缺陷。"""
    from app.defects.tracker import list_trash_defects, count_trash_defects
    items = list_trash_defects(limit=limit, offset=offset)
    return ok({"items": items, "total": count_trash_defects()})


@router.get("/api/defects/{defect_id}")
async def api_get_defect(defect_id: str):
    """获取单个缺陷。"""
    from app.defects.tracker import get_defect
    defect = get_defect(defect_id)
    if not defect:
        return JSONResponse({"error": f"defect {defect_id} 不存在"}, status_code=404)
    return JSONResponse(defect)


@router.put("/api/defects/{defect_id}")
async def api_update_defect(defect_id: str, req: Request):
    """更新缺陷。"""
    from app.defects.tracker import update_defect
    body = await req.json()
    updates = {k: v for k, v in body.items() if v is not None}
    try:
        defect = update_defect(defect_id, **updates)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    if not defect:
        return JSONResponse({"error": f"defect {defect_id} 不存在"}, status_code=404)
    return JSONResponse(defect)


@router.delete("/api/defects/{defect_id}")
async def api_delete_defect(defect_id: str):
    """删除缺陷（彻底删除）。"""
    from app.defects.tracker import delete_defect
    deleted = delete_defect(defect_id, permanent=True)
    if not deleted:
        return JSONResponse({"error": f"defect {defect_id} 不存在"}, status_code=404)
    return ok({"deleted": True})


@router.post("/api/defects/{defect_id}/trash")
async def api_trash_defect(defect_id: str):
    """将缺陷软删除，移入回收站。"""
    from app.defects.tracker import soft_delete_defect
    deleted = soft_delete_defect(defect_id)
    if not deleted:
        return JSONResponse({"error": f"defect {defect_id} 不存在"}, status_code=404)
    return ok({"deleted": True, "defect_id": defect_id})


@router.post("/api/defects/{defect_id}/restore")
async def api_restore_defect(defect_id: str):
    """从回收站恢复缺陷。"""
    from app.defects.tracker import restore_defect
    restored = restore_defect(defect_id)
    if not restored:
        return JSONResponse({"error": f"defect {defect_id} 不在回收站或不存在"}, status_code=404)
    return ok({"restored": True, "defect_id": defect_id})


@router.delete("/api/defects/trash/{defect_id}")
async def api_purge_defect(defect_id: str):
    """从回收站彻底删除缺陷。"""
    from app.defects.tracker import purge_defect
    purged = purge_defect(defect_id)
    if not purged:
        return JSONResponse({"error": f"defect {defect_id} 不存在"}, status_code=404)
    return ok({"purged": True, "defect_id": defect_id})


@router.post("/api/defects/trash/recover")
async def api_batch_restore_defects(req: Request):
    """批量从回收站恢复缺陷。"""
    from app.defects.tracker import restore_defect
    body = await req.json()
    ids = body.get("ids", [])
    restored = 0
    for did in ids:
        if restore_defect(did):
            restored += 1
    return ok({"restored": restored})


@router.post("/api/defects/trash/batch-delete")
async def api_batch_purge_defects(req: Request):
    """批量从回收站彻底删除缺陷。"""
    from app.defects.tracker import purge_defect
    body = await req.json()
    ids = body.get("ids", [])
    purged = 0
    for did in ids:
        if purge_defect(did):
            purged += 1
    return ok({"purged": purged})
