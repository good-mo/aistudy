"""
app.domains.wealth —— 理财产品分析模块

提供理财产品的深度画像分析、汇总与定时监控能力。
"""

from app.domains.wealth.analyzer import (
    DeepProductAnalyzer,
    FinancialProduct,
    InvestorProfile,
    WealthAnalyzer,
)
from app.domains.wealth.monitor import LcAlertConfig, LcMonitor

__all__ = [
    "WealthAnalyzer",
    "DeepProductAnalyzer",
    "FinancialProduct",
    "InvestorProfile",
    "LcMonitor",
    "LcAlertConfig",
]
