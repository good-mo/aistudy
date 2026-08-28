"""
终端颜色工具
统一 ANSI 颜色输出，供追踪、筛选等模块的终端报告使用。
"""


class Color:
    """终端 ANSI 颜色，提供涨跌/盈亏着色辅助方法。"""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @staticmethod
    def up(text):
        return f"{Color.RED}{text}{Color.RESET}"

    @staticmethod
    def down(text):
        return f"{Color.GREEN}{text}{Color.RESET}"

    @staticmethod
    def flat(text):
        return f"{Color.YELLOW}{text}{Color.RESET}"

    @staticmethod
    def by_value(value, fmt="{:+.2f}", suffix=""):
        """按数值正负着色（正=红，负=绿，零=黄）。"""
        text = fmt.format(value) + suffix
        if value > 0:
            return Color.up(text)
        elif value < 0:
            return Color.down(text)
        return Color.flat(text)


# 兼容旧脚本类名
TerminalColor = Color
