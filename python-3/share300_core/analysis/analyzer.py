"""share300_core.analysis.analyzer —— 沪深300 主分析器。

封装 HS300Analyzer，统一技术 + 基本面 + 行业分析流程。
"""

import importlib

from common.logging_utils import get_logger
from share300_core._paths import ensure_source_on_path

logger = get_logger(__name__)

ensure_source_on_path()
_src = importlib.import_module("hs300_analyzer")
logger.debug("share300 主分析器模块加载完成")

# 原 HS300Analyzer 主分析器
HS300Analyzer = getattr(_src, "HS300Analyzer", None)

__all__ = ["HS300Analyzer"]
