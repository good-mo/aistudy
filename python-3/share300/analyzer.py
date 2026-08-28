#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沪深300成分股综合分析系统（技术+基本面融合版）
功能：基于9大技术指标 + 估值/市值/位置 三维评分筛选信号
数据源：腾讯财经 API（K线 + 实时估值）
依赖：pandas, numpy, requests
"""

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
warnings.filterwarnings('ignore')

# ============================================================
# 全局会话
# ============================================================
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
})

# 腾讯财经实时行情 API（批量获取，最多60只/次）
TENCENT_API = "http://qt.gtimg.cn/q="
TENCENT_KLINE_API = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def _to_tencent_code(code: str) -> str:
    if code.startswith(("60", "68")):
        return f"sh{code}"
    return f"sz{code}"


# ============================================================
# 沪深300 成分股列表（内置）
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
# 技术指标计算模块（原逻辑，完全保留）
# ============================================================
class TechnicalIndicators:
    @staticmethod
    def calc_ma(df: pd.DataFrame, periods: List[int] = [5, 10, 20, 60]) -> pd.DataFrame:
        for p in periods:
            df[f'MA{p}'] = df['收盘'].rolling(window=p).mean()
        return df
    @staticmethod
    def calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        ema_fast = df['收盘'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['收盘'].ewm(span=slow, adjust=False).mean()
        df['DIF'] = ema_fast - ema_slow
        df['DEA'] = df['DIF'].ewm(span=signal, adjust=False).mean()
        df['MACD'] = 2 * (df['DIF'] - df['DEA'])
        return df
    @staticmethod
    def calc_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
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
        delta = df['收盘'].diff()
        for p in periods:
            gain = delta.where(delta > 0, 0).rolling(window=p).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=p).mean()
            rs = gain / loss
            df[f'RSI{p}'] = 100 - 100 / (1 + rs)
        return df
    @staticmethod
    def calc_volume_ma(df: pd.DataFrame, periods: List[int] = [5, 20]) -> pd.DataFrame:
        for p in periods:
            df[f'VOL_MA{p}'] = df['成交量'].rolling(window=p).mean()
        return df
    @staticmethod
    def calc_boll(df: pd.DataFrame, period: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
        df['BOLL_MID'] = df['收盘'].rolling(window=period).mean()
        std = df['收盘'].rolling(window=period).std()
        df['BOLL_UP'] = df['BOLL_MID'] + std_mult * std
        df['BOLL_DN'] = df['BOLL_MID'] - std_mult * std
        band_range = df['BOLL_UP'] - df['BOLL_DN']
        df['BOLL_WIDTH'] = (band_range / df['BOLL_MID']).replace([np.inf, -np.inf], np.nan).fillna(0) * 100
        df['BOLL_POS'] = ((df['收盘'] - df['BOLL_DN']) / band_range.replace(0, np.nan)).fillna(0.5)
        return df


# ============================================================
# 信号分析模块（原逻辑，完全保留）
# ============================================================
class SignalAnalyzer:
    def analyze(self, df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 30:
            return self._empty_result()
        signals = {}
        scores = {}
        signals['MA'], scores['MA'] = self._ma_signal(df)
        signals['MACD'], scores['MACD'] = self._macd_signal(df)
        signals['KDJ'], scores['KDJ'] = self._kdj_signal(df)
        signals['RSI'], scores['RSI'] = self._rsi_signal(df)
        signals['VOL'], scores['VOL'] = self._volume_signal(df)
        signals['BOLL'], scores['BOLL'] = self._boll_signal(df)
        signals['SR'], scores['SR'] = self._support_resistance_signal(df)
        signals['CANDLE'], scores['CANDLE'] = self._candlestick_signal(df)
        signals['PATTERN'], scores['PATTERN'] = self._pattern_signal(df)
        weights = {
            'MA': 1.0, 'MACD': 1.5, 'KDJ': 1.0, 'RSI': 1.0,
            'VOL': 0.5, 'BOLL': 0.8, 'SR': 0.5,
            'CANDLE': 0.8, 'PATTERN': 1.2,
        }
        total_score = sum(scores[k] * weights[k] for k in scores)
        if total_score >= 4.5:
            advice = '强烈买入'; level = 5
        elif total_score >= 2.5:
            advice = '建议买入'; level = 4
        elif total_score <= -4.5:
            advice = '强烈卖出'; level = 1
        elif total_score <= -2.5:
            advice = '建议卖出'; level = 2
        else:
            advice = '观望'; level = 3
        latest = df.iloc[-1]
        return {
            'signals': signals, 'scores': scores, 'total_score': total_score,
            'advice': advice, 'level': level, 'price': latest['收盘'],
            'change_pct': self._calc_change_pct(df), 'rsi': latest.get('RSI6', 50),
            'kdj_j': latest.get('J', 50),
        }
    def _calc_change_pct(self, df: pd.DataFrame) -> float:
        if len(df) < 2:
            return 0
        return (df.iloc[-1]['收盘'] - df.iloc[-2]['收盘']) / df.iloc[-2]['收盘'] * 100
    def _ma_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        if len(df) >= 65 and 'MA60' in df.columns:
            ma60_recent = df['MA60'].dropna().tail(5)
            if len(ma60_recent) >= 5:
                ma60_trend_up = ma60_recent.iloc[-1] > ma60_recent.iloc[0]
            else:
                ma60_trend_up = True
        else:
            ma60_trend_up = latest['收盘'] > latest.get('MA60', latest['MA20'])
        prev2 = df.iloc[-3] if len(df) >= 3 else prev
        golden_cross = (prev2['MA5'] <= prev2['MA10'] and prev['MA5'] <= prev['MA10'] and latest['MA5'] > latest['MA10'])
        death_cross = (prev2['MA5'] >= prev2['MA10'] and prev['MA5'] >= prev['MA10'] and latest['MA5'] < latest['MA10'])
        if golden_cross and ma60_trend_up:
            return ('MA5/10金叉(↑趋势)', +1.2)
        if golden_cross:
            return ('MA5/10金叉(↓趋势)', +0.5)
        if death_cross and not ma60_trend_up:
            return ('MA5/10死叉(↓趋势)', -1.2)
        if death_cross:
            return ('MA5/10死叉(↑趋势)', -0.5)
        if latest['MA5'] > latest['MA10'] > latest['MA20']:
            return ('多头排列(↑趋势)', +0.8) if ma60_trend_up else ('多头排列(↓趋势)', +0.3)
        if latest['MA5'] < latest['MA10'] < latest['MA20']:
            return ('空头排列(↓趋势)', -0.8) if not ma60_trend_up else ('空头排列(↑趋势)', -0.3)
        return ('站上MA20', +0.3) if latest['收盘'] > latest['MA20'] else ('跌破MA20', -0.3)
    def _macd_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        latest = df.iloc[-1]; prev = df.iloc[-2]
        if prev['DIF'] < prev['DEA'] and latest['DIF'] > latest['DEA']:
            return ('零下金叉', +1.0) if latest['DIF'] < 0 else ('金叉', +0.8)
        if prev['DIF'] > prev['DEA'] and latest['DIF'] < latest['DEA']:
            return ('零上死叉', -1.0) if latest['DIF'] > 0 else ('死叉', -0.8)
        if len(df) >= 40:
            recent = df.tail(40)
            prices = recent['收盘'].values; difs = recent['DIF'].values; n = len(recent)
            peaks = []
            for i in range(2, n-2):
                if prices[i] > prices[i-1] and prices[i] > prices[i-2] and prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                    peaks.append((i, prices[i], difs[i]))
            if len(peaks) >= 2:
                p1, p2 = peaks[-2], peaks[-1]
                if p2[1] > p1[1] and p2[2] < p1[2]:
                    return ('顶背离⚠️', -1.5)
            troughs = []
            for i in range(2, n-2):
                if prices[i] < prices[i-1] and prices[i] < prices[i-2] and prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                    troughs.append((i, prices[i], difs[i]))
            if len(troughs) >= 2:
                t1, t2 = troughs[-2], troughs[-1]
                if t2[1] < t1[1] and t2[2] > t1[2]:
                    return ('底背离🔥', +1.5)
        if latest['MACD'] > prev['MACD'] > 0:
            return ('红柱放大', +0.4)
        if latest['MACD'] < prev['MACD'] < 0:
            return ('绿柱放大', -0.4)
        return ('震荡', 0)
    def _kdj_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        latest = df.iloc[-1]; prev = df.iloc[-2]
        if latest['K'] > 80 and latest['D'] > 70:
            return ('严重超买', -1.0) if latest['J'] > 100 else ('超买区', -0.6)
        if latest['K'] < 20 and latest['D'] < 30:
            return ('严重超卖', +1.0) if latest['J'] < 0 else ('超卖区', +0.6)
        if prev['K'] < prev['D'] and latest['K'] > latest['D']:
            return ('低位金叉', +1.0) if latest['K'] < 30 else ('金叉', +0.5)
        if prev['K'] > prev['D'] and latest['K'] < latest['D']:
            return ('高位死叉', -1.0) if latest['K'] > 70 else ('死叉', -0.5)
        return ('中性', 0)
    def _rsi_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        rsi = df.iloc[-1]['RSI6']
        if pd.isna(rsi):
            return ('数据不足', 0)
        if rsi > 80: return (f'RSI={rsi:.1f}严重超买', -1.0)
        if rsi > 70: return (f'RSI={rsi:.1f}超买', -0.6)
        if rsi < 20: return (f'RSI={rsi:.1f}严重超卖', +1.0)
        if rsi < 30: return (f'RSI={rsi:.1f}超卖', +0.6)
        if 40 <= rsi <= 60: return (f'RSI={rsi:.1f}中性', 0)
        return (f'RSI={rsi:.1f}偏强', +0.3) if rsi > 60 else (f'RSI={rsi:.1f}偏弱', -0.3)
    def _volume_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        latest = df.iloc[-1]
        if pd.isna(latest.get('VOL_MA5')) or pd.isna(latest.get('VOL_MA20')):
            return ('数据不足', 0)
        vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 1
        price_up = latest['收盘'] > df.iloc[-2]['收盘']
        price_change = abs(latest['收盘'] - df.iloc[-2]['收盘']) / df.iloc[-2]['收盘']
        if len(df) >= 10:
            price_5d_ago = df.iloc[-6]['收盘']; vol_5d_ago = df.iloc[-6]['成交量']
            price_trend_5d = (latest['收盘'] - price_5d_ago) / price_5d_ago
            vol_trend_5d = (latest['成交量'] - vol_5d_ago) / vol_5d_ago if vol_5d_ago > 0 else 0
            if price_trend_5d > 0.03 and vol_trend_5d < -0.2:
                return ('量价背离(价涨量缩)', -1.2)
            if price_trend_5d < -0.03 and vol_trend_5d < -0.2:
                return ('价跌量缩(抛压减轻)', +0.8)
            if price_trend_5d < -0.03 and vol_trend_5d > 0.3:
                return ('价跌量增(恐慌抛售)', -1.0)
        if vol_ratio > 2.0 and price_up: return (f'放量上涨({vol_ratio:.1f}倍)', +1.0)
        if vol_ratio > 2.0 and not price_up: return (f'放量下跌({vol_ratio:.1f}倍)', -1.0)
        if vol_ratio < 0.6 and price_up and price_change > 0.005: return (f'缩量上涨(动能不足)', -0.5)
        if vol_ratio < 0.6 and not price_up and price_change > 0.005: return (f'缩量下跌(抛压轻)', +0.4)
        if vol_ratio < 0.5: return (f'极度缩量({vol_ratio:.1f}倍)', 0)
        if vol_ratio > 1.5 and price_up: return (f'温和放量({vol_ratio:.1f}倍)', +0.5)
        return (f'量能平稳({vol_ratio:.1f}倍)', 0)
    def _boll_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        latest = df.iloc[-1]
        if pd.isna(latest.get('BOLL_UP')) or pd.isna(latest.get('BOLL_DN')):
            return ('数据不足', 0)
        price, up, dn, mid = latest['收盘'], latest['BOLL_UP'], latest['BOLL_DN'], latest['BOLL_MID']
        pos = latest.get('BOLL_POS', 0.5); width = latest.get('BOLL_WIDTH', 0)
        if price >= up: return ('突破上轨(超买)', -0.8)
        if price <= dn: return ('跌破下轨(超卖)', +0.8)
        if pos > 0.8: return ('接近上轨', -0.4)
        if pos < 0.2: return ('接近下轨', +0.4)
        if not pd.isna(width) and width < 5:
            if pos > 0.6: return ('带宽收窄(高位)', -0.3)
            if pos < 0.4: return ('带宽收窄(低位)', +0.3)
            return ('带宽收窄', 0)
        return ('中轨附近', 0)
    def _candlestick_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        if len(df) < 3: return ('数据不足', 0)
        l0, l1, l2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]
        o0, c0, h0, lo0 = l0['开盘'], l0['收盘'], l0['最高'], l0['最低']
        o1, c1, h1, lo1 = l1['开盘'], l1['收盘'], l1['最高'], l1['最低']
        body0, body1 = abs(c0-o0), abs(c1-o1)
        avg_body_10 = df['收盘'].diff().abs().rolling(10).mean().iloc[-1]
        if pd.isna(avg_body_10) or avg_body_10 == 0: avg_body_10 = body0
        is_bull0, is_bear0, is_bull1 = c0 > o0, c0 < o0, c1 > o1
        is_small0 = body0 < avg_body_10 * 0.4
        lower_shadow0 = min(o0, c0) - lo0
        upper_shadow0 = h0 - max(o0, c0)
        if is_bull0 and lower_shadow0 >= body0 * 2 and upper_shadow0 < body0 * 0.5 and body0 > 0:
            if len(df) >= 5 and df.iloc[-1]['收盘'] < df.iloc[-5]['收盘']:
                return ('锤子线(底部反转)', +1.0)
        if upper_shadow0 >= body0 * 2 and lower_shadow0 < body0 * 0.5 and body0 > 0:
            if len(df) >= 5 and df.iloc[-1]['收盘'] > df.iloc[-5]['收盘']:
                return ('上吊线(顶部反转)', -1.0)
        body1_valid = body1 >= avg_body_10 * 0.4
        if is_bull0 and not is_bull1 and body1_valid:
            if c0 > max(o1, c1) and o0 < min(o1, c1): return ('阳包阴(看涨吞没)', +1.2)
        if is_bear0 and is_bull1 and body1_valid:
            if c0 < min(o1, c1) and o0 > max(o1, c1): return ('阴包阳(看跌吞没)', -1.2)
        if is_small0 and lower_shadow0 > body0 and upper_shadow0 > body0:
            if len(df) >= 5 and df.iloc[-1]['收盘'] > df.iloc[-5]['收盘']: return ('高位十字星(变盘)', -0.5)
            if len(df) >= 5 and df.iloc[-1]['收盘'] < df.iloc[-5]['收盘']: return ('低位十字星(变盘)', +0.5)
            return ('十字星', 0)
        if len(df) >= 4:
            three_bear = all(df.iloc[-i]['收盘'] < df.iloc[-i]['开盘'] for i in [2,3,4])
            if three_bear and is_bull0 and body0 > avg_body_10: return ('三连阴后放量阳', +0.8)
            three_bull = all(df.iloc[-i]['收盘'] > df.iloc[-i]['开盘'] for i in [2,3,4])
            if three_bull and not is_bull0 and body0 > avg_body_10: return ('三连阳后放量阴', -0.8)
        if o0 > h1 * 1.01: return ('向上跳空缺口', +0.6)
        if o0 < lo1 * 0.99: return ('向下跳空缺口', -0.6)
        return ('无明确形态', 0)
    def _pattern_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        if len(df) < 60: return ('数据不足', 0)
        prices = df['收盘'].values; highs = df['最高'].values; lows = df['最低'].values; n = len(prices)
        search_start = max(3, n-60)
        troughs = []
        for i in range(search_start, n-3):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i-3] and lows[i] < lows[i+1] and lows[i] < lows[i+2] and lows[i] < lows[i+3]:
                troughs.append((i, lows[i]))
        if len(troughs) >= 2:
            t1, t2 = troughs[-2], troughs[-1]
            if t2[0] - t1[0] >= 5 and abs(t2[1]-t1[1])/t1[1] < 0.03:
                neck_high = max(highs[t1[0]:t2[0]+1])
                if prices[-1] > neck_high: return ('W底突破颈线', +1.8)
                if (neck_high - prices[-1]) / prices[-1] < 0.03: return ('W底(待突破颈线)', +1.0)
                if abs(prices[-1] - neck_high) / neck_high < 0.02: return ('W底(回踩颈线)', +0.6)
        peaks = []
        for i in range(search_start, n-3):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i-3] and highs[i] > highs[i+1] and highs[i] > highs[i+2] and highs[i] > highs[i+3]:
                peaks.append((i, highs[i]))
        if len(peaks) >= 2:
            p1, p2 = peaks[-2], peaks[-1]
            if p2[0] - p1[0] >= 5 and abs(p2[1]-p1[1])/p1[1] < 0.03:
                neck_low = min(lows[p1[0]:p2[0]+1])
                if prices[-1] < neck_low: return ('M头跌破颈线', -1.8)
                if (prices[-1] - neck_low) / prices[-1] < 0.03: return ('M头(待破颈线)', -1.0)
                if abs(prices[-1] - neck_low) / neck_low < 0.02: return ('M头(反抽颈线)', -0.6)
        recent20 = df.tail(20)
        if len(recent20) >= 20:
            first10 = recent20.iloc[:10]; last10 = recent20.iloc[10:]
            h1, h2 = first10['最高'].max(), last10['最高'].max()
            l1, l2 = first10['最低'].min(), last10['最低'].min()
            hl_ratio = (h1-l1)/l1 if l1 > 0 else 1
            if abs(h2-h1)/h1 < 0.015 and l2 > l1*1.005 and hl_ratio < 0.15: return ('上升三角形(看涨)', +0.6)
            if abs(l2-l1)/l1 < 0.015 and h2 < h1*0.995 and hl_ratio < 0.15: return ('下降三角形(看跌)', -0.6)
            if h2 < h1 and l2 > l1:
                if hl_ratio < 0.08:
                    return ('对称三角形(待上破)', +0.4) if prices[-1] > recent20['收盘'].mean() else ('对称三角形(待下破)', -0.4)
                return ('收敛三角形整理', 0)
        return ('无明显形态', 0)
    def _support_resistance_signal(self, df: pd.DataFrame) -> Tuple[str, float]:
        latest = df.iloc[-1]; price = latest['收盘']
        recent60 = df.tail(60)
        resist_high = recent60['最高'].max(); support_low = recent60['最低'].min()
        dist_to_resist = (resist_high - price) / price * 100
        dist_to_support = (price - support_low) / price * 100
        ma60 = latest.get('MA60', None); ma20 = latest.get('MA20', None)
        score = 0.0; parts = []
        if dist_to_resist < 3: parts.append(f'接近阻力({resist_high:.2f})'); score -= 0.8
        elif dist_to_resist < 6: parts.append(f'距阻力{dist_to_resist:.1f}%'); score -= 0.3
        if dist_to_support < 3: parts.append(f'接近支撑({support_low:.2f})'); score += 0.8
        elif dist_to_support < 6: parts.append(f'距支撑{dist_to_support:.1f}%'); score += 0.3
        if ma60 is not None and not pd.isna(ma60):
            if price > ma60 and (price-ma60)/price*100 < 3: parts.append('MA60支撑'); score += 0.5
            elif price < ma60 and (ma60-price)/price*100 < 3: parts.append('MA60阻力'); score -= 0.5
        if ma20 is not None and not pd.isna(ma20):
            if price > ma20 and (price-ma20)/price*100 < 3: parts.append('MA20支撑'); score += 0.3
            elif price < ma20 and (ma20-price)/price*100 < 3: parts.append('MA20阻力'); score -= 0.3
        if not parts: return ('无明确支撑/阻力', 0)
        return ('; '.join(parts), score)
    def _empty_result(self):
        return {'signals': {}, 'scores': {}, 'total_score': 0, 'advice': '数据不足', 'level': 0,
                'price': 0, 'change_pct': 0, 'rsi': 50, 'kdj_j': 50}


# ============================================================
# 基本面数据获取器（腾讯API）
# ============================================================
class TencentFundamentalFetcher:
    """通过腾讯实时行情接口获取估值/市值/52周高低点"""
    # 腾讯API字段大致索引（不同接口版本可能微调，已做容错）
    # 返回值示例: v_sh600519="1~贵州茅台~600519~..."
    # 索引含义（常见）：3=现价, 39=市盈率, 44=总市值(万), 45=流通市值(万), 46=市净率, 52=52周高, 53=52周低
    @staticmethod
    def fetch(codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取基本面数据
        参数: codes 为通用代码列表，如 ['600519','000001']
        返回: {code: {'pe':..., 'pb':..., 'total_mv':..., 'float_mv':..., 'high_52w':..., 'low_52w':...}, ...}
        """
        results = {}
        # 每批最多请求60只
        for i in range(0, len(codes), 60):
            batch = codes[i:i+60]
            tc_codes = ",".join([_to_tencent_code(c) for c in batch])
            url = f"{TENCENT_API}{tc_codes}"
            try:
                resp = _session.get(url, timeout=15)
                text = resp.text
                # 解析多行返回结果
                for line in text.strip().split(';'):
                    line = line.strip()
                    if not line or '=""' in line:
                        continue
                    # 提取代码和值字符串
                    if '="' not in line:
                        continue
                    parts = line.split('="')
                    if len(parts) < 2:
                        continue
                    header = parts[0]  # e.g. v_sh600519
                    values = parts[1].rstrip('"')
                    if not values or '~' not in values:
                        continue
                    # 从header提取原始代码
                    raw_code = header.replace('v_sh', '').replace('v_sz', '').replace('v_sh688', '').replace('v_sz300', '').replace('v_sz000', '').replace('v_sz002', '').replace('v_sz001', '').replace('v_sz003', '').replace('v_sz301', '').replace('v_sz302', '').replace('v_sz600', '').replace('v_sz601', '').replace('v_sz603', '').replace('v_sz605', '').replace('v_sz600', '')
                    # 更稳健的方式：从header正则提取
                    import re
                    m = re.search(r'v_[a-z]+(\d+)', header)
                    if m:
                        raw_code = m.group(1)
                    else:
                        continue
                    data = values.split('~')
                    pe = None; pb = None; total_mv = None; float_mv = None; high_52w = None; low_52w = None
                    try:
                        if len(data) > 39:
                            pe = float(data[39]) if data[39] not in ('', '-', '--') else None
                        if len(data) > 46:
                            pb = float(data[46]) if data[46] not in ('', '-', '--') else None
                        if len(data) > 44:
                            total_mv = float(data[44]) if data[44] not in ('', '-', '--') else None
                        if len(data) > 45:
                            float_mv = float(data[45]) if data[45] not in ('', '-', '--') else None
                        if len(data) > 52:
                            high_52w = float(data[52]) if data[52] not in ('', '-', '--') else None
                        if len(data) > 53:
                            low_52w = float(data[53]) if data[53] not in ('', '-', '--') else None
                    except (ValueError, IndexError):
                        pass
                    results[raw_code] = {
                        'pe': pe, 'pb': pb, 'total_mv': total_mv,
                        'float_mv': float_mv, 'high_52w': high_52w, 'low_52w': low_52w
                    }
            except Exception as e:
                print(f"⚠️ 腾讯基本面接口请求失败: {e}")
        return results


# ============================================================
# 基本面评分器
# ============================================================
class FundamentalScorer:
    """将估值、市值、52周位置量化为评分"""
    @staticmethod
    def score(fund: Dict, price: float) -> Dict:
        """
        输入单只股票的基本面字典和价格
        返回: {'total_score': float, 'details': {...}}
        """
        pe = fund.get('pe'); pb = fund.get('pb')
        total_mv = fund.get('total_mv'); high_52w = fund.get('high_52w'); low_52w = fund.get('low_52w')
        details = {}
        score_val = 0.0
        # 1. PE评分（市盈率）
        if pe and pe > 0:
            if pe < 10: s, d = +1.0, f"PE={pe:.1f} 极低估值"
            elif pe < 20: s, d = +0.6, f"PE={pe:.1f} 低估值"
            elif pe < 30: s, d = +0.2, f"PE={pe:.1f} 合理"
            elif pe < 50: s, d = -0.3, f"PE={pe:.1f} 偏高"
            else: s, d = -0.8, f"PE={pe:.1f} 高估值"
            score_val += s; details['PE'] = d
        else:
            details['PE'] = "PE缺失"
        # 2. PB评分（市净率）
        if pb and pb > 0:
            if pb < 1.0: s, d = +0.8, f"PB={pb:.2f} 破净/极低"
            elif pb < 1.5: s, d = +0.5, f"PB={pb:.2f} 低估值"
            elif pb < 3.0: s, d = +0.2, f"PB={pb:.2f} 合理"
            elif pb < 5.0: s, d = -0.3, f"PB={pb:.2f} 偏高"
            else: s, d = -0.6, f"PB={pb:.2f} 高估值"
            score_val += s; details['PB'] = d
        else:
            details['PB'] = "PB缺失"
        # 3. 市值规模（越大越稳，但弹性小；这里中性处理）
        if total_mv and total_mv > 0:
            mv_yi = total_mv / 10000  # 万元转亿元
            if mv_yi > 5000: s, d = +0.3, f"总市值{mv_yi:.0f}亿 巨无霸"
            elif mv_yi > 1000: s, d = +0.1, f"总市值{mv_yi:.0f}亿 大盘"
            elif mv_yi > 300: s, d = 0.0, f"总市值{mv_yi:.0f}亿 中盘"
            else: s, d = -0.1, f"总市值{mv_yi:.0f}亿 小盘"
            score_val += s; details['市值'] = d
        else:
            details['市值'] = "市值缺失"
        # 4. 52周位置（判断当前价格在年度区间的相对位置）
        if high_52w and low_52w and high_52w > low_52w and price > 0:
            pos = (price - low_52w) / (high_52w - low_52w)
            if pos < 0.15: s, d = +0.8, f"52周低位({pos*100:.0f}%) 超跌"
            elif pos < 0.3: s, d = +0.4, f"52周偏低({pos*100:.0f}%)"
            elif pos > 0.95: s, d = -0.8, f"52周高位({pos*100:.0f}%) 追高风险"
            elif pos > 0.85: s, d = -0.4, f"52周偏高({pos*100:.0f}%)"
            else: s, d = 0.0, f"52周中位({pos*100:.0f}%)"
            score_val += s; details['位置'] = d
        else:
            details['位置'] = "52周数据缺失"
        # 限制范围
        score_val = max(-3, min(3, score_val))
        return {'total_score': score_val, 'details': details}


# ============================================================
# 腾讯财经数据获取模块（原逻辑）
# ============================================================
class TencentDataFetcher:
    @staticmethod
    def _parse_kline(klines: List) -> List[Dict]:
        records = []
        for line in klines:
            if not isinstance(line, list) or len(line) < 6:
                continue
            try:
                records.append({
                    '日期': line[0], '开盘': float(line[1]), '收盘': float(line[2]),
                    '最高': float(line[3]), '最低': float(line[4]), '成交量': float(line[5]),
                })
            except (ValueError, TypeError):
                continue
        return records
    @staticmethod
    def fetch_kline(code: str, days: int = 120) -> Optional[pd.DataFrame]:
        try:
            tc_code = _to_tencent_code(code)
            param = f"{tc_code},day,,,{days},qfq"
            resp = _session.get(TENCENT_KLINE_API, params={'param': param}, timeout=10)
            data = resp.json()
            if data.get('code') == 0 and data.get('data'):
                stock_data = data['data'].get(tc_code)
                if not stock_data:
                    return None
                klines = stock_data.get('qfqday') or stock_data.get('day', [])
                if not klines:
                    return None
                records = TencentDataFetcher._parse_kline(klines)
                if records:
                    return pd.DataFrame(records)
        except Exception:
            pass
        return None


# ============================================================
# 沪深300分析主程序（融合基本面）
# ============================================================
class HS300Analyzer:
    def __init__(self, max_workers: int = 10):
        self.indicators = TechnicalIndicators()
        self.analyzer = SignalAnalyzer()
        self.fetcher = TencentDataFetcher()
        self.fund_fetcher = TencentFundamentalFetcher()
        self.fund_scorer = FundamentalScorer()
        self.results = []
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self._completed = 0
        self._total = 0
        self._fund_data: Dict[str, Dict] = {}
    def get_hs300_stocks(self) -> List[Tuple[str, str]]:
        return HS300_CODES
    def _analyze_one(self, code: str, name: str) -> Optional[Dict]:
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
    def analyze_stock(self, code: str, name: str) -> Optional[Dict]:
        result = self._analyze_one(code, name)
        if result is None:
            with self._lock:
                self._completed += 1
            return None
        # === 基本面评分（核心新增）===
        fund_raw = self._fund_data.get(code, {})
        price = result.get('price', 0)
        fund_score = self.fund_scorer.score(fund_raw, price)
        result['fundamental_score'] = fund_score['total_score']
        result['fundamental_detail'] = fund_score['details']
        result['pe'] = fund_raw.get('pe')
        result['pb'] = fund_raw.get('pb')
        result['total_mv'] = fund_raw.get('total_mv')
        # === 三维度融合 ===
        tech_score = result['total_score']
        fund_score_val = result['fundamental_score']
        # 52周位置已包含在基本面评分中，这里直接融合
        composite = tech_score * 0.5 + fund_score_val * 0.5
        result['composite_score'] = composite
        # 更新建议等级
        if composite >= 3.5:
            result['advice'] = '强烈买入'; result['level'] = 5
        elif composite >= 1.5:
            result['advice'] = '建议买入'; result['level'] = 4
        elif composite <= -3.5:
            result['advice'] = '强烈卖出'; result['level'] = 1
        elif composite <= -1.5:
            result['advice'] = '建议卖出'; result['level'] = 2
        else:
            result['advice'] = '观望'; result['level'] = 3
        with self._lock:
            self._completed += 1
            progress = self._completed / self._total * 100
            sys.stdout.write(f"\r进度: {progress:.1f}% ({self._completed}/{self._total}) - 刚完成: {name}({code})    ")
            sys.stdout.flush()
        return result
    def run_analysis(self, top_n: int = 20):
        stocks = self.get_hs300_stocks()
        if not stocks:
            return
        # 第一步：批量获取全量基本面数据（仅1次网络请求，分批次）
        print("📊 正在通过腾讯API批量获取基本面数据(PE/PB/市值/52周高低点)...")
        all_codes = [c for c, _ in stocks]
        self._fund_data = self.fund_fetcher.fetch(all_codes)
        print(f"✅ 基本面数据获取完成，成功 {len(self._fund_data)} 只\n")
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
    def generate_report(self, top_n: int = 20):
        """生成分析报告"""
        if not self.results:
            print("❌ 没有有效的分析结果")
            return
        
        df = pd.DataFrame(self.results)
        df = df.sort_values('composite_score', ascending=False)
        
        buy_stocks = df[df['level'] >= 4].head(top_n)
        sell_stocks = df[df['level'] <= 2].sort_values('composite_score', ascending=True).head(top_n)
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("=" * 130)
        print(f"📊 沪深300成分股 技术+基本面 综合分析报告")
        print(f"生成时间: {now}")
        print("=" * 130)
        print(f"\n📈 市场概况:")
        print(f"  分析股票数: {len(df)}")
        print(f"  强烈买入/建议买入: {len(df[df['level'] >= 4])} 只")
        print(f"  强烈卖出/建议卖出: {len(df[df['level'] <= 2])} 只")
        print(f"  观望: {len(df[df['level'] == 3])} 只")
        # ==================== 买入建议 ====================
        if not buy_stocks.empty:
            print(f"\n{'='*130}")
            print(f"🟢 建议买入的股票（Top {min(top_n, len(buy_stocks))}）")
            print("=" * 130)
            print(f"{'代码':<8}{'名称':<10}{'现价':>8}{'涨幅':>8}{'综合分':>8}{'技术分':>8}{'基本面':>8}{'PE':>8}{'PB':>8}{'建议':<10}{'核心信号'}")
            print("-" * 130)
            for _, row in buy_stocks.iterrows():
                sig = ', '.join([f"{k}:{v}" for k, v in row['signals'].items() 
                                 if v not in ('震荡','中性','无明确形态','无明显形态','数据不足')])
                # 安全获取PE/PB，避免显示 'None'
                pe_val = row.get('pe')
                pb_val = row.get('pb')
                pe_str = f"{pe_val:.1f}" if pe_val is not None else "-"
                pb_str = f"{pb_val:.2f}" if pb_val is not None else "-"
                change_str = f"{row['change_pct']:+.2f}%"
                print(f"{row['code']:<8}{row['name']:<10}{row['price']:>8.2f}{change_str:>8}"
                      f"{row['composite_score']:>+8.2f}{row['total_score']:>+8.2f}{row['fundamental_score']:>+8.2f}"
                      f"{pe_str:>8}{pb_str:>8}{row['advice']:<10}{sig[:40]}")
        # ==================== 卖出建议 ====================
        if not sell_stocks.empty:
            print(f"\n{'='*130}")
            print(f"🔴 建议卖出的股票（Top {min(top_n, len(sell_stocks))}）")
            print("=" * 130)
            print(f"{'代码':<8}{'名称':<10}{'现价':>8}{'涨幅':>8}{'综合分':>8}{'技术分':>8}{'基本面':>8}{'PE':>8}{'PB':>8}{'建议':<10}{'核心信号'}")
            print("-" * 130)
            for _, row in sell_stocks.iterrows():
                sig = ', '.join([f"{k}:{v}" for k, v in row['signals'].items() 
                                 if v not in ('震荡','中性','无明确形态','无明显形态','数据不足')])
                pe_val = row.get('pe')
                pb_val = row.get('pb')
                pe_str = f"{pe_val:.1f}" if pe_val is not None else "-"
                pb_str = f"{pb_val:.2f}" if pb_val is not None else "-"
                change_str = f"{row['change_pct']:+.2f}%"
                print(f"{row['code']:<8}{row['name']:<10}{row['price']:>8.2f}{change_str:>8}"
                      f"{row['composite_score']:>+8.2f}{row['total_score']:>+8.2f}{row['fundamental_score']:>+8.2f}"
                      f"{pe_str:>8}{pb_str:>8}{row['advice']:<10}{sig[:40]}")
        # ==================== 保存结果 ====================
        output_file = f"hs300_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 完整分析结果已保存到: {output_file}")
        
        # ==================== 风险提示 ====================
        print(f"\n{'='*130}")
        print("⚠️  重要风险提示:")
        print("  1. 本分析基于技术指标与公开估值数据，不构成投资建议")
        print("  2. 技术指标存在滞后性，无法预测突发消息面影响")
        print("  3. 建议结合宏观环境、资金流向、政策面综合判断")
        print("  4. 严格执行仓位管理和止损纪律")
        print("  5. 股市有风险，投资需谨慎")
        print("=" * 130)

# ============================================================
# 入口
# ============================================================
def main():
    print("\n" + "=" * 120)
    print("🚀 沪深300成分股综合分析系统（技术+基本面融合版）")
    print("=" * 120)
    print("\n本程序将自动分析沪深300所有成分股，基于9大技术指标 + 估值/位置 筛选信号")
    print("技术指标：MA、MACD、KDJ、RSI、成交量、布林带、支撑/阻力、K线形态、价格形态")
    print("基本面维度：PE、PB、总市值、52周价格位置")
    print("数据源：腾讯财经 API\n")
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
