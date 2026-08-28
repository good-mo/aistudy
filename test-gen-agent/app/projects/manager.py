# app/projects/manager.py
"""
项目级扫描与多文件执行模块
============================
支持递归扫描整个项目目录，提取所有 Python 源文件与函数签名，
并针对多文件批量生成测试用例。
"""
import ast
import os
import time
import uuid
import json
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)


def scan_project(
    project_path: str,
    extensions: tuple = (".py",),
    exclude_dirs: tuple = (".git", "__pycache__", "venv", ".venv", "node_modules", "output", "logs"),
    exclude_patterns: tuple = ("test_", "_test"),
) -> Dict[str, Any]:
    """
    递归扫描项目目录，返回所有待测源文件及函数签名。

    Args:
        project_path: 项目根目录
        extensions: 要扫描的文件扩展名
        exclude_dirs: 要排除的目录
        exclude_patterns: 文件名中包含这些模式的排除（如 test_）
    """
    if not os.path.isdir(project_path):
        raise FileNotFoundError(f"项目目录不存在: {project_path}")

    source_files = []
    total_functions = 0

    for root, dirs, files in os.walk(project_path):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for fname in files:
            if not fname.endswith(extensions):
                continue
            if any(fname.startswith(p) or fname.endswith(p) for p in exclude_patterns):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    source = f.read()
                signatures = _extract_signatures(source)
                total_functions += len(signatures)
                source_files.append({
                    "path": fpath,
                    "relative_path": os.path.relpath(fpath, project_path),
                    "size": os.path.getsize(fpath),
                    "signatures": signatures,
                })
            except Exception as e:
                logger.warning("扫描文件失败 [path=%s, err=%s]", fpath, e)

    return {
        "project_path": project_path,
        "total_files": len(source_files),
        "total_functions": total_functions,
        "files": source_files,
    }


def _extract_signatures(source_code: str) -> List[Dict[str, Any]]:
    """从源码中提取函数签名。"""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    signatures = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            params = [
                {
                    "name": a.arg,
                    "annotation": ast.unparse(a.annotation) if a.annotation else None,
                }
                for a in node.args.args
            ]
            signatures.append({
                "name": node.name,
                "params": params,
                "returns": ast.unparse(node.returns) if node.returns else None,
                "docstring": ast.get_docstring(node) or "",
                "lineno": node.lineno,
            })
    return signatures


def collect_sources_from_paths(paths: List[str]) -> List[Dict[str, Any]]:
    """
    从指定文件路径列表读取源代码。

    Args:
        paths: 文件路径列表

    Returns:
        每个文件的内容 dict
    """
    result = []
    for path in paths:
        if not os.path.isfile(path):
            logger.warning("文件不存在 [path=%s]", path)
            continue
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        result.append({
            "file_path": os.path.basename(path),
            "source_code": source,
            "signatures": _extract_signatures(source),
        })
    return result
