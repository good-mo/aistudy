"""
app.domains.fund.scoring —— 基金综合评分模型

从原始 jijin_core.screening.scoring 提炼而来，基于基金经理方法论的综合评分
（满分 100），包含风格加成与周期动态阈值。
"""

from __future__ import annotations

from app.core.logging_setup import get_logger

logger = get_logger(__name__)


def calc_coarse_score(row) -> float:
    """粗筛简易风险调整收益评分（无需净值历史）。"""
    score = 0.0
    try:
        year_ret = float(getattr(row, "year_return", 0) or 0)
        mdd = float(getattr(row, "max_drawdown", 0) or 0)
        score = year_ret - 0.5 * mdd
    except Exception:  # noqa: BLE001
        score = 0.0
    return round(score, 2)


def _get_cycle_thresholds(cycle_phase: str, asset_type: str = "股票") -> dict:
    """根据周期阶段返回动态评分/信号阈值。"""
    base = {"buy": 60, "sell": 40, "hold": 50}
    if cycle_phase == "overheat":
        base = {"buy": 70, "sell": 35, "hold": 55}
    elif cycle_phase == "recession":
        base = {"buy": 55, "sell": 45, "hold": 45}
    return base


def score_fund(
    sharpe, mdd, ann_ret, calmar, sortino, volatility,
    *,
    style_bonus: float = 0.0,
    manager_score: float = 0.0,
    flow_score: float = 0.0,
    valuation_score: float = 0.0,
) -> float:
    """综合评分模型（0-100）。"""
    score = 50.0
    score += min(max(sharpe * 10, -20), 20)          # 夏普
    score += min(max(calmar * 8, -15), 15)            # 卡尔马
    score -= min(max((mdd - 0.2) * 80, 0), 20)        # 回撤惩罚
    score += min(max((ann_ret - 0.05) * 120, -15), 20)  # 年化
    score += min(max(sortino * 6, -10), 10)           # 索提诺
    score += style_bonus
    score += manager_score
    score += flow_score
    score += valuation_score
    result = round(min(max(score, 0), 100), 1)
    logger.debug("综合评分=%.1f（夏普%.2f 回撤%.2f 年化%.2f）", result, sharpe, mdd, ann_ret)
    return result


def generate_signal(
    score, sharpe, mdd, ann_ret, calmar,
    cycle_phase: str = "recovery",
    thresholds: dict | None = None,
) -> dict:
    """生成买入/卖出/持有信号。"""
    if thresholds is None:
        thresholds = _get_cycle_thresholds(cycle_phase)
    if score >= thresholds["buy"]:
        signal = "买入"
    elif score <= thresholds["sell"]:
        signal = "卖出"
    else:
        signal = "持有"
    return {
        "signal": signal,
        "score": score,
        "reason": f"综合评分 {score:.1f}（买入阈值 {thresholds['buy']}，卖出阈值 {thresholds['sell']}）",
    }


def get_cycle_thresholds(cycle_phase: str, asset_type: str = "股票") -> dict:
    """对外暴露周期阈值。"""
    return _get_cycle_thresholds(cycle_phase, asset_type)
