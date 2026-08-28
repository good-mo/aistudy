"""
app.domains.fund —— 基金分析模块

提供基金数据获取、评分、筛选、指数/稳健精选、追踪、监控等业务能力。
依赖 app.data 统一数据接口。
"""

from app.domains.fund.analyzer import FundAnalyzer, FundScorer
from app.domains.fund.metrics import (
    calc_alpha_and_ir,
    calc_annual_return,
    calc_calmar_ratio,
    calc_max_drawdown,
    calc_sharpe_ratio,
    calc_sortino_ratio,
    calc_volatility,
)
from app.domains.fund.scoring import (
    generate_signal,
    get_cycle_thresholds,
    score_fund,
)
from app.domains.fund.screener import FundScreener
from app.domains.fund.index_screener import IndexFundScreener
from app.domains.fund.tracking import (
    AlertConfig,
    AlertEngine,
    FundMonitor,
    FundTracker,
    load_portfolio,
)

__all__ = [
    "FundAnalyzer",
    "FundScorer",
    "FundScreener",
    "IndexFundScreener",
    "FundTracker",
    "FundMonitor",
    "AlertConfig",
    "AlertEngine",
    "load_portfolio",
    "calc_annual_return",
    "calc_max_drawdown",
    "calc_volatility",
    "calc_sharpe_ratio",
    "calc_calmar_ratio",
    "calc_sortino_ratio",
    "calc_alpha_and_ir",
    "score_fund",
    "generate_signal",
    "get_cycle_thresholds",
]
