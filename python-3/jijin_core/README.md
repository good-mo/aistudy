# jijin_core —— 专业基金分析工具箱

对 `jijin/` 目录下 7 个大型单文件脚本的专业化重构，按分层架构拆分文件、解耦职责。

## 架构目录

```
jijin_core/
├── __init__.py            # 包入口与版本
├── config/
│   └── settings.py        # 全局配置（API 端点、缓存路径、费率、阈值）
├── data/                  # 数据获取层
│   ├── fund_loader.py     # 全市场基金加载（CSV 缓存 + 增量同步）
│   ├── nav.py             # 基金净值历史（带缓存）
│   ├── benchmark.py       # 多基准系统（股票指数/债券基准）
│   ├── index_data.py      # 指数数据与估值分位
│   └── sources/           # 数据源（按供应商拆分）
│       ├── tencent.py     # 腾讯财经行情
│       ├── eastmoney.py   # 东方财富净值/基金列表
│       ├── akshare_source.py  # akshare（宏观/估值）
│       ├── sina.py        # 新浪指数 K 线
│       └── http.py        # 统一 Session/重试
├── analysis/              # 分析层
│   ├── metrics.py         # 绩效指标（夏普/回撤/波动/跟踪误差等）
│   ├── macro.py           # 宏观周期判断
│   ├── industry.py        # 行业配置穿透
│   ├── flow.py            # 资金流与情绪
│   └── manager.py         # 基金经理画像
├── screening/             # 筛选策略层
│   ├── scoring.py         # 综合评分模型 + 信号
│   ├── screener.py        # 主筛选流程
│   ├── index_fund.py      # 指数基金筛选
│   └── stable_picker.py   # 稳健基金（固收+）精选
├── tracking/              # 追踪层
│   ├── daily_tracker.py   # 每日收益追踪 + 报表
│   ├── alerts.py          # 监控告警引擎（终端 + 桌面通知）
│   └── alert_rules.py     # 告警规则与默认阈值
├── utils/                 # 工具层
│   ├── terminal.py        # 终端颜色
│   ├── caching.py         # JSON/CSV 缓存
│   └── dates.py           # 日期/交易日工具
└── cli/                   # 命令行入口
    ├── screener.py        # 基金筛选
    ├── tracker.py         # 每日追踪
    └── index_screener.py  # 指数/稳健基金筛选
```

## 设计原则

- **分层清晰**：数据 → 分析 → 策略 → 展示，各层相互解耦
- **复用提炼**：抽取各脚本重复的 `Color`、指标计算、缓存逻辑为公共模块
- **入口统一**：所有功能通过 `cli/` 入口脚本调用

## 快速开始

```bash
# 基金筛选
python -m jijin_core.cli.screener --top 20
python -m jijin_core.cli.screener --code 010855,009665
python -m jijin_core.cli.screener --holdings

# 每日收益追踪（需 portfolio.csv，含 fund_code 和 total_cost）
# 首次使用请先创建 portfolio.csv（可参考仓库根目录 portfolio.example.csv 模板）：
#   fund_code,total_cost
#   110011,10000.00
cp ../portfolio.example.csv portfolio.csv
python -m jijin_core.cli.tracker --csv portfolio.csv

# 指数基金 / 稳健基金筛选
python -m jijin_core.cli.index_screener --index
python -m jijin_core.cli.index_screener --stable

# 定时监控 + 阈值告警（默认每 5 分钟刷新）
python -m jijin_core.cli.monitor --csv portfolio.csv

# 一次性监控（配合 cron，触发告警时非零退出）
python -m jijin_core.cli.monitor --csv portfolio.csv --once --notify-exit

# 自定义阈值（单基日跌幅 5%，组合日亏 2000 元）
python -m jijin_core.cli.monitor --single-drop 5 --port-loss 2000
```

## 监控告警

`jijin_core.cli.monitor` 提供持续的持仓监控告警能力：

| 规则 | 默认阈值 | 说明 |
|------|---------|------|
| 单只基金日跌幅 | 3% | `--single-drop` |
| 组合当日亏损 | ¥1000 | `--port-loss` |
| 单只基金累计浮亏金额 | ¥2000 | `--single-loss` |
| 单只基金累计浮亏比例 | 10% | `--single-loss-pct` |
| 组合累计浮亏金额 | ¥5000 | `--port-float-loss` |

触发后通过终端彩色输出 + 桌面通知（plyer，可选）提醒。
每日追踪 `tracker` 也会在输出日报后自动评估告警。

## 依赖

```
pip install pandas numpy requests akshare
```

## 迁移对照

| 原脚本 | 重构后位置 |
|--------|-----------|
| fund_screener.py | analysis/ + screening/screener.py |
| stable_fund_picker.py | screening/stable_picker.py |
| fund_tracker.py / zhcc.py | tracking/daily_tracker.py |
| bestjj.py / bestver.py / jsjj.py | screening/index_fund.py + data/index_data.py |
