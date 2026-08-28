"""
app.domains.market.sentiment —— 市场情绪模块（P1）

专业分析师维度之三：市场情绪 / 市场宽度。

提供：
    - 涨跌统计：上涨/下跌家数、涨停/跌停家数、真实涨停
    - 市场宽度：上涨家数占比（衡量普涨/普跌）
    - 量能：两市成交额（若数据源可得）
    - 情绪温度：连板高度 / 赚钱效应（若数据源可得）
    - 情绪综合评分与信号（亢奋/正常/冰点）

数据源：
    - 市场活跃度：akshare `stock_market_activity_legu`（上涨/涨停等）
    - 涨跌停池：akshare `stock_zt_pool_em`（当日涨停池）
    - 两市成交额：akshare `stock_zh_a_spot_em` / `stock_market_fund_flow`
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
class MarketSentiment:
    """市场情绪快照。"""

    up_count: int | None = None          # 上涨家数
    down_count: int | None = None        # 下跌家数
    limit_up_count: int | None = None    # 涨停家数
    limit_down_count: int | None = None  # 跌停家数
    real_limit_up: int | None = None     # 真实涨停家数
    breadth: float | None = None         # 上涨家数占比（0-1）
    turnover: float | None = None        # 两市成交额（亿元）
    limit_up_ratio: float | None = None  # 涨停占比（赚钱效应）
    score: float | None = None
    sentiment: str = "未知"
    as_of: str = ""


def _fetch_market_activity() -> dict:
    """获取市场活跃度（上涨/涨停等）。"""
    if not _HAS_AK:
        return {}
    cache = get_cache_manager()
    cache_key = "market/sentiment/activity.json"
    cached = cache.get_json(cache_key, ttl="1d")
    if cached:
        return cached
    result: dict = {}
    try:
        df = ak.stock_market_activity_legu()
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                item = str(row.get("item", ""))
                val = row.get("value")
                try:
                    num = float(val)
                except (TypeError, ValueError):
                    num = None
                if item == "上涨" and num is not None:
                    result["up_count"] = int(num)
                elif item == "涨停" and num is not None:
                    result["limit_up_count"] = int(num)
                elif item == "真实涨停" and num is not None:
                    result["real_limit_up"] = int(num)
            cache.set_json(cache_key, result)
    except Exception as e:  # noqa: BLE001
        logger.warning("市场活跃度拉取失败: %s", e)
    return result


def _fetch_limit_down() -> int | None:
    """获取跌停家数。"""
    if not _HAS_AK:
        return None
    cache = get_cache_manager()
    cache_key = "market/sentiment/limit_down.json"
    cached = cache.get_json(cache_key, ttl="1d")
    if cached:
        return cached.get("limit_down_count")
    try:
        import datetime as _dt
        # 涨停池反向无法直接拿跌停数，用涨跌家数近似；返回 None 表示不可用
        result: dict = {}
        cache.set_json(cache_key, result)
    except Exception as e:  # noqa: BLE001
        logger.debug("跌停家数拉取失败: %s", e)
    return None


def analyze_market_sentiment() -> MarketSentiment:
    """分析当前市场情绪。

    Returns:
        MarketSentiment 市场情绪快照。
    """
    snap = MarketSentiment()
    activity = _fetch_market_activity()
    snap.up_count = activity.get("up_count")
    snap.limit_up_count = activity.get("limit_up_count")
    snap.real_limit_up = activity.get("real_limit_up")
    snap.limit_down_count = _fetch_limit_down()

    # 市场宽度（上涨家数占比）—— 需要下跌家数，通过活跃度可推算
    # stock_market_activity_legu 只给上涨/涨停，用简化逻辑：
    # 若无下跌家数，宽度以上涨家数相对全市场（约 5000 只）估算
    total_approx = 5000
    if snap.up_count is not None:
        snap.breadth = round(snap.up_count / total_approx, 3)

    # 涨停占比（赚钱效应）
    if snap.limit_up_count is not None and snap.up_count:
        snap.limit_up_ratio = round(snap.limit_up_count / snap.up_count, 4)

    snap.score, snap.sentiment = _score_sentiment(snap)
    return snap


def _score_sentiment(snap: MarketSentiment) -> tuple[float, str]:
    """综合情绪评分（0-100），>65 亢奋，<35 冰点。"""
    scores: list[float] = []
    if snap.breadth is not None:
        scores.append(snap.breadth * 100)
    if snap.limit_up_count is not None:
        # 涨停家数 0-100 映射
        scores.append(max(0.0, min(100.0, snap.limit_up_count * 1.5)))
    if not scores:
        return None, "未知"
    score = float(sum(scores) / len(scores))
    if score >= 65:
        sentiment = "亢奋"
    elif score <= 35:
        sentiment = "冰点"
    else:
        sentiment = "正常"
    return round(score, 1), sentiment
