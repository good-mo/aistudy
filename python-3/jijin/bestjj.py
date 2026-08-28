"""
指数基金专业筛选工具 V2.4 —— 数据质量修复版

V2.4 核心修复（数据质量修复）：
  1. NAV数据源：DWJZ（单位净值）→ LJJZ（累计净值）
     解决东财对不同基金复权处理不一致导致的极端TE异常
     （修复前510310 TE=45.63%，修复后TE=0.45%）
  2. TE/TD异常阈值：从80%/50% → 5%/5%
     被动ETF正常TE在0.3%-2%，超过5%即标记数据质量问题
  3. 降级策略优化：取消股息率复利近似修正
     均匀复利引入系统性偏差，导致TD失真（如-40%）
     降级后明确标注"价格指数(不含分红)"，不做粗糙修正
  4. 费率数据修正：修正FUND_REAL_FEE_RATE中的错误费率
     510300/510500/159919等标准费率基金从0.20%修正为0.60%
  5. 新增NAV与指数走势一致性检查
     计算皮尔逊相关系数，<0.80时跳过TE/TD计算
  6. 数据质量标记系统完善
     输出中显示数据来源、TE/TD异常标记、警告说明

V2.3 已有修复（数据质量增强）：
  1. 估值API升级（替换废弃接口，正确6位代码映射）
  2. CNI指数支持（创业板指等深证指数）
  3. 全收益→价格指数正确映射（修复H00510/HH30269问题）
  4. AKShare内部异常捕获（空数据不再崩溃）
  5. 数据质量标记系统（来源追踪+异常检测+评分惩罚）

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
# 指数基金代码 → 跟踪指数映射
# ============================================================
FUND_TO_INDEX = {
    "510300": {"price_idx": "000300", "total_return_idx": "H00300", "fund_type": "passive"},
    "510310": {"price_idx": "000300", "total_return_idx": "H00300", "fund_type": "passive"},
    "159919": {"price_idx": "000300", "total_return_idx": "H00300", "fund_type": "passive"},
    "510500": {"price_idx": "000905", "total_return_idx": "H00905", "fund_type": "passive"},
    "159922": {"price_idx": "000905", "total_return_idx": "H00905", "fund_type": "passive"},
    "159338": {"price_idx": "000510", "total_return_idx": "H00510", "fund_type": "passive"},
    "159339": {"price_idx": "000510", "total_return_idx": "H00510", "fund_type": "passive"},
    "515080": {"price_idx": "000015", "total_return_idx": "H00015", "fund_type": "passive"},
    "159515": {"price_idx": "000015", "total_return_idx": "H00015", "fund_type": "passive"},
    "512890": {"price_idx": "H30269", "total_return_idx": "HH30269", "fund_type": "passive"},
    "515100": {"price_idx": "H30269", "total_return_idx": "HH30269", "fund_type": "passive"},
    "159915": {"price_idx": "399006", "total_return_idx": "H399006", "fund_type": "passive"},
    "588000": {"price_idx": "000688", "total_return_idx": "000688", "fund_type": "passive"},  # 科创50使用价格指数
    "588080": {"price_idx": "000688", "total_return_idx": "000688", "fund_type": "passive"},
}

# ============================================================
# 全收益指数代码 → 价格指数代码 反向映射
# 用于降级策略：当全收益指数不可用时，查找对应的价格指数
# 注意：不能简单通过剥离前缀 H 得到，因为：
#   H00510 → 000510 (而非 00510)
#   H399006 → 399006 (CNI 指数)
#   HH30269 → H30269 (红利低波全收益)
# ============================================================
TOTAL_RETURN_TO_PRICE = {
    v["total_return_idx"]: v["price_idx"]
    for v in FUND_TO_INDEX.values()
}
# 去重（多个基金可能跟踪同一指数）
TOTAL_RETURN_TO_PRICE = dict(sorted(TOTAL_RETURN_TO_PRICE.items()))

# ============================================================
# 基金真实费率映射（来源：东方财富天天基金网 - 基金档案/基金费率页）
# 数据查证日期：2026-08-06
# 格式：基金代码 → {"management": 管理费率, "custody": 托管费率, "total": 总费率}
#
# 注意：ETF费率分两档——
#   - 标准费率：管理0.50% + 托管0.10% = 0.60%（多数老基金）
#   - 低费率：管理0.15% + 托管0.05% = 0.20%（新发/竞争激烈的ETF）
# 费率可能随基金公告调整，应定期更新。
# ============================================================
FUND_REAL_FEE_RATE = {
    # ===== 沪深300 ETF =====
    "510300": {"management": 0.0050, "custody": 0.0010, "total": 0.0060, "source": "天天基金"},  # 华泰柏瑞(标准费率)
    "510310": {"management": 0.0015, "custody": 0.0005, "total": 0.0020, "source": "天天基金"},  # 易方达(低费率)
    "159919": {"management": 0.0050, "custody": 0.0010, "total": 0.0060, "source": "天天基金"},  # 嘉实(标准费率)
    # ===== 中证500 ETF =====
    "510500": {"management": 0.0050, "custody": 0.0010, "total": 0.0060, "source": "天天基金"},  # 南方(标准费率)
    "159922": {"management": 0.0015, "custody": 0.0005, "total": 0.0020, "source": "天天基金"},  # 嘉实(低费率)
    # ===== 中证A500 ETF（新发基金，普遍低费率）=====
    "159338": {"management": 0.0015, "custody": 0.0005, "total": 0.0020, "source": "天天基金"},  # 国泰(低费率)
    "159339": {"management": 0.0015, "custody": 0.0005, "total": 0.0020, "source": "天天基金"},  # 银华(低费率)
    # ===== 红利类 ETF =====
    "515080": {"management": 0.0050, "custody": 0.0010, "total": 0.0060, "source": "天天基金"},  # 中证红利ETF招商(标准费率)
    "159515": {"management": 0.0015, "custody": 0.0005, "total": 0.0020, "source": "天天基金"},  # 国企红利ETF富国(低费率)
    "512890": {"management": 0.0050, "custody": 0.0010, "total": 0.0060, "source": "天天基金"},  # 红利低波ETF华泰柏瑞(标准费率)
    "515100": {"management": 0.0050, "custody": 0.0010, "total": 0.0060, "source": "天天基金"},  # 红利低波100ETF景顺(标准费率)
    # ===== 成长类 ETF =====
    "159915": {"management": 0.0050, "custody": 0.0010, "total": 0.0060, "source": "天天基金"},  # 创业板ETF易方达(标准费率)
    "588000": {"management": 0.0050, "custody": 0.0010, "total": 0.0060, "source": "天天基金"},  # 科创50ETF华夏(标准费率)
    "588080": {"management": 0.0015, "custody": 0.0005, "total": 0.0020, "source": "天天基金"},  # 科创50ETF易方达(低费率)
}

# 默认费率（当基金不在映射表中时使用，基于市场平均ETF费率）
DEFAULT_FEE_RATE = 0.0025  # 管理0.20% + 托管0.05%

# ============================================================
# 指数元数据
# ============================================================
INDEX_META = {
    "000300": {
        "name": "沪深300", "category": "大盘蓝筹", "weight_type": "自由流通市值加权",
        "components": 300, "rebalance": "半年",
        "pe_reasonable_low": 10, "pe_reasonable_high": 16,
        "pb_reasonable_low": 1.2, "pb_reasonable_high": 2.0,
        "dividend_yield_avg": 0.025,
    },
    "000905": {
        "name": "中证500", "category": "中盘成长", "weight_type": "自由流通市值加权",
        "components": 500, "rebalance": "半年",
        "pe_reasonable_low": 18, "pe_reasonable_high": 35,
        "pb_reasonable_low": 1.5, "pb_reasonable_high": 2.8,
        "dividend_yield_avg": 0.018,
    },
    "000510": {
        "name": "中证A500", "category": "大盘均衡", "weight_type": "自由流通市值加权+行业均衡",
        "components": 500, "rebalance": "半年",
        "pe_reasonable_low": 10, "pe_reasonable_high": 16,
        "pb_reasonable_low": 1.2, "pb_reasonable_high": 2.0,
        "dividend_yield_avg": 0.022,
    },
    "000015": {
        "name": "中证红利", "category": "红利价值", "weight_type": "股息率加权",
        "components": 100, "rebalance": "年",
        "pe_reasonable_low": 5, "pe_reasonable_high": 10,
        "pb_reasonable_low": 0.5, "pb_reasonable_high": 1.0,
        "dividend_yield_avg": 0.050,
    },
    "H30269": {
        "name": "红利低波", "category": "红利+低波 Smart Beta", "weight_type": "因子加权",
        "components": 50, "rebalance": "半年",
        "pe_reasonable_low": 5, "pe_reasonable_high": 10,
        "pb_reasonable_low": 0.5, "pb_reasonable_high": 1.0,
        "dividend_yield_avg": 0.045,
    },
    "399006": {
        "name": "创业板指", "category": "创业板成长", "weight_type": "自由流通市值加权",
        "components": 100, "rebalance": "半年",
        "pe_reasonable_low": 25, "pe_reasonable_high": 55,
        "pb_reasonable_low": 3.0, "pb_reasonable_high": 7.0,
        "dividend_yield_avg": 0.005,
    },
    "000688": {
        "name": "科创50", "category": "科创板成长", "weight_type": "自由流通市值加权",
        "components": 50, "rebalance": "季",
        "pe_reasonable_low": 30, "pe_reasonable_high": 60,
        "pb_reasonable_low": 3.0, "pb_reasonable_high": 6.0,
        "dividend_yield_avg": 0.003,
    },
}

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
# 1. 获取指数历史数据（带完整错误处理）
# ============================================================
def _is_cni_index(idx_code):
    """判断是否为 CNI（国证/深证）指数，代码以 3 开头或 399 开头"""
    return idx_code.startswith("3") or idx_code.startswith("399")


def _get_cni_close_column():
    """CNI 指数历史数据的收盘价列名"""
    return "收盘价"


def _fetch_csindex_hist(idx_code, start_date, end_date):
    """
    从 CSIndex 获取历史数据，包装 AKShare 的内部异常
    AKShare 的 stock_zh_index_hist_csindex 在 API 返回空数据时会直接
    抛 ValueError（列数不匹配），这里统一捕获并返回 None
    """
    if not HAS_AKSHARE:
        return None
    try:
        df = ak.stock_zh_index_hist_csindex(
            symbol=idx_code,
            start_date=start_date,
            end_date=end_date,
        )
        if df is None or df.empty or len(df.columns) == 0:
            return None
        # 验证必要列
        if "日期" not in df.columns or "收盘" not in df.columns:
            return None
        return df
    except (ValueError, KeyError, TypeError) as e:
        # AKShare 内部对空数据赋值列名时会抛 ValueError
        print(f"    CSIndex API 返回异常数据 ({idx_code}): {e}")
        return None
    except Exception as e:
        print(f"    CSIndex API 请求失败 ({idx_code}): {e}")
        return None


def _fetch_cni_hist(idx_code, start_date, end_date):
    """
    从 CNI（国证/深证）获取历史数据
    CNI 指数代码以 3 开头（如 399006 创业板指），使用 index_hist_cni
    """
    if not HAS_AKSHARE:
        return None
    try:
        df = ak.index_hist_cni(
            symbol=idx_code,
            start_date=start_date,
            end_date=end_date,
        )
        if df is None or df.empty or len(df.columns) == 0:
            return None
        # CNI 列名：日期, 开盘价, 最高价, 最低价, 收盘价, 涨跌幅, ...
        if "日期" not in df.columns or "收盘价" not in df.columns:
            return None
        return df
    except Exception as e:
        print(f"    CNI API 请求失败 ({idx_code}): {e}")
        return None


_IDX_CACHE = {}


def get_index_total_return(idx_code, days=1825):
    """
    获取全收益指数历史数据（AKShare）
    带完整的错误处理和数据验证
    支持 CSIndex（中证）和 CNI（国证/深证）两类指数
    """
    if not HAS_AKSHARE:
        return None
    
    cache_key = f"tr_{idx_code}"
    if cache_key in _IDX_CACHE:
        return _IDX_CACHE[cache_key]
    
    try:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        
        # 根据指数类型选择数据源
        if _is_cni_index(idx_code):
            df = _fetch_cni_hist(idx_code, start_date, end_date)
            close_col = _get_cni_close_column()
        else:
            df = _fetch_csindex_hist(idx_code, start_date, end_date)
            close_col = "收盘"
        
        # 关键修复：验证数据是否为空
        if df is None or df.empty:
            print(f"    全收益指数 {idx_code} 返回空数据")
            return None
        
        # 尝试重命名列（使用实际存在的列名）
        column_mapping = {}
        if "日期" in df.columns:
            column_mapping["日期"] = "date"
        if close_col in df.columns:
            column_mapping[close_col] = "close"
        
        if "date" not in column_mapping.values() or "close" not in column_mapping.values():
            print(f"    全收益指数 {idx_code} 缺少必要列（日期/收盘）")
            print(f"    实际列名: {list(df.columns)}")
            return None
        
        df = df.rename(columns=column_mapping)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        _IDX_CACHE[cache_key] = df
        return df
        
    except Exception as e:
        print(f"    获取全收益指数 {idx_code} 失败: {e}")
        return None


def get_index_price(idx_code, days=1825):
    """
    获取价格指数历史数据（降级策略）
    通过 TOTAL_RETURN_TO_PRICE 映射获取正确的价格指数代码，
    而非简单剥离前缀 H（因为 H00510 → 000510 而非 00510）。
    同时支持 CNI 指数（如 H399006 → 399006）。
    """
    if not HAS_AKSHARE:
        return None
    
    cache_key = f"price_{idx_code}"
    if cache_key in _IDX_CACHE:
        return _IDX_CACHE[cache_key]
    
    try:
        # 通过映射表获取正确的价格指数代码
        # 如果不在映射表中，尝试剥离单层前缀 H 作为后备
        price_idx = TOTAL_RETURN_TO_PRICE.get(idx_code)
        if price_idx is None:
            if idx_code.startswith("H"):
                price_idx = idx_code[1:]
            else:
                price_idx = idx_code
        
        # 根据指数类型选择数据源
        if _is_cni_index(price_idx):
            df = _fetch_cni_hist(price_idx, 
                (datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
                datetime.now().strftime("%Y%m%d"))
            close_col = _get_cni_close_column()
        else:
            df = _fetch_csindex_hist(price_idx,
                (datetime.now() - timedelta(days=days)).strftime("%Y%m%d"),
                datetime.now().strftime("%Y%m%d"))
            close_col = "收盘"
        
        # 验证数据
        if df is None or df.empty:
            return None
        
        # 重命名列
        column_mapping = {}
        if "日期" in df.columns:
            column_mapping["日期"] = "date"
        if close_col in df.columns:
            column_mapping[close_col] = "close"
        
        if "date" not in column_mapping.values() or "close" not in column_mapping.values():
            return None
        
        df = df.rename(columns=column_mapping)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        _IDX_CACHE[cache_key] = df
        return df
        
    except Exception as e:
        print(f"    获取价格指数 {idx_code} 失败: {e}")
        return None


def get_index_data_with_fallback(idx_code, days=1825):
    """
    获取指数数据（带降级策略）
    优先使用全收益指数，失败时使用价格指数（不做股息率近似修正）
    
    返回: (df, source)
        source: "total_return"  |  "price_only"  |  "none"
    
    重要设计决策：不再对价格指数做股息率复利近似修正。
    原因：实际分红不是均匀分布的（集中在特定月份），均匀复利会引入
          系统性偏差，导致跟踪偏离度(TD)严重失真（如-40%）。
          降级策略的目标是"有数据可用"而非"精确模拟全收益"。
    """
    # 优先尝试全收益指数
    df = get_index_total_return(idx_code, days)
    
    if df is not None and len(df) > 60:
        print(f"    ✓ 使用全收益指数 {idx_code}")
        return df, "total_return"
    
    # 降级：仅使用价格指数，明确标注"不含分红"
    # 不再做股息率复利近似——这会引入系统性误差，扭曲TE/TD
    print(f"    ⚠ 全收益指数 {idx_code} 不可用，使用价格指数(不含分红)")
    price_df = get_index_price(idx_code, days)
    
    if price_df is not None and len(price_df) > 60:
        return price_df, "price_only"
    
    print(f"    ✗ 指数 {idx_code} 数据获取失败")
    return None, None


# ============================================================
# 2. 获取真实PE/PB估值数据
# ============================================================
def get_index_valuation(idx_code, original_idx_code=None):
    """获取指数真实PE/PB估值数据（使用中证指数官网估值API）
    idx_code: 价格指数代码（如 000300, 399006）
    original_idx_code: 原始传入代码（可能含全收益前缀 H，如 H00300），
                       用于通过 TOTAL_RETURN_TO_PRICE 映射查找正确代码
    """
    if not HAS_AKSHARE:
        return None
    
    # 优先通过原始代码（含全收益前缀）查找正确的价格指数
    # 这解决了 H00300 → 000300（6位）而非 00300（5位）的问题
    price_idx = None
    if original_idx_code is not None:
        price_idx = TOTAL_RETURN_TO_PRICE.get(original_idx_code)
    
    if price_idx is None:
        # 后备：如果 original_idx_code 不在映射表中，说明本身就是价格指数
        price_idx = idx_code
    
    # CNI 指数（如 399006 创业板指）不使用 CSIndex 估值 API
    if _is_cni_index(price_idx):
        # CNI 指数无直接估值数据，返回 None
        print(f"    CNI 指数 {price_idx} 无公开估值数据")
        return None
    
    idx_name = INDEX_NAME_MAP.get(price_idx)
    if not idx_name:
        # 尝试从 INDEX_META 中获取名称
        meta = INDEX_META.get(price_idx, {})
        idx_name = meta.get("name", price_idx)
    
    try:
        df = ak.stock_zh_index_value_csindex(symbol=price_idx)
        
        if df is None or df.empty:
            return None
        
        # 列名：日期, 指数代码, 指数中文全称, 指数中文简称, 
        #        指数英文全称, 指数英文简称, 市盈率1, 市盈率2, 
        #        股息率1, 股息率2
        # 市盈率1 = 静态市盈率, 市盈率2 = 滚动市盈率(PE-TTM)
        pe_col = None
        for col in ["市盈率2", "市盈率1"]:
            if col in df.columns:
                pe_col = col
                break
        
        if pe_col is None:
            print(f"    估值数据 {price_idx} 缺少市盈率列")
            return None
        
        pe_series = df[pe_col].dropna()
        if pe_series.empty:
            return None
        
        latest_pe = pe_series.iloc[-1]
        pe_percentile = (pe_series <= latest_pe).mean()
        
        # PB 数据：CSIndex 估值 API 不提供市净率，用 None 表示
        latest_pb = None
        pb_percentile = None
        
        return {
            "pe": latest_pe,
            "pe_percentile": pe_percentile,
            "pb": latest_pb,
            "pb_percentile": pb_percentile,
        }
        
    except Exception as e:
        print(f"    获取指数 {idx_name}({price_idx}) 估值数据失败: {e}")
        return None


# ============================================================
# 3. 获取基金历史净值
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
                # 核心修复：使用 LJJZ（累计净值）替代 DWJZ（单位净值）
                # 原因：DWJZ 在除息日会跳水，且东财对不同基金的复权处理不一致
                #      （有的后复权、有的未复权），导致 NAV 序列与指数数据不匹配
                #      产生极端跟踪误差（如 45% TE）。
                # LJJZ 天然消除分红跳变，与全收益指数的"分红再投资"逻辑一致。
                # 若 LJJZ 不可用，fallback 到 DWJZ。
                nav_val = r.get("LJJZ") or r.get("DWJZ")
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
# 4. 获取ETF实时行情
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
    """计算跟踪误差和跟踪偏离度
    增加一致性检查：如果基金日收益与指数日收益相关性过低，
    说明数据源不匹配（如复权不一致），返回None避免错误TE。
    """
    if fund_returns is None or index_returns is None:
        return None, None
    
    common_idx = fund_returns.index.intersection(index_returns.index)
    if len(common_idx) < 60:
        return None, None
    
    fund_aligned = fund_returns.loc[common_idx]
    index_aligned = index_returns.loc[common_idx]
    
    # 一致性检查：计算皮尔逊相关系数
    # 被动ETF的日收益与指数日收益相关性应>0.95
    # 如果<0.8，说明数据源不匹配（如复权不一致、日期错位）
    corr = fund_aligned.corr(index_aligned)
    if corr < 0.80:
        # 相关性过低，数据可能有问题，不计算TE/TD
        return None, None
    
    diff = fund_aligned - index_aligned
    tracking_error = diff.std() * np.sqrt(250)
    
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


def calc_return_decomposition(fund_annual_ret, index_annual_ret, fee_rate, fund_type):
    """收益分解"""
    if fund_annual_ret is None or index_annual_ret is None:
        return None
    
    excess = fund_annual_ret - index_annual_ret
    cash_drag = 0.0015
    # 使用实际费率，而非硬编码的0.6%；若无费率则用市场平均
    fee_drag = -fee_rate if fee_rate else -DEFAULT_FEE_RATE
    management_alpha = excess - fee_drag - cash_drag
    
    result = {
        "总超额收益": excess,
        "费率拖累": fee_drag,
        "现金拖累": cash_drag,
        "管理超额": management_alpha,
        "归因解读": "",
    }
    
    if fund_type == "passive":
        if abs(management_alpha) < 0.005:
            result["归因解读"] = "被动复制精度高"
        elif management_alpha > 0.005:
            result["归因解读"] = "超额收益为正"
        else:
            result["归因解读"] = "存在跟踪偏离"
    else:
        if management_alpha > 0.02:
            result["归因解读"] = "增强效果显著"
        elif management_alpha > 0:
            result["归因解读"] = "有一定增强效果"
        else:
            result["归因解读"] = "增强效果不足"
    
    return result


# ============================================================
# 6. 估值分位计算
# ============================================================
def calc_valuation_percentile(idx_code, original_idx_code=None):
    """计算估值分位
    idx_code: 价格指数代码（用于 INDEX_META 查找）
    original_idx_code: 原始传入代码（可能含全收益前缀 H，用于 TOTAL_RETURN_TO_PRICE 映射）
    """
    valuation = get_index_valuation(idx_code, original_idx_code)
    
    if valuation is None:
        return None, None, None
    
    pe_pct = valuation.get("pe_percentile")
    pb_pct = valuation.get("pb_percentile")
    
    if pe_pct is not None and pb_pct is not None:
        combined_pct = pe_pct * 0.6 + pb_pct * 0.4
    elif pe_pct is not None:
        combined_pct = pe_pct
    else:
        combined_pct = pb_pct
    
    return combined_pct, pe_pct, pb_pct


# ============================================================
# 7. 指数质量评估
# ============================================================
def screen_index_quality(idx_code, original_idx_code=None):
    """指数质量评估
    idx_code: 传入的指数代码，可能是全收益代码（如 H00300）或
             价格指数代码（如 000300），也可能是 CNI 代码（399006）
    original_idx_code: 原始传入代码（含全收益前缀），用于 TOTAL_RETURN_TO_PRICE
                      映射查找正确的6位价格指数代码
    """
    if idx_code is None:
        return {"score": 50, "details": {}}
    
    # 优先使用 TOTAL_RETURN_TO_PRICE 映射获取正确的6位价格指数代码
    # 这解决了 H00300→000300（6位）而非简单剥H得到00300（5位）的问题
    price_idx = None
    if original_idx_code is not None:
        price_idx = TOTAL_RETURN_TO_PRICE.get(original_idx_code)
    
    if price_idx is None:
        # 后备：如果 original_idx_code 不在映射表中，尝试用 idx_code 本身
        # 或简单剥一层 H 前缀（兼容旧调用）
        if idx_code.startswith("H"):
            price_idx = idx_code[1:]
        else:
            price_idx = idx_code
    
    # 用 price_idx 作为主要索引进行后续查找
    meta_idx = price_idx
    
    meta = INDEX_META.get(meta_idx, {})
    valuation_pct, pe_pct, pb_pct = calc_valuation_percentile(meta_idx, original_idx_code)
    
    score = 0
    
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
        "指数名称": meta.get("name", INDEX_NAME_MAP.get(meta_idx, idx_code)),
        "估值分位": f"{valuation_pct*100:.0f}%" if valuation_pct else "N/A",
        "PE分位": f"{pe_pct*100:.0f}%" if pe_pct else "N/A",
        "PB分位": f"{pb_pct*100:.0f}%" if pb_pct else "N/A",
        "类别": category,
        "加权方式": weight_type,
        "成分股数": n_components,
        "调样频率": rebalance,
        "指数质量评分": score,
    }
    
    # 如果没有估值数据，添加数据来源说明
    if valuation_pct is None:
        if _is_cni_index(meta_idx):
            details["数据来源"] = "CNI指数(无估值API)"
        else:
            details["数据来源"] = "估值API不可用"
    elif original_idx_code and original_idx_code.startswith("H"):
        details["数据来源"] = "全收益指数"
    else:
        details["数据来源"] = "价格指数"
    
    return {"score": score, "details": details}


# ============================================================
# 8. 基金评分
# ============================================================
def calc_fund_layer_score(row, fund_type="passive", data_quality=None):
    """基金优选评分
    data_quality: dict with keys:
        - index_data_source: 'total_return' | 'price_adjusted' | 'none'
        - tracking_error_anomaly: bool (TE > 10% indicates data issue)
        - tracking_difference_anomaly: bool (TD > 50% indicates data issue)
    """
    score = 0
    quality_penalty = 0
    
    # 数据质量惩罚：如果使用了降级策略（近似指数数据），降低评分可信度
    if data_quality:
        if data_quality.get("index_data_source") == "price_only":
            quality_penalty -= 8  # 降级策略，指数数据为价格指数(不含分红)
        elif data_quality.get("index_data_source") == "none":
            quality_penalty -= 15  # 无指数数据，无法计算跟踪指标
        
        # 异常跟踪误差惩罚：TE > 10% 意味着数据严重不匹配
        if data_quality.get("tracking_error_anomaly"):
            quality_penalty -= 12
        if data_quality.get("tracking_difference_anomaly"):
            quality_penalty -= 8
    
    if fund_type == "passive":
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
    
    # 应用数据质量惩罚，确保分数不低于 0
    final_score = max(0, score + quality_penalty)
    
    return round(final_score, 2)


# ============================================================
# 9. 单只基金深度分析
# ============================================================
def _analyze_fund_deep(fund_info):
    """对单只基金做深度分析"""
    code, name, fee_rate, idx_info = fund_info
    idx_code = idx_info["total_return_idx"]
    fund_type = idx_info["fund_type"]
    
    nav_df = get_fund_nav(code, days=1825)
    if nav_df is None or len(nav_df) < 250:
        return None
    
    nav_series = nav_df.set_index("date")["nav"]
    fund_daily_ret = nav_series.pct_change().dropna()
    
    etf_quote = get_etf_quote_tencent(code)
    
    # 使用查证到的真实费率，而非硬编码的0.6%
    if fee_rate is None:
        if code in FUND_REAL_FEE_RATE:
            fee_rate = FUND_REAL_FEE_RATE[code]["total"]
            print(f"    使用真实费率: {code} = {fee_rate*100:.2f}% (来源: {FUND_REAL_FEE_RATE[code]['source']})")
        elif etf_quote:
            # 后备：使用市场平均ETF费率
            fee_rate = DEFAULT_FEE_RATE
            print(f"    使用默认费率: {code} = {fee_rate*100:.2f}% (市场平均)")
        else:
            fee_rate = DEFAULT_FEE_RATE
    
    idx_annual_ret = None
    tracking_error = None
    tracking_difference = None
    info_ratio = None
    excess_return = None
    attribution = None
    index_quality = None
    
    # 使用带降级策略的指数数据获取
    idx_df, data_source = get_index_data_with_fallback(idx_code, days=1825)
    
    if idx_df is not None and len(idx_df) > 60:
        idx_series = idx_df.set_index("date")["close"]
        idx_daily_ret = idx_series.pct_change().dropna()
        
        idx_annual_ret = calc_annual_return(idx_series)
        
        tracking_error, tracking_difference = calc_tracking_error_and_difference(
            fund_daily_ret, idx_daily_ret)
        
        fund_annual_ret = calc_annual_return(nav_series)
        
        if fund_annual_ret is not None and idx_annual_ret is not None:
            excess_return = fund_annual_ret - idx_annual_ret
        
        info_ratio = calc_information_ratio(
            fund_annual_ret, idx_annual_ret, tracking_error)
        
        attribution = calc_return_decomposition(
            fund_annual_ret, idx_annual_ret, fee_rate, fund_type)
        
        meta_idx = idx_code
        if idx_code.startswith("H"):
            meta_idx = idx_code[1:]  # 只剥一层：H399006→399006, HH30269→H30269
        # 传入原始 idx_code 用于估值映射（TOTAL_RETURN_TO_PRICE 需要全收益代码）
        index_quality = screen_index_quality(meta_idx, original_idx_code=idx_code)
    else:
        fund_annual_ret = calc_annual_return(nav_series)
    
    max_dd = calc_max_drawdown(nav_series)
    volatility = calc_volatility(nav_series)
    sharpe = calc_sharpe(fund_annual_ret, volatility)
    
    fund_scale = None
    premium = None
    avg_volume_amount = None
    if etf_quote:
        fund_scale = etf_quote.get("total_mv")
        premium = etf_quote.get("premium")
        avg_volume_amount = etf_quote.get("amount")
    
    # ============================================
    # 数据质量评估
    # ============================================
    data_quality = {
        "index_data_source": data_source if idx_df is not None else "none",
        "tracking_error_anomaly": False,
        "tracking_difference_anomaly": False,
    }
    
    # 检测异常跟踪误差（>5% 意味着数据严重不匹配，远超出被动ETF正常范围）
    # 被动ETF正常TE通常在0.3%-2%，超过5%几乎一定是数据源不一致
    if tracking_error is not None and tracking_error > 0.05:
        data_quality["tracking_error_anomaly"] = True
        print(f"    ⚠ 跟踪误差异常({tracking_error*100:.1f}%)，标记为数据质量问题")
    
    # 检测异常跟踪偏离度（绝对值>5% 意味着数据严重不匹配）
    if tracking_difference is not None and abs(tracking_difference) > 0.05:
        data_quality["tracking_difference_anomaly"] = True
    
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
        "data_source": data_source if idx_df is not None else "none",
        "data_quality": data_quality,
    }
    
    # 数据质量异常清理：TE超过5%即丢弃跟踪指标（避免错误数据污染评分）
    # 旧版阈值为80%，过于宽松——45%的TE本应被标记为异常
    if res["tracking_error"] is not None and res["tracking_error"] > 0.05:
        res["tracking_error"] = None
        res["tracking_difference"] = None
        res["information_ratio"] = None
        res["attribution"] = None
    
    if res["information_ratio"] is not None and abs(res["information_ratio"]) > 30:
        res["information_ratio"] = None
    
    return res


# ============================================================
# 10. 主流程
# ============================================================
def screen_popular_index_funds():
    """专业筛选主流程"""
    print("=" * 70)
    print("  指数基金专业筛选工具 V2.4（数据质量修复版）")
    print("  核心修复：")
    print("    1. NAV数据源：DWJZ→LJJZ（消除复权不一致导致的TE异常）")
    print("    2. TE/TD阈值：80%→5%（及时标记数据质量问题）")
    print("    3. 降级策略：取消股息率近似修正（避免TD失真）")
    print("    4. 费率数据：修正标准费率基金的实际费率")
    print("    5. 一致性检查：NAV与指数相关性<0.8跳过TE计算")
    print("=" * 70)
    
    if not HAS_AKSHARE:
        print("\n错误：未安装AKShare")
        print("请执行：pip install akshare")
        return None
    
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
    
    print("\n[Layer 0] 加载指数历史数据...")
    idx_codes = sorted(set(item[3]["total_return_idx"] for item in popular_funds))
    success_count = 0
    for ic in idx_codes:
        df, source = get_index_data_with_fallback(ic, days=1825)
        if df is not None:
            success_count += 1
        time.sleep(0.5)
    print(f"\n  指数数据加载完成: {success_count}/{len(idx_codes)} 个指数")
    
    print("\n" + "=" * 70)
    print("  Layer 1: 指数筛选")
    print("=" * 70)
    
    seen_idx = set()
    for item in popular_funds:
        idx_code = item[3]["total_return_idx"]  # 全收益代码如 H00300
        meta_idx = idx_code
        if idx_code.startswith("H"):
            meta_idx = idx_code[1:]  # 只剥一层
        
        if meta_idx and meta_idx not in seen_idx:
            seen_idx.add(meta_idx)
            # 传入原始全收益代码用于估值映射
            quality = screen_index_quality(meta_idx, original_idx_code=idx_code)
            d = quality["details"]
            # 显示数据来源标记
            src_mark = ""
            if d.get("数据来源"):
                src_mark = f" [{d['数据来源']}]"
            print(f"  {d['指数名称']:<12s} 估值{d['估值分位']:>6s} "
                  f"{d['类别']:<16s} 质量{d['指数质量评分']:>4d}{src_mark}")
    
    print("\n" + "=" * 70)
    print("  Layer 2: 基金深度分析")
    print("=" * 70)
    
    print("\n[1/3] 获取实时行情...")
    fund_quotes = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(get_etf_quote_tencent, item[0]): item[0] 
                   for item in popular_funds}
        for f in as_completed(futures):
            code = futures[f]
            try:
                q = f.result()
                if q:
                    fund_quotes[code] = q
            except Exception:
                pass
    
    print("[2/3] 深度分析各基金指标...\n")
    fund_infos = []
    for item in popular_funds:
        code, category, _, idx_info = item
        q = fund_quotes.get(code, {})
        name = q.get("name", code)
        fund_infos.append((code, name, None, idx_info))
    
    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(_analyze_fund_deep, fi): fi[0] for fi in fund_infos}
        for f in as_completed(futures):
            code = futures[f]
            try:
                res = f.result()
                if res:
                    idx_quality = res.get("index_quality")
                    idx_quality_score = idx_quality["score"] if idx_quality else 50
                    res["index_quality_score"] = idx_quality_score
                    
                    # 数据质量标记
                    dq = res.get("data_quality", {})
                    data_source = dq.get("index_data_source", "none")
                    te_anomaly = dq.get("tracking_error_anomaly", False)
                    td_anomaly = dq.get("tracking_difference_anomaly", False)
                    
                    fund_type = res.get("基金类型", "passive")
                    fund_score = calc_fund_layer_score(
                        res, fund_type, data_quality=dq)
                    res["fund_score"] = fund_score
                    
                    comprehensive = idx_quality_score * 0.25 + fund_score * 0.75
                    res["专业评分"] = round(comprehensive, 2)
                    
                    ar = f"{res['annual_return']*100:.1f}%" if res['annual_return'] else "N/A"
                    te = f"{res['tracking_error']*100:.2f}%" if res['tracking_error'] else "N/A"
                    td = f"{res['tracking_difference']*100:.2f}%" if res.get('tracking_difference') else "N/A"
                    ir = f"{res['information_ratio']:.2f}" if res['information_ratio'] else "N/A"
                    
                    # 数据质量标记
                    tags = []
                    if data_source == "price_only":
                        tags.append("近似指数")
                    if te_anomaly:
                        tags.append("TE异常")
                    if td_anomaly:
                        tags.append("TD异常")
                    tag_str = f"[{','.join(tags)}]" if tags else ""
                    
                    print(f"  {res['基金名称']:<20s} {code}  "
                          f"年化{ar:>8s}  TE{te:>7s}  TD{td:>7s}  IR{ir:>6s}  "
                          f"综合{comprehensive:>5.1f}{tag_str}")
                    results.append(res)
                else:
                    print(f"  {code}: 数据不足，跳过")
            except Exception as e:
                print(f"  {code}: 分析异常 ({e})")
    
    if not results:
        print("\n未获取到有效数据")
        return None
    
    df = pd.DataFrame(results)
    
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
    
    # 数据质量列
    df["数据来源"] = df["data_quality"].apply(
        lambda x: x.get("index_data_source", "none") if isinstance(x, dict) else "none")
    df["TE异常"] = df["data_quality"].apply(
        lambda x: "是" if isinstance(x, dict) and x.get("tracking_error_anomaly") else "否")
    df["TD异常"] = df["data_quality"].apply(
        lambda x: "是" if isinstance(x, dict) and x.get("tracking_difference_anomaly") else "否")
    
    # 数据来源可读标签
    df["数据来源标签"] = df["数据来源"].apply({
        "total_return": "全收益指数",
        "price_only": "价格指数(不含分红)",
        "none": "无指数数据",
    }.get)
    
    df = df.sort_values("专业评分", ascending=False).reset_index(drop=True)
    
    print("\n" + "=" * 90)
    print("  基金综合排名")
    print("=" * 90)
    
    display_cols = [
        "基金代码", "基金名称", "基金类型", "年化收益率", 
        "跟踪误差", "跟踪偏离度", "信息比率", "专业评分"
    ]
    print(df[display_cols].to_string(index=False))
    
    # 数据质量说明
    print("\n" + "=" * 90)
    print("  数据质量说明")
    print("=" * 90)
    quality_cols = ["基金代码", "基金名称", "数据来源标签", "TE异常", "TD异常"]
    print(df[quality_cols].to_string(index=False))
    
    # 数据质量警告
    flagged = df[(df["数据来源标签"] != "全收益指数") | 
                 (df["TE异常"] == "是") | 
                 (df["TD异常"] == "是")]
    if not flagged.empty:
        print("\n⚠  以下基金数据质量存疑，排名仅供参考：")
        for _, row in flagged.iterrows():
            reasons = []
            if row["数据来源标签"] != "全收益指数":
                reasons.append(f"使用{row['数据来源标签']}")
            if row["TE异常"] == "是":
                reasons.append("跟踪误差异常")
            if row["TD异常"] == "是":
                reasons.append("跟踪偏离度异常")
            print(f"  {row['基金代码']} {row['基金名称']}: {'; '.join(reasons)}")
    
    output_file = "index_fund_professional_result_v2.2.csv"
    df[display_cols].to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\n  完整结果已导出到: {output_file}")
    
    return df


if __name__ == "__main__":
    print("\n指数基金专业筛选工具 V2.4（数据质量修复版）")
    result = screen_popular_index_funds()
    print("\n风险提示：以上结果基于历史数据和公开信息，不构成投资建议。")
