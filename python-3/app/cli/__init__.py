"""
app.cli —— 统一命令行入口

提供：
    - main()         主入口（argparse 分发）
    - monitor.py     综合监控调度
    - commands/      各子命令实现
"""

from app.cli.main import main

__all__ = ["main"]
