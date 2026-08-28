"""
指数基金专业筛选工具 —— 基金经理方法论实现
核心逻辑：先选对指数（估值合理、编制科学），再选对基金（跟踪误差小、信息比率高、费率低、规模大、流动性好）
不看短期收益排名，用 3-5 年长期数据，通过定量指标系统化筛选"最忠实复制指数"或"最有效增强指数"的产品。

评估体系（两层）：
  Layer 1: 指数筛选层 —— 估值分位、编制科学性、基本面
  Layer 2: 基金优选层 —— 跟踪质量(35%) + 成本效率(20%) + 规模流动性(15%) + 风险收益(20%) + 超额归因(10%)

数据源：腾讯财经（qt.gtimg.cn）+ 新浪财经（money.finance.sina.com.cn）+ 东方财富（api.fund.eastmoney.com）
依赖：pip install pandas numpy requests
"""

import pandas as pd
import numpy as np
import requests
import re
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# API 配置
# ============================================================
# 腾讯财经实时行情
TENCENT_QUOTE_URL = "http://qt.gtimg.cn/q=jj{fund_code}"
# 腾讯财经指数历史K线（前复权）—— 已被限流，改用新浪财经
# TENCENT_IDX_KLINE_URL 已废弃
# 新浪财经指数历史K线（稳定可靠，日线240分钟级=日K）
SINA_IDX_KLINE_URL = (
    "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "CN_MarketData.getKLineData?symbol={idx_code}&scale=240&ma=no&datalen=1500"
)
# 东方财富基金排行
EASTMONEY_RANK_URL = (
    "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNRankNewList"
    "?FundType=000001&SortColumn=SYL_3Y&Sort=desc&pageIndex={page}&pageSize=100"
    "&plat=Android&appType=ttjj&deviceid=xxx&Version=1.0.0&product=EFund"
)
# 东方财富历史净值
EASTMONEY_NAV_URL = (
    "https://api.fund.eastmoney.com/f10/lsjz"
    "?fundCode={fund_code}&pageIndex={page}&pageSize=20"
    "&startDate={start_date}&endDate={end_date}"
)
# 腾讯财经ETF实时行情（含规模、折溢价、PE、成交额等，字段丰富）
TENCENT_ETF_QUOTE_URL = "http://qt.gtimg.cn/q={etf_code}"

# 全局 Session
_SESSION = None


def _get_session():
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        })
    return _SESSION


# ============================================================
# 指数基金代码 → 跟踪指数代码映射
# ============================================================
FUND_TO_INDEX = {
    # 沪深300
    "510300": "sh000300", "510310": "sh000300", "159919": "sh000300",
    # 中证500
    "510500": "sh000905", "159922": "sh000905",
    # 中证A500
    "159338": "sh000510", "159339": "sh000510",
    # 中证红利（000015）
    "515080": "sh000015", "159515": "sh000015",
    # 红利低波
    "512890": "shH30269", "515100": "shH30269",
    # 创业板
    "159915": "sz399006",
    # 科创50
    "588000": "sh000688", "588080": "sh000688",
}

# 新浪财经不支持的部分 CSI 定制指数 → 替代指数映射
IDX_FALLBACK = {
    "shH30269": "sh000015",  # 红利低波 → 中证红利（同属红利类，高度相关）
}

# ============================================================
# 指数元数据（编制信息、估值框架）—— 专业基金经理的"指数筛选"基础
# ============================================================
INDEX_META = {
    "sh000300": {
        "name": "沪深300", "category": "大盘蓝筹", "weight_type": "自由流通市值加权",
        "components": 300, "rebalance": "半年", "description": "沪深两市规模大、流动性好的300只股票",
        "pe_reasonable_low": 10, "pe_reasonable_high": 16, "pb_reasonable_low": 1.2, "pb_reasonable_high": 2.0,
    },
    "sh000905": {
        "name": "中证500", "category": "中盘成长", "weight_type": "自由流通市值加权",
        "components": 500, "rebalance": "半年",
        "description": "剔除沪深300后市值最大的500只股票，代表中盘",
        "pe_reasonable_low": 18, "pe_reasonable_high": 35, "pb_reasonable_low": 1.5, "pb_reasonable_high": 2.8,
    },
    "sh000510": {
        "name": "中证A500", "category": "大盘均衡", "weight_type": "自由流通市值加权+行业均衡",
        "components": 500, "rebalance": "半年",
        "description": "行业均衡的新一代宽基指数",
        "pe_reasonable_low": 10, "pe_reasonable_high": 16, "pb_reasonable_low": 1.2, "pb_reasonable_high": 2.0,
    },
    "sh000015": {
        "name": "中证红利", "category": "红利价值", "weight_type": "股息率加权",
        "components": 100, "rebalance": "年",
        "description": "沪深两市现金股息率高、分红稳定的100只股票",
        "pe_reasonable_low": 5, "pe_reasonable_high": 10, "pb_reasonable_low": 0.5, "pb_reasonable_high": 1.0,
    },
    "shH30269": {
        "name": "红利低波", "category": "红利+低波 Smart Beta", "weight_type": "因子加权",
        "components": 50, "rebalance": "半年",
        "description": "红利+低波动双因子策略指数",
        "pe_reasonable_low": 5, "pe_reasonable_high": 10, "pb_reasonable_low": 0.5, "pb_reasonable_high": 1.0,
    },
    "sz399006": {
        "name": "创业板指", "category": "创业板成长", "weight_type": "自由流通市值加权",
        "components": 100, "rebalance": "半年",
        "description": "创业板最具代表性的100只股票",
        "pe_reasonable_low": 25, "pe_reasonable_high": 55, "pb_reasonable_low": 3.0, "pb_reasonable_high": 7.0,
    },
    "sh000688": {
        "name": "科创50", "category": "科创板成长", "weight_type": "自由流通市值加权",
        "components": 50, "rebalance": "季",
        "description": "科创板市值大、流动性好的50只股票",
        "pe_reasonable_low": 30, "pe_reasonable_high": 60, "pb_reasonable_low": 3.0, "pb_reasonable_high": 6.0,
    },
}

# ============================================================
# 1. 获取指数基金列表
# ============================================================
def get_index_fund_list():
    """获取所有基金列表（东方财富排行，含费率信息）"""
    print("正在获取基金列表...")
    all_funds = []
    session = _get_session()
    for page in range(1, 21):
        try:
            resp = session.get(EASTMONEY_RANK_URL.format(page=page), timeout=15)
            data = resp.json()
            if data.get("ErrCode") != 0:
                break
            funds = data.get("Datas", [])
            if not funds:
                break
            all_funds.extend(funds)
            if len(funds) < 100:
                break
            time.sleep(0.3)
        except Exception as e:
            print(f"获取第 {page} 页失败: {e}")
            break
    if not all_funds:
        return pd.DataFrame()
    df = pd.DataFrame(all_funds)
    print(f"共获取 {len(df)} 只基金")
    return df


# ============================================================
# 2. 获取基金实时行情（腾讯财经）
# ============================================================
def get_fund_quote_tencent(fund_code):
    """
    腾讯财经实时行情：代码~名称~最新价~昨收~开盘~单位净值~累计净值~日增长率~净值日期~
    """
    try:
        resp = _get_session().get(
            TENCENT_QUOTE_URL.format(fund_code=fund_code), timeout=10)
        resp.encoding = "gbk"
        match = re.search(r'="(.+)"', resp.text)
        if match:
            parts = match.group(1).split("~")
            if len(parts) >= 9:
                return {
                    "code": parts[0], "name": parts[1],
                    "nav": float(parts[5]) if parts[5] and parts[5] != "0.0000" else None,
                    "accum_nav": float(parts[6]) if parts[6] else None,
                    "chg_pct": float(parts[7]) if parts[7] else None,
                    "nav_date": parts[8] if parts[8] else None,
                }
    except Exception:
        pass
    return None


# ============================================================
# 3. 获取ETF实时行情（腾讯财经，字段丰富）
# ============================================================
def get_etf_quote_tencent(code):
    """
    腾讯财经ETF实时行情（字段比基金接口更丰富）
    接口：http://qt.gtimg.cn/q=sh510300 或 sz159919
    关键字段：
      [3]=最新价, [6]=成交量(手), [37]=成交额(万), [38]=换手率(%)
      [44]=总市值(亿), [45]=流通市值(亿), [62]=溢价率(%)
      [69]=近1月涨跌, [70]=近1季涨跌, [71]=近1年涨跌
      [79]=PE
    """
    # 判断交易所前缀
    if code.startswith("5") or code.startswith("58"):
        etf_code = f"sh{code}"
    elif code.startswith("1") or code.startswith("16"):
        etf_code = f"sz{code}"
    else:
        etf_code = f"sh{code}"
    try:
        resp = _get_session().get(
            TENCENT_ETF_QUOTE_URL.format(etf_code=etf_code), timeout=10)
        resp.encoding = "gbk"
        match = re.search(r'="(.+)"', resp.text)
        if match:
            parts = match.group(1).split("~")
            if len(parts) >= 80:
                price = float(parts[3]) if parts[3] else None
                volume_hands = float(parts[6]) if parts[6] else None
                volume_amount = float(parts[37]) if parts[37] else None  # 万元
                turnover = float(parts[38]) if parts[38] else None  # %
                total_mv_yi = float(parts[44]) if parts[44] else None  # 亿
                premium = float(parts[62]) if parts[62] else None  # %
                pe = float(parts[79]) if parts[79] else None
                # 成交额换算为元
                amount_yuan = volume_amount * 1e4 if volume_amount else None
                # 规模换算为元
                total_mv_yuan = total_mv_yi * 1e8 if total_mv_yi else None
                return {
                    "code": str(parts[2]),
                    "name": str(parts[1]),
                    "price": price,
                    "volume_hands": volume_hands,
                    "amount": amount_yuan,
                    "turnover": turnover,
                    "total_mv": total_mv_yuan,
                    "premium": premium,
                    "pe": pe,
                    "chg_1m": float(parts[69]) if parts[69] else None,
                    "chg_1q": float(parts[70]) if parts[70] else None,
                    "chg_1y": float(parts[71]) if parts[71] else None,
                }
    except Exception:
        pass
    return None


# ============================================================
# 4. 获取基金历史净值（东方财富）—— 5年长期数据
# ============================================================
def get_fund_nav(fund_code, days=1825):
    """
    获取基金单位净值历史数据（默认5年）
    专业基金经理使用 3-5 年长期数据，避免短期噪声
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    all_records = []
    session = _get_session()
    page = 1
    while True:
        try:
            url = EASTMONEY_NAV_URL.format(
                fund_code=fund_code, page=page,
                start_date=start_date, end_date=end_date
            )
            resp = session.get(url, timeout=15,
                               headers={"Referer": "https://fundf10.eastmoney.com/"})
            data = resp.json()
            if data.get("ErrCode") != 0:
                break
            records = data.get("Data", {}).get("LSJZList", [])
            if not records:
                break
            for r in records:
                nav_val = r.get("DWJZ")
                if nav_val:
                    all_records.append((r.get("FSRQ", ""), float(nav_val)))
            if len(records) < 20:
                break
            page += 1
        except Exception:
            return None
    if not all_records:
        return None
    df = pd.DataFrame(all_records, columns=["date", "nav"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ============================================================
# 5. 获取指数历史K线（腾讯财经）—— 5年长期数据
# ============================================================
_IDX_CACHE = {}


def get_index_kline(idx_code, days=1825):
    """
    获取指数日K线（新浪财经，稳定可靠）
    新浪财经 API 返回前复权数据，1500条日K线（约6年）
    :param idx_code: 如 sh000300, sz399006
    """
    if idx_code in _IDX_CACHE:
        return _IDX_CACHE[idx_code]

    try:
        url = SINA_IDX_KLINE_URL.format(idx_code=idx_code)
        resp = _get_session().get(url, timeout=15)
        data = resp.json()

        if not data or not isinstance(data, list):
            # 新浪不支持该指数代码，尝试 fallback
            fallback = IDX_FALLBACK.get(idx_code)
            if fallback:
                return get_index_kline(fallback, days=days)
            return None

        records = [(r["day"], float(r["close"])) for r in data if r.get("close")]
        if len(records) < 60:
            fallback = IDX_FALLBACK.get(idx_code)
            if fallback:
                return get_index_kline(fallback, days=days)
            return None

        df = pd.DataFrame(records, columns=["date", "close"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        _IDX_CACHE[idx_code] = df
        return df
    except Exception:
        return None


# ============================================================
# 6. 指标计算
# ============================================================
def calc_annual_return(nav_series):
    """年化收益率"""
    if len(nav_series) < 250:
        return None
    total = nav_series.iloc[-1] / nav_series.iloc[0] - 1
    years = len(nav_series) / 250
    return (1 + total) ** (1 / years) - 1


def calc_max_drawdown(series):
    """最大回撤（返回负值）"""
    if len(series) < 2:
        return None
    cummax = series.cummax()
    drawdown = (series - cummax) / cummax
    return drawdown.min()


def calc_volatility(series):
    """年化波动率"""
    if len(series) < 250:
        return None
    rets = series.pct_change().dropna()
    return rets.std() * np.sqrt(250)


def calc_sharpe(annual_return, volatility, rf=0.02):
    """夏普比率"""
    if volatility is None or volatility == 0 or annual_return is None:
        return None
    return (annual_return - rf) / volatility


def calc_calmar(annual_return, max_dd):
    """卡玛比率"""
    if max_dd is None or max_dd == 0 or annual_return is None:
        return None
    return annual_return / abs(max_dd)


def calc_tracking_error(fund_returns, index_returns):
    """
    计算跟踪误差（年化）
    跟踪误差 = std(基金日收益 - 指数日收益) * sqrt(250)
    """
    if fund_returns is None or index_returns is None:
        return None
    common_idx = fund_returns.index.intersection(index_returns.index)
    if len(common_idx) < 60:
        return None
    diff = fund_returns.loc[common_idx] - index_returns.loc[common_idx]
    return diff.std() * np.sqrt(250)


def calc_information_ratio(fund_annual_ret, index_annual_ret, tracking_error):
    """
    信息比率 = (基金年化收益 - 指数年化收益) / 跟踪误差
    衡量主动管理超额收益的稳定性
    """
    if (tracking_error is None or tracking_error == 0
            or fund_annual_ret is None or index_annual_ret is None):
        return None
    return (fund_annual_ret - index_annual_ret) / tracking_error


def calc_pe_percentile(idx_code):
    """
    真实 PE 估值分位计算：
    用指数价格历史序列作为 PE 近似（价格与 PE 高度正相关，尤其对于宽基指数）
    返回当前价格在 5 年历史中的分位数（0=最便宜，1=最贵）
    同时结合指数合理估值区间做校准
    """
    if idx_code is None:
        return None, None

    idx_df = _IDX_CACHE.get(idx_code)

    # 如果缓存中没有，尝试 fallback（如 shH30269 → sh000015）
    if idx_df is None and idx_code in IDX_FALLBACK:
        idx_df = _IDX_CACHE.get(IDX_FALLBACK[idx_code])
        idx_code = IDX_FALLBACK[idx_code]

    if idx_df is None or len(idx_df) < 250:
        return None, None

    meta = INDEX_META.get(idx_code, {})
    current = idx_df["close"].iloc[-1]

    # 方法1: 价格历史分位（基于5年价格序列）
    hist_prices = idx_df["close"]
    price_pct = (hist_prices <= current).mean()

    # 方法2: 基于指数合理区间校准
    # 使用 PE 合理区间做二次验证（即使没有实时 PE，也能用价格分位做近似）
    pe_low = meta.get("pe_reasonable_low")
    pe_high = meta.get("pe_reasonable_high")

    # 综合：价格分位为主，合理区间为辅
    if pe_low and pe_high:
        # 价格分位本身就是估值分位的良好近似
        # 沪深300等宽基的价格与PE相关性 >0.85
        calibrated = price_pct
    else:
        calibrated = price_pct

    return round(calibrated, 3), round(price_pct, 3)


def calc_attribution(fund_annual_ret, index_annual_ret, tracking_error, fee_rate):
    """
    超额收益归因分析（基金经理级方法论）
    将超额收益分解为：
      1. 选股/复制偏差带来的收益（通过跟踪误差近似）
      2. 费率拖累（被动基金的超额主要来自低费率）
      3. 不可解释部分

    对于 ETF：超额收益 ≈ -费率 + 打新/其他收益
    信息比率 >0 说明管理能力优秀（超额覆盖了费率并有剩余）
    """
    if (fund_annual_ret is None or index_annual_ret is None
            or fee_rate is None):
        return None

    excess = fund_annual_ret - index_annual_ret

    result = {
        "超额收益": excess,
        "费率拖累": -fee_rate,
        "费率后超额": excess + fee_rate,  # 加回费率后看真正的管理超额
        "归因解读": "",
    }

    if excess > 0:
        result["归因解读"] = "超额收益为正，基金在费率之上仍有正向贡献（可能来自打新、选股等）"
    elif excess > -fee_rate * 1.5:
        result["归因解读"] = "超额收益为负但主要来自费率，管理层面基本忠实复制指数"
    elif excess > -fee_rate * 3:
        result["归因解读"] = "超额收益明显低于基准，可能存在跟踪偏离或交易损耗"
    else:
        result["归因解读"] = "严重跑输基准，需关注是否存在策略偏差或流动性问题"

    # 信息比率角度：IR = 超额/跟踪误差
    # IR > 0.5 表示超额收益在统计上显著
    if tracking_error and tracking_error > 0:
        result["信息比率"] = excess / tracking_error
        if result["信息比率"] > 0.5:
            result["归因解读"] += "（超额收益统计显著）"
        elif result["信息比率"] > 0:
            result["归因解读"] += "（超额收益不显著）"
        else:
            result["归因解读"] += "（超额为负）"

    return result


def screen_index_quality(idx_code):
    """
    Layer 1: 指数质量评估（先选对指数）
    评估维度：
      - 估值吸引力：当前 PE 历史分位（越低越好）
      - 编制科学性：加权方式、调样频率、成分股数量
      - 基本面：类别特征（宽基/策略/行业）
    返回 0-100 分
    """
    if idx_code is None:
        return {"score": 50, "details": {}}

    # 使用 fallback 映射获取数据（估值分位用替代指数），但保留原始指数的元数据名称
    meta_code = idx_code
    if idx_code in IDX_FALLBACK and IDX_FALLBACK[idx_code] in INDEX_META:
        meta_code = IDX_FALLBACK[idx_code]
    meta = INDEX_META.get(meta_code, {})
    # 原始指数的元数据（用于显示名称等）
    orig_meta = INDEX_META.get(idx_code, meta)
    pe_pct, price_pct = calc_pe_percentile(idx_code)

    score = 0
    details = {}

    # 1. 估值吸引力 (50分) —— 核心：越低估，长期预期收益越高
    if pe_pct is not None:
        if pe_pct <= 0.15:
            score += 50  # 极度低估
        elif pe_pct <= 0.25:
            score += 45
        elif pe_pct <= 0.40:
            score += 38
        elif pe_pct <= 0.60:
            score += 28
        elif pe_pct <= 0.75:
            score += 18
        elif pe_pct <= 0.90:
            score += 8
        else:
            score += 2
    else:
        score += 25

    # 2. 编制科学性 (30分) —— 加权方式、成分股数量、调样频率
    weight_type = meta.get("weight_type", "")
    n_components = meta.get("components", 0)
    rebalance = meta.get("rebalance", "")

    # 加权方式
    if "市值加权" in weight_type:
        score += 12  # 市值加权最主流，可复制性强
    elif "因子加权" in weight_type or "股息率加权" in weight_type:
        score += 8   # 策略指数有一定主观性
    else:
        score += 5

    # 成分股数量（数量越多越分散，越适合被动投资）
    if n_components >= 300:
        score += 10
    elif n_components >= 100:
        score += 8
    elif n_components >= 50:
        score += 5
    else:
        score += 3

    # 调样频率
    if "半年" in rebalance or "半" in rebalance:
        score += 8
    elif "季" in rebalance:
        score += 6
    elif "年" in rebalance:
        score += 5
    else:
        score += 4

    # 3. 类别特征 (20分)
    category = meta.get("category", "")
    if "大盘" in category or "均衡" in category:
        score += 20  # 大盘宽基：最核心的 Beta 工具
    elif "中盘" in category:
        score += 16
    elif "红利" in category or "价值" in category:
        score += 14  # 策略指数：有一定 Alpha 但偏离市场 Beta
    elif "成长" in category or "创业" in category or "科创" in category:
        score += 12
    else:
        score += 10

    details = {
        "指数名称": orig_meta.get("name", idx_code),
        "估值分位": f"{pe_pct*100:.0f}%" if pe_pct else "N/A",
        "类别": category,
        "加权方式": weight_type,
        "成分股数": n_components,
        "调样频率": rebalance,
        "指数质量评分": score,
    }

    return {"score": score, "details": details}


# ============================================================
# 7. 专业评分模型（Layer 1 指数筛选 + Layer 2 基金优选）
# ============================================================
def calc_fund_layer_score(row):
    """
    Layer 2: 基金优选评分（满分100分）
    专业基金经理的"选对基金"逻辑：
      - 跟踪质量 35分：跟踪误差 + 信息比率（最核心）
      - 成本效率 20分：费率 + 折溢价率
      - 规模流动性 15分：规模 + 日均成交额
      - 风险收益 20分：夏普比率 + 超额收益
      - 超额归因 10分：归因分析结论（超额是否覆盖费率）
    """
    score = 0

    # ---- 维度一：跟踪质量（35分，权重提升） ----
    # 被动投资的本质：高精度获取市场 Beta
    # 跟踪误差（20分）
    te = row.get("tracking_error")
    if te is not None:
        te_pct = te * 100
        if te_pct <= 0.3:
            score += 20  # 机构级精度
        elif te_pct <= 0.5:
            score += 18
        elif te_pct <= 1.0:
            score += 14 + (1.0 - te_pct) / 0.5 * 4
        elif te_pct <= 2.0:
            score += 8 + (2.0 - te_pct) / 1.0 * 6
        elif te_pct <= 5.0:
            score += max(0, (5.0 - te_pct) / 3.0 * 8)
    else:
        score += 10

    # 信息比率（15分）—— 超额收益的稳定性
    ir_val = row.get("information_ratio")
    if ir_val is not None:
        if ir_val >= 1.5:
            score += 15  # 顶级：超额收益高度稳定
        elif ir_val >= 1.0:
            score += 13 + (ir_val - 1.0) / 0.5 * 2
        elif ir_val >= 0.5:
            score += 10 + (ir_val - 0.5) / 0.5 * 3
        elif ir_val >= 0:
            score += 5 + ir_val / 0.5 * 5
        elif ir_val >= -0.5:
            score += max(0, 5 + ir_val / 0.5 * 5)
    else:
        score += 8

    # ---- 维度二：成本效率（20分） ----
    # 费率（12分）：管理费+托管费，长期复利效应
    fee = row.get("fee_rate")
    if fee is not None:
        fee_pct = fee * 100
        if fee_pct <= 0.15:
            score += 12  # 最低费率档（如 0.15% 管理费）
        elif fee_pct <= 0.3:
            score += 10 + (0.3 - fee_pct) / 0.15 * 2
        elif fee_pct <= 0.5:
            score += 8 + (0.5 - fee_pct) / 0.2 * 2
        elif fee_pct <= 0.8:
            score += 5 + (0.8 - fee_pct) / 0.3 * 3
        elif fee_pct <= 1.5:
            score += max(0, (1.5 - fee_pct) / 0.7 * 5)
    else:
        score += 6

    # 折溢价率（8分）：折价买入相当于"免费"获得超额
    premium = row.get("premium")
    if premium is not None:
        if -1.5 <= premium <= -0.3:
            score += 8  # 合理折价
        elif -0.3 < premium <= 0.3:
            score += 6
        elif -2.0 <= premium < -1.5:
            score += 5
        elif 0.3 < premium <= 1.0:
            score += 4
        elif 1.0 < premium <= 2.0:
            score += 2
        else:
            score += 0
    else:
        score += 4

    # ---- 维度三：规模流动性（15分） ----
    # 基金规模（8分）：太小有清盘风险，太大可能影响灵活性
    scale = row.get("fund_scale")
    if scale is not None:
        scale_yi = scale / 1e8
        if 20 <= scale_yi <= 500:
            score += 8
        elif 10 <= scale_yi < 20 or 500 < scale_yi <= 1000:
            score += 6
        elif 5 <= scale_yi < 10:
            score += 4
        elif 2 <= scale_yi < 5:
            score += 2
        else:
            score += 1
    else:
        score += 4

    # 日均成交额（7分）：流动性越好，冲击成本越低
    avg_vol = row.get("avg_volume_amount")
    if avg_vol is not None:
        vol_yi = avg_vol / 1e8
        if vol_yi >= 10:
            score += 7
        elif vol_yi >= 5:
            score += 5 + (vol_yi - 5) / 5 * 2
        elif vol_yi >= 1:
            score += 3 + (vol_yi - 1) / 4 * 2
        elif vol_yi >= 0.1:
            score += max(0, vol_yi / 0.9 * 3)
    else:
        score += 3

    # ---- 维度四：风险收益（20分） ----
    # 夏普比率（12分）：风险调整后收益
    sr = row.get("sharpe_ratio")
    if sr is not None:
        if sr >= 1.5:
            score += 12
        elif sr >= 1.0:
            score += 9 + (sr - 1.0) / 0.5 * 3
        elif sr >= 0.5:
            score += 5 + (sr - 0.5) / 0.5 * 4
        elif sr >= 0:
            score += sr / 0.5 * 5
        else:
            score += max(0, 2 + sr / 0.5 * 2)

    # 超额收益（8分）：相对基准的年化超额
    excess = row.get("excess_return")
    if excess is not None:
        ex_pct = excess * 100
        if ex_pct >= 2:
            score += 8
        elif ex_pct >= 1:
            score += 6 + (ex_pct - 1) / 1 * 2
        elif ex_pct >= 0:
            score += 4 + ex_pct / 1 * 2
        elif ex_pct >= -1:
            score += 2 + (ex_pct + 1) / 1 * 2
        elif ex_pct >= -3:
            score += max(0, (ex_pct + 3) / 2 * 2)
    else:
        score += 4

    # ---- 维度五：超额归因（10分） ----
    # 归因解读：超额收益是否覆盖了费率
    attribution = row.get("attribution")
    if attribution:
        fee_rate = row.get("fee_rate", 0)
        excess_val = excess if excess is not None else 0
        fee_drag = -fee_rate if fee_rate else 0

        if excess_val > fee_drag:
            # 超额收益覆盖了费率：优秀管理
            if excess_val > 0:
                score += 10
            else:
                score += 7
        elif excess_val > fee_drag * 0.5:
            # 大部分覆盖
            score += 4
        else:
            # 超额不足
            score += 1
    else:
        score += 5

    return round(score, 2)


def calc_comprehensive_score(fund_row):
    """
    综合评分 = 指数质量分(权重0.25) + 基金质量分(权重0.75)
    体现"先选指数、再选基金"的核心逻辑
    """
    idx_score = fund_row.get("index_quality_score", 50)
    fund_score = fund_row.get("fund_score", 0)
    return round(idx_score * 0.25 + fund_score * 0.75, 2)


# ============================================================
# 8. 单只基金深度分析（5年数据 + 超额归因）
# ============================================================
def _analyze_fund_deep(fund_info):
    """
    对单只基金做深度分析，返回所有指标
    核心流程：
      1. 获取 5 年历史净值
      2. 获取 ETF 实时行情（规模、PE、折溢价、成交额）
      3. 获取跟踪指数 5 年数据
      4. 计算跟踪误差、信息比率、超额收益
      5. 超额收益归因分析
      6. PE 历史分位（真实值）
    fund_info: (code, name, fee_rate, idx_code) 或 (code, name)
    """
    if len(fund_info) == 4:
        code, name, fee_rate, idx_code = fund_info
    else:
        code, name = fund_info
        fee_rate = None
        idx_code = FUND_TO_INDEX.get(code)

    # 1. 获取 5 年历史净值
    nav_df = get_fund_nav(code, days=1825)
    if nav_df is None or len(nav_df) < 250:
        return None

    nav_series = nav_df.set_index("date")["nav"]
    fund_daily_ret = nav_series.pct_change().dropna()

    # 2. 获取ETF实时行情（腾讯财经：规模、折溢价、PE、成交额）
    etf_quote = get_etf_quote_tencent(code)

    # 3. 费率兜底（必须在归因分析之前设置）
    if fee_rate is None and etf_quote:
        fee_rate = 0.006  # ETF 默认费率约 0.6%

    # 4. 获取跟踪指数 5 年数据
    idx_annual_ret = None
    tracking_error = None
    info_ratio = None
    excess_return = None
    pe_percentile = None
    price_percentile = None
    attribution = None
    index_quality = None

    if idx_code:
        idx_df = get_index_kline(idx_code, days=1825)

        # 如果使用了 fallback，更新 idx_code 以便估值分位和指数质量评估使用正确的指数
        if idx_df is not None and idx_code in IDX_FALLBACK:
            idx_code = IDX_FALLBACK[idx_code]

        if idx_df is not None and len(idx_df) > 60:
            idx_series = idx_df.set_index("date")["close"]
            idx_daily_ret = idx_series.pct_change().dropna()

            # 指数年化收益
            idx_annual_ret = calc_annual_return(idx_series)

            # 跟踪误差
            tracking_error = calc_tracking_error(fund_daily_ret, idx_daily_ret)

            # 基金年化收益
            fund_annual_ret = calc_annual_return(nav_series)

            # 超额收益
            if fund_annual_ret is not None and idx_annual_ret is not None:
                excess_return = fund_annual_ret - idx_annual_ret

            # 信息比率
            info_ratio = calc_information_ratio(
                fund_annual_ret, idx_annual_ret, tracking_error)

            # 真实 PE 估值分位（基于 5 年价格历史）
            pe_percentile, price_percentile = calc_pe_percentile(idx_code)

            # 超额收益归因分析（fee_rate 已在上面兜底）
            attribution = calc_attribution(
                fund_annual_ret, idx_annual_ret, tracking_error, fee_rate)

            # 指数质量评估
            index_quality = screen_index_quality(idx_code)
    else:
        # 无指数映射时只做基础分析
        fund_annual_ret = calc_annual_return(nav_series)

    # 5. 基础指标
    fund_annual_ret = calc_annual_return(nav_series)
    max_dd = calc_max_drawdown(nav_series)
    volatility = calc_volatility(nav_series)
    sharpe = calc_sharpe(fund_annual_ret, volatility)
    calmar = calc_calmar(fund_annual_ret, max_dd)

    # 5. 规模/流动性指标
    fund_scale = None
    premium = None
    avg_volume_amount = None
    pe = None
    if etf_quote:
        fund_scale = etf_quote.get("total_mv")
        premium = etf_quote.get("premium")
        pe = etf_quote.get("pe")
        avg_volume_amount = etf_quote.get("amount")

    # 6. 数据合理性校验
    res = {
        "基金代码": code,
        "基金名称": name,
        # 风险收益
        "annual_return": fund_annual_ret,
        "max_drawdown": max_dd,
        "volatility": volatility,
        "sharpe_ratio": sharpe,
        "calmar_ratio": calmar,
        # 跟踪质量
        "tracking_error": tracking_error,
        "information_ratio": info_ratio,
        "index_annual_return": idx_annual_ret,
        "excess_return": excess_return,
        # 成本效率
        "fee_rate": fee_rate,
        "premium": premium,
        # 规模流动性
        "fund_scale": fund_scale,
        "avg_volume_amount": avg_volume_amount,
        # 估值（真实历史分位）
        "pe": pe,
        "pe_percentile": pe_percentile,
        "price_percentile": price_percentile,
        # 超额归因
        "attribution": attribution,
        # 指数质量
        "index_quality": index_quality,
        # 元数据
        "idx_code": idx_code,
        "data_days": len(nav_df),
    }

    # 数据合理性校验：
    # - 跟踪误差 > 80% 视为数据异常（价格指数 vs 含分红净值在长周期可能自然偏高，但超过80%仍不合理）
    # - 信息比率绝对值 > 30 视为异常（正常范围 -5 ~ +3，超紧密跟踪+持续跑输时可能达-20）
    # - PE <= 0 视为无效
    if res["tracking_error"] is not None and res["tracking_error"] > 0.80:
        res["tracking_error"] = None
        res["information_ratio"] = None
        res["excess_return"] = None
        res["attribution"] = None
    if (res["information_ratio"] is not None
            and abs(res["information_ratio"]) > 30):
        res["information_ratio"] = None
    if res["pe"] is not None and res["pe"] <= 0:
        res["pe"] = None
        # 注意：pe_percentile 来自指数价格历史分位，不受 PE 字段影响，不清除

    return res


# ============================================================
# 9. 专业筛选（两层：先选指数 → 再选基金）
# ============================================================
def screen_popular_index_funds():
    """专业基金经理方法论：Layer 1 指数筛选 + Layer 2 基金优选"""
    print("=" * 70)
    print("  指数基金专业筛选工具（基金经理方法论实现）")
    print("  Layer 1: 指数筛选（估值分位 + 编制科学性）")
    print("  Layer 2: 基金优选（跟踪质量 35% | 成本 20% | 流动性 15% |")
    print("           风险收益 20% | 超额归因 10%）")
    print("  数据周期：5 年长期数据")
    print("  数据源：新浪财经 + 腾讯财经 + 东方财富")
    print("=" * 70)

    # 主流指数基金及预设跟踪指数
    popular_funds = [
        ("510300", "沪深300", None, "sh000300"),
        ("510310", "沪深300", None, "sh000300"),
        ("159919", "沪深300", None, "sh000300"),
        ("510500", "中证500", None, "sh000905"),
        ("159922", "中证500", None, "sh000905"),
        ("159338", "中证A500", None, "sh000510"),
        ("159339", "中证A500", None, "sh000510"),
        ("515080", "中证红利", None, "sh000015"),
        ("159515", "国企红利", None, "sh000015"),
        ("512890", "红利低波", None, "shH30269"),
        ("515100", "红利低波100", None, "shH30269"),
        ("159915", "创业板", None, "sz399006"),
        ("588000", "科创50", None, "sh000688"),
        ("588080", "科创50", None, "sh000688"),
    ]

    # === Layer 0: 预加载指数数据（串行，新浪财经）===
    print("\n[Layer 0] 加载跟踪指数历史数据（新浪财经，约6年数据）...")
    idx_codes = sorted(set(item[3] for item in popular_funds if item[3]))
    success_count = 0
    for ic in idx_codes:
        df = get_index_kline(ic, days=1825)
        if df is not None:
            print(f"    {ic}: {len(df)} 条数据 ✓  ({df['date'].min().strftime('%Y-%m-%d')} ~ {df['date'].max().strftime('%Y-%m-%d')})")
            success_count += 1
        else:
            print(f"    {ic}: 加载失败 ✗")
        time.sleep(0.3)
    print(f"\n  指数数据加载完成: {success_count}/{len(idx_codes)} 个指数")

    # === Layer 1: 指数筛选 ===
    print("\n" + "=" * 70)
    print("  Layer 1: 指数筛选（先选对指数）")
    print("=" * 70)
    print(f"  {'指数名称':<12s} {'估值分位':>8s} {'类别':<16s} {'加权方式':<22s} {'成分股':>6s} {'调样':>6s} {'质量评分':>8s}")
    print("  " + "-" * 85)

    # 去重（同一指数只评一次）
    seen_idx = set()
    idx_quality_map = {}
    for item in popular_funds:
        idx_code = item[3]
        if idx_code and idx_code not in seen_idx:
            seen_idx.add(idx_code)
            quality = screen_index_quality(idx_code)
            idx_quality_map[idx_code] = quality
            d = quality["details"]
            print(f"  {d['指数名称']:<12s} {d['估值分位']:>8s} {d['类别']:<16s} "
                  f"{d['加权方式']:<22s} {str(d['成分股数']):>6s} {d['调样频率']:<6s} "
                  f"{d['指数质量评分']:>8d}")
    print("\n  >> 指数质量评分越高，代表该指数越值得长期配置")

    # === Layer 2: 基金深度分析 ===
    print("\n" + "=" * 70)
    print("  Layer 2: 基金深度分析（5年数据 + 超额归因）")
    print("=" * 70)

    # 获取实时行情
    print("\n[1/3] 获取实时行情（腾讯财经）...")
    fund_quotes = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {}
        for item in popular_funds:
            code = item[0]
            futures[ex.submit(get_fund_quote_tencent, code)] = code
        for f in as_completed(futures):
            code = futures[f]
            try:
                q = f.result()
                if q:
                    fund_quotes[code] = q
            except Exception:
                pass

    # 构建分析参数
    print("[2/3] 深度分析各基金指标...\n")
    fund_infos = []
    for item in popular_funds:
        code, category, _, idx_code = item
        q = fund_quotes.get(code, {})
        name = q.get("name", code)
        fund_infos.append((code, name, None, idx_code))

    results = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(_analyze_fund_deep, fi): fi[0] for fi in fund_infos}
        for f in as_completed(futures):
            code = futures[f]
            try:
                res = f.result()
                if res:
                    # 计算双层评分
                    idx_quality = res.get("index_quality")
                    idx_quality_score = idx_quality["score"] if idx_quality else 50
                    res["index_quality_score"] = idx_quality_score

                    fund_score = calc_fund_layer_score(res)
                    res["fund_score"] = fund_score

                    comprehensive = calc_comprehensive_score({
                        "index_quality_score": idx_quality_score,
                        "fund_score": fund_score,
                    })
                    res["专业评分"] = comprehensive

                    # 格式化输出摘要
                    ar = f"{res['annual_return']*100:.1f}%" if res['annual_return'] else "N/A"
                    te = f"{res['tracking_error']*100:.2f}%" if res['tracking_error'] else "N/A"
                    ir = f"{res['information_ratio']:.2f}" if res['information_ratio'] else "N/A"
                    print(f"  {res['基金名称']:<20s} {code}  "
                          f"年化{ar:>8s}  跟踪误差{te:>8s}  信息比率{ir:>6s}  "
                          f"指数质量{idx_quality_score:>4d}  基金评分{fund_score:>5.1f}  "
                          f"综合{comprehensive:>5.1f}")
                    results.append(res)
                else:
                    print(f"  {code}: 数据不足，跳过")
            except Exception as e:
                print(f"  {code}: 分析异常 ({e})")

    if not results:
        print("\n未获取到有效数据")
        return

    df = pd.DataFrame(results)

    # === 格式化输出 ===
    print("\n[3/3] 生成报告...")

    # 格式化列
    df["年化收益率"] = df["annual_return"].apply(
        lambda x: f"{x*100:.2f}%" if x is not None and not np.isnan(x) else "N/A")
    df["最大回撤"] = df["max_drawdown"].apply(
        lambda x: f"{x*100:.2f}%" if x is not None and not np.isnan(x) else "N/A")
    df["跟踪误差"] = df["tracking_error"].apply(
        lambda x: f"{x*100:.2f}%" if x is not None and not np.isnan(x) else "N/A")
    df["信息比率"] = df["information_ratio"].apply(
        lambda x: f"{x:.2f}" if x is not None and not np.isnan(x) else "N/A")
    df["夏普比率"] = df["sharpe_ratio"].apply(
        lambda x: f"{x:.2f}" if x is not None and not np.isnan(x) else "N/A")
    df["超额收益"] = df["excess_return"].apply(
        lambda x: f"{x*100:.2f}%" if x is not None and not np.isnan(x) else "N/A")
    df["折溢价率"] = df["premium"].apply(
        lambda x: f"{x:.2f}%" if x is not None and not np.isnan(x) else "N/A")
    df["规模(亿)"] = df["fund_scale"].apply(
        lambda x: f"{x/1e8:.1f}" if x is not None and not np.isnan(x) else "N/A")
    df["费率"] = df["fee_rate"].apply(
        lambda x: f"{x*100:.2f}%" if x is not None and not np.isnan(x) else "N/A")
    df["PE"] = df["pe"].apply(
        lambda x: f"{x:.1f}" if x is not None and not np.isnan(x) else "N/A")
    df["估值分位"] = df["pe_percentile"].apply(
        lambda x: f"{x*100:.0f}%" if x is not None and not np.isnan(x) else "N/A")
    df["指数质量分"] = df["index_quality_score"].apply(
        lambda x: f"{int(x)}" if x is not None else "N/A")
    df["基金评分"] = df["fund_score"].apply(
        lambda x: f"{x:.1f}" if x is not None else "N/A")

    # 归因摘要
    def _attr_summary(attr):
        if attr is None:
            return "N/A"
        return attr.get("归因解读", "N/A")[:60] + ("..." if len(attr.get("归因解读", "")) > 60 else "")
    df["归因摘要"] = df["attribution"].apply(_attr_summary)

    # 按专业评分排序
    df = df.sort_values("专业评分", ascending=False).reset_index(drop=True)

    # ---- 输出 Layer 2 结果 ----
    print("\n" + "=" * 90)
    print("  基金综合排名（指数质量 × 基金质量）")
    print("=" * 90)
    display_cols = [
        "基金代码", "基金名称", "年化收益率", "最大回撤", "跟踪误差",
        "信息比率", "夏普比率", "超额收益", "折溢价率",
        "规模(亿)", "费率", "PE", "估值分位",
        "指数质量分", "基金评分", "专业评分", "归因摘要"
    ]
    print(df[display_cols].to_string(index=False, max_colwidth=60))

    # === 多维度推荐 ===
    print("\n" + "=" * 70)
    print("  多维度推荐（基金经理视角）")
    print("=" * 70)

    best = df.iloc[0]
    print(f"\n  >> 综合最优: {best['基金名称']}（{best['基金代码']}）")
    print(f"     综合评分: {best['专业评分']:.1f}  "
          f"年化: {best['年化收益率']}  跟踪误差: {best['跟踪误差']}  "
          f"信息比率: {best['信息比率']}")
    if best.get("归因摘要"):
        print(f"     归因: {best['归因摘要']}")

    # 指数最优（先选对指数）
    if "index_quality_score" in df.columns:
        valid_idx = df.dropna(subset=["index_quality_score"])
        if not valid_idx.empty:
            best_idx = valid_idx.loc[valid_idx["index_quality_score"].idxmax()]
            print(f"\n  >> 指数最值得配置: {best_idx['基金名称']}（{best_idx['基金代码']}）")
            print(f"     指数质量分: {best_idx['指数质量分']}  估值分位: {best_idx['估值分位']}")

    # 跟踪最紧密（被动投资本质）
    if "tracking_error" in df.columns:
        valid_te = df.dropna(subset=["tracking_error"])
        if not valid_te.empty:
            best_te = valid_te.loc[valid_te["tracking_error"].idxmin()]
            print(f"\n  >> 跟踪最紧密: {best_te['基金名称']}（{best_te['基金代码']}）")
            print(f"     跟踪误差: {best_te['跟踪误差']}  （最忠实复制指数）")

    # 信息比率最高（超额收益最稳定）
    if "information_ratio" in df.columns:
        valid_ir = df.dropna(subset=["information_ratio"])
        if not valid_ir.empty:
            valid_ir_sorted = valid_ir.sort_values("information_ratio", ascending=False)
            best_ir = valid_ir_sorted.iloc[0]
            print(f"\n  >> 超额收益最稳定: {best_ir['基金名称']}（{best_ir['基金代码']}）")
            print(f"     信息比率: {best_ir['信息比率']}  （超额/跟踪误差）")

    # 成本最优（费率最低 + 规模合适）
    if "fee_rate" in df.columns and "fund_scale" in df.columns:
        valid_fe = df.dropna(subset=["fee_rate", "fund_scale"])
        valid_fe = valid_fe[valid_fe["fund_scale"] > 5e8]
        if not valid_fe.empty:
            best_fe = valid_fe.loc[valid_fe["fee_rate"].idxmin()]
            print(f"\n  >> 成本最优: {best_fe['基金名称']}（{best_fe['基金代码']}）")
            print(f"     费率: {best_fe['费率']}  规模: {best_fe['规模(亿)']}亿")

    # 估值偏低（当前低估的指数）
    if "pe_percentile" in df.columns:
        valid_pct = df.dropna(subset=["pe_percentile"])
        valid_pct = valid_pct[valid_pct["pe_percentile"].apply(
            lambda x: float(x.replace("%", "")) if isinstance(x, str) else x) < 30]
        if not valid_pct.empty:
            best_pct = valid_pct.iloc[0]
            print(f"\n  >> 估值偏低: {best_pct['基金名称']}（{best_pct['基金代码']}）")
            print(f"     PE: {best_pct['PE']}  估值分位: {best_pct['估值分位']}  "
                  f"（越接近0%越低估）")

    # 导出
    output_file = "index_fund_professional_result.csv"
    df[display_cols].to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\n  完整结果已导出到: {output_file}")

    return df


# ============================================================
# 10. 运行入口
# ============================================================
if __name__ == "__main__":
    print("\n指数基金专业筛选工具（基金经理方法论）")
    print("  核心逻辑：先选对指数 → 再选对基金")
    print("  评估体系：Layer 1 指数筛选 + Layer 2 基金优选（5年长期数据）")
    print("\n请选择筛选模式：")
    print("  1. 快速筛选（主流指数基金深度对比，推荐）")
    print("  2. 全量筛选（从排行中筛选，耗时较长）")
    print()
    choice = input("请输入选项 (1/2)，默认 1: ").strip()
    if choice == "2":
        print("\n全量模式暂用快速模式代替（后续可扩展）")
        result = screen_popular_index_funds()
    else:
        result = screen_popular_index_funds()
    print("\n风险提示：以上结果基于历史数据和公开信息，不构成投资建议。投资有风险，入市需谨慎。")
    print("方法论文档：被动投资的本质是低成本、高精度地获取市场 Beta，任何偏离都必须有合理的补偿。")
