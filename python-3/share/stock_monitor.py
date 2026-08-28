#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股盯盘程序 - 监控沪深300及个股
功能：实时行情显示、涨跌幅监控、价格预警、桌面通知
数据源：腾讯财经 API（qt.gtimg.cn）
"""

import pandas as pd
import time
import re
import requests
from datetime import datetime
from collections import deque, defaultdict
import os
import sys
from typing import Dict, List, Optional, Tuple

# 尝试导入桌面通知库（可选）
try:
    from plyer import notification
    NOTIFICATION_AVAILABLE = True
except ImportError:
    NOTIFICATION_AVAILABLE = False
    print("提示：安装 plyer 可启用桌面通知 (pip install plyer)")

# 配置 requests Session
_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
})

# 腾讯财经行情 API 地址
TENCENT_API = "http://qt.gtimg.cn/q="

# 腾讯财经历史日K线 API（前复权）
TENCENT_KLINE_API = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

# 股票代码到腾讯财经代码的映射
# 上证：sh + 代码，深证：sz + 代码
# 指数：sh000300 等
def _to_tencent_code(code: str) -> str:
    """将通用代码转换为腾讯财经代码格式"""
    # 沪深300指数
    if code == "000300":
        return "sh000300"
    # 上证主板 (600xxx, 601xxx, 603xxx)
    if code.startswith(("60", "68")):
        return f"sh{code}"
    # 深证 (000xxx, 001xxx, 002xxx, 003xxx, 300xxx, 301xxx)
    return f"sz{code}"


class StockMonitor:
    """股票盯盘监控器"""
    
    def __init__(self):
        # 监控的股票列表（代码: 名称）
        self.watch_list = {
            '000300': '沪深300',  # 沪深300指数
            # 添加你关注的个股，格式：'股票代码': '股票名称'
            # 例如：
            # '600519': '贵州茅台',
            # '000858': '五粮液',
            # '601318': '中国平安',
            # '300750': '宁德时代',
        }
        
        # 预警设置
        self.alert_settings = {
            'price_change_pct': 3.0,   # 涨跌幅超过此百分比时预警
            'volume_ratio': 2.0,        # 量比超过此值时预警
        }
        
        # 买卖信号参数
        self.signal_params = {
            'strong_buy_score': 4,       # 综合评分 >= 此值为强买入
            'buy_score': 2,              # 综合评分 >= 此值为买入
            'strong_sell_score': -4,     # 综合评分 <= 此值为强卖出
            'sell_score': -2,            # 综合评分 <= 此值为卖出
            'breakout_pct': 2.0,         # 突破昨收/今开的百分比阈值
            'amplitude_alert': 5.0,      # 振幅预警阈值
            'v_reversal_pct': 2.0,       # V形反转阈值
            'volume_surge_ratio': 3.0,   # 放量倍数
            'price_volume_diverge': 1.5, # 量价背离阈值（价涨量缩或价跌量增）
        }
        
        # 历史数据（用于计算变化和趋势）
        self.history_data = {}       # code -> deque of (timestamp, price, volume) — 实时数据
        self.daily_history = {}      # code -> deque of (date, price, high, low, volume) — 日K线（指标计算专用）
        self.daily_volumes = {}      # code -> list of 近5日成交量（用于量比计算）
        self.signal_history = {}     # code -> deque of (timestamp, signal_type, score, reason)
        
        # 刷新间隔（秒）
        self.refresh_interval = 10
        
        # 预警记录（避免重复提醒）
        self.alerted_stocks = set()
        
        # 信号冷却期（秒），同一类型信号不重复发出
        self.signal_cooldown = {
            'buy': 300,      # 买入信号5分钟冷却
            'sell': 300,     # 卖出信号5分钟冷却
            'alert': 180,    # 预警信号3分钟冷却
        }
        self.last_signal_time = {}  # code -> {signal_type: timestamp}
        
        # 历史数据保留数量（MACD最长需要26周期）
        self.max_history_len = 50
    
    def add_stock(self, code: str, name: str):
        """添加监控股票"""
        self.watch_list[code] = name
        print(f"✓ 已添加监控：{name} ({code})")
    
    def remove_stock(self, code: str):
        """移除监控股票"""
        if code in self.watch_list:
            name = self.watch_list.pop(code)
            print(f"✓ 已移除监控：{name} ({code})")
        else:
            print(f"✗ 未找到股票：{code}")
    
    def _parse_tencent_data(self, raw: str, code: str, name: str) -> Optional[dict]:
        """解析腾讯财经返回的行情数据
        
        腾讯财经返回格式（以 ~ 分隔的字符串）：
        0:未知, 1:名称, 2:代码, 3:最新价, 4:昨收, 5:今开, 6:成交量(手),
        7:未知, 8:未知, 9:未知, 10:未知, 11:未知, 12:未知, 13:未知,
        14:未知, 15:未知, 16:未知, 17:未知, 18:未知, 19:未知, 20:未知,
        21:未知, 22:未知, 23:未知, 24:未知, 25:未知, 26:未知, 27:未知,
        28:未知, 29:未知, 30:时间, 31:涨跌额, 32:涨跌幅, 33:最高, 34:最低,
        35:最新价/成交量/成交额, 36:成交量(股), 37:成交额(万),
        38:换手率, 39:市盈率, 40:未知, 41:最高, 42:最低, 43:振幅,
        44:流通市值, 45:总市值, ...
        """
        try:
            # 从 "v_xxxx=\"...\"" 中提取数据
            match = re.search(r'"([^"]*)"', raw)
            if not match:
                return None
            data = match.group(1)
            fields = data.split("~")
            
            if len(fields) < 38:
                return None
            
            return {
                "代码": code,
                "名称": fields[1] if fields[1] else name,
                "最新价": float(fields[3]) if fields[3] else 0,
                "昨收": float(fields[4]) if fields[4] else 0,
                "今开": float(fields[5]) if fields[5] else 0,
                "成交量": float(fields[6]) if fields[6] else 0,  # 手
                "涨跌额": float(fields[31]) if fields[31] else 0,
                "涨跌幅": float(fields[32]) if fields[32] else 0,
                "最高": float(fields[33]) if fields[33] else 0,
                "最低": float(fields[34]) if fields[34] else 0,
                "成交额": float(fields[37]) if fields[37] else 0,  # 万元
            }
        except (ValueError, IndexError) as e:
            print(f"解析数据失败 [{code}]: {e}")
            return None

    def get_realtime_data(self) -> Optional[pd.DataFrame]:
        """获取实时行情数据（腾讯财经 API，带重试）"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                codes = list(self.watch_list.keys())
                tc_codes = [_to_tencent_code(c) for c in codes]
                url = TENCENT_API + ",".join(tc_codes)
                
                resp = _session.get(url, timeout=10)
                resp.encoding = "gbk"
                raw_text = resp.text
                
                # 腾讯财经一次返回所有代码的数据，用换行分隔
                lines = raw_text.strip().split("\n")
                results = []
                
                for i, code in enumerate(codes):
                    if i < len(lines):
                        row = self._parse_tencent_data(lines[i], code, self.watch_list[code])
                        if row:
                            results.append(row)
                
                if results:
                    return pd.DataFrame(results)
                return None
                
            except Exception as e:
                delay = 2 ** (attempt + 1)
                if attempt < max_retries - 1:
                    print(f"获取行情数据失败 (第{attempt + 1}/{max_retries}次): {e}，{delay}秒后重试...")
                    time.sleep(delay)
                else:
                    print(f"获取行情数据失败 (已达最大重试次数{max_retries}): {e}")
        
        return None
    
    def fetch_daily_kline(self, code: str, days: int = 60) -> List[dict]:
        """
        获取历史日K线数据（腾讯财经API，前复权）
        API: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600031,day,,,60,qfq
        返回: [{date, open, close, high, low, volume}, ...]
        注意：指数（如沪深300）可能不返回日K线，返回空列表
        """
        try:
            tc_code = _to_tencent_code(code)
            # param格式: 市场代码,day,,,天数,复权类型
            # qfq=前复权, hfq=后复权, 不填=不复权
            param = f"{tc_code},day,,,{days},qfq"
            
            resp = _session.get(TENCENT_KLINE_API, params={'param': param}, timeout=10)
            data = resp.json()
            
            if data.get('code') == 0 and data.get('data'):
                stock_data = data['data'].get(tc_code)
                if not stock_data:
                    return []
                
                # 取前复权日线数据: qfqday；指数（如沪深300）只返回 day 字段
                klines = stock_data.get('qfqday') or stock_data.get('day', [])
                if not klines:
                    return []
                
                result = []
                for line in klines:
                    # 格式: ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
                    # 注意：最后一条可能是个dict（含除权信息），需要跳过
                    if not isinstance(line, list) or len(line) < 6:
                        continue
                    try:
                        result.append({
                            'date': line[0],
                            'open': float(line[1]),
                            'close': float(line[2]),
                            'high': float(line[3]),
                            'low': float(line[4]),
                            'volume': float(line[5]),  # 手
                        })
                    except (ValueError, TypeError):
                        continue
                return result
            
        except Exception as e:
            print(f"获取 {code} 历史K线失败: {e}")
        
        return []
    
    def init_history_from_kline(self):
        """从历史日K线初始化历史数据，预热技术指标"""
        print("\n📥 正在加载历史日K线数据...")
        for code, name in self.watch_list.items():
            klines = self.fetch_daily_kline(code, days=60)
            if klines:
                if code not in self.daily_history:
                    self.daily_history[code] = deque(maxlen=self.max_history_len)
                
                for k in klines:
                    self.daily_history[code].append({
                        'date': k['date'],
                        'price': k['close'],
                        'volume': k['volume'],
                        'high': k['high'],
                        'low': k['low'],
                    })
                
                # 取最近5日的成交量用于量比计算
                recent_klines = klines[-5:]
                self.daily_volumes[code] = [k['volume'] for k in recent_klines]
                
                print(f"  ✓ {name}({code}) 加载 {len(klines)} 根日K线")
            else:
                print(f"  ✗ {name}({code}) 无法获取历史K线")
        
        print(f"📊 历史数据初始化完成，共 {len(self.daily_history)} 只股票\n")
    
    def check_alerts(self, df: pd.DataFrame):
        """检查预警条件"""
        if df is None or df.empty:
            return
        
        alerts = []
        
        for _, row in df.iterrows():
            code = row['代码']
            name = row['名称']
            change_pct = row.get('涨跌幅', 0)
            
            # 涨跌幅预警
            if abs(change_pct) >= self.alert_settings['price_change_pct']:
                alert_key = f"{code}_price"
                if alert_key not in self.alerted_stocks:
                    direction = "上涨" if change_pct > 0 else "下跌"
                    msg = f"⚠️ {name}({code}) {direction} {abs(change_pct):.2f}%"
                    alerts.append(msg)
                    self.alerted_stocks.add(alert_key)
                    
                    # 发送桌面通知
                    self.send_notification(
                        title=f"{name} {direction}预警",
                        message=f"当前涨跌幅: {change_pct:+.2f}%"
                    )
        
        # 打印预警信息
        if alerts:
            print("\n" + "="*60)
            print("🚨 预警信息")
            print("="*60)
            for alert in alerts:
                print(alert)
            print("="*60 + "\n")
    
    def send_notification(self, title: str, message: str):
        """发送桌面通知"""
        if NOTIFICATION_AVAILABLE:
            try:
                # plyer 在 Linux 上依赖 gdbus/notify-send
                # 如果系统没有 D-Bus 通知服务，静默跳过
                notification.notify(
                    title=title,
                    message=message,
                    app_name="A股盯盘助手",
                    timeout=10
                )
            except FileNotFoundError as e:
                # gdbus 或 notify-send 未安装，静默跳过
                pass
            except Exception as e:
                # 其他异常也只记录一次，避免刷屏
                if not hasattr(self, '_notify_error_logged'):
                    print(f"发送通知失败: {e}")
                    self._notify_error_logged = True
    
    # ================================================================
    #  买卖信号分析系统
    # ================================================================
    
    def _update_history(self, df: pd.DataFrame):
        """更新历史数据（实时tick + 日K线缓存）"""
        if df is None or df.empty:
            return
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        for _, row in df.iterrows():
            code = row['代码']
            price = row.get('最新价', 0)
            volume = row.get('成交量', 0)
            high = row.get('最高', price)
            low = row.get('最低', price)
            
            if code not in self.history_data:
                self.history_data[code] = deque(maxlen=self.max_history_len)
            self.history_data[code].append({
                'time': now,
                'price': price,
                'volume': volume,
                'high': high,
                'low': low,
            })
            
            # 同步更新日K线缓存：将当天的实时数据追加/替换到日K序列末尾
            # 这样 MACD/KDJ/RSI 等指标能反映盘中最新走势
            if code in self.daily_history and self.daily_history[code]:
                last_day = self.daily_history[code][-1]
                # 如果日K末尾已经是今天的数据，则更新它
                if last_day.get('date') == today_str:
                    last_day['price'] = price
                    last_day['high'] = max(last_day.get('high', price), high)
                    last_day['low'] = min(last_day.get('low', price), low)
                    last_day['volume'] = volume  # 当日累计成交量
                else:
                    # 新的交易日，追加一条
                    self.daily_history[code].append({
                        'date': today_str,
                        'price': price,
                        'high': high,
                        'low': low,
                        'volume': volume,
                    })
    
    def _is_in_cooldown(self, code: str, signal_type: str) -> bool:
        """检查信号是否在冷却期内"""
        if code not in self.last_signal_time:
            return False
        if signal_type not in self.last_signal_time[code]:
            return False
        cooldown_sec = self.signal_cooldown.get(signal_type, 300)
        elapsed = (datetime.now() - self.last_signal_time[code][signal_type]).total_seconds()
        return elapsed < cooldown_sec
    
    def _record_signal(self, code: str, signal_type: str, score: int, reason: str):
        """记录信号时间"""
        if code not in self.last_signal_time:
            self.last_signal_time[code] = {}
        self.last_signal_time[code][signal_type] = datetime.now()
        
        if code not in self.signal_history:
            self.signal_history[code] = deque(maxlen=20)
        self.signal_history[code].append({
            'time': datetime.now(),
            'type': signal_type,
            'score': score,
            'reason': reason,
        })
    
    # ---- 技术指标计算基础 ----
    def _get_price_history(self, code: str) -> List[float]:
        """获取某只股票的历史日K收盘价序列（用于技术指标计算）"""
        if code not in self.daily_history:
            return []
        return [h['price'] for h in self.daily_history[code]]
    
    def _get_high_history(self, code: str) -> List[float]:
        """获取某只股票的历史日K最高价序列"""
        if code not in self.daily_history:
            return []
        return [h.get('high', h['price']) for h in self.daily_history[code]]
    
    def _get_low_history(self, code: str) -> List[float]:
        """获取某只股票的历史日K最低价序列"""
        if code not in self.daily_history:
            return []
        return [h.get('low', h['price']) for h in self.daily_history[code]]
    
    def _calc_ema(self, data: List[float], period: int) -> List[float]:
        """计算指数移动平均 EMA"""
        if len(data) < period:
            return []
        k = 2 / (period + 1)
        ema = [sum(data[:period]) / period]  # 初始值用SMA
        for price in data[period:]:
            ema.append(price * k + ema[-1] * (1 - k))
        return [0] * (period - 1) + ema  # 补齐前面空位
    
    def _calc_sma(self, data: List[float], period: int) -> List[float]:
        """计算简单移动平均 SMA"""
        if len(data) < period:
            return []
        sma = []
        for i in range(len(data)):
            if i < period - 1:
                sma.append(0)
            else:
                sma.append(sum(data[i - period + 1:i + 1]) / period)
        return sma
    
    def _calc_macd(self, prices: List[float], fast=12, slow=26, signal=9) -> Tuple[List[float], List[float], List[float]]:
        """
        计算 MACD 指标
        返回: (DIF, DEA, MACD柱)
        """
        if len(prices) < slow:
            return [], [], []
        ema_fast = self._calc_ema(prices, fast)
        ema_slow = self._calc_ema(prices, slow)
        
        # DIF = EMA快 - EMA慢
        # 用索引判断有效性，避免真值判断误伤 0.0
        dif = []
        for i, (f, s) in enumerate(zip(ema_fast, ema_slow)):
            if i < slow - 1:
                dif.append(0.0)  # 前导无效部分
            else:
                dif.append(f - s)
        
        # 对 DIF 的有效部分计算 DEA（从 slow-1 位置开始才有意义）
        valid_start = slow - 1  # EMA慢线从slow-1位置开始有效
        valid_dif = dif[valid_start:]  # 去掉前导的无效部分
        
        if len(valid_dif) < signal:
            dea = [0] * len(dif)
            macd_bar = [0] * len(dif)
            return dif, dea, macd_bar
        
        dea_vals = self._calc_ema(valid_dif, signal)
        # DEA补齐到与DIF等长
        dea = [0] * valid_start + dea_vals
        
        macd_bar = [(dif[i] - dea[i]) * 2 for i in range(len(dif))]
        return dif, dea, macd_bar
    
    def _calc_kdj(self, code: str, prices: List[float], highs: List[float], lows: List[float], n=9) -> Tuple[float, float, float]:
        """
        计算 KDJ 指标
        返回: (K, D, J) 当前值
        """
        if len(prices) < n:
            return 50, 50, 50
        
        # 取最近 n 个周期
        recent_prices = prices[-n:]
        recent_highs = highs[-n:] if len(highs) >= n else prices[-n:]
        recent_lows = lows[-n:] if len(lows) >= n else prices[-n:]
        
        # 计算 RSV
        hn = max(recent_highs)
        ln = min(recent_lows)
        cn = recent_prices[-1]
        
        if hn == ln:
            rsv = 50
        else:
            rsv = (cn - ln) / (hn - ln) * 100
        
        # 递归计算 K, D, J（用前一次的值，首次用50）
        # 用独立的属性存储每个code的KDJ前值
        if not hasattr(self, '_kdj_prev'):
            self._kdj_prev = {}
        if code not in self._kdj_prev:
            self._kdj_prev[code] = {'k': 50, 'd': 50}
        
        prev = self._kdj_prev[code]
        k = 2/3 * prev['k'] + 1/3 * rsv
        d = 2/3 * prev['d'] + 1/3 * k
        j = 3 * k - 2 * d
        
        # 保存当前值供下次使用
        self._kdj_prev[code] = {'k': k, 'd': d}
        
        return k, d, j
    
    def _calc_rsi(self, prices: List[float], period=14) -> float:
        """计算 RSI 指标"""
        if len(prices) < period + 1:
            return 50
        
        gains = []
        losses = []
        for i in range(-period, 0):
            diff = prices[i] - prices[i - 1]
            if diff > 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calc_bollinger(self, prices: List[float], period=20, std_dev=2) -> Tuple[float, float, float, float]:
        """
        计算布林带指标
        返回: (中轨MA20, 上轨, 下轨, 带宽百分比)
              带宽% = (上轨-下轨)/中轨*100，越小越可能变盘
        """
        if len(prices) < period:
            return 0, 0, 0, 0
        
        ma = self._calc_sma(prices, period)
        if not ma or ma[-1] == 0:
            return 0, 0, 0, 0
        
        mid = ma[-1]
        # 计算标准差
        recent = prices[-period:]
        mean = sum(recent) / period
        variance = sum((x - mean) ** 2 for x in recent) / period
        std = variance ** 0.5
        
        upper = mid + std_dev * std
        lower = mid - std_dev * std
        bandwidth = (upper - lower) / mid * 100 if mid > 0 else 0
        
        return mid, upper, lower, bandwidth
    
    # ================================================================
    #  因子1: MA 均线 + 支撑阻力 + K线形态 信号（权重: ±6）
    #  趋势判断的核心因子，权重最大
    # ================================================================
    def _ma_signal(self, row) -> Tuple[int, str, int]:
        """
        MA 均线 + 支撑阻力 + K线形态综合分析：
        - MA5上穿MA10 → 金叉买入
        - MA5下穿MA10 → 死叉卖出
        - MA5>MA10>MA20 → 多头排列
        - MA5<MA10<MA20 → 空头排列
        - 价格与MA20关系 → 强弱分界
        - 前高/前低作为支撑阻力位
        - 连阳/连阴 K线形态识别
        - 长上影/长下影 单日反转形态
        - MA5/10/20收敛检测 → 变盘信号
        返回 (score, reason, trend_dir)
          trend_dir: 1=多头趋势, -1=空头趋势, 0=震荡
        """
        score = 0
        reasons = []
        
        code = row['代码']
        prices = self._get_price_history(code)
        highs = self._get_high_history(code)
        lows = self._get_low_history(code)
        
        if len(prices) < 22:
            return 0, "", 0
        
        ma5 = self._calc_sma(prices, 5)
        ma10 = self._calc_sma(prices, 10)
        ma20 = self._calc_sma(prices, 20)
        ma60 = self._calc_sma(prices, 60)
        
        if not ma5 or not ma10 or not ma20:
            return 0, "", 0
        
        cur_price = prices[-1]
        cur_ma5 = ma5[-1]
        cur_ma10 = ma10[-1]
        cur_ma20 = ma20[-1]
        prev_ma5 = ma5[-2] if len(ma5) >= 2 else cur_ma5
        prev_ma10 = ma10[-2] if len(ma10) >= 2 else cur_ma10
        prev_ma20 = ma20[-2] if len(ma20) >= 2 else cur_ma20
        
        trend_dir = 0  # 趋势方向：1多头 -1空头 0震荡
        
        # --- 均线排列（核心趋势判断，权重最大）---
        if cur_ma5 > cur_ma10 > cur_ma20 and cur_ma5 > 0:
            score += 3
            reasons.append("多头排列(MA5>MA10>MA20)")
            trend_dir = 1
            # 如果还有 MA60 且 MA20 > MA60，趋势更强
            if ma60 and ma60[-1] > 0 and cur_ma20 > ma60[-1]:
                score += 1
                reasons.append("中长期多头(MA20>MA60)")
        elif cur_ma5 < cur_ma10 < cur_ma20 and cur_ma5 > 0:
            score -= 3
            reasons.append("空头排列(MA5<MA10<MA20)")
            trend_dir = -1
            if ma60 and ma60[-1] > 0 and cur_ma20 < ma60[-1]:
                score -= 1
                reasons.append("中长期空头(MA20<MA60)")
        else:
            # 排列不明确，看价格与MA20关系
            if cur_price > cur_ma20 and cur_ma20 > prev_ma20:
                score += 1
                reasons.append("价格站上MA20且均线上行")
                trend_dir = 1
            elif cur_price < cur_ma20 and cur_ma20 < prev_ma20:
                score -= 1
                reasons.append("价格跌破MA20且均线下行")
                trend_dir = -1
        
        # --- 金叉/死叉（趋势确认信号）---
        # 金叉：MA5 上穿 MA10
        if prev_ma5 <= prev_ma10 and cur_ma5 > cur_ma10:
            if trend_dir >= 0:
                score += 2
                reasons.append("MA5↑上穿MA10 金叉")
            else:
                score += 1
                reasons.append("MA5↑上穿MA10 金叉(反弹)")
        # 死叉：MA5 下穿 MA10
        elif prev_ma5 >= prev_ma10 and cur_ma5 < cur_ma10:
            if trend_dir <= 0:
                score -= 2
                reasons.append("MA5↓下穿MA10 死叉")
            else:
                score -= 1
                reasons.append("MA5↓下穿MA10 死叉(回调)")
        
        # --- 价格与MA20关系（强弱分界线）---
        if cur_price > cur_ma20 * 1.02:
            if trend_dir > 0:
                score += 1
        elif cur_price < cur_ma20 * 0.98:
            if trend_dir < 0:
                score -= 1
        
        # --- 支撑/阻力位分析（前高前低 + MA20/MA60） ---
        if len(prices) >= 30:
            # 找最近20根K线（排除最新一根）的前高和前低
            lookback_prices = prices[-21:-1]  # 前20根
            lookback_highs = highs[-21:-1] if len(highs) >= 21 else lookback_prices
            lookback_lows = lows[-21:-1] if len(lows) >= 21 else lookback_prices
            
            recent_high = max(lookback_highs)
            recent_low = min(lookback_lows)
            
            # 突破前高：强势信号
            if cur_price > recent_high * 1.005:
                score += 2
                reasons.append(f"突破前高{recent_high:.2f}")
            # 跌破前低：弱势信号
            elif cur_price < recent_low * 0.995:
                score -= 2
                reasons.append(f"跌破前低{recent_low:.2f}")
            
            # MA20/MA60 作为支撑/阻力
            if trend_dir > 0 and cur_price > cur_ma20 and abs(cur_price - cur_ma20) / cur_ma20 < 0.02:
                score += 1
                reasons.append("回踩MA20支撑有效")
            elif trend_dir < 0 and cur_price < cur_ma20 and abs(cur_price - cur_ma20) / cur_ma20 < 0.02:
                score -= 1
                reasons.append("反弹受阻MA20")
        
        # --- 连阳/连阴 K线形态识别 ---
        if len(prices) >= 5:
            # 连阳检测（最近N根K线收盘 > 开盘的简化：用涨跌幅替代）
            consecutive_up = 0
            for i in range(-1, -6, -1):
                if abs(i) <= len(prices) and prices[i] > prices[i-1]:
                    consecutive_up += 1
                else:
                    break
            
            consecutive_down = 0
            for i in range(-1, -6, -1):
                if abs(i) <= len(prices) and prices[i] < prices[i-1]:
                    consecutive_down += 1
                else:
                    break
            
            if consecutive_up >= 3:
                score += 2 if consecutive_up >= 4 else 1
                reasons.append(f"{consecutive_up}连阳上攻")
            if consecutive_down >= 3:
                score -= 2 if consecutive_down >= 4 else 1
                reasons.append(f"{consecutive_down}连阴下杀")
        
        # --- 单日反转形态（长上影/长下影）---
        if len(highs) >= 1 and len(lows) >= 1:
            cur_high = highs[-1] if highs else cur_price
            cur_low = lows[-1] if lows else cur_price
            cur_open = row.get('今开', cur_price)
            
            if cur_open > 0 and cur_high > cur_low:
                candle_range = cur_high - cur_low
                if candle_range > 0:
                    # 上影线 = 最高 - max(开盘,收盘)
                    upper_shadow = cur_high - max(cur_open, cur_price)
                    # 下影线 = min(开盘,收盘) - 最低
                    lower_shadow = min(cur_open, cur_price) - cur_low
                    body = abs(cur_price - cur_open)
                    
                    # 长下影线（下影 > 实体*2 且 下影 > 上影*2）→ 单针探底
                    if lower_shadow > body * 2 and lower_shadow > upper_shadow * 2 and candle_range > 0:
                        if trend_dir <= 0:
                            score += 2
                            reasons.append("长下影线 单针探底✨")
                        else:
                            score += 1
                            reasons.append("长下影线 支撑确认")
                    
                    # 长上影线（上影 > 实体*2 且 上影 > 下影*2）→ 射击之星
                    if upper_shadow > body * 2 and upper_shadow > lower_shadow * 2 and candle_range > 0:
                        if trend_dir >= 0:
                            score -= 2
                            reasons.append("长上影线 射击之星⚠️")
                        else:
                            score -= 1
                            reasons.append("长上影线 反弹遇阻")
        
        # --- MA5/MA10/MA20 收敛检测（实战中最强的变盘信号之一）---
        # 当三条均线之间距离极近时，表示多空力量均衡，即将选择方向
        if cur_ma5 > 0 and cur_ma10 > 0 and cur_ma20 > 0:
            # 计算均线间最大距离与均值的比率
            ma_values = [cur_ma5, cur_ma10, cur_ma20]
            ma_avg = sum(ma_values) / 3
            max_divergence = max(abs(v - ma_avg) for v in ma_values)
            convergence_ratio = max_divergence / ma_avg if ma_avg > 0 else 1
            
            # 收敛率 < 1%：极度收敛，即将大变盘
            if convergence_ratio < 0.01:
                reasons.append(f"MA5/10/20极度收敛(发散率{convergence_ratio*100:.1f}%) 变盘在即")
                # 价格在均线上方则向上变盘概率大，下方则向下
                if cur_price > ma_avg:
                    score += 2
                    reasons.append("均线收敛+价格站上均线 向上变盘")
                    if trend_dir == 0:
                        trend_dir = 1
                else:
                    score -= 2
                    reasons.append("均线收敛+价格跌破均线 向下变盘")
                    if trend_dir == 0:
                        trend_dir = -1
            # 收敛率 < 2%：高度收敛
            elif convergence_ratio < 0.02:
                reasons.append(f"MA5/10/20高度收敛(发散率{convergence_ratio*100:.1f}%)")
                if cur_price > ma_avg:
                    score += 1
                    reasons.append("均线收敛偏多")
                else:
                    score -= 1
                    reasons.append("均线收敛偏空")
        
        return score, "；".join(reasons) if reasons else "", trend_dir
    
    # ================================================================
    #  因子2: MACD 信号（权重: ±5）
    #  新增：MACD柱连续缩短/放大，提前捕捉变盘信号
    #  背离信号降低权重（±3），需要成交量或金叉死叉确认
    # ================================================================
    def _macd_signal(self, row, trend_dir: int = 0) -> Tuple[int, str, float, float]:
        """
        MACD 分析：
        - DIF上穿DEA → 金叉（零下金叉更强）
        - DIF下穿DEA → 死叉（零上死叉更危险）
        - 底背离：价格创新低，DIF不创新低 → 看涨（需后续确认）
        - 顶背离：价格创新高，DIF不创新高 → 看跌（需后续确认）
        - DIF>0 → 多头市场
        - DIF<0 → 空头市场
        - MACD柱连续缩短（绿柱→红柱前夕）→ 提前看多
        - MACD柱连续放大 → 趋势加速确认
        返回 (score, reason, cur_dif, cur_dea)
        """
        score = 0
        reasons = []
        
        code = row['代码']
        prices = self._get_price_history(code)
        
        if len(prices) < 30:
            return 0, "", 0, 0
        
        dif, dea, macd_bar = self._calc_macd(prices)
        
        if len(dif) < 3 or len(macd_bar) < 3:
            return 0, "", 0, 0
        
        cur_dif = dif[-1]
        cur_dea = dea[-1]
        prev_dif = dif[-2] if len(dif) >= 2 else cur_dif
        prev_dea = dea[-2] if len(dea) >= 2 else cur_dea
        cur_bar = macd_bar[-1]
        prev_bar = macd_bar[-2] if len(macd_bar) >= 2 else cur_bar
        
        # --- 背离判断（实战中最强的反转信号）---
        lookback = min(20, len(prices) - 1)
        
        # 顶背离：价格创新高，但 DIF 不创新高
        price_high_20 = max(prices[-lookback-1:-1])
        dif_high_20 = max([d for d in dif[-lookback-1:-1] if d != 0] or [0])
        if prices[-1] > price_high_20 and cur_dif < dif_high_20 * 0.9:
            score -= 3
            reasons.append("⚠️MACD顶背离(价创新高DIF未创新高)")
        
        # 底背离：价格创新低，但 DIF 不创新低
        price_low_20 = min(prices[-lookback-1:-1])
        dif_low_20 = min([d for d in dif[-lookback-1:-1] if d != 0] or [float('inf')])
        if prices[-1] < price_low_20 and cur_dif > dif_low_20 * 1.1:
            score += 3
            reasons.append("✨MACD底背离(价创新低DIF未创新低)")
        
        # --- MACD柱连续变化（提前捕捉变盘）---
        if len(macd_bar) >= 4:
            bar_3ago = macd_bar[-3]
            bar_4ago = macd_bar[-4] if len(macd_bar) >= 4 else bar_3ago
            
            # 绿柱连续缩短（空头力量衰竭）→ 提前看多信号
            if cur_bar < 0 and cur_bar > prev_bar and prev_bar > bar_3ago:
                shorten_streak = 2
                if bar_3ago > bar_4ago and bar_4ago < 0:
                    shorten_streak = 3
                if shorten_streak >= 3:
                    score += 2
                    reasons.append("MACD绿柱持续缩短-空方衰竭")
                elif trend_dir >= 0:
                    score += 1
                    reasons.append("MACD绿柱缩短")
            
            # 红柱连续缩短（多头力量衰竭）→ 提前看空信号
            if cur_bar > 0 and cur_bar < prev_bar and prev_bar < bar_3ago:
                shorten_streak = 2
                if bar_3ago < bar_4ago and bar_4ago > 0:
                    shorten_streak = 3
                if shorten_streak >= 3:
                    score -= 2
                    reasons.append("MACD红柱持续缩短-多方衰竭")
                elif trend_dir <= 0:
                    score -= 1
                    reasons.append("MACD红柱缩短")
            
            # 红柱连续放大（多头加速）→ 趋势确认
            if cur_bar > 0 and cur_bar > prev_bar > bar_3ago > 0:
                if trend_dir > 0:
                    score += 1
                    reasons.append("MACD红柱放大-多头加速")
            
            # 绿柱连续放大（空头加速）→ 趋势确认
            if cur_bar < 0 and cur_bar < prev_bar < bar_3ago < 0:
                if trend_dir < 0:
                    score -= 1
                    reasons.append("MACD绿柱放大-空头加速")
        
        # --- 金叉/死叉 ---
        # 金叉：DIF 上穿 DEA
        if prev_dif <= prev_dea and cur_dif > cur_dea:
            if cur_dif < 0:
                score += 3
                reasons.append("DIF上穿DEA 零下金叉✨")
            else:
                score += 2
                reasons.append("DIF上穿DEA 金叉")
        
        # 死叉：DIF 下穿 DEA
        elif prev_dif >= prev_dea and cur_dif < cur_dea:
            if cur_dif > 0:
                score -= 3
                reasons.append("DIF下穿DEA 零上死叉⚠️")
            else:
                score -= 2
                reasons.append("DIF下穿DEA 死叉")
        
        # --- MACD 方向与趋势一致性 ---
        if cur_dif > 0 and cur_dif > cur_dea and macd_bar[-1] > 0:
            if trend_dir >= 0:
                score += 1
                reasons.append("MACD多头运行")
        elif cur_dif < 0 and cur_dif < cur_dea and macd_bar[-1] < 0:
            if trend_dir <= 0:
                score -= 1
                reasons.append("MACD空头运行")
        
        return score, "；".join(reasons) if reasons else "", cur_dif, cur_dea
    
    # ================================================================
    #  因子3: KDJ 信号（权重: ±2）
    #  震荡指标，需结合趋势方向避免钝化误判
    # ================================================================
    def _kdj_signal(self, row, trend_dir: int = 0) -> Tuple[int, str]:
        """
        KDJ 分析：
        - J<0 → 超卖区，可能反弹
        - J>100 → 超买区，可能回调（趋势向上时钝化，降低权重）
        - K上穿D且J<20 → 低位金叉（强买入）
        - K下穿D且J>80 → 高位死叉（强卖出）
        返回 (score, reason)
        """
        score = 0
        reasons = []
        
        code = row['代码']
        prices = self._get_price_history(code)
        highs = self._get_high_history(code)
        lows = self._get_low_history(code)
        
        if len(prices) < 9:
            return 0, ""
        
        # 获取前一次的K/D用于判断交叉
        prev_k = 50
        prev_d = 50
        if hasattr(self, '_kdj_prev') and code in self._kdj_prev:
            prev_k = self._kdj_prev[code].get('k', 50)
            prev_d = self._kdj_prev[code].get('d', 50)
        
        k, d, j = self._calc_kdj(code, prices, highs, lows)
        
        # --- 超卖区：趋势向下时超卖可能继续跌，降低信号强度 ---
        if j < 0:
            if trend_dir >= 0:
                score += 2
                reasons.append(f"KDJ超卖(J={j:.1f})")
            else:
                score += 1  # 趋势向下时钝化，降低权重
                reasons.append(f"KDJ超卖钝化(J={j:.1f})")
        elif j < 20:
            if trend_dir >= 0:
                score += 1
                reasons.append(f"KDJ低位(J={j:.1f})")
            # 趋势向下时低位不给分
        
        # --- 超买区：趋势向上时超买可能钝化，降低信号强度 ---
        if j > 100:
            if trend_dir <= 0:
                score -= 2
                reasons.append(f"KDJ超买(J={j:.1f})")
            else:
                score -= 1  # 趋势向上时钝化，降低权重
                reasons.append(f"KDJ超买钝化(J={j:.1f})")
        elif j > 80:
            if trend_dir <= 0:
                score -= 1
                reasons.append(f"KDJ高位(J={j:.1f})")
            # 趋势向上时高位不给分
        
        # --- 低位金叉：K上穿D 且 J < 20（强买入信号）---
        if prev_k <= prev_d and k > d and j < 20:
            score += 2
            reasons.append("KDJ低位金叉✨")
        
        # --- 高位死叉：K下穿D 且 J > 80（强卖出信号）---
        elif prev_k >= prev_d and k < d and j > 80:
            if trend_dir <= 0:
                score -= 2
                reasons.append("KDJ高位死叉⚠️")
            else:
                # 趋势向上时死叉可能是回调买点
                score -= 1
                reasons.append("KDJ高位死叉(强势回调)")
        
        return score, "；".join(reasons) if reasons else ""
    
    # ================================================================
    #  因子4: RSI 信号（权重: ±2）
    #  新增：趋势方向过滤，避免牛市超买/熊市超卖误判
    # ================================================================
    def _rsi_signal(self, row, trend_dir: int = 0) -> Tuple[int, str, float]:
        """
        RSI 分析：
        - RSI<20 → 严重超卖（强买入，但熊市中降低权重）
        - RSI<30 → 超卖（买入）
        - RSI>80 → 严重超买（强卖出，但牛市中降低权重）
        - RSI>70 → 超买（卖出）
        - 趋势过滤：牛市RSI>70是强势特征，熊市RSI<30是弱势特征
        返回 (score, reason, rsi_value)
        """
        score = 0
        reasons = []
        
        code = row['代码']
        prices = self._get_price_history(code)
        
        if len(prices) < 15:
            return 0, "", 50
        
        rsi = self._calc_rsi(prices)
        
        # 超卖区：趋势向下时钝化，降低买入信号强度
        if rsi <= 20:
            if trend_dir >= 0:
                score += 3
                reasons.append(f"RSI严重超卖({rsi:.1f})✨")
            else:
                score += 1  # 熊市超卖可能继续跌
                reasons.append(f"RSI严重超卖钝化({rsi:.1f})")
        elif rsi <= 30:
            if trend_dir >= 0:
                score += 2
                reasons.append(f"RSI超卖({rsi:.1f})")
            else:
                score += 1
                reasons.append(f"RSI超卖({rsi:.1f})")
        elif rsi <= 35:
            if trend_dir >= 0:
                score += 1
                reasons.append(f"RSI偏低({rsi:.1f})")
        
        # 超买区：趋势向上时钝化，降低卖出信号强度
        if rsi >= 80:
            if trend_dir <= 0:
                score -= 3
                reasons.append(f"RSI严重超买({rsi:.1f})⚠️")
            else:
                score -= 1  # 牛市超买是强势特征
                reasons.append(f"RSI严重超买-强势({rsi:.1f})")
        elif rsi >= 70:
            if trend_dir <= 0:
                score -= 2
                reasons.append(f"RSI超买({rsi:.1f})")
            # 牛市RSI>70不扣分
        elif rsi >= 65:
            if trend_dir <= 0:
                score -= 1
                reasons.append(f"RSI偏高({rsi:.1f})")
        
        # RSI 背离检测（简化版）
        if len(prices) >= 16:
            # 找最近14根的前高和前低（排除最新一根）
            lookback_prices = prices[-15:-1]
            prev_rsi_high = 50  # 简化：用RSI历史值
            prev_rsi_low = 50
            
            # RSI顶背离：价格新高 RSI不新高
            if prices[-1] > max(lookback_prices) and rsi < 65:
                score -= 1
                reasons.append(f"RSI顶背离({rsi:.1f})")
            # RSI底背离：价格新低 RSI不新低
            if prices[-1] < min(lookback_prices) and rsi > 35:
                score += 1
                reasons.append(f"RSI底背离({rsi:.1f})")
        
        return score, "；".join(reasons) if reasons else "", rsi
    
    # ================================================================
    #  因子5: 布林带信号（权重: ±2）
    #  判断价格极端位置、带宽收窄变盘
    # ================================================================
    def _bollinger_signal(self, row, trend_dir: int = 0) -> Tuple[int, str, Tuple[float, float, float, float]]:
        """
        布林带分析：
        - 价格突破上轨 → 超买（但趋势向上时可能是加速）
        - 价格跌破下轨 → 超卖（但趋势向下时可能是加速）
        - 价格沿上轨运行 → 强势特征
        - 价格沿下轨运行 → 弱势特征
        - 带宽收窄（<5%）→ 即将变盘
        - 带宽扩张 → 趋势加速
        返回 (score, reason, (mid, upper, lower, bandwidth))
        """
        score = 0
        reasons = []
        
        code = row['代码']
        prices = self._get_price_history(code)
        cur_price = prices[-1] if prices else 0
        
        if len(prices) < 21:
            return 0, "", (0, 0, 0, 0)
        
        mid, upper, lower, bandwidth = self._calc_bollinger(prices)
        
        if mid == 0:
            return 0, "", (0, 0, 0, 0)
        
        # 价格相对布林带的位置（%b = (price - lower) / (upper - lower)）
        if upper > lower:
            pct_b = (cur_price - lower) / (upper - lower)
        else:
            pct_b = 0.5
        
        # --- 突破上轨 ---
        if cur_price > upper:
            if trend_dir > 0:
                # 趋势向上时突破上轨是强势加速
                score += 2
                reasons.append(f"突破布林上轨 强势加速")
            else:
                # 趋势不明确时突破上轨可能超买
                score -= 1
                reasons.append(f"突破布林上轨 警惕回落")
        
        # --- 跌破下轨 ---
        if cur_price < lower:
            if trend_dir < 0:
                # 趋势向下时跌破下轨是弱势加速
                score -= 2
                reasons.append(f"跌破布林下轨 弱势加速")
            else:
                # 趋势不明确时跌破下轨可能超卖反弹
                score += 1
                reasons.append(f"跌破布林下轨 超卖反弹")
        
        # --- 价格沿上轨运行（强势特征）---
        if pct_b > 0.8 and trend_dir > 0:
            # 连续3根在0.8以上
            if len(prices) >= 3:
                prices_3 = prices[-3:]
                mid_vals = self._calc_sma(prices, 20)
                if mid_vals and len(mid_vals) >= 3:
                    b_vals = []
                    for i in range(-3, 0):
                        m = mid_vals[i]
                        # 简化：用固定std估算
                        if m > 0:
                            est_upper = m * 1.05  # 估算上轨
                            est_lower = m * 0.95  # 估算下轨
                            if est_upper > est_lower:
                                b_vals.append((prices[i] - est_lower) / (est_upper - est_lower))
                    if len(b_vals) >= 3 and all(b > 0.75 for b in b_vals):
                        score += 1
                        reasons.append("沿布林上轨运行 极强势")
        
        # --- 价格沿下轨运行（弱势特征）---
        if pct_b < 0.2 and trend_dir < 0:
            score -= 1
            reasons.append("沿布林下轨运行 极弱势")
        
        # --- 带宽收窄（变盘信号）---
        if bandwidth < 5:
            # 带宽<5%表示波动率极低，即将变盘
            # 趋势向上时变盘向上概率大，反之亦然
            if trend_dir > 0:
                score += 1
                reasons.append(f"布林带宽收窄({bandwidth:.1f}%) 蓄势向上")
            elif trend_dir < 0:
                score -= 1
                reasons.append(f"布林带宽收窄({bandwidth:.1f}%) 警惕下破")
            else:
                reasons.append(f"布林带宽收窄({bandwidth:.1f}%) 即将变盘")
        
        # --- 带宽扩张（趋势加速）---
        if bandwidth > 15:
            if trend_dir > 0:
                score += 1
                reasons.append(f"布林带宽扩张({bandwidth:.1f}%) 趋势加速")
            elif trend_dir < 0:
                score -= 1
                reasons.append(f"布林带宽扩张({bandwidth:.1f}%) 下跌加速")
        
        return score, "；".join(reasons) if reasons else "", (mid, upper, lower, bandwidth)
    
    # ================================================================
    #  因子6: 成交量信号（权重: ±3）
    #  量在价先，是最不可操控的指标，提升权重
    # ================================================================
    def _volume_signal(self, row, trend_dir: int = 0) -> Tuple[int, str]:
        """
        成交量分析：
        - 量比 = 当日实时累计成交量 / 过去5日均量
        - 放量上涨 → 买入信号（趋势向上时确认）
        - 放量下跌 → 卖出信号（趋势向下时确认）
        - 缩量上涨 → 量价背离，需警惕
        - 缩量下跌 → 洗盘概率大
        - 放量滞涨（量大价不涨）→ 顶部信号
        - 连续缩量后放量（地量见地价）→ 变盘信号
        - 量堆（连续3天以上放量）→ 资金介入信号
        返回 (score, reason)
        """
        score = 0
        reasons = []
        
        code = row['代码']
        volume = row.get('成交量', 0)
        change_pct = row.get('涨跌幅', 0)
        
        if volume == 0:
            return 0, ""
        
        # 量比 = 当日实时累计成交量 / 过去5日均量
        if code in self.daily_volumes and self.daily_volumes[code]:
            avg_vol = sum(self.daily_volumes[code]) / len(self.daily_volumes[code])
            if avg_vol > 0:
                vol_ratio = volume / avg_vol
                
                # --- 连续缩量后放量（地量见地价，关键变盘信号）---
                # 检查日K线历史成交量序列是否连续缩量
                if code in self.daily_history and len(self.daily_history[code]) >= 5:
                    daily_vols = [h.get('volume', 0) for h in list(self.daily_history[code])[-6:-1]]
                    # 前4天连续缩量（每根比前一根小）
                    if len(daily_vols) >= 4 and all(daily_vols[i] > 0 for i in range(len(daily_vols))):
                        is_shrinking = all(daily_vols[i] < daily_vols[i-1] * 0.9 for i in range(1, len(daily_vols)))
                        if is_shrinking and vol_ratio >= 1.5:
                            if change_pct > 0:
                                score += 3
                                reasons.append(f"连续缩量后放量上攻 地量见地价✨")
                            elif change_pct < 0:
                                score -= 2
                                reasons.append(f"连续缩量后放量下杀 方向选择向下")
                
                # --- 量堆识别（连续放量区域）---
                if code in self.daily_history and len(self.daily_history[code]) >= 4:
                    recent_vols = [h.get('volume', 0) for h in list(self.daily_history[code])[-4:]]
                    if len(recent_vols) >= 3:
                        all_above_avg = all(v > avg_vol * 1.2 for v in recent_vols if v > 0)
                        if all_above_avg:
                            if trend_dir > 0:
                                score += 2
                                reasons.append("量堆形成 资金持续介入")
                
                # 放量上涨（量比 > 2）：量价齐升，趋势确认
                if vol_ratio >= 2 and change_pct > 0:
                    if trend_dir >= 0:
                        score += 2
                        reasons.append(f"放量上涨(量比{vol_ratio:.1f})")
                    else:
                        score += 1
                        reasons.append(f"放量反弹(量比{vol_ratio:.1f})")
                
                # 放量下跌（量比 > 2）：量价齐跌，趋势确认
                elif vol_ratio >= 2 and change_pct < 0:
                    if trend_dir <= 0:
                        score -= 2
                        reasons.append(f"放量下跌(量比{vol_ratio:.1f})")
                    else:
                        score -= 1
                        reasons.append(f"放量回调(量比{vol_ratio:.1f})")
                
                # 放量滞涨（量大但涨不动）→ 顶部信号
                elif vol_ratio >= 2 and abs(change_pct) < 0.5:
                    score -= 3
                    reasons.append(f"放量滞涨⚠️(量比{vol_ratio:.1f})")
                
                # 缩量下跌（量比 < 0.6）：洗盘概率大
                elif vol_ratio <= 0.6 and change_pct < 0:
                    if trend_dir >= 0:
                        score += 1
                        reasons.append(f"缩量下跌-洗盘(量比{vol_ratio:.1f})")
                
                # 温和放量上涨
                elif vol_ratio >= 1.5 and change_pct > 0:
                    if trend_dir >= 0:
                        score += 1
                        reasons.append(f"温和放量(量比{vol_ratio:.1f})")
                
                # 缩量上涨（量价背离，警惕）
                elif vol_ratio <= 0.6 and change_pct > 1:
                    if trend_dir >= 0:
                        pass
                    else:
                        score -= 1
                        reasons.append(f"缩量上涨-量价背离(量比{vol_ratio:.1f})")
        
        return score, "；".join(reasons) if reasons else ""
    
    # ---- 综合信号评分 ----
    def _calculate_total_score(self, row) -> Tuple[int, str, List[str], dict]:
        """
        综合多因子打分，生成买卖信号
        
        核心逻辑：
        1. 先判断趋势方向（均线排列 + 价格位置）
        2. 趋势信号（MA/MACD）权重较高，决定主方向
        3. 震荡信号（KDJ/RSI/布林带）权重较低，辅助确认，趋势过滤
        4. 成交量信号确认趋势有效性（量在价先，权重提升）
        5. 多空冲突时，趋势方向优先
        6. 信号共振加成：多因子同向时额外加分
        7. 时间衰减：旧的K线形态信号权重递减
        
        因子权重:
          MA均线:  ±6  (排列/交叉/支撑阻力/K线形态/均线收敛) — 趋势核心
          MACD:    ±5  (金叉/死叉/背离/零轴/柱变化) — 趋势确认
          KDJ:     ±2  (超买/超卖/交叉) — 辅助，趋势过滤
          RSI:     ±2  (超买/超卖/背离) — 辅助，趋势过滤
          布林带:   ±2  (突破/带宽/沿轨运行) — 极端位置判断
          成交量:   ±3  (放量/缩量/量堆/地量) — 确认（最不可操控指标）
        
        返回 (总分, 信号等级, 详细原因列表, 指标值字典)
        """
        total_score = 0
        all_reasons = []
        indicators = {}
        
        # === 第一层：趋势方向判断（MA均线 + 支撑阻力 + K线形态） ===
        score, reason, trend_dir = self._ma_signal(row)
        total_score += score
        if reason:
            all_reasons.append(f"[MA]{reason}")
        indicators['trend_dir'] = trend_dir
        
        # === 第二层：MACD 趋势确认（含背离、柱变化方向） ===
        score, reason, macd_dif, macd_dea = self._macd_signal(row, trend_dir)
        total_score += score
        if reason:
            all_reasons.append(f"[MACD]{reason}")
        indicators['macd_dif'] = macd_dif
        indicators['macd_dea'] = macd_dea
        
        # === 第三层：KDJ 辅助判断（趋势过滤钝化） ===
        score, reason = self._kdj_signal(row, trend_dir)
        total_score += score
        if reason:
            all_reasons.append(f"[KDJ]{reason}")
        code = row['代码']
        if hasattr(self, '_kdj_prev') and code in self._kdj_prev:
            kdj = self._kdj_prev[code]
            indicators['kdj_k'] = kdj.get('k', 50)
            indicators['kdj_d'] = kdj.get('d', 50)
            indicators['kdj_j'] = 3 * indicators['kdj_k'] - 2 * indicators['kdj_d']
        
        # === 第四层：RSI 辅助判断（趋势过滤） ===
        score, reason, rsi_val = self._rsi_signal(row, trend_dir)
        total_score += score
        if reason:
            all_reasons.append(f"[RSI]{reason}")
        indicators['rsi'] = rsi_val
        
        # === 第五层：布林带（极端位置/变盘判断） ===
        score, reason, boll = self._bollinger_signal(row, trend_dir)
        total_score += score
        if reason:
            all_reasons.append(f"[布林]{reason}")
        indicators['boll_mid'] = boll[0]
        indicators['boll_bandwidth'] = boll[3]
        
        # === 第六层：成交量确认 ===
        score, reason = self._volume_signal(row, trend_dir)
        total_score += score
        if reason:
            all_reasons.append(f"[量能]{reason}")
        
        # === 信号共振加成（多因子同向确认时额外加分） ===
        # 统计有实际信号输出的因子数
        seen_factors = set()
        for r in all_reasons:
            for prefix in ['[MA]', '[MACD]', '[KDJ]', '[RSI]', '[布林]', '[量能]']:
                if r.startswith(prefix) and prefix not in seen_factors:
                    seen_factors.add(prefix)
                    break
        
        # 至少3个因子同向 → 共振加成
        if len(seen_factors) >= 3:
            if total_score > 0:
                bonus = min(len(seen_factors) - 2, 3)  # 3因子+1, 4因子+2, 5因子+3
                total_score += bonus
                all_reasons.append(f"[共振]{len(seen_factors)}因子共振看多 +{bonus}")
            elif total_score < 0:
                bonus = min(len(seen_factors) - 2, 3)
                total_score -= bonus
                all_reasons.append(f"[共振]{len(seen_factors)}因子共振看空 -{bonus}")
        
        # === 时间衰减：对旧K线形态信号（连阳/连阴/长影线）衰减 ===
        # 4日前开始的连阳/连阴，信号强度衰减
        time_sensitive_signals = ['连阳', '连阴', '长下影', '长上影']
        has_time_sensitive = any(any(kw in r for kw in time_sensitive_signals) for r in all_reasons)
        if has_time_sensitive:
            # 检查是否有4连阳/4连阴这种早期开始的信号
            for r in all_reasons:
                if '4连阳' in r or '4连阴' in r:
                    if total_score > 0:
                        total_score -= 1
                    elif total_score < 0:
                        total_score += 1
                    all_reasons.append("[衰减]多日前K线形态信号时间衰减")
                    break
        
        # === 大盘环境加成（沪深300 作为市场风向标）===
        # 如果监控列表中有沪深300，利用它来调整个股信号
        market_trend = 0
        if '000300' in self.watch_list and code != '000300':
            # 获取沪深300的趋势方向
            market_prices = self._get_price_history('000300')
            if len(market_prices) >= 22:
                market_ma20 = self._calc_sma(market_prices, 20)
                if market_ma20 and market_ma20[-1] > 0:
                    market_change = (market_prices[-1] - market_prices[-2]) / market_prices[-2] if len(market_prices) >= 2 and market_prices[-2] > 0 else 0
                    if market_prices[-1] > market_ma20[-1]:
                        market_trend = 1  # 大盘在MA20上方
                    elif market_prices[-1] < market_ma20[-1]:
                        market_trend = -1  # 大盘在MA20下方
            
            # 大盘向好时，个股买入信号加成
            if market_trend > 0 and total_score > 0:
                total_score += 2
                all_reasons.append("[大盘]大盘强势 信号加成")
            # 大盘走弱时，个股卖出信号加成
            elif market_trend < 0 and total_score < 0:
                total_score -= 2
                all_reasons.append("[大盘]大盘弱势 信号加成")
            # 逆势上涨（大盘跌个股涨）：强于大盘，加分
            elif market_trend < 0 and total_score > 0:
                total_score += 2
                all_reasons.append("[大盘]逆势走强 强于大盘")
            # 逆势下跌（大盘涨个股跌）：弱于大盘，减分
            elif market_trend > 0 and total_score < 0:
                total_score -= 2
                all_reasons.append("[大盘]逆势走弱 弱于大盘")
        
        # === 多空冲突检测：趋势方向优先 ===
        if trend_dir > 0 and total_score <= 0:
            total_score = max(total_score, 0)
        elif trend_dir < 0 and total_score >= 0:
            total_score = min(total_score, 0)
        
        # 确定信号等级
        params = self.signal_params
        if total_score >= params['strong_buy_score']:
            level = "🟢 强买入"
        elif total_score >= params['buy_score']:
            level = "🔵 买入"
        elif total_score <= params['strong_sell_score']:
            level = "🔴 强卖出"
        elif total_score <= params['sell_score']:
            level = "🟠 卖出"
        else:
            level = "⚪ 观望"
        
        return total_score, level, all_reasons, indicators
    
    def analyze_signals(self, df: pd.DataFrame, precomputed_scores: dict = None):
        """分析买卖信号并显示
        
        Args:
            df: 实时行情数据
            precomputed_scores: 预计算的评分结果 {code: (total_score, level, reasons, indicators)}
                                由 display_data 传入，避免重复计算
        """
        if df is None or df.empty:
            return
        
        signals_output = []
        alert_output = []
        
        for _, row in df.iterrows():
            code = row['代码']
            name = row['名称']
            price = row.get('最新价', 0)
            change_pct = row.get('涨跌幅', 0)
            
            # 使用预计算的评分（避免重复计算，尤其是KDJ的状态污染）
            if precomputed_scores and code in precomputed_scores:
                total_score, level, reasons, indicators = precomputed_scores[code]
            else:
                total_score, level, reasons, indicators = self._calculate_total_score(row)
            
            # 检查是否需要发出信号
            signal_type = None
            if total_score >= self.signal_params['strong_buy_score']:
                signal_type = 'strong_buy'
            elif total_score >= self.signal_params['buy_score']:
                signal_type = 'buy'
            elif total_score <= self.signal_params['strong_sell_score']:
                signal_type = 'strong_sell'
            elif total_score <= self.signal_params['sell_score']:
                signal_type = 'sell'
            
            # 检查冷却期（按 buy/sell 大类冷却）
            cooldown_key = 'buy' if signal_type and 'buy' in signal_type else ('sell' if signal_type and 'sell' in signal_type else None)
            should_emit = cooldown_key and not self._is_in_cooldown(code, cooldown_key)
            
            if signal_type:
                signals_output.append({
                    'code': code,
                    'name': name,
                    'price': price,
                    'change_pct': change_pct,
                    'score': total_score,
                    'level': level,
                    'reasons': reasons,
                    'should_emit': should_emit,
                })
            
            # 涨跌幅预警（保留原有逻辑，但用冷却机制避免刷屏）
            if abs(change_pct) >= self.alert_settings['price_change_pct']:
                if not self._is_in_cooldown(code, 'alert'):
                    direction = "上涨" if change_pct > 0 else "下跌"
                    alert_output.append({
                        'code': code,
                        'name': name,
                        'change_pct': change_pct,
                        'direction': direction,
                    })
                    self._record_signal(code, 'alert', 0, f"涨跌幅预警 {change_pct:+.2f}%")
        
        # 显示买卖信号
        if signals_output:
            print("\n" + "=" * 80)
            print("📊 买卖信号分析")
            print("=" * 80)
            
            for sig in signals_output:
                code = sig['code']
                name = sig['name']
                price = sig['price']
                change_pct = sig['change_pct']
                score = sig['score']
                level = sig['level']
                reasons = sig['reasons']
                should_emit = sig['should_emit']
                
                # 颜色
                if score > 0:
                    color = "\033[91m"  # 红（看多）
                elif score < 0:
                    color = "\033[92m"  # 绿（看空）
                else:
                    color = "\033[0m"
                reset = "\033[0m"
                
                # 新信号标记
                new_tag = "🆕 " if should_emit else "   "
                
                print(f"\n{new_tag}{color}{name}({code}) | 现价: {price:.2f} | 涨跌: {change_pct:+.2f}%")
                print(f"   评分: {score:+d} | 信号: {level}{reset}")
                if reasons:
                    for r in reasons:
                        print(f"   └ {r}")
                
                # 发出新信号时记录
                if should_emit:
                    cooldown_key = 'buy' if score >= self.signal_params['buy_score'] else 'sell'
                    self._record_signal(code, cooldown_key, score, level)
                    self.send_notification(
                        title=f"{level} - {name}",
                        message=f"现价:{price:.2f} 涨跌:{change_pct:+.2f}% 评分:{score:+d}"
                    )
            
            print("\n" + "=" * 80)
        
        # 显示涨跌幅预警
        if alert_output:
            print("\n" + "-" * 60)
            print("🚨 涨跌幅预警")
            print("-" * 60)
            for alert in alert_output:
                print(f"  ⚠️ {alert['name']}({alert['code']}) {alert['direction']} {abs(alert['change_pct']):.2f}%")
            print("-" * 60 + "\n")
    
    def format_number(self, value, decimals=2):
        """格式化数字显示"""
        if pd.isna(value):
            return "--"
        if abs(value) >= 1e8:
            return f"{value/1e8:.{decimals}f}亿"
        elif abs(value) >= 1e4:
            return f"{value/1e4:.{decimals}f}万"
        else:
            return f"{value:.{decimals}f}"
    
    def display_data(self, df: pd.DataFrame) -> dict:
        """显示行情数据（含信号评分），返回预计算的评分供 analyze_signals 复用"""
        if df is None or df.empty:
            print("暂无数据")
            return {}
        
        # 清屏（可选）
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # 显示时间
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n{'='*120}")
        print(f"📊 A股盯盘助手 | 更新时间: {now}  |  引擎: MA+MACD+KDJ+RSI+布林+量能+大盘+共振")
        print(f"{'='*120}\n")
        
        # 表头
        header = f"{'代码':<8} {'名称':<8} {'最新价':>8} {'涨跌幅':>8} {'涨跌额':>8} {'评分':>5} {'信号':<8} {'MA':<5} {'MACD':<5} {'KDJ':<5} {'RSI':<5} {'布林':<5} {'量能':<5}"
        print(header)
        print("-" * 120)
        
        precomputed_scores = {}
        
        # 数据行
        for _, row in df.iterrows():
            code = row['代码']
            name = row['名称']
            price = row.get('最新价', 0)
            change_pct = row.get('涨跌幅', 0)
            change_amt = row.get('涨跌额', 0)
            
            # 计算评分和各指标（只算一次，KDJ等有副作用的指标不会重复计算）
            total_score, level, reasons, indicators = self._calculate_total_score(row)
            precomputed_scores[code] = (total_score, level, reasons, indicators)
            
            # 从指标字典获取摘要
            ma_str = "-"
            macd_str = "-"
            kdj_str = "-"
            rsi_str = "-"
            boll_str = "-"
            vol_str = "-"
            
            # MA 摘要：从已有数据重新算 SMA（无副作用）
            prices = self._get_price_history(code)
            if len(prices) >= 20:
                ma5_vals = self._calc_sma(prices, 5)
                ma10_vals = self._calc_sma(prices, 10)
                if ma5_vals and ma10_vals and ma5_vals[-1] and ma10_vals[-1]:
                    ma_str = "多" if ma5_vals[-1] > ma10_vals[-1] else "空"
            
            # MACD 摘要
            if 'macd_dif' in indicators and 'macd_dea' in indicators:
                macd_str = "金" if indicators['macd_dif'] > indicators['macd_dea'] else "死"
            
            # KDJ 摘要
            if 'kdj_j' in indicators:
                j = indicators['kdj_j']
                if j < 0:
                    kdj_str = "超卖"
                elif j > 100:
                    kdj_str = "超买"
                else:
                    kdj_str = "正常"
            
            # RSI 摘要
            if 'rsi' in indicators:
                rsi = indicators['rsi']
                if rsi <= 30:
                    rsi_str = f"{rsi:.0f}超卖"
                elif rsi >= 70:
                    rsi_str = f"{rsi:.0f}超买"
                else:
                    rsi_str = f"{rsi:.0f}"
            
            # 布林带摘要
            if 'boll_bandwidth' in indicators and indicators['boll_mid'] > 0:
                bw = indicators['boll_bandwidth']
                mid = indicators['boll_mid']
                if bw < 5:
                    boll_str = f"{bw:.0f}%收窄"
                elif bw > 15:
                    boll_str = f"{bw:.0f}%扩张"
                else:
                    pct_pos = (price - mid) / mid * 100 if mid > 0 else 0
                    boll_str = f"{pct_pos:+.0f}%"
            
            # 量能摘要
            vol = row.get('成交量', 0)
            if code in self.daily_volumes and self.daily_volumes[code]:
                avg_vol = sum(self.daily_volumes[code]) / len(self.daily_volumes[code])
                if avg_vol > 0:
                    vol_ratio = vol / avg_vol
                    if vol_ratio >= 2:
                        vol_str = "放量"
                    elif vol_ratio <= 0.6:
                        vol_str = "缩量"
                    elif vol_ratio >= 1.3:
                        vol_str = "温和"
                    else:
                        vol_str = "正常"
            
            # 颜色标记
            if change_pct > 0:
                color = "\033[91m"
            elif change_pct < 0:
                color = "\033[92m"
            else:
                color = "\033[0m"
            
            if total_score >= self.signal_params['buy_score']:
                sig_color = "\033[91m"
            elif total_score <= self.signal_params['sell_score']:
                sig_color = "\033[92m"
            else:
                sig_color = ""
            
            reset = "\033[0m"
            
            # 格式化输出
            line = (
                f"{color}{code:<8} {name:<8} {price:>8.2f} {change_pct:>+7.2f}% "
                f"{change_amt:>+8.2f} {sig_color}{total_score:>+4d}  {level:<6}{reset}"
                f" {ma_str:<5} {macd_str:<5} {kdj_str:<5} {rsi_str:<5} {boll_str:<5} {vol_str:<5}"
            )
            print(line)
        
        print("-" * 120)
        
        # 显示统计信息
        up_count = len(df[df['涨跌幅'] > 0])
        down_count = len(df[df['涨跌幅'] < 0])
        flat_count = len(df[df['涨跌幅'] == 0])
        
        print(f"\n📈 上涨: {up_count} | 📉 下跌: {down_count} | ➖ 平盘: {flat_count}")
        print(f"⏱️  下次刷新: {self.refresh_interval}秒后")
        print(f"💡 提示: 按 Ctrl+C 退出程序\n")
        
        return precomputed_scores
    
    def run(self):
        """运行盯盘程序"""
        print("\n🚀 A股盯盘助手启动中...")
        print(f"📋 监控列表: {len(self.watch_list)} 只股票/指数")
        print(f"⚠️  预警阈值: 涨跌幅 ±{self.alert_settings['price_change_pct']}%")
        print(f"📊 信号引擎: MA均线+MACD+KDJ+RSI+布林带+成交量+大盘环境")
        print(f"   因子: MA(排列/金叉死叉/支撑阻力/K线形态)")
        print(f"         MACD(金叉死叉/背离/柱变化方向)")
        print(f"         KDJ(超买超卖/金叉死叉 趋势过滤钝化)")
        print(f"         RSI(超买超卖/背离 趋势过滤)")
        print(f"         布林带(突破/带宽收窄变盘/沿轨运行)")
        print(f"         成交量(放量/缩量/量堆/地量见地价)")
        print(f"         大盘(沪深300环境加成 ±2)")
        print(f"         均线收敛检测 + 因子共振加成 + 时间衰减")
        print(f"   🟢强买入≥{self.signal_params['strong_buy_score']} 🔵买入≥{self.signal_params['buy_score']}")
        print(f"   🟠卖出≤{self.signal_params['sell_score']} 🔴强卖出≤{self.signal_params['strong_sell_score']}")
        print(f"🔄 刷新间隔: {self.refresh_interval}秒")
        print("\n按 Ctrl+C 退出程序\n")
        
        # 初始化历史日K线数据（预热技术指标）
        self.init_history_from_kline()
        
        time.sleep(2)
        
        try:
            while True:
                # 获取数据
                df = self.get_realtime_data()
                
                # 先更新日K线缓存（将当日实时数据注入，使技术指标反映盘中走势）
                self._update_history(df)
                
                # 显示数据（同时预计算评分，避免重复）
                precomputed = self.display_data(df)
                
                # 分析买卖信号（复用预计算的评分）
                self.analyze_signals(df, precomputed)
                
                # 等待下次刷新
                time.sleep(self.refresh_interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 盯盘程序已退出")
            sys.exit(0)


def main():
    """主函数"""
    monitor = StockMonitor()
    
    # 添加你关注的个股
    # 取消下面的注释并修改为你想监控的股票
    monitor.add_stock('600031', '三一重工')
    monitor.add_stock('600018', '上港集团')
    monitor.add_stock('601398', '工商银行')
    monitor.add_stock('601628', '中国人寿')
    monitor.add_stock('600690', '海尔智家')
    monitor.add_stock('600415', '小商品城')
    monitor.add_stock('600050', '中国联通')
    monitor.add_stock('600030', '中信证券')
    monitor.add_stock('002027', '分众传媒')
    monitor.add_stock('600958', '东方证券')
    monitor.add_stock('600930', '华电新能')
    monitor.add_stock('600919', '江苏银行')
    monitor.add_stock('600795', '国电电力')
    monitor.add_stock('000725', '京东方Ａ')
    monitor.add_stock('600036', '招商银行')
    monitor.add_stock('601318', '中国平安')
    monitor.add_stock('002475', '立讯精密')
    monitor.add_stock('601985', '中国核电')
    monitor.add_stock('300760', '迈瑞医疗')
    monitor.add_stock('601899', '紫金矿业')
    monitor.add_stock('601138', '工业富联')
    monitor.add_stock('002142', '宁波银行')
    monitor.add_stock('603259', '药明康德')
    # 修改预警阈值（可选）
    # monitor.alert_settings['price_change_pct'] = 5.0  # 涨跌幅5%时预警
    
    # 修改刷新间隔（可选）
    # monitor.refresh_interval = 5  # 每5秒刷新一次
    
    # 启动监控
    monitor.run()


if __name__ == "__main__":
    main()
