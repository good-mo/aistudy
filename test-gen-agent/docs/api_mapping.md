# API 映射表

前后端 API 路径映射关系总表。用于追踪前端调用路径与后端实现路径的对应关系，
避免重复补丁和路径不匹配问题。

## 生成方式

此文档由 `scripts/route_conflict_check.py` 自动生成和比对。
运行方式：
```bash
python3 scripts/route_conflict_check.py --generate   # 生成映射表
python3 scripts/route_conflict_check.py --check      # 检查冲突
```

## 映射约定

前端（MeterSphere v3.x 风格）路径 → 后端（FastAPI 业务路径）路径映射规则：

| 前端路径前缀 | 后端路径前缀 | 说明 |
|---|---|---|
| `/functional/case/*` | `/api/cases/*` | 功能用例管理 |
| `/bug/*` | `/api/defects/*` | 缺陷管理 |
| `/api/definition/*` | `/api/apitest/definitions/*` | 接口定义 |
| `/api/case/*` | `/api/apitest/cases/*` | 接口用例 |
| `/api/scenario/*` | `/api/apitest/scenarios/*` | 场景编排 |
| `/api/mock/*` | `/api/apitest/mocks/*` | Mock 服务 |
| `/api/environment/*` | `/api/environments/*` | 环境管理 |
| `/test-plan/*` | `/test-plan/*` | 测试计划 |
| `/api/report/*` | `/api/reports/*` | 报告中心 |
| `/api/ai/*` | `/api/ai/*` | AI 功能 |

## 路由注册分布

### 当前路由注册情况（重构前）

| 文件 | 路由数 | 说明 |
|---|---|---|
| `app/main.py` | 180 | 内联路由，包含大量业务逻辑 |
| `app/adapters/router.py` | 376 | MeterSphere 前端适配 |
| `app/adapters/missing_apis.py` | 515 | 缺失 API 补齐 |
| `app/adapters/method_fixes.py` | 121 | HTTP 方法修复 |
| `app/adapters/path_param_fixes.py` | 226 | 路径参数修复 |
| `app/auth/router.py` | 68 | 认证模块 |
| `app/test_plan/router.py` | 153 | 测试计划 |
| `app/file_mgmt/router.py` | 22 | 文件管理 |

### 目标路由注册情况（重构后）

| 文件 | 路由数 | 说明 |
|---|---|---|
| `app/main.py` | < 50 | 仅应用装配和挂载 |
| `app/routers/*` | 各 < 100 | 按业务域拆分 |
| `app/core/router.py` | 统一注册 | 表驱动路由注册 |

## 路由冲突检测规则

1. **相同 path + method**：视为冲突，禁止重复注册
2. **相同 path + 不同 method**：允许，但需确认方法语义一致
3. **路径参数冲突**：如 `/api/cases/{id}` 与 `/api/cases/import` 应确保顺序注册

## 迁移清单

- [ ] 阶段0: 冻结 adapters/ 新增路由，新路由进 routers/
- [ ] 阶段1: 统一数据库连接管理
- [ ] 阶段2: 引入统一路由契约层
- [ ] 阶段3: 拆分 main.py 和 adapters 层
- [ ] 阶段4: 统一响应格式与异常处理
- [ ] 阶段5: 前端 API 契约同步
- [ ] 阶段6: 数据库合并
