"""
行业配置穿透分析
基金行业分类、行业集中度、行业周期偏好。
"""

from common.logging_utils import get_logger

logger = get_logger(__name__)

# 常见行业关键词映射（名称 → 行业）
INDUSTRY_KEYWORDS = {
    "消费": ["消费", "食品", "饮料", "白酒", "家电", "零售", "免税", "旅游", "农牧", "养殖", "农业"],
    "医药": ["医药", "医疗", "生物", "健康", "创新药", "中药", "疫苗", "养老"],
    "科技": ["科技", "电子", "半导体", "芯片", "计算机", "软件", "人工智能", "大数据", "5G", "信息", "互联网", "通信", "数字"],
    "新能源": ["新能源", "光伏", "锂电", "电池", "储能", "风电", "碳中和", "清洁能源", "汽车"],
    "金融": ["银行", "证券", "保险", "金融", "非银"],
    "地产": ["地产", "房地产", "基建", "建筑", "建材"],
    "制造": ["制造", "军工", "高端装备", "机械", "工业", "汽车"],
    "周期": ["有色", "钢铁", "煤炭", "化工", "资源", "稀土", "石油", "矿业"],
    "公用事业": ["公用", "电力", "环保", "燃气", "水务"],
}


def classify_fund_industry(fund_name: str, fund_type: str) -> dict:
    """根据基金名称与类型分类到行业，返回 {industry, confidence}。"""
    name = fund_name or ""
    for industry, kws in INDUSTRY_KEYWORDS.items():
        for kw in kws:
            if kw in name:
                return {"industry": industry, "confidence": 0.8}
    return {"industry": "其他", "confidence": 0.3}


def calc_industry_concentration(industries: dict) -> float:
    """计算行业集中度（0-1），输入 {industry: weight}。"""
    if not industries:
        return 0.0
    total = sum(industries.values())
    if total <= 0:
        return 0.0
    # 用 HHI 简化衡量集中度
    hhi = sum((w / total) ** 2 for w in industries.values())
    logger.debug("行业集中度 HHI=%.4f（%d 个行业）", hhi, len(industries))
    return round(float(hhi), 4)


def classify_fund_asset_type(fund_name: str, fund_type: str) -> str:
    """判断基金资产类型（股票/债券/混合/货币/QDII等）。"""
    name = (fund_name or "") + (fund_type or "")
    if any(k in name for k in ["货币", "现金", "理财"]):
        return "货币"
    if any(k in name for k in ["债", "纯债", "利率", "信用债"]):
        return "债券"
    if any(k in name for k in ["混合", "灵活配置", "平衡"]):
        return "混合"
    if any(k in name for k in ["QDII", "美股", "港股", "海外"]):
        return "QDII"
    if any(k in name for k in ["ETF", "指数", "LOF"]):
        return "指数"
    return "股票"


def classify_fund_type_label(fund_name: str, fund_type_raw: str) -> str:
    """返回标准化的基金类型标签。"""
    name = fund_name or ""
    if "货币" in name:
        return "货币型"
    if "债券" in name or "债" in name:
        return "债券型"
    if "指数" in name or "ETF" in name.upper():
        return "指数型"
    if "混合" in name:
        return "混合型"
    if "股票" in name or "QDII" in name.upper():
        return "股票型"
    return fund_type_raw or "未知"
