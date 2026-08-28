"""
app 完整功能移植 单元测试。

验证移植到 app 框架的原始功能：
    - 基金域：筛选/评分/追踪/监控/指数/稳健
    - 沪深300域：9 大指标
    - 理财域：深度画像/监控
    - A股盯盘域：七大因子信号引擎
"""

import os
import sys

import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 基金域
# ---------------------------------------------------------------------------

class TestFundMetrics:
    def test_metrics_annual_return(self):
        from app.domains.fund.metrics import calc_annual_return

        nav = pd.Series([1.0, 1.1, 1.21, 1.331], index=pd.to_datetime(
            ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]))
        result = calc_annual_return(nav)
        assert result > 0

    def test_metrics_max_drawdown(self):
        from app.domains.fund.metrics import calc_max_drawdown

        nav = pd.Series([1.0, 1.2, 0.8, 0.9])
        mdd = calc_max_drawdown(nav)
        assert mdd > 0.2

    def test_metrics_sharpe_calmar_sortino(self):
        from app.domains.fund.metrics import (
            calc_calmar_ratio,
            calc_sharpe_ratio,
            calc_sortino_ratio,
        )

        nav = pd.Series([1.0, 1.05, 1.1, 1.02, 1.15], index=pd.to_datetime(
            ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01", "2024-05-01"]))
        assert calc_sharpe_ratio(nav) >= 0
        assert calc_sortino_ratio(nav) >= 0
        assert isinstance(calc_calmar_ratio(nav), float)


class TestFundScoring:
    def test_score_fund(self):
        from app.domains.fund.scoring import score_fund

        score = score_fund(
            sharpe=1.5, mdd=0.1, ann_ret=0.15, calmar=1.5, sortino=1.2, volatility=0.2,
        )
        assert 0 <= score <= 100
        assert score > 50

    def test_generate_signal(self):
        from app.domains.fund.scoring import generate_signal

        sig = generate_signal(80, 1.5, 0.1, 0.2, 2.0, "recovery")
        assert sig["signal"] in ("买入", "卖出", "持有")
        assert "score" in sig


class TestFundScreener:
    def test_analyze_fund_basic(self):
        """不依赖网络：分析不存在净值时返回错误信息。"""
        from app.domains.fund.screener import FundScreener

        screener = FundScreener()
        result = screener.analyze_fund("999999")  # 无效代码
        assert "error" in result or "fund_code" in result


class TestIndexFundScreener:
    def test_calc_fund_layer_score(self):
        from types import SimpleNamespace

        from app.domains.fund.index_screener import IndexFundScreener

        screener = IndexFundScreener()
        row = SimpleNamespace(
            tracking_error=0.01, information_ratio=1.0,
            max_drawdown=0.1, sharpe=1.0, fee_rate=0.006, fund_scale=100,
        )
        score = screener.calc_fund_layer_score(row, fund_type="passive")
        assert 0 <= score <= 100
        assert score > 50

    def test_calc_stability_score(self):
        from app.domains.fund.index_screener import IndexFundScreener

        screener = IndexFundScreener()
        score = screener.calc_stability_score({
            "max_drawdown": 0.03, "sharpe": 1.2, "annual_return": 0.06,
        })
        assert score > 70


class TestFundTracking:
    def test_load_portfolio_missing(self):
        from app.domains.fund.tracking import load_portfolio

        df = load_portfolio("/nonexistent/path.csv")
        assert df.empty

    def test_alert_engine(self):
        from app.domains.fund.tracking import AlertConfig, AlertEngine

        engine = AlertEngine(AlertConfig(single_daily_drop_pct=3.0))
        df = pd.DataFrame([{
            "fund_code": "110011", "fund_name": "测试", "total_cost": 10000,
            "daily_return": -5.0, "daily_profit": -500,
            "profit": -3000, "profit_pct": -0.3,
        }])
        messages = engine.evaluate(df)
        assert len(messages) >= 1  # 日跌幅与浮亏均触发
        assert "测试" in messages[0]

    def test_alert_engine_no_alert(self):
        from app.domains.fund.tracking import AlertConfig, AlertEngine

        engine = AlertEngine(AlertConfig(single_daily_drop_pct=3.0))
        df = pd.DataFrame([{
            "fund_code": "110011", "fund_name": "测试", "total_cost": 10000,
            "daily_return": 1.0, "daily_profit": 100,
            "profit": 500, "profit_pct": 0.05,
        }])
        messages = engine.evaluate(df)
        assert len(messages) == 0


# ---------------------------------------------------------------------------
# 沪深300 域
# ---------------------------------------------------------------------------

class TestHs300Indicators:
    def test_technical_analyzer_all_indicators(self):
        from app.domains.hs300.indicators import TechnicalAnalyzer

        # 构造 60 行 K 线数据
        import numpy as np
        np.random.seed(42)
        n = 60
        closes = np.linspace(10, 20, n) + np.random.normal(0, 0.3, n)
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=n),
            "open": closes,
            "close": closes,
            "high": closes + 0.5,
            "low": closes - 0.5,
            "volume": np.random.randint(100000, 200000, n),
        })
        analyzer = TechnicalAnalyzer()
        prepared = analyzer.prepare(df.copy())
        # 应计算全部指标列
        for col in ("ma5", "DIF", "DEA", "K", "D", "J", "RSI6", "BOLL_MID"):
            assert col in prepared.columns
        result = analyzer.analyze(prepared)
        assert "total_score" in result
        assert "advice" in result
        assert set(result["scores"].keys()) == set(analyzer.WEIGHTS.keys())
        assert len(result["scores"]) == 9  # 9 大指标

    def test_support_resistance_and_pattern(self):
        from app.domains.hs300.indicators import TechnicalAnalyzer

        import numpy as np
        closes = np.array([10]*15 + [20]*15)
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=30),
            "open": closes, "close": closes,
            "high": closes + 0.5, "low": closes - 0.5,
            "volume": [100000]*30,
        })
        analyzer = TechnicalAnalyzer()
        prepared = analyzer.prepare(df.copy())
        result = analyzer.analyze(prepared)
        assert "SR" in result["scores"]


# ---------------------------------------------------------------------------
# A股盯盘 域（七大因子）
# ---------------------------------------------------------------------------

class TestStockSignals:
    def _make_ctx(self, prices, volumes=None):
        from app.domains.stock_watch.signals import IndicatorContext

        hist = {"600519": [
            {"close": p, "high": p, "low": p, "volume": v}
            for p, v in zip(prices, volumes or [10000]*len(prices))
        ]}
        vols = volumes or [10000]*len(prices)
        return IndicatorContext(hist, {"600519": vols})

    def test_signal_engine_calculate(self):
        from app.domains.stock_watch.signals import SignalEngine, SignalParams

        import numpy as np
        np.random.seed(1)
        prices = list(np.linspace(100, 120, 60) + np.random.normal(0, 1, 60))
        ctx = self._make_ctx(prices)
        engine = SignalEngine(SignalParams())
        row = {"code": "600519", "volume": 15000, "change_pct": 1.0}
        score, level, reasons, indicators = engine.calculate(row, ctx, market_trend=1)
        assert isinstance(score, (int, float))
        assert level in ("🟢 强买入", "🔵 买入", "🟠 卖出", "🔴 强卖出", "⚪ 观望")
        assert isinstance(reasons, list)

    def test_signal_engine_uptrend(self):
        """上涨趋势应得到正向评分。"""
        from app.domains.stock_watch.signals import SignalEngine, SignalParams

        # 严格上涨序列
        prices = [100 + i for i in range(60)]
        ctx = self._make_ctx(prices, [15000]*60)
        engine = SignalEngine(SignalParams())
        row = {"code": "600519", "volume": 20000, "change_pct": 2.0}
        score, level, reasons, _ = engine.calculate(row, ctx, market_trend=1)
        assert score > 0

    def test_signal_engine_downtrend(self):
        """下跌趋势应得到负向评分。"""
        from app.domains.stock_watch.signals import SignalEngine, SignalParams

        prices = [200 - i for i in range(60)]
        ctx = self._make_ctx(prices, [8000]*60)
        engine = SignalEngine(SignalParams())
        row = {"code": "600519", "volume": 6000, "change_pct": -2.0}
        score, level, reasons, _ = engine.calculate(row, ctx, market_trend=-1)
        assert score < 0


# ---------------------------------------------------------------------------
# 理财 域
# ---------------------------------------------------------------------------

class TestWealth:
    def test_deep_analyzer(self):
        from app.domains.wealth import (
            DeepProductAnalyzer,
            FinancialProduct,
            InvestorProfile,
        )

        product = FinancialProduct(
            code="107333", name="招行稳健理财", expected_rate=3.5,
            risk_level=2, term_days=180,
        )
        analyzer = DeepProductAnalyzer(product)
        profile = InvestorProfile(risk_tolerance=3, liquidity_need="中")
        report = analyzer.full_report(profile=profile)
        assert "综合评分" in report
        assert "买卖建议" in report
        assert report["综合评分"]["综合得分"] > 0

    def test_lc_monitor_alert(self):
        from app.domains.wealth import FinancialProduct, LcAlertConfig, LcMonitor

        monitor = LcMonitor(LcAlertConfig(min_annual_rate=2.0))
        products = [FinancialProduct(code="A", name="低收益", expected_rate=1.0)]
        messages = monitor.check(products)
        assert len(messages) == 1
        assert "低收益" in messages[0]

    def test_lc_monitor_no_alert(self):
        from app.domains.wealth import FinancialProduct, LcAlertConfig, LcMonitor

        monitor = LcMonitor(LcAlertConfig(min_annual_rate=2.0))
        products = [FinancialProduct(code="A", name="正常", expected_rate=3.0)]
        messages = monitor.check(products)
        assert len(messages) == 0


# ---------------------------------------------------------------------------
# CLI 集成
# ---------------------------------------------------------------------------

class TestCliCommands:
    def test_fund_command_no_crash(self):
        from app.cli.commands.fund import fund_command

        # 空参数应走默认筛选，不崩溃
        ret = fund_command([])
        assert ret == 0

    def test_wealth_command_no_crash(self):
        from app.cli.commands.wealth import wealth_command

        ret = wealth_command([])
        assert ret == 0

    def test_stock_command_no_crash(self):
        from app.cli.commands.stock import stock_command

        ret = stock_command(["--once"])
        assert ret == 0
