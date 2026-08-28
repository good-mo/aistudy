"""
理财监控模块
============

读取理财持仓 CSV（理财编码 + 投入金额），加载产品详情，
评估收益/风险/期限告警，支持一次性检查与定时跟踪。

持仓 CSV 格式（推荐列名，兼容中英文）：
    理财编码, 产品名称, 投入金额, 年化收益, 风险等级, 期限天数, 到期日
    或
    code, name, amount, annual_rate, risk_level, term_days, maturity_date
"""

import os
from datetime import datetime
from typing import List, Optional

import pandas as pd

from ..models import FinancialProduct
from ..datasources import load_product_detail
from .alert_rules import LcAlertConfig
from common.logging_utils import get_logger

logger = get_logger(__name__)

# 桌面通知（可选依赖 plyer）
try:
    from plyer import notification

    _NOTIFICATION_AVAILABLE = True
except Exception:  # noqa: BLE001
    notification = None
    _NOTIFICATION_AVAILABLE = False

# 默认持仓 CSV 路径（项目根目录）
DEFAULT_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "lc_holding.csv",
)
# 默认产品编码清单
DEFAULT_CODES_CSV = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "lc", "product_codes.csv",
)

# 列名归一化映射（兼容中英文）
_COL_ALIAS = {
    "理财编码": "code",
    "code": "code",
    "产品代码": "code",
    "产品名称": "name",
    "name": "name",
    "投入金额": "amount",
    "amount": "amount",
    "成本": "amount",
    "年化收益": "annual_rate",
    "annual_rate": "annual_rate",
    "风险等级": "risk_level",
    "risk_level": "risk_level",
    "期限天数": "term_days",
    "term_days": "term_days",
    "到期日": "maturity_date",
    "maturity_date": "maturity_date",
    "到期日期": "maturity_date",
}


def load_holdings(csv_path: str) -> pd.DataFrame:
    """读取理财持仓 CSV，返回规范化 DataFrame（code/amount/...）。"""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"理财持仓文件不存在: {csv_path}")
    df = pd.read_csv(csv_path)
    df = df.rename(columns={c: _COL_ALIAS.get(str(c).strip(), str(c).strip()) for c in df.columns})
    if "code" not in df.columns:
        raise ValueError("理财持仓 CSV 缺少列: code（理财编码）")
    if "amount" not in df.columns:
        # 默认按 1 份估算
        df["amount"] = 100000.0
    df["code"] = df["code"].astype(str).str.strip()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    if "annual_rate" in df.columns:
        df["annual_rate"] = pd.to_numeric(df["annual_rate"], errors="coerce").fillna(0)
    if "risk_level" in df.columns:
        df["risk_level"] = pd.to_numeric(df["risk_level"], errors="coerce").fillna(3).astype(int)
    if "term_days" in df.columns:
        df["term_days"] = pd.to_numeric(df["term_days"], errors="coerce").fillna(365).astype(int)
    return df


def build_products(holdings: pd.DataFrame, codes_csv: str = DEFAULT_CODES_CSV) -> List[dict]:
    """为每条持仓加载产品详情，返回（持仓信息 + FinancialProduct）字典列表。

    产品详情优先从本地 CSV 加载；加载失败时以持仓中的字段构造基础产品。
    """
    products = []
    for _, row in holdings.iterrows():
        code = row["code"]
        product = None
        if os.path.exists(codes_csv):
            try:
                product = load_product_detail(codes_csv, code)
            except Exception as e:  # noqa: BLE001
                logger.warning("加载产品 %s 失败: %s", code, e)
        if product is None:
            product = FinancialProduct(
                product_code=code,
                name=str(row.get("name", f"理财产品-{code}")),
                annual_rate=float(row.get("annual_rate", 3.0)),
                risk_level=int(row.get("risk_level", 3)),
                term_days=int(row.get("term_days", 365)),
            )
            logger.info("产品 %s 未在 CSV 找到详情，使用持仓字段构造基础产品", code)
        else:
            # 持仓 CSV 提供的字段优先于产品详情（更精确），仅补充缺失字段
            if row.get("name") and pd.notna(row.get("name")):
                product.name = str(row["name"])
            if row.get("annual_rate") and pd.notna(row.get("annual_rate")):
                product.annual_rate = float(row["annual_rate"])
            if row.get("risk_level") and pd.notna(row.get("risk_level")):
                product.risk_level = int(row["risk_level"])
            if row.get("term_days") and pd.notna(row.get("term_days")):
                product.term_days = int(row["term_days"])
            logger.info(
                "加载产品成功 理财[%s] %s | 预期年化 %.2f%% | 风险等级 R%d | 期限 %d 天",
                code, product.name, product.annual_rate, product.risk_level, product.term_days,
            )
        products.append({"holding": row, "product": product})
    return products


def _parse_maturity(row) -> Optional[datetime]:
    """从持仓行解析到期日。"""
    val = row.get("maturity_date")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


class LcMonitor:
    """理财监控器。"""

    def __init__(self, config: Optional[LcAlertConfig] = None):
        self.config = config or LcAlertConfig()

    def evaluate(self, products: List[dict]) -> List[str]:
        """评估告警，返回触发文案列表。"""
        messages: List[str] = []
        cfg = self.config

        for item in products:
            row = item["holding"]
            product = item["product"]
            code = product.product_code or str(row.get("code", ""))
            name = product.name or str(row.get("name", code))
            amount = float(row.get("amount", 0))

            # 1. 年化收益偏低
            annual_rate = float(product.annual_rate or row.get("annual_rate", 0))
            if annual_rate < cfg.min_annual_rate:
                messages.append(
                    f"{name}({code}) 预期年化 {annual_rate:.2f}%，低于阈值 {cfg.min_annual_rate}%，收益偏低"
                )

            # 2. 集中度 + 高风险
            risk = int(product.risk_level or row.get("risk_level", 3))
            if amount >= cfg.single_concentration_amt and risk >= cfg.high_risk_level:
                messages.append(
                    f"{name}({code}) 投入 ¥{amount:,.0f}，风险等级 R{risk}，集中度偏高建议分散"
                )

            # 3. 临近到期 / 开放
            maturity = _parse_maturity(row)
            if maturity is not None:
                days_left = (maturity - datetime.now()).days
                if 0 <= days_left <= cfg.near_term_days:
                    messages.append(
                        f"{name}({code}) 将于 {maturity:%Y-%m-%d} 到期（剩余 {days_left} 天），请关注赎回安排"
                    )
                elif days_left < 0:
                    messages.append(
                        f"{name}({code}) 已于 {maturity:%Y-%m-%d} 到期，请确认是否已赎回"
                    )

        # 组合整体收益偏低
        if products:
            total_annual = sum(
                float(p["product"].annual_rate or 0) * float(p["holding"].get("amount", 0))
                for p in products
            )
            total_amt = sum(float(p["holding"].get("amount", 0)) for p in products)
            if total_amt > 0 and total_annual / total_amt < cfg.min_annual_rate:
                messages.append(
                    f"组合加权年化 {(total_annual/total_amt):.2f}%，低于阈值 {cfg.min_annual_rate}%，整体收益偏低"
                )

        return messages

    def report(self, messages: List[str]) -> None:
        """打印告警并推送桌面通知。"""
        if not messages:
            return
        body = "；".join(messages)
        logger.warning("理财监控告警：%s", body)
        if self.config.enable_console:
            print(f"\n\033[91m\033[1m⚠️  理财监控告警\033[0m")
            for m in messages:
                print(f"  \033[91m⚠ {m}\033[0m")
            print()
        if self.config.enable_notify and _NOTIFICATION_AVAILABLE:
            try:
                notification.notify(
                    title="📢 理财监控告警",
                    message=body[:200],
                    app_name="理财监控",
                    timeout=10,
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("桌面通知失败: %s", e)

    def log_holdings(self, products: List[dict]) -> None:
        """记录本次监控的理财持仓投入明细与汇总（便于留档排查）。"""
        if not products:
            logger.info("理财监控：无持仓数据")
            return
        # 单条持仓投入明细（产品详情日志见 build_products）
        total_amt = 0.0
        for item in products:
            row = item["holding"]
            product = item["product"]
            code = product.product_code or str(row.get("code", ""))
            name = product.name or str(row.get("name", code))
            amount = float(row.get("amount", 0) or 0)
            total_amt += amount
            logger.info(
                "理财持仓明细 理财[%s] %s | 投入 ¥%.2f",
                code, name, amount,
            )
        logger.info("理财持仓汇总 | 共 %d 条 | 总投入 ¥%.2f", len(products), total_amt)

    def check(self, products: List[dict]) -> List[str]:
        """评估并输出告警，返回触发文案（便于测试）。"""
        # 将本次监控的理财持仓数据写入日志
        self.log_holdings(products)
        messages = self.evaluate(products)
        if messages:
            self.report(messages)
        else:
            logger.info("理财监控：未触发告警")
        return messages


def main_once(holdings_csv: str, codes_csv: str = DEFAULT_CODES_CSV,
              config: Optional[LcAlertConfig] = None) -> List[str]:
    """执行一次理财监控：读持仓 → 加载产品 → 评估告警。返回触发文案。"""
    holdings = load_holdings(holdings_csv)
    products = build_products(holdings, codes_csv)
    monitor = LcMonitor(config)
    return monitor.check(products)
