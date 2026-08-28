"""
app 专业分析师扩展模块（P0-P2） 单元测试。

验证：
    - P0-1 基本面指标模块（估值分位/贵贱判断）
    - P0-2 资金面模块（北向/主力/评分）
    - P1-1 市场情绪模块（宽度/情绪评分）
    - P1-2 高级技术指标模块（ATR/ADX/OBV/BIAS/缺口）
    - P2-1 宏观利率模块（M1/M2/国债收益率/环境判断）
    - P2-2 风险组合模块（Beta/波动率/VaR/相关性）
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _make_kline_df(n=120, seed=42, start=100.0):
    """构造一份合成日 K 线 DataFrame。"""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = np.cumprod(1 + rng.normal(0, 0.01, n)) * start
    open_ = np.roll(close, 1) * (1 + rng.normal(0, 0.005, n))
    open_[0] = close[0]
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, n)))
    volume = rng.integers(10000, 100000, n).astype(float)
    return pd.DataFrame({
        "date": dates,
        "open": open_,
        "close": close,
        "high": high,
        "low": low,
        "volume": volume,
    })


# ---------------------------------------------------------------------------
# P1-2 高级技术指标
# ---------------------------------------------------------------------------

class TestAdvancedIndicators:
    def test_atr_positive(self):
        from app.domains.stock_watch.advanced_indicators import _calc_atr
        df = _make_kline_df()
        atr = _calc_atr(df)
        assert atr is not None and atr > 0

    def test_adx_range(self):
        from app.domains.stock_watch.advanced_indicators import _calc_adx
        df = _make_kline_df()
        adx = _calc_adx(df)
        assert adx is None or 0 <= adx <= 100

    def test_obv_trend(self):
        from app.domains.stock_watch.advanced_indicators import _calc_obv
        df = _make_kline_df()
        obv, trend = _calc_obv(df)
        assert obv is not None
        assert trend in ("上涨", "下跌", "持平")

    def test_bias_returns_state(self):
        from app.domains.stock_watch.advanced_indicators import _calc_bias
        df = _make_kline_df()
        bias, state = _calc_bias(df)
        assert bias is not None
        assert state in ("超买", "超卖", "偏高", "偏低", "合理")

    def test_gap_detection(self):
        from app.domains.stock_watch.advanced_indicators import _detect_gaps
        df = _make_kline_df()
        gaps, unfilled = _detect_gaps(df)
        assert gaps >= 0 and unfilled >= 0

    def test_analyze_full(self):
        from app.domains.stock_watch.advanced_indicators import analyze_advanced_indicators
        import app.domains.stock_watch.advanced_indicators as adv_mod
        # monkeypatch get_kline_df 引用（模块内直接引用）
        orig = adv_mod.get_kline_df
        adv_mod.get_kline_df = lambda code, days=120, **kw: _make_kline_df()
        try:
            snap = analyze_advanced_indicators("TEST", "测试")
            assert snap.code == "TEST"
            assert snap.atr is not None
            assert snap.adx is not None
            assert snap.obv is not None
        finally:
            adv_mod.get_kline_df = orig


# ---------------------------------------------------------------------------
# P2-2 风险组合
# ---------------------------------------------------------------------------

class TestRisk:
    def test_beta(self):
        from app.domains.stock_watch.risk import _calc_beta
        df = _make_kline_df(seed=1)
        df2 = _make_kline_df(seed=2)
        ret1 = df["close"].pct_change().dropna()
        ret2 = df2["close"].pct_change().dropna()
        beta = _calc_beta(ret1, ret2)
        assert beta is not None

    def test_volatility(self):
        from app.domains.stock_watch.risk import _calc_volatility
        df = _make_kline_df()
        ret = df["close"].pct_change().dropna()
        vol = _calc_volatility(ret)
        assert vol is not None and 0 < vol < 200

    def test_var(self):
        from app.domains.stock_watch.risk import _calc_var
        df = _make_kline_df()
        ret = df["close"].pct_change().dropna()
        var95 = _calc_var(ret, 0.95)
        var99 = _calc_var(ret, 0.99)
        assert var95 is not None and var95 > 0
        assert var99 is not None and var99 >= var95

    def test_max_drawdown(self):
        from app.domains.stock_watch.risk import _calc_max_drawdown
        df = _make_kline_df()
        mdd = _calc_max_drawdown(df["close"])
        assert mdd is not None and mdd <= 0

    def test_analyze_risk(self):
        from app.domains.stock_watch.risk import analyze_risk
        import app.domains.stock_watch.risk as risk_mod
        orig_kline = risk_mod.get_kline_df
        risk_mod.get_kline_df = lambda code, days=250, **kw: _make_kline_df(n=250)
        orig_idx = risk_mod.get_index_close_series
        risk_mod.get_index_close_series = lambda code, days=250, **kw: \
            [(str(d.date()), c) for d, c in zip(
                pd.date_range("2024-01-01", periods=250, freq="D"),
                _make_kline_df(n=250)["close"])]
        try:
            snap = analyze_risk("TEST", "测试")
            assert snap.annual_volatility is not None
            assert snap.var_95 is not None
        finally:
            risk_mod.get_kline_df = orig_kline
            risk_mod.get_index_close_series = orig_idx

    def test_correlation_matrix(self):
        from app.domains.stock_watch.risk import correlation_matrix
        import app.domains.stock_watch.risk as risk_mod
        orig_kline = risk_mod.get_kline_df
        risk_mod.get_kline_df = lambda code, days=250, **kw: _make_kline_df(n=250)
        orig_idx = risk_mod.get_index_close_series
        risk_mod.get_index_close_series = lambda code, days=250, **kw: \
            [(str(d.date()), c) for d, c in zip(
                pd.date_range("2024-01-01", periods=250, freq="D"),
                _make_kline_df(n=250)["close"])]
        try:
            corr = correlation_matrix(["A", "B"])
            assert corr is None or corr.shape[0] >= 2
        finally:
            risk_mod.get_kline_df = orig_kline
            risk_mod.get_index_close_series = orig_idx


# ---------------------------------------------------------------------------
# P0-1 基本面估值分位
# ---------------------------------------------------------------------------

class TestFundamental:
    def test_percentile(self):
        from app.domains.stock_watch.fundamental import _calc_percentile
        s = pd.Series([10.0, 20.0, 30.0, 40.0])
        assert _calc_percentile(s, 25.0) == 50.0
        assert _calc_percentile(s, 10.0) == 25.0
        assert _calc_percentile(s, None) is None

    def test_classify_verdict(self):
        from app.domains.stock_watch.fundamental import _classify_verdict
        v, score = _classify_verdict(15.0, 10.0, 5.0, 14.0)
        assert v == "低估"
        assert score >= 70
        v2, s2 = _classify_verdict(50.0, 90.0, 95.0, 49.0)
        assert v2 == "高估"
        v3, s3 = _classify_verdict(20.0, None, None, 19.0)
        assert v3 == "未知"

    def test_analyze_fundamental_no_data(self):
        from app.domains.stock_watch.fundamental import analyze_fundamental
        import app.domains.stock_watch.fundamental as fmod
        orig = fmod._fetch_valuation_history
        fmod._fetch_valuation_history = lambda code: None
        try:
            snap = analyze_fundamental("TEST")
            assert snap.pe_ttm is None
            assert snap.verdict == "未知"
        finally:
            fmod._fetch_valuation_history = orig

    def test_to_float(self):
        from app.domains.stock_watch.fundamental import _to_float
        assert _to_float(3.5) == 3.5
        assert _to_float("4.2") == 4.2
        assert _to_float(None) is None
        assert _to_float("abc") is None


# ---------------------------------------------------------------------------
# P0-2 资金面
# ---------------------------------------------------------------------------

class TestMoneyFlow:
    def test_score_flow_inflow(self):
        from app.domains.stock_watch.money_flow import MoneyFlowSnapshot, _score_money_flow
        snap = MoneyFlowSnapshot(northbound_today=30.0, northbound_5d=100.0, main_net_inflow_pct=3.0)
        score, verdict = _score_money_flow(snap)
        assert verdict == "资金流入"
        assert score is not None and score > 60

    def test_score_flow_outflow(self):
        from app.domains.stock_watch.money_flow import MoneyFlowSnapshot, _score_money_flow
        snap = MoneyFlowSnapshot(northbound_today=-40.0, northbound_5d=-200.0, main_net_inflow_pct=-4.0)
        score, verdict = _score_money_flow(snap)
        assert verdict == "资金流出"
        assert score is not None and score < 40

    def test_score_flow_unknown(self):
        from app.domains.stock_watch.money_flow import MoneyFlowSnapshot, _score_money_flow
        snap = MoneyFlowSnapshot()
        score, verdict = _score_money_flow(snap)
        assert verdict == "未知"
        assert score is None

    def test_analyze_money_flow_no_data(self):
        from app.domains.stock_watch.money_flow import analyze_money_flow
        import app.domains.stock_watch.money_flow as mf
        orig_n, orig_m = mf._fetch_northbound_flow, mf._fetch_main_flow
        orig_margin = mf._fetch_margin
        mf._fetch_northbound_flow = lambda: {}
        mf._fetch_main_flow = lambda code: {}
        mf._fetch_margin = lambda: {}
        try:
            snap = analyze_money_flow("TEST")
            assert snap.northbound_today is None
            assert snap.verdict == "未知"
        finally:
            mf._fetch_northbound_flow, mf._fetch_main_flow = orig_n, orig_m
            mf._fetch_margin = orig_margin


# ---------------------------------------------------------------------------
# P1-1 市场情绪
# ---------------------------------------------------------------------------

class TestSentiment:
    def test_score_sentiment_hot(self):
        from app.domains.market.sentiment import MarketSentiment, _score_sentiment
        snap = MarketSentiment(up_count=4000, limit_up_count=80, breadth=0.8)
        score, sentiment = _score_sentiment(snap)
        assert sentiment == "亢奋"
        assert score is not None and score > 65

    def test_score_sentiment_cold(self):
        from app.domains.market.sentiment import MarketSentiment, _score_sentiment
        snap = MarketSentiment(up_count=500, limit_up_count=5, breadth=0.1)
        score, sentiment = _score_sentiment(snap)
        assert sentiment == "冰点"
        assert score is not None and score < 35

    def test_score_sentiment_unknown(self):
        from app.domains.market.sentiment import MarketSentiment, _score_sentiment
        snap = MarketSentiment()
        score, sentiment = _score_sentiment(snap)
        assert sentiment == "未知"
        assert score is None


# ---------------------------------------------------------------------------
# P2-1 宏观
# ---------------------------------------------------------------------------

class TestMacro:
    def test_score_macro_easy(self):
        from app.domains.macro.macro_data import MacroSnapshot, _score_macro
        snap = MacroSnapshot(m1m2_gap=2.0, bond_10y=1.5, yield_curve=1.0)
        score, env = _score_macro(snap)
        assert env == "宽松"
        assert score is not None and score > 65

    def test_score_macro_tight(self):
        from app.domains.macro.macro_data import MacroSnapshot, _score_macro
        snap = MacroSnapshot(m1m2_gap=-5.0, bond_10y=4.5, yield_curve=-1.0)
        score, env = _score_macro(snap)
        assert env == "收紧"
        assert score is not None and score < 35

    def test_score_macro_unknown(self):
        from app.domains.macro.macro_data import MacroSnapshot, _score_macro
        snap = MacroSnapshot()
        score, env = _score_macro(snap)
        assert env == "未知"
        assert score is None

    def test_to_float(self):
        from app.domains.macro.macro_data import _to_float
        assert _to_float(1.5) == 1.5
        assert _to_float("2.5") == 2.5
        assert _to_float(None) is None


# ---------------------------------------------------------------------------
# CLI pro 命令
# ---------------------------------------------------------------------------

class TestProCli:
    def test_pro_command_registered(self):
        from app.cli.commands import pro_command
        assert callable(pro_command)

    def test_pro_no_code_returns_1(self):
        from app.cli.commands.pro import pro_command
        rc = pro_command([])
        assert rc == 1

    def test_pro_market_returns_0(self):
        from app.cli.commands.pro import pro_command
        rc = pro_command(["--market"])
        assert rc == 0
