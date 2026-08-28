"""
common.logging_utils —— 统一专业日志模块
==========================================

为项目内各金融分析子系统（基金 / 盯盘 / 沪深300 / 理财 / 交易引擎）
提供一致的、专业化的日志能力：

功能特性
--------
- **分级输出**：DEBUG / INFO / WARNING / ERROR / CRITICAL 五级
- **彩色控制台**：按日志级别着色的 StreamHandler，便于终端识别
- **滚动文件**：按大小滚动的 RotatingFileHandler，写入项目根目录 `logs/`
- **统一格式**：时间戳 + 级别 + 日志器名 + 线程 + 消息，便于检索与排查
- **日志目录**：自动创建 `logs/`，子模块可方便地定位日志文件
- **幂等初始化**：重复调用 `setup_logging()` 不会叠加重复的 handler

用法示例
--------
    from common.logging_utils import get_logger, setup_logging

    setup_logging()                     # 在程序入口初始化一次
    logger = get_logger(__name__)       # 各模块获取自己的日志器
    logger.info("任务开始")
    logger.error("处理失败: %s", err)
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

# ---------------------------------------------------------------------------
# 路径与常量
# ---------------------------------------------------------------------------

# common/ 包所在目录
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
# 项目根目录（common/ 的上一级）
PROJECT_ROOT = os.path.dirname(_PKG_DIR)

# 日志根目录
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
# 默认日志文件名
DEFAULT_LOG_FILE = "app.log"

# 默认滚动文件大小 / 备份份数
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUP_COUNT = 5

# 默认日志级别（可通过环境变量 APP_LOG_LEVEL 覆盖）
DEFAULT_LEVEL = os.environ.get("APP_LOG_LEVEL", "INFO").upper()

# 已初始化标志（保证幂等）
_INITIALIZED = False


# ---------------------------------------------------------------------------
# 格式化器
# ---------------------------------------------------------------------------

class LogFormatter(logging.Formatter):
    """统一的日志格式（无颜色）。"""

    # 使用空格补齐 %-5s 等格式，保证对齐；
    # 加入 %(funcName)s 使每条日志都能对应到所属运行函数，便于定位。
    FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s | %(message)s"
    DATEFMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, include_thread: bool = False):
        fmt = self.FMT
        if include_thread:
            fmt = fmt.replace("%(name)s", "%(threadName)s | %(name)s")
        super().__init__(fmt=fmt, datefmt=self.DATEFMT)
        self._include_thread = include_thread


class ColoredFormatter(logging.Formatter):
    """为控制台输出提供按级别着色的日志格式。"""

    # ANSI 颜色码
    COLORS = {
        "DEBUG": "\033[90m",      # 灰
        "INFO": "\033[32m",       # 绿
        "WARNING": "\033[33m",    # 黄
        "ERROR": "\033[31m",      # 红
        "CRITICAL": "\033[41;97m",  # 红底白字
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    # 时间戳（暗色）、级别（着色加粗）、日志器名（青色）、函数名（淡青色）
    FMT = (
        "\033[2m%(asctime)s\033[0m | "
        "%(levelcolor)s%(levelname)-8s\033[0m | "
        "\033[36m%(name)s\033[0m | "
        "\033[36m%(funcName)s\033[0m | %(message)s"
    )
    DATEFMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, include_thread: bool = False):
        fmt = self.FMT
        if include_thread:
            fmt = fmt.replace("%(name)s", "%(threadName)s | %(name)s")
        super().__init__(fmt=fmt, datefmt=self.DATEFMT)
        self._include_thread = include_thread

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        level_fmt = self._fmt  # 使用实例格式串（已处理 include_thread）
        # 用真实级别名替换占位符，避免多行消息错乱
        record.levelcolor = color
        # 借助临时变量保存原格式串
        _orig_fmt = self._fmt
        self._fmt = level_fmt
        try:
            return super().format(record)
        finally:
            self._fmt = _orig_fmt


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------

def get_log_dir() -> str:
    """返回日志目录，并确保其存在。"""
    os.makedirs(LOG_DIR, exist_ok=True)
    return LOG_DIR


def _level_from_str(level: str) -> int:
    """将字符串级别安全地转换为 logging 级别数字。"""
    level = str(level).upper()
    if level in logging._nameToLevel:
        return logging._nameToLevel[level]
    return logging.INFO


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    console: bool = True,
    to_file: bool = True,
    include_thread: bool = False,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> None:
    """初始化全局日志配置（幂等）。

    参数
    ----
    level : str
        日志级别，如 DEBUG/INFO/WARNING/ERROR。默认读取环境变量 APP_LOG_LEVEL，
        未设置时为 INFO。
    log_file : str
        日志文件名（默认 app.log），写入项目根目录 logs/ 下。
    console : bool
        是否启用彩色控制台输出。
    to_file : bool
        是否启用滚动文件输出。
    include_thread : bool
        文件日志是否包含线程名（便于排查并发问题）。
    max_bytes / backup_count :
        滚动文件大小与备份份数。
    """
    global _INITIALIZED

    level_num = _level_from_str(level) if level else _level_from_str(DEFAULT_LEVEL)
    root = logging.getLogger()

    # 幂等：已初始化则仅更新级别
    if _INITIALIZED:
        root.setLevel(level_num)
        return

    root.setLevel(level_num)
    root.handlers.clear()  # 清理可能存在的默认 handler

    # 控制台彩色输出
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level_num)
        console_handler.setFormatter(ColoredFormatter(include_thread=include_thread))
        root.addHandler(console_handler)

    # 滚动文件输出
    if to_file:
        log_dir = get_log_dir()
        path = os.path.join(log_dir, log_file or DEFAULT_LOG_FILE)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level_num)
        file_handler.setFormatter(LogFormatter(include_thread=include_thread))
        root.addHandler(file_handler)

    # 防止日志消息向 stderr 的默认 handler 重复输出
    root.propagate = True

    _INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """获取统一配置的子日志器。

    参数
    ----
    name : str
        通常传 ``__name__``，日志器名自动继承 common. 前缀层级。
    """
    return logging.getLogger(name)
