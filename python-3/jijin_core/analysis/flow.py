"""
资金流与市场情绪分析
基金份额变动、规模变动趋势与情绪评分。
"""

from ..utils.caching import get_cache_dir, load_json_cache, save_json_cache
from common.logging_utils import get_logger

logger = get_logger(__name__)

# 资金流缓存
FLOW_CACHE_FILE = "flow/{fund_code}.json"
FLOW_CACHE_DAYS = 1


def fetch_fund_flow_data(fund_code: str, force_refresh: bool = False) -> dict:
    """获取基金资金流数据（份额/规模变动）。网络不可用时返回缓存或空。"""
    if not force_refresh:
        cached = load_json_cache(FLOW_CACHE_FILE.format(fund_code=fund_code), FLOW_CACHE_DAYS)
        if cached:
            return cached
    # 简化实现：网络获取逻辑可在此扩展；暂无数据时返回空
    data = {}
    save_json_cache(FLOW_CACHE_FILE.format(fund_code=fund_code), data)
    return data


def analyze_flow_sentiment(
    share_change_str: str,
    scale_change_str: str,
    interval: str = "近3月",
) -> str:
    """根据份额/规模变动字符串推断资金情绪。"""
    def _parse(s):
        try:
            return float(str(s).replace("%", "").strip())
        except (ValueError, AttributeError):
            return 0.0

    share = _parse(share_change_str)
    scale = _parse(scale_change_str)
    # 份额或规模持续增加 → 资金流入
    if share > 5 or scale > 5:
        return "资金明显流入"
    if share < -5 or scale < -5:
        return "资金明显流出"
    if share > 0 or scale > 0:
        return "资金温和流入"
    if share < 0 or scale < 0:
        return "资金温和流出"
    return "资金平稳"


def flow_sentiment_to_score(flow_sentiment: str) -> float:
    """将资金情绪转化为评分（0-5）。"""
    mapping = {
        "资金明显流入": 5.0,
        "资金温和流入": 3.5,
        "资金平稳": 2.5,
        "资金温和流出": 1.5,
        "资金明显流出": 0.5,
    }
    return mapping.get(flow_sentiment, 2.5)


def get_flow_cache_dir() -> str:
    """返回资金流缓存目录。"""
    return get_cache_dir("flow")
