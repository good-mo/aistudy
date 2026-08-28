# app/config.py
"""
统一配置模块
============
基于 pydantic-settings 的集中式配置管理（FastAPI 现代最佳实践）：
  - 从 .env 文件 / 环境变量自动加载并做类型验证
  - @lru_cache 缓存 settings 实例，避免重复解析
  - get_llm() 工厂：支持多 LLM provider（OpenAI 兼容 / Azure / 本地）切换

参考实践：
  - 配置与代码分离，避免硬编码、避免敏感信息进版本控制
  - 使用 Pydantic 定义 schema 并强制类型验证
  - 通过 .env 管理，便于 dev/staging/prod 环境切换
"""

import os
from functools import lru_cache
from typing import Optional

from app.db import PROJECT_ROOT

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ════════════════════════════════════════════════════════════
# 1. Settings 定义（Pydantic v2 写法）
# ════════════════════════════════════════════════════════════

class Settings(BaseSettings):
    # ── 应用基本信息 ──────────────────────────────
    app_name: str = Field("Test Generation Toolkit", description="应用名称")
    environment: str = Field("development", description="运行环境: development/staging/production")
    debug: bool = Field(True, description="Debug 模式，生产环境应为 False")
    host: str = Field("0.0.0.0", description="服务监听地址")
    port: int = Field(8000, description="服务端口")

    # ── LLM Provider 选择 ─────────────────────────
    # 可选: "openai" | "azure" | "local"（OpenAI 兼容端点，如 vLLM/Ollama/LiteLLM）
    llm_provider: str = Field("openai", description="LLM 提供方")
    llm_model: str = Field("gpt-4o", description="模型名称 / Azure 部署名")
    llm_temperature: float = Field(0.0, description="默认采样温度")
    llm_timeout: int = Field(120, description="LLM 调用超时（秒）")
    llm_max_retries: int = Field(2, description="LLM 网络层重试次数")

    # ── LLM 限流重试 ────────────────────────────
    llm_rate_limit_max_retries: int = Field(3, description="LLM 限流错误最大重试次数")
    llm_rate_limit_base_delay: float = Field(2.0, description="限流重试初始等待秒数")
    llm_rate_limit_max_delay: float = Field(30.0, description="限流重试最大等待秒数")
    llm_rate_limit_backoff_factor: float = Field(2.0, description="限流重试退避倍数")

    # ── OpenAI / OpenAI 兼容端点 ──────────────────
    openai_api_key: Optional[str] = Field(None, description="OpenAI / 兼容 API Key")
    openai_api_base: Optional[str] = Field(None, description="OpenAI / 兼容 base_url")
    # 自定义 HTTP 请求头（JSON 字符串），用于兼容特殊认证方式的 LLM 端点
    llm_default_headers: str = Field("", description="自定义 HTTP 请求头（JSON 字符串）")

    # ── Azure OpenAI ──────────────────────────────
    azure_api_key: Optional[str] = Field(None, description="Azure OpenAI API Key")
    azure_endpoint: Optional[str] = Field(None, description="Azure OpenAI 端点")
    azure_api_version: str = Field("2024-08-01-preview", description="Azure API 版本")

    # ── Agent 行为配置 ────────────────────────────
    max_retries: int = Field(3, description="测试修复最大重试次数")
    max_coverage_retries: int = Field(5, description="覆盖率补测总重试上限")
    coverage_threshold: float = Field(80.0, description="覆盖率达标阈值(%)")
    test_timeout: int = Field(60, description="单次 pytest 运行超时（秒）")

    # ── P0：任务队列（异步化）────────────────────────
    task_queue_maxsize: int = Field(100, description="任务队列最大容量")
    task_workers: int = Field(2, description="后台任务 worker 数量")
    task_timeout: int = Field(600, description="单任务最大执行时长（秒）")

    # ── P0：Docker 沙箱（安全隔离）─────────────────
    sandbox_enabled: bool = Field(True, description="是否启用 Docker 沙箱隔离")
    sandbox_image: str = Field("python:3.12-slim", description="沙箱基础镜像")
    sandbox_mem_limit: str = Field("512m", description="沙箱容器内存限制")
    sandbox_nano_cpus: int = Field(1000000000, description="沙箱 CPU 限制（纳秒，1 CPU=1e9）")
    sandbox_network_mode: str = Field("none", description="沙箱网络模式，默认禁用网络以提升安全性")

    # ── 持久化 / 检查点 ───────────────────────────
    checkpoint_db: str = Field("checkpoints.db", description="LangGraph SQLite 检查点路径")

    # ── 企业级性能测试引擎 ────────────────────────
    perf_enabled: bool = Field(False, description="是否在用例生成流程中默认执行性能测试")
    perf_iterations: int = Field(50, description="性能基准采样次数")
    perf_warmup: int = Field(5, description="性能基准预热次数")
    perf_concurrency: int = Field(1, description="性能基准并发线程数")
    perf_p95_max_sec: float = Field(1.0, description="性能 P95 响应时间上限（秒）")
    perf_throughput_min: float = Field(10.0, description="性能吞吐量下限（次/秒）")
    perf_memory_max_mb: float = Field(512.0, description="性能峰值内存上限（MB）")

    # ── 可观测性（可选）────────────────────────────
    langfuse_public_key: Optional[str] = Field(None, description="Langfuse Public Key")
    langfuse_secret_key: Optional[str] = Field(None, description="Langfuse Secret Key")
    langfuse_host: Optional[str] = Field(None, description="Langfuse Host")

    @field_validator("checkpoint_db")
    @classmethod
    def _resolve_checkpoint_db(cls, value: str) -> str:
        """将相对路径的数据库文件解析为项目根目录下的绝对路径。"""
        if not value:
            return value
        return value if os.path.isabs(value) else os.path.join(PROJECT_ROOT, value)

    # ── Pydantic v2 配置 ──────────────────────────
    model_config = SettingsConfigDict(
        env_file=".env",         # 从 .env 文件加载
        env_file_encoding="utf-8",
        extra="ignore",          # 忽略 .env 中未定义的多余字段
        case_sensitive=False,    # 环境变量名不区分大小写
    )

    # ── 便捷属性 ──────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


# ════════════════════════════════════════════════════════════
# 2. 缓存的 Settings 单例
# ════════════════════════════════════════════════════════════

@lru_cache()
def get_settings() -> Settings:
    """
    返回缓存的 Settings 实例。
    @lru_cache 确保 .env 只解析一次，节省内存并加速。
    """
    return Settings()


# 模块级单例，供其他模块直接 `from app.config import settings`
settings = get_settings()


# ════════════════════════════════════════════════════════════
# 3. LLM 工厂：get_llm（多 provider 切换）
# ════════════════════════════════════════════════════════════

# 简单缓存，避免每个节点重复构造客户端
_LLM_CACHE: dict = {}


def get_llm(
    temperature: Optional[float] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
):
    """
    根据配置返回 LangChain Chat 模型实例。

    Args:
        temperature: 覆盖默认温度（如 refinement 用 0）
        model:       覆盖默认模型
        provider:    覆盖默认 provider（openai/azure/local）

    Returns:
        ChatOpenAI / AzureChatOpenAI 实例
    """
    s = get_settings()
    provider = (provider or s.llm_provider).lower()
    model = model or s.llm_model
    temperature = s.llm_temperature if temperature is None else temperature

    cache_key = f"{provider}:{model}:{temperature}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    if provider == "azure":
        llm = _build_azure_llm(s, model, temperature)
    elif provider in ("openai", "local"):
        llm = _build_openai_llm(s, model, temperature)
    else:
        raise ValueError(
            f"不支持的 llm_provider: '{provider}'，"
            f"可选值: openai / azure / local"
        )

    _LLM_CACHE[cache_key] = llm
    return llm


def _build_openai_llm(s: Settings, model: str, temperature: float):
    """构建 OpenAI 兼容端点的 ChatOpenAI（适配 OpenAI / vLLM / Ollama / LiteLLM）。"""
    from langchain_openai import ChatOpenAI

    if not s.openai_api_key:
        raise ValueError(
            "缺少 OPENAI_API_KEY，请在 .env 中配置。"
            "（本地兼容端点可填任意占位符，如 'sk-local'）"
        )

    kwargs = {
        "model": model,
        "temperature": temperature,
        "api_key": s.openai_api_key,
        "timeout": s.llm_timeout,
        "max_retries": s.llm_max_retries,
    }
    # 自定义/本地端点
    if s.openai_api_base:
        kwargs["base_url"] = s.openai_api_base

    # 自定义请求头（如 opencode.ai 需要 api-key 而非 Authorization Bearer）
    if s.llm_default_headers:
        import json
        try:
            headers = json.loads(s.llm_default_headers)
            if headers:
                kwargs["default_headers"] = headers
        except json.JSONDecodeError:
            raise ValueError(
                f"LLM_DEFAULT_HEADERS 必须是合法 JSON 对象字符串，当前值: {s.llm_default_headers}"
            )

    return ChatOpenAI(**kwargs)


def _build_azure_llm(s: Settings, model: str, temperature: float):
    """构建 Azure OpenAI 的 AzureChatOpenAI。"""
    from langchain_openai import AzureChatOpenAI

    if not (s.azure_api_key and s.azure_endpoint):
        raise ValueError(
            "缺少 AZURE_API_KEY 或 AZURE_ENDPOINT，请在 .env 中配置。"
        )

    return AzureChatOpenAI(
        azure_deployment=model,          # Azure 用部署名
        azure_endpoint=s.azure_endpoint,
        api_key=s.azure_api_key,
        api_version=s.azure_api_version,
        temperature=temperature,
        timeout=s.llm_timeout,
        max_retries=s.llm_max_retries,
    )


# ════════════════════════════════════════════════════════════
# 4. 启动时配置校验（fail-fast）
# ════════════════════════════════════════════════════════════

def validate_config() -> None:
    """
    程序启动后尽快验证关键配置，发现无效立即报错退出。
    （配置最佳实践：尽早验证 schema，避免运行时才暴露问题）
    """
    s = get_settings()
    errors = []

    if s.llm_provider.lower() in ("openai", "local") and not s.openai_api_key:
        errors.append("OPENAI_API_KEY 未设置")
    if s.llm_provider.lower() == "azure":
        if not s.azure_api_key:
            errors.append("AZURE_API_KEY 未设置")
        if not s.azure_endpoint:
            errors.append("AZURE_ENDPOINT 未设置")
    if not (0.0 <= s.coverage_threshold <= 100.0):
        errors.append("coverage_threshold 应在 0~100 之间")

    if errors:
        raise RuntimeError("配置校验失败:\n  - " + "\n  - ".join(errors))


# ════════════════════════════════════════════════════════════
# 5. 本地自测
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    s = get_settings()
    print("=== 当前配置 ===")
    print(f"app_name        : {s.app_name}")
    print(f"environment     : {s.environment}")
    print(f"llm_provider    : {s.llm_provider}")
    print(f"llm_model       : {s.llm_model}")
    print(f"openai_api_base : {s.openai_api_base}")
    print(f"coverage_thresh : {s.coverage_threshold}")
    print(f"is_production   : {s.is_production}")

    print("\n=== 配置校验 ===")
    try:
        validate_config()
        print("✅ 配置校验通过")
    except RuntimeError as e:
        print(f"❌ {e}")
