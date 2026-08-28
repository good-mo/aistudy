"""
测试类型定义与注册表
====================
定义系统支持的测试类型类别，以及每个类型对应的元数据。

测试类型（行业标准分类）:
  - functional  功能测试   — 验证业务功能正确性
  - api         接口测试   — 验证 API 端点/方法的请求响应契约
  - ui          UI 测试    — 验证用户界面交互
  - performance 性能测试   — 验证性能指标与 SLO
  - security    安全测试   — 验证安全防护
  - compatibility 兼容性测试 — 验证跨环境兼容
  - reliability 可靠性测试 — 验证容错与稳定性
"""

from enum import Enum
from typing import Dict, Any


class TestType(str, Enum):
    """测试类型枚举（字符串值保持与前端/API 一致）。"""
    __test__ = False  # 防止 pytest 将其误收集为测试类
    FUNCTIONAL = "functional"
    API = "api"
    UI = "ui"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPATIBILITY = "compatibility"
    RELIABILITY = "reliability"


# ── 测试类型注册表：集中管理各类型的元数据 ────────────────────
TEST_TYPES: Dict[str, Dict[str, Any]] = {
    TestType.FUNCTIONAL.value: {
        "key": TestType.FUNCTIONAL.value,
        "label": "功能测试",
        "icon": "🧪",
        "description": "验证业务功能的正确性（正常流程/边界/异常）",
    },
    TestType.API.value: {
        "key": TestType.API.value,
        "label": "接口测试",
        "icon": "🔌",
        "description": "验证 API 端点的请求/响应契约、状态码与数据格式",
    },
    TestType.UI.value: {
        "key": TestType.UI.value,
        "label": "UI 测试",
        "icon": "🎨",
        "description": "验证用户界面的元素、交互与视觉呈现",
    },
    TestType.PERFORMANCE.value: {
        "key": TestType.PERFORMANCE.value,
        "label": "性能测试",
        "icon": "⚡",
        "description": "验证系统在负载下的响应时间、吞吐量与资源消耗",
    },
    TestType.SECURITY.value: {
        "key": TestType.SECURITY.value,
        "label": "安全测试",
        "icon": "🔒",
        "description": "验证输入校验、注入防护、越权访问等安全场景",
    },
    TestType.COMPATIBILITY.value: {
        "key": TestType.COMPATIBILITY.value,
        "label": "兼容性测试",
        "icon": "🖥️",
        "description": "验证跨 Python 版本、跨平台、跨浏览器/库版本兼容",
    },
    TestType.RELIABILITY.value: {
        "key": TestType.RELIABILITY.value,
        "label": "可靠性测试",
        "icon": "🔧",
        "description": "验证系统在异常条件下的容错、幂等与稳定性",
    },
}


def get_test_type_info(test_type: str) -> Dict[str, Any]:
    """
    获取测试类型信息。

    Args:
        test_type: 测试类型 key（如 "functional" / "api"）

    Returns:
        类型元数据 dict；未知类型返回默认 functional。
    """
    return TEST_TYPES.get(test_type, TEST_TYPES[TestType.FUNCTIONAL.value])


def get_default_test_type() -> str:
    """返回默认测试类型。"""
    return TestType.FUNCTIONAL.value


def is_valid_test_type(test_type: str) -> bool:
    """判断是否为合法测试类型。"""
    return test_type in TEST_TYPES


def list_test_types() -> list:
    """列出所有测试类型（供前端/API 展示）。"""
    return list(TEST_TYPES.values())


# 兼容旧接口：便捷访问
def get_all_test_types() -> Dict[str, Dict[str, Any]]:
    return TEST_TYPES
