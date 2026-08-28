"""
app.core.logging_setup —— 统一日志

复用 common.logging_utils 的成熟日志能力，封装为 app.core 统一的入口。
同时保留对 common 的兼容（若 common 不可用则退化为标准库日志）。

功能：
    - setup_logging() 幂等初始化
    - get_logger(name) 获取日志器
"""

from __future__ import annotations

import logging
import sys

from app.core.config import get_config


def setup_logging() -> None:
    """初始化统一日志（幂等）。

    优先复用 common.logging_utils（彩色控制台 + 滚动文件），
    若不可用则退化为标准库 basicConfig。
    """
    try:
        from common.logging_utils import setup_logging as _common_setup

        _common_setup()
        return
    except ImportError:
        pass

    # 退化：标准库日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    """获取日志器。

    Args:
        name: 日志器名称（通常传 __name__）。
    """
    try:
        from common.logging_utils import get_logger as _common_logger

        return _common_logger(name)
    except ImportError:
        pass
    return logging.getLogger(name)
