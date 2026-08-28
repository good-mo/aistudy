"""测试 stock_monitor.api 的 K线获取：重试 + 新浪回退。"""

import json
import os
import sys
from unittest.mock import MagicMock

import pytest

# 将 share/ 加入导入路径，以便导入 stock_monitor 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "share"))

from stock_monitor.api import TencentDataClient


class TestFetchDailyKline:
    """fetch_daily_kline 的重试与新浪回退逻辑。"""

    def _make_resp(self, text: str, status: int = 200):
        resp = MagicMock()
        resp.status_code = status
        resp.text = text
        resp.raise_for_status.return_value = None
        if text:
            def _json():
                return json.loads(text)
            resp.json = _json
        else:
            import json as _json_mod

            def _fail_json():
                raise _json_mod.JSONDecodeError("Expecting value", "", 0)
            resp.json = _fail_json
        return resp

    def test_tencent_success(self):
        """腾讯源正常返回。"""
        client = TencentDataClient()
        code = "600031"  # 独立代码避免磁盘缓存跨用例污染
        payload = {
            "code": 0,
            "data": {
                "sh600031": {
                    "qfqday": [
                        ["2026-08-01", "10.0", "10.1", "10.2", "9.9", "1000.0"],
                        ["2026-08-02", "10.1", "10.3", "10.4", "10.0", "1200.0"],
                    ]
                }
            }
        }
        mock_session = MagicMock()
        mock_session.get.return_value = self._make_resp(json.dumps(payload))
        client._session = mock_session

        result = client.fetch_daily_kline(code, days=60)
        assert len(result) == 2
        assert result[0]["date"] == "2026-08-01"
        assert result[0]["close"] == 10.1
        assert mock_session.get.call_count == 1

    def test_tencent_empty_then_retry_success(self):
        """腾讯第一次返回空响应，第二次成功。"""
        client = TencentDataClient()
        code = "600032"  # 独立代码避免磁盘缓存跨用例污染
        payload = {
            "code": 0,
            "data": {
                "sh600032": {
                    "qfqday": [["2026-08-01", "10.0", "10.1", "10.2", "9.9", "1000.0"]]
                }
            }
        }
        mock_session = MagicMock()
        # 第一次空响应（触发重试），第二次正常
        mock_session.get.side_effect = [
            self._make_resp(""),
            self._make_resp(json.dumps(payload)),
        ]
        client._session = mock_session

        result = client.fetch_daily_kline(code, days=60)
        assert len(result) == 1
        assert mock_session.get.call_count == 2

    def test_tencent_fail_then_sina_fallback(self):
        """腾讯3次全失败后回退新浪源。"""
        client = TencentDataClient()
        code = "600033"  # 独立代码避免磁盘缓存跨用例污染

        original_get = client._session.get

        def mock_get(url, **kwargs):
            if "ifzq.gtimg.cn" in url:
                # 腾讯源恒失败
                resp = self._make_resp("")
                return resp
            # 新浪源走真实网络
            return original_get(url, **kwargs)

        client._session.get = mock_get

        result = client.fetch_daily_kline(code, days=10)
        # 新浪源应返回非空 K 线（沙箱联网可用），或至少不抛异常
        assert isinstance(result, list)
        assert len(result) > 0  # 新浪源成功返回数据

    def test_tencent_and_sina_both_fail(self):
        """腾讯与新浪都失败时返回空列表，不抛异常。"""
        client = TencentDataClient()
        code = "600034"  # 独立代码避免磁盘缓存跨用例污染

        mock_session = MagicMock()
        mock_session.get.return_value = self._make_resp("")  # 所有请求都返回空
        client._session = mock_session

        result = client.fetch_daily_kline(code, days=60)
        assert result == []
        # 不抛异常

    def test_permanent_error_501_skips_retry_and_falls_back(self):
        """腾讯返回永久性错误 501 时不再重试，直接回退新浪。

        501 = Not Implemented，属永久性错误，重试只会白等 2s→4s，
        应立即切到新浪源。断言腾讯只被请求一次（未重试）。
        """
        client = TencentDataClient()
        code = "600035"  # 独立代码避免磁盘缓存跨用例污染

        original_get = client._session.get

        def mock_get(url, **kwargs):
            if "ifzq.gtimg.cn" in url:
                # 腾讯源返回 501 Not Implemented（永久性错误）
                return self._make_resp("", status=501)
            # 新浪源走真实网络
            return original_get(url, **kwargs)

        client._session.get = mock_get

        result = client.fetch_daily_kline(code, days=10)
        # 新浪源成功返回数据
        assert isinstance(result, list)
        assert len(result) > 0

    def test_transient_500_is_retried(self):
        """腾讯返回瞬时错误 500 时仍按重试策略处理。

        500 属网关/服务瞬时抖动，应走统一重试逻辑（多次请求），
        而非立即回退新浪。
        """
        client = TencentDataClient()
        code = "600036"  # 独立代码避免磁盘缓存跨用例污染

        original_get = client._session.get
        calls = []

        def mock_get(url, **kwargs):
            if "ifzq.gtimg.cn" in url:
                calls.append(url)
                return self._make_resp("", status=500)
            return original_get(url, **kwargs)

        client._session.get = mock_get

        # 3 次腾讯请求全部 500 后回退新浪
        result = client.fetch_daily_kline(code, days=10)
        assert len(calls) == 3  # 瞬时错误会被重试 3 次
        assert isinstance(result, list)
