"""lc_core.stats —— 统计工具层。

年化波动、最大回撤、下行偏差、VaR/CVaR、偏度、峰度、胜率、
盈亏比、相关系数、跟踪误差等绩效统计指标。
"""

import importlib

from common.logging_utils import get_logger
from lc_core._paths import ensure_source_on_path

logger = get_logger(__name__)

ensure_source_on_path()
_src = importlib.import_module("wealth_product_analyzer")
logger.debug("lc 统计工具模块加载完成")

StatisticalUtils = getattr(_src, "StatisticalUtils", None)

__all__ = ["StatisticalUtils"]
