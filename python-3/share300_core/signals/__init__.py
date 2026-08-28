"""share300_core.signals —— 买卖信号子系统。

基于 9 大技术指标（MA/MACD/KDJ/RSI/成交量/布林/支撑阻力/K线形态/价格形态）
的综合评分与买卖信号判定。

实现复用原 `share300/hs300_analyzer.py` 中的 SignalAnalyzer。
"""

import importlib

from common.logging_utils import get_logger
from share300_core._paths import ensure_source_on_path

logger = get_logger(__name__)

ensure_source_on_path()
_src = importlib.import_module("hs300_analyzer")
logger.debug("share300 买卖信号模块加载完成")

# 买卖信号分析器（9 大技术指标综合评分）
SignalAnalyzer = getattr(_src, "SignalAnalyzer", None)

__all__ = ["SignalAnalyzer"]
