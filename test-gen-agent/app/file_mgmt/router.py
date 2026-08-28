# app/file_mgmt/router.py
"""文件管理 API 路由：上传、下载、预览、附件管理。"""

import os
import shutil
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(tags=["file-management"])

# 上传文件存储目录
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── 项目文件管理 ───────────────────────────────────────
@router.post("/project/file/upload")
async def project_file_upload(request: Request):
    """上传项目文件。"""
    # 支持 multipart/form-data 和 JSON 两种方式
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if file and hasattr(file, "filename"):
            filename = file.filename
            content = await file.read()
            file_id = str(uuid.uuid4())
            file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
            with open(file_path, "wb") as f:
                f.write(content)
            return JSONResponse({"code": 200, "message": "success", "data": {
                "id": file_id,
                "name": filename,
                "path": file_path,
                "size": len(content),
                "uploadTime": time.time(),
            }})
        return JSONResponse({"code": 400, "message": "未找到文件", "data": None}, status_code=400)
    else:
        body = await request.json()
        return JSONResponse({"code": 200, "message": "success", "data": {
            "id": str(uuid.uuid4()),
            "name": body.get("name", ""),
            "size": 0,
        }})


@router.post("/project/file/page")
async def project_file_page(request: Request):
    """分页查询项目文件列表。"""
    body = await request.json()
    keyword = body.get("keyword", "")
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    # 列出上传目录中的文件
    files = []
    try:
        for fname in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                # 从文件名解析原始名称（去掉 UUID 前缀）
                orig_name = fname.split("_", 1)[1] if "_" in fname else fname
                files.append({
                    "id": fname.split("_", 1)[0] if "_" in fname else fname,
                    "name": orig_name,
                    "path": fpath,
                    "size": stat.st_size,
                    "uploadTime": stat.st_mtime,
                    "type": _get_file_type(orig_name),
                })
    except Exception:
        pass

    # 关键词过滤
    if keyword:
        files = [f for f in files if keyword.lower() in f["name"].lower()]

    # 分页
    start = (current - 1) * page_size
    page_items = files[start:start + page_size]

    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": page_items,
        "total": len(files),
        "pageSize": page_size,
        "current": current,
    }})


@router.post("/project/file/delete")
async def project_file_delete(request: Request):
    """删除项目文件。"""
    body = await request.json()
    file_id = body.get("id", "")
    # 查找并删除
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            os.remove(os.path.join(UPLOAD_DIR, fname))
            break
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/project/file/download/{file_id}")
async def project_file_download(file_id: str):
    """下载项目文件。"""
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            fpath = os.path.join(UPLOAD_DIR, fname)
            orig_name = fname.split("_", 1)[1] if "_" in fname else fname
            return FileResponse(fpath, filename=orig_name)
    return JSONResponse({"code": 404, "message": "文件不存在", "data": None}, status_code=404)


@router.get("/project/file/get/{file_id}")
async def project_file_get(file_id: str):
    """获取文件详情。"""
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            fpath = os.path.join(UPLOAD_DIR, fname)
            stat = os.stat(fpath)
            orig_name = fname.split("_", 1)[1] if "_" in fname else fname
            return JSONResponse({"code": 200, "message": "success", "data": {
                "id": file_id,
                "name": orig_name,
                "path": fpath,
                "size": stat.st_size,
                "type": _get_file_type(orig_name),
            }})
    return JSONResponse({"code": 404, "message": "文件不存在", "data": None}, status_code=404)


@router.post("/project/file/type")
async def project_file_type():
    """获取文件类型集合。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        "FILE", "IMAGE", "JAR", "XLS", "XLSX", "CSV",
        "DOC", "DOCX", "PDF", "TXT", "MD", "JSON", "YAML",
    ]})


@router.get("/project/file-module/tree")
async def project_file_module_tree():
    """获取文件模块树。"""
    return JSONResponse({"code": 200, "message": "success", "data": [
        {"id": "root", "name": "全部文件", "type": "MODULE", "children": []}
    ]})


@router.post("/project/file-module/add")
async def project_file_module_add(request: Request):
    """添加文件模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.post("/project/file-module/delete")
async def project_file_module_delete(request: Request):
    """删除文件模块。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 文件预览 ─────────────────────────────────────────
@router.get("/file/preview/original")
async def file_preview_original():
    """预览原图。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/file/preview/compressed")
async def file_preview_compressed():
    """预览压缩图。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


# ── 附件管理 ─────────────────────────────────────────
@router.post("/attachment/upload")
async def attachment_upload(request: Request):
    """上传附件。"""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if file and hasattr(file, "filename"):
            filename = file.filename
            content = await file.read()
            file_id = str(uuid.uuid4())
            file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
            with open(file_path, "wb") as f:
                f.write(content)
            return JSONResponse({"code": 200, "message": "success", "data": {
                "id": file_id,
                "name": filename,
                "size": len(content),
                "uploadTime": time.time(),
            }})
    return JSONResponse({"code": 400, "message": "未找到文件", "data": None}, status_code=400)


@router.post("/attachment/page")
async def attachment_page(request: Request):
    """附件分页列表。"""
    body = await request.json()
    page_size = body.get("pageSize", 10)
    current = body.get("current", 1)

    files = []
    try:
        for fname in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                orig_name = fname.split("_", 1)[1] if "_" in fname else fname
                files.append({
                    "id": fname.split("_", 1)[0] if "_" in fname else fname,
                    "name": orig_name,
                    "path": fpath,
                    "size": stat.st_size,
                    "uploadTime": stat.st_mtime,
                })
    except Exception:
        pass

    start = (current - 1) * page_size
    return JSONResponse({"code": 200, "message": "success", "data": {
        "list": files[start:start + page_size],
        "total": len(files),
    }})


@router.post("/attachment/delete")
async def attachment_delete(request: Request):
    """删除附件。"""
    body = await request.json()
    file_id = body.get("id", "")
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            os.remove(os.path.join(UPLOAD_DIR, fname))
            break
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/attachment/download/{file_id}")
async def attachment_download(file_id: str):
    """下载附件。"""
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            fpath = os.path.join(UPLOAD_DIR, fname)
            orig_name = fname.split("_", 1)[1] if "_" in fname else fname
            return FileResponse(fpath, filename=orig_name)
    return JSONResponse({"code": 404, "message": "文件不存在", "data": None}, status_code=404)


@router.get("/attachment/list/{resource_id}")
async def attachment_list(resource_id: str):
    """获取资源附件列表。"""
    files = []
    try:
        for fname in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fpath):
                stat = os.stat(fpath)
                orig_name = fname.split("_", 1)[1] if "_" in fname else fname
                files.append({
                    "id": fname.split("_", 1)[0] if "_" in fname else fname,
                    "name": orig_name,
                    "size": stat.st_size,
                })
    except Exception:
        pass
    return JSONResponse({"code": 200, "message": "success", "data": files})


# ── 缺陷附件 ─────────────────────────────────────────
@router.post("/bug/attachment/upload")
async def bug_attachment_upload(request: Request):
    """上传缺陷附件。"""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if file and hasattr(file, "filename"):
            filename = file.filename
            content = await file.read()
            file_id = str(uuid.uuid4())
            file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
            with open(file_path, "wb") as f:
                f.write(content)
            return JSONResponse({"code": 200, "message": "success", "data": {
                "id": file_id,
                "name": filename,
                "size": len(content),
            }})
    return JSONResponse({"code": 400, "message": "未找到文件", "data": None}, status_code=400)


@router.get("/bug/attachment/list/{bug_id}")
async def bug_attachment_list(bug_id: str):
    """获取缺陷附件列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


@router.post("/bug/attachment/delete")
async def bug_attachment_delete(request: Request):
    """删除缺陷附件。"""
    return JSONResponse({"code": 200, "message": "success", "data": None})


@router.get("/bug/attachment/download/{file_id}")
async def bug_attachment_download(file_id: str):
    """下载缺陷附件。"""
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(file_id):
            fpath = os.path.join(UPLOAD_DIR, fname)
            orig_name = fname.split("_", 1)[1] if "_" in fname else fname
            return FileResponse(fpath, filename=orig_name)
    return JSONResponse({"code": 404, "message": "文件不存在", "data": None}, status_code=404)


@router.post("/bug/attachment/upload/md/file")
async def bug_attachment_upload_md(request: Request):
    """富文本编辑器上传图片。"""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if file and hasattr(file, "filename"):
            filename = file.filename
            content = await file.read()
            file_id = str(uuid.uuid4())
            file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")
            with open(file_path, "wb") as f:
                f.write(content)
            return JSONResponse({"code": 200, "message": "success", "data": {
                "id": file_id,
                "name": filename,
                "url": f"/attachment/download/{file_id}",
            }})
    return JSONResponse({"code": 400, "message": "未找到文件", "data": None}, status_code=400)


# ── 文件历史版本 ─────────────────────────────────────
@router.get("/project/file/file-version/{file_id}")
async def project_file_version(file_id: str):
    """获取文件历史版本列表。"""
    return JSONResponse({"code": 200, "message": "success", "data": []})


def _get_file_type(filename: str) -> str:
    """根据文件名判断文件类型。"""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    img_exts = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg"}
    if ext in img_exts:
        return "IMAGE"
    doc_exts = {"doc", "docx", "pdf", "txt", "md"}
    if ext in doc_exts:
        return "DOC"
    if ext in {"xls", "xlsx", "csv"}:
        return "XLS"
    if ext in {"jar"}:
        return "JAR"
    if ext in {"json", "yaml", "yml"}:
        return "CONFIG"
    return "FILE"
