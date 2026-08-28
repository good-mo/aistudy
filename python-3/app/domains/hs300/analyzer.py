"""
app.domains.hs300.analyzer —— 沪深300 分析器

从原始 share300/hs300_analyzer.py 提炼，基于 9 大技术指标（MA/MACD/KDJ/RSI/
成交量/布林带/支撑阻力/K线形态/价格形态）对沪深300 成分股做综合分析。

数据源：app.data 统一接口（多源降级）。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple

from app.core.logging_setup import get_logger
from app.data.kline import get_kline_df
from app.domains.hs300.data import HS300_CODES, get_hs300_stocks
from app.domains.hs300.indicators import TechnicalAnalyzer

logger = get_logger(__name__)


class HS300Analyzer:
    """沪深300 成分股分析器。"""

    #: 沪深300成分股代码（取自全局变量 HS300_CODES，兼容历史 CLI 与测试引用）
    SAMPLE_CODES = [code for code, _ in HS300_CODES]

    def __init__(self, max_workers: int = 10, force_refresh: bool = False):
        self.max_workers = max_workers
        self.force_refresh = force_refresh
        self.technical = TechnicalAnalyzer()

    def get_hs300_stocks(self) -> List[Tuple[str, str]]:
        """获取沪深300成分股列表。"""
        return get_hs300_stocks(force_refresh=self.force_refresh)

    def analyze_code(self, code: str, days: int = 120) -> dict | None:
        """分析单只股票。"""
        df = get_kline_df(code, days=days, force_refresh=self.force_refresh)
        if df is None or len(df) < 30:
            logger.debug("%s 日K线数据不足，跳过", code)
            return None

        df = self.technical.prepare(df)
        result = self.technical.analyze(df)
        result["code"] = code
        result["data_points"] = len(df)
        return result

    def analyze_stock(self, code: str, name: str) -> dict | None:
        """按代码+名称分析单只股票。"""
        result = self.analyze_code(code)
        if result:
            result["name"] = name
        return result

    def analyze_batch(
        self, stocks: List[Tuple[str, str]] | None = None, days: int = 120,
    ) -> List[dict]:
        """批量分析（并发）。"""
        if stocks is None:
            stocks = self.get_hs300_stocks()
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self.analyze_stock, code, name): code
                for code, name in stocks
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
        results.sort(key=lambda r: r.get("total_score", 0), reverse=True)
        return results

    def run_analysis(self, top_n: int = 20) -> List[dict]:
        """运行完整分析并生成报告。"""
        logger.info("阶段[成分股] 获取沪深300成分股列表...")
        stocks = self.get_hs300_stocks()
        print(f"📋 沪深300成分股列表（共 {len(stocks)} 只）\n")
        results = self.analyze_batch(stocks)
        logger.info("分析完成，有效结果 %d 只", len(results))
        return results[:top_n]

    def generate_report(self, top_n: int = 20) -> None:
        """生成终端报告。"""
        results = self.run_analysis(top_n)
        if not results:
            print("无有效分析结果")
            return
        print("\n" + "=" * 100)
        print("🚀 沪深300成分股综合分析报告")
        print("=" * 100)
        print("技术指标：MA / MACD / KDJ / RSI / 成交量 / 布林带 / 支撑阻力 / K线形态 / 价格形态")
        print("=" * 100)
        print(f"{'排名':<4}{'代码':<8}{'名称':<10}{'价格':>8}{'涨跌':>8}{'评分':>8}  建议")
        for i, r in enumerate(results, 1):
            code = r.get("code", "")
            name = r.get("name", code)
            print(
                f"{i:<4}{code:<8}{name:<10}"
                f"{r.get('price', 0):>8.2f}{r.get('change_pct', 0):>7.2f}%"
                f"{r.get('total_score', 0):>8.2f}  {r.get('advice', '')}"
            )
        print("\n1. 本分析仅基于技术指标，不构成投资建议")
        print("2. 技术指标存在滞后性，无法预测突发消息面影响")
