"""
app.domains.fund.metrics —— 基金绩效指标计算

从原始 jijin_core.analysis.metrics 提炼而来，提供完整的基金绩效评估指标，
并统一接入 app.data 数据层。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.logging_setup import get_logger

logger = get_logger(__name__)

# 默认无风险利率
RISK_FREE_RATE = 0.02


def calc_annual_return(nav_series: pd.Series) -> float:
    """计算年化收益率（基于累计净值序列）。"""
    if nav_series is None or len(nav_series) < 2:
        return 0.0
    first = float(nav_series.iloc[0])
    last = float(nav_series.iloc[-1])
    if first <= 0:
        return 0.0
    days = _index_span_days(nav_series)
    years = days / 365.0
    if years <= 0:
        return 0.0
    result = (last / first) ** (1 / years) - 1
    logger.debug("年化收益=%.4f（首%.4f 末%.4f 跨度%d天）", result, first, last, days)
    return result


def _index_span_days(nav_series: pd.Series) -> int:
    """计算序列首尾时间跨度（天），兼容 datetime 与字符串索引。"""
    try:
        idx0, idx1 = nav_series.index[0], nav_series.index[-1]
        if hasattr(idx0, "year"):
            return max((idx1 - idx0).days, 1)
        return max((pd.to_datetime(idx1) - pd.to_datetime(idx0)).days, 1)
    except Exception:  # noqa: BLE001
        return 1


def calc_max_drawdown(series: pd.Series) -> float:
    """计算最大回撤（正数，如 0.2 表示 20% 回撤）。"""
    if series is None or len(series) < 2:
        return 0.0
    s = series.astype(float)
    running_max = s.cummax()
    drawdown = (s - running_max) / running_max
    result = float(-drawdown.min()) if not drawdown.empty else 0.0
    logger.debug("最大回撤=%.4f", result)
    return result


def calc_volatility(nav_series: pd.Series) -> float:
    """计算年化波动率。"""
    if nav_series is None or len(nav_series) < 2:
        return 0.0
    ret = nav_series.pct_change().dropna()
    if ret.empty:
        return 0.0
    return float(ret.std() * np.sqrt(252))


def calc_sharpe_ratio(nav_series: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    """计算夏普比率。"""
    ann_ret = calc_annual_return(nav_series)
    vol = calc_volatility(nav_series)
    if vol <= 0:
        return 0.0
    return (ann_ret - risk_free_rate) / vol


def calc_calmar_ratio(nav_series: pd.Series) -> float:
    """计算卡尔马比率（年化收益 / 最大回撤）。"""
    ann_ret = calc_annual_return(nav_series)
    mdd = calc_max_drawdown(nav_series)
    if mdd <= 0:
        return 0.0
    return ann_ret / mdd


def calc_sortino_ratio(nav_series: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    """计算索提诺比率（仅用下行波动）。"""
    ann_ret = calc_annual_return(nav_series)
    ret = nav_series.pct_change().dropna()
    if ret.empty:
        return 0.0
    downside = ret[ret < risk_free_rate / 252].std()
    if downside is None or np.isnan(downside) or downside <= 0:
        return 0.0
    return (ann_ret - risk_free_rate) / (downside * np.sqrt(252))


def calc_tracking_error_and_difference(
    fund_returns: pd.Series, index_returns: pd.Series
) -> dict:
    """计算跟踪误差（TE）与跟踪偏离度（TD）。"""
    if fund_returns is None or index_returns is None:
        return {"tracking_error": None, "tracking_difference": None}
    df = pd.concat([fund_returns, index_returns], axis=1, join="inner").dropna()
    if df.empty or len(df) < 2:
        return {"tracking_error": None, "tracking_difference": None}
    diff = df.iloc[:, 0] - df.iloc[:, 1]
    te = float(diff.std() * np.sqrt(252))
    td = float(diff.mean() * 252)
    return {"tracking_error": te, "tracking_difference": td}


def calc_information_ratio(
    fund_annual_ret: float, index_annual_ret: float, tracking_error: float
) -> float:
    """计算信息比率。"""
    if not tracking_error or tracking_error <= 0:
        return 0.0
    return (fund_annual_ret - index_annual_ret) / tracking_error


def calc_alpha_and_ir(nav_series: pd.Series, benchmark: pd.Series) -> dict:
    """基于净值与基准计算 Alpha 与信息比率。"""
    if nav_series is None or benchmark is None:
        return {"alpha": 0.0, "information_ratio": 0.0}
    fund_ret = nav_series.pct_change().dropna()
    bench_ret = benchmark.pct_change().dropna()
    df = pd.concat([fund_ret, bench_ret], axis=1, join="inner").dropna()
    if df.empty or len(df) < 2:
        return {"alpha": 0.0, "information_ratio": 0.0}
    fund_ann = (1 + df.iloc[:, 0].mean()) ** 252 - 1
    bench_ann = (1 + df.iloc[:, 1].mean()) ** 252 - 1
    alpha = fund_ann - bench_ann
    diff = df.iloc[:, 0] - df.iloc[:, 1]
    te = diff.std() * np.sqrt(252)
    ir = (diff.mean() * 252) / te if te > 0 else 0.0
    return {"alpha": float(alpha), "information_ratio": float(ir)}


def calc_nav_percentile(nav_series: pd.Series) -> float:
    """计算当前净值在历史区间的百分位（0-100）。"""
    if nav_series is None or len(nav_series) < 2:
        return 50.0
    current = float(nav_series.iloc[-1])
    hist = nav_series.iloc[:-1].astype(float)
    if hist.empty:
        return 50.0
    below = (hist <= current).sum()
    return float(below / len(hist) * 100)


def calc_downside_capture(nav_series: pd.Series, benchmark: pd.Series) -> float:
    """计算下行捕获率。"""
    fund_ret = nav_series.pct_change().dropna()
    bench_ret = benchmark.pct_change().dropna()
    df = pd.concat([fund_ret, bench_ret], axis=1, join="inner").dropna()
    if df.empty:
        return 0.0
    down = df[df.iloc[:, 1] < 0]
    if down.empty:
        return 0.0
    return float(down.iloc[:, 0].mean() / down.iloc[:, 1].mean())


def calc_upside_capture(nav_series: pd.Series, benchmark: pd.Series) -> float:
    """计算上行捕获率。"""
    fund_ret = nav_series.pct_change().dropna()
    bench_ret = benchmark.pct_change().dropna()
    df = pd.concat([fund_ret, bench_ret], axis=1, join="inner").dropna()
    if df.empty:
        return 0.0
    up = df[df.iloc[:, 1] > 0]
    if up.empty:
        return 0.0
    return float(up.iloc[:, 0].mean() / up.iloc[:, 1].mean())


def calc_monthly_win_rate(nav_series: pd.Series, benchmark: pd.Series | None = None) -> dict:
    """计算月度胜率与平均收益。"""
    if nav_series is None or len(nav_series) < 2:
        return {"monthly_win_rate": 0.0, "avg_monthly": 0.0, "months": 0}
    s = nav_series.copy()
    s.index = pd.to_datetime(s.index)
    monthly = s.resample("ME").last().pct_change().dropna()
    if monthly.empty:
        return {"monthly_win_rate": 0.0, "avg_monthly": 0.0, "months": 0}
    win = (monthly > 0).mean()
    return {
        "monthly_win_rate": float(win),
        "avg_monthly": float(monthly.mean()),
        "months": int(len(monthly)),
    }


def calc_drawdown_recovery(nav_series: pd.Series) -> dict:
    """计算回撤修复天数。"""
    if nav_series is None or len(nav_series) < 20:
        return {"recovery_days": None, "max_drawdown": 0.0}
    s = nav_series.astype(float)
    values = s.values
    peak_pos = int(np.argmax(values))
    peak_value = float(values[peak_pos])
    trough_rel = int(np.argmin(values[peak_pos:]))
    trough_pos = peak_pos + trough_rel
    trough_value = float(values[trough_pos])
    mdd = (peak_value - trough_value) / peak_value if peak_value > 0 else 0.0
    recovery = None
    after_trough = s.iloc[trough_pos:]
    for i in range(len(after_trough)):
        if float(after_trough.iloc[i]) >= peak_value:
            recovery = i
            break
    return {"recovery_days": recovery, "max_drawdown": float(mdd)}


def calc_rolling_metrics(nav_series: pd.Series, window: int = 252) -> dict:
    """计算滚动窗口收益的稳定性。"""
    if nav_series is None or len(nav_series) < window:
        return {"rolling_std": 0.0, "rolling_sharpe": 0.0, "positive_windows": 0.0}
    ret = nav_series.pct_change().rolling(window).sum().dropna()
    if ret.empty:
        return {"rolling_std": 0.0, "rolling_sharpe": 0.0, "positive_windows": 0.0}
    positive = (ret > 0).mean()
    return {
        "rolling_std": float(ret.std()),
        "rolling_sharpe": float(ret.mean() / ret.std()) if ret.std() > 0 else 0.0,
        "positive_windows": float(positive),
    }
