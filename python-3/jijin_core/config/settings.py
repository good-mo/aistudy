"""
全局配置模块
集中管理各数据源 API 端点、缓存路径、费率、筛选常量，
供 data / analysis / screening 各层统一引用。
"""

import os

from common.logging_utils import get_logger

logger = get_logger(__name__)

# ============================================================
# 数据源 API 端点
# ============================================================
# 腾讯财经实时行情
TENCENT_QUOTE_URL = "http://qt.gtimg.cn/q=jj{fund_code}"
TENCENT_ETF_QUOTE_URL = "http://qt.gtimg.cn/q=sh{code},sz{code}"

# 东方财富基金净值
EASTMONEY_FUND_NAV_URL = "http://api.fund.eastmoney.com/f10/lsjz"
EASTMONEY_FUND_NAV_HEADERS = {
    "Referer": "http://fundf10.eastmoney.com/jjjz_{fund_code}.html",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}

# 新浪财经指数历史
SINA_INDEX_KLINE_URL = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"

# ============================================================
# 路径配置
# ============================================================
# 包根目录
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PACKAGE_DIR)

# 缓存目录（默认位于包内 cache/）
CACHE_DIR = os.path.join(PACKAGE_DIR, "cache")

# ============================================================
# 费率（年化管理费率，用于指数基金收益分解）
# ============================================================
# 标准费率基金（沪深300/中证500 等主流宽基）
FUND_REAL_FEE_RATE = 0.006

# ============================================================
# 无风险利率（夏普比率默认）
# ============================================================
RISK_FREE_RATE = 0.02

# ============================================================
# 筛选阈值
# ============================================================
# 跟踪误差 / 跟踪偏离度异常阈值
TE_ABNORMAL_THRESHOLD = 0.05
TD_ABNORMAL_THRESHOLD = 0.05
# NAV 与指数走势一致性（皮尔逊相关系数）下限
NAV_INDEX_CORR_MIN = 0.80

# 估值分位使用天数（5 年）
VALUATION_DAYS = 1825

# 风格基准权重（配置风格资产配置比例）
STYLE_BENCHMARK_WEIGHTS = {
    "大盘价值": {"沪深300": 0.6, "中证红利": 0.2, "中证500": 0.2},
    "大盘成长": {"沪深300": 0.6, "创业板指": 0.2, "中证500": 0.2},
    "小盘": {"中证500": 0.6, "创业板指": 0.2, "沪深300": 0.2},
}


def ensure_cache_dirs() -> None:
    """确保缓存目录存在。"""
    for sub in ("", "manager", "flow", "benchmark", "index", "nav"):
        d = os.path.join(CACHE_DIR, sub)
        os.makedirs(d, exist_ok=True)
    logger.debug("确保缓存目录存在：%s", CACHE_DIR)
