"""
app.domains.macro.macro_data —— 宏观利率模块（P2）

专业分析师维度之五：宏观面 / 利率。

提供：
    - 货币供应：M1 / M2 同比增速、M1-M2 剪刀差（资金活化指标）
    - 利率：10 年期国债收益率、10Y-2Y 利差（估值中枢）、LPR
    - 宏观综合信号与市场环境判断（宽松/正常/收紧）

数据源：
    - 货币供应：akshare `macro_china_money_supply`
    - 国债收益率：akshare `bond_zh_us_rate`
    - LPR：akshare `macro_china_lpr`
    - 全部通过 app.core.cache 缓存（TTL 1 天），失败返回空 dict 可降级。
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
class MacroSnapshot:
    """宏观环境快照。"""

    m1_yoy: float | None = None       # M1 同比（%）
    m2_yoy: float | None = None       # M2 同比（%）
    m1m2_gap: float | None = None     # M1-M2 剪刀差（%）
    bond_10y: float | None = None     # 10 年期国债收益率（%）
    bond_2y: float | None = None      # 2 年期国债收益率（%）
    yield_curve: float | None = None  # 10Y-2Y 利差（%）
    lpr_1y: float | None = None       # 1 年期 LPR（%）
    lpr_5y: float | None = None       # 5 年期以上 LPR（%）
    environment: str = "未知"
    score: float | None = None


def _fetch_money_supply() -> dict:
    """获取 M1/M2 货币供应数据。"""
    if not _HAS_AK:
        return {}
    cache = get_cache_manager()
    cache_key = "macro/money_supply.json"
    cached = cache.get_json(cache_key, ttl="1d")
    if cached:
        return cached
    result: dict = {}
    try:
        df = ak.macro_china_money_supply()
        if df is not None and not df.empty:
            df = df.copy()
            # 列名含 M2/M1 同比
            m2_col = [c for c in df.columns if "M2" in str(c) and "同比" in str(c)]
            m1_col = [c for c in df.columns if "M1" in str(c) and "同比" in str(c)]
            if m2_col:
                result["m2_yoy"] = _to_float(df[m2_col[0]].iloc[0])
            if m1_col:
                result["m1_yoy"] = _to_float(df[m1_col[0]].iloc[0])
            if "m1_yoy" in result and "m2_yoy" in result:
                result["m1m2_gap"] = round(result["m1_yoy"] - result["m2_yoy"], 1)
            if result:
                cache.set_json(cache_key, result)
    except Exception as e:  # noqa: BLE001
        logger.warning("货币供应拉取失败: %s", e)
    return result


def _fetch_bond_rate() -> dict:
    """获取国债收益率。"""
    if not _HAS_AK:
        return {}
    cache = get_cache_manager()
    cache_key = "macro/bond_rate.json"
    cached = cache.get_json(cache_key, ttl="1d")
    if cached:
        return cached
    result: dict = {}
    try:
        df = ak.bond_zh_us_rate()
        if df is not None and not df.empty:
            df = df.copy()
            last = df.iloc[-1]
            col_10 = [c for c in df.columns if "中国国债收益率10年" in str(c)]
            col_2 = [c for c in df.columns if "中国国债收益率2年" in str(c)]
            if col_10:
                result["bond_10y"] = _to_float(last[col_10[0]])
            if col_2:
                result["bond_2y"] = _to_float(last[col_2[0]])
            if "bond_10y" in result and "bond_2y" in result:
                result["yield_curve"] = round(result["bond_10y"] - result["bond_2y"], 2)
            if result:
                cache.set_json(cache_key, result)
    except Exception as e:  # noqa: BLE001
        logger.warning("国债收益率拉取失败: %s", e)
    return result


def _fetch_lpr() -> dict:
    """获取 LPR 利率。"""
    if not _HAS_AK:
        return {}
    cache = get_cache_manager()
    cache_key = "macro/lpr.json"
    cached = cache.get_json(cache_key, ttl="1d")
    if cached:
        return cached
    result: dict = {}
    try:
        df = ak.macro_china_lpr()
        if df is not None and not df.empty:
            df = df.copy()
            last = df.iloc[-1]
            for col in df.columns:
                if "1年期" in str(col):
                    result["lpr_1y"] = _to_float(last[col])
                elif "5年期" in str(col) or "5年以上" in str(col):
                    result["lpr_5y"] = _to_float(last[col])
            if result:
                cache.set_json(cache_key, result)
    except Exception as e:  # noqa: BLE001
        logger.warning("LPR 拉取失败: %s", e)
    return result


def analyze_macro() -> MacroSnapshot:
    """分析当前宏观环境。

    Returns:
        MacroSnapshot 宏观环境快照。
    """
    snap = MacroSnapshot()
    money = _fetch_money_supply()
    snap.m1_yoy = money.get("m1_yoy")
    snap.m2_yoy = money.get("m2_yoy")
    snap.m1m2_gap = money.get("m1m2_gap")

    bond = _fetch_bond_rate()
    snap.bond_10y = bond.get("bond_10y")
    snap.bond_2y = bond.get("bond_2y")
    snap.yield_curve = bond.get("yield_curve")

    lpr = _fetch_lpr()
    snap.lpr_1y = lpr.get("lpr_1y")
    snap.lpr_5y = lpr.get("lpr_5y")

    snap.score, snap.environment = _score_macro(snap)
    return snap


def _score_macro(snap: MacroSnapshot) -> tuple[float, str]:
    """宏观环境综合评分（0-100），>65 宽松，<35 收紧。"""
    scores: list[float] = []
    # M1-M2 剪刀差回升 = 资金活化、利好股市
    if snap.m1m2_gap is not None:
        # 剪刀差 0 附近为中性，正值（M1 快于 M2）偏宽松
        scores.append(max(0.0, min(100.0, 50 + snap.m1m2_gap * 10)))
    # 10 年国债收益率下行 = 估值中枢抬升
    if snap.bond_10y is not None:
        scores.append(max(0.0, min(100.0, 100 - (snap.bond_10y - 2.0) * 30)))
    # 10Y-2Y 利差为正（陡峭）偏经济复苏
    if snap.yield_curve is not None:
        scores.append(max(0.0, min(100.0, 50 + snap.yield_curve * 20)))
    if not scores:
        return None, "未知"
    score = float(sum(scores) / len(scores))
    if score >= 65:
        env = "宽松"
    elif score <= 35:
        env = "收紧"
    else:
        env = "正常"
    return round(score, 1), env


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
        return v if not pd.isna(v) else None
    except (TypeError, ValueError):
        return None
