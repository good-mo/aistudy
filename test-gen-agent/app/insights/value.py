# app/insights/value.py
"""
测试价值量化（被认可需求）
==========================
帮助一线测试人员量化工作价值，回答"测试的价值在哪里"：
  - 发现了多少个严重缺陷（避免了多少线上事故）
  - 测试覆盖率可视化，证明"该测的都测了"
  - 缺陷价值 / 覆盖价值 / 风险避免估算
"""
import os
import sqlite3
import json
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 缺陷严重程度对应的"避免线上事故"价值权重（可配置）
SEVERITY_WEIGHT = {
    "blocker": 100.0,   # 阻塞级：避免重大线上事故
    "critical": 50.0,   # 严重：高危故障
    "major": 10.0,      # 中等：功能缺陷
    "minor": 1.0,       # 轻微：体验问题
}

# 单次覆盖避免回归的平均价值（估算基准，可按团队成本调整）
COVERAGE_POINT_VALUE = 0.5


from app.core.database import Database


def _connect(db_path: str):
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn(db_path)


def get_defects_db_path() -> str:
    """定位缺陷库路径。"""
    return "defects.db"


def get_cases_db_path() -> str:
    """定位用例库路径。"""
    return "testcases.db"


def summarize_value(severity_weight: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    汇总测试价值量化指标。

    Returns:
        {
          "defect_value": 发现缺陷的总价值（权重和）
          "defect_count": 缺陷总数
          "severity_breakdown": 按严重度分布
          "avoided_incidents": 估算避免的线上事故数（blocker+critical）
          "coverage_summary": 覆盖率汇总（基于用例库 last_result）
          "value_score": 综合价值分（0-100）
        }
    """
    weight = severity_weight or SEVERITY_WEIGHT

    # 1. 缺陷价值
    defect_value = 0.0
    avoided_incidents = 0
    severity_breakdown = {"blocker": 0, "critical": 0, "major": 0, "minor": 0}
    defect_count = 0
    db_path = get_defects_db_path()
    if os.path.exists(db_path):
        conn = _connect(db_path)
        try:
            rows = conn.execute("SELECT severity, status FROM defects").fetchall()
            for r in rows:
                sev = r["severity"]
                defect_count += 1
                severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1
                defect_value += weight.get(sev, 0)
                if sev in ("blocker", "critical"):
                    # 已关闭/已修复的严重缺陷，视为避免了一次线上事故
                    avoided_incidents += 1
        finally:
            # 不关闭共享连接：由 Database 连接池统一管理，避免破坏连接复用
            pass

    # 2. 覆盖率汇总（从用例库 last_result 聚合）
    coverage_summary = {"measured_files": 0, "avg_coverage": 0.0, "covered": 0, "missed": 0}
    cases_db = get_cases_db_path()
    if os.path.exists(cases_db):
        conn = _connect(cases_db)
        try:
            rows = conn.execute("SELECT last_result FROM test_cases").fetchall()
            cov_values = []
            for r in rows:
                lr = r["last_result"]
                if not lr:
                    continue
                try:
                    data = json.loads(lr)
                except Exception:
                    continue
                cov = (data or {}).get("coverage") or (data or {}).get("coverage_pct")
                if cov is not None:
                    coverage_summary["measured_files"] += 1
                    cov_values.append(float(cov))
            if cov_values:
                coverage_summary["avg_coverage"] = round(sum(cov_values) / len(cov_values), 1)
                coverage_summary["covered"] = len([c for c in cov_values if c >= 80])
                coverage_summary["missed"] = len([c for c in cov_values if c < 80])
        finally:
            # 不关闭共享连接：由 Database 连接池统一管理，避免破坏连接复用
            pass

    # 3. 综合价值分（0-100）
    defect_score = min(defect_value, 50.0) * 2  # 缺陷价值最大贡献 50 分
    coverage_score = min(coverage_summary["avg_coverage"], 100.0) * 0.5  # 覆盖率最大贡献 50 分
    value_score = round(min(defect_score + coverage_score, 100.0), 1)

    return {
        "defect_value": round(defect_value, 1),
        "defect_count": defect_count,
        "severity_breakdown": severity_breakdown,
        "avoided_incidents": avoided_incidents,
        "coverage_summary": coverage_summary,
        "value_score": value_score,
        "metric_desc": "价值分 = 缺陷严重度权重分 + 平均覆盖率折算分（各占 50 分上限）",
    }


def estimate_incident_avoidance(severity_weight: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    估算测试人员"避免的线上事故"价值。

    以缺陷严重度作为代理指标，把已修复的 blocker/critical 缺陷折算为
    "避免的线上事故"。可作为团队/个人价值展示。
    """
    weight = severity_weight or SEVERITY_WEIGHT
    db_path = get_defects_db_path()
    fixed_defects = []
    if os.path.exists(db_path):
        conn = _connect(db_path)
        try:
            rows = conn.execute(
                "SELECT id, title, severity, status, file_path FROM defects"
            ).fetchall()
            for r in rows:
                if r["status"] in ("fixed", "closed"):
                    fixed_defects.append({
                        "id": r["id"],
                        "title": r["title"],
                        "severity": r["severity"],
                        "file_path": r["file_path"],
                        "weight": weight.get(r["severity"], 0),
                    })
        finally:
            # 不关闭共享连接：由 Database 连接池统一管理，避免破坏连接复用
            pass

    total_weight = sum(d["weight"] for d in fixed_defects)
    high_impact = [d for d in fixed_defects if d["severity"] in ("blocker", "critical")]
    return {
        "fixed_defect_count": len(fixed_defects),
        "high_impact_fixed": len(high_impact),
        "avoided_incident_estimate": len(high_impact),
        "total_value_weight": round(total_weight, 1),
        "detail": fixed_defects[:50],
    }
