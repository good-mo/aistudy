"""
app.core.config —— 配置中心

集中管理全局配置，支持：
    - 代码默认值
    - 环境变量覆盖（如 APP_LOG_LEVEL、APP_DATA_CACHE_DIR）
    - dataclass 分组建模
    - 从文件加载（可选，YAML/JSON）

所有业务/数据模块通过 get_config() 获取统一配置单例。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

from app.core.errors import ConfigError

# 项目根目录（app/ 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# 各分组配置
# ---------------------------------------------------------------------------

@dataclass
class LoggingConfig:
    """日志配置。"""

    level: str = "INFO"
    log_dir: str = str(PROJECT_ROOT / "logs")
    log_file: str = "app.log"
    max_bytes: int = 10 * 1024 * 1024  # 10 MB
    backup_count: int = 5
    color_console: bool = True
    file_enabled: bool = True


@dataclass
class NetworkConfig:
    """网络请求配置。"""

    timeout: float = 15.0
    retries: int = 3
    backoff_base: float = 1.0  # 指数退避基数（秒）
    backoff_factor: float = 2.0
    pool_connections: int = 20
    pool_maxsize: int = 20
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )


@dataclass
class CacheConfig:
    """缓存配置。"""

    enabled: bool = True
    # 缓存根目录（默认 .data_cache）
    cache_dir: str = str(PROJECT_ROOT / ".data_cache")
    # 各数据源默认 TTL
    default_ttl: str = "1d"
    # 内存缓存开关（二级缓存，提升高频访问性能）
    memory_cache: bool = True
    memory_ttl: float = 300.0  # 内存缓存 TTL（秒）


@dataclass
class DataSourceConfig:
    """数据源配置（API 端点、优先级）。"""

    # 数据源优先级（从高到低）
    source_priority: list = field(default_factory=lambda: [
        "tencent", "eastmoney", "sina", "akshare",
    ])
    # 各 API 端点
    tencent_quote_url: str = "http://qt.gtimg.cn/q="
    tencent_kline_url: str = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    eastmoney_fund_nav_url: str = "http://api.fund.eastmoney.com/f10/lsjz"
    eastmoney_fund_list_url: str = "http://fund.eastmoney.com/data/rankhandler.aspx"
    sina_kline_url: str = (
        "https://money.finance.sina.com.cn/quotes_service/api/"
        "json_v2.php/CN_MarketData.getKLineData"
    )
    # 并发
    max_workers: int = 10


@dataclass
class AppConfig:
    """全局应用配置。"""

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    data_source: DataSourceConfig = field(default_factory=DataSourceConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """从环境变量覆盖默认值构造配置。"""
        cfg = cls()

        # 日志
        cfg.logging.level = os.environ.get("APP_LOG_LEVEL", cfg.logging.level).upper()

        # 缓存目录
        cache_env = os.environ.get("APP_DATA_CACHE_DIR")
        if cache_env:
            cfg.cache.cache_dir = cache_env

        # 网络超时/重试
        try:
            cfg.network.timeout = float(os.environ.get("APP_HTTP_TIMEOUT", cfg.network.timeout))
            cfg.network.retries = int(os.environ.get("APP_HTTP_RETRIES", cfg.network.retries))
        except ValueError as e:
            raise ConfigError(f"无效的网络配置: {e}") from e

        return cfg

    @classmethod
    def load(cls, path: str | None = None) -> "AppConfig":
        """从文件加载（可选）并合并环境变量。

        支持 JSON/YAML 文件。若指定文件不存在，仅用环境变量。
        """
        cfg = cls.from_env()
        if path and Path(path).exists():
            try:
                import json

                if path.endswith((".yaml", ".yml")):
                    try:
                        import yaml
                        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
                    except ImportError:
                        raise ConfigError("加载 YAML 配置需要安装 pyyaml")
                else:
                    data = json.loads(Path(path).read_text(encoding="utf-8"))
                cfg._merge_dict(data)
            except (json.JSONDecodeError, OSError) as e:
                raise ConfigError(f"配置文件解析失败: {path}: {e}") from e
        return cfg

    def _merge_dict(self, data: dict) -> None:
        """将 dict 配置合并进当前实例（仅覆盖存在的分组字段）。"""
        if not isinstance(data, dict):
            return
        for group_name, group_cfg in fields(self):
            if group_name not in data:
                continue
            group_data = data[group_name]
            if not isinstance(group_data, dict):
                continue
            current = getattr(self, group_name)
            for f in fields(current):
                if f.name in group_data:
                    setattr(current, f.name, group_data[f.name])


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_config_instance: AppConfig | None = None


def get_config() -> AppConfig:
    """返回全局配置单例（懒加载）。"""
    global _config_instance
    if _config_instance is None:
        _config_instance = AppConfig.from_env()
    return _config_instance


def set_config(config: AppConfig) -> None:
    """注入全局配置（测试/框架层使用）。"""
    global _config_instance
    _config_instance = config
