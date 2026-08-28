"""
test_llm_retry.py — LLM 限流重试工具单元测试

覆盖:
  - 功能: is_rate_limit_error 识别各类限流错误
  - 功能: exponential_backoff_delay 指数退避计算
  - 功能: invoke_llm_with_retry 自动重试逻辑
  - 边界: 达到最大重试次数后抛异常
  - 异常: 非限流错误不重试
"""

import time
from unittest.mock import Mock, patch

import pytest

from app.llm.retry import (
    is_rate_limit_error,
    exponential_backoff_delay,
    invoke_llm_with_retry,
    DEFAULT_MAX_RETRIES,
    DEFAULT_BASE_DELAY,
    DEFAULT_MAX_DELAY,
    DEFAULT_BACKOFF_FACTOR,
)


class TestIsRateLimitError:
    """限流错误识别测试"""

    def test_rate_limit_error_by_name(self):
        """功能: RateLimitError 类型名识别"""
        class RateLimitError(Exception):
            pass
        assert is_rate_limit_error(RateLimitError("limit hit")) is True

    def test_free_usage_limit_error_by_name(self):
        """功能: FreeUsageLimitError 类型名识别"""
        class FreeUsageLimitError(Exception):
            pass
        assert is_rate_limit_error(FreeUsageLimitError("free limit")) is True

    def test_429_in_message(self):
        """功能: 消息含 429 识别"""
        assert is_rate_limit_error(Exception("Error code: 429 - rate limit")) is True

    def test_rate_limit_message_keywords(self):
        """功能: 消息含 rate limit 关键词识别"""
        assert is_rate_limit_error(Exception("Rate limit exceeded. Try again later.")) is True

    def test_quota_exceeded(self):
        """功能: 配额超限识别"""
        assert is_rate_limit_error(Exception("Quota exceeded")) is True

    def test_non_rate_limit_error(self):
        """功能: 普通错误不识别为限流"""
        assert is_rate_limit_error(Exception("Connection refused")) is False

    def test_auth_error_not_retryable(self):
        """功能: 认证错误不可重试"""
        class AuthenticationError(Exception):
            pass
        assert is_rate_limit_error(AuthenticationError("Invalid API key")) is False

    def test_http_500_not_rate_limit(self):
        """功能: 500 服务器错误不识别为限流"""
        assert is_rate_limit_error(Exception("Error code: 500 - Internal server error")) is False


class TestExponentialBackoffDelay:
    """指数退避计算测试"""

    def test_returns_positive_delay(self):
        """功能: 返回正数延迟"""
        delay = exponential_backoff_delay(0)
        assert delay > 0

    def test_delay_increases_with_attempt(self):
        """功能: 延迟随尝试次数递增"""
        with patch("random.uniform", return_value=1.0):  # 去掉抖动
            d0 = exponential_backoff_delay(0, base_delay=1.0, backoff_factor=2.0)
            d1 = exponential_backoff_delay(1, base_delay=1.0, backoff_factor=2.0)
            d2 = exponential_backoff_delay(2, base_delay=1.0, backoff_factor=2.0)
            assert d0 < d1 < d2

    def test_capped_at_max_delay(self):
        """边界: 延迟不超过最大值"""
        with patch("random.uniform", return_value=1.0):
            delay = exponential_backoff_delay(10, base_delay=2.0, max_delay=30.0, backoff_factor=2.0)
            assert delay <= 30.0

    def test_jitter_applied(self):
        """功能: 抖动范围 0.5x~1.5x"""
        base = 2.0
        with patch("random.uniform", return_value=0.5):
            assert exponential_backoff_delay(0, base_delay=base) >= base * 0.5
        with patch("random.uniform", return_value=1.5):
            assert exponential_backoff_delay(0, base_delay=base) <= base * 1.5


class TestInvokeLLMWithRetry:
    """LLM 重试调用测试"""

    def test_success_first_try(self):
        """功能: 首次调用成功无需重试"""
        mock_func = Mock(return_value="ok")
        result = invoke_llm_with_retry(mock_func, max_retries=3)
        assert result == "ok"
        assert mock_func.call_count == 1

    def test_retries_on_rate_limit_then_succeeds(self):
        """功能: 限流后重试成功"""
        calls = []
        def flaky():
            if len(calls) < 2:
                calls.append(1)
                raise Exception("Error code: 429 - Rate limit exceeded")
            return "success"

        with patch("time.sleep"):  # 不实际等待
            result = invoke_llm_with_retry(flaky, max_retries=3, base_delay=0.1)
        assert result == "success"
        assert len(calls) == 2

    def test_raises_after_max_retries(self):
        """边界: 达到最大重试次数后抛异常"""
        calls = []
        def always_fails():
            calls.append(1)
            raise Exception("Error code: 429 - Rate limit exceeded")

        with patch("time.sleep"):
            with pytest.raises(Exception, match="429"):
                invoke_llm_with_retry(always_fails, max_retries=2, base_delay=0.1)
        # 首次 + 2 次重试 = 3 次调用
        assert len(calls) == 3

    def test_non_retryable_error_raises_immediately(self):
        """异常: 非限流错误不重试直接抛出"""
        mock_func = Mock(side_effect=ValueError("bad argument"))
        with pytest.raises(ValueError):
            invoke_llm_with_retry(mock_func, max_retries=3)
        assert mock_func.call_count == 1

    def test_free_usage_limit_retries(self):
        """功能: FreeUsageLimitError 自动重试"""
        calls = []
        def flaky():
            if len(calls) < 1:
                calls.append(1)
                raise Exception("FreeUsageLimitError: Rate limit exceeded")
            return "ok"

        with patch("time.sleep"):
            result = invoke_llm_with_retry(flaky, max_retries=3, base_delay=0.1)
        assert result == "ok"

    def test_passes_args_and_kwargs(self):
        """功能: 正确传递参数"""
        mock_func = Mock(return_value="result")
        invoke_llm_with_retry(mock_func, "arg1", key="val", max_retries=1)
        mock_func.assert_called_once_with("arg1", key="val")
