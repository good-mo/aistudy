"""
app.core.errors —— 统一异常体系

定义全项目共享的异常层次，所有业务/数据层异常均继承自 AppError，
便于上层统一捕获与降级处理。
"""

from __future__ import annotations


class AppError(Exception):
    """应用统一异常基类。"""

    def __init__(self, message: str = "", *, cause: Exception | None = None):
        super().__init__(message)
        self.message = message
        self.cause = cause

    def __str__(self) -> str:
        base = self.message or self.__class__.__name__
        if self.cause:
            return f"{base} (caused by: {self.cause.__class__.__name__}: {self.cause})"
        return base


class ConfigError(AppError):
    """配置错误（无效配置、缺失必填项等）。"""


class NetworkError(AppError):
    """网络请求错误（超时、连接失败、HTTP 错误等）。"""


class DataSourceError(AppError):
    """数据源错误（数据源返回异常、解析失败等）。"""


class DataFetchError(AppError):
    """数据获取错误（所有数据源均失败时抛出）。"""


class CacheError(AppError):
    """缓存读写错误。"""


class DomainError(AppError):
    """领域业务逻辑错误。"""


class ValidationError(AppError):
    """数据校验错误。"""
