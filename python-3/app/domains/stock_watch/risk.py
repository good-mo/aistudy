"""
app.domains.stock_watch.risk —— 风险组合模块（P2）

专业分析师维度之六：风险与组合管理。

提供：
    - Beta：个股相对大盘（沪深300/上证指数）的贝塔
    - 波动率：年化历史波动率
    - VaR：风险价值（历史模拟法，95%/99% 置信度）
    - ES：预期缺口（尾部风险，可选）
    - 相关性矩阵：组合内标的相关系数（分散化质量）
    - 风险综合评分

数据源：复用 app.data.kline.get_kline_df / get_index_close_series（多源降级 + 缓存）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.logging_setup import get_logger
from app.data.index import get_index_close_series
from app.data.kline import get_kline_df

logger = get_logger(__name__)

# 默认大盘基准（沪深300 指数）
_DEFAULT_BENCHMARK = "000300"


@dataclass
class RiskSnapshot:
    """单只股票风险指标快照。"""

    code: str = ""
    name: str = ""
    beta: float | None = None
    annual_volatility: float | None = None
    var_95: float | None = None       # 95% 置信度单日 VaR（%）
    var_99: float | None = None       # 99% 置信度单日 VaR（%）
    es_95: float | None = None        # 95% 预期缺口（%）
    max_drawdown: float | None = None  # 区间最大回撤（%）
    score: float | None = None
    risk_level: str = "中"


def _returns_from_close(df: pd.DataFrame) -> pd.Series:
    """从收盘价计算收益率序列。"""
    close = df["close"].astype(float)
    return close.pct_change().dropna()


def _calc_beta(stock_ret: pd.Series, bench_ret: pd.Series) -> float | None:
    """计算 Beta = cov(股票, 大盘) / var(大盘)。"""
    aligned = pd.concat([stock_ret, bench_ret], axis=1, join="inner").dropna()
    if len(aligned) < 30:
        return None
    bench_var = aligned.iloc[:, 1].var()
    if bench_var == 0 or pd.isna(bench_var):
        return None
    cov = aligned.cov().iloc[0, 1]
    return round(float(cov / bench_var), 2)


def _calc_volatility(returns: pd.Series) -> float | None:
    """计算年化历史波动率（%）。"""
    if len(returns) < 20:
        return None
    daily_std = returns.std()
    if pd.isna(daily_std) or daily_std == 0:
        return None
    return round(float(daily_std * np.sqrt(252) * 100), 2)


def _calc_var(returns: pd.Series, confidence: float) -> float | None:
    """历史模拟法 VaR（%，正数表示潜在损失）。"""
    if len(returns) < 30:
        return None
    # 取损失分位数
    quantile = 1 - confidence
    var = returns.quantile(quantile)
    return round(float(-var * 100), 2)


def _calc_es(returns: pd.Series, confidence: float) -> float | None:
    """历史模拟法 ES（预期缺口，%）。"""
    if len(returns) < 30:
        return None
    quantile = 1 - confidence
    tail = returns[returns <= returns.quantile(quantile)]
    if tail.empty:
        return None
    return round(float(-tail.mean() * 100), 2)


def _calc_max_drawdown(close: pd.Series) -> float | None:
    """计算最大回撤（%）。"""
    if len(close) < 5:
        return None
    cummax = close.cummax()
    drawdown = (close - cummax) / cummax
    mdd = drawdown.min()
    return round(float(mdd * 100), 2) if not pd.isna(mdd) else None


def analyze_risk(
    code: str,
    name: str = "",
    benchmark: str = _DEFAULT_BENCHMARK,
    days: int = 250,
) -> RiskSnapshot:
    """分析单只股票的风险指标。

    Args:
        code: 证券代码
        name: 证券名称（可选）
        benchmark: 大盘基准指数代码（默认沪深300）
        days: K 线获取天数

    Returns:
        RiskSnapshot 风险指标快照。
    """
    snap = RiskSnapshot(code=code, name=name)
    df = get_kline_df(code, days=days)
    if df is None or len(df) < 30:
        logger.debug("%s 风险指标 K 线不足", code)
        return snap

    stock_ret = _returns_from_close(df)
    snap.annual_volatility = _calc_volatility(stock_ret)
    snap.var_95 = _calc_var(stock_ret, 0.95)
    snap.var_99 = _calc_var(stock_ret, 0.99)
    snap.es_95 = _calc_es(stock_ret, 0.95)
    snap.max_drawdown = _calc_max_drawdown(df["close"].astype(float))

    # Beta 需要大盘收益率
    try:
        bench = get_index_close_series(benchmark, days=days)
        if bench:
            bench_df = pd.DataFrame(bench, columns=["date", "close"])
            bench_ret = bench_df["close"].pct_change().dropna()
            snap.beta = _calc_beta(stock_ret, bench_ret)
    except Exception as e:  # noqa: BLE001
        logger.debug("%s Beta 计算失败: %s", code, e)

    snap.score, snap.risk_level = _score_risk(snap)
    return snap


def _score_risk(snap: RiskSnapshot) -> tuple[float, str]:
    """风险综合评分（0-100），>65 高风险，<35 低风险。"""
    scores: list[float] = []
    if snap.beta is not None:
        scores.append(max(0.0, min(100.0, snap.beta * 40)))
    if snap.annual_volatility is not None:
        # 波动率 10%-50% 映射到 0-100
        scores.append(max(0.0, min(100.0, (snap.annual_volatility - 10) * 2.5)))
    if snap.var_95 is not None:
        scores.append(max(0.0, min(100.0, snap.var_95 * 20)))
    if not scores:
        return None, "未知"
    score = float(sum(scores) / len(scores))
    if score >= 65:
        level = "高"
    elif score <= 35:
        level = "低"
    else:
        level = "中"
    return round(score, 1), level


def correlation_matrix(
    codes: list[str],
    benchmark: str = _DEFAULT_BENCHMARK,
    days: int = 250,
) -> pd.DataFrame | None:
    """计算组合内标的收益率相关性矩阵。

    Args:
        codes: 证券代码列表
        benchmark: 基准指数（附加列）
        days: K 线获取天数

    Returns:
        相关系数 DataFrame，数据不足返回 None。
    """
    rets: dict[str, pd.Series] = {}
    for code in codes:
        df = get_kline_df(code, days=days)
        if df is not None and len(df) > 30:
            rets[code] = _returns_from_close(df)
    # 附加大盘
    try:
        bench = get_index_close_series(benchmark, days=days)
        if bench:
            bench_df = pd.DataFrame(bench, columns=["date", "close"])
            rets[benchmark] = bench_df["close"].pct_change().dropna()
    except Exception as e:  # noqa: BLE001
        logger.debug("相关性矩阵基准获取失败: %s", e)

    if len(rets) < 2:
        return None
    frame = pd.DataFrame(rets).dropna()
    if len(frame) < 20:
        return None
    return frame.corr()
