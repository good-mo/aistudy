"""
app.domains.stock_watch —— A股盯盘模块

基于 app.data 层统一接口，提供专业分析师多维度的盯盘能力：
    - monitor.py        股票盯盘监控器（七大因子信号）
    - signals.py        七大因子信号引擎
    - fundamental.py    基本面指标（PE/PB/ROE/估值分位）
    - money_flow.py     资金面（北向/主力/两融）
    - advanced_indicators.py 高级技术指标（ATR/ADX/OBV/BIAS/缺口）
    - risk.py           风险组合（Beta/波动率/VaR/相关性）
"""

from app.domains.stock_watch.monitor import StockWatcher
from app.domains.stock_watch.signals import SignalEngine, SignalParams

__all__ = ["StockWatcher", "SignalEngine", "SignalParams"]
