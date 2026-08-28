"""lc_core.models —— 数据模型层。

FinancialProduct：理财产品数据模型
InvestorProfile：投资者画像模型
"""

import importlib

from common.logging_utils import get_logger
from lc_core._paths import ensure_source_on_path

logger = get_logger(__name__)

ensure_source_on_path()
_src = importlib.import_module("wealth_product_analyzer")
logger.debug("lc 数据模型模块加载完成")

FinancialProduct = getattr(_src, "FinancialProduct", None)
InvestorProfile = getattr(_src, "InvestorProfile", None)

__all__ = ["FinancialProduct", "InvestorProfile"]
