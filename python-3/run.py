#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
金融分析工具箱 —— 统一入口
=============================

将本项目四大金融分析子系统整合为统一的命令行工具：

    ├── jijin       基金筛选与追踪（jijin_core）
    ├── share       A股盯盘（share/stock_monitor）
    ├── share300    沪深300 综合分析与信号筛选（share300_core）
    └── lc          理财产品深度分析（lc_core）

用法：
    python run.py <command> [options]

    python run.py jijin --top 20
    python run.py share
    python run.py share300 --workers 10 --top 20
    python run.py lc --code 010855,009665 --risk 3

    python run.py monitor                 # 综合监控：一次跑完基金/理财/沪深300（每天一次即可）
    python run.py monitor --only jijin,lc # 只跑指定子系统
    python run.py list           # 查看可用命令
    python run.py doctor         # 环境自检（依赖/导入检查）
"""

import argparse
import subprocess
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 确保项目根目录与各子包可在 sys.path 中导入
for p in (PROJECT_ROOT,):
    if p not in sys.path:
        sys.path.insert(0, p)

# 初始化统一专业日志（控制台彩色 + 滚动文件）
try:
    from common.logging_utils import setup_logging, get_logger
    setup_logging()
    logger = get_logger("run")
except ImportError:
    # 缺少 common 包时不阻塞运行，退化为标准日志
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("run")


REQUIREMENTS = os.path.join(PROJECT_ROOT, "requirements.txt")

# 运行各子命令前需要可用的核心依赖
CORE_DEPS = [
    ("pandas", "pandas"),
    ("numpy", "numpy"),
    ("requests", "requests"),
    # 金融数据 / 理财分析（jijin/share300/lc 需要）
    ("akshare", "akshare"),
    ("gmssl", "gmssl"),
    ("scipy", "scipy"),
    ("beautifulsoup4", "bs4"),
]


def check_missing_deps():
    """返回缺失的核心依赖包名列表。"""
    missing = []
    for pip_name, import_name in CORE_DEPS:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)
    return missing


SUBCOMMANDS = {
    "jijin": {
        "help": "基金筛选与追踪（jijin_core）",
        "module": "jijin_core.cli.screener",
    },
    "share": {
        "help": "A股实时盯盘（share/stock_monitor）",
        "module": "stock_monitor.main",
        "cwd": os.path.join(PROJECT_ROOT, "share"),
    },
    "share300": {
        "help": "沪深300 综合分析与买卖信号（share300_core）",
        "module": "share300_core.cli.analyzer",
    },
    "lc": {
        "help": "理财产品深度分析（lc_core）",
        "module": "lc_core.cli.analyze",
    },
}


def cmd_list():
    print("📦 可用命令：\n")
    width = max(len(k) for k in SUBCOMMANDS) + 2
    for name, meta in SUBCOMMANDS.items():
        print(f"  {name:<{width}} {meta['help']}")
    print(f"\n  {'monitor':<{width}} 综合每日监控（一次跑完基金/理财/沪深300）")
    print(f"  {'doctor':<{width}} 环境自检（依赖与导入检查）")
    print(f"  {'install':<{width}} 自动安装缺失依赖（bootstrap）")
    print("\n用法示例：")
    print("  python run.py jijin --top 20")
    print("  python run.py share300 --workers 10 --top 20")
    print("  python run.py lc --code 010855,009665 --risk 3")
    print("  python run.py share")
    print("  python run.py monitor")
    print("  python run.py monitor --only jijin,lc")


def cmd_doctor():
    """环境自检：检查依赖是否可用、核心模块能否导入。"""
    print("🔧 环境自检\n")
    checks = [
        ("pandas", "import pandas"),
        ("numpy", "import numpy"),
        ("requests", "import requests"),
        ("akshare", "import akshare"),
        ("gmssl", "import gmssl"),
        ("scipy", "import scipy"),
    ]
    ok = True
    for name, stmt in checks:
        try:
            exec(stmt)
            print(f"  ✅ {name:<10} 可用")
        except ImportError:
            print(f"  ❌ {name:<10} 缺失（pip install {name}）")
            ok = False

    print("\n📦 核心包导入检查：")
    # stock_monitor 位于 share/ 子目录，需将其加入 sys.path
    share_dir = os.path.join(PROJECT_ROOT, "share")
    if share_dir not in sys.path:
        sys.path.insert(0, share_dir)
    for pkg in ("jijin_core", "share300_core", "lc_core", "stock_monitor"):
        try:
            __import__(pkg)
            print(f"  ✅ {pkg:<14} 导入正常")
        except Exception as e:
            print(f"  ❌ {pkg:<14} 导入失败: {e}")
            ok = False

    print("\n" + ("✅ 环境正常，可运行。" if ok else "⚠️ 存在缺失依赖，请先安装。"))
    return 0 if ok else 1


# 综合每日监控：各子系统以 --once 模式各跑一次快照，汇总结果。
# 适用场景：基金/理财等每天看一次即可的监控，用 cron / 手动每天跑一次。
DAILY_MONITORS = [
    {
        "key": "jijin",
        "name": "基金监控",
        "module": "jijin_core.cli.monitor",
        "cwd": PROJECT_ROOT,
        # 默认使用项目根目录的持仓 CSV（可通过 --csv 覆盖）
        "args": ["--once", "--quiet"],
    },
    {
        "key": "lc",
        "name": "理财产品监控",
        "module": "lc_core.cli.monitor",
        "cwd": PROJECT_ROOT,
        # lc 监控暂无 --quiet 参数，仅传 --once
        "args": ["--once"],
    },
    {
        "key": "share300",
        "name": "沪深300 综合监控",
        "module": "share300_core.cli.analyzer",
        "cwd": PROJECT_ROOT,
        "args": ["--top", "20"],
    },
]

# 盘中实时盯盘（A股），不适合每天一次，仅作为可选提示项
REALTIME_MONITOR = {
    "key": "share",
    "name": "A股实时盯盘",
    "module": "stock_monitor.main",
    "cwd": os.path.join(PROJECT_ROOT, "share"),
}


def cmd_monitor(args):
    """统一运行综合监控：每天跑一次，逐个执行各每日监控子系统。

    参数（通过 run.py 剩余参数解析）：
        --only jijin,lc   仅运行指定子系统（逗号分隔）
        --console-only    全部以终端模式运行，不触发桌面通知
        --csv PATH        指定持仓 CSV（基金/理财共用）
    """
    rest = list(args)

    # --only 指定子系统白名单
    only = None
    if "--only" in rest:
        i = rest.index("--only")
        only = [k.strip() for k in rest[i + 1].split(",") if k.strip()]
        del rest[i : i + 2]

    console_only = "--console-only" in rest
    if console_only:
        rest.remove("--console-only")

    # --csv 覆盖持仓路径，传递给需要持仓文件的子系统
    csv_arg = None
    if "--csv" in rest:
        i = rest.index("--csv")
        csv_arg = rest[i + 1]
        del rest[i : i + 2]

    print("=" * 72)
    print("📊 综合监控 · 每日运行入口")
    print("=" * 72)
    print("💡 基金/理财每天看一次即可，本命令将依次完成全部每日监控快照。")
    print("   建议配合 cron 每天定时执行一次，或在每日收盘后手动运行。\n")

    if only:
        items = [m for m in DAILY_MONITORS if m["key"] in only]
        print(f"🔍 仅运行: {', '.join(m['key'] for m in items)}\n")
    else:
        items = DAILY_MONITORS

    if not items:
        print("❌ --only 未匹配到任何已知子系统，可用: " + ",".join(m["key"] for m in DAILY_MONITORS))
        return 1

    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        PROJECT_ROOT if not existing else PROJECT_ROOT + os.pathsep + existing
    )

    results = []
    for item in items:
        name = item["name"]
        print("-" * 72)
        print(f"▶ [{item['key']}] {name}")
        print("-" * 72)
        argv = [sys.executable, "-m", item["module"]]
        if csv_arg and item["key"] in ("jijin", "lc"):
            argv += ["--csv", csv_arg]
        # 仅基金/理财监控支持 --console-only；share300 分析器无此参数
        if console_only and item["key"] in ("jijin", "lc"):
            argv += ["--console-only"]
        argv += item["args"]
        logger.info("综合监控运行 [%s] %s", item["key"], name)
        ret = subprocess.call(argv, cwd=item["cwd"], env=env)
        results.append((item["key"], name, ret))
        print()

    # 汇总结果
    print("=" * 72)
    print("📋 综合监控汇总")
    print("=" * 72)
    failed = 0
    for key, name, ret in results:
        status = "✅ 完成" if ret == 0 else f"⚠️ 失败(码{ret})"
        if ret != 0:
            failed += 1
        print(f"  [{key}] {name:<12} {status}")
    print("=" * 72)
    if failed:
        print(f"⚠️ 共 {len(results)} 个子系统，{failed} 个执行异常，请查看上方日志。")
        return 1
    print("✅ 全部子系统监控完成，今日数据已刷新。\n")
    print("💡 如需盘中实时盯盘，请单独运行:  python run.py share")
    return 0


def cmd_install():
    """自动安装缺失依赖（复用 bootstrap.py 逻辑）。"""
    bootstrap = os.path.join(PROJECT_ROOT, "bootstrap.py")
    if os.path.exists(bootstrap):
        print("🚀 调用 bootstrap.py 自动安装依赖...\n")
        return subprocess.call([sys.executable, bootstrap])

    # 兜底：直接 pip install requirements.txt
    print("🚀 未找到 bootstrap.py，直接安装 requirements.txt...\n")
    if not os.path.exists(REQUIREMENTS):
        print("❌ 未找到 requirements.txt，无法安装。")
        return 1
    return subprocess.call([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS])


def pip_install(packages, mirror=None):
    """使用 pip 安装指定包，支持镜像源与失败回退。"""
    cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir"]
    if mirror:
        cmd += ["-i", mirror]
    cmd += packages
    logger.info("执行 pip 安装: %s", " ".join(cmd))
    print(f"📦 执行: {' '.join(cmd)}")
    return subprocess.call(cmd) == 0


def auto_install(missing):
    """自动安装缺失的核心依赖（含镜像源回退）。"""
    if not missing:
        return True
    print(f"🚀 检测到缺失核心依赖: {', '.join(missing)}，正在自动安装...\n")
    # 优先只装缺失的包，加速；失败再回退镜像源
    if pip_install(missing):
        return True
    print("\n默认源安装失败，尝试腾讯云镜像源...")
    return pip_install(missing, mirror="https://mirrors.cloud.tencent.com/pypi/simple/")


def install_full_requirements(mirror=None):
    """安装完整依赖（复用 bootstrap.py，talib 作为可选依赖单独容错安装）。"""
    bootstrap = os.path.join(PROJECT_ROOT, "bootstrap.py")
    if os.path.exists(bootstrap):
        args = [sys.executable, bootstrap]
        if mirror:
            args += ["--mirror", mirror]
        print(f"\n🚀 同步安装完整依赖（bootstrap.py）...")
        subprocess.call(args)
        return True
    # 兜底：从 requirements.txt 剔除 talib 后整批安装
    if not os.path.exists(REQUIREMENTS):
        return True
    pkgs = []
    with open(REQUIREMENTS, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name = line.split(">=")[0].split("==")[0].split("<")[0].strip()
            if name and name.lower() != "talib":
                pkgs.append(name)
    cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir"]
    if mirror:
        cmd += ["-i", mirror]
    cmd += pkgs
    logger.info("执行完整依赖安装: %s", " ".join(cmd))
    print(f"📦 执行: {' '.join(cmd)}")
    return subprocess.call(cmd) == 0


def ensure_deps(auto=True):
    """执行命令前检查核心依赖；缺失时自动安装（默认开启），失败或关闭时给出提示。"""
    missing = check_missing_deps()
    if not missing:
        return True
    if auto and auto_install(missing):
        # 再安装完整 requirements.txt，确保 akshare/gmssl/scipy/talib 等就绪
        install_full_requirements()
        # 安装后重新检查，确认已就绪
        still_missing = check_missing_deps()
        if not still_missing:
            print("✅ 依赖已自动安装完成，继续运行。\n")
            return True
        missing = still_missing
    print(f"⚠️ 缺失核心依赖: {', '.join(missing)}\n")
    print("  可手动执行:  python run.py install  或  python bootstrap.py")
    return False


def main():
    parser = argparse.ArgumentParser(prog="run.py", description="金融分析工具箱统一入口")
    parser.add_argument("command", nargs="?", help="子命令：jijin / share / share300 / lc / list / doctor")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="传递给子命令的参数")
    args = parser.parse_args()

    cmd = args.command or "list"

    # 从剩余参数中解析自动安装开关：
    #   --auto    ：缺依赖时自动安装（默认开启）
    #   --no-auto ：关闭自动安装，缺依赖仅提示
    rest = list(args.args)
    auto_install_flag = True
    if "--no-auto" in rest:
        auto_install_flag = False
        rest.remove("--no-auto")
    if "--auto" in rest:
        auto_install_flag = True
        rest.remove("--auto")

    if cmd == "list":
        cmd_list()
        return 0
    if cmd == "doctor":
        return cmd_doctor()
    if cmd == "install":
        # install 本身就是安装命令，--auto 仅作兼容，直接执行安装
        return cmd_install()
    if cmd == "monitor":
        # 综合每日监控：需解析 --only/--console-only/--csv 等自身参数
        # 缺依赖时自动安装（默认开启），保证各子系统可运行
        if not ensure_deps(auto=auto_install_flag):
            return 1
        return cmd_monitor(rest)

    meta = SUBCOMMANDS.get(cmd)
    if not meta:
        print(f"❌ 未知命令: {cmd}\n")
        cmd_list()
        return 1

    # 执行前检查核心依赖是否齐全（缺失时自动安装，默认开启）
    if not ensure_deps(auto=auto_install_flag):
        return 1

    # 拼装子命令调用
    module = meta["module"]
    cwd = meta.get("cwd", PROJECT_ROOT)
    argv = [sys.executable, "-m", module] + rest

    # 确保子进程（cwd 可能切换到子包目录）也能导入项目根目录下的
    # 公共模块（如 common/logging_utils）。将项目根目录注入 PYTHONPATH。
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        PROJECT_ROOT
        if not existing
        else PROJECT_ROOT + os.pathsep + existing
    )

    print(f"▶ 运行 {cmd}（{module}）\n")
    logger.info("启动子命令 %s（module=%s, cwd=%s）", cmd, module, cwd)
    ret = subprocess.call(argv, cwd=cwd, env=env)
    logger.info("子命令 %s 执行结束，返回码=%s", cmd, ret)
    return ret


if __name__ == "__main__":
    sys.exit(main())
