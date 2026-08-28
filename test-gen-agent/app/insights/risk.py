# app/insights/risk.py
"""
高风险模块预警（减少背锅需求）
==============================
在回归/发布前，提前识别高风险模块，避免遗漏测试：
  - 综合代码复杂度、覆盖率缺口、缺陷密度、变更频率计算模块风险分
  - 输出高风险模块清单，建议优先回归
"""
import os
import ast
import json
import sqlite3
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 风险等级
RISK_HIGH = "high"
RISK_MEDIUM = "medium"
RISK_LOW = "low"


from app.core.database import Database


def _get_defects_conn() -> Optional[sqlite3.Connection]:
    return Database.get_conn("defects.db")


def _get_cases_conn() -> Optional[sqlite3.Connection]:
    return Database.get_conn("testcases.db")


def _complexity_metrics(source_code: str) -> Dict[str, int]:
    """估算代码复杂度：函数数、分支数（if/for/while/try）、行数。"""
    metrics = {"functions": 0, "branches": 0, "lines": 0}
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        metrics["lines"] = len(source_code.splitlines())
        return metrics
    metrics["lines"] = len(source_code.splitlines())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            metrics["functions"] += 1
        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler)):
            metrics["branches"] += 1
    return metrics


def assess_risk(
    project_path: Optional[str] = None,
    source_files: Optional[List[Dict[str, Any]]] = None,
    threshold_high: int = 60,
    threshold_medium: int = 30,
) -> Dict[str, Any]:
    """
    评估各模块风险，输出高风险清单。

    风险分 = 复杂度分(0-40) + 覆盖率缺口分(0-30) + 缺陷密度分(0-30)

    Args:
        project_path: 项目目录（配合 source_files 使用，可为空）
        source_files: 由 scan_project 返回的 files 列表（含 path/signatures）
        threshold_high / threshold_medium: 风险分阈值
    """
    if source_files is None:
        source_files = []

    defects_conn = _get_defects_conn()
    cases_conn = _get_cases_conn()

    # 收集每个文件的缺陷数
    defect_by_file: Dict[str, int] = {}
    if defects_conn:
        try:
            rows = defects_conn.execute("SELECT file_path FROM defects WHERE status != 'closed'").fetchall()
            for r in rows:
                fp = r["file_path"]
                defect_by_file[fp] = defect_by_file.get(fp, 0) + 1
        finally:
            # 不关闭共享连接：由 Database 连接池统一管理，避免破坏连接复用
            pass

    # 收集每个文件的覆盖率（从用例库 last_result）
    coverage_by_file: Dict[str, float] = {}
    if cases_conn:
        try:
            rows = cases_conn.execute("SELECT file_path, last_result FROM test_cases").fetchall()
            for r in rows:
                lr = r["last_result"]
                fp = r["file_path"]
                cov = None
                if lr:
                    try:
                        data = json.loads(lr)
                        cov = (data or {}).get("coverage") or (data or {}).get("coverage_pct")
                    except Exception:
                        cov = None
                coverage_by_file[fp] = float(cov) if cov is not None else 0.0
        finally:
            # 不关闭共享连接：由 Database 连接池统一管理，避免破坏连接复用
            pass

    assessed = []
    for f in source_files:
        path = f.get("relative_path") or f.get("path", "unknown")
        src = f.get("source_code", "")
        if not src and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    src = fh.read()
            except Exception:
                src = ""

        metrics = _complexity_metrics(src)
        # 复杂度分（0-40）：函数越多、分支越多风险越高
        complexity_score = min(40, (metrics["functions"] * 4) + (metrics["branches"] * 2))

        # 覆盖率缺口分（0-30）：覆盖率越低缺口越大
        cov = coverage_by_file.get(path, coverage_by_file.get(f.get("path"), 0))
        coverage_gap_score = 0
        if cov > 0:
            coverage_gap_score = min(30, max(0, 30 - int(cov * 0.3)))
        else:
            coverage_gap_score = 20  # 未测量，默认中高风险

        # 缺陷密度分（0-30）：未关闭缺陷越多风险越高
        defect_count = defect_by_file.get(path, defect_by_file.get(f.get("path"), 0))
        defect_score = min(30, defect_count * 10)

        risk_score = complexity_score + coverage_gap_score + defect_score
        if risk_score >= threshold_high:
            level = RISK_HIGH
        elif risk_score >= threshold_medium:
            level = RISK_MEDIUM
        else:
            level = RISK_LOW

        assessed.append({
            "file_path": path,
            "functions": metrics["functions"],
            "branches": metrics["branches"],
            "lines": metrics["lines"],
            "coverage": cov,
            "open_defects": defect_count,
            "risk_score": risk_score,
            "risk_level": level,
            "breakdown": {
                "complexity": complexity_score,
                "coverage_gap": coverage_gap_score,
                "defect_density": defect_score,
            },
        })

    # 按风险分降序
    assessed.sort(key=lambda x: x["risk_score"], reverse=True)

    high = [a for a in assessed if a["risk_level"] == RISK_HIGH]
    medium = [a for a in assessed if a["risk_level"] == RISK_MEDIUM]

    return {
        "total_modules": len(assessed),
        "high_risk": high,
        "medium_risk": medium,
        "low_risk": [a for a in assessed if a["risk_level"] == RISK_LOW],
        "recommendation": (
            "发布前请优先回归以上高风险模块，并补齐覆盖率缺口。"
            if high else "暂未发现高风险模块，建议保持常规回归节奏。"
        ),
    }
