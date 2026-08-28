"""
app 架构修复回归测试。

覆盖：
    - CacheManager.get_json 支持 allow_stale 回退旧缓存（不抛 TypeError）
    - HTTPClient 对可重试状态码（500/429 等）进行重试，永久错误（404）不重试
    - Sina 数据源股票代码前缀（深市 sz / 沪市 sh）正确
    - HS300 SAMPLE_CODES 无重复
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# CacheManager allow_stale
# ---------------------------------------------------------------------------

class TestCacheManagerAllowStale:
    def test_get_json_accepts_allow_stale(self):
        """get_json 应支持 allow_stale 参数（回退旧缓存），不抛 TypeError。"""
        from app.core.cache import CacheManager

        cm = CacheManager(namespace="test_fix", memory_enabled=False)
        cm.clear()
        # 未命中时 allow_stale=True 不应抛异常
        assert cm.get_json("k1", ttl="1d", allow_stale=True) is None
        cm.clear()

    def test_get_json_stale_fallback(self):
        """写入后 allow_stale=True 应能读到旧数据。"""
        from app.core.cache import CacheManager
        import time

        cm = CacheManager(namespace="test_fix2", memory_enabled=False)
        cm.clear()
        cm.set_json("k2", {"v": 1})
        # 用 ttl=1s 且 allow_stale=True 应返回数据（不抛异常）
        val = cm.get_json("k2", ttl="1s", allow_stale=True)
        assert val == {"v": 1}
        cm.clear()


# ---------------------------------------------------------------------------
# HTTPClient 重试
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, code):
        self.status_code = code

    def json(self):
        return {}

    @property
    def text(self):
        return ""


class TestHTTPClientRetry:
    def test_retryable_status_retried(self):
        """可重试状态码（500）应重试多次而非立即失败。"""
        from app.core.network import HTTPClient

        client = HTTPClient(retries=3, backoff_base=0.001, backoff_factor=1.0)
        calls = []

        def fake_get(*a, **k):
            calls.append(1)
            return _FakeResp(500)

        client._session.get = fake_get
        with pytest.raises(Exception):
            client.get("http://example.com")
        assert len(calls) == 3

    def test_permanent_status_not_retried(self):
        """永久错误（404）应立即失败，不重试。"""
        from app.core.network import HTTPClient

        client = HTTPClient(retries=3, backoff_base=0.001, backoff_factor=1.0)
        calls = []

        def fake_get(*a, **k):
            calls.append(1)
            return _FakeResp(404)

        client._session.get = fake_get
        with pytest.raises(Exception):
            client.get("http://example.com")
        assert len(calls) == 1

    def test_recover_after_retry(self):
        """重试后成功应返回正常响应。"""
        from app.core.network import HTTPClient

        client = HTTPClient(retries=3, backoff_base=0.001, backoff_factor=1.0)
        seq = [500, 200]

        def fake_get(*a, **k):
            return _FakeResp(seq.pop(0))

        client._session.get = fake_get
        resp = client.get("http://example.com")
        assert resp.status_code == 200

    def test_remote_disconnected_detected(self):
        """RemoteDisconnected 应从异常链中被正确识别。"""
        from http.client import RemoteDisconnected
        from urllib3.exceptions import ProtocolError
        from app.core.network import _is_remote_disconnected
        from requests.exceptions import ConnectionError as ReqConnErr

        # 模拟 requests 对 RemoteDisconnected 的包装链
        rd = RemoteDisconnected("Remote end closed connection without response")
        pe = ProtocolError("Connection aborted.", rd)
        ce = ReqConnErr(pe)
        assert _is_remote_disconnected(ce) is True

        # 普通连接错误不应被识别为 RemoteDisconnected
        assert _is_remote_disconnected(ReqConnErr("generic error")) is False

    def test_remote_disconnected_clears_connection_pool(self):
        """RemoteDisconnected 时应清理连接池再重试。"""
        from http.client import RemoteDisconnected
        from urllib3.exceptions import ProtocolError
        from requests.exceptions import ConnectionError as ReqConnErr
        from app.core.network import HTTPClient

        client = HTTPClient(retries=2, backoff_base=0.001, backoff_factor=1.0)
        calls = []
        pool_cleared = []

        # 记录连接池清理调用
        import app.core.network as network_mod
        original_clear = network_mod._close_stale_connections

        def fake_get(*a, **k):
            calls.append(1)
            rd = RemoteDisconnected("Remote end closed connection without response")
            pe = ProtocolError("Connection aborted.", rd)
            raise ReqConnErr(pe)

        def fake_clear(session):
            pool_cleared.append(1)
            original_clear(session)

        client._session.get = fake_get
        with pytest.raises(Exception) as exc_info:
            with pytest.MonkeyPatch().context() as mp:
                mp.setattr(network_mod, "_close_stale_connections", fake_clear)
                client.get("http://example.com")

        # 每个失败请求都应触发连接池清理
        assert len(calls) == 2
        assert len(pool_cleared) == 2
        assert "已重试 2 次" in str(exc_info.value)

    def test_normal_connection_error_no_pool_clear(self):
        """普通连接错误（非 RemoteDisconnected）不应触发连接池清理。"""
        from requests.exceptions import ConnectionError as ReqConnErr
        from app.core.network import HTTPClient

        client = HTTPClient(retries=2, backoff_base=0.001, backoff_factor=1.0)
        calls = []

        def fake_get(*a, **k):
            calls.append(1)
            raise ReqConnErr("Connection refused")

        client._session.get = fake_get
        with pytest.raises(Exception):
            client.get("http://example.com")
        assert len(calls) == 2  # 仍然重试


# ---------------------------------------------------------------------------
# Sina 股票代码前缀
# ---------------------------------------------------------------------------

class TestSinaSymbol:
    def test_stock_prefix(self):
        from app.data.sources.sina import to_sina_stock_symbol

        # 深市
        assert to_sina_stock_symbol("000725") == "sz000725"
        assert to_sina_stock_symbol("002050") == "sz002050"
        assert to_sina_stock_symbol("300750") == "sz300750"
        # 沪市
        assert to_sina_stock_symbol("600519") == "sh600519"
        assert to_sina_stock_symbol("601318") == "sh601318"
        assert to_sina_stock_symbol("688981") == "sh688981"

    def test_index_prefix_unchanged(self):
        from app.data.sources.sina import to_sina_symbol

        assert to_sina_symbol("000300") == "sh000300"
        assert to_sina_symbol("399001") == "sz399001"


# ---------------------------------------------------------------------------
# HS300 SAMPLE_CODES 去重
# ---------------------------------------------------------------------------

class TestSampleCodes:
    def test_no_duplicates(self):
        from app.domains.hs300.analyzer import HS300Analyzer

        codes = HS300Analyzer.SAMPLE_CODES
        assert len(codes) == len(set(codes))

    def test_hs300_codes_no_duplicates(self):
        """内置 HS300_CODES 不应有重复代码。"""
        from app.domains.hs300.data import HS300_CODES

        codes = [c for c, _ in HS300_CODES]
        assert len(codes) == len(set(codes))
        assert len(codes) >= 50  # 兜底列表数量应足够


# ---------------------------------------------------------------------------
# HS300 成分股 API 失败降级（stale 缓存 / 内置列表）
# ---------------------------------------------------------------------------

class TestHs300Fallback:
    def _make_stocks(self, n):
        """构造 n 只股票 [(code, name), ...]。"""
        return [(f"{600000+i:06d}", f"股票{i}") for i in range(n)]

    def test_api_fail_fallback_to_builtin(self):
        """API 失败返回空时，get_hs300_stocks 应回退内置列表。"""
        from unittest.mock import MagicMock, patch
        from app.domains.hs300 import data as hs300_data

        mock_client = MagicMock()
        mock_client.get_json.side_effect = Exception("Connection aborted")
        mock_cache = MagicMock()
        mock_cache.get_json.side_effect = [None, None]  # 新鲜缓存无，stale 缓存也无

        with patch.object(hs300_data, "get_http_client", return_value=mock_client), \
             patch.object(hs300_data, "get_cache_manager", return_value=mock_cache):
            result = hs300_data.get_hs300_stocks()

        assert result == hs300_data.HS300_CODES
        # 新鲜缓存 + stale 缓存均被查询
        assert mock_cache.get_json.call_count == 2

    def test_api_fail_fallback_to_stale_cache(self):
        """API 失败且有过期缓存时，应回退过期缓存而非内置列表。"""
        from unittest.mock import MagicMock, patch
        from app.domains.hs300 import data as hs300_data

        stale_stocks = self._make_stocks(300)
        mock_client = MagicMock()
        mock_client.get_json.side_effect = Exception("Connection aborted")
        mock_cache = MagicMock()
        mock_cache.get_json.side_effect = [None, [list(x) for x in stale_stocks]]

        with patch.object(hs300_data, "get_http_client", return_value=mock_client), \
             patch.object(hs300_data, "get_cache_manager", return_value=mock_cache):
            result = hs300_data.get_hs300_stocks()

        assert len(result) == 300
        assert result[0][0] == stale_stocks[0][0]

    def test_api_success_returns_stocks(self):
        """API 正常返回时，应返回成分股并写缓存。"""
        from unittest.mock import MagicMock, patch
        from app.domains.hs300 import data as hs300_data

        stocks = self._make_stocks(300)
        api_data = {"data": {"diff": [{"f12": c, "f14": n} for c, n in stocks]}}

        mock_client = MagicMock()
        mock_client.get_json.return_value = api_data
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None

        with patch.object(hs300_data, "get_http_client", return_value=mock_client), \
             patch.object(hs300_data, "get_cache_manager", return_value=mock_cache):
            result = hs300_data.get_hs300_stocks()

        assert len(result) >= 280
        assert mock_cache.set_json.called

    def test_api_primary_fail_fallback_to_secondary_endpoint(self):
        """push2delay 失败时，应回退到 push2 备选端点拉取。"""
        from unittest.mock import MagicMock, patch
        from app.domains.hs300 import data as hs300_data

        stocks = self._make_stocks(300)
        api_data = {"data": {"diff": [{"f12": c, "f14": n} for c, n in stocks]}}

        # 记录每个请求的 URL 和 retries 参数
        requested = []

        def fake_get_json(url, **kwargs):
            requested.append((url, kwargs.get("retries")))
            if "push2delay.eastmoney.com" in url:
                # push2delay 全部抛错
                raise Exception("Connection aborted")
            # push2 备选端点正常返回
            return api_data

        mock_client = MagicMock()
        mock_client.get_json.side_effect = fake_get_json
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None

        with patch.object(hs300_data, "get_http_client", return_value=mock_client), \
             patch.object(hs300_data, "get_cache_manager", return_value=mock_cache):
            result = hs300_data.get_hs300_stocks()

        assert len(result) >= 280
        # 确实请求过两个端点
        assert any("push2delay.eastmoney.com" in u for u, _ in requested)
        assert any("push2.eastmoney.com" in u for u, _ in requested)
        # 缓存写入成功
        assert mock_cache.set_json.called

    def test_primary_endpoint_preferred(self):
        """push2delay（稳定端点）应优先于 push2（实时端点）。"""
        from unittest.mock import MagicMock, patch
        from app.domains.hs300 import data as hs300_data

        stocks = self._make_stocks(300)
        api_data = {"data": {"diff": [{"f12": c, "f14": n} for c, n in stocks]}}

        requested_urls = []

        def fake_get_json(url, **kwargs):
            requested_urls.append(url)
            return api_data

        mock_client = MagicMock()
        mock_client.get_json.side_effect = fake_get_json
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None

        with patch.object(hs300_data, "get_http_client", return_value=mock_client), \
             patch.object(hs300_data, "get_cache_manager", return_value=mock_cache):
            result = hs300_data.get_hs300_stocks()

        assert len(result) >= 280
        # push2delay 应首先被请求
        assert "push2delay.eastmoney.com" in requested_urls[0]

    def test_push2_reduced_retries(self):
        """push2（已知不稳定端点）应使用更低的重试次数。"""
        from unittest.mock import MagicMock, patch
        from app.domains.hs300 import data as hs300_data

        stocks = self._make_stocks(300)
        api_data = {"data": {"diff": [{"f12": c, "f14": n} for c, n in stocks]}}

        # 记录 push2delay 请求的 retries 参数
        delay_retries = []
        push2_retries = []

        def fake_get_json(url, **kwargs):
            retries = kwargs.get("retries", 3)
            if "push2delay.eastmoney.com" in url:
                delay_retries.append(retries)
                raise Exception("Connection aborted")
            if "push2.eastmoney.com" in url:
                push2_retries.append(retries)
                return api_data
            raise Exception("unknown url")

        mock_client = MagicMock()
        mock_client.get_json.side_effect = fake_get_json
        mock_cache = MagicMock()
        mock_cache.get_json.return_value = None

        with patch.object(hs300_data, "get_http_client", return_value=mock_client), \
             patch.object(hs300_data, "get_cache_manager", return_value=mock_cache):
            result = hs300_data.get_hs300_stocks()

        assert len(result) >= 280
        # push2delay 使用默认 3 次重试
        assert all(r == 3 for r in delay_retries)
        # push2 使用降低的重试（1 次）
        assert all(r == 1 for r in push2_retries)
