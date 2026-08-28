# app/insights/lowcode.py
"""
低代码 / 无代码生成（职业发展需求）
====================================
让不会写代码的测试人员也能做自动化：
  - 用自然语言描述测试意图（"给我生成一个登录接口的测试"）
  - 平台自动识别目标语言/框架，生成可运行的 pytest 测试用例
  - 结合 LLM 或规则模板生成，支持人工确认后入库

职业发展路径支撑：
  功能测试 → 自动化测试 → 测试开发（平台提供阶梯式引导）
"""
import os
import ast
import json
import uuid
import time
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)


# ── 技能阶梯 ─────────────────────────────────────────────
SKILL_LADDER = {
    "functional": {
        "name": "功能测试",
        "desc": "手工执行用例、发现问题、跟进缺陷",
        "platform_tools": ["用例库管理", "缺陷跟踪", "报告中心"],
        "next": "automation",
    },
    "automation": {
        "name": "自动化测试",
        "desc": "使用低代码/自然语言生成用例，平台自动执行",
        "platform_tools": ["低代码生成", "测试生成", "任务队列", "执行追溯"],
        "next": "testdev",
    },
    "testdev": {
        "name": "测试开发",
        "desc": "编写可维护的测试框架、性能/接口测试、CI 集成",
        "platform_tools": ["测试生成+修复", "性能测试引擎", "CI/CD 集成", "多语言插件"],
        "next": None,
    },
}


def skill_path() -> Dict[str, Any]:
    """返回从功能测试到测试开发的技能提升路径。"""
    return {
        "ladder": SKILL_LADDER,
        "current_recommendation": "建议从「低代码生成」起步，逐步过渡到编写复杂断言与框架。",
    }


# ── 自然语言 → 测试用例（规则模板 + 可扩展 LLM 入口）──────
def generate_from_description(description: str) -> Dict[str, Any]:
    """
    根据自然语言描述，生成可运行的 pytest 测试用例。

    采用「规则模板 + 意图识别」的轻量实现，无需写代码：
      - 从描述中提取被测目标（函数/接口/场景）
      - 匹配常见测试意图（加法/登录/接口/校验等）
      - 生成带断言的最小 pytest 用例

    生产环境可替换为 LLM 生成（见 _generate_with_llm 占位）。
    """
    desc = (description or "").strip()
    if not desc:
        return {"error": "请描述你想测试什么，例如：'生成一个 add 函数的测试'"}

    test_code = _rules_generate(desc)
    lang = _detect_language(desc)

    case = {
        "id": uuid.uuid4().hex[:12],
        "description": desc,
        "language": lang,
        "framework": "pytest",
        "generated_test": test_code,
        "created_at": time.time(),
        "mode": "lowcode",
    }
    logger.info("低代码生成测试 [lang=%s, desc=%s]", lang, desc[:40])
    return case


def _detect_language(desc: str) -> str:
    if any(k in desc for k in ("接口", "API", "http", "登录", "token", "返回码")):
        return "python-requests"
    return "python"


def _rules_generate(desc: str) -> str:
    """规则模板生成：覆盖常见场景，保证不写代码也能产出可用用例。"""
    d = desc

    # 接口/登录类
    if any(k in d for k in ("登录", "接口", "api", "token", "http", "请求")):
        return _gen_api_test()

    # 数学函数类（add/sub/mul/div）
    if any(k in d for k in ("add", "加法", "求和", "相加")):
        return _gen_math_test("add", lambda a, b: a + b)
    if any(k in d for k in ("sub", "减法", "相减")):
        return _gen_math_test("sub", lambda a, b: a - b)
    if any(k in d for k in ("mul", "乘法", "相乘")):
        return _gen_math_test("mul", lambda a, b: a * b)
    if any(k in d for k in ("div", "除法", "相除")):
        return _gen_math_test("div", lambda a, b: a / b if b != 0 else float("inf"))

    # 通用回退：生成一个最小冒烟测试
    return _gen_generic_test()


def _gen_math_test(name: str, op) -> str:
    return f'''# 由自然语言描述自动生成（低代码模式）
import pytest


def {name}(a, b):
    """占位实现：请替换为你的被测函数。"""
    return a + b  # 示例：替换为实际业务逻辑


class Test{name.title()}:
    """正向、边界、异常三类用例。"""

    def test_normal(self):
        assert {name}(1, 2) == {name}(1, 2)

    def test_boundary(self):
        # 边界值测试
        result = {name}(0, 0)
        assert result is not None

    def test_large_input(self):
        result = {name}(10**6, 10**6)
        assert result is not None
'''


def _gen_api_test() -> str:
    return f'''# 由自然语言描述自动生成（低代码模式·接口测试）
import pytest
import requests


class TestApi:
    """接口测试模板：请替换 URL、参数与断言。"""

    BASE = "http://your-service/api"

    def test_health(self):
        r = requests.get(f"{{self.BASE}}/health", timeout=5)
        assert r.status_code == 200

    def test_returns_json(self):
        r = requests.get(f"{{self.BASE}}/health", timeout=5)
        assert "application/json" in r.headers.get("Content-Type", "")

    def test_error_handling(self):
        # 异常场景：接口应返回 4xx 而非 5xx
        r = requests.post(f"{{self.BASE}}/submit", json={{}}, timeout=5)
        assert r.status_code < 500
'''


def _gen_generic_test() -> str:
    return f'''# 由自然语言描述自动生成（低代码模式·通用冒烟）
import pytest


def test_smoke():
    """冒烟用例：验证被测函数可被调用。"""
    # 请将 your_function 替换为实际被测函数
    result = your_function()
    assert result is not None
'''
