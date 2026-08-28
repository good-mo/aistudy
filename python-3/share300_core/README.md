# share300_core —— 沪深300 成分股专业分析工具箱

对 `share300/` 目录下分散脚本的专业化重构，基于 **9 大技术指标 + 基本面** 对
沪深300 成分股进行买入 / 卖出信号筛选。

## 架构

```
share300_core/
├── __init__.py          # 包入口（导出 HS300Analyzer）
├── _paths.py            # 内部路径工具（复用原 share300/ 逻辑）
├── config/              # 配置与常量
│   └── constants.py     # API 地址、请求头、默认参数、300 成分股列表
├── data/                # 数据获取层
│   └── __init__.py      # TencentDataFetcher / 基本面 / 行业 / 成分股获取
├── analysis/            # 分析层
│   ├── analyzer.py      # HS300Analyzer 主分析器
│   └── __init__.py      # TechnicalIndicators / SignalAnalyzer / 基本面评分
├── signals/             # 买卖信号子系统
│   └── __init__.py      # 9 大技术指标综合评分引擎
└── cli/                 # 命令行入口
    └── analyzer.py      # python -m share300_core.cli.analyzer
```

## 设计要点

- **分层清晰**：配置 → 数据 → 分析 → 信号 → 展示，各层解耦。
- **复用提炼**：复用原 `hs300_analyzer.py` 中经实测验证的分析逻辑，避免重复移植上万行。
- **技术指标**：MA / MACD / KDJ / RSI / 成交量 / 布林带 / 支撑阻力 / K线形态 / 价格形态，共 9 大类。

## 运行方式

```bash
# 直接运行
python -m share300_core.cli.analyzer --workers 10 --top 20

# 或通过统一入口
python run.py share300 --workers 10 --top 20
```

## 依赖

```
pip install pandas numpy requests akshare
```
