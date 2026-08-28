"""测试腾讯 K 线对 000 前缀（指数/股票市场歧义）的前缀兜底。

修复点：000300（沪深300 指数）被 to_tencent_code 映射为 sz000300，
腾讯 fqkline 接口下 sz000300 无 K 线数据（返回空 day/qfqday），
而 sh000300 才返回完整指数 K 线。此处验证 fetch_kline 会尝试两个市场前缀。
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, ".")

from app.data.sources.tencent import TencentDataSource, _alternate_tencent_code


def _payload(tc_code: str, rows: int = 2) -> dict:
    """构造腾讯 K 线 JSON 响应。"""
    klines = [
        [f"2026-08-{i:02d}", "10.0", "10.1", "10.2", "9.9", "1000.0"]
        for i in range(1, rows + 1)
    ]
    return {"code": 0, "data": {tc_code: {"qfqday": klines}}}


def _empty_payload(tc_code: str) -> dict:
    """构造腾讯 K 线"无数据"响应（sz000300 在腾讯接口下的表现）。"""
    return {"code": 0, "data": {tc_code: {"day": []}}}


class TestAlternateTencentCode:
    def test_sz000_prefix_gets_sh_alternate(self):
        assert _alternate_tencent_code("sz000300") == "sh000300"

    def test_sh000_prefix_gets_sz_alternate(self):
        assert _alternate_tencent_code("sh000001") == "sz000001"

    def test_non_000_prefix_no_alternate(self):
        # 深市股票 000651 存在 sh 前缀的兄弟指数，但 600 开头沪股无歧义
        assert _alternate_tencent_code("sz002415") is None
        assert _alternate_tencent_code("sh600519") is None


class TestFetchKlineIndexPrefix:
    def test_sz_empty_then_sh_success(self):
        """首选 sz000300 返回空，应兜底 sh000300 拿到完整指数 K 线。"""
        src = TencentDataSource()
        mock_client = MagicMock()

        # sz000300 返回空 day，sh000300 返回数据
        def fake_get_json(url, params=None, **kwargs):
            param = params["param"]
            tc = param.split(",")[0]
            if tc == "sz000300":
                return _empty_payload(tc)
            return _payload(tc)

        mock_client.get_json.side_effect = fake_get_json
        with patch("app.data.sources.tencent.get_http_client", return_value=mock_client):
            result = src.fetch_kline("000300", days=120)

        assert result is not None
        assert len(result) == 2
        # 两个前缀都尝试过
        params = [c.kwargs["params"]["param"] for c in mock_client.get_json.call_args_list]
        assert any("sz000300" in p for p in params)
        assert any("sh000300" in p for p in params)

    def test_primary_sh_success_single_call(self):
        """首选前缀直接有数据时，只需一次请求（sh600519）。"""
        src = TencentDataSource()
        mock_client = MagicMock()
        mock_client.get_json.return_value = _payload("sh600519")

        with patch("app.data.sources.tencent.get_http_client", return_value=mock_client):
            result = src.fetch_kline("600519", days=120)

        assert result is not None
        assert len(result) == 2
        assert mock_client.get_json.call_count == 1

    def test_primary_sz_success_single_call(self):
        """深市股票（非 000 前缀）首选即有数据，单次请求（sz002415）。"""
        src = TencentDataSource()
        mock_client = MagicMock()
        mock_client.get_json.return_value = _payload("sz002415")

        with patch("app.data.sources.tencent.get_http_client", return_value=mock_client):
            result = src.fetch_kline("002415", days=120)

        assert result is not None
        assert len(result) == 2
        assert mock_client.get_json.call_count == 1

    def test_deep_000_stock_primary_sz_success(self):
        """000 前缀深市股票（000651 格力）首选 sz 即有数据，不误切 sh。"""
        src = TencentDataSource()
        mock_client = MagicMock()
        mock_client.get_json.return_value = _payload("sz000651")

        with patch("app.data.sources.tencent.get_http_client", return_value=mock_client):
            result = src.fetch_kline("000651", days=120)

        assert result is not None
        assert len(result) == 2
        assert mock_client.get_json.call_count == 1

    def test_both_empty_then_sina_fallback(self):
        """两个前缀都无数据时，回退新浪源。"""
        src = TencentDataSource()
        mock_client = MagicMock()
        mock_client.get_json.side_effect = [
            _empty_payload("sz000300"),
            _empty_payload("sh000300"),
        ]

        # 新浪回退：返回一行数据
        sina_rows = [{
            "date": "2026-08-01",
            "open": 10.0, "high": 10.2, "low": 9.9, "close": 10.1,
            "volume": 1000.0,
        }]
        with patch("app.data.sources.tencent.get_http_client", return_value=mock_client), \
             patch.object(src, "_fetch_kline_sina", return_value=sina_rows):
            result = src.fetch_kline("000300", days=120)

        assert result == sina_rows
