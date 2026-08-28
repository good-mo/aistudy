# 企业级接口测试指南（API Testing Guide）

> 适用对象：Test Generation Agent Toolkit 全量 REST API
> 标准依据：ISO/IEC/IEEE 29119、RESTful API 测试最佳实践、OWASP API Security Top 10

## 一、接口测试目标与层次

企业级接口测试不只是"验证状态码是否正确"，而是从 **契约 → 功能 → 边界 → 异常 → 安全 → 幂等 → 并发 → 兼容** 八个层次做系统性验证，确保接口在真实生产环境下稳定、安全、可扩展。

```
┌─────────────────────────────────────────────┐
│  第 8 层 兼容性（协议/内容协商/版本）        │
│  第 7 层 并发与竞态（多请求/资源争用）       │
│  第 6 层 幂等与重放（重复提交防护）          │
│  第 5 层 安全（认证/鉴权/注入/敏感数据）     │
│  第 4 层 异常（4xx/5xx/超时/依赖故障）       │
│  第 3 层 边界（空值/极值/非法类型/超长）     │
│  第 2 层 功能（CRUD/业务流/查询过滤）        │
│  第 1 层 契约（Schema/字段/状态码/响应结构） │
└─────────────────────────────────────────────┘
```

## 二、API 全量清单（27 个端点）

### 2.1 用例库（7 个）

| # | 方法 | 路径 | 说明 | 风险等级 |
|---|------|------|------|---------|
| 1 | GET | `/api/cases` | 列表 + 过滤 | P0 |
| 2 | GET | `/api/cases/stats` | 统计 | P1 |
| 3 | POST | `/api/cases` | 创建 | P0 |
| 4 | GET | `/api/cases/{id}` | 详情 | P0 |
| 5 | PUT | `/api/cases/{id}` | 更新 | P0 |
| 6 | DELETE | `/api/cases/{id}` | 删除 | P1 |
| 7 | GET | `/` | 控制台首页 | P2 |

### 2.2 缺陷跟踪（5 个）

| # | 方法 | 路径 | 说明 | 风险等级 |
|---|------|------|------|---------|
| 8 | GET | `/api/defects` | 列表 + 过滤 | P1 |
| 9 | POST | `/api/defects` | 创建 | P0 |
| 10 | GET | `/api/defects/{id}` | 详情 | P1 |
| 11 | PUT | `/api/defects/{id}` | 更新 | P0 |
| 12 | DELETE | `/api/defects/{id}` | 删除 | P1 |

### 2.3 项目扫描（2 个）

| # | 方法 | 路径 | 说明 | 风险等级 |
|---|------|------|------|---------|
| 13 | POST | `/api/projects/scan` | 递归扫描 | P0 |
| 14 | POST | `/api/projects/generate` | 项目级生成 | P1 |

### 2.4 报告中心（3 个）

| # | 方法 | 路径 | 说明 | 风险等级 |
|---|------|------|------|---------|
| 15 | POST | `/api/reports/generate` | 生成报告 | P1 |
| 16 | GET | `/api/reports/list` | 报告列表 | P2 |
| 17 | GET | `/api/reports/download/{name}` | 下载报告 | P1 |

### 2.5 测试生成与任务队列（5 个）

| # | 方法 | 路径 | 说明 | 风险等级 |
|---|------|------|------|---------|
| 18 | POST | `/api/generate` | 单次生成（同步/异步） | P0 |
| 19 | POST | `/api/tasks` | 提交异步任务 | P1 |
| 20 | GET | `/api/tasks/{id}` | 查询任务 | P0 |
| 21 | GET | `/api/tasks` | 任务列表 | P2 |
| 22 | WS | `/ws/generate` | WebSocket 流式生成 | P1 |

### 2.6 系统（5 个）

| # | 方法 | 路径 | 说明 | 风险等级 |
|---|------|------|------|---------|
| 23 | GET | `/health` | 健康检查 | P0 |
| 24 | POST | `/api/generate?async_mode=true` | 异步生成 | P0 |
| 25 | GET | `/openapi.json` | Swagger 契约 | P1 |
| 26 | GET | `/docs` | Swagger UI | P2 |
| 27 | GET | `/redoc` | ReDoc | P2 |

## 三、各层测试设计规范

### 3.1 契约层（Contract）

- **响应结构校验**：所有 `GET` 列表返回 `{...}` 容器，单个资源返回资源对象；断言关键字段存在且类型正确。
- **状态码契约**：`200` 成功、`400` 业务校验失败、`404` 资源不存在、`422` 请求体校验失败（FastAPI 默认）。
- **Content-Type**：`application/json` 一致；`/` 与 `/docs` 为 `text/html`。
- **Schema 一致性**：通过 `/openapi.json` 校验 `paths` 中注册的端点与实现一致（防止路由漂移）。

### 3.2 功能层（Functional）

- 每个资源完整走一遍 **CRUD 闭环**：创建 → 查询 → 更新 → 删除 → 再次查询（404）。
- 查询过滤链：`status` / `priority` / `tag` / `search` 单条件与组合条件。
- 业务关联验证：缺陷关联 `test_case_id`、报告从用例库 `last_result` 汇总。

### 3.3 边界层（Boundary）

- 空值：空 `title`、空列表 `tags`、空 `source_code`。
- 极值：`limit` 负数/0/超上限、`offset` 巨大值。
- 非法类型：非 JSON、字段类型错误（数字传字符串）、未知枚举值。
- 超长字段：超长 `title` / `description` / 超大 body。
- 非法 ID：不存在的 UUID、路径穿越式 ID（`../`）、超长 ID。

### 3.4 异常层（Exception）

- **4xx**：404 不存在资源、400 非法枚举、404 扫描不存在路径。
- **5xx**：扫描不可读目录、报告无数据时 404。
- **超时**：LLM 调用失败被捕获为任务失败而非接口崩溃（`/api/tasks/{id}` 状态为 `failed`）。
- **依赖故障**：数据库无数据时的空列表行为、报告目录不存在时的空响应。

### 3.5 安全层（Security）— OWASP API Top 10

| 风险 | 本项目接口测试关注点 |
|------|---------------------|
| A1 对象级授权 | 访问不存在资源应 404，不泄露内部实现细节 |
| A2 认证失败 | 当前无鉴权，属已知缺口，测试应标记为"待加固" |
| A3 数据泄露 | 错误信息不包含完整 SQL/堆栈；响应不含 API Key |
| A6 批量分配 | POST/PUT 不应接受未定义字段（FastAPI 默认忽略，测试验证不影响业务） |
| A8 注入 | 查询参数 `search` 注入尝试（`' OR '1'='1`）应作为普通文本处理 |
| A10 路径遍历 | `download/{filename}` 传 `../`、`/etc/passwd` 应被拒绝/404 |
| 限流 | 无内置 Rate Limit（已知缺口，压测时观察） |

### 3.6 幂等层（Idempotency）

- **GET** 天然幂等：相同请求返回一致结果。
- **DELETE** 幂等性缺口：重复删除已删除资源返回 404（当前行为），企业级应返回 200 或明确 410。
- **POST** 非幂等（每次创建新资源）：测试应验证重复提交产生不同 `id`，不相互覆盖。
- **PUT** 部分更新应幂等：相同更新内容多次执行结果一致。

### 3.7 并发层（Concurrency）

- 并发创建用例：资源 ID 不冲突、总数正确。
- 并发更新同一资源：最后写入生效，不产生脏数据/异常。
- 并发任务提交：任务队列不丢任务、状态机一致。
- 并发删除 + 查询：不产生 5xx 或悬挂引用。

### 3.8 兼容层（Compatibility）

- 内容协商：`Accept: application/json` 正常返回。
- URL 编码：中文/特殊字符文件名、查询参数 URL 编码。
- HTTP 版本：HTTP/1.1 正常。
- 协议：REST + WebSocket 双通道一致性（同一请求两者结果一致）。

## 四、接口测试用例组织（建议优先级）

| 优先级 | 覆盖内容 | 触发时机 |
|--------|---------|---------|
| **P0 冒烟** | 健康检查、核心 CRUD、任务队列基本流 | 每次部署/PR |
| **P1 全量功能** | 全部 27 端点功能 + 主要异常 + 安全 | 每次发版 |
| **P2 深水区** | 边界/幂等/并发/兼容/契约 | 回归 + 发布前 |

## 五、执行方式

```bash
# 全量企业级接口测试（含安全/幂等/并发）
pytest tests/test_api_enterprise.py -v

# 仅运行某一层
pytest tests/test_api_enterprise.py -k "Security or Boundary" -v

# 冒烟（P0）
pytest tests/test_api_enterprise.py -k "Health or Smoke or CRUD" -v

# 覆盖率
pytest tests/ -v --cov=app --cov-report=term-missing
```

> 配套可执行套件见 `tests/test_api_enterprise.py`（详见 PR）。

## 六、契约漂移检测

每次改动接口后运行以下断言，确保实现与 `/openapi.json` 契约一致：

```python
# 伪代码示例
spec = client.get("/openapi.json").json()
paths = set(spec["paths"].keys())
assert "/api/cases" in paths
assert {k: list(v.keys()) for k, v in spec["paths"].items() if "/api/cases" in k}
```

## 七、已知接口风险与加固建议

| 风险 | 当前状态 | 企业级建议 |
|------|---------|-----------|
| 无认证/授权 | 全部接口匿名可访问 | 引入 RBAC + JWT/OAuth2 中间件 |
| 无速率限制 | 可被无限调用 | 加 Rate Limit（令牌桶） |
| 无输入长度上限 | 超大 body 可占用内存 | 加 `max_request_size` 中间件 |
| 报告下载路径 | `os.path.join("reports", filename)` 存在目录穿越面 | 校验文件名 `os.path.basename` + 白名单 |
| 错误信息泄露 | 部分 500 返回内部细节 | 统一异常处理，脱敏 |
| 无 API 版本化 | 路径无 `/api/v1` | 契约演进期引入版本前缀 |
