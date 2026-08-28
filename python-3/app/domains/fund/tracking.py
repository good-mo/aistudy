"""
app.domains.fund.tracking —— 基金每日收益追踪与定时监控

从原始 jijin_core.tracking 提炼而来，统一接入 app.data 数据层：
    - load_portfolio: 读取极简持仓 CSV（fund_code + total_cost）
    - FundTracker:    每日收益追踪
    - FundMonitor:    定时监控（阈值告警）
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import pandas as pd

from app.core.logging_setup import get_logger
from app.data.fund_nav import get_fund_nav_df

logger = get_logger(__name__)

DEFAULT_CSV = "portfolio.csv"


@dataclass
class AlertConfig:
    """基金监控告警默认配置。"""

    single_daily_drop_pct: float = 3.0
    portfolio_daily_loss_amt: float = 1000.0
    single_float_loss_amt: float = 2000.0
    single_float_loss_pct: float = 10.0
    portfolio_float_loss_amt: float = 5000.0
    enable_console: bool = True
    enable_notify: bool = True


class AlertEngine:
    """告警评估引擎。"""

    def __init__(self, config: AlertConfig | None = None):
        self.config = config or AlertConfig()

    def evaluate(self, portfolio: pd.DataFrame) -> list[str]:
        """对合并后的持仓 DataFrame 评估告警规则。"""
        if portfolio is None or portfolio.empty:
            return []
        messages: list[str] = []

        daily_drop_th = self.config.single_daily_drop_pct
        if "daily_return" in portfolio.columns:
            for _, row in portfolio.iterrows():
                dr = self._num(row.get("daily_return"))
                if dr <= -daily_drop_th:
                    messages.append(
                        "{name}({code}) 当日下跌 {value:.2f}%，超过阈值 {threshold}%".format(
                            name=row.get("fund_name", row.get("fund_code", "")),
                            code=row.get("fund_code", ""),
                            value=dr, threshold=daily_drop_th,
                        )
                    )

        daily_loss_th = self.config.portfolio_daily_loss_amt
        total_daily_profit = self._num(
            portfolio["daily_profit"].sum() if "daily_profit" in portfolio.columns else 0
        )
        if total_daily_profit <= -daily_loss_th:
            messages.append(
                "组合当日亏损 ¥{value:,.2f}，超过阈值 ¥{threshold:,.0f}".format(
                    value=total_daily_profit, threshold=daily_loss_th
                )
            )

        single_loss_th = self.config.single_float_loss_amt
        if "profit" in portfolio.columns:
            for _, row in portfolio.iterrows():
                profit = self._num(row.get("profit"))
                if profit <= -single_loss_th:
                    messages.append(
                        "{name}({code}) 累计浮亏 ¥{value:,.2f}，超过阈值 ¥{threshold:,.0f}".format(
                            name=row.get("fund_name", row.get("fund_code", "")),
                            code=row.get("fund_code", ""),
                            value=profit, threshold=single_loss_th,
                        )
                    )

        single_loss_pct_th = self.config.single_float_loss_pct
        if "profit_pct" in portfolio.columns:
            for _, row in portfolio.iterrows():
                pct = self._num(row.get("profit_pct")) * 100
                if pct <= -single_loss_pct_th:
                    messages.append(
                        "{name}({code}) 累计浮亏 {value:.2f}%，超过阈值 {threshold}%".format(
                            name=row.get("fund_name", row.get("fund_code", "")),
                            code=row.get("fund_code", ""),
                            value=pct, threshold=single_loss_pct_th,
                        )
                    )

        port_loss_th = self.config.portfolio_float_loss_amt
        total_profit = self._num(
            portfolio["profit"].sum() if "profit" in portfolio.columns else 0
        )
        if total_profit <= -port_loss_th:
            messages.append(
                "组合累计浮亏 ¥{value:,.2f}，超过阈值 ¥{threshold:,.0f}".format(
                    value=total_profit, threshold=port_loss_th,
                )
            )

        return messages

    @staticmethod
    def _num(value) -> float:
        """安全转 float，None/NaN 视为 0。"""
        if value is None:
            return 0.0
        try:
            import math
            v = float(value)
            return 0.0 if math.isnan(v) else v
        except (TypeError, ValueError):
            return 0.0

    def report(self, messages: list[str]) -> None:
        """打印告警。"""
        if not messages:
            return
        logger.warning("基金监控告警：%s", "；".join(messages))
        if self.config.enable_console:
            print("\n⚠️  基金监控告警")
            for m in messages:
                print(f"  ⚠ {m}")
            print()


def load_portfolio(csv_path: str) -> pd.DataFrame:
    """读取极简持仓 CSV，至少含 fund_code 和 total_cost。"""
    if not os.path.exists(csv_path):
        logger.error("持仓文件不存在: %s", csv_path)
        return pd.DataFrame(columns=["fund_code", "total_cost"])
    if os.path.getsize(csv_path) == 0:
        logger.warning("持仓文件为空: %s", csv_path)
        return pd.DataFrame(columns=["fund_code", "total_cost"])
    try:
        df = pd.read_csv(csv_path, dtype={"fund_code": str})
    except pd.errors.EmptyDataError:
        logger.warning("持仓文件无有效列（内容为空）: %s", csv_path)
        return pd.DataFrame(columns=["fund_code", "total_cost"])
    except Exception as e:  # noqa: BLE001
        logger.error("持仓 CSV 解析失败: %s", e)
        return pd.DataFrame(columns=["fund_code", "total_cost"])
    if "fund_code" not in df.columns and "代码" in df.columns:
        df = df.rename(columns={"代码": "fund_code"})
    if "total_cost" not in df.columns and "成本" in df.columns:
        df = df.rename(columns={"成本": "total_cost"})
    required = {"fund_code", "total_cost"}
    missing = required - set(df.columns)
    if missing:
        logger.error("持仓 CSV 缺少必需列: %s", missing)
        return pd.DataFrame(columns=["fund_code", "total_cost"])
    df["fund_code"] = df["fund_code"].astype(str).str.strip().str.zfill(6)
    df["total_cost"] = pd.to_numeric(df["total_cost"], errors="coerce").fillna(0)
    logger.debug("加载持仓 %d 条：%s", len(df), csv_path)
    return df


class FundTracker:
    """基金每日收益追踪。"""

    def __init__(self, csv_path: str = DEFAULT_CSV):
        self.csv_path = csv_path

    def load(self) -> pd.DataFrame:
        """加载持仓。"""
        return load_portfolio(self.csv_path)

    def build_snapshot(self, portfolio: pd.DataFrame) -> pd.DataFrame:
        """为持仓拉取最新净值并计算收益/浮亏。"""
        rows = []
        for _, row in portfolio.iterrows():
            code = str(row["fund_code"])
            cost = float(row.get("total_cost", 0))
            entry = {
                "fund_code": code,
                "fund_name": row.get("fund_name", code),
                "total_cost": cost,
                "nav": 0.0,
                "daily_return": 0.0,
                "prev_nav": 0.0,
            }
            try:
                df = get_fund_nav_df(code, days=60)
                if df is not None and not df.empty:
                    latest = float(df.iloc[-1])
                    prev = float(df.iloc[-2]) if len(df) > 1 else latest
                    entry["nav"] = latest
                    entry["prev_nav"] = prev
                    entry["daily_return"] = (latest / prev - 1) * 100 if prev else 0.0
                    logger.info(
                        "拉取净值成功 基金[%s] | 净值 %.4f | 日涨跌 %+.2f%%",
                        code, latest, entry["daily_return"],
                    )
                else:
                    logger.warning("基金 %s 净值数据为空，使用成本口径", code)
            except Exception as e:  # noqa: BLE001
                logger.warning("获取基金 %s 净值失败: %s", code, e)
            rows.append(entry)

        snap = pd.DataFrame(rows)
        snap["market_value"] = snap["total_cost"] * (1 + snap["daily_return"].fillna(0) / 100)
        snap["profit"] = snap["market_value"] - snap["total_cost"]
        snap["profit_pct"] = snap["profit"] / snap["total_cost"].replace(0, 1)
        snap["daily_profit"] = snap["total_cost"] * snap["daily_return"].fillna(0) / 100
        return snap

    def run_once(self, alert_config: AlertConfig | None = None) -> pd.DataFrame:
        """执行一次追踪快照，输出报告并评估告警。"""
        portfolio = self.load()
        if portfolio.empty:
            logger.warning("持仓为空，跳过本次追踪")
            return pd.DataFrame()
        snap = self.build_snapshot(portfolio)
        self.print_report(snap)
        engine = AlertEngine(alert_config or AlertConfig())
        messages = engine.evaluate(snap)
        engine.report(messages)
        return snap

    def print_report(self, snap: pd.DataFrame) -> None:
        """打印收益报告。"""
        if snap is None or snap.empty:
            print("无基金数据")
            return
        total_cost = float(snap.get("total_cost", 0).sum() or 0)
        total_value = float(snap.get("market_value", snap["total_cost"]).sum() or total_cost)
        total_profit = total_value - total_cost
        total_daily = float(snap.get("daily_profit", 0).sum() or 0)

        print(f"\n基金持仓明细（{len(snap)} 只）")
        print(f"总成本 ¥{total_cost:,.2f} | 总市值 ¥{total_value:,.2f} | "
              f"累计盈亏 ¥{total_profit:+.2f} | 今日收益 ¥{total_daily:+.2f}")
        print("-" * 72)
        print(f"{'代码':<8}{'名称':<20}{'净值':>10}{'日涨跌':>10}{'累计盈亏':>16}{'日收益':>12}")
        for _, row in snap.iterrows():
            code = str(row.get("fund_code", ""))
            name = str(row.get("fund_name", row.get("fund_code", code)))
            nav = float(row.get("nav", 0) or 0)
            dr = float(row.get("daily_return", 0) or 0)
            profit = float(row.get("profit", 0) or 0)
            daily_profit = float(row.get("daily_profit", 0) or 0)
            print(
                f"{code:<8}{name:<20}{nav:>10.4f}"
                f"{dr:>9.2f}%"
                f"{profit:>15.2f}"
                f"{daily_profit:>11.2f}"
            )
        print("-" * 72)


class FundMonitor:
    """基金定时监控。"""

    def __init__(self, csv_path: str = DEFAULT_CSV):
        self.csv_path = csv_path
        self.tracker = FundTracker(csv_path)

    def run_once(self, alert_config: AlertConfig | None = None) -> list[str]:
        """执行一次监控快照，返回触发的告警文案。"""
        portfolio = load_portfolio(self.csv_path)
        if portfolio.empty:
            logger.warning("持仓为空，跳过本次监控")
            return []
        snap = self.tracker.build_snapshot(portfolio)
        engine = AlertEngine(alert_config or AlertConfig())
        messages = engine.evaluate(snap)
        engine.report(messages)
        return messages

    def run_loop(self, interval: int = 300, alert_config: AlertConfig | None = None):
        """持续监控。"""
        logger.info("开始基金监控，刷新间隔 %d 秒", interval)
        try:
            while True:
                self.run_once(alert_config)
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("基金监控已停止")
