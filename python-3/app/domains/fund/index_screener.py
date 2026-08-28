"""
app.domains.fund.index_screener —— 指数基金与稳健基金精选

从原始 jijin_core.screening.index_fund 与 stable_picker 提炼而来，
统一接入 app.data 数据层。
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from app.core.logging_setup import get_logger
from app.data.fund_nav import get_fund_nav_df
from app.domains.fund.metrics import (
    calc_annual_return,
    calc_max_drawdown,
    calc_sharpe_ratio,
    calc_volatility,
)

logger = get_logger(__name__)

# 指数基金示例池
_DEFAULT_INDEX_POOL = [
    {"code": "510300", "name": "沪深300ETF", "fee_rate": 0.006, "fund_scale": 500},
    {"code": "510500", "name": "中证500ETF", "fee_rate": 0.006, "fund_scale": 300},
    {"code": "159919", "name": "沪深300ETF易方达", "fee_rate": 0.006, "fund_scale": 200},
]

# 稳健（固收+）候选池
_DEFAULT_STABLE_POOL = [
    {"code": "000001", "name": "华夏债券A", "type": "二级债基"},
    {"code": "110007", "name": "易方达稳健收益A", "type": "二级债基"},
]


class IndexFundScreener:
    """指数基金 / 稳健基金筛选器。"""

    def calc_fund_layer_score(self, row, fund_type: str = "passive") -> float:
        """基金优选层评分（跟踪质量 + 成本效率 + 规模流动性 + 风险收益）。"""
        score = 0.0
        te = getattr(row, "tracking_error", None) or 0
        ir = getattr(row, "information_ratio", 0) or 0
        mdd = getattr(row, "max_drawdown", 0) or 0
        sharpe = getattr(row, "sharpe", 0) or 0

        if fund_type == "passive":
            score += max(0, (0.03 - te) / 0.03 * 35) if te else 30
            score += min(max(ir * 20, 0), 10)
        else:
            score += min(max(ir * 25, 0), 35)
            score += min(max((0.05 - te) / 0.05 * 10, 0), 10) if te else 8

        fee = getattr(row, "fee_rate", 0.006) or 0.006
        score += max(0, (0.012 - fee) / 0.012 * 20)

        scale = getattr(row, "fund_scale", 0) or 0
        if scale >= 50:
            score += 15
        elif scale >= 10:
            score += 10
        else:
            score += 5

        score += min(max(sharpe * 8, 0), 10)
        score += min(max((0.15 - mdd) / 0.15 * 10, 0), 10)

        return round(min(score, 100), 1)

    def analyze_index_fund(self, fund_info: dict) -> dict:
        """深度分析单只指数基金。"""
        code = fund_info.get("code", "")
        nav = get_fund_nav_df(code, days=1825)
        if nav.empty or len(nav) < 2:
            return {**fund_info, "error": "净值数据不足"}
        metrics = {
            "annual_return": calc_annual_return(nav),
            "max_drawdown": calc_max_drawdown(nav),
            "volatility": calc_volatility(nav),
            "sharpe": calc_sharpe_ratio(nav),
        }
        return {**fund_info, **metrics}

    def screen_popular_index_funds(self, pool: list | None = None) -> pd.DataFrame:
        """筛选热门指数基金。"""
        results = []
        for fund in pool or _DEFAULT_INDEX_POOL:
            r = self.analyze_index_fund(fund)
            if "error" not in r:
                r["fund_layer_score"] = self.calc_fund_layer_score(
                    SimpleNamespace(**r), fund_type="passive"
                )
                results.append(r)
        logger.info("指数基金筛选完成：%d 只", len(results))
        return pd.DataFrame(results)

    def calc_stability_score(self, row) -> float:
        """计算稳健评分（回撤越小、夏普越高得分越高）。"""
        score = 50.0
        mdd = float(row.get("max_drawdown", 0) or 0)
        sharpe = float(row.get("sharpe", 0) or 0)
        ann_ret = float(row.get("annual_return", 0) or 0)

        if mdd < 0.03:
            score += 25
        elif mdd < 0.05:
            score += 18
        elif mdd < 0.08:
            score += 8
        else:
            score -= 10

        score += min(max(sharpe * 10, 0), 15)

        if 0.04 <= ann_ret <= 0.08:
            score += 10
        elif 0.02 <= ann_ret <= 0.10:
            score += 5

        return round(min(score, 100), 1)

    def pick_stable_fund(self, candidates: list | None = None) -> list:
        """精选稳健基金，返回评分排序结果。"""
        results = []
        for cand in candidates or _DEFAULT_STABLE_POOL:
            code = cand.get("code")
            if not code:
                continue
            nav = get_fund_nav_df(code, days=1095)
            if nav.empty or len(nav) < 60:
                continue
            row = {
                **cand,
                "annual_return": calc_annual_return(nav),
                "max_drawdown": calc_max_drawdown(nav),
                "sharpe": calc_sharpe_ratio(nav),
            }
            row["stability_score"] = self.calc_stability_score(row)
            results.append(row)

        results.sort(key=lambda x: x["stability_score"], reverse=True)
        return results
