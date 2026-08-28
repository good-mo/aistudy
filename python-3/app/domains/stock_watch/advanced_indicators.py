"""
app.domains.stock_watch.advanced_indicators —— 高级技术指标模块（P1）

专业分析师维度之四：高级技术分析（基于现有 K 线即可计算）。

提供：
    - ATR：真实波幅（动态止盈止损位计算）
    - ADX：平均趋向指数（判断趋势是否确立，>25 为强趋势）
    - OBV：能量潮（量价配合分析）
    - BIAS：乖离率（价格偏离均线程度）
    - 缺口：跳空缺口检测与回补
    - 综合技术评分与信号

数据源：复用 app.data.kline.get_kline_df（多源降级 + 缓存），不新增网络依赖。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.core.logging_setup import get_logger
from app.data.kline import get_kline_df

logger = get_logger(__name__)


@dataclass
class AdvancedIndicatorSnapshot:
    """高级技术指标快照。"""

    code: str = ""
    name: str = ""
    atr: float | None = None
    atr_pct: float | None = None
    adx: float | None = None
    adx_state: str = "无趋势"
    obv: float | None = None
    obv_trend: str = "持平"
    bias: float | None = None
    bias_state: str = "合理"
    gap_count: int = 0
    gap_unfilled: int = 0
    score: float | None = None
    verdict: str = "未知"


def _calc_atr(df: pd.DataFrame, period: int = 14) -> float | None:
    """计算 ATR（真实波幅）。"""
    if len(df) < period + 1:
        return None
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    return round(float(atr), 4) if not pd.isna(atr) else None


def _calc_adx(df: pd.DataFrame, period: int = 14) -> float | None:
    """计算 ADX（平均趋向指数）。"""
    if len(df) < period * 2 + 2:
        return None
    high, low, close = df["high"], df["low"], df["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
    return round(float(adx), 2) if not pd.isna(adx) else None


def _calc_obv(df: pd.DataFrame) -> tuple[float | None, str]:
    """计算 OBV（能量潮）并判断趋势。"""
    if len(df) < 2:
        return None, "持平"
    close = df["close"]
    volume = df["volume"].fillna(0)
    sign = np.sign(close.diff().fillna(0))
    obv = (sign * volume).cumsum()
    latest = obv.iloc[-1]
    obv20 = obv.iloc[-20:] if len(obv) >= 20 else obv
    if len(obv20) >= 5:
        trend = "上涨" if obv20.iloc[-1] > obv20.iloc[0] else ("下跌" if obv20.iloc[-1] < obv20.iloc[0] else "持平")
    else:
        trend = "持平"
    return (round(float(latest), 2), trend)


def _calc_bias(df: pd.DataFrame, period: int = 12) -> tuple[float | None, str]:
    """计算 BIAS 乖离率。"""
    if len(df) < period:
        return None, "合理"
    close = df["close"]
    ma = close.rolling(window=period).mean().iloc[-1]
    if ma == 0 or pd.isna(ma):
        return None, "合理"
    bias = (close.iloc[-1] - ma) / ma * 100
    bias = round(float(bias), 2)
    if bias > 8:
        state = "超买"
    elif bias < -8:
        state = "超卖"
    elif bias > 3:
        state = "偏高"
    elif bias < -3:
        state = "偏低"
    else:
        state = "合理"
    return bias, state


def _detect_gaps(df: pd.DataFrame, threshold_pct: float = 1.0) -> tuple[int, int]:
    """检测跳空缺口。

    Returns:
        (gap_count, unfilled_count)
    """
    if len(df) < 2:
        return 0, 0
    gaps = 0
    unfilled = 0
    for i in range(1, len(df)):
        prev_close = df["close"].iloc[i - 1]
        low, high = df["low"].iloc[i], df["high"].iloc[i]
        if prev_close == 0:
            continue
        if low > prev_close * (1 + threshold_pct / 100):
            gaps += 1
            # 向上缺口未回补
            if i + 1 < len(df):
                if df["close"].iloc[i + 1:].min() > prev_close:
                    unfilled += 1
            else:
                unfilled += 1
        elif high < prev_close * (1 - threshold_pct / 100):
            gaps += 1
            if i + 1 < len(df):
                if df["close"].iloc[i + 1:].max() < prev_close:
                    unfilled += 1
            else:
                unfilled += 1
    return gaps, unfilled


def analyze_advanced_indicators(code: str, name: str = "", days: int = 250) -> AdvancedIndicatorSnapshot:
    """分析单只股票的高级技术指标。

    Args:
        code: 证券代码
        name: 证券名称（可选）
        days: K 线获取天数

    Returns:
        AdvancedIndicatorSnapshot 高级技术指标快照。
    """
    snap = AdvancedIndicatorSnapshot(code=code, name=name)
    df = get_kline_df(code, days=days)
    if df is None or len(df) < 30:
        logger.debug("%s 高级指标 K 线不足", code)
        return snap

    snap.atr = _calc_atr(df)
    last_close = float(df["close"].iloc[-1])
    if snap.atr and last_close:
        snap.atr_pct = round(snap.atr / last_close * 100, 2)

    snap.adx = _calc_adx(df)
    if snap.adx is not None:
        if snap.adx >= 40:
            snap.adx_state = "极强趋势"
        elif snap.adx >= 25:
            snap.adx_state = "强趋势"
        elif snap.adx >= 20:
            snap.adx_state = "趋势酝酿"
        else:
            snap.adx_state = "无趋势"

    obv, obv_trend = _calc_obv(df)
    snap.obv = obv
    snap.obv_trend = obv_trend

    snap.bias, snap.bias_state = _calc_bias(df)
    snap.gap_count, snap.gap_unfilled = _detect_gaps(df)

    snap.score, snap.verdict = _score_advanced(snap)
    return snap


def _score_advanced(snap: AdvancedIndicatorSnapshot) -> tuple[float, str]:
    """高级技术指标综合评分（0-100）。"""
    scores: list[float] = []
    # ADX 强趋势加分
    if snap.adx is not None:
        scores.append(max(0.0, min(100.0, snap.adx * 2)))
    # OBV 上涨趋势加分
    if snap.obv_trend == "上涨":
        scores.append(70.0)
    elif snap.obv_trend == "下跌":
        scores.append(30.0)
    # BIAS 超卖反弹机会
    if snap.bias_state == "超卖":
        scores.append(65.0)
    elif snap.bias_state == "超买":
        scores.append(35.0)
    elif snap.bias_state == "合理":
        scores.append(50.0)
    if not scores:
        return None, "未知"
    score = float(sum(scores) / len(scores))
    if score >= 65:
        verdict = "偏强"
    elif score <= 35:
        verdict = "偏弱"
    else:
        verdict = "中性"
    return round(score, 1), verdict
