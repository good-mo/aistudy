# app/insights/trace.py
"""
测试执行追溯（减少背锅需求）
============================
当线上出问题被问"为什么没测出来"时，帮助测试人员证明"当时测了"：
  - 记录每次测试执行的完整审计信息（时间、环境、被测版本、结果、异常归因）
  - 可追溯"当时测过、当时通过"，并定位是需求变更/环境异常/数据问题导致
"""
import os
import json
import sqlite3
import time
import uuid
import platform
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 统一使用 Database 连接池管理
from app.core.database import Database

# 执行归因：帮助定位"为什么线上出问题"
ATTRIBUTION_REQUIREMENT_CHANGE = "requirement_change"  # 需求变更
ATTRIBUTION_ENV_ANOMALY = "environment_anomaly"        # 环境异常
ATTRIBUTION_DATA_ISSUE = "data_issue"                  # 数据问题
ATTRIBUTION_CODE_REGRESSION = "code_regression"        # 代码回归（新缺陷）
ATTRIBUTION_COVERAGE_GAP = "coverage_gap"              # 覆盖遗漏

ATTRIBUTIONS = {
    ATTRIBUTION_REQUIREMENT_CHANGE: "需求变更",
    ATTRIBUTION_ENV_ANOMALY: "环境异常",
    ATTRIBUTION_DATA_ISSUE: "数据问题",
    ATTRIBUTION_CODE_REGRESSION: "代码回归",
    ATTRIBUTION_COVERAGE_GAP: "覆盖遗漏",
}


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("trace.db")


def _init_db() -> None:
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_runs (
                id TEXT PRIMARY KEY,
                file_path TEXT NOT NULL,
                source_hash TEXT DEFAULT '',
                result TEXT DEFAULT 'unknown',      -- passed / failed / error
                passed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                coverage REAL DEFAULT 0,
                env_info TEXT DEFAULT '{}',          -- 运行环境 JSON
                attribution TEXT DEFAULT '',
                note TEXT DEFAULT '',
                created_at REAL,
                created_by TEXT DEFAULT ''
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_file ON test_runs(file_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_time ON test_runs(created_at)")
        conn.commit()
    finally:
        pass  # shared cached conn


_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def _json_dumps(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "{}"


def capture_env() -> Dict[str, str]:
    """采集当前运行环境快照，用于证明"当时就是这个环境"。"""
    try:
        return {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        }
    except Exception as e:
        logger.warning("采集环境失败: %s", e)
        return {}


def record_run(
    file_path: str,
    result: str,
    passed_count: int = 0,
    failed_count: int = 0,
    error_count: int = 0,
    coverage: float = 0.0,
    source_hash: str = "",
    attribution: str = "",
    note: str = "",
    created_by: str = "",
) -> Dict[str, Any]:
    """
    记录一次测试执行，形成可追溯的审计证据。

    attribution 取值见 ATTRIBUTIONS，用于回答"为什么当时没测出来"。
    """
    run_id = uuid.uuid4().hex[:12]
    env_info = capture_env()
    conn = _get_conn()
    try:
        conn.execute("""
            INSERT INTO test_runs
            (id, file_path, source_hash, result, passed_count, failed_count, error_count,
             coverage, env_info, attribution, note, created_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, file_path, source_hash, result, passed_count, failed_count, error_count,
            coverage, _json_dumps(env_info), attribution, note, time.time(), created_by,
        ))
        conn.commit()
    finally:
        pass  # shared cached conn

    logger.info("测试执行已追溯 [id=%s, file=%s, result=%s]", run_id, file_path, result)
    return {
        "id": run_id,
        "file_path": file_path,
        "result": result,
        "coverage": coverage,
        "attribution": attribution,
        "created_at": time.time(),
    }


def list_runs(
    file_path: Optional[str] = None,
    result: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """列出执行追溯记录，可按文件/结果过滤。"""
    sql = "SELECT * FROM test_runs WHERE 1=1"
    params: list = []
    if file_path:
        sql += " AND file_path LIKE ?"
        params.append(f"%{file_path}%")
    if result:
        sql += " AND result = ?"
        params.append(result)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    conn = _get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM test_runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        pass  # shared cached conn


def prove_coverage(file_path: str) -> Dict[str, Any]:
    """
    "自证清白"核心能力：针对某个文件，调出全部历史执行记录，
    证明"该测的都测了、当时测了且通过"。

    Returns:
        {
          "file_path": ...,
          "total_runs": ...,
          "last_run": {...},
          "has_passed_evidence": bool,
          "runs": [...]
        }
    """
    runs = list_runs(file_path=file_path, limit=100)
    last_run = runs[0] if runs else None
    has_passed_evidence = any(r["result"] == "passed" for r in runs)
    return {
        "file_path": file_path,
        "total_runs": len(runs),
        "last_run": last_run,
        "has_passed_evidence": has_passed_evidence,
        "coverage_snapshot": last_run.get("coverage", 0) if last_run else 0,
        "runs": runs,
    }


def stats() -> Dict[str, Any]:
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM test_runs").fetchone()["c"]
        passed = conn.execute("SELECT COUNT(*) AS c FROM test_runs WHERE result='passed'").fetchone()["c"]
        failed = conn.execute("SELECT COUNT(*) AS c FROM test_runs WHERE result='failed'").fetchone()["c"]
        files = conn.execute("SELECT COUNT(DISTINCT file_path) AS c FROM test_runs").fetchone()["c"]
        avg_cov = conn.execute("SELECT AVG(coverage) AS c FROM test_runs WHERE coverage > 0").fetchone()["c"]
        return {
            "total_runs": total,
            "passed": passed,
            "failed": failed,
            "covered_files": files,
            "avg_coverage": round(avg_cov or 0, 1),
        }
    finally:
        pass  # shared cached conn
