"""
app.cli.commands.stock —— A股盯盘命令

用法：
    python -m app stock --once     # 单次快照
    python -m app stock --loop     # 持续盯盘
"""

from __future__ import annotations

import argparse

from app.core.logging_setup import get_logger
from app.domains.stock_watch import StockWatcher

logger = get_logger(__name__)


def stock_command(argv: list[str] | None = None) -> int:
    """A股盯盘命令。"""
    parser = argparse.ArgumentParser(description="A股实时盯盘")
    parser.add_argument("--once", action="store_true", help="单次快照运行")
    parser.add_argument("--loop", action="store_true", help="持续盯盘")
    parser.add_argument("--interval", type=int, default=10, help="刷新间隔（秒）")
    parser.add_argument("--refresh", action="store_true", help="强制刷新K线缓存")
    args = parser.parse_args(argv)

    watcher = StockWatcher(days=120)
    print("=" * 60)
    print("📈 A股实时盯盘（七大因子信号）")
    print("=" * 60)

    if args.loop:
        watcher.run_loop(interval=args.interval)
    else:
        result = watcher.run_once()
        print(f"监控 {result['watch_count']} 只，成功获取 {result['success_count']} 只\n")
        # 综合买卖建议（多维度融合）
        print("📊 多因子信号评分（含多维度专业指标）：")
        for s in result["signals"]:
            composite = s.get("composite_score")
            comp_str = f"  综合 {composite}" if composite is not None else ""
            print(
                f"  {s['name']}({s['code']})  价格 {s['price']}  涨跌 {s['change_pct']:+.2f}%  "
                f"技术 {s['score']}{comp_str}  [{s.get('composite_level', s['level'])}]"
            )
            if s["reasons"]:
                print(f"      {'；'.join(s['reasons'])}")
            # 各维度指标摘要
            dims = []
            fund = s.get("fundamental")
            mf = s.get("money_flow")
            adv = s.get("advanced")
            rk = s.get("risk")
            if fund and getattr(fund, "score", None) is not None:
                dims.append(f"基本面[{fund.verdict} {fund.score}]")
            if mf and getattr(mf, "score", None) is not None:
                dims.append(f"资金面[{mf.verdict} {mf.score}]")
            if adv and getattr(adv, "score", None) is not None:
                dims.append(f"技术面[{adv.verdict} {adv.score}]")
            if rk and getattr(rk, "score", None) is not None:
                dims.append(f"风险[{rk.risk_level} {rk.score}]")
            if dims:
                print(f"      {'  '.join(dims)}")
        if result["alerts"]:
            print("\n⚠️ 预警:")
            for alert in result["alerts"]:
                print(f"  {alert['message']}")

    return 0
