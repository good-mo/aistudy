"""lc_core.datasources —— 数据源层。

招行理财（CMBDataSource，SM4 国密签名）、浦发理财（SPDBDataSource）、
本地 CSV 数据源。
"""

import importlib

from common.logging_utils import get_logger
from lc_core._paths import ensure_source_on_path

logger = get_logger(__name__)

ensure_source_on_path()
_src = importlib.import_module("wealth_product_analyzer")
logger.debug("lc 数据源模块加载完成")

CMBDataSource = getattr(_src, "CMBDataSource", None)
SPDBDataSource = getattr(_src, "SPDBDataSource", None)
# 本地 CSV 加载工具
load_product_codes = getattr(_src, "load_product_codes", None)
load_fund_from_csv = getattr(_src, "load_fund_from_csv", None)
load_product_detail = getattr(_src, "load_product_detail", None)

__all__ = [
    "CMBDataSource",
    "SPDBDataSource",
    "load_product_codes",
    "load_fund_from_csv",
    "load_product_detail",
]
