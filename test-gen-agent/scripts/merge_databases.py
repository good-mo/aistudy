#!/usr/bin/env python3
"""
数据库合并脚本（Phase 6）
=========================
将多个 SQLite 数据库合并为统一数据库 tga.db。

目标：
  - 14+ 个 .db 文件 → 1 个 tga.db（业务数据）+ checkpoints.db（LangGraph）
  - 合并后统一使用 app.core.database.Database 访问

用法：
    python3 scripts/merge_databases.py --dry-run    # 预览合并计划
    python3 scripts/merge_databases.py --execute    # 执行合并
    python3 scripts/merge_databases.py --backup     # 备份原数据库
"""
import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import PROJECT_ROOT, TGA_DB

# 需要合并的业务数据库
BUSINESS_DBS = {
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
    "datafactory.db": "datafactory",
}

# 不需要合并的独立数据库
SEPARATE_DBS = ["checkpoints.db"]


def db_path(filename: str) -> str:
    return os.path.join(PROJECT_ROOT, filename)


def list_tables(db_file: str) -> list:
    """列出数据库中的所有表。"""
    if not os.path.exists(db_file):
        return []
    conn = sqlite3.connect(db_file)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r[0] for r in rows if not r[0].startswith('sqlite_')]
    finally:
        conn.close()


def get_table_info(db_file: str, table: str) -> dict:
    """获取表的创建 SQL 和行数。"""
    conn = sqlite3.connect(db_file)
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        count = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
        return {"sql": row[0] if row else "", "count": count}
    finally:
        conn.close()


def merge_tables(source_db: str, target_db: str, prefix: str = "") -> int:
    """将 source_db 中的所有表合并到 target_db。

    Args:
        source_db: 源数据库文件路径
        target_db: 目标数据库文件路径
        prefix: 表名前缀，避免重名冲突

    Returns:
        合并的行数
    """
    total_rows = 0
    tables = list_tables(source_db)
    if not tables:
        return 0

    target_conn = sqlite3.connect(target_db)
    try:
        for table in tables:
            info = get_table_info(source_db, table)
            if not info["sql"]:
                continue

            # 添加前缀避免冲突
            target_table = f"{prefix}_{table}" if prefix else table

            # 检查目标表是否已存在
            exists = target_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (target_table,),
            ).fetchone()

            if not exists:
                # 创建表（替换表名为目标表名）
                sql = info["sql"]
                sql = sql.replace(f'CREATE TABLE "{table}"', f'CREATE TABLE "{target_table}"')
                sql = sql.replace(f"CREATE TABLE {table}", f"CREATE TABLE {target_table}")
                target_conn.execute(sql)

            # 复制数据
            src_conn = sqlite3.connect(source_db)
            try:
                cols = [r[1] for r in src_conn.execute(f"PRAGMA table_info([{table}])").fetchall()]
                if not cols:
                    continue
                col_names = ", ".join([f'"{c}"' for c in cols])
                placeholders = ", ".join(["?"] * len(cols))

                rows = src_conn.execute(f"SELECT {col_names} FROM [{table}]").fetchall()
                for row in rows:
                    try:
                        target_conn.execute(
                            f'INSERT OR IGNORE INTO "{target_table}" ({col_names}) VALUES ({placeholders})',
                            row,
                        )
                        total_rows += 1
                    except sqlite3.Error as e:
                        print(f"  ⚠️ 跳过行: {e}")
            finally:
                src_conn.close()

        target_conn.commit()
        return total_rows
    finally:
        target_conn.close()


def dry_run() -> None:
    """预览合并计划。"""
    print("=" * 60)
    print("数据库合并计划（Dry Run）")
    print("=" * 60)

    total_before = 0
    total_after = 0

    for db_file, prefix in BUSINESS_DBS.items():
        path = db_path(db_file)
        if not os.path.exists(path):
            continue
        size = os.path.getsize(path) / 1024
        tables = list_tables(path)
        total_before += size
        print(f"\n📦 {db_file} ({size:.0f}KB, {len(tables)} tables)")
        for t in tables:
            info = get_table_info(path, t)
            print(f"  └─ {prefix}_{t}: {info['count']} rows")
            total_after += info["count"]

    print(f"\n{'=' * 60}")
    print(f"合并前: {len(BUSINESS_DBS)} 个数据库文件")
    print(f"合并后: 1 个 {TGA_DB}")
    print(f"预计迁移 {total_after} 行数据")


def execute() -> None:
    """执行数据库合并。"""
    print("=" * 60)
    print("正在执行数据库合并...")
    print("=" * 60)

    target = db_path(TGA_DB)

    # 创建目标数据库
    if os.path.exists(target):
        print(f"目标数据库已存在: {target}")
        backup = f"{target}.bak"
        shutil.copy2(target, backup)
        print(f"已备份: {backup}")

    total_migrated = 0
    for db_file, prefix in BUSINESS_DBS.items():
        path = db_path(db_file)
        if not os.path.exists(path):
            print(f"⚠️ 跳过不存在的数据库: {db_file}")
            continue

        print(f"\n📦 合并 {db_file} → {TGA_DB} (prefix: {prefix})...")
        rows = merge_tables(path, target, prefix)
        print(f"  ✅ 迁移 {rows} 行")
        total_migrated += rows

    print(f"\n{'=' * 60}")
    print(f"✅ 合并完成！共迁移 {total_migrated} 行数据")
    print(f"   目标数据库: {target}")
    print(f"\n💡 下一步:")
    print(f"   1. app/core/database.py 已更新，自动路由到 {TGA_DB}")
    print(f"   2. 删除旧的 .db 文件")
    print(f"   3. 验证应用功能")


def backup() -> None:
    """备份所有数据库文件。"""
    backup_dir = os.path.join(PROJECT_ROOT, "backup_dbs")
    os.makedirs(backup_dir, exist_ok=True)

    for db_file in list(BUSINESS_DBS.keys()) + SEPARATE_DBS:
        path = db_path(db_file)
        if os.path.exists(path):
            dest = os.path.join(backup_dir, db_file)
            shutil.copy2(path, dest)
            print(f"✅ 备份 {db_file} → {dest}")
        else:
            print(f"⚠️ 跳过不存在的: {db_file}")

    print(f"\n备份完成，所有数据库已保存到 {backup_dir}")


def main():
    parser = argparse.ArgumentParser(description="数据库合并工具")
    parser.add_argument("--dry-run", action="store_true", help="预览合并计划")
    parser.add_argument("--execute", action="store_true", help="执行合并")
    parser.add_argument("--backup", action="store_true", help="备份原数据库")
    args = parser.parse_args()

    if args.backup:
        backup()
    elif args.execute:
        execute()
    else:
        dry_run()


if __name__ == "__main__":
    main()
