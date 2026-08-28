"""
app.cli.commands.pro —— 专业股票分析师命令

用法：
    python -m app pro --code 600519       # 单只股票专业分析（基本面+资金+技术+风险）
    python -m app pro --market            # 市场情绪 + 宏观环境
    python -m app pro --corr --codes 600519,600036   # 组合相关性
"""

from __future__ import annotations

import argparse

from app.core.logging_setup import get_logger

logger = get_logger(__name__)


def pro_command(argv: list[str] | None = None) -> int:
    """专业分析师综合分析命令。"""
    parser = argparse.ArgumentParser(description="专业股票分析师（基本面/资金/技术/风险/宏观）")
    parser.add_argument("--code", type=str, default="", help="股票代码")
    parser.add_argument("--name", type=str, default="", help="股票名称")
    parser.add_argument("--market", action="store_true", help="市场情绪 + 宏观环境")
    parser.add_argument("--corr", action="store_true", help="组合相关性矩阵")
    parser.add_argument("--codes", type=str, default="", help="组合代码列表（逗号分隔）")
    parser.add_argument("--benchmark", type=str, default="000300", help="大盘基准代码")
    args = parser.parse_args(argv)

    from app.domains.market import analyze_macro, analyze_market_sentiment
    from app.domains.stock_watch.advanced_indicators import analyze_advanced_indicators
    from app.domains.stock_watch.fundamental import analyze_fundamental
    from app.domains.stock_watch.money_flow import analyze_money_flow
    from app.domains.stock_watch.risk import analyze_risk, correlation_matrix

    print("=" * 62)
    print("📊 专业股票分析师 · 多维度综合分析")
    print("=" * 62)

    if args.market:
        print("\n🌐 宏观环境")
        macro = analyze_macro()
        _print_macro(macro)
        print("\n🔥 市场情绪")
        senti = analyze_market_sentiment()
        _print_sentiment(senti)
        return 0

    if args.corr:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        if len(codes) < 2:
            print("组合相关性需要至少 2 只股票，如 --codes 600519,600036")
            return 1
        print("\n🔗 组合相关性矩阵")
        corr = correlation_matrix(codes, benchmark=args.benchmark)
        if corr is None:
            print("  数据不足，无法计算相关性")
        else:
            print(corr.round(2).to_string())
        return 0

    if not args.code:
        parser.print_help()
        return 1

    code, name = args.code, args.name
    print(f"\n📈 {name or code} 专业分析")

    print("\n  ◆ 基本面（估值）")
    _print_fundamental(analyze_fundamental(code, name))

    print("\n  ◆ 资金面")
    _print_money_flow(analyze_money_flow(code, name))

    print("\n  ◆ 高级技术指标")
    _print_advanced(analyze_advanced_indicators(code, name))

    print("\n  ◆ 风险指标")
    _print_risk(analyze_risk(code, name, benchmark=args.benchmark))

    return 0


def _print_fundamental(snap) -> None:
    print(f"   PE(TTM): {_f(snap.pe_ttm)}   PB: {_f(snap.pb)}   PS: {_f(snap.ps)}")
    print(f"   PEG: {_f(snap.peg)}   股息率: {_f(snap.dividend_yield)}%   总市值: {_fmt_cap(snap.market_cap)}")
    print(f"   PE 分位(5y): {_f(snap.pe_percentile_5y)}%  (10y): {_f(snap.pe_percentile_10y)}%")
    print(f"   PB 分位(5y): {_f(snap.pb_percentile_5y)}%  (10y): {_f(snap.pb_percentile_10y)}%")
    print(f"   估值: {snap.verdict}  评分: {_f(snap.score)}")


def _print_money_flow(snap) -> None:
    print(f"   北向今日: {_f(snap.northbound_today)}亿  近5日: {_f(snap.northbound_5d)}亿  近20日: {_f(snap.northbound_20d)}亿")
    print(f"   主力净流入: {_f(snap.main_net_inflow)}万  占比: {_f(snap.main_net_inflow_pct)}%")
    if snap.margin_balance is not None:
        print(f"   两融余额: {_f(snap.margin_balance)}亿  变化: {_f(snap.margin_change)}亿")
    print(f"   资金面: {snap.verdict}  评分: {_f(snap.score)}")


def _print_advanced(snap) -> None:
    print(f"   ATR: {_f(snap.atr)} ({_f(snap.atr_pct)}%)   ADX: {_f(snap.adx)} [{snap.adx_state}]")
    print(f"   OBV: {_f(snap.obv)} [{snap.obv_trend}]   BIAS: {_f(snap.bias)} [{snap.bias_state}]")
    print(f"   跳空缺口: {snap.gap_count} 个 (未回补 {snap.gap_unfilled})")
    print(f"   技术面: {snap.verdict}  评分: {_f(snap.score)}")


def _print_risk(snap) -> None:
    print(f"   Beta: {_f(snap.beta)}   年化波动率: {_f(snap.annual_volatility)}%")
    print(f"   VaR(95%): {_f(snap.var_95)}%   VaR(99%): {_f(snap.var_99)}%   ES(95%): {_f(snap.es_95)}%")
    print(f"   最大回撤: {_f(snap.max_drawdown)}%")
    print(f"   风险等级: {snap.risk_level}  评分: {_f(snap.score)}")


def _print_macro(snap) -> None:
    print(f"   M1同比: {_f(snap.m1_yoy)}%   M2同比: {_f(snap.m2_yoy)}%   M1-M2剪刀差: {_f(snap.m1m2_gap)}%")
    print(f"   10年国债: {_f(snap.bond_10y)}%  2年国债: {_f(snap.bond_2y)}%  10Y-2Y利差: {_f(snap.yield_curve)}%")
    if snap.lpr_1y is not None:
        print(f"   LPR 1年期: {_f(snap.lpr_1y)}%  5年期: {_f(snap.lpr_5y)}%")
    print(f"   宏观环境: {snap.environment}  评分: {_f(snap.score)}")


def _print_sentiment(snap) -> None:
    print(f"   上涨: {snap.up_count}  涨停: {snap.limit_up_count}  真实涨停: {snap.real_limit_up}")
    print(f"   市场宽度: {_f_pct(snap.breadth)}  涨停占比: {_f_pct(snap.limit_up_ratio)}")
    print(f"   情绪: {snap.sentiment}  评分: {_f(snap.score)}")


def _f(value) -> str:
    return "--" if value is None else f"{value:g}"


def _f_pct(value) -> str:
    return "--" if value is None else f"{value * 100:.1f}%"


def _fmt_cap(value) -> str:
    if value is None:
        return "--"
    try:
        return f"{float(value) / 1e8:.0f}亿"
    except (TypeError, ValueError):
        return "--"
