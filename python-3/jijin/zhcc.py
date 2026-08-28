"""
基金每日收益追踪工具 v4.0（专业基金经理逻辑版）
CSV 只需提供 fund_code 和 total_cost，其余全部自动查询并分析。

评估维度：
  1. 基金经理评估（从业年限、管理规模、历史业绩）
  2. 业绩风险评估（夏普比率、最大回撤、波动率、同类排名）
  3. 持仓分析（行业集中度、重仓股）
  4. 技术面辅助（均线、MACD、RSI）
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import re
import warnings
import time
warnings.filterwarnings("ignore")

# ============================================================
# 终端颜色
# ============================================================
class Color:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    @staticmethod
    def up(text):
        return f"{Color.RED}{text}{Color.RESET}"
    @staticmethod
    def down(text):
        return f"{Color.GREEN}{text}{Color.RESET}"
    @staticmethod
    def flat(text):
        return f"{Color.YELLOW}{text}{Color.RESET}"
    @staticmethod
    def by_value(value, fmt="{:+.2f}", suffix=""):
        text = fmt.format(value) + suffix
        if value > 0:
            return Color.up(text)
        elif value < 0:
            return Color.down(text)
        else:
            return Color.flat(text)
    @staticmethod
    def by_signal(signal_text):
        if "强买" in signal_text or "买入" in signal_text:
            return Color.up(signal_text)
        elif "清仓" in signal_text or "减仓" in signal_text:
            return Color.down(signal_text)
        elif "持有" in signal_text or "观望" in signal_text:
            return Color.flat(signal_text)
        return signal_text


# ============================================================
# 配置
# ============================================================
CSV_FILE = "portfolio.csv"
REPORT_DIR = "reports"

STAGE_COLUMNS = {
    "日增长率": ("daily_return", "daily_profit"),
    "近1周":   ("week_return",  "week_profit"),
    "近1月":   ("month_return", "month_profit"),
    "近3月":   ("month3_return","month3_profit"),
    "近6月":   ("month6_return","month6_profit"),
    "近1年":   ("year_return",  "year_profit"),
    "今年来":  ("ytd_return",   "ytd_profit"),
}


# ============================================================
# 1. 读取 CSV
# ============================================================

def load_portfolio(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        print(Color.down(f"❌ 找不到文件: {csv_path}"))
        print("请创建 CSV，格式：fund_code,total_cost")
        sys.exit(1)
    df = pd.read_csv(csv_path, dtype={"fund_code": str})
    required = {"fund_code", "total_cost"}
    missing = required - set(df.columns)
    if missing:
        print(Color.down(f"❌ CSV 缺少列: {missing}"))
        sys.exit(1)
    df = df[["fund_code", "total_cost"]].copy()
    df["fund_code"] = df["fund_code"].str.strip().str.zfill(6)
    df["total_cost"] = pd.to_numeric(df["total_cost"], errors="coerce").fillna(0)
    df = df.groupby("fund_code", as_index=False)["total_cost"].sum()
    print(Color.up(f"✅ 加载 {len(df)} 只基金，总投入 ¥{df['total_cost'].sum():,.2f}\n"))
    return df


# ============================================================
# 2. 获取全市场基金日数据
# ============================================================

def fetch_all_fund_data() -> pd.DataFrame:
    print("📡 正在获取全市场基金数据...")
    try:
        df = ak.fund_open_fund_daily_em()
    except Exception as e:
        print(Color.down(f"❌ 获取基金数据失败: {e}"))
        sys.exit(1)
    col_map = {}
    # 新版 AKShare: 列名带日期前缀，如 "2026-08-06-单位净值"
    # 可能有多个日期前缀的列，只取最新一天的（且非空）
    nav_cols = []
    accum_cols = []
    for cn_name in df.columns:
        cn_stripped = cn_name.strip()
        if cn_stripped == "基金代码":
            col_map[cn_name] = "fund_code"
        elif cn_stripped in ("基金简称", "基金名称"):
            col_map[cn_name] = "fund_name"
        elif cn_stripped == "日增长率":
            col_map[cn_name] = "daily_return"
        elif cn_stripped == "日增长值":
            col_map[cn_name] = "daily_change"
        # 收集所有带日期前缀的单位净值/累计净值列
        m = re.match(r"(\d{4}-\d{2}-\d{2})-单位净值", cn_stripped)
        if m:
            nav_cols.append((m.group(1), cn_name))
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})-累计净值", cn_stripped)
        if m:
            accum_cols.append((m.group(1), cn_name))
            continue
    # 按日期排序，取最新的非空列（今天净值可能未更新，降级用昨天）
    if nav_cols:
        nav_cols.sort(reverse=True)
        # 找第一个非空的列
        chosen_nav = None
        for date_str, col_name in nav_cols:
            if df[col_name].notna().any() and (df[col_name] != "").any():
                chosen_nav = col_name
                break
        if chosen_nav is None:
            chosen_nav = nav_cols[0][1]
        col_map[chosen_nav] = "nav"
    if accum_cols:
        accum_cols.sort(reverse=True)
        chosen_accum = None
        for date_str, col_name in accum_cols:
            if df[col_name].notna().any() and (df[col_name] != "").any():
                chosen_accum = col_name
                break
        if chosen_accum is None:
            chosen_accum = accum_cols[0][1]
        col_map[chosen_accum] = "nav_accumulated"
    df = df.rename(columns=col_map)
    df["fund_code"] = df["fund_code"].astype(str).str.strip().str.zfill(6)
    num_cols = ["nav", "nav_accumulated", "daily_return", "daily_change"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # 如果日增长率缺失，用历史净值计算（当日净值 / 昨日净值 - 1）
    # 需要从原始列名找昨日净值
    if "daily_return" not in df.columns or df["daily_return"].isna().all():
        # 找次新日期的单位净值列（昨日）
        yesterday_nav_col = None
        if len(nav_cols) >= 2:
            # nav_cols 已按日期降序，取第二个
            yesterday_nav_col = nav_cols[1][1]
        elif len(nav_cols) == 1:
            # 只有一个，无法计算
            yesterday_nav_col = None
        if yesterday_nav_col and yesterday_nav_col in df.columns:
            yesterday_nav = pd.to_numeric(df[yesterday_nav_col], errors="coerce")
            today_nav = df["nav"]
            # 计算日增长率（百分比形式）
            valid = today_nav.notna() & yesterday_nav.notna() & (yesterday_nav != 0)
            df["daily_return"] = 0.0
            df.loc[valid, "daily_return"] = (
                (today_nav.loc[valid] / yesterday_nav.loc[valid] - 1) * 100
            )
    # 新版 AKShare 不再提供阶段收益列（近1周、近1月等），全部初始化为 0
    for std_name, _ in STAGE_COLUMNS.values():
        if std_name != "daily_return" and std_name not in df.columns:
            df[std_name] = 0.0
    print(f"   获取到 {len(df)} 只基金数据\n")
    return df


# ============================================================
# 3. 获取单只基金历史净值
# ============================================================

def fetch_fund_history(fund_code: str) -> pd.DataFrame:
    try:
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        df.columns = ["date", "nav", "daily_return"]
        df["date"] = pd.to_datetime(df["date"])
        df["nav"] = df["nav"].astype(float)
        return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        print(Color.flat(f"  ⚠ 获取 {fund_code} 历史净值失败: {e}"))
        return pd.DataFrame()


# ============================================================
# 4. 获取基金经理信息
# ============================================================

# 全量基金经理数据缓存（避免每次请求都拉全量）
_MANAGER_CACHE = None


def _load_all_managers() -> pd.DataFrame:
    """加载全量基金经理数据并缓存"""
    global _MANAGER_CACHE
    if _MANAGER_CACHE is None:
        try:
            _MANAGER_CACHE = ak.fund_manager_em()
            if _MANAGER_CACHE is not None and not _MANAGER_CACHE.empty:
                # 标准化基金代码列
                if "现任基金代码" in _MANAGER_CACHE.columns:
                    _MANAGER_CACHE["fund_code"] = (
                        _MANAGER_CACHE["现任基金代码"]
                        .astype(str).str.strip().str.zfill(6)
                    )
        except Exception as e:
            print(Color.flat(f"  ⚠ 加载全量基金经理数据失败: {e}"))
            _MANAGER_CACHE = pd.DataFrame()
    return _MANAGER_CACHE


def fetch_fund_manager_info(fund_code: str) -> dict:
    """
    获取基金经理信息：姓名、从业年限、管理规模、历史最佳回报
    新版 AKShare fund_manager_em() 不接受参数，需全量获取后过滤
    """
    fund_code = str(fund_code).strip().zfill(6)
    df = _load_all_managers()
    if df is None or df.empty:
        return {}
    # 按基金代码过滤
    matches = df[df["fund_code"] == fund_code]
    if matches.empty:
        return {}
    # 取第一行（现任）
    manager = matches.iloc[0]
    info = {}
    # 字段名可能有变化，做兼容
    for col in df.columns:
        col_lower = str(col).lower()
        if "姓名" in col or "name" in col_lower:
            val = manager[col]
            info["manager_name"] = str(val) if pd.notna(val) else "--"
        elif "从业" in col and "时间" in col:
            # 累计从业时间单位可能是"天"，转换为年
            val = pd.to_numeric(manager[col], errors="coerce")
            if pd.notna(val):
                # 如果值大于100，认为是天数；否则直接是年数
                info["work_years"] = val / 365 if val > 100 else val
        elif "规模" in col:
            val = pd.to_numeric(manager[col], errors="coerce")
            if pd.notna(val):
                info["aum"] = val
        elif "回报" in col or "最佳" in col:
            val = pd.to_numeric(manager[col], errors="coerce")
            if pd.notna(val):
                info["best_return"] = val
    return info


# ============================================================
# 5. 获取基金持仓
# ============================================================

def fetch_fund_portfolio(fund_code: str) -> dict:
    """
    获取基金持仓：前十大重仓股、行业分布
    """
    try:
        # 获取最新季报持仓
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date="")
        if df is None or df.empty:
            return {}
        # 取最新一期
        if "季度" in df.columns:
            df = df.sort_values("季度", ascending=False)
        latest = df.head(10)  # 前十大重仓
        holdings = []
        for _, row in latest.iterrows():
            stock_code = row.get("股票代码", "")
            stock_name = row.get("股票名称", "")
            pct = pd.to_numeric(row.get("占净值比例", 0), errors="coerce")
            holdings.append({
                "stock_code": str(stock_name),
                "stock_name": str(stock_code),
                "pct": float(pct) if pd.notna(pct) else 0
            })
        # 计算行业集中度（前十大占比）
        top10_pct = sum(h["pct"] for h in holdings)
        return {
            "holdings": holdings,
            "top10_pct": top10_pct,
            "holding_count": len(holdings)
        }
    except Exception as e:
        print(Color.flat(f"  ⚠ 获取 {fund_code} 持仓失败: {e}"))
        return {}


# ============================================================
# 6. 计算业绩风险指标
# ============================================================

def calc_performance_metrics(df: pd.DataFrame) -> dict:
    """
    计算夏普比率、最大回撤、波动率、年化收益、同类排名等
    """
    if df.empty or len(df) < 60:
        return {}
    nav = df["nav"].values
    n = len(nav)
    metrics = {}
    # ---- 日收益率序列 ----
    returns = np.diff(nav) / nav[:-1]
    returns = returns[~np.isnan(returns)]
    if len(returns) < 20:
        return {}
    # ---- 年化收益率 ----
    if n >= 250:
        total_return = nav[-1] / nav[-250] - 1
        metrics["annual_return_1y"] = total_return * 100
    elif n >= 60:
        total_return = nav[-1] / nav[-60] - 1
        metrics["annual_return_3m"] = (1 + total_return) ** (250/60) - 1
        metrics["annual_return_3m"] *= 100
    # ---- 年化波动率 ----
    annual_vol = np.std(returns) * np.sqrt(250) * 100
    metrics["volatility"] = annual_vol
    # ---- 夏普比率（无风险利率按 2% 计算） ----
    risk_free = 0.02
    if n >= 250:
        excess_return = (nav[-1] / nav[-250] - 1) - risk_free
        sharpe = excess_return / (np.std(returns) * np.sqrt(250))
        metrics["sharpe_ratio"] = sharpe
    elif n >= 60:
        excess_return = (nav[-1] / nav[-60] - 1) * (250/60) - risk_free
        sharpe = excess_return / (np.std(returns) * np.sqrt(250))
        metrics["sharpe_ratio"] = sharpe
    # ---- 最大回撤（近1年或全部） ----
    lookback = min(250, n)
    recent_nav = nav[-lookback:]
    peak = np.maximum.accumulate(recent_nav)
    drawdown = (recent_nav - peak) / peak
    metrics["max_drawdown"] = np.min(drawdown) * 100
    # ---- 卡玛比率（年化收益 / 最大回撤） ----
    if metrics["max_drawdown"] != 0 and "annual_return_1y" in metrics:
        metrics["calmar_ratio"] = metrics["annual_return_1y"] / abs(metrics["max_drawdown"])
    # ---- 胜率（日收益为正的天数占比） ----
    win_rate = np.sum(returns > 0) / len(returns) * 100
    metrics["win_rate"] = win_rate
    # ---- 盈亏比（平均盈利 / 平均亏损） ----
    gains = returns[returns > 0]
    losses = returns[returns < 0]
    if len(gains) > 0 and len(losses) > 0:
        metrics["profit_loss_ratio"] = np.mean(gains) / abs(np.mean(losses))
    return metrics


# ============================================================
# 7. 技术面指标计算
# ============================================================

def calc_technical_indicators(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 60:
        return {}
    nav = df["nav"].values
    n = len(nav)
    indicators = {}
    # 均线
    for period in [5, 20, 60]:
        if n >= period:
            indicators[f"MA{period}"] = np.mean(nav[-period:])
    if all(f"MA{p}" in indicators for p in [5, 20, 60]):
        if indicators["MA5"] > indicators["MA20"] > indicators["MA60"]:
            indicators["ma_trend"] = "多头排列"
        elif indicators["MA5"] < indicators["MA20"] < indicators["MA60"]:
            indicators["ma_trend"] = "空头排列"
        else:
            indicators["ma_trend"] = "震荡整理"
    # MACD
    if n >= 35:
        ema12 = pd.Series(nav).ewm(span=12, adjust=False).mean().values
        ema26 = pd.Series(nav).ewm(span=26, adjust=False).mean().values
        dif = ema12 - ema26
        dea = pd.Series(dif).ewm(span=9, adjust=False).mean().values
        macd_bar = (dif - dea) * 2
        indicators["DIF"] = dif[-1]
        indicators["DEA"] = dea[-1]
        indicators["MACD"] = macd_bar[-1]
        recent_dif = dif[-5:]
        recent_dea = dea[-5:]
        if recent_dif[-1] > recent_dea[-1] and recent_dif[-2] <= recent_dea[-2]:
            indicators["macd_signal"] = "金叉"
        elif recent_dif[-1] < recent_dea[-1] and recent_dif[-2] >= recent_dea[-2]:
            indicators["macd_signal"] = "死叉"
        elif dif[-1] > dea[-1]:
            indicators["macd_signal"] = "DIF在DEA上方"
        else:
            indicators["macd_signal"] = "DIF在DEA下方"
    # RSI
    if n >= 20:
        deltas = np.diff(nav[-20:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        if avg_loss == 0:
            indicators["RSI14"] = 100.0
        else:
            rs = avg_gain / avg_loss
            indicators["RSI14"] = 100 - (100 / (1 + rs))
        if indicators["RSI14"] > 70:
            indicators["rsi_signal"] = "超买"
        elif indicators["RSI14"] < 30:
            indicators["rsi_signal"] = "超卖"
        else:
            indicators["rsi_signal"] = "正常"
    # 近20日涨幅
    if n >= 20:
        indicators["return_20d"] = (nav[-1] / nav[-20] - 1) * 100
    return indicators


# ============================================================
# 8. 综合评分系统（专业基金经理逻辑）
# ============================================================

def generate_professional_advice(
    manager_info: dict,
    performance: dict,
    portfolio: dict,
    technical: dict
) -> dict:
    """
    综合多维度评估，给出专业级买卖建议
    评分范围: -20 ~ +20
    """
    score = 0
    reasons = []
    dimension_scores = {}
    # ========== 维度1: 基金经理评估（满分 6 分） ==========
    mgr_score = 0
    # 从业年限（0~2分）
    work_years = manager_info.get("work_years", 0)
    if work_years >= 7:
        mgr_score += 2
        reasons.append(Color.up(f"👨‍💼 基金经理从业 {work_years:.1f} 年，经验丰富 (+2)"))
    elif work_years >= 5:
        mgr_score += 1
        reasons.append(Color.up(f"👨‍💼 基金经理从业 {work_years:.1f} 年 (+1)"))
    elif work_years >= 3:
        reasons.append(Color.flat(f"👨‍💼 基金经理从业 {work_years:.1f} 年 (0)"))
    elif work_years > 0:
        mgr_score -= 1
        reasons.append(Color.down(f"👨‍💼 基金经理从业 {work_years:.1f} 年，经验不足 (-1)"))
    # 管理规模（0~2分）
    aum = manager_info.get("aum", 0)
    if 20 <= aum <= 100:
        mgr_score += 2
        reasons.append(Color.up(f"💰 管理规模 {aum:.1f} 亿，规模适中 (+2)"))
    elif 10 <= aum < 20 or 100 < aum <= 300:
        mgr_score += 1
        reasons.append(Color.up(f"💰 管理规模 {aum:.1f} 亿 (+1)"))
    elif aum > 300:
        mgr_score -= 1
        reasons.append(Color.down(f"💰 管理规模 {aum:.1f} 亿，规模过大收益衰减 (-1)"))
    elif aum > 0:
        reasons.append(Color.flat(f"💰 管理规模 {aum:.1f} 亿 (0)"))
    # 历史最佳回报（0~2分）
    best_ret = manager_info.get("best_return", 0)
    if best_ret >= 100:
        mgr_score += 2
        reasons.append(Color.up(f"🏆 历史最佳回报 {best_ret:.1f}%，业绩优秀 (+2)"))
    elif best_ret >= 50:
        mgr_score += 1
        reasons.append(Color.up(f"🏆 历史最佳回报 {best_ret:.1f}% (+1)"))
    elif best_ret > 0:
        reasons.append(Color.flat(f"🏆 历史最佳回报 {best_ret:.1f}% (0)"))
    elif best_ret < 0:
        mgr_score -= 1
        reasons.append(Color.down(f"🏆 历史最佳回报 {best_ret:.1f}%，业绩较差 (-1)"))
    dimension_scores["基金经理"] = mgr_score
    # ========== 维度2: 业绩风险评估（满分 8 分） ==========
    perf_score = 0
    # 夏普比率（-2~+2）
    sharpe = performance.get("sharpe_ratio", 0)
    if sharpe >= 1.5:
        perf_score += 2
        reasons.append(Color.up(f"📊 夏普比率 {sharpe:.2f}，风险收益比优秀 (+2)"))
    elif sharpe >= 1.0:
        perf_score += 1
        reasons.append(Color.up(f"📊 夏普比率 {sharpe:.2f} (+1)"))
    elif sharpe >= 0.5:
        reasons.append(Color.flat(f"📊 夏普比率 {sharpe:.2f} (0)"))
    elif sharpe >= 0:
        perf_score -= 1
        reasons.append(Color.down(f"📊 夏普比率 {sharpe:.2f}，风险收益较差 (-1)"))
    else:
        perf_score -= 2
        reasons.append(Color.down(f"📊 夏普比率 {sharpe:.2f}，亏损且波动大 (-2)"))
    # 最大回撤（-2~+2）
    max_dd = performance.get("max_drawdown", 0)
    if max_dd > -10:
        perf_score += 2
        reasons.append(Color.up(f"📉 最大回撤 {max_dd:.1f}%，风控优秀 (+2)"))
    elif max_dd > -20:
        perf_score += 1
        reasons.append(Color.up(f"📉 最大回撤 {max_dd:.1f}% (+1)"))
    elif max_dd > -30:
        reasons.append(Color.flat(f"📉 最大回撤 {max_dd:.1f}% (0)"))
    else:
        perf_score -= 2
        reasons.append(Color.down(f"📉 最大回撤 {max_dd:.1f}%，风险极高 (-2)"))
    # 波动率（-2~+2）
    vol = performance.get("volatility", 0)
    if vol < 15:
        perf_score += 2
        reasons.append(Color.up(f"📈 年化波动率 {vol:.1f}%，走势稳健 (+2)"))
    elif vol < 25:
        perf_score += 1
        reasons.append(Color.up(f"📈 年化波动率 {vol:.1f}% (+1)"))
    elif vol < 35:
        reasons.append(Color.flat(f"📈 年化波动率 {vol:.1f}% (0)"))
    else:
        perf_score -= 1
        reasons.append(Color.down(f"📈 年化波动率 {vol:.1f}%，波动过大 (-1)"))
    # 卡玛比率（-2~+2）
    calmar = performance.get("calmar_ratio", 0)
    if calmar >= 1.0:
        perf_score += 2
        reasons.append(Color.up(f"📊 卡玛比率 {calmar:.2f}，收益回撤比优秀 (+2)"))
    elif calmar >= 0.5:
        perf_score += 1
        reasons.append(Color.up(f"📊 卡玛比率 {calmar:.2f} (+1)"))
    elif calmar >= 0:
        reasons.append(Color.flat(f"📊 卡玛比率 {calmar:.2f} (0)"))
    else:
        perf_score -= 1
        reasons.append(Color.down(f"📊 卡玛比率 {calmar:.2f} (-1)"))
    dimension_scores["业绩风险"] = perf_score
    # ========== 维度3: 持仓分析（满分 4 分） ==========
    hold_score = 0
    top10_pct = portfolio.get("top10_pct", 0)
    if top10_pct > 0:
        # 集中度适中（40-60%）最佳
        if 40 <= top10_pct <= 60:
            hold_score += 2
            reasons.append(Color.up(f"🏢 前十大持仓占比 {top10_pct:.1f}%，集中度适中 (+2)"))
        elif 30 <= top10_pct < 40 or 60 < top10_pct <= 70:
            hold_score += 1
            reasons.append(Color.up(f"🏢 前十大持仓占比 {top10_pct:.1f}% (+1)"))
        elif top10_pct > 70:
            hold_score -= 1
            reasons.append(Color.down(f"🏢 前十大持仓占比 {top10_pct:.1f}%，过于集中 (-1)"))
        elif top10_pct < 30:
            reasons.append(Color.flat(f"🏢 前十大持仓占比 {top10_pct:.1f}%，过于分散 (0)"))
    dimension_scores["持仓分析"] = hold_score
    # ========== 维度4: 技术面辅助（满分 2 分） ==========
    tech_score = 0
    ma_trend = technical.get("ma_trend", "")
    if ma_trend == "多头排列":
        tech_score += 1
        reasons.append(Color.up("📈 均线多头排列，短期偏强 (+1)"))
    elif ma_trend == "空头排列":
        tech_score -= 1
        reasons.append(Color.down("📉 均线空头排列，短期偏弱 (-1)"))
    rsi = technical.get("RSI14", 50)
    if rsi < 30:
        tech_score += 1
        reasons.append(Color.up(f"📊 RSI={rsi:.1f} 超卖，可能反弹 (+1)"))
    elif rsi > 70:
        tech_score -= 1
        reasons.append(Color.down(f"📊 RSI={rsi:.1f} 超买，可能回调 (-1)"))
    dimension_scores["技术面"] = tech_score
    # ========== 综合评分 ==========
    score = mgr_score + perf_score + hold_score + tech_score
    # 映射为建议
    if score >= 12:
        advice = "🔴 强烈买入"
    elif score >= 8:
        advice = "🔴 建议买入"
    elif score >= 4:
        advice = "🔴 轻仓买入"
    elif score >= -3:
        advice = "🟡 继续持有"
    elif score >= -8:
        advice = "🟢 轻仓减仓"
    elif score >= -12:
        advice = "🟢 建议减仓"
    else:
        advice = "🟢 建议清仓"
    return {
        "score": score,
        "advice": advice,
        "reasons": reasons,
        "dimension_scores": dimension_scores,
        "manager_info": manager_info,
        "performance": performance,
        "portfolio": portfolio,
        "technical": technical,
    }


# ============================================================
# 9. 合并持仓与市场数据
# ============================================================

def merge_portfolio(portfolio: pd.DataFrame, market_data: pd.DataFrame) -> pd.DataFrame:
    merged = portfolio.merge(market_data, on="fund_code", how="left")
    not_found = merged[merged["fund_name"].isna()]
    if not not_found.empty:
        codes = not_found["fund_code"].tolist()
        print(Color.flat(f"⚠ 以下基金代码未找到: {codes}\n"))
    merged = merged.dropna(subset=["fund_name"]).copy()
    cost = merged["total_cost"]
    for cn_name, (std_name, profit_name) in STAGE_COLUMNS.items():
        if std_name in merged.columns:
            # daily_return 已经是百分比形式（如 1.5 表示 1.5%）
            # 但新版 AKShare 的日增长率是小数形式（如 0.015 表示 1.5%）
            # 需要判断：如果值 < 1，说明是小数形式，转百分比
            if std_name == "daily_return":
                vals = merged[std_name]
                # 如果最大值 < 10，说明是小数形式（如 0.015），转百分比
                if vals.max() < 10 and vals.max() > 0:
                    merged[std_name] = vals * 100
                merged[profit_name] = cost * merged[std_name] / 100
            else:
                merged[profit_name] = cost * merged[std_name] / 100
    return merged


# ============================================================
# 10. 彩色终端输出
# ============================================================

def safe_get(row, col, default=0):
    if col not in row.index:
        return default
    v = row[col]
    if pd.isna(v):
        return default
    return float(v)


def print_color_report(df: pd.DataFrame, advice_map: dict):
    display_stages = [
        ("daily_return", "daily_profit", "日涨跌", "日收益"),
        ("week_return",  "week_profit",  "近1周",  None),
        ("month_return", "month_profit", "近1月",  None),
        ("month3_return","month3_profit","近3月",  None),
        ("ytd_return",   "ytd_profit",   "今年来", None),
    ]
    display_stages = [s for s in display_stages if s[0] in df.columns]
    sep = "=" * 110
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{Color.BOLD}{sep}{Color.RESET}")
    print(f"{Color.BOLD}{'📈 基金收益日报 & 专业评估报告':^102}{Color.RESET}")
    print(f"{'报告日期: ' + now:^106}")
    print(f"{Color.BOLD}{sep}{Color.RESET}")
    # ---- 持仓明细 ----
    print(f"\n{Color.BOLD}【持仓明细】{Color.RESET}")
    print(f"{Color.DIM}{'─'*110}{Color.RESET}")
    header_parts = [f"{'代码':<8}", f"{'名称':<14}", f"{'净值':>8}"]
    for stage in display_stages:
        header_parts.append(f"{stage[2]:>10}")
        if stage[3]:
            header_parts.append(f"{stage[3]:>12}")
    header_parts.append(f"{'评分':>6}")
    header_parts.append(f"{'建议':>14}")
    print(f"{Color.CYAN}{''.join(header_parts)}{Color.RESET}")
    print(f"{Color.DIM}{'─'*110}{Color.RESET}")
    for _, row in df.iterrows():
        code = str(row["fund_code"])
        name = str(row["fund_name"])[:12]
        nav = safe_get(row, "nav", 0)
        nav_str = f"{nav:.4f}" if nav > 0 else "--"
        line_parts = [f"{code:<8}", f"{name:<14}", f"{nav_str:>8}"]
        for std_name, profit_name, label, profit_label in display_stages:
            ret_val = safe_get(row, std_name)
            ret_str = Color.by_value(ret_val, "{:+.2f}", "%")
            line_parts.append(f"{ret_str:>20}")
            if profit_label:
                profit_val = safe_get(row, profit_name)
                profit_str = Color.by_value(profit_val, "¥{:+,.2f}")
                line_parts.append(f"{profit_str:>22}")
        adv = advice_map.get(code, {})
        score = adv.get("score", 0)
        advice = adv.get("advice", "数据不足")
        score_str = Color.by_value(score, "{:+d}")
        advice_colored = Color.by_signal(advice)
        line_parts.append(f"{score_str:>16}")
        line_parts.append(f"{advice_colored:>24}")
        print("".join(line_parts))
    print(f"{Color.DIM}{'─'*110}{Color.RESET}")
    # ---- 资产汇总 ----
    total_cost = df["total_cost"].sum()
    print(f"\n{Color.BOLD}{sep}{Color.RESET}")
    print(f"{Color.BOLD}【资产汇总】{Color.RESET}")
    print(f"  💰 总投入成本:   ¥{total_cost:>14,.2f}")
    summary_labels = [
        ("daily_profit", "今日收益"),
        ("week_profit",  "近1周收益"),
        ("month_profit", "近1月收益"),
        ("month3_profit","近3月收益"),
        ("ytd_profit",   "今年来收益"),
    ]
    for profit_col, label in summary_labels:
        if profit_col in df.columns:
            val = df[profit_col].sum()
            print(f"  📈 {label}:   " + Color.by_value(val, "¥{:+14,.2f}"))
    # ---- 专业评估详情 ----
    print(f"\n{Color.BOLD}{sep}{Color.RESET}")
    print(f"{Color.BOLD}【专业评估详情】{Color.RESET}")
    print(f"{Color.DIM}{'─'*110}{Color.RESET}")
    for _, row in df.iterrows():
        code = str(row["fund_code"])
        name = str(row["fund_name"])[:14]
        adv = advice_map.get(code, {})
        if not adv or adv.get("advice") == "数据不足":
            print(f"\n  {code} {name}: {Color.flat('数据不足，无法分析')}")
            continue
        score = adv["score"]
        advice = adv["advice"]
        reasons = adv.get("reasons", [])
        dim_scores = adv.get("dimension_scores", {})
        manager_info = adv.get("manager_info", {})
        performance = adv.get("performance", {})
        technical = adv.get("technical", {})
        print(f"\n  {Color.BOLD}{code} {name}{Color.RESET}")
        print(f"  综合评分: {Color.by_value(score, '{:+d}')}  →  建议: {Color.by_signal(advice)}")
        # 维度得分
        dim_str = " | ".join([f"{k}: {v:+d}" for k, v in dim_scores.items()])
        print(f"  {Color.DIM}维度得分: {dim_str}{Color.RESET}")
        # 关键指标
        mgr_name = manager_info.get("manager_name", "--")
        work_years = manager_info.get("work_years", 0)
        sharpe = performance.get("sharpe_ratio", 0)
        max_dd = performance.get("max_drawdown", 0)
        vol = performance.get("volatility", 0)
        ma_trend = technical.get("ma_trend", "--")
        rsi = technical.get("RSI14", 0)
        print(f"  {Color.DIM}基金经理: {mgr_name}({work_years:.1f}年) | "
              f"夏普: {sharpe:.2f} | 回撤: {max_dd:.1f}% | "
              f"波动: {vol:.1f}% | 均线: {ma_trend} | RSI: {rsi:.1f}{Color.RESET}")
        # 分析理由
        for r in reasons:
            print(f"    • {r}")
    print(f"\n{Color.BOLD}{sep}{Color.RESET}")
    # ---- 风险提示 ----
    print(f"\n{Color.YELLOW}⚠️ 免责声明：以上评估基于公开数据的量化分析，不构成投资建议。")
    print(f"   基金投资有风险，请结合市场环境、个人风险承受能力和投资目标综合判断。{Color.RESET}\n")


# ============================================================
# 11. 导出
# ============================================================

def export_report(df: pd.DataFrame, advice_map: dict):
    os.makedirs(REPORT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    txt_path = os.path.join(REPORT_DIR, f"fund_report_{today}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"基金收益日报 & 专业评估报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 80 + "\n\n")
        keep_cols = ["fund_code", "fund_name", "nav", "total_cost"]
        for cn_name, (std_name, profit_name) in STAGE_COLUMNS.items():
            if std_name in df.columns:
                keep_cols.extend([std_name, profit_name])
        available = [c for c in keep_cols if c in df.columns]
        f.write(df[available].to_string(index=False))
        f.write("\n\n")
        f.write("=" * 80 + "\n")
        f.write("专业评估详情\n")
        f.write("=" * 80 + "\n\n")
        for _, row in df.iterrows():
            code = str(row["fund_code"])
            name = str(row["fund_name"])
            adv = advice_map.get(code, {})
            if adv and adv.get("advice") != "数据不足":
                f.write(f"{code} {name}\n")
                f.write(f"  综合评分: {adv['score']:+d}  →  建议: {adv['advice']}\n")
                dim_scores = adv.get("dimension_scores", {})
                f.write(f"  维度得分: {' | '.join([f'{k}: {v:+d}' for k, v in dim_scores.items()])}\n")
                manager_info = adv.get("manager_info", {})
                f.write(f"  基金经理: {manager_info.get('manager_name', '--')}\n")
                performance = adv.get("performance", {})
                f.write(f"  夏普比率: {performance.get('sharpe_ratio', 0):.2f}\n")
                f.write(f"  最大回撤: {performance.get('max_drawdown', 0):.1f}%\n")
                f.write(f"  波动率: {performance.get('volatility', 0):.1f}%\n\n")
        f.write("\n⚠️ 免责声明：以上评估仅基于公开数据的量化分析，不构成投资建议。\n")
    print(f"✅ 报表已保存: {txt_path}")
    csv_path = os.path.join(REPORT_DIR, f"fund_data_{today}.csv")
    export_df = df.copy()
    export_df["综合评分"] = export_df["fund_code"].map(
        lambda x: advice_map.get(x, {}).get("score", "")
    )
    export_df["买卖建议"] = export_df["fund_code"].map(
        lambda x: advice_map.get(x, {}).get("advice", "")
    )
    export_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"✅ 数据已导出: {csv_path}")


# ============================================================
# 12. 主程序
# ============================================================

def main():
    os.system("")  # Windows ANSI 支持
    print(f"{Color.BOLD}{'='*60}")
    print(f"   基金收益追踪工具 v4.0（专业基金经理逻辑版）")
    print(f"{'='*60}{Color.RESET}\n")
    # 1. 加载持仓
    portfolio = load_portfolio(CSV_FILE)
    # 2. 获取全市场数据
    market_data = fetch_all_fund_data()
    # 3. 合并
    df = merge_portfolio(portfolio, market_data)
    if df.empty:
        print(Color.down("❌ 没有有效的基金数据"))
        sys.exit(1)
    # 4. 逐只基金多维度分析
    print("\n📊 正在进行专业评估（多维度分析）...\n")
    advice_map = {}
    for i, (_, row) in enumerate(df.iterrows(), 1):
        code = str(row["fund_code"])
        name = str(row["fund_name"])[:10]
        print(f"  [{i}/{len(df)}] 分析 {code} {name}...")
        # 获取历史净值
        print(f"    → 获取历史净值... ", end="")
        hist = fetch_fund_history(code)
        print("✓")
        # 用历史净值中的最新日增长率更新全市场数据（解决今日净值未更新的问题）
        if not hist.empty and "daily_return" in hist.columns:
            latest_daily_ret = hist.iloc[-1]["daily_return"]
            if pd.notna(latest_daily_ret) and latest_daily_ret != 0:
                mask = df["fund_code"] == code
                df.loc[mask, "daily_return"] = float(latest_daily_ret)
                # 重新计算日收益
                df.loc[mask, "daily_profit"] = df.loc[mask, "total_cost"] * float(latest_daily_ret) / 100
        # 获取基金经理信息
        print(f"    → 获取基金经理信息...", end=" ")
        manager_info = fetch_fund_manager_info(code)
        print("✓" if manager_info else "⚠")
        # 获取持仓
        print(f"    → 获取持仓信息...", end=" ")
        portfolio_info = fetch_fund_portfolio(code)
        print("✓" if portfolio_info else "⚠")
        # 计算指标
        print(f"    → 计算业绩风险指标...", end=" ")
        performance = calc_performance_metrics(hist)
        print("✓" if performance else "⚠")
        print(f"    → 计算技术指标...", end=" ")
        technical = calc_technical_indicators(hist)
        print("✓" if technical else "⚠")
        # 综合评估
        print(f"    → 生成综合评估...", end=" ")
        advice = generate_professional_advice(manager_info, performance, portfolio_info, technical)
        advice_map[code] = advice
        print(f"→ 评分: {Color.by_value(advice['score'], '{:+d}')}  "
              f"建议: {Color.by_signal(advice['advice'])}")
        # 避免请求过快
        time.sleep(0.5)
    # 5. 输出报表
    print_color_report(df, advice_map)
    # 6. 导出
    export_report(df, advice_map)


if __name__ == "__main__":
    main()

