"""信号因子：MA / MACD / KDJ / RSI / 布林带 / 成交量。

每个因子是一个独立的类，实现 `evaluate(row, context) -> FactorResult` 接口，
便于独立测试与扩展。
"""

from dataclasses import dataclass
from typing import List

from common.logging_utils import get_logger
from stock_monitor import indicators as ind
from stock_monitor.config import SignalParams

logger = get_logger(__name__)


@dataclass
class FactorResult:
    """单个因子输出结果。"""

    score: int = 0
    reason: str = ""
    data: dict = None  # 额外指标值（如 trend_dir / rsi / 布林带宽 等）

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class IndicatorContext:
    """向因子提供历史行情与指标计算的上下文。

    封装对 daily_history 的访问，使因子无需直接接触底层存储结构。
    """

    def __init__(self, daily_history: dict, daily_volumes: dict, kdj_state: ind.KdjState):
        self._daily_history = daily_history
        self._daily_volumes = daily_volumes
        self.kdj_state = kdj_state

    def prices(self, code: str) -> List[float]:
        """日K收盘价序列。"""
        hist = self._daily_history.get(code)
        return [h['price'] for h in hist] if hist else []

    def highs(self, code: str) -> List[float]:
        hist = self._daily_history.get(code)
        return [h.get('high', h['price']) for h in hist] if hist else []

    def lows(self, code: str) -> List[float]:
        hist = self._daily_history.get(code)
        return [h.get('low', h['price']) for h in hist] if hist else []

    def daily_volumes(self, code: str) -> List[float]:
        return self._daily_volumes.get(code, [])


class BaseSignal:
    """信号因子基类。"""

    name = "base"

    def __init__(self, params: SignalParams):
        self.params = params

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        raise NotImplementedError


class MaSignal(BaseSignal):
    """因子1: MA 均线 + 支撑阻力 + K线形态信号（权重: ±6）。"""

    name = "MA"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []

        code = row['代码']
        prices = ctx.prices(code)
        highs = ctx.highs(code)
        lows = ctx.lows(code)

        if len(prices) < 22:
            return FactorResult(0, "", {'trend_dir': 0})

        ma5 = ind.calc_sma(prices, 5)
        ma10 = ind.calc_sma(prices, 10)
        ma20 = ind.calc_sma(prices, 20)
        ma60 = ind.calc_sma(prices, 60)

        if not ma5 or not ma10 or not ma20:
            return FactorResult(0, "", {'trend_dir': 0})

        cur_price = prices[-1]
        cur_ma5 = ma5[-1]
        cur_ma10 = ma10[-1]
        cur_ma20 = ma20[-1]
        prev_ma5 = ma5[-2] if len(ma5) >= 2 else cur_ma5
        prev_ma10 = ma10[-2] if len(ma10) >= 2 else cur_ma10
        prev_ma20 = ma20[-2] if len(ma20) >= 2 else cur_ma20

        trend_dir = 0

        # --- 均线排列（核心趋势判断）---
        if cur_ma5 > cur_ma10 > cur_ma20 and cur_ma5 > 0:
            score += 3
            reasons.append("多头排列(MA5>MA10>MA20)")
            trend_dir = 1
            if ma60 and ma60[-1] > 0 and cur_ma20 > ma60[-1]:
                score += 1
                reasons.append("中长期多头(MA20>MA60)")
        elif cur_ma5 < cur_ma10 < cur_ma20 and cur_ma5 > 0:
            score -= 3
            reasons.append("空头排列(MA5<MA10<MA20)")
            trend_dir = -1
            if ma60 and ma60[-1] > 0 and cur_ma20 < ma60[-1]:
                score -= 1
                reasons.append("中长期空头(MA20<MA60)")
        else:
            if cur_price > cur_ma20 and cur_ma20 > prev_ma20:
                score += 1
                reasons.append("价格站上MA20且均线上行")
                trend_dir = 1
            elif cur_price < cur_ma20 and cur_ma20 < prev_ma20:
                score -= 1
                reasons.append("价格跌破MA20且均线下行")
                trend_dir = -1

        # --- 金叉/死叉 ---
        if prev_ma5 <= prev_ma10 and cur_ma5 > cur_ma10:
            if trend_dir >= 0:
                score += 2
                reasons.append("MA5↑上穿MA10 金叉")
            else:
                score += 1
                reasons.append("MA5↑上穿MA10 金叉(反弹)")
        elif prev_ma5 >= prev_ma10 and cur_ma5 < cur_ma10:
            if trend_dir <= 0:
                score -= 2
                reasons.append("MA5↓下穿MA10 死叉")
            else:
                score -= 1
                reasons.append("MA5↓下穿MA10 死叉(回调)")

        # --- 价格与MA20关系 ---
        if cur_price > cur_ma20 * 1.02:
            if trend_dir > 0:
                score += 1
        elif cur_price < cur_ma20 * 0.98:
            if trend_dir < 0:
                score -= 1

        # --- 支撑/阻力位分析 ---
        if len(prices) >= 30:
            lookback_prices = prices[-21:-1]
            lookback_highs = highs[-21:-1] if len(highs) >= 21 else lookback_prices
            lookback_lows = lows[-21:-1] if len(lows) >= 21 else lookback_prices

            recent_high = max(lookback_highs)
            recent_low = min(lookback_lows)

            if cur_price > recent_high * 1.005:
                score += 2
                reasons.append(f"突破前高{recent_high:.2f}")
            elif cur_price < recent_low * 0.995:
                score -= 2
                reasons.append(f"跌破前低{recent_low:.2f}")

            if trend_dir > 0 and cur_price > cur_ma20 and abs(cur_price - cur_ma20) / cur_ma20 < 0.02:
                score += 1
                reasons.append("回踩MA20支撑有效")
            elif trend_dir < 0 and cur_price < cur_ma20 and abs(cur_price - cur_ma20) / cur_ma20 < 0.02:
                score -= 1
                reasons.append("反弹受阻MA20")

        # --- 连阳/连阴 ---
        if len(prices) >= 5:
            consecutive_up = 0
            for i in range(-1, -6, -1):
                if abs(i) <= len(prices) and prices[i] > prices[i - 1]:
                    consecutive_up += 1
                else:
                    break
            consecutive_down = 0
            for i in range(-1, -6, -1):
                if abs(i) <= len(prices) and prices[i] < prices[i - 1]:
                    consecutive_down += 1
                else:
                    break

            if consecutive_up >= 3:
                score += 2 if consecutive_up >= 4 else 1
                reasons.append(f"{consecutive_up}连阳上攻")
            if consecutive_down >= 3:
                score -= 2 if consecutive_down >= 4 else 1
                reasons.append(f"{consecutive_down}连阴下杀")

        # --- 单日反转形态 ---
        if len(highs) >= 1 and len(lows) >= 1:
            cur_high = highs[-1] if highs else cur_price
            cur_low = lows[-1] if lows else cur_price
            cur_open = row.get('今开', cur_price)

            if cur_open > 0 and cur_high > cur_low:
                candle_range = cur_high - cur_low
                if candle_range > 0:
                    upper_shadow = cur_high - max(cur_open, cur_price)
                    lower_shadow = min(cur_open, cur_price) - cur_low
                    body = abs(cur_price - cur_open)

                    if lower_shadow > body * 2 and lower_shadow > upper_shadow * 2:
                        if trend_dir <= 0:
                            score += 2
                            reasons.append("长下影线 单针探底✨")
                        else:
                            score += 1
                            reasons.append("长下影线 支撑确认")
                    if upper_shadow > body * 2 and upper_shadow > lower_shadow * 2:
                        if trend_dir >= 0:
                            score -= 2
                            reasons.append("长上影线 射击之星⚠️")
                        else:
                            score -= 1
                            reasons.append("长上影线 反弹遇阻")

        # --- MA5/MA10/MA20 收敛检测 ---
        if cur_ma5 > 0 and cur_ma10 > 0 and cur_ma20 > 0:
            ma_values = [cur_ma5, cur_ma10, cur_ma20]
            ma_avg = sum(ma_values) / 3
            max_divergence = max(abs(v - ma_avg) for v in ma_values)
            convergence_ratio = max_divergence / ma_avg if ma_avg > 0 else 1

            if convergence_ratio < 0.01:
                reasons.append(f"MA5/10/20极度收敛(发散率{convergence_ratio * 100:.1f}%) 变盘在即")
                if cur_price > ma_avg:
                    score += 2
                    reasons.append("均线收敛+价格站上均线 向上变盘")
                    if trend_dir == 0:
                        trend_dir = 1
                else:
                    score -= 2
                    reasons.append("均线收敛+价格跌破均线 向下变盘")
                    if trend_dir == 0:
                        trend_dir = -1
            elif convergence_ratio < 0.02:
                reasons.append(f"MA5/10/20高度收敛(发散率{convergence_ratio * 100:.1f}%)")
                if cur_price > ma_avg:
                    score += 1
                    reasons.append("均线收敛偏多")
                else:
                    score -= 1
                    reasons.append("均线收敛偏空")

        return FactorResult(score, "；".join(reasons) if reasons else "", {'trend_dir': trend_dir})


class MacdSignal(BaseSignal):
    """因子2: MACD 信号（权重: ±5）。"""

    name = "MACD"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []

        code = row['代码']
        prices = ctx.prices(code)

        if len(prices) < 30:
            return FactorResult(0, "", {'macd_dif': 0, 'macd_dea': 0})

        dif, dea, macd_bar = ind.calc_macd(prices)
        if len(dif) < 3 or len(macd_bar) < 3:
            return FactorResult(0, "", {'macd_dif': 0, 'macd_dea': 0})

        cur_dif = dif[-1]
        cur_dea = dea[-1]
        prev_dif = dif[-2] if len(dif) >= 2 else cur_dif
        prev_dea = dea[-2] if len(dea) >= 2 else cur_dea
        cur_bar = macd_bar[-1]
        prev_bar = macd_bar[-2] if len(macd_bar) >= 2 else cur_bar

        # --- 背离判断 ---
        lookback = min(20, len(prices) - 1)
        price_high_20 = max(prices[-lookback - 1:-1])
        dif_high_20 = max([d for d in dif[-lookback - 1:-1] if d != 0] or [0])
        if prices[-1] > price_high_20 and cur_dif < dif_high_20 * 0.9:
            score -= 3
            reasons.append("⚠️MACD顶背离(价创新高DIF未创新高)")

        price_low_20 = min(prices[-lookback - 1:-1])
        dif_low_20 = min([d for d in dif[-lookback - 1:-1] if d != 0] or [float('inf')])
        if prices[-1] < price_low_20 and cur_dif > dif_low_20 * 1.1:
            score += 3
            reasons.append("✨MACD底背离(价创新低DIF未创新低)")

        # --- MACD柱连续变化 ---
        if len(macd_bar) >= 4:
            bar_3ago = macd_bar[-3]
            bar_4ago = macd_bar[-4] if len(macd_bar) >= 4 else bar_3ago

            if cur_bar < 0 and cur_bar > prev_bar and prev_bar > bar_3ago:
                shorten_streak = 2
                if bar_3ago > bar_4ago and bar_4ago < 0:
                    shorten_streak = 3
                if shorten_streak >= 3:
                    score += 2
                    reasons.append("MACD绿柱持续缩短-空方衰竭")
                elif trend_dir >= 0:
                    score += 1
                    reasons.append("MACD绿柱缩短")

            if cur_bar > 0 and cur_bar < prev_bar and prev_bar < bar_3ago:
                shorten_streak = 2
                if bar_3ago < bar_4ago and bar_4ago > 0:
                    shorten_streak = 3
                if shorten_streak >= 3:
                    score -= 2
                    reasons.append("MACD红柱持续缩短-多方衰竭")
                elif trend_dir <= 0:
                    score -= 1
                    reasons.append("MACD红柱缩短")

            if cur_bar > 0 and cur_bar > prev_bar > bar_3ago > 0:
                if trend_dir > 0:
                    score += 1
                    reasons.append("MACD红柱放大-多头加速")

            if cur_bar < 0 and cur_bar < prev_bar < bar_3ago < 0:
                if trend_dir < 0:
                    score -= 1
                    reasons.append("MACD绿柱放大-空头加速")

        # --- 金叉/死叉 ---
        if prev_dif <= prev_dea and cur_dif > cur_dea:
            if cur_dif < 0:
                score += 3
                reasons.append("DIF上穿DEA 零下金叉✨")
            else:
                score += 2
                reasons.append("DIF上穿DEA 金叉")
        elif prev_dif >= prev_dea and cur_dif < cur_dea:
            if cur_dif > 0:
                score -= 3
                reasons.append("DIF下穿DEA 零上死叉⚠️")
            else:
                score -= 2
                reasons.append("DIF下穿DEA 死叉")

        # --- MACD 方向与趋势一致性 ---
        if cur_dif > 0 and cur_dif > cur_dea and macd_bar[-1] > 0:
            if trend_dir >= 0:
                score += 1
                reasons.append("MACD多头运行")
        elif cur_dif < 0 and cur_dif < cur_dea and macd_bar[-1] < 0:
            if trend_dir <= 0:
                score -= 1
                reasons.append("MACD空头运行")

        return FactorResult(score, "；".join(reasons) if reasons else "",
                            {'macd_dif': cur_dif, 'macd_dea': cur_dea})


class KdjSignal(BaseSignal):
    """因子3: KDJ 信号（权重: ±2）。"""

    name = "KDJ"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []

        code = row['代码']
        prices = ctx.prices(code)
        highs = ctx.highs(code)
        lows = ctx.lows(code)

        if len(prices) < 9:
            return FactorResult(0, "", {})

        prev_k, prev_d = ctx.kdj_state.prev_value(code)
        k, d, j = ctx.kdj_state.calc(code, prices, highs, lows)

        if j < 0:
            if trend_dir >= 0:
                score += 2
                reasons.append(f"KDJ超卖(J={j:.1f})")
            else:
                score += 1
                reasons.append(f"KDJ超卖钝化(J={j:.1f})")
        elif j < 20:
            if trend_dir >= 0:
                score += 1
                reasons.append(f"KDJ低位(J={j:.1f})")

        if j > 100:
            if trend_dir <= 0:
                score -= 2
                reasons.append(f"KDJ超买(J={j:.1f})")
            else:
                score -= 1
                reasons.append(f"KDJ超买钝化(J={j:.1f})")
        elif j > 80:
            if trend_dir <= 0:
                score -= 1
                reasons.append(f"KDJ高位(J={j:.1f})")

        if prev_k <= prev_d and k > d and j < 20:
            score += 2
            reasons.append("KDJ低位金叉✨")
        elif prev_k >= prev_d and k < d and j > 80:
            if trend_dir <= 0:
                score -= 2
                reasons.append("KDJ高位死叉⚠️")
            else:
                score -= 1
                reasons.append("KDJ高位死叉(强势回调)")

        return FactorResult(score, "；".join(reasons) if reasons else "",
                            {'kdj_k': k, 'kdj_d': d, 'kdj_j': j})


class RsiSignal(BaseSignal):
    """因子4: RSI 信号（权重: ±2）。"""

    name = "RSI"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []

        code = row['代码']
        prices = ctx.prices(code)

        if len(prices) < 15:
            return FactorResult(0, "", {'rsi': 50})

        rsi = ind.calc_rsi(prices)

        if rsi <= 20:
            if trend_dir >= 0:
                score += 3
                reasons.append(f"RSI严重超卖({rsi:.1f})✨")
            else:
                score += 1
                reasons.append(f"RSI严重超卖钝化({rsi:.1f})")
        elif rsi <= 30:
            if trend_dir >= 0:
                score += 2
                reasons.append(f"RSI超卖({rsi:.1f})")
            else:
                score += 1
                reasons.append(f"RSI超卖({rsi:.1f})")
        elif rsi <= 35:
            if trend_dir >= 0:
                score += 1
                reasons.append(f"RSI偏低({rsi:.1f})")

        if rsi >= 80:
            if trend_dir <= 0:
                score -= 3
                reasons.append(f"RSI严重超买({rsi:.1f})⚠️")
            else:
                score -= 1
                reasons.append(f"RSI严重超买-强势({rsi:.1f})")
        elif rsi >= 70:
            if trend_dir <= 0:
                score -= 2
                reasons.append(f"RSI超买({rsi:.1f})")
        elif rsi >= 65:
            if trend_dir <= 0:
                score -= 1
                reasons.append(f"RSI偏高({rsi:.1f})")

        # RSI 背离检测（简化版）
        if len(prices) >= 16:
            lookback_prices = prices[-15:-1]
            if prices[-1] > max(lookback_prices) and rsi < 65:
                score -= 1
                reasons.append(f"RSI顶背离({rsi:.1f})")
            if prices[-1] < min(lookback_prices) and rsi > 35:
                score += 1
                reasons.append(f"RSI底背离({rsi:.1f})")

        return FactorResult(score, "；".join(reasons) if reasons else "", {'rsi': rsi})


class BollingerSignal(BaseSignal):
    """因子5: 布林带信号（权重: ±2）。"""

    name = "布林"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []

        code = row['代码']
        prices = ctx.prices(code)
        cur_price = prices[-1] if prices else 0

        if len(prices) < 21:
            return FactorResult(0, "", {'boll_mid': 0, 'boll_bandwidth': 0})

        mid, upper, lower, bandwidth = ind.calc_bollinger(prices)
        if mid == 0:
            return FactorResult(0, "", {'boll_mid': 0, 'boll_bandwidth': 0})

        pct_b = (cur_price - lower) / (upper - lower) if upper > lower else 0.5

        if cur_price > upper:
            if trend_dir > 0:
                score += 2
                reasons.append("突破布林上轨 强势加速")
            else:
                score -= 1
                reasons.append("突破布林上轨 警惕回落")

        if cur_price < lower:
            if trend_dir < 0:
                score -= 2
                reasons.append("跌破布林下轨 弱势加速")
            else:
                score += 1
                reasons.append("跌破布林下轨 超卖反弹")

        if pct_b > 0.8 and trend_dir > 0:
            if len(prices) >= 3:
                mid_vals = ind.calc_sma(prices, 20)
                if mid_vals and len(mid_vals) >= 3:
                    b_vals = []
                    for i in range(-3, 0):
                        m = mid_vals[i]
                        if m > 0:
                            est_upper = m * 1.05
                            est_lower = m * 0.95
                            if est_upper > est_lower:
                                b_vals.append((prices[i] - est_lower) / (est_upper - est_lower))
                    if len(b_vals) >= 3 and all(b > 0.75 for b in b_vals):
                        score += 1
                        reasons.append("沿布林上轨运行 极强势")

        if pct_b < 0.2 and trend_dir < 0:
            score -= 1
            reasons.append("沿布林下轨运行 极弱势")

        if bandwidth < 5:
            if trend_dir > 0:
                score += 1
                reasons.append(f"布林带宽收窄({bandwidth:.1f}%) 蓄势向上")
            elif trend_dir < 0:
                score -= 1
                reasons.append(f"布林带宽收窄({bandwidth:.1f}%) 警惕下破")
            else:
                reasons.append(f"布林带宽收窄({bandwidth:.1f}%) 即将变盘")

        if bandwidth > 15:
            if trend_dir > 0:
                score += 1
                reasons.append(f"布林带宽扩张({bandwidth:.1f}%) 趋势加速")
            elif trend_dir < 0:
                score -= 1
                reasons.append(f"布林带宽扩张({bandwidth:.1f}%) 下跌加速")

        return FactorResult(score, "；".join(reasons) if reasons else "",
                            {'boll_mid': mid, 'boll_bandwidth': bandwidth})


class VolumeSignal(BaseSignal):
    """因子6: 成交量信号（权重: ±3）。"""

    name = "量能"

    def evaluate(self, row, ctx: IndicatorContext, trend_dir: int = 0) -> FactorResult:
        score = 0
        reasons = []

        code = row['代码']
        volume = row.get('成交量', 0)
        change_pct = row.get('涨跌幅', 0)

        if volume == 0:
            return FactorResult(0, "", {'volume_ratio': 0})

        avg_vol = None
        vols = ctx.daily_volumes(code)
        if vols:
            avg_vol = sum(vols) / len(vols)

        vol_ratio = 0
        if avg_vol and avg_vol > 0:
            vol_ratio = volume / avg_vol

            # --- 连续缩量后放量（地量见地价）---
            hist = ctx._daily_history.get(code)
            if hist and len(hist) >= 5:
                daily_vols = [h.get('volume', 0) for h in list(hist)[-6:-1]]
                if len(daily_vols) >= 4 and all(daily_vols[i] > 0 for i in range(len(daily_vols))):
                    is_shrinking = all(daily_vols[i] < daily_vols[i - 1] * 0.9 for i in range(1, len(daily_vols)))
                    if is_shrinking and vol_ratio >= 1.5:
                        if change_pct > 0:
                            score += 3
                            reasons.append("连续缩量后放量上攻 地量见地价✨")
                        elif change_pct < 0:
                            score -= 2
                            reasons.append("连续缩量后放量下杀 方向选择向下")

            # --- 量堆识别 ---
            hist = ctx._daily_history.get(code)
            if hist and len(hist) >= 4:
                recent_vols = [h.get('volume', 0) for h in list(hist)[-4:]]
                if len(recent_vols) >= 3:
                    all_above_avg = all(v > avg_vol * 1.2 for v in recent_vols if v > 0)
                    if all_above_avg and trend_dir > 0:
                        score += 2
                        reasons.append("量堆形成 资金持续介入")

            # --- 放量上涨/下跌/滞涨/缩量 ---
            if vol_ratio >= 2 and change_pct > 0:
                if trend_dir >= 0:
                    score += 2
                    reasons.append(f"放量上涨(量比{vol_ratio:.1f})")
                else:
                    score += 1
                    reasons.append(f"放量反弹(量比{vol_ratio:.1f})")
            elif vol_ratio >= 2 and change_pct < 0:
                if trend_dir <= 0:
                    score -= 2
                    reasons.append(f"放量下跌(量比{vol_ratio:.1f})")
                else:
                    score -= 1
                    reasons.append(f"放量回调(量比{vol_ratio:.1f})")
            elif vol_ratio >= 2 and abs(change_pct) < 0.5:
                score -= 3
                reasons.append(f"放量滞涨⚠️(量比{vol_ratio:.1f})")
            elif vol_ratio <= 0.6 and change_pct < 0:
                if trend_dir >= 0:
                    score += 1
                    reasons.append(f"缩量下跌-洗盘(量比{vol_ratio:.1f})")
            elif vol_ratio >= 1.5 and change_pct > 0:
                if trend_dir >= 0:
                    score += 1
                    reasons.append(f"温和放量(量比{vol_ratio:.1f})")
            elif vol_ratio <= 0.6 and change_pct > 1:
                if trend_dir < 0:
                    score -= 1
                    reasons.append(f"缩量上涨-量价背离(量比{vol_ratio:.1f})")

        return FactorResult(score, "；".join(reasons) if reasons else "",
                            {'volume_ratio': vol_ratio})
