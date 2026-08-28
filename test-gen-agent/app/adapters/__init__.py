# app/adapters/__init__.py
"""MeterSphere 前端 API 适配层。

⚠️ 阶段0 冻结说明（Phase 0）：
  本目录已冻结新增路由。新路由请放到 app/routers/ 目录下。
  现有适配器将在 Phase 3 迁移完成后移除。

  目标架构：前端路径与后端路径通过 app/routers/ 统一管理。
"""
from app.adapters.router import router as adapter_router

__all__ = ["adapter_router"]
