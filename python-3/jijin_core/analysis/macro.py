"""
宏观周期分析
宏观状态初始化、周期判断、行业偏好与风格建议。
"""

from ..config.settings import STYLE_BENCHMARK_WEIGHTS
from ..data.sources.akshare_source import fetch_macro_data
from ..utils.caching import load_json_cache, save_json_cache
from common.logging_utils import get_logger

logger = get_logger(__name__)

# 宏观状态全局
MACRO_STATE = {
    "pmi_manufacturing": None,
    "pmi_trend": None,
    "csi300_pe": None,
    "bond_10y": None,
    "equity_risk_premium": None,
    "cycle_phase": None,
    "preferred_style": None,
    "data_source": "manual_fallback",
}

MACRO_CACHE_FILE = "macro_state.json"
MACRO_CACHE_DAYS = 1


def init_macro_state(force_refresh: bool = False) -> dict:
    """初始化宏观状态，优先读缓存，否则动态获取并做降级回退。"""
    global MACRO_STATE
    if not force_refresh:
        cached = load_json_cache(MACRO_CACHE_FILE, MACRO_CACHE_DAYS)
        if cached:
            MACRO_STATE.update(cached)
            logger.debug("命中宏观状态缓存：%s", MACRO_CACHE_FILE)
            return MACRO_STATE

    data = fetch_macro_data(force_refresh=force_refresh)
    # 降级回退：宏观数据获取失败时使用人工设定的周期假设
    MACRO_STATE["pmi_manufacturing"] = data.get("pmi_manufacturing")
    MACRO_STATE["cycle_phase"] = _infer_cycle_phase(MACRO_STATE["pmi_manufacturing"])
    MACRO_STATE["preferred_style"] = _style_for_cycle(MACRO_STATE["cycle_phase"])
    MACRO_STATE["data_source"] = "auto" if data else "manual_fallback"
    save_json_cache(MACRO_CACHE_FILE, MACRO_STATE)
    logger.info(
        "宏观状态初始化完成：周期=%s 风格=%s 数据源=%s",
        MACRO_STATE["cycle_phase"], MACRO_STATE["preferred_style"], MACRO_STATE["data_source"],
    )
    return MACRO_STATE


def _infer_cycle_phase(pmi: float | None) -> str:
    """根据 PMI 推断经济周期阶段。"""
    if pmi is None:
        return "recovery"  # 缺省假设为复苏期
    if pmi >= 52:
        return "overheat"
    if pmi >= 50:
        return "recovery"
    if pmi >= 48:
        return "stagflation"
    return "recession"


def _style_for_cycle(cycle_phase: str) -> str:
    """根据周期阶段给出偏好风格。"""
    mapping = {
        "overheat": "大盘价值",
        "recovery": "大盘成长",
        "stagflation": "大盘价值",
        "recession": "大盘价值",
    }
    return mapping.get(cycle_phase, "大盘成长")


def get_cycle_industry_preference(cycle_phase: str) -> list:
    """根据周期阶段返回行业偏好。"""
    mapping = {
        "overheat": ["有色金属", "钢铁", "煤炭", "化工"],
        "recovery": ["电子", "新能源", "医药", "食品饮料"],
        "stagflation": ["公用事业", "消费", "农业"],
        "recession": ["银行", "公用事业", "基建"],
    }
    return mapping.get(cycle_phase, [])


def get_cycle_advice(cycle: str) -> str:
    """生成周期配置建议文案。"""
    advice = {
        "overheat": "经济过热期：关注顺周期资源品与价值风格，控制仓位、注意通胀风险。",
        "recovery": "经济复苏期：成长风格占优，可适度提升股票型基金配置比例。",
        "stagflation": "滞胀期：防御为主，优选固收+与价值蓝筹，降低波动。",
        "recession": "衰退期：以稳健配置为核心，加大债券与货币基金比例。",
    }
    return advice.get(cycle, "市场环境不确定，建议均衡配置、控制回撤。")
