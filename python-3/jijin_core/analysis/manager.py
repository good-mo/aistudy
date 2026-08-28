"""
基金经理画像分析
基金经理信息抓取（缓存）、深度画像与综合评分。
"""

from ..utils.caching import get_cache_dir, load_json_cache, save_json_cache
from common.logging_utils import get_logger

logger = get_logger(__name__)

# 经理画像缓存
MGR_BASIC_CACHE = "manager/{fund_code}_basic.json"
MGR_DEEP_CACHE = "manager/{fund_code}_deep.json"
CACHE_DAYS = 7


def _scrape_manager_info(fund_code: str, force_refresh: bool = False) -> dict:
    """抓取基金经理基本信息（网络不可用时返回缓存或空）。"""
    if not force_refresh:
        cached = load_json_cache(MGR_BASIC_CACHE.format(fund_code=fund_code), CACHE_DAYS)
        if cached:
            return cached
    # 简化实现：网络抓取逻辑可在此扩展
    data = {}
    save_json_cache(MGR_BASIC_CACHE.format(fund_code=fund_code), data)
    return data


def _scrape_holdings_concentration(fund_code: str, force_refresh: bool = False) -> dict:
    """抓取持仓集中度信息。"""
    if not force_refresh:
        cached = load_json_cache(f"manager/{fund_code}_hold.json", CACHE_DAYS)
        if cached:
            return cached
    data = {}
    save_json_cache(f"manager/{fund_code}_hold.json", data)
    return data


def scrape_manager_deep_profile(fund_code: str, force_refresh: bool = False) -> dict:
    """获取基金经理深度画像（从业年限、管理规模、风格等）。"""
    if not force_refresh:
        cached = load_json_cache(MGR_DEEP_CACHE.format(fund_code=fund_code), CACHE_DAYS)
        if cached:
            return cached
    basic = _scrape_manager_info(fund_code, force_refresh)
    hold = _scrape_holdings_concentration(fund_code, force_refresh)
    profile = {
        "manager_years": basic.get("manager_years", 0),
        "fund_scale": basic.get("fund_scale", 0),
        "manager_style": basic.get("manager_style", ""),
        "holdings_concentration": hold.get("concentration", 0.0),
        "manager_level": basic.get("manager_level", ""),
    }
    save_json_cache(MGR_DEEP_CACHE.format(fund_code=fund_code), profile)
    logger.info("基金经理[%s] 深度画像：从业%d年 规模%s 风格%s",
                fund_code, profile["manager_years"], profile["fund_scale"], profile["manager_style"])
    return profile


def get_combined_manager_score(mgr_basic: dict, mgr_deep: dict) -> float:
    """综合基金经理评分（0-5）。"""
    score = 3.0
    years = mgr_deep.get("manager_years", 0) or 0
    if years >= 10:
        score += 1.0
    elif years >= 5:
        score += 0.5
    elif years >= 2:
        score += 0.2

    scale = mgr_deep.get("fund_scale", 0) or 0
    if scale >= 200:
        score += 0.5
    elif scale >= 50:
        score += 0.3

    hold = mgr_deep.get("holdings_concentration", 0) or 0
    if 0.3 <= hold <= 0.7:
        score += 0.3

    level = mgr_deep.get("manager_level", "")
    if level and "资深" in str(level):
        score += 0.5

    return round(min(score, 5.0), 2)


def get_combined_manager_score_from_enrich(
    mgr_level: str,
    mgr_years: float,
    fund_scale: float,
) -> float:
    """从增强字段快速计算经理评分。"""
    return get_combined_manager_score(
        {},
        {
            "manager_level": mgr_level,
            "manager_years": mgr_years,
            "fund_scale": fund_scale,
            "holdings_concentration": 0.0,
        },
    )


def get_mgr_profile_cache_dir() -> str:
    """返回经理画像缓存目录。"""
    return get_cache_dir("manager")
