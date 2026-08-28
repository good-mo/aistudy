"""
app.domains.stock_watch.fundamental —— 基本面指标模块（P0）

专业分析师维度之一：基本面（估值 + 盈利质量）。

提供：
    - 估值指标：PE(TTM)、PB、PS、PEG、股息率、总市值
    - 估值分位：当前 PE/PB 处于近 5/10 年历史百分位（判断贵贱的关键）
    - 盈利质量：ROE、毛利率/净利率（若数据源可得）
    - 综合基本面评分（0-100）与信号（低估/合理/高估）

数据源：
    - 优先 akshare `stock_value_em`（东财历史估值，含 PE(TTM)/PB/PS/PEG/股息率）
    - 失败时回退到指数基准或返回空（交由上层降级）

设计：
    - 通过 app.core.cache 缓存估值历史（TTL 1 天），避免高频请求
    - 所有接口失败返回 None / 空 dict，不抛异常，保证可降级
"""

from __future__ import annotations

import statistics
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

# 估值分位参考周期（交易日）
_PERCENTILE_WINDOWS = {"5y": 1250, "10y": 2500}


@dataclass
class ValuationSnapshot:
    """单只股票的基本面估值快照。"""

    code: str = ""
    name: str = ""
    pe_ttm: float | None = None
    pe_static: float | None = None
    pb: float | None = None
    ps: float | None = None
    peg: float | None = None
    dividend_yield: float | None = None
    market_cap: float | None = None
    pe_percentile_5y: float | None = None
    pb_percentile_5y: float | None = None
    pe_percentile_10y: float | None = None
    pb_percentile_10y: float | None = None
    score: float | None = None
    verdict: str = "未知"
    data_points: int = 0


def _fetch_valuation_history(code: str) -> pd.DataFrame | None:
    """获取个股历史估值数据（含 PE(TTM)/PB/PS/PEG 等）。

    Args:
        code: 证券代码（如 "600519"）

    Returns:
        按日期升序的估值 DataFrame，失败返回 None。
    """
    if not _HAS_AK:
        logger.debug("akshare 未安装，跳过估值历史 %s", code)
        return None
    cache = get_cache_manager()
    cache_key = f"fundamental/value/{code}.json"
    cached = cache.get_json(cache_key, ttl="1d")
    if cached:
        try:
            df = pd.DataFrame(cached)
            if not df.empty:
                return df
        except Exception:  # noqa: BLE001
            pass
    try:
        df = ak.stock_value_em(symbol=code)
        if df is not None and not df.empty:
            # 统一列名：PE(TTM)/市净率/市销率/PEG值/股息率/总市值
            rename = {
                "PE(TTM)": "pe_ttm",
                "PE(静)": "pe_static",
                "市净率": "pb",
                "市销率": "ps",
                "PEG值": "peg",
                "股息率": "dividend_yield",
                "总市值": "market_cap",
                "数据日期": "date",
            }
            df = df.rename(columns=rename)
            keep = [c for c in rename.values() if c in df.columns]
            df = df[keep]
            for col in keep:
                if col != "date":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["pe_ttm", "pb"], how="all")
            df = df.sort_values("date")
            # date 列转为字符串，保证可 JSON 序列化缓存
            if "date" in df.columns:
                df["date"] = df["date"].astype(str)
            cache.set_json(cache_key, df.to_dict("records"))
            logger.debug("估值历史 %s 共 %d 条", code, len(df))
            return df
    except Exception as e:  # noqa: BLE001
        logger.warning("估值历史 %s 拉取失败: %s", code, e)
    return None


def _calc_percentile(series: pd.Series, value: float) -> float | None:
    """计算当前值在历史序列中的百分位（0-100）。

    Args:
        series: 历史值序列（忽略 NaN）
        value: 当前值

    Returns:
        百分位（0~100）；数据不足返回 None。
    """
    clean = series.dropna()
    if clean.empty or value is None or pd.isna(value):
        return None
    try:
        return float((clean <= value).mean() * 100)
    except Exception:  # noqa: BLE001
        return None


def _classify_verdict(
    pe_ttm: float | None,
    pe_pct: float | None,
    pb_pct: float | None,
    pe_static: float | None,
) -> tuple[str, float]:
    """根据估值分位给出贵贱判断与综合分数。

    Returns:
        (verdict, score): verdict 为 低估/合理/高估，score 0-100。
    """
    scores: list[float] = []
    if pe_pct is not None:
        # PE 分位越低越便宜
        scores.append(max(0.0, 100.0 - pe_pct))
    if pb_pct is not None:
        scores.append(max(0.0, 100.0 - pb_pct))
    if not scores:
        return "未知", 50.0
    score = float(statistics.mean(scores))
    if score >= 70:
        verdict = "低估"
    elif score <= 30:
        verdict = "高估"
    else:
        verdict = "合理"
    return verdict, round(score, 1)


def analyze_fundamental(code: str, name: str = "") -> ValuationSnapshot:
    """分析单只股票的基本面。

    Args:
        code: 证券代码
        name: 证券名称（可选）

    Returns:
        ValuationSnapshot 估值快照。
    """
    snap = ValuationSnapshot(code=code, name=name)
    df = _fetch_valuation_history(code)
    if df is None or df.empty:
        return snap

    snap.data_points = len(df)
    # 当前值 = 最新一条
    latest = df.iloc[-1]
    snap.pe_ttm = _to_float(latest.get("pe_ttm"))
    snap.pe_static = _to_float(latest.get("pe_static"))
    snap.pb = _to_float(latest.get("pb"))
    snap.ps = _to_float(latest.get("ps"))
    snap.peg = _to_float(latest.get("peg"))
    snap.dividend_yield = _to_float(latest.get("dividend_yield"))
    snap.market_cap = _to_float(latest.get("market_cap"))

    # 估值分位
    for label, window in _PERCENTILE_WINDOWS.items():
        sub = df.tail(window)
        if len(sub) < 60:  # 至少 60 个交易日才有统计意义
            continue
        snap.pe_percentile_5y = _calc_percentile(
            sub["pe_ttm"], snap.pe_ttm) if label == "5y" else snap.pe_percentile_5y
        snap.pb_percentile_5y = _calc_percentile(
            sub["pb"], snap.pb) if label == "5y" else snap.pb_percentile_5y
        snap.pe_percentile_10y = _calc_percentile(
            sub["pe_ttm"], snap.pe_ttm) if label == "10y" else snap.pe_percentile_10y
        snap.pb_percentile_10y = _calc_percentile(
            sub["pb"], snap.pb) if label == "10y" else snap.pb_percentile_10y

    # 使用 10 年分位（不足则用 5 年）
    pe_pct = snap.pe_percentile_10y if snap.pe_percentile_10y is not None else snap.pe_percentile_5y
    pb_pct = snap.pb_percentile_10y if snap.pb_percentile_10y is not None else snap.pb_percentile_5y
    snap.verdict, snap.score = _classify_verdict(
        snap.pe_ttm, pe_pct, pb_pct, snap.pe_static)
    return snap


def _to_float(value) -> float | None:
    """安全转 float。"""
    if value is None:
        return None
    try:
        v = float(value)
        return v if not pd.isna(v) else None
    except (TypeError, ValueError):
        return None
