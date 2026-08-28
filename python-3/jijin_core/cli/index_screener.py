"""
指数基金筛选命令行入口
    python -m jijin_core.cli.index_screener
"""

import argparse

from common.logging_utils import get_logger, setup_logging
from ..screening.index_fund import screen_popular_index_funds
from ..screening.stable_picker import main as stable_main

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="指数基金筛选")
    parser.add_argument("--index", action="store_true", help="筛选指数基金")
    parser.add_argument("--stable", action="store_true", help="精选稳健基金")
    args = parser.parse_args()

    setup_logging()
    logger.info("指数基金筛选启动：index=%s stable=%s", args.index, args.stable)

    if args.stable:
        stable_main()
        return

    df = screen_popular_index_funds()
    if df.empty:
        print("无筛选结果")
        logger.warning("指数基金筛选结果为空")
        return
    logger.info("指数基金筛选完成，共 %d 条结果", len(df))
    print(f"{'代码':<8}{'名称':<24}{'年化':>8}{'回撤':>8}{'评分':>8}")
    for _, row in df.iterrows():
        print(
            f"{str(row.get('code','')):<8}{str(row.get('name','')):<24}"
            f"{float(row.get('annual_return',0) or 0)*100:>7.2f}%"
            f"{float(row.get('max_drawdown',0) or 0)*100:>7.2f}%"
            f"{float(row.get('fund_layer_score',0) or 0):>8.1f}"
        )


if __name__ == "__main__":
    main()
