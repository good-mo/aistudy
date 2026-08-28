"""A股盯盘助手命令行入口。

用法：
    python -m stock_monitor.main [--refresh]
"""

import argparse

from common.logging_utils import setup_logging, get_logger
from stock_monitor.config import default_config
from stock_monitor.monitor import StockMonitor

logger = get_logger(__name__)


def main():
    """主函数：构建配置、实例化监控器并启动。"""
    parser = argparse.ArgumentParser(description="A股盯盘助手")
    parser.add_argument("--refresh", action="store_true", help="强制刷新历史日K线缓存")
    args = parser.parse_args()

    setup_logging()
    config = default_config()
    logger.info("A股盯盘助手入口启动")

    # 示例：自定义预警阈值 / 刷新间隔（取消注释启用）
    # config.alert_settings.price_change_pct = 5.0   # 涨跌幅5%时预警
    # config.refresh_interval = 5                    # 每5秒刷新一次

    monitor = StockMonitor(config, force_refresh=args.refresh)
    monitor.run()


if __name__ == "__main__":
    main()
