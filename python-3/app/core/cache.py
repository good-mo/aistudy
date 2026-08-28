"""
app.core.cache —— 分级缓存管理器

提供两级缓存：
    1. 内存缓存（可选，二级）：提升高频重复访问性能
    2. 磁盘缓存（复用 common.caching.DiskCache）：按 TTL 持久化

设计：
    - 按 namespace 隔离不同模块的缓存
    - 支持 JSON / CSV(DataFrame) / pickle
    - 内存缓存带独立 TTL
    - 原子写入避免损坏

用法：
    from app.core.cache import get_cache_manager

    cache = get_cache_manager()
    data = cache.get_json("fund/nav/110011")
    if data is None:
        data = fetch_from_api()
        cache.set_json("fund/nav/110011", data)
"""

from __future__ import annotations

import time
from typing import Any

from app.core.config import get_config
from app.core.errors import CacheError

try:
    from common.caching import DiskCache
    _HAS_COMMON_CACHE = True
except ImportError:  # pragma: no cover
    _HAS_COMMON_CACHE = False


class _MemoryCache:
    """简单的进程内内存缓存（带 TTL）。"""

    def __init__(self, default_ttl: float = 300.0):
        self._default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        if key not in self._store:
            return None
        ts, val = self._store[key]
        if time.time() - ts > self._default_ttl:
            del self._store[key]
            return None
        return val

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


class CacheManager:
    """统一缓存管理器（内存 + 磁盘两级）。"""

    def __init__(
        self,
        *,
        namespace: str = "app",
        memory_enabled: bool = True,
        memory_ttl: float = 300.0,
    ):
        self._namespace = namespace
        self._memory_enabled = memory_enabled and memory_ttl > 0
        self._memory = _MemoryCache(memory_ttl) if self._memory_enabled else None

        if _HAS_COMMON_CACHE:
            self._disk = DiskCache(namespace)
        else:  # pragma: no cover - 兜底
            self._disk = None

    # ------------------------------------------------------------------
    # 内部：生成带 namespace 的 key
    # ------------------------------------------------------------------

    @staticmethod
    def _full_key(key: str) -> str:
        return f"app/{key}"

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def get_json(
        self,
        key: str,
        ttl: str | int | None = None,
        allow_stale: bool = False,
    ) -> Any:
        """读取 JSON 缓存。

        allow_stale=True 时，缓存过期但文件仍存在也会返回旧数据
        （供"全部数据源失败时回退旧缓存"场景使用）。
        """
        full = self._full_key(key)
        # 内存
        if self._memory and not allow_stale:
            val = self._memory.get(full)
            if val is not None:
                return val
        # 磁盘
        if self._disk:
            try:
                val = self._disk.get_json(key, ttl=ttl, allow_stale=allow_stale)
                if val is not None and self._memory:
                    self._memory.set(full, val)
                return val
            except (OSError, ValueError):
                return None
        return None

    def set_json(self, key: str, data: Any) -> None:
        full = self._full_key(key)
        if self._memory:
            self._memory.set(full, data)
        if self._disk:
            try:
                self._disk.set_json(key, data)
            except (OSError, ValueError) as e:
                raise CacheError(f"JSON 缓存写入失败: {key}") from e

    # ------------------------------------------------------------------
    # CSV (DataFrame)
    # ------------------------------------------------------------------

    def get_csv(self, key: str, ttl: str | int | None = None, allow_stale: bool = False, **kwargs):
        if self._disk:
            try:
                return self._disk.get_csv(key, ttl=ttl, allow_stale=allow_stale, **kwargs)
            except (OSError, ValueError):
                return None
        return None

    def set_csv(self, key: str, df, **kwargs) -> None:
        if self._disk:
            try:
                self._disk.set_csv(key, df, **kwargs)
            except (OSError, ValueError) as e:
                raise CacheError(f"CSV 缓存写入失败: {key}") from e

    # ------------------------------------------------------------------
    # pickle（任意对象）
    # ------------------------------------------------------------------

    def get_pickle(self, key: str, ttl: str | int | None = None, allow_stale: bool = False):
        if self._disk:
            try:
                return self._disk.get_pickle(key, ttl=ttl, allow_stale=allow_stale)
            except (OSError, ValueError):
                return None
        return None

    def set_pickle(self, key: str, obj) -> None:
        if self._disk:
            try:
                self._disk.set_pickle(key, obj)
            except (OSError, ValueError) as e:
                raise CacheError(f"pickle 缓存写入失败: {key}") from e

    # ------------------------------------------------------------------
    # 通用 get/set（自动选择序列化方式）
    # ------------------------------------------------------------------

    def get(self, key: str, ttl: str | int | None = None, allow_stale: bool = False):
        if self._disk:
            try:
                return self._disk.get(key, ttl=ttl, allow_stale=allow_stale)
            except (OSError, ValueError):
                return None
        return None

    def set(self, key: str, obj) -> None:
        if self._disk:
            try:
                self._disk.set(key, obj)
            except (OSError, ValueError) as e:
                raise CacheError(f"缓存写入失败: {key}") from e

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def clear(self, key: str | None = None) -> None:
        if self._memory:
            self._memory.clear()
        if self._disk:
            self._disk.clear(key)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_cache_instance: CacheManager | None = None


def get_cache_manager() -> CacheManager:
    """返回全局缓存管理器单例。"""
    global _cache_instance
    if _cache_instance is None:
        cfg = get_config()
        _cache_instance = CacheManager(
            namespace="app",
            memory_enabled=cfg.cache.memory_cache,
            memory_ttl=cfg.cache.memory_ttl,
        )
    return _cache_instance
