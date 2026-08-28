"""
app.domains.wealth.monitor —— 理财定时监控

从原始 lc_core.tracking 提炼而来，评估产品收益/风险/期限告警。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.logging_setup import get_logger
from app.domains.wealth.analyzer import FinancialProduct, WealthAnalyzer

logger = get_logger(__name__)

DEFAULT_HOLDING_CSV = "lc_holding.csv"


@dataclass
class LcAlertConfig:
    """理财监控告警配置。"""

    min_annual_rate: float = 2.0
    enable_console: bool = True
    enable_notify: bool = True


class LcMonitor:
    """理财监控器。"""

    def __init__(self, config: LcAlertConfig | None = None):
        self.config = config or LcAlertConfig()

    def check(self, products: list[FinancialProduct]) -> list[str]:
        """评估产品是否触发告警。"""
        messages = []
        for p in products:
            if p.expected_rate < self.config.min_annual_rate:
                msg = (
                    f"{p.name}({p.code}) 预期年化 {p.expected_rate:.2f}% "
                    f"低于阈值 {self.config.min_annual_rate}%"
                )
                messages.append(msg)
                logger.warning(msg)
        if self.config.enable_console and messages:
            print("\n⚠️  理财监控告警")
            for m in messages:
                print(f"  ⚠ {m}")
            print()
        return messages

    def run_once(self, csv_path: str = DEFAULT_HOLDING_CSV) -> list[str]:
        """执行一次监控快照。"""
        logger.info("开始本次理财监控快照")
        analyzer = WealthAnalyzer(portfolio_csv=csv_path)
        products = analyzer.load_products()
        messages = self.check(products)
        logger.info("本次理财监控完成，共 %d 条持仓，告警 %d 条", len(products), len(messages))
        return messages

    def run_loop(self, csv_path: str = DEFAULT_HOLDING_CSV, interval: int = 3600):
        """持续监控。"""
        logger.info("开始理财监控，刷新间隔 %d 秒", interval)
        try:
            while True:
                self.run_once(csv_path)
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("理财监控已停止")
