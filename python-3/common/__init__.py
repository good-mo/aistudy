"""
common —— 跨包共享的基础设施

供 jijin_core / share300_core / lc_core / stock_monitor / stock 等
各专业子包复用的通用能力：

    common/
    ├── caching.py         跨包通用磁盘缓存（分级 TTL、JSON/CSV/pickle）
    ├── logging_utils.py   统一专业日志（控制台彩色 + 滚动文件 + 分级）
    └── __init__.py        包入口

依赖：标准库 logging + logging.handlers
"""

from common.caching import DiskCache, get_cache, parse_ttl
from common.logging_utils import (
    get_logger,
    setup_logging,
    get_log_dir,
    LogFormatter,
    ColoredFormatter,
)

__all__ = [
    "DiskCache",
    "get_cache",
    "parse_ttl",
    "get_logger",
    "setup_logging",
    "get_log_dir",
    "LogFormatter",
    "ColoredFormatter",
]
__version__ = "1.0.0"
