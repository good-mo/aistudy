"""配置管理与加载。

将原来散落在 StockMonitor.__init__ 中的监控列表、预警设置、
买卖信号参数等集中管理，并支持从文件或环境变量加载。
"""

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class SignalParams:
    """买卖信号参数。"""

    strong_buy_score: int = 4      # 综合评分 >= 此值为强买入
    buy_score: int = 2             # 综合评分 >= 此值为买入
    strong_sell_score: int = -4    # 综合评分 <= 此值为强卖出
    sell_score: int = -2           # 综合评分 <= 此值为卖出
    breakout_pct: float = 2.0      # 突破昨收/今开的百分比阈值
    amplitude_alert: float = 5.0   # 振幅预警阈值
    v_reversal_pct: float = 2.0    # V形反转阈值
    volume_surge_ratio: float = 3.0   # 放量倍数
    price_volume_diverge: float = 1.5 # 量价背离阈值


@dataclass
class AlertSettings:
    """预警设置。"""

    price_change_pct: float = 3.0   # 涨跌幅超过此百分比时预警
    volume_ratio: float = 2.0       # 量比超过此值时预警


@dataclass
class MonitorConfig:
    """盯盘程序整体配置。"""

    # 监控的股票列表（代码: 名称）
    watch_list: Dict[str, str] = field(default_factory=lambda: {
        '000300': '沪深300',
        '600031': '三一重工',
        '600018': '上港集团',
        '601398': '工商银行',
        '601628': '中国人寿',
        '600690': '海尔智家',
        '600415': '小商品城',
        '600050': '中国联通',
        '600030': '中信证券',
        '002027': '分众传媒',
        '600958': '东方证券',
        '600930': '华电新能',
        '600919': '江苏银行',
        '600795': '国电电力',
        '000725': '京东方Ａ',
    })

    # 预警设置
    alert_settings: AlertSettings = field(default_factory=AlertSettings)

    # 买卖信号参数
    signal_params: SignalParams = field(default_factory=SignalParams)

    # 刷新间隔（秒）
    refresh_interval: int = 10

    # 历史数据保留数量（MACD最长需要26周期）
    max_history_len: int = 50

    # 信号冷却期（秒）
    signal_cooldown: Dict[str, int] = field(default_factory=lambda: {
        'buy': 300,    # 买入信号5分钟冷却
        'sell': 300,   # 卖出信号5分钟冷却
        'alert': 180,  # 预警信号3分钟冷却
    })

    # 历史日K线加载数量
    kline_days: int = 60


_DEFAULT_CONFIG: Optional[MonitorConfig] = None


def default_config() -> MonitorConfig:
    """返回默认配置的副本（便于调用方局部修改而不影响全局默认）。"""
    global _DEFAULT_CONFIG
    if _DEFAULT_CONFIG is None:
        _DEFAULT_CONFIG = MonitorConfig()
    base = _DEFAULT_CONFIG
    return MonitorConfig(
        watch_list=dict(base.watch_list),
        alert_settings=AlertSettings(
            price_change_pct=base.alert_settings.price_change_pct,
            volume_ratio=base.alert_settings.volume_ratio,
        ),
        signal_params=SignalParams(
            strong_buy_score=base.signal_params.strong_buy_score,
            buy_score=base.signal_params.buy_score,
            strong_sell_score=base.signal_params.strong_sell_score,
            sell_score=base.signal_params.sell_score,
            breakout_pct=base.signal_params.breakout_pct,
            amplitude_alert=base.signal_params.amplitude_alert,
            v_reversal_pct=base.signal_params.v_reversal_pct,
            volume_surge_ratio=base.signal_params.volume_surge_ratio,
            price_volume_diverge=base.signal_params.price_volume_diverge,
        ),
        refresh_interval=base.refresh_interval,
        max_history_len=base.max_history_len,
        signal_cooldown=dict(base.signal_cooldown),
        kline_days=base.kline_days,
    )
