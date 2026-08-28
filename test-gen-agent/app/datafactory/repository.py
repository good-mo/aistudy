"""
数据模板 / 一键造数 / 数据清理模块
=================================
提供：
  - 数据模板管理：创建/编辑/查看/删除数据模板
  - 一键造数：根据模板批量生成测试数据（含依赖关系自动解析）
  - 数据清理：一键清理测试数据，支持按批次/模板/环境隔离
"""
import json
import os
import sqlite3
import time
import uuid
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

# 统一使用 Database 连接池管理
from app.core.database import Database

# 数据模板类别
CATEGORY_USER = "user"
CATEGORY_ORDER = "order"
CATEGORY_PRODUCT = "product"
CATEGORY_INVENTORY = "inventory"
CATEGORY_COUPON = "coupon"
CATEGORY_PAYMENT = "payment"
CATEGORY_CUSTOM = "custom"

VALID_CATEGORIES = {
    CATEGORY_USER, CATEGORY_ORDER, CATEGORY_PRODUCT,
    CATEGORY_INVENTORY, CATEGORY_COUPON, CATEGORY_PAYMENT,
    CATEGORY_CUSTOM,
}

# 数据生成策略
STRATEGY_SEQUENCE = "sequence"
STRATEGY_FIXED = "fixed"
STRATEGY_UUID = "uuid"
STRATEGY_RANDOM = "random"
STRATEGY_TIMESTAMP = "timestamp"
STRATEGY_REFERENCE = "reference"

VALID_STRATEGIES = {
    STRATEGY_SEQUENCE, STRATEGY_FIXED, STRATEGY_UUID,
    STRATEGY_RANDOM, STRATEGY_TIMESTAMP, STRATEGY_REFERENCE,
}



def _get_conn() -> sqlite3.Connection:
    """获取数据库连接（统一使用 Database 连接池）。"""
    return Database.get_conn("datafactory.db")


def _init_db() -> None:
    """初始化表结构（使用独立临时连接）。"""
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'custom',
                schema_json TEXT DEFAULT '{}',
                deps_json TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                status TEXT DEFAULT 'active',
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS data_batches (
                id TEXT PRIMARY KEY,
                template_id TEXT,
                template_name TEXT DEFAULT '',
                batch_size INTEGER DEFAULT 1,
                env_key TEXT DEFAULT 'default',
                data_json TEXT DEFAULT '[]',
                status TEXT DEFAULT 'active',
                created_at REAL,
                updated_at REAL
            )
        """)
        conn.commit()
    finally:
        pass  # shared cached conn


_init_db()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """将数据库行转为 dict，解析 JSON 字段。"""
    data = dict(row)

    # 解析 schema_json → schema
    schema_raw = data.get("schema_json", "")
    data["schema"] = json.loads(schema_raw) if schema_raw else {}
    data.pop("schema_json", None)

    # 解析 deps_json → deps
    deps_raw = data.get("deps_json", "")
    data["deps"] = json.loads(deps_raw) if deps_raw else []
    data.pop("deps_json", None)

    # 解析 tags
    tags_raw = data.get("tags", "")
    data["tags"] = json.loads(tags_raw) if tags_raw else []
    return data


# ═══════════════════════════════════════════════════════════
# 数据模板 CRUD
# ═══════════════════════════════════════════════════════════

def create_template(
    name: str,
    description: str = "",
    category: str = CATEGORY_CUSTOM,
    schema: Optional[Dict] = None,
    deps: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """创建数据模板。"""
    template_id = uuid.uuid4().hex[:12]
    now = time.time()
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO data_templates
               (id, name, description, category, schema_json, deps_json,
                tags, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (template_id, name, description, category,
             json.dumps(schema or {}, ensure_ascii=False),
             json.dumps(deps or []),
             json.dumps(tags or []), "active", now, now),
        )
        conn.commit()
        logger.info("数据模板已创建 [id=%s, name=%s]", template_id, name)
        return get_template(template_id) or {"id": template_id}
    finally:
        pass  # shared cached conn


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM data_templates WHERE id = ?", (template_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        pass  # shared cached conn


def list_templates(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        query = "SELECT * FROM data_templates WHERE status = 'active'"
        params: List = []
        if category and category in VALID_CATEGORIES:
            query += " AND category = ?"
            params.append(category)
        if search:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        pass  # shared cached conn


def update_template(template_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    existing = get_template(template_id)
    if not existing:
        return None

    allowed = {"name", "description", "category", "schema", "deps", "tags", "status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}

    if "schema" in updates and isinstance(updates["schema"], dict):
        updates["schema_json"] = json.dumps(updates["schema"], ensure_ascii=False)
        del updates["schema"]
    if "deps" in updates and isinstance(updates["deps"], list):
        updates["deps_json"] = json.dumps(updates["deps"])
        del updates["deps"]
    if "tags" in updates and isinstance(updates["tags"], list):
        updates["tags"] = json.dumps(updates["tags"])

    if not updates:
        return existing

    updates["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [template_id]

    conn = _get_conn()
    try:
        conn.execute(f"UPDATE data_templates SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return get_template(template_id)
    finally:
        pass  # shared cached conn


def delete_template(template_id: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM data_templates WHERE id = ?", (template_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


# ═══════════════════════════════════════════════════════════
# 一键造数
# ═══════════════════════════════════════════════════════════

def _generate_value(field_spec: Dict[str, Any], seq: int, registry: Dict[str, Any]) -> Any:
    """根据字段定义生成值。"""
    strategy = field_spec.get("strategy", STRATEGY_FIXED)
    value = field_spec.get("value", "")

    if strategy == STRATEGY_FIXED:
        return value
    elif strategy == STRATEGY_SEQUENCE:
        if isinstance(value, str) and "{n}" in value:
            return value.replace("{n}", str(seq))
        return f"{value}{seq}"
    elif strategy == STRATEGY_UUID:
        return uuid.uuid4().hex
    elif strategy == STRATEGY_RANDOM:
        import random
        choices = field_spec.get("choices", [])
        if choices:
            return random.choice(choices)
        low = field_spec.get("min", 0)
        high = field_spec.get("max", 1000)
        return random.randint(int(low), int(high))
    elif strategy == STRATEGY_TIMESTAMP:
        fmt = field_spec.get("format", "%Y-%m-%d %H:%M:%S")
        return time.strftime(fmt, time.localtime(time.time() + seq))
    elif strategy == STRATEGY_REFERENCE:
        ref_key = field_spec.get("ref", "")
        if ref_key in registry:
            return registry[ref_key]
        return None
    return value


def generate_data(
    template_id: str,
    batch_size: int = 1,
    env_key: str = "default",
) -> Dict[str, Any]:
    """
    一键造数：根据模板生成指定批次大小的测试数据。
    自动解析模板之间的依赖关系（deps）。
    """
    template = get_template(template_id)
    if not template:
        raise ValueError(f"数据模板 {template_id} 不存在")

    schema = template.get("schema", {})
    if not isinstance(schema, dict):
        schema = {}

    # 解析依赖
    deps = template.get("deps", [])
    dep_data = {}
    for dep_id in deps:
        dep = get_template(dep_id)
        if dep:
            dep_schema = dep.get("schema", {})
            if isinstance(dep_schema, dict):
                for field, spec in dep_schema.items():
                    if isinstance(spec, dict):
                        dep_data[f"{dep['name']}.{field}"] = _generate_value(spec, 1, {})

    batch_id = uuid.uuid4().hex[:12]
    now = time.time()
    generated_items = []

    for i in range(batch_size):
        item = {}
        registry = {**dep_data}
        for field, spec in schema.items():
            if isinstance(spec, dict):
                item[field] = _generate_value(spec, i + 1, registry)
            else:
                item[field] = spec
        generated_items.append(item)

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO data_batches
               (id, template_id, template_name, batch_size, env_key,
                data_json, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (batch_id, template_id, template.get("name", ""), batch_size,
             env_key, json.dumps(generated_items, ensure_ascii=False),
             "active", now, now),
        )
        conn.commit()
        logger.info("数据已生成 [batch=%s, template=%s, size=%d]",
                    batch_id, template_id, batch_size)
    finally:
        pass  # shared cached conn

    return {
        "batch_id": batch_id,
        "template_id": template_id,
        "template_name": template.get("name", ""),
        "batch_size": batch_size,
        "env_key": env_key,
        "data": generated_items,
        "created_at": now,
    }


# ═══════════════════════════════════════════════════════════
# 数据清理
# ═══════════════════════════════════════════════════════════

def cleanup_batch(batch_id: str) -> bool:
    """清理指定批次的数据（软删除）。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE data_batches SET status = 'cleaned', updated_at = ? WHERE id = ?",
            (time.time(), batch_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        pass  # shared cached conn


def cleanup_by_template(template_id: str, env_key: str = "default") -> int:
    """清理某模板在某环境下的所有批次数据。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """UPDATE data_batches SET status = 'cleaned', updated_at = ?
               WHERE template_id = ? AND env_key = ? AND status = 'active'""",
            (time.time(), template_id, env_key),
        )
        conn.commit()
        return cur.rowcount
    finally:
        pass  # shared cached conn


def cleanup_by_env(env_key: str) -> int:
    """清理某环境下的所有测试数据。"""
    conn = _get_conn()
    try:
        cur = conn.execute(
            """UPDATE data_batches SET status = 'cleaned', updated_at = ?
               WHERE env_key = ? AND status = 'active'""",
            (time.time(), env_key),
        )
        conn.commit()
        return cur.rowcount
    finally:
        pass  # shared cached conn


def list_batches(
    template_id: Optional[str] = None,
    env_key: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """列出生成的数据批次。"""
    conn = _get_conn()
    try:
        query = "SELECT * FROM data_batches WHERE 1=1"
        params: List = []
        if template_id:
            query += " AND template_id = ?"
            params.append(template_id)
        if env_key:
            query += " AND env_key = ?"
            params.append(env_key)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("data_json"):
                try:
                    d["data"] = json.loads(d["data_json"])
                except (json.JSONDecodeError, TypeError):
                    d["data"] = []
            d.pop("data_json", None)
            result.append(d)
        return result
    finally:
        pass  # shared cached conn


def get_stats() -> Dict[str, Any]:
    """获取数据工厂统计。"""
    conn = _get_conn()
    try:
        template_count = conn.execute("SELECT COUNT(*) FROM data_templates WHERE status = 'active'").fetchone()[0]
        batch_count = conn.execute("SELECT COUNT(*) FROM data_batches WHERE status = 'active'").fetchone()[0]
        cleaned_count = conn.execute("SELECT COUNT(*) FROM data_batches WHERE status = 'cleaned'").fetchone()[0]

        # 一次 GROUP BY 查询代替逐类别 COUNT（消除 N+1）
        by_category = {c: 0 for c in VALID_CATEGORIES}
        for row in conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM data_templates GROUP BY category"
        ):
            if row["category"] in by_category:
                by_category[row["category"]] = row["cnt"]

        return {
            "template_count": template_count,
            "active_batches": batch_count,
            "cleaned_batches": cleaned_count,
            "total_batches": batch_count + cleaned_count,
            "by_category": by_category,
        }
    finally:
        pass  # shared cached conn


# ═══════════════════════════════════════════════════════════
# 内置常用模板
# ═══════════════════════════════════════════════════════════

def seed_default_templates() -> None:
    """初始化常用数据模板（用户/商品/订单/库存/优惠券）。"""
    existing = list_templates(limit=1)
    if existing:
        return

    now = time.time()
    templates = [
        {
            "name": "用户模板",
            "description": "创建测试用户，含手机号/邮箱/地址等字段",
            "category": CATEGORY_USER,
            "schema": {
                "username": {"strategy": STRATEGY_SEQUENCE, "value": "test_user_{n}"},
                "phone": {"strategy": STRATEGY_RANDOM, "choices": ["13800138000", "13900139000", "13700137000"]},
                "email": {"strategy": STRATEGY_SEQUENCE, "value": "user{n}@test.com"},
                "address": {"strategy": STRATEGY_FIXED, "value": "北京市朝阳区测试路1号"},
                "is_vip": {"strategy": STRATEGY_FIXED, "value": False},
                "created_at": {"strategy": STRATEGY_TIMESTAMP, "format": "%Y-%m-%d %H:%M:%S"},
            },
            "deps": [],
            "tags": ["用户", "基础数据"],
        },
        {
            "name": "商品模板",
            "description": "创建测试商品，含名称/价格/分类/库存",
            "category": CATEGORY_PRODUCT,
            "schema": {
                "product_name": {"strategy": STRATEGY_SEQUENCE, "value": "测试商品_{n}"},
                "price": {"strategy": STRATEGY_RANDOM, "min": 10, "max": 1000},
                "category": {"strategy": STRATEGY_FIXED, "value": "电子产品"},
                "description": {"strategy": STRATEGY_FIXED, "value": "自动化测试生成"},
                "sku": {"strategy": STRATEGY_UUID},
                "created_at": {"strategy": STRATEGY_TIMESTAMP, "format": "%Y-%m-%d %H:%M:%S"},
            },
            "deps": [],
            "tags": ["商品", "基础数据"],
        },
        {
            "name": "订单模板",
            "description": "创建测试订单，依赖用户/商品模板",
            "category": CATEGORY_ORDER,
            "schema": {
                "order_no": {"strategy": STRATEGY_SEQUENCE, "value": "ORD{n:06d}"},
                "user_id": {"strategy": STRATEGY_REFERENCE, "ref": "用户模板.user_id"},
                "product_id": {"strategy": STRATEGY_REFERENCE, "ref": "商品模板.sku"},
                "amount": {"strategy": STRATEGY_RANDOM, "min": 1, "max": 10000},
                "status": {"strategy": STRATEGY_FIXED, "value": "pending"},
                "payment_method": {"strategy": STRATEGY_FIXED, "value": "wechat"},
                "created_at": {"strategy": STRATEGY_TIMESTAMP, "format": "%Y-%m-%d %H:%M:%S"},
            },
            "deps": [],
            "tags": ["订单", "核心数据"],
        },
        {
            "name": "库存模板",
            "description": "创建测试库存记录，关联商品",
            "category": CATEGORY_INVENTORY,
            "schema": {
                "warehouse_id": {"strategy": STRATEGY_SEQUENCE, "value": "WH-{n}"},
                "product_sku": {"strategy": STRATEGY_UUID},
                "quantity": {"strategy": STRATEGY_RANDOM, "min": 1, "max": 500},
                "reserved": {"strategy": STRATEGY_FIXED, "value": 0},
                "created_at": {"strategy": STRATEGY_TIMESTAMP, "format": "%Y-%m-%d %H:%M:%S"},
            },
            "deps": [],
            "tags": ["库存", "基础数据"],
        },
        {
            "name": "优惠券模板",
            "description": "创建测试优惠券，支持满减/折扣类型",
            "category": CATEGORY_COUPON,
            "schema": {
                "coupon_code": {"strategy": STRATEGY_SEQUENCE, "value": "CPN{n:08d}"},
                "type": {"strategy": STRATEGY_FIXED, "value": "discount"},
                "value": {"strategy": STRATEGY_RANDOM, "min": 5, "max": 50},
                "min_amount": {"strategy": STRATEGY_FIXED, "value": 100},
                "expire_at": {"strategy": STRATEGY_TIMESTAMP, "format": "%Y-%m-%d"},
                "created_at": {"strategy": STRATEGY_TIMESTAMP, "format": "%Y-%m-%d %H:%M:%S"},
            },
            "deps": [],
            "tags": ["优惠券", "营销数据"],
        },
    ]

    conn = _get_conn()
    try:
        for t in templates:
            template_id = uuid.uuid4().hex[:12]
            conn.execute(
                """INSERT INTO data_templates
                   (id, name, description, category, schema_json, deps_json,
                    tags, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (template_id, t["name"], t["description"], t["category"],
                 json.dumps(t["schema"], ensure_ascii=False),
                 json.dumps(t["deps"]),
                 json.dumps(t["tags"]), "active", now, now),
            )
        conn.commit()
        logger.info("已初始化 %d 个内置数据模板", len(templates))
    finally:
        pass  # shared cached conn
