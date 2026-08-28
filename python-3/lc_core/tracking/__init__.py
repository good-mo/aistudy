"""
lc_core.tracking —— 理财监控告警层
==================================

读取理财持仓并评估收益/风险/期限告警，支持定时跟踪。
"""

from .monitor import (
    LcMonitor,
    load_holdings,
    build_products,
    main_once,
)
from .alert_rules import LcAlertConfig

__all__ = [
    "LcMonitor",
    "LcAlertConfig",
    "load_holdings",
    "build_products",
    "main_once",
]
