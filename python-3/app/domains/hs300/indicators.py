"""
app.domains.hs300.indicators —— 技术指标计算器

从原始 share300/hs300_analyzer.py 提炼 9 大技术指标实现，
统一接入 app.data 数据层。
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from app.core.logging_setup import get_logger

logger = get_logger(__name__)


class TechnicalAnalyzer:
    """技术指标计算器（自包含实现，覆盖 9 大指标）。"""

    # 指标权重（MACD/背离 和 形态识别 权重最高）
    WEIGHTS = {
        "MA": 1.0, "MACD": 1.5, "KDJ": 1.0, "RSI": 1.0,
        "VOL": 0.5, "BOLL": 0.8, "SR": 0.5,
        "CANDLE": 0.8, "PATTERN": 1.2,
    }

    # ------------------------------------------------------------------
    # 基础指标计算
    # ------------------------------------------------------------------

    def calc_ma(self, df: pd.DataFrame, periods=(5, 10, 20, 60)) -> pd.DataFrame:
        for p in periods:
            df[f"ma{p}"] = df["close"].rolling(window=p).mean()
        return df

    def calc_macd(self, df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
        ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
        df["DIF"] = ema_fast - ema_slow
        df["DEA"] = df["DIF"].ewm(span=signal, adjust=False).mean()
        df["MACD"] = (df["DIF"] - df["DEA"]) * 2
        return df

    def calc_kdj(self, df: pd.DataFrame, n=9, m1=3, m2=3) -> pd.DataFrame:
        low_n = df["low"].rolling(window=n, min_periods=1).min()
        high_n = df["high"].rolling(window=n, min_periods=1).max()
        rsv = (df["close"] - low_n) / (high_n - low_n).replace(0, 1e-10) * 100
        df["K"] = rsv.ewm(alpha=1 / m1, adjust=False).mean()
        df["D"] = df["K"].ewm(alpha=1 / m2, adjust=False).mean()
        df["J"] = 3 * df["K"] - 2 * df["D"]
        return df

    def calc_rsi(self, df: pd.DataFrame, periods=(6, 12, 24)) -> pd.DataFrame:
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        for p in periods:
            avg_gain = gain.rolling(window=p, min_periods=1).mean()
            avg_loss = loss.rolling(window=p, min_periods=1).mean()
            rs = avg_gain / avg_loss.replace(0, 1e-10)
            df[f"RSI{p}"] = 100 - (100 / (1 + rs))
        return df

    def calc_volume_ma(self, df: pd.DataFrame, periods=(5, 20)) -> pd.DataFrame:
        for p in periods:
            df[f"VOL_MA{p}"] = df["volume"].rolling(window=p).mean()
        return df

    def calc_boll(self, df: pd.DataFrame, period=20, std_mult=2.0) -> pd.DataFrame:
        mid = df["close"].rolling(window=period).mean()
        std = df["close"].rolling(window=period).std()
        df["BOLL_MID"] = mid
        df["BOLL_UP"] = mid + std_mult * std
        df["BOLL_LOW"] = mid - std_mult * std
        return df

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算全部指标。"""
        df = self.calc_ma(df)
        df = self.calc_macd(df)
        df = self.calc_kdj(df)
        df = self.calc_rsi(df)
        df = self.calc_volume_ma(df)
        df = self.calc_boll(df)
        return df

    # ------------------------------------------------------------------
    # 单指标信号
    # ------------------------------------------------------------------

    def _safe(self, df, col, default=0.0):
        if col in df.columns and not df[col].isna().iloc[-1]:
            return float(df[col].iloc[-1])
        return default

    def _ma_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        score = 0.0
        signals = []
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        ma5, ma10, ma20 = (
            self._safe(df, "ma5"), self._safe(df, "ma10"), self._safe(df, "ma20")
        )
        price = float(latest["close"])
        prev_ma5 = self._safe(df.iloc[:-1], "ma5") if len(df) > 1 else ma5

        if ma5 > ma10 > ma20:
            score += 3
            signals.append("多头排列")
        elif ma5 < ma10 < ma20:
            score -= 3
            signals.append("空头排列")
        else:
            if price > ma20:
                score += 1
                signals.append("站上MA20")
            elif price < ma20:
                score -= 1
                signals.append("跌破MA20")

        if prev_ma5 < self._safe(df.iloc[:-1], "ma10") and ma5 > ma10:
            score += 2
            signals.append("MA金叉")
        elif prev_ma5 > self._safe(df.iloc[:-1], "ma10") and ma5 < ma10:
            score -= 2
            signals.append("MA死叉")

        return "；".join(signals) if signals else "", score

    def _macd_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        score = 0.0
        signals = []
        dif = self._safe(df, "DIF")
        dea = self._safe(df, "DEA")
        macd = self._safe(df, "MACD")
        prev_dif = self._safe(df.iloc[:-1], "DIF") if len(df) > 1 else dif
        prev_dea = self._safe(df.iloc[:-1], "DEA") if len(df) > 1 else dea

        if prev_dif <= prev_dea and dif > dea:
            score += 3
            signals.append("MACD金叉")
        elif prev_dif >= prev_dea and dif < dea:
            score -= 3
            signals.append("MACD死叉")
        if dif > 0 and dif > dea and macd > 0:
            score += 1
            signals.append("MACD多头")
        elif dif < 0 and dif < dea and macd < 0:
            score -= 1
            signals.append("MACD空头")

        return "；".join(signals) if signals else "", score

    def _kdj_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        score = 0.0
        signals = []
        k, d, j = (
            self._safe(df, "K"), self._safe(df, "D"), self._safe(df, "J")
        )
        if j < 20:
            score += 2
            signals.append("KDJ超卖")
        elif j > 80:
            score -= 2
            signals.append("KDJ超买")
        if k > d:
            score += 0.5
        else:
            score -= 0.5
        return "；".join(signals) if signals else "", score

    def _rsi_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        score = 0.0
        signals = []
        rsi6 = self._safe(df, "RSI6", 50)
        if rsi6 < 30:
            score += 2
            signals.append("RSI超卖")
        elif rsi6 > 70:
            score -= 2
            signals.append("RSI超买")
        return "；".join(signals) if signals else "", score

    def _volume_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        score = 0.0
        signals = []
        vol = self._safe(df, "volume")
        vol_ma = self._safe(df, "VOL_MA5")
        change_pct = self._calc_change_pct(df)
        if vol_ma and vol > vol_ma * 1.5 and change_pct > 0:
            score += 1
            signals.append("放量上涨")
        elif vol_ma and vol > vol_ma * 1.5 and change_pct < 0:
            score -= 1
            signals.append("放量下跌")
        elif vol_ma and vol < vol_ma * 0.6:
            signals.append("缩量")
        return "；".join(signals) if signals else "", score

    def _boll_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        score = 0.0
        signals = []
        price = float(df.iloc[-1]["close"])
        up = self._safe(df, "BOLL_UP")
        low = self._safe(df, "BOLL_LOW")
        if up and price > up:
            score += 1
            signals.append("突破布林上轨")
        elif low and price < low:
            score -= 1
            signals.append("跌破布林下轨")
        return "；".join(signals) if signals else "", score

    def _support_resistance_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        score = 0.0
        signals = []
        if len(df) < 30:
            return "", 0.0
        price = float(df.iloc[-1]["close"])
        recent = df.iloc[-21:-1]
        recent_high = float(recent["high"].max())
        recent_low = float(recent["low"].min())
        if price > recent_high * 1.005:
            score += 1
            signals.append("突破前高")
        elif price < recent_low * 0.995:
            score -= 1
            signals.append("跌破前低")
        return "；".join(signals) if signals else "", score

    def _candlestick_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """K线组合形态信号。"""
        score = 0.0
        signals = []
        if len(df) < 3:
            return "", 0.0
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        open_, close = float(latest["open"]), float(latest["close"])
        high, low = float(latest["high"]), float(latest["low"])
        body = abs(close - open_)
        rng = high - low
        if rng <= 0:
            return "", 0.0

        lower_shadow = min(open_, close) - low
        upper_shadow = high - max(open_, close)
        # 长下影线
        if lower_shadow > body * 2 and lower_shadow > upper_shadow * 2:
            score += 2
            signals.append("长下影线")
        # 长上影线
        if upper_shadow > body * 2 and upper_shadow > lower_shadow * 2:
            score -= 2
            signals.append("长上影线")
        # 连续阳线/阴线
        closes = df["close"].tail(5).tolist()
        if len(closes) >= 4:
            if all(closes[i] > closes[i - 1] for i in range(1, len(closes))):
                score += 1
                signals.append("连阳")
            elif all(closes[i] < closes[i - 1] for i in range(1, len(closes))):
                score -= 1
                signals.append("连阴")
        return "；".join(signals) if signals else "", score

    def _pattern_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """价格形态识别（W底/M头/三角形）。"""
        score = 0.0
        signals = []
        if len(df) < 20:
            return "", 0.0
        recent = df["close"].tail(20)
        low_left = float(recent.iloc[:10].min())
        low_right = float(recent.iloc[10:].min())
        high_left = float(recent.iloc[:10].max())
        high_right = float(recent.iloc[10:].max())
        # W 底
        if abs(low_left - low_right) / max(low_left, 1) < 0.03:
            score += 1
            signals.append("疑似W底")
        # M 头
        if abs(high_left - high_right) / max(high_left, 1) < 0.03:
            score -= 1
            signals.append("疑似M头")
        return "；".join(signals) if signals else "", score

    def _calc_change_pct(self, df: pd.DataFrame) -> float:
        if len(df) < 2:
            return 0.0
        return (float(df.iloc[-1]["close"]) - float(df.iloc[-2]["close"])) / float(
            df.iloc[-2]["close"]
        ) * 100

    # ------------------------------------------------------------------
    # 综合分析
    # ------------------------------------------------------------------

    def analyze(self, df: pd.DataFrame) -> dict:
        """综合分析，返回各指标信号和综合评分。"""
        if df is None or len(df) < 30:
            return self._empty_result()

        signals = {}
        scores = {}
        signals["MA"], scores["MA"] = self._ma_signal(df)
        signals["MACD"], scores["MACD"] = self._macd_signal(df)
        signals["KDJ"], scores["KDJ"] = self._kdj_signal(df)
        signals["RSI"], scores["RSI"] = self._rsi_signal(df)
        signals["VOL"], scores["VOL"] = self._volume_signal(df)
        signals["BOLL"], scores["BOLL"] = self._boll_signal(df)
        signals["SR"], scores["SR"] = self._support_resistance_signal(df)
        signals["CANDLE"], scores["CANDLE"] = self._candlestick_signal(df)
        signals["PATTERN"], scores["PATTERN"] = self._pattern_signal(df)

        total_score = sum(scores[k] * self.WEIGHTS[k] for k in scores)
        if total_score >= 4.5:
            advice, level = "强烈买入", 5
        elif total_score >= 2.5:
            advice, level = "建议买入", 4
        elif total_score <= -4.5:
            advice, level = "强烈卖出", 1
        elif total_score <= -2.5:
            advice, level = "建议卖出", 2
        else:
            advice, level = "观望", 3

        latest = df.iloc[-1]
        return {
            "signals": signals,
            "scores": scores,
            "total_score": total_score,
            "advice": advice,
            "level": level,
            "price": float(latest["close"]),
            "change_pct": self._calc_change_pct(df),
            "rsi": self._safe(df, "RSI6", 50),
            "kdj_j": self._safe(df, "J", 50),
        }

    def _empty_result(self) -> dict:
        return {
            "signals": {}, "scores": {},
            "total_score": 0, "advice": "数据不足", "level": 0,
            "price": 0, "change_pct": 0, "rsi": 50, "kdj_j": 50,
        }
