"""
app.core —— 核心基础设施层

提供全项目共享的基础能力：
    - config.py        配置中心（dataclass + 环境变量覆盖）
    - logging_setup.py 统一日志
    - cache.py         分级缓存（内存 + 磁盘）
    - network.py       统一 HTTP 客户端（重试/降级/限速）
    - errors.py        统一异常体系

本层不依赖任何业务模块，可独立使用。
"""

from app.core.config import AppConfig, get_config
from app.core.errors import (
    AppError,
    ConfigError,
    DataFetchError,
    DataSourceError,
    CacheError,
    NetworkError,
)
from app.core.logging_setup import setup_logging, get_logger
from app.core.cache import CacheManager, get_cache_manager
from app.core.network import HTTPClient, get_http_client

__all__ = [
    "AppConfig",
    "get_config",
    "AppError",
    "ConfigError",
    "DataFetchError",
    "DataSourceError",
    "CacheError",
    "NetworkError",
    "setup_logging",
    "get_logger",
    "CacheManager",
    "get_cache_manager",
    "HTTPClient",
    "get_http_client",
]
