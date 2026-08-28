"""
app.cli.commands.hs300 —— 沪深300 分析命令

用法：
    python -m app hs300 --top 10 --workers 10
"""

from __future__ import annotations

import argparse

from app.core.logging_setup import get_logger
from app.domains.hs300 import HS300Analyzer

logger = get_logger(__name__)


def hs300_command(argv: list[str] | None = None) -> int:
    """沪深300 技术分析命令。"""
    parser = argparse.ArgumentParser(description="沪深300 技术分析")
    parser.add_argument("--top", type=int, default=20, help="展示前 N 名")
    parser.add_argument("--workers", type=int, default=10, help="并发线程数")
    parser.add_argument("--refresh", action="store_true", help="强制刷新")
    args = parser.parse_args(argv)

    analyzer = HS300Analyzer(max_workers=args.workers, force_refresh=args.refresh)
    analyzer.generate_report(top_n=args.top)
    return 0
