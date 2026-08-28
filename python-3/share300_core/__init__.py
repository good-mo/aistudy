"""
share300_core —— 沪深300 成分股专业分析工具箱
=============================================

对 share300/ 目录下分散脚本的专业化重构，基于 9 大技术指标 + 基本面
对沪深300 成分股进行买入 / 卖出信号筛选。

分层架构：

    share300_core/
    ├── config/      配置与常量（API 地址、成分股列表、默认参数）
    ├── data/        数据获取层（腾讯 K 线 / 东方财富成分股与财务）
    ├── analysis/    分析层（技术指标、信号判定、基本面评分）
    ├── signals/     买卖信号子系统（多因子综合）
    ├── cli/         命令行入口
    └── __init__.py  包入口

依赖：pip install pandas numpy requests akshare
"""

from share300_core.analysis.analyzer import HS300Analyzer

__all__ = ["HS300Analyzer"]
__version__ = "1.0.0"
