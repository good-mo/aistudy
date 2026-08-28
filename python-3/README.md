# Cloud Native Python 3.12 Development Environment

本仓库在云原生 Python 3.12 开发环境基础上，沉淀了一套**个人金融分析工具箱**，将
**基金 / 理财 / A股盯盘 / 沪深300** 四大子系统整合为一个专业、完整的项目，
各子系统既可独立运行，也可通过统一入口 `run.py` 调用。

## 项目结构

```
├── run.py                    # 统一入口：整合四大子系统（jijin/share/share300/lc）
├── common/                   # 跨包共享基础设施（统一专业日志 logging_utils）
├── jijin_core/               # 基金筛选与追踪（专业包架构）
├── share/stock_monitor/      # A股盯盘（专业包架构）
├── share300_core/            # 沪深300 综合分析（专业包架构）
├── lc_core/                  # 理财产品深度分析（专业包架构）
│
├── jijin/                    # 基金原始脚本（保留）
├── share/                    # A股盯盘原始脚本（保留）
├── share300/                 # 沪深300 原始脚本（保留）
├── lc/                       # 理财原始脚本（保留）
│
├── stock/                    # 交易引擎（实验性）
├── data/                     # 行情数据抓取脚本
├── api/                      # API 调用示例
├── demo/                     # Python 语法示例
├── tests/                    # 单元测试
└── requirements.txt          # 统一依赖声明
```

## 快速开始

```bash
# 方式一：一键自动安装依赖 + 自检（推荐）
python bootstrap.py            # 自动安装缺失依赖并自检
# 或
python run.py install          # 统一入口调用自动安装

# 方式二：手动安装
pip install -r requirements.txt

# 环境自检 / 查看命令
python run.py doctor
python run.py list

# 统一入口调用各子系统
python run.py jijin --top 20        # 基金筛选
python run.py share                 # A股盯盘
python run.py share300 --top 20     # 沪深300 分析
python run.py lc --code 107333E     # 理财产品分析

# 运行单元测试
python -m pytest tests/

> 💡 **Auto-install on run**: Running any subcommand (e.g. `python run.py share300 ...`)
> auto-installs missing dependencies via `pip install` and continues, so manual install
> is no longer required. Use `--no-auto` to disable (only warn), `--auto` to re-enable.

# 各子系统独立运行（专业包架构）
python -m jijin_core.cli.screener --top 20
cd share && python -m stock_monitor.main
python -m share300_core.cli.analyzer --top 20
python -m lc_core.cli.analyze --code 107333E
```

## 运行命令

本项目分为 **4 大子系统 + 统一入口**，以下是所有功能的运行命令。

### 🎯 一、统一入口（推荐）

```bash
# 查看可用命令
python run.py list

# 环境自检（依赖与导入检查）
python run.py doctor

# 自动安装缺失依赖
python run.py install

# 通过统一入口调用各子系统
python run.py jijin --top 20          # 基金筛选
python run.py share                   # A股盯盘
python run.py share300 --top 20       # 沪深300 分析
python run.py lc --code 107333E       # 理财分析

# 综合每日监控（基金/理财/沪深300 一次跑完，每天看一次即可）
python run.py monitor
python run.py monitor --only jijin,lc  # 仅运行指定子系统
python run.py monitor --console-only   # 终端模式，不触发桌面通知
```

### 📦 二、基金子系统（jijin_core）

| 功能 | 命令 | 说明 |
|------|------|------|
| **基金筛选** | `python -m jijin_core.cli.screener --top 50` | 按综合评分筛选前 N 名 |
| 指定基金分析 | `python -m jijin_core.cli.screener --code 110011,009665` | 指定基金代码，逗号分隔 |
| 持仓分析 | `python -m jijin_core.cli.screener --holdings` | 分析现有持仓 |
| 强制刷新数据 | `python -m jijin_core.cli.screener --refresh` | 忽略缓存重新拉取 |
| **指数基金筛选** | `python -m jijin_core.cli.index_screener --index` | 筛选热门指数基金 |
| **稳健基金精选** | `python -m jijin_core.cli.index_screener --stable` | 精选稳健型基金 |
| **每日收益追踪** | `python -m jijin_core.cli.tracker --csv portfolio.csv` | 追踪持仓每日收益 |
| 🔴 **基金定时监控** | `python -m jijin_core.cli.monitor --csv portfolio.csv` | **常驻监控：拉取净值→触发告警** |
| 🔴 监控只跑一次 | `python -m jijin_core.cli.monitor --csv portfolio.csv --once` | 单次检查即退出（适合 cron） |
| 🔴 监控自定义阈值 | `python -m jijin_core.cli.monitor --single-drop 5 --port-loss 2000` | 自定跌幅/亏损告警阈值 |

**基金监控完整参数：**
```bash
python -m jijin_core.cli.monitor \
    --csv portfolio.csv \
    --interval 300 \              # 刷新间隔（秒），默认5分钟
    --single-drop 3 \             # 单只基金日跌幅阈值（%）
    --port-loss 1000 \            # 组合当日亏损阈值（元）
    --single-loss 2000 \          # 单只基金浮亏阈值（元）
    --single-loss-pct 10 \        # 单只基金浮亏百分比阈值（%）
    --port-float-loss 5000 \      # 组合累计浮亏阈值（元）
    --once \                      # 只运行一次即退出
    --console-only \              # 仅终端输出，不尝试桌面通知
    --notify-exit                 # 触发告警时以非零退出码结束
```

### 📈 三、A股盯盘子系统（share）

| 功能 | 命令 | 说明 |
|------|------|------|
| 🔴 **A股实时盯盘** | `cd share && python -m stock_monitor.main` | **常驻实时盯盘，多因子信号评分** |
| 🔴 A股盯盘（统一入口） | `python run.py share` | 同上 |
| 🔴 强制刷新日K缓存 | `cd share && python -m stock_monitor.main --refresh` | 忽略缓存，强制重新拉取历史日K线 |

**盯盘功能说明：** MA均线 + MACD + KDJ + RSI + 布林带 + 成交量 + 大盘环境 七大因子综合评分，输出买入/卖出/观望信号，含涨跌幅预警（默认±3%触发）与桌面通知。

> 历史日K线已接入磁盘缓存（1天 TTL），启动时自动命中缓存，避免重复请求腾讯接口。

> 💡 修改 `share/stock_monitor/config.py` 中的 `watch_list` 可自定义监控股票池；修改 `refresh_interval` 可调整刷新间隔（默认10秒）。

### 📊 四、沪深300 子系统（share300_core）

| 功能 | 命令 | 说明 |
|------|------|------|
| **沪深300 综合分析** | `python -m share300_core.cli.analyzer --workers 10 --top 20` | 9大技术指标筛选全成分股买卖信号 |
| 调整并发 | `python -m share300_core.cli.analyzer --workers 20` | 并发线程数（默认10） |
| 调整展示数量 | `python -m share300_core.cli.analyzer --top 50` | 报告展示前 N 名（默认20） |
| 强制刷新缓存 | `python -m share300_core.cli.analyzer --refresh` | 忽略缓存，强制重新拉取所有数据 |

**数据缓存说明：** 沪深300 子系统已接入按更新频率分级的磁盘缓存——日K线（1天）、成分股列表（30天）、基本面财务（30天）、行业板块（1天）。二次运行时自动命中缓存，显著减少外部 API 请求量。缓存存放于项目根目录 `.data_cache/`，无需手动清理（过期自动刷新）。

### 💰 五、理财子系统（lc_core）

| 功能 | 命令 | 说明 |
|------|------|------|
| **理财深度分析** | `python -m lc_core.cli.analyze --code 107333E --risk 3` | 按产品代码分析 |
| 自定义画像 | `python -m lc_core.cli.analyze --risk 2 --goal 短期理财 --horizon 3-12月 --liquidity 高` | 自定风险/目标/期限/流动性 |
| 🔴 **理财定时监控** | `python -m lc_core.cli.monitor --csv lc_holding.csv` | **常驻监控：评估收益/风险/期限告警** |
| 🔴 理财监控只跑一次 | `python -m lc_core.cli.monitor --csv lc_holding.csv --once` | 单次检查即退出 |

**理财监控完整参数：**
```bash
python -m lc_core.cli.monitor \
    --csv lc_holding.csv \        # 理财持仓 CSV
    --codes-csv lc/product_codes.csv \  # 产品编码清单
    --interval 3600 \             # 刷新间隔（秒），默认1小时
    --min-rate 2.0 \              # 年化收益下限（%），低于则告警
    --once \                      # 只运行一次即退出
    --console-only \              # 仅终端输出
    --notify-exit                 # 触发告警时非零退出码
```

### 🔴 全部监控命令速查表

```bash
# ① 基金监控（5分钟刷新，默认阈值）
python -m jijin_core.cli.monitor --csv portfolio.csv

# ② 基金每日收益追踪（单次）
python -m jijin_core.cli.tracker --csv portfolio.csv

# ③ A股实时盯盘（10秒刷新，常驻）
cd share && python -m stock_monitor.main

# ④ 理财监控（1小时刷新，默认阈值）
python -m lc_core.cli.monitor --csv lc_holding.csv

# ⑤ 统一入口（均可加 --no-auto 关闭自动安装依赖）
python run.py jijin --top 20
python run.py share
python run.py share300 --top 20
python run.py lc --code 107333E
```

### 📋 六、其他功能

| 功能 | 命令 | 说明 |
|------|------|------|
| 单元测试 | `python -m pytest tests/` | 运行测试用例 |
| 依赖安装自检 | `python bootstrap.py` | 自动装依赖 + 自检 |
| 交易引擎（实验性） | `python -m stock.trade_service` | 实验性交易模块 |
| 行情数据抓取 | `python data/fetch.py` | 数据抓取脚本 |

> ⚠️ **使用前准备**：监控类命令需要先准备持仓 CSV 文件（参考 `portfolio.example.csv`）：
> - **基金**：`portfolio.csv`（含 `fund_code` + `total_cost` 两列）
> - **理财**：`lc_holding.csv`（持仓清单）
>
> **快捷启动**：先运行 `python bootstrap.py` 一键装好所有依赖，再执行各监控命令即可。

## 数据说明

- 各脚本运行会生成 `*.csv / *.json / *.txt` 结果文件，已加入 `.gitignore`，不入库。
- `stock/config/trade_client.json` 含明文口令，仅本地使用，已加入 `.gitignore`。

## 日志功能

项目内置**统一专业日志**模块（`common/logging_utils.py`），四大子系统与交易引擎共享同一套日志配置：

- **分级输出**：DEBUG / INFO / WARNING / ERROR / CRITICAL 五级，可用环境变量 `APP_LOG_LEVEL` 覆盖默认级别（默认 INFO）
- **彩色控制台**：按级别着色的终端输出，便于实时识别（DEBUG 灰 / INFO 绿 / WARNING 黄 / ERROR 红 / CRITICAL 红底白字）
- **滚动文件**：写入项目根目录 `logs/` 下，按大小滚动（默认 10MB × 5 份），便于排查与归档
- **统一格式**：`时间戳 | 级别 | 日志器名 | 消息`，文件日志可附带线程名
- **函数级定位**：日志自动记录**所属运行函数名**（`funcName`），格式为 `时间戳 | 级别 | 日志器名 | 函数名 | 消息`，让每条日志都能精确对应到运行的函数层面，便于排查与定位问题
- **函数名高亮**：控制台中函数名以淡青色展示，与消息区分

```python
from common.logging_utils import setup_logging, get_logger

setup_logging()                      # 在程序入口初始化一次（幂等）
logger = get_logger(__name__)        # 各模块获取自己的日志器
logger.info("任务开始")
logger.error("处理失败: %s", err)
```

CLI 入口（`run.py` / `python -m jijin_core.cli.*` / `python -m stock_monitor.main` 等）已统一初始化日志，无需额外配置。

## Included Software

- Python 3.12.10
- code-server
- pip (latest)
- setuptools & wheel
- git / curl / wget
- cmake / clang / llvm-dev / libclang-dev
- build-essential
- twine / build(Python) / uv / poetry
- System utilities: unzip, lsof, nload, htop, net-tools, dnsutils, openssh-server, vim

## Included VS Code Extensions

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
