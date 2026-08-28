# 后端重构指南

基于 Phase 0-6 重构计划的具体实施指南。

## 已完成的重构

### Phase 0：冻结增量 ✅
- `docs/api_mapping.md` — 前后端 API 路径映射文档
- `scripts/route_conflict_check.py` — 路由冲突检测脚本
- `app/adapters/__init__.py` — 冻结说明

### Phase 1：统一数据层 ✅
- `app/core/database.py` — 统一数据库连接管理
  - `Database.get_conn(db_name)` — 连接池复用
  - `Database.transaction(db_name)` — 事务管理
  - `get_conn/execute/query_one/query_all` — 便捷函数
- `app/core/config.py` — 统一数据库路径配置

### Phase 2：统一路由契约层 ✅
- `app/core/router.py` — 表驱动路由注册
  - `api_route(path, methods)` — 统一注册装饰器
  - `register_alias(alias, target)` — 路径别名
  - `build_api_router()` — 构建路由
  - `check_duplicate_paths()` — 冲突检测

### Phase 3：分层重构 ✅
- `app/models/` — Pydantic 模型层
  - `case.py` — 用例请求/响应模型
  - `defect.py` — 缺陷请求/响应模型
- `app/repositories/` — 数据访问层
  - `base.py` — BaseRepo 抽象基类
  - `case_repo.py` — 用例数据访问
  - `defect_repo.py` — 缺陷数据访问
- `app/services/` — 业务逻辑层
  - `case_service.py` — 用例服务
  - `defect_service.py` — 缺陷服务
- `app/routers/` — 路由层
  - `cases.py` — 用例路由
  - `defects.py` — 缺陷路由
  - `apitest.py` — 接口测试路由
  - `projects.py` — 项目管理路由
  - `environments.py` — 环境管理路由

### Phase 4：统一响应与异常 ✅
- `app/core/exceptions.py` — 全局异常处理
  - `AppError/NotFoundError/AuthError/ValidationError/ConflictError`
  - `register_exception_handlers(app)` — 注册处理器
- `app/core/response.py` — 统一响应格式
  - `ok(data, message, code)` / `fail(message, code, data)`
- `app/core/middleware.py` — 请求日志中间件
  - `RequestLoggingMiddleware` — 方法/路径/耗时/状态码

### Phase 5：前端 API 契约 ✅
- `frontend/src/api/contracts.ts` — 统一前端 API 契约
  - 所有前端 API 调用的单一数据源
  - 路径和 HTTP 方法与后端对齐

### Phase 6：数据库合并 ✅
- `scripts/merge_databases.py` — 数据库合并工具
  - `--dry-run` — 预览合并计划
  - `--execute` — 执行合并
  - `--backup` — 备份原数据库
- 11 个业务数据库 → 1 个 `tga.db`

## 待完成工作

### 主要迁移路径

1. **将 main.py 内联路由迁移到 routers/** 
   - main.py 中 180 个内联路由逐步迁移到 `app/routers/`
   - 每个业务域创建对应的 router 文件
   - 迁移完成后 main.py 仅保留应用装配

2. **将 adapters/ 补丁迁移到 routers/**
   - `adapters/router.py` (3967行/376路由) → 按业务域拆分
   - `adapters/missing_apis.py` (3574行/515路由) → 归入对应 router
   - `adapters/method_fixes.py` (846行/121路由) → 统一为方法规范
   - `adapters/path_param_fixes.py` (1303行/226路由) → 用路径参数规范

3. **统一数据库连接**
   - 将各模块的 `_get_conn()` 替换为 `Database.get_conn()`
   - 13 个独立 `sqlite3.connect()` 收敛为 1 个 `Database` 类
   - 最终合并为单一 `tga.db`

4. **Pydantic 模型替换**
   - `request.json()` 391 处 → Pydantic 模型
   - 手写 `JSONResponse` 1005 处 → `ok()`/`fail()`

## 验收标准

| 指标 | 当前 | 目标 |
|------|------|------|
| 最大文件行数 | 3967 (adapters/router.py) | < 500 |
| 总路由数 | ~1661 | ~1500 |
| sqlite3.connect 调用点 | 13+ | 2 (Database类) |
| request.json() | 391 | 0 |
| JSONResponse 手写 | 1005 | 0 |
| 重复路由 | 71 | 0 |
| 测试通过 | 532 | 532 |
| adapters/ 目录 | 4文件/9691行 | 移除 |
