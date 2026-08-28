"""技术指标计算：EMA / SMA / MACD / KDJ / RSI / 布林带。

均为纯函数式计算，不持有状态，便于单元测试与复用。
KDJ 因为需要前一周期递归值，额外提供一个有状态的辅助类 KdjState。
"""

from typing import List, Tuple

from common.logging_utils import get_logger

logger = get_logger(__name__)


def calc_sma(data: List[float], period: int) -> List[float]:
    """计算简单移动平均 SMA，前 period-1 位补 0。"""
    if len(data) < period:
        return []
    sma = []
    for i in range(len(data)):
        if i < period - 1:
            sma.append(0)
        else:
            sma.append(sum(data[i - period + 1:i + 1]) / period)
    return sma


def calc_ema(data: List[float], period: int) -> List[float]:
    """计算指数移动平均 EMA，前 period-1 位补 0。"""
    if len(data) < period:
        return []
    k = 2 / (period + 1)
    ema = [sum(data[:period]) / period]  # 初始值用 SMA
    for price in data[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return [0] * (period - 1) + ema  # 补齐前面空位


def calc_macd(
    prices: List[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[List[float], List[float], List[float]]:
    """计算 MACD 指标，返回 (DIF, DEA, MACD柱)。"""
    if len(prices) < slow:
        return [], [], []
    ema_fast = calc_ema(prices, fast)
    ema_slow = calc_ema(prices, slow)

    # DIF = EMA快 - EMA慢
    # 用索引判断有效性，避免真值判断误伤 0.0
    dif = []
    for i, (f, s) in enumerate(zip(ema_fast, ema_slow)):
        if i < slow - 1:
            dif.append(0.0)  # 前导无效部分
        else:
            dif.append(f - s)

    # 对 DIF 的有效部分计算 DEA（从 slow-1 位置开始才有意义）
    valid_start = slow - 1  # EMA慢线从 slow-1 位置开始有效
    valid_dif = dif[valid_start:]  # 去掉前导的无效部分

    if len(valid_dif) < signal:
        dea = [0] * len(dif)
        macd_bar = [0] * len(dif)
        return dif, dea, macd_bar

    dea_vals = calc_ema(valid_dif, signal)
    # DEA补齐到与DIF等长
    dea = [0] * valid_start + dea_vals

    macd_bar = [(dif[i] - dea[i]) * 2 for i in range(len(dif))]
    return dif, dea, macd_bar


class KdjState:
    """KDJ 指标的有状态计算器（需要前一周期 K/D 递归值）。"""

    def __init__(self):
        self._prev: dict = {}

    def calc(self, code: str, prices: List[float],
             highs: List[float], lows: List[float], n: int = 9) -> Tuple[float, float, float]:
        """计算 (K, D, J) 当前值。"""
        if len(prices) < n:
            return 50, 50, 50

        recent_prices = prices[-n:]
        recent_highs = highs[-n:] if len(highs) >= n else prices[-n:]
        recent_lows = lows[-n:] if len(lows) >= n else prices[-n:]

        # 计算 RSV
        hn = max(recent_highs)
        ln = min(recent_lows)
        cn = recent_prices[-1]

        if hn == ln:
            rsv = 50
        else:
            rsv = (cn - ln) / (hn - ln) * 100

        prev = self._prev.get(code, {'k': 50, 'd': 50})
        k = 2 / 3 * prev['k'] + 1 / 3 * rsv
        d = 2 / 3 * prev['d'] + 1 / 3 * k
        j = 3 * k - 2 * d

        self._prev[code] = {'k': k, 'd': d}
        return k, d, j

    def prev_value(self, code: str) -> Tuple[float, float]:
        """返回某只股票上一次的 (K, D)，用于交叉判断。"""
        prev = self._prev.get(code, {'k': 50, 'd': 50})
        return prev.get('k', 50), prev.get('d', 50)


def calc_rsi(prices: List[float], period: int = 14) -> float:
    """计算 RSI 指标。"""
    if len(prices) < period + 1:
        return 50

    gains = []
    losses = []
    for i in range(-period, 0):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_bollinger(
    prices: List[float], period: int = 20, std_dev: int = 2
) -> Tuple[float, float, float, float]:
    """计算布林带，返回 (中轨MA, 上轨, 下轨, 带宽百分比)。"""
    if len(prices) < period:
        return 0, 0, 0, 0

    ma = calc_sma(prices, period)
    if not ma or ma[-1] == 0:
        return 0, 0, 0, 0

    mid = ma[-1]
    recent = prices[-period:]
    mean = sum(recent) / period
    variance = sum((x - mean) ** 2 for x in recent) / period
    std = variance ** 0.5

    upper = mid + std_dev * std
    lower = mid - std_dev * std
    bandwidth = (upper - lower) / mid * 100 if mid > 0 else 0

    return mid, upper, lower, bandwidth
