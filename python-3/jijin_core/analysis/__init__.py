"""分析包：绩效指标、宏观、行业、资金流、经理画像等分析能力。"""

from .metrics import (
    calc_annual_return,
    calc_max_drawdown,
    calc_volatility,
    calc_sharpe_ratio,
    calc_calmar_ratio,
    calc_sortino_ratio,
    calc_tracking_error_and_difference,
    calc_information_ratio,
    calc_alpha_and_ir,
    calc_nav_percentile,
    calc_downside_capture,
    calc_upside_capture,
    calc_monthly_win_rate,
    calc_drawdown_recovery,
    calc_rolling_metrics,
)
from .macro import (
    MACRO_STATE,
    init_macro_state,
    get_cycle_industry_preference,
    get_cycle_advice,
)
from .industry import (
    classify_fund_industry,
    calc_industry_concentration,
    classify_fund_asset_type,
    classify_fund_type_label,
)
from .flow import (
    fetch_fund_flow_data,
    analyze_flow_sentiment,
    flow_sentiment_to_score,
    get_flow_cache_dir,
)
from .manager import (
    scrape_manager_deep_profile,
    get_combined_manager_score,
    get_combined_manager_score_from_enrich,
    get_mgr_profile_cache_dir,
)

__all__ = [
    "calc_annual_return",
    "calc_max_drawdown",
    "calc_volatility",
    "calc_sharpe_ratio",
    "calc_calmar_ratio",
    "calc_sortino_ratio",
    "calc_tracking_error_and_difference",
    "calc_information_ratio",
    "calc_alpha_and_ir",
    "calc_nav_percentile",
    "calc_downside_capture",
    "calc_upside_capture",
    "calc_monthly_win_rate",
    "calc_drawdown_recovery",
    "calc_rolling_metrics",
    "MACRO_STATE",
    "init_macro_state",
    "get_cycle_industry_preference",
    "get_cycle_advice",
    "classify_fund_industry",
    "calc_industry_concentration",
    "classify_fund_asset_type",
    "classify_fund_type_label",
    "fetch_fund_flow_data",
    "analyze_flow_sentiment",
    "flow_sentiment_to_score",
    "get_flow_cache_dir",
    "scrape_manager_deep_profile",
    "get_combined_manager_score",
    "get_combined_manager_score_from_enrich",
    "get_mgr_profile_cache_dir",
]
