"""
缓存工具
统一 CSV / JSON 文件缓存的读写与时效判断，替代各脚本中重复的缓存逻辑。
"""

import json
import os
from datetime import datetime, timedelta

from ..config.settings import CACHE_DIR, ensure_cache_dirs
from common.logging_utils import get_logger

logger = get_logger(__name__)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def is_same_trading_day(date_str: str) -> bool:
    """判断给定日期字符串是否为今天（视为同一交易日）。"""
    if not date_str:
        return False
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date() == datetime.now().date()
    except ValueError:
        return False


def json_cache_path(cache_file: str) -> str:
    """返回 JSON 缓存文件的绝对路径。"""
    if not os.path.isabs(cache_file):
        cache_file = os.path.join(CACHE_DIR, cache_file)
    return cache_file


def load_json_cache(cache_file: str, max_days: int) -> dict | None:
    """读取 JSON 缓存，若不存在或超期返回 None。"""
    ensure_cache_dirs()
    path = json_cache_path(cache_file)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.warning("JSON 缓存解析失败: %s", path)
        return None
    # 记录时间
    saved = data.get("_saved")
    if saved and isinstance(max_days, int):
        try:
            saved_dt = datetime.strptime(saved, "%Y-%m-%d")
            if datetime.now() - saved_dt > timedelta(days=max_days):
                logger.debug("JSON 缓存已过期: %s", path)
                return None
        except ValueError:
            pass
    return data


def save_json_cache(cache_file: str, data: dict) -> None:
    """写入 JSON 缓存并记录保存时间。"""
    ensure_cache_dirs()
    path = json_cache_path(cache_file)
    payload = dict(data)
    payload["_saved"] = _today()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def load_csv_frame(csv_path: str, max_days: int = 1) -> "pd.DataFrame | None":
    """读取 CSV 缓存为 DataFrame（避免顶部循环导入，延迟导入 pandas）。"""
    import pandas as pd

    if not os.path.exists(csv_path):
        return None
    try:
        saved = datetime.fromtimestamp(os.path.getmtime(csv_path))
        if datetime.now() - saved > timedelta(days=max_days):
            return None
        return pd.read_csv(csv_path)
    except (OSError, pd.errors.EmptyDataError):
        return None


def get_cache_dir(sub: str = "") -> str:
    """返回缓存子目录绝对路径。"""
    ensure_cache_dirs()
    d = os.path.join(CACHE_DIR, sub)
    os.makedirs(d, exist_ok=True)
    return d
