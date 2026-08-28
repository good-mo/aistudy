"""
jijin_core —— 专业基金分析工具箱（对 jijin/ 脚本集的专业化重构）

围绕基金经理方法论构建的基金筛选 / 追踪 / 分析体系，按分层架构组织：

    jijin_core/
    ├── config/      全局配置（API 端点、缓存、费率、常量）
    ├── data/        数据获取层（腾讯 / 东方财富 / akshare / 新浪 + 缓存）
    ├── analysis/    分析层（绩效指标、评分、信号、经理画像、宏观、行业、资金流）
    ├── screening/   筛选策略层（指数基金筛选、稳健基金精选、主筛选流程）
    ├── tracking/    追踪层（每日收益追踪、报表导出）
    ├── utils/       通用工具（终端颜色、缓存、日期）
    └── cli/         命令行入口

设计原则：
    - 分层清晰：数据 / 分析 / 策略 / 展示 相互解耦
    - 复用提炼：抽取各脚本重复的 Color、指标计算、缓存逻辑为公共模块
    - 入口统一：所有功能通过 cli/ 下的入口脚本调用

依赖：pip install pandas numpy requests akshare
"""

__version__ = "1.0.0"
__all__ = ["config", "data", "analysis", "screening", "tracking", "utils"]
