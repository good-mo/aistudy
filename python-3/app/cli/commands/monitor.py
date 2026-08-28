"""
app.cli.commands.monitor —— 综合监控命令

将基金、沪深300、理财等每日监控整合为一次统一运行。
"""

from __future__ import annotations

import argparse

from app.core.logging_setup import get_logger

logger = get_logger(__name__)


def monitor_command(argv: list[str] | None = None) -> int:
    """综合监控命令。"""
    parser = argparse.ArgumentParser(description="综合每日监控")
    parser.add_argument("--only", default=None, help="仅运行指定子系统（逗号分隔: fund,hs300,wealth）")
    parser.add_argument("--csv", default=None, help="持仓 CSV 路径（基金/理财共用）")
    args = parser.parse_args(argv)

    only = None
    if args.only:
        only = [k.strip() for k in args.only.split(",") if k.strip()]

    print("=" * 60)
    print("📊 综合监控 · 每日运行")
    print("=" * 60)

    results = []
    csv_args = ["--csv", args.csv] if args.csv else []

    # 基金监控
    if only is None or "fund" in only:
        print("\n▶ 基金监控")
        from app.cli.commands import fund_command
        ret = fund_command(csv_args + ["--monitor", "--once"])
        results.append(("fund", "基金监控", ret))

    # 沪深300 监控
    if only is None or "hs300" in only:
        print("\n▶ 沪深300 监控")
        from app.cli.commands import hs300_command
        ret = hs300_command(["--top", "5"])
        results.append(("hs300", "沪深300", ret))

    # 理财监控
    if only is None or "wealth" in only:
        print("\n▶ 理财产品监控")
        from app.cli.commands import wealth_command
        ret = wealth_command(csv_args + ["--monitor", "--once"])
        results.append(("wealth", "理财", ret))

    # 汇总
    print("\n" + "=" * 60)
    print("📋 监控汇总")
    print("=" * 60)
    failed = 0
    for key, name, ret in results:
        status = "✅ 完成" if ret == 0 else f"⚠️ 失败(码{ret})"
        if ret != 0:
            failed += 1
        print(f"  [{key}] {name:<8} {status}")

    return 1 if failed else 0
