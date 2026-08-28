"""
基金监控告警引擎
================

根据持仓数据与告警规则评估是否触发告警，并通过终端 / 桌面通知输出。

用法示例
--------
    from jijin_core.tracking.alerts import AlertEngine, default_alert_engine
    from jijin_core.tracking.alert_rules import AlertConfig

    engine = AlertEngine(AlertConfig())
    alerts = engine.evaluate(portfolio_df)   # 返回触发告警的文本列表
    engine.report(alerts)                    # 打印并推送通知
"""

from typing import List, Optional

from .alert_rules import AlertConfig, AlertRule
from ..utils.terminal import Color
from common.logging_utils import get_logger

logger = get_logger(__name__)

# 桌面通知（可选依赖 plyer）
try:
    from plyer import notification

    _NOTIFICATION_AVAILABLE = True
except Exception:  # noqa: BLE001
    notification = None
    _NOTIFICATION_AVAILABLE = False


class AlertEngine:
    """告警评估引擎。"""

    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()

    # ------------------------------------------------------------------
    # 评估
    # ------------------------------------------------------------------
    def evaluate(self, portfolio: "pd.DataFrame") -> List[str]:
        """对合并后的持仓 DataFrame 评估告警规则，返回触发告警文案列表。

        要求 DataFrame 至少含列：
            fund_code, fund_name, total_cost,
            daily_return, daily_profit, profit, profit_pct
        """
        import pandas as pd

        if portfolio is None or portfolio.empty:
            return []

        messages: List[str] = []

        # 单只基金日跌幅
        daily_drop_th = self.config.single_daily_drop_pct
        if "daily_return" in portfolio.columns:
            for _, row in portfolio.iterrows():
                dr = self._num(row.get("daily_return"))
                if dr <= -daily_drop_th:
                    messages.append(
                        "{name}({code}) 当日下跌 {value:.2f}%，超过阈值 {threshold}%".format(
                            name=row.get("fund_name", row.get("fund_code", "")),
                            code=row.get("fund_code", ""),
                            value=dr,
                            threshold=daily_drop_th,
                        )
                    )

        # 组合当日总亏损
        daily_loss_th = self.config.portfolio_daily_loss_amt
        total_daily_profit = self._num(
            portfolio["daily_profit"].sum() if "daily_profit" in portfolio.columns else 0
        )
        if total_daily_profit <= -daily_loss_th:
            messages.append(
                "组合当日亏损 ¥{value:,.2f}，超过阈值 ¥{threshold:,.0f}".format(
                    value=total_daily_profit, threshold=daily_loss_th
                )
            )

        # 单只基金累计浮亏（金额）
        single_loss_th = self.config.single_float_loss_amt
        if "profit" in portfolio.columns:
            for _, row in portfolio.iterrows():
                profit = self._num(row.get("profit"))
                if profit <= -single_loss_th:
                    messages.append(
                        "{name}({code}) 累计浮亏 ¥{value:,.2f}，超过阈值 ¥{threshold:,.0f}".format(
                            name=row.get("fund_name", row.get("fund_code", "")),
                            code=row.get("fund_code", ""),
                            value=profit,
                            threshold=single_loss_th,
                        )
                    )

        # 单只基金累计浮亏（百分比）
        single_loss_pct_th = self.config.single_float_loss_pct
        if "profit_pct" in portfolio.columns:
            for _, row in portfolio.iterrows():
                pct = self._num(row.get("profit_pct")) * 100  # profit_pct 为小数
                if pct <= -single_loss_pct_th:
                    messages.append(
                        "{name}({code}) 累计浮亏 {value:.2f}%，超过阈值 {threshold}%".format(
                            name=row.get("fund_name", row.get("fund_code", "")),
                            code=row.get("fund_code", ""),
                            value=pct,
                            threshold=single_loss_pct_th,
                        )
                    )

        # 组合累计浮亏（金额）
        port_loss_th = self.config.portfolio_float_loss_amt
        total_profit = self._num(
            portfolio["profit"].sum() if "profit" in portfolio.columns else 0
        )
        if total_profit <= -port_loss_th:
            messages.append(
                "组合累计浮亏 ¥{value:,.2f}，超过阈值 ¥{threshold:,.0f}".format(
                    value=total_profit, threshold=port_loss_th
                )
            )

        return messages

    @staticmethod
    def _num(value) -> float:
        """安全转 float，None/NaN 视为 0。"""
        if value is None:
            return 0.0
        try:
            import math

            v = float(value)
            return 0.0 if math.isnan(v) else v
        except (TypeError, ValueError):
            return 0.0

    # ------------------------------------------------------------------
    # 输出
    # ------------------------------------------------------------------
    def report(self, messages: List[str]) -> None:
        """打印告警并推送桌面通知。"""
        if not messages:
            return

        title = "📢 基金监控告警"
        body = "；".join(messages)
        logger.warning("基金监控告警：%s", body)

        if self.config.enable_console:
            print(f"\n{Color.RED}{Color.BOLD}⚠️  基金监控告警{Color.RESET}")
            for m in messages:
                print(f"  {Color.RED}⚠ {m}{Color.RESET}")
            print()

        if self.config.enable_notify and _NOTIFICATION_AVAILABLE:
            try:
                notification.notify(
                    title=title,
                    message=body[:200],  # 桌面通知长度限制
                    app_name="基金监控",
                    timeout=10,
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("桌面通知失败: %s", e)

    def check(self, portfolio) -> List[str]:
        """评估并输出告警，返回触发告警文案（便于测试）。"""
        messages = self.evaluate(portfolio)
        if messages:
            self.report(messages)
        else:
            logger.info("基金监控：未触发告警")
        return messages


def default_alert_engine() -> AlertEngine:
    """返回使用默认配置的告警引擎。"""
    return AlertEngine(AlertConfig())
