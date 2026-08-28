"""
app.domains.stock_watch.money_flow —— 资金面模块（P0）

专业分析师维度之二：资金面（主力 + 北向资金）。

提供：
    - 北向资金：沪股通/深股通当日净流入、历史区间净流入
    - 主力资金：个股/市场主力净流入（超大单/大单）
    - 融资融券：两融余额变化（若数据源可得）
    - 资金面综合评分与信号（流入/流出/观望）

数据源：
    - 北向资金：akshare `stock_hsgt_fund_flow_summary_em`（当日）
                `stock_hsgt_hist_em`（历史区间）
    - 主力资金：akshare `stock_main_fund_flow` / `stock_fund_flow_individual`
    - 全部通过 app.core.cache 缓存，失败返回空 dict 可降级。
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.core.cache import get_cache_manager
from app.core.logging_setup import get_logger

logger = get_logger(__name__)

try:
    import akshare as ak
    _HAS_AK = True
except Exception:  # noqa: BLE001
    ak = None
    _HAS_AK = False


@dataclass
class MoneyFlowSnapshot:
    """资金面快照。"""

    code: str = ""
    name: str = ""
    northbound_today: float | None = None   # 当日北向净流入（亿元）
    northbound_5d: float | None = None      # 近5日北向净流入（亿元）
    northbound_20d: float | None = None     # 近20日北向净流入（亿元）
    main_net_inflow: float | None = None    # 个股主力净流入（万元）
    main_net_inflow_pct: float | None = None  # 主力净流入占比
    margin_balance: float | None = None     # 两融余额（亿元，市场级）
    margin_change: float | None = None      # 两融余额变化（亿元）
    score: float | None = None
    verdict: str = "未知"


def _fetch_northbound_flow() -> dict:
    """获取北向资金当日与历史净流入。

    Returns:
        {"today", "5d", "20d"}（亿元）。失败返回空 dict。
    """
    if not _HAS_AK:
        return {}
    cache = get_cache_manager()
    cache_key = "money_flow/northbound.json"
    cached = cache.get_json(cache_key, ttl="1d")
    if cached:
        return cached
    result: dict = {}
    try:
        summary = ak.stock_hsgt_fund_flow_summary_em()
        if summary is not None and not summary.empty:
            # 北向 = 沪股通 + 深股通 当日净流入（亿元）
            north = summary[summary["资金方向"] == "北向"]
            if not north.empty and "成交净买额" in north.columns:
                total = pd.to_numeric(north["成交净买额"], errors="coerce").sum()
                result["today"] = round(float(total), 2)
    except Exception as e:  # noqa: BLE001
        logger.warning("北向当日净流入拉取失败: %s", e)
    try:
        hist = ak.stock_hsgt_hist_em(symbol="北向资金")
        if hist is not None and not hist.empty:
            hist = hist.copy()
            date_col = [c for c in hist.columns if "日期" in c]
            val_col = [c for c in hist.columns if "净买额" in c or "净流入" in c]
            if date_col and val_col:
                hist = hist.rename(columns={date_col[0]: "date", val_col[0]: "val"})
                hist["date"] = pd.to_datetime(hist["date"])
                hist["val"] = pd.to_numeric(hist["val"], errors="coerce")
                hist = hist.sort_values("date")
                if "today" not in result and not hist.empty:
                    result["today"] = round(float(hist["val"].iloc[-1]), 2)
                for days, key in ((5, "5d"), (20, "20d")):
                    sub = hist.tail(days)
                    if len(sub) > 0:
                        result[key] = round(float(sub["val"].sum()), 2)
    except Exception as e:  # noqa: BLE001
        logger.warning("北向历史净流入拉取失败: %s", e)
    if result:
        cache.set_json(cache_key, result)
    return result


def _fetch_main_flow(code: str) -> dict:
    """获取个股主力资金净流入。

    Returns:
        {"net_inflow": 万元, "net_inflow_pct": 占比}；失败返回空 dict。
    """
    if not _HAS_AK:
        return {}
    cache = get_cache_manager()
    cache_key = f"money_flow/main/{code}.json"
    cached = cache.get_json(cache_key, ttl="1d")
    if cached:
        return cached
    result: dict = {}
    try:
        df = ak.stock_fund_flow_individual(symbol=code)
        if df is not None and not df.empty:
            # 最新一行通常是当日主力净流入
            last = df.iloc[-1]
            for col in df.columns:
                if "主力净流入" in str(col) and "净占比" not in str(col):
                    result["net_inflow"] = _to_float(last[col])
                elif "主力净流入净占比" in str(col) or "主力净流入占比" in str(col):
                    result["net_inflow_pct"] = _to_float(last[col])
            if "net_inflow" in result:
                cache.set_json(cache_key, result)
    except Exception as e:  # noqa: BLE001
        logger.debug("个股主力净流入 %s 拉取失败: %s", code, e)
    return result


def _fetch_margin() -> dict:
    """获取市场融资融券余额。

    Returns:
        {"balance": 亿元, "change": 亿元}；失败返回空 dict。
    """
    if not _HAS_AK:
        return {}
    cache = get_cache_manager()
    cache_key = "money_flow/margin.json"
    cached = cache.get_json(cache_key, ttl="1d")
    if cached:
        return cached
    result: dict = {}
    # 尝试从 akshare 两融数据接口拉取（若存在）
    fn = getattr(ak, "stock_margin_sse", None) or getattr(ak, "stock_margin_account_info", None)
    if fn is None:
        return result
    try:
        df = fn()
        if df is not None and not df.empty:
            balance_col = [c for c in df.columns if "融资余额" in str(c)]
            if balance_col:
                df = df.sort_values(df.columns[0])
                latest = pd.to_numeric(df[balance_col[0]].iloc[-1], errors="coerce")
                prev = pd.to_numeric(df[balance_col[0]].iloc[-2], errors="coerce") \
                    if len(df) > 1 else None
                if latest is not None and not pd.isna(latest):
                    result["balance"] = round(float(latest) / 1e8, 2)
                if prev is not None and not pd.isna(prev):
                    result["change"] = round(float((latest - prev) / 1e8), 2)
                cache.set_json(cache_key, result)
    except Exception as e:  # noqa: BLE001
        logger.debug("两融余额拉取失败: %s", e)
    return result


def analyze_money_flow(code: str, name: str = "") -> MoneyFlowSnapshot:
    """分析个股与市场资金面。

    Args:
        code: 证券代码
        name: 证券名称（可选）

    Returns:
        MoneyFlowSnapshot 资金面快照。
    """
    snap = MoneyFlowSnapshot(code=code, name=name)
    north = _fetch_northbound_flow()
    snap.northbound_today = north.get("today")
    snap.northbound_5d = north.get("5d")
    snap.northbound_20d = north.get("20d")

    main = _fetch_main_flow(code)
    snap.main_net_inflow = main.get("net_inflow")
    snap.main_net_inflow_pct = main.get("net_inflow_pct")

    margin = _fetch_margin()
    snap.margin_balance = margin.get("balance")
    snap.margin_change = margin.get("change")

    snap.score, snap.verdict = _score_money_flow(snap)
    return snap


def _score_money_flow(snap: MoneyFlowSnapshot) -> tuple[float, str]:
    """综合资金面评分（0-100）。

    - 北向资金净流入：正分（今日+近5日）
    - 主力净流入：正分，净流入占比越高越强
    """
    scores: list[float] = []
    if snap.northbound_today is not None:
        # 当日北向净流入（亿元），-50 ~ +50 映射到 0-100
        scores.append(max(0.0, min(100.0, 50 + snap.northbound_today)))
    if snap.northbound_5d is not None:
        # 近5日净流入累计
        scores.append(max(0.0, min(100.0, 50 + snap.northbound_5d / 5)))
    if snap.main_net_inflow_pct is not None:
        # 主力净流入占比（%），-5 ~ +5 映射到 0-100
        scores.append(max(0.0, min(100.0, 50 + snap.main_net_inflow_pct * 10)))
    if not scores:
        return None, "未知"
    score = float(sum(scores) / len(scores))
    if score >= 65:
        verdict = "资金流入"
    elif score <= 35:
        verdict = "资金流出"
    else:
        verdict = "资金均衡"
    return round(score, 1), verdict


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
        return v if not pd.isna(v) else None
    except (TypeError, ValueError):
        return None
