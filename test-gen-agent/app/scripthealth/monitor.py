"""
稳定定位策略 + 自动修复 + 脚本健康度监控模块
=====================================
提供：
  - 稳定定位策略：data-testid 推荐 / CSS 选择器质量评估 / XPath 稳定性评分
  - 自动修复：元素定位失败时自动尝试替代策略
  - 脚本健康度监控：执行历史记录、失败率统计、健康度评分、波动预警
"""
import json
import os
import re
import sqlite3
import time
import uuid
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 统一使用 Database 连接池管理
from app.core.database import Database

# 定位策略类型
LOCATOR_CSS = "css"
LOCATOR_XPATH = "xpath"
LOCATOR_TESTID = "data-testid"
LOCATOR_TEXT = "text"
LOCATOR_NAME = "name"
LOCATOR_ID = "id"

VALID_LOCATOR_TYPES = {LOCATOR_CSS, LOCATOR_XPATH, LOCATOR_TESTID, LOCATOR_TEXT, LOCATOR_NAME, LOCATOR_ID}



def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("scripthealth.db")


def _init_db() -> None:
    """初始化表结构（使用独立临时连接）。"""
    conn = _get_conn()
    try:
        # 脚本注册表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scripts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                file_path TEXT DEFAULT '',
                framework TEXT DEFAULT 'pytest',
                description TEXT DEFAULT '',
                locators_json TEXT DEFAULT '[]',
                total_runs INTEGER DEFAULT 0,
                success_runs INTEGER DEFAULT 0,
                fail_runs INTEGER DEFAULT 0,
                last_run_at REAL,
                last_status TEXT DEFAULT '',
                health_score REAL DEFAULT 100.0,
                status TEXT DEFAULT 'healthy',
                created_at REAL,
                updated_at REAL
            )
        """)
        # 定位器库
        conn.execute("""
            CREATE TABLE IF NOT EXISTS locators (
                id TEXT PRIMARY KEY,
                script_id TEXT DEFAULT '',
                name TEXT NOT NULL,
                element_type TEXT DEFAULT '',
                current_strategy TEXT DEFAULT 'css',
                current_selector TEXT DEFAULT '',
                alternatives_json TEXT DEFAULT '[]',
                best_strategy TEXT DEFAULT 'css',
                best_selector TEXT DEFAULT '',
                last_success_at REAL,
                last_fail_at REAL,
                fail_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                stability_score REAL DEFAULT 100.0,
                status TEXT DEFAULT 'stable',
                created_at REAL,
                updated_at REAL
            )
        """)
        # 执行历史
        conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_history (
                id TEXT PRIMARY KEY,
                script_id TEXT DEFAULT '',
                script_name TEXT DEFAULT '',
                success INTEGER DEFAULT 0,
                duration REAL DEFAULT 0,
                error_type TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                locator_failures_json TEXT DEFAULT '[]',
                created_at REAL
            )
        """)
        conn.commit()
    finally:
        pass  # shared cached conn


_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    for k in ("locators_json", "alternatives_json", "locator_failures_json"):
        if data.get(k):
            try:
                data[k.replace("_json", "")] = json.loads(data[k])
                data.pop(k, None)
            except (json.JSONDecodeError, TypeError):
                pass
    if "locators_json" in data:
        data["locators"] = data.pop("locators_json")
    return data


# ═══════════════════════════════════════════════════════════
# 稳定定位策略
# ═══════════════════════════════════════════════════════════

def evaluate_selector(strategy: str, selector: str) -> Dict[str, Any]:
    """
    评估定位器的稳定性。
    返回稳定性评分 0-100，以及建议。
    """
    score = 100.0
    suggestions = []

    if strategy == LOCATOR_TESTID:
        # data-testid 是最稳定的
        if len(selector) < 3:
            score -= 10
            suggestions.append("data-testid 名称过短，建议使用有意义的命名")
        elif not re.match(r'^[a-zA-Z0-9_-]+$', selector):
            score -= 15
            suggestions.append("data-testid 应使用字母/数字/下划线/中划线")
        return {"score": score, "strategy": strategy, "suggestions": suggestions,
                "verdict": "stable" if score >= 80 else "needs_attention"}

    elif strategy == LOCATOR_CSS:
        # CSS 选择器评估
        if selector.startswith("div") or selector.startswith("span"):
            score -= 10
            suggestions.append("使用通用标签选择器，建议添加 class 或 id")
        if "> " in selector or " > " in selector:
            score -= 5
            suggestions.append("深层嵌套选择器可能脆弱，建议减少层级")
        if selector.startswith("#"):
            score += 5  # ID 选择器较稳定
        if "nth-child" in selector or "nth-of-type" in selector:
            score -= 30
            suggestions.append("nth-child/nth-of-type 是脆弱定位器，页面元素变化会导致失败")
        if "[" in selector and "data-testid" in selector:
            score += 20
            suggestions.append("使用 data-testid 属性，稳定性高")
        if "class" in selector or "." in selector:
            score += 5
        if score > 100:
            score = 100
        if score < 50:
            suggestions.append("建议改用 data-testid 属性定位")

    elif strategy == LOCATOR_XPATH:
        # XPath 评估
        if "//" in selector and "text()" in selector:
            score -= 15
            suggestions.append("文本匹配 XPath 脆弱，建议改用 data-testid")
        if "position()" in selector or "[1]" in selector:
            score -= 20
            suggestions.append("使用 position() 或 [1] 的 XPath 脆弱，页面变化会导致失败")
        if "contains(" in selector:
            score -= 10
            suggestions.append("contains() 匹配可能不稳定，建议使用精确属性")
        if "@data-testid" in selector:
            score += 20
            suggestions.append("使用 data-testid 属性，稳定性高")

    elif strategy == LOCATOR_TEXT:
        score = 40
        suggestions.append("文本定位最脆弱，页面文案改变即失败")
        suggestions.append("建议改用 data-testid 或稳定的 CSS 选择器")

    elif strategy == LOCATOR_NAME:
        score = 70
        suggestions.append("name 属性定位较稳定，但可能与业务数据冲突")
    elif strategy == LOCATOR_ID:
        score = 85
        if re.match(r'^[0-9]', selector):
            score -= 15
            suggestions.append("ID 以数字开头，可能存在动态生成风险")

    if score > 100:
        score = 100.0

    verdict = "stable" if score >= 80 else ("needs_attention" if score >= 50 else "unstable")
    return {"score": score, "strategy": strategy, "suggestions": suggestions, "verdict": verdict}


def recommend_stable_strategy(selector: str, strategy: str = LOCATOR_CSS) -> Dict[str, Any]:
    """
    为给定选择器推荐稳定的定位策略。
    返回推荐的替代策略。
    """
    evaluation = evaluate_selector(strategy, selector)
    if evaluation["score"] >= 80:
        return {
            "current_strategy": strategy,
            "current_selector": selector,
            "recommendation": "当前定位器稳定，无需修改",
            "alternatives": [],
            "score": evaluation["score"],
        }

    alternatives = []
    # 根据当前策略推荐替代方案
    if strategy == LOCATOR_XPATH:
        # 尝试从 XPath 中提取 data-testid
        testid_match = re.search(r'@data-testid=["\']([^"\']+)["\']', selector)
        if testid_match:
            alternatives.append({
                "strategy": LOCATOR_TESTID,
                "selector": testid_match.group(1),
                "reason": "从 XPath 中提取了 data-testid，稳定性更高",
            })
        alternatives.append({
            "strategy": LOCATOR_CSS,
            "selector": "添加 data-testid 属性后用 CSS 定位",
            "reason": "建议在 HTML 元素上添加 data-testid 属性",
        })
    elif strategy == LOCATOR_CSS:
        alternatives.append({
            "strategy": LOCATOR_TESTID,
            "selector": "使用 data-testid",
            "reason": "data-testid 是业界最佳实践，不受 UI 样式变化影响",
        })
    elif strategy == LOCATOR_TEXT:
        alternatives.append({
            "strategy": LOCATOR_CSS,
            "selector": "为元素添加 class 或 data-testid",
            "reason": "文本定位脆弱，应使用稳定的属性定位",
        })
        alternatives.append({
            "strategy": LOCATOR_TESTID,
            "selector": "使用 data-testid",
            "reason": "data-testid 是最稳定的定位方式",
        })

    return {
        "current_strategy": strategy,
        "current_selector": selector,
        "recommendation": f"当前定位器稳定性评分 {evaluation['score']}，建议优化",
        "alternatives": alternatives,
        "score": evaluation["score"],
    }


# ═══════════════════════════════════════════════════════════
# 脚本管理
# ═══════════════════════════════════════════════════════════

def register_script(
    name: str,
    file_path: str = "",
    framework: str = "pytest",
    description: str = "",
    locators: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """注册测试脚本。"""
    script_id = uuid.uuid4().hex[:12]
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO scripts
               (id, name, file_path, framework, description, locators_json,
                total_runs, success_runs, fail_runs, status,
                health_score, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 'healthy', 100.0, ?, ?)""",
            (script_id, name, file_path, framework, description,
             json.dumps(locators or []), now, now),
        )
        conn.commit()
        logger.info("脚本已注册 [id=%s, name=%s]", script_id, name)
        return get_script(script_id) or {"id": script_id}
    finally:
        pass  # shared cached conn


def get_script(script_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM scripts WHERE id = ?", (script_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        pass  # shared cached conn


def list_scripts(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        query = "SELECT * FROM scripts WHERE 1=1"
        params: List = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if search:
            query += " AND (name LIKE ? OR file_path LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def update_script(script_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    existing = get_script(script_id)
    if not existing:
        return None

    allowed = {"name", "file_path", "framework", "description", "locators",
               "total_runs", "success_runs", "fail_runs", "last_run_at",
               "last_status", "health_score", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}

    if "locators" in updates and isinstance(updates["locators"], list):
        updates["locators_json"] = json.dumps(updates["locators"])
        del updates["locators"]

    if not updates:
        return existing

    updates["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [script_id]

    conn = _get_conn()
    try:
        conn.execute(f"UPDATE scripts SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return get_script(script_id)
    finally:
        pass  # shared cached conn


def delete_script(script_id: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM scripts WHERE id = ?", (script_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ═══════════════════════════════════════════════════════════
# 自动修复
# ═══════════════════════════════════════════════════════════

def auto_repair_locator(script_id: str, locator_name: str) -> Dict[str, Any]:
    """
    自动修复失效的定位器。
    分析失败原因，从替代策略中选取最优方案并更新。
    """
    script = get_script(script_id)
    if not script:
        return {"success": False, "error": f"脚本 {script_id} 不存在"}

    locators = script.get("locators", [])
    target = None
    for loc in locators:
        if loc.get("name") == locator_name:
            target = loc
            break

    if not target:
        return {"success": False, "error": f"定位器 {locator_name} 不存在"}

    # 获取替代策略
    alternatives = target.get("alternatives", [])
    if not alternatives:
        # 自动生成替代方案
        recommendation = recommend_stable_strategy(
            target.get("current_selector", ""),
            target.get("current_strategy", LOCATOR_CSS),
        )
        alternatives = recommendation.get("alternatives", [])

    if not alternatives:
        return {
            "success": False,
            "error": "无法自动修复，需要手动更新定位器",
            "suggestion": "建议在页面元素上添加 data-testid 属性",
        }

    # 选择最优替代方案（优先 data-testid）
    best = None
    for alt in alternatives:
        if alt["strategy"] == LOCATOR_TESTID:
            best = alt
            break
    if not best and alternatives:
        best = alternatives[0]

    # 更新定位器
    target["current_strategy"] = best["strategy"]
    target["current_selector"] = best["selector"]
    target["best_strategy"] = best["strategy"]
    target["best_selector"] = best["selector"]
    target["status"] = "repaired"
    target["updated_at"] = time.time()

    # 更新脚本中的定位器
    for i, loc in enumerate(locators):
        if loc.get("name") == locator_name:
            locators[i] = target
            break

    update_script(script_id, locators=locators)

    logger.info("定位器已自动修复 [script=%s, locator=%s, new=%s:%s]",
                script_id, locator_name, best["strategy"], best["selector"])

    return {
        "success": True,
        "locator": locator_name,
        "old_strategy": target.get("current_strategy", ""),
        "new_strategy": best["strategy"],
        "new_selector": best["selector"],
        "message": f"已自动修复定位器，改用 {best['strategy']} 策略",
    }


# ═══════════════════════════════════════════════════════════
# 执行记录与健康度监控
# ═══════════════════════════════════════════════════════════

def record_execution(
    script_id: str,
    success: bool,
    duration: float = 0,
    error_type: str = "",
    error_message: str = "",
    locator_failures: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """记录一次脚本执行，并自动更新健康度评分。"""
    script = get_script(script_id)
    if not script:
        return {"success": False, "error": f"脚本 {script_id} 不存在"}

    now = time.time()
    hist_id = uuid.uuid4().hex[:12]

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO execution_history
               (id, script_id, script_name, success, duration,
                error_type, error_message, locator_failures_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (hist_id, script_id, script.get("name", ""),
             1 if success else 0, duration,
             error_type, error_message,
             json.dumps(locator_failures or []), now),
        )
        conn.commit()
    finally:
        pass  # shared cached conn

    # 更新脚本统计
    total = script.get("total_runs", 0) + 1
    success_count = script.get("success_runs", 0) + (1 if success else 0)
    fail_count = script.get("fail_runs", 0) + (0 if success else 1)

    # 计算健康度评分
    health_score = _calculate_health_score(
        total, success_count, fail_count, script.get("health_score", 100.0), success
    )
    status = _determine_status(health_score)

    update_script(
        script_id,
        total_runs=total,
        success_runs=success_count,
        fail_runs=fail_count,
        last_run_at=now,
        last_status="success" if success else "failed",
        health_score=health_score,
        status=status,
    )

    # 如果有定位器失败，触发自动修复
    repair_results = []
    if locator_failures:
        for failure in locator_failures:
            repair = auto_repair_locator(script_id, failure.get("name", ""))
            if repair.get("success"):
                repair_results.append(repair)

    return {
        "success": True,
        "history_id": hist_id,
        "health_score": health_score,
        "status": status,
        "auto_repairs": repair_results,
    }


def _calculate_health_score(total: int, success_count: int, fail_count: int,
                            previous_score: float, last_success: bool) -> float:
    """计算健康度评分（0-100）。"""
    # 基础：成功率
    success_rate = success_count / total if total > 0 else 1.0
    base_score = success_rate * 100.0

    # 惩罚因子
    penalty = 0.0
    if not last_success:
        penalty += 10.0
    if fail_count >= 3:
        penalty += 5.0 * min(fail_count, 10)

    score = max(0, min(100, base_score - penalty))

    # 平滑处理：新分数 = 旧分数 * 0.7 + 新分数 * 0.3
    smoothed = previous_score * 0.7 + score * 0.3
    return round(max(0, min(100, smoothed)), 1)


def _determine_status(health_score: float) -> str:
    if health_score >= 85:
        return "healthy"
    elif health_score >= 60:
        return "unstable"
    return "degraded"


def list_executions(
    script_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        query = "SELECT * FROM execution_history WHERE 1=1"
        params: List = []
        if script_id:
            query += " AND script_id = ?"
            params.append(script_id)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("locator_failures_json"):
                try:
                    d["locator_failures"] = json.loads(d["locator_failures_json"])
                except (json.JSONDecodeError, TypeError):
                    d["locator_failures"] = []
            d.pop("locator_failures_json", None)
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def get_stats() -> Dict[str, Any]:
    """获取脚本健康度整体统计。"""
    conn = _get_conn()
    try:
        script_total = conn.execute("SELECT COUNT(*) FROM scripts").fetchone()[0]
        # 一次 GROUP BY 查询代替逐状态 COUNT（消除 N+1）
        by_status = {s: 0 for s in ("healthy", "unstable", "degraded")}
        for row in conn.execute(
            "SELECT status, COUNT(*) AS cnt FROM scripts GROUP BY status"
        ):
            if row["status"] in by_status:
                by_status[row["status"]] = row["cnt"]

        exec_total = conn.execute("SELECT COUNT(*) FROM execution_history").fetchone()[0]
        exec_success = conn.execute(
            "SELECT COUNT(*) FROM execution_history WHERE success = 1"
        ).fetchone()[0]
        exec_fail = exec_total - exec_success

        avg_health = conn.execute(
            "SELECT AVG(health_score) FROM scripts"
        ).fetchone()[0] or 0

        recent_failures = conn.execute(
            "SELECT COUNT(*) FROM execution_history WHERE success = 0 AND created_at > ?",
            (time.time() - 24 * 3600,),
        ).fetchone()[0]

        return {
            "script_total": script_total,
            "script_by_status": by_status,
            "exec_total": exec_total,
            "exec_success": exec_success,
            "exec_fail": exec_fail,
            "avg_health_score": round(float(avg_health), 1),
            "recent_24h_failures": recent_failures,
        }
    finally:
        pass  # shared cached conn
