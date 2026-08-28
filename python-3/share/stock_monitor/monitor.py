"""主监控器：编排数据获取、历史缓存、信号分析、展示与循环。"""

import sys
import time
from collections import deque
from datetime import datetime
from typing import Optional

import pandas as pd

from stock_monitor import display
from stock_monitor.api import TencentDataClient
from stock_monitor.config import MonitorConfig, default_config
from stock_monitor.indicators import KdjState
from stock_monitor.notifier import Notifier
from stock_monitor.signals.engine import SignalEngine
from stock_monitor.signals.factors import IndicatorContext
from common.logging_utils import get_logger

logger = get_logger(__name__)


class StockMonitor:
    """股票盯盘监控器。

    依赖注入各子模块，职责清晰：
      - config   : 配置
      - client   : 腾讯财经数据客户端
      - engine   : 多因子信号评分引擎
      - notifier : 桌面通知
      - display  : 终端展示
    """

    def __init__(self, config: Optional[MonitorConfig] = None,
                 client: Optional[TencentDataClient] = None,
                 force_refresh: bool = False):
        self.config = config or default_config()
        self.client = client or TencentDataClient()
        self.force_refresh = force_refresh
        self.notifier = Notifier()
        self.engine = SignalEngine(self.config.signal_params)
        self.table = display.TableDisplay(self.config)

        # 历史数据（用于计算变化和趋势）
        self.history_data = {}      # code -> deque of (timestamp, price, volume)
        self.daily_history = {}     # code -> deque of daily bars（指标计算专用）
        self.daily_volumes = {}     # code -> list of 近5日成交量（用于量比计算）
        self.signal_history = {}    # code -> deque of (timestamp, signal_type, score, reason)

        # 预警记录（避免重复提醒）
        self.alerted_stocks = set()

        # 信号冷却
        self.last_signal_time = {}  # code -> {signal_type: timestamp}

        # KDJ 有状态计算器
        self._kdj_state = KdjState()

    # ------------------------------------------------------------------
    # 监控列表管理
    # ------------------------------------------------------------------

    def add_stock(self, code: str, name: str):
        """添加监控股票。"""
        self.config.watch_list[code] = name
        logger.info("添加监控股票 %s(%s)", name, code)
        print(f"✓ 已添加监控：{name} ({code})")

    def remove_stock(self, code: str):
        """移除监控股票。"""
        if code in self.config.watch_list:
            name = self.config.watch_list.pop(code)
            logger.info("移除监控股票 %s(%s)", name, code)
            print(f"✓ 已移除监控：{name} ({code})")
        else:
            logger.warning("未找到监控股票 %s", code)
            print(f"✗ 未找到股票：{code}")

    # ------------------------------------------------------------------
    # 历史数据初始化与更新
    # ------------------------------------------------------------------

    def init_history_from_kline(self):
        """从历史日K线初始化历史数据，预热技术指标。"""
        logger.info("开始加载历史日K线数据...")
        print("\n📥 正在加载历史日K线数据...")
        cfg = self.config
        for code, name in cfg.watch_list.items():
            klines = self.client.fetch_daily_kline(
                code, days=cfg.kline_days, force_refresh=self.force_refresh
            )
            if klines:
                if code not in self.daily_history:
                    self.daily_history[code] = deque(maxlen=cfg.max_history_len)
                for k in klines:
                    self.daily_history[code].append({
                        'date': k['date'],
                        'price': k['close'],
                        'volume': k['volume'],
                        'high': k['high'],
                        'low': k['low'],
                    })

                # 取最近5日的成交量用于量比计算
                self.daily_volumes[code] = [k['volume'] for k in klines[-5:]]
                logger.debug("%s(%s) 加载 %d 根日K线", name, code, len(klines))
                print(f"  ✓ {name}({code}) 加载 {len(klines)} 根日K线")
            else:
                logger.warning("%s(%s) 无法获取历史K线", name, code)
                print(f"  ✗ {name}({code}) 无法获取历史K线")

        logger.info("历史数据初始化完成，共 %d 只股票", len(self.daily_history))
        print(f"📊 历史数据初始化完成，共 {len(self.daily_history)} 只股票\n")

    def _update_history(self, df: pd.DataFrame):
        """更新历史数据（实时tick + 日K线缓存）。"""
        if df is None or df.empty:
            return
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        cfg = self.config
        for _, row in df.iterrows():
            code = row['代码']
            price = row.get('最新价', 0)
            volume = row.get('成交量', 0)
            high = row.get('最高', price)
            low = row.get('最低', price)

            if code not in self.history_data:
                self.history_data[code] = deque(maxlen=cfg.max_history_len)
            self.history_data[code].append({
                'time': now, 'price': price, 'volume': volume,
                'high': high, 'low': low,
            })

            # 同步更新日K线缓存，使技术指标反映盘中最新走势
            if code in self.daily_history and self.daily_history[code]:
                last_day = self.daily_history[code][-1]
                if last_day.get('date') == today_str:
                    last_day['price'] = price
                    last_day['high'] = max(last_day.get('high', price), high)
                    last_day['low'] = min(last_day.get('low', price), low)
                    last_day['volume'] = volume
                else:
                    self.daily_history[code].append({
                        'date': today_str, 'price': price,
                        'high': high, 'low': low, 'volume': volume,
                    })

    # ------------------------------------------------------------------
    # 预警与通知
    # ------------------------------------------------------------------

    def check_alerts(self, df: pd.DataFrame):
        """检查涨跌幅预警。"""
        if df is None or df.empty:
            return
        alerts = []
        threshold = self.config.alert_settings.price_change_pct
        for _, row in df.iterrows():
            code = row['代码']
            name = row['名称']
            change_pct = row.get('涨跌幅', 0)
            if abs(change_pct) >= threshold:
                alert_key = f"{code}_price"
                if alert_key not in self.alerted_stocks:
                    direction = "上涨" if change_pct > 0 else "下跌"
                    alerts.append(f"⚠️ {name}({code}) {direction} {abs(change_pct):.2f}%")
                    self.alerted_stocks.add(alert_key)
                    self.notifier.notify(
                        title=f"{name} {direction}预警",
                        message=f"当前涨跌幅: {change_pct:+.2f}%",
                    )
        if alerts:
            logger.warning("触发 %d 条涨跌幅预警", len(alerts))
            print("\n" + "=" * 60)
            print("🚨 预警信息")
            print("=" * 60)
            for a in alerts:
                print(a)
            print("=" * 60 + "\n")

    # ------------------------------------------------------------------
    # 信号冷却
    # ------------------------------------------------------------------

    def _is_in_cooldown(self, code: str, signal_type: str) -> bool:
        cooldown = self.config.signal_cooldown.get(signal_type, 300)
        last = self.last_signal_time.get(code, {}).get(signal_type)
        if not last:
            return False
        elapsed = (datetime.now() - last).total_seconds()
        return elapsed < cooldown

    def _record_signal(self, code: str, signal_type: str, score: int, reason: str):
        if code not in self.last_signal_time:
            self.last_signal_time[code] = {}
        self.last_signal_time[code][signal_type] = datetime.now()
        if code not in self.signal_history:
            self.signal_history[code] = deque(maxlen=20)
        self.signal_history[code].append({
            'time': datetime.now(), 'type': signal_type,
            'score': score, 'reason': reason,
        })

    # ------------------------------------------------------------------
    # 信号分析与展示
    # ------------------------------------------------------------------

    def display_data(self, df: pd.DataFrame) -> dict:
        """显示行情数据（含信号评分），返回预计算的评分。"""
        if df is None or df.empty:
            print("暂无数据")
            return {}

        ctx = IndicatorContext(self.daily_history, self.daily_volumes, self._kdj_state)
        precomputed_scores = {}
        cfg = self.config

        for _, row in df.iterrows():
            code = row['代码']
            market_trend = self.engine.market_trend_for(code, ctx, cfg.watch_list)
            total_score, level, reasons, indicators = self.engine.calculate(row, ctx, market_trend)
            precomputed_scores[code] = (total_score, level, reasons, indicators)

        self.table.render(df, precomputed_scores, cfg.refresh_interval)
        return precomputed_scores

    def analyze_signals(self, df: pd.DataFrame, precomputed_scores: dict = None):
        """分析买卖信号并显示。"""
        if df is None or df.empty:
            return

        ctx = IndicatorContext(self.daily_history, self.daily_volumes, self._kdj_state)
        signals_output = []
        alert_output = []
        cfg = self.config

        for _, row in df.iterrows():
            code = row['代码']
            name = row['名称']
            price = row.get('最新价', 0)
            change_pct = row.get('涨跌幅', 0)

            if precomputed_scores and code in precomputed_scores:
                total_score, level, reasons, indicators = precomputed_scores[code]
            else:
                market_trend = self.engine.market_trend_for(code, ctx, cfg.watch_list)
                total_score, level, reasons, indicators = self.engine.calculate(row, ctx, market_trend)

            signal_type = None
            if total_score >= cfg.signal_params.strong_buy_score:
                signal_type = 'strong_buy'
            elif total_score >= cfg.signal_params.buy_score:
                signal_type = 'buy'
            elif total_score <= cfg.signal_params.strong_sell_score:
                signal_type = 'strong_sell'
            elif total_score <= cfg.signal_params.sell_score:
                signal_type = 'sell'

            cooldown_key = (
                'buy' if signal_type and 'buy' in signal_type
                else ('sell' if signal_type and 'sell' in signal_type else None)
            )
            should_emit = cooldown_key and not self._is_in_cooldown(code, cooldown_key)

            if signal_type:
                signals_output.append({
                    'code': code, 'name': name, 'price': price,
                    'change_pct': change_pct, 'score': total_score,
                    'level': level, 'reasons': reasons, 'should_emit': should_emit,
                })

            if abs(change_pct) >= cfg.alert_settings.price_change_pct:
                if not self._is_in_cooldown(code, 'alert'):
                    direction = "上涨" if change_pct > 0 else "下跌"
                    alert_output.append({
                        'code': code, 'name': name,
                        'change_pct': change_pct, 'direction': direction,
                    })
                    self._record_signal(code, 'alert', 0, f"涨跌幅预警 {change_pct:+.2f}%")

        display.print_signals(signals_output)

        # 发出新信号时记录冷却并通知
        for sig in signals_output:
            if sig['should_emit']:
                score = sig['score']
                cooldown_key = 'buy' if score >= cfg.signal_params.buy_score else 'sell'
                self._record_signal(sig['code'], cooldown_key, score, sig['level'])
                self.notifier.notify(
                    title=f"{sig['level']} - {sig['name']}",
                    message=f"现价:{sig['price']:.2f} 涨跌:{sig['change_pct']:+.2f}% 评分:{score:+d}",
                )

        display.print_alerts(alert_output)

    # ------------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------------

    def run(self):
        """运行盯盘程序主循环。"""
        cfg = self.config
        logger.info("A股盯盘助手启动：监控 %d 只，刷新间隔 %s 秒", len(cfg.watch_list), cfg.refresh_interval)
        print("\n🚀 A股盯盘助手启动中...")
        print(f"📋 监控列表: {len(cfg.watch_list)} 只股票/指数")
        print("⚠️  预警阈值: 涨跌幅 ±"
              f"{cfg.alert_settings.price_change_pct}%")
        print("📊 信号引擎: MA均线+MACD+KDJ+RSI+布林带+成交量+大盘环境")
        print("   🟢强买入≥" + str(cfg.signal_params.strong_buy_score)
              + " 🔵买入≥" + str(cfg.signal_params.buy_score))
        print("   🟠卖出≤" + str(cfg.signal_params.sell_score)
              + " 🔴强卖出≤" + str(cfg.signal_params.strong_sell_score))
        print("🔄 刷新间隔: " + str(cfg.refresh_interval) + "秒")
        print("\n按 Ctrl+C 退出程序\n")

        # 初始化历史日K线数据（预热技术指标）
        self.init_history_from_kline()
        time.sleep(2)

        try:
            while True:
                df = self.client.get_realtime(cfg.watch_list)
                self._update_history(df)
                precomputed = self.display_data(df)
                self.analyze_signals(df, precomputed)
                time.sleep(cfg.refresh_interval)
        except KeyboardInterrupt:
            logger.info("盯盘程序已退出（Ctrl+C）")
            print("\n\n👋 盯盘程序已退出")
            sys.exit(0)
