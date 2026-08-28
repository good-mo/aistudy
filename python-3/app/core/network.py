"""
app.core.network —— 统一 HTTP 客户端

提供全项目共享的网络请求能力：
    - 连接池复用（requests.Session）
    - 指数退避重试
    - 可配置超时
    - 统一请求头
    - 可重试状态码 vs 永久错误区分

设计要点：
    - 所有数据源共用同一个 Session 池，减少连接建立开销
    - 重试仅针对瞬时错误（超时/限流/5xx/网络抖动）
    - 永久错误（404/501 等）不重试，直接抛给上层做降级
"""

from __future__ import annotations

import random
import time
from http.client import RemoteDisconnected as HttpRemoteDisconnected
from typing import Any

import requests

from app.core.config import get_config
from app.core.errors import NetworkError
from app.core.logging_setup import get_logger

logger = get_logger(__name__)

# 可重试的瞬时状态码
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _is_remote_disconnected(exc: BaseException) -> bool:
    """判断异常链中是否包含 RemoteDisconnected（服务端主动关闭连接）。

    RemoteDisconnected 通常意味着服务端主动拒绝/关闭了连接（如限流、
    防火墙拦截或连接池中的 keep-alive 连接已被服务端关闭），此时在
    同一连接池上立即重试大概率仍会失败，应视为不可重试的错误类型。
    """
    seen: set[int] = set()
    stack = [exc]
    while stack:
        e = stack.pop()
        if id(e) in seen:
            continue
        seen.add(id(e))
        if isinstance(e, HttpRemoteDisconnected):
            return True
        args = getattr(e, "args", ()) or ()
        for arg in args:
            if isinstance(arg, BaseException):
                stack.append(arg)
        cause = getattr(e, "__cause__", None)
        if cause is not None:
            stack.append(cause)
    return False


def _close_stale_connections(session: requests.Session) -> None:
    """关闭 Session 中所有 keep-alive 空闲连接，强制下次请求新建 TCP 连接。

    当收到 RemoteDisconnected 时，往往是连接池中缓存的 keep-alive 连接
    已被服务端关闭，requests 未感知仍继续复用导致失败。关闭全部连接后，
    下次请求会建立全新的 TCP 连接，避免继续命中已失效的连接。
    """
    try:
        for adapter in session.adapters.values():
            pool = getattr(adapter, "poolmanager", None)
            if pool is not None:
                pool.clear()
    except Exception:  # noqa: BLE001 连接池清理失败不应影响主流程
        pass


class HTTPClient:
    """统一 HTTP 客户端（带连接池、重试、降级）。"""

    def __init__(
        self,
        *,
        timeout: float = 15.0,
        retries: int = 3,
        backoff_base: float = 1.0,
        backoff_factor: float = 2.0,
        user_agent: str | None = None,
        pool_connections: int = 20,
        pool_maxsize: int = 20,
    ):
        self._timeout = timeout
        self._retries = retries
        self._backoff_base = backoff_base
        self._backoff_factor = backoff_factor
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": user_agent or _DEFAULT_USER_AGENT,
        })
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=0,  # 我们自己做重试控制，不用 urllib3 的重试
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    # ------------------------------------------------------------------
    # 请求方法
    # ------------------------------------------------------------------

    def get(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
        retries: int | None = None,
        **kwargs,
    ) -> requests.Response:
        """带重试的 GET 请求。

        仅在瞬时错误（超时/限流/5xx/网络抖动）时重试，
        永久错误（404/501）直接抛出。
        """
        effective_timeout = timeout or self._timeout
        effective_retries = retries or self._retries
        last_err: Exception | None = None

        for attempt in range(effective_retries):
            try:
                resp = self._session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=effective_timeout,
                    **kwargs,
                )
                if resp.status_code >= 400:
                    if resp.status_code in _RETRYABLE_STATUS:
                        # 可重试状态码：记录错误，进入下面的重试逻辑
                        last_err = NetworkError(
                            f"HTTP {resp.status_code}（可重试）: {url}",
                            cause=None,
                        )
                        logger.warning(
                            "HTTP %d（可重试）%s（第 %d/%d 次）",
                            resp.status_code, url, attempt + 1, effective_retries,
                        )
                    else:
                        # 永久错误：直接抛出，不重试
                        raise NetworkError(f"HTTP {resp.status_code}: {url}")
                else:
                    return resp
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_err = exc
                # RemoteDisconnected（服务端主动断开）通常意味着连接池中的
                # keep-alive 连接已失效，先关闭旧连接再重试，否则会持续命中
                # 同一个已断开的连接。
                if _is_remote_disconnected(exc):
                    _close_stale_connections(self._session)
                    logger.warning(
                        "连接被服务端断开 %s（第 %d/%d 次）: %s（已清理连接池）",
                        url, attempt + 1, effective_retries, exc,
                    )
                else:
                    logger.warning(
                        "请求超时/连接失败 %s（第 %d/%d 次）: %s",
                        url, attempt + 1, effective_retries, exc,
                    )
            except NetworkError:
                raise  # 永久 HTTP 错误不重试
            except requests.RequestException as exc:
                last_err = exc
                logger.warning(
                    "请求异常 %s（第 %d/%d 次）: %s",
                    url, attempt + 1, effective_retries, exc,
                )

            if attempt < effective_retries - 1:
                delay = self._backoff_base * (self._backoff_factor**attempt)
                # 加 0~30% 随机抖动，避免多个客户端同时重试造成 thundering herd
                delay *= 1 + random.random() * 0.3
                logger.debug("   %.1fs 后重试", delay)
                time.sleep(delay)

        raise NetworkError(
            f"请求失败（已重试 {effective_retries} 次）: {url}",
            cause=last_err,
        )

    def get_json(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
        retries: int | None = None,
    ) -> dict | list:
        """GET 并解析 JSON。"""
        resp = self.get(
            url, params=params, headers=headers, timeout=timeout, retries=retries,
        )
        try:
            return resp.json()
        except ValueError as e:
            raise NetworkError(f"JSON 解析失败: {url}") from e

    def get_text(
        self,
        url: str,
        *,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
        retries: int | None = None,
        encoding: str | None = None,
    ) -> str:
        """GET 并返回文本（可选指定编码）。"""
        resp = self.get(
            url, params=params, headers=headers, timeout=timeout, retries=retries,
        )
        if encoding:
            resp.encoding = encoding
        return resp.text

    # ------------------------------------------------------------------
    # Session 访问
    # ------------------------------------------------------------------

    @property
    def session(self) -> requests.Session:
        """返回底层 Session（兼容需要直接操作的场景）。"""
        return self._session


_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_client_instance: HTTPClient | None = None


def get_http_client() -> HTTPClient:
    """返回全局 HTTP 客户端单例。"""
    global _client_instance
    if _client_instance is None:
        cfg = get_config()
        _client_instance = HTTPClient(
            timeout=cfg.network.timeout,
            retries=cfg.network.retries,
            backoff_base=cfg.network.backoff_base,
            backoff_factor=cfg.network.backoff_factor,
            user_agent=cfg.network.user_agent,
            pool_connections=cfg.network.pool_connections,
            pool_maxsize=cfg.network.pool_maxsize,
        )
    return _client_instance
