# 测试覆盖差距补齐 — 并发 / 系统集成 / 非功能性测试

> 针对 AI 自动生成测试用例在「真实环境支撑」场景的 10% 差距，
> 本文档提供**并发测试、系统集成测试、非功能性测试**的完整测试方案与用例。

---

## 一、背景

在微信上传图片功能的质量评估中，AI 自动生成用例覆盖率达到手工测试质量的 **~90%**。
剩余 10% 差距集中在需要**真实环境支撑**的场景：

| 差距维度 | 说明 | 解决方案 |
|---------|------|---------|
| **并发测试** | 多线程上传、竞态条件、并发批量 | 使用 `ThreadPoolExecutor` / `threading` 进行真实并发验证 |
| **系统集成** | 弱网、断网、服务器错误、模块协同 | 使用本地 HTTP mock server 模拟真实网络 |
| **非功能性** | 性能基准、可靠性、安全性、资源 | 性能计时、幂等验证、恶意输入测试 |

---

## 二、并发测试矩阵

### 2.1 并发场景测试

| 测试编号 | 场景 | 并发数 | 验证目标 | 测试文件 |
|---------|------|-------|---------|---------|
| CC-001 | 多线程同时上传同一文件 | 10 | 全部成功，无竞态 | test_wechat_concurrency.py |
| CC-002 | 多线程并发计算 MD5 | 20 | 结果一致（幂等） | test_wechat_concurrency.py |
| CC-003 | 带进度回调的并发上传 | 5 | 回调正确，进度范围 0-100 | test_wechat_concurrency.py |
| CC-004 | 批量上传多 worker 并发 | 4 | 全部处理完成 | test_wechat_concurrency.py |
| CC-005 | 批量上传部分失败隔离 | 5 | 失败不影响其他文件 | test_wechat_concurrency.py |
| CC-006 | 高并发批量上传线程安全 | 60 | 无数据竞争、全部完成 | test_wechat_concurrency.py |
| CC-007 | 并发压缩+上传竞态 | 2 | 互不冲突 | test_wechat_concurrency.py |
| CC-008 | 50 线程并发文件校验 | 50 | 校验结果一致 | test_wechat_concurrency.py |
| CC-009 | 100 并发上传压力测试 | 100 | 系统稳定、不崩溃 | test_wechat_concurrency.py |

### 2.2 并发测试实现要点

- 使用 `threading.Thread` + `ThreadPoolExecutor` 模拟真实并发
- 使用 `lock` 保护共享数据（进度回调、结果列表）
- 每个线程独立 mock，互不干扰
- 超时保护：`join(timeout=30)` / `result(timeout=60)`

---

## 三、系统集成测试矩阵

### 3.1 网络集成场景

| 测试编号 | 场景 | 模拟方式 | 验证目标 | 测试文件 |
|---------|------|---------|---------|---------|
| SI-001 | 完整上传流程 | 本地 mock HTTP server | 返回 media_id | test_wechat_integration.py |
| SI-002 | 压缩后上传 | mock server + 压缩 | 压缩文件生成并上传 | test_wechat_integration.py |
| SI-003 | 进度回调集成 | mock server | 进度 0→100 | test_wechat_integration.py |
| SI-004 | MD5 一致性 | mock server | 上传不修改源文件 | test_wechat_integration.py |
| SI-005 | 慢网络超时 | mock server /slow | 超时抛异常 | test_wechat_integration.py |
| SI-006 | 慢网络+重试恢复 | mock server + retries | 重试后成功 | test_wechat_integration.py |
| SI-007 | 服务器 500 + 重试耗尽 | mock server /error | 抛出 UploadError | test_wechat_integration.py |
| SI-008 | 401 认证失败 | mock server /auth_fail | 抛出 UploadError | test_wechat_integration.py |
| SI-009 | 微信 API 错误码 | mock server /wechat_error | 抛出 WeChatAPIError | test_wechat_integration.py |
| SI-010 | 断网连接错误 | mock ConnectionError | 抛出异常 | test_wechat_integration.py |

### 3.2 多模块协同

| 测试编号 | 场景 | 验证目标 | 测试文件 |
|---------|------|---------|---------|
| SI-011 | 校验→压缩→上传 | 全链路正确 | test_wechat_integration.py |
| SI-012 | 尺寸校验→上传 | 前置条件满足 | test_wechat_integration.py |
| SI-013 | 批量上传端到端 | 多文件全部成功 | test_wechat_integration.py |
| SI-014 | 临时目录上传 | 文件系统集成 | test_wechat_integration.py |
| SI-015 | Unicode 文件名上传 | 编码兼容 | test_wechat_integration.py |
| SI-016 | 只读目录上传 | 权限处理 | test_wechat_integration.py |

### 3.3 集成测试实现要点

- 使用 `HTTPServer` + `BaseHTTPRequestHandler` 构建本地 mock API
- 通过 `/slow`、`/error`、`/auth_fail`、`/wechat_error` 路径模拟不同响应
- 使用 `patch` 模拟 `requests.post` 的异常行为
- 验证真实文件系统交互（临时文件、Unicode、只读）

---

## 四、非功能性测试矩阵

### 4.1 性能测试

| 测试编号 | 指标 | 阈值 | 验证目标 | 测试文件 |
|---------|------|------|---------|---------|
| NF-001 | MD5 计算（1MB） | < 5s | 大文件处理效率 | test_wechat_nonfunctional.py |
| NF-002 | 单次上传（Mock） | 平均 < 2s | API 响应速度 | test_wechat_nonfunctional.py |
| NF-003 | 批量上传（20 文件） | < 30s | 吞吐量 | test_wechat_nonfunctional.py |
| NF-004 | 压缩大文件（512KB） | < 5s | 资源处理效率 | test_wechat_nonfunctional.py |
| NF-005 | 批量上传（100 文件） | < 60s | 稳定性 | test_wechat_nonfunctional.py |

### 4.2 可靠性测试

| 测试编号 | 场景 | 验证目标 | 测试文件 |
|---------|------|---------|---------|
| NF-006 | MD5 幂等性 | 多次计算一致 | test_wechat_nonfunctional.py |
| NF-007 | 指数退避重试 | 重试间隔按 2^n | test_wechat_nonfunctional.py |
| NF-008 | 多次失败最终成功 | 重试恢复 | test_wechat_nonfunctional.py |
| NF-009 | 内存占用有界 | 大量文件不 OOM | test_wechat_nonfunctional.py |

### 4.3 安全测试

| 测试编号 | 场景 | 验证目标 | 测试文件 |
|---------|------|---------|---------|
| NF-010 | 路径穿越攻击 | 被拒绝 | test_wechat_nonfunctional.py |
| NF-011 | 符号链接处理 | 正确解析 | test_wechat_nonfunctional.py |
| NF-012 | 超大文件拒绝 | 超限抛 ImageSizeError | test_wechat_nonfunctional.py |
| NF-013 | 空文件处理 | 被识别为无效 | test_wechat_nonfunctional.py |
| NF-014 | 恶意质量参数 | 拒绝非法值 | test_wechat_nonfunctional.py |
| NF-015 | 空 token | 拒绝 | test_wechat_nonfunctional.py |
| NF-016 | 极端尺寸值 | 全部拒绝 | test_wechat_nonfunctional.py |
| NF-017 | 大文件 MD5 | 不崩溃 | test_wechat_nonfunctional.py |
| NF-018 | 深层嵌套目录 | 处理正常 | test_wechat_nonfunctional.py |

---

## 五、执行说明

### 5.1 运行测试

```bash
# 运行全部 10% 差距补齐测试
cd examples
python -m pytest test_wechat_concurrency.py test_wechat_integration.py test_wechat_nonfunctional.py -v

# 单独运行某一类别
python -m pytest test_wechat_concurrency.py -v   # 并发
python -m pytest test_wechat_integration.py -v   # 系统集成
python -m pytest test_wechat_nonfunctional.py -v # 非功能性
```

### 5.2 测试依赖

- `pytest` — 测试框架
- 标准库：`threading`, `concurrent.futures`, `http.server`, `unittest.mock`
- 无第三方运行时依赖（requests 已由模块导入）

### 5.3 环境要求

- Python 3.8+
- 支持 `ThreadPoolExecutor` 与 `HTTPServer`

---

> 本文档与 `docs/test-matrix.md` 和 `docs/test-cases-guide.md` 配套使用。
> 通过补齐这 10% 差距，可实现 **AI 生成测试 + 真实环境支撑测试** 的完整覆盖。
