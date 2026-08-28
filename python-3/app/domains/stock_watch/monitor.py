"""
app.domains.stock_watch.monitor —— A股盯盘监控器

基于 app.data 统一接口 + 七大因子信号引擎，提供实时行情监控与买卖信号。
"""

from __future__ import annotations

import time
from typing import Dict, List

from app.core.logging_setup import get_logger
from app.data.kline import get_kline
from app.data.quotes import get_realtime_quote
from app.domains.stock_watch.signals import (
    IndicatorContext,
    SignalEngine,
    SignalParams,
)

logger = get_logger(__name__)

DEFAULT_WATCH_LIST: Dict[str, str] = {
 "600018": "上港集团",
        "601398": "工商银行",
        "601628": "中国人寿",
        "600690": "海尔智家",
        "600415": "小商品城",
        "600050": "中国联通",
        "600030": "中信证券",
        "002027": "分众传媒",
        "600958": "东方证券",
        "600930": "华电新能",
        "600919": "江苏银行",
        "600795": "国电电力",
        "000725": "京东方Ａ",
        "600036": "招商银行",
        "601318": "中国平安",
        "002475": "立讯精密",
        "601985": "中国核电",
        "300760": "迈瑞医疗",
        "601899": "紫金矿业",
        "601138": "工业富联",
        "002142": "宁波银行",
        "603259": "药明康德",
}


# 综合买卖建议融合权重（各维度 0-100，方向越高越利于买入）
_COMPOSITE_WEIGHTS = {
    "tech": 0.40,          # 七大因子技术信号
    "fundamental": 0.20,   # 基本面（估值，越高越低估）
    "money_flow": 0.15,    # 资金面（越高资金越流入）
    "advanced": 0.15,      # 高级技术（越高越偏强）
    "safety": 0.10,        # 风险安全度（100 - 风险评分）
}

# 综合买入潜力分 → 买卖建议等级
_STRONG_BUY = 75.0
_BUY = 60.0
_SELL = 40.0
_STRONG_SELL = 25.0


class StockWatcher:
    """A股实时盯盘监控器。"""

    def __init__(
        self,
        watch_list: Dict[str, str] | None = None,
        alert_threshold: float = 3.0,
        days: int = 120,
    ):
        self.watch_list = watch_list or DEFAULT_WATCH_LIST
        self.alert_threshold = alert_threshold
        self.days = days
        self.signal_engine = SignalEngine(SignalParams())

    def _load_history(self) -> tuple[dict, dict]:
        """加载所有监控股票的历史 K 线，构建因子上下文。"""
        daily_history: dict = {}
        daily_volumes: dict = {}
        for code in self.watch_list:
            klines = get_kline(code, days=self.days)
            if klines:
                daily_history[code] = klines
                daily_volumes[code] = [k.get("volume", 0) for k in klines]
        return daily_history, daily_volumes

    def get_all_quotes(self) -> dict[str, dict | None]:
        """获取所有监控股票的实时行情。"""
        results = {}
        for code, name in self.watch_list.items():
            quote = get_realtime_quote(code)
            if quote:
                quote["code"] = code
                quote["name"] = quote.get("name", name)
                results[code] = quote
            else:
                logger.warning("获取 %s(%s) 行情失败", name, code)
        return results

    def _tech_score_to_100(self, score: float) -> float | None:
        """将七大因子技术信号（约 -25~+25）归一化到 0-100。"""
        if score is None:
            return None
        return max(0.0, min(100.0, (score + 25.0) / 50.0 * 100.0))

    def _analyze_pro_indicators(self, code: str, name: str) -> dict:
        """为单只监控股票计算四大专业维度指标。"""
        from app.domains.stock_watch.advanced_indicators import analyze_advanced_indicators
        from app.domains.stock_watch.fundamental import analyze_fundamental
        from app.domains.stock_watch.money_flow import analyze_money_flow
        from app.domains.stock_watch.risk import analyze_risk

        fundamental = analyze_fundamental(code, name)
        money_flow = analyze_money_flow(code, name)
        advanced = analyze_advanced_indicators(code, name)
        risk = analyze_risk(code, name)
        return {
            "fundamental": fundamental,
            "money_flow": money_flow,
            "advanced": advanced,
            "risk": risk,
        }

    def _composite_score(self, tech_score_100: float | None, indicators: dict) -> float | None:
        """融合各维度评分得到综合买入潜力分（0-100）。"""
        parts: dict[str, float | None] = {
            "tech": tech_score_100,
            "fundamental": indicators["fundamental"].score,
            "money_flow": indicators["money_flow"].score,
            "advanced": indicators["advanced"].score,
            "safety": (100.0 - indicators["risk"].score) if indicators["risk"].score is not None else None,
        }
        weight_sum = 0.0
        acc = 0.0
        for key, weight in _COMPOSITE_WEIGHTS.items():
            val = parts[key]
            if val is None:
                continue
            acc += val * weight
            weight_sum += weight
        if weight_sum == 0:
            return None
        return round(acc / weight_sum, 1)

    @staticmethod
    def _composite_level(composite: float | None) -> str:
        """将综合买入潜力分映射为买卖建议等级。"""
        if composite is None:
            return "⚪ 观望"
        if composite >= _STRONG_BUY:
            return "🟢 强买入"
        if composite >= _BUY:
            return "🔵 买入"
        if composite <= _STRONG_SELL:
            return "🔴 强卖出"
        if composite <= _SELL:
            return "🟠 卖出"
        return "⚪ 观望"

    def analyze_signals(self) -> list[dict]:
        """使用七大因子引擎 + 多维度专业指标对监控股票评分，生成更合理的买卖建议。"""
        daily_history, daily_volumes = self._load_history()
        ctx = IndicatorContext(daily_history, daily_volumes)
        quotes = self.get_all_quotes()
        signals = []
        for code, quote in quotes.items():
            if code == "000300":
                continue  # 大盘只做环境判断
            name = quote.get("name", code)
            row = {
                "code": code,
                "volume": quote.get("volume", 0),
                "change_pct": quote.get("change_pct", 0),
            }
            market_trend = 0
            score, level, reasons, _ = self.signal_engine.calculate(row, ctx, market_trend)

            # 多维度专业指标（基本面/资金面/高级技术/风险）
            indicators = self._analyze_pro_indicators(code, name)
            tech_score_100 = self._tech_score_to_100(score)
            composite = self._composite_score(tech_score_100, indicators)
            composite_level = self._composite_level(composite)

            signals.append({
                "code": code,
                "name": name,
                "price": quote.get("price", 0),
                "change_pct": quote.get("change_pct", 0),
                "score": score,
                "level": level,
                "reasons": reasons,
                # 多维度专业指标
                "fundamental": indicators["fundamental"],
                "money_flow": indicators["money_flow"],
                "advanced": indicators["advanced"],
                "risk": indicators["risk"],
                "tech_score_100": tech_score_100,
                "composite_score": composite,
                "composite_level": composite_level,
            })
        signals.sort(key=lambda s: (s.get("composite_score") or 0), reverse=True)
        return signals

    def check_alerts(self, quotes: dict[str, dict | None]) -> list[dict]:
        """检查涨跌幅预警。"""
        alerts = []
        for code, quote in quotes.items():
            if not quote or code == "000300":
                continue
            change_pct = quote.get("change_pct", 0)
            name = quote.get("name", code)
            if abs(change_pct) >= self.alert_threshold:
                alerts.append({
                    "code": code,
                    "name": name,
                    "change_pct": change_pct,
                    "message": f"{name}({code}) 涨跌幅 {change_pct:.2f}% 超过阈值 {self.alert_threshold}%",
                })
        return alerts

    def run_once(self) -> dict:
        """单次快照运行，返回行情 + 信号。"""
        quotes = self.get_all_quotes()
        alerts = self.check_alerts(quotes)
        signals = self.analyze_signals()
        return {
            "quotes": quotes,
            "alerts": alerts,
            "signals": signals,
            "watch_count": len(self.watch_list),
            "success_count": len([q for q in quotes.values() if q]),
        }

    def run_loop(self, interval: int = 10, max_iterations: int | None = None):
        """持续盯盘（阻塞，Ctrl+C 退出）。"""
        logger.info("开始盯盘，刷新间隔 %d 秒", interval)
        iteration = 0
        try:
            while max_iterations is None or iteration < max_iterations:
                iteration += 1
                result = self.run_once()
                print(f"\n[第 {iteration} 轮] 监控 {result['watch_count']} 只，成功 {result['success_count']} 只")
                for alert in result["alerts"]:
                    print(f"  ⚠️ {alert['message']}")
                for s in result["signals"]:
                    composite = s.get("composite_score")
                    comp_str = f" 综合 {composite}" if composite is not None else ""
                    print(
                        f"  {s['name']}({s['code']})  价格 {s['price']}  涨跌 {s['change_pct']:+.2f}%  "
                        f"技术 {s['score']}{comp_str}  [{s.get('composite_level', s['level'])}]"
                    )
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("盯盘已停止")
