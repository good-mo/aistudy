"""
理财定时监控命令行入口
======================

读取理财持仓，评估收益/风险/期限告警，支持一次检查与定时跟踪。

用法：
    python -m lc_core.cli.monitor --csv lc_holding.csv [--interval 3600]
                                          [--min-rate 2.0] [--once]
                                          [--console-only]

参数说明：
    --csv           理财持仓 CSV 路径（默认 lc_holding.csv）
    --codes-csv     产品编码清单 CSV 路径（默认 lc/product_codes.csv）
    --interval      刷新间隔（秒），默认 3600（1 小时）
    --min-rate      单产品/组合年化收益下限（%），低于则告警
    --once          只运行一次即退出
    --console-only  仅终端输出，不尝试桌面通知
"""

import argparse
import sys
import time

from common.logging_utils import get_logger, setup_logging
from lc_core.tracking.monitor import (
    DEFAULT_CODES_CSV,
    load_holdings,
    build_products,
    LcMonitor,
)
from lc_core.tracking.alert_rules import LcAlertConfig

logger = get_logger(__name__)


def run_once(args) -> None:
    """执行一次理财监控快照。"""
    logger.info("开始本次理财监控快照")
    holdings = load_holdings(args.csv)
    products = build_products(holdings, args.codes_csv)
    config = LcAlertConfig(
        min_annual_rate=args.min_rate,
        enable_console=True,
        enable_notify=not args.console_only,
    )
    monitor = LcMonitor(config)
    messages = monitor.check(products)
    if messages and args.notify_exit:
        logger.warning("理财监控触发 %d 条告警", len(messages))
    logger.info("本次理财监控完成，共 %d 条持仓，告警 %d 条", len(products), len(messages))


def main() -> None:
    parser = argparse.ArgumentParser(description="理财定时监控告警")
    parser.add_argument("--csv", type=str, default="lc_holding.csv", help="理财持仓 CSV 路径")
    parser.add_argument("--codes-csv", type=str, default=DEFAULT_CODES_CSV, help="产品编码清单 CSV 路径")
    parser.add_argument("--interval", type=int, default=3600, help="刷新间隔（秒），默认 3600")
    parser.add_argument("--min-rate", type=float, default=2.0, help="年化收益下限（%%）")
    parser.add_argument("--once", action="store_true", help="只运行一次即退出")
    parser.add_argument("--console-only", action="store_true", help="仅终端输出，不尝试桌面通知")
    parser.add_argument("--notify-exit", action="store_true", help="触发告警时以非零退出码结束（配合 --once）")
    args = parser.parse_args()

    setup_logging()
    logger.info("理财监控启动：csv=%s interval=%ss once=%s", args.csv, args.interval, args.once)

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
