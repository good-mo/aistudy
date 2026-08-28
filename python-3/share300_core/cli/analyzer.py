"""沪深300 成分股分析命令行入口。

用法：
    python -m share300_core.cli.analyzer [--workers N] [--top N] [--refresh]
"""

import argparse
import sys

from common.logging_utils import get_logger, setup_logging
from share300_core.analysis.analyzer import HS300Analyzer

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="沪深300成分股综合分析系统")
    parser.add_argument("--workers", type=int, default=10, help="并发线程数")
    parser.add_argument("--top", type=int, default=20, help="报告展示前 N 名")
    parser.add_argument("--refresh", action="store_true", help="强制刷新所有缓存数据")
    args = parser.parse_args()

    setup_logging()
    logger.info("沪深300 综合分析启动：workers=%s top=%s refresh=%s", args.workers, args.top, args.refresh)

    print("\n" + "=" * 100)
    print("🚀 沪深300成分股综合分析系统 (share300_core)")
    print("=" * 100)
    print("本程序将自动分析沪深300所有成分股，基于9大技术指标筛选买入/卖出信号")
    print("技术指标：MA均线、MACD、KDJ、RSI、成交量、布林带、支撑/阻力位、K线形态、价格形态")
    print("数据源：腾讯财经 API（qt.gtimg.cn）\n")
    if args.refresh:
        print("🔄 已开启强制刷新模式，将忽略缓存重新拉取数据\n")

    logger.info("阶段[初始化] 创建 HS300Analyzer，加载基本面/行业缓存数据...")
    analyzer = HS300Analyzer(max_workers=args.workers, force_refresh=args.refresh)
    logger.info("阶段[成分股] 开始获取沪深300成分股列表...")
    analyzer.run_analysis(top_n=args.top)
    logger.info("沪深300 综合分析完成")


if __name__ == "__main__":
    main()
