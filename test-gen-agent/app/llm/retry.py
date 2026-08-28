# app/llm/retry.py
"""
LLM 调用限流重试工具
=====================
当 LLM 调用遇到 RateLimitError（限流/免费额度超限）时，
使用指数退避 + 抖动（jitter）策略自动重试，提升任务成功率。

错误类型说明：
  - OpenAI `RateLimitError` (HTTP 429)
  - 子类 `FreeUsageLimitError`（免费额度超限）
    这类错误通常是瞬时状态（额度按时间窗口恢复），适合重试。
  - 非限流类错误（认证失败、参数错误等 4xx）不应重试。
"""
import time
import random
from typing import Any, Callable, Optional, Type

from app.logging_config import get_logger

logger = get_logger(__name__)

# 默认重试配置
DEFAULT_MAX_RETRIES = 3          # 最多重试次数
DEFAULT_BASE_DELAY = 2.0         # 初始等待秒数
DEFAULT_MAX_DELAY = 30.0         # 最大等待秒数（封顶）
DEFAULT_BACKOFF_FACTOR = 2.0     # 退避倍数


def is_rate_limit_error(e: Exception) -> bool:
    """
    判断异常是否为限流/额度超限错误。

    支持:
      - langchain_openai.chat_models.base.OpenAIRateLimitError
      - openai.RateLimitError
      - 任何 HTTP 429 相关错误
    """
    # 1. 按类型名称匹配（避免强依赖 import，兼容多 provider）
    type_name = type(e).__name__
    if "RateLimitError" in type_name:
        return True
    if "FreeUsageLimitError" in type_name:
        return True

    # 2. 按消息内容匹配
    msg = str(e).lower()
    keywords = [
        "rate limit",
        "429",
        "freeusagelimiterror",
        "too many requests",
        "quota exceeded",
        "rate_limit_exceeded",
    ]
    return any(kw in msg for kw in keywords)


def exponential_backoff_delay(
    attempt: int,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
) -> float:
    """
    计算指数退避 + 抖动的等待时间。

    delay = min(max_delay, base_delay * backoff_factor ** attempt) * (0.5 + random())
    """
    exp_delay = min(max_delay, base_delay * (backoff_factor ** attempt))
    # 添加 0.5x~1.5x 随机抖动，避免多请求同时重试造成"惊群"
    jitter = random.uniform(0.5, 1.5)
    return exp_delay * jitter


def invoke_llm_with_retry(
    func: Callable[..., Any],
    *args,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    error_class: Optional[Type[Exception]] = None,
    **kwargs,
) -> Any:
    """
    调用 LLM 函数，遇到限流错误时自动指数退避重试。

    Args:
        func: 可调用对象（如 llm.invoke）
        *args: 传给 func 的位置参数
        max_retries: 最多重试次数（不含首次尝试）
        base_delay: 初始退避等待秒数
        max_delay: 最大退避等待秒数
        backoff_factor: 退避倍数
        error_class: 指定的异常类型（可选，用于精确捕获）
        **kwargs: 传给 func 的关键字参数

    Returns:
        func 的返回值

    Raises:
        最后一次重试时的原始异常
    """
    attempt = 0
    while True:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # 判断是否是可重试的限流错误
            is_retryable = is_rate_limit_error(e)
            # 如果指定了 error_class，且当前异常不是该类型或其子类，则不再重试
            if error_class is not None and not isinstance(e, error_class):
                is_retryable = False

            if not is_retryable:
                logger.warning("LLM 调用失败（不可重试）[err=%s]", e)
                raise

            if attempt >= max_retries:
                logger.error(
                    "LLM 限流重试 %d 次后仍失败 [err=%s]",
                    max_retries, e
                )
                raise

            delay = exponential_backoff_delay(
                attempt, base_delay, max_delay, backoff_factor
            )
            logger.warning(
                "LLM 触发限流，第 %d 次重试将在 %.1fs 后进行 [err=%s]",
                attempt + 1, delay, e
            )
            time.sleep(delay)
            attempt += 1
