# lc_core —— 理财产品深度分析专业工具箱

对 `lc/wealth_product_analyzer.py`（招行/浦发理财深度分析）的专业化重构，
按分层架构组织，提供干净的模型、统计、数据源与分析接口。

## 架构

```
lc_core/
├── __init__.py          # 包入口（导出 FinancialProduct / InvestorProfile）
├── _paths.py            # 内部路径工具（复用原 lc/ 逻辑）
├── models/              # 数据模型层
│   └── product.py       # FinancialProduct（理财产品）、InvestorProfile（投资者画像）
├── stats/               # 统计工具层
│   └── metrics.py       # StatisticalUtils（波动/回撤/夏普/偏度/峰度/VaR/CVaR 等）
├── datasources/         # 数据源层
│   └── providers.py     # CMBDataSource（招行 SM4 签名）/ SPDBDataSource（浦发）/ CSV
├── analysis/            # 分析层
│   └── analyzers.py     # 业绩/组合/信用/费率/行为/时机/经理评估/资产配置
├── tracking/            # 监控告警层（新增）
│   ├── monitor.py       # 理财持仓监控（收益/风险/期限告警）
│   └── alert_rules.py   # 告警规则与默认阈值
└── cli/                 # 命令行入口
    ├── analyze.py       # python -m lc_core.cli.analyze
    └── monitor.py       # python -m lc_core.cli.monitor（定时监控）
```

## 分析能力

| 分析器 | 能力 |
|--------|------|
| `DeepProductAnalyzer` | 深度产品分析：收益/风险/费率/时机/信用/流动性综合评分 |
| `PortfolioAnalyzer` | 组合相关性矩阵 + 分散度评分 |
| `ManagerEvaluator` / `PersonalManagerEvaluator` | 投资经理维度评估 |
| `CreditQualityAnalyzer` | 信用风险穿透分析 |
| `FeeCompetitivenessAnalyzer` | 费率竞争力百分位排名 |
| `BehavioralAdvisor` | 行为金融适配 |
| `TimingAdvisor` | 申购时机与利率周期判断 |

## 运行方式

```bash
# 指定产品代码深度分析（本地 CSV）
python -m lc_core.cli.analyze --code 107333E,108992A --risk 3

# 招行 API 批量分析（网络可用时）
python -m lc_core.cli.analyze --risk 3

# 或通过统一入口
python run.py lc --code 107333E --risk 3

# 理财持仓监控 + 阈值告警（默认每小时刷新）
python -m lc_core.cli.monitor --csv lc_holding.csv

# 一次性监控（配合 cron）
python -m lc_core.cli.monitor --csv lc_holding.csv --once
```

## 监控告警

`lc_core.cli.monitor` 对理财持仓提供持续监控告警（收益 / 风险 / 期限）：

| 规则 | 默认阈值 | 说明 |
|------|---------|------|
| 单产品/组合年化收益偏低 | 2% | `--min-rate` |
| 单产品集中度偏高 + 高风险 | 50万 & R4+ | 单产品投入超阈值且风险高时提醒分散 |
| 临近到期/开放 | 15天 | 到期前提醒关注赎回安排 |

持仓 CSV（`lc_holding.csv`）至少含 `理财编码`/`code` 和 `投入金额`/`amount`，
可选的 `年化收益`/`风险等级`/`到期日` 字段优先于产品详情用于判定。

## 依赖

```
pip install pandas numpy requests gmssl scipy
```
