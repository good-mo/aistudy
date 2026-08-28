"""
A股盯盘程序 - 模块化专业架构包
================================

将原本的单文件 stock_monitor.py 拆分为清晰的职责模块：

- constants   : 常量（API 地址、股票代码映射、默认配置）
- config      : 配置管理与加载
- api         : 腾讯财经行情 / K线数据客户端
- indicators  : 技术指标计算（EMA/SMA/MACD/KDJ/RSI/布林带）
- notifier    : 桌面通知
- display     : 终端展示与格式化
- signals     : 多因子买卖信号分析（MA/MACD/KDJ/RSI/布林带/成交量 + 评分引擎）
- monitor     : 主监控器，编排整个盯盘流程
- main        : 命令行入口
"""

from stock_monitor.monitor import StockMonitor
from stock_monitor.config import MonitorConfig

__all__ = [
    "StockMonitor",
    "MonitorConfig",
]

__version__ = "1.0.0"
