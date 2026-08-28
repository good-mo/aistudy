"""
每日收益追踪
读取极简 CSV（fund_code + total_cost），自动查询并追踪每日收益。
"""

import os

import pandas as pd

from ..data.sources.akshare_source import has_akshare, get_fund_nav_akshare
from ..utils.terminal import Color
from .alerts import AlertEngine
from .alert_rules import AlertConfig
from common.logging_utils import get_logger

logger = get_logger(__name__)

# 默认 CSV 路径
DEFAULT_CSV = "portfolio.csv"
REPORT_DIR = "fund_records"

# 阶段收益率列映射：中文名 → (标准名, 利润列名)
STAGE_COLUMNS = {
    "日增长率": ("daily_return", "daily_profit"),
    "近1周": ("week_return", "week_profit"),
    "近1月": ("month_return", "month_profit"),
    "近3月": ("month3_return", "month3_profit"),
    "近6月": ("month6_return", "month6_profit"),
    "近1年": ("year_return", "year_profit"),
    "今年来": ("ytd_return", "ytd_profit"),
}


def load_portfolio(csv_path: str) -> pd.DataFrame:
    """读取极简持仓 CSV，至少含 fund_code 和 total_cost。"""
    if not os.path.exists(csv_path):
        logger.error("持仓文件不存在: %s", csv_path)
        raise FileNotFoundError(
            f"持仓文件不存在: {csv_path}\n"
            f"请先创建持仓文件（CSV），至少包含 fund_code（基金代码）和 "
            f"total_cost（投入成本）两列，示例：\n"
            f"fund_code,total_cost\n"
            f"110011,10000.00\n"
            f"009665,20000.00"
        )
    df = pd.read_csv(csv_path, dtype={"fund_code": str})
    # 兼容中文/英文列名
    if "fund_code" not in df.columns and "代码" in df.columns:
        df = df.rename(columns={"代码": "fund_code"})
    if "total_cost" not in df.columns and "成本" in df.columns:
        df = df.rename(columns={"成本": "total_cost"})
    # 校验必需列
    required = {"fund_code", "total_cost"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"持仓 CSV 缺少必需列: {missing}，请至少提供 fund_code 与 total_cost"
        )
    df["fund_code"] = df["fund_code"].astype(str).str.strip().str.zfill(6)
    df["total_cost"] = pd.to_numeric(df["total_cost"], errors="coerce").fillna(0)
    logger.debug("加载持仓 %d 条：%s", len(df), csv_path)
    return df


def fetch_fund_data(fund_code: str) -> dict:
    """获取单只基金的最新净值与收益率。"""
    data = {"fund_code": fund_code}
    if has_akshare():
        df = get_fund_nav_akshare(fund_code)
        if df is not None and not df.empty:
            latest = float(df.iloc[-1]["value"])
            prev = float(df.iloc[-2]["value"]) if len(df) > 1 else latest
            data["nav"] = latest
            data["daily_return"] = (latest / prev - 1) if prev else 0.0
    return data


def fetch_all_fund_data() -> pd.DataFrame:
    """获取组合中所有基金的数据。"""
    # 简化：组合数据由上层传入
    return pd.DataFrame()


def merge_portfolio(portfolio: pd.DataFrame, market_data: pd.DataFrame) -> pd.DataFrame:
    """合并持仓与行情数据，计算收益与盈亏。"""
    df = portfolio.copy()
    for _, row in market_data.iterrows():
        code = row.get("fund_code")
        mask = df["fund_code"] == code
        if mask.any():
            df.loc[mask, "nav"] = row.get("nav", 0)
            df.loc[mask, "daily_return"] = row.get("daily_return", 0)
    # 计算持仓市值与盈亏
    if "total_cost" in df and "nav" in df:
        df["market_value"] = df["total_cost"] * (1 + df["daily_return"].fillna(0))
        df["profit"] = df["market_value"] - df["total_cost"]
        df["profit_pct"] = df["profit"] / df["total_cost"].replace(0, 1)
    return df


def safe_get(row, col, default=0):
    """安全取值。"""
    try:
        val = row.get(col, default)
        return val if val is not None else default
    except Exception:  # noqa: BLE001
        return default


def print_color_report(df: pd.DataFrame) -> None:
    """终端彩色输出收益报告。"""
    if df.empty:
        print("无数据")
        return
    total_cost = df["total_cost"].sum()
    total_value = df.get("market_value", df["total_cost"]).sum()
    total_profit = total_value - total_cost
    print(f"\n{Color.BOLD}组合总览{Color.RESET}")
    print(f"总成本: {total_cost:.2f}  总市值: {total_value:.2f}")
    print(f"总盈亏: {Color.by_value(total_profit, '{:+.2f}')}")
    print()
    print(f"{'代码':<8}{'名称':<20}{'净值':>8}{'日涨跌':>10}{'盈亏':>12}")
    for _, row in df.iterrows():
        code = safe_get(row, "fund_code", "")
        name = safe_get(row, "name", code, )
        nav = safe_get(row, "nav", 0)
        dr = safe_get(row, "daily_return", 0)
        profit = safe_get(row, "profit", 0)
        print(
            f"{code:<8}{str(name):<20}{nav:>8.4f}"
            f"{Color.by_value(dr*100, '{:+.2f}', '%'):>10}"
            f"{Color.by_value(profit, '{:+.2f}'):>12}"
        )


def export_report(df: pd.DataFrame) -> str:
    """导出报告到 CSV，返回文件路径。"""
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join(REPORT_DIR, f"fund_report_{pd.Timestamp.now():%Y%m%d}.csv")
    df.to_csv(path, index=False)
    logger.info("收益报告已导出：%s", path)
    return path


def main(csv_path: str = DEFAULT_CSV, alert_config: AlertConfig | None = None) -> None:
    """追踪入口。

    加载持仓 → 合并行情 → 输出日报 → 评估并输出监控告警。
    """
    logger.info("每日收益追踪：加载持仓 %s", csv_path)
    portfolio = load_portfolio(csv_path)
    data = fetch_all_fund_data()
    df = merge_portfolio(portfolio, data)
    if df.empty:
        logger.warning("无有效持仓数据，跳过报告与告警")
        return
    print_color_report(df)

    # 监控告警（告警引擎期望 daily_return 为百分比，profit_pct 为小数）
    alert_df = df.copy()
    if "daily_return" in alert_df.columns:
        alert_df["daily_return"] = alert_df["daily_return"] * 100
    engine = AlertEngine(alert_config or AlertConfig())
    engine.check(alert_df)

    logger.info("每日收益追踪完成，共 %d 只基金", len(df))
