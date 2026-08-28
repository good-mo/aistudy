"""腾讯财经数据客户端：实时行情与历史日K线获取。"""

import json
import re
import time
from typing import Dict, List, Optional

import pandas as pd
import requests

from stock_monitor import constants
from stock_monitor.constants import to_tencent_code
from common.logging_utils import get_logger

# 通用磁盘缓存（历史日K线按日更新，TTL 1 天）
try:
    from common.caching import DiskCache

    _kline_cache = DiskCache("stock_monitor/kline", default_ttl="1d")
except ImportError:
    # 未部署 common 包时降级为空实现
    class _NoCache:
        def get_csv(self, *a, **k):
            return None

        def set_csv(self, *a, **k):
            return None

    _kline_cache = _NoCache()

logger = get_logger(__name__)


class TencentDataClient:
    """封装腾讯财经行情 / K线 API 的客户端。"""

    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()
        self._session.headers.update(constants.HTTP_HEADERS)

    # ------------------------------------------------------------------
    # 实时行情
    # ------------------------------------------------------------------

    def get_realtime(self, watch_list: Dict[str, str]) -> Optional[pd.DataFrame]:
        """获取实时行情数据（腾讯财经 API，带重试）。

        Args:
            watch_list: 监控列表 {代码: 名称}

        Returns:
            DataFrame，失败时返回 None。
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                codes = list(watch_list.keys())
                tc_codes = [to_tencent_code(c) for c in codes]
                url = constants.TENCENT_API + ",".join(tc_codes)

                resp = self._session.get(url, timeout=constants.REQUEST_TIMEOUT)
                resp.encoding = "gbk"
                raw_text = resp.text

                # 腾讯财经一次返回所有代码的数据，用换行分隔
                lines = raw_text.strip().split("\n")
                results = []

                for i, code in enumerate(codes):
                    if i < len(lines):
                        row = self._parse_tencent_data(
                            lines[i], code, watch_list[code]
                        )
                        if row:
                            results.append(row)

                if results:
                    return pd.DataFrame(results)
                return None

            except Exception as e:  # noqa: BLE001 - 网络异常统一重试
                delay = 2 ** (attempt + 1)
                if attempt < max_retries - 1:
                    logger.warning("获取行情数据失败（第 %d/%d 次）: %s，%.1fs 后重试", attempt + 1, max_retries, e, delay)
                    print(
                        f"获取行情数据失败 (第{attempt + 1}/{max_retries}次): "
                        f"{e}，{delay}秒后重试..."
                    )
                    time.sleep(delay)
                else:
                    logger.error("获取行情数据失败（已达最大重试次数 %d）: %s", max_retries, e)
                    print(f"获取行情数据失败 (已达最大重试次数{max_retries}): {e}")

        return None

    @staticmethod
    def _parse_tencent_data(raw: str, code: str, name: str) -> Optional[dict]:
        """解析腾讯财经返回的行情数据。

        腾讯财经返回格式（以 ~ 分隔的字符串）：
        0:未知, 1:名称, 2:代码, 3:最新价, 4:昨收, 5:今开, 6:成交量(手),
        31:涨跌额, 32:涨跌幅, 33:最高, 34:最低, 37:成交额(万), ...
        """
        try:
            match = re.search(r'"([^"]*)"', raw)
            if not match:
                return None
            data = match.group(1)
            fields = data.split("~")

            if len(fields) < 38:
                return None

            return {
                "代码": code,
                "名称": fields[1] if fields[1] else name,
                "最新价": float(fields[3]) if fields[3] else 0,
                "昨收": float(fields[4]) if fields[4] else 0,
                "今开": float(fields[5]) if fields[5] else 0,
                "成交量": float(fields[6]) if fields[6] else 0,  # 手
                "涨跌额": float(fields[31]) if fields[31] else 0,
                "涨跌幅": float(fields[32]) if fields[32] else 0,
                "最高": float(fields[33]) if fields[33] else 0,
                "最低": float(fields[34]) if fields[34] else 0,
                "成交额": float(fields[37]) if fields[37] else 0,  # 万元
            }
        except (ValueError, IndexError) as e:
            logger.warning("解析行情数据失败 [%s]: %s", code, e)
            print(f"解析数据失败 [{code}]: {e}")
            return None

    # ------------------------------------------------------------------
    # 历史日K线
    # ------------------------------------------------------------------

    def fetch_daily_kline(self, code: str, days: int = 60,
                          force_refresh: bool = False) -> List[dict]:
        """获取历史日K线数据（腾讯财经API，前复权），带重试、新浪回退与磁盘缓存。

        日K线按交易日更新，因此使用 1 天 TTL 缓存，避免每次启动盯盘都
        重复请求腾讯接口。腾讯源失败时自动重试，最终回退新浪源。

        Args:
            code: 通用股票代码
            days: 获取的K线根数
            force_refresh: 强制刷新缓存

        Returns:
            [{date, open, close, high, low, volume}, ...]
            注意：指数（如沪深300）可能不返回日K线，返回空列表。
        """
        cache_key = f"{code}_{days}.csv"
        # 1. 读缓存（未过期）
        if not force_refresh:
            cached = _kline_cache.get_csv(cache_key, ttl="1d")
            if cached is not None and not cached.empty:
                rows = cached.to_dict("records")
                # 确保列名与下游一致
                if rows and "date" in rows[0]:
                    return rows

        tc_code = to_tencent_code(code)
        # param格式: 市场代码,day,,,天数,复权类型
        # qfq=前复权, hfq=后复权, 不填=不复权
        param = f"{tc_code},day,,,{days},qfq"
        max_retries = 3

        # 501/404 等永久性错误不重试：服务端明确不支持该请求，重试只会
        # 白白等待 (2s→4s)，应直接回退新浪源。仅对网络抖动/空响应等
        # 瞬时错误进行指数退避重试。
        # 可重试的瞬时状态码：408 超时、425/429 限流、500/502/503/504 网关抖动
        _RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}

        for attempt in range(max_retries):
            try:
                resp = self._session.get(
                    constants.TENCENT_KLINE_API,
                    params={'param': param},
                    timeout=constants.REQUEST_TIMEOUT,
                )
                if resp.status_code != 200:
                    if resp.status_code in _RETRYABLE_STATUS:
                        # 瞬时错误：走统一重试逻辑
                        raise requests.exceptions.HTTPError(
                            f"{resp.status_code} Server Error",
                            response=resp,
                        )
                    # 永久性错误：直接放弃腾讯源，回退新浪
                    logger.error(
                        "获取 %s 历史K线失败（腾讯源返回永久性错误 %d，不重试）: %s",
                        code, resp.status_code, resp.url,
                    )
                    print(
                        f"获取 {code} 历史K线失败 (腾讯源返回 {resp.status_code}，"
                        f"不重试直接回退新浪)"
                    )
                    break
                # 腾讯接口偶发返回空 body，直接 json 解析会抛
                # JSONDecodeError: Expecting value: line 1 column 1 (char 0)
                if not resp.text or not resp.text.strip():
                    raise ValueError("腾讯K线API返回空响应")

                data = resp.json()

                if data.get('code') == 0 and data.get('data'):
                    stock_data = data['data'].get(tc_code)
                    if not stock_data:
                        return []

                    # 取前复权日线数据: qfqday；指数（如沪深300）只返回 day 字段
                    klines = stock_data.get('qfqday') or stock_data.get('day', [])
                    if not klines:
                        return []

                    result = []
                    for line in klines:
                        # 格式: ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
                        # 最后一条可能是个dict（含除权信息），需要跳过
                        if not isinstance(line, list) or len(line) < 6:
                            continue
                        try:
                            result.append({
                                'date': line[0],
                                'open': float(line[1]),
                                'close': float(line[2]),
                                'high': float(line[3]),
                                'low': float(line[4]),
                                'volume': float(line[5]),  # 手
                            })
                        except (ValueError, TypeError):
                            continue
                    # 拉取成功则写入缓存
                    try:
                        _kline_cache.set_csv(cache_key, pd.DataFrame(result))
                    except Exception:  # noqa: BLE001
                        pass
                    return result

            except Exception as e:  # noqa: BLE001 - 网络/解析异常统一重试
                delay = 2 ** (attempt + 1)
                if attempt < max_retries - 1:
                    logger.warning(
                        "获取 %s 历史K线失败（第 %d/%d 次）: %s，%.1fs 后重试",
                        code, attempt + 1, max_retries, e, delay,
                    )
                    print(
                        f"获取 {code} 历史K线失败 (第{attempt + 1}/{max_retries}次): "
                        f"{e}，{delay}秒后重试..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "获取 %s 历史K线失败（已达最大重试次数 %d）: %s",
                        code, max_retries, e,
                    )
                    print(f"获取 {code} 历史K线失败 (已达最大重试次数{max_retries}): {e}")

        # 腾讯全部重试失败，回退新浪财经K线源
        logger.info("%s 腾讯K线拉取失败，回退新浪源", code)
        print(f"  ↻ {code} 回退新浪K线源...")
        result = self._fetch_kline_sina(code, days)
        if result:
            # 新浪回退成功则写入缓存
            try:
                _kline_cache.set_csv(cache_key, pd.DataFrame(result))
            except Exception:  # noqa: BLE001
                pass
            return result

        # 腾讯与新浪都失败，回退旧缓存（即使过期也返回，保证可用性）
        stale = _kline_cache.get_csv(cache_key, allow_stale=True)
        if stale is not None and not stale.empty:
            return stale.to_dict("records")
        return []

    def _fetch_kline_sina(self, code: str, days: int = 60) -> List[dict]:
        """新浪财经历史日K线（回退源，不复权）。

        Args:
            code: 通用股票代码
            days: 获取的K线根数

        Returns:
            [{date, open, close, high, low, volume}, ...]
        """
        tc_code = to_tencent_code(code)
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {
            "symbol": tc_code,
            "scale": 240,          # 240 分钟 => 日线
            "ma": "no",
            "datalen": days,
        }
        try:
            resp = self._session.get(url, params=params, timeout=constants.REQUEST_TIMEOUT)
            resp.raise_for_status()
            if not resp.text or not resp.text.strip():
                raise ValueError("新浪K线API返回空响应")
            # 新浪返回 JSON 数组，直接 text 解析（可能带 BOM/引号包裹）
            raw = resp.text.strip()
            if raw.startswith("(") and raw.endswith(")"):
                raw = raw[1:-1]
            data = json.loads(raw)
            if not isinstance(data, list):
                return []

            result = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                try:
                    result.append({
                        'date': str(row['day']),
                        'open': float(row['open']),
                        'close': float(row['close']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'volume': float(row.get('volume', 0)),
                    })
                except (ValueError, TypeError, KeyError):
                    continue
            logger.info("%s 新浪K线回退拉取 %d 条", code, len(result))
            print(f"  ✓ {code} 新浪K线拉取 {len(result)} 条")
            return result

        except Exception as e:  # noqa: BLE001
            logger.error("获取 %s 历史K线失败（新浪源）: %s", code, e)
            print(f"获取 {code} 历史K线失败（新浪源）: {e}")
            return []
