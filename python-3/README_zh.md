# 云原生 Python 3 开发环境

本仓库在云原生 Python 3 开发环境基础上，沉淀了一套**个人金融分析工具箱**，将
**基金 / 理财 / A股盯盘 / 沪深300** 四大子系统整合为一个专业、完整的项目，
各子系统既可独立运行，也可通过统一入口 `run.py` 调用。

## 🎯 项目总览

```
├── run.py                    # 🎯 统一入口：整合四大子系统（jijin/share/share300/lc）
├── common/                   # 🛠 跨包共享基础设施（统一专业日志 logging_utils）
├── jijin_core/               # 📦 基金筛选与追踪（专业包架构）
├── share/stock_monitor/      # 📦 A股盯盘（专业包架构）
├── share300_core/            # 📦 沪深300 综合分析（专业包架构）
├── lc_core/                  # 📦 理财产品深度分析（专业包架构）
│
├── jijin/                    # 基金原始单文件脚本（保留，独立运行）
├── share/                    # A股盯盘原始脚本（保留，含 stock_monitor/）
├── share300/                 # 沪深300 原始脚本（保留）
├── lc/                       # 理财原始脚本（保留）
│
├── stock/                    # 交易引擎（实验性）
├── data/                     # 同花顺/行情数据抓取脚本
├── api/                      # OpenAI/InternLM API 调用示例
├── demo/                     # Python 语法示例
├── tests/                    # 单元测试
└── requirements.txt          # 统一依赖声明
```

## 🚀 快速开始

```bash
# 方式一：一键自动安装依赖 + 自检（推荐）
python bootstrap.py            # 自动检测并安装缺失依赖，完成后自检
# 或
python run.py install          # 通过统一入口调用自动安装

# 方式二：手动安装
pip install -r requirements.txt

# 环境自检（检查依赖与核心包导入）
python run.py doctor

# 查看可用命令
python run.py list
```

> 💡 **自动安装**：`bootstrap.py` 会自动检测缺失的依赖（numpy/pandas/requests 等）
> 并逐一安装，支持 `--check`（仅检查）与 `--mirror`（指定镜像源）参数；
> TA-Lib 因需系统 C 库作为**可选依赖**处理，缺失不阻断主流程。
>
> ✨ **运行即自动安装**：直接执行任意子命令（如 `python run.py share300 ...`）时，
> 若检测到缺失依赖会自动执行 `pip install` 并继续运行，无需手动安装。
> 如需关闭自动安装，可在命令后加 `--no-auto`（仅提示不安装）；
> 恢复默认自动安装用 `--auto`。

### 统一入口 `run.py`

| 命令 | 说明 | 示例 |
|------|------|------|
| `jijin` | 基金筛选与追踪 | `python run.py jijin --top 20` |
| `share` | A股实时盯盘 | `python run.py share` |
| `share300` | 沪深300 综合分析 | `python run.py share300 --workers 10 --top 20` |
| `lc` | 理财产品深度分析 | `python run.py lc --code 107333E --risk 3` |
| `monitor` | 综合每日监控（一次跑完基金/理财/沪深300） | `python run.py monitor` |
| `install` | 自动安装缺失依赖 | `python run.py install` |
| `doctor` | 环境自检 | `python run.py doctor` |

#### 📊 综合每日监控（`monitor`）

基金、理财产品等通常**每天看一次即可**，无需盘中实时盯盘。`monitor` 命令将
基金监控（`jijin`）、理财监控（`lc`）与沪深300 综合监控（`share300`）整合为
**一次统一入口**，逐个以“单次快照”模式运行并汇总结果：

```bash
# 一次跑完全部每日监控（基金 + 理财 + 沪深300）
python run.py monitor

# 仅运行指定子系统（逗号分隔）
python run.py monitor --only jijin,lc

# 全部以终端模式运行，不触发桌面通知（适合无图形界面的服务器）
python run.py monitor --console-only

# 指定持仓 CSV（基金/理财共用；默认取项目根目录 portfolio.csv / lc_holding.csv）
python run.py monitor --csv ./data/my_portfolio.csv
```

> 💡 **建议配合定时任务**：将 `python run.py monitor --console-only` 加入 cron
> 每日收盘后（如工作日 15:30）执行一次，即可自动完成基金、理财、沪深300 的
> 每日监控并输出告警。如需盘中实时盯盘，请单独运行 `python run.py share`。

### 各子系统独立运行

```bash
# 基金筛选
python -m jijin_core.cli.screener --top 20

# A股盯盘（模块化架构）
cd share && python -m stock_monitor.main

# 沪深300 分析
python -m share300_core.cli.analyzer --workers 10 --top 20

# 理财产品分析
python -m lc_core.cli.analyze --code 107333E --risk 3
```

## 📊 专业股票分析师（app 模块，P0-P2 多维指标）

`app` 模块基于统一数据访问层（多源降级 + 缓存），提供**专业分析师多维度**指标分析：

```bash
# 单只股票专业分析（基本面+资金面+高级技术+风险）
python -m app pro --code 600519 --name 贵州茅台

# 市场情绪 + 宏观环境
python -m app pro --market

# 组合相关性矩阵
python -m app pro --corr --codes 600519,600036
```

### 六大分析维度（P0-P2）

| 优先级 | 维度 | 模块 | 覆盖指标 |
|------|------|------|------|
| **P0** | 基本面 | `stock_watch/fundamental.py` | PE(TTM)/PB/PS/PEG、估值历史分位(5y/10y)、贵贱判断 |
| **P0** | 资金面 | `stock_watch/money_flow.py` | 北向净流入(当日/5日/20日)、主力净流入、两融余额、资金评分 |
| **P1** | 市场情绪 | `market/sentiment.py` | 上涨/涨停家数、市场宽度、涨停占比、情绪温度 |
| **P1** | 高级技术 | `stock_watch/advanced_indicators.py` | ATR、ADX、OBV、BIAS、跳空缺口 |
| **P2** | 宏观利率 | `macro/macro_data.py` | M1/M2同比、M1-M2剪刀差、国债收益率(10Y/2Y)、LPR |
| **P2** | 风险组合 | `stock_watch/risk.py` | Beta、年化波动率、VaR/ES、最大回撤、组合相关性 |

> 所有模块均通过 `app.core.cache` 缓存（TTL 1 天），数据源失败时自动降级，不阻塞主流程。

## 📦 专业包架构说明

| 包 | 功能 | 分层 |
|----|------|------|
| `jijin_core` | 基金筛选/追踪/分析 | config → data → analysis → screening → tracking → cli |
| `share/stock_monitor` | A股盯盘 | config → api → indicators → signals → monitor → cli |
| `share300_core` | 沪深300 信号筛选 | config → data → analysis → signals → cli |
| `lc_core` | 理财产品深度分析 | models → stats → datasources → analysis → cli |

各包遵循**分层清晰、单一职责、复用提炼、入口统一**的设计原则；专业包复用原始
脚本中经实测验证的逻辑，避免重复移植，同时提供干净的分层接口与命令行入口。

## 🧪 运行与验证

- 全部 `.py` 文件通过 `py_compile` 编译检查 ✅
- 单元测试 `tests/test_event_engine.py` 通过 ✅
- `run.py doctor` 环境自检通过 ✅

> ⚠️ 说明：`jijin`、`share300`、`lc` 的实时行情/宏观/理财数据依赖外部数据源
> （腾讯/东方财富/akshare/招行/浦发 API）。当网络不可达时，脚本会自动回退到内置
> 默认值 / 本地 CSV 模式，不报错。`share` 为常驻盯盘程序（Ctrl+C 退出）。

## 数据说明

- 各脚本运行会生成 `*.csv / *.json / *.txt` 结果文件，已加入 `.gitignore`，不入库。
- `stock/config/trade_client.json` 含明文口令，仅本地使用，已加入 `.gitignore`。

## 📝 日志功能

项目内置**统一专业日志**模块（`common/logging_utils.py`），四大子系统与交易引擎共享同一套日志配置：

- **分级输出**：DEBUG / INFO / WARNING / ERROR / CRITICAL 五级，可用环境变量 `APP_LOG_LEVEL` 覆盖默认级别（默认 INFO）
- **彩色控制台**：按级别着色的终端输出（DEBUG 灰 / INFO 绿 / WARNING 黄 / ERROR 红 / CRITICAL 红底白字）
- **滚动文件**：写入项目根目录 `logs/` 下，按大小滚动（默认 10MB × 5 份）
- **统一格式**：`时间戳 | 级别 | 日志器名 | 消息`，文件日志可附带线程名
- **函数级定位**：日志自动记录**所属运行函数名**（`funcName`），格式为 `时间戳 | 级别 | 日志器名 | 函数名 | 消息`，让每条日志都能精确对应到运行的函数层面，便于排查与定位问题
- **函数名高亮**：控制台中函数名以淡青色展示，与消息区分

```python
from common.logging_utils import setup_logging, get_logger

setup_logging()                      # 程序入口初始化一次（幂等）
logger = get_logger(__name__)        # 各模块获取自己的日志器
logger.info("任务开始")
logger.error("处理失败: %s", err)
```

CLI 入口（`run.py` / `python -m jijin_core.cli.*` / `python -m stock_monitor.main` 等）已统一初始化日志，无需额外配置。

## 包含的软件

- Python 3
- code-server
- pip (最新版)
- setuptools & wheel
- git / curl / wget
- cmake / clang / llvm-dev / libclang-dev
- build-essential
- twine / build(Python) / uv / poetry
- 系统工具: unzip, lsof, nload, htop, net-tools, dnsutils, openssh-server, vim

## 包含的 VS Code 扩展

- ms-python.python / flake8 / black-formatter / mypy-type-checker / pylint
- formulahendry.code-runner
- ms-toolsai.jupyter
- ms-python.debugpy
- tencent-cloud.coding-copilot
- cnbcool.cnb-welcome

---

> 使用云原生开发环境：
>
> ```yaml
> $:
>   vscode:
>     - docker:
>         image: docker.cnb.cool/examples/language/python-3
>       services:
>         - vscode
>         - docker
>       stages:
>         - name: ls
>           script: ls -al
> ```
