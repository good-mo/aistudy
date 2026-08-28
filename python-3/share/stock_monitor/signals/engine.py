"""综合多因子评分引擎：汇总各因子信号，生成买卖信号。"""

from typing import Dict, List, Tuple

from common.logging_utils import get_logger
from stock_monitor.config import SignalParams
from stock_monitor.signals.factors import (
    BaseSignal,
    BollingerSignal,
    IndicatorContext,
    KdjSignal,
    MaSignal,
    MacdSignal,
    RsiSignal,
    VolumeSignal,
)

logger = get_logger(__name__)


class SignalEngine:
    """多因子综合评分引擎。

    因子权重：
      MA均线:  ±6  (排列/交叉/支撑阻力/K线形态/均线收敛) — 趋势核心
      MACD:    ±5  (金叉/死叉/背离/零轴/柱变化) — 趋势确认
      KDJ:     ±2  (超买/超卖/交叉) — 辅助，趋势过滤
      RSI:     ±2  (超买/超卖/背离) — 辅助，趋势过滤
      布林带:   ±2  (突破/带宽/沿轨运行) — 极端位置判断
      成交量:   ±3  (放量/缩量/量堆/地量) — 确认（最不可操控指标）
    """

    FACTOR_CLASSES = [
        MaSignal,
        MacdSignal,
        KdjSignal,
        RsiSignal,
        BollingerSignal,
        VolumeSignal,
    ]

    def __init__(self, params: SignalParams):
        self.params = params
        self._factors: List[BaseSignal] = [cls(params) for cls in self.FACTOR_CLASSES]

    def calculate(self, row, ctx: IndicatorContext, market_trend: int = 0) -> Tuple[int, str, List[str], dict]:
        """对单只股票计算综合评分。

        Args:
            row: 实时行情 DataFrame 的一行
            ctx: 指标上下文（历史数据 + KDJ 状态）
            market_trend: 大盘趋势（1 多 / -1 空 / 0 震荡），0 表示不适用

        Returns:
            (总分, 信号等级, 详细原因列表, 指标值字典)
        """
        total_score = 0
        all_reasons = []
        indicators = {}

        # === 第一层：趋势方向判断（MA 因子） ===
        ma_result = self._factors[0].evaluate(row, ctx)
        trend_dir = ma_result.data.get('trend_dir', 0)
        total_score += ma_result.score
        if ma_result.reason:
            all_reasons.append(f"[MA]{ma_result.reason}")
        indicators['ma_direction'] = trend_dir

        # === 第二~六层：其余因子 ===
        for factor in self._factors[1:]:
            result = factor.evaluate(row, ctx, trend_dir)
            total_score += result.score
            if result.reason:
                all_reasons.append(f"[{factor.name}]{result.reason}")
            indicators.update(result.data or {})

        # === 信号共振加成 ===
        total_score, all_reasons = self._resonance_bonus(total_score, all_reasons)

        # === 时间衰减：旧K线形态信号 ===
        total_score, all_reasons = self._time_decay(total_score, all_reasons)

        # === 大盘环境加成 ===

        if market_trend != 0:
            total_score, all_reasons = self._market_adjust(total_score, all_reasons, market_trend)

        # === 多空冲突检测：趋势方向优先 ===
        if trend_dir > 0 and total_score <= 0:
            total_score = max(total_score, 0)
        elif trend_dir < 0 and total_score >= 0:
            total_score = min(total_score, 0)

        level = self._level(total_score)
        logger.debug("信号引擎[%s] 综合评分 %+d 等级:%s 因子:%d个",
                     row['代码'], total_score, level, len(all_reasons))
        return total_score, level, all_reasons, indicators

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _resonance_bonus(self, total_score: int, all_reasons: List[str]):
        """多因子共振加成。"""
        seen_factors = set()
        for r in all_reasons:
            for prefix in ['[MA]', '[MACD]', '[KDJ]', '[RSI]', '[布林]', '[量能]']:
                if r.startswith(prefix) and prefix not in seen_factors:
                    seen_factors.add(prefix)
                    break

        if len(seen_factors) >= 3:
            if total_score > 0:
                bonus = min(len(seen_factors) - 2, 3)
                total_score += bonus
                all_reasons.append(f"[共振]{len(seen_factors)}因子共振看多 +{bonus}")
            elif total_score < 0:
                bonus = min(len(seen_factors) - 2, 3)
                total_score -= bonus
                all_reasons.append(f"[共振]{len(seen_factors)}因子共振看空 -{bonus}")
        return total_score, all_reasons

    def _time_decay(self, total_score: int, all_reasons: List[str]):
        """对旧K线形态信号进行时间衰减。"""
        time_sensitive_signals = ['连阳', '连阴', '长下影', '长上影']
        has_time_sensitive = any(
            any(kw in r for kw in time_sensitive_signals) for r in all_reasons
        )
        if has_time_sensitive:
            for r in all_reasons:
                if '4连阳' in r or '4连阴' in r:
                    if total_score > 0:
                        total_score -= 1
                    elif total_score < 0:
                        total_score += 1
                    all_reasons.append("[衰减]多日前K线形态信号时间衰减")
                    break
        return total_score, all_reasons

    def _market_adjust(self, total_score: int, all_reasons: List[str], market_trend: int):
        """大盘环境加成。"""
        if market_trend > 0 and total_score > 0:
            total_score += 2
            all_reasons.append("[大盘]大盘强势 信号加成")
        elif market_trend < 0 and total_score < 0:
            total_score -= 2
            all_reasons.append("[大盘]大盘弱势 信号加成")
        elif market_trend < 0 and total_score > 0:
            total_score += 2
            all_reasons.append("[大盘]逆势走强 强于大盘")
        elif market_trend > 0 and total_score < 0:
            total_score -= 2
            all_reasons.append("[大盘]逆势走弱 弱于大盘")
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

    def market_trend_for(self, code: str, ctx: IndicatorContext, watch_list: Dict[str, str]) -> int:
        """计算大盘（沪深300）趋势方向，用于个股信号加成。

        返回 1 多 / -1 空 / 0 震荡或不可用。
        """
        if '000300' not in watch_list or code == '000300':
            return 0

        market_prices = ctx.prices('000300')
        if len(market_prices) < 22:
            return 0

        from stock_monitor.indicators import calc_sma
        market_ma20 = calc_sma(market_prices, 20)
        if not market_ma20 or market_ma20[-1] <= 0:
            return 0

        if market_prices[-1] > market_ma20[-1]:
            logger.debug("大盘[000300] 趋势向上，个股[%s] 加成", code)
            return 1
        elif market_prices[-1] < market_ma20[-1]:
            logger.debug("大盘[000300] 趋势向下，个股[%s] 加成", code)
            return -1
        return 0
