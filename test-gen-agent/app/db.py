# app/db.py
"""统一数据存储配置模块

Phase 6：数据库合并后，所有业务数据统一使用 tga.db。
各模块的独立 .db 文件已合并，保留常量用于向后兼容。
"""

import os

# 项目根目录：app/db.py -> 项目根
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 合并后的统一数据库
TGA_DB = "tga.db"


def db_path(filename: str) -> str:
    """返回项目根目录下的数据库文件绝对路径。"""
    return os.path.join(PROJECT_ROOT, filename)


# ── Phase 6 数据库合并映射 ─────────────────────────────────
# 所有业务数据库统一映射到 tga.db
# 表名带业务前缀以避免冲突（如 auth_users, test_cases 等）
_LEGACY_DB_MAP = {
    "auth.db": TGA_DB,
    "apitest.db": TGA_DB,
    "defects.db": TGA_DB,
    "environments.db": TGA_DB,
    "projects.db": TGA_DB,
    "runs.db": TGA_DB,
    "scripthealth.db": TGA_DB,
    "test_plans.db": TGA_DB,
    "testcases.db": TGA_DB,
    "trace.db": TGA_DB,
    "datafactory.db": TGA_DB,
    "api_testing.db": TGA_DB,
    "api_testing_datas.db": TGA_DB,
    "script_health.db": TGA_DB,
}


def resolve_db_name(db_name: str) -> str:
    """将旧数据库名映射到统一数据库名。"""
    return _LEGACY_DB_MAP.get(db_name, TGA_DB)


# ── 向后兼容常量（各模块逐步迁移）──────────────────────────
APITEST_DB = TGA_DB
AUTH_DB = TGA_DB
CHECKPOINTS_DB = "checkpoints.db"
DATAFACTORY_DB = TGA_DB
DEFECTS_DB = TGA_DB
ENVIRONMENTS_DB = TGA_DB
PROJECTS_DB = TGA_DB
RUNS_DB = TGA_DB
SCRIPTHEALTH_DB = TGA_DB
TEST_PLANS_DB = TGA_DB
TESTCASES_DB = TGA_DB
TRACE_DB = TGA_DB

# api_testing 模块与 apitest 共用同一数据库
API_TESTING_DB = APITEST_DB
