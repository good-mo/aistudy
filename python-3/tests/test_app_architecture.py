"""
app 架构单元测试。

验证：
    - 配置中心
    - 统一异常
    - 数据源注册与降级链
    - 统一数据访问层（K线/行情/净值/指数）
    - 领域模块
"""

import os
import sys

import pandas as pd
import pytest

# 确保项目根目录在 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

class TestConfig:
    def test_default_config(self):
        from app.core.config import AppConfig

        cfg = AppConfig()
        assert cfg.logging.level == "INFO"
        assert cfg.network.timeout == 15.0
        assert cfg.cache.enabled is True
        assert "tencent" in cfg.data_source.source_priority

    def test_config_from_env(self):
        from app.core.config import AppConfig

        os.environ["APP_LOG_LEVEL"] = "DEBUG"
        cfg = AppConfig.from_env()
        assert cfg.logging.level == "DEBUG"
        os.environ.pop("APP_LOG_LEVEL", None)

    def test_errors_hierarchy(self):
        from app.core.errors import (
            AppError,
            ConfigError,
            DataFetchError,
            DataSourceError,
            NetworkError,
        )

        # 所有异常继承自 AppError
        for cls in (ConfigError, DataFetchError, DataSourceError, NetworkError):
            assert issubclass(cls, AppError)

        err = DataFetchError("测试错误")
        assert "测试错误" in str(err)


# ---------------------------------------------------------------------------
# 数据源注册表与降级链
# ---------------------------------------------------------------------------

class TestDataSourceRegistry:
    def test_registry_builtins(self):
        from app.data.base import get_registry

        registry = get_registry()
        assert "tencent" in registry.names
        assert "eastmoney" in registry.names
        assert "sina" in registry.names

    def test_call_returns_data(self):
        """降级链应返回第一个成功的数据源结果。"""
        from app.data.base import get_registry

        # 腾讯 K 线
        result = get_registry().call("fetch_kline", "600519", days=5)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
        assert "date" in result[0]
        assert "close" in result[0]


# ---------------------------------------------------------------------------
# 统一数据访问层
# ---------------------------------------------------------------------------

class TestDataAccess:
    def test_get_kline(self):
        from app.data.kline import get_kline

        result = get_kline("600519", days=5, force_refresh=True)
        assert result is not None
        assert len(result) > 0
        assert "date" in result[0]
        assert "close" in result[0]

    def test_get_kline_df(self):
        from app.data.kline import get_kline_df

        df = get_kline_df("600519", days=5, force_refresh=True)
        assert df is not None
        assert not df.empty
        assert "date" in df.columns
        assert "close" in df.columns

    def test_get_fund_nav(self):
        from app.data.fund_nav import get_fund_nav

        result = get_fund_nav("110011", days=30, force_refresh=True)
        assert result is not None
        assert len(result) > 0
        assert "date" in result[0]
        assert "nav" in result[0]

    def test_get_index_close_series(self):
        from app.data.index import get_index_close_series

        result = get_index_close_series("000300", days=10, force_refresh=True)
        assert result is not None
        assert len(result) > 0
        date, close = result[0]
        assert isinstance(date, str)
        assert isinstance(close, float)

    def test_get_realtime_quote_fund(self):
        from app.data.quotes import get_realtime_quote

        quote = get_realtime_quote("110011", kind="fund", force_refresh=True)
        assert quote is not None
        assert "name" in quote
        assert "nav" in quote

    def test_get_realtime_quote_stock(self):
        from app.data.quotes import get_realtime_quote

        quote = get_realtime_quote("600519", force_refresh=True)
        assert quote is not None
        assert "name" in quote
        assert quote.get("price", 0) > 0


# ---------------------------------------------------------------------------
# 领域模块
# ---------------------------------------------------------------------------

class TestDomains:
    def test_fund_analyzer_metrics(self):
        from app.domains.fund import FundAnalyzer

        analyzer = FundAnalyzer()
        nav = analyzer.get_nav_history("110011", days=30)
        assert not nav.empty
        metrics = analyzer.calculate_metrics(nav)
        assert "annual_return" in metrics
        assert "max_drawdown" in metrics
        assert "sharpe_ratio" in metrics

    def test_fund_scorer(self):
        from app.domains.fund import FundScorer

        scorer = FundScorer()
        metrics = {
            "annual_return": 0.15,
            "max_drawdown": -0.08,
            "sharpe_ratio": 1.2,
        }
        score = scorer.score(metrics)
        assert "total_score" in score
        assert "level" in score
        assert score["total_score"] > 0

    def test_hs300_analyzer(self):
        from app.domains.hs300 import HS300Analyzer

        analyzer = HS300Analyzer(max_workers=2)
        result = analyzer.analyze_code("600519", days=60)
        assert result is not None
        assert "code" in result
        assert "advice" in result
        # 完整 9 大指标实现：返回综合评分 total_score 与各指标分数
        assert "total_score" in result
        assert "scores" in result
        assert "signals" in result

    def test_wealth_analyzer(self):
        from app.domains.wealth import WealthAnalyzer

        analyzer = WealthAnalyzer()
        summary = analyzer.summarize()
        assert "total_products" in summary

    def test_wealth_analyzer_empty_csv(self):
        """空持仓 CSV 应优雅返回空 DataFrame，不抛错。"""
        import tempfile
        from app.domains.wealth import WealthAnalyzer

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            empty_path = f.name
        try:
            analyzer = WealthAnalyzer(portfolio_csv=empty_path)
            df = analyzer.load_portfolio()
            assert df.empty
            # summarize 也不应崩溃
            summary = analyzer.summarize()
            assert summary["total_products"] == 0
            assert summary["total_amount"] == 0
        finally:
            os.unlink(empty_path)

    def test_fund_load_portfolio_empty_csv(self):
        """基金持仓空 CSV 应优雅返回空 DataFrame。"""
        import tempfile
        from app.domains.fund.tracking import load_portfolio

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            empty_path = f.name
        try:
            df = load_portfolio(empty_path)
            assert df.empty
        finally:
            os.unlink(empty_path)

    def test_stock_watcher(self):
        from app.domains.stock_watch import StockWatcher

        watcher = StockWatcher()
        result = watcher.run_once()
        assert "quotes" in result
        assert "watch_count" in result
