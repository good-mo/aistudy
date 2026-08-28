"""
app.cli.main —— 统一 CLI 主入口

用法：
    python -m app fund --top 20
    python -m app hs300 --top 20
    python -m app wealth
    python -m app stock --once
    python -m app doctor
    python -m app monitor
"""

from __future__ import annotations

import argparse
import sys

from app.core.logging_setup import get_logger, setup_logging

logger = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """构建主参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="app",
        description="金融分析工具箱 · 新一代统一入口",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["fund", "hs300", "wealth", "stock", "monitor", "doctor", "pro", "list"],
        default="list",
        help="子命令",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="传递给子命令的参数",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """主入口。"""
    parsed = build_parser().parse_args(argv)
    command = parsed.command
    rest = list(parsed.args)

    setup_logging()
    logger.info("app CLI 启动: command=%s", command)

    if command == "list":
        print_help()
        return 0

    # 延迟导入避免不必要的初始化
    if command == "fund":
        from app.cli.commands import fund_command
        return fund_command(rest)
    if command == "hs300":
        from app.cli.commands import hs300_command
        return hs300_command(rest)
    if command == "wealth":
        from app.cli.commands import wealth_command
        return wealth_command(rest)
    if command == "stock":
        from app.cli.commands import stock_command
        return stock_command(rest)
    if command == "monitor":
        from app.cli.commands import monitor_command
        return monitor_command(rest)
    if command == "pro":
        from app.cli.commands import pro_command
        return pro_command(rest)
    if command == "doctor":
        from app.cli.commands import doctor_command
        return doctor_command(rest)

    return 1


def print_help() -> None:
    """打印可用命令。"""
    print("📦 金融分析工具箱 · app 统一入口\n")
    print("可用命令：")
    print("  fund     基金分析/筛选/追踪/监控")
    print("           --code 110011      指定基金分析")
    print("           --top 20           基金筛选")
    print("           --index            指数基金筛选")
    print("           --stable           稳健基金精选")
    print("           --track --csv      每日收益追踪")
    print("           --monitor --once   定时监控")
    print("  hs300    沪深300 9大指标技术分析")
    print("  wealth   理财产品汇总/深度分析/监控")
    print("  stock    A股实时盯盘（七大因子信号）")
    print("  monitor  综合监控（基金+沪深300+理财）")
    print("  pro      专业分析师（基本面/资金/技术/风险/宏观）")
    print("  doctor   环境自检")
    print("  list     查看可用命令\n")
    print("用法示例：")
    print("  python -m app fund --code 110011")
    print("  python -m app fund --top 20")
    print("  python -m app fund --track --csv portfolio.csv")
    print("  python -m app fund --monitor --once --csv portfolio.csv")
    print("  python -m app hs300 --top 10")
    print("  python -m app wealth analyze --risk 3")
    print("  python -m app stock --once")
    print("  python -m app pro --code 600519")
    print("  python -m app pro --market")
    print("  python -m app monitor")


if __name__ == "__main__":
    sys.exit(main())
