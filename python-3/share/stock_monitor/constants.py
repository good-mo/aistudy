"""常量定义：API 地址、股票代码映射、默认预警阈值等。"""

# ---------------------------------------------------------------------------
# API 地址
# ---------------------------------------------------------------------------

# 腾讯财经实时行情 API 地址
TENCENT_API = "http://qt.gtimg.cn/q="

# 腾讯财经历史日K线 API（前复权）
TENCENT_KLINE_API = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# 请求会话配置
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

REQUEST_TIMEOUT = 10  # 秒

# ---------------------------------------------------------------------------
# 股票代码转换
# ---------------------------------------------------------------------------

# 上证主板 / 科创板前缀
SH_PREFIXES = ("60", "68")

# 沪深300 指数代码
INDEX_HS300 = "000300"


def to_tencent_code(code: str) -> str:
    """将通用代码转换为腾讯财经代码格式。

    上证: sh + 代码，深证: sz + 代码；指数: sh000300 等。
    """
    # 沪深300指数
    if code == INDEX_HS300:
        return "sh000300"
    # 上证主板 (600xxx, 601xxx, 603xxx) / 科创板 (688xxx)
    if code.startswith(SH_PREFIXES):
        return f"sh{code}"
    # 深证 (000xxx, 001xxx, 002xxx, 003xxx, 300xxx, 301xxx)
    return f"sz{code}"
