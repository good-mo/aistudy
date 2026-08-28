"""
指数基金专业筛选工具 V2.1 —— 专业基金经理方法论实现（完整修复版）

核心修复：
  1. 基准选择：使用全收益指数（含分红）作为基准
  2. 估值数据：接入真实PE/PB数据（AKShare）
  3. 跟踪指标：同时计算跟踪误差和跟踪偏离度
  4. 基金分类：区分被动型与增强型指数基金
  5. 收益分解：替代原Brinson归因（需持仓数据）
  6. 降级策略：全收益指数获取失败时降级到价格指数+股息率修正
  
数据源：
  - AKShare（全收益指数、真实PE/PB估值）
  - 腾讯财经（实时行情）
  - 东方财富（基金净值）
  
依赖：pip install akshare pandas numpy requests
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

# 尝试导入AKShare
try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    print("警告：未安装AKShare，部分功能不可用。请执行：pip install akshare")

# ============================================================
# API 配置
# ============================================================
TENCENT_ETF_QUOTE_URL = "http://qt.gtimg.cn/q={etf_code}"
EASTMONEY_NAV_URL = (
    "https://api.fund.eastmoney.com/f10/lsjz"
    "?fundCode={fund_code}&pageIndex={page}&pageSize=20"
    "&startDate={start_date}&endDate={end_date}"
)

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
# 指数基金代码 → 跟踪指数映射（完整修复版）
# ============================================================
FUND_TO_INDEX = {
    # 沪深300系列
    "510300": {
        "price_idx": "000300",
        "total_return_idx": "H00300",
        "fund_type": "passive"
    },
    "510310": {
        "price_idx": "000300",
        "total_return_idx": "H00300",
        "fund_type": "passive"
    },
    "159919": {
        "price_idx": "000300",
        "total_return_idx": "H00300",
        "fund_type": "passive"
    },
    
    # 中证500系列
    "510500": {
        "price_idx": "000905",
        "total_return_idx": "H00905",
        "fund_type": "passive"
    },
    "159922": {
        "price_idx": "000905",
        "total_return_idx": "H00905",
        "fund_type": "passive"
    },
    
    # 中证A500系列
    "159338": {
        "price_idx": "000510",
        "total_return_idx": "H00510",
        "fund_type": "passive"
    },
    "159339": {
        "price_idx": "000510",
        "total_return_idx": "H00510",
        "fund_type": "passive"
    },
    
    # 中证红利系列
    "515080": {
        "price_idx": "000015",
        "total_return_idx": "H00015",
        "fund_type": "passive"
    },
    "159515": {
        "price_idx": "000015",
        "total_return_idx": "H00015",
        "fund_type": "passive"
    },
    
    # 红利低波系列
    "512890": {
        "price_idx": "H30269",
        "total_return_idx": "HH30269",
        "fund_type": "passive"
    },
    "515100": {
        "price_idx": "H30269",
        "total_return_idx": "HH30269",
        "fund_type": "passive"
    },
    
    # 创业板系列
    "159915": {
        "price_idx": "399006",
        "total_return_idx": "H399006",
        "fund_type": "passive"
    },
    
    # 科创50系列
    "588000": {
        "price_idx": "000688",
        "total_return_idx": "H00688",
        "fund_type": "passive"
    },
    "588080": {
        "price_idx": "000688",
        "total_return_idx": "H00688",
        "fund_type": "passive"
    },
}

# ============================================================
# 指数元数据
# ============================================================
INDEX_META = {
    "000300": {
        "name": "沪深300", "category": "大盘蓝筹", "weight_type": "自由流通市值加权",
        "components": 300, "rebalance": "半年",
        "description": "沪深两市规模大、流动性好的300只股票",
        "pe_reasonable_low": 10, "pe_reasonable_high": 16,
        "pb_reasonable_low": 1.2, "pb_reasonable_high": 2.0,
        "dividend_yield_avg": 0.025,
    },
    "000905": {
        "name": "中证500", "category": "中盘成长", "weight_type": "自由流通市值加权",
        "components": 500, "rebalance": "半年",
        "description": "剔除沪深300后市值最大的500只股票",
        "pe_reasonable_low": 18, "pe_reasonable_high": 35,
        "pb_reasonable_low": 1.5, "pb_reasonable_high": 2.8,
        "dividend_yield_avg": 0.018,
    },
    "000510": {
        "name": "中证A500", "category": "大盘均衡", "weight_type": "自由流通市值加权+行业均衡",
        "components": 500, "rebalance": "半年",
        "description": "行业均衡的新一代宽基指数",
        "pe_reasonable_low": 10, "pe_reasonable_high": 16,
        "pb_reasonable_low": 1.2, "pb_reasonable_high": 2.0,
        "dividend_yield_avg": 0.022,
    },
    "000015": {
        "name": "中证红利", "category": "红利价值", "weight_type": "股息率加权",
        "components": 100, "rebalance": "年",
        "description": "沪深两市现金股息率高、分红稳定的100只股票",
        "pe_reasonable_low": 5, "pe_reasonable_high": 10,
        "pb_reasonable_low": 0.5, "pb_reasonable_high": 1.0,
        "dividend_yield_avg": 0.050,
    },
    "H30269": {
        "name": "红利低波", "category": "红利+低波 Smart Beta", "weight_type": "因子加权",
        "components": 50, "rebalance": "半年",
        "description": "红利+低波动双因子策略指数",
        "pe_reasonable_low": 5, "pe_reasonable_high": 10,
        "pb_reasonable_low": 0.5, "pb_reasonable_high": 1.0,
        "dividend_yield_avg": 0.045,
    },
    "399006": {
        "name": "创业板指", "category": "创业板成长", "weight_type": "自由流通市值加权",
        "components": 100, "rebalance": "半年",
        "description": "创业板最具代表性的100只股票",
        "pe_reasonable_low": 25, "pe_reasonable_high": 55,
        "pb_reasonable_low": 3.0, "pb_reasonable_high": 7.0,
        "dividend_yield_avg": 0.005,
    },
    "000688": {
        "name": "科创50", "category": "科创板成长", "weight_type": "自由流通市值加权",
        "components": 50, "rebalance": "季",
        "description": "科创板市值大、流动性好的50只股票",
        "pe_reasonable_low": 30, "pe_reasonable_high": 60,
        "pb_reasonable_low": 3.0, "pb_reasonable_high": 6.0,
        "dividend_yield_avg": 0.003,
    },
}

# 指数名称映射（用于估值接口）
INDEX_NAME_MAP = {
    "000300": "沪深300",
    "000905": "中证500",
    "000510": "中证A500",
    "000015": "中证红利",
    "H30269": "红利低波",
    "399006": "创业板指",
    "000688": "科创50",
}

# ============================================================
# 1. 获取全收益指数历史数据（AKShare）
# ============================================================
_IDX_CACHE = {}


def get_index_total_return(idx_code, days=1825):
    """
    获取全收益指数历史数据（AKShare）
    全收益指数 = 价格指数 + 成分股分红再投资收益
    """
    if not HAS_AKSHARE:
        return None
    
    cache_key = f"tr_{idx_code}"
    if cache_key in _IDX_CACHE:
        return _IDX_CACHE[cache_key]
    
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        
        # 使用正确的AKShare接口
        df = ak.stock_zh_index_hist_csindex(
            symbol=idx_code,
            start_date=start_date,
            end_date=end_date
        )
        
        if df is None or df.empty:
            return None
        
        # 标准化列名
        df = df.rename(columns={
            "日期": "date",
            "收盘": "close",
        })
        
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        _IDX_CACHE[cache_key] = df
        return df
        
    except Exception as e:
        print(f"    获取全收益指数 {idx_code} 失败: {e}")
        return None


def get_index_price_with_dividend_adjustment(idx_code, days=1825):
    """
    降级策略：获取价格指数并用股息率近似修正分红差异
    """
    if not HAS_AKSHARE:
        return None
    
    cache_key = f"price_adj_{idx_code}"
    if cache_key in _IDX_CACHE:
        return _IDX_CACHE[cache_key]
    
    try:
        # 获取价格指数
        price_idx = idx_code
        if idx_code.startswith("H"):
            # 全收益代码转价格指数代码
            price_idx = idx_code[1:]  # H00300 -> 000300
            if price_idx.startswith("H"):  # HH30269 -> H30269
                price_idx = price_idx[1:]
        
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        
        df = ak.stock_zh_index_hist_csindex(
            symbol=price_idx,
            start_date=start_date,
            end_date=end_date
        )
        
        if df is None or df.empty:
            return None
        
        df = df.rename(columns={
            "日期": "date",
            "收盘": "close",
        })
        
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # 用股息率近似修正分红差异
        # 获取对应元数据
        meta_idx = price_idx
        if meta_idx.startswith("H"):
            meta_idx = meta_idx[1:]
        
        dividend_yield = INDEX_META.get(meta_idx, {}).get("dividend_yield_avg", 0.02)
        
        # 简单修正：每日增加股息率/250的收益
        daily_dividend = dividend_yield / 250
        df["close"] = df["close"] * (1 + daily_dividend) ** range(len(df))
        
        print(f"    使用价格指数+股息率({dividend_yield*100:.1f}%)近似修正")
        
        _IDX_CACHE[cache_key] = df
        return df
        
    except Exception as e:
        print(f"    获取价格指数 {idx_code} 失败: {e}")
        return None


# ============================================================
# 2. 获取真实PE/PB估值数据（AKShare）
# ============================================================
def get_index_valuation(idx_code):
    """
    获取指数真实PE/PB估值数据（AKShare）
    注意：需要传入指数名称，不是代码
    """
    if not HAS_AKSHARE:
        return None
    
    # 获取指数名称
    idx_name = INDEX_NAME_MAP.get(idx_code)
    if not idx_name:
        print(f"    未找到指数 {idx_code} 的名称映射")
        return None
    
    try:
        # 获取PE数据
        df_pe = ak.index_value_hist_funddb(
            symbol=idx_name,
            indicator="市盈率"
        )
        
        if df_pe is None or df_pe.empty:
            return None
        
        # 获取最新PE和计算分位
        latest_pe = df_pe.iloc[-1]["市盈率"]
        pe_series = df_pe["市盈率"].dropna()
        pe_percentile = (pe_series <= latest_pe).mean()
        
        # 获取PB数据
        df_pb = ak.index_value_hist_funddb(
            symbol=idx_name,
            indicator="市净率"
        )
        
        if df_pb is not None and not df_pb.empty:
            latest_pb = df_pb.iloc[-1]["市净率"]
            pb_series = df_pb["市净率"].dropna()
            pb_percentile = (pb_series <= latest_pb).mean()
        else:
            latest_pb = None
            pb_percentile = None
        
        return {
            "pe": latest_pe,
            "pe_percentile": pe_percentile,
            "pb": latest_pb,
            "pb_percentile": pb_percentile,
        }
        
    except Exception as e:
        print(f"    获取指数 {idx_name} 估值数据失败: {e}")
        return None


# ============================================================
# 3. 获取基金历史净值（东方财富）
# ============================================================
def get_fund_nav(fund_code, days=1825):
    """获取基金单位净值历史数据"""
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
        except Exception as e:
            print(f"    获取基金 {fund_code} 净值失败: {e}")
            return None
    
    if not all_records:
        return None
    
    df = pd.DataFrame(all_records, columns=["date", "nav"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ============================================================
# 4. 获取ETF实时行情（腾讯财经）
# ============================================================
def get_etf_quote_tencent(code):
    """腾讯财经ETF实时行情"""
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
                volume_amount = float(parts[37]) if parts[37] else None
                total_mv_yi = float(parts[44]) if parts[44] else None
                premium = float(parts[62]) if parts[62] else None
                
                amount_yuan = volume_amount * 1e4 if volume_amount else None
                total_mv_yuan = total_mv_yi * 1e8 if total_mv_yi else None
                
                return {
                    "code": str(parts[2]),
                    "name": str(parts[1]),
                    "price": price,
                    "amount": amount_yuan,
                    "total_mv": total_mv_yuan,
                    "premium": premium,
                }
    except Exception as e:
        print(f"    获取ETF {code} 行情失败: {e}")
    return None


# ============================================================
# 5. 指标计算
# ============================================================
def calc_annual_return(nav_series):
    """年化收益率"""
    if len(nav_series) < 250:
        return None
    total = nav_series.iloc[-1] / nav_series.iloc[0] - 1
    years = len(nav_series) / 250
    return (1 + total) ** (1 / years) - 1


def calc_max_drawdown(series):
    """最大回撤"""
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


def calc_tracking_error_and_difference(fund_returns, index_returns):
    """
    计算跟踪误差和跟踪偏离度（修复版）
    
    跟踪偏离度（Tracking Difference）：累积收益差值，反映系统性偏差
    跟踪误差（Tracking Error）：日收益差的标准差，反映波动离散程度
    """
    if fund_returns is None or index_returns is None:
        return None, None
    
    # 日期对齐
    common_idx = fund_returns.index.intersection(index_returns.index)
    if len(common_idx) < 60:
        return None, None
    
    fund_aligned = fund_returns.loc[common_idx]
    index_aligned = index_returns.loc[common_idx]
    
    # 日收益差
    diff = fund_aligned - index_aligned
    
    # 跟踪误差（年化）
    tracking_error = diff.std() * np.sqrt(250)
    
    # 跟踪偏离度（累积收益差）
    fund_cumulative = (1 + fund_aligned).prod() - 1
    index_cumulative = (1 + index_aligned).prod() - 1
    tracking_difference = fund_cumulative - index_cumulative
    
    return tracking_error, tracking_difference


def calc_information_ratio(fund_annual_ret, index_annual_ret, tracking_error):
    """信息比率"""
    if (tracking_error is None or tracking_error == 0
            or fund_annual_ret is None or index_annual_ret is None):
        return None
    return (fund_annual_ret - index_annual_ret) / tracking_error


# ============================================================
# 6. 收益分解（替代Brinson归因）
# ============================================================
def calc_return_decomposition(fund_annual_ret, index_annual_ret, fee_rate, fund_type):
    """
    收益分解（简化版归因）
    
    将超额收益分解为：
    1. 费率拖累
    2. 现金拖累
    3. 管理超额（扣除费率和现金后的真实贡献）
    
    注意：真正的Brinson归因需要持仓数据，这里只是简化版
    """
    if fund_annual_ret is None or index_annual_ret is None:
        return None
    
    excess = fund_annual_ret - index_annual_ret
    
    # 估算现金拖累（假设平均现金比例2%）
    cash_drag = 0.0015  # 0.15%
    
    # 费率拖累
    fee_drag = -fee_rate if fee_rate else -0.006
    
    # 管理超额
    management_alpha = excess - fee_drag - cash_drag
    
    result = {
        "总超额收益": excess,
        "费率拖累": fee_drag,
        "现金拖累": cash_drag,
        "管理超额": management_alpha,
        "归因解读": "",
    }
    
    # 根据基金类型给出不同解读
    if fund_type == "passive":
        if abs(management_alpha) < 0.005:
            result["归因解读"] = "被动复制精度高，管理层面基本忠实复制指数"
        elif management_alpha > 0.005:
            result["归因解读"] = "超额收益为正，可能来自打新、运营效率等"
        else:
            result["归因解读"] = "存在跟踪偏离，需关注交易损耗或运营问题"
    else:
        if management_alpha > 0.02:
            result["归因解读"] = "增强效果显著，选股能力突出"
        elif management_alpha > 0:
            result["归因解读"] = "有一定增强效果，但需关注稳定性"
        else:
            result["归因解读"] = "增强效果不足，未能覆盖较高管理费"
    
    return result


# ============================================================
# 7. 估值分位计算
# ============================================================
def calc_valuation_percentile(idx_code):
    """计算估值分位（使用真实PE/PB数据）"""
    valuation = get_index_valuation(idx_code)
    
    if valuation is None:
        return None, None, None
    
    pe_pct = valuation.get("pe_percentile")
    pb_pct = valuation.get("pb_percentile")
    
    # 综合估值分位
    if pe_pct is not None and pb_pct is not None:
        combined_pct = pe_pct * 0.6 + pb_pct * 0.4
    elif pe_pct is not None:
        combined_pct = pe_pct
    else:
        combined_pct = pb_pct
    
    return combined_pct, pe_pct, pb_pct


# ============================================================
# 8. 指数质量评估（Layer 1）
# ============================================================
def screen_index_quality(idx_code):
    """Layer 1: 指数质量评估"""
    if idx_code is None:
        return {"score": 50, "details": {}}
    
    # 获取元数据索引
    meta_idx = idx_code
    if idx_code.startswith("H"):
        meta_idx = idx_code[1:]
        if meta_idx.startswith("H"):
            meta_idx = meta_idx[1:]
    
    meta = INDEX_META.get(meta_idx, {})
    valuation_pct, pe_pct, pb_pct = calc_valuation_percentile(meta_idx)
    
    score = 0
    details = {}
    
    # 1. 估值吸引力 (50分)
    if valuation_pct is not None:
        if valuation_pct <= 0.15:
            score += 50
        elif valuation_pct <= 0.25:
            score += 45
        elif valuation_pct <= 0.40:
            score += 38
        elif valuation_pct <= 0.60:
            score += 28
        elif valuation_pct <= 0.75:
            score += 18
        elif valuation_pct <= 0.90:
            score += 8
        else:
            score += 2
    else:
        score += 25
    
    # 2. 编制科学性 (30分)
    weight_type = meta.get("weight_type", "")
    n_components = meta.get("components", 0)
    rebalance = meta.get("rebalance", "")
    
    if "市值加权" in weight_type:
        score += 12
    elif "因子加权" in weight_type or "股息率加权" in weight_type:
        score += 8
    else:
        score += 5
    
    if n_components >= 300:
        score += 10
    elif n_components >= 100:
        score += 8
    elif n_components >= 50:
        score += 5
    else:
        score += 3
    
    if "半年" in rebalance:
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
        score += 20
    elif "中盘" in category:
        score += 16
    elif "红利" in category or "价值" in category:
        score += 14
    elif "成长" in category:
        score += 12
    else:
        score += 10
    
    details = {
        "指数名称": meta.get("name", idx_code),
        "估值分位": f"{valuation_pct*100:.0f}%" if valuation_pct else "N/A",
        "PE分位": f"{pe_pct*100:.0f}%" if pe_pct else "N/A",
        "PB分位": f"{pb_pct*100:.0f}%" if pb_pct else "N/A",
        "类别": category,
        "加权方式": weight_type,
        "成分股数": n_components,
        "调样频率": rebalance,
        "指数质量评分": score,
    }
    
    return {"score": score, "details": details}


# ============================================================
# 9. 基金评分（Layer 2）
# ============================================================
def calc_fund_layer_score(row, fund_type="passive"):
    """Layer 2: 基金优选评分"""
    score = 0
    
    if fund_type == "passive":
        # 被动型：跟踪精度最重要
        # 跟踪质量 (45分)
        te = row.get("tracking_error")
        if te is not None:
            te_pct = te * 100
            if te_pct <= 0.3:
                score += 25
            elif te_pct <= 0.5:
                score += 22
            elif te_pct <= 1.0:
                score += 18
            elif te_pct <= 2.0:
                score += 12
            else:
                score += max(0, 25 - te_pct * 5)
        else:
            score += 12
        
        # 跟踪偏离度 (20分)
        td = row.get("tracking_difference")
        if td is not None:
            td_abs = abs(td)
            if td_abs <= 0.01:
                score += 20
            elif td_abs <= 0.03:
                score += 15
            elif td_abs <= 0.05:
                score += 10
            else:
                score += max(0, 20 - td_abs * 100)
        else:
            score += 10
        
        # 成本效率 (25分)
        fee = row.get("fee_rate")
        if fee is not None:
            fee_pct = fee * 100
            if fee_pct <= 0.15:
                score += 15
            elif fee_pct <= 0.3:
                score += 12
            elif fee_pct <= 0.5:
                score += 9
            else:
                score += max(0, 15 - fee_pct * 10)
        else:
            score += 7
        
        # 规模流动性 (20分)
        scale = row.get("fund_scale")
        if scale is not None:
            scale_yi = scale / 1e8
            if 20 <= scale_yi <= 500:
                score += 12
            elif 10 <= scale_yi < 20 or 500 < scale_yi <= 1000:
                score += 9
            elif 5 <= scale_yi < 10:
                score += 6
            else:
                score += 3
        else:
            score += 6
        
        avg_vol = row.get("avg_volume_amount")
        if avg_vol is not None:
            vol_yi = avg_vol / 1e8
            if vol_yi >= 10:
                score += 8
            elif vol_yi >= 5:
                score += 6
            elif vol_yi >= 1:
                score += 4
            else:
                score += 2
        else:
            score += 4
        
        # 风险收益 (10分)
        sr = row.get("sharpe_ratio")
        if sr is not None:
            if sr >= 1.0:
                score += 10
            elif sr >= 0.5:
                score += 7
            elif sr >= 0:
                score += 4
            else:
                score += 1
        else:
            score += 5
    
    else:
        # 增强型：超额收益更重要
        # 跟踪质量 (25分)
        te = row.get("tracking_error")
        if te is not None:
            te_pct = te * 100
            if te_pct <= 3.0:
                score += 15
            elif te_pct <= 5.0:
                score += 12
            elif te_pct <= 8.0:
                score += 8
            else:
                score += 4
        else:
            score += 8
        
        # 增强效果 (10分)
        attribution = row.get("attribution")
        if attribution:
            mgmt_alpha = attribution.get("管理超额", 0)
            if mgmt_alpha > 0.03:
                score += 10
            elif mgmt_alpha > 0.02:
                score += 8
            elif mgmt_alpha > 0.01:
                score += 6
            elif mgmt_alpha > 0:
                score += 4
            else:
                score += 1
        else:
            score += 5
        
        # 成本效率 (15分)
        fee = row.get("fee_rate")
        if fee is not None:
            fee_pct = fee * 100
            if fee_pct <= 0.8:
                score += 10
            elif fee_pct <= 1.2:
                score += 7
            else:
                score += 4
        else:
            score += 5
        
        # 规模流动性 (15分)
        scale = row.get("fund_scale")
        if scale is not None:
            scale_yi = scale / 1e8
            if scale_yi >= 10:
                score += 10
            elif scale_yi >= 5:
                score += 7
            else:
                score += 4
        else:
            score += 5
        
        avg_vol = row.get("avg_volume_amount")
        if avg_vol is not None:
            vol_yi = avg_vol / 1e8
            if vol_yi >= 5:
                score += 5
            elif vol_yi >= 1:
                score += 3
            else:
                score += 1
        else:
            score += 2
        
        # 风险收益 (35分)
        sr = row.get("sharpe_ratio")
        if sr is not None:
            if sr >= 1.5:
                score += 20
            elif sr >= 1.0:
                score += 15
            elif sr >= 0.5:
                score += 10
            elif sr >= 0:
                score += 5
            else:
                score += 2
        else:
            score += 10
        
        excess = row.get("excess_return")
        if excess is not None:
            ex_pct = excess * 100
            if ex_pct >= 3:
                score += 15
            elif ex_pct >= 2:
                score += 12
            elif ex_pct >= 1:
                score += 8
            elif ex_pct >= 0:
                score += 4
            else:
                score += 1
        else:
            score += 7
    
    return round(score, 2)


# ============================================================
# 10. 单只基金深度分析
# ============================================================
def _analyze_fund_deep(fund_info):
    """对单只基金做深度分析"""
    code, name, fee_rate, idx_info = fund_info
    idx_code = idx_info["total_return_idx"]
    fund_type = idx_info["fund_type"]
    
    # 1. 获取基金5年历史净值
    nav_df = get_fund_nav(code, days=1825)
    if nav_df is None or len(nav_df) < 250:
        return None
    
    nav_series = nav_df.set_index("date")["nav"]
    fund_daily_ret = nav_series.pct_change().dropna()
    
    # 2. 获取ETF实时行情
    etf_quote = get_etf_quote_tencent(code)
    
    # 3. 费率兜底
    if fee_rate is None and etf_quote:
        fee_rate = 0.006
    
    # 4. 获取全收益指数数据（带降级策略）
    idx_annual_ret = None
    tracking_error = None
    tracking_difference = None
    info_ratio = None
    excess_return = None
    attribution = None
    index_quality = None
    
    idx_df = get_index_total_return(idx_code, days=1825)
    
    # 降级策略：全收益指数获取失败时，使用价格指数+股息率修正
    if idx_df is None:
        print(f"    全收益指数 {idx_code} 获取失败，尝试降级策略")
        idx_df = get_index_price_with_dividend_adjustment(idx_code, days=1825)
    
    if idx_df is not None and len(idx_df) > 60:
        idx_series = idx_df.set_index("date")["close"]
        idx_daily_ret = idx_series.pct_change().dropna()
        
        # 指数年化收益
        idx_annual_ret = calc_annual_return(idx_series)
        
        # 跟踪误差和跟踪偏离度
        tracking_error, tracking_difference = calc_tracking_error_and_difference(
            fund_daily_ret, idx_daily_ret)
        
        # 基金年化收益
        fund_annual_ret = calc_annual_return(nav_series)
        
        # 超额收益
        if fund_annual_ret is not None and idx_annual_ret is not None:
            excess_return = fund_annual_ret - idx_annual_ret
        
        # 信息比率
        info_ratio = calc_information_ratio(
            fund_annual_ret, idx_annual_ret, tracking_error)
        
        # 收益分解
        attribution = calc_return_decomposition(
            fund_annual_ret, idx_annual_ret, fee_rate, fund_type)
        
        # 指数质量评估
        meta_idx = idx_code
        if idx_code.startswith("H"):
            meta_idx = idx_code[1:]
            if meta_idx.startswith("H"):
                meta_idx = meta_idx[1:]
        index_quality = screen_index_quality(meta_idx)
    else:
        fund_annual_ret = calc_annual_return(nav_series)
    
    # 5. 基础指标
    max_dd = calc_max_drawdown(nav_series)
    volatility = calc_volatility(nav_series)
    sharpe = calc_sharpe(fund_annual_ret, volatility)
    
    # 6. 规模/流动性指标
    fund_scale = None
    premium = None
    avg_volume_amount = None
    if etf_quote:
        fund_scale = etf_quote.get("total_mv")
        premium = etf_quote.get("premium")
        avg_volume_amount = etf_quote.get("amount")
    
    # 7. 数据合理性校验
    res = {
        "基金代码": code,
        "基金名称": name,
        "基金类型": fund_type,
        "annual_return": fund_annual_ret,
        "max_drawdown": max_dd,
        "volatility": volatility,
        "sharpe_ratio": sharpe,
        "tracking_error": tracking_error,
        "tracking_difference": tracking_difference,
        "information_ratio": info_ratio,
        "index_annual_return": idx_annual_ret,
        "excess_return": excess_return,
        "fee_rate": fee_rate,
        "premium": premium,
        "fund_scale": fund_scale,
        "avg_volume_amount": avg_volume_amount,
        "attribution": attribution,
        "index_quality": index_quality,
        "idx_code": idx_code,
        "data_days": len(nav_df),
    }
    
    # 数据合理性校验
    if res["tracking_error"] is not None and res["tracking_error"] > 0.80:
        res["tracking_error"] = None
        res["tracking_difference"] = None
        res["information_ratio"] = None
        res["attribution"] = None
    
    if res["information_ratio"] is not None and abs(res["information_ratio"]) > 30:
        res["information_ratio"] = None
    
    return res


# ============================================================
# 11. 专业筛选主流程
# ============================================================
def screen_popular_index_funds():
    """专业基金经理方法论：Layer 1 指数筛选 + Layer 2 基金优选"""
    print("=" * 70)
    print("  指数基金专业筛选工具 V2.1（完整修复版）")
    print("  核心修复：")
    print("    1. 使用全收益指数作为基准（含分红）")
    print("    2. 同时计算跟踪误差和跟踪偏离度")
    print("    3. 使用真实PE/PB估值数据")
    print("    4. 区分被动型与增强型指数基金")
    print("    5. 收益分解（替代Brinson归因）")
    print("    6. 降级策略（全收益指数失败时用价格指数+股息率）")
    print("=" * 70)
    
    if not HAS_AKSHARE:
        print("\n错误：未安装AKShare，无法获取全收益指数和真实估值数据")
        print("请执行：pip install akshare")
        return None
    
    # 主流指数基金
    popular_funds = [
        ("510300", "沪深300ETF", None, FUND_TO_INDEX["510300"]),
        ("510310", "沪深300ETF易方达", None, FUND_TO_INDEX["510310"]),
        ("159919", "沪深300ETF嘉实", None, FUND_TO_INDEX["159919"]),
        ("510500", "中证500ETF", None, FUND_TO_INDEX["510500"]),
        ("159922", "中证500ETF嘉实", None, FUND_TO_INDEX["159922"]),
        ("159338", "中证A500ETF", None, FUND_TO_INDEX["159338"]),
        ("159339", "中证A500ETF嘉实", None, FUND_TO_INDEX["159339"]),
        ("515080", "中证红利ETF", None, FUND_TO_INDEX["515080"]),
        ("159515", "国企红利ETF", None, FUND_TO_INDEX["159515"]),
        ("512890", "红利低波ETF", None, FUND_TO_INDEX["512890"]),
        ("515100", "红利低波100ETF", None, FUND_TO_INDEX["515100"]),
        ("159915", "创业板ETF", None, FUND_TO_INDEX["159915"]),
        ("588000", "科创50ETF", None, FUND_TO_INDEX["588000"]),
        ("588080", "科创50ETF易方达", None, FUND_TO_INDEX["588080"]),
    ]
    
    # === Layer 0: 预加载指数数据 ===
    print("\n[Layer 0] 加载全收益指数历史数据（AKShare）...")
    idx_codes = sorted(set(item[3]["total_return_idx"] for item in popular_funds))
    success_count = 0
    for ic in idx_codes:
        df = get_index_total_return(ic, days=1825)
        if df is not None:
            print(f"    {ic}: {len(df)} 条数据 ✓")
            success_count += 1
        else:
            print(f"    {ic}: 加载失败，将使用降级策略")
        time.sleep(0.5)  # 控制请求频率
    print(f"\n  指数数据加载完成: {success_count}/{len(idx_codes)} 个指数")
    
    # === Layer 1: 指数筛选 ===
    print("\n" + "=" * 70)
    print("  Layer 1: 指数筛选（使用真实PE/PB估值数据）")
    print("=" * 70)
    
    seen_idx = set()
    idx_quality_map = {}
    for item in popular_funds:
        idx_code = item[3]["total_return_idx"]
        meta_idx = idx_code
        if idx_code.startswith("H"):
            meta_idx = idx_code[1:]
            if meta_idx.startswith("H"):
                meta_idx = meta_idx[1:]
        
        if meta_idx and meta_idx not in seen_idx:
            seen_idx.add(meta_idx)
            quality = screen_index_quality(meta_idx)
            idx_quality_map[meta_idx] = quality
            d = quality["details"]
            print(f"  {d['指数名称']:<12s} 估值{d['估值分位']:>6s} "
                  f"(PE{d['PE分位']:>6s} PB{d['PB分位']:>6s}) "
                  f"{d['类别']:<16s} 质量{d['指数质量评分']:>4d}")
    
    # === Layer 2: 基金深度分析 ===
    print("\n" + "=" * 70)
    print("  Layer 2: 基金深度分析（全收益指数基准 + 收益分解）")
    print("=" * 70)
    
    # 获取实时行情
    print("\n[1/3] 获取实时行情...")
    fund_quotes = {}
    with ThreadPoolExecutor(max_workers=4) as ex:  # 降低并发数
        futures = {ex.submit(get_etf_quote_tencent, item[0]): item[0] 
                   for item in popular_funds}
        for f in as_completed(futures):
            code = futures[f]
            try:
                q = f.result()
                if q:
                    fund_quotes[code] = q
            except Exception as e:
                print(f"    获取 {code} 行情异常: {e}")
    
    # 构建分析参数
    print("[2/3] 深度分析各基金指标...\n")
    fund_infos = []
    for item in popular_funds:
        code, category, _, idx_info = item
        q = fund_quotes.get(code, {})
        name = q.get("name", code)
        fund_infos.append((code, name, None, idx_info))
    
    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:  # 降低并发数
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
                    
                    fund_type = res.get("基金类型", "passive")
                    fund_score = calc_fund_layer_score(res, fund_type)
                    res["fund_score"] = fund_score
                    
                    comprehensive = idx_quality_score * 0.25 + fund_score * 0.75
                    res["专业评分"] = round(comprehensive, 2)
                    
                    # 格式化输出
                    ar = f"{res['annual_return']*100:.1f}%" if res['annual_return'] else "N/A"
                    te = f"{res['tracking_error']*100:.2f}%" if res['tracking_error'] else "N/A"
                    td = f"{res['tracking_difference']*100:.2f}%" if res.get('tracking_difference') else "N/A"
                    ir = f"{res['information_ratio']:.2f}" if res['information_ratio'] else "N/A"
                    
                    print(f"  {res['基金名称']:<20s} {code}  "
                          f"年化{ar:>8s}  TE{te:>7s}  TD{td:>7s}  IR{ir:>6s}  "
                          f"综合{comprehensive:>5.1f}")
                    results.append(res)
                else:
                    print(f"  {code}: 数据不足，跳过")
            except Exception as e:
                print(f"  {code}: 分析异常 ({e})")
    
    if not results:
        print("\n未获取到有效数据")
        return None
    
    df = pd.DataFrame(results)
    
    # 格式化列
    df["年化收益率"] = df["annual_return"].apply(
        lambda x: f"{x*100:.2f}%" if x is not None and not np.isnan(x) else "N/A")
    df["跟踪误差"] = df["tracking_error"].apply(
        lambda x: f"{x*100:.2f}%" if x is not None and not np.isnan(x) else "N/A")
    df["跟踪偏离度"] = df["tracking_difference"].apply(
        lambda x: f"{x*100:.2f}%" if x is not None and not np.isnan(x) else "N/A")
    df["信息比率"] = df["information_ratio"].apply(
        lambda x: f"{x:.2f}" if x is not None and not np.isnan(x) else "N/A")
    df["基金类型"] = df["基金类型"].apply(
        lambda x: "被动型" if x == "passive" else "增强型")
    
    df = df.sort_values("专业评分", ascending=False).reset_index(drop=True)
    
    # 输出结果
    print("\n" + "=" * 90)
    print("  基金综合排名（全收益指数基准 + 跟踪偏离度 + 收益分解）")
    print("=" * 90)
    
    display_cols = [
        "基金代码", "基金名称", "基金类型", "年化收益率", 
        "跟踪误差", "跟踪偏离度", "信息比率", "专业评分"
    ]
    print(df[display_cols].to_string(index=False))
    
    # 多维度推荐
    print("\n" + "=" * 70)
    print("  多维度推荐")
    print("=" * 70)
    
    # 被动型最优
    passive_df = df[df["基金类型"] == "被动型"]
    if not passive_df.empty:
        best_passive = passive_df.iloc[0]
        print(f"\n  >> 被动型最优: {best_passive['基金名称']}（{best_passive['基金代码']}）")
        print(f"     跟踪误差: {best_passive['跟踪误差']}  "
              f"跟踪偏离度: {best_passive['跟踪偏离度']}")
    
    # 跟踪最紧密
    valid_te = df.dropna(subset=["tracking_error"])
    if not valid_te.empty:
        best_te = valid_te.loc[valid_te["tracking_error"].idxmin()]
        print(f"\n  >> 跟踪最紧密: {best_te['基金名称']}（{best_te['基金代码']}）")
        print(f"     跟踪误差: {best_te['跟踪误差']}")
    
    # 导出
    output_file = "index_fund_professional_result_v2.1.csv"
    df[display_cols].to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\n  完整结果已导出到: {output_file}")
    
    return df


# ============================================================
# 12. 运行入口
# ============================================================
if __name__ == "__main__":
    print("\n指数基金专业筛选工具 V2.1（完整修复版）")
    result = screen_popular_index_funds()
    print("\n风险提示：以上结果基于历史数据和公开信息，不构成投资建议。投资有风险，入市需谨慎。")
    print("方法论文档：被动投资的本质是低成本、高精度地获取市场Beta，任何偏离都必须有合理的补偿。")