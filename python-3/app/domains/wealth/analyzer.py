"""
app.domains.wealth.analyzer —— 理财产品深度分析

从原始 lc_core 提炼而来，提供投资者画像 + 产品深度分析能力。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pandas as pd

from app.core.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class InvestorProfile:
    """投资者画像。"""

    risk_tolerance: int = 3  # 1-5
    investment_goal: str = "稳健增值"
    investment_horizon: str = "1-3年"
    liquidity_need: str = "中"
    age_range: str = "30-50"


@dataclass
class FinancialProduct:
    """理财产品。"""

    code: str = ""
    name: str = ""
    expected_rate: float = 0.0
    risk_level: int = 3
    term_days: int = 365
    min_amount: float = 0.0
    description: str = ""


class DeepProductAnalyzer:
    """产品深度分析器。"""

    def __init__(self, product: FinancialProduct):
        self.product = product

    def full_report(self, profile: InvestorProfile | None = None) -> dict:
        """生成完整分析报告。"""
        profile = profile or InvestorProfile()
        rate = self.product.expected_rate
        risk = self.product.risk_level

        # 综合评分（0-100）
        score = 50.0
        # 收益评分
        score += min(max((rate - 2.0) * 15, 0), 30)
        # 风险匹配
        risk_diff = abs(risk - profile.risk_tolerance)
        score -= risk_diff * 8
        # 流动性
        if profile.liquidity_need == "高" and self.product.term_days > 365:
            score -= 10
        elif profile.liquidity_need == "低" and self.product.term_days <= 365:
            score += 5
        score = max(0, min(score, 100))

        # 买卖建议
        if score >= 70:
            advice = "建议购买"
        elif score >= 55:
            advice = "可以考虑"
        elif score >= 40:
            advice = "谨慎评估"
        else:
            advice = "不建议购买"

        return {
            "产品": self.product.name,
            "代码": self.product.code,
            "综合评分": {"综合得分": round(score, 1)},
            "买卖建议": advice,
            "预期年化": f"{rate:.2f}%",
            "风险等级": f"R{risk}",
        }


class WealthAnalyzer:
    """理财产品分析器（深度 + 汇总）。"""

    def __init__(self, portfolio_csv: str | None = None):
        self._portfolio_csv = portfolio_csv or str(
            Path(__file__).resolve().parent.parent.parent.parent / "portfolio.csv"
        )
        self._products: List[FinancialProduct] = []

    def load_portfolio(self) -> pd.DataFrame:
        """加载持仓 CSV。"""
        if not os.path.exists(self._portfolio_csv):
            logger.warning("持仓文件不存在: %s", self._portfolio_csv)
            return pd.DataFrame()
        # 空文件 / 无内容时优雅返回空表，避免 EmptyDataError 报错刷屏
        if os.path.getsize(self._portfolio_csv) == 0:
            logger.warning("持仓文件为空: %s", self._portfolio_csv)
            return pd.DataFrame()
        try:
            df = pd.read_csv(self._portfolio_csv)
            logger.info("加载持仓 %d 行", len(df))
            return df
        except pd.errors.EmptyDataError:
            logger.warning("持仓文件无有效列（内容为空）: %s", self._portfolio_csv)
            return pd.DataFrame()
        except Exception as e:  # noqa: BLE001
            logger.error("持仓 CSV 解析失败: %s", e)
            return pd.DataFrame()

    def load_products(self, df: pd.DataFrame | None = None) -> List[FinancialProduct]:
        """从持仓加载产品对象。"""
        df = df if df is not None else self.load_portfolio()
        products = []
        if df.empty:
            return products
        code_col = next((c for c in ("code", "产品代码", "product_code") if c in df.columns), None)
        rate_col = next((c for c in ("expected_rate", "预期年化", "annual_rate", "年化收益", "rate") if c in df.columns), None)
        risk_col = next((c for c in ("risk_level", "风险等级", "risk") if c in df.columns), None)
        for _, row in df.iterrows():
            products.append(FinancialProduct(
                code=str(row.get(code_col, "")) if code_col else "",
                name=str(row.get("name", row.get("产品名称", ""))),
                expected_rate=float(row.get(rate_col, 0) or 0) if rate_col else 0.0,
                risk_level=int(row.get(risk_col, 3) or 3) if risk_col else 3,
                term_days=int(row.get("term_days", row.get("期限", 365)) or 365),
            ))
        self._products = products
        return products

    def analyze(self, profile: InvestorProfile | None = None) -> list[dict]:
        """深度分析所有产品，返回报告列表。"""
        if not self._products:
            self.load_products()
        profile = profile or InvestorProfile()
        reports = []
        for p in self._products[:10]:
            try:
                analyzer = DeepProductAnalyzer(p)
                reports.append(analyzer.full_report(profile=profile))
            except Exception as e:  # noqa: BLE001
                logger.exception("产品分析失败：%s", p.code)
                reports.append({"产品": p.name, "错误": str(e)})
        return reports

    def summarize(self) -> dict:
        """汇总持仓概况。"""
        df = self.load_portfolio()
        if df.empty:
            return {"total_products": 0, "total_amount": 0}
        amount_col = None
        for col in ("金额", "amount", "持有金额", "市值"):
            if col in df.columns:
                amount_col = col
                break
        total_amount = 0.0
        if amount_col:
            total_amount = df[amount_col].sum()
        return {
            "total_products": len(df),
            "total_amount": total_amount,
            "columns": list(df.columns),
        }
