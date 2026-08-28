"""
app.domains.fund.analyzer —— 基金分析器

基于 app.data 层统一接口，提供：
    - 单只基金净值分析
    - 基金实时行情查询
    - 基金评分（简化版）
"""

from __future__ import annotations

import pandas as pd

from app.core.logging_setup import get_logger
from app.data.fund_nav import get_fund_nav, get_fund_nav_df
from app.data.quotes import get_realtime_quote
from app.domains.fund.metrics import (
    calc_alpha_and_ir,
    calc_annual_return,
    calc_calmar_ratio,
    calc_max_drawdown,
    calc_sharpe_ratio,
    calc_sortino_ratio,
    calc_volatility,
)

logger = get_logger(__name__)


class FundAnalyzer:
    """基金分析器。"""

    def get_nav_history(self, fund_code: str, days: int = 1095) -> pd.Series:
        """获取基金历史净值序列。"""
        return get_fund_nav_df(fund_code, days)

    def get_realtime(self, fund_code: str) -> dict | None:
        """获取基金实时行情。"""
        return get_realtime_quote(fund_code, kind="fund")

    def get_nav_rows(self, fund_code: str, days: int = 1095) -> list[dict] | None:
        """获取基金净值原始列表。"""
        return get_fund_nav(fund_code, days)

    def calculate_daily_returns(self, nav: pd.Series) -> pd.Series:
        """计算每日收益率。"""
        return nav.pct_change().dropna()

    def calculate_metrics(self, nav: pd.Series) -> dict:
        """计算基金绩效指标（复用完整指标库）。"""
        if nav is None or nav.empty:
            return {}
        returns = self.calculate_daily_returns(nav)
        if returns.empty:
            return {}

        annual_return = calc_annual_return(nav)
        annual_vol = calc_volatility(nav)
        max_drawdown = calc_max_drawdown(nav)
        sharpe = calc_sharpe_ratio(nav)
        calmar = calc_calmar_ratio(nav)
        sortino = calc_sortino_ratio(nav)

        total_return = float(nav.iloc[-1] / nav.iloc[0] - 1)

        return {
            "total_return": total_return,
            "annual_return": annual_return,
            "annual_volatility": annual_vol,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe,
            "calmar_ratio": calmar,
            "sortino_ratio": sortino,
            "n_days": len(nav),
            "latest_nav": float(nav.iloc[-1]),
        }


class FundScorer:
    """基金评分器（简化：基于绩效指标的综合评分 0-5）。"""

    def score(self, metrics: dict) -> dict:
        """根据绩效指标给出综合评分。"""
        if not metrics:
            return {"total_score": 0, "level": "无数据"}

        score = 0.0
        details = {}

        # 年化收益率（0-2 分）
        annual = metrics.get("annual_return", 0)
        if annual >= 0.20:
            score += 2.0
            details["return"] = 2.0
        elif annual >= 0.10:
            score += 1.5
            details["return"] = 1.5
        elif annual >= 0.05:
            score += 1.0
            details["return"] = 1.0
        elif annual > 0:
            score += 0.5
            details["return"] = 0.5
        else:
            score += 0.0
            details["return"] = 0.0

        # 最大回撤（0-1.5 分）
        max_dd = abs(metrics.get("max_drawdown", 0))
        if max_dd < 0.10:
            score += 1.5
            details["drawdown"] = 1.5
        elif max_dd < 0.20:
            score += 1.0
            details["drawdown"] = 1.0
        elif max_dd < 0.30:
            score += 0.5
            details["drawdown"] = 0.5
        else:
            score += 0.0
            details["drawdown"] = 0.0

        # 夏普比率（0-1.5 分）
        sharpe = metrics.get("sharpe_ratio", 0)
        if sharpe >= 1.5:
            score += 1.5
            details["sharpe"] = 1.5
        elif sharpe >= 1.0:
            score += 1.0
            details["sharpe"] = 1.0
        elif sharpe >= 0.5:
            score += 0.5
            details["sharpe"] = 0.5
        else:
            score += 0.0
            details["sharpe"] = 0.0

        # 评级
        if score >= 4.0:
            level = "优秀"
        elif score >= 3.0:
            level = "良好"
        elif score >= 2.0:
            level = "一般"
        else:
            level = "较差"

        return {
            "total_score": round(score, 2),
            "level": level,
            "details": details,
        }
