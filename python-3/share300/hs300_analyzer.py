#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪深300成分股综合分析系统
功能：自动扫描沪深300所有股票，基于9大技术指标筛选买入/卖出信号
数据源：腾讯财经 API（qt.gtimg.cn / web.ifzq.gtimg.cn）
"""

import os
import json
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
import sys
from typing import Dict, List, Tuple, Optional
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from common.logging_utils import get_logger

logger = get_logger(__name__)
warnings.filterwarnings('ignore')

# 通用磁盘缓存工具（跨包共享，位于 common/caching.py）
try:
    from common.caching import DiskCache
except ImportError:
    # 未部署 common 包时降级为空实现，不影响原有功能
    class DiskCache:  # type: ignore[no-redef]
        def __init__(self, *a, **k):
            self.ns_dir = ""

        def get_csv(self, *a, **k):
            return None

        def set_csv(self, *a, **k):
            return None

        def get_json(self, *a, **k):
            return None

        def set_json(self, *a, **k):
            return None

        def get_pickle(self, *a, **k):
            return None

        def set_pickle(self, *a, **k):
            return None

# ============================================================
# 缓存配置（按数据更新频率设定 TTL）
# ============================================================
# 各数据源的磁盘缓存实例（命名空间隔离）
_kline_cache = DiskCache("share300/kline", default_ttl="1d")     # 日K线，按日更新
_stock_list_cache = DiskCache("share300/stock_list", default_ttl="30d")  # 成分股列表，季度更新
_fundamental_cache = DiskCache("share300/fundamental", default_ttl="30d")  # 基本面，季度更新
_industry_cache = DiskCache("share300/industry", default_ttl="1d")        # 行业板块，按日更新


# ============================================================
# 腾讯财经 API 配置
# ============================================================
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
})

# 腾讯财经实时行情 API
TENCENT_API = "http://qt.gtimg.cn/q="

# 腾讯财经历史日K线 API（前复权）
TENCENT_KLINE_API = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def _to_tencent_code(code: str) -> str:
    """将通用代码转换为腾讯财经代码格式"""
    if code.startswith(("60", "68")):
        return f"sh{code}"
    return f"sz{code}"


# ============================================================
# 沪深300 成分股列表（最新，通过东方财富API动态获取）
# 数据来源: https://push2.eastmoney.com/api/qt/clist/get
# 注：代码运行时可通过 fetch_hs300_from_api() 函数动态刷新
# ============================================================
HS300_CODES = [
    ("000001", "平安银行"), ("000002", "万  科Ａ"), ("000063", "中兴通讯"),
    ("000100", "TCL科技"), ("000157", "中联重科"), ("000166", "申万宏源"),
    ("000301", "东方盛虹"), ("000333", "美的集团"), ("000338", "潍柴动力"),
    ("000408", "藏格矿业"), ("000425", "徐工机械"), ("000538", "云南白药"),
    ("000568", "泸州老窖"), ("000596", "古井贡酒"), ("000617", "中油资本"),
    ("000625", "长安汽车"), ("000630", "铜陵有色"), ("000651", "格力电器"),
    ("000657", "中钨高新"), ("000708", "中信特钢"), ("000725", "京东方Ａ"),
    ("000768", "中航西飞"), ("000776", "广发证券"), ("000792", "盐湖股份"),
    ("000807", "云铝股份"), ("000858", "五 粮 液"), ("000895", "双汇发展"),
    ("000938", "紫光股份"), ("000963", "华东医药"), ("000975", "山金国际"),
    ("000977", "浪潮信息"), ("000988", "华工科技"), ("000999", "华润三九"),
    ("001280", "中国铀业"), ("001391", "国货航"), ("001965", "招商公路"),
    ("001979", "招商蛇口"), ("002001", "新 和 成"), ("002027", "分众传媒"),
    ("002028", "思源电气"), ("002049", "紫光国微"), ("002050", "三花智控"),
    ("002074", "国轩高科"), ("002142", "宁波银行"), ("002179", "中航光电"),
    ("002202", "金风科技"), ("002230", "科大讯飞"), ("002236", "大华股份"),
    ("002241", "歌尔股份"), ("002304", "洋河股份"), ("002311", "海大集团"),
    ("002352", "顺丰控股"), ("002353", "杰瑞股份"), ("002371", "北方华创"),
    ("002384", "东山精密"), ("002415", "海康威视"), ("002422", "科伦药业"),
    ("002460", "赣锋锂业"), ("002463", "沪电股份"), ("002466", "天齐锂业"),
    ("002475", "立讯精密"), ("002493", "荣盛石化"), ("002532", "天山铝业"),
    ("002558", "巨人网络"), ("002594", "比亚迪"), ("002600", "领益智造"),
    ("002602", "世纪华通"), ("002625", "光启技术"), ("002648", "卫星化学"),
    ("002709", "天赐材料"), ("002714", "牧原股份"), ("002736", "国信证券"),
    ("002837", "英维克"), ("002916", "深南电路"), ("002920", "德赛西威"),
    ("002938", "鹏鼎控股"), ("003816", "中国广核"), ("300014", "亿纬锂能"),
    ("300015", "爱尔眼科"), ("300033", "同花顺"), ("300059", "东方财富"),
    ("300122", "智飞生物"), ("300124", "汇川技术"), ("300251", "光线传媒"),
    ("300274", "阳光电源"), ("300308", "中际旭创"), ("300316", "晶盛机电"),
    ("300394", "天孚通信"), ("300408", "三环集团"), ("300413", "芒果超媒"),
    ("300418", "昆仑万维"), ("300433", "蓝思科技"), ("300442", "润泽科技"),
    ("300450", "先导智能"), ("300476", "胜宏科技"), ("300498", "温氏股份"),
    ("300502", "新易盛"), ("300628", "亿联网络"), ("300661", "圣邦股份"),
    ("300750", "宁德时代"), ("300760", "迈瑞医疗"), ("300803", "指南针"),
    ("300832", "新产业"), ("300866", "安克创新"), ("300896", "爱美客"),
    ("300999", "金龙鱼"), ("301165", "锐捷网络"), ("301236", "软通动力"),
    ("301269", "华大九天"), ("301308", "江波龙"), ("302132", "中航成飞"),
    ("600000", "浦发银行"), ("600009", "上海机场"), ("600010", "包钢股份"),
    ("600011", "华能国际"), ("600015", "华夏银行"), ("600016", "民生银行"),
    ("600018", "上港集团"), ("600019", "宝钢股份"), ("600023", "浙能电力"),
    ("600025", "华能水电"), ("600026", "中远海能"), ("600027", "华电国际"),
    ("600028", "中国石化"), ("600029", "南方航空"), ("600030", "中信证券"),
    ("600031", "三一重工"), ("600036", "招商银行"), ("600039", "四川路桥"),
    ("600048", "保利发展"), ("600050", "中国联通"), ("600061", "国投资本"),
    ("600066", "宇通客车"), ("600085", "同仁堂"), ("600089", "特变电工"),
    ("600104", "上汽集团"), ("600111", "北方稀土"), ("600115", "中国东航"),
    ("600118", "中国卫星"), ("600150", "中国船舶"), ("600160", "巨化股份"),
    ("600176", "中国巨石"), ("600183", "生益科技"), ("600188", "兖矿能源"),
    ("600196", "复星医药"), ("600219", "南山铝业"), ("600221", "海航控股"),
    ("600233", "圆通速递"), ("600276", "恒瑞医药"), ("600309", "万华化学"),
    ("600346", "恒力石化"), ("600362", "江西铜业"), ("600372", "中航机载"),
    ("600406", "国电南瑞"), ("600415", "小商品城"), ("600426", "华鲁恒升"),
    ("600436", "片仔癀"), ("600438", "通威股份"), ("600460", "士兰微"),
    ("600482", "中国动力"), ("600489", "中金黄金"), ("600515", "海南机场"),
    ("600519", "贵州茅台"), ("600522", "中天科技"), ("600547", "山东黄金"),
    ("600549", "厦门钨业"), ("600570", "恒生电子"), ("600584", "长电科技"),
    ("600585", "海螺水泥"), ("600588", "用友网络"), ("600600", "青岛啤酒"),
    ("600660", "福耀玻璃"), ("600674", "川投能源"), ("600690", "海尔智家"),
    ("600741", "华域汽车"), ("600760", "中航沈飞"), ("600795", "国电电力"),
    ("600803", "新奥股份"), ("600809", "山西汾酒"), ("600845", "宝信软件"),
    ("600875", "东方电气"), ("600886", "国投电力"), ("600887", "伊利股份"),
    ("600893", "航发动力"), ("600900", "长江电力"), ("600905", "三峡能源"),
    ("600918", "中泰证券"), ("600919", "江苏银行"), ("600926", "杭州银行"),
    ("600930", "华电新能"), ("600938", "中国海油"), ("600941", "中国移动"),
    ("600958", "东方证券"), ("600989", "宝丰能源"), ("600999", "招商证券"),
    ("601006", "大秦铁路"), ("601009", "南京银行"), ("601012", "隆基绿能"),
    ("601018", "宁波港"), ("601021", "春秋航空"), ("601058", "赛轮轮胎"),
    ("601059", "信达证券"), ("601066", "中信建投"), ("601077", "渝农商行"),
    ("601088", "中国神华"), ("601100", "恒立液压"), ("601111", "中国国航"),
    ("601117", "中国化学"), ("601127", "赛力斯"), ("601136", "首创证券"),
    ("601138", "工业富联"), ("601166", "兴业银行"), ("601169", "北京银行"),
    ("601186", "中国铁建"), ("601211", "国泰海通"), ("601225", "陕西煤业"),
    ("601229", "上海银行"), ("601238", "广汽集团"), ("601288", "农业银行"),
    ("601318", "中国平安"), ("601319", "中国人保"), ("601328", "交通银行"),
    ("601336", "新华保险"), ("601360", "三六零"), ("601377", "兴业证券"),
    ("601390", "中国中铁"), ("601398", "工商银行"), ("601456", "国联民生"),
    ("601600", "中国铝业"), ("601601", "中国太保"), ("601607", "上海医药"),
    ("601618", "中国中冶"), ("601628", "中国人寿"), ("601633", "长城汽车"),
    ("601658", "邮储银行"), ("601668", "中国建筑"), ("601669", "中国电建"),
    ("601688", "华泰证券"), ("601689", "拓普集团"), ("601698", "中国卫通"),
    ("601727", "上海电气"), ("601728", "中国电信"), ("601766", "中国中车"),
    ("601788", "光大证券"), ("601800", "中国交建"), ("601816", "京沪高铁"),
    ("601818", "光大银行"), ("601825", "沪农商行"), ("601838", "成都银行"),
    ("601857", "中国石油"), ("601868", "中国能建"), ("601872", "招商轮船"),
    ("601877", "正泰电器"), ("601878", "浙商证券"), ("601881", "中国银河"),
    ("601888", "中国中免"), ("601898", "中煤能源"), ("601899", "紫金矿业"),
    ("601901", "方正证券"), ("601916", "浙商银行"), ("601919", "中远海控"),
    ("601939", "建设银行"), ("601985", "中国核电"), ("601988", "中国银行"),
    ("601995", "中金公司"), ("601998", "中信银行"), ("603019", "中科曙光"),
    ("603259", "药明康德"), ("603260", "合盛硅业"), ("603288", "海天味业"),
    ("603296", "华勤技术"), ("603369", "今世缘"), ("603392", "万泰生物"),
    ("603501", "豪威集团"), ("603799", "华友钴业"), ("603893", "瑞芯微"),
    ("603986", "兆易创新"), ("603993", "洛阳钼业"), ("605117", "德业股份"),
    ("605499", "东鹏饮料"), ("688008", "澜起科技"), ("688009", "中国通号"),
    ("688012", "中微公司"), ("688036", "传音控股"), ("688041", "海光信息"),
    ("688047", "龙芯中科"), ("688072", "拓荆科技"), ("688082", "盛美上海"),
    ("688111", "金山办公"), ("688126", "沪硅产业"), ("688183", "生益电子"),
    ("688223", "晶科能源"), ("688256", "寒武纪"), ("688271", "联影医疗"),
    ("688303", "大全能源"), ("688396", "华润微"), ("688472", "阿特斯"),
    ("688506", "百利天恒"), ("688521", "芯原股份"), ("688981", "中芯国际"),
]
import akshare as ak
import pandas as pd
from typing import Dict, Optional
from datetime import datetime

class FundamentalDataFetcher:
    """基本面数据获取器（支持批量缓存）"""

    def __init__(self, force_refresh: bool = False):
        self._fin_df: Optional[pd.DataFrame] = None  # 财务指标缓存
        self._spot_df: Optional[pd.DataFrame] = None  # 实时估值缓存
        self._industry_map: Optional[pd.DataFrame] = None  # 行业映射缓存
        self._load_data(force_refresh=force_refresh)

    @staticmethod
    def _latest_report_dates(now=None) -> list:
        """生成候选报告期（YYYYMMDD），从最近已结束的季度末开始逐个尝试。

        业绩报表(stock_yjbb_em)只接受季度末日期(如 20250331)，传空串会
        导致接口过滤条件变为 REPORTDATE='--' 返回空结果，进而触发
        'NoneType' object is not subscriptable。这里按季度回退生成有效日期。

        注意：仅生成已结束的季度末日期。若当前季度尚未结束（例如 8 月就
        不应请求 0930），会把日期推到上一季度末，避免请求未来报告期导致
        接口无数据而抛出 'NoneType' object is not subscriptable。
        """
        now = now or datetime.now()
        # 先确定最近一个“已结束”的季度末作为起点
        y, m = now.year, now.month
        quarter = (m - 1) // 3
        end_month = [3, 6, 9, 12][quarter]
        end_day = 31 if end_month in (3, 12) else 30
        cur_end = datetime(y, end_month, end_day)
        if cur_end >= now:
            # 当前季度尚未结束，改用上一季度末
            if quarter > 0:
                end_month = [3, 6, 9, 12][quarter - 1]
            else:
                end_month = 12
                y -= 1
            end_day = 31 if end_month in (3, 12) else 30

        dates = []
        seen = set()
        for _ in range(12):  # 最多回退 12 个季度
            d = f"{y}{end_month:02d}{end_day:02d}"
            if d not in seen:
                dates.append(d)
                seen.add(d)
            # 回退到上一个季度末
            end_month -= 3
            if end_month <= 0:
                end_month += 12
                y -= 1
            end_day = 31 if end_month in (3, 12) else 30
        return dates

    @staticmethod
    def _retry(fn, retries: int = 3, base_delay: float = 1.0, desc: str = ""):
        """带指数退避的重试封装，容忍临时性网络抖动（RemoteDisconnected 等）。"""
        for attempt in range(1, retries + 1):
            try:
                return fn()
            except Exception as e:
                if attempt == retries:
                    raise
                delay = base_delay * (2 ** (attempt - 1))
                print(f"  ↻ {desc or fn.__name__} 第{attempt}次失败({e})，{delay:.1f}s后重试...")
                time.sleep(delay)

    def _load_fin_df(self):
        """加载 A 股业绩报表（动态挑选最近可用的报告期）。"""
        last_err = None
        for report_date in self._latest_report_dates():
            try:
                df = self._retry(
                    lambda d=report_date: ak.stock_yjbb_em(date=d),
                    desc=f"业绩报表({report_date})",
                )
                if df is None or df.empty:
                    continue
                logger.info("业绩报表加载成功（报告期 %s，%d 行）", report_date, len(df))
                return df.drop_duplicates(subset=["股票代码"], keep="first")
            except Exception as e:
                last_err = e
        if last_err is not None:
            logger.warning("业绩报表加载失败: %s", last_err)
            print(f"⚠️ 业绩报表加载失败: {last_err}")
        return None

    def _load_spot_df(self):
        """加载 A 股实时行情（含 PE、PB、总市值等）。

        优先使用东方财富源（stock_zh_a_spot_em，含市盈率-动态/市净率列）；
        若该源因网络/反爬失败（如 RemoteDisconnected），自动回退到
        新浪源（stock_zh_a_spot），并把列名统一规范为下游所依赖的
        eastmoney 格式（代码 / 市盈率-动态 / 市净率），保证
        get_fundamental() 能正常读取，避免因单个数据源不可达导致全链路失败。
        """
        # 1) 东方财富源：列齐全，含 PE/PB
        try:
            df = self._retry(lambda: ak.stock_zh_a_spot_em(), desc="实时行情(东财)")
            if df is not None and not df.empty and "代码" in df.columns:
                logger.info("实时行情(东财)加载成功，%d 行", len(df))
                return df
        except Exception as e:
            logger.warning("实时行情(东财)加载失败: %s", e)
            print(f"⚠️ 实时行情(东财)加载失败: {e}")

        # 2) 新浪源回退：新浪字段不含 PE/PB，需统一列名并补空列
        try:
            print("↻ 尝试回退新浪数据源 stock_zh_a_spot()...")
            df = self._retry(lambda: ak.stock_zh_a_spot(), desc="实时行情(新浪)")
            if df is None or df.empty or "代码" not in df.columns:
                return None
            # 新浪代码带 sh/sz/bj 前缀，统一去掉以与下游（东财成分股 6 位代码）对齐
            df = df.copy()
            df["代码"] = df["代码"].astype(str).str.replace(
                r"^(sh|sz|bj)", "", regex=True
            )
            # 统一为下游依赖的列名；新浪无 PE/PB，置为 NaN（可空）
            for col in ("市盈率-动态", "市净率"):
                if col not in df.columns:
                    df[col] = np.nan
            return df
        except Exception as e:
            print(f"⚠️ 实时行情(新浪)加载失败: {e}")
            return None

    def _load_industry_map(self):
        """加载行业分类映射（代码 -> 行业名）。

        旧版 akshare 的 stock_industry_classify_sina() 已在新版本中移除；
        而业绩报表(stock_yjbb_em)本身就带有所处行业字段，
        因此直接从中提取 code -> industry 映射，最稳定可靠。
        """
        if self._fin_df is None:
            return None
        try:
            if "股票代码" not in self._fin_df.columns or "所处行业" not in self._fin_df.columns:
                return None
            sub = self._fin_df[["股票代码", "所处行业"]].dropna(subset=["所处行业"])
            sub.columns = ["code", "industry"]
            return sub.drop_duplicates(subset=["code"]).set_index("code")
        except Exception as e:
            print(f"⚠️ 行业分类加载失败: {e}")
            return None

    def _load_data(self, force_refresh: bool = False):
        """批量加载沪深300所需的基本面数据（每日调用一次即可）。

        每个数据源独立加载、独立容错，避免单点失败导致全部数据丢失。
        基本面数据（业绩报表 / 实时行情估值）更新频率为季度/日，因此
        使用 30 天 / 1 天的磁盘缓存，避免每次运行重复请求 akshare。
        """
        print("📊 正在加载基本面数据...")

        # 尝试从磁盘缓存读取（未过期）
        if not force_refresh:
            cached_fin = _fundamental_cache.get_csv("fin_df.csv", ttl="30d")
            cached_spot = _fundamental_cache.get_csv("spot_df.csv", ttl="1d")
            cached_ind = _fundamental_cache.get_csv("industry_map.csv", ttl="30d")
            if cached_fin is not None:
                self._fin_df = cached_fin
                logger.debug("基本面缓存命中 fin_df（%d 行）", len(cached_fin))
            if cached_spot is not None:
                self._spot_df = cached_spot
                logger.debug("基本面缓存命中 spot_df（%d 行）", len(cached_spot))
            if cached_ind is not None:
                self._industry_map = cached_ind
                logger.debug("基本面缓存命中 industry_map")

        # 缺失的数据源逐个加载（独立容错）
        if self._fin_df is None:
            logger.info("业绩报表数据缺失，开始加载...")
            self._fin_df = self._load_fin_df()
            if self._fin_df is not None:
                try:
                    _fundamental_cache.set_csv("fin_df.csv", self._fin_df)
                except Exception as e:
                    logger.warning("fin_df 写入缓存失败: %s", e)
        if self._spot_df is None:
            logger.info("实时行情数据缺失，开始加载...")
            self._spot_df = self._load_spot_df()
            if self._spot_df is not None:
                try:
                    _fundamental_cache.set_csv("spot_df.csv", self._spot_df)
                except Exception as e:
                    logger.warning("spot_df 写入缓存失败: %s", e)
        if self._industry_map is None:
            logger.info("行业映射数据缺失，开始加载...")
            self._industry_map = self._load_industry_map()
            if self._industry_map is not None and not getattr(self._industry_map, "empty", True):
                try:
                    # industry_map 可能以 code 为 index，存缓存前重置
                    _fundamental_cache.set_csv("industry_map.csv", self._industry_map.reset_index())
                except Exception as e:
                    logger.warning("industry_map 写入缓存失败: %s", e)
        logger.info("基本面数据加载完成：fin=%s spot=%s industry=%s",
                    "OK" if self._fin_df is not None else "FAIL",
                    "OK" if self._spot_df is not None else "FAIL",
                    "OK" if self._industry_map is not None else "FAIL")
        print("✅ 基本面数据加载完成")

    def get_industry_by_code(self, code: str) -> str:
        """按股票代码返回行业名称（兼容 set_index 后的 DataFrame）。"""
        if self._industry_map is None:
            return ""
        try:
            if "code" in self._industry_map.columns:
                rows = self._industry_map[self._industry_map["code"] == code]
                if not rows.empty:
                    return str(rows.iloc[0].get("industry", ""))
            elif self._industry_map.index.name == "code":
                if code in self._industry_map.index:
                    return str(self._industry_map.loc[code].get("industry", ""))
        except Exception:
            pass
        return ""
    
    def get_fundamental(self, code: str) -> Dict:
        """
        获取单只股票的基本面指标
        返回: {
            'roe': float,           # 净资产收益率(%)
            'revenue_growth': float, # 营收增长率(%)
            'profit_growth': float,  # 净利润增长率(%)
            'pe_ttm': float,        # 市盈率(TTM)
            'pb': float,            # 市净率
            'debt_ratio': float,    # 资产负债率(%)
            'gross_margin': float,  # 毛利率(%)
        }
        """
        result = {
            'roe': None, 'revenue_growth': None, 'profit_growth': None,
            'pe_ttm': None, 'pb': None, 'debt_ratio': None, 'gross_margin': None
        }
        
        # 从业绩报表提取
        if self._fin_df is not None:
            row = self._fin_df[self._fin_df["股票代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                result['roe'] = self._safe_float(r.get("净资产收益率"))
                result['revenue_growth'] = self._safe_float(r.get("营业总收入-同比增长"))
                result['profit_growth'] = self._safe_float(r.get("净利润-同比增长"))
                result['gross_margin'] = self._safe_float(r.get("销售毛利率"))
                result['debt_ratio'] = self._safe_float(r.get("资产负债率"))
        
        # 从实时行情提取估值
        if self._spot_df is not None:
            # spot_em 中代码格式为 "600519"
            row = self._spot_df[self._spot_df["代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                result['pe_ttm'] = self._safe_float(r.get("市盈率-动态"))
                result['pb'] = self._safe_float(r.get("市净率"))
        
        return result
    
    @staticmethod
    def _safe_float(val):
        try:
            return float(val) if pd.notna(val) and val != "-" else None
        except:
            return None

class IndustryDataFetcher:
    """行业景气度数据获取器"""
    
    def __init__(self, force_refresh: bool = False):
        self._industry_perf: Optional[pd.DataFrame] = None
        self._load_industry_data(force_refresh=force_refresh)
    
    def _load_industry_data(self, force_refresh: bool = False):
        """加载行业板块近期表现（含涨跌幅、成交额、主力净流入等）。

        优先使用同花顺源（stock_board_industry_summary_ths）。当前网络实测东财
        push2 接口（stock_board_industry_name_em）会被服务端主动断连
        （RemoteDisconnected），同花顺源更稳定、能正常返回含涨跌幅/净流入的数据；
        因此把同花顺设为首选，若其失败再回退到东财源，并把列名统一为下游
        get_industry_score 依赖的格式，避免行业景气度因子整体丢失。

        行业板块行情按日更新，使用 1 天磁盘缓存。
        """
        # 0) 尝试从磁盘缓存读取（未过期）
        if not force_refresh:
            cached = _industry_cache.get_csv("industry_perf.csv", ttl="1d")
            if cached is not None and not cached.empty:
                self._industry_perf = cached
                logger.debug("行业景气度缓存命中（%d 行）", len(cached))
                return

        # 1) 同花顺源（首选）：列名不同（板块/涨跌幅/净流入），统一为东财格式
        try:
            df = FundamentalDataFetcher._retry(
                lambda: ak.stock_board_industry_summary_ths(),
                desc="行业板块行情(同花顺)",
            )
            if df is None or df.empty:
                self._industry_perf = None
                return
            df = df.copy()
            df = df.rename(columns={"板块": "板块名称"})
            if "主力净流入-净额" not in df.columns and "净流入" in df.columns:
                df["主力净流入-净额"] = df["净流入"]
            self._industry_perf = df
            logger.info("行业景气度(同花顺)加载成功，%d 个行业", len(df))
            self._cache_industry_perf()
            return
        except Exception as e:
            logger.warning("行业板块行情(同花顺)加载失败: %s", e)
            print(f"⚠️ 行业板块行情(同花顺)加载失败: {e}")

        # 2) 东方财富源回退（列最全）
        try:
            print("↻ 尝试回退东方财富数据源 stock_board_industry_name_em()...")
            self._industry_perf = FundamentalDataFetcher._retry(
                lambda: ak.stock_board_industry_name_em(),
                desc="行业板块行情(东财)",
            )
            if self._industry_perf is not None and not self._industry_perf.empty:
                logger.info("行业景气度(东财回退)加载成功，%d 个行业", len(self._industry_perf))
                self._cache_industry_perf()
                return
        except Exception as e:
            logger.warning("行业板块行情(东财)加载失败: %s", e)
            print(f"⚠️ 行业板块行情(东财)加载失败: {e}")

        logger.warning("行业景气度数据加载失败，行业因子将置零")
        self._industry_perf = None

    def _cache_industry_perf(self):
        """将行业板块数据写入磁盘缓存。"""
        if self._industry_perf is None or getattr(self._industry_perf, "empty", True):
            return
        try:
            _industry_cache.set_csv("industry_perf.csv", self._industry_perf)
        except Exception:
            pass
    
    def get_industry_score(self, industry_name: str) -> Dict:
        """
        获取行业景气度评分
        返回: {'score': float(-1~1), 'change_pct': float, 'net_inflow': float}
        """
        if self._industry_perf is None or not industry_name:
            return {'score': 0, 'change_pct': 0, 'net_inflow': 0}
        
        # 模糊匹配行业名称
        matched = self._industry_perf[
            self._industry_perf['板块名称'].str.contains(industry_name[:4], na=False)
        ]
        
        if matched.empty:
            return {'score': 0, 'change_pct': 0, 'net_inflow': 0}
        
        row = matched.iloc[0]
        change = self._safe_float(row.get('涨跌幅', 0))
        # 将涨跌幅映射到 -1~1 的分数区间
        score = max(-1, min(1, change / 5))  # 5%涨跌幅视为满格
        return {
            'score': score,
            'change_pct': change,
            'net_inflow': self._safe_float(row.get('主力净流入-净额', 0))
        }
    
    @staticmethod
    def _safe_float(val):
        try:
            return float(val) if pd.notna(val) else 0
        except:
            return 0

class FundamentalScorer:
    """基本面评分器（将财务数据量化为 -1~1 的得分）"""
    
    @staticmethod
    def score(fund_dict: Dict) -> Dict:
        """
        输入基本面字典，输出各维度得分与综合基本面分
        返回: {'details': {}, 'total_score': float, 'quality_level': str}
        """
        scores = {}
        
        # 1. 盈利能力 (ROE)
        roe = fund_dict.get('roe')
        if roe is not None:
            if roe > 20: scores['ROE'] = (+1.0, f"ROE={roe:.1f}% 优秀")
            elif roe > 15: scores['ROE'] = (+0.6, f"ROE={roe:.1f}% 良好")
            elif roe > 8: scores['ROE'] = (+0.2, f"ROE={roe:.1f}% 一般")
            elif roe > 0: scores['ROE'] = (-0.2, f"ROE={roe:.1f}% 偏弱")
            else: scores['ROE'] = (-0.8, f"ROE={roe:.1f}% 亏损")
        else:
            scores['ROE'] = (0, "ROE缺失")
        
        # 2. 成长性 (净利润增速)
        pg = fund_dict.get('profit_growth')
        if pg is not None:
            if pg > 50: scores['Growth'] = (+1.0, f"净利增{pg:.1f}% 高成长")
            elif pg > 20: scores['Growth'] = (+0.6, f"净利增{pg:.1f}% 稳健")
            elif pg > 0: scores['Growth'] = (+0.2, f"净利增{pg:.1f}% 微增")
            elif pg > -20: scores['Growth'] = (-0.4, f"净利增{pg:.1f}% 下滑")
            else: scores['Growth'] = (-1.0, f"净利增{pg:.1f}% 大幅衰退")
        else:
            scores['Growth'] = (0, "增速缺失")
        
        # 3. 估值水平 (PE)
        pe = fund_dict.get('pe_ttm')
        if pe is not None and pe > 0:
            if pe < 15: scores['PE'] = (+0.8, f"PE={pe:.1f} 低估")
            elif pe < 25: scores['PE'] = (+0.4, f"PE={pe:.1f} 合理")
            elif pe < 50: scores['PE'] = (-0.2, f"PE={pe:.1f} 偏贵")
            else: scores['PE'] = (-0.8, f"PE={pe:.1f} 高估")
        else:
            scores['PE'] = (0, "PE缺失/亏损")
        
        # 4. 估值水平 (PB)
        pb = fund_dict.get('pb')
        if pb is not None and pb > 0:
            if pb < 1.5: scores['PB'] = (+0.6, f"PB={pb:.2f} 低估值")
            elif pb < 3: scores['PB'] = (+0.2, f"PB={pb:.2f} 合理")
            else: scores['PB'] = (-0.4, f"PB={pb:.2f} 偏高")
        else:
            scores['PB'] = (0, "PB缺失")
        
        # 5. 财务安全 (负债率)
        dr = fund_dict.get('debt_ratio')
        if dr is not None:
            if dr > 80: scores['Debt'] = (-0.6, f"负债率{dr:.1f}% 高风险")
            elif dr > 60: scores['Debt'] = (-0.2, f"负债率{dr:.1f}% 偏高")
            else: scores['Debt'] = (+0.2, f"负债率{dr:.1f}% 健康")
        else:
            scores['Debt'] = (0, "负债率缺失")
        
        # 加权综合
        weights = {'ROE': 1.5, 'Growth': 1.2, 'PE': 1.0, 'PB': 0.8, 'Debt': 0.5}
        total = sum(v[0] * weights.get(k, 1.0) for k, v in scores.items())
        total = max(-3, min(3, total))  # 限制范围
        
        return {
            'details': {k: v[1] for k, v in scores.items()},
            'total_score': total,
            'quality_level': '优质' if total >= 1.5 else '良好' if total >= 0.5 else '一般' if total >= -0.5 else '较差'
        }


# 动态获取最新沪深300成分股的函数（通过东方财富API）
def fetch_hs300_from_api(force_refresh: bool = False) -> list:
    """
    从东方财富API获取最新沪深300成分股列表（带磁盘缓存）。

    成分股名单每季度调整一次，因此使用 30 天的缓存 TTL，避免每次运行
    分析都重复请求东方财富接口。

    返回: [(code, name), ...]
    """
    cache_key = "hs300_stocks.json"
    # 1. 读缓存（未过期）
    if not force_refresh:
        cached = _stock_list_cache.get_json(cache_key)
        if cached:
            logger.debug("沪深300成分股列表缓存命中（%d 只）", len(cached))
            return [tuple(x) for x in cached]

    # 2. 拉取最新
    all_stocks = []
    for pn in range(1, 5):
        url = 'https://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'cb': '', 'fid': 'f3', 'po': '1', 'pz': '100', 'pn': str(pn),
            'np': '1', 'fltt': '2', 'invt': '2',
            'fs': 'b:BK0500+f:!50', 'fields': 'f12,f14'
        }
        try:
            resp = _session.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get('data') and data['data'].get('diff'):
                diff = data['data']['diff']
                for item in diff:
                    all_stocks.append((item['f12'], item['f14']))
                logger.debug("成分股第 %d 页拉取 %d 条（累计 %d）", pn, len(diff), len(all_stocks))
            else:
                logger.debug("成分股第 %d 页无数据，停止拉取", pn)
                break
        except Exception as e:
            logger.warning("成分股第 %d 页拉取失败: %s", pn, e)
            break
    all_stocks.sort(key=lambda x: x[0])
    logger.info("沪深300成分股API拉取完成，共 %d 只", len(all_stocks))

    # 3. 拉取成功且数据量合理时写入缓存
    if len(all_stocks) >= 280:
        _stock_list_cache.set_json(cache_key, [list(x) for x in all_stocks])
        logger.debug("沪深300成分股列表已写入缓存（%d 只）", len(all_stocks))
    return all_stocks


# ============================================================
# 技术指标计算模块
# ============================================================
class TechnicalIndicators:
    """技术指标计算器"""
    @staticmethod
    def calc_ma(df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        """计算移动平均线"""
        for p in periods:
            df[f'MA{p}'] = df['收盘'].rolling(window=p).mean()
        return df
    @staticmethod
    def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算MACD指标"""
        ema_fast = df['收盘'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['收盘'].ewm(span=slow, adjust=False).mean()
        df['DIF'] = ema_fast - ema_slow
        df['DEA'] = df['DIF'].ewm(span=signal, adjust=False).mean()
        df['MACD'] = 2 * (df['DIF'] - df['DEA'])
        return df
    @staticmethod
    def calc_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """计算KDJ指标"""
        low_n = df['最低'].rolling(window=n).min()
        high_n = df['最高'].rolling(window=n).max()
        rsv = (df['收盘'] - low_n) / (high_n - low_n) * 100
        rsv = rsv.fillna(50)
        k = pd.Series(index=df.index, dtype=float)
        d = pd.Series(index=df.index, dtype=float)
        k.iloc[0] = 50
        d.iloc[0] = 50
        for i in range(1, len(df)):
            k.iloc[i] = (m1 - 1) / m1 * k.iloc[i - 1] + 1 / m1 * rsv.iloc[i]
            d.iloc[i] = (m2 - 1) / m2 * d.iloc[i - 1] + 1 / m2 * k.iloc[i]
        df['K'] = k
        df['D'] = d
        df['J'] = 3 * k - 2 * d
        return df
    @staticmethod
    def calc_rsi(df: pd.DataFrame, periods: List[int] = [6, 12, 24]) -> pd.DataFrame:
        """计算RSI指标"""
        delta = df['收盘'].diff()
        for p in periods:
            gain = delta.where(delta > 0, 0).rolling(window=p).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=p).mean()
            rs = gain / loss
            df[f'RSI{p}'] = 100 - 100 / (1 + rs)
        return df
    @staticmethod
    def calc_volume_ma(df: pd.DataFrame, periods: List[int] = [5, 20]) -> pd.DataFrame:
        """计算成交量均线"""
        for p in periods:
            df[f'VOL_MA{p}'] = df['成交量'].rolling(window=p).mean()
        return df

    @staticmethod
    def calc_boll(df: pd.DataFrame, period: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
        """计算布林带（BOLL）"""
        df['BOLL_MID'] = df['收盘'].rolling(window=period).mean()
        std = df['收盘'].rolling(window=period).std()
        df['BOLL_UP'] = df['BOLL_MID'] + std_mult * std
        df['BOLL_DN'] = df['BOLL_MID'] - std_mult * std
        # 带宽 = (上轨-下轨)/中轨，用于判断变盘
        band_range = df['BOLL_UP'] - df['BOLL_DN']
        df['BOLL_WIDTH'] = (band_range / df['BOLL_MID']).replace([np.inf, -np.inf], np.nan).fillna(0) * 100
        # 价格在布林带中的位置 (0~1, 0=下轨, 1=上轨)
        df['BOLL_POS'] = ((df['收盘'] - df['BOLL_DN']) / band_range.replace(0, np.nan)).fillna(0.5)
        return df


# ============================================================
# 信号分析模块
# ============================================================
class SignalAnalyzer:
    """买卖信号分析器"""
    def analyze(self, df: pd.DataFrame) -> Dict:
        """综合分析，返回各指标信号和综合评分"""
        if df is None or len(df) < 30:
            return self._empty_result()
        signals = {}
        scores = {}
        # 1. MA均线信号
        signals['MA'], scores['MA'] = self._ma_signal(df)
        # 2. MACD信号
        signals['MACD'], scores['MACD'] = self._macd_signal(df)
        # 3. KDJ信号
        signals['KDJ'], scores['KDJ'] = self._kdj_signal(df)
        # 4. RSI信号
        signals['RSI'], scores['RSI'] = self._rsi_signal(df)
        # 5. 成交量信号
        signals['VOL'], scores['VOL'] = self._volume_signal(df)
        # 6. 布林带信号
        signals['BOLL'], scores['BOLL'] = self._boll_signal(df)
        # 7. 支撑/阻力位分析
        signals['SR'], scores['SR'] = self._support_resistance_signal(df)
        # 8. K线组合形态
        signals['CANDLE'], scores['CANDLE'] = self._candlestick_signal(df)
        # 9. 价格形态识别（W底/M头/三角形）
        signals['PATTERN'], scores['PATTERN'] = self._pattern_signal(df)
        # 综合评分（加权 — MACD/背离 和 形态识别 权重最高）
        weights = {
            'MA': 1.0, 'MACD': 1.5, 'KDJ': 1.0, 'RSI': 1.0,
            'VOL': 0.5, 'BOLL': 0.8, 'SR': 0.5,
            'CANDLE': 0.8, 'PATTERN': 1.2,
        }
        total_score = sum(scores[k] * weights[k] for k in scores)
        # 综合建议（阈值校准：新增 CANDLE + PATTERN 后分数跨度更大）
        if total_score >= 4.5:
            advice = '强烈买入'
            level = 5
        elif total_score >= 2.5:
            advice = '建议买入'
            level = 4
        elif total_score <= -4.5:
            advice = '强烈卖出'
            level = 1
        elif total_score <= -2.5:
            advice = '建议卖出'
            level = 2
        else:
            advice = '观望'
            level = 3
        latest = df.iloc[-1]
        return {
            'signals': signals,
            'scores': scores,
            'total_score': total_score,
            'advice': advice,
            'level': level,
            'price': latest['收盘'],
            'change_pct': self._calc_change_pct(df),
            'rsi': latest.get('RSI6', 50),
            'kdj_j': latest.get('J', 50),
        }
    def _calc_change_pct(self, df: pd.DataFrame) -> float:
        """计算最近涨跌幅"""
        if len(df) < 2:
            return 0
        return (df.iloc[-1]['收盘'] - df.iloc[-2]['收盘']) / df.iloc[-2]['收盘'] * 100
    def _ma_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """MA均线信号（含金叉/死叉确认 + MA60趋势过滤）"""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        # 趋势判断：MA60 方向（用最近5根K线的 MA60 斜率）
        if len(df) >= 65 and 'MA60' in df.columns:
            ma60_recent = df['MA60'].dropna().tail(5)
            if len(ma60_recent) >= 5:
                ma60_trend_up = ma60_recent.iloc[-1] > ma60_recent.iloc[0]
            else:
                ma60_trend_up = True
        else:
            ma60_trend_up = latest['收盘'] > latest.get('MA60', latest['MA20'])

        # 金叉/死叉 + 确认：需要连续2天满足
        prev2 = df.iloc[-3] if len(df) >= 3 else prev
        golden_cross = (prev2['MA5'] <= prev2['MA10'] and
                        prev['MA5'] <= prev['MA10'] and
                        latest['MA5'] > latest['MA10'])
        death_cross = (prev2['MA5'] >= prev2['MA10'] and
                       prev['MA5'] >= prev['MA10'] and
                       latest['MA5'] < latest['MA10'])

        if golden_cross and ma60_trend_up:
            return ('MA5/10金叉(↑趋势)', +1.2)
        if golden_cross:
            return ('MA5/10金叉(↓趋势)', +0.5)
        if death_cross and not ma60_trend_up:
            return ('MA5/10死叉(↓趋势)', -1.2)
        if death_cross:
            return ('MA5/10死叉(↑趋势)', -0.5)

        if latest['MA5'] > latest['MA10'] > latest['MA20']:
            if ma60_trend_up:
                return ('多头排列(↑趋势)', +0.8)
            return ('多头排列(↓趋势)', +0.3)
        if latest['MA5'] < latest['MA10'] < latest['MA20']:
            if not ma60_trend_up:
                return ('空头排列(↓趋势)', -0.8)
            return ('空头排列(↑趋势)', -0.3)

        if latest['收盘'] > latest['MA20']:
            return ('站上MA20', +0.3)
        else:
            return ('跌破MA20', -0.3)
    def _macd_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """MACD信号（含顶底背离检测 — 峰峰/谷谷对比）"""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        # 金叉/死叉信号
        cross_signal = None
        cross_score = 0.0
        if prev['DIF'] < prev['DEA'] and latest['DIF'] > latest['DEA']:
            if latest['DIF'] < 0:
                cross_signal, cross_score = ('零下金叉', +1.0)
            else:
                cross_signal, cross_score = ('金叉', +0.8)
        elif prev['DIF'] > prev['DEA'] and latest['DIF'] < latest['DEA']:
            if latest['DIF'] > 0:
                cross_signal, cross_score = ('零上死叉', -1.0)
            else:
                cross_signal, cross_score = ('死叉', -0.8)

        # 背离检测：在最近 40 根 K 线中找两个局部峰/谷，对比价格与 DIF
        if len(df) >= 40:
            recent = df.tail(40)
            prices = recent['收盘'].values
            difs = recent['DIF'].values
            n = len(recent)

            # --- 顶背离：找最近两个局部峰（价格高点），价格更高但 DIF 更低 ---
            peaks = []  # (index_in_recent, price, dif)
            for i in range(2, n - 2):
                if prices[i] > prices[i - 1] and prices[i] > prices[i - 2] and \
                   prices[i] > prices[i + 1] and prices[i] > prices[i + 2]:
                    peaks.append((i, prices[i], difs[i]))
            if len(peaks) >= 2:
                # 最近两个峰
                p1, p2 = peaks[-2], peaks[-1]
                # 价格更高但 DIF 更低 → 顶背离
                if p2[1] > p1[1] and p2[2] < p1[2]:
                    return ('顶背离⚠️', -1.5)

            # --- 底背离：找最近两个局部谷（价格低点），价格更低但 DIF 更高 ---
            troughs = []
            for i in range(2, n - 2):
                if prices[i] < prices[i - 1] and prices[i] < prices[i - 2] and \
                   prices[i] < prices[i + 1] and prices[i] < prices[i + 2]:
                    troughs.append((i, prices[i], difs[i]))
            if len(troughs) >= 2:
                t1, t2 = troughs[-2], troughs[-1]
                # 价格更低但 DIF 更高 → 底背离
                if t2[1] < t1[1] and t2[2] > t1[2]:
                    return ('底背离🔥', +1.5)

        if cross_signal:
            return (cross_signal, cross_score)

        if latest['MACD'] > prev['MACD'] > 0:
            return ('红柱放大', +0.4)
        if latest['MACD'] < prev['MACD'] < 0:
            return ('绿柱放大', -0.4)
        return ('震荡', 0)
    def _kdj_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """KDJ信号（调整后的超买超卖阈值）"""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        # 超买：K>80 且 D>70（比原来的 J>100 更敏感）
        if latest['K'] > 80 and latest['D'] > 70:
            if latest['J'] > 100:
                return ('严重超买', -1.0)
            return ('超买区', -0.6)
        # 超卖：K<20 且 D<30
        if latest['K'] < 20 and latest['D'] < 30:
            if latest['J'] < 0:
                return ('严重超卖', +1.0)
            return ('超卖区', +0.6)

        if prev['K'] < prev['D'] and latest['K'] > latest['D']:
            if latest['K'] < 30:
                return ('低位金叉', +1.0)
            return ('金叉', +0.5)
        if prev['K'] > prev['D'] and latest['K'] < latest['D']:
            if latest['K'] > 70:
                return ('高位死叉', -1.0)
            return ('死叉', -0.5)
        return ('中性', 0)
    def _rsi_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """RSI信号"""
        latest = df.iloc[-1]
        rsi = latest['RSI6']
        if pd.isna(rsi):
            return ('数据不足', 0)
        if rsi > 80:
            return (f'RSI={rsi:.1f}严重超买', -1.0)
        if rsi > 70:
            return (f'RSI={rsi:.1f}超买', -0.6)
        if rsi < 20:
            return (f'RSI={rsi:.1f}严重超卖', +1.0)
        if rsi < 30:
            return (f'RSI={rsi:.1f}超卖', +0.6)
        if 40 <= rsi <= 60:
            return (f'RSI={rsi:.1f}中性', 0)
        if rsi > 60:
            return (f'RSI={rsi:.1f}偏强', +0.3)
        return (f'RSI={rsi:.1f}偏弱', -0.3)
    def _volume_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """成交量信号（含量价背离 + 缩量涨跌分析）"""
        latest = df.iloc[-1]
        if pd.isna(latest.get('VOL_MA5')) or pd.isna(latest.get('VOL_MA20')):
            return ('数据不足', 0)
        vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 1
        price_up = latest['收盘'] > df.iloc[-2]['收盘']
        price_change = abs(latest['收盘'] - df.iloc[-2]['收盘']) / df.iloc[-2]['收盘']

        # --- 量价背离检测：近5天价格趋势 vs 量能趋势 ---
        if len(df) >= 10:
            price_5d_ago = df.iloc[-6]['收盘']
            vol_5d_ago = df.iloc[-6]['成交量']
            price_trend_5d = (latest['收盘'] - price_5d_ago) / price_5d_ago
            vol_trend_5d = (latest['成交量'] - vol_5d_ago) / vol_5d_ago if vol_5d_ago > 0 else 0
            # 价涨量缩 → 上涨动能不足，顶部分信号
            if price_trend_5d > 0.03 and vol_trend_5d < -0.2:
                return (f'量价背离(价涨量缩)', -1.2)
            # 价跌量缩 → 抛压减轻，可能见底
            if price_trend_5d < -0.03 and vol_trend_5d < -0.2:
                return (f'价跌量缩(抛压减轻)', +0.8)
            # 价跌量增 → 恐慌抛售
            if price_trend_5d < -0.03 and vol_trend_5d > 0.3:
                return (f'价跌量增(恐慌抛售)', -1.0)

        # --- 单日量价关系 ---
        if vol_ratio > 2.0 and price_up:
            return (f'放量上涨({vol_ratio:.1f}倍)', +1.0)
        if vol_ratio > 2.0 and not price_up:
            return (f'放量下跌({vol_ratio:.1f}倍)', -1.0)
        # 缩量上涨（涨幅>0.5%）→ 上涨乏力
        if vol_ratio < 0.6 and price_up and price_change > 0.005:
            return (f'缩量上涨(动能不足)', -0.5)
        # 缩量下跌（跌幅>0.5%）→ 抛压减轻
        if vol_ratio < 0.6 and not price_up and price_change > 0.005:
            return (f'缩量下跌(抛压轻)', +0.4)
        if vol_ratio < 0.5:
            return (f'极度缩量({vol_ratio:.1f}倍)', 0)
        if vol_ratio > 1.5 and price_up:
            return (f'温和放量({vol_ratio:.1f}倍)', +0.5)
        return (f'量能平稳({vol_ratio:.1f}倍)', 0)

    def _boll_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """布林带信号"""
        latest = df.iloc[-1]
        if pd.isna(latest.get('BOLL_UP')) or pd.isna(latest.get('BOLL_DN')):
            return ('数据不足', 0)
        price = latest['收盘']
        up = latest['BOLL_UP']
        dn = latest['BOLL_DN']
        mid = latest['BOLL_MID']
        pos = latest.get('BOLL_POS', 0.5)
        width = latest.get('BOLL_WIDTH', 0)

        # 价格触及/突破轨道
        if price >= up:
            return ('突破上轨(超买)', -0.8)
        if price <= dn:
            return ('跌破下轨(超卖)', +0.8)
        if pos > 0.8:
            return ('接近上轨', -0.4)
        if pos < 0.2:
            return ('接近下轨', +0.4)

        # 带宽收窄 → 变盘前兆
        if not pd.isna(width) and width < 5:
            # 结合价格相对位置判断方向概率
            if pos > 0.6:
                return ('带宽收窄(高位)', -0.3)
            if pos < 0.4:
                return ('带宽收窄(低位)', +0.3)
            return ('带宽收窄', 0)

        return ('中轨附近', 0)

    def _candlestick_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """K线组合形态识别（经典反转形态）"""
        if len(df) < 3:
            return ('数据不足', 0)
        l0, l1, l2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]

        o0, c0, h0, lo0 = l0['开盘'], l0['收盘'], l0['最高'], l0['最低']
        o1, c1, h1, lo1 = l1['开盘'], l1['收盘'], l1['最高'], l1['最低']
        o2, c2, h2, lo2 = l2['开盘'], l2['收盘'], l2['最高'], l2['最低']

        body0 = abs(c0 - o0)        # 实体大小
        body1 = abs(c1 - o1)
        body2 = abs(c2 - o2)
        avg_body_10 = df['收盘'].diff().abs().rolling(10).mean().iloc[-1]
        if pd.isna(avg_body_10) or avg_body_10 == 0:
            avg_body_10 = body0

        is_bull0 = c0 > o0  # 阳线
        is_bear0 = c0 < o0  # 阴线
        is_bull1 = c1 > o1  # 昨阳线
        is_bear1 = c1 < o1  # 昨阴线

        # 判断是否为小实体（十字星类）
        is_small0 = body0 < avg_body_10 * 0.4
        is_small1 = body1 < avg_body_10 * 0.4

        # 判断下影线/上影线长度
        lower_shadow0 = min(o0, c0) - lo0
        upper_shadow0 = h0 - max(o0, c0)

        # 1) 锤子线（底部反转）：阳线 + 长下影线 ≥ 实体2倍 + 上影线极小 + 出现在下跌后
        if is_bull0 and lower_shadow0 >= body0 * 2 and upper_shadow0 < body0 * 0.5 and body0 > 0:
            if len(df) >= 5 and df.iloc[-1]['收盘'] < df.iloc[-5]['收盘']:
                return ('锤子线(底部反转)', +1.0)

        # 2) 上吊线（顶部反转）：长上影线 + 下影线极小 + 出现在上涨后
        if upper_shadow0 >= body0 * 2 and lower_shadow0 < body0 * 0.5 and body0 > 0:
            if len(df) >= 5 and df.iloc[-1]['收盘'] > df.iloc[-5]['收盘']:
                return ('上吊线(顶部反转)', -1.0)

        # 3) 吞没形态：要求昨实体 ≥ 平均实体的 0.4 倍（排除十字星误判）
        body1_valid = body1 >= avg_body_10 * 0.4
        # 阳包阴：昨阴线有明确实体，今阳线且实体完全包住昨实体
        if is_bull0 and not is_bull1 and body1_valid:
            if c0 > max(o1, c1) and o0 < min(o1, c1):
                return ('阳包阴(看涨吞没)', +1.2)
        # 阴包阳：昨阳线有明确实体，今阴线且实体完全包住昨实体
        if is_bear0 and not is_bear1 and body1_valid:
            if c0 < min(o1, c1) and o0 > max(o1, c1):
                return ('阴包阳(看跌吞没)', -1.2)

        # 4) 十字星（变盘信号）：实体极小 + 上下影线差不多
        if is_small0 and lower_shadow0 > body0 and upper_shadow0 > body0:
            if len(df) >= 5 and df.iloc[-1]['收盘'] > df.iloc[-5]['收盘']:
                return ('高位十字星(变盘)', -0.5)
            if len(df) >= 5 and df.iloc[-1]['收盘'] < df.iloc[-5]['收盘']:
                return ('低位十字星(变盘)', +0.5)
            return ('十字星', 0)

        # 5) 早晨之星（底部三K线）：阴线 → 小实体(跳空低开) → 阳线(跳空高开)
        if not is_bull0 and is_small1 and c2 > o2:  # l2阳线, l1小实体, l0阴线 顺序颠倒
            pass  # 早晨之星需要更严格判断
        # 简化版：三连阴后出现阳线 + 放量
        if len(df) >= 4:
            three_bear = all(df.iloc[-i]['收盘'] < df.iloc[-i]['开盘'] for i in [2, 3, 4])
            if three_bear and is_bull0 and body0 > avg_body_10:
                return ('三连阴后放量阳', +0.8)

        # 6) 黄昏之星（顶部三K线）：阳线 → 小实体(跳空高开) → 阴线(跳空低开)
        if len(df) >= 4:
            three_bull = all(df.iloc[-i]['收盘'] > df.iloc[-i]['开盘'] for i in [2, 3, 4])
            if three_bull and not is_bull0 and body0 > avg_body_10:
                return ('三连阳后放量阴', -0.8)

        # 7) 跳空缺口
        if o0 > h1 * 1.01:  # 向上跳空 >1%
            return ('向上跳空缺口', +0.6)
        if o0 < lo1 * 0.99:  # 向下跳空 >1%
            return ('向下跳空缺口', -0.6)

        return ('无明确形态', 0)

    def _pattern_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """价格形态识别：W底（双底）/ M头（双顶）"""
        if len(df) < 60:
            return ('数据不足', 0)

        prices = df['收盘'].values
        highs = df['最高'].values
        lows = df['最低'].values
        n = len(prices)

        # ========== W底（双底）检测 ==========
        # 在最近60根K线中找两个局部低点
        troughs = []  # (index, low_price)
        search_start = max(3, n - 60)
        for i in range(search_start, n - 3):
            if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and lows[i] < lows[i - 3] and \
               lows[i] < lows[i + 1] and lows[i] < lows[i + 2] and lows[i] < lows[i + 3]:
                troughs.append((i, lows[i]))

        if len(troughs) >= 2:
            t1, t2 = troughs[-2], troughs[-1]
            # 两个低点间隔至少 5 天
            if t2[0] - t1[0] >= 5:
                # 两底价格接近（差距 < 3%）
                if abs(t2[1] - t1[1]) / t1[1] < 0.03:
                    # 颈线：两底之间的最高点
                    neck_high = max(highs[t1[0]:t2[0] + 1])
                    # 当前价格突破颈线 → W底确认
                    if prices[-1] > neck_high:
                        return ('W底突破颈线', +1.8)
                    # 当前价格在颈线附近（< 3%）→ 潜在突破
                    if (neck_high - prices[-1]) / prices[-1] < 0.03:
                        return ('W底(待突破颈线)', +1.0)
                    # 回踩颈线不破
                    if abs(prices[-1] - neck_high) / neck_high < 0.02:
                        return ('W底(回踩颈线)', +0.6)

        # ========== M头（双顶）检测 ==========
        peaks = []
        for i in range(search_start, n - 3):
            if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and highs[i] > highs[i - 3] and \
               highs[i] > highs[i + 1] and highs[i] > highs[i + 2] and highs[i] > highs[i + 3]:
                peaks.append((i, highs[i]))

        if len(peaks) >= 2:
            p1, p2 = peaks[-2], peaks[-1]
            if p2[0] - p1[0] >= 5:
                if abs(p2[1] - p1[1]) / p1[1] < 0.03:
                    # 颈线：两顶之间的最低点
                    neck_low = min(lows[p1[0]:p2[0] + 1])
                    if prices[-1] < neck_low:
                        return ('M头跌破颈线', -1.8)
                    if (prices[-1] - neck_low) / prices[-1] < 0.03:
                        return ('M头(待破颈线)', -1.0)
                    if abs(prices[-1] - neck_low) / neck_low < 0.02:
                        return ('M头(反抽颈线)', -0.6)

        # ========== 三角形整理检测 ==========
        # 最近20根K线，分前后两段对比
        recent20 = df.tail(20)
        if len(recent20) >= 20:
            first10 = recent20.iloc[:10]
            last10 = recent20.iloc[10:]
            h1 = first10['最高'].max()
            h2 = last10['最高'].max()
            l1 = first10['最低'].min()
            l2 = last10['最低'].min()
            hl_ratio = (h1 - l1) / l1 if l1 > 0 else 1

            # 高点持平(±1.5%) + 低点抬升 → 上升三角形（看涨）
            if abs(h2 - h1) / h1 < 0.015 and l2 > l1 * 1.005 and hl_ratio < 0.15:
                return ('上升三角形(看涨)', +0.6)
            # 低点持平(±1.5%) + 高点降低 → 下降三角形（看跌）
            if abs(l2 - l1) / l1 < 0.015 and h2 < h1 * 0.995 and hl_ratio < 0.15:
                return ('下降三角形(看跌)', -0.6)
            # 高点降低 + 低点抬高 → 收敛三角形
            if h2 < h1 and l2 > l1:
                if hl_ratio < 0.08:  # 波动空间 < 8%，即将突破
                    if prices[-1] > recent20['收盘'].mean():
                        return ('对称三角形(待上破)', +0.4)
                    else:
                        return ('对称三角形(待下破)', -0.4)
                return ('收敛三角形整理', 0)

        return ('无明显形态', 0)

    def _support_resistance_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        """支撑/阻力位分析（基于近期高低点 + MA60/MA120）"""
        latest = df.iloc[-1]
        price = latest['收盘']

        # 最近 60 根 K 线的最高/最低点作为阻力/支撑
        recent60 = df.tail(60)
        resist_high = recent60['最高'].max()
        support_low = recent60['最低'].min()

        # 距离阻力位和支撑位的百分比
        dist_to_resist = (resist_high - price) / price * 100
        dist_to_support = (price - support_low) / price * 100

        # MA60 支撑/阻力
        ma60 = latest.get('MA60', None)
        ma20 = latest.get('MA20', None)

        score = 0.0
        parts = []

        # 接近强阻力位（价格在 60 日高点 3% 以内）
        if dist_to_resist < 3:
            parts.append(f'接近阻力({resist_high:.2f})')
            score -= 0.8
        elif dist_to_resist < 6:
            parts.append(f'距阻力{dist_to_resist:.1f}%')
            score -= 0.3

        # 接近强支撑位（价格在 60 日低点 3% 以内）
        if dist_to_support < 3:
            parts.append(f'接近支撑({support_low:.2f})')
            score += 0.8
        elif dist_to_support < 6:
            parts.append(f'距支撑{dist_to_support:.1f}%')
            score += 0.3

        # MA60/MA20 作为动态支撑/阻力
        if ma60 is not None and not pd.isna(ma60):
            if price > ma60:
                ma60_dist = (price - ma60) / price * 100
                if ma60_dist < 3:
                    parts.append('MA60支撑')
                    score += 0.5
            else:
                ma60_dist = (ma60 - price) / price * 100
                if ma60_dist < 3:
                    parts.append('MA60阻力')
                    score -= 0.5

        if ma20 is not None and not pd.isna(ma20):
            if price > ma20:
                if (price - ma20) / price * 100 < 3:
                    parts.append('MA20支撑')
                    score += 0.3
            else:
                if (ma20 - price) / price * 100 < 3:
                    parts.append('MA20阻力')
                    score -= 0.3

        if not parts:
            return ('无明确支撑/阻力', 0)
        return ('; '.join(parts), score)
    def _empty_result(self):
        return {
            'signals': {},
            'scores': {},
            'total_score': 0,
            'advice': '数据不足',
            'level': 0,
            'price': 0,
            'change_pct': 0,
            'rsi': 50,
            'kdj_j': 50,
        }


# ============================================================
# 腾讯财经数据获取模块
# ============================================================
class TencentDataFetcher:
    """腾讯财经数据获取器"""
    
    @staticmethod
    def _parse_kline(klines: List) -> List[Dict]:
        """解析K线数据列表为字典列表"""
        records = []
        for line in klines:
            if not isinstance(line, list) or len(line) < 6:
                continue
            try:
                records.append({
                    '日期': line[0],
                    '开盘': float(line[1]),
                    '收盘': float(line[2]),
                    '最高': float(line[3]),
                    '最低': float(line[4]),
                    '成交量': float(line[5]),
                })
            except (ValueError, TypeError):
                continue
        return records
    
    @staticmethod
    def _fetch_kline_sina(code: str, days: int = 120) -> Optional[pd.DataFrame]:
        """新浪财经历史日K线（腾讯源回退，不复权）。

        返回 DataFrame，列名与腾讯源一致：日期, 开盘, 收盘, 最高, 最低, 成交量
        """
        tc_code = _to_tencent_code(code)
        url = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
        params = {
            "symbol": tc_code,
            "scale": 240,          # 240 分钟 => 日线
            "ma": "no",
            "datalen": days,
        }
        try:
            resp = _session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            if not resp.text or not resp.text.strip():
                raise ValueError("新浪K线API返回空响应")
            raw = resp.text.strip()
            if raw.startswith("(") and raw.endswith(")"):
                raw = raw[1:-1]
            data = json.loads(raw)
            if not isinstance(data, list):
                return None

            records = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                try:
                    records.append({
                        '日期': str(row['day']),
                        '开盘': float(row['open']),
                        '收盘': float(row['close']),
                        '最高': float(row['high']),
                        '最低': float(row['low']),
                        '成交量': float(row.get('volume', 0)),
                    })
                except (ValueError, TypeError, KeyError):
                    continue
            if not records:
                return None
            logger.info("%s 新浪K线回退拉取 %d 条", code, len(records))
            return pd.DataFrame(records)
        except Exception as e:
            logger.debug("新浪K线拉取失败 %s: %s", code, e)
            return None

    @staticmethod
    def fetch_kline(code: str, days: int = 120, force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """
        获取历史日K线数据（腾讯财经API，优先前复权，失败回退新浪）
        API: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600031,day,,,120,qfq
        返回 DataFrame，列名：日期, 开盘, 收盘, 最高, 最低, 成交量
        注意：部分新股/科创板股票没有前复权数据（qfqday），此时回退到不复权数据（day）

        带磁盘缓存：日K线按交易日更新，使用 1 天 TTL，避免每次分析重复请求。
        """
        cache_key = f"{code}_{days}.csv"
        # 1. 读缓存（未过期）
        if not force_refresh:
            cached = _kline_cache.get_csv(cache_key, ttl="1d")
            if cached is not None and not cached.empty:
                logger.debug("K线缓存命中 %s（%d 行）", code, len(cached))
                return cached

        # 2. 请求 API
        df = None
        try:
            tc_code = _to_tencent_code(code)
            # 优先请求前复权数据
            param = f"{tc_code},day,,,{days},qfq"
            resp = _session.get(TENCENT_KLINE_API, params={'param': param}, timeout=10)
            data = resp.json()

            if data.get('code') == 0 and data.get('data'):
                stock_data = data['data'].get(tc_code)
                if not stock_data:
                    return None

                # 优先使用前复权数据，没有则回退到不复权数据
                klines = stock_data.get('qfqday') or stock_data.get('day', [])
                if not klines:
                    return None

                records = TencentDataFetcher._parse_kline(klines)
                if records:
                    df = pd.DataFrame(records)
                    logger.debug("K线拉取成功 %s（%d 条记录）", code, len(records))
        except Exception as e:
            logger.debug("K线拉取失败 %s: %s", code, e)

        # 3. 拉取成功则写入缓存
        if df is not None and not df.empty:
            try:
                _kline_cache.set_csv(cache_key, df)
            except Exception as e:
                logger.warning("K线写入缓存失败 %s: %s", code, e)
            return df

        # 4. 腾讯失败时回退新浪源（避免腾讯临时故障/限流导致拿不到数据）
        logger.info("%s 腾讯K线拉取失败，回退新浪源", code)
        sina_df = TencentDataFetcher._fetch_kline_sina(code, days)
        if sina_df is not None and not sina_df.empty:
            try:
                _kline_cache.set_csv(cache_key, sina_df)
            except Exception as e:
                logger.warning("K线写入缓存失败 %s: %s", code, e)
            return sina_df

        # 5. 全部数据源失败时回退旧缓存（即使过期也返回，保证可用性）
        if not force_refresh:
            stale = _kline_cache.get_csv(cache_key, allow_stale=True)
            if stale is not None and not stale.empty:
                logger.debug("K线回退旧缓存 %s（%d 行）", code, len(stale))
                return stale
        logger.warning("K线数据获取失败，无可用数据 %s", code)
        return None


# ============================================================
# 沪深300分析主程序
# ============================================================
class HS300Analyzer:
    """沪深300成分股分析器"""
    def __init__(self, max_workers: int = 10, force_refresh: bool = False):
        self.indicators = TechnicalIndicators()
        self.analyzer = SignalAnalyzer()
        self.fetcher = TencentDataFetcher()
        self.force_refresh = force_refresh

        self.fund_fetcher = FundamentalDataFetcher(force_refresh=force_refresh)
        self.ind_fetcher = IndustryDataFetcher(force_refresh=force_refresh)
        self.fund_scorer = FundamentalScorer()

        self.results = []
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._completed = 0
        self._total = 0
        logger.info("HS300Analyzer 初始化完成：max_workers=%s force_refresh=%s", max_workers, force_refresh)
    
    def get_hs300_stocks(self) -> List[Tuple[str, str]]:
        """获取沪深300成分股列表（优先从API动态获取，带缓存）"""
        try:
            stocks = fetch_hs300_from_api(force_refresh=self.force_refresh)
            if stocks and len(stocks) >= 280:
                logger.info("沪深300成分股列表（API动态获取，共 %d 只）", len(stocks))
                print(f"📋 沪深300成分股列表（API动态获取，共 {len(stocks)} 只）\n")
                return stocks
        except Exception:
            logger.warning("沪深300成分股API获取失败，使用内置列表")
            pass
        logger.info("沪深300成分股列表（使用内置列表，共 %d 只）", len(HS300_CODES))
        print(f"📋 沪深300成分股列表（使用内置列表，共 {len(HS300_CODES)} 只）\n")
        return HS300_CODES
    
    def _analyze_one(self, code: str, name: str) -> Optional[Dict]:
        """分析单只股票（线程安全）"""
        try:
            df = self.fetcher.fetch_kline(code, days=120, force_refresh=self.force_refresh)
            if df is None or len(df) < 30:
                logger.debug("%s(%s) 日K线数据不足(%s)，跳过", name, code, "无数据" if df is None else f"{len(df)}行")
                return None
            logger.debug("%s(%s) 获取K线 %d 行，开始技术指标计算", name, code, len(df))
            
            df = self.indicators.calc_ma(df)
            df = self.indicators.calc_macd(df)
            df = self.indicators.calc_kdj(df)
            df = self.indicators.calc_rsi(df)
            df = self.indicators.calc_volume_ma(df)
            df = self.indicators.calc_boll(df)
            
            result = self.analyzer.analyze(df)
            result['code'] = code
            result['name'] = name
            logger.debug("%s(%s) 技术分析完成，评分 %.2f", name, code, result.get('total_score', 0))
            return result
        except Exception as e:
            logger.warning("%s(%s) 技术分析异常: %s", name, code, e)
            return None
    



    def analyze_stock(self, code: str, name: str) -> Optional[Dict]:
        """分析单只股票（技术 + 基本面 + 行业）"""
        # 1. 技术分析（原有逻辑）
        result = self._analyze_one(code, name)
        if result is None:
            with self._lock:
                self._completed += 1
            logger.debug("%s(%s) 技术面无有效数据，跳过", name, code)
            return None
        
        # 2. 基本面评分（新增）
        fund_dict = self.fund_fetcher.get_fundamental(code)
        fund_score = self.fund_scorer.score(fund_dict)
        result['fundamental'] = fund_score
        result['fundamental_score'] = fund_score['total_score']
        logger.debug("%s(%s) 基本面评分 %.2f", name, code, fund_score['total_score'])
        
        # 3. 行业景气度（新增）
        # 获取行业名称
        industry_name = self.fund_fetcher.get_industry_by_code(code)
        if industry_name:
            ind_data = self.ind_fetcher.get_industry_score(industry_name)
            result['industry_name'] = industry_name
            result['industry_score'] = ind_data['score']
            result['industry_change'] = ind_data['change_pct']
            logger.debug("%s(%s) 行业[%s]景气度评分 %.2f", name, code, industry_name, ind_data['score'])
        else:
            result['industry_name'] = ""
            result['industry_score'] = 0
            result['industry_change'] = 0
            logger.debug("%s(%s) 未获取到行业信息", name, code)
        
        # 4. 三维度加权融合（核心逻辑）
        tech_score = result['total_score']      # 技术面评分
        fund_score_val = result['fundamental_score']  # 基本面评分
        ind_score = result['industry_score'] * 2      # 行业评分放大到相近量纲
        
        # 权重：技术面 50% + 基本面 30% + 行业 20%
        composite = tech_score * 0.5 + fund_score_val * 0.3 + ind_score * 0.2
        result['composite_score'] = composite
        
        # 更新建议等级（综合评分阈值）
        if composite >= 4.0:
            result['advice'] = '强烈买入'; result['level'] = 5
        elif composite >= 2.0:
            result['advice'] = '建议买入'; result['level'] = 4
        elif composite <= -4.0:
            result['advice'] = '强烈卖出'; result['level'] = 1
        elif composite <= -2.0:
            result['advice'] = '建议卖出'; result['level'] = 2
        else:
            result['advice'] = '观望'; result['level'] = 3
        
        logger.debug("%s(%s) 综合评分 %.2f（技术 %.2f / 基本面 %.2f / 行业 %.2f），建议: %s",
                     name, code, composite, tech_score, fund_score_val, ind_score, result['advice'])
        
        # 进度更新（原有逻辑）
        with self._lock:
            self._completed += 1
            progress = self._completed / self._total * 100
            sys.stdout.write(f"\r进度: {progress:.1f}% ({self._completed}/{self._total}) - 刚完成: {name}({code})    ")
            sys.stdout.flush()
        
        return result

    
    def run_analysis(self, top_n: int = 20):
        """运行完整分析（多线程并发）"""
        stocks = self.get_hs300_stocks()
        if not stocks:
            logger.warning("无沪深300成分股数据，分析中止")
            return

        self._total = len(stocks)
        self._completed = 0
        logger.info("开始分析 %d 只股票，并发线程数 %d", self._total, self.max_workers)
        print(f"🔍 开始分析 {self._total} 只股票，并发线程数: {self.max_workers}\n")
        
        start_time = time.time()
        
        # 多线程并发分析
        failed = 0
        last_progress = -1
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.analyze_stock, code, name): (code, name)
                for code, name in stocks
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    self.results.append(result)
                else:
                    failed += 1
                # 每完成 10% 输出一次进度日志
                progress = int(self._completed / self._total * 100 // 10)
                if progress != last_progress:
                    last_progress = progress
                    logger.info("并发分析进度：%d%%（已分析 %d/%d，成功 %d，失败 %d）",
                                progress * 10, self._completed, self._total, len(self.results), failed)
            # 结束时输出最终进度日志
            logger.info("并发分析进度：成功 %d / 失败 %d / 总计 %d", len(self.results), failed, self._total)
        
        elapsed = time.time() - start_time
        logger.info("沪深300分析完成，有效结果 %d 条，失败 %d 条，耗时 %.1f 秒", len(self.results), failed, elapsed)
        print(f"\n\n✅ 分析完成！耗时: {elapsed:.1f} 秒\n")
        
        # 生成报告
        self.generate_report(top_n)
    def generate_report(self, top_n: int = 20):
        """生成分析报告"""
        if not self.results:
            logger.warning("无有效分析结果，无法生成报告")
            print("❌ 没有有效的分析结果")
            return
        # 转换为DataFrame并排序
        df = pd.DataFrame(self.results)
        df = df.sort_values('total_score', ascending=False)
        logger.info("生成报告：有效股票 %d 只，买入 %d 只 / 卖出 %d 只 / 观望 %d 只",
                    len(df), len(df[df['level'] >= 4]), len(df[df['level'] <= 2]), len(df[df['level'] == 3]))
        # 分类
        buy_stocks = df[df['level'] >= 4].head(top_n)
        sell_stocks = df[df['level'] <= 2].sort_values('total_score', ascending=True).head(top_n)
        watch_stocks = df[df['level'] == 3]
        # 输出报告
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("=" * 100)
        print(f"📊 沪深300成分股技术分析报告")
        print(f"生成时间: {now}")
        print("=" * 100)
        # 统计信息
        print(f"\n📈 市场概况:")
        print(f"  分析股票数: {len(df)}")
        print(f"  买入信号: {len(df[df['level'] >= 4])} 只")
        print(f"  卖出信号: {len(df[df['level'] <= 2])} 只")
        print(f"  观望信号: {len(df[df['level'] == 3])} 只")
        # 买入建议
        if not buy_stocks.empty:
            print(f"\n{'='*100}")
            print(f"🟢 建议买入的股票（Top {min(top_n, len(buy_stocks))}）")
            print("=" * 100)
            print(f"{'代码':<8}{'名称':<12}{'现价':>10}{'涨跌幅':>8}{'评分':>8}{'建议':<12}{'主要信号'}")
            print("-" * 100)
            for _, row in buy_stocks.iterrows():
                signals_str = ', '.join([f"{k}:{v}" for k, v in row['signals'].items() if v != '震荡' and v != '中性'])
                change_str = f"{row['change_pct']:+.2f}%"
                print(f"{row['code']:<8}{row['name']:<12}{row['price']:>10.2f}{change_str:>8}{row['total_score']:>+8.2f}{row['advice']:<12}{signals_str[:40]}")
        # 卖出建议
        if not sell_stocks.empty:
            print(f"\n{'='*100}")
            print(f"🔴 建议卖出的股票（Top {min(top_n, len(sell_stocks))}）")
            print("=" * 100)
            print(f"{'代码':<8}{'名称':<12}{'现价':>10}{'涨跌幅':>8}{'评分':>8}{'建议':<12}{'主要信号'}")
            print("-" * 100)
            for _, row in sell_stocks.iterrows():
                signals_str = ', '.join([f"{k}:{v}" for k, v in row['signals'].items() if v != '震荡' and v != '中性'])
                change_str = f"{row['change_pct']:+.2f}%"
                print(f"{row['code']:<8}{row['name']:<12}{row['price']:>10.2f}{change_str:>8}{row['total_score']:>+8.2f}{row['advice']:<12}{signals_str[:40]}")
        # 保存结果到CSV
        output_file = f"hs300_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        logger.info("分析结果已保存到 %s（%d 行）", output_file, len(df))
        print(f"\n💾 完整分析结果已保存到: {output_file}")
        # 风险提示
        print(f"\n{'='*100}")
        print("⚠️  重要风险提示:")
        print("  1. 本分析仅基于技术指标，不构成投资建议")
        print("  2. 技术指标存在滞后性，无法预测突发消息面影响")
        print("  3. 建议结合基本面、消息面、资金面综合判断")
        print("  4. 严格执行仓位管理和止损纪律")
        print("  5. 股市有风险，投资需谨慎")
        print("=" * 100)


# ============================================================
# 入口
# ============================================================
def main():
    print("\n" + "=" * 100)
    print("🚀 沪深300成分股综合分析系统")
    print("=" * 100)
    print("\n本程序将自动分析沪深300所有成分股，基于9大技术指标筛选买入/卖出信号")
    print("技术指标：MA均线、MACD、KDJ、RSI、成交量、布林带、支撑/阻力位、K线形态、价格形态")
    print("数据源：腾讯财经 API（qt.gtimg.cn）\n")
    
    # 并发线程数，可通过命令行参数指定
    max_workers = 15
    if len(sys.argv) > 1:
        try:
            max_workers = int(sys.argv[1])
        except ValueError:
            pass
    
    analyzer = HS300Analyzer(max_workers=max_workers)
    top_n = 20
    analyzer.run_analysis(top_n=top_n)


if __name__ == "__main__":
    main()
