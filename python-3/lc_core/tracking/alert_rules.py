"""
理财监控告警规则
================

定义理财持仓监控的阈值规则与默认配置，供定时跟踪 / 告警使用。

理财产品的净值 / 收益数据依赖业绩基准年化收益率估算（招行/浦发 API
或本地 CSV 提供的 annual_rate），因此监控以"预期年化收益偏差"和
"持仓金额 / 期限 / 风险"为核心维度。
"""

from dataclasses import dataclass
from typing import List


@dataclass
class LcAlertConfig:
    """理财监控告警默认配置。"""

    # 单产品预期年化收益低于该值（%）时提示收益偏低
    min_annual_rate: float = 2.0

    # 单产品投入超过该金额（元）且风险等级 >= 该值时提示集中度风险
    single_concentration_amt: float = 500000.0
    high_risk_level: int = 4

    # 距离到期 / 开放日小于该天数（天）时提示关注
    near_term_days: int = 15

    # 是否启用终端打印
    enable_console: bool = True

    # 是否启用桌面通知（依赖 plyer，可选）
    enable_notify: bool = True
