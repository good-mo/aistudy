"""
指数基金专业筛选
先选对指数（估值合理、编制科学），再选对基金（跟踪质量、信息比率、费率、规模、流动性）。
"""

import pandas as pd

from common.logging_utils import get_logger
from ..data import (
    get_index_total_return,
    get_index_price,
    get_index_valuation,
    calc_valuation_percentile,
    screen_index_quality,
)
from ..data.nav import load_fund_nav
from ..data.sources.tencent import get_etf_quote_tencent
from ..analysis.metrics import (
    calc_annual_return,
    calc_max_drawdown,
    calc_volatility,
    calc_sharpe_ratio,
    calc_tracking_error_and_difference,
    calc_information_ratio,
)

logger = get_logger(__name__)


def calc_return_decomposition(fund_annual_ret: float, index_annual_ret: float, fee_rate: float, fund_type: str) -> dict:
    """收益分解：超额收益、成本、跟踪贡献。"""
    excess = fund_annual_ret - index_annual_ret
    return {
        "excess_return": excess,
        "fee_rate": fee_rate,
        "fund_type": fund_type,
    }


def calc_fund_layer_score(
    row,
    fund_type: str = "passive",
    data_quality: dict | None = None,
) -> float:
    """基金优选层评分（跟踪质量 + 成本效率 + 规模流动性 + 风险收益 + 超额归因）。"""
    score = 0.0
    te = getattr(row, "tracking_error", None) or 0
    ir = getattr(row, "information_ratio", 0) or 0
    mdd = getattr(row, "max_drawdown", 0) or 0
    sharpe = getattr(row, "sharpe", 0) or 0

    if fund_type == "passive":
        # 被动型：跟踪误差越小越好
        score += max(0, (0.03 - te) / 0.03 * 35)
        score += min(max(ir * 20, 0), 10)
    else:
        # 增强型：信息比率越大越好
        score += min(max(ir * 25, 0), 35)
        score += min(max((0.05 - te) / 0.05 * 10, 0), 10)

    # 成本效率（费率 20%）
    fee = getattr(row, "fee_rate", 0.006) or 0.006
    score += max(0, (0.012 - fee) / 0.012 * 20)

    # 规模流动性（15%）
    scale = getattr(row, "fund_scale", 0) or 0
    if scale >= 50:
        score += 15
    elif scale >= 10:
        score += 10
    else:
        score += 5

    # 风险收益（20%）
    score += min(max(sharpe * 8, 0), 10)
    score += min(max((0.15 - mdd) / 0.15 * 10, 0), 10)

    # 数据质量扣分
    if data_quality and not data_quality.get("ok", True):
        score *= 0.6

    return round(min(score, 100), 1)


def _analyze_fund_deep(fund_info: dict) -> dict:
    """对单只指数基金做深度分析。"""
    code = fund_info.get("code", "")
    nav = load_fund_nav(code, days=1825)
    if nav.empty or len(nav) < 2:
        return {**fund_info, "error": "净值数据不足"}
    metrics = {
        "annual_return": calc_annual_return(nav),
        "max_drawdown": calc_max_drawdown(nav),
        "volatility": calc_volatility(nav),
        "sharpe": calc_sharpe_ratio(nav),
    }
    return {**fund_info, **metrics}


def screen_popular_index_funds() -> pd.DataFrame:
    """筛选热门指数基金（简化演示流程）。"""
    # 示例基金池
    pool = [
        {"code": "510300", "name": "沪深300ETF", "fee_rate": 0.006},
        {"code": "510500", "name": "中证500ETF", "fee_rate": 0.006},
        {"code": "159919", "name": "沪深300ETF易方达", "fee_rate": 0.006},
    ]
    results = []
    for fund in pool:
        r = _analyze_fund_deep(fund)
        if "error" not in r:
            r["fund_layer_score"] = calc_fund_layer_score(pd.Series(r), fund_type="passive")
            results.append(r)
    logger.info("指数基金筛选完成：%d 只", len(results))
    return pd.DataFrame(results)
