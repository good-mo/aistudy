"""
app.cli.commands.fund —— 基金命令（分析/筛选/追踪/监控）

用法：
    python -m app fund --code 110011,009665 --days 1095   # 指定基金分析
    python -m app fund --top 20                           # 基金筛选
    python -m app fund screen --top 20                    # 基金筛选（默认）
    python -m app fund index                              # 指数基金筛选
    python -m app fund stable                             # 稳健基金精选
    python -m app fund track --csv portfolio.csv          # 每日收益追踪
    python -m app fund monitor --csv portfolio.csv --once # 定时监控
"""

from __future__ import annotations

import argparse

from app.core.logging_setup import get_logger
from app.domains.fund import (
    AlertConfig,
    FundAnalyzer,
    FundMonitor,
    FundScorer,
    FundScreener,
    FundTracker,
    IndexFundScreener,
)

logger = get_logger(__name__)


def _analyze_codes(args) -> int:
    """分析指定基金代码。"""
    analyzer = FundAnalyzer()
    scorer = FundScorer()
    codes = [c.strip() for c in args.code.split(",") if c.strip()]
    print("=" * 60)
    print("📊 基金分析")
    print("=" * 60)

    for code in codes:
        print(f"\n▶ 基金 {code}")
        quote = analyzer.get_realtime(code)
        if quote:
            print(f"  名称: {quote.get('name', '未知')}")
            print(f"  净值: {quote.get('nav', 'N/A')}")
            print(f"  涨跌幅: {quote.get('change_pct', 'N/A')}%")
        else:
            print("  ⚠️ 实时行情获取失败（无数据）")

        nav = analyzer.get_nav_history(code, days=args.days)
        if not nav.empty:
            metrics = analyzer.calculate_metrics(nav)
            score = scorer.score(metrics)
            print(f"  净值数据: {metrics.get('n_days', 0)} 条")
            print(f"  年化收益: {metrics.get('annual_return', 0) * 100:.2f}%")
            print(f"  最大回撤: {metrics.get('max_drawdown', 0) * 100:.2f}%")
            print(f"  夏普比率: {metrics.get('sharpe_ratio', 0):.2f}")
            print(f"  综合评分: {score['total_score']} ({score['level']})")
        else:
            print("  ⚠️ 历史净值获取失败（无数据）")
    return 0


def fund_command(argv: list[str] | None = None) -> int:
    """基金命令入口。"""
    parser = argparse.ArgumentParser(description="基金分析")
    parser.add_argument("subcommand", nargs="?",
                        help="子命令（screen/index/stable/track/monitor）")
    parser.add_argument("--code", default="", help="基金代码（逗号分隔）")
    parser.add_argument("--days", type=int, default=1095, help="获取天数")
    parser.add_argument("--refresh", action="store_true", help="强制刷新数据")
    parser.add_argument("--top", type=int, default=50, help="筛选前 N 名")
    parser.add_argument("--csv", default="portfolio.csv", help="持仓 CSV 路径")
    parser.add_argument("--interval", type=int, default=300, help="监控刷新间隔（秒）")
    parser.add_argument("--single-drop", type=float, default=3.0, help="单只日跌幅阈值")
    parser.add_argument("--port-loss", type=float, default=1000.0, help="组合日亏损阈值")
    parser.add_argument("--single-loss", type=float, default=2000.0, help="单只浮亏阈值")
    parser.add_argument("--single-loss-pct", type=float, default=10.0, help="单只浮亏百分比")
    parser.add_argument("--port-float-loss", type=float, default=5000.0, help="组合浮亏阈值")
    parser.add_argument("--once", action="store_true", help="只运行一次")
    parser.add_argument("--index", action="store_true", help="指数基金筛选")
    parser.add_argument("--stable", action="store_true", help="稳健基金精选")
    parser.add_argument("--track", action="store_true", help="每日收益追踪")
    parser.add_argument("--monitor", action="store_true", help="定时监控")
    args = parser.parse_args(argv)

    # 兼容子命令形式：`app fund screen/index/stable/track/monitor`
    if args.subcommand == "track":
        args.track = True
    elif args.subcommand == "monitor":
        args.monitor = True
    elif args.subcommand == "index":
        args.index = True
    elif args.subcommand == "stable":
        args.stable = True

    # 功能路由
    if args.track:
        tracker = FundTracker(args.csv)
        tracker.run_once()
        return 0

    if args.monitor:
        config = AlertConfig(
            single_daily_drop_pct=args.single_drop,
            portfolio_daily_loss_amt=args.port_loss,
            single_float_loss_amt=args.single_loss,
            single_float_loss_pct=args.single_loss_pct,
            portfolio_float_loss_amt=args.port_float_loss,
        )
        monitor = FundMonitor(args.csv)
        if args.once:
            monitor.run_once(config)
            return 0
        monitor.run_loop(args.interval, config)
        return 0

    if args.index or args.stable:
        screener = IndexFundScreener()
        if args.stable:
            results = screener.pick_stable_fund()
            print(f"{'代码':<8}{'名称':<24}{'年化':>8}{'回撤':>8}{'夏普':>8}{'稳健分':>8}")
            for r in results[: args.top]:
                print(
                    f"{r['code']:<8}{r['name']:<24}"
                    f"{r['annual_return']*100:>7.2f}%{r['max_drawdown']*100:>7.2f}%"
                    f"{r['sharpe']:>8.2f}{r['stability_score']:>8.1f}"
                )
            return 0
        df = screener.screen_popular_index_funds()
        print(f"{'代码':<8}{'名称':<24}{'年化':>8}{'回撤':>8}{'评分':>8}")
        for _, row in df.iterrows():
            print(
                f"{str(row.get('code','')):<8}{str(row.get('name','')):<24}"
                f"{float(row.get('annual_return',0) or 0)*100:>7.2f}%"
                f"{float(row.get('max_drawdown',0) or 0)*100:>7.2f}%"
                f"{float(row.get('fund_layer_score',0) or 0):>8.1f}"
            )
        return 0

    if args.code:
        return _analyze_codes(args)

    # 默认：基金筛选
    screener = FundScreener()
    code_list = None
    if args.code:
        code_list = [c.strip() for c in args.code.split(",") if c.strip()]
    df = screener.run_screening(top_n=args.top, force_refresh=args.refresh, code_list=code_list)
    if df.empty:
        print("无筛选结果")
        return 0
    print(f"{'代码':<8}{'名称':<20}{'年化':>8}{'回撤':>8}{'评分':>8}{'信号':<6}")
    for _, row in df.iterrows():
        print(
            f"{str(row.get('fund_code','')):<8}{str(row.get('fund_name','')):<20}"
            f"{float(row.get('annual_return',0) or 0)*100:>7.2f}%"
            f"{float(row.get('max_drawdown',0) or 0)*100:>7.2f}%"
            f"{float(row.get('score',0) or 0):>8.1f}{str(row.get('signal','')):<6}"
        )
    return 0
