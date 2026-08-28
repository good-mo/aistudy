"""测试 share300.hs300_analyzer.TencentDataFetcher 的 K线获取：腾讯失败回退新浪。

修复点：此前 hs300_analyzer 的 fetch_kline 只用腾讯源，腾讯临时故障/限流时
（如并发拉取返回 501/断连）这些股票会拿不到K线、整只被跳过分析。
现增加新浪回退源，保证可用性。
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd

# 将仓库根目录加入导入路径，以便导入 share300 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from share300.hs300_analyzer import TencentDataFetcher


def _make_resp(text: str, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.raise_for_status.return_value = None
    if text:
        def _json():
            return json.loads(text)
        resp.json = _json
    else:
        def _fail_json():
            raise json.JSONDecodeError("Expecting value", "", 0)
        resp.json = _fail_json
    return resp


TENCENT_PAYLOAD = {
    "code": 0,
    "data": {
        "sz000977": {
            "qfqday": [
                ["2026-08-24", "61.0", "58.0", "62.0", "57.0", "500000.0"],
                ["2026-08-25", "58.5", "59.0", "60.0", "57.5", "480000.0"],
            ]
        }
    },
}

SINA_PAYLOAD = [
    {"day": "2026-08-24", "open": "61.0", "high": "62.0", "low": "57.0", "close": "58.0", "volume": "500000"},
    {"day": "2026-08-25", "open": "58.5", "high": "60.0", "low": "57.5", "close": "59.0", "volume": "480000"},
]


class TestHs300FetchKlineFallback:
    def test_tencent_success(self):
        """腾讯源正常返回，直接使用腾讯数据。"""
        mock_session = MagicMock()
        mock_session.get.return_value = _make_resp(json.dumps(TENCENT_PAYLOAD))
        with patch("share300.hs300_analyzer._session", mock_session):
            df = TencentDataFetcher.fetch_kline("000977", days=120, force_refresh=True)
        assert df is not None
        assert len(df) == 2
        assert list(df.columns) == ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
        assert mock_session.get.call_count == 1

    def test_tencent_fail_then_sina_fallback(self):
        """腾讯源失败时回退新浪源。"""
        def fake_get(url, **kwargs):
            if "fqkline" in url:
                raise RuntimeError("simulated tencent failure")
            return _make_resp(json.dumps(SINA_PAYLOAD))
        mock_session = MagicMock()
        mock_session.get.side_effect = fake_get
        with patch("share300.hs300_analyzer._session", mock_session):
            df = TencentDataFetcher.fetch_kline("000977", days=120, force_refresh=True)
        assert df is not None
        assert len(df) == 2
        # 新浪回退数据列名与腾讯保持一致
        assert list(df.columns) == ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
        assert df.iloc[0]["收盘"] == 58.0

    def test_sina_fallback_writes_cache(self):
        """新浪回退成功后应写入缓存，后续可命中。"""
        def fake_get(url, **kwargs):
            if "fqkline" in url:
                raise RuntimeError("simulated tencent failure")
            return _make_resp(json.dumps(SINA_PAYLOAD))
        mock_session = MagicMock()
        mock_session.get.side_effect = fake_get

        cache_key = "000977_120.csv"
        try:
            with patch("share300.hs300_analyzer._session", mock_session):
                df = TencentDataFetcher.fetch_kline("000977", days=120, force_refresh=True)
            assert df is not None
            # 缓存文件已写入
            from share300.hs300_analyzer import _kline_cache
            cached = _kline_cache.get_csv(cache_key, allow_stale=True)
            assert cached is not None and not cached.empty
        finally:
            # 清理测试缓存，避免污染
            from share300.hs300_analyzer import _kline_cache
            import os as _os
            p = _kline_cache._abs_path(cache_key)
            for pth in (p, p + ".meta.json"):
                if _os.path.exists(pth):
                    _os.remove(pth)

    def test_both_fail_returns_none(self):
        """腾讯与新浪都失败时返回 None。"""
        def fake_get(url, **kwargs):
            raise RuntimeError("all sources down")
        mock_session = MagicMock()
        mock_session.get.side_effect = fake_get
        with patch("share300.hs300_analyzer._session", mock_session):
            df = TencentDataFetcher.fetch_kline("000977", days=120, force_refresh=True)
        assert df is None
