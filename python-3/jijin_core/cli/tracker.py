"""
每日收益追踪命令行入口
    python -m jijin_core.cli.tracker [--csv portfolio.csv]
"""

import argparse

from common.logging_utils import get_logger, setup_logging
from ..tracking.daily_tracker import load_portfolio, merge_portfolio, print_color_report, main as tracker_main

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="基金每日收益追踪")
    parser.add_argument("--csv", type=str, default="portfolio.csv", help="持仓 CSV 路径")
    args = parser.parse_args()

    setup_logging()
    logger.info("每日收益追踪启动：csv=%s", args.csv)
    tracker_main(args.csv)


if __name__ == "__main__":
    main()
