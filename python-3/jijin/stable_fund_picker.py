"""
年化 6% 稳健基金精选 —— 专注二级债基（固收+）策略
基于 fund_screener.py 的完整分析框架，以专业基金经理视角筛选：
  - 目标年化：精确瞄准 6%
  - 成立 5 年以上（经历完整牛熊周期）
  - 最大回撤 < 5%（严格控制下行风险）
  - 基金经理稳定（管理团队可靠）
  - 风险收益比优秀（夏普比率、波动率综合考量）
"""

import sys
import os

# 确保可以导入同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from fund_screener import (
    init_macro_state, MACRO_STATE,
    _get_cycle_advice, STYLE_BENCHMARK_WEIGHTS,
    analyze_fund, load_all_funds, load_all_benchmarks,
)

# ============================================================
# 二级债基（固收+）候选池构建
# ============================================================

def _find_secondary_bond_candidates(max_candidates: int = 80) -> pd.DataFrame:
    """
    从全市场基金缓存中筛选符合 年化6% 二级债基（固收+）特征的候选基金：
      1. 名称包含 "债" 且非 可转债/纯债/短债/指数/ETF
      2. 成立 >= 5 年
      3. 近1年收益率 5%–7%（宽筛，精细分析时再做精确 6% 匹配）
      4. 近2年、近3年收益率也接近 6% 区间（长期稳定性验证）
      5. 规模 >= 1 亿
    """
    from fund_screener import load_all_funds
    all_funds = load_all_funds(force_refresh=False)
    if all_funds.empty:
        return pd.DataFrame()

    df = all_funds.copy()
    name = df["基金简称"].astype(str)

    # 1. 债券型关键词
    bond_mask = name.str.contains("债|债券", na=False)
    df = df[bond_mask].copy()

    # 2. 排除高风险/特殊类型
    exclude_kw = ["可转债", "纯债", "短债", "中短债", "指数", "ETF", "联接", "QDII", "美元"]
    for kw in exclude_kw:
        df = df[~name[df.index].str.contains(kw, na=False)]

    # 3. 成立 >= 5 年
    df["_成立日期"] = pd.to_datetime(df["成立日期"], errors="coerce")
    five_years_ago = datetime.now() - timedelta(days=5 * 365)
    df = df[df["_成立日期"] < five_years_ago]

    # 4. 近1年收益率 5%–7%（宽筛区间，精细分析再做精准 6% 匹配）
    df["近1年"] = pd.to_numeric(df["近1年"], errors="coerce")
    df["近2年"] = pd.to_numeric(df["近2年"], errors="coerce")
    df["近3年"] = pd.to_numeric(df["近3年"], errors="coerce")
    df["近6月"] = pd.to_numeric(df["近6月"], errors="coerce")
    df = df[(df["近1年"] >= 5) & (df["近1年"] <= 7)]

    # 5. 规模过滤
    df["基金规模"] = pd.to_numeric(df["基金规模"], errors="coerce")
    df = df[df["基金规模"].isna() | (df["基金规模"] >= 1.0)]

    # 6. 计算与目标 6% 的偏离度（近1年+近2年+近3年的综合偏离）
    df["_偏离6pct"] = (
        abs(df["近1年"].fillna(6) - 6) * 0.5 +
        abs(df["近2年"].fillna(6) - 6) * 0.3 +
        abs(df["近3年"].fillna(6) - 6) * 0.2
    )
    # 按偏离度升序（越接近6%越靠前）
    df = df.sort_values("_偏离6pct", ascending=True)
    df = df.head(max_candidates)

    return df


def _get_asset_type(row: pd.Series) -> str:
    """判断基金资产类型：债券/股票/混合/货币/其他"""
    asset = str(row.get("资产类别", ""))
    ftype = str(row.get("基金类型", ""))
    name = str(row.get("基金名称", ""))
    if asset in ("债券", "货币"):
        return asset
    # 基金类型中包含债券关键词
    for kw in ["债券", "纯债", "信用债", "利率债", "短债", "转债"]:
        if kw in ftype or kw in name:
            return "债券"
    if "货币" in ftype or "货币" in name:
        return "货币"
    if asset == "股票" or "股票" in ftype:
        return "股票"
    return "混合"


def calc_stability_score(row: pd.Series) -> float:
    """
    年化 6% 二级债基（固收+）专项评分 —— 满分 100
    以专业基金经理视角，瞄准 6% 年化收益目标，综合考量风险收益比。

    核心考量维度（按年化6%目标校准）：
    1. 最大回撤控制（28分）—— 回撤 < 5% 满分，> 10% 0分
    2. 年化收益匹配（25分）—— 精确瞄准 6%，5.5%–6.5% 为最佳区间
    3. 波动率控制（15分）—— 波动越小越好，二级债基应 < 5%
    4. 夏普比率（12分）—— 风险调整收益，2.0+ 满分
    5. 月度胜率（8分）—— 跑赢基准的稳定性
    6. 回撤修复速度（5分）—— 下跌后快速回本
    7. 基金规模（4分）—— 规模适度（5-50亿为佳）
    8. 经理团队稳定性（3分）—— 团队稳定加分
    """
    score = 0.0
    max_possible = 0.0

    # ---- 1. 最大回撤（28分）—— 核心风控指标 ----
    mdd_str = str(row.get("最大回撤", "-100%"))
    try:
        mdd_val = float(mdd_str.strip("%")) / 100
    except (ValueError, AttributeError):
        mdd_val = -0.10

    if not np.isnan(mdd_val):
        # 回撤 < 3% → 满分，3%–5% → 轻微衰减，> 10% → 0分
        if mdd_val >= 0:
            mdd_sub = 28
        elif mdd_val > -0.02:
            mdd_sub = 28 * (1 + mdd_val / 0.02) ** 0.3
        elif mdd_val > -0.03:
            mdd_sub = 28 * (1 - (abs(mdd_val) - 0.02) / 0.01 * 0.15)
        elif mdd_val > -0.05:
            mdd_sub = 28 * (1 - (abs(mdd_val) - 0.02) / 0.03 * 0.5)
        elif mdd_val > -0.08:
            mdd_sub = 28 * (1 - (abs(mdd_val) - 0.02) / 0.06)
        elif mdd_val > -0.10:
            mdd_sub = max(0, 28 * (1 - (abs(mdd_val) - 0.02) / 0.08) ** 0.7)
        else:
            mdd_sub = 0
        score += mdd_sub
    max_possible += 28

    # ---- 2. 年化收益（25分）—— 精确瞄准 6% ----
    ann_ret_str = str(row.get("年化收益", "0%"))
    try:
        ann_ret_val = float(ann_ret_str.strip("%")) / 100
    except (ValueError, AttributeError):
        ann_ret_val = 0.06

    if not np.isnan(ann_ret_val):
        # 以 6% 为精确目标，窄正态分布：
        #   偏离 < 0.3% → 满分
        #   偏离 0.3%–1.0% → 缓慢衰减
        #   偏离 1.0%–2.0% → 加速衰减
        #   偏离 > 2.0% → 大幅扣分
        target = 0.06
        deviation = abs(ann_ret_val - target)
        if deviation <= 0.003:
            ret_sub = 25
        elif deviation <= 0.01:
            ret_sub = 25 * (1 - (deviation - 0.003) / 0.007 * 0.25)
        elif deviation <= 0.02:
            ret_sub = 25 * (1 - (deviation - 0.003) / 0.017 * 0.6)
        elif deviation <= 0.03:
            ret_sub = 25 * (1 - (deviation - 0.003) / 0.027 * 0.85)
        else:
            ret_sub = max(0, 25 * (1 - deviation / 0.08))
        score += ret_sub
    max_possible += 25

    # ---- 3. 年化波动（15分） ----
    vol_str = str(row.get("年化波动", "50%"))
    try:
        vol_val = float(vol_str.strip("%")) / 100
    except (ValueError, AttributeError):
        vol_val = 0.15

    if not np.isnan(vol_val):
        # 二级债基波动：2%→满分, 10%→0分
        if vol_val <= 0.02:
            vol_sub = 15
        elif vol_val <= 0.05:
            vol_sub = 15 * (1 - (vol_val - 0.02) / 0.03 * 0.4)
        elif vol_val <= 0.08:
            vol_sub = 15 * (1 - (vol_val - 0.02) / 0.06) ** 0.6
        else:
            vol_sub = max(0, 15 * (1 - vol_val / 0.12))
        score += vol_sub
    max_possible += 15

    # ---- 4. 夏普比率（12分） ----
    sharpe_str = str(row.get("夏普比率", "0"))
    try:
        sharpe_val = float(sharpe_str)
    except (ValueError, AttributeError):
        sharpe_val = 0

    if not np.isnan(sharpe_val):
        # 二级债基：夏普 2.0+ → 满分
        sharpe_sub = np.clip((sharpe_val + 0.5) / 2.5 * 12, 0, 12)
        score += sharpe_sub
    max_possible += 12

    # ---- 5. 月度胜率（8分） ----
    win_str = str(row.get("月度胜率", "0%"))
    try:
        win_val = float(win_str.strip("%")) / 100
    except (ValueError, AttributeError):
        win_val = 0

    if not np.isnan(win_val):
        # 债券型胜率天然偏高，80%+ → 满分
        win_sub = np.clip(win_val / 0.80 * 8, 0, 8)
        score += win_sub
    max_possible += 8

    # ---- 6. 回撤修复速度（5分） ----
    dd_str = str(row.get("最大回撤修复天", "999"))
    try:
        dd_val = float(dd_str)
    except (ValueError, AttributeError):
        dd_val = 999

    if not np.isnan(dd_val):
        if dd_val <= 30:
            dd_sub = 5
        elif dd_val <= 90:
            dd_sub = 5 * (1 - (dd_val - 30) / 60 * 0.4)
        elif dd_val <= 180:
            dd_sub = 5 * (1 - (dd_val - 30) / 150) ** 0.6
        else:
            dd_sub = max(0, 5 * (1 - dd_val / 365))
        score += dd_sub
    max_possible += 5

    # ---- 7. 基金规模（4分）—— 5-50亿为佳 ----
    scale_str = str(row.get("基金规模(亿)", "0"))
    try:
        scale_val = float(scale_str)
    except (ValueError, AttributeError):
        scale_val = 0

    if not np.isnan(scale_val) and scale_val > 0:
        # 5-50亿最佳区间，正态分布
        if 5 <= scale_val <= 50:
            scale_sub = 4
        elif scale_val < 5:
            scale_sub = scale_val / 5 * 4
        else:
            # 超过50亿适当扣分（规模太大运作不灵活）
            scale_sub = max(1, 4 - (scale_val - 50) / 50 * 3)
        score += scale_sub
    max_possible += 4

    # ---- 8. 经理团队稳定性（3分） ----
    stability = str(row.get("团队稳定性", ""))
    if "稳定" in stability and "频繁" not in stability:
        stability_sub = 3
    elif "一般" in stability:
        stability_sub = 1.5
    else:
        stability_sub = 0.5  # 未评级给基本分
    score += stability_sub
    max_possible += 3

    # 归一化
    if max_possible > 0:
        score = score / max_possible * 100
    return round(score, 2)


def pick_stable_fund(df: pd.DataFrame) -> pd.DataFrame:
    """
    从全市场筛选结果中，按 年化6% 二级债基（固收+）偏好，
    以专业基金经理视角选出唯一一只最佳基金。

    核心标准（6% 目标导向）：
    - 目标年化：精确瞄准 6%（精细分析后的年化收益 5.5%–6.5%）
    - 成立 5 年以上（经历完整牛熊周期）
    - 最大回撤 < 5%（严格控制下行风险）
    - 基金经理稳定（管理团队可靠）
    """
    print("\n" + "=" * 70)
    print("🎯  年化 6% 稳健基金精选 —— 专业基金经理视角")
    print("=" * 70)
    print(f"\n当前宏观环境: {MACRO_STATE.get('cycle_phase', 'unknown')}")
    print(f"当前偏好风格: {MACRO_STATE.get('preferred_style', 'unknown')}")
    advice = _get_cycle_advice(MACRO_STATE.get('cycle_phase', 'transition'))
    print(f"策略提示: {advice}")

    # 解析数值列
    df = df.copy()

    def parse_pct(x):
        """解析百分比字符串"""
        if isinstance(x, str):
            try:
                return float(x.strip("%")) / 100
            except (ValueError, AttributeError):
                return np.nan
        return x

    df["_mdd"] = df["最大回撤"].apply(parse_pct)
    df["_vol"] = df["年化波动"].apply(parse_pct)
    df["_ann_ret"] = df["年化收益"].apply(parse_pct)
    df["_sharpe"] = pd.to_numeric(df["夏普比率"], errors="coerce")
    df["_sortino"] = pd.to_numeric(df["Sortino"], errors="coerce")
    df["_win_rate"] = df["月度胜率"].apply(parse_pct)
    df["_dd_recovery"] = pd.to_numeric(df["最大回撤修复天"], errors="coerce")
    df["_is_bond"] = df.apply(
        lambda r: _get_asset_type(r) in ("债券", "货币"), axis=1)

    # ---- 年化 6% 二级债基硬性筛选条件 ----
    print("\n📋 年化 6% 精选筛选条件：")
    print("  ① 基金类型：债券型（排除可转债/纯债/短债/指数）")
    print("  ② 成立 ≥ 5 年")
    print("  ③ 最大回撤 < 5%（严格控制下行风险）")
    print("  ④ 年化收益 5.5%–6.5%（精确瞄准 6%）")
    print("  ⑤ 综合评分给出买入信号")

    # 债券型 + 回撤 < 5% + 收益 5.5-6.5%
    bond_mask = (
        df["_is_bond"] &
        (df["_mdd"] > -0.05) &
        (df["_ann_ret"] >= 0.055) &
        (df["_ann_ret"] <= 0.065) &
        (df["操作信号"].str.contains("买入", na=False))
    )
    stable_funds = df[bond_mask].copy()

    print(f"\n✅ 精确符合年化 6% 条件的基金: {len(stable_funds)} 只（共 {len(df)} 只）")

    if len(stable_funds) == 0:
        # 第一层放宽：去掉"买入"信号要求，只看"买入|观望"
        print("\n⚠️ 无买入信号基金，放宽信号要求...")
        relaxed_mask = (
            df["_is_bond"] &
            (df["_mdd"] > -0.05) &
            (df["_ann_ret"] >= 0.055) &
            (df["_ann_ret"] <= 0.065) &
            (df["操作信号"].str.contains("买入|观望", na=False))
        )
        stable_funds = df[relaxed_mask].copy()
        print(f"✅ 放宽信号后: {len(stable_funds)} 只")

    if len(stable_funds) == 0:
        # 第二层放宽：收益区间 5%–7%
        print("\n⚠️ 无 5.5-6.5% 区间基金，放宽收益区间至 5%–7%...")
        relaxed2_mask = (
            df["_is_bond"] &
            (df["_mdd"] > -0.05) &
            (df["_ann_ret"] >= 0.05) &
            (df["_ann_ret"] <= 0.07) &
            (df["操作信号"].str.contains("买入|观望", na=False))
        )
        stable_funds = df[relaxed2_mask].copy()
        print(f"✅ 放宽收益后: {len(stable_funds)} 只")

    if len(stable_funds) == 0:
        # 第三层放宽：回撤 < 8%，收益 4%–8%
        print("\n⚠️ 无 5% 回撤基金，进一步放宽...")
        relaxed3_mask = (
            df["_is_bond"] &
            (df["_mdd"] > -0.08) &
            (df["_ann_ret"] >= 0.04) &
            (df["_ann_ret"] <= 0.08) &
            (df["操作信号"].str.contains("买入|观望", na=False))
        )
        stable_funds = df[relaxed3_mask].copy()
        print(f"✅ 最终放宽后: {len(stable_funds)} 只")

    if len(stable_funds) == 0:
        print("\n❌ 未能找到合适的年化 6% 二级债基")
        return pd.DataFrame()

    # ---- 计算 年化6% 专项评分 ----
    print("\n📊 计算年化 6% 专项评分（精确匹配 6% 目标）...")
    stable_funds["稳定性评分"] = stable_funds.apply(calc_stability_score, axis=1)
    stable_funds = stable_funds.sort_values("稳定性评分", ascending=False).reset_index(drop=True)

    # ---- 输出排名前10 ----
    print("\n🏆 年化 6% 稳健基金 TOP 10：")
    print("-" * 90)
    display_cols = [
        "基金代码", "基金名称", "基金类型", "资产类别",
        "稳定性评分", "综合评分", "最大回撤", "年化波动", "年化收益",
        "夏普比率", "Sortino", "月度胜率", "胜率趋势",
        "最大回撤修复天", "基金规模(亿)", "团队稳定性",
        "基金经理", "资金流情绪", "操作信号"
    ]
    display_cols = [c for c in display_cols if c in stable_funds.columns]

    top10 = stable_funds.head(10)
    for _, row in top10.iterrows():
        print(f"\n  {row.get('基金代码','')} | {row.get('基金名称','')}")
        print(f"    稳定性评分: {row.get('稳定性评分',''):.1f} 分 | 综合评分: {row.get('综合评分','')}")
        print(f"    最大回撤: {row.get('最大回撤','')} | 年化波动: {row.get('年化波动','')} | 年化收益: {row.get('年化收益','')}")
        print(f"    夏普: {row.get('夏普比率','')} | Sortino: {row.get('Sortino','')} | 月度胜率: {row.get('月度胜率','')}")
        print(f"    回撤修复: {row.get('最大回撤修复天','')}天 | 规模: {row.get('基金规模(亿)','')}亿")
        print(f"    经理: {row.get('基金经理','')} | 团队: {row.get('团队稳定性','')} | 资金流: {row.get('资金流情绪','')}")

    # ---- 精选唯一一只 ----
    best = stable_funds.iloc[0]
    print("\n" + "=" * 70)
    print("🎯 🎯 🎯  年化 6% 稳健基金 唯一精选推荐 🎯 🎯 🎯")
    print("=" * 70)
    print(f"""
    📌 基金代码: {best.get('基金代码', 'N/A')}
    📌 基金名称: {best.get('基金名称', 'N/A')}
    📌 基金类型: {best.get('基金类型', 'N/A')}
    📌 资产类别: {best.get('资产类别', 'N/A')}

    ═══ 核心指标 ═══
    ⭐ 6%匹配评分: {best.get('稳定性评分', 0):.1f} / 100
    ⭐ 综合评分:    {best.get('综合评分', 0)}
    📉 最大回撤:    {best.get('最大回撤', 'N/A')}
    📊 年化波动:    {best.get('年化波动', 'N/A')}
    📈 年化收益:    {best.get('年化收益', 'N/A')}
    🎯 夏普比率:    {best.get('夏普比率', 'N/A')}
    🛡️ Sortino:     {best.get('Sortino', 'N/A')}
    ✅ 月度胜率:    {best.get('月度胜率', 'N/A')}
    📈 胜率趋势:    {best.get('胜率趋势', 'N/A')}
    ⏱️ 回撤修复:    {best.get('最大回撤修复天', 'N/A')} 天

    ═══ 附加信息 ═══
    💰 基金规模:    {best.get('基金规模(亿)', 'N/A')} 亿
    👤 基金经理:    {best.get('基金经理', 'N/A')}
    🏢 团队稳定性:  {best.get('团队稳定性', 'N/A')}
    📋 资金流:      {best.get('资金流情绪', 'N/A')}
    📊 前十大集中度: {best.get('前十大集中度', 'N/A')}
    🏷️ 操作信号:    {best.get('操作信号', 'N/A')}

    ═══ 基金经理专业推荐理由 ═══
""")

    # 生成推荐理由（专业基金经理视角）
    reasons = []
    mdd = best.get('_mdd', -1)
    vol = best.get('_vol', 1)
    ann_ret = best.get('_ann_ret', 0)
    sharpe = best.get('_sharpe', 0)
    sortino = best.get('_sortino', 0)
    win_rate = best.get('_win_rate', 0)
    dd_days = best.get('_dd_recovery', 999)
    stability = str(best.get('团队稳定性', ''))
    scale = best.get('基金规模(亿)', 0) or 0
    manager = str(best.get('基金经理', ''))
    ann_ret_str = str(best.get('年化收益', ''))
    mdd_str = str(best.get('最大回撤', ''))
    vol_str = str(best.get('年化波动', ''))
    sharpe_str = str(best.get('夏普比率', ''))
    win_rate_str = str(best.get('月度胜率', ''))
    dd_str = str(best.get('最大回撤修复天', ''))

    # 核心推荐：年化 6% 匹配度
    if not np.isnan(ann_ret):
        diff = abs(ann_ret - 0.06) * 100
        if diff <= 0.3:
            reasons.append(f"🎯 年化收益 {ann_ret_str}，与 6% 目标偏差仅 {diff:.1f} 个百分点，匹配度极高")
        elif diff <= 0.5:
            reasons.append(f"🎯 年化收益 {ann_ret_str}，与 6% 目标偏差 {diff:.1f} 个百分点，匹配度优秀")
        else:
            reasons.append(f"🎯 年化收益 {ann_ret_str}，接近 6% 目标")

    if mdd > -0.02:
        reasons.append(f"🛡️ 最大回撤仅 {mdd_str}，极端风控能力卓越，下行保护充分")
    elif mdd > -0.03:
        reasons.append(f"🛡️ 最大回撤 {mdd_str}，回撤控制在 3% 以内，风险极低")
    elif mdd > -0.05:
        reasons.append(f"🛡️ 最大回撤 {mdd_str}，控制在 5% 以内，符合稳健标准")

    if vol < 0.03:
        reasons.append(f"📊 年化波动 {vol_str}，净值曲线平滑，持有体验优秀")
    elif vol < 0.05:
        reasons.append(f"📊 年化波动 {vol_str}，低波动特征明显，适合稳健配置")

    if sharpe > 2.0:
        reasons.append(f"📈 夏普比率 {sharpe_str}，风险调整后收益在同类中名列前茅")
    elif sharpe > 1.5:
        reasons.append(f"📈 夏普比率 {sharpe_str}，风险收益比优秀")

    if not np.isnan(sortino) and sortino > 2.5:
        reasons.append(f"📈 Sortino 比率 {sortino}，下行风险控制能力突出")

    if win_rate > 0.7:
        reasons.append(f"✅ 月度胜率 {win_rate_str}，持续稳定跑赢基准，收益可靠性高")
    elif win_rate > 0.6:
        reasons.append(f"✅ 月度胜率 {win_rate_str}，多数月份跑赢基准")

    if dd_days < 60:
        reasons.append(f"⏱️ 回撤修复仅需 {dd_str} 天，下跌后快速回本")
    elif dd_days < 90:
        reasons.append(f"⏱️ 回撤修复 {dd_str} 天，回本速度良好")

    if "稳定" in stability:
        reasons.append(f"👤 基金经理团队稳定（{stability}），策略延续性好")

    if 5 <= scale <= 50:
        reasons.append(f"💰 规模 {scale:.0f} 亿，黄金规模区间，兼顾灵活性与流动性")
    elif scale > 50:
        reasons.append(f"💰 规模 {scale:.0f} 亿，流动性充裕，机构认可度高")

    if manager and manager != "nan" and manager != "":
        reasons.append(f"👤 现任基金经理：{manager}")

    if not reasons:
        reasons.append("🎯 综合 6% 匹配评分排名第一，各项指标均衡")

    for r in reasons:
        print(f"  {r}")

    print(f"""
    ═══ 配置建议 ═══
    💡 作为资产配置的核心底仓，建议占稳健资产组合的 40-60%
    💡 持有周期建议 1 年以上，充分享受固收+复利效应
    💡 目标年化 6%，在严格控制风险的前提下实现稳健增值
    💡 定期再平衡，每季度检视一次是否偏离 6% 目标区间
    """)
    print("=" * 70)

    # 保存结果
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "stable_fund_pick.csv")
    save_cols = [c for c in display_cols if c in stable_funds.columns]
    stable_funds[save_cols + ["稳定性评分"]].to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\n📁 完整二级债基排名已保存至: {output_file}")

    return stable_funds


def main():
    """
    主流程（专业基金经理视角）：
    候选筛选 → 精细分析 → 6% 精确匹配 → 精选唯一最佳基金
    """
    import sys
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    force = "--refresh" in sys.argv or "--force" in sys.argv

    print("🚀 年化 6% 稳健基金精选系统启动...")
    print("   以专业基金经理视角，瞄准年化 6% 的二级债基（固收+）")

    # 初始化宏观环境
    init_macro_state()

    # ---- 步骤 1: 找到二级债基候选池 ----
    print("\n📡 步骤 1/4: 从全市场筛选 年化6% 候选池...")
    candidates = _find_secondary_bond_candidates(max_candidates=80)

    if candidates.empty:
        print("❌ 未找到符合条件的二级债基")
        return

    print(f"\n📊 找到 {len(candidates)} 只候选基金（按 6% 偏离度排序）")
    print("候选基金列表（越接近 6% 越靠前）：")
    for _, r in candidates.head(15).iterrows():
        dev = r.get("_偏离6pct", 0)
        print(f"  {r['基金代码']} | {r['基金简称']} | 1Y:{r['近1年']:.1f}% | 2Y:{r['近2年']:.1f}% | 3Y:{r['近3年']:.1f}% | 偏离:{dev:.2f} | 规模:{r['基金规模']}亿")

    # ---- 步骤 2: 预加载基准 ----
    print("\n📡 步骤 2/4: 加载基准数据...")
    load_all_benchmarks(force_refresh=False)

    # ---- 步骤 3: 对候选基金做精细分析 ----
    print(f"\n📡 步骤 3/4: 对 {len(candidates)} 只候选基金做精细分析（8 线程并发）...")
    tasks = [
        (row["基金代码"], row.get("基金简称", ""), row.get("基金类型", ""))
        for _, row in candidates.iterrows()
    ]

    results = []
    completed = 0
    total = len(tasks)
    t_start = time.time()

    with ThreadPoolExecutor(max_workers=8) as executor:
        future_map = {
            executor.submit(analyze_fund, code, name, ftype, force): (code, name)
            for code, name, ftype in tasks
        }
        for future in as_completed(future_map):
            code, name = future_map[future]
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"  ⚠ {code} {name} 分析异常: {e}")
            completed += 1
            if completed % 5 == 0 or completed == total or completed == 1:
                elapsed = time.time() - t_start
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"  进度: {completed}/{total} | 速率: {rate:.1f}只/秒 | 预计剩余: {eta:.0f}秒")

    if not results:
        print("❌ 没有成功分析的基金")
        return

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("综合评分", ascending=False).reset_index(drop=True)

    print(f"\n✅ 成功分析 {len(df_result)} 只基金")

    # ---- 步骤 4: 6% 精确匹配过滤 & 排序 ----
    print("\n📡 步骤 4/4: 年化 6% 精确匹配 & 唯一精选...")
    stable_result = pick_stable_fund(df_result)

    if stable_result.empty:
        print("\n❌ 未找到符合年化 6% 标准的基金")
    else:
        print(f"\n✅ 完成！共 {len(stable_result)} 只基金符合年化 6% 稳健标准")


if __name__ == "__main__":
    main()
