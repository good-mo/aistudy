"""
基金筛选系统 —— 基于资深基金经理逻辑的买入/卖出决策
数据源：腾讯财经 + 东方财富公开API + akshare
依赖：pip install pandas numpy requests akshare
"""

import pandas as pd
import numpy as np
import requests
import time
import re
import json
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 宏观周期判断模块（v3 —— 动态自动获取宏观数据）
# ============================================================
MACRO_STATE = {
    "pmi_manufacturing": None,
    "pmi_trend": None,
    "csi300_pe": None,
    "bond_10y": None,
    "equity_risk_premium": None,
    "cycle_phase": None,
    "preferred_style": None,
    "data_source": "manual_fallback",   # auto / manual_fallback
}

# ---- 默认回退值（网络异常时使用） ----
_MACRO_FALLBACK = {
    "pmi_manufacturing": 49.4,
    "csi300_pe": 14.8,
    "bond_10y": 1.72,
}


def fetch_macro_data_akshare(force_refresh: bool = False) -> dict:
    """通过 akshare 自动获取实时宏观数据：PMI、沪深300 PE、10Y国债收益率"""
    # 缓存：macro_cache.json，1天过期
    cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "cache", "macro_cache.json")
    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cached = json.load(f)
            cached_time = cached.get("_cached_at", "")
            if cached_time and (datetime.now() - datetime.strptime(cached_time, "%Y-%m-%d")).days <= 1:
                return cached
        except Exception:
            pass

    result = {}
    try:
        import akshare as ak
        # 1. 制造业PMI（最新一个月）
        try:
            pmi_df = ak.macro_china_pmi()
            if pmi_df is not None and len(pmi_df) > 0:
                latest_pmi = float(pmi_df.iloc[-1]["制造业"])
                result["pmi_manufacturing"] = latest_pmi
        except Exception:
            pass

        # 2. 沪深300 PE（通过指数估值）
        try:
            pe_df = ak.stock_zh_index_value_csindex(symbol="000300")
            if pe_df is not None and len(pe_df) > 0:
                latest_pe = float(pe_df.iloc[-1]["pe"])
                result["csi300_pe"] = latest_pe
        except Exception:
            pass

        # 3. 10年期国债收益率
        try:
            bond_df = ak.bond_zh_us_rate()
            if bond_df is not None and len(bond_df) > 0:
                latest_bond = float(bond_df.iloc[-1]["中国国债收益率10年"])
                result["bond_10y"] = latest_bond
        except Exception:
            pass

        result["_cached_at"] = datetime.now().strftime("%Y-%m-%d")
        # 保存缓存
        try:
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, "w") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    except Exception:
        pass

    return result


def init_macro_state(force_refresh: bool = False):
    """初始化宏观状态（优先自动获取，失败则用默认值）"""
    global MACRO_STATE

    # 尝试自动获取
    macro_data = fetch_macro_data_akshare(force_refresh)

    pmi = macro_data.get("pmi_manufacturing")
    pe = macro_data.get("csi300_pe")
    bond = macro_data.get("bond_10y")

    auto_ok = all(v is not None for v in [pmi, pe, bond])

    if auto_ok:
        MACRO_STATE["data_source"] = "auto"
    else:
        # 回退到默认值
        pmi = _MACRO_FALLBACK["pmi_manufacturing"]
        pe = _MACRO_FALLBACK["csi300_pe"]
        bond = _MACRO_FALLBACK["bond_10y"]
        MACRO_STATE["data_source"] = "manual_fallback"

    MACRO_STATE["pmi_manufacturing"] = pmi
    MACRO_STATE["csi300_pe"] = pe
    MACRO_STATE["bond_10y"] = bond

    # 计算 ERP
    try:
        MACRO_STATE["equity_risk_premium"] = round(1.0 / pe * 100 - bond, 2)
    except Exception:
        MACRO_STATE["equity_risk_premium"] = 5.0

    # PMI 趋势
    MACRO_STATE["pmi_trend"] = "expansion" if pmi >= 50 else "contraction"

    # 周期判断
    _pmi = pmi
    _erp = MACRO_STATE["equity_risk_premium"]
    if _pmi >= 50.5 and _erp > 4.5:
        MACRO_STATE["cycle_phase"] = "recovery"
        MACRO_STATE["preferred_style"] = "growth"
    elif _pmi >= 50.5 and _erp <= 4.5:
        MACRO_STATE["cycle_phase"] = "overheat"
        MACRO_STATE["preferred_style"] = "value"
    elif _pmi < 49.5 and _erp > 5.5:
        MACRO_STATE["cycle_phase"] = "recession"
        MACRO_STATE["preferred_style"] = "defensive"
    elif _pmi < 49.5 and _erp <= 5.5:
        MACRO_STATE["cycle_phase"] = "stagflation"
        MACRO_STATE["preferred_style"] = "defensive_value"
    else:
        MACRO_STATE["cycle_phase"] = "transition"
        MACRO_STATE["preferred_style"] = "balanced"


# 初始化
init_macro_state()

# 风格偏好→基准权重映射
STYLE_BENCHMARK_WEIGHTS = {
    "growth":      {"大盘成长": 0.50, "中盘成长": 0.30, "小盘成长": 0.20},
    "value":       {"大盘价值": 0.55, "中盘价值": 0.30, "小盘价值": 0.15},
    "defensive":   {"大盘价值": 0.40, "大盘成长": 0.10, "中盘价值": 0.20, "债券": 0.30},
    "defensive_value": {"大盘价值": 0.50, "中盘价值": 0.25, "债券": 0.25},
    "balanced":    {"大盘成长": 0.30, "大盘价值": 0.30, "中盘成长": 0.15, "中盘价值": 0.15, "小盘": 0.10},
}

# 规模风格指数映射（akshare symbol）
SIZE_STYLE_INDICES = {
    "大盘成长": "sh000300",   # 沪深300近似大盘
    "大盘价值": "sh000300",   # 同上，价值/成长用行业指数区分
    "中盘成长": "sh000905",   # 中证500近似中盘
    "中盘价值": "sh000905",
    "小盘成长": "sh000852",   # 中证1000近似小盘
    "小盘价值": "sh000852",
    "小盘":     "sh000852",
    "债券":     "bond",        # 用中债综合指数
}

# ============================================================
# 资金流与市场情绪分析模块（v3 新增）
# ============================================================
_FLOW_CACHE_FILE = None


def _get_flow_cache_path():
    global _FLOW_CACHE_FILE
    if _FLOW_CACHE_FILE is None:
        _FLOW_CACHE_FILE = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "cache", "fund_flow_cache.json")
    return _FLOW_CACHE_FILE


def fetch_fund_flow_data(fund_code: str, force_refresh: bool = False) -> dict:
    """
    获取基金资金流数据：
    - 基金份额变动（季度）
    - 基金规模变化趋势
    - 净申购/赎回状态

    缓存：cache/fund_flow_cache.json，按基金代码存储，7天过期
    """
    cache_path = _get_flow_cache_path()
    all_flow_cache = {}
    if not force_refresh and os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                all_flow_cache = json.load(f)
        except Exception:
            all_flow_cache = {}

    # 检查该基金是否有未过期缓存
    if fund_code in all_flow_cache:
        entry = all_flow_cache[fund_code]
        cached_time = entry.get("_cached_at", "")
        if cached_time:
            days_ago = (datetime.now() - datetime.strptime(cached_time, "%Y-%m-%d")).days
            if days_ago <= 7:
                return {k: v for k, v in entry.items() if k != "_cached_at"}

    # 抓取数据
    result = {}
    try:
        # 东方财富基金规模变动页面
        url = f"https://fundf10.eastmoney.com/gmbd_{fund_code}.html"
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://fund.eastmoney.com/",
        }, timeout=10)
        resp.encoding = "utf-8"
        text = resp.text

        # 提取期末份额（最近两个季度）
        shares = re.findall(r'<td[^>]*>\s*([\d,]+\.?\d*)\s*万份\s*</td>', text)
        if len(shares) >= 2:
            try:
                latest_shares = float(shares[0].replace(",", ""))
                prev_shares = float(shares[1].replace(",", ""))
                if prev_shares > 0:
                    share_change = (latest_shares - prev_shares) / prev_shares
                    result["份额变动率"] = f"{share_change:.2%}"
                    result["份额变动信号"] = "净申购" if share_change > 0.02 else ("净赎回" if share_change < -0.02 else "基本持平")
            except Exception:
                pass

        # 提取基金规模
        scales = re.findall(r'<td[^>]*>\s*([\d,]+\.?\d*)\s*亿元\s*</td>', text)
        if len(scales) >= 2:
            try:
                latest_scale = float(scales[0].replace(",", ""))
                prev_scale = float(scales[1].replace(",", ""))
                if prev_scale > 0:
                    scale_change = (latest_scale - prev_scale) / prev_scale
                    result["规模变动率"] = f"{scale_change:.2%}"
                    # 规模暴增可能是情绪过热信号
                    if scale_change > 0.5:
                        result["规模信号"] = "⚠️ 规模暴增"
                    elif scale_change > 0.2:
                        result["规模信号"] = "规模扩张"
                    elif scale_change < -0.3:
                        result["规模信号"] = "⚠️ 大幅缩水"
                    else:
                        result["规模信号"] = "规模稳定"
            except Exception:
                pass

        # 缓存
        result["_cached_at"] = datetime.now().strftime("%Y-%m-%d")
        all_flow_cache[fund_code] = result
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(all_flow_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    except Exception:
        # 降级：尝试返回过期缓存
        if fund_code in all_flow_cache:
            entry = all_flow_cache[fund_code]
            return {k: v for k, v in entry.items() if k != "_cached_at"}

    return result


def analyze_flow_sentiment(share_change_str: str, scale_change_str: str,
                           scale_signal: str) -> str:
    """
    综合资金流信号分析：
    - 散户大量申购 + 规模暴增 → 情绪过热，反向卖出信号
    - 散户赎回 + 规模缩水 → 情绪冰点，反向买入信号
    - 净申购温和 → 正常
    """
    try:
        share_chg = float(share_change_str.strip("%")) / 100 if share_change_str else 0
    except Exception:
        share_chg = 0
    try:
        scale_chg = float(scale_change_str.strip("%")) / 100 if scale_change_str else 0
    except Exception:
        scale_chg = 0

    # 极端信号
    if share_chg > 0.3 and scale_chg > 0.5:
        return "🔴 情绪过热（散户大量涌入）"
    if share_chg < -0.2 and scale_chg < -0.2:
        return "🟡 情绪冰点（资金流出）"
    if share_chg > 0.1:
        return "🟢 温和申购"
    if share_chg < -0.1:
        return "🟡 轻度赎回"
    return "➖ 资金平稳"


# ============================================================
# 行业配置穿透分析模块（v3 新增）
# ============================================================
# 常见行业关键词映射
INDUSTRY_KEYWORDS = {
    "新能源": ["新能源", "能源革新", "光伏", "风电", "锂电", "储能", "电动车", "宁德", "碳中和"],
    "消费":   ["消费", "食品", "饮料", "白酒", "家电", "乳业", "调味品", "农业"],
    "医药":   ["医药", "医疗", "生物", "制药", "中药", "器械", "CXO", "医美"],
    "科技":   ["科技", "芯片", "半导体", "5G", "AI", "人工智能", "计算机", "软件", "电子", "通信"],
    "金融":   ["金融", "银行", "证券", "保险", "券商", "地产"],
    "军工":   ["军工", "航天", "航空", "国防"],
    "周期":   ["煤炭", "钢铁", "有色", "化工", "建材", "石油", "基建"],
    "红利":   ["红利", "股息", "高分红", "价值精选"],
    "债券":   ["债券", "纯债", "信用债", "利率债", "转债"],
    "均衡":   ["均衡", "灵活", "混合"],
    "指数":   ["沪深300", "中证500", "中证1000", "创业板", "科创"],
}


def classify_fund_industry(fund_name: str, fund_type: str) -> dict:
    """
    根据基金名称和类型推断行业/赛道分布
    返回: {行业: 匹配度(0~1)}
    """
    name = str(fund_name)
    ftype = str(fund_type)
    industries = {}

    # 债券型直接返回
    if "债" in ftype or "债" in name:
        return {"债券": 1.0}

    # 货币型
    if "货币" in ftype:
        return {"货币": 1.0}

    # 指数型：从名称提取
    if "指数" in ftype or "ETF" in name:
        for ind, keywords in INDUSTRY_KEYWORDS.items():
            if ind == "均衡":
                continue
            for kw in keywords:
                if kw in name:
                    industries[ind] = industries.get(ind, 0) + 0.3
        if industries:
            total = sum(industries.values())
            return {k: round(v / total, 2) for k, v in industries.items()}
        # 宽基指数
        for kw in ["沪深300", "中证500", "中证1000", "创业板", "科创"]:
            if kw in name:
                return {"指数": 1.0}

    # 主动管理型：从名称关键词推断
    for ind, keywords in INDUSTRY_KEYWORDS.items():
        if ind in ("均衡", "指数"):
            continue
        for kw in keywords:
            if kw in name:
                industries[ind] = industries.get(ind, 0) + 0.25

    if industries:
        total = sum(industries.values())
        return {k: round(v / total, 2) for k, v in industries.items()}

    # 默认均衡
    return {"均衡": 1.0}


def calc_industry_concentration(industries: dict) -> float:
    """
    计算行业集中度（赫芬达尔指数简化版）
    越接近 1 表示越集中在单一行业
    """
    if not industries or len(industries) <= 1:
        return 1.0
    return sum(v ** 2 for v in industries.values())


def get_cycle_industry_preference(cycle_phase: str) -> list:
    """
    当前宏观周期下偏好的行业
    """
    cycle_industry_map = {
        "recovery":    ["科技", "新能源", "消费"],       # 复苏→成长行业
        "overheat":    ["金融", "周期", "红利"],          # 过热→顺周期/价值
        "stagflation": ["红利", "消费", "医药"],          # 滞胀→防御+价值
        "recession":   ["债券", "红利", "医药"],          # 衰退→纯防御
        "transition":  ["均衡", "消费", "科技"],          # 过渡→均衡
    }
    return cycle_industry_map.get(cycle_phase, ["均衡"])


# ============================================================
# 缓存路径配置
# ============================================================
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
FUNDS_LIST_CACHE = os.path.join(CACHE_DIR, "funds_list.csv")
NAV_CACHE_DIR = os.path.join(CACHE_DIR, "nav")
MANAGER_CACHE_DIR = os.path.join(CACHE_DIR, "manager")
HOLDINGS_CACHE_DIR = os.path.join(CACHE_DIR, "holdings")
META_CACHE = os.path.join(CACHE_DIR, "meta.json")

def ensure_cache_dirs():
    """确保缓存目录存在"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(NAV_CACHE_DIR, exist_ok=True)
    os.makedirs(MANAGER_CACHE_DIR, exist_ok=True)
    os.makedirs(HOLDINGS_CACHE_DIR, exist_ok=True)

def load_meta():
    """加载元信息（上次更新时间等）"""
    ensure_cache_dirs()
    if os.path.exists(META_CACHE):
        with open(META_CACHE, "r") as f:
            return json.load(f)
    return {}

def save_meta(meta: dict):
    """保存元信息"""
    ensure_cache_dirs()
    with open(META_CACHE, "w") as f:
        json.dump(meta, f, indent=2)

def is_same_trading_day(date_str: str) -> bool:
    """判断缓存日期是否为同一交易日（忽略周末）"""
    today = datetime.now().strftime("%Y-%m-%d")
    if date_str == today:
        return True
    # 如果是周五或周六的缓存，周日晚间也认为有效（基金净值通常在晚间更新）
    cached_dt = datetime.strptime(date_str, "%Y-%m-%d")
    now = datetime.now()
    if now.weekday() == 6:  # 周日
        return cached_dt.weekday() == 4  # 上周五的数据仍有效
    if now.weekday() == 0 and now.hour < 18:  # 周一18点前
        return cached_dt.weekday() == 4  # 上周五的数据仍有效
    return False

# ============================================================
# 第 1 步：加载全市场基金数据（带CSV缓存 + 增量同步）
# ============================================================

def _fetch_funds_page(session, page: int, sd_str: str, ed_str: str) -> list:
    """拉取单页基金数据，返回记录列表"""
    url = "https://fund.eastmoney.com/data/rankhandler.aspx"
    params = {
        "op": "ph", "dt": "kf", "ft": "all",
        "rs": "", "gs": 0,
        "sc": "1nzf", "st": "desc",
        "sd": sd_str, "ed": ed_str,
        "pi": page, "pn": 500, "dx": 1,
        "v": f"0.{int(time.time())}",
    }
    resp = session.get(url, params=params, timeout=15)
    text = resp.text
    match = re.search(r'\{.*\}', text)
    if not match:
        return None, True  # None, done=True
    js_obj = match.group(0)
    json_str = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', js_obj)
    try:
        data = json.loads(json_str)
    except Exception:
        return None, True
    records = data.get("datas", [])
    return records, len(records) < 500


def _parse_funds(records: list) -> list:
    """解析原始记录为字典列表"""
    fields = ["基金代码","基金简称","净值日期","单位净值","累计净值","日增长率",
              "近1周","近1月","近3月","近6月","近1年","近2年","近3年","今年来","成立来",
              "成立日期","基金类型","基金规模"]
    result = []
    for record in records:
        parts = record.split(",")
        if len(parts) < 18:
            continue
        # 基金类型映射: 1=混合型, 其他股票型/债券型等
        fund_type_raw = parts[17].strip() if len(parts) > 17 else ""
        # 基金规模(亿元), 字段[24]
        scale_raw = parts[24].strip() if len(parts) > 24 else ""
        result.append(dict(zip(fields, [
            parts[0], parts[1], parts[3], parts[4], parts[5], parts[6],
            parts[7], parts[8], parts[9], parts[10], parts[11], parts[12],
            parts[13], parts[14], parts[15],
            parts[16] if len(parts) > 16 else "", fund_type_raw, scale_raw,
        ])))
    return result


def load_all_funds(force_refresh: bool = False):
    """
    加载全市场开放式基金列表及各周期收益率（带CSV缓存 + 增量同步）

    策略：
      - 无缓存：全量拉取 400+ 页，写入缓存
      - 有缓存 & 同交易日：直接读缓存，0 请求
      - 有缓存 & 新交易日：增量同步 —— 只拉前 INCR_PAGES 页，
        用基金代码匹配覆盖缓存中的旧数据，排名低的基金保持旧数据不变
      - force_refresh=True：强制全量拉取
    """
    INCR_PAGES = 10  # 增量同步时最多拉取页数（500只基金，覆盖排行榜前列）

    ensure_cache_dirs()
    meta = load_meta()

    # ---- 缓存命中（同交易日）----
    if not force_refresh and os.path.exists(FUNDS_LIST_CACHE):
        cached_date = meta.get("funds_list_date", "")
        if is_same_trading_day(cached_date):
            print(f"📦 使用缓存的基金列表（{cached_date}），跳过网络请求")
            df = pd.read_csv(FUNDS_LIST_CACHE, dtype={"基金代码": str})
            print(f"共加载 {len(df)} 只基金（来自缓存）")
            return df

    # ---- 判断是增量还是全量 ----
    cached_df = None
    if not force_refresh and os.path.exists(FUNDS_LIST_CACHE):
        try:
            cached_df = pd.read_csv(FUNDS_LIST_CACHE, dtype={"基金代码": str})
            cached_df = cached_df.set_index("基金代码")
            print(f"📦 已加载缓存 {len(cached_df)} 只，将增量同步前 {INCR_PAGES} 页...")
        except Exception:
            cached_df = None

    # ---- 网络加载 ----
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://fund.eastmoney.com/data/fundranking.html",
    })
    sd_str = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    ed_str = datetime.now().strftime("%Y-%m-%d")

    all_funds = []
    page = 1

    if cached_df is not None:
        # === 增量模式：只拉前 INCR_PAGES 页 ===
        print(f"🔄 增量同步中（最多 {INCR_PAGES} 页）...")
        for page in range(1, INCR_PAGES + 1):
            try:
                records, done = _fetch_funds_page(session, page, sd_str, ed_str)
                if records is None:
                    break
                parsed = _parse_funds(records)
                all_funds.extend(parsed)
                if page % 3 == 0:
                    print(f"  增量同步第{page}/{INCR_PAGES}页")
                if done:
                    break
            except Exception as e:
                print(f"  增量同步第{page}页失败: {e}")
                break

        # 合并：新数据覆盖旧缓存（用基金代码匹配）
        new_df = pd.DataFrame(all_funds).set_index("基金代码") if all_funds else pd.DataFrame()
        if not new_df.empty:
            # 去重
            new_df = new_df[~new_df.index.duplicated(keep="last")]
            # 直接用 concat + 去重（keep=last 让新数据覆盖旧数据）
            combined = pd.concat([cached_df, new_df])
            combined = combined[~combined.index.duplicated(keep="last")]
            cached_df = combined
        df = cached_df.reset_index()
        print(f"✅ 增量同步完成，共 {len(df)} 只基金")

    else:
        # === 全量模式：拉取所有页（每页500条，约40页拉完全部20000+只） ===
        print("正在全量加载全市场基金数据...")
        t_fetch_start = time.time()
        while True:
            try:
                records, done = _fetch_funds_page(session, page, sd_str, ed_str)
                if records is None:
                    break
                all_funds.extend(_parse_funds(records))
                if page % 5 == 0:
                    elapsed = time.time() - t_fetch_start
                    print(f"  第{page}页，累计 {len(all_funds)} 只 ({elapsed:.1f}s)")
                if done:
                    break
                page += 1
            except Exception as e:
                print(f"  第{page}页加载失败: {e}")
                break
        df = pd.DataFrame(all_funds)
        print(f"全量加载完成，共 {len(df)} 只基金")

    # ---- 写入缓存 ----
    if not df.empty:
        df.to_csv(FUNDS_LIST_CACHE, index=False, encoding="utf-8-sig")
        meta["funds_list_date"] = datetime.now().strftime("%Y-%m-%d")
        save_meta(meta)
        print(f"💾 基金列表已缓存至 {FUNDS_LIST_CACHE}")

    return df

def get_tencent_quote(fund_code: str) -> dict:
    """
    通过腾讯财经实时行情接口获取基金数据
    接口：http://qt.gtimg.cn/q=jj{fund_code}
    返回格式：代码~名称~最新价~...~单位净值~累计净值~日增长率~净值日期~
    """
    url = f"http://qt.gtimg.cn/q=jj{fund_code}"
    try:
        resp = requests.get(url, timeout=10,
                          headers={"User-Agent": "Mozilla/5.0"})
        resp.encoding = "gbk"
        text = resp.text
        # 解析返回格式: v_jjCODE="CODE~NAME~PRICE~...~NAV~ACCUM_NAV~CHG%~DATE~..."
        match = re.search(r'="(.+)"', text)
        if match:
            parts = match.group(1).split("~")
            if len(parts) >= 9:
                return {
                    "code": parts[0],
                    "name": parts[1],
                    "nav": float(parts[5]) if parts[5] and parts[5] != "0.0000" else None,
                    "accum_nav": float(parts[6]) if parts[6] else None,
                    "chg_pct": float(parts[7]) if parts[7] else None,
                    "nav_date": parts[8] if parts[8] else None,
                }
    except Exception as e:
        print(f"  ⚠ 腾讯行情 {fund_code} 获取失败: {e}")
    return None

def load_fund_nav_history(fund_code: str, days: int = 1095, force_refresh: bool = False):
    """
     加载单只基金历史净值（默认 3 年），带 CSV 缓存
    数据源：东方财富基金净值API
    缓存策略：
      - 每只基金一个 cache/nav/{基金代码}.csv
      - 首次加载全量数据并缓存
      - 再次加载时读缓存 + 增量拉取最新几天
      - 缓存同交易日有效，不重复请求
    """
    ensure_cache_dirs()
    cache_file = os.path.join(NAV_CACHE_DIR, f"{fund_code}.csv")
    cutoff_date = datetime.now() - timedelta(days=days)
    today_str = datetime.now().strftime("%Y-%m-%d")

    # ---- 尝试从缓存加载 ----
    cached_df = None
    CACHE_STALE_DAYS = 3  # 缓存超过3天视为过期，需增量更新
    if not force_refresh and os.path.exists(cache_file):
        try:
            cached_df = pd.read_csv(
                cache_file,
                dtype={"nav": float},
                parse_dates=["date"],
                index_col="date",
            ).sort_index().dropna(subset=["nav"])
            if len(cached_df) > 0:
                last_cached_date = cached_df.index.max()
                days_since = (datetime.now() - last_cached_date).days
                # 缓存未过期（≤3天）：直接返回
                if days_since <= CACHE_STALE_DAYS:
                    result = cached_df[cached_df.index >= cutoff_date]
                    if len(result) >= 60:
                        return result
        except Exception:
            cached_df = None

    # ---- 确定拉取范围 ----
    if cached_df is not None and len(cached_df) > 0:
        last_date = cached_df.index.max()
        fetch_start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        fetch_start = cutoff_date.strftime("%Y-%m-%d")

    # 如果拉取起始日期 >= 今天，说明缓存已是最新，直接返回
    if fetch_start >= today_str:
        result = cached_df[cached_df.index >= cutoff_date] if cached_df is not None else None
        return result if result is not None and len(result) >= 60 else None

    end_date = today_str
    all_records = []
    page = 1
    # 复用 session 减少 TCP 握手
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://fundf10.eastmoney.com/",
    })

    while True:
        url = (
            f"https://api.fund.eastmoney.com/f10/lsjz"
            f"?fundCode={fund_code}&pageIndex={page}&pageSize=20"
            f"&startDate={fetch_start}&endDate={end_date}"
        )
        try:
            resp = session.get(url, timeout=15)
            data = resp.json()
            if data.get("ErrCode") != 0:
                break
            records = data.get("Data", {}).get("LSJZList", [])
            if not records:
                break
            # 批量提取，减少循环内操作
            for r in records:
                nav_val = r.get("DWJZ")
                if nav_val:
                    all_records.append((r.get("FSRQ", ""), float(nav_val)))
            if len(records) < 20:
                break
            page += 1
        except Exception as e:
            # 降级返回缓存
            if cached_df is not None and len(cached_df) >= 60:
                return cached_df[cached_df.index >= cutoff_date]
            return None

    if not all_records and cached_df is None:
        return None

    # ---- 合并缓存 + 新数据 ----
    if all_records:
        new_df = pd.DataFrame(all_records, columns=["date", "nav"])
        new_df["date"] = pd.to_datetime(new_df["date"])
        new_df = new_df.set_index("date").sort_index()

        if cached_df is not None and len(cached_df) > 0:
            combined = pd.concat([cached_df, new_df])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        else:
            combined = new_df

        result = combined[combined.index >= cutoff_date]
    else:
        result = cached_df[cached_df.index >= cutoff_date]

    # ---- 写入缓存（合并全量历史再存） ----
    if result is not None and len(result) > 0:
        save_df = pd.concat([cached_df, result]) if cached_df is not None and len(cached_df) > 0 else result
        save_df = save_df[~save_df.index.duplicated(keep="last")].sort_index()
        save_df.to_csv(cache_file, encoding="utf-8-sig")

    return result if result is not None and len(result) >= 60 else None

# ============================================================
# 第 2 步：多基准系统 & 基金分类
# ============================================================

BENCHMARK_DIR = os.path.join(CACHE_DIR, "benchmarks")

def _load_single_benchmark(symbol: str, name: str) -> pd.Series:
    """加载单个规模指数作为基准"""
    ensure_cache_dirs()
    os.makedirs(BENCHMARK_DIR, exist_ok=True)
    cache_file = os.path.join(BENCHMARK_DIR, f"{symbol}.csv")
    CACHE_STALE_DAYS = 5
    if os.path.exists(cache_file):
        try:
            df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date").sort_index()
            if len(df) > 0 and (datetime.now() - df.index.max()).days <= CACHE_STALE_DAYS:
                return df["close"]
        except Exception:
            pass
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol=symbol)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        df.to_csv(cache_file, encoding="utf-8-sig")
        return df["close"]
    except Exception:
        return None

_benchmarks_cache = {}

def _load_bond_benchmark(force_refresh: bool = False) -> pd.Series:
    """加载中债综合指数作为债券基准（中证全债指数 H11001）"""
    ensure_cache_dirs()
    os.makedirs(BENCHMARK_DIR, exist_ok=True)
    cache_file = os.path.join(BENCHMARK_DIR, "bond_benchmark.csv")
    CACHE_STALE_DAYS = 5
    if not force_refresh and os.path.exists(cache_file):
        try:
            df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date").sort_index()
            if len(df) > 0 and (datetime.now() - df.index.max()).days <= CACHE_STALE_DAYS:
                return df["close"]
        except Exception:
            pass
    try:
        import akshare as ak
        # 中证全债指数 H11001
        df = ak.bond_zh_us_rate()
        if df is not None and len(df) > 0 and "中国国债收益率10年" in df.columns:
            # 用10年国债收益率反推债券价格指数（简化处理）
            # 债券价格变化 ≈ -duration * Δyield，假设久期=7
            df = df.rename(columns={"日期": "date"} if "日期" in df.columns else {df.columns[0]: "date"})
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            df["yield_10y"] = df["中国国债收益率10年"].astype(float)
            # 用收益率变化模拟债券指数：起始值100，每日涨跌 ≈ -duration * 收益率变化
            # 简化：用累积收益率变化的反向作为近似
            bond_idx = 100 * (1 + df["yield_10y"].diff().fillna(0) * (-7) / 100).cumprod()
            bond_idx.name = "close"
            bond_idx.to_csv(cache_file, encoding="utf-8-sig")
            return bond_idx
    except Exception:
        pass

    # Fallback: 尝试获取中证全债指数
    try:
        import akshare as ak
        df = ak.index_zh_a_hist(symbol="H11001", period="daily", start_date="20200101",
                                end_date=datetime.now().strftime("%Y%m%d"))
        df["date"] = pd.to_datetime(df["日期"])
        df = df.set_index("date").sort_index()
        df["close"].to_csv(cache_file, encoding="utf-8-sig")
        return df["close"]
    except Exception:
        pass
    return None


def load_all_benchmarks(force_refresh: bool = False) -> dict:
    """
    加载多规模基准：沪深300(大盘)、中证500(中盘)、中证1000(小盘)、中债综合(债券)
    返回 {"大盘": Series, "中盘": Series, "小盘": Series, "债券": Series}
    """
    global _benchmarks_cache
    if _benchmarks_cache and not force_refresh:
        return _benchmarks_cache
    benchmarks = {}
    for name, symbol in [("大盘", "sh000300"), ("中盘", "sh000905"), ("小盘", "sh000852")]:
        s = _load_single_benchmark(symbol, name)
        if s is not None:
            benchmarks[name] = s
    # 加载债券基准
    bond_bm = _load_bond_benchmark(force_refresh)
    if bond_bm is not None:
        benchmarks["债券"] = bond_bm
    _benchmarks_cache = benchmarks
    return benchmarks


def classify_fund_asset_type(fund_name: str, fund_type: str) -> str:
    """
    v5 新增：根据基金名称和类型判断资产大类
    返回: "股票" / "债券" / "混合" / "货币" / "其他"
    """
    name = str(fund_name)
    ftype = str(fund_type)

    # 货币型优先
    if "货币" in ftype or "货币" in name:
        return "货币"

    # 债券型
    if "债" in ftype:
        return "债券"
    # 名称包含债券相关关键词
    bond_kw = ["纯债", "信用债", "利率债", "中短债", "短债", "转债", "债券", "债基",
               "可转债", "国债", "政金债"]
    for kw in bond_kw:
        if kw in name:
            return "债券"

    # 混合型
    if "混合" in ftype:
        return "混合"

    # 股票型 / 指数型
    if "股票" in ftype or "指数" in ftype or "ETF" in name:
        return "股票"

    # 其他默认按股票处理
    return "股票"


def classify_fund_type_label(fund_name: str, fund_type_raw: str) -> str:
    """
    v5 新增：根据基金名称和原始类型编码，返回人类可读的基金类型标签。
    原始数据中 fund_type_raw 多为数字编码（1=混合/股票等），
    因此主要依赖名称关键词来判断具体类型。

    返回示例: "混合型-偏股" / "债券型-纯债" / "股票型" / "指数型" / "货币型" / "QDII" 等
    """
    name = str(fund_name)
    ftype = str(fund_type_raw)

    # 货币型
    if "货币" in name:
        return "货币型"

    # QDII
    is_qdii = "QDII" in name.upper()

    # 债券型细分
    bond_kw = ["纯债", "信用债", "利率债", "中短债", "短债", "转债", "债券", "债基",
               "可转债", "国债", "政金债", "双月乐", "双季", "稳安", "丰元", "恒盛",
               "景颐", "双季红", "泓利", "汇阳", "嘉信", "盈瑞"]
    is_bond = any(kw in name for kw in bond_kw)
    if is_bond:
        if "可转债" in name or "转债" in name:
            return "可转债"
        if "中短债" in name or "短债" in name:
            return "债券型-短债"
        return "债券型-纯债" if not is_qdii else "债券型-QDII"

    # 指数型
    index_kw = ["ETF", "指数", "ETF联接"]
    is_index = any(kw in name for kw in index_kw)
    if is_index:
        prefix = "指数型-QDII" if is_qdii else "指数型"
        return prefix

    # FOF
    if "FOF" in name.upper():
        return "FOF"

    # 混合型
    if "混合" in name:
        if is_qdii:
            return "混合型-QDII"
        return "混合型"

    # 股票型
    if "股票" in name:
        if is_qdii:
            return "股票型-QDII"
        return "股票型"

    # 其他：通过名称特征判断
    if "灵活配置" in name:
        return "混合型-灵活"
    if is_qdii:
        return "QDII"

    # 默认
    if is_bond:
        return "债券型"
    if is_index:
        return "指数型"
    return "混合型"
    return "股票"


def classify_fund_by_scale(fund_name: str, fund_type: str) -> str:
    """
    根据基金名称和类型推断规模风格
    关键词 → 规模分类
    """
    name = str(fund_name)
    ftype = str(fund_type)

    # 债券/货币型直接返回对应类型
    asset = classify_fund_asset_type(name, ftype)
    if asset in ("债券", "货币"):
        return asset

    # 指数型：从名称推断
    if "沪深300" in name or "大盘" in name or "蓝筹" in name or "龙头" in name:
        return "大盘"
    if "中证500" in name or "中盘" in name:
        return "中盘"
    if "中证1000" in name or "中证2000" in name or "小盘" in name or "小微" in name:
        return "小盘"
    if "创业板" in name or "科创" in name:
        return "小盘"
    # 行业主题基金，默认中盘
    if any(kw in name for kw in ["医疗","医药","消费","科技","新能源","军工","半导体","白酒","汽车"]):
        return "中盘"
    # 量化基金，默认中盘
    if "量化" in name:
        return "中盘"
    # 混合型默认中盘
    if "混合" in ftype:
        return "中盘"
    # 股票型默认大盘
    if "股票" in ftype:
        return "大盘"
    return "中盘"  # 默认

def get_matched_benchmark(fund_name: str, fund_type: str) -> tuple:
    """
    为基金匹配最合适的规模基准（v5：债基匹配债券基准）
    返回 (benchmark_name, benchmark_series)
    """
    scale = classify_fund_by_scale(fund_name, fund_type)
    benchmarks = load_all_benchmarks()

    # 债券/货币基金 → 匹配债券基准
    if scale in ("债券", "货币") and "债券" in benchmarks:
        return "中债综合", benchmarks["债券"]

    if scale in benchmarks:
        return scale, benchmarks[scale]
    # fallback to 沪深300
    if "大盘" in benchmarks:
        return "大盘", benchmarks["大盘"]
    return "沪深300", None

# 兼容旧接口
def load_benchmark_nav(force_refresh: bool = False) -> pd.Series:
    """兼容旧代码，返回沪深300"""
    bms = load_all_benchmarks(force_refresh)
    return bms.get("大盘")

_benchmark_cache = None

def get_benchmark(force_refresh: bool = False) -> pd.Series:
    global _benchmark_cache
    if _benchmark_cache is not None and not force_refresh:
        return _benchmark_cache
    _benchmark_cache = load_benchmark_nav(force_refresh)
    return _benchmark_cache

def calc_sharpe_ratio(nav_series: pd.Series, risk_free_rate: float = 0.02) -> float:
    """年化夏普比率 = (年化收益 - 无风险利率) / 年化波动率"""
    returns = nav_series.pct_change().dropna()
    if len(returns) < 60:
        return np.nan
    annual_ret = returns.mean() * 252
    annual_vol = returns.std() * np.sqrt(252)
    if annual_vol == 0:
        return np.nan
    return (annual_ret - risk_free_rate) / annual_vol

def calc_max_drawdown(nav_series: pd.Series) -> float:
    """最大回撤（负值，越小越差）"""
    cummax = nav_series.cummax()
    drawdown = (nav_series - cummax) / cummax
    return drawdown.min()

def calc_annual_return(nav_series: pd.Series) -> float:
    """年化收益率"""
    if len(nav_series) < 60:
        return np.nan
    total_ret = nav_series.iloc[-1] / nav_series.iloc[0]
    years = len(nav_series) / 252
    return total_ret ** (1 / years) - 1

def calc_calmar_ratio(nav_series: pd.Series) -> float:
    """Calmar 比率 = 年化收益 / |最大回撤|"""
    ann_ret = calc_annual_return(nav_series)
    mdd = calc_max_drawdown(nav_series)
    if mdd == 0 or np.isnan(ann_ret):
        return np.nan
    return ann_ret / abs(mdd)

def calc_volatility(nav_series: pd.Series) -> float:
    """年化波动率"""
    returns = nav_series.pct_change().dropna()
    return returns.std() * np.sqrt(252)

def calc_sortino_ratio(nav_series: pd.Series, risk_free_rate: float = 0.02) -> float:
    """Sortino 比率（只惩罚下行波动）"""
    returns = nav_series.pct_change().dropna()
    if len(returns) < 60:
        return np.nan
    annual_ret = returns.mean() * 252
    downside = returns[returns < 0]
    downside_std = downside.std() * np.sqrt(252)
    if downside_std == 0:
        return np.nan
    return (annual_ret - risk_free_rate) / downside_std


def calc_alpha_and_ir(nav_series: pd.Series, benchmark: pd.Series) -> tuple:
    """
    计算相对基准的 Alpha（年化超额收益）和信息比率 IR
    Alpha = 基金年化收益 - 基准年化收益
    IR    = Alpha / 跟踪误差（超额收益的标准差年化）
    """
    if benchmark is None:
        return np.nan, np.nan
    # 对齐日期
    common_idx = nav_series.index.intersection(benchmark.index)
    if len(common_idx) < 60:
        return np.nan, np.nan
    fund_aligned = nav_series.loc[common_idx]
    bench_aligned = benchmark.loc[common_idx]
    fund_ret = fund_aligned.pct_change().dropna()
    bench_ret = bench_aligned.pct_change().dropna()
    common = fund_ret.index.intersection(bench_ret.index)
    if len(common) < 60:
        return np.nan, np.nan
    fund_ret = fund_ret.loc[common]
    bench_ret = bench_ret.loc[common]
    excess_ret = fund_ret - bench_ret
    # Alpha（年化）
    alpha = excess_ret.mean() * 252
    # 信息比率
    tracking_error = excess_ret.std() * np.sqrt(252)
    if tracking_error == 0:
        return alpha, np.nan
    ir = alpha / tracking_error
    return alpha, ir


def calc_nav_percentile(nav_series: pd.Series) -> float:
    """计算当前净值在3年历史中的分位（0~1，越高越贵）"""
    if len(nav_series) < 60:
        return np.nan
    current = nav_series.iloc[-1]
    return (nav_series < current).sum() / len(nav_series)


def calc_downside_capture(nav_series: pd.Series, benchmark: pd.Series) -> float:
    """
    下行捕获率：基准下跌期间，基金跌多少
    < 100% 说明抗跌，> 100% 说明跌得比市场更凶
    """
    if benchmark is None:
        return np.nan
    common_idx = nav_series.index.intersection(benchmark.index)
    if len(common_idx) < 60:
        return np.nan
    fund_aligned = nav_series.loc[common_idx].pct_change().dropna()
    bench_aligned = benchmark.loc[common_idx].pct_change().dropna()
    common = fund_aligned.index.intersection(bench_aligned.index)
    fund_ret = fund_aligned.loc[common]
    bench_ret = bench_aligned.loc[common]
    down_mask = bench_ret < 0
    if down_mask.sum() < 10:
        return np.nan
    fund_down = fund_ret[down_mask].sum()
    bench_down = bench_ret[down_mask].sum()
    if bench_down == 0:
        return np.nan
    return abs(fund_down / bench_down)


# ============================================================
# 新增：月度胜率 & 滚动分析
# ============================================================

def calc_monthly_win_rate(nav_series: pd.Series, benchmark: pd.Series = None) -> dict:
    """
    计算月度胜率指标：
      - monthly_win_rate: 跑赢基准的月份占比
      - rolling_12m_win_rate: 滚动12个月的胜率（最近值）
      - win_rate_trend: 胜率趋势（上升/下降/稳定）
      - consecutive_win: 最近连续跑赢月数
      - consecutive_loss: 最近连续跑输月数
    """
    if len(nav_series) < 120:
        return {"月度胜率": np.nan, "滚动12月胜率": np.nan, "胜率趋势": "N/A",
                "连续跑赢": np.nan, "连续跑输": np.nan}

    # 按月重采样
    monthly_fund = nav_series.resample("ME").last().pct_change().dropna()
    if len(monthly_fund) < 6:
        return {"月度胜率": np.nan, "滚动12月胜率": np.nan, "胜率趋势": "N/A",
                "连续跑赢": np.nan, "连续跑输": np.nan}

    if benchmark is not None:
        monthly_bench = benchmark.resample("ME").last().pct_change().dropna()
        common = monthly_fund.index.intersection(monthly_bench.index)
        if len(common) < 6:
            return {"月度胜率": np.nan, "滚动12月胜率": np.nan, "胜率趋势": "N/A",
                    "连续跑赢": np.nan, "连续跑输": np.nan}
        fund_m = monthly_fund.loc[common]
        bench_m = monthly_bench.loc[common]
        excess_m = fund_m - bench_m
        wins = (excess_m > 0).astype(int)
    else:
        # 无基准时，跑赢0即算赢
        wins = (monthly_fund > 0).astype(int)

    total_months = len(wins)
    if total_months == 0:
        return {"月度胜率": np.nan, "滚动12月胜率": np.nan, "胜率趋势": "N/A",
                "连续跑赢": np.nan, "连续跑输": np.nan}

    # 总胜率
    monthly_win_rate = wins.sum() / total_months

    # 滚动12个月胜率
    rolling_win = wins.rolling(12).mean()
    rolling_12m_win = rolling_win.iloc[-1] if len(rolling_win) > 0 else np.nan

    # 胜率趋势：近12月 vs 前12月
    if total_months >= 24:
        recent_12 = wins.iloc[-12:].mean()
        prior_12 = wins.iloc[-24:-12].mean()
        if recent_12 > prior_12 + 0.05:
            trend = "上升↑"
        elif recent_12 < prior_12 - 0.05:
            trend = "下降↓"
        else:
            trend = "稳定→"
    else:
        trend = "N/A"

    # 连续跑赢/跑输
    consecutive_win = 0
    consecutive_loss = 0
    for v in reversed(wins.values):
        if v == 1:
            consecutive_win += 1
            if consecutive_loss > 0:
                break
        else:
            consecutive_loss += 1
            if consecutive_win > 0:
                break

    return {
        "月度胜率": round(monthly_win_rate, 3),
        "滚动12月胜率": round(rolling_12m_win, 3) if not np.isnan(rolling_12m_win) else None,
        "胜率趋势": trend,
        "连续跑赢": consecutive_win,
        "连续跑输": consecutive_loss,
    }


def calc_drawdown_recovery(nav_series: pd.Series) -> dict:
    """
    计算回撤修复天数：从最大回撤底部回到前高所需天数
    返回 (max_dd_recovery_days, avg_dd_recovery_days)
    """
    if len(nav_series) < 120:
        return {"最大回撤修复天": np.nan, "平均回撤修复天": np.nan}

    cummax = nav_series.cummax()
    drawdown = (nav_series - cummax) / cummax
    # 找所有回撤>5%的区间
    recovery_days = []
    in_dd = False
    dd_start = None
    dd_bottom_idx = None
    dd_bottom_val = float("inf")

    for i in range(len(drawdown)):
        val = drawdown.iloc[i]
        if val < -0.05 and not in_dd:
            in_dd = True
            dd_start = i
            dd_bottom_idx = i
            dd_bottom_val = val
        elif in_dd:
            if val < dd_bottom_val:
                dd_bottom_val = val
                dd_bottom_idx = i
            if val >= -0.01:  # 回撤修复（回到-1%以内）
                recovery_days.append(i - dd_start)
                in_dd = False

    if in_dd and dd_start is not None:
        # 当前仍在回撤中
        recovery_days.append(len(drawdown) - dd_start)

    if not recovery_days:
        return {"最大回撤修复天": 0, "平均回撤修复天": 0}

    return {
        "最大回撤修复天": int(max(recovery_days)),
        "平均回撤修复天": int(np.mean(recovery_days)),
    }


def calc_rolling_metrics(nav_series: pd.Series, window: int = 252) -> dict:
    """
    滚动窗口指标：计算滚动1年夏普的最大/最小/当前值
    用于判断业绩稳定性
    """
    if len(nav_series) < window + 60:
        return {"滚动夏普(当前)": np.nan, "滚动夏普(最大)": np.nan, "滚动夏普(最小)": np.nan}

    returns = nav_series.pct_change().dropna()
    rolling_sharpe = returns.rolling(window).apply(
        lambda x: (x.mean() * 252 - 0.02) / (x.std() * np.sqrt(252)) if x.std() > 0 else np.nan
    ).dropna()

    if len(rolling_sharpe) == 0:
        return {"滚动夏普(当前)": np.nan, "滚动夏普(最大)": np.nan, "滚动夏普(最小)": np.nan}

    return {
        "滚动夏普(当前)": round(rolling_sharpe.iloc[-1], 3),
        "滚动夏普(最大)": round(rolling_sharpe.max(), 3),
        "滚动夏普(最小)": round(rolling_sharpe.min(), 3),
    }


def calc_upside_capture(nav_series: pd.Series, benchmark: pd.Series) -> float:
    """
    上行捕获率：基准上涨期间，基金涨多少
    > 100% 说明弹性好
    """
    if benchmark is None:
        return np.nan
    common_idx = nav_series.index.intersection(benchmark.index)
    if len(common_idx) < 60:
        return np.nan
    fund_aligned = nav_series.loc[common_idx].pct_change().dropna()
    bench_aligned = benchmark.loc[common_idx].pct_change().dropna()
    common = fund_aligned.index.intersection(bench_aligned.index)
    fund_ret = fund_aligned.loc[common]
    bench_ret = bench_aligned.loc[common]
    up_mask = bench_ret > 0
    if up_mask.sum() < 10:
        return np.nan
    fund_up = fund_ret[up_mask].sum()
    bench_up = bench_ret[up_mask].sum()
    if bench_up == 0:
        return np.nan
    return fund_up / bench_up

# ============================================================
# 粗筛辅助：简易风险调整收益（无需拉取净值历史）
# ============================================================

def calc_coarse_score(row: pd.Series) -> float:
    """
    粗筛综合得分（用于替代单纯按近1年收益排序）：
      - 利用基金列表自带的多周期收益率，估算简易夏普 = (年均收益 - 2%) / 波动估计
      - 同时考虑多周期一致性，惩罚「近1年好但近3年差」的基金
    得分范围 0~100，越高越好。
    """
    ret_1y = pd.to_numeric(row.get("近1年"), errors="coerce")
    ret_2y = pd.to_numeric(row.get("近2年"), errors="coerce")
    ret_3y = pd.to_numeric(row.get("近3年"), errors="coerce")
    ret_6m = pd.to_numeric(row.get("近6月"), errors="coerce")

    # 必须至少有近1年和近3年数据
    if pd.isna(ret_1y) or pd.isna(ret_3y):
        return -999

    # 年化收益估算：用各周期复合计算
    annual_ret = ret_1y / 100.0  # 近1年年化

    # 波动估计：用多周期收益的离散度近似
    periods = []
    if not pd.isna(ret_6m):
        periods.append(ret_6m / 100.0 * 2)  # 年化
    if not pd.isna(ret_1y):
        periods.append(ret_1y / 100.0)
    if not pd.isna(ret_2y):
        periods.append(ret_2y / 200.0)  # 2年总→年化
    if not pd.isna(ret_3y):
        periods.append(ret_3y / 300.0)  # 3年总→年化

    if len(periods) >= 2:
        vol_est = np.std(periods) + 0.05  # 加0.05防止零波动
    else:
        vol_est = 0.15  # 默认波动

    risk_free = 0.02
    est_sharpe = (annual_ret - risk_free) / max(vol_est, 0.01)

    # 多周期一致性惩罚：近1年 vs 近3年年化差距
    ret_3y_annual = ret_3y / 300.0
    consistency_penalty = abs(annual_ret - ret_3y_annual)  # 越大越不稳定

    # 综合得分
    score = est_sharpe * 20 - consistency_penalty * 30
    return round(score, 2)

# ============================================================
# 第 3 步：综合评分模型（满分 100）
# ============================================================

def score_fund(sharpe, mdd, ann_ret, calmar, sortino, volatility,
               monthly_win_rate=None, ir=None, alpha=None,
               macro_preferred_style=None, fund_scale_class=None,
               industry_match=0.0,
               manager_score=0.0, flow_sentiment_score=0.0,
               nav_percentile=0.5, asset_type="股票") -> float:
    """
    加权评分（v5 —— 按资产类别分别校准 + 去共线性）：
      债基用债基的夏普/回撤/收益校准曲线，股基用股基的，
      确保同类比较而非跨类混排。

      【风险调整收益维度 — 22%】
      【下行风险维度 — 最大回撤 15%】
      【绝对收益维度 — 年化收益 10%】
      【超额收益维度 — 信息比率+Alpha 12%】
      【稳定性维度 — 月度胜率 10%】
      【宏观适配维度 — 风格+行业 12%】
      【经理质量维度 — 8%】
      【资金流情绪维度 — 6%】
      【估值安全边际维度 — 5%】
    """
    score = 0.0
    max_score = 0.0

    # ---- 按资产类型选择校准参数 ----
    if asset_type in ("债券", "货币"):
        # 债基/货基校准：夏普 1.0~2.5 是优秀区间，回撤 -3% 是极端
        _sharpe_norm = 3.0   # (sharpe + 1.0) / 3.0 → sharpe=2.0 → 满分
        _sharpe_offset = 1.0
        _sortino_norm = 4.0
        _sortino_offset = 1.0
        _calmar_norm = 5.0
        _mdd_denom = 0.20       # 回撤 0~-20% 映射到 0~1
        _mdd_offset = 0.20
        _ann_ret_denom = 0.08   # 年化 8% → 满分（债基天花板）
        _ir_norm = 1.5
        _ir_offset = 0.2
        _alpha_norm = 0.10
        _alpha_offset = 0.02
        _win_rate_denom = 0.75  # 月度胜率 75% → 满分
    else:
        # 股基/混合基校准（原有参数）
        _sharpe_norm = 2.5
        _sharpe_offset = 0.5
        _sortino_norm = 3.5
        _sortino_offset = 0.5
        _calmar_norm = 3.0
        _mdd_denom = 0.45
        _mdd_offset = 0.50
        _ann_ret_denom = 0.30
        _ir_norm = 2.0
        _ir_offset = 0.3
        _alpha_norm = 0.30
        _alpha_offset = 0.05
        _win_rate_denom = 0.70

    # ---- 1. 风险调整收益综合维度（0~22） ----
    risk_adj_scores = []
    if not np.isnan(sharpe):
        risk_adj_scores.append(np.clip((sharpe + _sharpe_offset) / _sharpe_norm, 0, 1))
    if not np.isnan(sortino):
        risk_adj_scores.append(np.clip((sortino + _sortino_offset) / _sortino_norm, 0, 1))
    if not np.isnan(calmar):
        risk_adj_scores.append(np.clip(calmar / _calmar_norm, 0, 1))
    if risk_adj_scores:
        risk_adj_composite = np.mean(risk_adj_scores)
        score += risk_adj_composite * 22
    max_score += 22

    # ---- 2. 最大回撤（0~15） ----
    if not np.isnan(mdd):
        raw = (mdd + _mdd_offset) / (_mdd_offset - _mdd_denom)
        raw = np.clip(raw, 0, 1)
        nonlinear = raw ** 0.7 if raw > 0.5 else raw
        score += nonlinear * 15
    max_score += 15

    # ---- 3. 年化收益（0~10） ----
    if not np.isnan(ann_ret):
        score += np.clip(ann_ret / _ann_ret_denom * 10, 0, 10)
    max_score += 10

    # ---- 4. 超额收益维度：信息比率+Alpha（0~12） ----
    excess_scores = []
    if ir is not None and not np.isnan(ir):
        excess_scores.append(np.clip((ir + _ir_offset) / _ir_norm, 0, 1))
    if alpha is not None and not np.isnan(alpha):
        excess_scores.append(np.clip((alpha + _alpha_offset) / _alpha_norm, 0, 1))
    if excess_scores:
        score += np.mean(excess_scores) * 12
    max_score += 12

    # ---- 5. 月度胜率（0~10） ----
    if monthly_win_rate is not None and not np.isnan(monthly_win_rate):
        score += np.clip(monthly_win_rate / _win_rate_denom * 10, 0, 10)
    max_score += 10

    # ---- 6. 宏观适配维度：风格+行业（0~12） ----
    macro_score = 0.0
    if macro_preferred_style and fund_scale_class:
        style_bonus = _calc_style_bonus(macro_preferred_style, fund_scale_class)
        macro_score += style_bonus / 10 * 6
    if industry_match > 0:
        macro_score += industry_match * 6
    score += macro_score
    max_score += 12

    # ---- 7. 经理质量维度（0~8）—— v4 新增 ----
    if manager_score > 0:
        score += manager_score / 10 * 8
        max_score += 8

    # ---- 8. 资金流情绪维度（0~6）—— v4 新增 ----
    if flow_sentiment_score > 0:
        score += flow_sentiment_score * 6
        max_score += 6

    # ---- 9. 估值安全边际维度（0~5）—— v4 新增 ----
    if not np.isnan(nav_percentile):
        valuation_score = max(0, 1 - nav_percentile)
        if nav_percentile > 0.8:
            valuation_score = valuation_score ** 1.5
        elif nav_percentile < 0.3:
            valuation_score = valuation_score ** 0.6
        score += valuation_score * 5
        max_score += 5

    # 归一化到满分100
    if max_score > 0:
        score = score / max_score * 100
    return round(score, 2)


def _calc_style_bonus(preferred_style: str, fund_scale: str) -> float:
    """
    根据当前宏观周期偏好风格计算适配加分
    preferred_style: growth/value/defensive/defensive_value/balanced
    fund_scale: 大盘/中盘/小盘/债券/货币
    """
    # 债券/货币在防御周期中获得高适配分
    style_map = {
        "growth":           {"小盘": 10, "中盘": 7,  "大盘": 4, "债券": 2, "货币": 1},
        "value":            {"大盘": 10, "中盘": 5,  "小盘": 2, "债券": 4, "货币": 2},
        "defensive":        {"大盘": 10, "中盘": 6,  "小盘": 3, "债券": 9, "货币": 6},
        "defensive_value":  {"大盘": 10, "中盘": 5,  "小盘": 1, "债券": 8, "货币": 5},
        "balanced":         {"大盘": 7,  "中盘": 7,  "小盘": 7, "债券": 7, "货币": 5},
    }
    return style_map.get(preferred_style, {}).get(fund_scale, 5)

# ============================================================
# 第 4 步：买入 / 卖出信号判定（v3 —— 融合资金流/经理/估值 + 周期动态阈值）
# ============================================================

def _get_cycle_thresholds(cycle_phase: str, asset_type: str = "股票") -> dict:
    """
    根据宏观周期阶段和资产类型动态调整信号阈值。
    债基/货基的阈值与股基分开校准，避免跨类混排。

    v5: 资产类型区分 → 债基用债基阈值
    """
    if asset_type in ("债券", "货币"):
        # 债基/货基专用阈值：评分更集中在高分区间
        defaults = {
            "buy_strong": 70, "buy_normal": 55, "sell_normal": 40, "sell_strong": 20,
            "sharpe_buy_strong": 1.2, "sharpe_buy_normal": 0.6, "sharpe_sell": -0.3,
            "mdd_buy_strong": -0.03, "mdd_sell_strong": -0.08,
            "ann_ret_sell_strong": -0.02, "win_rate_buy": 0.50, "win_rate_sell": 0.35,
        }
        cycle_adjust = {
            "stagflation": {
                "buy_strong": +3, "buy_normal": +3,  # 滞胀期债基门槛略升
                "mdd_buy_strong": -0.02,              # 更严格回撤
            },
            "recession": {
                "buy_strong": -3, "buy_normal": -5,   # 衰退期债基降低门槛
                "sharpe_buy_normal": 0.4,
            },
        }
    else:
        # 股基/混合基阈值（原有参数）
        defaults = {
            "buy_strong": 62, "buy_normal": 48, "sell_normal": 38, "sell_strong": 18,
            "sharpe_buy_strong": 0.8, "sharpe_buy_normal": 0.4, "sharpe_sell": 0.0,
            "mdd_buy_strong": -0.25, "mdd_sell_strong": -0.45,
            "ann_ret_sell_strong": -0.12, "win_rate_buy": 0.45, "win_rate_sell": 0.35,
        }
        cycle_adjust = {
            "recovery": {
                "buy_strong": -3, "buy_normal": -5,
                "mdd_buy_strong": -0.30,
                "ann_ret_sell_strong": -0.08,
            },
            "overheat": {
                "buy_strong": +5, "buy_normal": +3,
                "sharpe_buy_strong": 1.0,
                "win_rate_buy": 0.50,
            },
            "stagflation": {
                "buy_strong": +5, "buy_normal": +3,
                "sell_normal": +2, "sell_strong": +2,
                "mdd_buy_strong": -0.20,
            },
            "recession": {
                "buy_strong": +3,
                "sell_normal": -13, "sell_strong": -6,
                "sharpe_buy_normal": 0.3,
                "ann_ret_sell_strong": -0.06,
            },
            "transition": {},
        }

    result = dict(defaults)
    adj = cycle_adjust.get(cycle_phase, {})
    for k, v in adj.items():
        if k in result:
            if isinstance(v, (int, float)) and isinstance(result[k], (int, float)):
                if k.startswith(("buy_", "sell_")):
                    result[k] = result[k] + v
                elif k.startswith(("sharpe_", "win_rate_")):
                    if v > 0:
                        result[k] = v
                elif k.startswith(("mdd_", "ann_ret_")):
                    result[k] = v
                else:
                    result[k] = v
            else:
                result[k] = v
    return result


def generate_signal(score, sharpe, mdd, ann_ret, calmar,
                    monthly_win_rate=None, ir=None,
                    macro_preferred_style=None, fund_scale_class=None,
                    drawdown_recovery_days=None,
                    flow_sentiment="", manager_level="",
                    nav_percentile=None, asset_type="股票") -> str:
    """
    信号规则（v5 —— 按资产类型分开判定 + 周期动态阈值）：
    🟢 强烈推荐买入：
        score >= 动态阈值 且 sharpe 优秀 且 monthly_win_rate 优秀 且 mdd 温和
        且无情绪过热/无估值过高警告
    🟢 建议买入：
        score >= 动态阈值 且 sharpe 良好 且 monthly_win_rate 合格
    🟡 持有观望：
        中间地带
    🔴 建议卖出：
        score < 动态阈值 或 sharpe < 0 或 monthly_win_rate 低
        或 情绪过热 + 估值高位 → 强制卖出信号
    🔴 强烈建议卖出：
        score < 动态阈值 或 mdd 极大 或 ann_ret 极差
        或 drawdown_recovery > 500天
        或 经理新手 + 连续跑输 → 信任危机信号
    """
    cycle_phase = MACRO_STATE.get("cycle_phase", "transition")
    t = _get_cycle_thresholds(cycle_phase, asset_type)

    # ---- 宏观风格适配调整 ----
    style_adjust = 0
    if macro_preferred_style and fund_scale_class:
        bonus = _calc_style_bonus(macro_preferred_style, fund_scale_class)
        if bonus >= 8:
            style_adjust = 5
        elif bonus <= 3:
            style_adjust = -5

    adj_score = score + style_adjust

    # ---- 资金流情绪降级/升级 ----
    flow_downgrade = False
    flow_upgrade = False
    if flow_sentiment:
        if "过热" in str(flow_sentiment):
            flow_downgrade = True
        elif "冰点" in str(flow_sentiment):
            flow_upgrade = True

    # ---- 经理信任危机 ----
    mgr_crisis = False
    if manager_level and "新手" in str(manager_level):
        mgr_crisis = True

    # ---- 估值高位风险 ----
    valuation_high = False
    if nav_percentile is not None and not np.isnan(nav_percentile):
        if nav_percentile > 0.90:
            valuation_high = True

    # ========== 强烈卖出优先判定 ==========
    if (score < t["sell_strong"]
        or (not np.isnan(mdd) and mdd < t["mdd_sell_strong"])
        or (not np.isnan(ann_ret) and ann_ret < t["ann_ret_sell_strong"])
        or (drawdown_recovery_days is not None and drawdown_recovery_days > 500)):
        return "🔴 强烈卖出"

    # 经理新手 + 跑输基准 → 信任危机
    if mgr_crisis and monthly_win_rate is not None and not np.isnan(monthly_win_rate) and monthly_win_rate < 0.40:
        return "🔴 强烈卖出（经理信任危机）"

    # 情绪过热 + 估值高位 → 强制卖出
    if flow_downgrade and valuation_high:
        return "🔴 强烈卖出（情绪过热+估值高位）"

    # ========== 建议卖出判定 ==========
    if (adj_score < t["sell_normal"]
        or (not np.isnan(sharpe) and sharpe < t["sharpe_sell"])
        or (monthly_win_rate is not None and not np.isnan(monthly_win_rate) and monthly_win_rate < t["win_rate_sell"])):
        return "🔴 建议卖出"

    # 情绪过热单独触发建议卖出
    if flow_downgrade and not flow_upgrade:
        if valuation_high:
            return "🔴 建议卖出（情绪过热）"

    # ========== 买入判定 ==========
    # 情绪冰点 + 基本面尚可 → 逆势买入信号
    if flow_upgrade:
        if (adj_score >= t["buy_normal"]
            and not np.isnan(sharpe) and sharpe > t["sharpe_buy_normal"]
            and (monthly_win_rate is None or np.isnan(monthly_win_rate) or monthly_win_rate > t["win_rate_buy"])):
            return "🟢 建议买入（逆势信号）"

    if (adj_score >= t["buy_strong"]
        and not np.isnan(sharpe) and sharpe > t["sharpe_buy_strong"]
        and (monthly_win_rate is None or np.isnan(monthly_win_rate) or monthly_win_rate > 0.55)
        and not np.isnan(mdd) and mdd > t["mdd_buy_strong"]):
        if valuation_high:
            return "🟢 建议买入（估值偏高）"
        return "🟢 强烈推荐买入"

    if (adj_score >= t["buy_normal"]
        and not np.isnan(sharpe) and sharpe > t["sharpe_buy_normal"]
        and (monthly_win_rate is None or np.isnan(monthly_win_rate) or monthly_win_rate > t["win_rate_buy"])):
        return "🟢 建议买入"

    return "🟡 持有观望"

# ============================================================
# 第 5 步：主流程 —— 批量分析
# ============================================================

# ---- 基金经理 / 持仓集中度的缓存辅助函数 ----
MANAGER_CACHE_DAYS = 7   # 基金经理信息缓存 7 天
HOLDINGS_CACHE_DAYS = 30 # 持仓集中度缓存 30 天（季报数据更新慢）

def _load_json_cache(cache_file: str, max_days: int) -> dict | None:
    """加载 JSON 缓存，如果未过期则返回数据，否则返回 None"""
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
        cached_time = data.get("_cached_at", "")
        if cached_time:
            cached_dt = datetime.strptime(cached_time, "%Y-%m-%d")
            if (datetime.now() - cached_dt).days <= max_days:
                return data
    except Exception:
        pass
    return None

def _save_json_cache(cache_file: str, data: dict):
    """写入 JSON 缓存，附带时间戳"""
    try:
        data["_cached_at"] = datetime.now().strftime("%Y-%m-%d")
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _scrape_manager_info(fund_code: str, force_refresh: bool = False) -> dict:
    """抓取基金经理信息（姓名、任职天数、任职回报），带 JSON 缓存（7天过期）"""
    cache_file = os.path.join(MANAGER_CACHE_DIR, f"{fund_code}.json")
    if not force_refresh:
        cached = _load_json_cache(cache_file, MANAGER_CACHE_DAYS)
        if cached is not None:
            # 返回时去掉缓存元数据
            return {k: v for k, v in cached.items() if k != "_cached_at"}
    try:
        url = f"https://fundf10.eastmoney.com/jjjl_{fund_code}.html"
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://fund.eastmoney.com/",
        }, timeout=10)
        resp.encoding = "utf-8"
        text = resp.text
        # 提取当前基金经理行。HTML结构: <td>日期</td><td>至今</td><td><a>姓名</a></td><td>天数</td><td>回报</td>
        mgr_rows = re.findall(
            r'<td>(\d{4}-\d{2}-\d{2})</td><td>(至今)</td><td[^>]*>(?:<a[^>]*>)?([^<]+)(?:</a>)?\s*</td><td[^>]*>(\d+(?:年又\d+)?天)</td><td[^>]*>\s*([\-\d.]+%)\s*</td>',
            text
        )
        if mgr_rows:
            m = mgr_rows[0]  # 第一位是现任基金经理
            result = {
                "基金经理": m[2].strip(),
                "任职起始": m[0],
                "任职天数": m[3],
                "任职回报": m[4],
            }
            _save_json_cache(cache_file, result)
            return result
    except Exception:
        # 网络异常时降级返回过期缓存
        cached = _load_json_cache(cache_file, 99999)  # 忽略过期
        if cached:
            return {k: v for k, v in cached.items() if k != "_cached_at"}
    return {}

def _scrape_holdings_concentration(fund_code: str, force_refresh: bool = False) -> dict:
    """抓取前十大持仓集中度，带 JSON 缓存（30天过期，季报数据更新慢）"""
    cache_file = os.path.join(HOLDINGS_CACHE_DIR, f"{fund_code}.json")
    if not force_refresh:
        cached = _load_json_cache(cache_file, HOLDINGS_CACHE_DAYS)
        if cached is not None:
            return {k: v for k, v in cached.items() if k != "_cached_at"}
    try:
        url = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
        params = {"type": "jjcc", "code": fund_code, "topline": 10, "year": "", "month": ""}
        resp = requests.get(url, params=params, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": f"https://fundf10.eastmoney.com/ccmx_{fund_code}.html",
        }, timeout=10)
        resp.encoding = "utf-8"
        text = resp.text
        # 提取占净值比例
        pcts = re.findall(r'<td[^>]*>\s*(\d+\.\d+)%\s*</td>', text)
        if pcts:
            pct_sum = sum(float(p) for p in pcts[:10])
            result = {"前十大集中度": f"{pct_sum:.1f}%"}
            _save_json_cache(cache_file, result)
            return result
    except Exception:
        # 网络异常时降级返回过期缓存
        cached = _load_json_cache(cache_file, 99999)
        if cached:
            return {k: v for k, v in cached.items() if k != "_cached_at"}
    return {}


# ============================================================
# 基金经理深度画像模块（v3 新增）
# ============================================================
_MGR_PROFILE_CACHE_DIR = None


def _get_mgr_profile_cache_dir():
    global _MGR_PROFILE_CACHE_DIR
    if _MGR_PROFILE_CACHE_DIR is None:
        _MGR_PROFILE_CACHE_DIR = os.path.join(CACHE_DIR, "manager_profile")
    return _MGR_PROFILE_CACHE_DIR


def scrape_manager_deep_profile(fund_code: str, force_refresh: bool = False) -> dict:
    """
    抓取基金经理深度画像：
    - 管理基金数量
    - 历任基金数（经验丰富度）
    - 管理总规模
    - 团队稳定性（基金经理变更频率）
    - 从业年限（从首次任职日期算）
    缓存：cache/manager_profile/{fund_code}.json，7天过期
    """
    cache_dir = _get_mgr_profile_cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{fund_code}.json")

    if not force_refresh:
        cached = _load_json_cache(cache_file, 7)
        if cached is not None:
            return {k: v for k, v in cached.items() if k != "_cached_at"}

    result = {}
    try:
        url = f"https://fundf10.eastmoney.com/jjjl_{fund_code}.html"
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://fund.eastmoney.com/",
        }, timeout=10)
        resp.encoding = "utf-8"
        text = resp.text

        # 解析所有历任基金经理
        all_mgrs = re.findall(
            r'<td>(\d{4}-\d{2}-\d{2})</td><td>(至今|\d{4}-\d{2}-\d{2})</td>'
            r'<td[^>]*>(?:<a[^>]*>)?([^<]+)(?:</a>)?\s*</td>'
            r'<td[^>]*>(\d+(?:年又\d+)?天)</td>'
            r'<td[^>]*>\s*([\-\d.]+%)\s*</td>',
            text
        )

        if all_mgrs:
            result["历任经理人数"] = len(set(m[2].strip() for m in all_mgrs))

            # 首个任职日期 → 估算从业年限
            first_date = all_mgrs[-1][0]  # 最后一条是最早的记录
            try:
                first_dt = datetime.strptime(first_date, "%Y-%m-%d")
                years = (datetime.now() - first_dt).days / 365.25
                result["团队管理年限"] = round(years, 1)
            except Exception:
                pass

            # 现任经理信息
            current_mgr = all_mgrs[0]
            mgr_name = current_mgr[2].strip()
            mgr_start = current_mgr[0]
            mgr_days_str = current_mgr[3]
            mgr_return = current_mgr[4]

            # 解析任职天数
            days = 0
            day_match = re.findall(r'(\d+)', mgr_days_str)
            if "年" in mgr_days_str and len(day_match) >= 2:
                days = int(day_match[0]) * 365 + int(day_match[1])
            elif len(day_match) >= 1:
                days = int(day_match[0])

            result["现任经理"] = mgr_name
            result["现任任职天数"] = days
            result["现任任职年数"] = round(days / 365.25, 1)
            result["现任任职回报"] = mgr_return

            # 判断经理经验等级
            if days > 5 * 365:
                result["经理经验等级"] = "🏅 资深（>5年）"
            elif days > 3 * 365:
                result["经理经验等级"] = "✅ 成熟（3-5年）"
            elif days > 1 * 365:
                result["经理经验等级"] = "🟡 中等（1-3年）"
            else:
                result["经理经验等级"] = "⚠️ 新手（<1年）"

            # 团队稳定性：历任经理人数越少越稳定
            if result["历任经理人数"] <= 3:
                result["团队稳定性"] = "🟢 稳定"
            elif result["历任经理人数"] <= 6:
                result["团队稳定性"] = "🟡 一般"
            else:
                result["团队稳定性"] = "🔴 频繁更换"

        _save_json_cache(cache_file, result)
    except Exception:
        cached = _load_json_cache(cache_file, 99999)
        if cached:
            return {k: v for k, v in cached.items() if k != "_cached_at"}

    return result


def get_combined_manager_score(mgr_basic: dict, mgr_deep: dict) -> float:
    """
    综合基金经理评分（0~10）：
    - 任职年数: 0~3 分
    - 经验等级: 0~3 分
    - 团队稳定性: 0~2 分
    - 任职回报: 0~2 分
    """
    score = 0.0

    # 任职年数
    years = mgr_deep.get("现任任职年数", 0)
    if years >= 5:
        score += 3
    elif years >= 3:
        score += 2
    elif years >= 1:
        score += 1

    # 经验等级
    level = mgr_deep.get("经理经验等级", "")
    if "资深" in level:
        score += 3
    elif "成熟" in level:
        score += 2
    elif "中等" in level:
        score += 1

    # 团队稳定性
    stability = mgr_deep.get("团队稳定性", "")
    if "稳定" in stability:
        score += 2
    elif "一般" in stability:
        score += 1

    # 任职回报
    ret_str = mgr_basic.get("任职回报", "0%")
    try:
        ret_val = float(ret_str.strip("%"))
        if ret_val > 100:
            score += 2
        elif ret_val > 30:
            score += 1
    except Exception:
        pass

    return round(score, 1)


def get_combined_manager_score_from_enrich(mgr_level: str, mgr_years: float,
                                            mgr_stability: str,
                                            mgr_return_val: float) -> float:
    """
    从 enrich 字典的平铺字段计算经理综合评分（0~10）
    避免再次调用 scrape 函数，直接使用 enrich_fund_analysis 已获取的数据
    """
    score = 0.0
    years = mgr_years or 0
    if years >= 5:
        score += 3
    elif years >= 3:
        score += 2
    elif years >= 1:
        score += 1

    level = str(mgr_level)
    if "资深" in level:
        score += 3
    elif "成熟" in level:
        score += 2
    elif "中等" in level:
        score += 1

    stability = str(mgr_stability)
    if "稳定" in stability:
        score += 2
    elif "一般" in stability:
        score += 1

    if mgr_return_val > 100:
        score += 2
    elif mgr_return_val > 30:
        score += 1

    return round(score, 1)


def _flow_sentiment_to_score(flow_sentiment: str) -> float:
    """
    将资金流情绪文字转换为评分（0~1）
    - 情绪冰点 → 高逆势价值，得分高
    - 温和申购/资金平稳 → 正常
    - 情绪过热 → 低分，风险信号
    """
    s = str(flow_sentiment)
    if "冰点" in s:
        return 0.9   # 冰点=逆势买入信号，高价值
    if "轻度赎回" in s:
        return 0.6
    if "温和申购" in s or "平稳" in s:
        return 0.5
    if "过热" in s:
        return 0.1   # 过热=风险信号
    return 0.5


# ============================================================
# 综合增强分析函数（v3 —— 整合资金流+行业+经理画像）
# ============================================================
def enrich_fund_analysis(fund_code: str, fund_name: str, fund_type: str,
                         force_refresh: bool = False) -> dict:
    """
    对单只基金进行增强分析，整合资金流、行业配置、经理深度画像
    返回额外分析字段
    """
    enrich = {}

    # 行业分类
    industries = classify_fund_industry(fund_name, fund_type)
    enrich["行业分布"] = industries
    enrich["行业集中度"] = calc_industry_concentration(industries)
    # 当前周期偏好行业
    preferred_inds = get_cycle_industry_preference(MACRO_STATE.get("cycle_phase", "transition"))
    industry_match = 0
    for ind, weight in industries.items():
        if ind in preferred_inds:
            industry_match += weight
    enrich["行业周期匹配度"] = round(min(industry_match, 1.0), 2)

    # 资金流（异步，失败不影响主流程）
    try:
        flow_data = fetch_fund_flow_data(fund_code, force_refresh)
        enrich["份额变动率"] = flow_data.get("份额变动率", "")
        enrich["份额变动信号"] = flow_data.get("份额变动信号", "")
        enrich["规模变动率"] = flow_data.get("规模变动率", "")
        enrich["规模信号"] = flow_data.get("规模信号", "")
        enrich["资金流情绪"] = analyze_flow_sentiment(
            flow_data.get("份额变动率", ""),
            flow_data.get("规模变动率", ""),
            flow_data.get("规模信号", ""),
        )
    except Exception:
        pass

    # 基金经理深度画像（异步，失败不影响主流程）
    try:
        mgr_deep = scrape_manager_deep_profile(fund_code, force_refresh)
        enrich["现任经理"] = mgr_deep.get("现任经理", "")
        enrich["经理经验等级"] = mgr_deep.get("经理经验等级", "")
        enrich["现任任职年数"] = mgr_deep.get("现任任职年数", "")
        enrich["历任经理人数"] = mgr_deep.get("历任经理人数", "")
        enrich["团队稳定性"] = mgr_deep.get("团队稳定性", "")
        enrich["团队管理年限"] = mgr_deep.get("团队管理年限", "")
    except Exception:
        pass

    return enrich


def analyze_fund(fund_code: str, fund_name: str, fund_type: str = "",
                 force_refresh: bool = False) -> dict:
    """分析单只基金，返回指标字典（v3 —— 含行业/资金流/经理深度画像）"""
    nav_df = load_fund_nav_history(fund_code, days=1095, force_refresh=force_refresh)  # 3 年数据
    if nav_df is None or len(nav_df) < 120:
        return None
    nav = nav_df["nav"]

    # ---- 风格分类 & 匹配基准 ----
    asset_type = classify_fund_asset_type(fund_name, fund_type)
    fund_type_label = classify_fund_type_label(fund_name, fund_type)
    scale_class = classify_fund_by_scale(fund_name, fund_type)
    matched_bench_name, matched_bench = get_matched_benchmark(fund_name, fund_type)

    # ---- 基础指标 ----
    sharpe = calc_sharpe_ratio(nav)
    mdd = calc_max_drawdown(nav)
    ann_ret = calc_annual_return(nav)
    calmar = calc_calmar_ratio(nav)
    vol = calc_volatility(nav)
    sortino = calc_sortino_ratio(nav)

    # ---- 估值分位 ----
    nav_pct = calc_nav_percentile(nav)

    # ---- 基准对标（使用匹配的风格基准） ----
    alpha, ir = np.nan, np.nan
    down_cap = np.nan
    up_cap = np.nan
    if matched_bench is not None:
        alpha, ir = calc_alpha_and_ir(nav, matched_bench)
        down_cap = calc_downside_capture(nav, matched_bench)
        up_cap = calc_upside_capture(nav, matched_bench)

    # ---- 月度胜率 & 滚动分析 ----
    win_rate_info = calc_monthly_win_rate(nav, matched_bench)
    monthly_win_rate = win_rate_info.get("月度胜率")
    rolling_12m_win = win_rate_info.get("滚动12月胜率")
    win_trend = win_rate_info.get("胜率趋势")
    consecutive_win = win_rate_info.get("连续跑赢")
    consecutive_loss = win_rate_info.get("连续跑输")

    # ---- 回撤修复天数 ----
    dd_recovery = calc_drawdown_recovery(nav)
    max_dd_recovery = dd_recovery.get("最大回撤修复天")
    avg_dd_recovery = dd_recovery.get("平均回撤修复天")

    # ---- 滚动夏普 ----
    rolling_sharpe_info = calc_rolling_metrics(nav, 252)
    rolling_sharpe_cur = rolling_sharpe_info.get("滚动夏普(当前)")

    # ---- v3 增强分析：行业配置 + 资金流 + 经理画像 ----
    enrich = enrich_fund_analysis(fund_code, fund_name, fund_type, force_refresh)
    industry_match = enrich.get("行业周期匹配度", 0)

    # ---- 综合评分（v4 —— 去共线性 + 新维度） ----
    macro_style = MACRO_STATE.get("preferred_style")

    # 计算经理综合评分和资金流情绪评分
    mgr_deep = enrich.get("经理经验等级", "")
    mgr_years = enrich.get("现任任职年数", 0) or 0
    mgr_stability = enrich.get("团队稳定性", "")
    mgr_ret_str = enrich.get("现任任职回报", "0%")
    try:
        mgr_ret_val = float(str(mgr_ret_str).strip("%"))
    except Exception:
        mgr_ret_val = 0
    mgr_score = get_combined_manager_score_from_enrich(mgr_deep, mgr_years, mgr_stability, mgr_ret_val)

    # 资金流情绪评分
    flow_sent = enrich.get("资金流情绪", "")
    flow_score = _flow_sentiment_to_score(flow_sent)

    # 净值分位数值
    nav_pct_val = nav_pct if not np.isnan(nav_pct) else 0.5

    score = score_fund(sharpe, mdd, ann_ret, calmar, sortino, vol,
                       monthly_win_rate=monthly_win_rate,
                       ir=ir, alpha=alpha,
                       macro_preferred_style=macro_style,
                       fund_scale_class=scale_class,
                       industry_match=industry_match,
                       manager_score=mgr_score,
                       flow_sentiment_score=flow_score,
                       nav_percentile=nav_pct_val,
                       asset_type=asset_type)

    # ---- 信号判定（v5 —— 按资产类型分开判定） ----
    signal = generate_signal(score, sharpe, mdd, ann_ret, calmar,
                             monthly_win_rate=monthly_win_rate,
                             ir=ir,
                             macro_preferred_style=macro_style,
                             fund_scale_class=scale_class,
                             drawdown_recovery_days=max_dd_recovery,
                             flow_sentiment=flow_sent,
                             manager_level=mgr_deep,
                             nav_percentile=nav_pct_val,
                             asset_type=asset_type)

    return {
        "基金代码": fund_code,
        "基金名称": fund_name,
        "基金类型": fund_type_label,
        "资产类别": asset_type,
        "规模风格": scale_class,
        "匹配基准": matched_bench_name,
        "综合评分": score,
        "夏普比率": round(sharpe, 3) if not np.isnan(sharpe) else None,
        "最大回撤": f"{mdd:.2%}" if not np.isnan(mdd) else None,
        "年化收益": f"{ann_ret:.2%}" if not np.isnan(ann_ret) else None,
        "Calmar": round(calmar, 3) if not np.isnan(calmar) else None,
        "Sortino": round(sortino, 3) if not np.isnan(sortino) else None,
        "年化波动": f"{vol:.2%}" if not np.isnan(vol) else None,
        "Alpha(年化)": f"{alpha:.2%}" if not np.isnan(alpha) else None,
        "信息比率": round(ir, 3) if not np.isnan(ir) else None,
        "下行捕获率": f"{down_cap:.1%}" if not np.isnan(down_cap) else None,
        "上行捕获率": f"{up_cap:.1%}" if not np.isnan(up_cap) else None,
        "月度胜率": f"{monthly_win_rate:.1%}" if monthly_win_rate is not None and not np.isnan(monthly_win_rate) else None,
        "滚动12月胜率": f"{rolling_12m_win:.1%}" if rolling_12m_win is not None and not np.isnan(rolling_12m_win) else None,
        "胜率趋势": win_trend,
        "连续跑赢(月)": consecutive_win,
        "连续跑输(月)": consecutive_loss,
        "最大回撤修复天": max_dd_recovery,
        "平均回撤修复天": avg_dd_recovery,
        "滚动夏普(当前)": rolling_sharpe_cur,
        "净值分位": f"{nav_pct:.0%}" if not np.isnan(nav_pct) else None,
        "操作信号": signal,
        # ---- v3 新增字段 ----
        "行业分布": enrich.get("行业分布", {}),
        "行业集中度": enrich.get("行业集中度", ""),
        "行业周期匹配度": enrich.get("行业周期匹配度", ""),
        "份额变动率": enrich.get("份额变动率", ""),
        "份额变动信号": enrich.get("份额变动信号", ""),
        "规模变动率": enrich.get("规模变动率", ""),
        "规模信号": enrich.get("规模信号", ""),
        "资金流情绪": enrich.get("资金流情绪", ""),
        "经理经验等级": enrich.get("经理经验等级", ""),
        "现任任职年数": enrich.get("现任任职年数", ""),
        "团队稳定性": enrich.get("团队稳定性", ""),
    }


def _output_coarse_screening(all_funds: pd.DataFrame, top_n: int):
    """
    全市场粗筛结果输出：
    - 用粗筛得分对所有基金排序
    - 基于粗筛得分 + 近1年收益做简易信号判定
    - 输出到 coarse_screening.csv，方便查看全市场排名
    """
    output_file = "coarse_screening_result.csv"

    # 构建输出
    out_cols = ["基金代码", "基金简称", "基金类型", "近1年", "近2年", "近3年",
                "近6月", "粗筛得分"]
    out_cols = [c for c in out_cols if c in all_funds.columns]
    df_out = all_funds[out_cols].copy()

    # 简易信号：基于粗筛得分 + 近1年收益
    def coarse_signal(row):
        cs = row.get("粗筛得分", 0)
        ret_1y = pd.to_numeric(row.get("近1年"), errors="coerce") or 0
        if cs >= 75:
            return "🟢 粗筛买入"
        elif cs >= 60:
            return "🟡 粗筛关注"
        elif cs < 30 or ret_1y < -0.10:
            return "🔴 粗筛回避"
        return "🟡 粗筛一般"

    df_out["粗筛信号"] = df_out.apply(coarse_signal, axis=1)

    df_out.to_csv(output_file, index=False, encoding="utf-8-sig")
    total = len(df_out)
    buy = (df_out["粗筛信号"] == "🟢 粗筛买入").sum()
    watch = (df_out["粗筛信号"] == "🟡 粗筛关注").sum()
    avoid = (df_out["粗筛信号"] == "🔴 粗筛回避").sum()
    neutral = total - buy - watch - avoid

    print(f"\n📊 全市场粗筛（{total} 只基金）：")
    print(f"  🟢 粗筛买入: {buy} 只")
    print(f"  🟡 粗筛关注: {watch} 只")
    print(f"  🟡 粗筛一般: {neutral} 只")
    print(f"  🔴 粗筛回避: {avoid} 只")
    print(f"  💾 全量结果已保存至 {output_file}")
    print(f"  📌 接下来对 Top{top_n} 做精细分析...")
    print()


def run_screening(top_n: int = 50, max_workers: int = 8, force_refresh: bool = False,
                  min_scale: float = 1.0):
    """
    主入口（v3 —— 动态宏观+行业/资金流/经理深度画像）：
    1. 自动获取宏观数据（PMI/PE/国债），动态判断周期阶段
    2. 加载全市场基金列表及各周期收益率（优先用缓存）
    3. 规模过滤：剔除规模 < min_scale 亿的基金（排雷）
    4. 粗筛：用简易风险调整收益得分排序，取 top_n + bottom_n/2
    5. 预加载多规模基准（沪深300/中证500/中证1000）
    6. 多线程并发对粗筛结果做精细指标计算
       （含月度胜率、风格匹配基准、Alpha/IR、回撤修复等）
    7. v3增强：行业配置穿透 + 资金流分析 + 基金经理深度画像
    8. 补充基金经理信息 + 持仓集中度
    9. 添加同类排名百分位，输出买入/卖出清单

    max_workers: 并发线程数，默认 8
    force_refresh: 强制刷新所有缓存
    min_scale: 最小基金规模（亿元）
    """
    # ---- 输出宏观周期 ----
    print("\n" + "=" * 70)
    print("📊 当前宏观环境判断")
    print("=" * 70)
    src_label = "🌐 自动获取" if MACRO_STATE.get("data_source") == "auto" else "⚠️ 默认回退值"
    print(f"  数据来源: {src_label}")
    print(f"  制造业PMI: {MACRO_STATE['pmi_manufacturing']} ({'扩张' if MACRO_STATE['pmi_manufacturing']>=50 else '收缩'})")
    print(f"  沪深300 PE: {MACRO_STATE['csi300_pe']}")
    print(f"  10Y国债收益率: {MACRO_STATE['bond_10y']}%")
    print(f"  股权风险溢价(ERP): {MACRO_STATE['equity_risk_premium']}%")
    print(f"  🔄 周期阶段: {MACRO_STATE['cycle_phase']}")
    print(f"  ⭐ 偏好风格: {MACRO_STATE['preferred_style']}")
    print(f"  🏭 偏好行业: {', '.join(get_cycle_industry_preference(MACRO_STATE['cycle_phase']))}")
    print(f"  💡 策略提示: {_get_cycle_advice(MACRO_STATE['cycle_phase'])}")
    print("=" * 70)

    # ---- 加载基金列表（含各周期收益率）----
    all_funds = load_all_funds(force_refresh=force_refresh)
    if all_funds.empty:
        print("❌ 未加载到基金数据")
        return pd.DataFrame()

    total_before = len(all_funds)

    # ---- 规模过滤 ----
    if "基金规模" in all_funds.columns:
        all_funds["基金规模"] = pd.to_numeric(all_funds["基金规模"], errors="coerce")
        scale_mask = all_funds["基金规模"] >= min_scale
        scale_mask = scale_mask | all_funds["基金规模"].isna()
        all_funds = all_funds[scale_mask]
        filtered_count = total_before - len(all_funds)
        if filtered_count > 0:
            print(f"🔍 规模过滤：剔除 {filtered_count} 只规模 < {min_scale}亿 的基金，剩余 {len(all_funds)} 只")

    # ---- 粗筛：用简易风险调整收益得分排序 ----
    all_funds["近1年"] = pd.to_numeric(all_funds["近1年"], errors="coerce")
    all_funds = all_funds.dropna(subset=["近1年"])
    all_funds["粗筛得分"] = all_funds.apply(calc_coarse_score, axis=1)
    all_funds = all_funds[all_funds["粗筛得分"] > -900]
    all_funds = all_funds.sort_values("粗筛得分", ascending=False)

    print(f"📊 粗筛池共 {len(all_funds)} 只基金，按风险调整收益排序")

    # ---- 全市场粗筛结果输出 ----
    # 对所有基金做粗筛信号判定（简易版），让用户看到全市场排名
    _output_coarse_screening(all_funds, top_n)

    top_funds = all_funds.head(top_n)
    bottom_funds = all_funds.tail(top_n // 2)
    candidates = pd.concat([top_funds, bottom_funds]).drop_duplicates(subset=["基金代码"])
    print(f"\n精细分析 {len(candidates)} 只候选基金（{max_workers} 线程并发）...")

    # ---- 预加载多规模基准 ----
    print("📈 加载多规模基准（沪深300/中证500/中证1000）...")
    load_all_benchmarks(force_refresh=False)

    # ---- 构建任务列表（带基金类型） ----
    tasks = [
        (row["基金代码"], row.get("基金简称", ""), row.get("基金类型", ""))
        for _, row in candidates.iterrows()
    ]

    # ---- 多线程并发分析 ----
    results = []
    completed = 0
    total = len(tasks)

    t_start = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(analyze_fund, code, name, ftype, force_refresh): (code, name)
            for code, name, ftype in tasks
        }
        for future in as_completed(future_map):
            code, name = future_map[future]
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"  ⚠ {code} {name} 分析异常: {e}")
            completed += 1
            if completed % 5 == 0 or completed == total or completed == 1:
                elapsed = time.time() - t_start
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"  进度: {completed}/{total} | 速率: {rate:.1f}只/秒 | 预计剩余: {eta:.0f}秒")

    if not results:
        print("❌ 没有成功分析的基金")
        return pd.DataFrame()

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("综合评分", ascending=False).reset_index(drop=True)

    # ---- 同类排名百分位（v5：按资产类型分别计算） ----
    for period in ["近1月", "近3月", "近6月", "近1年", "近2年", "近3年"]:
        if period in all_funds.columns:
            all_vals = pd.to_numeric(all_funds[period], errors="coerce").dropna()
            if len(all_vals) > 0:
                col_name = f"{period}百分位"
                # v5: 按基金代码获取对应的资产类型，传给 _calc_percentile
                asset_map = {}
                if "资产类别" in df_result.columns:
                    for _, r in df_result.iterrows():
                        asset_map[r["基金代码"]] = r.get("资产类别")
                df_result[col_name] = df_result["基金代码"].apply(
                    lambda code: _calc_percentile(code, period, all_funds, all_vals,
                                                  asset_type=asset_map.get(code))
                )

    # ---- 合并基金规模 & 粗筛得分 ----
    scale_map = {}
    coarse_map = {}
    if "基金规模" in all_funds.columns:
        for _, row in all_funds.iterrows():
            code = row["基金代码"]
            scale_map[code] = row.get("基金规模")
            coarse_map[code] = row.get("粗筛得分")
    df_result["基金规模(亿)"] = df_result["基金代码"].map(scale_map)
    df_result["粗筛得分"] = df_result["基金代码"].map(coarse_map)

    # ---- 补充基金经理 & 持仓集中度（对买入清单，串行抓取避免被封） ----
    buy_codes = df_result[df_result["操作信号"].str.contains("买入")]["基金代码"].tolist()
    if buy_codes:
        print(f"\n👤 补充基金经理 & 持仓信息（{len(buy_codes)} 只买入基金）...")
        mgr_data = {}
        hold_data = {}
        for i, code in enumerate(buy_codes):
            if (i + 1) % 3 == 0 or i == 0:
                print(f"  基金经理: {i+1}/{len(buy_codes)}")
            mgr_data[code] = _scrape_manager_info(code)
            hold_data[code] = _scrape_holdings_concentration(code)
            time.sleep(0.3)  # 避免请求过快被封
        # 合并到结果
        df_result["基金经理"] = df_result["基金代码"].apply(
            lambda c: mgr_data.get(c, {}).get("基金经理", ""))
        df_result["任职天数"] = df_result["基金代码"].apply(
            lambda c: mgr_data.get(c, {}).get("任职天数", ""))
        df_result["任职回报"] = df_result["基金代码"].apply(
            lambda c: mgr_data.get(c, {}).get("任职回报", ""))
        df_result["前十大集中度"] = df_result["基金代码"].apply(
            lambda c: hold_data.get(c, {}).get("前十大集中度", ""))

    # ---- 输出结果 ----
    buy_list = df_result[df_result["操作信号"].str.contains("买入")]
    sell_list = df_result[df_result["操作信号"].str.contains("卖出")]
    hold_list = df_result[df_result["操作信号"].str.contains("观望")]
    print("\n" + "=" * 70)
    print("📊 基金筛选结果汇总")
    print("=" * 70)
    print(f"  分析总数：{len(df_result)}")
    print(f"  🟢 买入信号：{len(buy_list)} 只")
    print(f"  🔴 卖出信号：{len(sell_list)} 只")
    print(f"  🟡 观望信号：{len(hold_list)} 只")
    print(f"\n  当前周期偏好: {MACRO_STATE['preferred_style']} 风格")
    print("\n🟢 【值得买 —— 推荐清单】")
    buy_cols = ["基金代码", "基金名称", "基金类型", "资产类别", "规模风格", "匹配基准", "综合评分", "夏普比率",
                "最大回撤", "年化收益", "Alpha(年化)", "信息比率",
                "月度胜率", "胜率趋势", "连续跑赢(月)",
                "行业周期匹配度", "资金流情绪",
                "经理经验等级", "团队稳定性",
                "近1年百分位", "净值分位", "最大回撤修复天",
                "基金经理", "任职回报", "前十大集中度", "基金规模(亿)", "操作信号"]
    buy_cols = [c for c in buy_cols if c in df_result.columns]
    print(buy_list[buy_cols].to_string(index=False))
    print("\n🔴 【必须卖 —— 风险清单】")
    sell_cols = ["基金代码", "基金名称", "基金类型", "资产类别", "规模风格", "综合评分", "夏普比率",
                 "最大回撤", "年化收益", "月度胜率",
                 "资金流情绪", "行业周期匹配度",
                 "下行捕获率", "最大回撤修复天", "近1年百分位", "操作信号"]
    sell_cols = [c for c in sell_cols if c in df_result.columns]
    print(sell_list[sell_cols].to_string(index=False))
    # 保存完整结果
    df_result.to_csv("fund_screening_result.csv", index=False, encoding="utf-8-sig")
    total_time = time.time() - t_start
    print(f"\n✅ 完整结果已保存至 fund_screening_result.csv（总耗时 {total_time:.0f}秒）")
    return df_result


def _get_cycle_advice(cycle: str) -> str:
    """返回当前宏观周期下的操作建议"""
    advice = {
        "recovery":    "复苏期→偏好成长风格，关注中小盘高弹性基金",
        "overheat":    "过热期→偏好价值风格，关注大盘蓝筹、红利基金",
        "stagflation": "滞胀期→偏防守+价值，关注低波动、高股息基金",
        "recession":   "衰退期→防御优先，关注债券基金、货币基金",
        "transition":  "过渡期→均衡配置，股债平衡，分散风险",
    }
    return advice.get(cycle, "均衡配置")


def _calc_percentile(code: str, period: str, all_funds: pd.DataFrame, all_vals: pd.Series,
                     asset_type: str = None) -> str:
    """计算单只基金在某周期的同类排名百分位（v5：可限定资产类型）"""
    try:
        fund_row = all_funds[all_funds["基金代码"] == code]
        if fund_row.empty:
            return "N/A"
        val = pd.to_numeric(fund_row[period].iloc[0], errors="coerce")
        if pd.isna(val):
            return "N/A"
        # v5: 如果指定了资产类型，只和同类比较
        if asset_type is not None and "基金类型" in all_funds.columns:
            same_type_mask = all_funds["基金类型"].apply(
                lambda ft: classify_fund_asset_type("", str(ft))
            ) == asset_type
            same_type_indices = all_funds[same_type_mask].index
            same_type_vals = all_vals.loc[all_vals.index.intersection(same_type_indices)]
            if len(same_type_vals) > 0:
                pct = (same_type_vals < val).sum() / len(same_type_vals) * 100
                return f"{pct:.1f}%"
        # 回退：全市场百分位
        pct = (all_vals < val).sum() / len(all_vals) * 100
        return f"{pct:.1f}%"
    except Exception:
        return "N/A"

# ============================================================
# 第 6 步：持有基金分析
# ============================================================

HOLDINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "holdings.csv")


def _analyze_portfolio(df_final: pd.DataFrame, quotes: dict,
                       holdings: pd.DataFrame, total_pnl: float):
    """
    v4 新增：组合层面分析
    1. 组合风格/行业暴露分布
    2. 组合集中度风险（同风格/同赛道占比）
    3. 组合净值序列合成 → 组合回撤/波动率
    4. 组合相关性矩阵（高相关警告）
    """
    if len(df_final) < 2:
        return

    print("\n" + "=" * 70)
    print("📐 组合层面分析")
    print("=" * 70)

    # ---- 1. 风格暴露分布 ----
    if "规模风格" in df_final.columns:
        style_counts = df_final["规模风格"].value_counts()
        print(f"\n  📊 风格暴露分布:")
        for style, cnt in style_counts.items():
            pct = cnt / len(df_final) * 100
            bar = "█" * int(pct / 5)
            print(f"     {style}: {cnt}只 ({pct:.0f}%) {bar}")
        # 风格集中度警告
        max_style_pct = style_counts.max() / len(df_final) * 100
        if max_style_pct > 60:
            max_style = style_counts.idxmax()
            print(f"  ⚠️  {max_style} 风格占比 {max_style_pct:.0f}%，集中度偏高！")

    # ---- 2. 行业暴露分布 ----
    if "行业分布" in df_final.columns:
        industry_agg = {}
        for _, row in df_final.iterrows():
            inds = row["行业分布"]
            if isinstance(inds, dict):
                for ind, w in inds.items():
                    industry_agg[ind] = industry_agg.get(ind, 0) + w
        if industry_agg:
            total_w = sum(industry_agg.values())
            print(f"\n  🏭 行业暴露分布:")
            sorted_inds = sorted(industry_agg.items(), key=lambda x: x[1], reverse=True)
            for ind, w in sorted_inds[:8]:
                pct = w / total_w * 100 if total_w > 0 else 0
                bar = "█" * int(pct / 5)
                print(f"     {ind}: {pct:.0f}% {bar}")
            # 行业集中度
            hhi = sum((w / total_w) ** 2 for w in industry_agg.values()) if total_w > 0 else 0
            if hhi > 0.5:
                top_ind = sorted_inds[0][0]
                print(f"  ⚠️  行业集中度偏高（HHI={hhi:.2f}），{top_ind} 占比过大！")

    # ---- 3. 组合相关性矩阵 ----
    print(f"\n  🔗 组合相关性分析（基于净值序列）:")
    nav_dict = {}
    for _, row in df_final.iterrows():
        code = row["基金代码"]
        try:
            nav_df = load_fund_nav_history(str(code), days=365, force_refresh=False)
            if nav_df is not None and len(nav_df) >= 60:
                nav_dict[code] = nav_df["nav"]
        except Exception:
            pass

    if len(nav_dict) >= 2:
        # 构建收益率DataFrame
        ret_df = pd.DataFrame()
        for code, nav in nav_dict.items():
            ret = nav.pct_change().dropna()
            ret_df[code] = ret
        # 对齐日期
        ret_df = ret_df.dropna()
        if len(ret_df) >= 30 and ret_df.shape[1] >= 2:
            corr = ret_df.corr()
            # 输出高相关对（>0.85）
            high_corr_pairs = []
            codes = list(corr.columns)
            for i in range(len(codes)):
                for j in range(i + 1, len(codes)):
                    if corr.iloc[i, j] > 0.85:
                        name_i = df_final[df_final["基金代码"] == str(codes[i])]
                        name_j = df_final[df_final["基金代码"] == str(codes[j])]
                        ni = name_i["基金名称"].values[0] if len(name_i) > 0 else codes[i]
                        nj = name_j["基金名称"].values[0] if len(name_j) > 0 else codes[j]
                        high_corr_pairs.append((ni, nj, corr.iloc[i, j]))
            if high_corr_pairs:
                print(f"     ⚠️  发现 {len(high_corr_pairs)} 对高相关基金（>0.85）：")
                for ni, nj, c in high_corr_pairs[:5]:
                    print(f"       {ni} ↔ {nj}: r={c:.3f}")
            else:
                print(f"     ✅ 未发现高度相关基金对（分散化良好）")
            # 平均相关性
            avg_corr = (corr.values.sum() - corr.shape[0]) / (corr.shape[0] * (corr.shape[0] - 1))
            print(f"     组合平均相关性: {avg_corr:.3f}")
            if avg_corr > 0.7:
                print(f"     ⚠️  平均相关性偏高，分散化不足！")

    # ---- 4. 组合净值合成与回撤 ----
    if len(nav_dict) >= 2:
        combined_nav = None
        holdings_map = {}
        for _, hrow in holdings.iterrows():
            shares = float(hrow.get("持有份额", 0) or 0)
            holdings_map[str(hrow["基金代码"])] = shares
        total_shares = sum(holdings_map.values())
        if total_shares > 0:
            # 按份额加权合成组合净值
            nav_list = []
            for code, nav_s in nav_dict.items():
                w = holdings_map.get(code, 0) / total_shares
                if w > 0:
                    nav_list.append(nav_s * w)
            if nav_list:
                combined_nav = pd.concat(nav_list, axis=1).sum(axis=1).dropna()
        else:
            # 无份额信息，等权合成
            combined_nav = pd.concat(
                [s for s in nav_dict.values()], axis=1
            ).mean(axis=1).dropna()

        if combined_nav is not None and len(combined_nav) >= 60:
            port_mdd = calc_max_drawdown(combined_nav)
            port_vol = calc_volatility(combined_nav)
            port_ann = calc_annual_return(combined_nav)
            port_sharpe = calc_sharpe_ratio(combined_nav)
            print(f"\n  📈 组合整体指标（近1年）：")
            print(f"     组合年化收益: {port_ann:.2%}" if not np.isnan(port_ann) else f"     组合年化收益: N/A")
            print(f"     组合最大回撤: {port_mdd:.2%}" if not np.isnan(port_mdd) else f"     组合最大回撤: N/A")
            print(f"     组合年化波动: {port_vol:.2%}" if not np.isnan(port_vol) else f"     组合年化波动: N/A")
            print(f"     组合夏普比率: {port_sharpe:.3f}" if not np.isnan(port_sharpe) else f"     组合夏普比率: N/A")

    # ---- 5. 组合健康度综合评估 ----
    print(f"\n  🏥 组合健康度评估:")
    issues = []
    warnings = []

    # 集中度检查
    if "规模风格" in df_final.columns:
        max_sp = df_final["规模风格"].value_counts().max() / len(df_final) * 100
        if max_sp > 70:
            issues.append(f"风格过度集中（单一风格>70%）")

    # 相关性检查
    if len(nav_dict) >= 2 and 'ret_df' in dir() and ret_df.shape[1] >= 2:
        avg_c = (ret_df.corr().values.sum() - ret_df.shape[1]) / (ret_df.shape[1] * (ret_df.shape[1] - 1))
        if avg_c > 0.75:
            issues.append(f"组合相关性过高（{avg_c:.2f}），分散化严重不足")
        elif avg_c > 0.6:
            warnings.append(f"组合相关性偏高（{avg_c:.2f}），建议增加低相关资产")

    # 卖出比例
    if len(sell_list := df_final[df_final["操作信号"].str.contains("卖出")]) > len(df_final) * 0.5:
        issues.append(f"超过50%持仓发出卖出信号，组合质量堪忧")

    # 经理稳定性
    if "团队稳定性" in df_final.columns:
        unstable = (df_final["团队稳定性"] == "🔴 频繁更换").sum()
        if unstable > len(df_final) * 0.3:
            warnings.append(f"多只基金经理团队不稳定")

    if issues:
        for i in issues:
            print(f"     🔴 {i}")
    if warnings:
        for w in warnings:
            print(f"     🟡 {w}")
    if not issues and not warnings:
        print(f"     ✅ 组合整体健康，分散化良好")


def load_holdings() -> pd.DataFrame:
    """加载用户持仓配置（只需填基金代码一列，成本和份额可选）"""
    if not os.path.exists(HOLDINGS_FILE):
        # 自动创建模板文件
        template = pd.DataFrame({"基金代码": ["", ""]})
        template.to_csv(HOLDINGS_FILE, index=False, encoding="utf-8-sig")
        print(f"📝 已创建持仓模板文件 {HOLDINGS_FILE}，请填写基金代码后重新运行")
        return pd.DataFrame()
    df = pd.read_csv(HOLDINGS_FILE, dtype={"基金代码": str})
    df = df.dropna(subset=["基金代码"])
    df = df[df["基金代码"].str.strip() != ""]
    return df

def get_latest_nav(fund_code: str) -> dict:
    """获取单只基金最新净值和名称（腾讯行情接口）"""
    url = f"http://qt.gtimg.cn/q=jj{fund_code}"
    try:
        resp = requests.get(url, timeout=10,
                          headers={"User-Agent": "Mozilla/5.0"})
        resp.encoding = "gbk"
        text = resp.text
        match = re.search(r'="(.+)"', text)
        if match:
            parts = match.group(1).split("~")
            if len(parts) >= 9:
                return {
                    "name": parts[1],
                    "nav": float(parts[5]) if parts[5] and parts[5] != "0.0000" else None,
                    "accum_nav": float(parts[6]) if parts[6] else None,
                    "chg_pct": float(parts[7]) if parts[7] else None,
                    "nav_date": parts[8] if parts[8] else None,
                }
    except Exception as e:
        print(f"  ⚠ 行情获取 {fund_code} 失败: {e}")
    return None

def analyze_holdings(force_refresh: bool = False):
    """
    持有基金分析：
    1. 读取 holdings.csv 获取用户持仓（基金代码、成本、份额）
    2. 获取实时净值，计算浮动盈亏
    3. 加载历史净值做精细指标分析（夏普、回撤等）
    4. 输出持仓体检报告
    """
    holdings = load_holdings()
    if holdings.empty:
        print("❌ 未找到持仓数据，请在 holdings.csv 中填写持有的基金代码")
        return pd.DataFrame()

    print(f"\n{'='*70}")
    print(f"📋 持仓分析：共 {len(holdings)} 只基金")
    print(f"{'='*70}")

    # ---- 第一步：获取实时行情（并行）----
    print("\n📡 获取实时行情...")
    quotes = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(get_latest_nav, row["基金代码"]): row["基金代码"]
            for _, row in holdings.iterrows()
        }
        for future in as_completed(futures):
            code = futures[future]
            try:
                res = future.result()
                if res:
                    quotes[code] = res
            except Exception as e:
                print(f"  ⚠ {code} 行情异常: {e}")

    # ---- 第二步：精细指标分析（复用缓存）----
    print(f"\n🔬 精细指标分析...")
    # 预加载多规模基准
    print("📈 加载多规模基准（沪深300/中证500/中证1000）...")
    load_all_benchmarks(force_refresh=False)

    # v5: 先加载基金列表以获取名称和类型，用于资产类别判定
    fund_info_map = {}
    try:
        all_funds_info = load_all_funds(force_refresh=False)
        if not all_funds_info.empty:
            for _, frow in all_funds_info.iterrows():
                code = str(frow["基金代码"])
                fund_info_map[code] = {
                    "name": str(frow.get("基金简称", "")),
                    "type": str(frow.get("基金类型", "")),
                }
    except Exception:
        pass

    results = []
    completed = 0
    total = len(holdings)

    t_start = time.time()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(
                analyze_fund,
                row["基金代码"],
                fund_info_map.get(row["基金代码"], {}).get("name", ""),
                fund_info_map.get(row["基金代码"], {}).get("type", ""),
                force_refresh,
            ): row
            for _, row in holdings.iterrows()
        }
        for future in as_completed(futures):
            row = futures[future]
            code = row["基金代码"]
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"  ⚠ {code} 分析异常: {e}")
            completed += 1
            if completed % 5 == 0 or completed == total or completed == 1:
                elapsed = time.time() - t_start
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"  进度: {completed}/{total} | 速率: {rate:.1f}只/秒 | 预计剩余: {eta:.0f}秒")

    if not results:
        print("❌ 没有成功分析的基金")
        return pd.DataFrame()

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values("综合评分", ascending=False).reset_index(drop=True)

    # ---- 同类排名百分位（v5：按资产类型分别计算） ----
    try:
        all_funds = load_all_funds(force_refresh=False)
        if not all_funds.empty:
            # 构建资产类型映射
            asset_map = {}
            if "资产类别" in df_result.columns:
                for _, r in df_result.iterrows():
                    asset_map[r["基金代码"]] = r.get("资产类别")
            for period in ["近1月", "近3月", "近6月", "近1年", "近2年", "近3年"]:
                if period in all_funds.columns:
                    all_vals = pd.to_numeric(all_funds[period], errors="coerce").dropna()
                    if len(all_vals) > 0:
                        col_name = f"{period}百分位"
                        df_result[col_name] = df_result["基金代码"].apply(
                            lambda code: _calc_percentile(code, period, all_funds, all_vals,
                                                          asset_type=asset_map.get(code))
                        )
            if "基金规模" in all_funds.columns:
                scale_map = dict(zip(all_funds["基金代码"], all_funds["基金规模"]))
                df_result["基金规模(亿)"] = df_result["基金代码"].map(scale_map)
    except Exception:
        pass

    # ---- 同类综合评分排名（v5：同类比较） ----
    if "资产类别" in df_result.columns:
        rank_list = []
        total_list = []
        for _, row in df_result.iterrows():
            asset = row["资产类别"]
            subset = df_result[df_result["资产类别"] == asset]
            rank = int(subset["综合评分"].rank(ascending=False, method="min").loc[row.name])
            rank_list.append(rank)
            total_list.append(len(subset))
        df_result["同类排名"] = [f"{r}/{t}" for r, t in zip(rank_list, total_list)]

    # ---- 补充基金经理 & 持仓集中度 ----
    print(f"\n👤 补充基金经理 & 持仓信息...")
    mgr_data = {}
    hold_data = {}
    for i, (_, row) in enumerate(df_result.iterrows()):
        code = row["基金代码"]
        if (i + 1) % 3 == 0 or i == 0:
            print(f"  进度: {i+1}/{len(df_result)}")
        mgr_data[code] = _scrape_manager_info(code)
        hold_data[code] = _scrape_holdings_concentration(code)
        time.sleep(0.3)
    df_result["基金经理"] = df_result["基金代码"].apply(
        lambda c: mgr_data.get(c, {}).get("基金经理", ""))
    df_result["任职天数"] = df_result["基金代码"].apply(
        lambda c: mgr_data.get(c, {}).get("任职天数", ""))
    df_result["任职回报"] = df_result["基金代码"].apply(
        lambda c: mgr_data.get(c, {}).get("任职回报", ""))
    df_result["前十大集中度"] = df_result["基金代码"].apply(
        lambda c: hold_data.get(c, {}).get("前十大集中度", ""))

    # ---- 合并持仓成本与盈亏 ----
    holdings_map = {}
    for _, row in holdings.iterrows():
        cost = float(row.get("持仓成本", 0) or 0) if "持仓成本" in row.index else 0
        shares = float(row.get("持有份额", 0) or 0) if "持有份额" in row.index else 0
        holdings_map[row["基金代码"]] = {"cost": cost, "shares": shares}

    pnl_list = []
    for _, row in df_result.iterrows():
        code = row["基金代码"]
        info = holdings_map.get(code, {})
        cost = info.get("cost", 0)
        shares = info.get("shares", 0)
        q = quotes.get(code, {})
        current_nav = q.get("nav") if q else None
        chg_pct = q.get("chg_pct") if q else None
        fund_name = q.get("name", row.get("基金名称", "")) if q else row.get("基金名称", "")

        # 计算盈亏（有成本才计算）
        if current_nav and cost > 0:
            pnl_pct = (current_nav - cost) / cost
            pnl_amt = (current_nav - cost) * shares if shares > 0 else None
        else:
            pnl_pct = None
            pnl_amt = None

        pnl_list.append({
            **row.to_dict(),
            "基金名称": fund_name or row.get("基金名称", ""),
            "持仓成本": cost if cost > 0 else None,
            "持有份额": shares if shares > 0 else None,
            "最新净值": current_nav,
            "当日涨跌": f"{chg_pct:.2f}%" if chg_pct is not None else None,
            "浮动盈亏%": f"{pnl_pct:.2%}" if pnl_pct is not None else None,
            "浮动盈亏额": f"¥{pnl_amt:,.2f}" if pnl_amt is not None else None,
        })

    df_final = pd.DataFrame(pnl_list)

    # ---- 输出持仓报告 ----
    buy_list = df_final[df_final["操作信号"].str.contains("买入")]
    sell_list = df_final[df_final["操作信号"].str.contains("卖出")]
    hold_list = df_final[df_final["操作信号"].str.contains("观望")]

    # 计算总盈亏
    total_pnl = 0
    for item in pnl_list:
        if item["浮动盈亏额"] and item["浮动盈亏额"] != "None":
            try:
                val = float(item["浮动盈亏额"].replace("¥", "").replace(",", ""))
                total_pnl += val
            except:
                pass

    print("\n" + "=" * 70)
    print("📊 持仓体检报告")
    print("=" * 70)
    print(f"  持有总数：{len(df_final)} 只")
    print(f"  🟢 建议持有/加仓：{len(buy_list)} 只")
    print(f"  🔴 建议卖出/减仓：{len(sell_list)} 只")
    print(f"  🟡 观望：{len(hold_list)} 只")
    if total_pnl != 0:
        pnl_sign = "📈" if total_pnl > 0 else "📉"
        print(f"  {pnl_sign} 总浮动盈亏：¥{total_pnl:,.2f}")

    # ---- v4 新增：组合层面分析 ----
    _analyze_portfolio(df_final, quotes, holdings, total_pnl)

    # 详细列表
    detail_cols = ["基金代码", "基金名称", "基金类型", "资产类别", "同类排名", "规模风格", "匹配基准",
                   "综合评分", "夏普比率", "最大回撤",
                   "年化收益", "Alpha(年化)", "信息比率", "月度胜率", "胜率趋势",
                   "连续跑赢(月)", "最大回撤修复天", "净值分位",
                   "行业周期匹配度", "资金流情绪", "经理经验等级", "团队稳定性",
                   "近1年百分位", "基金经理", "任职回报", "前十大集中度",
                   "基金规模(亿)", "浮动盈亏%", "浮动盈亏额", "操作信号"]
    # 过滤不存在的列
    detail_cols = [c for c in detail_cols if c in df_final.columns]

    if not buy_list.empty:
        print("\n🟢 【建议持有 / 可加仓】")
        print(buy_list[detail_cols].to_string(index=False))

    if not sell_list.empty:
        print("\n🔴 【建议卖出 / 减仓】")
        print(sell_list[detail_cols].to_string(index=False))

    if not hold_list.empty:
        print("\n🟡 【观望】")
        print(hold_list[detail_cols].to_string(index=False))

    # 保存完整结果
    output_file = "holdings_analysis.csv"
    df_final.to_csv(output_file, index=False, encoding="utf-8-sig")
    total_time = time.time() - t_start
    print(f"\n✅ 持仓分析已保存至 {output_file}（总耗时 {total_time:.0f}秒）")
    return df_final

# ============================================================
# 运行
# ============================================================
if __name__ == "__main__":
    import sys
    force = "--refresh" in sys.argv or "--force" in sys.argv

    if "--holdings" in sys.argv:
        if force:
            print("🔄 强制刷新模式：忽略所有缓存，重新拉取数据\n")
        analyze_holdings(force_refresh=force)
    else:
        if force:
            print("🔄 强制刷新模式：忽略所有缓存，重新拉取数据\n")
        run_screening(top_n=50, force_refresh=force)
