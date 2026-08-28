"""
app.domains.market —— 市场情绪与宏观模块

专业分析师维度：
    - sentiment：市场情绪 / 市场宽度 / 涨跌停
    - macro：宏观利率（货币供应 / 国债收益率 / LPR）
"""

from app.domains.market.sentiment import MarketSentiment, analyze_market_sentiment
from app.domains.macro.macro_data import MacroSnapshot, analyze_macro

__all__ = [
    "MarketSentiment",
    "analyze_market_sentiment",
    "MacroSnapshot",
    "analyze_macro",
]
