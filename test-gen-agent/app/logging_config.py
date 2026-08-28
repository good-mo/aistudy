# app/logging_config.py
"""
集中式日志配置
==============
遵循最佳实践：统一门面、合理分级、含上下文、控制台 + 文件双输出、日志轮转。
日志路径统一解析为项目根目录下的绝对路径（与 CWD 无关），避免因启动目录不同
导致日志分散、无法追溯。

trace_id 贯穿：
    通过 contextvars 记录当前请求的 request_id，配合 TraceFilter 自动注入到
    每条日志中，使一次请求内的业务日志可跨模块串联，便于排障定位。
"""
import contextvars
import logging
import logging.handlers
import os
import sys

from app.config import settings
from app.db import PROJECT_ROOT


# 当前请求的 trace_id（由 RequestLoggingMiddleware 设置）
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> None:
    """设置当前请求的 trace_id，供日志贯穿使用。"""
    _request_id.set(request_id)


def get_request_id() -> str:
    """获取当前请求的 trace_id。"""
    return _request_id.get()


# 日志格式：时间 | 级别 | trace_id | 模块:行号 | 消息
LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(trace_id)s | %(name)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日志目录：固定在项目根目录下的 logs/，不依赖进程启动 CWD
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")
ERROR_LOG_FILE = os.path.join(LOG_DIR, "error.log")


class TraceFilter(logging.Filter):
    """为日志记录附加当前请求的 trace_id 字段。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_request_id()
        return True


def setup_logging() -> None:
    """
    初始化全局日志配置。应在应用启动时（main.py）尽早调用一次。
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    # 根据环境决定日志级别：开发 DEBUG，生产 INFO
    level = logging.DEBUG if settings.debug else logging.INFO

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    trace_filter = TraceFilter()

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()  # 避免重复添加 handler

    def _new_handler(hdlr: logging.Handler) -> logging.Handler:
        hdlr.setFormatter(formatter)
        hdlr.addFilter(trace_filter)
        return hdlr

    # 1. 控制台输出
    console = _new_handler(logging.StreamHandler(sys.stdout))
    console.setLevel(level)
    root_logger.addHandler(console)

    # 2. 文件输出（按大小轮转：单文件 10MB，保留 5 个备份）
    file_handler = _new_handler(
        logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
    )
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    # 3. 错误日志单独文件（只记 ERROR 及以上，便于快速定位故障）
    error_handler = _new_handler(
        logging.handlers.RotatingFileHandler(
            ERROR_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
    )
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    # 4. 调低第三方库的噪音日志（避免冗余）
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    root_logger.info("✅ 日志系统初始化完成 (level=%s, dir=%s)", logging.getLevelName(level), LOG_DIR)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定模块的 logger。各模块统一调用此函数。
    用法: logger = get_logger(__name__)
    """
    return logging.getLogger(name)


__all__ = ["setup_logging", "get_logger", "set_request_id", "get_request_id"]
