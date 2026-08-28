"""lc_core.analysis —— 分析层。

涵盖业绩分析、组合分析、信用分析、费率分析、行为金融、时机判断、
投资经理评估、资产配置穿透等各类理财分析器。

实现复用原 `lc/wealth_product_analyzer.py` 中经实测验证的分析逻辑。
"""

import importlib

from common.logging_utils import get_logger
from lc_core._paths import ensure_source_on_path

logger = get_logger(__name__)

ensure_source_on_path()
_src = importlib.import_module("wealth_product_analyzer")
logger.debug("lc 分析器模块加载完成")


def _bind(name):
    return getattr(_src, name, None)


# 投资经理评估
ManagerEvaluator = _bind("ManagerEvaluator")
PersonalManagerEvaluator = _bind("PersonalManagerEvaluator")
# 市场环境
MarketContext = _bind("MarketContext")
# 行为金融
BehavioralAdvisor = _bind("BehavioralAdvisor")
# 组合分析
PortfolioAnalyzer = _bind("PortfolioAnalyzer")
# 时机判断
TimingAdvisor = _bind("TimingAdvisor")
# 资产配置穿透
AssetAllocationParser = _bind("AssetAllocationParser")
# 信用质量
CreditQualityAnalyzer = _bind("CreditQualityAnalyzer")
# 费率竞争力
FeeCompetitivenessAnalyzer = _bind("FeeCompetitivenessAnalyzer")
# 期限提取
TermExtractor = _bind("TermExtractor")
# 深度产品分析器（核心）
DeepProductAnalyzer = _bind("DeepProductAnalyzer")
# 报告打印
print_full_report = _bind("print_full_report")
print_peer_comparison_report = _bind("print_peer_comparison_report")

__all__ = [
    "ManagerEvaluator",
    "PersonalManagerEvaluator",
    "MarketContext",
    "BehavioralAdvisor",
    "PortfolioAnalyzer",
    "TimingAdvisor",
    "AssetAllocationParser",
    "CreditQualityAnalyzer",
    "FeeCompetitivenessAnalyzer",
    "TermExtractor",
    "DeepProductAnalyzer",
    "print_full_report",
    "print_peer_comparison_report",
]
