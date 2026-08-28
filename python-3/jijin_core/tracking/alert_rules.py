"""
基金监控告警规则
================

定义持仓监控的阈值规则，用于在每日收益追踪 / 定时监控时判断是否触发告警。

支持的告警类型：
- 单只基金日跌幅超阈值（如单日跌 -3%）
- 整个组合日收益低于阈值（如组合日亏 -2%）
- 单只基金累计浮亏超阈值（绝对金额或百分比）
- 组合总浮亏超阈值（绝对金额或百分比）
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from ..utils.terminal import Color
from common.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class AlertRule:
    """单条告警规则。

    Parameters
    ----------
    rule_type : str
        规则类型，取值：
        - ``single_daily_drop``  单只基金日跌幅（%）低于阈值触发
        - ``portfolio_daily_loss`` 组合当日总收益（金额）为负且幅度超阈值
        - ``single_float_loss``  单只基金累计浮亏（金额）超过阈值
        - ``single_float_loss_pct`` 单只基金累计浮亏（%）超过阈值
        - ``portfolio_float_loss`` 组合累计总浮亏（金额）超过阈值
    threshold : float
        阈值（单位随 rule_type 而定：百分比为 0-100 数值，金额为人民币元）
    message : str, optional
        触发时的提示文案模板（可含 {code}/{name}/{value} 占位符）
    """

    rule_type: str = "single_daily_drop"
    threshold: float = 3.0
    message: str = ""
    enabled: bool = True

    def description(self) -> str:
        """人类可读的规则描述。"""
        if self.rule_type == "single_daily_drop":
            return f"单只基金当日跌幅超 {self.threshold}%"
        if self.rule_type == "portfolio_daily_loss":
            return f"组合当日亏损超 ¥{self.threshold:,.0f}"
        if self.rule_type == "single_float_loss":
            return f"单只基金累计浮亏超 ¥{self.threshold:,.0f}"
        if self.rule_type == "single_float_loss_pct":
            return f"单只基金累计浮亏超 {self.threshold}%"
        if self.rule_type == "portfolio_float_loss":
            return f"组合累计浮亏超 ¥{self.threshold:,.0f}"
        return self.rule_type


@dataclass
class AlertConfig:
    """基金监控告警默认配置。

    默认阈值可按需修改，或从环境变量 / 配置文件加载。
    """

    # 单只基金当日跌幅超过该百分比（%）时告警
    single_daily_drop_pct: float = 3.0

    # 组合当日总亏损超过该金额（元）时告警
    portfolio_daily_loss_amt: float = 1000.0

    # 单只基金累计浮亏超过该金额（元）时告警
    single_float_loss_amt: float = 2000.0

    # 单只基金累计浮亏超过该百分比（%）时告警
    single_float_loss_pct: float = 10.0

    # 组合累计浮亏超过该金额（元）时告警
    portfolio_float_loss_amt: float = 5000.0

    # 是否启用终端打印告警
    enable_console: bool = True

    # 是否启用桌面通知（依赖 plyer，可选）
    enable_notify: bool = True

    def build_rules(self) -> list:
        """根据配置生成规则列表。"""
        rules = [
            AlertRule("single_daily_drop", self.single_daily_drop_pct,
                      message="{name}({code}) 当日下跌 {value:.2f}%，超过阈值 {threshold}%"),
            AlertRule("portfolio_daily_loss", self.portfolio_daily_loss_amt,
                      message="组合当日亏损 ¥{value:,.2f}，超过阈值 ¥{threshold:,.0f}"),
            AlertRule("single_float_loss", self.single_float_loss_amt,
                      message="{name}({code}) 累计浮亏 ¥{value:,.2f}，超过阈值 ¥{threshold:,.0f}"),
            AlertRule("single_float_loss_pct", self.single_float_loss_pct,
                      message="{name}({code}) 累计浮亏 {value:.2f}%，超过阈值 {threshold}%"),
            AlertRule("portfolio_float_loss", self.portfolio_float_loss_amt,
                      message="组合累计浮亏 ¥{value:,.2f}，超过阈值 ¥{threshold:,.0f}"),
        ]
        logger.debug("构建 %d 条基金告警规则", len(rules))
        return rules


def default_config() -> AlertConfig:
    """返回默认告警配置副本。"""
    return AlertConfig()
