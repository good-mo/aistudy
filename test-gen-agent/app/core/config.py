# app/core/config.py
"""
统一配置模块（核心扩展）
=========================
Phase 1 重构目标：在 app/config.py 之上补充数据库路径统一管理。
"""
import os
from app.db import PROJECT_ROOT

# 统一数据库配置
# 合并后统一使用 tga.db
TARGET_DB = os.path.join(PROJECT_ROOT, "tga.db")

# 数据库文件到表前缀的映射（Phase 6 合并时使用）
# 注意：api_testing 模块已统一使用 apitest.db，不再有独立的 api_testing.db
DB_PREFIX_MAP = {
    "auth.db": "auth",
    "apitest.db": "apitest",
    "defects.db": "defects",
    "environments.db": "environments",
    "projects.db": "projects",
    "runs.db": "runs",
    "scripthealth.db": "scripthealth",
    "test_plans.db": "test_plans",
    "testcases.db": "test_cases",
    "trace.db": "trace",
}

__all__ = ["TARGET_DB", "DB_PREFIX_MAP"]
