"""
lc_core —— 理财产品深度分析专业工具箱
=====================================

对 lc/wealth_product_analyzer.py（招行/浦发理财深度分析）的专业化重构，
按分层架构组织：

    lc_core/
    ├── models/      数据模型（FinancialProduct、InvestorProfile）
    ├── stats/       统计工具（波动率/回撤/夏普/偏度/峰度等）
    ├── datasources/ 数据源（招行 CMB / 浦发 SPDB / 本地 CSV）
    ├── analysis/    分析层（业绩/信用/费率/组合/行为/时机等）
    ├── cli/         命令行入口
    └── __init__.py  包入口

依赖：pip install pandas numpy requests gmssl scipy
"""

from lc_core.models.product import FinancialProduct, InvestorProfile

__all__ = ["FinancialProduct", "InvestorProfile"]
__version__ = "1.0.0"
