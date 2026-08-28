"""
测试用例高级管理模块
====================
在基础用例库之上提供：
  - 用例关联（接口/场景/性能用例互相关联）
  - 用例脑图视图（树形结构导出）
  - 用例导入/导出（Excel / XMind JSON）
  - 用例评审流程（提交评审/通过/驳回）
  - 用例依赖关系（前置/后置依赖）
  - 用例回收站（软删除/恢复/彻底删除）
  - 用例版本管理（快照/回滚）
  - 用例变更记录（审计日志）
  - 用例关联需求（JIRA/TAPD 工单号）
"""
import json
import os
import sqlite3
import uuid
import time
import csv
import io
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from app.logging_config import get_logger

logger = get_logger(__name__)

# 复用基础库的连接函数
from app.cases.repository import (
    _get_conn as _get_base_conn,
    get_case as _get_base_case,
    update_case as _update_base_case,
    list_cases as _list_base_cases,
)

# 评审状态
REVIEW_STATUS_PENDING = "pending"      # 待评审
REVIEW_STATUS_APPROVED = "approved"    # 已通过
REVIEW_STATUS_REJECTED = "rejected"    # 已驳回
REVIEW_STATUS_NEED_REVISE = "need_revise"  # 需修改

# 变更动作
CHANGE_CREATED = "created"
CHANGE_UPDATED = "updated"
CHANGE_DELETED = "deleted"
CHANGE_RESTORED = "restored"
CHANGE_VERSION_CREATED = "version_created"
CHANGE_VERSION_ROLLED_BACK = "version_rolled_back"
CHANGE_REVIEW_SUBMITTED = "review_submitted"
CHANGE_REVIEW_APPROVED = "review_approved"
CHANGE_REVIEW_REJECTED = "review_rejected"
CHANGE_IMPORTED = "imported"
CHANGE_EXPORTED = "exported"


def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（复用基础库的连接）。"""
    return _get_base_conn()


def _init_management_tables() -> None:
    """初始化高级管理相关的表结构。"""
    conn = _get_conn()
    try:
        # 用例关联表：用例之间的关联关系（接口/场景/性能等）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_relations (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                related_case_id TEXT NOT NULL,
                relation_type TEXT DEFAULT 'related',
                created_at REAL,
                FOREIGN KEY (case_id) REFERENCES test_cases(id),
                FOREIGN KEY (related_case_id) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_relations_case_id
            ON case_relations(case_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_relations_related_id
            ON case_relations(related_case_id)
        """)

        # 用例依赖表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_dependencies (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                depends_on TEXT NOT NULL,
                dep_type TEXT DEFAULT 'before',  -- before=前置, after=后置
                description TEXT DEFAULT '',
                created_at REAL,
                FOREIGN KEY (case_id) REFERENCES test_cases(id),
                FOREIGN KEY (depends_on) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_dependencies_case_id
            ON case_dependencies(case_id)
        """)

        # 用例评审记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_reviews (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                review_status TEXT DEFAULT 'pending',
                reviewer TEXT DEFAULT '',
                comment TEXT DEFAULT '',
                created_at REAL,
                reviewed_at REAL,
                FOREIGN KEY (case_id) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_reviews_case_id
            ON case_reviews(case_id)
        """)

        # 用例版本表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_versions (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                snapshot TEXT NOT NULL,
                created_at REAL,
                created_by TEXT DEFAULT '',
                change_desc TEXT DEFAULT '',
                FOREIGN KEY (case_id) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_versions_case_id
            ON case_versions(case_id)
        """)

        # 用例变更记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_change_logs (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                action TEXT NOT NULL,
                field TEXT DEFAULT '',
                old_value TEXT DEFAULT '',
                new_value TEXT DEFAULT '',
                operator TEXT DEFAULT '',
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_change_logs_case_id
            ON case_change_logs(case_id)
        """)

        # 用例回收站（软删除）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_trash (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                case_data TEXT NOT NULL,
                deleted_at REAL,
                deleted_by TEXT DEFAULT '',
                reason TEXT DEFAULT ''
            )
        """)

        # 用例关联需求表（JIRA/TAPD）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_requirements (
                id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,   -- JIRA/TAPD 工单号
                requirement_type TEXT DEFAULT 'jira',  -- jira/tapd
                requirement_title TEXT DEFAULT '',
                requirement_url TEXT DEFAULT '',
                created_at REAL,
                FOREIGN KEY (case_id) REFERENCES test_cases(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_case_requirements_case_id
            ON case_requirements(case_id)
        """)

        conn.commit()
        logger.info("用例高级管理表初始化完成")
    finally:
        pass  # shared cached conn


# 初始化表结构
_init_management_tables()


# ════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════

def _now() -> float:
    return time.time()


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


def _record_change(case_id: str, action: str, field: str = "",
                   old_value: str = "", new_value: str = "",
                   operator: str = "") -> None:
    """记录用例变更日志。"""
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO case_change_logs
               (id, case_id, action, field, old_value, new_value, operator, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (_gen_id(), case_id, action, field, old_value, new_value, operator, _now()),
        )
        conn.commit()
    except Exception as e:
        logger.warning("记录变更日志失败 [case=%s, err=%s]", case_id, e)
    finally:
        pass  # shared cached conn


def _create_version(case_id: str, created_by: str = "", change_desc: str = "") -> int:
    """为用例创建版本快照，返回版本号。"""
    case = _get_base_case(case_id)
    if not case:
        return 0
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT MAX(version) as max_v FROM case_versions WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        version = (row["max_v"] or 0) + 1
        # 序列化快照（排除动态字段）
        snapshot = json.dumps({
            "title": case.get("title", ""),
            "description": case.get("description", ""),
            "source_code": case.get("source_code", ""),
            "test_code": case.get("test_code", ""),
            "file_path": case.get("file_path", ""),
            "tags": case.get("tags", []),
            "status": case.get("status", "draft"),
            "priority": case.get("priority", "P2"),
            "requirement_ref": case.get("requirement_ref", ""),
            "test_type": case.get("test_type", ""),
            "structured_cases": case.get("structured_cases", []),
        }, ensure_ascii=False)
        conn.execute(
            """INSERT INTO case_versions
               (id, case_id, version, snapshot, created_at, created_by, change_desc)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (_gen_id(), case_id, version, snapshot, _now(), created_by, change_desc),
        )
        conn.commit()
        _record_change(case_id, CHANGE_VERSION_CREATED,
                       old_value="", new_value=f"v{version}",
                       operator=created_by, field="version")
        return version
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 1. 用例关联（接口/场景/性能用例互相关联）
# ════════════════════════════════════════════════════════════

def add_case_relation(case_id: str, related_case_id: str,
                      relation_type: str = "related") -> Dict[str, Any]:
    """为用例添加关联。relation_type: related/interface/scenario/performance"""
    if case_id == related_case_id:
        raise ValueError("不能关联自身")
    if not _get_base_case(case_id) or not _get_base_case(related_case_id):
        raise ValueError("用例不存在")
    conn = _get_conn()
    try:
        existing = conn.execute(
            """SELECT id FROM case_relations
               WHERE case_id = ? AND related_case_id = ? AND relation_type = ?""",
            (case_id, related_case_id, relation_type),
        ).fetchone()
        if existing:
            return {"id": existing["id"], "duplicated": True}
        rel_id = _gen_id()
        conn.execute(
            """INSERT INTO case_relations (id, case_id, related_case_id, relation_type, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (rel_id, case_id, related_case_id, relation_type, _now()),
        )
        conn.commit()
        _record_change(case_id, CHANGE_UPDATED, field="relation",
                       new_value=f"关联[{relation_type}]: {related_case_id}")
        return {"id": rel_id, "duplicated": False}
    finally:
        pass  # shared cached conn


def remove_case_relation(case_id: str, related_case_id: str,
                         relation_type: str = "related") -> bool:
    """移除用例关联。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """DELETE FROM case_relations
               WHERE case_id = ? AND related_case_id = ? AND relation_type = ?""",
            (case_id, related_case_id, relation_type),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def list_case_relations(case_id: str) -> List[Dict[str, Any]]:
    """列出用例的所有关联。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT r.*, c.title as related_title
               FROM case_relations r
               LEFT JOIN test_cases c ON c.id = r.related_case_id
               WHERE r.case_id = ?""",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 2. 用例脑图视图
# ════════════════════════════════════════════════════════════

_mindmap_cache: Dict[str, tuple] = {}  # cache_key -> (timestamp, data)
_MINDMAP_CACHE_TTL = 10.0  # 秒


def invalidate_mindmap_cache() -> None:
    """用例数据变更时主动清空脑图缓存。"""
    global _mindmap_cache
    _mindmap_cache.clear()


def get_case_mindmap(project_filter: str = "") -> Dict[str, Any]:
    """
    生成用例脑图树形结构。
    返回层级结构：项目 → 测试类型 → 优先级 → 用例列表
    带 10s 内存缓存，避免高频只读请求反复构建树。
    每个 cache_key 独立计时，避免不同 key 相互影响 TTL。
    """
    global _mindmap_cache
    cache_key = f"mindmap:{project_filter}"
    now = time.time()
    cached_entry = _mindmap_cache.get(cache_key)
    if cached_entry is not None and (now - cached_entry[0]) < _MINDMAP_CACHE_TTL:
        return cached_entry[1]

    cases = _list_base_cases(limit=1000)
    if project_filter:
        cases = [c for c in cases if project_filter in (c.get("file_path") or "")]

    # 构建树
    tree = {
        "id": "root",
        "text": "测试用例库",
        "children": [],
    }

    # 按测试类型分组
    type_groups: Dict[str, List[Dict]] = {}
    for c in cases:
        tt = c.get("test_type") or "functional"
        type_groups.setdefault(tt, []).append(c)

    test_type_names = {
        "functional": "功能测试", "api": "接口测试", "ui": "UI 测试",
        "performance": "性能测试", "security": "安全测试",
        "compatibility": "兼容性测试", "reliability": "可靠性测试",
    }

    for tt, tcases in type_groups.items():
        type_node = {
            "id": f"type_{tt}",
            "text": f"{test_type_names.get(tt, tt)} ({len(tcases)})",
            "children": [],
        }
        # 按优先级分组
        for prio in ["P0", "P1", "P2", "P3"]:
            pcases = [c for c in tcases if (c.get("priority") or "P2") == prio]
            if pcases:
                prio_node = {
                    "id": f"prio_{prio}",
                    "text": f"{prio} 优先级 ({len(pcases)})",
                    "children": [],
                }
                for c in pcases:
                    prio_node["children"].append({
                        "id": c["id"],
                        "text": c.get("title", ""),
                        "status": c.get("status", "draft"),
                        "case_id": c["id"],
                        "type": "case",
                    })
                type_node["children"].append(prio_node)
        tree["children"].append(type_node)

    _mindmap_cache[cache_key] = (time.time(), tree)
    return tree


# ════════════════════════════════════════════════════════════
# 3. 用例导入/导出（Excel / XMind JSON）
# ════════════════════════════════════════════════════════════

def export_cases_excel(cases: List[Dict[str, Any]]) -> bytes:
    """将用例导出为 Excel 格式（CSV with BOM for Excel compatibility）。"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "标题", "描述", "类型", "优先级", "状态",
                     "标签", "文件路径", "需求关联", "创建时间"])
    for c in cases:
        tags = ",".join(c.get("tags") or [])
        writer.writerow([
            c.get("id", ""),
            c.get("title", ""),
            c.get("description", ""),
            c.get("test_type", "functional"),
            c.get("priority", "P2"),
            c.get("status", "draft"),
            tags,
            c.get("file_path", ""),
            c.get("requirement_ref", ""),
            datetime.fromtimestamp(c.get("created_at") or 0).strftime("%Y-%m-%d %H:%M:%S"),
        ])
    csv_data = output.getvalue()
    # 加 BOM 让 Excel 正确识别 UTF-8
    return ("\ufeff" + csv_data).encode("utf-8")


def export_cases_mindmap(cases: List[Dict[str, Any]]) -> str:
    """将用例导出为 XMind 兼容的 JSON 格式。"""
    from app.cases.management import get_case_mindmap
    mindmap = get_case_mindmap()
    return json.dumps(mindmap, ensure_ascii=False, indent=2)


def import_cases_from_excel(csv_text: str, operator: str = "") -> Dict[str, Any]:
    """从 Excel (CSV) 导入用例。"""
    from app.cases.repository import create_case
    reader = csv.DictReader(io.StringIO(csv_text))
    imported = 0
    errors = []
    for row in reader:
        try:
            title = (row.get("标题") or row.get("title") or "").strip()
            if not title:
                continue
            test_type = (row.get("类型") or row.get("test_type") or "functional").strip()
            priority = (row.get("优先级") or row.get("priority") or "P2").strip()
            tags_str = (row.get("标签") or row.get("tags") or "").strip()
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            case = create_case(
                title=title,
                description=row.get("描述") or row.get("description") or "",
                file_path=row.get("文件路径") or row.get("file_path") or "",
                tags=tags,
                status="draft",
                priority=priority if priority in ("P0", "P1", "P2", "P3") else "P2",
                test_type=test_type,
                requirement_ref=row.get("需求关联") or row.get("requirement_ref") or "",
            )
            imported += 1
            _record_change(case.get("id", ""), CHANGE_IMPORTED, operator=operator)
        except Exception as e:
            errors.append(f"行 {reader.line_num}: {str(e)}")
    return {"imported": imported, "errors": errors}


def import_cases_from_xmind(mindmap_json: str, operator: str = "") -> Dict[str, Any]:
    """从 XMind JSON 导入用例。"""
    from app.cases.repository import create_case
    try:
        data = json.loads(mindmap_json)
    except json.JSONDecodeError as e:
        return {"imported": 0, "errors": [f"JSON 解析失败: {e}"]}

    imported = 0
    errors = []

    def walk_node(node, parent_type=""):
        nonlocal imported
        text = node.get("text", "")
        node_type = node.get("type", "")
        case_id = node.get("case_id", "")
        children = node.get("children", [])

        # 如果是用例节点，创建用例
        if node_type == "case" and case_id:
            existing = _get_base_case(case_id)
            if existing:
                return
            try:
                case = create_case(
                    title=text,
                    status="draft",
                    test_type=parent_type or "functional",
                )
                imported += 1
                _record_change(case.get("id", ""), CHANGE_IMPORTED, operator=operator)
            except Exception as e:
                errors.append(f"节点「{text}」: {str(e)}")
        elif case_id:
            existing = _get_base_case(case_id)
            if not existing:
                try:
                    case = create_case(title=text, status="draft")
                    imported += 1
                except Exception as e:
                    errors.append(f"节点「{text}」: {str(e)}")

        for child in children:
            walk_node(child, parent_type=node.get("id", "") or parent_type)

    walk_node(data)
    return {"imported": imported, "errors": errors}


# ════════════════════════════════════════════════════════════
# 4. 用例评审流程
# ════════════════════════════════════════════════════════════

def submit_for_review(case_id: str, reviewer: str = "",
                      comment: str = "") -> Dict[str, Any]:
    """提交用例进入评审流程。"""
    case = _get_base_case(case_id)
    if not case:
        raise ValueError("用例不存在")
    conn = _get_conn()
    try:
        rev_id = _gen_id()
        conn.execute(
            """INSERT INTO case_reviews
               (id, case_id, review_status, reviewer, comment, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (rev_id, case_id, REVIEW_STATUS_PENDING, reviewer, comment, _now()),
        )
        conn.commit()
        # 更新用例状态为评审中
        _update_base_case(case_id, status="review")
        _record_change(case_id, CHANGE_REVIEW_SUBMITTED, operator=reviewer,
                       new_value=comment)
        return {"id": rev_id, "case_id": case_id, "review_status": REVIEW_STATUS_PENDING}
    finally:
        pass  # shared cached conn


def approve_review(case_id: str, reviewer: str = "", comment: str = "") -> Dict[str, Any]:
    """通过评审。"""
    conn = _get_conn()
    try:
        conn.execute(
            """UPDATE case_reviews
               SET review_status = ?, reviewer = ?, comment = ?, reviewed_at = ?
               WHERE case_id = ?""",
            (REVIEW_STATUS_APPROVED, reviewer, comment, _now(), case_id),
        )
        # 直接更新状态（避免嵌套连接）
        conn.execute("UPDATE test_cases SET status = ?, updated_at = ? WHERE id = ?",
                     ("approved", _now(), case_id))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_REVIEW_APPROVED, operator=reviewer)
        except Exception as e:
            logger.warning("记录评审日志失败 [case=%s, err=%s]", case_id, e)
        return {"case_id": case_id, "review_status": REVIEW_STATUS_APPROVED}
    finally:
        pass  # shared cached conn


def reject_review(case_id: str, reviewer: str = "",
                  comment: str = "") -> Dict[str, Any]:
    """驳回评审。"""
    conn = _get_conn()
    try:
        conn.execute(
            """UPDATE case_reviews
               SET review_status = ?, reviewer = ?, comment = ?, reviewed_at = ?
               WHERE case_id = ?""",
            (REVIEW_STATUS_REJECTED, reviewer, comment, _now(), case_id),
        )
        # 直接更新状态（避免嵌套连接）
        conn.execute("UPDATE test_cases SET status = ?, updated_at = ? WHERE id = ?",
                     ("draft", _now(), case_id))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_REVIEW_REJECTED, operator=reviewer,
                           new_value=comment)
        except Exception as e:
            logger.warning("记录驳回日志失败 [case=%s, err=%s]", case_id, e)
        return {"case_id": case_id, "review_status": REVIEW_STATUS_REJECTED}
    finally:
        pass  # shared cached conn


def get_case_reviews(case_id: str) -> List[Dict[str, Any]]:
    """获取用例的评审记录。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM case_reviews WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 5. 用例依赖关系
# ════════════════════════════════════════════════════════════

def add_case_dependency(case_id: str, depends_on: str,
                        dep_type: str = "before",
                        description: str = "") -> Dict[str, Any]:
    """添加用例依赖。dep_type: before=前置依赖, after=后置依赖"""
    if case_id == depends_on:
        raise ValueError("不能依赖自身")
    if not _get_base_case(case_id) or not _get_base_case(depends_on):
        raise ValueError("用例不存在")
    conn = _get_conn()
    try:
        existing = conn.execute(
            """SELECT id FROM case_dependencies
               WHERE case_id = ? AND depends_on = ?""",
            (case_id, depends_on),
        ).fetchone()
        if existing:
            return {"id": existing["id"], "duplicated": True}
        dep_id = _gen_id()
        conn.execute(
            """INSERT INTO case_dependencies
               (id, case_id, depends_on, dep_type, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (dep_id, case_id, depends_on, dep_type, description, _now()),
        )
        conn.commit()
        _record_change(case_id, CHANGE_UPDATED, field="dependency",
                       new_value=f"依赖[{dep_type}]: {depends_on}")
        return {"id": dep_id, "duplicated": False}
    finally:
        pass  # shared cached conn


def remove_case_dependency(case_id: str, depends_on: str) -> bool:
    """移除用例依赖。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM case_dependencies WHERE case_id = ? AND depends_on = ?",
            (case_id, depends_on),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def list_case_dependencies(case_id: str) -> List[Dict[str, Any]]:
    """列出用例的所有依赖。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT d.*, c.title as dep_title
               FROM case_dependencies d
               LEFT JOIN test_cases c ON c.id = d.depends_on
               WHERE d.case_id = ?""",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 6. 用例回收站（软删除）
# ════════════════════════════════════════════════════════════

def soft_delete_case(case_id: str, deleted_by: str = "",
                     reason: str = "") -> bool:
    """软删除用例：放入回收站。"""
    case = _get_base_case(case_id)
    if not case:
        return False
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO case_trash
               (id, case_id, case_data, deleted_at, deleted_by, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (_gen_id(), case_id, json.dumps(case, ensure_ascii=False),
             _now(), deleted_by, reason),
        )
        # 直接更新状态（避免嵌套连接）
        conn.execute("UPDATE test_cases SET status = ?, updated_at = ? WHERE id = ?",
                     ("deprecated", _now(), case_id))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_DELETED, operator=deleted_by, new_value=reason)
        except Exception as e:
            logger.warning("记录删除日志失败 [case=%s, err=%s]", case_id, e)
        invalidate_mindmap_cache()
        return True
    finally:
        pass  # shared cached conn


def restore_case(case_id: str, operator: str = "") -> bool:
    """从回收站恢复用例。"""
    conn = _get_conn()
    try:
        trash = conn.execute(
            "SELECT * FROM case_trash WHERE case_id = ?", (case_id,)
        ).fetchone()
        if not trash:
            return False
        # 恢复状态为草稿
        conn.execute("UPDATE test_cases SET status = ?, updated_at = ? WHERE id = ?",
                     ("draft", _now(), case_id))
        conn.execute("DELETE FROM case_trash WHERE case_id = ?", (case_id,))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_RESTORED, operator=operator)
        except Exception as e:
            logger.warning("记录恢复日志失败 [case=%s, err=%s]", case_id, e)
        invalidate_mindmap_cache()
        return True
    finally:
        pass  # shared cached conn


def list_trash_cases() -> List[Dict[str, Any]]:
    """列出回收站中的用例。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM case_trash ORDER BY deleted_at DESC"
        ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            try:
                item["case_data"] = json.loads(item.get("case_data") or "{}")
            except json.JSONDecodeError:
                item["case_data"] = {}
            result.append(item)
        return result
    finally:
        pass  # shared cached conn


def purge_case(case_id: str) -> bool:
    """从回收站彻底删除用例（从主表和回收站都删除）。"""
    from app.cases.repository import delete_case as _delete_hard
    conn = _get_conn()
    try:
        # 删除关联数据
        conn.execute("DELETE FROM case_relations WHERE case_id = ? OR related_case_id = ?",
                     (case_id, case_id))
        conn.execute("DELETE FROM case_dependencies WHERE case_id = ? OR depends_on = ?",
                     (case_id, case_id))
        conn.execute("DELETE FROM case_reviews WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM case_versions WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM case_change_logs WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM case_requirements WHERE case_id = ?", (case_id,))
        conn.execute("DELETE FROM case_trash WHERE case_id = ?", (case_id,))
        conn.commit()
    finally:
        pass  # shared cached conn
    invalidate_mindmap_cache()
    return _delete_hard(case_id)


# ════════════════════════════════════════════════════════════
# 7. 用例版本管理
# ════════════════════════════════════════════════════════════

def list_case_versions(case_id: str) -> List[Dict[str, Any]]:
    """列出用例的所有版本。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM case_versions WHERE case_id = ? ORDER BY version DESC",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def get_case_version(case_id: str, version: int) -> Optional[Dict[str, Any]]:
    """获取指定版本。"""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM case_versions WHERE case_id = ? AND version = ?",
            (case_id, version),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["snapshot"] = json.loads(item.get("snapshot") or "{}")
        return item
    finally:
        pass  # shared cached conn


def rollback_case(case_id: str, version: int, operator: str = "") -> bool:
    """将用例回滚到指定版本。"""
    version_data = get_case_version(case_id, version)
    if not version_data:
        return False
    snapshot = version_data["snapshot"]
    # 记录当前版本
    _create_version(case_id, created_by=operator, change_desc="回滚前自动保存")
    # 恢复快照内容
    _update_base_case(
        case_id,
        title=snapshot.get("title", ""),
        description=snapshot.get("description", ""),
        source_code=snapshot.get("source_code", ""),
        test_code=snapshot.get("test_code", ""),
        file_path=snapshot.get("file_path", ""),
        tags=snapshot.get("tags", []),
        status=snapshot.get("status", "draft"),
        priority=snapshot.get("priority", "P2"),
        requirement_ref=snapshot.get("requirement_ref", ""),
        structured_cases=snapshot.get("structured_cases", []),
    )
    _record_change(case_id, CHANGE_VERSION_ROLLED_BACK, operator=operator,
                   old_value=f"v{version}", new_value="current")
    return True


# ════════════════════════════════════════════════════════════
# 8. 用例变更记录
# ════════════════════════════════════════════════════════════

def list_case_changes(case_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """列出用例的变更记录。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM case_change_logs
               WHERE case_id = ? ORDER BY created_at DESC LIMIT ?""",
            (case_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


# ════════════════════════════════════════════════════════════
# 9. 用例关联需求（JIRA/TAPD）
# ════════════════════════════════════════════════════════════

def add_case_requirement(case_id: str, requirement_id: str,
                         requirement_type: str = "jira",
                         requirement_title: str = "",
                         requirement_url: str = "") -> Dict[str, Any]:
    """关联需求到用例。"""
    if not _get_base_case(case_id):
        raise ValueError("用例不存在")
    conn = _get_conn()
    try:
        existing = conn.execute(
            """SELECT id FROM case_requirements
               WHERE case_id = ? AND requirement_id = ?""",
            (case_id, requirement_id),
        ).fetchone()
        if existing:
            return {"id": existing["id"], "duplicated": True}
        req_id = _gen_id()
        conn.execute(
            """INSERT INTO case_requirements
               (id, case_id, requirement_id, requirement_type,
                requirement_title, requirement_url, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (req_id, case_id, requirement_id, requirement_type,
             requirement_title, requirement_url, _now()),
        )
        # 同时更新 requirement_ref 字段
        conn.execute("UPDATE test_cases SET requirement_ref = ?, updated_at = ? WHERE id = ?",
                     (requirement_id, _now(), case_id))
        conn.commit()
        try:
            _record_change(case_id, CHANGE_UPDATED, field="requirement",
                           new_value=f"{requirement_type}: {requirement_id}")
        except Exception as e:
            logger.warning("记录需求日志失败 [case=%s, err=%s]", case_id, e)
        return {"id": req_id, "duplicated": False}
    finally:
        pass  # shared cached conn


def remove_case_requirement(case_id: str, requirement_id: str) -> bool:
    """移除需求关联。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM case_requirements WHERE case_id = ? AND requirement_id = ?",
            (case_id, requirement_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def list_case_requirements(case_id: str) -> List[Dict[str, Any]]:
    """列出用例关联的所有需求。"""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM case_requirements WHERE case_id = ? ORDER BY created_at DESC",
            (case_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def get_case_full_info(case_id: str) -> Optional[Dict[str, Any]]:
    """获取用例完整信息（含关联/依赖/评审/版本/变更/需求）。"""
    case = _get_base_case(case_id)
    if not case:
        return None
    case["relations"] = list_case_relations(case_id)
    case["dependencies"] = list_case_dependencies(case_id)
    case["reviews"] = get_case_reviews(case_id)
    case["versions"] = list_case_versions(case_id)
    case["changes"] = list_case_changes(case_id)
    case["requirements"] = list_case_requirements(case_id)
    return case
