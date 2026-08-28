"""
app.cli.commands —— 各 CLI 子命令实现
"""

from app.cli.commands.fund import fund_command
from app.cli.commands.hs300 import hs300_command
from app.cli.commands.wealth import wealth_command
from app.cli.commands.stock import stock_command
from app.cli.commands.doctor import doctor_command
from app.cli.commands.monitor import monitor_command
from app.cli.commands.pro import pro_command

__all__ = [
    "fund_command",
    "hs300_command",
    "wealth_command",
    "stock_command",
    "doctor_command",
    "monitor_command",
    "pro_command",
]
