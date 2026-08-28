"""
DefaultLogHandler —— 交易引擎默认日志处理器
=============================================

基于标准库 `logging` + 项目统一 `common.logging_utils` 实现，
替代原先依赖第三方 `logbook` 的实现，去掉可选的 logbook 依赖，
提供与旧接口兼容的默认日志器。

用法：
    from stock.infrastructure.default_handler import DefaultLogHandler

    log = DefaultLogHandler(name='trade', log_type='file',
                            filepath='logs/trade.log', loglevel='INFO')
    log.info('...')
"""

import os
import sys

from common.logging_utils import get_logger


class DefaultLogHandler(object):
    """默认的 Log 类（基于标准库 logging）。"""

    def __init__(self, name='default', log_type='stdout', filepath='default.log', loglevel='DEBUG'):
        """Log对象

        :param name: log 名字
        :param log_type: 'stdout' 输出到屏幕, 'file' 输出到指定文件
        :param filepath: log 文件名
        :param loglevel: 设定log等级
                         ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
        :return log handler object
        """
        # 统一使用项目日志器（按 name 命名）
        self.log = get_logger(name)
        level = loglevel.upper() if isinstance(loglevel, str) else 'DEBUG'
        if hasattr(self.log, 'setLevel'):
            self.log.setLevel(level)

        # file 类型：配置一个独立的文件 handler（避免重复叠加）
        if log_type == 'file':
            self._attach_file_handler(filepath, level)

    # ------------------------------------------------------------------
    # 文件 handler（按需附加到该日志器）
    # ------------------------------------------------------------------

    def _attach_file_handler(self, filepath, level):
        """为日志器附加一个按大小滚动的文件 handler。"""
        from logging.handlers import RotatingFileHandler

        # 确保文件所在目录存在
        d = os.path.dirname(os.path.abspath(filepath))
        if d:
            os.makedirs(d, exist_ok=True)

        # 已存在同名文件 handler 则跳过，避免重复输出
        for h in self.log.handlers:
            if isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(filepath):
                return

        handler = RotatingFileHandler(
            filepath, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8'
        )
        handler.setLevel(level)
        handler.setFormatter(
            logging_formatter(include_thread=True)
        )
        self.log.addHandler(handler)
        # 阻止向根 logger 冒泡，避免重复输出
        self.log.propagate = False

    def __getattr__(self, item):
        """透传标准 logging 方法（info/warning/error/debug 等）。"""
        return getattr(self.log, item)


def logging_formatter(include_thread: bool = False):
    """返回统一格式的 Formatter（与 common.logging_utils.LogFormatter 一致）。"""
    from common.logging_utils import LogFormatter
    return LogFormatter(include_thread=include_thread)
