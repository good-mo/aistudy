"""
基金定时监控命令行入口
======================

持续运行，定时拉取持仓基金净值/收益，超过阈值即触发告警（终端 + 桌面通知）。

用法：
    python -m jijin_core.cli.monitor --csv portfolio.csv [--interval 300]
                                        [--single-drop 3] [--port-loss 1000]
                                        [--single-loss 2000] [--single-loss-pct 10]
                                        [--port-float-loss 5000]
                                        [--once] [--console-only]

参数说明：
    --interval          刷新间隔（秒），默认 300（5 分钟）
    --single-drop       单只基金当日跌幅阈值（%）
    --port-loss         组合当日亏损金额阈值（元）
    --single-loss       单只基金累计浮亏金额阈值（元）
    --single-loss-pct   单只基金累计浮亏百分比阈值（%）
    --port-float-loss   组合累计浮亏金额阈值（元）
    --once              只运行一次即退出（便于 cron / 测试）
    --console-only      仅终端输出，不尝试桌面通知
"""

import argparse
import sys
import time

import pandas as pd

from common.logging_utils import get_logger, setup_logging
from ..tracking.daily_tracker import load_portfolio
from ..tracking.alerts import AlertEngine
from ..tracking.alert_rules import AlertConfig
from ..utils.terminal import Color

logger = get_logger(__name__)


def build_merged_snapshot(portfolio: pd.DataFrame) -> pd.DataFrame:
    """为持仓拉取最新净值并计算收益/浮亏，返回合并后的 DataFrame。

    单只基金数据获取失败时该项保留原始成本（收益记为 0），不阻塞整体监控。
    """
    from ..data.sources.akshare_source import has_akshare, get_fund_nav_akshare

    rows = []
    for _, row in portfolio.iterrows():
        code = str(row["fund_code"])
        cost = float(row.get("total_cost", 0))
        entry = {
            "fund_code": code,
            "fund_name": row.get("fund_name", code),
            "total_cost": cost,
            "nav": 0.0,
            "daily_return": 0.0,
            "prev_nav": 0.0,
        }
        try:
            if has_akshare():
                df = get_fund_nav_akshare(code)
                if df is not None and not df.empty:
                    df = df.sort_values("date")
                    latest = float(df.iloc[-1]["value"])
                    prev = float(df.iloc[-2]["value"]) if len(df) > 1 else latest
                    entry["nav"] = latest
                    entry["prev_nav"] = prev
                    entry["daily_return"] = (latest / prev - 1) * 100 if prev else 0.0
                    entry["nav_date"] = str(df.iloc[-1]["date"])
                    logger.info(
                        "拉取净值成功 基金[%s] %s | 净值 %.4f | 日涨跌 %+.2f%% | 净值日期 %s",
                        code, row.get("fund_name", code), latest, entry["daily_return"],
                        entry["nav_date"],
                    )
                else:
                    logger.warning("基金 %s 净值数据为空，使用成本口径（收益记为 0）", code)
        except Exception as e:  # noqa: BLE001
            logger.warning("获取基金 %s 净值失败: %s", code, e)

        rows.append(entry)

    snap = pd.DataFrame(rows)
    # 计算浮亏：以最新净值相对成本估算（简化，净值归一化到成本口径）
    # market_value = cost * nav / first_nav(成本当日约等于1)
    # 此处若无法取得持仓成本对应净值，则用当前净值相对最近日增长粗略估算
    snap["market_value"] = snap["total_cost"] * (
        1 + snap["daily_return"].fillna(0) / 100
    )
    snap["profit"] = snap["market_value"] - snap["total_cost"]
    snap["profit_pct"] = snap["profit"] / snap["total_cost"].replace(0, 1)
    snap["daily_profit"] = snap["total_cost"] * snap["daily_return"].fillna(0) / 100
    return snap


def build_alert_config(args) -> AlertConfig:
    """根据命令行参数构建告警配置。"""
    return AlertConfig(
        single_daily_drop_pct=args.single_drop,
        portfolio_daily_loss_amt=args.port_loss,
        single_float_loss_amt=args.single_loss,
        single_float_loss_pct=args.single_loss_pct,
        portfolio_float_loss_amt=args.port_float_loss,
        enable_console=True,
        enable_notify=not args.console_only,
    )


def print_fund_table(snap: pd.DataFrame) -> None:
    """在终端打印持仓基金明细表（含名称、净值、日涨跌、盈亏等核心字段）。

    无论是否触发告警，都输出每只基金的核心指标，便于人工核对。
    """
    if snap is None or snap.empty:
        print("无基金数据")
        return

    total_cost = float(snap.get("total_cost", 0).sum() or 0)
    total_value = float(snap.get("market_value", snap["total_cost"]).sum() or total_cost)
    total_profit = total_value - total_cost
    total_daily = float(snap.get("daily_profit", 0).sum() or 0)

    print(f"\n{Color.BOLD}基金持仓明细（{len(snap)} 只）{Color.RESET}")
    print(f"总成本 ¥{total_cost:,.2f} | 总市值 ¥{total_value:,.2f} | "
          f"累计盈亏 {Color.by_value(total_profit, '{:+.2f}', '')} | "
          f"今日收益 {Color.by_value(total_daily, '{:+.2f}', '')}")
    print("-" * 78)
    print(f"{'代码':<8}{'名称':<20}{'净值':>10}{'日涨跌':>10}{'累计盈亏':>16}{'日收益':>12}")
    for _, row in snap.iterrows():
        code = str(row.get("fund_code", ""))
        name = str(row.get("fund_name", row.get("name", code)))
        nav = float(row.get("nav", 0) or 0)
        dr = float(row.get("daily_return", 0) or 0)
        profit = float(row.get("profit", 0) or 0)
        daily_profit = float(row.get("daily_profit", 0) or 0)
        print(
            f"{code:<8}{name:<20}{nav:>10.4f}"
            f"{Color.by_value(dr, '{:+.2f}', '%'):>10}"
            f"{Color.by_value(profit, '{:+.2f}'):>16}"
            f"{Color.by_value(daily_profit, '{:+.2f}'):>12}"
        )
    print("-" * 78)


def log_fund_snapshot(snap: pd.DataFrame) -> None:
    """记录本次监控的基金持仓收益明细与组合汇总（便于留档排查）。"""
    if snap is None or snap.empty:
        logger.info("本次监控无基金数据")
        return
    # 单只基金收益明细（净值拉取明细见 build_merged_snapshot）
    for _, row in snap.iterrows():
        code = str(row.get("fund_code", ""))
        name = str(row.get("fund_name", code))
        cost = float(row.get("total_cost", 0) or 0)
        market_value = float(row.get("market_value", cost) or 0)
        profit = float(row.get("profit", 0) or 0)
        profit_pct = float(row.get("profit_pct", 0) or 0)
        daily_profit = float(row.get("daily_profit", 0) or 0)
        logger.info(
            "基金收益明细 基金[%s] %s | 成本 ¥%.2f | 市值 ¥%.2f | 累计盈亏 ¥%+.2f (%+.2f%%) | 日收益 ¥%+.2f",
            code, name, cost, market_value, profit, profit_pct, daily_profit,
        )
    # 组合汇总
    total_cost = float(snap["total_cost"].sum() or 0)
    total_value = float(snap["market_value"].sum() if "market_value" in snap.columns else total_cost)
    total_profit = total_value - total_cost
    total_daily = float(snap["daily_profit"].sum() if "daily_profit" in snap.columns else 0)
    logger.info(
        "基金组合汇总 | 共 %d 只 | 总成本 ¥%.2f | 总市值 ¥%.2f | 累计盈亏 ¥%+.2f | 今日收益 ¥%+.2f",
        len(snap), total_cost, total_value, total_profit, total_daily,
    )


def run_once(args) -> None:
    """执行一次监控快照：拉数据 → 评估告警 → 输出。"""
    logger.info("开始本次基金监控快照")
    portfolio = load_portfolio(args.csv)
    if portfolio.empty:
        logger.warning("持仓为空，跳过本次监控")
        return
    snap = build_merged_snapshot(portfolio)
    # 将本次监控的基金数据写入日志
    log_fund_snapshot(snap)
    # 终端输出持仓基金核心指标明细表（名称/净值/日涨跌/盈亏）
    if not args.quiet:
        print_fund_table(snap)
    engine = AlertEngine(build_alert_config(args))
    messages = engine.evaluate(snap)
    if messages:
        engine.report(messages)
        if not args.console_only and args.notify_exit:
            # 触发告警时可选择非零退出码，便于外部脚本感知
            logger.warning("监控触发 %d 条告警", len(messages))
    else:
        if not args.quiet:
            print(f"{Color.GREEN}✅ {snap['fund_code'].nunique()} 只基金监控正常，未触发告警{Color.RESET}")
    logger.info("本次监控完成，共 %d 只基金，告警 %d 条", len(snap), len(messages))


def main() -> None:
    parser = argparse.ArgumentParser(description="基金定时监控告警")
    parser.add_argument("--csv", type=str, default="portfolio.csv", help="持仓 CSV 路径")
    parser.add_argument("--interval", type=int, default=300, help="刷新间隔（秒），默认 300")
    parser.add_argument("--single-drop", type=float, default=3.0, help="单只基金日跌幅阈值（%%）")
    parser.add_argument("--port-loss", type=float, default=1000.0, help="组合当日亏损阈值（元）")
    parser.add_argument("--single-loss", type=float, default=2000.0, help="单只基金浮亏阈值（元）")
    parser.add_argument("--single-loss-pct", type=float, default=10.0, help="单只基金浮亏百分比阈值（%%）")
    parser.add_argument("--port-float-loss", type=float, default=5000.0, help="组合累计浮亏阈值（元）")
    parser.add_argument("--once", action="store_true", help="只运行一次即退出")
    parser.add_argument("--console-only", action="store_true", help="仅终端输出，不尝试桌面通知")
    parser.add_argument("--quiet", action="store_true", help="无告警时不打印正常提示")
    parser.add_argument("--notify-exit", action="store_true", help="触发告警时以非零退出码结束（配合 --once）")
    args = parser.parse_args()

    setup_logging()
    logger.info("基金监控启动：csv=%s interval=%ss once=%s", args.csv, args.interval, args.once)

    try:
        while True:
            run_once(args)
            if args.once:
                break
            logger.debug("休眠 %d 秒后继续监控...", args.interval)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n监控已停止")
        sys.exit(0)


if __name__ == "__main__":
    main()
