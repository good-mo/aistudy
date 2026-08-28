"""
跨包通用磁盘缓存工具
=====================

为 jijin_core / share300_core / lc_core / stock_monitor / stock 等
各子系统的数据获取层提供统一的磁盘缓存能力。

设计要点：
    - 按数据本身的更新频率分级设置缓存有效期（TTL）。
    - 支持 JSON / CSV / 任意二进制对象（pickle）三种序列化方式。
    - 原子写入（写临时文件再 rename），避免并发/中断导致缓存损坏。
    - 缓存命中/未命中均返回清晰的信号，便于调用方打日志。
    - 目录与文件隔离，避免各子系统互相污染。

使用示例：
    from common.caching import DiskCache

    cache = DiskCache("share300", default_ttl="1d")
    data = cache.get("kline/600519", allow_stale=False)
    if data is None:
        data = fetch_from_api()
        cache.set("kline/600519", data)

    # 也可以直接使用便捷的 load/save（CSV DataFrame）：
    df = cache.load_csv("kline/600519.csv", ttl="1d")
    if df is None:
        df = fetch_kline()
        cache.save_csv("kline/600519.csv", df)
"""

from __future__ import annotations

import json
import os
import pickle
import shutil
import tempfile
import time
from datetime import datetime

# 全局缓存根目录
DEFAULT_CACHE_ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".data_cache"
)
DEFAULT_CACHE_ROOT = os.path.abspath(DEFAULT_CACHE_ROOT)

# 时间单位 -> 秒
_UNITS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 7 * 86400,
}


def parse_ttl(ttl: str | int) -> float:
    """将 TTL 解析为秒数。

    支持格式：数字秒、以及带单位字符串，如 "30s" / "5m" / "6h" / "1d" / "1w"。
    传入纯数字视为秒。
    """
    if isinstance(ttl, (int, float)):
        return float(ttl)
    ttl = str(ttl).strip().lower()
    if not ttl:
        return 0.0
    # 分离数字与单位
    for unit, sec in _UNITS.items():
        if ttl.endswith(unit):
            num = ttl[: -len(unit)].strip()
            if num.isdigit():
                return float(num) * sec
    # 纯数字字符串
    if ttl.isdigit():
        return float(ttl)
    raise ValueError(f"无法解析 TTL: {ttl!r}（支持如 30s / 5m / 6h / 1d / 1w）")


def now_ts() -> float:
    return time.time()


class DiskCache:
    """基于本地文件的通用缓存。

    Args:
        namespace: 缓存命名空间（如 "share300"、"stock_monitor"），
                   用于在根目录下隔离不同子系统的缓存。
        default_ttl: 默认缓存有效期（秒或字符串）。
    """

    def __init__(self, namespace: str, default_ttl: str | int = "1d", root: str | None = None):
        self.namespace = namespace.strip("/")
        self.root = root or DEFAULT_CACHE_ROOT
        self.ns_dir = os.path.join(self.root, self.namespace)
        self.default_ttl = parse_ttl(default_ttl)
        os.makedirs(self.ns_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 路径 / 元数据
    # ------------------------------------------------------------------

    def _abs_path(self, key: str) -> str:
        """返回缓存文件的绝对路径（同时兼容带 .json/.csv 等后缀的 key）。"""
        safe = key.lstrip("/").replace("..", "")
        return os.path.join(self.ns_dir, safe)

    def _meta_path(self, abs_path: str) -> str:
        return abs_path + ".meta.json"

    def _is_fresh(self, abs_path: str, ttl: float | None) -> bool:
        """判断缓存文件是否在有效期内（不存在则视为过期）。"""
        if not os.path.exists(abs_path):
            return False
        meta = self._meta_path(abs_path)
        if os.path.exists(meta):
            try:
                with open(meta, "r", encoding="utf-8") as f:
                    mtime = float(json.load(f).get("ts", 0))
                # 以元数据时间为准
            except (json.JSONDecodeError, OSError, TypeError):
                mtime = os.path.getmtime(abs_path)
        else:
            mtime = os.path.getmtime(abs_path)
        eff_ttl = self.default_ttl if ttl is None else parse_ttl(ttl)
        return (now_ts() - mtime) <= eff_ttl

    # ------------------------------------------------------------------
    # JSON 缓存
    # ------------------------------------------------------------------

    def get_json(self, key: str, ttl: str | int | None = None, allow_stale: bool = False):
        """读取 JSON 缓存。命中且未过期返回对象；过期返回 None。

        allow_stale=True 时，未过期仍正常返回，过期时若存在旧文件也返回
        旧数据（供"API 不可用回退"场景使用）。
        """
        path = self._abs_path(key)
        if not os.path.exists(path):
            return None
        if not self._is_fresh(path, ttl) and not allow_stale:
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
            return None

    def set_json(self, key: str, data) -> None:
        """写入 JSON 缓存（原子）。"""
        path = self._abs_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._atomic_write(path, lambda tmp: json.dump(data, tmp, ensure_ascii=False))
        self._write_meta(path)

    # ------------------------------------------------------------------
    # CSV 缓存（DataFrame）
    # ------------------------------------------------------------------

    def get_csv(self, key: str, ttl: str | int | None = None, allow_stale: bool = False,
                **read_kwargs):
        """读取 CSV 缓存为 DataFrame。命中且未过期返回；否则返回 None。"""
        import pandas as pd

        path = self._abs_path(key)
        if not os.path.exists(path):
            return None
        if not self._is_fresh(path, ttl) and not allow_stale:
            return None
        try:
            return pd.read_csv(path, **read_kwargs)
        except (OSError, pd.errors.EmptyDataError, ValueError):
            return None

    def set_csv(self, key: str, df, **to_csv_kwargs) -> None:
        """写入 CSV 缓存（原子）。"""
        path = self._abs_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        def _do(tmp):
            df.to_csv(tmp, index=False, **to_csv_kwargs)

        self._atomic_write(path, _do)
        self._write_meta(path)

    # ------------------------------------------------------------------
    # 二进制缓存（pickle，任意 Python 对象）
    # ------------------------------------------------------------------

    def get_pickle(self, key: str, ttl: str | int | None = None, allow_stale: bool = False):
        """读取 pickle 缓存。"""
        path = self._abs_path(key)
        if not os.path.exists(path):
            return None
        if not self._is_fresh(path, ttl) and not allow_stale:
            return None
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except (OSError, pickle.PickleError, EOFError, ValueError, UnicodeDecodeError):
            return None

    def set_pickle(self, key: str, obj) -> None:
        """写入 pickle 缓存（原子）。"""
        path = self._abs_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._atomic_write(path, lambda tmp: pickle.dump(obj, tmp), binary=True)
        self._write_meta(path)

    # ------------------------------------------------------------------
    # 便捷封装：带"过期即刷新"的一体化读取
    # ------------------------------------------------------------------

    def get(self, key: str, default=None, ttl: str | int | None = None,
            allow_stale: bool = False):
        """通用 get：先尝试 JSON，再尝试 pickle。"""
        val = self.get_json(key, ttl=ttl, allow_stale=allow_stale)
        if val is not None:
            return val
        val = self.get_pickle(key, ttl=ttl, allow_stale=allow_stale)
        return default if val is None else val

    def set(self, key: str, obj) -> None:
        """通用 set：根据对象类型选择 JSON 或 pickle。"""
        if isinstance(obj, (dict, list, str, int, float, bool)) or obj is None:
            self.set_json(key, obj)
        else:
            self.set_pickle(key, obj)

    def load_csv(self, key: str, ttl: str | int | None = None, allow_stale: bool = False,
                 **read_kwargs):
        return self.get_csv(key, ttl=ttl, allow_stale=allow_stale, **read_kwargs)

    def save_csv(self, key: str, df, **to_csv_kwargs) -> None:
        self.set_csv(key, df, **to_csv_kwargs)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _atomic_write(self, path: str, writer, binary: bool = False) -> None:
        """原子写入：写入临时文件后 rename，避免进程中断留下半成品。

        Args:
            path: 目标文件路径
            writer: 写入回调，接收打开的文件对象
            binary: 是否以二进制模式打开（pickle 等需要）
        """
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            mode = "wb" if binary else "w"
            with os.fdopen(fd, mode, encoding=None if binary else "utf-8") as f:
                writer(f)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def _write_meta(self, path: str) -> None:
        meta = self._meta_path(path)
        try:
            with open(meta, "w", encoding="utf-8") as f:
                json.dump({"ts": now_ts(), "created": datetime.now().isoformat()}, f)
        except OSError:
            pass

    def clear(self, key: str | None = None) -> None:
        """删除缓存。key 为 None 时清空整个命名空间。"""
        if key is None:
            shutil.rmtree(self.ns_dir, ignore_errors=True)
            os.makedirs(self.ns_dir, exist_ok=True)
            return
        path = self._abs_path(key)
        for p in (path, self._meta_path(path)):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


# 便捷的单例访问器（按命名空间懒加载）
_instances: dict[str, DiskCache] = {}


def get_cache(namespace: str, default_ttl: str | int = "1d") -> DiskCache:
    """返回指定命名空间的 DiskCache 单例。"""
    if namespace not in _instances:
        _instances[namespace] = DiskCache(namespace, default_ttl=default_ttl)
    return _instances[namespace]
