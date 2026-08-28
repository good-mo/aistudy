"""
基金每日收益追踪工具（极简 CSV 版 v2.1 - 修复 KeyError）
CSV 只需提供 fund_code 和 total_cost，其余全部自动查询。
"""

import akshare as ak
import pandas as pd
from datetime import datetime
import os
import sys

# ============================================================
# 终端颜色
# ============================================================
class Color:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
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


# ============================================================
# 配置
# ============================================================
CSV_FILE = "portfolio.csv"
REPORT_DIR = "fund_records"

# 阶段收益率列的映射：中文名 → (标准名, 利润列名)
# 如果 API 返回的列名有变化，只需修改这里
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
# 1. 读取极简 CSV
# ============================================================

def load_portfolio(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        print(Color.down(f"❌ 找不到文件: {csv_path}"))
        print("请创建 CSV，格式：")
        print("fund_code,total_cost")
        print("110011,10000.00")
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
# 2. 获取全市场基金数据（带列名自动探测）
# ============================================================

def fetch_all_fund_data() -> pd.DataFrame:
    print("📡 正在获取全市场基金数据...")
    try:
        df = ak.fund_open_fund_daily_em()
    except Exception as e:
        print(Color.down(f"❌ 获取基金数据失败: {e}"))
        sys.exit(1)
    print(f"   API 返回列名: {list(df.columns)}")
    # ---- 动态列名映射: 找出带日期的净值列 ----
    date_nav_cols = {}  # date_str -> column_name
    col_map = {}
    for cn_name in df.columns:
        cn_stripped = cn_name.strip()
        # 匹配 "YYYY-MM-DD-单位净值" 格式的列
        import re
        m = re.match(r"(\d{4}-\d{2}-\d{2})-单位净值", cn_stripped)
        if m:
            date_nav_cols[m.group(1)] = cn_name
            continue
        # 匹配 "YYYY-MM-DD-累计净值"
        m2 = re.match(r"(\d{4}-\d{2}-\d{2})-累计净值", cn_stripped)
        if m2:
            continue  # 累计净值不参与计算, 跳过
        # 普通列名映射
        if cn_stripped == "基金代码" or cn_stripped.endswith("基金代码"):
            col_map[cn_name] = "fund_code"
        elif cn_stripped in ("基金简称", "基金名称") or cn_stripped.endswith("基金简称") or cn_stripped.endswith("基金名称"):
            col_map[cn_name] = "fund_name"
        elif cn_stripped == "日期" or cn_stripped.endswith("日期"):
            col_map[cn_name] = "date"
        elif cn_stripped == "日增长值":
            col_map[cn_name] = "daily_value_raw"
        elif cn_stripped == "日增长率":
            col_map[cn_name] = "daily_return_raw"
        elif cn_stripped in STAGE_COLUMNS:
            std_name = STAGE_COLUMNS[cn_stripped][0]
            col_map[cn_name] = std_name
    df = df.rename(columns=col_map)
    # ---- 从日期净值列中取最新确认净值作为 nav ----
    if date_nav_cols:
        sorted_dates = sorted(date_nav_cols.keys(), reverse=True)
        # 取第一个有数据的日期(从最新往前找)
        latest_date = None
        for d in sorted_dates:
            non_empty = df[date_nav_cols[d]].dropna()
            non_empty = non_empty[non_empty.astype(str).str.strip() != ""]
            if len(non_empty) > 0:
                latest_date = d
                break
        if latest_date:
            # 找前一个日期计算日涨幅
            prev_date = None
            for d in sorted_dates:
                if d < latest_date:
                    prev_date = d
                    break
            nav_col = date_nav_cols[latest_date]
            df["nav"] = pd.to_numeric(df[nav_col], errors="coerce")
            df["nav_date"] = latest_date
            if prev_date:
                prev_col = date_nav_cols[prev_date]
                prev_nav = pd.to_numeric(df[prev_col], errors="coerce")
                # 计算日增长率 = (最新净值 - 前一净值) / 前一净值 * 100
                df["daily_return"] = (df["nav"] - prev_nav) / prev_nav * 100
                df["daily_value"] = df["nav"] - prev_nav
                df["prev_nav"] = prev_nav  # 保留前一净值，供收益精确计算
                print(f"   净值日期: {latest_date} (从 {prev_date} 计算日涨幅)")
            else:
                df["daily_return"] = 0.0
                df["daily_value"] = 0.0
                print(f"   净值日期: {latest_date} (仅1天数据, 无法计算日涨幅)")
        else:
            df["nav"] = 0.0
            df["daily_return"] = 0.0
            df["daily_value"] = 0.0
    else:
        # fallback: 用原始列名匹配
        if "单位净值" in df.columns:
            df["nav"] = pd.to_numeric(df["单位净值"], errors="coerce")
        if "日增长率" in df.columns:
            df["daily_return"] = pd.to_numeric(df["日增长率"], errors="coerce").fillna(0)
    df["fund_code"] = df["fund_code"].astype(str).str.strip().str.zfill(6)
    # 转换阶段数值列
    for v in STAGE_COLUMNS.values():
        std_name = v[0]
        if std_name in df.columns:
            df[std_name] = pd.to_numeric(df[std_name], errors="coerce")
    print(f"   获取到 {len(df)} 只基金数据\n")
    return df


# ============================================================
# 3. 合并持仓与市场数据
# ============================================================

def merge_portfolio(portfolio: pd.DataFrame, market_data: pd.DataFrame) -> pd.DataFrame:
    merged = portfolio.merge(market_data, on="fund_code", how="left")
    not_found = merged[merged["fund_name"].isna()]
    if not not_found.empty:
        codes = not_found["fund_code"].tolist()
        print(Color.flat(f"⚠ 以下基金代码未找到: {codes}"))
        print(Color.flat("  请检查代码是否正确\n"))
    merged = merged.dropna(subset=["fund_name"]).copy()
    # 动态计算各阶段收益金额（只计算存在的列）
    cost = merged["total_cost"]
    available_stages = []
    for cn_name, (std_name, profit_name) in STAGE_COLUMNS.items():
        if std_name in merged.columns:
            merged[profit_name] = cost * merged[std_name] / 100
            available_stages.append((std_name, profit_name))
    # 日收益：优先用精确公式 cost × (nav - prev_nav) / prev_nav
    # （daily_value 列即 nav - prev_nav，注意分母应为前一交易日净值 prev_nav，而非最新 nav）
    if "daily_value" in merged.columns and "prev_nav" in merged.columns:
        prev_nav = merged["prev_nav"].replace(0, pd.NA)
        merged["daily_profit"] = cost * merged["daily_value"] / prev_nav
    elif "daily_value" in merged.columns:
        # 兜底：无 prev_nav 列时，直接用增长率推导
        merged["daily_profit"] = cost * merged["daily_return"] / 100
    # 防御：个别基金无前一日数据时避免 NaN 污染汇总
    if "daily_profit" in merged.columns:
        merged["daily_profit"] = merged["daily_profit"].fillna(0)
    # 把可用阶段信息存到 DataFrame 的 attrs 中，供后续使用
    merged.attrs["available_stages"] = available_stages
    if "nav_date" in market_data.columns:
        merged.attrs["nav_date"] = market_data["nav_date"].iloc[0] if len(market_data) > 0 else ""
    return merged


# ============================================================
# 4. 彩色终端输出
# ============================================================

def safe_get(row, col, default=0):
    """安全获取列值，列不存在或为 NaN 时返回 default"""
    if col not in row.index:
        return default
    v = row[col]
    if pd.isna(v):
        return default
    return float(v)


def print_color_report(df: pd.DataFrame):
    available_stages = df.attrs.get("available_stages", [])
    # 用于显示的阶段列：(标准名, 利润名, 显示标签)
    display_stages = [
        ("daily_return", "daily_profit", "日涨跌", "日收益"),
        ("week_return",  "week_profit",  "近1周",  None),
        ("month_return", "month_profit", "近1月",  None),
        ("month3_return","month3_profit","近3月",  None),
        ("ytd_return",   "ytd_profit",   "今年来", None),
    ]
    # 只保留实际存在的阶段
    display_stages = [s for s in display_stages if s[0] in df.columns]
    sep = "=" * 90
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    nav_date_str = df.attrs.get("nav_date", "")
    print(f"\n{Color.BOLD}{sep}{Color.RESET}")
    print(f"{Color.BOLD}{'📈 基金收益日报':^82}{Color.RESET}")
    print(f"{'报告日期: ' + now:^86}")
    if nav_date_str:
        print(f"{'最新确认净值: ' + nav_date_str:^86}")
        sub = "交易日白天显示昨日确认净值, 日涨跌需今晚收盘后更新"
        print(f"{'(' + sub + ')':^86}{Color.DIM}{Color.RESET}")
    print(f"{Color.BOLD}{sep}{Color.RESET}")
    # ---- 持仓明细 ----
    print(f"\n{Color.BOLD}【持仓明细】{Color.RESET}")
    print(f"{Color.DIM}{'─'*90}{Color.RESET}")
    # 动态表头（净值列带上实际净值日期，如 净值(08-07)）
    nav_label = f"净值({nav_date_str[5:]})" if nav_date_str else "净值"
    header_parts = [f"{'代码':<8}", f"{'名称':<16}", f"{nav_label:>8}"]
    for stage in display_stages:
        header_parts.append(f"{stage[2]:>10}")
        if stage[3]:  # 日收益单独显示
            header_parts.append(f"{stage[3]:>12}")
    print(f"{Color.CYAN}{''.join(header_parts)}{Color.RESET}")
    print(f"{Color.DIM}{'─'*90}{Color.RESET}")
    for _, row in df.iterrows():
        code = str(row["fund_code"])
        name = str(row["fund_name"])[:14]
        nav = safe_get(row, "nav", 0)
        nav_str = f"{nav:.4f}" if nav > 0 else "--"
        line_parts = [f"{code:<8}", f"{name:<16}", f"{nav_str:>8}"]
        for std_name, profit_name, label, profit_label in display_stages:
            ret_val = safe_get(row, std_name)
            ret_str = Color.by_value(ret_val, "{:+.2f}", "%")
            line_parts.append(f"{ret_str:>20}")
            if profit_label:
                profit_val = safe_get(row, profit_name)
                profit_str = Color.by_value(profit_val, "¥{:+,.2f}")
                line_parts.append(f"{profit_str:>22}")
        print("".join(line_parts))
    print(f"{Color.DIM}{'─'*90}{Color.RESET}")
    # ---- 资产汇总 ----
    total_cost = df["total_cost"].sum()
    print(f"\n{Color.BOLD}{sep}{Color.RESET}")
    print(f"{Color.BOLD}【资产汇总】{Color.RESET}")
    print(f"  💰 总投入成本:   ¥{total_cost:>14,.2f}")
    # 动态汇总（只汇总存在的利润列）
    summary_labels = [
        ("daily_profit", "今日收益"),
        ("week_profit",  "近1周收益"),
        ("month_profit", "近1月收益"),
        ("month3_profit","近3月收益"),
        ("month6_profit","近6月收益"),
        ("year_profit",  "近1年收益"),
        ("ytd_profit",   "今年来收益"),
    ]
    for profit_col, label in summary_labels:
        if profit_col in df.columns:
            val = df[profit_col].sum()
            print(f"  📈 {label}:   " + Color.by_value(val, "¥{:+14,.2f}"))
    print(f"{Color.BOLD}{sep}{Color.RESET}\n")


# ============================================================
# 5. 导出（纯文本，无颜色码）
# ============================================================

def export_report(df: pd.DataFrame):
    os.makedirs(REPORT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    # 文本报表
    txt_path = os.path.join(REPORT_DIR, f"fund_report_{today}.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"基金收益日报 - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 80 + "\n\n")
        # 只写出存在的列（净值列带上实际净值日期，如 nav(2026-08-07)）
        nav_date_str = df.attrs.get("nav_date", "")
        nav_label = f"nav({nav_date_str})" if nav_date_str else "nav"
        keep_cols = ["fund_code", "fund_name", nav_label]
        for cn_name, (std_name, profit_name) in STAGE_COLUMNS.items():
            if std_name in df.columns:
                keep_cols.extend([std_name, profit_name])
        disp = df.rename(columns={"nav": nav_label})
        available = [c for c in keep_cols if c in disp.columns]
        f.write(disp[available].to_string(index=False))
        f.write("\n\n")
        total_cost = df["total_cost"].sum()
        f.write(f"总投入成本: ¥{total_cost:,.2f}\n")
        for profit_col, label in [
            ("daily_profit", "今日收益"),
            ("week_profit",  "近1周收益"),
            ("month_profit", "近1月收益"),
            ("month3_profit","近3月收益"),
            ("ytd_profit",   "今年来收益"),
        ]:
            if profit_col in df.columns:
                f.write(f"{label}: ¥{df[profit_col].sum():+,.2f}\n")
    print(f"✅ 报表已保存: {txt_path}")
    # CSV 数据
    csv_path = os.path.join(REPORT_DIR, f"fund_data_{today}.csv")
    available = [c for c in df.columns if c in df.columns]
    df[available].to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"✅ 数据已导出: {csv_path}")


# ============================================================
# 6. 主程序
# ============================================================

def main():
    os.system("")  # Windows ANSI 支持
    print(f"{Color.BOLD}{'='*50}")
    print(f"   基金收益追踪工具 v2.1（修复版）")
    print(f"{'='*50}{Color.RESET}\n")
    portfolio = load_portfolio(CSV_FILE)
    market_data = fetch_all_fund_data()
    df = merge_portfolio(portfolio, market_data)
    if df.empty:
        print(Color.down("❌ 没有有效的基金数据"))
        sys.exit(1)
    print_color_report(df)
    export_report(df)


if __name__ == "__main__":
    main()
