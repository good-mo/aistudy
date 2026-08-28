"""
运行记录持久化模块
==================
保存每次测试运行的所有完整记录，支持：
  - 单文件生成 / 项目批量生成 / WebSocket 流式生成 / 后台任务队列
  - 完整快照：源代码、生成测试、测试结果、覆盖率、性能、重试次数、产物路径
  - 查询：按时间/文件路径/结果筛选，分页浏览
  - 追溯：为"为什么没测出来 / 为什么失败"提供完整审计证据

存储：SQLite（runs.db）
"""
import json
import os
import sqlite3
import time
import uuid
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 运行来源类型
SOURCE_SINGLE = "single"      # 单文件生成
SOURCE_PROJECT = "project"    # 项目批量生成
SOURCE_WS = "websocket"       # WebSocket 流式生成
SOURCE_TASK = "task"          # 后台任务队列

VALID_SOURCES = {SOURCE_SINGLE, SOURCE_PROJECT, SOURCE_WS, SOURCE_TASK}

# 统一使用 Database 连接池管理
from app.core.database import Database



def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("runs.db")


def _init_db() -> None:
    """初始化运行记录表结构（使用独立临时连接）。"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS run_records (
                id TEXT PRIMARY KEY,
                source TEXT DEFAULT 'single',
                file_path TEXT DEFAULT '',
                source_code TEXT DEFAULT '',
                generated_tests TEXT DEFAULT '',
                test_result TEXT DEFAULT '{}',
                coverage_report TEXT DEFAULT '{}',
                performance_report TEXT DEFAULT '{}',
                retry_count INTEGER DEFAULT 0,
                passed INTEGER DEFAULT 0,
                saved_to TEXT DEFAULT '',
                error TEXT DEFAULT '',
                created_at REAL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_run_records_created ON run_records(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_run_records_file ON run_records(file_path)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_run_records_passed ON run_records(passed)
        """)
        conn.commit()
    finally:
        pass  # shared cached conn


_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """将数据库行转为 dict（JSON 字段反序列化）。"""
    data = dict(row)
    for field in ("test_result", "coverage_report", "performance_report", "metadata"):
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except (json.JSONDecodeError, TypeError):
                pass  # 保留原始字符串
    return data


def save_run_record(
    file_path: str = "",
    source_code: str = "",
    generated_tests: str = "",
    test_result: Optional[Dict[str, Any]] = None,
    coverage_report: Optional[Dict[str, Any]] = None,
    performance_report: Optional[Dict[str, Any]] = None,
    retry_count: int = 0,
    saved_to: str = "",
    error: str = "",
    source: str = SOURCE_SINGLE,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    保存一次运行的所有记录。
    任何一次测试生成/执行都会调用本函数，落盘完整快照。
    """
    if source not in VALID_SOURCES:
        source = SOURCE_SINGLE

    test_result = test_result or {}
    coverage_report = coverage_report or {}
    performance_report = performance_report or {}
    metadata = metadata or {}

    record_id = uuid.uuid4().hex[:16]
    now = time.time()
    passed = int(bool(test_result.get("passed", False)))

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO run_records
               (id, source, file_path, source_code, generated_tests,
                test_result, coverage_report, performance_report,
                retry_count, passed, saved_to, error, created_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record_id, source, file_path, source_code, generated_tests,
                json.dumps(test_result, ensure_ascii=False),
                json.dumps(coverage_report, ensure_ascii=False),
                json.dumps(performance_report, ensure_ascii=False),
                retry_count, passed, saved_to, error, now,
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        conn.commit()
        logger.info(
            "运行记录已保存 [id=%s, file=%s, passed=%s]",
            record_id, file_path, passed,
        )
        return get_run_record(record_id)
    except Exception as e:
        logger.error("运行记录保存失败 [err=%s]", e, exc_info=True)
        return None
    finally:
        pass  # shared cached conn


def get_run_record(record_id: str) -> Optional[Dict[str, Any]]:
    """按 ID 获取一条运行记录。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM run_records WHERE id = ?", (record_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        pass  # shared cached conn


def list_run_records(
    file_path: Optional[str] = None,
    source: Optional[str] = None,
    passed: Optional[bool] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """列出运行记录，支持按文件路径/来源/结果过滤与分页。"""
    conn = _get_conn()
    try:
        query = "SELECT * FROM run_records WHERE 1=1"
        params: List = []

        if file_path:
            query += " AND file_path LIKE ?"
            params.append(f"%{file_path}%")
        if source and source in VALID_SOURCES:
            query += " AND source = ?"
            params.append(source)
        if passed is not None:
            query += " AND passed = ?"
            params.append(int(passed))
        if search:
            query += " AND (file_path LIKE ? OR error LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def get_run_stats() -> Dict[str, Any]:
    """获取运行记录统计。"""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM run_records").fetchone()[0]
        passed = conn.execute(
            "SELECT COUNT(*) FROM run_records WHERE passed = 1"
        ).fetchone()[0]
        failed = total - passed
        # 一次 GROUP BY 查询代替逐来源 COUNT（消除 N+1）
        by_source = {s: 0 for s in VALID_SOURCES}
        for row in conn.execute(
            "SELECT source, COUNT(*) AS cnt FROM run_records GROUP BY source"
        ):
            if row["source"] in by_source:
                by_source[row["source"]] = row["cnt"]
        # 平均覆盖率：用 Python 侧解析 coverage_report 字段
        # 只在 Python 中逐条解析 JSON（无法用 SQL 计算，但减少重复查询）
        rows = conn.execute(
            "SELECT coverage_report FROM run_records WHERE coverage_report IS NOT NULL AND coverage_report != '' AND coverage_report != '{}'"
        ).fetchall()
        coverage_sum, coverage_cnt = 0.0, 0
        for r in rows:
            try:
                cov = json.loads(r["coverage_report"])
                pct = cov.get("coverage_pct")
                if pct is not None:
                    coverage_sum += float(pct)
                    coverage_cnt += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        avg_coverage = round(coverage_sum / coverage_cnt, 2) if coverage_cnt else 0.0
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "by_source": by_source,
            "avg_coverage": avg_coverage,
        }
    finally:
        pass  # shared cached conn


def clear_run_records() -> int:
    """清空全部运行记录（谨慎使用）。返回删除条数。"""
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM run_records")
        conn.commit()
        deleted = cur.rowcount
        if deleted:
            logger.info("运行记录已清空 [count=%s]", deleted)
        return deleted
    finally:
        pass  # shared cached conn
