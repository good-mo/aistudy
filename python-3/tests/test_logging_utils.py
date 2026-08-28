"""common.logging_utils 单元测试。

验证统一专业日志模块的核心行为：
- setup_logging 幂等，仅配置一次 handler
- 控制台 / 文件 handler 均被正确挂载
- 日志消息写入滚动文件
- get_logger 返回可用的标准 logging.Logger
"""

import logging
import logging.handlers
import os

from common.logging_utils import (
    get_logger,
    setup_logging,
    get_log_dir,
    LogFormatter,
    ColoredFormatter,
)


def _reset_logging():
    """重置全局日志状态，保证测试相互独立。"""
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(logging.WARNING)
    from common import logging_utils
    logging_utils._INITIALIZED = False


def test_setup_logging_installs_handlers():
    _reset_logging()
    setup_logging(level="DEBUG")
    root = logging.getLogger()

    handler_types = {type(h) for h in root.handlers}
    assert logging.StreamHandler in handler_types
    assert logging.handlers.RotatingFileHandler in handler_types

    # 文件 handler 写向 logs/ 目录
    file_handler = next(h for h in root.handlers
                        if isinstance(h, logging.handlers.RotatingFileHandler))
    assert file_handler.baseFilename.startswith(get_log_dir())


def test_setup_logging_is_idempotent():
    _reset_logging()
    setup_logging()
    count_before = len(logging.getLogger().handlers)
    setup_logging()
    count_after = len(logging.getLogger().handlers)
    assert count_before == count_after, "重复 setup_logging 不应叠加 handler"


def test_logger_writes_to_file():
    _reset_logging()
    setup_logging(level="INFO")

    log = get_logger("test.logger")
    log.info("测试日志消息 %s", 42)

    log_file = os.path.join(get_log_dir(), "app.log")
    assert os.path.exists(log_file)
    content = open(log_file, encoding="utf-8").read()
    assert "测试日志消息 42" in content


def test_get_logger_returns_standard_logger():
    _reset_logging()
    log = get_logger("some.module")
    assert isinstance(log, logging.Logger)
    assert log.name == "some.module"


def test_colored_formatter_contains_level_and_name():
    _reset_logging()
    fmtr = ColoredFormatter()
    record = logging.LogRecord(
        name="mod", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello %s", args=("world",), exc_info=None, func="run",
    )
    out = fmtr.format(record)
    assert "mod" in out
    assert "INFO" in out
    assert "hello world" in out
    assert "run" in out  # 运行函数名被记录，便于定位


def test_log_formatter():
    _reset_logging()
    fmtr = LogFormatter()
    record = logging.LogRecord(
        name="mod", level=logging.INFO, pathname=__file__, lineno=1,
        msg="msg", args=(), exc_info=None, func="collect_data",
    )
    out = fmtr.format(record)
    assert "mod" in out
    assert "msg" in out
    assert "collect_data" in out  # 运行函数名被记录
