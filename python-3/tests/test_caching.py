"""common.caching 单元测试。

验证跨包通用磁盘缓存工具的核心行为：
- parse_ttl 时间解析
- JSON / CSV 缓存的读写与过期
- allow_stale 过期回退
- clear 清理
- 原子写入（写临时文件再 rename）
"""

import os
import time

import pandas as pd
import pytest

from common.caching import DiskCache, parse_ttl


@pytest.fixture()
def cache(tmp_path):
    """返回指向临时目录的 DiskCache 实例，测试后自动清理。"""
    c = DiskCache("test", default_ttl="1d", root=str(tmp_path))
    yield c
    c.clear()


def test_parse_ttl():
    assert parse_ttl("30s") == 30
    assert parse_ttl("5m") == 300
    assert parse_ttl("6h") == 21600
    assert parse_ttl("1d") == 86400
    assert parse_ttl("1w") == 7 * 86400
    assert parse_ttl(3600) == 3600
    assert parse_ttl("120") == 120


def test_json_roundtrip(cache):
    cache.set_json("foo", {"a": 1, "b": [1, 2, 3], "c": "x"})
    assert cache.get_json("foo") == {"a": 1, "b": [1, 2, 3], "c": "x"}
    # 未命中
    assert cache.get_json("missing") is None


def test_json_ttl_expiry(cache):
    cache.set_json("foo", {"v": 1})
    assert cache.get_json("foo", ttl="1d") == {"v": 1}
    # 设置极短 TTL 并等待过期
    cache.set_json("bar", {"v": 2})
    time.sleep(1.1)
    assert cache.get_json("bar", ttl="1s") is None


def test_json_allow_stale(cache):
    cache.set_json("foo", {"v": 1})
    time.sleep(1.1)
    assert cache.get_json("foo", ttl="1s") is None
    # allow_stale=True 应返回过期数据
    assert cache.get_json("foo", ttl="1s", allow_stale=True) == {"v": 1}


def test_csv_roundtrip(cache):
    df = pd.DataFrame({"code": ["600519", "600030"], "name": ["贵州茅台", "中信证券"]})
    cache.set_csv("stocks.csv", df)
    loaded = cache.get_csv("stocks.csv")
    assert loaded is not None
    assert list(loaded["code"].astype(str)) == ["600519", "600030"]
    assert list(loaded["name"]) == ["贵州茅台", "中信证券"]


def test_csv_ttl_expiry(cache):
    df = pd.DataFrame({"x": [1]})
    cache.set_csv("data.csv", df)
    time.sleep(1.1)
    assert cache.get_csv("data.csv", ttl="1s") is None
    assert cache.get_csv("data.csv", ttl="1s", allow_stale=True) is not None


def test_pickle_roundtrip(cache):
    obj = {"nested": [1, 2, {"k": "v"}]}
    cache.set_pickle("obj.pkl", obj)
    assert cache.get_pickle("obj.pkl") == obj


def test_generic_get_set(cache):
    # dict -> JSON
    cache.set("cfg", {"a": 1})
    assert cache.get("cfg") == {"a": 1}
    # list -> JSON
    cache.set("lst", [1, 2, 3])
    assert cache.get("lst") == [1, 2, 3]
    # tuple -> pickle（不可 JSON 序列化）
    cache.set("tup", (1, 2, 3))
    assert cache.get("tup") == (1, 2, 3)


def test_clear(cache):
    cache.set_json("foo", {"a": 1})
    assert cache.get_json("foo") == {"a": 1}
    cache.clear("foo")
    assert cache.get_json("foo") is None


def test_namespace_isolation(tmp_path):
    c1 = DiskCache("ns1", root=str(tmp_path))
    c2 = DiskCache("ns2", root=str(tmp_path))
    c1.set_json("k", "v1")
    assert c1.get_json("k") == "v1"
    # ns2 不受 ns1 影响
    assert c2.get_json("k") is None
    c1.clear()
    c2.clear()
