#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪深300综合分析系统（技术+深度基本面版）
财务数据来源：东方财富公开API（纯requests，无需akshare）
估值/市值来源：腾讯财经API
"""

import pandas as pd
import numpy as np
import requests
from datetime import datetime
import time
import sys
import re
import threading
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://data.eastmoney.com/",
})

TENCENT_API = "http://qt.gtimg.cn/q="
TENCENT_KLINE_API = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def _to_tencent_code(code: str) -> str:
    if code.startswith(("60", "68")):
        return f"sh{code}"
    return f"sz{code}"


# ============================================================
# 沪深300 成分股列表
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


# ============================================================
# 技术指标（原逻辑，精简保留）
# ============================================================
class TechnicalIndicators:
    @staticmethod
    def calc_ma(df, periods=(5, 10, 20, 60)):
        for p in periods:
            df[f'MA{p}'] = df['收盘'].rolling(window=p).mean()
        return df
    @staticmethod
    def calc_macd(df):
        ema_fast = df['收盘'].ewm(span=12, adjust=False).mean()
        ema_slow = df['收盘'].ewm(span=26, adjust=False).mean()
        df['DIF'] = ema_fast - ema_slow
        df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = 2 * (df['DIF'] - df['DEA'])
        return df
    @staticmethod
    def calc_kdj(df, n=9):
        low_n = df['最低'].rolling(window=n).min()
        high_n = df['最高'].rolling(window=n).max()
        rsv = (df['收盘'] - low_n) / (high_n - low_n) * 100
        rsv = rsv.fillna(50)
        k = pd.Series(50.0, index=df.index)
        d = pd.Series(50.0, index=df.index)
        for i in range(1, len(df)):
            k.iloc[i] = 2.0/3 * k.iloc[i-1] + 1.0/3 * rsv.iloc[i]
            d.iloc[i] = 2.0/3 * d.iloc[i-1] + 1.0/3 * k.iloc[i]
        df['K'] = k; df['D'] = d; df['J'] = 3*k - 2*d
        return df
    @staticmethod
    def calc_rsi(df, periods=(6, 12, 24)):
        delta = df['收盘'].diff()
        for p in periods:
            gain = delta.where(delta > 0, 0).rolling(window=p).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=p).mean()
            df[f'RSI{p}'] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
        return df
    @staticmethod
    def calc_volume_ma(df, periods=(5, 20)):
        for p in periods:
            df[f'VOL_MA{p}'] = df['成交量'].rolling(window=p).mean()
        return df
    @staticmethod
    def calc_boll(df, period=20):
        df['BOLL_MID'] = df['收盘'].rolling(window=period).mean()
        std = df['收盘'].rolling(window=period).std()
        df['BOLL_UP'] = df['BOLL_MID'] + 2 * std
        df['BOLL_DN'] = df['BOLL_MID'] - 2 * std
        return df


# ============================================================
# 信号分析器（精简版，保留核心逻辑）
# ============================================================
class SignalAnalyzer:
    def analyze(self, df):
        if df is None or len(df) < 30:
            return self._empty_result()
        latest = df.iloc[-1]; prev = df.iloc[-2]
        signals = {}; scores = {}
        # MA
        if latest['MA5'] > latest['MA10'] > latest['MA20']:
            signals['MA'] = '多头排列'; scores['MA'] = +0.8
        elif latest['MA5'] < latest['MA10'] < latest['MA20']:
            signals['MA'] = '空头排列'; scores['MA'] = -0.8
        else:
            signals['MA'] = '均线纠缠'; scores['MA'] = 0
        # MACD
        if prev['DIF'] < prev['DEA'] and latest['DIF'] > latest['DEA']:
            signals['MACD'] = '金叉'; scores['MACD'] = +1.0
        elif prev['DIF'] > prev['DEA'] and latest['DIF'] < latest['DEA']:
            signals['MACD'] = '死叉'; scores['MACD'] = -1.0
        else:
            signals['MACD'] = '震荡'; scores['MACD'] = 0
        # KDJ
        if latest['K'] < 20 and latest['D'] < 30:
            signals['KDJ'] = '超卖区'; scores['KDJ'] = +0.6
        elif latest['K'] > 80 and latest['D'] > 70:
            signals['KDJ'] = '超买区'; scores['KDJ'] = -0.6
        else:
            signals['KDJ'] = '中性'; scores['KDJ'] = 0
        # RSI
        rsi = latest.get('RSI6', 50)
        if rsi > 70: signals['RSI'] = f'超买({rsi:.0f})'; scores['RSI'] = -0.6
        elif rsi < 30: signals['RSI'] = f'超卖({rsi:.0f})'; scores['RSI'] = +0.6
        else: signals['RSI'] = f'中性({rsi:.0f})'; scores['RSI'] = 0
        # VOL
        vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest.get('VOL_MA5', 0) > 0 else 1
        if vol_ratio > 2.0 and latest['收盘'] > prev['收盘']:
            signals['VOL'] = f'放量上涨({vol_ratio:.1f}倍)'; scores['VOL'] = +0.8
        else:
            signals['VOL'] = '量能平稳'; scores['VOL'] = 0
        # BOLL
        if latest['收盘'] >= latest['BOLL_UP']: signals['BOLL'] = '突破上轨'; scores['BOLL'] = -0.5
        elif latest['收盘'] <= latest['BOLL_DN']: signals['BOLL'] = '跌破下轨'; scores['BOLL'] = +0.5
        else: signals['BOLL'] = '中轨附近'; scores['BOLL'] = 0
        total_score = sum(scores[k] for k in scores)
        if total_score >= 3.0: advice, level = '强烈买入', 5
        elif total_score >= 1.5: advice, level = '建议买入', 4
        elif total_score <= -3.0: advice, level = '强烈卖出', 1
        elif total_score <= -1.5: advice, level = '建议卖出', 2
        else: advice, level = '观望', 3
        return {
            'signals': signals, 'scores': scores, 'total_score': total_score,
            'advice': advice, 'level': level, 'price': latest['收盘'],
            'change_pct': (latest['收盘']-prev['收盘'])/prev['收盘']*100 if len(df)>1 else 0,
        }
    def _empty_result(self):
        return {'signals': {}, 'scores': {}, 'total_score': 0, 'advice': '数据不足', 'level': 0,
                'price': 0, 'change_pct': 0}


# ============================================================
# 腾讯K线获取
# ============================================================
class TencentDataFetcher:
    @staticmethod
    def fetch_kline(code, days=120):
        try:
            tc_code = _to_tencent_code(code)
            param = f"{tc_code},day,,,{days},qfq"
            resp = _session.get(TENCENT_KLINE_API, params={'param': param}, timeout=10)
            data = resp.json()
            if data.get('code') == 0 and data.get('data'):
                stock_data = data['data'].get(tc_code)
                if not stock_data: return None
                klines = stock_data.get('qfqday') or stock_data.get('day', [])
                if not klines: return None
                records = []
                for line in klines:
                    if isinstance(line, list) and len(line) >= 6:
                        records.append({'日期': line[0], '开盘': float(line[1]), '收盘': float(line[2]),
                                        '最高': float(line[3]), '最低': float(line[4]), '成交量': float(line[5])})
                return pd.DataFrame(records) if records else None
        except Exception:
            pass
        return None


# ============================================================
# 腾讯实时估值获取（PE/PB/市值/52周高低点）
# ============================================================
class TencentFundamentalFetcher:
    @staticmethod
    def fetch(codes: List[str]) -> Dict[str, Dict]:
        results = {}
        for i in range(0, len(codes), 60):
            batch = codes[i:i+60]
            tc_codes = ",".join([_to_tencent_code(c) for c in batch])
            url = f"{TENCENT_API}{tc_codes}"
            try:
                resp = _session.get(url, timeout=15)
                text = resp.text
                for line in text.strip().split(';'):
                    if '="' not in line:
                        continue
                    header, values = line.split('="', 1)
                    values = values.rstrip('"')
                    m = re.search(r'v_(sh|sz)([\d]+)', header)
                    if not m:
                        continue
                    code = m.group(2)
                    data = values.split('~')
                    if len(data) < 54:
                        continue
                    try:
                        pe = float(data[39]) if data[39] not in ('', '-', '--') else None
                        pb = float(data[46]) if data[46] not in ('', '-', '--') else None
                        total_mv = float(data[44]) if data[44] not in ('', '-', '--') else None
                        high_52w = float(data[52]) if data[52] not in ('', '-', '--') else None
                        low_52w = float(data[53]) if data[53] not in ('', '-', '--') else None
                        results[code] = {'pe': pe, 'pb': pb, 'total_mv': total_mv, 'high_52w': high_52w, 'low_52w': low_52w}
                    except (ValueError, IndexError):
                        continue
            except Exception:
                pass
        return results


# ============================================================
# 东方财富财务数据获取（纯requests，无需akshare）
# ============================================================
class EastmoneyDataFetcher:
    """通过东方财富公开API获取ROE、净利润增速、负债率、现金流/利润比"""
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://data.eastmoney.com/",
        })
    def fetch_all(self, codes: List[str]) -> Dict[str, Dict]:
        """批量获取财务指标，返回 {code: {roe, profit_growth, debt_ratio, cash_profit_ratio}}"""
        results = {}
        # 东方财富主要财务指标接口（沪深A股）
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            "sortColumns": "UPDATE_DATE,SECURITY_CODE",
            "sortTypes": "-1,-1",
            "pageSize": "500",
            "pageNumber": "1",
            "reportName": "RPT_FCI_PERFORMANCEE",
            "columns": "SECURITY_CODE,ROE,NETPROFIT_GROWTHRATE,DEBT_ASSET_RATIO,OPERATE_CASHFLOW_NETPROFIT",
            "source": "WEB",
            "client": "WEB"
        }
        try:
            resp = self._session.get(url, params=params, timeout=20)
            data = resp.json()
            if data.get("result") and data["result"].get("data"):
                for item in data["result"]["data"]:
                    code = str(item.get("SECURITY_CODE", "")).zfill(6)
                    if code not in codes:
                        continue
                    results[code] = {
                        "roe": self._to_float(item.get("ROE")),
                        "profit_growth": self._to_float(item.get("NETPROFIT_GROWTHRATE")),
                        "debt_ratio": self._to_float(item.get("DEBT_ASSET_RATIO")),
                        "cash_profit_ratio": self._to_float(item.get("OPERATE_CASHFLOW_NETPROFIT")),
                    }
                print(f"✅ 东方财富财务指标获取完成，成功 {len(results)} 只")
            else:
                print("⚠️ 东方财富接口返回为空")
        except Exception as e:
            print(f"⚠️ 东方财富接口请求失败: {e}")
        return results
    @staticmethod
    def _to_float(val):
        try:
            if val is None or str(val) in ("", "-", "--", "None"):
                return None
            return float(val)
        except (ValueError, TypeError):
            return None


# ============================================================
# 基本面评分器（深化版）
# ============================================================
class FundamentalScorer:
    @staticmethod
    def score(fund: Dict, price: float) -> Dict:
        pe = fund.get('pe'); pb = fund.get('pb')
        total_mv = fund.get('total_mv'); high_52w = fund.get('high_52w'); low_52w = fund.get('low_52w')
        roe = fund.get('roe'); profit_growth = fund.get('profit_growth')
        debt_ratio = fund.get('debt_ratio'); cash_profit_ratio = fund.get('cash_profit_ratio')
        details = {}; score_val = 0.0
        # 1. PE
        if pe and pe > 0:
            if pe < 10: s, d = +0.8, f"PE={pe:.1f} 极低"
            elif pe < 20: s, d = +0.5, f"PE={pe:.1f} 低估值"
            elif pe < 30: s, d = +0.2, f"PE={pe:.1f} 合理"
            elif pe < 50: s, d = -0.3, f"PE={pe:.1f} 偏高"
            else: s, d = -0.8, f"PE={pe:.1f} 高估值"
            score_val += s; details['PE'] = d
        elif pe and pe <= 0:
            score_val += -1.0; details['PE'] = "PE<=0 亏损"
        else:
            details['PE'] = "PE缺失"
        # 2. PB
        if pb and pb > 0:
            if pb < 1.0: s, d = +0.6, f"PB={pb:.2f} 破净"
            elif pb < 1.5: s, d = +0.4, f"PB={pb:.2f} 低"
            elif pb < 3.0: s, d = +0.1, f"PB={pb:.2f} 合理"
            else: s, d = -0.4, f"PB={pb:.2f} 高"
            score_val += s; details['PB'] = d
        else:
            details['PB'] = "PB缺失"
        # 3. ROE（权重最高）
        if roe is not None:
            if roe > 20: s, d = +1.2, f"ROE={roe:.1f}% 优秀"
            elif roe > 15: s, d = +0.9, f"ROE={roe:.1f}% 良好"
            elif roe > 10: s, d = +0.4, f"ROE={roe:.1f}% 合格"
            elif roe > 5: s, d = +0.1, f"ROE={roe:.1f}% 偏弱"
            else: s, d = -0.8, f"ROE={roe:.1f}% 差"
            score_val += s * 1.5; details['ROE'] = d
        else:
            details['ROE'] = "ROE缺失"
        # 4. 成长性
        if profit_growth is not None:
            if profit_growth > 50: s, d = +1.0, f"净利增{profit_growth:.1f}% 高成长"
            elif profit_growth > 20: s, d = +0.6, f"净利增{profit_growth:.1f}% 稳健"
            elif profit_growth > 0: s, d = +0.2, f"净利增{profit_growth:.1f}% 微增"
            elif profit_growth > -20: s, d = -0.5, f"净利增{profit_growth:.1f}% 下滑"
            else: s, d = -1.2, f"净利增{profit_growth:.1f}% 衰退"
            score_val += s; details['Growth'] = d
        else:
            details['Growth'] = "增速缺失"
        # 5. 现金流质量
        if cash_profit_ratio is not None:
            if cash_profit_ratio > 1.5: s, d = +0.8, f"现金流/净利={cash_profit_ratio:.2f} 极高"
            elif cash_profit_ratio > 1.0: s, d = +0.5, f"现金流/净利={cash_profit_ratio:.2f} 健康"
            elif cash_profit_ratio > 0.5: s, d = +0.2, f"现金流/净利={cash_profit_ratio:.2f} 一般"
            else: s, d = -0.8, f"现金流/净利={cash_profit_ratio:.2f} 低质量"
            score_val += s; details['Cash'] = d
        else:
            details['Cash'] = "现金流比缺失"
        # 6. 负债率
        if debt_ratio is not None:
            if debt_ratio > 80: s, d = -0.8, f"负债率{debt_ratio:.1f}% 危险"
            elif debt_ratio > 60: s, d = -0.3, f"负债率{debt_ratio:.1f}% 偏高"
            else: s, d = +0.3, f"负债率{debt_ratio:.1f}% 安全"
            score_val += s; details['Debt'] = d
        else:
            details['Debt'] = "负债率缺失"
        # 7. 52周位置
        if high_52w and low_52w and high_52w > low_52w and price > 0:
            pos = (price - low_52w) / (high_52w - low_52w)
            if pos < 0.15: s, d = +0.6, f"52周低位({pos*100:.0f}%)"
            elif pos < 0.3: s, d = +0.3, f"52周偏低({pos*100:.0f}%)"
            elif pos > 0.95: s, d = -0.8, f"52周高位({pos*100:.0f}%)"
            elif pos > 0.85: s, d = -0.4, f"52周偏高({pos*100:.0f}%)"
            else: s, d = 0.0, f"52周中位({pos*100:.0f}%)"
            score_val += s; details['位置'] = d
        else:
            details['位置'] = "52周数据缺失"
        score_val = max(-5, min(5, score_val))
        return {
            'total_score': score_val, 'details': details,
            'roe': roe, 'profit_growth': profit_growth,
            'debt_ratio': debt_ratio, 'cash_profit_ratio': cash_profit_ratio,
        }


# ============================================================
# 主分析器
# ============================================================
class HS300Analyzer:
    def __init__(self, max_workers=10):
        self.indicators = TechnicalIndicators()
        self.analyzer = SignalAnalyzer()
        self.fetcher = TencentDataFetcher()
        self.fund_fetcher = TencentFundamentalFetcher()
        self.fund_scorer = FundamentalScorer()
        self.em_fetcher = EastmoneyDataFetcher()
        self.results = []
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._completed = 0
        self._total = 0
        self._tencent_data = {}
        self._em_data = {}
    def get_hs300_stocks(self):
        return HS300_CODES
    def _analyze_one(self, code, name):
        try:
            df = self.fetcher.fetch_kline(code, days=120)
            if df is None or len(df) < 30:
                return None
            df = self.indicators.calc_ma(df)
            df = self.indicators.calc_macd(df)
            df = self.indicators.calc_kdj(df)
            df = self.indicators.calc_rsi(df)
            df = self.indicators.calc_volume_ma(df)
            df = self.indicators.calc_boll(df)
            result = self.analyzer.analyze(df)
            result['code'] = code
            result['name'] = name
            return result
        except Exception:
            return None
    def analyze_stock(self, code, name):
        result = self._analyze_one(code, name)
        if result is None:
            with self._lock:
                self._completed += 1
            return None
        # 合并数据
        tencent_info = self._tencent_data.get(code, {})
        em_info = self._em_data.get(code, {})
        price = result.get('price', 0)
        full_fund = {
            'pe': tencent_info.get('pe'), 'pb': tencent_info.get('pb'),
            'total_mv': tencent_info.get('total_mv'), 'high_52w': tencent_info.get('high_52w'), 'low_52w': tencent_info.get('low_52w'),
            'roe': em_info.get('roe'), 'profit_growth': em_info.get('profit_growth'),
            'debt_ratio': em_info.get('debt_ratio'), 'cash_profit_ratio': em_info.get('cash_profit_ratio'),
        }
        fund_score = self.fund_scorer.score(full_fund, price)
        result['fundamental_score'] = fund_score['total_score']
        result['fundamental_detail'] = fund_score['details']
        result['pe'] = full_fund['pe']; result['pb'] = full_fund['pb']
        result['roe'] = fund_score['roe']; result['profit_growth'] = fund_score['profit_growth']
        result['debt_ratio'] = fund_score['debt_ratio']; result['cash_profit_ratio'] = fund_score['cash_profit_ratio']
        # 融合：技术40% + 基本面60%
        composite = result['total_score'] * 0.4 + fund_score['total_score'] * 0.6
        result['composite_score'] = composite
        if composite >= 3.5: result['advice'] = '强烈买入'; result['level'] = 5
        elif composite >= 1.5: result['advice'] = '建议买入'; result['level'] = 4
        elif composite <= -3.5: result['advice'] = '强烈卖出'; result['level'] = 1
        elif composite <= -1.5: result['advice'] = '建议卖出'; result['level'] = 2
        else: result['advice'] = '观望'; result['level'] = 3
        with self._lock:
            self._completed += 1
            progress = self._completed / self._total * 100
            sys.stdout.write(f"\r进度: {progress:.1f}% ({self._completed}/{self._total}) - {name}({code})    ")
            sys.stdout.flush()
        return result
    def run_analysis(self, top_n=20):
        stocks = self.get_hs300_stocks()
        all_codes = [c for c, _ in stocks]
        # 获取腾讯估值
        print("📊 正在通过腾讯API获取估值数据...")
        self._tencent_data = self.fund_fetcher.fetch(all_codes)
        print(f"✅ 腾讯估值数据完成，成功 {len(self._tencent_data)} 只\n")
        # 获取东方财富财务
        print("📊 正在通过东方财富API获取财务数据...")
        self._em_data = self.em_fetcher.fetch_all(all_codes)
        print(f"✅ 东方财富财务数据完成，成功 {len(self._em_data)} 只\n")
        self._total = len(stocks)
        self._completed = 0
        print(f"🔍 开始分析 {self._total} 只股票，并发线程数: {self.max_workers}\n")
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.analyze_stock, code, name): (code, name) for code, name in stocks}
            for future in as_completed(futures):
                res = future.result()
                if res:
                    self.results.append(res)
        elapsed = time.time() - start_time
        print(f"\n\n✅ 分析完成！耗时: {elapsed:.1f} 秒\n")
        self.generate_report(top_n)
    def generate_report(self, top_n=20):
        if not self.results:
            print("❌ 没有有效的分析结果")
            return
        df = pd.DataFrame(self.results)
        df = df.sort_values('composite_score', ascending=False)
        buy_stocks = df[df['level'] >= 4].head(top_n)
        sell_stocks = df[df['level'] <= 2].sort_values('composite_score', ascending=True).head(top_n)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("=" * 150)
        print(f"📊 沪深300成分股 技术+深度基本面 综合分析报告")
        print(f"生成时间: {now}")
        print("=" * 150)
        print(f"\n📈 市场概况:")
        print(f"  分析股票数: {len(df)}")
        print(f"  买入信号: {len(df[df['level'] >= 4])} 只")
        print(f"  卖出信号: {len(df[df['level'] <= 2])} 只")
        print(f"  观望信号: {len(df[df['level'] == 3])} 只")
        if not buy_stocks.empty:
            print(f"\n{'='*150}")
            print(f"🟢 建议买入的股票（Top {min(top_n, len(buy_stocks))}）")
            print("=" * 150)
            print(f"{'代码':<8}{'名称':<10}{'现价':>8}{'涨幅':>8}{'综合分':>8}{'技术分':>8}{'基本面':>8}{'PE':>8}{'PB':>8}{'ROE':>6}{'负债%':>6}{'建议':<10}{'核心信号'}")
            print("-" * 150)
            for _, row in buy_stocks.iterrows():
                sig = ', '.join([f"{k}:{v}" for k, v in row['signals'].items()])
                pe_str = f"{row['pe']:.1f}" if row.get('pe') is not None else "-"
                pb_str = f"{row['pb']:.2f}" if row.get('pb') is not None else "-"
                roe_str = f"{row['roe']:.1f}" if row.get('roe') is not None else "-"
                debt_str = f"{row['debt_ratio']:.1f}" if row.get('debt_ratio') is not None else "-"
                change_str = f"{row['change_pct']:+.2f}%"
                print(f"{row['code']:<8}{row['name']:<10}{row['price']:>8.2f}{change_str:>8}"
                      f"{row['composite_score']:>+8.2f}{row['total_score']:>+8.2f}{row['fundamental_score']:>+8.2f}"
                      f"{pe_str:>8}{pb_str:>8}{roe_str:>6}{debt_str:>6}"
                      f"{row['advice']:<10}{sig[:40]}")
        if not sell_stocks.empty:
            print(f"\n{'='*150}")
            print(f"🔴 建议卖出的股票（Top {min(top_n, len(sell_stocks))}）")
            print("=" * 150)
            print(f"{'代码':<8}{'名称':<10}{'现价':>8}{'涨幅':>8}{'综合分':>8}{'技术分':>8}{'基本面':>8}{'PE':>8}{'PB':>8}{'ROE':>6}{'负债%':>6}{'建议':<10}{'核心信号'}")
            print("-" * 150)
            for _, row in sell_stocks.iterrows():
                sig = ', '.join([f"{k}:{v}" for k, v in row['signals'].items()])
                pe_str = f"{row['pe']:.1f}" if row.get('pe') is not None else "-"
                pb_str = f"{row['pb']:.2f}" if row.get('pb') is not None else "-"
                roe_str = f"{row['roe']:.1f}" if row.get('roe') is not None else "-"
                debt_str = f"{row['debt_ratio']:.1f}" if row.get('debt_ratio') is not None else "-"
                change_str = f"{row['change_pct']:+.2f}%"
                print(f"{row['code']:<8}{row['name']:<10}{row['price']:>8.2f}{change_str:>8}"
                      f"{row['composite_score']:>+8.2f}{row['total_score']:>+8.2f}{row['fundamental_score']:>+8.2f}"
                      f"{pe_str:>8}{pb_str:>8}{roe_str:>6}{debt_str:>6}"
                      f"{row['advice']:<10}{sig[:40]}")
        output_file = f"hs300_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 完整分析结果已保存到: {output_file}")
        print(f"\n{'='*150}")
        print("⚠️  重要风险提示:")
        print("  1. 本分析基于技术指标与公开财务数据，不构成投资建议")
        print("  2. 东方财富财务数据为最新报告期，可能存在延迟")
        print("  3. 严格执行仓位管理和止损纪律")
        print("  4. 股市有风险，投资需谨慎")
        print("=" * 150)


# ============================================================
# 入口
# ============================================================
def main():
    print("\n" + "=" * 150)
    print("🚀 沪深300成分股综合分析系统（技术+深度基本面版）")
    print("=" * 150)
    print("\n数据来源：")
    print("  - 腾讯财经：实时行情、PE、PB、市值、52周高低点")
    print("  - 东方财富：ROE、净利润增速、负债率、经营现金流质量")
    print("依赖：pandas, numpy, requests（无需akshare）\n")
    max_workers = 15
    if len(sys.argv) > 1:
        try:
            max_workers = int(sys.argv[1])
        except ValueError:
            pass
    analyzer = HS300Analyzer(max_workers=max_workers)
    analyzer.run_analysis(top_n=20)


if __name__ == "__main__":
    main()
