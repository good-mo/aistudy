# app/core/router.py
"""
统一路由契约层
==============
Phase 2 重构目标：建立表驱动的路由注册机制，让路径差异由数据驱动而非代码驱动。

通过 api_route 装饰器注册路由，统一管理路由注册、鉴权、操作ID生成。
不再需要为每个"前端路径 vs 后端路径"差异单独写补丁文件。
"""
import re
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import APIRouter


# ── 路由注册表 ──────────────────────────────────────────────
# 存储所有通过 api_route 注册的路由元信息
_route_registry: Dict[str, Dict[str, Any]] = {}
_registered_paths: Set[str] = set()


def api_route(path: str, methods: List[str], **kwargs):
    """统一路由注册装饰器。

    用法:
        @api_route("/api/cases", methods=["GET"])
        async def list_cases():
            return {"ok": True}

        # 同时支持前端路径和后端路径，映射到同一个处理函数
        @api_route("/functional/case/page", methods=["POST"])
        @api_route("/api/cases/page", methods=["POST"])
        async def case_page(request: Request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        key = f"{','.join(sorted(methods))} {path}"
        if key in _registered_paths:
            raise ValueError(f"路由重复注册: {key}")
        _registered_paths.add(key)

        if path not in _route_registry:
            _route_registry[path] = {
                "methods": methods,
                "handler": func,
                "kwargs": kwargs,
                "aliases": [],
            }
        else:
            # 相同路径追加方法
            for m in methods:
                if m not in _route_registry[path]["methods"]:
                    _route_registry[path]["methods"].append(m)

        return func
    return decorator


def register_alias(alias_path: str, target_path: str, methods: Optional[List[str]] = None):
    """注册路径别名：alias_path 转发到 target_path 对应的 handler。

    用于前端路径与后端路径不一致的场景。
    """
    if target_path not in _route_registry:
        raise ValueError(f"目标路由未注册: {target_path}")

    target = _route_registry[target_path]
    alias_methods = methods or target["methods"]
    _route_registry[alias_path] = {
        "methods": alias_methods,
        "handler": target["handler"],
        "kwargs": dict(target["kwargs"]),
        "aliases": [target_path],
    }


def build_api_router(prefix: str = "") -> APIRouter:
    """根据路由注册表构建 FastAPI APIRouter。"""
    router = APIRouter()

    # 确保唯一 operation ID
    seen_ids: Set[str] = set()

    for path, meta in sorted(_route_registry.items()):
        for method in meta["methods"]:
            # 生成唯一 operation ID
            norm_path = path.replace("/", "_").replace("{", "").replace("}", "")
            op_id = f"{method.lower()}_{norm_path}"
            base_op_id = op_id
            suffix = 2
            while op_id in seen_ids:
                op_id = f"{base_op_id}_{suffix}"
                suffix += 1
            seen_ids.add(op_id)

            route_path = prefix + path
            # 注册路由
            route_meta = dict(meta["kwargs"])
            route_meta["operation_id"] = op_id

            handler = meta["handler"]
            # 检查是否已经是 APIRoute
            getattr(router, method.lower())(
                route_path,
                **route_meta,
            )(handler)

    return router


def route_count() -> int:
    """返回已注册的路由数量。"""
    return len(_route_registry)


def list_routes() -> List[Dict[str, Any]]:
    """返回所有已注册路由的摘要信息。"""
    return [
        {
            "path": path,
            "methods": meta["methods"],
            "handler": meta["handler"].__name__,
        }
        for path, meta in sorted(_route_registry.items())
    ]


# ── 路由冲突检测 ────────────────────────────────────────────

def check_duplicate_paths(extra_paths: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """检测路由冲突（相同 path + method 重复注册）。

    Args:
        extra_paths: 额外需要检查的路由列表，格式 [{path, methods}]

    Returns:
        冲突路由列表
    """
    all_paths: Dict[str, Set[str]] = {}
    conflicts: List[Dict[str, Any]] = []

    # 收集注册表中的路由
    for path, meta in _route_registry.items():
        all_paths.setdefault(path, set()).update(meta["methods"])

    # 收集额外路由
    if extra_paths:
        for r in extra_paths:
            p = r["path"]
            m = set(r["methods"])
            if p in all_paths:
                overlap = m & all_paths[p]
                if overlap:
                    conflicts.append({"path": p, "methods": sorted(overlap)})
            else:
                all_paths[p] = m

    return conflicts


__all__ = [
    "api_route",
    "register_alias",
    "build_api_router",
    "route_count",
    "list_routes",
    "check_duplicate_paths",
]
