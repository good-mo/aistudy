# app/__init__.py
"""
Test Generation Agent Toolkit

分层架构（Phase 3 重构后目标结构）：
  app/core/          # 核心基础设施（数据库/异常/响应/路由/中间件）
  app/models/        # Pydantic 请求/响应模型
  app/repositories/  # 数据访问层（统一数据库操作）
  app/services/      # 业务逻辑层（复用/可测试）
  app/routers/       # 路由层（按业务域拆分）
  app/adapters/      # 前端适配层（Phase 0 冻结，待迁移到 routers/）
"""
