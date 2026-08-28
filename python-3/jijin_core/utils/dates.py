"""
日期工具
交易日判断、日期格式化等通用函数。
"""

from datetime import datetime, timedelta


def today_str() -> str:
    """返回今天日期字符串 YYYY-MM-DD。"""
    return datetime.now().strftime("%Y-%m-%d")


def date_n_days_ago(days: int) -> str:
    """返回 N 天前的日期字符串。"""
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


def start_end_date(days: int = 1825) -> tuple:
    """返回 (起始日期, 结束日期)，默认向前 5 年。"""
    end = datetime.now()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def parse_date(value: str) -> datetime:
    """解析常见日期字符串为 datetime。"""
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {value}")
