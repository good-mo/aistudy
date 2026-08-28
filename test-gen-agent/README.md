# Test Generation Agent Toolkit

基于 FastAPI + LangGraph 的自动化测试用例生成 Agent，支持 **单文件生成**、**项目级批量扫描**、**用例库管理**、**缺陷跟踪**、**报告导出** 等功能。

> 📖 **完整操作手册**：[docs/操作手册.md](./docs/操作手册.md)

## 🔐 本地登录

启动项目后访问 `http://localhost:5173`，可使用以下开发环境默认账号：

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `admin` | `admin123` | 管理员 |
| `demo` | `demo` | 普通用户 |

以上凭据仅用于本地开发和演示。部署到生产环境后，请立即修改默认密码。

## ✨ 核心功能

### 🔧 测试用例生成（核心）
- **单文件模式**：粘贴 Python 代码 → 自动生成 pytest 测试 → 沙箱运行 → 覆盖率分析 → 自动修复
- **项目级扫描**：递归扫描整个项目目录，批量生成测试用例
- **多语言扩展点**：插件化 Scanner 设计，可扩展 Java/JS/Go 等语言
- **测试类型分类**：按行业标准支持 7 种测试类型分类生成
  - 🧪 **功能测试** `functional` — 验证业务功能正确性（正常/边界/异常）
  - 🔌 **接口测试** `api` — 验证 API 请求/响应契约、状态码与数据格式
  - 🎨 **UI 测试** `ui` — 验证用户界面元素、交互与状态变化
  - ⚡ **性能测试** `performance` — 验证响应时间、吞吐量与 SLO
  - 🔒 **安全测试** `security` — 验证注入防护、越权访问与敏感信息保护
  - 🖥️ **兼容性测试** `compatibility` — 验证跨版本/跨平台/跨配置兼容
  - 🔧 **可靠性测试** `reliability` — 验证幂等性、容错性与稳定性


### 🔗 接口测试模块（仿 MeterSphere）
提供完整的接口测试能力，覆盖接口全生命周期：

- **接口定义管理** `GET/POST /api/apitest/definitions`
  - 支持 HTTP / TCP / SQL / DUBBO 协议
  - 管理方法、路径、请求头、请求体、查询参数
- **接口用例管理** `GET/POST /api/apitest/cases`
  - 为接口配置断言、前置/后置脚本、变量提取、逻辑控制器
  - 支持运行单个接口用例并查看断言结果
- **接口场景编排** `GET/POST /api/apitest/scenarios`
  - 拖拽式按顺序编排多个接口步骤
  - 支持循环 / 条件 / 等待 / 事务控制器，步骤间变量传递
- **Mock 服务** `GET/POST /api/apitest/mocks`
  - 配置接口 Mock，通过 `/mock/{path}` 调用
  - 支持自定义状态码、响应体、响应头、延迟
- **断言规则**：文本 / 正则 / JSONPath / XPath / 状态码 / 包含
- **前置/后置脚本**：支持 Python / Groovy / BeanShell
- **前后置 SQL**：在请求前后执行 SQL 操作
- **变量提取**：JSONPath / 正则，跨用例/场景复用
- **逻辑控制器**：循环 / 条件 / 等待 / 事务
- **接口导入** `POST /api/apitest/import`
  - 支持 Postman Collection 与 Swagger/OpenAPI 导入
- **环境管理（多环境切换）** `GET/POST /api/apitest/environments`
  - 管理 Base URL、全局请求头、环境变量
  - 用例/场景执行时按环境切换
- **接口调试** `POST /api/apitest/debug`
  - 发送真实请求，实时查看响应、断言结果与提取变量

前端在「接口测试」模块下提供完整的 6 个子页面：接口定义 / 接口用例 / 场景编排 / Mock 服务 / 环境管理 / 接口调试。



### 📚 用例库管理（企业级）
- 用例 CRUD：创建、查看、更新、删除（软删除 → 回收站）

- 标签/优先级/状态管理（草稿/评审/已批准/已废弃）
- 关键词搜索、按状态/优先级过滤
- **用例关联**：接口/场景/性能用例互相关联
- **用例脑图视图**：树形结构展示用例层级（测试类型 → 优先级 → 用例）
- **用例导入/导出**：Excel(CSV) / XMind(JSON) 格式导入导出
- **用例评审流程**：提交评审 → 通过/驳回，完整评审记录
- **用例依赖关系**：前置/后置依赖管理
- **用例回收站**：软删除 → 回收站 → 恢复/彻底删除
- **用例版本管理**：自动快照、版本列表、回滚
- **用例变更记录**：完整审计日志（谁在何时改了什么）
- **用例关联需求**：关联 JIRA/TAPD 需求工单

#### 用例管理 API 一览

| 功能 | API |
|------|-----|
| 用例完整信息 | `GET /api/cases/{id}/full` |
| 用例关联 | `POST/GET/DELETE /api/cases/{id}/relations` |
| 用例脑图 | `GET /api/cases/mindmap` |
| 用例导出 | `GET /api/cases/export?format=excel\|mindmap` |
| 用例导入 | `POST /api/cases/import` |
| 提交评审 | `POST /api/cases/{id}/reviews/submit` |
| 通过评审 | `POST /api/cases/{id}/reviews/approve` |
| 驳回评审 | `POST /api/cases/{id}/reviews/reject` |
| 用例依赖 | `POST/GET/DELETE /api/cases/{id}/dependencies` |
| 回收站列表 | `GET /api/cases/trash` |
| 软删除 | `POST /api/cases/{id}/trash` |
| 恢复 | `POST /api/cases/{id}/restore` |
| 彻底删除 | `DELETE /api/cases/{id}/purge` |
| 版本列表 | `GET /api/cases/{id}/versions` |
| 版本回滚 | `POST /api/cases/{id}/rollback` |
| 变更记录 | `GET /api/cases/{id}/changes` |
| 需求关联 | `POST/GET/DELETE /api/cases/{id}/requirements` |



### 🔗 接口测试管理

- **接口定义管理**：HTTP/TCP/SQL/DUBBO 协议支持，请求/响应定义
- **接口用例管理**：基于接口定义的测试用例，支持断言/前置后置脚本/变量提取
- **场景编排**：多接口用例组合成场景，支持顺序执行与结果汇总
- **Mock 服务**：模拟接口响应，支持响应延迟与自定义响应
- **断言规则**：文本/正则/JSONPath/XPath/状态码断言
- **接口导入**：支持 Postman Collection / Swagger/OpenAPI JSON 导入
- **环境管理**：多环境切换（Base URL/请求头/变量）
- **接口调试**：在线调试接口，查看响应状态码/耗时/错误信息

#### 接口测试 API 一览

| 功能 | API |
|------|-----|
| 接口定义 CRUD | `GET/POST /api/api-definitions` |
| 接口用例 CRUD | `GET/POST /api/api-test-cases` |
| 场景编排 | `GET/POST /api/scenarios` + `POST /api/scenarios/{id}/execute` |
| Mock 服务 | `GET/POST /api/mock-services` |
| 断言规则 | `GET/POST /api/assertion-rules` |
| 接口导入 | `POST /api/api-definitions/import` |
| 环境管理 | `GET/POST /api/environments` |
| 接口调试 | `POST /api/debug` + `GET /api/debug-logs` |

### 📦 项目管理

- 项目 CRUD：创建/查看/更新/删除
- 语言标注：Python/Java/JavaScript/Go 等
- 项目状态：active/archived

### 📋 用例高级管理界面

- **脑图视图**：树形结构展示用例层级（测试类型 → 优先级 → 用例）
- **导入/导出**：Excel(CSV) / XMind(JSON) 格式
- **评审流程**：提交评审 → 通过/驳回
- **依赖关系**：前置/后置依赖
- **回收站**：软删除 → 恢复/彻底删除
- **版本管理**：自动快照、版本列表、回滚
- **变更记录**：完整审计日志
- **需求关联**：关联 JIRA/TAPD 需求工单

### 🐛 缺陷跟踪
- 测试失败自动创建缺陷
- 缺陷严重程度（Blocker/Critical/Major/Minor）与状态管理
- 关联用例与文件路径

### 📊 报告中心
- HTML / JUnit XML / Markdown 三种格式
- 在线预览与下载
- 自动从用例库生成汇总报告

### 💡 测试洞察（一线测试人员隐性需求）
面向一线测试人员的**被认可 / 减少背锅 / 职业发展**三大隐性需求，平台提供：

- **价值量化（被认可）** `GET /api/insights/value`
  - 缺陷价值分：按严重度折算"发现缺陷/避免线上事故"的价值
  - 覆盖率可视化：汇总平均覆盖率，证明"该测的都测了"
  - 避免事故估算：已修复的 blocker/critical 缺陷折算为线上事故规避

- **执行追溯（减少背锅）** `GET/POST /api/insights/trace`
  - 每次测试执行自动留痕（时间、文件、环境、结果、覆盖率、归因）
  - `GET /api/insights/trace/prove?file_path=...` 一键"自证清白"，
    回答"为什么没测出来"——是需求变更/环境异常/数据问题而非漏测

- **风险预警（减少背锅）** `GET /api/insights/risk`
  - 综合**代码复杂度 + 覆盖率缺口 + 缺陷密度**计算模块风险分
  - 发布前优先回归高风险模块，避免遗漏

- **低代码/无代码（职业发展）** `POST /api/insights/lowcode`
  - 用自然语言描述测试意图，自动生成可运行 pytest 用例
  - 无需写代码也能做自动化，配合 `GET /api/insights/skill-path`
    的技能阶梯（功能→自动化→测试开发）实现职业进阶

### 📁 项目扫描
- 递归扫描项目目录
- 提取函数签名、统计文件/函数数量

### ⚡ 异步任务队列
- 后台异步执行 LLM 生成 + 测试运行
- REST 接口立即返回 `task_id`，轮询查询进度
- 支持同步/异步双模式

### ⚡ 企业级性能测试引擎
- **自动性能基准**：测试通过 + 覆盖率达标后自动执行性能基准
- **SLO 校验**：响应时间 / 吞吐量 / 内存指标阈值校验
- **并发负载**：多线程模拟真实用户并发场景
- **资源监控**：峰值内存 / CPU 时间测量
- **报告集成**：性能报告可 JSON 序列化，供报告中心/CI 使用

### 🛡️ Docker 沙箱隔离
- 在隔离容器中运行测试代码
- CPU/内存/网络资源限制
- 未安装 Docker 时自动降级为宿主机执行

## 🚀 快速开始

### 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 .env（复制模板）
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY
```

### 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

访问 `http://localhost:8000` 打开 Web 控制台。

### CLI 使用

```bash
# 生成单个文件的测试（默认功能测试）
python -m app.cli generate --source-file demo.py

# 按指定测试类型生成（接口/性能/安全等）
python -m app.cli generate --source-file demo.py --test-type api
python -m app.cli generate --source-file demo.py --test-type security
python -m app.cli generate --source-file demo.py --test-type performance

# 项目级扫描并生成测试
python -m app.cli generate --project-path ./src --report

# 列出用例
python -m app.cli list-cases

# 列出缺陷
python -m app.cli defects
```

## 🎨 企业级 Web 控制台

项目内置了一套现代化的企业级 Web UI，支持测试工程师的完整日常工作流：

### 功能模块

| 模块 | 说明 |
|------|------|
| 📊 **仪表盘** | 工作台总览：用例统计、缺陷统计、最近活动、状态分布 |
| ⚙️ **测试生成** | AI 驱动的单文件 / 项目批量测试生成，实时进度展示 |
| 📚 **用例库** | 用例 CRUD、搜索过滤、状态流转（草稿→评审→批准） |
| 🐛 **缺陷跟踪** | 缺陷生命周期管理：打开→进行中→已修复→已关闭 |
| 📁 **项目扫描** | 递归扫描项目目录，展示函数签名，支持批量生成 |
| 📊 **报告中心** | HTML / JUnit / Markdown 三种格式报告生成与下载 |
| 💡 **测试洞察** | 价值量化、执行追溯自证清白、风险预警、低代码生成、职业发展路径 |
| ⚡ **任务队列** | 后台异步任务执行状态监控 |

### 技术架构

```
Enterprise UI
  ├─ templates/index.html    — 页面结构（侧边栏 + 内容区 + 弹窗）
  ├─ static/css/style.css    — 企业级设计系统（暗色主题）
  └─ static/js/app.js        — 应用逻辑（API 调用 + 状态管理）
```

- **测试生成**：单文件 / 项目批量 / 低代码生成（自然语言 → pytest）三种模式
- **测试洞察**：独立页面集成价值量化、执行追溯、风险预警、低代码与技能阶梯

- **设计语言**：现代暗色主题，专业配色方案
- **响应式**：支持桌面 / 平板 / 移动端
- **交互**：Toast 通知、模态框、进度条、状态徽章、数据表格

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/test-types` | 列出所有支持的测试类型 |
| POST | `/api/generate` | 生成测试（支持 `?async_mode=true`，body 含 `test_type`） |
| POST | `/api/tasks` | 提交异步任务 |
| GET | `/api/tasks/{id}` | 查询任务状态 |
| GET | `/api/tasks` | 列出任务 |
| GET | `/api/cases` | 列出用例 |
| POST | `/api/cases` | 创建用例 |
| GET | `/api/cases/{id}` | 获取用例 |
| PUT | `/api/cases/{id}` | 更新用例 |
| DELETE | `/api/cases/{id}` | 删除用例 |
| GET | `/api/cases/stats` | 用例统计 |
| GET | `/api/defects` | 列出缺陷 |
| POST | `/api/defects` | 创建缺陷 |
| GET | `/api/defects/{id}` | 获取缺陷 |
| PUT | `/api/defects/{id}` | 更新缺陷 |
| DELETE | `/api/defects/{id}` | 删除缺陷 |
| POST | `/api/projects/scan` | 扫描项目 |
| POST | `/api/projects/generate` | 项目级生成 |
| POST | `/api/reports/generate` | 生成报告 |
| GET | `/api/reports/list` | 列出报告 |
| GET | `/api/reports/download/{name}` | 下载报告 |
| GET | `/health` | 健康检查 |
| WS | `/ws/generate` | WebSocket 流式生成 |

## 🏗️ 架构

```
┌─────────────────────────────────────────────┐
│            Web 控制台 (FastAPI)              │
│  ├─ 单文件生成（REST / WebSocket）          │
│  ├─ 项目级扫描                              │
│  ├─ 用例库管理                              │
│  ├─ 缺陷跟踪                                │
│  └─ 报告中心                                │
├─────────────────────────────────────────────┤
│            LangGraph 工作流                  │
│  scan_code → generate_mocks                 │
│    → generate_tests → test_runner           │
│    ⇄ refinement_node (失败修复)             │
│    → coverage_analysis ⇄ refinement         │
├─────────────────────────────────────────────┤
│           服务支撑层                         │
│  ├─ Docker 沙箱（安全隔离测试执行）          │
│  ├─ 异步任务队列（后台执行）                │
│  └─ SQLite 持久化（用例/缺陷/检查点）        │
└─────────────────────────────────────────────┘
```



## 🧪 测试体系

项目包含完整的测试文档体系与自动化测试代码：

| 文档 | 说明 |
|------|------|
| [docs/test-matrix.md](./docs/test-matrix.md) | 全面测试矩阵（功能/边界/异常/安全/兼容/回归/性能/可靠性/并发） |
| [docs/test-cases-guide.md](./docs/test-cases-guide.md) | 详细测试用例指南（手工/自动化/性能/UI） |
| [docs/test-case-template.md](./docs/test-case-template.md) | 行业标准测试用例模板（IEEE 829） |
| [docs/test-gap-coverage.md](./docs/test-gap-coverage.md) | 10% 差距补齐测试（并发/系统集成/非功能性） |
| [docs/enterprise-performance-testing.md](./docs/enterprise-performance-testing.md) | 企业级性能测试流程（基准/SLO/并发/资源） |

### 运行自动化测试

```bash
# 安装测试依赖
pip install -r requirements-dev.txt

# 运行全部测试
pytest tests/ -v --cov=app --cov-report=term-missing

# 运行特定模块测试
pytest tests/test_config.py -v
pytest tests/test_mock_generator_extended.py -v
pytest tests/test_api_integration.py -v
```


## 🖥️ MeterSphere 前端集成

本项目已引入 **MeterSphere v3.x 官方前端工程**（`frontend/` 目录），并保留了一套对接现有
FastAPI 后端的精简 Web 控制台（`templates/index.html` + `static/`）。

### 目录结构

```
frontend/                          # MeterSphere v3.x 官方前端工程（Vue3 + TS + Vite）
  ├─ package.json                  # 依赖清单（已移除 link 依赖，可独立安装构建）
  ├─ config/                       # Vite 构建配置（dev/prod）
  ├─ src/                          # 前端源码
  ├─ nginx.conf                    # 前端部署 Nginx 配置（/front、/api、/ws 反代到 FastAPI）
  └─ dist/                         # 构建产物（由 Docker/CI 生成，不提交）
templates/index.html               # 精简 Web 控制台（FastAPI 直接渲染，默认入口）
static/                            # 精简控制台静态资源
```

### 本地开发前端

```bash
cd frontend
# 安装依赖（官方工程存在 peer 冲突，需 --legacy-peer-deps）
npm install --legacy-peer-deps --no-audit --no-fund   # 压缩所需的 terser 已含在 devDependencies
# 启动 dev server（/front、/api 请求代理到 http://localhost:8000 的 FastAPI 后端）
npm run dev
```

### 构建前端产物

```bash
cd frontend
npm run build        # 等价 npx vite build --config ./config/vite.config.prod.ts
```

构建产物输出到 `frontend/dist/`，FastAPI 通过 `/ms/` 前缀提供服务（见 `app/main.py`）。

### Docker 构建

`Dockerfile` 已改为多阶段构建：先用 `node:20` 构建 MeterSphere 前端产物，再在
`python:3.12` 运行时中随后端一起提供（`frontend/dist/` 挂载到 `/ms/`）。

```bash
docker build -t test-gen-agent .
docker run -p 8000:8000 -e OPENAI_API_KEY=your-key test-gen-agent
# 访问 http://localhost:8000/ms 查看 MeterSphere 前端
```

### 后端对接说明

- MeterSphere 前端以 `/front/` 前缀发起 API 请求；部署层（nginx / Vite dev proxy）
  会将该前缀剥离后转发到现有 FastAPI 后端的 `/api/*`。
- 现有精简控制台仍是默认入口（`/`），可通过 `/ms` 访问 MeterSphere 前端。

## 📦 部署

### Docker 部署

```bash
docker build -t test-gen-agent .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your-key \
  -v $(pwd)/data:/app/data \
  test-gen-agent
```

### 多架构镜像

项目已配置 CI 流水线，main 分支 push 自动构建并推送 amd64 + arm64 双架构镜像到制品库。
