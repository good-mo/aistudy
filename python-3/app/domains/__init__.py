"""
app.domains —— 领域业务模块

各领域模块依赖 app.data 层统一接口，不直接依赖具体数据源。
    - fund/       基金分析（筛选/评分/追踪）
    - hs300/      沪深300 分析
    - wealth/     理财产品分析
    - stock_watch/ A股盯盘

每模块包含：
    - models/   领域数据模型
    - services/ 业务服务（核心逻辑）
    - analysis/ 分析器
"""

from app.domains.fund import FundAnalyzer, FundScorer
from app.domains.hs300 import HS300Analyzer

__all__ = ["FundAnalyzer", "FundScorer", "HS300Analyzer"]
