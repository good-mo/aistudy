"""理财产品深度分析命令行入口。

用法：
    python -m lc_core.cli.analyze [--csv PATH] [--code CODE,...] [--risk N]
                                  [--goal 短期理财|稳健增值|财富增值|子女教育|退休养老]
                                  [--horizon <3月|3-12月|1-3年|3-5年|>5年] [--liquidity 低|中|高]
"""

import argparse
import os
import sys

from common.logging_utils import get_logger, setup_logging

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="理财产品深度分析系统 (lc_core)")
    parser.add_argument("--csv", type=str, default="",
                        help="本地 CSV 数据文件路径（默认 product_codes.csv）")
    parser.add_argument("--code", type=str, default="",
                        help="指定产品代码，逗号分隔")
    parser.add_argument("--risk", type=int, default=3, choices=[1, 2, 3, 4, 5],
                        help="风险承受能力 1-5（默认 3）")
    parser.add_argument("--goal", type=str, default="稳健增值",
                        choices=["短期理财", "稳健增值", "财富增值", "子女教育", "退休养老"])
    parser.add_argument("--horizon", type=str, default="1-3年",
                        choices=["<3月", "3-12月", "1-3年", "3-5年", ">5年"])
    parser.add_argument("--liquidity", type=str, default="中", choices=["低", "中", "高"])
    args = parser.parse_args()

    setup_logging()
    logger.info(
        "理财分析启动：risk=%s goal=%s horizon=%s liquidity=%s code=%s",
        args.risk, args.goal, args.horizon, args.liquidity, args.code or "全部",
    )

    from lc_core.models import FinancialProduct, InvestorProfile
    from lc_core.datasources import CMBDataSource, SPDBDataSource, load_product_detail
    from lc_core.analysis import DeepProductAnalyzer

    profile = InvestorProfile(
        risk_tolerance=args.risk,
        investment_goal=args.goal,
        investment_horizon=args.horizon,
        liquidity_need=args.liquidity,
        age_range="30-50",
    )

    print(f"\n{'='*80}")
    print(f"📊 理财产品深度分析系统 (lc_core v1.0)")
    print(f"{'='*80}")
    print(f"👤 画像：风险R{args.risk} | {args.goal} | {args.horizon} | 流动性{args.liquidity}")

    # 选择数据源
    if args.code:
        codes = [c.strip() for c in args.code.split(",") if c.strip()]
        print(f"\n📡 从本地 CSV 加载 {len(codes)} 个指定产品...")
        logger.info("从本地 CSV 加载 %d 个指定产品：%s", len(codes), codes)
        csv_path = args.csv or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "lc", "product_codes.csv",
        )
        products = []
        for code in codes:
            p = load_product_detail(csv_path, code)
            if p:
                products.append(p)
            else:
                logger.warning("未加载到产品：%s", code)
    else:
        # 尝试 API，失败回退 CSV
        print("\n📡 正在连接招商银行理财 API...")
        logger.info("尝试从招商银行 API 拉取全部理财产品...")
        raw = CMBDataSource.fetch_all_products(max_pages=45)
        products = [CMBDataSource.to_financial_product(r) for r in raw] if raw else []
        if not products:
            print("❌ 无法获取招行数据，回退到本地 CSV 模式")
            logger.warning("招行 API 无数据，回退到本地 CSV 模式")
            csv_path = args.csv or os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "lc", "product_codes.csv",
            )
            products = []
            from lc_core.datasources import load_product_codes
            codes = load_product_codes(csv_path)
            for code in codes:
                p = load_product_detail(csv_path, code)
                if p:
                    products.append(p)

    logger.info("加载产品 %d 款", len(products))
    print(f"✅ 加载 {len(products)} 款产品")

    # 逐产品深度分析
    print(f"\n{'='*80}")
    print(f"🔍 深度分析（前 {min(len(products), 10)} 款）")
    print(f"{'='*80}")
    for i, p in enumerate(products[:10]):
        try:
            dpa = DeepProductAnalyzer(p)
            report = dpa.full_report(profile=profile)
            print(f"\n[{i+1}] {p.name if hasattr(p, 'name') else p.code} "
                  f"| 综合得分 {report['综合评分']['综合得分']:.1f} | {report['买卖建议']}")
        except Exception as e:
            logger.exception("产品分析失败：%s", getattr(p, "code", getattr(p, "name", "?")))
            print(f"\n[{i+1}] 分析失败: {e}")

    logger.info("理财分析完成，共处理 %d 款产品", min(len(products), 10))
    print(f"\n✅ 分析完成，共处理 {min(len(products), 10)} 款产品")


if __name__ == "__main__":
    main()
