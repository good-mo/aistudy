"""终端展示与格式化模块。"""

import os
from datetime import datetime
from typing import List

import pandas as pd

from common.logging_utils import get_logger

logger = get_logger(__name__)


def format_number(value, decimals: int = 2) -> str:
    """格式化数字显示（万/亿）。"""
    if pd.isna(value):
        return "--"
    if abs(value) >= 1e8:
        return f"{value / 1e8:.{decimals}f}亿"
    elif abs(value) >= 1e4:
        return f"{value / 1e4:.{decimals}f}万"
    else:
        return f"{value:.{decimals}f}"


class TableDisplay:
    """行情表格展示，负责表头与数据行的格式化输出。"""

    HEADER = (
        f"{'代码':<8} {'名称':<8} {'最新价':>8} {'涨跌幅':>8} {'涨跌额':>8} "
        f"{'评分':>5} {'信号':<8} {'MA':<5} {'MACD':<5} {'KDJ':<5} "
        f"{'RSI':<5} {'布林':<5} {'量能':<5}"
    )

    def __init__(self, config):
        self.config = config

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def render(self, df: pd.DataFrame, precomputed_scores: dict, refresh_interval: int):
        """渲染表格，返回统计信息 dict。"""
        self.clear_screen()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("渲染行情表，更新时间 %s，共 %d 行", now, len(df))
        print(f"\n{'=' * 120}")
        print(
            f"📊 A股盯盘助手 | 更新时间: {now}  |  引擎: "
            f"MA+MACD+KDJ+RSI+布林+量能+大盘+共振"
        )
        print(f"{'=' * 120}\n")

        print(self.HEADER)
        print("-" * 120)

        for _, row in df.iterrows():
            code = row['代码']
            name = row['名称']
            price = row.get('最新价', 0)
            change_pct = row.get('涨跌幅', 0)
            change_amt = row.get('涨跌额', 0)

            if code in precomputed_scores:
                total_score, level, _reasons, indicators = precomputed_scores[code]
            else:
                total_score, level, indicators = 0, "⚪ 观望", {}

            summaries = self._build_summaries(row, indicators, price)
            ma_str, macd_str, kdj_str, rsi_str, boll_str, vol_str = summaries

            color, reset = self._color_for(change_pct)
            sig_color, sig_reset = self._signal_color(total_score)

            line = (
                f"{color}{code:<8} {name:<8} {price:>8.2f} {change_pct:>+7.2f}% "
                f"{change_amt:>+8.2f} {sig_color}{total_score:>+4d}  {level:<6}{sig_reset}"
                f" {ma_str:<5} {macd_str:<5} {kdj_str:<5} {rsi_str:<5} "
                f"{boll_str:<5} {vol_str:<5}{reset}"
            )
            print(line)

        print("-" * 120)
        return self._stats(df, refresh_interval)

    def _build_summaries(self, row, indicators: dict, price: float):
        """根据指标字典生成各列的简短摘要。"""
        ma_str = macd_str = kdj_str = rsi_str = boll_str = vol_str = "-"

        # MA 摘要：由调用方通过 indicators 传入 'ma_direction'
        ma_dir = indicators.get('ma_direction')
        if ma_dir:
            ma_str = "多" if ma_dir > 0 else "空"

        if indicators.get('macd_dif') is not None and indicators.get('macd_dea') is not None:
            macd_str = "金" if indicators['macd_dif'] > indicators['macd_dea'] else "死"

        kdj_j = indicators.get('kdj_j')
        if kdj_j is not None:
            if kdj_j < 0:
                kdj_str = "超卖"
            elif kdj_j > 100:
                kdj_str = "超买"
            else:
                kdj_str = "正常"

        rsi = indicators.get('rsi')
        if rsi is not None:
            if rsi <= 30:
                rsi_str = f"{rsi:.0f}超卖"
            elif rsi >= 70:
                rsi_str = f"{rsi:.0f}超买"
            else:
                rsi_str = f"{rsi:.0f}"

        boll_mid = indicators.get('boll_mid')
        boll_bw = indicators.get('boll_bandwidth')
        if boll_mid and boll_bw is not None:
            if boll_bw < 5:
                boll_str = f"{boll_bw:.0f}%收窄"
            elif boll_bw > 15:
                boll_str = f"{boll_bw:.0f}%扩张"
            else:
                pct_pos = (price - boll_mid) / boll_mid * 100 if boll_mid > 0 else 0
                boll_str = f"{pct_pos:+.0f}%"

        vol_ratio = indicators.get('volume_ratio')
        if vol_ratio is not None:
            if vol_ratio >= 2:
                vol_str = "放量"
            elif vol_ratio <= 0.6:
                vol_str = "缩量"
            elif vol_ratio >= 1.3:
                vol_str = "温和"
            else:
                vol_str = "正常"

        return ma_str, macd_str, kdj_str, rsi_str, boll_str, vol_str

    @staticmethod
    def _color_for(change_pct: float):
        if change_pct > 0:
            return "\033[91m", "\033[0m"
        elif change_pct < 0:
            return "\033[92m", "\033[0m"
        return "\033[0m", "\033[0m"

    def _signal_color(self, total_score: int):
        params = self.config.signal_params
        if total_score >= params.buy_score:
            return "\033[91m", "\033[0m"
        elif total_score <= params.sell_score:
            return "\033[92m", "\033[0m"
        return "", ""

    def _stats(self, df: pd.DataFrame, refresh_interval: int) -> dict:
        up_count = len(df[df['涨跌幅'] > 0])
        down_count = len(df[df['涨跌幅'] < 0])
        flat_count = len(df[df['涨跌幅'] == 0])

        logger.info("行情统计：上涨 %d | 下跌 %d | 平盘 %d", up_count, down_count, flat_count)
        print(f"\n📈 上涨: {up_count} | 📉 下跌: {down_count} | ➖ 平盘: {flat_count}")
        print(f"⏱️  下次刷新: {refresh_interval}秒后")
        print("💡 提示: 按 Ctrl+C 退出程序\n")

        return {'up': up_count, 'down': down_count, 'flat': flat_count}


def print_signals(signals_output: List[dict]):
    """打印买卖信号分析结果。"""
    if not signals_output:
        return

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
        logger.info("买卖信号 [%s] %s(%s) 现价%.2f 涨跌%+.2f%% 评分%+d 信号:%s",
                    "🆕" if should_emit else "  ", name, code, price, change_pct, score, level)

        if score > 0:
            color = "\033[91m"  # 红（看多）
        elif score < 0:
            color = "\033[92m"  # 绿（看空）
        else:
            color = "\033[0m"
        reset = "\033[0m"

        new_tag = "🆕 " if should_emit else "   "

        print(f"\n{new_tag}{color}{name}({code}) | 现价: {price:.2f} | 涨跌: {change_pct:+.2f}%")
        print(f"   评分: {score:+d} | 信号: {level}{reset}")
        if reasons:
            for r in reasons:
                print(f"   └ {r}")

    print("\n" + "=" * 80)


def print_alerts(alert_output: List[dict]):
    """打印涨跌幅预警。"""
    if not alert_output:
        return
    print("\n" + "-" * 60)
    print("🚨 涨跌幅预警")
    print("-" * 60)
    for alert in alert_output:
        logger.warning("涨跌幅预警 %s(%s) %s %.2f%%", alert['name'], alert['code'], alert['direction'], abs(alert['change_pct']))
        print(
            f"  ⚠️ {alert['name']}({alert['code']}) "
            f"{alert['direction']} {abs(alert['change_pct']):.2f}%"
        )
    print("-" * 60 + "\n")
