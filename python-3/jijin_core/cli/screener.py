"""
基金筛选命令行入口
    python -m jijin_core.cli.screener [--top N] [--refresh] [--code CODE,...] [--holdings]
"""

import argparse

from common.logging_utils import get_logger, setup_logging
from ..screening.screener import run_screening, analyze_holdings
from ..analysis.macro import init_macro_state, get_cycle_advice

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="基金筛选系统")
    parser.add_argument("--top", type=int, default=50, help="筛选前 N 名")
    parser.add_argument("--refresh", action="store_true", help="强制刷新数据")
    parser.add_argument("--code", type=str, default="", help="指定基金代码，逗号分隔")
    parser.add_argument("--holdings", action="store_true", help="分析持仓")
    args = parser.parse_args()

    setup_logging()
    logger.info("基金筛选启动：top=%s refresh=%s holdings=%s", args.top, args.refresh, args.holdings)

    macro = init_macro_state(force_refresh=args.refresh)
    print(f"周期阶段: {macro.get('cycle_phase')} | 偏好风格: {macro.get('preferred_style')}")
    print(get_cycle_advice(macro.get("cycle_phase")))
    print("-" * 60)

    if args.holdings:
        df = analyze_holdings(force_refresh=args.refresh)
    else:
        code_list = [c.strip() for c in args.code.split(",") if c.strip()] if args.code else None
        df = run_screening(top_n=args.top, force_refresh=args.refresh, code_list=code_list)

    if df.empty:
        print("无筛选结果")
        logger.warning("筛选结果为空")
        return
    logger.info("筛选完成，共 %d 条结果", len(df))
    print(f"{'代码':<8}{'名称':<20}{'类型':<10}{'行业':<8}{'年化':>8}{'回撤':>8}{'评分':>8}{'信号':<6}")
    for _, row in df.iterrows():
        print(
            f"{str(row.get('fund_code','')):<8}{str(row.get('fund_name','')):<20}"
            f"{str(row.get('asset_type','')):<10}{str(row.get('industry','')):<8}"
            f"{float(row.get('annual_return',0) or 0)*100:>7.2f}%"
            f"{float(row.get('max_drawdown',0) or 0)*100:>7.2f}%"
            f"{float(row.get('score',0) or 0):>8.1f}{str(row.get('signal','')):<6}"
        )


if __name__ == "__main__":
    main()
