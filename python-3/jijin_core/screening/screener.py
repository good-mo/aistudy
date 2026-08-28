"""
基金筛选主流程
基于资深基金经理逻辑的买入/卖出决策主流程。
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from ..data import load_all_funds, load_fund_nav
from ..data.sources.tencent import get_tencent_quote
from ..analysis.macro import init_macro_state, get_cycle_industry_preference, get_cycle_advice
from ..analysis.industry import classify_fund_industry, classify_fund_asset_type
from ..analysis.flow import analyze_flow_sentiment
from ..analysis.manager import scrape_manager_deep_profile, get_combined_manager_score
from ..analysis.metrics import (
    calc_annual_return,
    calc_max_drawdown,
    calc_sharpe_ratio,
    calc_calmar_ratio,
    calc_sortino_ratio,
    calc_alpha_and_ir,
    calc_nav_percentile,
    calc_monthly_win_rate,
)
from .scoring import score_fund, generate_signal, get_cycle_thresholds, calc_coarse_score
from common.logging_utils import get_logger

logger = get_logger(__name__)


def analyze_fund(fund_code: str, fund_name: str, fund_type: str = "", **kwargs) -> dict:
    """分析单只基金并返回综合评估结果。"""
    macro = init_macro_state(force_refresh=kwargs.get("force_refresh", False))
    cycle_phase = macro.get("cycle_phase", "recovery")
    preferred_style = macro.get("preferred_style", "大盘成长")

    nav = load_fund_nav(fund_code, days=1095, force_refresh=kwargs.get("force_refresh", False))
    if nav.empty or len(nav) < 2:
        return {"fund_code": fund_code, "fund_name": fund_name, "error": "净值数据不足"}

    metrics = {
        "annual_return": calc_annual_return(nav),
        "max_drawdown": calc_max_drawdown(nav),
        "sharpe": calc_sharpe_ratio(nav),
        "calmar": calc_calmar_ratio(nav),
        "sortino": calc_sortino_ratio(nav),
    }
    alpha_ir = calc_alpha_and_ir(nav, _default_benchmark())

    # 行业与资金流
    industry = classify_fund_industry(fund_name, fund_type)
    asset_type = classify_fund_asset_type(fund_name, fund_type)
    flow = analyze_flow_sentiment("", "")

    # 经理画像
    mgr = scrape_manager_deep_profile(fund_code, force_refresh=kwargs.get("force_refresh", False))
    mgr_score = get_combined_manager_score({}, mgr)

    thresholds = get_cycle_thresholds(cycle_phase, asset_type)
    score = score_fund(
        metrics["sharpe"], metrics["max_drawdown"], metrics["annual_return"],
        metrics["calmar"], metrics["sortino"], 0.0,
        style_bonus=0.0,
        manager_score=mgr_score,
        flow_score=0.0,
        valuation_score=0.0,
    )
    signal = generate_signal(
        score, metrics["sharpe"], metrics["max_drawdown"],
        metrics["annual_return"], metrics["calmar"], cycle_phase, thresholds,
    )

    return {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "fund_type": fund_type,
        "asset_type": asset_type,
        "industry": industry["industry"],
        "cycle_phase": cycle_phase,
        **metrics,
        "alpha": alpha_ir.get("alpha", 0.0),
        "information_ratio": alpha_ir.get("information_ratio", 0.0),
        "manager_score": mgr_score,
        "score": score,
        "signal": signal["signal"],
        "reason": signal["reason"],
    }


def _default_benchmark() -> pd.Series:
    """返回默认基准净值（简化，避免循环依赖）。"""
    from ..data.benchmark import get_benchmark

    return get_benchmark()


def run_screening(
    top_n: int = 50,
    max_workers: int = 8,
    force_refresh: bool = False,
    code_list: list | None = None,
) -> pd.DataFrame:
    """批量筛选基金，返回综合评分排序结果。"""
    if code_list:
        all_funds = pd.DataFrame([{"code": c, "name": c, "type": ""} for c in code_list])
    else:
        all_funds = load_all_funds(force_refresh=force_refresh)

    logger.info("开始筛选：候选基金 %d 只（top_n=%s workers=%s）", len(all_funds), top_n, max_workers)
    results = []

    def _work(row):
        try:
            return analyze_fund(row.get("code", ""), row.get("name", ""), row.get("type", ""),
                                force_refresh=force_refresh)
        except Exception:  # noqa: BLE001
            logger.exception("分析基金失败：%s", row.get("code", ""))
            return {"fund_code": row.get("code", ""), "error": "分析失败"}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_work, row) for _, row in all_funds.head(200).iterrows()]
        for fut in as_completed(futures):
            result = fut.result()
            if "error" not in result:
                results.append(result)

    df = pd.DataFrame(results)
    if not df.empty and "score" in df:
        df = df.sort_values("score", ascending=False).head(top_n)
    logger.info("筛选完成：成功 %d 只，输出前 %d 名", len(results), min(top_n, len(results)))
    return df


def analyze_holdings(force_refresh: bool = False) -> pd.DataFrame:
    """分析持有基金组合。"""
    logger.info("开始分析持仓组合")
    holdings = load_holdings()
    results = []
    for _, row in holdings.iterrows():
        r = analyze_fund(row.get("code", ""), row.get("name", ""), "", force_refresh=force_refresh)
        results.append(r)
    return pd.DataFrame(results)


def load_holdings() -> pd.DataFrame:
    """加载持仓清单（从默认持仓文件）。"""
    import os

    from ..config.settings import PROJECT_ROOT

    path = os.path.join(PROJECT_ROOT, "jijin", "readme.md")
    if not os.path.exists(path):
        return pd.DataFrame(columns=["code", "name"])
    codes = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.isdigit() and len(line) == 6:
                codes.append({"code": line, "name": line})
    return pd.DataFrame(codes)
