# app/routers/datafactory.py
"""数据工厂路由（Phase 3 重构：从 main.py 拆分）。"""
import asyncio
from typing import Optional, List

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.core.response import ok, fail

from pydantic import BaseModel

router = APIRouter(tags=["data-factory"])


class DataTemplateRequest(BaseModel):
    name: str
    description: str = ""
    category: str = ""
    schema_def: Optional[dict] = None
    deps: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class DataTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    schema_def: Optional[dict] = None
    deps: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class DataGenerateRequest(BaseModel):
    template_id: str = ""
    batch_size: int = 1
    env_key: str = ""


@router.get("/api/data/templates")
async def api_list_data_templates(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """列出数据模板。"""
    from app.datafactory.repository import list_templates
    templates = list_templates(category=category, search=search, limit=limit, offset=offset)
    return ok({"templates": templates, "total": len(templates)})


@router.post("/api/data/templates")
async def api_create_data_template(req: DataTemplateRequest):
    """创建数据模板。"""
    from app.datafactory.repository import create_template
    template = create_template(
        name=req.name,
        description=req.description,
        category=req.category,
        schema_def=req.schema_def,
        deps=req.deps,
        tags=req.tags,
    )
    return JSONResponse(template)


@router.get("/api/data/templates/{template_id}")
async def api_get_data_template(template_id: str):
    """获取数据模板详情。"""
    from app.datafactory.repository import get_template
    template = get_template(template_id)
    if not template:
        return JSONResponse({"error": f"模板 {template_id} 不存在"}, status_code=404)
    return JSONResponse(template)


@router.put("/api/data/templates/{template_id}")
async def api_update_data_template(template_id: str, req: DataTemplateUpdate):
    """更新数据模板。"""
    from app.datafactory.repository import update_template
    template = update_template(template_id, req.model_dump(exclude_none=True))
    if not template:
        return JSONResponse({"error": f"模板 {template_id} 不存在"}, status_code=404)
    return JSONResponse(template)


@router.delete("/api/data/templates/{template_id}")
async def api_delete_data_template(template_id: str):
    """删除数据模板。"""
    from app.datafactory.repository import delete_template
    deleted = delete_template(template_id)
    if not deleted:
        return JSONResponse({"error": f"模板 {template_id} 不存在"}, status_code=404)
    return ok({"deleted": True, "template_id": template_id})


@router.post("/api/data/generate")
async def api_generate_data(req: DataGenerateRequest):
    """按模板批量生成数据。"""
    from app.datafactory.repository import generate_data_batch
    result = generate_data_batch(
        template_id=req.template_id,
        batch_size=req.batch_size,
        env_key=req.env_key,
    )
    return JSONResponse(result)


@router.get("/api/data/batches")
async def api_list_data_batches(limit: int = 50):
    """列出生成批次。"""
    from app.datafactory.repository import list_batches
    batches = list_batches(limit=limit)
    return ok({"batches": batches, "total": len(batches)})


@router.post("/api/data/cleanup/batch/{batch_id}")
async def api_cleanup_batch(batch_id: str):
    """清理指定批次的数据。"""
    from app.datafactory.repository import cleanup_batch
    result = cleanup_batch(batch_id)
    return JSONResponse(result)


@router.post("/api/data/cleanup/template/{template_id}")
async def api_cleanup_template(template_id: str):
    """清理指定模板的数据。"""
    from app.datafactory.repository import cleanup_by_template
    result = cleanup_by_template(template_id)
    return JSONResponse(result)


@router.post("/api/data/cleanup/env/{env_key}")
async def api_cleanup_env(env_key: str):
    """清理指定环境的数据。"""
    from app.datafactory.repository import cleanup_by_env
    result = cleanup_by_env(env_key)
    return JSONResponse(result)


@router.get("/api/data/stats")
async def api_data_stats():
    """数据工厂统计。"""
    from app.datafactory.repository import get_stats
    return JSONResponse(await asyncio.to_thread(get_stats))
