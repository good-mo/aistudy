"""
app.cli.commands.wealth —— 理财产品命令（分析/监控）

用法：
    python -m app wealth                     # 持仓汇总
    python -m app wealth analyze --risk 3    # 深度画像分析
    python -m app wealth monitor --once      # 定时监控
"""

from __future__ import annotations

import argparse

from app.core.logging_setup import get_logger
from app.domains.wealth import (
    InvestorProfile,
    LcAlertConfig,
    LcMonitor,
    WealthAnalyzer,
)

logger = get_logger(__name__)


def wealth_command(argv: list[str] | None = None) -> int:
    """理财产品命令。"""
    parser = argparse.ArgumentParser(description="理财产品分析")
    parser.add_argument("subcommand", nargs="?", help="子命令（analyze/monitor）")
    parser.add_argument("--csv", default=None, help="持仓 CSV 路径")
    parser.add_argument("--analyze", action="store_true", help="深度画像分析")
    parser.add_argument("--monitor", action="store_true", help="定时监控")
    parser.add_argument("--once", action="store_true", help="只运行一次")
    parser.add_argument("--risk", type=int, default=3, choices=[1, 2, 3, 4, 5], help="风险承受 1-5")
    parser.add_argument("--goal", type=str, default="稳健增值", help="投资目标")
    parser.add_argument("--horizon", type=str, default="1-3年", help="投资期限")
    parser.add_argument("--liquidity", type=str, default="中", help="流动性需求")
    parser.add_argument("--min-rate", type=float, default=2.0, help="年化收益下限")
    parser.add_argument("--interval", type=int, default=3600, help="监控刷新间隔（秒）")
    args = parser.parse_args(argv)

    # 兼容子命令形式：`app wealth analyze` / `app wealth monitor`
    if args.subcommand == "analyze":
        args.analyze = True
    elif args.subcommand == "monitor":
        args.monitor = True

    if args.monitor:
        config = LcAlertConfig(min_annual_rate=args.min_rate)
        monitor = LcMonitor(config)
        if args.once:
            monitor.run_once(args.csv or "lc_holding.csv")
            return 0
        monitor.run_loop(args.csv or "lc_holding.csv", args.interval)
        return 0

    analyzer = WealthAnalyzer(portfolio_csv=args.csv)

    if args.analyze:
        profile = InvestorProfile(
            risk_tolerance=args.risk,
            investment_goal=args.goal,
            investment_horizon=args.horizon,
            liquidity_need=args.liquidity,
        )
        print(f"\n{'='*60}")
        print("🔍 理财产品深度分析")
        print(f"{'='*60}")
        print(f"👤 画像：风险R{args.risk} | {args.goal} | {args.horizon} | 流动性{args.liquidity}")
        reports = analyzer.analyze(profile)
        for i, r in enumerate(reports, 1):
            score = r.get("综合评分", {}).get("综合得分", 0)
            print(f"\n[{i}] {r.get('产品', '')} | 综合得分 {score:.1f} | {r.get('买卖建议', '')}")
        return 0

    print("=" * 60)
    print("💼 理财产品汇总")
    print("=" * 60)
    summary = analyzer.summarize()
    print(f"  产品数量: {summary.get('total_products', 0)}")
    print(f"  总金额:   {summary.get('total_amount', 0):.2f}")
    if summary.get("columns"):
        print(f"  字段:     {', '.join(summary['columns'])}")
    return 0
