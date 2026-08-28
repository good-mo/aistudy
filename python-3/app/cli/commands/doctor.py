"""
app.cli.commands.doctor —— 环境自检命令

检查依赖、数据源连通性、核心包导入。
"""

from __future__ import annotations

import argparse

from app.core.logging_setup import get_logger

logger = get_logger(__name__)

# 核心依赖检查
CORE_DEPS = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("requests", "requests"),
    ("akshare", "akshare"),
    ("gmssl", "gmssl"),
    ("scipy", "scipy"),
]


def doctor_command(argv: list[str] | None = None) -> int:
    """环境自检命令。"""
    parser = argparse.ArgumentParser(description="环境自检")
    args = parser.parse_args(argv)

    print("🔧 环境自检\n")

    # 1. 依赖检查
    print("📦 依赖检查：")
    ok = True
    for pip_name, import_name in CORE_DEPS:
        try:
            __import__(import_name)
            print(f"  ✅ {pip_name:<12} 可用")
        except ImportError:
            print(f"  ❌ {pip_name:<12} 缺失")
            ok = False

    # 2. 核心包导入
    print("\n📦 核心模块导入检查：")
    for pkg in ("app", "app.core", "app.data", "app.domains", "app.cli"):
        try:
            __import__(pkg)
            print(f"  ✅ {pkg:<20} 导入正常")
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ {pkg:<20} 导入失败: {e}")
            ok = False

    # 3. 数据源连通性（可选）
    print("\n🌐 数据源连通性检查：")
    try:
        from app.data.base import get_registry
        registry = get_registry()
        for name in registry.names:
            source = registry.get(name)
            print(f"  ✅ {name:<12} 已注册")
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️ 数据源检查失败: {e}")

    print("\n" + ("✅ 环境正常。" if ok else "⚠️ 存在缺失依赖，请先安装。"))
    return 0 if ok else 1
