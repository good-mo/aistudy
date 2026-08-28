#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动安装依赖 + 环境自检脚本
=============================

功能：
  1. 自动检测缺失的 Python 依赖并安装（读取 requirements.txt）
  2. 校验核心依赖是否可用
  3. 支持 --check 仅检查不安装、--mirror 指定镜像源

用法：
    python bootstrap.py             # 自动安装缺失依赖并自检
    python bootstrap.py --check     # 仅检查，不安装
    python bootstrap.py --mirror https://pypi.tuna.tsinghua.edu.cn/simple
"""

import argparse
import importlib
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = os.path.join(PROJECT_ROOT, "requirements.txt")

# 核心依赖（用于 doctor 检测）
CORE_DEPS = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("requests", "requests"),
    ("beautifulsoup4", "bs4"),
    ("akshare", "akshare"),
    ("gmssl", "gmssl"),
    ("scipy", "scipy"),
]

# 可选依赖：TA-Lib 需系统 C 库（libta-lib），安装失败不阻断主流程
OPTIONAL_DEPS = [
    ("talib", "talib"),
]

# 核心包（用于导入检查）
CORE_PACKAGES = ["jijin_core", "share300_core", "lc_core", "stock_monitor"]


def pip_install(packages, mirror=None):
    """使用 pip 安装指定包，支持镜像源与失败回退。"""
    cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir"]
    if mirror:
        cmd += ["-i", mirror]
    cmd += packages
    print(f"📦 执行: {' '.join(cmd)}")
    return subprocess.call(cmd) == 0


def _importable(import_name):
    """尝试导入模块，成功返回模块对象，失败返回 None。"""
    try:
        return importlib.import_module(import_name)
    except ImportError:
        return None


def check_missing():
    """返回缺失的依赖包名列表。"""
    missing = []
    for pip_name, import_name in CORE_DEPS:
        if _importable(import_name) is None:
            missing.append(pip_name)
    return missing


def read_requirements():
    """解析 requirements.txt，返回包名列表（忽略注释与空行）。"""
    pkgs = []
    try:
        with open(REQUIREMENTS, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # 去掉版本约束：a>=1.0  -> a
                name = line.split(">=")[0].split("==")[0].split("<")[0].strip()
                if name and name not in ("#",):
                    pkgs.append(name)
    except FileNotFoundError:
        print(f"⚠️ 未找到 {REQUIREMENTS}")
    return pkgs


def doctor():
    """环境自检：检查依赖与核心包导入。"""
    print("🔧 环境自检\n")
    ok = True

    # 依赖检查
    print("📦 核心依赖：")
    for pip_name, import_name in CORE_DEPS:
        try:
            importlib.import_module(import_name)
            print(f"  ✅ {pip_name:<14} 可用")
        except ImportError:
            print(f"  ❌ {pip_name:<14} 缺失（pip install {pip_name}）")
            ok = False

    # 可选依赖检查（不阻断）
    print("\n🟡 可选依赖（TA-Lib 需系统库，缺失不影响主流程）：")
    for pip_name, import_name in OPTIONAL_DEPS:
        try:
            importlib.import_module(import_name)
            print(f"  ✅ {pip_name:<14} 可用")
        except ImportError:
            print(f"  ⚪ {pip_name:<14} 未安装（可选）")

    # 核心包导入检查
    print("\n📦 核心包导入：")
    # stock_monitor 位于 share/ 子目录，需加入 sys.path
    share_dir = os.path.join(PROJECT_ROOT, "share")
    if share_dir not in sys.path:
        sys.path.insert(0, share_dir)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    for pkg in CORE_PACKAGES:
        try:
            __import__(pkg)
            print(f"  ✅ {pkg:<14} 导入正常")
        except Exception as e:
            print(f"  ❌ {pkg:<14} 导入失败: {e}")
            ok = False

    print("\n" + ("✅ 环境正常，可运行。" if ok else "⚠️ 存在缺失依赖，请安装。"))
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(prog="bootstrap.py", description="自动安装依赖并自检环境")
    parser.add_argument("--check", action="store_true", help="仅检查缺失依赖，不安装")
    parser.add_argument("--mirror", default=None, help="指定 pip 镜像源（如清华/腾讯源）")
    args = parser.parse_args()

    print("🔍 正在检查缺失依赖...\n")
    missing = check_missing()

    if not missing:
        print("✅ 所有核心依赖均已安装。")
        return doctor()

    print(f"缺失依赖: {', '.join(missing)}\n")

    if args.check:
        print("⚠️ 已开启 --check，未执行安装。请运行: python bootstrap.py")
        return 1

    # 优先安装缺失的核心依赖
    print("🚀 开始安装缺失依赖...")
    pip_install(missing, args.mirror)

    # 尝试安装可选依赖（talib 等，失败不阻断主流程）
    missing_opt = [name for name, mod in OPTIONAL_DEPS
                   if _importable(mod) is None]
    if missing_opt:
        print(f"\n🟡 尝试安装可选依赖: {', '.join(missing_opt)}（失败不阻断）")
        pip_install(missing_opt, args.mirror)

    print("\n" + "=" * 40)
    return doctor()


if __name__ == "__main__":
    sys.exit(main())
