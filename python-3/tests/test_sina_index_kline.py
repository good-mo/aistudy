"""测试 sina 数据源 get_index_kline 的响应解析。

修复点：新浪 CN_MarketData.getKLineData 返回的是「dict 列表」
（每行为 {day, open, high, low, close, volume}），而非「list 列表」。
此前用 row[0]/row[1] 取数会抛 KeyError，导致新浪拉取指数日K线恒失败、
基准指数回退（东财+新浪）均拿不到数据。
"""

import json
from unittest.mock import MagicMock, patch

from jijin_core.data.sources.sina import get_index_kline


def _make_resp(payload) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.text = json.dumps(payload)
    return resp


def _make_session(payload) -> MagicMock:
    session = MagicMock()
    session.get.return_value = _make_resp(payload)
    return session


SINA_DICT_ROWS = [
    {
        "day": "2026-08-19",
        "open": "7795.259",
        "high": "7821.177",
        "low": "7490.212",
        "close": "7517.768",
        "volume": "26519509400",
    },
    {
        "day": "2026-08-20",
        "open": "7602.498",
        "high": "7656.613",
        "low": "7541.475",
        "close": "7589.779",
        "volume": "24104799000",
    },
]


def test_parse_dict_rows():
    """新浪返回 dict 列表时应正确解析（回归修复前 KeyError）。"""
    session = _make_session(SINA_DICT_ROWS)
    with patch("jijin_core.data.sources.sina.get_session", return_value=session):
        rows = get_index_kline("sh000852", days=5)

    assert len(rows) == 2
    assert rows[0]["day"] == "2026-08-19"
    assert rows[0]["close"] == 7517.768
    assert rows[0]["open"] == 7795.259
    assert rows[0]["volume"] == 26519509400.0
    assert rows[1]["close"] == 7589.779


def test_parse_list_rows_backward_compat():
    """兼容历史 list 格式 [day, open, high, low, close, volume]。"""
    list_rows = [
        ["2026-08-19", "7795.259", "7821.177", "7490.212", "7517.768", "26519509400"],
        ["2026-08-20", "7602.498", "7656.613", "7541.475", "7589.779", "24104799000"],
    ]
    session = _make_session(list_rows)
    with patch("jijin_core.data.sources.sina.get_session", return_value=session):
        rows = get_index_kline("sh000852", days=5)

    assert len(rows) == 2
    assert rows[0]["close"] == 7517.768


def test_missing_volume_defaults_to_zero():
    """volume 键缺失或为空时应默认 0，不抛异常。"""
    row = {
        "day": "2026-08-19",
        "open": "7795.259",
        "high": "7821.177",
        "low": "7490.212",
        "close": "7517.768",
    }
    session = _make_session([row])
    with patch("jijin_core.data.sources.sina.get_session", return_value=session):
        rows = get_index_kline("sh000852", days=5)

    assert rows[0]["volume"] == 0.0


def test_non_list_response_returns_empty():
    """响应不是 list 时返回空列表（不抛异常）。"""
    session = _make_session({"error": "bad request"})
    with patch("jijin_core.data.sources.sina.get_session", return_value=session):
        rows = get_index_kline("sh000852", days=5)

    assert rows == []
