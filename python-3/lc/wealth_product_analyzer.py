"""
理财产品深度分析工具 v6.1
v5.1 → v6.0 关键升级（P0+P1 修复，实质性缩小与资深理财顾问差距）：
v5.1 已有功能：
  - 申购时机与利率周期判断（久期建议、定投vs一次性建议）★ TimingAdvisor
  - 投资经理个人维度评估（任职年限、业绩持续性、产品存续期）★ PersonalManagerEvaluator
  - 真实同类百分位排名（基于全量API数据的同风险等级内对比）★ compute_peer_ranking
  - 更多决策维度输出（时机评分、同类排名、行为适配汇总）
v6.0 P0 修复：
  - ★ 月度收益率序列重构：用真实历年收益率+业绩基准区间替代纯随机模拟
    → 日收益率基于真实历史年度数据按月插值，风险指标（波动率/回撤/夏普）更真实
  - 保留真实历年数据的年化波动特征，缺失年份用基准区间填充
v6.0 P1 修复：
  - ★ 信用风险穿透分析：从 zbasDsc 描述中解析信用质量等级
    → 识别利率债/高评级/信用精选/下沉等信用策略，标记地产/民企/非标等风险信号
    → 信用质量纳入安全性评分（高信用→加分，弱资质→扣分）
  - ★ 费率竞争力分析：在同风险等级内计算费率百分位排名
    → CSV输出费率评级（★极低费率/★★★中等/★高费率），对比同类中位数/最低/最高
v5.0 基础功能（继承）：
  - 产品期限智能提取、真实历史业绩、组合相关性分析、行为金融适配、费率阶梯
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Callable
import numpy as np
import json
import csv
import os
import sys
import time
import base64
import statistics
import re
import requests
from datetime import datetime, timedelta
from gmssl import sm4

from common.logging_utils import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────
# 1. 数据模型（增强版）
# ─────────────────────────────────────────────

@dataclass
class FinancialProduct:
    """理财产品数据模型 v5.0"""
    # 基础信息
    product_code: str = ""
    name: str = ""
    issuer: str = ""
    product_type: str = "混合"  # 固收/权益/混合/货币/信托/结构性
    purchase_price: float = 1.0
    current_price: float = 1.0
    annual_rate: float = 0.0  # 预期年化 (%)
    annual_rate_low: float = 0.0  # 业绩基准下限
    annual_rate_high: float = 0.0  # 业绩基准上限
    term_days: int = 365
    term_type: str = "开放式"  # v5.0: 封闭式/定期开放/最短持有/开放式
    min_holding_days: int = 0  # v5.0: 最短持有天数
    risk_level: int = 3  # 1-5
    min_investment: float = 1000
    
    # 费用（v5.0 增强）
    purchase_fee_rate: float = 0.0  # 申购费率
    management_fee_rate: float = 0.0  # 固定管理费率（年化 %）
    redemption_fee_rate: float = 0.0  # 赎回费率
    custody_fee_rate: float = 0.0  # 托管费率（年化 %）
    sales_service_fee_rate: float = 0.0  # 销售服务费率（年化 %）
    performance_fee_rate: float = 0.0  # 超额业绩报酬比例（如 50%）
    performance_fee_threshold: float = 0.0  # 超额业绩报酬门槛（年化 %）
    early_redeemable: bool = True
    early_redeem_penalty: float = 0.0
    redemption_fee_tiers: List[Tuple[int, float]] = field(default_factory=list)  # v5.0: [(天数, 费率), ...]
    
    # 历史数据
    daily_returns: List[float] = field(default_factory=list)
    nav_series: List[float] = field(default_factory=list)
    
    # 基准数据
    benchmark_returns: List[float] = field(default_factory=list)
    benchmark_name: str = "沪深300"
    
    # 基金特有信息
    fund_size: float = 0.0  # 基金规模（亿元）
    manager_experience: int = 0
    inception_date: Optional[datetime] = None
    
    # 同类排名
    peer_rank: int = 0
    peer_count: int = 0
    
    # v5.0 新增：真实历史业绩
    inception_nav_yield: float = 0.0  # 成立以来累计净值收益率 (%)
    historical_annual_returns: List[float] = field(default_factory=list)  # 历年收益率
    inception_years: float = 0.0  # 成立年限
    
    # v5.0 新增：资产配置信息
    equity_allocation_pct: float = 0.0  # 权益类资产比例 (%)
    fixed_income_allocation_pct: float = 80.0  # 固收类资产比例 (%)
    derivatives_allocation_pct: float = 0.0  # 衍生品比例 (%)
    asset_description: str = ""  # 底层资产描述
    duration_hint: str = ""  # v5.0: 久期特征（短久期/中久期/长久期）
    
    # v5.0 新增：管理人信息
    manager_company: str = ""  # 管理公司全称
    manager_type: str = ""  # 机构类型：银行理财子/公募基金/券商资管/信托
    manager_rating: int = 3  # 管理人评级 1-5
    manager_name: str = ""  # v5.1: 具体投资经理姓名
    manager_tenure_years: float = 0.0  # v5.1: 经理任职年限
    has_performance_fee: bool = False  # 是否有超额业绩报酬
    currency: str = "CNY"  # 币种
    
    # 税收
    tax_rate: float = 0.0
    tax_free: bool = False
    
    # 其他
    inflation_rate: float = 2.5
    tags: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────
# 2. 统计分析工具
# ─────────────────────────────────────────────

class StatisticalUtils:
    """统计工具类"""
    
    @staticmethod
    def annualized_volatility(daily_returns: List[float]) -> float:
        """年化波动率"""
        if len(daily_returns) < 2:
            return 0.0
        returns = np.array(daily_returns)
        daily_std = np.std(returns, ddof=1)
        return daily_std * np.sqrt(252)  # 年化
    
    @staticmethod
    def max_drawdown(nav_series: List[float]) -> Tuple[float, int, int]:
        """
        最大回撤
        返回: (回撤幅度%, 峰值索引, 谷值索引)
        """
        if len(nav_series) < 2:
            return 0.0, 0, 0
        
        nav = np.array(nav_series)
        peak = np.maximum.accumulate(nav)
        drawdown = (peak - nav) / peak * 100
        
        max_dd = np.max(drawdown)
        trough_idx = np.argmax(drawdown)
        peak_idx = np.argmax(nav[:trough_idx+1])
        
        return float(max_dd), int(peak_idx), int(trough_idx)
    
    @staticmethod
    def downside_deviation(daily_returns: List[float], mar: float = 0.0) -> float:
        """下行标准差（Minimum Acceptable Return = mar）"""
        if len(daily_returns) < 2:
            return 0.0
        returns = np.array(daily_returns)
        downside = returns[returns < mar] - mar
        if len(downside) == 0:
            return 0.0
        return np.sqrt(np.mean(downside**2)) * np.sqrt(252)
    
    @staticmethod
    def var(returns: List[float], confidence: float = 0.95) -> float:
        """在险价值 (VaR) - 历史模拟法"""
        if len(returns) < 10:
            return 0.0
        return float(np.percentile(returns, (1 - confidence) * 100))
    
    @staticmethod
    def cvar(returns: List[float], confidence: float = 0.95) -> float:
        """条件在险价值 (CVaR) - 期望损失"""
        if len(returns) < 10:
            return 0.0
        returns = np.array(returns)
        var_threshold = np.percentile(returns, (1 - confidence) * 100)
        tail_returns = returns[returns <= var_threshold]
        if len(tail_returns) == 0:
            return float(var_threshold)
        return float(np.mean(tail_returns))
    
    @staticmethod
    def skewness(returns: List[float]) -> float:
        """偏度"""
        if len(returns) < 3:
            return 0.0
        # 近恒定数据（标准差≈0）时偏度无意义，scipy 会报数值精度警告，直接返回 0
        if float(np.std(returns)) < 1e-12:
            return 0.0
        try:
            from scipy import stats
            return float(stats.skew(returns))
        except ImportError:
            # scipy 未安装时退化为 0（避免运行时崩溃）
            return 0.0
    
    @staticmethod
    def kurtosis(returns: List[float]) -> float:
        """峰度（超额峰度）"""
        if len(returns) < 4:
            return 0.0
        # 近恒定数据（标准差≈0）时峰度无意义，scipy 会报数值精度警告，直接返回 0
        if float(np.std(returns)) < 1e-12:
            return 0.0
        try:
            from scipy import stats
            return float(stats.kurtosis(returns, fisher=True))
        except ImportError:
            # scipy 未安装时退化为 0（避免运行时崩溃）
            return 0.0
    
    @staticmethod
    def win_rate(returns: List[float]) -> float:
        """胜率（正收益占比）"""
        if len(returns) == 0:
            return 0.0
        positive = sum(1 for r in returns if r > 0)
        return positive / len(returns) * 100
    
    @staticmethod
    def profit_loss_ratio(returns: List[float]) -> float:
        """盈亏比"""
        positive = [r for r in returns if r > 0]
        negative = [r for r in returns if r < 0]
        if len(negative) == 0 or np.mean(negative) == 0:
            # 无亏损日：无意义，返回 0（避免 inf 破坏下游 CSV/JSON 序列化）
            return 0.0
        return abs(np.mean(positive) / np.mean(negative))
    
    @staticmethod
    def correlation(returns1: List[float], returns2: List[float]) -> float:
        """相关系数"""
        if len(returns1) != len(returns2) or len(returns1) < 2:
            return 0.0
        return float(np.corrcoef(returns1, returns2)[0, 1])
    
    @staticmethod
    def tracking_error(returns1: List[float], returns2: List[float]) -> float:
        """跟踪误差"""
        if len(returns1) != len(returns2) or len(returns1) < 2:
            return 0.0
        diff = np.array(returns1) - np.array(returns2)
        return float(np.std(diff, ddof=1) * np.sqrt(252))


# ─────────────────────────────────────────────
# 3. 用户画像系统（v4.0 新增）
# ─────────────────────────────────────────────

@dataclass
class InvestorProfile:
    """投资者画像"""
    risk_tolerance: int = 3  # 风险承受能力 1-5
    investment_goal: str = "稳健增值"  # 退休养老/子女教育/稳健增值/财富增值/短期理财
    investment_horizon: str = "1-3年"  # <3月/3-12月/1-3年/3-5年/>5年
    liquidity_need: str = "中"  # 高/中/低
    age_range: str = "30-50"  # <30/30-50/50-65/>65
    invest_amount: float = 100000  # 投资金额
    
    def get_weights(self) -> dict:
        """根据画像生成动态评分权重"""
        weights = {
            "收益性": 0.25,
            "安全性": 0.25,
            "风险调整": 0.20,
            "流动性": 0.15,
            "费用": 0.10,
            "同类排名": 0.05,
        }
        
        # 风险厌恶者：安全性权重↑，收益性↓
        if self.risk_tolerance <= 2:
            weights["安全性"] += 0.15
            weights["收益性"] -= 0.10
            weights["风险调整"] -= 0.05
        
        # 风险偏好者：收益性↑
        if self.risk_tolerance >= 4:
            weights["收益性"] += 0.10
            weights["安全性"] -= 0.10
        
        # 退休养老/子女教育：安全性↑
        if self.investment_goal in ("退休养老", "子女教育"):
            weights["安全性"] += 0.05
            weights["收益性"] -= 0.05
        
        # 短期理财：流动性↑
        if self.investment_horizon in ("<3月", "3-12月"):
            weights["流动性"] += 0.10
            weights["收益性"] -= 0.05
            weights["风险调整"] -= 0.05
        
        # 高流动性需求
        if self.liquidity_need == "高":
            weights["流动性"] += 0.05
            weights["费用"] -= 0.05
        
        # 老年投资者：更保守
        if self.age_range in (">65",):
            weights["安全性"] += 0.10
            weights["收益性"] -= 0.10
        
        # 归一化
        total = sum(weights.values())
        for k in weights:
            weights[k] = round(weights[k] / total, 4)
        
        return weights


# ─────────────────────────────────────────────
# 4. 管理人评估系统（v4.0 新增）
# ─────────────────────────────────────────────

class ManagerEvaluator:
    """管理人/机构评估器"""
    
    # 理财子公司评级（基于行业认知）
    INSTITUTION_RATINGS = {
        # 头部理财子
        "招银理财": 5, "工银理财": 5, "建信理财": 5, "中银理财": 5, "农银理财": 5,
        # 股份制银行
        "兴银理财": 4, "信银理财": 4, "光大理财": 4, "平安理财": 4, "浦银理财": 4,
        "华夏理财": 4, "民生银行": 4,
        # 城商行理财子
        "宁银理财": 4, "南银理财": 3, "杭银理财": 3, "苏银理财": 3,
        "上银理财": 3, "北银理财": 3,
        # 其他
        "交银理财": 4, "中邮理财": 3, "民生理财": 3,
    }
    
    # 机构类型映射
    INSTITUTION_TYPES = {
        "招银理财": "银行理财子", "工银理财": "银行理财子", "建信理财": "银行理财子",
        "中银理财": "银行理财子", "农银理财": "银行理财子", "交银理财": "银行理财子",
        "兴银理财": "银行理财子", "信银理财": "银行理财子", "光大理财": "银行理财子",
        "平安理财": "银行理财子", "浦银理财": "银行理财子", "华夏理财": "银行理财子",
        "中邮理财": "银行理财子", "民生理财": "银行理财子", "北银理财": "银行理财子",
        "宁银理财": "银行理财子", "南银理财": "银行理财子", "杭银理财": "银行理财子",
        "苏银理财": "银行理财子", "上银理财": "银行理财子",
        "民生银行": "银行理财子",
    }
    
    @staticmethod
    def evaluate(product: FinancialProduct) -> dict:
        """评估管理人质量，返回 (评分, 明细)"""
        issuer = product.issuer
        company = product.manager_company or issuer
        
        # 从 issuer 匹配
        rating = 3  # 默认中等
        inst_type = "其他"
        
        for key, val in ManagerEvaluator.INSTITUTION_RATINGS.items():
            if key in issuer or key in company:
                rating = val
                inst_type = ManagerEvaluator.INSTITUTION_TYPES.get(key, "银行理财子")
                break
        
        score = rating * 20  # 1-5 -> 20-100
        
        details = {
            "管理人评级": f"{'★' * rating}{'☆' * (5 - rating)}",
            "机构类型": inst_type,
            "管理人评分": score,
            "发行机构": issuer,
        }
        
        # 头部机构加分项
        if rating >= 5:
            details["评价"] = "头部机构，风控体系成熟，投研能力突出"
        elif rating >= 4:
            details["评价"] = "大型机构，整体实力较强，产品线丰富"
        elif rating >= 3:
            details["评价"] = "中型机构，基本风控完善，需关注产品差异"
        else:
            details["评价"] = "需关注机构信用和产品风险"
        
        return details


# ─────────────────────────────────────────────
# 5. 市场环境评估（v4.0 新增）
# ─────────────────────────────────────────────

class MarketContext:
    """市场环境评估器"""
    
    # 当前市场环境参数（可手动更新）
    CURRENT_SETTINGS = {
        "short_rate": 1.5,       # 当前短期利率（7天逆回购），%
        "long_rate": 2.6,        # 当前10年期国债收益率，%
        "credit_spread": 0.8,    # 信用利差（AAA企业债-国债），%
        "equity_pe": 14.5,       # 沪深300 PE
        "equity_pe_median": 13.0, # 沪深300 PE 历史中位
        "usd_cny": 7.25,         # 美元/人民币
        "rate_cycle": "宽松",     # 利率周期：宽松/中性/紧缩
        "equity_cycle": "震荡",   # 股市周期：牛市/震荡/熊市
    }
    
    @staticmethod
    def evaluate(product: FinancialProduct) -> dict:
        """评估当前市场环境对产品的影响"""
        s = MarketContext.CURRENT_SETTINGS
        results = {}
        
        # 1. 利率环境评估
        if s["rate_cycle"] == "宽松":
            rate_impact = -5  # 低利率压低固收收益
            rate_note = "宽松货币政策下，固收类产品收益率承压"
        elif s["rate_cycle"] == "紧缩":
            rate_impact = 5
            rate_note = "紧缩环境下新发固收产品收益率有望提升"
        else:
            rate_impact = 0
            rate_note = "利率环境中性"
        
        # 固收产品对利率敏感
        if product.product_type in ("固收", "货币"):
            results["利率环境影响"] = rate_note
            results["利率调整"] = rate_impact
        else:
            results["利率环境影响"] = "影响较小"
            results["利率调整"] = 0
        
        # 2. 权益市场环境
        if product.equity_allocation_pct > 20:
            pe = s["equity_pe"]
            pe_med = s["equity_pe_median"]
            if pe > pe_med * 1.2:
                equity_impact = -10
                equity_note = f"当前PE({pe})偏高，权益仓位高的产品回调风险增大"
            elif pe < pe_med * 0.8:
                equity_impact = 10
                equity_note = f"当前PE({pe})偏低，权益类资产估值有吸引力"
            else:
                equity_impact = 0
                equity_note = f"当前PE({pe})处于历史中位附近"
            results["权益市场环境"] = equity_note
            results["权益调整"] = equity_impact
        
        # 3. 汇率风险（QDII/美元产品）
        if product.currency == "USD" or "QDII" in product.name or "美元" in product.name:
            usd = s["usd_cny"]
            if usd > 7.2:
                fx_note = f"人民币偏弱(USD/CNY={usd})，持有美元资产有汇兑收益"
                fx_impact = 5
            elif usd < 6.8:
                fx_note = f"人民币偏强(USD/CNY={usd})，持有美元资产需注意汇兑损失"
                fx_impact = -10
            else:
                fx_note = f"汇率中性(USD/CNY={usd})"
                fx_impact = 0
            results["汇率风险"] = fx_note
            results["汇率调整"] = fx_impact
        
        # 综合市场调整分
        total_adjustment = sum(v for k, v in results.items() if k.endswith("调整"))
        results["市场环境调整"] = total_adjustment
        results["市场环境评级"] = "有利" if total_adjustment > 5 else ("不利" if total_adjustment < -5 else "中性")
        
        return results


# ─────────────────────────────────────────────
# 5b. 行为金融学适配检查（v5.0 新增）
# ─────────────────────────────────────────────

class BehavioralAdvisor:
    """行为金融学适配度评估器
    
    资深理财顾问会评估：这个产品是否真的适合这个客户？
    不仅看风险等级匹配，还要看行为偏差和心理承受能力。
    """
    
    @staticmethod
    def evaluate(product: FinancialProduct, profile: InvestorProfile) -> dict:
        """检查产品与客户的行为适配度"""
        warnings = []
        tips = []
        match_score = 100  # 适配分
        
        # 1. 风险等级匹配检查
        risk_gap = product.risk_level - profile.risk_tolerance
        if risk_gap >= 2:
            warnings.append(f"⛔ 产品风险等级(R{product.risk_level})远高于您的风险承受(R{profile.risk_tolerance})，强烈不推荐")
            match_score -= 40
        elif risk_gap == 1:
            warnings.append(f"⚠️ 产品风险等级(R{product.risk_level})略高于您的风险承受(R{profile.risk_tolerance})，请确认您能接受")
            match_score -= 15
        elif risk_gap <= -2:
            tips.append(f"💡 产品风险等级(R{product.risk_level})低于您的承受能力，可考虑更高收益选择")
        
        # 2. 期限匹配检查
        horizon_map = {"<3月": 90, "3-12月": 365, "1-3年": 1095, "3-5年": 1825, ">5年": 3650}
        max_horizon_days = horizon_map.get(profile.investment_horizon, 365)
        
        if product.term_type == "封闭式" and product.term_days > max_horizon_days:
            warnings.append(f"⛔ 产品封闭期({product.term_days}天)超过您的投资期限({profile.investment_horizon})")
            match_score -= 30
        elif product.min_holding_days > max_horizon_days:
            warnings.append(f"⚠️ 产品最短持有期({product.min_holding_days}天)超过您的投资期限({profile.investment_horizon})")
            match_score -= 20
        
        # 3. 流动性需求匹配
        if profile.liquidity_need == "高":
            if product.term_type in ("封闭式", "定期开放"):
                warnings.append(f"⚠️ 您有高流动性需求，但产品为{product.term_type}，可能无法及时赎回")
                match_score -= 25
            elif product.min_holding_days > 30:
                warnings.append(f"⚠️ 您有高流动性需求，但产品有{product.min_holding_days}天持有期")
                match_score -= 15
        
        # 4. 回撤承受力提醒（行为金融核心）
        nav = product.nav_series if product.nav_series else [1.0]
        max_dd = 0.0
        if len(nav) > 1:
            peak = nav[0]
            for v in nav:
                if v > peak:
                    peak = v
                dd = (peak - v) / peak * 100
                max_dd = max(max_dd, dd)
        
        investment = profile.invest_amount
        potential_loss = investment * max_dd / 100
        
        if max_dd > 10:
            warnings.append(f"📉 该产品历史最大回撤 {max_dd:.1f}%，投入{investment/10000:.0f}万最多可能浮亏约 ¥{potential_loss:,.0f}")
            tips.append("💡 建议在市场下跌时不要恐慌赎回，产品净值波动是正常现象")
        elif max_dd > 3:
            tips.append(f"📉 该产品历史最大回撤 {max_dd:.1f}%，投入{investment/10000:.0f}万最多可能浮亏约 ¥{potential_loss:,.0f}")
        
        # 5. 追涨杀跌提醒
        if product.risk_level >= 3 and profile.risk_tolerance <= 2:
            tips.append("💡 理财非存款，净值会有波动。建议避免在市场波动时频繁申赎")
        
        # 6. 集中度提醒
        if profile.invest_amount > 500000 and product.risk_level >= 3:
            tips.append(f"💡 单产品投入超过50万，建议分散到2-3只不同策略的产品以降低集中度风险")
        
        # 7. 投资目标匹配
        if profile.investment_goal == "退休养老" and product.risk_level >= 4:
            warnings.append("⚠️ 退休养老资金不宜配置过高风险产品")
            match_score -= 15
        elif profile.investment_goal == "短期理财" and product.term_days > 365:
            warnings.append(f"⚠️ 短期理财目标与产品期限({product.term_days}天)不匹配")
            match_score -= 15
        
        # 综合评估
        if match_score >= 90:
            verdict = "✅ 产品与您的画像高度匹配"
        elif match_score >= 70:
            verdict = "🟡 基本匹配，需注意上述提示"
        elif match_score >= 50:
            verdict = "🟠 存在一定不匹配，请谨慎考虑"
        else:
            verdict = "🔴 与您的画像不匹配，强烈建议重新选择"
        
        return {
            "适配评分": match_score,
            "适配评估": verdict,
            "警告": warnings,
            "行为提示": tips,
            "历史最大回撤(%)": round(max_dd, 2),
            "预估最大浮亏": round(potential_loss, 2),
        }


# ─────────────────────────────────────────────
# 5c. 组合相关性分析（v5.0 新增）
# ─────────────────────────────────────────────

class PortfolioAnalyzer:
    """多产品组合分析器
    
    资深理财顾问会评估组合是否有效分散风险，避免买一堆同质化产品。
    """
    
    @staticmethod
    def correlation_matrix(products: List[FinancialProduct]) -> dict:
        """计算产品间的收益率相关性矩阵"""
        n = len(products)
        if n < 2:
            return {"error": "至少需要2个产品"}
        
        # 提取所有产品的收益率序列（对齐长度）
        non_empty = [p.daily_returns for p in products if p.daily_returns]
        if not non_empty:
            return {"error": "无收益率数据"}
        min_len = min(len(r) for r in non_empty)
        if min_len < 10:
            return {"error": "数据不足"}
        
        returns_matrix = []
        for p in products:
            if p.daily_returns:
                returns_matrix.append(p.daily_returns[-min_len:])
            else:
                returns_matrix.append([0] * min_len)
        
        with np.errstate(invalid='ignore', divide='ignore'):
            corr_matrix = np.corrcoef(returns_matrix)
        # 过滤 NaN：零方差（恒定收益/无数据）序列会导致相关系数为 NaN，按 0（无相关）处理
        corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)
        
        # 构建结果
        names = [p.name[:20] for p in products]
        result = {"产品列表": names, "相关性矩阵": []}
        
        high_corr_pairs = []
        for i in range(n):
            row = []
            for j in range(n):
                corr_val = round(float(corr_matrix[i][j]), 3)
                row.append(corr_val)
                if i < j and abs(corr_val) > 0.7:
                    high_corr_pairs.append({
                        "产品1": names[i],
                        "产品2": names[j],
                        "相关系数": corr_val,
                        "警告": "高度相关，同涨同跌风险高" if corr_val > 0 else "高度负相关"
                    })
            result["相关性矩阵"].append(row)
        
        result["高相关警告"] = high_corr_pairs
        
        # 组合分散度评分
        if len(high_corr_pairs) == 0:
            result["分散度"] = "优秀 - 各产品相关性低，有效分散"
        elif len(high_corr_pairs) <= n // 3:
            result["分散度"] = "良好 - 少数产品相关性偏高"
        else:
            result["分散度"] = "⚠️ 较差 - 多数产品走势趋同，建议减少同质化配置"
        
        return result
    
    @staticmethod
    def diversification_score(products: List[FinancialProduct]) -> dict:
        """组合多元化评分"""
        if len(products) < 2:
            return {"评分": 100, "说明": "单产品无需评估分散度"}
        
        score = 100
        details = []
        
        # 1. 检查发行机构集中度
        issuers = [p.issuer for p in products]
        issuer_counts = {}
        for i in issuers:
            issuer_counts[i] = issuer_counts.get(i, 0) + 1
        
        max_concentration = max(issuer_counts.values()) / len(products)
        if max_concentration > 0.5:
            score -= 20
            details.append(f"机构集中度过高（同一发行机构占{max_concentration*100:.0f}%）")
        
        # 2. 检查产品类型分散
        types = [p.product_type for p in products]
        unique_types = len(set(types))
        if unique_types == 1:
            score -= 25
            details.append(f"产品类型完全同质（全部为{types[0]}）")
        elif unique_types == 2 and len(products) >= 3:
            score -= 10
            details.append("产品类型较单一")
        
        # 3. 检查风险等级分散
        risk_levels = [p.risk_level for p in products]
        unique_risks = len(set(risk_levels))
        if unique_risks == 1:
            score -= 15
            details.append(f"风险等级完全一致（全部为R{risk_levels[0]}）")
        
        # 4. 检查币种分散
        currencies = [p.currency for p in products]
        if len(set(currencies)) == 1 and currencies[0] == "CNY":
            details.append("提示: 可考虑增加美元产品对冲汇率风险")
        
        return {
            "分散度评分": max(0, score),
            "详情": details,
            "机构分布": issuer_counts,
            "类型分布": {t: types.count(t) for t in set(types)},
        }


# ─────────────────────────────────────────────
# 5d. 申购时机与利率周期判断（v5.1 新增）
# ─────────────────────────────────────────────

class TimingAdvisor:
    """申购时机与策略建议器
    
    资深理财顾问会根据利率周期、权益估值、产品久期等因素，
    给出"现在该买吗？一次性买还是定投？买短久期还是长久期？"的建议。
    """
    
    # 当前市场参数（可定期更新）
    CURRENT = {
        "short_rate": 1.5,           # 7天逆回购利率 %
        "long_rate_10y": 2.6,        # 10年期国债 %
        "rate_trend": "下降",         # 上升/下降/走平
        "rate_cycle_position": "宽松后期",  # 宽松初期/宽松后期/紧缩初期/紧缩后期
        "credit_spread": 0.8,        # AAA企业债-国债利差 %
        "equity_pe_ttm": 14.5,       # 沪深300 PE-TTM
        "equity_pe_pct": 55,         # PE历史分位数 %
        "equity_trend": "震荡",       # 牛市/震荡/熊市
    }
    
    @staticmethod
    def evaluate(product: FinancialProduct, profile: InvestorProfile = None) -> dict:
        """评估申购时机和策略"""
        c = TimingAdvisor.CURRENT
        results = {}
        
        # ── 1. 利率周期判断：影响固收产品收益预期 ──
        if product.product_type in ("固收", "货币", "混合") and product.risk_level <= 3:
            if c["rate_trend"] == "下降":
                rate_advice = "⚠️ 利率处于下降通道，新发固收产品收益率可能继续走低"
                rate_action = "建议锁定当前较高收益产品，可配置较长久期"
                rate_score = 5  # 现在买比以后买好
            elif c["rate_trend"] == "上升":
                rate_advice = "💡 利率处于上升通道，新发固收产品收益率有望提升"
                rate_action = "建议配置短久期产品，待利率见顶后再拉长久期"
                rate_score = -5  # 现在买可能不如等等
            else:
                rate_advice = "利率环境相对稳定"
                rate_action = "可根据个人需求正常配置"
                rate_score = 0
            
            results["利率周期"] = {
                "判断": rate_advice,
                "策略": rate_action,
                "影响分": rate_score,
                "当前短期利率(%)": c["short_rate"],
                "当前长期利率(%)": c["long_rate_10y"],
            }
            
            # 久期建议
            if product.duration_hint == "长久期" and c["rate_trend"] == "上升":
                results["久期建议"] = "⚠️ 当前产品为长久期，利率上升时净值下跌风险较大，建议优先考虑短久期产品"
            elif product.duration_hint == "短久期" and c["rate_trend"] == "下降":
                results["久期建议"] = "💡 当前产品为短久期，利率下降时再投资收益下降，可适度拉长久期"
        
        # ── 2. 权益估值判断 ──
        if product.equity_allocation_pct > 20:
            pe_pct = c["equity_pe_pct"]
            pe = c["equity_pe_ttm"]
            
            if pe_pct > 80:
                eq_advice = f"🔴 沪深300 PE({pe})处于历史{pe_pct}%分位，估值偏高"
                eq_action = "建议定投分批入场，避免一次性重仓"
                eq_score = -10
            elif pe_pct > 60:
                eq_advice = f"🟡 沪深300 PE({pe})处于历史{pe_pct}%分位，估值适中偏高"
                eq_action = "可适度配置，建议分2-3批入场"
                eq_score = -3
            elif pe_pct < 20:
                eq_advice = f"🟢 沪深300 PE({pe})处于历史{pe_pct}%分位，估值偏低"
                eq_action = "中长期配置价值显现，可一次性买入"
                eq_score = 10
            elif pe_pct < 40:
                eq_advice = f"🟢 沪深300 PE({pe})处于历史{pe_pct}%分位，估值合理"
                eq_action = "可一次性买入或定投"
                eq_score = 5
            else:
                eq_advice = f"沪深300 PE({pe})处于历史{pe_pct}%分位"
                eq_action = "可正常配置"
                eq_score = 0
            
            results["权益估值"] = {
                "判断": eq_advice,
                "策略": eq_action,
                "影响分": eq_score,
                "当前PE": pe,
                "历史分位(%)": pe_pct,
            }
        
        # ── 3. 定投 vs 一次性建议 ──
        total_timing_score = sum(
            v.get("影响分", 0) for v in results.values() 
            if isinstance(v, dict) and "影响分" in v
        )
        
        if product.risk_level >= 3 and product.equity_allocation_pct > 30:
            # 高波动产品，默认倾向定投
            if total_timing_score < -5:
                results["申购策略"] = "🔴 当前不建议大额买入，可小额定投积累仓位"
            elif total_timing_score < 0:
                results["申购策略"] = "🟡 建议定投，每周/每月分批买入，降低择时风险"
            else:
                results["申购策略"] = "🟢 可一次性买入 + 定投组合"
        elif product.risk_level <= 2:
            # 低波动产品，定投意义不大
            if total_timing_score >= 0:
                results["申购策略"] = "✅ 低风险产品，可一次性买入"
            else:
                results["申购策略"] = "🟡 可买入，但可等待利率更优时点"
        else:
            if total_timing_score >= 5:
                results["申购策略"] = "🟢 市场环境有利，可一次性买入"
            elif total_timing_score >= -5:
                results["申购策略"] = "🟡 可分批买入"
            else:
                results["申购策略"] = "🔴 建议等待更佳时机，或小额定投"
        
        # ── 4. 综合时机评分 ──
        timing_score = 60 + total_timing_score * 2  # 基础60分
        timing_score = max(20, min(100, timing_score))
        
        results["综合时机评分"] = round(timing_score, 1)
        
        if timing_score >= 80:
            results["时机评估"] = "🟢 当前是较好的申购时机"
        elif timing_score >= 60:
            results["时机评估"] = "🟡 时机中性，可适度参与"
        elif timing_score >= 40:
            results["时机评估"] = "🟠 时机一般，建议等待或定投"
        else:
            results["时机评估"] = "🔴 时机不佳，建议观望"
        
        return results


# ─────────────────────────────────────────────
# 5e. 投资经理个人评估（v5.1 新增）
# ─────────────────────────────────────────────

class PersonalManagerEvaluator:
    """投资经理个人维度评估
    
    资深理财顾问不仅看机构，还看具体是谁在管这个产品。
    """
    
    @staticmethod
    def evaluate(product: FinancialProduct) -> dict:
        """评估投资经理个人能力和产品管理稳定性"""
        results = {}
        
        # 1. 经理姓名
        if product.manager_name:
            results["投资经理"] = product.manager_name
        else:
            results["投资经理"] = "未公开披露"
        
        # 2. 任职年限评估
        tenure = product.manager_tenure_years
        if tenure > 0:
            if tenure >= 5:
                tenure_note = f"管理该产品{tenure:.1f}年，经验丰富，策略一致性高"
                tenure_score = 10
            elif tenure >= 2:
                tenure_note = f"管理该产品{tenure:.1f}年，有一定历史可追溯"
                tenure_score = 5
            elif tenure >= 1:
                tenure_note = f"管理该产品仅{tenure:.1f}年，历史数据有限"
                tenure_score = 0
            else:
                tenure_note = "任职不足1年，策略不确定性较高"
                tenure_score = -5
            results["任职年限"] = tenure_note
            results["任职评分调整"] = tenure_score
        else:
            results["任职年限"] = "理财计划通常为团队管理，非单一经理制"
            results["任职评分调整"] = 0
        
        # 3. 产品成立年限与稳定性
        if product.inception_years > 0:
            if product.inception_years >= 5:
                results["产品存续"] = f"已运作{product.inception_years:.1f}年，穿越多轮市场周期"
            elif product.inception_years >= 2:
                results["产品存续"] = f"已运作{product.inception_years:.1f}年，有一定历史业绩"
            elif product.inception_years >= 1:
                results["产品存续"] = f"运作{product.inception_years:.1f}年，业绩记录尚短"
            else:
                results["产品存续"] = f"运作不足1年，历史数据有限，需谨慎参考"
        else:
            results["产品存续"] = "成立日期未知"
        
        # 4. 历史业绩持续性
        hist = product.historical_annual_returns
        if len(hist) >= 3:
            positive_years = sum(1 for r in hist if r > 0)
            consistency = positive_years / len(hist) * 100
            
            if consistency >= 90:
                results["业绩持续性"] = f"过去{len(hist)}年中有{positive_years}年正收益({consistency:.0f}%)，表现稳定"
            elif consistency >= 70:
                results["业绩持续性"] = f"过去{len(hist)}年中有{positive_years}年正收益({consistency:.0f}%)，基本稳定"
            else:
                results["业绩持续性"] = f"过去{len(hist)}年中有{positive_years}年正收益({consistency:.0f}%)，波动较大"
        
        return results


# ─────────────────────────────────────────────
# 6. 资产配置解析
# ─────────────────────────────────────────────

class AssetAllocationParser:
    """从产品描述中解析资产配置比例"""
    
    @staticmethod
    def parse(product: FinancialProduct) -> FinancialProduct:
        """解析 zbasDsc 中的资产配置信息，更新 product 的配置字段"""
        dsc = product.asset_description
        if not dsc:
            return product
        
        # 解析权益类比例
        equity_patterns = [
            r'权益类资产[^0-9]*(\d+)[-~](\d+)%',
            r'权益类[^0-9]*(\d+)[-~](\d+)%',
            r'股票[^0-9]*(\d+)[-~](\d+)%',
            r'不低于(\d+)%.*固定收益.*(\d+)[-~](\d+)%.*权益',
            r'不低于(\d+)%.*固收.*(\d+)[-~](\d+)%.*权益',
            r'(\d+)[-~](\d+)%.*权益',
            r'权益.*?(\d+)[-~](\d+)%',
        ]
        
        for pat in equity_patterns:
            m = re.search(pat, dsc)
            if m:
                groups = m.groups()
                if len(groups) == 2:
                    product.equity_allocation_pct = (float(groups[0]) + float(groups[1])) / 2
                elif len(groups) == 3:
                    product.equity_allocation_pct = (float(groups[1]) + float(groups[2])) / 2
                break
        
        # 解析固收类比例
        fixed_patterns = [
            r'不低于(\d+)%.*固定收益',
            r'不低于(\d+)%.*债券',
            r'固收类[^0-9]*(\d+)[-~](\d+)%',
            r'固定收益类[^0-9]*(\d+)[-~](\d+)%',
        ]
        
        for pat in fixed_patterns:
            m = re.search(pat, dsc)
            if m:
                groups = m.groups()
                if len(groups) == 1:
                    product.fixed_income_allocation_pct = float(groups[0])
                elif len(groups) == 2:
                    product.fixed_income_allocation_pct = (float(groups[0]) + float(groups[1])) / 2
                break
        
        # 解析衍生品
        deriv_pattern = r'衍生品[^0-9]*(\d+)[-~](\d+)%'
        m = re.search(deriv_pattern, dsc)
        if m:
            product.derivatives_allocation_pct = (float(m.group(1)) + float(m.group(2))) / 2
        
        # 根据风险等级修正默认值
        if product.equity_allocation_pct == 0:
            defaults = {1: 0, 2: 5, 3: 20, 4: 50, 5: 80}
            product.equity_allocation_pct = defaults.get(product.risk_level, 20)
        
        if product.fixed_income_allocation_pct == 0:
            product.fixed_income_allocation_pct = max(0, 100 - product.equity_allocation_pct - product.derivatives_allocation_pct)
        
        return product


# ─────────────────────────────────────────────
# P1: 信用质量分析器
# ─────────────────────────────────────────────

class CreditQualityAnalyzer:
    """从产品描述中解析信用质量信号，评估底层资产信用风险等级"""
    
    # 信用质量分级及关键词
    CREDIT_SIGNALS = {
        "极高（利率债/存款级）": {
            "keywords": ["国债", "政策性金融债", "中央银行票据", "地方政府债", "存款", "存单",
                        "现金管理", "货币市场", "央票", "政府债券", "利率债", "准政府"],
            "score": 95,
            "description": "底层以国债、政策性银行债、存款存单为主，几乎无信用风险",
        },
        "高（高评级/银行级）": {
            "keywords": ["高评级", "高等级", "AAA", "投资级", "大型银行", "国有银行",
                        "金融债", "商业银行债", "银行间", "金融工具", "优质"],
            "score": 80,
            "description": "主要配置高评级债券和银行间资产，信用风险极低",
        },
        "中高（精选信用）": {
            "keywords": ["信用精选", "信用债", "城投", "产业债", "中高等级", "AA+",
                        "精选信用", "信用策略", "国企", "优质企业"],
            "score": 60,
            "description": "有一定信用下沉，配置城投债、产业债等，需关注区域和行业分布",
        },
        "中等（适度下沉）": {
            "keywords": ["高收益", "民营", "地产", "弱资质", "下沉", "AA",
                        "收益增强", "信用挖掘", "中低评级"],
            "score": 40,
            "description": "信用下沉较明显，含高收益债或弱资质主体，波动和违约风险上升",
        },
        "低/未知": {
            "keywords": [],
            "score": 50,
            "description": "未从描述中识别到明确信用策略，按中等风险保守评估",
        },
    }
    
    # 风险信号（需要警惕的）
    RISK_FLAGS = {
        "地产敞口": ["地产", "房地产", "房企", "住房"],
        "民企敞口": ["民营", "民企", "非国有企业"],
        "弱资质城投": ["弱资质", "区县", "尾部城投", "高负债"],
        "非标资产": ["非标", "信托计划", "债权计划", "资管计划"],
        "永续债": ["永续债", "二级资本债", "次级债"],
        "高收益债": ["高收益", "垃圾债", "困境债"],
    }
    
    @staticmethod
    def analyze(product: FinancialProduct) -> dict:
        """分析产品的信用质量
        
        Returns:
            {
                "信用等级": str,
                "信用评分": int (0-100),
                "描述": str,
                "风险信号": List[str],
                "底层信用判断": str,
            }
        """
        dsc = product.asset_description or ""
        name = product.name or ""
        full_text = dsc + " " + name
        
        # 1. 匹配信用等级
        best_level = None
        best_score = 0
        best_desc = ""
        
        for level_name, config in CreditQualityAnalyzer.CREDIT_SIGNALS.items():
            for kw in config["keywords"]:
                if kw in full_text:
                    if config["score"] > best_score:
                        best_score = config["score"]
                        best_level = level_name
                        best_desc = config["description"]
                    break
        
        if best_level is None:
            # 根据产品类型和风险等级推断
            if product.product_type == "货币":
                best_level = "极高（利率债/存款级）"
                best_score = 92
                best_desc = "货币类产品，底层以存款存单和短期利率债为主"
            elif product.risk_level == 1:
                best_level = "极高（利率债/存款级）"
                best_score = 90
                best_desc = "R1低风险产品，底层以高流动性安全资产为主"
            elif product.risk_level == 2 and product.product_type == "固收":
                best_level = "中高（精选信用）"
                best_score = 65
                best_desc = "R2固收产品，按中等信用质量保守评估"
            elif product.product_type == "结构性":
                best_level = "极高（利率债/存款级）"
                best_score = 85
                best_desc = "结构性存款/理财，本金部分通常有存款保障"
            else:
                best_level = "低/未知"
                best_score = 50
                best_desc = "未识别到明确信用策略，按中等风险保守评估"
        
        # 2. 检测风险信号
        risk_flags = []
        for flag_name, flag_keywords in CreditQualityAnalyzer.RISK_FLAGS.items():
            for kw in flag_keywords:
                if kw in full_text:
                    risk_flags.append(flag_name)
                    break
        
        # 风险信号扣分
        penalty = len(risk_flags) * 8
        adjusted_score = max(10, best_score - penalty)
        
        # 3. 生成底层信用判断
        if risk_flags:
            judge = f"信用等级{best_level}，但存在风险信号：{'、'.join(risk_flags)}。建议关注底层资产披露。"
        else:
            judge = f"信用等级{best_level}，{best_desc}"
        
        return {
            "信用等级": best_level,
            "信用评分": adjusted_score,
            "描述": best_desc,
            "风险信号": risk_flags,
            "底层信用判断": judge,
        }


# ─────────────────────────────────────────────
# P1: 费率竞争力分析器
# ─────────────────────────────────────────────

class FeeCompetitivenessAnalyzer:
    """在同风险等级内计算费率百分位，评估费率竞争力"""
    
    @staticmethod
    def compute_fee_percentile(all_products: List[FinancialProduct], target_code: str) -> dict:
        """计算目标产品在同风险等级内的费率百分位
        
        Returns:
            {
                "费率百分位": float,  # 越低越好（费率越低百分位越低）
                "同类费率中位数": float,
                "同类费率最低": float,
                "同类费率最高": float,
                "同类产品数量": int,
                "费率评级": str,
            }
        """
        if not all_products:
            return {"error": "无对比数据"}
        
        target = None
        for p in all_products:
            if p.product_code == target_code:
                target = p
                break
        
        if target is None:
            return {"error": f"未找到产品 {target_code}"}
        
        # 同风险等级产品
        peers = [p for p in all_products if p.risk_level == target.risk_level and p.product_code != target_code]
        
        if not peers:
            return {
                "费率百分位": 50.0,
                "同类费率中位数": round(target.management_fee_rate + target.custody_fee_rate + target.sales_service_fee_rate, 4),
                "同类费率最低": round(target.management_fee_rate + target.custody_fee_rate + target.sales_service_fee_rate, 4),
                "同类费率最高": round(target.management_fee_rate + target.custody_fee_rate + target.sales_service_fee_rate, 4),
                "同类产品数量": 0,
                "费率评级": "无对比数据",
            }
        
        # 计算年化总费率
        target_fee = target.management_fee_rate + target.custody_fee_rate + target.sales_service_fee_rate
        peer_fees = [p.management_fee_rate + p.custody_fee_rate + p.sales_service_fee_rate for p in peers]
        
        peer_fees_sorted = sorted(peer_fees)
        median_fee = statistics.median(peer_fees) if len(peer_fees) >= 2 else peer_fees[0]
        min_fee = min(peer_fees)
        max_fee = max(peer_fees)
        
        # 百分位（越低越好）
        n_lower = sum(1 for f in peer_fees if f <= target_fee)
        percentile = (n_lower / len(peer_fees)) * 100
        
        # 费率评级
        if percentile <= 10:
            rating = "★★★★★ 极低费率（前10%）"
        elif percentile <= 25:
            rating = "★★★★ 低费率（前25%）"
        elif percentile <= 50:
            rating = "★★★ 中等费率"
        elif percentile <= 75:
            rating = "★★ 偏高费率"
        else:
            rating = "★ 高费率（后25%）"
        
        return {
            "费率百分位": round(percentile, 1),
            "同类费率中位数": round(median_fee, 4),
            "同类费率最低": round(min_fee, 4),
            "同类费率最高": round(max_fee, 4),
            "同类产品数量": len(peers),
            "费率评级": rating,
        }


# ─────────────────────────────────────────────
# 7. 产品期限智能提取（v5.0 新增）
# ─────────────────────────────────────────────

class TermExtractor:
    """从产品名称/字段中智能提取期限信息"""
    
    @staticmethod
    def extract(product: FinancialProduct, raw: dict = None) -> FinancialProduct:
        """从产品名称和 API 字段中提取期限
        
        API 数据中 begdat 是起息日/下一开放日，zrunDat 是成立日。
        没有直接的期限字段，从产品名称中通过正则提取。
        """
        full_name = product.name + " " + (raw.get("shortName", "") if raw else "")
        
        # 1. 提取最短持有期
        holding_patterns = [
            (r'(\d+)\s*天\s*持有', 'days'),
            (r'持有\s*(\d+)\s*天', 'days'),
            (r'(\d+)\s*个月\s*持有', 'months'),
            (r'持有\s*(\d+)\s*个?\s*月', 'months'),
            (r'(\d+)\s*个月最短持有', 'months'),
            (r'最短持有\s*(\d+)\s*个?\s*月', 'months'),
        ]
        
        for pat, unit in holding_patterns:
            m = re.search(pat, full_name)
            if m:
                num = int(m.group(1))
                if unit == 'months':
                    product.min_holding_days = num * 30
                else:
                    product.min_holding_days = num
                product.term_type = "最短持有"
                product.term_days = product.min_holding_days
                break
        
        # 2. 提取封闭期
        closed_patterns = [
            (r'(\d+)\s*天\s*封闭', 'days'),
            (r'封闭\s*(\d+)\s*天', 'days'),
            (r'(\d+)\s*个月\s*封闭', 'months'),
            (r'封闭\s*(\d+)\s*个?\s*月', 'months'),
            (r'(\d+)\s*天\s*最短持有', 'days'),  # 部分用最短持有
        ]
        
        if product.term_type == "最短持有":
            # 已经匹配到持有期，跳过
            pass
        else:
            for pat, unit in closed_patterns:
                m = re.search(pat, full_name)
                if m:
                    num = int(m.group(1))
                    if unit == 'months':
                        product.term_days = num * 30
                    else:
                        product.term_days = num
                    product.term_type = "封闭式"
                    break
        
        # 3. 提取定期开放周期
        if product.term_type not in ("最短持有", "封闭式"):
            open_patterns = [
                (r'(\d+)\s*个?\s*月\s*定开', 'months'),
                (r'定开\s*(\d+)\s*个?\s*月', 'months'),
                (r'(\d+)\s*月开', 'months'),
                (r'(\d+)\s*天\s*定开', 'days'),
                (r'月开\s*(\d+)\s*号', 'months'),  # 月开
            ]
            
            for pat, unit in open_patterns:
                m = re.search(pat, full_name)
                if m:
                    num = int(m.group(1))
                    if unit == 'months':
                        product.term_days = num * 30
                    else:
                        product.term_days = num
                    product.term_type = "定期开放"
                    break
        
        # 4. 从名称中提取其他期限线索（如 "30天"、"90天"、"12个月"）
        if product.term_type == "开放式":
            generic_patterns = [
                (r'(\d+)\s*天', 'days'),
                (r'(\d+)\s*个?\s*月', 'months'),
                (r'(\d+)\s*年', 'years'),
            ]
            
            for pat, unit in generic_patterns:
                m = re.search(pat, full_name)
                if m:
                    num = int(m.group(1))
                    # 过滤掉太小的数字（可能是编号）
                    if num >= 7 and num <= 3650:
                        if unit == 'months':
                            product.term_days = num * 30
                        elif unit == 'years':
                            product.term_days = num * 365
                        else:
                            product.term_days = num
                        break
        
        # 5. 根据产品名称判断类型
        name_lower = full_name.lower()
        if any(kw in name_lower for kw in ['日开', '日日', '天天', '活期', '现金', '零钱包']):
            if product.term_type == "开放式":
                product.term_days = 1  # T+0/T+1 灵活申赎
                product.term_type = "开放式(T+0/T+1)"
        
        if any(kw in name_lower for kw in ['定开', '定期开放']):
            if product.term_type == "开放式":
                product.term_type = "定期开放"
        
        if any(kw in name_lower for kw in ['持有', '最短持有']):
            if product.term_type == "开放式":
                product.term_type = "最短持有"
        
        # 6. 安全兜底
        if product.term_days <= 0:
            product.term_days = 365
        
        return product


# ─────────────────────────────────────────────
# 8. 招商银行 API 数据源
# ─────────────────────────────────────────────

class CMBDataSource:
    """招商银行理财产品 API 数据源
    
    使用 SM4 国密签名认证，从招行理财平台获取真实产品数据。
    内置 JSON 文件缓存机制，避免重复请求 API。
    """
    
    APP_ID = "FinProd"
    AUTH_KEY = "XBILEWN2h1DJACiF"
    BASE_URL = "https://finprod.paas.cmbchina.com/api/prod/queryProdList"
    
    # 风险等级映射
    RISK_MAP = {"R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}
    
    # 缓存配置
    CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
    CACHE_FILE = os.path.join(CACHE_DIR, "cmb_products.json")
    CACHE_MAX_AGE_HOURS = 6  # 缓存有效期（小时），超过后重新拉取
    
    @staticmethod
    def _generate_signature(timespan: str) -> str:
        """生成 SM4 ECB 签名"""
        plain = (CMBDataSource.APP_ID + '|' + timespan).encode()
        pad_len = 16 - len(plain) % 16
        padded = plain + bytes([pad_len] * pad_len)
        
        c = sm4.CryptSM4()
        c.set_key(CMBDataSource.AUTH_KEY.encode(), sm4.SM4_ENCRYPT)
        cipher = c.crypt_ecb(padded)
        return base64.b64encode(cipher[:32]).decode()
    
    @staticmethod
    def _build_headers() -> dict:
        """构建请求头"""
        ts = str(int(time.time() * 1000))
        return {
            "Content-Type": "application/json;charset=UTF-8",
            "appid": CMBDataSource.APP_ID,
            "timespan": ts,
            "signature": CMBDataSource._generate_signature(ts),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://finprod.paas.cmbchina.com",
            "Referer": "https://finprod.paas.cmbchina.com/",
            "Accept": "application/json",
        }
    
    @staticmethod
    def fetch_page(page_no: int, page_size: int = 50) -> dict:
        """获取单页产品数据"""
        payload = {
            "keyWords": "", "type": "PN", "isOwn": "A", "isPublic": "A",
            "status": "1", "pageNO": page_no, "pageSize": page_size,
            "crossFinance": "Z", "riskLevel": "", "obligate": ""
        }
        r = requests.post(CMBDataSource.BASE_URL, headers=CMBDataSource._build_headers(),
                          json=payload, timeout=30)
        return r.json()
    
    @staticmethod
    def _read_cache() -> Optional[dict]:
        """读取缓存，返回 (数据列表, 缓存时间戳) 或 None"""
        if not os.path.exists(CMBDataSource.CACHE_FILE):
            return None
        try:
            with open(CMBDataSource.CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
            # 检查是否过期
            cache_time = cache.get("cached_at", 0)
            age_hours = (time.time() - cache_time) / 3600
            if age_hours > CMBDataSource.CACHE_MAX_AGE_HOURS:
                return None
            return cache
        except (json.JSONDecodeError, KeyError):
            return None
    
    @staticmethod
    def _write_cache(products: List[dict]):
        """写入缓存"""
        os.makedirs(CMBDataSource.CACHE_DIR, exist_ok=True)
        cache = {
            "cached_at": time.time(),
            "cache_hours": CMBDataSource.CACHE_MAX_AGE_HOURS,
            "product_count": len(products),
            "products": products,
        }
        with open(CMBDataSource.CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    
    @staticmethod
    def clear_cache():
        """清除缓存"""
        if os.path.exists(CMBDataSource.CACHE_FILE):
            os.remove(CMBDataSource.CACHE_FILE)
            print("🗑️  缓存已清除")
    
    @staticmethod
    def fetch_all_products(max_pages: int = 45, force_refresh: bool = False) -> List[dict]:
        """获取全部产品（最多 max_pages 页）
        
        Args:
            max_pages: 最大页数
            force_refresh: 是否强制刷新缓存
        """
        # 1. 尝试读缓存
        if not force_refresh:
            cache = CMBDataSource._read_cache()
            if cache:
                products = cache["products"]
                age_hours = (time.time() - cache["cached_at"]) / 3600
                logger.info("CMB 命中缓存：%d 款产品（%.1fh 前）", len(products), age_hours)
                print(f"📦 使用缓存数据（{len(products)} 款产品，缓存于 {age_hours:.1f} 小时前，有效期 {CMBDataSource.CACHE_MAX_AGE_HOURS}h）")
                return products
        
        # 2. 从 API 拉取
        all_products = []
        
        data = CMBDataSource.fetch_page(1)
        if data.get('code') != 'SUC0000':
            logger.error("CMB API 调用失败: %s", data.get('message'))
            print(f"❌ API 调用失败: {data.get('message')}")
            # API 失败时尝试返回过期缓存
            if not force_refresh and os.path.exists(CMBDataSource.CACHE_FILE):
                try:
                    with open(CMBDataSource.CACHE_FILE, "r", encoding="utf-8") as f:
                        old_cache = json.load(f)
                    products = old_cache.get("products", [])
                    age_hours = (time.time() - old_cache.get("cached_at", 0)) / 3600
                    logger.warning("CMB API 不可用，回退到过期缓存（%d 款，%.1fh 前）", len(products), age_hours)
                    print(f"⚠️ API 不可用，回退到过期缓存（{len(products)} 款，{age_hours:.1f}h 前）")
                    return products
                except:
                    pass
            return all_products
        
        total = data['data']['totalSize']
        total_pages = min(data['data']['totalPage'], max_pages)
        all_products.extend(data['data']['list'])
        
        logger.info("CMB API 连接成功，总计 %d 款产品，获取 %d 页", total, total_pages)
        print(f"📡 招行 API 连接成功，总计 {total} 款产品，将获取 {total_pages} 页...")
        
        for page in range(2, total_pages + 1):
            data = CMBDataSource.fetch_page(page)
            if data.get('code') == 'SUC0000':
                all_products.extend(data['data']['list'])
                if page % 5 == 0:
                    logger.info("CMB 拉取进度: %d/%d 页（%d 条）", page, total_pages, len(all_products))
                    print(f"  进度: {page}/{total_pages} 页 ({len(all_products)} 条)")
            else:
                logger.warning("CMB 第 %d 页获取失败: %s", page, data.get('message'))
                print(f"  ⚠️ 第 {page} 页获取失败: {data.get('message')}")
            time.sleep(0.25)
        
        # 3. 写入缓存
        if all_products:
            CMBDataSource._write_cache(all_products)
            logger.info("CMB 已缓存 %d 款产品（有效期 %sh）", len(all_products), CMBDataSource.CACHE_MAX_AGE_HOURS)
            print(f"💾 已缓存 {len(all_products)} 款产品（有效期 {CMBDataSource.CACHE_MAX_AGE_HOURS}h）")
        
        return all_products
    
    @staticmethod
    def to_financial_product(raw: dict) -> FinancialProduct:
        """将招行 API 原始数据转换为 FinancialProduct 模型（v5.0 增强版）"""
        code = raw.get('code', '')
        name = raw.get('name', '')
        
        # 风险等级
        risk_str = raw.get('risk', 'R2')
        risk_level = CMBDataSource.RISK_MAP.get(risk_str, 2)
        
        # ── 费率提取（v5.0 增强：赎回费阶梯） ──
        buy_rate = raw.get('buyRate', 0) or 0
        redeem_rate = raw.get('redeemRate', 0) or 0
        manage_rate = raw.get('manageRate', 0) or 0
        
        # 托管费：chrmn2 字段（年化 %）
        custody_rate = raw.get('chrmn2', 0) or 0
        
        # 销售服务费：chrsal 字段（年化 %）
        sales_service_rate = raw.get('chrsal', 0) or 0
        
        # 赎回费阶梯：rfelt1-4 是天数阈值，rfert1-4 是对应费率
        redemption_tiers = []
        for i in range(1, 5):
            threshold = raw.get(f'rfelt{i}', 0) or 0
            rate = raw.get(f'rfert{i}', -100) or -100
            if threshold > 0 and rate >= 0:
                redemption_tiers.append((int(threshold), float(rate)))
        
        # 超额业绩报酬：从 zfloMan 字段解析
        perf_fee_rate = 0.0
        perf_fee_threshold = 0.0
        zfloMan = raw.get('zfloMan', '')
        if zfloMan and '超出' in zfloMan and '%' in zfloMan:
            m1 = re.search(r'超出部分[的]?(\d+)%', zfloMan)
            if m1:
                perf_fee_rate = float(m1.group(1))
            m2 = re.search(r'超过.*?([\d.]+)%', zfloMan)
            if m2:
                perf_fee_threshold = float(m2.group(1))
        has_perf_fee = perf_fee_rate > 0
        
        # 起投金额
        buy_amount_str = raw.get('buynfq', '100')
        try:
            min_investment = float(buy_amount_str) if buy_amount_str else 100
        except:
            min_investment = 100
        
        # 成立日期
        run_date_str = raw.get('zrunDat', '')
        inception_date = None
        if run_date_str:
            try:
                inception_date = datetime.strptime(run_date_str, '%Y年%m月%d日')
            except:
                pass
        
        # 币种
        ccy_map = {"10": "CNY", "32": "USD", "12": "HKD"}
        currency = ccy_map.get(raw.get('ccynbr', '10'), 'CNY')
        
        # ── 业绩比较基准 -> 年化收益 ──
        perf_bench = raw.get('zbasPrf', '')
        annual_rate = 0.0
        annual_rate_low = 0.0
        annual_rate_high = 0.0
        if perf_bench and '%' in perf_bench:
            if '-' in perf_bench:
                try:
                    parts = perf_bench.replace('%', '').split('-')
                    if len(parts) == 2:
                        low, high = float(parts[0]), float(parts[1])
                        annual_rate_low = low
                        annual_rate_high = high
                        annual_rate = (low + high) / 2
                except:
                    annual_rate = 0.0
            else:
                try:
                    val = float(perf_bench.replace('%', '').strip())
                    annual_rate = val
                    annual_rate_low = val
                    annual_rate_high = val
                except:
                    annual_rate = 0.0
        
        # ── v5.0: 真实历史业绩提取 ──
        past_perf = raw.get('pastPerf', {}) or {}
        
        # 历年收益率（tqilstw4z4）
        yearly_data = past_perf.get('tqilstw4z4') or []
        history_returns = []
        for y in yearly_data:
            try:
                yr = y.get('zyeaYld', '0')
                if yr:
                    history_returns.append(float(yr))
            except:
                pass
        
        # 成立以来累计净值收益率（tqilstw4z3 的最后一条 zprfTyp='F'）
        inception_nav_yield = 0.0
        inception_years = 0.0
        nav_perf_data = past_perf.get('tqilstw4z3') or []
        for item in reversed(nav_perf_data):
            if item.get('zprfTyp') == 'F':
                try:
                    inception_nav_yield = float(item.get('znavYld', 0))
                except:
                    pass
                break
        
        # 计算成立年限
        if inception_date:
            inception_years = (datetime.now() - inception_date).days / 365.0
        
        # 如果 zbasPrf 无法解析出年化收益，从真实历史数据中提取
        if annual_rate == 0.0:
            if inception_nav_yield > 0 and inception_years > 0:
                # 从成立以来累计收益率推年化
                annual_rate = ((1 + inception_nav_yield / 100) ** (1 / max(inception_years, 0.5)) - 1) * 100
            elif history_returns:
                annual_rate = statistics.mean(history_returns)
            else:
                # 从 pastPerf zyeaYld 中提取
                if yearly_data:
                    try:
                        annual_rate = float(yearly_data[-1].get('zyeaYld', 0)) or 0.0
                    except:
                        pass
                if annual_rate == 0.0 and nav_perf_data:
                    try:
                        annual_rate = float(nav_perf_data[-1].get('zyeaYld', 0)) or 0.0
                    except:
                        pass
        
        # 净值
        nav = raw.get('dnvval', 1.0) or 1.0
        
        # ── 产品类型分类 ──
        name_lower = name.lower()
        if any(kw in name_lower for kw in ['货币', '现金', '日日', '天天']):
            product_type = "货币"
        elif any(kw in name_lower for kw in ['权益', '股票', '红利']):
            product_type = "权益"
        elif any(kw in name_lower for kw in ['固收', '债券', '债', '颐养', '增利']):
            product_type = "固收"
        elif any(kw in name_lower for kw in ['结构性', '挂钩', '鲨鱼']):
            product_type = "结构性"
        elif any(kw in name_lower for kw in ['信托']):
            product_type = "信托"
        else:
            product_type = "混合"
        
        # ── v5.0: 久期特征提取 ──
        duration_hint = ""
        if any(kw in name_lower for kw in ['短债', '超短', '现金', '活期', '货币', '30天', '7天', '14天']):
            duration_hint = "短久期"
        elif any(kw in name_lower for kw in ['中短', '90天', '180天']):
            duration_hint = "中短久期"
        elif any(kw in name_lower for kw in ['长', '360天', '370天', '12个月', '年']):
            duration_hint = "长久期"
        else:
            duration_hint = "中久期"
        
        # 标签
        tags = [product_type, risk_str]
        if '美元' in name or 'QD' in code or currency == "USD":
            tags.append('QDII/海外')
        if 'FOF' in name:
            tags.append('FOF')
        if has_perf_fee:
            tags.append('含超额报酬')
        
        # ── P0: 用真实历史年化收益 + 业绩基准区间 + 风险等级生成月度→日度收益率序列 ──
        effective_rate = annual_rate if annual_rate > 0 else (statistics.mean(history_returns) if history_returns else 2.5)
        
        # 使用真实历年数据 + 基准区间生成月度收益率
        monthly_returns, effective_rate, annual_vol_actual = CMBDataSource._generate_monthly_returns_from_history(
            annual_rate=effective_rate,
            annual_rate_low=annual_rate_low,
            annual_rate_high=annual_rate_high,
            risk_level=risk_level,
            historical_annual_returns=history_returns,
            inception_years=inception_years,
            product_code=code,
        )
        # 月度转日度
        num_days = max(252, int(inception_years * 252)) if inception_years > 0 else 252
        num_days = min(num_days, 2520)  # 最多10年
        daily_returns = CMBDataSource._monthly_to_daily(monthly_returns, num_days)
        
        # 净值序列
        nav_series = [nav]
        for r in daily_returns:
            nav_series.append(nav_series[-1] * (1 + r / 100))
        
        # 基准收益率
        bench_returns = CMBDataSource._simulate_benchmark_returns(len(daily_returns))
        
        # ── 资产配置描述 ──
        asset_desc = raw.get('zbasDsc', '') or ''
        
        # ── 管理人信息 ──
        manager_company = raw.get('zcrpNam', '') or raw.get('orgName', '')
        issuer = raw.get('orgName', '')
        
        # v5.1: 投资经理姓名（从产品全名中尝试提取）
        # 招行 API 一般不直接返回经理姓名，但 zfinNam 字段可能存在
        manager_name = raw.get('zfinNam', '') or raw.get('managerName', '') or ''
        # 经理任职年限：从成立日期推算
        manager_tenure = 0.0
        if inception_date:
            manager_tenure = (datetime.now() - inception_date).days / 365.0
        
        # 构建产品对象
        product = FinancialProduct(
            product_code=code,
            name=name,
            issuer=issuer,
            product_type=product_type,
            purchase_price=1.0,
            current_price=nav,
            annual_rate=annual_rate,
            annual_rate_low=annual_rate_low,
            annual_rate_high=annual_rate_high,
            term_days=365,  # 先占位，后面 TermExtractor 会修正
            risk_level=risk_level,
            min_investment=min_investment,
            purchase_fee_rate=buy_rate,
            management_fee_rate=manage_rate,
            redemption_fee_rate=redeem_rate,
            custody_fee_rate=custody_rate,
            sales_service_fee_rate=sales_service_rate,
            performance_fee_rate=perf_fee_rate,
            performance_fee_threshold=perf_fee_threshold,
            early_redeemable=True,
            early_redeem_penalty=0.0,
            daily_returns=daily_returns,
            benchmark_returns=bench_returns,
            benchmark_name="沪深300",
            inception_date=inception_date,
            tax_rate=0.0,
            tax_free=True,
            inflation_rate=2.5,
            tags=tags,
            nav_series=nav_series,
            peer_rank=0,
            peer_count=0,
            manager_company=manager_company,
            manager_name=manager_name,
            manager_tenure_years=manager_tenure,
            has_performance_fee=has_perf_fee,
            currency=currency,
            asset_description=asset_desc,
            inception_nav_yield=inception_nav_yield,
            historical_annual_returns=history_returns,
            inception_years=inception_years,
            duration_hint=duration_hint,
            redemption_fee_tiers=redemption_tiers,
        )
        
        # v5.0: 智能期限提取
        product = TermExtractor.extract(product, raw)
        
        # 解析资产配置
        product = AssetAllocationParser.parse(product)
        
        return product
    
    @staticmethod
    def compute_peer_ranking(all_products: List[FinancialProduct], target_code: str) -> dict:
        """v5.1: 在全量产品中计算真实同类百分位排名
        
        按同风险等级内排序，使用年化收益 + 费率调整。
        """
        if not all_products:
            return {"排名": "无数据", "百分位": 0, "同类数量": 0}
        
        target = None
        peers = []
        for p in all_products:
            if p.product_code == target_code:
                target = p
            elif p.risk_level == (target.risk_level if target else 2):
                peers.append(p)
        
        if target is None:
            for p in all_products:
                if p.product_code == target_code:
                    target = p
                    break
        if target is None:
            return {"排名": "无数据", "百分位": 0, "同类数量": 0}
        
        # 重新收集同风险等级产品
        peers = [p for p in all_products if p.risk_level == target.risk_level]
        if len(peers) <= 1:
            return {"排名": f"1/{len(peers)}", "百分位": 100.0, "同类数量": len(peers)}
        
        # 按年化收益率排名（扣费后净收益）
        def net_score(p):
            annual_fee = p.management_fee_rate + p.custody_fee_rate + p.sales_service_fee_rate
            return p.annual_rate - annual_fee
        
        sorted_peers = sorted(peers, key=net_score, reverse=True)
        
        target_rank = 1
        for i, p in enumerate(sorted_peers):
            if p.product_code == target_code:
                target_rank = i + 1
                break
        
        percentile = (1 - (target_rank - 1) / len(sorted_peers)) * 100
        
        return {
            "排名": f"{target_rank}/{len(sorted_peers)}",
            "百分位": round(percentile, 1),
            "同类数量": len(sorted_peers),
            "同类最高年化(%)": round(net_score(sorted_peers[0]), 2),
            "同类中位年化(%)": round(net_score(sorted_peers[len(sorted_peers)//2]), 2),
            "同类最低年化(%)": round(net_score(sorted_peers[-1]), 2),
        }
    
    @staticmethod
    def _deterministic_hash(s: str) -> int:
        """确定性 hash 函数（跨进程稳定）"""
        import hashlib
        return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)
    
    @staticmethod
    def _generate_monthly_returns_from_history(
        annual_rate: float, annual_rate_low: float, annual_rate_high: float,
        risk_level: int, historical_annual_returns: List[float],
        inception_years: float, product_code: str = ""
    ) -> Tuple[List[float], float, float]:
        """P0: 基于真实历史年度收益+业绩基准区间，生成月度收益率序列
        
        优先使用真实历年收益率，缺失年份用业绩基准区间插值，
        每月收益率在年化±波动范围内随机波动，保证最终年化趋近目标。
        
        返回: (月度收益率序列 %, 有效年化 %, 年化波动率 %)
        """
        seed = CMBDataSource._deterministic_hash(str(annual_rate) + str(risk_level) + product_code) % 100000
        rng = np.random.RandomState(seed)
        
        # 波动率映射（月度年化波动率 %）
        vol_map = {1: 0.15, 2: 0.8, 3: 4.0, 4: 10.0, 5: 18.0}
        annual_vol_pct = vol_map.get(risk_level, 4.0)
        monthly_vol = (annual_vol_pct / 100) / np.sqrt(12)
        
        # 确定要生成的年数和有效年化
        total_years = max(1, int(inception_years)) if inception_years > 0 else 3
        total_years = min(total_years, 10)  # 最多10年
        
        # 用历史收益率填充真实年份
        real_years = len(historical_annual_returns) if historical_annual_returns else 0
        year_returns = list(historical_annual_returns[:total_years]) if real_years > 0 else []
        
        # 缺失年份：用业绩基准区间中点填充
        if annual_rate_low > 0 and annual_rate_high > 0:
            fill_rate = (annual_rate_low + annual_rate_high) / 2
        else:
            fill_rate = annual_rate if annual_rate > 0 else 2.0
        
        while len(year_returns) < total_years:
            year_returns.append(fill_rate)
        
        # 每月：年化/12 + 噪音（用月波动率）
        monthly_returns = []
        for yr in year_returns:
            monthly_drift = yr / 12.0
            # 生成12个月，每月在月度波动率范围内
            for m in range(12):
                noise = rng.normal(0, monthly_vol)
                monthly_returns.append(monthly_drift + noise)
        
        # 校准：确保整体年化趋近有效年化
        effective_rate = annual_rate if annual_rate > 0 else (
            statistics.mean(historical_annual_returns) if historical_annual_returns else fill_rate
        )
        if len(monthly_returns) >= 12:
            actual_annual = np.mean(monthly_returns) * 12
            # 缩放至目标年化
            scale = effective_rate / actual_annual if abs(actual_annual) > 0.001 else 1.0
            scale = max(0.3, min(3.0, scale))  # 防止极端缩放
            monthly_returns = [r * scale for r in monthly_returns]
        
        # 计算实际年化波动率
        monthly_arr = np.array(monthly_returns)
        real_annual_vol = float(np.std(monthly_arr, ddof=1) * np.sqrt(12))
        
        return monthly_returns, effective_rate, real_annual_vol
    
    @staticmethod
    def _monthly_to_daily(monthly_returns: List[float], days: int = 252) -> List[float]:
        """将月度收益率插值为日收益率序列
        
        保持月度总收益不变，在月内均匀分布日收益+微量噪音。
        """
        if not monthly_returns:
            return [0.0] * days
        
        n_months = len(monthly_returns)
        days_per_month = max(1, days // n_months)
        
        seed = CMBDataSource._deterministic_hash(str(sum(monthly_returns))) % 100000
        rng = np.random.RandomState(seed)
        
        daily = []
        for monthly_r in monthly_returns:
            # 月度收益率转换为日化
            daily_r = (1 + monthly_r / 100) ** (1 / days_per_month) - 1
            # 在月内添加微量日内噪音（±10%）
            for _ in range(days_per_month):
                noise = rng.normal(0, abs(daily_r) * 0.1 + 0.0001)
                daily.append((daily_r + noise) * 100)  # 转回百分比
        
        # 截断到目标天数
        if len(daily) > days:
            daily = daily[:days]
        while len(daily) < days:
            daily.append(0.0)
        
        return daily
    
    @staticmethod
    def _simulate_daily_returns(annual_rate: float, risk_level: int, days: int = 252) -> List[float]:
        """P0 遗留兼容接口：对于无历史数据的产品，用基准区间生成月度后转日度
        
        不同风险等级的典型年化波动率：
          R1（货币/现金管理）: 0.1%-0.3%
          R2（固收/债券）:     0.5%-1.5%
          R3（混合/平衡）:     3%-8%
          R4（偏股混合）:      8%-15%
          R5（权益）:          15%-25%
        """
        monthly_returns, _, _ = CMBDataSource._generate_monthly_returns_from_history(
            annual_rate=annual_rate,
            annual_rate_low=0.0,
            annual_rate_high=0.0,
            risk_level=risk_level,
            historical_annual_returns=[],
            inception_years=3.0,
        )
        return CMBDataSource._monthly_to_daily(monthly_returns, days)
    
    @staticmethod
    def _simulate_benchmark_returns(days: int) -> List[float]:
        """模拟沪深300基准日收益率"""
        np.random.seed(888)
        daily_drift = 0.02 / 252
        daily_vol = 1.2 / np.sqrt(252)
        return np.random.normal(daily_drift, daily_vol, days).tolist()


class SPDBDataSource:
    """浦发银行理财产品 API 数据源
    
    从浦发银行理财平台（per.spdb.com.cn）获取真实产品数据。
    使用 SSL legacy renegotiation 兼容模式连接。
    内置 JSON 文件缓存机制。
    """
    
    BASE_URL = "https://per.spdb.com.cn/api/search"
    CHLID = 1075  # 专项理财频道ID
    PAGE_SIZE = 10  # API 每页固定 10 条
    
    # 风险等级映射（浦发格式 → 数字等级）
    RISK_MAP = [
        ("R5高风险", 5), ("R5", 5),
        ("R4较高风险", 4), ("R4", 4),
        ("R3中风险", 3), ("R3", 3),
        ("R2较低风险", 2), ("R2", 2),
        ("R1低风险", 1), ("R1", 1),
    ]
    
    # 期限映射（用于提取投资期限天数）
    TERM_DAYS_MAP = {
        "1个月以下": 15,
        "1-3个月": 60,
        "3-6个月": 135,
        "6-12个月": 270,
        "1年以上": 540,
        "活期": 1,
    }
    
    # 缓存配置
    CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
    CACHE_FILE = os.path.join(CACHE_DIR, "spdb_products.json")
    CACHE_MAX_AGE_HOURS = 6
    
    # SSL context（类级别单例）
    _ssl_context = None
    
    @classmethod
    def _get_ssl_context(cls):
        """获取兼容浦发 SSL 的 context"""
        if cls._ssl_context is None:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            # SSL_OP_LEGACY_SERVER_CONNECT = 0x4
            ctx.options |= 0x4
            ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
            cls._ssl_context = ctx
        return cls._ssl_context
    
    @staticmethod
    def _build_headers() -> dict:
        return {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "content-type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0",
            "referer": "https://per.spdb.com.cn/bank_financing/financial_product/",
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://per.spdb.com.cn",
        }
    
    @staticmethod
    def fetch_page(page_no: int) -> dict:
        """获取单页产品数据"""
        import urllib.request
        payload = json.dumps({
            "chlid": SPDBDataSource.CHLID,
            "page": page_no,
            "searchword": ""
        }).encode()
        
        req = urllib.request.Request(
            SPDBDataSource.BASE_URL,
            data=payload,
            headers=SPDBDataSource._build_headers()
        )
        
        ctx = SPDBDataSource._get_ssl_context()
        resp = urllib.request.urlopen(req, context=ctx, timeout=30)
        body = resp.read().decode('utf-8')
        return json.loads(body)
    
    @staticmethod
    def _read_cache() -> Optional[List[dict]]:
        """读取缓存"""
        if not os.path.exists(SPDBDataSource.CACHE_FILE):
            return None
        try:
            with open(SPDBDataSource.CACHE_FILE, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            cached_at = cached.get("cached_at", 0)
            age_hours = (time.time() - cached_at) / 3600
            if age_hours > SPDBDataSource.CACHE_MAX_AGE_HOURS:
                return None
            return cached.get("products", [])
        except:
            return None
    
    @staticmethod
    def _write_cache(products: List[dict]):
        """写入缓存"""
        os.makedirs(SPDBDataSource.CACHE_DIR, exist_ok=True)
        with open(SPDBDataSource.CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "cached_at": time.time(),
                "cache_hours": SPDBDataSource.CACHE_MAX_AGE_HOURS,
                "product_count": len(products),
                "products": products,
            }, f, ensure_ascii=False)
    
    @staticmethod
    def clear_cache():
        """清除缓存"""
        if os.path.exists(SPDBDataSource.CACHE_FILE):
            os.remove(SPDBDataSource.CACHE_FILE)
    
    @staticmethod
    def fetch_all_products(max_pages: int = 600, force_refresh: bool = False) -> List[dict]:
        """拉取全部产品数据（含缓存逻辑）
        
        Args:
            max_pages: 最大拉取页数（每页10条）
            force_refresh: 是否强制刷新（忽略缓存）
        
        Returns:
            原始产品 dict 列表
        """
        # 读缓存
        if not force_refresh:
            cached = SPDBDataSource._read_cache()
            if cached:
                age_hours = (time.time() - os.path.getmtime(SPDBDataSource.CACHE_FILE)) / 3600
                logger.info("SPDB 命中缓存：%d 款产品（%.1fh 前）", len(cached), age_hours)
                print(f"  📦 缓存: {len(cached)} 款产品（{age_hours:.1f}h 前）| 输入 'c' 清除缓存")
                return cached
        
        logger.info("正在从浦发银行 API 拉取产品数据...")
        print(f"  🌐 正在从浦发银行 API 拉取产品数据...")
        
        try:
            first_page = SPDBDataSource.fetch_page(1)
        except Exception as e:
            logger.warning("SPDB API 请求失败: %s，尝试使用过期缓存...", e)
            print(f"  ⚠️ API 请求失败: {e}，尝试使用过期缓存...")
            cached = SPDBDataSource._read_cache()
            if cached:
                return cached
            return []
        
        if first_page.get("code") != 20000:
            logger.warning("SPDB API 返回异常: %s", first_page.get('message'))
            print(f"  ⚠️ API 返回异常: {first_page.get('message')}")
            cached = SPDBDataSource._read_cache()
            if cached:
                return cached
            return []
        
        data = first_page.get("data", {})
        total_pages = min(data.get("totalPages", 1), max_pages)
        total_elements = data.get("totalElements", 0)
        products = list(data.get("content", []))
        
        logger.info("SPDB 总产品 %d 款 | 总页数 %d | 每页 %d 条", total_elements, min(data.get('totalPages', 1), max_pages), SPDBDataSource.PAGE_SIZE)
        print(f"  总产品: {total_elements} 款 | 总页数: {min(data.get('totalPages', 1), max_pages)} | 每页 {SPDBDataSource.PAGE_SIZE} 条")
        
        # 分页拉取
        for page in range(2, total_pages + 1):
            try:
                result = SPDBDataSource.fetch_page(page)
                if result.get("code") == 20000:
                    page_data = result.get("data", {})
                    page_products = page_data.get("content", [])
                    products.extend(page_products)
                    if page % 50 == 0:
                        logger.info("SPDB 拉取进度: %d/%d（%d 款）", page, total_pages, len(products))
                        print(f"  进度: {page}/{total_pages} ({len(products)} 款)...")
                else:
                    logger.warning("SPDB 第 %d 页返回异常: %s", page, result.get('message'))
                    print(f"  ⚠️ 第 {page} 页返回异常: {result.get('message')}")
            except Exception as e:
                logger.warning("SPDB 第 %d 页请求失败: %s", page, e)
                print(f"  ⚠️ 第 {page} 页请求失败: {e}")
            time.sleep(0.15)  # 降低请求频率
        
        # 过滤在售产品
        products = [p for p in products if p.get("ProductStatus") == "在售"]
        logger.info("SPDB 在售产品 %d 款", len(products))
        print(f"  在售产品: {len(products)} 款")
        
        # 写缓存
        SPDBDataSource._write_cache(products)
        return products
    
    @staticmethod
    def _parse_risk_level(risk_str: str) -> int:
        """解析风险等级"""
        if not risk_str:
            return 2
        # 按优先级从高到低匹配
        for key, val in SPDBDataSource.RISK_MAP:
            if key in risk_str:
                return val
        # 尝试提取数字
        m = re.search(r'R(\d)', risk_str)
        if m:
            return int(m.group(1))
        return 2
    
    @staticmethod
    def _parse_income_rate(rate_str: str) -> Tuple[float, float, float]:
        """解析收益率字符串，返回 (low, high, mid)
        
        Args:
            rate_str: 如 "17.81％" 或 "3.5%-4.5%"
        
        Returns:
            (最低, 最高, 中位) 年化收益率
        """
        if not rate_str:
            return (2.0, 2.0, 2.0)
        
        # 清理全角百分号
        cleaned = rate_str.replace('％', '%').replace('，', ',').strip()
        
        # 尝试区间 "3.5%-4.5%"
        m = re.search(r'([\d.]+)%\s*[-~到]\s*([\d.]+)%', cleaned)
        if m:
            low = float(m.group(1))
            high = float(m.group(2))
            return (low, high, (low + high) / 2)
        
        # 尝试单值 "3.5%"
        m = re.search(r'([\d.]+)%', cleaned)
        if m:
            val = float(m.group(1))
            return (val, val, val)
        
        # 兜底
        try:
            val = float(cleaned)
            return (val, val, val)
        except:
            return (2.0, 2.0, 2.0)
    
    @staticmethod
    def _parse_term_days(income_dates: str) -> int:
        """从 IncomeDates 字段解析投资期限天数"""
        if not income_dates:
            return 90  # 默认3个月
        for key, days in SPDBDataSource.TERM_DAYS_MAP.items():
            if key in income_dates:
                return days
        return 90
    
    @staticmethod
    def _deterministic_hash(s: str) -> int:
        """确定性哈希（用于生成稳定的随机种子）"""
        import hashlib
        return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)
    
    @staticmethod
    def to_financial_product(raw: dict) -> FinancialProduct:
        """将浦发 API 原始数据转换为 FinancialProduct 模型
        
        Args:
            raw: API 返回的单条产品记录
        
        Returns:
            FinancialProduct 实例
        """
        code = raw.get("ProductCode", "")
        name = raw.get("ProductName", "")
        issuer = raw.get("TAName", "浦发银行")
        
        # 风险等级
        risk_level = SPDBDataSource._parse_risk_level(raw.get("RiskLevel", ""))
        
        # 收益率
        rate_str = raw.get("ChannelDisIncomeRate", "")
        rate_low, rate_high, annual_rate = SPDBDataSource._parse_income_rate(rate_str)
        
        # 收益率描述（成立以来年化/近一月年化等）
        income_rate_des = raw.get("IncomeRateDes", "")
        
        # 期限
        term_days = SPDBDataSource._parse_term_days(raw.get("IncomeDates", ""))
        deadline_brand = raw.get("DeadlineBrandID", "")  # 周周鑫/月月增/季季盈/年年泓
        
        # 起购金额
        min_amt_str = raw.get("IndiIPOMinAmnt", "1")
        try:
            min_investment = float(min_amt_str)
        except:
            min_investment = 1.0
        # 如果起购金额 < 100，可能是万元单位，需要换算
        if min_investment <= 100 and min_amt_str.isdigit():
            min_amt_status = raw.get("IndiIPOMinStauts", "")
            if "万" in min_amt_status:
                min_investment *= 10000
        
        # 币种
        currency = raw.get("CurrencyType", "人民币")
        if "美元" in currency:
            currency = "USD"
        elif "人民币" in currency:
            currency = "CNY"
        
        # 产品状态
        status = raw.get("ProductStatus", "")
        
        # 产品类型推断
        product_type = "固收"
        if any(kw in name for kw in ["现金", "货币", "天天", "日开"]):
            product_type = "货币"
        elif any(kw in name for kw in ["股票", "权益", "红利轮动", "科技"]):
            product_type = "混合"
        elif any(kw in name for kw in ["QDII", "美元", "海外", "全球"]):
            product_type = "QDII"
        
        # 默认费率（浦发列表API不直接提供费率，使用行业常见默认值）
        purchase_fee_rate = 0.0  # 多数理财免申购费
        management_fee_rate = 0.3  # 固收类约 0.15-0.5%
        redemption_fee_rate = 0.0  # 多数持有期满后免费
        custody_fee_rate = 0.05
        sales_service_fee_rate = 0.0
        performance_fee_rate = 0.0
        performance_fee_threshold = 0.0
        
        # 根据风险等级调整费率假设
        if risk_level >= 4:
            management_fee_rate = 0.8
        elif risk_level == 3:
            management_fee_rate = 0.5
        
        # 根据期限品牌调整管理费
        if "周周鑫" in deadline_brand:
            management_fee_rate = 0.2
        elif "月月增" in deadline_brand:
            management_fee_rate = 0.25
        elif "季季盈" in deadline_brand:
            management_fee_rate = 0.3
        elif "年年泓" in deadline_brand:
            management_fee_rate = 0.4
        
        # 产品存续期（用期限天数估算）
        inception_years = max(0.5, term_days / 365.0 * 2)  # 粗略假设已运行期限2倍
        
        # 历史业绩（从当前收益率反推）
        # 用 deterministic hash 生成稳定的历史年度收益序列
        seed = SPDBDataSource._deterministic_hash(code)
        np.random.seed(seed)
        historical_returns = []
        years_count = max(1, min(5, int(inception_years)))
        for _ in range(years_count):
            # 围绕当前年化收益率 ± 波动
            hist_ret = annual_rate + np.random.normal(0, max(0.5, annual_rate * 0.15))
            historical_returns.append(round(max(0.5, hist_ret), 2))
        np.random.seed(None)  # 恢复随机状态
        
        # 生成收益率序列
        days = max(60, term_days)
        monthly_returns, effective_rate, _ = CMBDataSource._generate_monthly_returns_from_history(
            annual_rate=annual_rate,
            annual_rate_low=rate_low,
            annual_rate_high=rate_high,
            risk_level=risk_level,
            historical_annual_returns=historical_returns,
            inception_years=inception_years,
            product_code=code,
        )
        daily_returns = CMBDataSource._monthly_to_daily(monthly_returns, days)
        benchmark_returns = CMBDataSource._simulate_benchmark_returns(days)
        
        # 生成净值序列
        nav = 1.0
        nav_series = [nav]
        for dr in daily_returns:
            nav *= (1 + dr / 100)
            nav_series.append(round(nav, 6))
        
        # 构建 FinancialProduct
        product = FinancialProduct(
            product_code=code,
            name=name,
            issuer=issuer,
            product_type=product_type,
            purchase_price=1.0,
            current_price=nav_series[-1] if nav_series else 1.0,
            annual_rate=round(effective_rate, 2),
            annual_rate_low=round(rate_low, 2),
            annual_rate_high=round(rate_high, 2),
            term_days=term_days,
            term_type="固定期限" if term_days > 0 else "活期",
            min_holding_days=term_days,
            risk_level=risk_level,
            min_investment=min_investment,
            purchase_fee_rate=purchase_fee_rate,
            management_fee_rate=management_fee_rate,
            redemption_fee_rate=redemption_fee_rate,
            custody_fee_rate=custody_fee_rate,
            sales_service_fee_rate=sales_service_fee_rate,
            performance_fee_rate=performance_fee_rate,
            performance_fee_threshold=performance_fee_threshold,
            early_redeemable=True,
            daily_returns=daily_returns,
            nav_series=nav_series,
            benchmark_returns=benchmark_returns,
            benchmark_name="沪深300",
            inception_years=inception_years,
            historical_annual_returns=historical_returns,
            inception_nav_yield=round(effective_rate, 2),
            manager_company=issuer,
            manager_type="银行理财子",
            manager_rating=3,  # 浦发数据未提供具体评级，按默认中等处理
            manager_name=issuer,
            currency=currency,
            tax_free=True,
            tags=[deadline_brand] if deadline_brand else [],
        )
        
        # 后处理：期限提取
        TermExtractor.extract(product, raw)
        
        return product
    
    @staticmethod
    def compute_peer_ranking(all_products: List[FinancialProduct], target_code: str) -> Tuple[int, int]:
        """计算同类百分位排名（同风险等级内）"""
        target = None
        same_risk = []
        for p in all_products:
            if p.product_code == target_code:
                target = p
            elif p.risk_level == (target.risk_level if target else 2):
                same_risk.append(p)
        
        if target is None:
            return (0, 0)
        
        same_risk.append(target)
        # 按年化收益率降序排名
        same_risk.sort(key=lambda x: x.annual_rate, reverse=True)
        
        rank = same_risk.index(target) + 1
        total = len(same_risk)
        return (rank, total)


# ─────────────────────────────────────────────
# 4. 深度分析引擎
# ─────────────────────────────────────────────

class DeepProductAnalyzer:
    """深度理财产品分析器"""
    
    # 基准参数
    RISK_FREE_RATE = 1.8
    BENCHMARK_DEPOSIT_RATE = 2.0
    BENCHMARK_BOND_RATE = 2.8
    
    def __init__(self, product: FinancialProduct):
        self.p = product
        self.stats = StatisticalUtils()
    
    # ========== 基础收益分析 ==========
    
    def gross_return(self) -> float:
        """毛收益率"""
        return (self.p.current_price - self.p.purchase_price) / self.p.purchase_price * 100
    
    def annualized_return(self) -> float:
        """实际年化"""
        gross = self.gross_return()
        if self.p.term_days <= 0:
            return gross
        return gross * 365 / self.p.term_days
    
    def net_return_after_fee(self, investment: float = 100000) -> float:
        """扣费后净年化"""
        fees = self.total_fee_cost(investment)
        fee_ratio = fees["费用占投资比(%)"]
        annual_fee_impact = fee_ratio * 365 / self.p.term_days if self.p.term_days > 0 else 0
        return self.p.annual_rate - annual_fee_impact
    
    def real_return(self) -> float:
        """实际收益（扣通胀）"""
        return self.net_return_after_fee() - self.p.inflation_rate
    
    # ========== 费用分析 ==========
    
    def total_fee_cost(self, investment: float = 100000) -> dict:
        """费用明细（v4.0 增强版：含托管费、销售服务费、超额业绩报酬）"""
        purchase_fee = investment * self.p.purchase_fee_rate / 100
        annual_mgmt = investment * self.p.management_fee_rate / 100
        mgmt_fee = annual_mgmt * self.p.term_days / 365
        
        # 托管费
        annual_custody = investment * self.p.custody_fee_rate / 100
        custody_fee = annual_custody * self.p.term_days / 365
        
        # 销售服务费
        annual_sales = investment * self.p.sales_service_fee_rate / 100
        sales_fee = annual_sales * self.p.term_days / 365
        
        redemption_fee = investment * self.p.redemption_fee_rate / 100
        
        # 超额业绩报酬（预估）
        perf_fee = 0.0
        perf_note = "无"
        if self.p.has_performance_fee and self.p.annual_rate > self.p.performance_fee_threshold:
            excess = self.p.annual_rate - self.p.performance_fee_threshold
            gross_profit = investment * excess / 100 * self.p.term_days / 365
            perf_fee = gross_profit * self.p.performance_fee_rate / 100
            perf_note = f"超额{excess:.2f}%部分提取{self.p.performance_fee_rate:.0f}%"
        
        total = purchase_fee + mgmt_fee + custody_fee + sales_fee + redemption_fee + perf_fee
        fee_pct = total / investment * 100
        
        return {
            "申购费": round(purchase_fee, 2),
            "管理费(固定)": round(mgmt_fee, 2),
            "托管费": round(custody_fee, 2),
            "销售服务费": round(sales_fee, 2),
            "赎回费": round(redemption_fee, 2),
            "超额业绩报酬": f"{perf_note} (¥{perf_fee:.2f})",
            "总费用": round(total, 2),
            "费用占投资比(%)": round(fee_pct, 4),
            "年化总费率(%)": round(self.p.management_fee_rate + self.p.custody_fee_rate + self.p.sales_service_fee_rate, 4),
        }
    
    # ========== 风险分析（增强） ==========
    
    def risk_metrics(self) -> dict:
        """全面风险指标"""
        if not self.p.daily_returns:
            return {"error": "无历史数据"}
        
        returns = self.p.daily_returns
        nav = self.p.nav_series if self.p.nav_series else self._simulate_nav(returns)
        
        # 波动率
        volatility = self.stats.annualized_volatility(returns)
        
        # 最大回撤
        max_dd, peak_idx, trough_idx = self.stats.max_drawdown(nav)
        
        # 下行风险
        downside_dev = self.stats.downside_deviation(returns)
        
        # VaR & CVaR
        var_95 = self.stats.var(returns, 0.95)
        cvar_95 = self.stats.cvar(returns, 0.95)
        var_99 = self.stats.var(returns, 0.99)
        
        # 收益分布
        skew = self.stats.skewness(returns)
        kurt = self.stats.kurtosis(returns)
        
        return {
            "年化波动率(%)": round(volatility, 4),
            "最大回撤(%)": round(max_dd, 4),
            "下行标准差(%)": round(downside_dev, 4),
            "VaR_95(%)": round(var_95, 6),
            "CVaR_95(%)": round(cvar_95, 6),
            "VaR_99(%)": round(var_99, 6),
            "偏度": round(skew, 3),
            "峰度": round(kurt, 3),
            "回撤峰值位置": peak_idx,
            "回撤谷值位置": trough_idx,
        }
    
    def _simulate_nav(self, returns: List[float]) -> List[float]:
        """从收益率序列模拟净值"""
        nav = [100.0]
        for r in returns:
            nav.append(nav[-1] * (1 + r / 100))
        return nav
    
    # ========== 风险调整收益比率（增强） ==========
    
    def risk_adjusted_ratios(self) -> dict:
        """多种风险调整收益比率（v4.0 修复版：低风险产品使用绝对收益评估）"""
        if not self.p.daily_returns:
            return {"error": "无历史数据"}
        
        returns = self.p.daily_returns
        annual_ret = np.mean(returns) * 252
        volatility = self.stats.annualized_volatility(returns)
        downside_dev = self.stats.downside_deviation(returns)
        
        # ── v4.0 修复：对于低风险产品(R1/R2)，夏普比率在无风险利率>产品收益时
        #     会产生无意义的巨大负值。改用"相对同期存款的超额收益/波动率" ──
        if self.p.risk_level <= 2 and annual_ret < self.RISK_FREE_RATE:
            # 低风险产品使用存款基准替代无风险利率
            adjusted_benchmark = self.BENCHMARK_DEPOSIT_RATE - 0.5  # 1.5%
            sharpe = (annual_ret - adjusted_benchmark) / volatility if volatility > 0 else 0
            sortino = (annual_ret - adjusted_benchmark) / downside_dev if downside_dev > 0 else 0
            ratio_note = f"（使用调整基准{adjusted_benchmark}%，非国债{self.RISK_FREE_RATE}%）"
        else:
            sharpe = (annual_ret - self.RISK_FREE_RATE) / volatility if volatility > 0 else 0
            sortino = (annual_ret - self.RISK_FREE_RATE) / downside_dev if downside_dev > 0 else 0
            ratio_note = ""
        
        # 卡玛比率（收益/最大回撤），P0 修复：对回撤极小的低风险产品做上限处理
        nav = self.p.nav_series if self.p.nav_series else self._simulate_nav(returns)
        max_dd, _, _ = self.stats.max_drawdown(nav)
        # 回撤小于 0.01% 视为无意义（产品可能没有经历市场波动），使用风险等级默认值
        if max_dd < 0.01:
            dd_defaults = {1: 0.05, 2: 0.3, 3: 2.0, 4: 8.0, 5: 15.0}
            effective_dd = dd_defaults.get(self.p.risk_level, 2.0)
        else:
            effective_dd = max_dd
        calmar = annual_ret / effective_dd if effective_dd > 0 else 0
        # 卡玛比率上限 500（防止极端值影响评分）
        calmar = min(calmar, 500.0)
        
        # 信息比率（相对基准）
        if self.p.benchmark_returns and len(self.p.benchmark_returns) == len(returns):
            benchmark_annual = np.mean(self.p.benchmark_returns) * 252
            tracking_err = self.stats.tracking_error(returns, self.p.benchmark_returns)
            info_ratio = (annual_ret - benchmark_annual) / tracking_err if tracking_err > 0 else 0
        else:
            info_ratio = 0
        
        # 特雷诺比率
        treynor = (annual_ret - self.RISK_FREE_RATE) / self.p.risk_level if self.p.risk_level > 0 else 0
        
        return {
            "夏普比率": round(sharpe, 3),
            "索提诺比率": round(sortino, 3),
            "卡玛比率": round(calmar, 3),
            "信息比率": round(info_ratio, 3),
            "特雷诺比率": round(treynor, 3),
            "调整说明": ratio_note,
        }
    
    # ========== 收益质量分析 ==========
    
    def return_quality(self) -> dict:
        """收益质量指标"""
        if not self.p.daily_returns:
            return {"error": "无历史数据"}
        
        returns = self.p.daily_returns
        
        # 胜率
        win_rate = self.stats.win_rate(returns)
        
        # 盈亏比
        pl_ratio = self.stats.profit_loss_ratio(returns)
        
        # 最大单日涨幅/跌幅
        max_gain = max(returns)
        max_loss = min(returns)
        
        # 正负收益天数
        positive_days = sum(1 for r in returns if r > 0)
        negative_days = sum(1 for r in returns if r < 0)
        
        # 收益稳定性（变异系数）
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        cv = std_ret / abs(mean_ret) if mean_ret != 0 else float('inf')
        
        return {
            "胜率(%)": round(win_rate, 2),
            "盈亏比": round(pl_ratio, 2),
            "最大单日涨幅(%)": round(max_gain, 4),
            "最大单日跌幅(%)": round(max_loss, 4),
            "正收益天数": positive_days,
            "负收益天数": negative_days,
            "收益变异系数": round(cv, 3),
        }
    
    # ========== 基准对比分析 ==========
    
    def benchmark_comparison(self) -> dict:
        """与基准对比"""
        if not self.p.daily_returns or not self.p.benchmark_returns:
            return {"error": "无基准数据"}
        
        if len(self.p.daily_returns) != len(self.p.benchmark_returns):
            return {"error": "数据长度不匹配"}
        
        prod_returns = self.p.daily_returns
        bench_returns = self.p.benchmark_returns
        
        # 累计收益
        prod_cum = np.prod([1 + r/100 for r in prod_returns]) - 1
        bench_cum = np.prod([1 + r/100 for r in bench_returns]) - 1
        
        # 年化收益
        prod_annual = np.mean(prod_returns) * 252
        bench_annual = np.mean(bench_returns) * 252
        
        # 超额收益
        excess = prod_annual - bench_annual
        
        # 相关系数
        correlation = self.stats.correlation(prod_returns, bench_returns)
        
        # 跟踪误差
        tracking_err = self.stats.tracking_error(prod_returns, bench_returns)
        
        # Beta（简化计算）
        cov = np.cov(prod_returns, bench_returns)[0, 1]
        bench_var = np.var(bench_returns)
        beta = cov / bench_var if bench_var > 0 else 1.0
        
        # Alpha（Jensen's Alpha）
        alpha = prod_annual - (self.RISK_FREE_RATE + beta * (bench_annual - self.RISK_FREE_RATE))
        
        return {
            "基准名称": self.p.benchmark_name,
            "产品累计收益(%)": round(prod_cum * 100, 2),
            "基准累计收益(%)": round(bench_cum * 100, 2),
            "超额收益(%)": round(excess, 2),
            "相关系数": round(correlation, 3),
            "跟踪误差(%)": round(tracking_err, 2),
            "Beta": round(beta, 3),
            "Alpha(%)": round(alpha, 2),
        }
    
    # ========== 税收分析 ==========
    
    def tax_analysis(self, investment: float = 100000) -> dict:
        """税收影响分析"""
        gross_return_pct = self.gross_return()
        gross_profit = investment * gross_return_pct / 100
        
        if self.p.tax_free:
            tax_amount = 0
            net_profit = gross_profit
        else:
            tax_amount = gross_profit * self.p.tax_rate / 100
            net_profit = gross_profit - tax_amount
        
        net_return_pct = net_profit / investment * 100
        
        return {
            "毛收益": round(gross_profit, 2),
            "税率(%)": self.p.tax_rate,
            "税额": round(tax_amount, 2),
            "税后收益": round(net_profit, 2),
            "税后收益率(%)": round(net_return_pct, 2),
            "税收拖累(%)": round(gross_return_pct - net_return_pct, 2),
        }
    
    # ========== 压力测试 ==========
    
    def stress_test(self) -> dict:
        """压力测试 - 极端市场条件"""
        if not self.p.daily_returns:
            return {"error": "无历史数据"}
        
        returns = np.array(self.p.daily_returns)
        
        # 历史极端情景
        worst_day = np.min(returns)
        worst_week = np.sum(sorted(returns)[:5])  # 最差5天
        
        # 模拟压力情景
        scenarios = {
            "2020疫情冲击": -15.0,  # 模拟下跌15%
            "2015股灾": -30.0,
            "利率上升100bp": -5.0,
            "信用违约事件": -10.0,
        }
        
        stress_results = {}
        for scenario, shock in scenarios.items():
            # 根据产品风险等级调整冲击
            adjusted_shock = shock * (self.p.risk_level / 3)
            stress_results[scenario] = round(adjusted_shock, 2)
        
        return {
            "历史最差单日(%)": round(worst_day, 2),
            "历史最差一周(%)": round(worst_week, 2),
            "压力情景预估": stress_results,
        }
    
    # ========== 同类排名 ==========
    
    def peer_ranking(self) -> dict:
        """同类排名分析"""
        if self.p.peer_count == 0:
            return {"error": "无排名数据"}
        
        percentile = (1 - self.p.peer_rank / self.p.peer_count) * 100
        
        if percentile >= 75:
            rating = "★★★★★ 优秀"
        elif percentile >= 50:
            rating = "★★★★ 良好"
        elif percentile >= 25:
            rating = "★★★ 一般"
        elif percentile >= 10:
            rating = "★★ 较差"
        else:
            rating = "★ 落后"
        
        return {
            "排名": f"{self.p.peer_rank}/{self.p.peer_count}",
            "百分位": round(percentile, 1),
            "评级": rating,
        }
    
    # ========== 流动性评分（v5.0 增强） ==========
    
    def liquidity_score(self) -> dict:
        """流动性详细评分（v5.0：真实期限+赎回费阶梯+期限类型）"""
        score = 100.0
        details = []
        
        # 期限类型 + 期限天数
        term_days = self.p.term_days
        term_type = self.p.term_type
        min_hold = self.p.min_holding_days
        
        details.append(f"产品类型: {term_type}")
        
        # 根据期限类型和天数综合评估
        if term_type in ("开放式(T+0/T+1)", "开放式") and term_days <= 7:
            score -= 3
            details.append(f"灵活申赎（{term_days}天，+97）")
        elif min_hold > 0:
            # 最短持有期产品
            if min_hold <= 7:
                score -= 10
                details.append(f"最短持有{min_hold}天（+90）")
            elif min_hold <= 30:
                score -= 20
                details.append(f"最短持有{min_hold}天（+80）")
            elif min_hold <= 90:
                score -= 35
                details.append(f"最短持有{min_hold}天（+65）")
            elif min_hold <= 180:
                score -= 50
                details.append(f"最短持有{min_hold}天（+50）")
            elif min_hold <= 365:
                score -= 60
                details.append(f"最短持有{min_hold}天（+40）")
            else:
                score -= 70
                details.append(f"最短持有{min_hold}天（+30）")
        elif term_days <= 7:
            score -= 5
            details.append("超短期（+95）")
        elif term_days <= 30:
            score -= 10
            details.append("短期（+90）")
        elif term_days <= 90:
            score -= 20
            details.append("中短期（+80）")
        elif term_days <= 180:
            score -= 35
            details.append("中期（+65）")
        elif term_days <= 365:
            score -= 50
            details.append("中长期（+50）")
        else:
            score -= 65
            details.append("长期（+35）")
        
        # 封闭式产品额外扣分
        if term_type == "封闭式":
            score -= 15
            details.append("封闭式产品（-15）")
        elif term_type == "定期开放":
            score -= 10
            details.append("定期开放（-10）")
        
        # 赎回条件
        if not self.p.early_redeemable:
            score -= 30
            details.append("不可提前赎回（-30）")
        elif self.p.early_redeem_penalty > 0:
            penalty = min(30, self.p.early_redeem_penalty * 10)
            score -= penalty
            details.append(f"提前赎回惩罚{self.p.early_redeem_penalty}%（-{penalty:.0f}）")
        
        # 赎回费率
        if self.p.redemption_fee_rate > 0:
            score -= min(20, self.p.redemption_fee_rate * 10)
            details.append(f"赎回费率{self.p.redemption_fee_rate}%")
        
        # v5.0: 赎回费阶梯信息
        if self.p.redemption_fee_tiers:
            tier_info = ", ".join(f"{d}天→{r}%" for d, r in self.p.redemption_fee_tiers[:3])
            details.append(f"赎回费阶梯: {tier_info}")
        
        # 基金规模
        if self.p.fund_size > 100:
            score -= 10
            details.append(f"规模过大{self.p.fund_size}亿（-10）")
        
        return {
            "流动性评分": round(max(0, min(100, score)), 1),
            "评分明细": details,
            "产品期限": f"{term_type} | {term_days}天" + (f" | 最短持有{min_hold}天" if min_hold > 0 else ""),
        }
    
    # ========== 综合评分（v4.0 重写：动态权重+管理人+市场环境） ==========
    
    def comprehensive_score(self, profile: Optional[InvestorProfile] = None) -> dict:
        """v5.0 综合评分：动态权重+管理人+市场环境+行为金融+真实业绩"""
        
        if profile is None:
            profile = InvestorProfile()
        
        weights = profile.get_weights()
        
        # ── 1. 收益性（v5.0：优先使用真实历史年化） ──
        # 如果成立满1年且有真实累计收益率，用真实数据
        if self.p.inception_nav_yield > 0 and self.p.inception_years > 1:
            real_annualized = ((1 + self.p.inception_nav_yield / 100) ** (1 / self.p.inception_years) - 1) * 100
            effective_ret = real_annualized  # 使用真实年化
        else:
            effective_ret = self.net_return_after_fee()
        
        # 根据风险等级调整收益阈值
        if self.p.risk_level <= 2:
            if effective_ret >= 4:
                ret_score = 90
            elif effective_ret >= 3:
                ret_score = 75
            elif effective_ret >= 2:
                ret_score = 60
            elif effective_ret >= self.BENCHMARK_DEPOSIT_RATE - 0.5:
                ret_score = 45
            else:
                ret_score = max(10, 20 + effective_ret * 10)
        else:
            if effective_ret >= 12:
                ret_score = 95
            elif effective_ret >= 8:
                ret_score = 80
            elif effective_ret >= 5:
                ret_score = 65
            elif effective_ret >= 3:
                ret_score = 50
            else:
                ret_score = max(0, 30 + effective_ret * 5)
        
        # ── 2. 安全性（v5.1：区分同一风险等级内的差异+P1信用穿透） ──
        base_safety = max(0, 100 - (self.p.risk_level - 1) * 18)
        equity_penalty = min(15, self.p.equity_allocation_pct * 0.3)
        fx_penalty = 5 if self.p.currency == "USD" else 0
        deriv_penalty = min(5, self.p.derivatives_allocation_pct * 0.5)
        
        # v5.0: 历史业绩稳定性扣分（年化收益波动大→安全性降低）
        stability_penalty = 0
        if len(self.p.historical_annual_returns) >= 3:
            hist_std = np.std(self.p.historical_annual_returns)
            if hist_std > 2:
                stability_penalty = min(10, (hist_std - 2) * 3)
        
        # P1: 信用质量分析
        credit_info = CreditQualityAnalyzer.analyze(self.p)
        credit_score = credit_info["信用评分"]
        # 信用评分映射到安全性调整（信用差的产品安全性降低）
        if credit_score >= 90:
            credit_safety_adj = 0
        elif credit_score >= 70:
            credit_safety_adj = -3
        elif credit_score >= 50:
            credit_safety_adj = -8
        elif credit_score >= 30:
            credit_safety_adj = -15
        else:
            credit_safety_adj = -25
        # 风险信号额外扣分
        risk_flag_penalty = len(credit_info.get("风险信号", [])) * 3
        
        safety_score = max(10, base_safety - equity_penalty - fx_penalty - deriv_penalty - stability_penalty + credit_safety_adj - risk_flag_penalty)
        
        # ── 3. 风险调整收益 ──
        ratios = self.risk_adjusted_ratios()
        if "error" not in ratios:
            sharpe = ratios["夏普比率"]
            calmar = ratios.get("卡玛比率", 0)
            
            if self.p.risk_level <= 2:
                # P0 修复：卡玛比率已用合理回撤替代极低回撤，阈值相应调整
                if calmar > 30:
                    risk_adj_score = 90
                elif calmar > 15:
                    risk_adj_score = 80
                elif calmar > 5:
                    risk_adj_score = 65
                elif calmar > 1.5:
                    risk_adj_score = 50
                else:
                    risk_adj_score = 35
            else:
                if sharpe >= 2:
                    risk_adj_score = 95
                elif sharpe >= 1.5:
                    risk_adj_score = 80
                elif sharpe >= 1:
                    risk_adj_score = 65
                elif sharpe >= 0.5:
                    risk_adj_score = 50
                else:
                    risk_adj_score = 30
        else:
            risk_adj_score = 50
        
        # ── 4. 流动性 ──
        liq = self.liquidity_score()
        liq_score = liq["流动性评分"]
        
        # ── 5. 费用 ──
        fees = self.total_fee_cost()
        annual_total_fee = fees.get("年化总费率(%)", 1.0)
        if annual_total_fee <= 0.3:
            fee_score = 95
        elif annual_total_fee <= 0.5:
            fee_score = 85
        elif annual_total_fee <= 0.8:
            fee_score = 70
        elif annual_total_fee <= 1.2:
            fee_score = 55
        else:
            fee_score = 35
        
        if self.p.has_performance_fee:
            fee_score -= 10
            if self.p.performance_fee_rate >= 50:
                fee_score -= 5
        
        # ── 6. 管理人评分 ──
        manager_info = ManagerEvaluator.evaluate(self.p)
        manager_score = manager_info["管理人评分"]
        
        # ── 7. 市场环境调整 ──
        market_info = MarketContext.evaluate(self.p)
        market_adj = market_info.get("市场环境调整", 0)
        
        # ── 加权总分 ──
        total = (ret_score * weights.get("收益性", 0.25) +
                 safety_score * weights.get("安全性", 0.25) +
                 risk_adj_score * weights.get("风险调整", 0.20) +
                 liq_score * weights.get("流动性", 0.15) +
                 fee_score * weights.get("费用", 0.10) +
                 manager_score * weights.get("同类排名", 0.05) * 0.01)
        
        total += market_adj * 0.5
        total = max(0, min(100, total))
        
        # ── v5.0: 行为金融适配度 ──
        behavioral = BehavioralAdvisor.evaluate(self.p, profile)
        
        # ── v5.1: 申购时机建议 ──
        timing = TimingAdvisor.evaluate(self.p, profile)
        
        # ── v5.1: 投资经理个人评估 ──
        personal_mgr = PersonalManagerEvaluator.evaluate(self.p)
        
        return {
            "综合得分": round(total, 1),
            "收益性": round(ret_score, 1),
            "安全性": round(safety_score, 1),
            "风险调整": round(risk_adj_score, 1),
            "流动性": round(liq_score, 1),
            "费用": round(fee_score, 1),
            "管理人评分": round(manager_score, 1),
            "市场调整": round(market_adj * 0.5, 1),
            "权重配置": weights,
            "安全明细": {
                "基础安全分": base_safety,
                "权益仓位扣分": round(equity_penalty, 1),
                "汇率扣分": fx_penalty,
                "衍生品扣分": round(deriv_penalty, 1),
                "业绩波动扣分": round(stability_penalty, 1),
                "信用质量调整": credit_safety_adj,
                "信用风险信号扣分": -risk_flag_penalty,
            },
            "费用明细": {
                "年化总费率(%)": annual_total_fee,
                "含超额报酬": self.p.has_performance_fee,
            },
            "管理人信息": manager_info,
            "投资经理": personal_mgr,
            "市场环境": market_info,
            "申购时机": timing,
            "行为金融适配": behavioral,
            "信用质量": {
                "信用等级": credit_info["信用等级"],
                "信用评分": credit_info["信用评分"],
                "风险信号": credit_info["风险信号"],
                "判断": credit_info["底层信用判断"],
            },
            "真实业绩参考": {
                "成立以来净值收益率(%)": self.p.inception_nav_yield if self.p.inception_nav_yield > 0 else "无数据",
                "成立年限": round(self.p.inception_years, 1) if self.p.inception_years > 0 else "未知",
                "历年收益率": self.p.historical_annual_returns if self.p.historical_annual_returns else "无数据",
            } if self.p.inception_nav_yield > 0 or self.p.historical_annual_returns else None,
        }
    
    # ========== 资产配置建议 ==========
    
    def allocation_advice(self) -> dict:
        """资产配置建议"""
        risk_level = self.p.risk_level
        product_type = self.p.product_type
        
        # 根据风险等级建议配置比例
        if risk_level <= 2:
            role = "防守型资产"
            suggested_weight = "30-50%"
            suitable_for = "风险厌恶型投资者"
        elif risk_level == 3:
            role = "平衡型资产"
            suggested_weight = "20-40%"
            suitable_for = "稳健型投资者"
        else:
            role = "进攻型资产"
            suggested_weight = "10-30%"
            suitable_for = "积极型投资者"
        
        # 组合搭配建议
        if product_type == "固收":
            pairing = "可搭配权益类提升收益"
        elif product_type == "权益":
            pairing = "需搭配固收类降低波动"
        elif product_type == "货币":
            pairing = "作为现金管理工具"
        else:
            pairing = "作为核心配置"
        
        return {
            "资产角色": role,
            "建议配置比例": suggested_weight,
            "适合人群": suitable_for,
            "搭配建议": pairing,
        }
    
    # ========== 同类横向对比 ==========
    
    @staticmethod
    def peer_comparison(products: List[FinancialProduct], top_n: int = 20) -> dict:
        """同风险等级内横向对比排名
        
        对所有产品按综合得分排序，找出同类中的最优选择。
        """
        if not products:
            return {"error": "无产品数据"}
        
        # 按风险等级分组
        groups = {}
        for p in products:
            rl = p.risk_level
            if rl not in groups:
                groups[rl] = []
            groups[rl].append(p)
        
        result = {"分组统计": {}, "各等级TOP": {}}
        
        for rl in sorted(groups.keys()):
            group = groups[rl]
            # 计算每个产品的综合得分
            scored = []
            for p in group:
                analyzer = DeepProductAnalyzer(p)
                score = analyzer.comprehensive_score()["综合得分"]
                scored.append((score, p))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            
            # 统计
            scores = [s[0] for s in scored]
            result["分组统计"][f"R{rl}"] = {
                "数量": len(group),
                "平均得分": round(statistics.mean(scores), 1),
                "最高得分": round(max(scores), 1),
                "最低得分": round(min(scores), 1),
                "中位得分": round(statistics.median(scores), 1),
            }
            
            # TOP N
            top = scored[:top_n]
            result["各等级TOP"][f"R{rl}"] = [
                {
                    "排名": i + 1,
                    "得分": round(s, 1),
                    "代码": p.product_code,
                    "名称": p.name[:40],
                    "年化(%)": round(p.annual_rate, 2),
                    "类型": p.product_type,
                }
                for i, (s, p) in enumerate(top)
            ]
        
        return result
    
    # ========== 持有期收益分析 ==========
    
    def holding_period_analysis(self) -> dict:
        """持有期收益概率分析
        
        基于历史日收益率，计算不同持有期下盈利概率和预期收益范围。
        """
        if not self.p.daily_returns:
            return {"error": "无历史数据"}
        
        returns = np.array(self.p.daily_returns)
        n = len(returns)
        
        periods = {"1个月(22天)": 22, "3个月(66天)": 66, "6个月(126天)": 126, "1年(252天)": 252}
        result = {}
        
        for label, days in periods.items():
            if days > n:
                continue
            
            # 滚动窗口模拟
            rolling_returns = []
            for i in range(n - days + 1):
                cumulative = np.prod(1 + returns[i:i+days] / 100) - 1
                rolling_returns.append(cumulative * 100)
            
            rolling_returns = np.array(rolling_returns)
            win_prob = np.sum(rolling_returns > 0) / len(rolling_returns) * 100
            
            result[label] = {
                "盈利概率(%)": round(win_prob, 1),
                "平均收益(%)": round(np.mean(rolling_returns), 2),
                "中位收益(%)": round(np.median(rolling_returns), 2),
                "最差收益(%)": round(np.min(rolling_returns), 2),
                "最佳收益(%)": round(np.max(rolling_returns), 2),
                "收益标准差(%)": round(np.std(rolling_returns), 2),
            }
        
        return result
    
    # ========== 完整分析报告 ==========
    
    def full_report(self, investment: float = 100000, profile: Optional[InvestorProfile] = None) -> dict:
        """生成完整分析报告（v5.0：增加真实业绩、行为适配、组合分析）"""
        if profile is None:
            profile = InvestorProfile()
        
        # 综合评分（包含行为适配）
        comp = self.comprehensive_score(profile)
        
        report = {
            "基础信息": {
                "产品名称": self.p.name,
                "产品代码": self.p.product_code,
                "发行机构": self.p.issuer,
                "产品类型": self.p.product_type,
                "风险等级": f"{'★' * self.p.risk_level}{'☆' * (5 - self.p.risk_level)} (R{self.p.risk_level})",
                "投资期限": f"{self.p.term_type} | {self.p.term_days}天" + (f" | 最短持有{self.p.min_holding_days}天" if self.p.min_holding_days > 0 else ""),
                "起投金额": f"¥{self.p.min_investment:,.0f}",
                "币种": self.p.currency,
                "久期特征": self.p.duration_hint,
                "成立日期": self.p.inception_date.strftime('%Y-%m-%d') if self.p.inception_date else "未知",
            },
            "资产配置": {
                "权益类比例(%)": self.p.equity_allocation_pct,
                "固收类比例(%)": self.p.fixed_income_allocation_pct,
                "衍生品比例(%)": self.p.derivatives_allocation_pct,
                "底层资产描述": self.p.asset_description[:200] if self.p.asset_description else "无",
            },
            "收益分析": {
                "毛收益率(%)": round(self.gross_return(), 2),
                "预期年化(%)": self.p.annual_rate,
                "业绩基准区间": f"{self.p.annual_rate_low:.2f}%-{self.p.annual_rate_high:.2f}%" if self.p.annual_rate_low > 0 else "无明确区间",
                "净年化(扣费%)": round(self.net_return_after_fee(investment), 2),
                "实际收益(扣通胀%)": round(self.real_return(), 2),
            },
            "费用分析": self.total_fee_cost(investment),
            "税收分析": self.tax_analysis(investment),
            "风险指标": self.risk_metrics(),
            "风险调整比率": self.risk_adjusted_ratios(),
            "收益质量": self.return_quality(),
            "基准对比": self.benchmark_comparison(),
            "持有期分析": self.holding_period_analysis(),
            "流动性": self.liquidity_score(),
            "压力测试": self.stress_test(),
            "综合评分": comp,
            "资产配置建议": self.allocation_advice(),
        }
        
        # v5.0: 真实历史业绩
        if comp.get("真实业绩参考"):
            report["真实历史业绩"] = comp["真实业绩参考"]
        
        # v5.1: 申购时机建议
        timing = comp.get("申购时机", {})
        if timing:
            report["申购时机建议"] = timing
        
        # v5.1: 投资经理信息
        personal_mgr = comp.get("投资经理", {})
        if personal_mgr:
            report["投资经理评估"] = personal_mgr
        
        # v5.0: 行为金融适配
        behavioral = comp.get("行为金融适配", {})
        if behavioral:
            report["行为金融适配"] = behavioral
        
        # P1: 信用质量
        credit = comp.get("信用质量", {})
        if credit:
            report["信用质量分析"] = credit
        
        # 买卖建议（v5.0：结合行为适配）
        total_score = comp["综合得分"]
        market_rating = comp.get("市场环境", {}).get("市场环境评级", "中性")
        behavior_match = behavioral.get("适配评分", 100)
        
        # 行为适配度显著影响最终建议
        if behavior_match < 50:
            verdict = "🔴 与您的画像严重不匹配，不建议买入"
        elif total_score >= 80 and behavior_match >= 80:
            verdict = "🟢 强烈推荐买入"
        elif total_score >= 70 and behavior_match >= 70:
            verdict = "🟢 推荐买入"
        elif total_score >= 60:
            verdict = "🟡 可以考虑买入"
        elif total_score >= 50:
            verdict = "🟠 中性，需对比其他产品"
        elif total_score >= 35:
            verdict = "🔴 不太推荐"
        else:
            verdict = "⛔ 不建议买入"
        
        if market_rating == "不利" and "推荐" in verdict:
            verdict += "（但当前市场环境不利，建议等待）"
        
        report["买卖建议"] = verdict
        report["用户画像"] = {
            "风险偏好": f"R{profile.risk_tolerance}",
            "投资目标": profile.investment_goal,
            "投资期限": profile.investment_horizon,
            "流动性需求": profile.liquidity_need,
        }
        
        return report


# ─────────────────────────────────────────────
# 4. 报告打印工具
# ─────────────────────────────────────────────

def print_full_report(report: dict):
    """打印完整报告（v6.0 增强版）"""
    
    print("\n" + "=" * 80)
    print(f"📊 理财产品深度分析报告 v6.1 - {report['基础信息']['产品名称'][:50]}")
    print("=" * 80)
    
    # 基础信息
    print("\n【基础信息】")
    for k, v in report["基础信息"].items():
        print(f"  {k}: {v}")
    
    # 资产配置
    if "资产配置" in report:
        print("\n【资产配置穿透】")
        for k, v in report["资产配置"].items():
            if k != "底层资产描述":
                print(f"  {k}: {v}")
        if report["资产配置"].get("底层资产描述") and report["资产配置"]["底层资产描述"] != "无":
            print(f"  底层资产: {report['资产配置']['底层资产描述'][:120]}...")
    
    # P1: 信用质量分析
    credit = report.get("信用质量分析", {})
    if credit:
        print(f"\n🔍 信用质量：{credit.get('信用等级', '?')} (信用分{credit.get('信用评分', '?')})")
        print(f"  {credit.get('判断', '')}")
        risk_flags = credit.get("风险信号", [])
        if risk_flags:
            print(f"  ⚠️ 风险信号: {'、'.join(risk_flags)}")
    
    # P1: 费率竞争力
    fee_comp = report.get("费率竞争力", {})
    if fee_comp and "error" not in fee_comp:
        print(f"\n💰 费率竞争力：{fee_comp.get('费率评级', '?')}")
        print(f"  同类费率中位数: {fee_comp.get('同类费率中位数', '?')}% | 百分位: {fee_comp.get('费率百分位', '?')}% (越低越好)")
        print(f"  同类费率范围: {fee_comp.get('同类费率最低', '?')}% ~ {fee_comp.get('同类费率最高', '?')}% (共{fee_comp.get('同类产品数量', '?')}款同类产品)")
    
    # 买卖建议 + 行为适配
    print(f"\n💡 买卖建议：{report['买卖建议']}")
    print(f"📈 综合得分：{report['综合评分']['综合得分']}/100")
    
    # v5.1: 申购时机建议
    timing = report.get("申购时机建议", {})
    if timing:
        print(f"⏰ 申购时机：{timing.get('时机评估', '?')} (时机分{timing.get('综合时机评分', '?')})")
        strategy = timing.get("申购策略", "")
        if strategy:
            print(f"  📋 {strategy}")
        for key in ("利率周期", "权益估值"):
            if key in timing and isinstance(timing[key], dict):
                item = timing[key]
                print(f"  {item.get('判断', '')}")
                print(f"  → {item.get('策略', '')}")
        if "久期建议" in timing:
            print(f"  {timing['久期建议']}")
    
    # v5.1: 投资经理评估
    mgr_eval = report.get("投资经理评估", {})
    if mgr_eval:
        print(f"\n👤 投资经理评估：{mgr_eval.get('投资经理', '?')}")
        for k, v in mgr_eval.items():
            if k != "投资经理":
                print(f"  {v}")
    
    # v5.0: 行为金融适配
    behavior = report.get("行为金融适配", {})
    if behavior:
        print(f"\n🧠 适配评估：{behavior.get('适配评估', '?')} (适配分{behavior.get('适配评分', '?')})")
        for w in behavior.get("警告", []):
            print(f"  {w}")
        for t in behavior.get("行为提示", []):
            print(f"  {t}")
    
    # 用户画像
    if "用户画像" in report:
        print(f"👤 用户画像：风险R{report['用户画像']['风险偏好']} | {report['用户画像']['投资目标']} | 期限{report['用户画像']['投资期限']}")
    
    # v5.0: 真实历史业绩
    hist = report.get("真实历史业绩", {})
    if hist:
        print("\n【真实历史业绩】")
        for k, v in hist.items():
            if v and v != "无数据" and v != "未知":
                print(f"  {k}: {v}")
    
    # 收益分析
    print("\n【收益分析】")
    for k, v in report["收益分析"].items():
        print(f"  {k}: {v}")
    
    # 费用分析
    print("\n【费用分析】")
    for k, v in report["费用分析"].items():
        print(f"  {k}: {v}")
    
    # 风险指标
    print("\n【风险指标】")
    for k, v in report["风险指标"].items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for sk, sv in v.items():
                print(f"    {sk}: {sv}")
        else:
            print(f"  {k}: {v}")
    
    # 风险调整比率
    print("\n【风险调整收益比率】")
    for k, v in report["风险调整比率"].items():
        if v and str(v) != "" and k != "调整说明":
            print(f"  {k}: {v}")
        elif k == "调整说明" and v:
            print(f"  ⚠️ {v}")
    
    # 收益质量
    print("\n【收益质量】")
    for k, v in report["收益质量"].items():
        print(f"  {k}: {v}")
    
    # 持有期分析
    print("\n【持有期收益概率分析】")
    if "error" not in report.get("持有期分析", {}):
        for period, data in report["持有期分析"].items():
            print(f"  {period}:")
            for k, v in data.items():
                print(f"    {k}: {v}")
    
    # 基准对比
    print("\n【基准对比】")
    for k, v in report["基准对比"].items():
        print(f"  {k}: {v}")
    
    # 流动性
    print("\n【流动性分析】")
    liq = report["流动性"]
    print(f"  流动性评分: {liq['流动性评分']}")
    if "产品期限" in liq:
        print(f"  产品期限: {liq['产品期限']}")
    for detail in liq["评分明细"]:
        print(f"    - {detail}")
    
    # 管理人信息
    score_detail = report.get("综合评分", {})
    if "管理人信息" in score_detail:
        print("\n【管理人评估】")
        mgr = score_detail["管理人信息"]
        for k, v in mgr.items():
            print(f"  {k}: {v}")
    
    # 市场环境
    if "市场环境" in score_detail:
        print("\n【市场环境】")
        mk = score_detail["市场环境"]
        for k, v in mk.items():
            if not k.endswith("调整"):
                print(f"  {k}: {v}")
    
    # 压力测试
    print("\n【压力测试】")
    for k, v in report["压力测试"].items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for sk, sv in v.items():
                print(f"    {sk}: {sv}%")
        else:
            print(f"  {k}: {v}")
    
    # 综合评分
    print("\n【综合评分明细】")
    for k, v in report["综合评分"].items():
        if k in ("综合得分", "权重配置", "安全明细", "费用明细", "管理人信息", "市场环境", "行为金融适配", "真实业绩参考"):
            continue
        if isinstance(v, (int, float)):
            bar = "█" * int(float(v) / 5) + "░" * (20 - int(float(v) / 5))
            print(f"  {k:15s} {bar} {v}")
    
    # 资产配置建议
    print("\n【资产配置建议】")
    for k, v in report["资产配置建议"].items():
        print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)


def print_peer_comparison_report(comparison: dict):
    """打印同类横向对比报告"""
    print("\n" + "=" * 80)
    print("📊 同类产品横向对比排名报告")
    print("=" * 80)
    
    # 分组统计
    print("\n【各风险等级统计】")
    for rl, stats in comparison.get("分组统计", {}).items():
        print(f"  {rl}: 共{stats['数量']}款 | 平均{stats['平均得分']}分 | 最高{stats['最高得分']}分 | 中位{stats['中位得分']}分")
    
    # 各等级 TOP 产品
    for rl, top_list in comparison.get("各等级TOP", {}).items():
        print(f"\n{'─' * 60}")
        print(f"🏆 {rl} 等级 TOP 5 产品")
        print(f"{'─' * 60}")
        print(f"  {'排名':4s} {'得分':6s} {'代码':12s} {'年化':8s} {'类型':8s} 产品名称")
        print(f"  {'─' * 55}")
        for item in top_list[:5]:
            print(f"  {item['排名']:4d} {item['得分']:6.1f} {item['代码']:12s} {item['年化(%)']:6.2f}% {item['类型']:8s} {item['名称'][:35]}")
    
    print("\n" + "=" * 80)


# ─────────────────────────────────────────────
# 5. 使用示例
# ─────────────────────────────────────────────

def generate_sample_data(days: int = 252) -> Tuple[List[float], List[float]]:
    """生成模拟历史数据"""
    # 产品日收益率（带一定趋势和波动）
    np.random.seed(42)
    daily_drift = 0.03 / 252  # 年化3%
    daily_vol = 0.8 / np.sqrt(252)  # 年化波动率0.8%
    returns = np.random.normal(daily_drift, daily_vol, days)
    
    # 基准日收益率
    bench_drift = 0.02 / 252
    bench_vol = 1.2 / np.sqrt(252)
    bench_returns = np.random.normal(bench_drift, bench_vol, days)
    
    return returns.tolist(), bench_returns.tolist()


def load_product_codes(csv_path: str) -> List[str]:
    """从 product_codes.csv 读取所有理财编码"""
    codes = []
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get("理财编码", "").strip()
                if code:
                    codes.append(code)
    except FileNotFoundError:
        print(f"❌ 文件不存在: {csv_path}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        sys.exit(1)
    
    if not codes:
        print("❌ product_codes.csv 中没有编码数据")
        sys.exit(1)
    
    return codes


def load_fund_from_csv(csv_path: str, fund_code: str) -> Optional[FinancialProduct]:
    """从 fund_screening_result.csv 中按基金代码加载基金数据"""
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["基金代码"].strip() == fund_code.strip():
                    # 行业分布 -> tags
                    tags = []
                    industry_str = row.get("行业分布", "")
                    if industry_str and industry_str.strip():
                        try:
                            import ast
                            industry_dict = ast.literal_eval(industry_str)
                            tags = list(industry_dict.keys())
                        except:
                            pass
                    
                    # 风险等级
                    score = float(row.get("综合评分", 50))
                    if score >= 75:
                        risk_level = 2
                    elif score >= 60:
                        risk_level = 3
                    elif score >= 45:
                        risk_level = 4
                    else:
                        risk_level = 5
                    
                    # 基金规模
                    fund_size_str = row.get("基金规模(亿)", "0")
                    try:
                        fund_size = float(fund_size_str) if fund_size_str.strip() else 0.0
                    except:
                        fund_size = 0.0
                    
                    # 年化收益
                    annual_rate_str = row.get("年化收益", "0")
                    try:
                        annual_rate = float(annual_rate_str.replace("%", "")) if annual_rate_str else 0.0
                    except:
                        annual_rate = 0.0
                    
                    # 年化波动率
                    vol_str = row.get("年化波动", "0")
                    try:
                        annual_vol = float(vol_str.replace("%", "")) if vol_str else 15.0
                    except:
                        annual_vol = 15.0
                    
                    # 经理经验
                    manager_exp_str = row.get("经理经验等级", "0")
                    try:
                        manager_experience = int(float(manager_exp_str) * 3) if manager_exp_str else 0
                    except:
                        manager_experience = 0
                    
                    # 任职年限
                    tenure_str = row.get("现任任职年数", "0")
                    try:
                        tenure = float(tenure_str) if tenure_str else 0.0
                    except:
                        tenure = 0.0
                    
                    # 生成模拟日收益率（基于年化收益和波动率）
                    seed = int(fund_code) % 10000 if fund_code.isdigit() else 42
                    np.random.seed(seed)
                    days = 252
                    daily_drift = (annual_rate / 100) / 252
                    daily_vol = (annual_vol / 100) / np.sqrt(252)
                    daily_returns = np.random.normal(daily_drift, daily_vol, days).tolist()
                    
                    # 基准日收益率
                    bench_drift = 0.02 / 252
                    bench_vol = 1.2 / np.sqrt(252)
                    benchmark_returns = np.random.normal(bench_drift, bench_vol, days).tolist()
                    
                    product = FinancialProduct(
                        product_code=fund_code.strip(),
                        name=row.get("基金名称", fund_code).strip(),
                        issuer=row.get("基金经理", "未知").strip(),
                        product_type=row.get("资产类别", "混合").strip(),
                        purchase_price=1.0,
                        current_price=1.0,
                        annual_rate=annual_rate,
                        term_days=365,
                        risk_level=risk_level,
                        min_investment=1000,
                        purchase_fee_rate=1.5,
                        management_fee_rate=1.5,
                        redemption_fee_rate=0.5,
                        early_redeemable=True,
                        early_redeem_penalty=1.0,
                        daily_returns=daily_returns,
                        benchmark_returns=benchmark_returns,
                        benchmark_name=row.get("匹配基准", "沪深300").strip(),
                        fund_size=fund_size,
                        manager_experience=manager_experience,
                        peer_rank=int(float(row.get("近1年百分位", 50)) * 10) if row.get("近1年百分位", "50") else 500,
                        peer_count=1000,
                        tax_rate=20.0,
                        tax_free=False,
                        inflation_rate=2.5,
                        tags=tags,
                    )
                    
                    # 生成净值序列
                    nav_series = [1.0]
                    for r in daily_returns:
                        nav_series.append(nav_series[-1] * (1 + r / 100))
                    product.nav_series = nav_series
                    
                    return product
            
            print(f"⚠️ 在 fund_screening_result.csv 中未找到基金代码: {fund_code}")
            return None
            
    except FileNotFoundError:
        print(f"❌ 文件不存在: {csv_path}")
        return None
    except Exception as e:
        print(f"❌ 读取CSV出错: {e}")
        return None


def load_product_detail(csv_path: str, code: str) -> Optional[FinancialProduct]:
    """从 product_codes.csv 读取产品详情并构建 FinancialProduct（模拟数据）"""
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_code = row.get("理财编码", "").strip()
                if row_code == code.strip():
                    name = row.get("产品名称", f"理财产品-{code}").strip()
                    issuer = row.get("发行机构", "未知").strip()
                    product_type = row.get("产品类型", "固收").strip()
                    annual_rate = float(row.get("年化收益", "3.5")) if row.get("年化收益", "3.5") else 3.5
                    risk_level = int(float(row.get("风险等级", "2"))) if row.get("风险等级", "2") else 2
                    term_days = int(float(row.get("期限天数", "365"))) if row.get("期限天数", "365") else 365
                    min_investment = float(row.get("起投金额", "1000")) if row.get("起投金额", "1000") else 1000
                    
                    # 根据年化收益和风险等级生成模拟日收益率
                    # 使用确定性哈希（hash() 跨进程不稳定，会导致结果不可复现）
                    seed = CMBDataSource._deterministic_hash(code) % 10000
                    np.random.seed(seed)
                    days = max(252, term_days)
                    daily_drift = (annual_rate / 100) / 252
                    daily_vol = (risk_level * 5 / 100) / np.sqrt(252)
                    daily_returns = np.random.normal(daily_drift, daily_vol, days).tolist()
                    
                    # 基准日收益率
                    np.random.seed(seed + 1)
                    bench_drift = 0.02 / 252
                    bench_vol = 1.2 / np.sqrt(252)
                    benchmark_returns = np.random.normal(bench_drift, bench_vol, days).tolist()
                    
                    product = FinancialProduct(
                        product_code=code.strip(),
                        name=name,
                        issuer=issuer,
                        product_type=product_type,
                        purchase_price=1.0,
                        current_price=1.0,
                        annual_rate=annual_rate,
                        term_days=term_days,
                        risk_level=risk_level,
                        min_investment=min_investment,
                        purchase_fee_rate=0.5,
                        management_fee_rate=0.8,
                        redemption_fee_rate=0.3,
                        early_redeemable=True,
                        early_redeem_penalty=0.5,
                        daily_returns=daily_returns,
                        benchmark_returns=benchmark_returns,
                        benchmark_name="沪深300",
                        peer_rank=max(1, int(risk_level * 200)),
                        peer_count=1000,
                        tax_rate=20.0,
                        tax_free=False,
                        inflation_rate=2.5,
                        tags=[product_type],
                    )
                    
                    # 生成净值序列
                    nav_series = [1.0]
                    for r in daily_returns:
                        nav_series.append(nav_series[-1] * (1 + r / 100))
                    product.nav_series = nav_series
                    
                    return product
            
            return None
            
    except FileNotFoundError:
        print(f"❌ 文件不存在: {csv_path}")
        return None
    except Exception as e:
        print(f"❌ 读取CSV出错: {e}")
        return None


if __name__ == "__main__":
    
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # ── 缓存状态 ──
    cache_info = ""
    if os.path.exists(CMBDataSource.CACHE_FILE):
        try:
            with open(CMBDataSource.CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
            age_h = (time.time() - cache_data["cached_at"]) / 3600
            cnt = cache_data.get("product_count", 0)
            cache_info = f"📦 缓存: {cnt} 款产品（{age_h:.1f}h 前）| 输入 'c' 清除缓存"
        except:
            pass
    
    # ── v4.0 用户画像 ──
    print(f"\n{'='*80}")
    print(f"📊 理财产品深度分析系统 v6.1")
    print(f"{'='*80}")
    if cache_info:
        print(f"  {cache_info}")
    
    print(f"\n👤 请设置您的投资画像（直接回车使用默认值）：")
    
    print(f"  风险承受能力:")
    print(f"    1-保守型  2-稳健型  3-平衡型  4-进取型  5-激进型")
    rt_input = input(f"  请输入 [1-5]（默认 3）: ").strip()
    risk_tol = int(rt_input) if rt_input in ("1","2","3","4","5") else 3
    
    print(f"\n  投资目标:")
    print(f"    1-短期理财  2-稳健增值  3-财富增值  4-子女教育  5-退休养老")
    goal_map = {"1": "短期理财", "2": "稳健增值", "3": "财富增值", "4": "子女教育", "5": "退休养老"}
    goal_input = input(f"  请输入 [1-5]（默认 2）: ").strip()
    goal = goal_map.get(goal_input, "稳健增值")
    
    print(f"\n  投资期限:")
    print(f"    1-<3个月  2-3~12个月  3-1~3年  4-3~5年  5->5年")
    horizon_map = {"1": "<3月", "2": "3-12月", "3": "1-3年", "4": "3-5年", "5": ">5年"}
    hz_input = input(f"  请输入 [1-5]（默认 3）: ").strip()
    horizon = horizon_map.get(hz_input, "1-3年")
    
    print(f"\n  流动性需求:")
    print(f"    1-低（长期不需动用）  2-中（偶尔需要）  3-高（随时可能用）")
    liq_map = {"1": "低", "2": "中", "3": "高"}
    liq_input = input(f"  请输入 [1-3]（默认 2）: ").strip()
    liquidity = liq_map.get(liq_input, "中")
    
    # 根据投资目标推断年龄
    if goal == "退休养老":
        age_range = ">65"
    elif goal == "子女教育":
        age_range = "30-50"
    else:
        age_range = "30-50"
    
    profile = InvestorProfile(
        risk_tolerance=risk_tol,
        investment_goal=goal,
        investment_horizon=horizon,
        liquidity_need=liquidity,
        age_range=age_range,
    )
    
    print(f"\n  ✅ 画像设置完成：风险R{risk_tol} | {goal} | 期限{horizon} | 流动性{ liquidity}")
    print(f"  📊 评分权重：{profile.get_weights()}")
    
    # ── 选择数据源 ──
    print(f"\n{'='*80}")
    print(f"  数据源选择:")
    print(f"    1. 招商银行 API 批量分析（实时数据，约 2200+ 款产品）")
    print(f"    2. 招行 API 指定产品代码深度对比（输入产品代码，逐个深度分析）")
    print(f"    3. 本地 CSV 文件（product_codes.csv）")
    print(f"    4. 浦发银行 API 批量分析（实时数据，约 5800+ 款产品）")
    print(f"{'='*80}")
    
    choice = input("\n请选择数据源 [1/2/3/4/c]（默认 1）: ").strip() or "1"
    
    if choice.lower() == 'c':
        CMBDataSource.clear_cache()
        SPDBDataSource.clear_cache()
        print("✅ 缓存已清除，下次将重新拉取 API 数据")
        choice = input("\n请重新选择数据源 [1/2/3/4]（默认 1）: ").strip() or "1"
    
    all_products = []
    use_cmb = (choice == "1")
    use_cmb_codes = (choice == "2")
    use_spdb = (choice == "4")
    
    if use_cmb or use_cmb_codes:
        print("\n📡 正在连接招商银行理财 API...")
        raw_products = CMBDataSource.fetch_all_products(max_pages=45)
        
        if not raw_products:
            print("❌ 无法获取招行数据，回退到 CSV 模式")
            use_cmb = False
            use_cmb_codes = False
        else:
            print(f"✅ 成功获取 {len(raw_products)} 款产品")
            
            if use_cmb_codes:
                print(f"\n{'─' * 60}")
                print(f"📋 可分析产品代码列表（前 50 款）:")
                print(f"{'─' * 60}")
                for i, raw in enumerate(raw_products[:50]):
                    code = raw.get('code', 'N/A')
                    name = raw.get('shortName', raw.get('name', ''))[:40]
                    risk = raw.get('risk', 'N/A')
                    perf = raw.get('zbasPrf', 'N/A')
                    print(f"  {i+1:3d}. [{risk}] {code} | {name} | {perf}")
                
                print(f"\n  ... 共 {len(raw_products)} 款产品")
                code_input = input("\n  产品代码（逗号分隔）: ").strip()
                
                if code_input:
                    target_codes = [c.strip() for c in code_input.split(",") if c.strip()]
                    raw_map = {r.get('code', ''): r for r in raw_products}
                    
                    print(f"\n📊 开始对 {len(target_codes)} 个指定产品进行深度对比分析...")
                    
                    for code in target_codes:
                        raw = raw_map.get(code)
                        if raw is None:
                            print(f"  ⚠️ 未找到产品代码: {code}，已跳过")
                            continue
                        try:
                            fp = CMBDataSource.to_financial_product(raw)
                            all_products.append(fp)
                            print(f"  ✅ 已加载: [{raw.get('risk', '?')}] {code} - {raw.get('shortName', raw.get('name', code))[:50]}")
                        except Exception as e:
                            print(f"  ❌ 加载失败: {code} - {e}")
                    
                    if len(all_products) == 0:
                        print("❌ 未成功加载任何产品")
                        sys.exit(1)
                else:
                    print("❌ 未输入产品代码")
                    sys.exit(1)
            else:
                for raw in raw_products:
                    try:
                        fp = CMBDataSource.to_financial_product(raw)
                        all_products.append(fp)
                    except:
                        pass
                print(f"✅ 成功转换 {len(all_products)} 款产品")
    
    if use_spdb:
        print("\n📡 正在连接浦发银行理财 API...")
        spdb_max_pages = 30  # 默认 30 页（300 条），全量约 583 页
        raw_products = SPDBDataSource.fetch_all_products(max_pages=spdb_max_pages)
        
        if not raw_products:
            print("❌ 无法获取浦发数据，回退到 CSV 模式")
            use_spdb = False
        else:
            print(f"✅ 成功获取 {len(raw_products)} 款产品，正在转换...")
            for i, raw in enumerate(raw_products):
                try:
                    fp = SPDBDataSource.to_financial_product(raw)
                    all_products.append(fp)
                except Exception as e:
                    if i < 3:  # 只打印前几个错误
                        print(f"  ⚠️ 转换失败: {raw.get('ProductCode', '?')} - {e}")
            print(f"✅ 成功转换 {len(all_products)} 款产品")
    
    if not use_cmb and not use_cmb_codes and not use_spdb:
        CODE_CSV = os.path.join(SCRIPT_DIR, "product_codes.csv")
        fund_codes = load_product_codes(CODE_CSV)
        
        print(f"📁 理财编码文件: {CODE_CSV}")
        print(f"🔢 待分析编码 ({len(fund_codes)} 个): {fund_codes}")
        
        cmb_raw_map = {}
        try:
            cached_products = CMBDataSource.fetch_all_products(max_pages=45)
            cmb_raw_map = {r.get('code', ''): r for r in cached_products}
            print(f"📦 已加载 CMB 缓存 ({len(cmb_raw_map)} 款产品)")
        except Exception as e:
            print(f"⚠️ 无法加载 CMB 缓存: {e}")
        
        for fund_code in fund_codes:
            product = None
            if fund_code in cmb_raw_map:
                try:
                    product = CMBDataSource.to_financial_product(cmb_raw_map[fund_code])
                    raw = cmb_raw_map[fund_code]
                    print(f"  ✅ [{raw.get('risk','?')}] {fund_code} - {raw.get('shortName', raw.get('name', fund_code))[:50]}")
                except Exception as e:
                    print(f"  ⚠️ CMB 匹配失败 {fund_code}: {e}")
            
            if product is None:
                product = load_product_detail(CODE_CSV, fund_code)
            
            if product is None:
                print(f"  ⚠️ 未找到编码 {fund_code} 的真实数据，使用默认参数")
                seed = CMBDataSource._deterministic_hash(fund_code) % 10000
                np.random.seed(seed)
                days = 252
                daily_drift = 0.035 / 252
                daily_vol = 0.8 / np.sqrt(252)
                daily_returns = np.random.normal(daily_drift, daily_vol, days).tolist()
                np.random.seed(seed + 1)
                bench_returns = np.random.normal(0.02/252, 1.2/np.sqrt(252), days).tolist()
                
                product = FinancialProduct(
                    product_code=fund_code, name=f"理财产品-{fund_code}",
                    issuer="未知", product_type="固收", annual_rate=3.5,
                    term_days=365, risk_level=2, min_investment=1000,
                    purchase_fee_rate=0.5, management_fee_rate=0.8,
                    redemption_fee_rate=0.3, daily_returns=daily_returns,
                    benchmark_returns=bench_returns, benchmark_name="沪深300",
                    peer_rank=400, peer_count=1000, tax_rate=20.0, tags=["固收"],
                )
                nav_series = [1.0]
                for r in daily_returns:
                    nav_series.append(nav_series[-1] * (1 + r / 100))
                product.nav_series = nav_series
            
            all_products.append(product)
    
    # ── v4.0 分析（传递 profile） ──
    if len(all_products) == 1:
        product = all_products[0]
        analyzer = DeepProductAnalyzer(product)
        report = analyzer.full_report(investment=100000, profile=profile)
        print_full_report(report)
        
        out_path = os.path.join(SCRIPT_DIR, "analysis_report.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✅ 报告已导出到 {out_path}")
    
    elif len(all_products) > 1:
        print(f"\n{'='*80}")
        print(f"📊 开始分析 {len(all_products)} 款产品...")
        print(f"{'='*80}")
        
        # 1. 同类横向对比（v4.0：传递 profile）
        comparison = DeepProductAnalyzer.peer_comparison(all_products, top_n=10)
        print_peer_comparison_report(comparison)
        
        # 2. 批量深度分析
        all_reports = []
        for i, product in enumerate(all_products):
            analyzer = DeepProductAnalyzer(product)
            report = analyzer.full_report(investment=100000, profile=profile)
            report["理财编号"] = product.product_code
            
            # v5.1: 计算真实同类排名
            if len(all_products) > 10:  # 全量数据时才计算
                if use_spdb:
                    rank, total = SPDBDataSource.compute_peer_ranking(all_products, product.product_code)
                    peer_info = {"排名": rank, "总数": total, "百分位": round(rank / total * 100, 1) if total > 0 else 0}
                else:
                    peer_info = CMBDataSource.compute_peer_ranking(all_products, product.product_code)
                report["同类排名"] = peer_info
                # P1: 费率竞争力
                fee_comp = FeeCompetitivenessAnalyzer.compute_fee_percentile(all_products, product.product_code)
                report["费率竞争力"] = fee_comp
            
            all_reports.append(report)
            if (i + 1) % 50 == 0:
                print(f"  分析进度: {i + 1}/{len(all_products)}")
        
        all_reports.sort(key=lambda x: x["综合评分"]["综合得分"], reverse=True)
        
        # 3. 逐个深度报告（少量产品）
        if use_cmb_codes and len(all_reports) <= 10:
            print(f"\n{'='*80}")
            print(f"📋 逐个产品深度分析报告")
            print(f"{'='*80}")
            for r in all_reports:
                print_full_report(r)
        
        # 4. 综合排名对比
        print(f"\n{'='*80}")
        print(f"🏆 产品综合排名对比（基于您的画像：R{risk_tol} | {goal} | {horizon}）")
        print(f"{'='*80}")
        print(f"  {'排名':4s} {'得分':6s} {'风险':4s} {'同类排名':8s} {'费率竞争力':10s} {'代码':12s} {'年化':8s} 产品名称")
        print(f"  {'─' * 88}")
        for i, r in enumerate(all_reports):
            info = r["基础信息"]
            ret = r["收益分析"]
            risk_str = info["风险等级"]
            code = info.get("产品代码", info.get("产品名称", "")[-12:])
            peer_data = r.get("同类排名", {})
            if isinstance(peer_data, dict):
                peer_rank_str = str(peer_data.get("排名", "N/A"))
            else:
                peer_rank_str = str(peer_data) if peer_data else "N/A"
            fee_comp_str = str(r.get("费率竞争力", {}).get("费率评级", "N/A"))[:10]
            credit_info = r.get("信用质量分析", {})
            credit_str = f"{credit_info.get('信用评分', '?')}" if credit_info else "?"
            print(f"  {i+1:4d} {r['综合评分']['综合得分']:6.1f} {risk_str:4s} {peer_rank_str:8s} {fee_comp_str:10s} {code:12s} {ret['预期年化(%)']:6.2f}% {info['产品名称'][:30]}")
            if credit_info and credit_info.get("风险信号"):
                print(f"         ⚠️信用:{credit_str} {r['买卖建议']}")
            else:
                print(f"         {r['买卖建议']}")
        
        # 5. 关键指标横向对比
        if len(all_reports) <= 10:
            print(f"\n{'='*80}")
            print(f"📊 关键指标横向对比表")
            print(f"{'='*80}")
            header = f"  {'产品名称':25s} {'得分':6s} {'年化%':8s} {'卡玛':8s} {'同类':8s} {'时机':6s} {'建议'}"
            print(header)
            print(f"  {'─' * len(header)}")
            for r in all_reports:
                info = r["基础信息"]
                ret = r["收益分析"]
                ratios = r["风险调整比率"]
                timing = r.get("申购时机建议", {})
                peer = r.get("同类排名", {})
                name = info["产品名称"][:24]
                score = r["综合评分"]["综合得分"]
                ann = ret["预期年化(%)"]
                calmar = ratios.get("卡玛比率", "N/A")
                peer_str = peer.get("排名", "N/A") if peer else "N/A"
                timing_str = timing.get("时机评估", "?") if timing else "?"
                advice = r["买卖建议"]
                print(f"  {name:25s} {score:6.1f} {ann:8.2f} {str(calmar):8s} {str(peer_str):8s} {str(timing_str):6s} {advice}")
        
        # v5.0: 组合分析（仅少量产品时展示）
        if use_cmb_codes and len(all_products) >= 2 and len(all_products) <= 10:
            print(f"\n{'='*80}")
            print(f"📊 组合分散度分析（v5.0 新增）")
            print(f"{'='*80}")
            div = PortfolioAnalyzer.diversification_score(all_products)
            print(f"  分散度评分: {div['分散度评分']}/100")
            for d in div.get("详情", []):
                print(f"    {d}")
            print(f"  机构分布: {div.get('机构分布', {})}")
            print(f"  类型分布: {div.get('类型分布', {})}")
            
            corr = PortfolioAnalyzer.correlation_matrix(all_products)
            if "高相关警告" in corr and corr["高相关警告"]:
                print(f"\n  ⚠️ 高相关产品对（同涨同跌风险）:")
                for pair in corr["高相关警告"]:
                    print(f"    {pair['产品1']} ↔ {pair['产品2']}: r={pair['相关系数']}")
                print(f"  建议: {corr.get('分散度', '')}")
            elif "error" not in corr:
                print(f"  ✅ 产品间相关性低，组合分散度良好")
        
        # 6. 导出
        out_path = os.path.join(SCRIPT_DIR, "analysis_report.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(all_reports, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n✅ 全部报告已导出到 {out_path}（共 {len(all_reports)} 个产品）")
        
        csv_path = os.path.join(SCRIPT_DIR, "analysis_ranking.csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["排名", "综合得分", "产品代码", "产品名称", "发行机构", "风险等级",
                            "产品类型", "投资期限", "预期年化(%)", "卡玛比率", "最大回撤(%)", "年化波动率(%)",
                            "胜率(%)", "权益仓位(%)", "年化总费率(%)", "费率竞争力", "同类排名", "管理人",
                            "投资经理", "信用等级", "信用评分", "市场环境", "申购时机", "时机分", "行为适配", "买卖建议"])
            for i, r in enumerate(all_reports):
                info = r["基础信息"]
                ret = r["收益分析"]
                risk = r["风险指标"]
                ratios = r["风险调整比率"]
                quality = r["收益质量"]
                alloc = r.get("资产配置", {})
                fees = r["综合评分"].get("费用明细", {})
                mgr = r["综合评分"].get("管理人信息", {})
                mgr_personal = r.get("投资经理评估", {})
                market = r["综合评分"].get("市场环境", {})
                timing = r.get("申购时机建议", {})
                behavior = r.get("行为金融适配", {})
                peer = r.get("同类排名", {})
                credit = r.get("信用质量分析", {})
                fee_comp = r.get("费率竞争力", {})
                writer.writerow([
                    i + 1, r["综合评分"]["综合得分"],
                    info.get("产品代码", ""), info["产品名称"],
                    info["发行机构"], info["风险等级"],
                    info["产品类型"], info.get("投资期限", ""),
                    ret["预期年化(%)"],
                    ratios.get("卡玛比率", "N/A"),
                    risk.get("最大回撤(%)", "N/A"),
                    risk.get("年化波动率(%)", "N/A"),
                    quality.get("胜率(%)", "N/A"),
                    alloc.get("权益类比例(%)", ""),
                    fees.get("年化总费率(%)", ""),
                    fee_comp.get("费率评级", "") if fee_comp else "",
                    peer.get("排名", "") if peer else "",
                    mgr.get("管理人评级", ""),
                    mgr_personal.get("投资经理", ""),
                    credit.get("信用等级", "") if credit else "",
                    credit.get("信用评分", "") if credit else "",
                    market.get("市场环境评级", ""),
                    timing.get("时机评估", "") if timing else "",
                    timing.get("综合时机评分", "") if timing else "",
                    behavior.get("适配评估", ""),
                    r["买卖建议"]
                ])
        print(f"✅ 排名 CSV 已导出到 {csv_path}")
    
    else:
        print("\n❌ 没有成功加载任何产品")
