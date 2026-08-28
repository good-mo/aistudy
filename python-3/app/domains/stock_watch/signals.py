"""
app.domains.stock_watch.signals —— A股盯盘多因子信号引擎

从原始 stock_monitor/signals 提炼而来，提供七大因子（MA/MACD/KDJ/RSI/
布林带/成交量/大盘环境）的综合评分信号引擎。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from app.core.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class SignalParams:
    """信号引擎参数。"""

    # 方案 B：按因子权重分布（总和约 20.5，不含共振与大盘）优化阈值
    #   买入 ~35% → 7；强买入 ~55% → 12
    #   卖出 ~35% → -7；强卖出 ~55% → -12
    buy_score: int = 7
    strong_buy_score: int = 12
    sell_score: int = -7
    strong_sell_score: int = -12


@dataclass
class FactorResult:
    """单个因子输出结果。"""

    score: int = 0
    reason: str = ""
    data: dict = field(default_factory=dict)


class IndicatorContext:
    """向因子提供历史行情与指标计算的上下文。"""

    def __init__(self, daily_history: dict, daily_volumes: dict):
        self._daily_history = daily_history
        self._daily_volumes = daily_volumes

    def prices(self, code: str) -> List[float]:
        hist = self._daily_history.get(code)
        return [h["close"] for h in hist] if hist else []

    def highs(self, code: str) -> List[float]:
        hist = self._daily_history.get(code)
        return [h.get("high", h["close"]) for h in hist] if hist else []

    def lows(self, code: str) -> List[float]:
        hist = self._daily_history.get(code)
        return [h.get("low", h["close"]) for h in hist] if hist else []

    def daily_volumes(self, code: str) -> List[float]:
        return self._daily_volumes.get(code, [])


def _sma(data: List[float], period: int) -> List[float]:
    """计算简单移动平均 SMA。"""
    if len(data) < period:
        return []
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(0)
        else:
            result.append(sum(data[i - period + 1:i + 1]) / period)
    return result


def _ema(data: List[float], period: int) -> List[float]:
    """计算指数移动平均 EMA。"""
    if len(data) < period:
        return []
    k = 2 / (period + 1)
    ema = [sum(data[:period]) / period]
    for price in data[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return [0] * (period - 1) + ema


def _macd(prices: List[float], fast=12, slow=26, signal=9):
    """计算 MACD，返回 (DIF, DEA, MACD柱)。"""
    if len(prices) < slow:
        return [], [], []
    ema_fast = _ema(prices, fast)
    ema_slow = _ema(prices, slow)
    dif = []
    for i, (f, s) in enumerate(zip(ema_fast, ema_slow)):
        dif.append(f - s if i >= slow - 1 else 0.0)
    valid_start = slow - 1
    valid_dif = dif[valid_start:]
    if len(valid_dif) < signal:
        return dif, [0] * len(dif), [0] * len(dif)
    dea_vals = _ema(valid_dif, signal)
    dea = [0] * valid_start + dea_vals
    macd_bar = [(dif[i] - dea[i]) * 2 for i in range(len(dif))]
    return dif, dea, macd_bar


def _rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(-period, 0):
        diff = prices[i] - prices[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _bollinger(prices: List[float], period=20, std_dev=2):
    if len(prices) < period:
        return 0, 0, 0, 0
    ma = _sma(prices, period)
    if not ma or ma[-1] == 0:
        return 0, 0, 0, 0
    mid = ma[-1]
    recent = prices[-period:]
    mean = sum(recent) / period
    std = (sum((x - mean) ** 2 for x in recent) / period) ** 0.5
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    bandwidth = (upper - lower) / mid * 100 if mid > 0 else 0
    return mid, upper, lower, bandwidth


class BaseSignal:
    """信号因子基类。"""

    name = "base"

    def __init__(self, params: SignalParams):
        self.params = params

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        raise NotImplementedError


class MaSignal(BaseSignal):
    """因子1: MA 均线 + 支撑阻力 + K线形态（权重 ±6）。"""

    name = "MA"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []
        code = row["code"]
        prices = ctx.prices(code)
        if len(prices) < 22:
            return FactorResult(0, "", {"trend_dir": 0})
        ma5, ma10, ma20 = _sma(prices, 5), _sma(prices, 10), _sma(prices, 20)
        ma60 = _sma(prices, 60)
        if not ma5 or not ma10 or not ma20:
            return FactorResult(0, "", {"trend_dir": 0})
        cur_price = prices[-1]
        cur_ma5, cur_ma10, cur_ma20 = ma5[-1], ma10[-1], ma20[-1]
        prev_ma5 = ma5[-2] if len(ma5) >= 2 else cur_ma5
        prev_ma10 = ma10[-2] if len(ma10) >= 2 else cur_ma10

        trend_dir = 0
        if cur_ma5 > cur_ma10 > cur_ma20 and cur_ma5 > 0:
            score += 3
            reasons.append("多头排列")
            trend_dir = 1
            if ma60 and ma60[-1] > 0 and cur_ma20 > ma60[-1]:
                score += 1
                reasons.append("中长期多头")
        elif cur_ma5 < cur_ma10 < cur_ma20 and cur_ma5 > 0:
            score -= 3
            reasons.append("空头排列")
            trend_dir = -1
            if ma60 and ma60[-1] > 0 and cur_ma20 < ma60[-1]:
                score -= 1
                reasons.append("中长期空头")
        else:
            if cur_price > cur_ma20 and cur_ma20 > 0:
                score += 1
                reasons.append("站上MA20")
                trend_dir = 1
            elif cur_price < cur_ma20:
                score -= 1
                reasons.append("跌破MA20")
                trend_dir = -1

        if prev_ma5 <= prev_ma10 and cur_ma5 > cur_ma10:
            score += 2 if trend_dir >= 0 else 1
            reasons.append("MA5上穿MA10金叉")
        elif prev_ma5 >= prev_ma10 and cur_ma5 < cur_ma10:
            score -= 2 if trend_dir <= 0 else 1
            reasons.append("MA5下穿MA10死叉")

        return FactorResult(score, "；".join(reasons), {"trend_dir": trend_dir})


class MacdSignal(BaseSignal):
    """因子2: MACD 信号（权重 ±5）。"""

    name = "MACD"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []
        code = row["code"]
        prices = ctx.prices(code)
        if len(prices) < 30:
            return FactorResult(0, "", {})
        dif, dea, macd_bar = _macd(prices)
        if len(dif) < 3:
            return FactorResult(0, "", {})
        cur_dif, cur_dea = dif[-1], dea[-1]
        prev_dif = dif[-2] if len(dif) >= 2 else cur_dif
        prev_dea = dea[-2] if len(dea) >= 2 else cur_dea

        if prev_dif <= prev_dea and cur_dif > cur_dea:
            score += 3 if cur_dif < 0 else 2
            reasons.append("DIF上穿DEA金叉")
        elif prev_dif >= prev_dea and cur_dif < cur_dea:
            score -= 3 if cur_dif > 0 else 2
            reasons.append("DIF下穿DEA死叉")

        if cur_dif > 0 and cur_dif > cur_dea:
            score += 1
            reasons.append("MACD多头")
        elif cur_dif < 0 and cur_dif < cur_dea:
            score -= 1
            reasons.append("MACD空头")

        return FactorResult(score, "；".join(reasons), {"macd_dif": cur_dif, "macd_dea": cur_dea})


class KdjSignal(BaseSignal):
    """因子3: KDJ 信号（权重 ±2）。"""

    name = "KDJ"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []
        code = row["code"]
        prices = ctx.prices(code)
        if len(prices) < 9:
            return FactorResult(0, "", {})
        lows, highs = ctx.lows(code), ctx.highs(code)
        low_n = min(lows[-9:]) if len(lows) >= 9 else min(prices[-9:])
        high_n = max(highs[-9:]) if len(highs) >= 9 else max(prices[-9:])
        rsv = (prices[-1] - low_n) / (high_n - low_n) * 100 if high_n != low_n else 50
        k = 2 / 3 * 50 + 1 / 3 * rsv
        d = 2 / 3 * 50 + 1 / 3 * k
        j = 3 * k - 2 * d
        if j < 0:
            score += 2 if trend_dir >= 0 else 1
            reasons.append(f"KDJ超卖(J={j:.1f})")
        elif j > 100:
            score -= 2 if trend_dir <= 0 else 1
            reasons.append(f"KDJ超买(J={j:.1f})")
        if k > d:
            score += 0.5
        return FactorResult(score, "；".join(reasons), {"kdj_k": k, "kdj_d": d, "kdj_j": j})


class RsiSignal(BaseSignal):
    """因子4: RSI 信号（权重 ±2）。"""

    name = "RSI"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []
        code = row["code"]
        prices = ctx.prices(code)
        if len(prices) < 15:
            return FactorResult(0, "", {"rsi": 50})
        rsi = _rsi(prices)
        if rsi <= 20:
            score += 3 if trend_dir >= 0 else 1
            reasons.append(f"RSI严重超卖({rsi:.1f})")
        elif rsi <= 30:
            score += 2 if trend_dir >= 0 else 1
            reasons.append(f"RSI超卖({rsi:.1f})")
        elif rsi >= 80:
            score -= 3 if trend_dir <= 0 else 1
            reasons.append(f"RSI严重超买({rsi:.1f})")
        elif rsi >= 70:
            score -= 2 if trend_dir <= 0 else 1
            reasons.append(f"RSI超买({rsi:.1f})")
        return FactorResult(score, "；".join(reasons), {"rsi": rsi})


class BollingerSignal(BaseSignal):
    """因子5: 布林带信号（权重 ±2）。"""

    name = "布林"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []
        code = row["code"]
        prices = ctx.prices(code)
        if len(prices) < 21:
            return FactorResult(0, "", {})
        mid, upper, lower, bandwidth = _bollinger(prices)
        if mid == 0:
            return FactorResult(0, "", {})
        cur_price = prices[-1]
        if cur_price > upper:
            score += 2 if trend_dir > 0 else -1
            reasons.append("突破布林上轨")
        if cur_price < lower:
            score -= 2 if trend_dir < 0 else 1
            reasons.append("跌破布林下轨")
        if bandwidth < 5:
            reasons.append("布林带宽收窄")
        return FactorResult(score, "；".join(reasons), {"boll_bandwidth": bandwidth})


class VolumeSignal(BaseSignal):
    """因子6: 成交量信号（权重 ±3）。"""

    name = "量能"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []
        code = row["code"]
        volume = row.get("volume", 0)
        change_pct = row.get("change_pct", 0)
        vols = ctx.daily_volumes(code)
        if volume == 0 or not vols:
            return FactorResult(0, "", {"volume_ratio": 0})
        avg_vol = sum(vols) / len(vols)
        vol_ratio = volume / avg_vol if avg_vol > 0 else 0
        if vol_ratio >= 2 and change_pct > 0:
            score += 2 if trend_dir >= 0 else 1
            reasons.append(f"放量上涨(量比{vol_ratio:.1f})")
        elif vol_ratio >= 2 and change_pct < 0:
            score -= 2 if trend_dir <= 0 else 1
            reasons.append(f"放量下跌(量比{vol_ratio:.1f})")
        elif vol_ratio <= 0.6 and change_pct < 0 and trend_dir >= 0:
            score += 1
            reasons.append("缩量洗盘")
        return FactorResult(score, "；".join(reasons), {"volume_ratio": vol_ratio})


class SignalEngine:
    """多因子综合评分引擎。"""

    FACTOR_CLASSES = [
        MaSignal, MacdSignal, KdjSignal, RsiSignal, BollingerSignal, VolumeSignal,
    ]

    def __init__(self, params: SignalParams | None = None):
        self.params = params or SignalParams()
        self._factors = [cls(self.params) for cls in self.FACTOR_CLASSES]

    def calculate(self, row, ctx: IndicatorContext, market_trend: int = 0):
        """对单只股票计算综合评分。"""
        total_score = 0
        all_reasons = []
        indicators = {}

        ma_result = self._factors[0].evaluate(row, ctx)
        trend_dir = ma_result.data.get("trend_dir", 0)
        total_score += ma_result.score
        if ma_result.reason:
            all_reasons.append(f"[MA]{ma_result.reason}")
        indicators["trend_dir"] = trend_dir

        for factor in self._factors[1:]:
            result = factor.evaluate(row, ctx, trend_dir)
            total_score += result.score
            if result.reason:
                all_reasons.append(f"[{factor.name}]{result.reason}")
            indicators.update(result.data or {})

        total_score, all_reasons = self._resonance_bonus(total_score, all_reasons)

        if market_trend != 0:
            total_score, all_reasons = self._market_adjust(total_score, all_reasons, market_trend)

        if trend_dir > 0 and total_score <= 0:
            total_score = max(total_score, 0)
        elif trend_dir < 0 and total_score >= 0:
            total_score = min(total_score, 0)

        level = self._level(total_score)
        return total_score, level, all_reasons, indicators

    def _resonance_bonus(self, total_score, all_reasons):
        seen = set()
        for r in all_reasons:
            for prefix in ["[MA]", "[MACD]", "[KDJ]", "[RSI]", "[布林]", "[量能]"]:
                if r.startswith(prefix) and prefix not in seen:
                    seen.add(prefix)
                    break
        if len(seen) >= 3:
            bonus = min(len(seen) - 2, 3)
            if total_score > 0:
                total_score += bonus
                all_reasons.append(f"[共振]{len(seen)}因子看多+{bonus}")
            elif total_score < 0:
                total_score -= bonus
                all_reasons.append(f"[共振]{len(seen)}因子看空-{bonus}")
        return total_score, all_reasons

    def _market_adjust(self, total_score, all_reasons, market_trend):
        if market_trend > 0 and total_score > 0:
            total_score += 2
            all_reasons.append("[大盘]大盘强势加成")
        elif market_trend < 0 and total_score < 0:
            total_score -= 2
            all_reasons.append("[大盘]大盘弱势加成")
        return total_score, all_reasons

    def _level(self, total_score: int) -> str:
        p = self.params
        if total_score >= p.strong_buy_score:
            return "🟢 强买入"
        elif total_score >= p.buy_score:
            return "🔵 买入"
        elif total_score <= p.strong_sell_score:
            return "🔴 强卖出"
        elif total_score <= p.sell_score:
            return "🟠 卖出"
        return "⚪ 观望"
