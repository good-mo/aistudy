"""share300_core.analysis —— 分析层。

封装沪深300 成分股的技术指标计算、买卖信号判定与基本面评分。

实现复用原 `share300/hs300_analyzer.py` 中经实测验证的分析逻辑
（避免重复移植上万行），以包形式提供干净的分层接口。
"""

import importlib

from share300_core._paths import ensure_source_on_path

ensure_source_on_path()
_src = importlib.import_module("hs300_analyzer")


def _bind(name):
    return getattr(_src, name, None)


# 技术指标计算器（MA/MACD/KDJ/RSI/成交量/布林带）
TechnicalIndicators = _bind("TechnicalIndicators")
# 买卖信号分析器（9 大技术指标综合评分）
SignalAnalyzer = _bind("SignalAnalyzer")
# 基本面评分器
FundamentalScorer = _bind("FundamentalScorer")
# 基本面数据获取器
FundamentalDataFetcher = _bind("FundamentalDataFetcher")
# 行业数据获取器
IndustryDataFetcher = _bind("IndustryDataFetcher")

__all__ = [
    "TechnicalIndicators",
    "SignalAnalyzer",
    "FundamentalScorer",
    "FundamentalDataFetcher",
    "IndustryDataFetcher",
]
