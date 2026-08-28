# 新增功能模块

本版本新增了三个企业级测试平台能力模块，覆盖了此前项目中缺失的三大测试工作流场景。

## 📦 数据工厂（需求1：别让我重复造数据）

### 数据模板
- 内置 5 套常用数据模板：**用户 / 商品 / 订单 / 库存 / 优惠券**
- 支持自定义模板：字段定义 JSON Schema + 6 种生成策略
  - `fixed` 固定值
  - `sequence` 序列号（支持 `{n}` 占位符）
  - `uuid` 唯一标识
  - `random` 随机值
  - `timestamp` 时间戳
  - `reference` 跨模板引用

### 一键造数
- 选择模板 + 指定批次数量 → 自动生成完整数据链路
- 支持模板间依赖关系自动解析
- 生成批次可溯源（batch_id + 环境标识）

### 数据清理
- 按批次清理：清理单个批次的数据
- 按模板清理：清理某模板在某环境的所有数据
- 按环境清理：一键清理某环境下所有测试数据
- 软删除机制，可追溯历史

## 🖥️ 环境管理（需求2：环境别总是出问题）

### 环境状态可视化
- 环境注册：记录容器名、镜像、Compose 路径、健康检查 URL
- 实时状态展示：在线 / 离线 / 异常 / 启动中 / 维护中
- 批量健康检查：一键检查所有环境状态

### 容器环境拉起
- 支持 Docker Compose 一键拉起完整环境
- 支持单容器快速拉起
- Docker 不可用时自动降级并给出明确错误提示

### 环境告警
- 健康检查失败自动触发告警
- 容器未运行、HTTP 检查异常等场景自动告警
- 告警级别分级：info / warning / critical
- 告警处理：一键解决并归档

## 💚 脚本健康度（需求6：自动化脚本别总是挂）

### 稳定定位策略
- 定位器稳定性评估（评分 0-100）
- 支持 CSS / XPath / data-testid / text / ID / name 六种策略
- 自动推荐替代方案
- data-testid 最佳实践检测

### 自动修复
- 定位器失败时自动分析原因
- 从替代策略中自动选择最优方案
- 优先推荐 data-testid 定位方式
- 修复记录可追溯

### 脚本健康度监控
- 脚本注册：名称、文件路径、框架、定位器列表
- 执行记录：成功/失败、耗时、错误类型
- 健康度评分：基于成功率和失败惩罚因子自动计算
- 状态分级：healthy（≥85）/ unstable（60-84）/ degraded（<60）
- 执行历史追踪：最近 24h 失败统计

## API 接口一览

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 数据工厂 | GET | `/api/data/templates` | 列出数据模板 |
| 数据工厂 | POST | `/api/data/templates` | 创建模板 |
| 数据工厂 | POST | `/api/data/generate` | 一键造数 |
| 数据工厂 | GET | `/api/data/batches` | 列出生成批次 |
| 数据工厂 | POST | `/api/data/cleanup/batch/{id}` | 清理批次 |
| 数据工厂 | POST | `/api/data/cleanup/template/{id}` | 按模板清理 |
| 数据工厂 | POST | `/api/data/cleanup/env/{env}` | 按环境清理 |
| 环境管理 | GET | `/api/environments` | 列出环境 |
| 环境管理 | POST | `/api/environments` | 注册环境 |
| 环境管理 | POST | `/api/environments/{id}/launch` | 拉起环境 |
| 环境管理 | POST | `/api/environments/{id}/stop` | 停止环境 |
| 环境管理 | POST | `/api/environments/{id}/health` | 检查健康 |
| 环境管理 | GET | `/api/alerts` | 列出告警 |
| 脚本健康 | GET | `/api/scripts` | 列出脚本 |
| 脚本健康 | POST | `/api/scripts` | 注册脚本 |
| 脚本健康 | POST | `/api/locators/evaluate` | 评估定位器 |
| 脚本健康 | POST | `/api/scripts/{id}/repair/{name}` | 自动修复 |
| 脚本健康 | POST | `/api/scripts/{id}/executions` | 记录执行 |
