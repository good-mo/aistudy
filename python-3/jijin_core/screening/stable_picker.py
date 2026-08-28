"""
稳健基金精选（固收+）
专注二级债基（固收+）策略，年化目标 6%，严格控制回撤。
"""

from ..data import load_all_funds
from ..analysis.industry import classify_fund_asset_type
from common.logging_utils import get_logger

logger = get_logger(__name__)


def _find_secondary_bond_candidates(max_candidates: int = 80) -> list:
    """构建二级债基（固收+）候选池。"""
    all_funds = load_all_funds(force_refresh=False)
    if all_funds.empty:
        logger.info("无基金数据，构建二级债基候选池为空")
        return []
    candidates = []
    for _, row in all_funds.iterrows():
        name = str(row.get("name", ""))
        # 固收+：名字含"债"且非纯债
        if "债" in name and "纯债" not in name and "货币" not in name:
            candidates.append({
                "code": row.get("code"),
                "name": name,
                "type": "二级债基",
            })
        if len(candidates) >= max_candidates:
            break
    logger.debug("二级债基候选池 %d 只", len(candidates))
    return candidates


def _get_asset_type(row) -> str:
    """判断基金资产类型。"""
    return classify_fund_asset_type(str(row.get("name", "")), str(row.get("type", "")))


def calc_stability_score(row) -> float:
    """计算稳健评分（回撤越小、夏普越高得分越高）。"""
    score = 50.0
    mdd = float(row.get("max_drawdown", 0) or 0)
    sharpe = float(row.get("sharpe", 0) or 0)
    ann_ret = float(row.get("annual_return", 0) or 0)

    # 回撤控制（目标 < 5%）
    if mdd < 0.03:
        score += 25
    elif mdd < 0.05:
        score += 18
    elif mdd < 0.08:
        score += 8
    else:
        score -= 10

    # 风险收益
    score += min(max(sharpe * 10, 0), 15)

    # 年化贴近 6%
    if 0.04 <= ann_ret <= 0.08:
        score += 10
    elif 0.02 <= ann_ret <= 0.10:
        score += 5

    return round(min(score, 100), 1)


def pick_stable_fund(candidates: list | None = None) -> list:
    """精选稳健基金，返回评分排序结果。"""
    from ..data.nav import load_fund_nav
    from ..analysis.metrics import (
        calc_annual_return,
        calc_max_drawdown,
        calc_sharpe_ratio,
    )

    if candidates is None:
        candidates = _find_secondary_bond_candidates()

    results = []
    for cand in candidates:
        code = cand.get("code")
        if not code:
            continue
        nav = load_fund_nav(code, days=1095)
        if nav.empty or len(nav) < 60:
            continue
        row = {
            **cand,
            "annual_return": calc_annual_return(nav),
            "max_drawdown": calc_max_drawdown(nav),
            "sharpe": calc_sharpe_ratio(nav),
        }
        row["stability_score"] = calc_stability_score(pd_series_like(row))
        results.append(row)

    results.sort(key=lambda x: x["stability_score"], reverse=True)
    return results


def pd_series_like(d: dict):
    """返回类似 row 的可访问对象（兼容 pandas Series 的 .get）。"""
    from types import SimpleNamespace

    ns = SimpleNamespace(**d)
    return ns


def main(top_n: int = 20) -> None:
    """精选入口。"""
    results = pick_stable_fund()
    print(f"{'代码':<8}{'名称':<24}{'年化':>8}{'回撤':>8}{'夏普':>8}{'稳健分':>8}")
    for r in results[:top_n]:
        print(
            f"{r['code']:<8}{r['name']:<24}"
            f"{r['annual_return']*100:>7.2f}%{r['max_drawdown']*100:>7.2f}%"
            f"{r['sharpe']:>8.2f}{r['stability_score']:>8.1f}"
        )
