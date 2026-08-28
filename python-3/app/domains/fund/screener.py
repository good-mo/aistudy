"""
app.domains.fund.screener —— 基金筛选

从原始 jijin_core.screening.screener 提炼而来，基于资深基金经理逻辑的
买入/卖出决策主流程，统一接入 app.data 数据层。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from app.core.logging_setup import get_logger
from app.data.fund_nav import get_fund_nav_df
from app.domains.fund.metrics import (
    calc_alpha_and_ir,
    calc_annual_return,
    calc_calmar_ratio,
    calc_max_drawdown,
    calc_sharpe_ratio,
    calc_sortino_ratio,
)
from app.domains.fund.scoring import generate_signal, get_cycle_thresholds, score_fund

logger = get_logger(__name__)

# 内置兜底基金池（无外部数据源时用于演示）
_DEFAULT_FUND_POOL = [
    {"code": "110011", "name": "易方达中小盘", "type": "股票型"},
    {"code": "009665", "name": "华夏成长", "type": "混合型"},
    {"code": "000001", "name": "华夏成长A", "type": "混合型"},
]


class FundScreener:
    """基金筛选器。"""

    def __init__(self, max_workers: int = 8):
        self.max_workers = max_workers

    def analyze_fund(
        self, fund_code: str, fund_name: str = "", fund_type: str = "",
        *, force_refresh: bool = False, days: int = 1095,
    ) -> dict:
        """分析单只基金并返回综合评估结果。"""
        nav = get_fund_nav_df(fund_code, days=days, force_refresh=force_refresh)
        if nav.empty or len(nav) < 2:
            return {"fund_code": fund_code, "fund_name": fund_name, "error": "净值数据不足"}

        metrics = {
            "annual_return": calc_annual_return(nav),
            "max_drawdown": calc_max_drawdown(nav),
            "sharpe": calc_sharpe_ratio(nav),
            "calmar": calc_calmar_ratio(nav),
            "sortino": calc_sortino_ratio(nav),
        }

        score = score_fund(
            metrics["sharpe"], metrics["max_drawdown"], metrics["annual_return"],
            metrics["calmar"], metrics["sortino"], 0.0,
        )
        signal = generate_signal(
            score, metrics["sharpe"], metrics["max_drawdown"],
            metrics["annual_return"], metrics["calmar"],
        )

        return {
            "fund_code": fund_code,
            "fund_name": fund_name or fund_code,
            "fund_type": fund_type,
            "asset_type": "股票" if "股票" in fund_type else "混合",
            **metrics,
            "score": score,
            "signal": signal["signal"],
            "reason": signal["reason"],
        }

    def run_screening(
        self,
        top_n: int = 50,
        force_refresh: bool = False,
        code_list: list | None = None,
    ) -> pd.DataFrame:
        """批量筛选基金，返回综合评分排序结果。"""
        if code_list:
            all_funds = pd.DataFrame(
                [{"code": c, "name": c, "type": ""} for c in code_list]
            )
        else:
            all_funds = pd.DataFrame(_DEFAULT_FUND_POOL)

        logger.info("开始筛选：候选基金 %d 只（top_n=%s workers=%s）", len(all_funds), top_n, self.max_workers)
        results = []

        def _work(row):
            try:
                return self.analyze_fund(
                    row.get("code", ""), row.get("name", ""), row.get("type", ""),
                    force_refresh=force_refresh,
                )
            except Exception:  # noqa: BLE001
                logger.exception("分析基金失败：%s", row.get("code", ""))
                return {"fund_code": row.get("code", ""), "error": "分析失败"}

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [
                pool.submit(_work, row) for _, row in all_funds.head(200).iterrows()
            ]
            for fut in as_completed(futures):
                result = fut.result()
                if "error" not in result:
                    results.append(result)

        df = pd.DataFrame(results)
        if not df.empty and "score" in df:
            df = df.sort_values("score", ascending=False).head(top_n)
        logger.info("筛选完成：成功 %d 只，输出前 %d 名", len(results), min(top_n, len(results)))
        return df

    def analyze_holdings(self, holdings: pd.DataFrame | None = None) -> pd.DataFrame:
        """分析持仓组合。"""
        logger.info("开始分析持仓组合")
        if holdings is None:
            holdings = pd.DataFrame(
                [{"code": "110011", "name": "易方达中小盘", "type": ""}]
            )
        results = []
        for _, row in holdings.iterrows():
            r = self.analyze_fund(
                str(row.get("code", "")), str(row.get("name", "")), "",
            )
            results.append(r)
        return pd.DataFrame(results)
