#!/usr/bin/env python3
"""
路由冲突检测脚本
=================
Phase 0 目标：建立路由冲突检测机制，防止重复路径注册。

用法：
    python3 scripts/route_conflict_check.py --check    # 检查当前路由冲突
    python3 scripts/route_conflict_check.py --generate # 生成 API 映射表
"""
import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# 收集所有路由装饰器的路径和方法
ROUTE_PATTERNS = [
    (r"@app\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", "main.py"),
    (r"@router\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", "router"),
    (r"@missing_apis_router\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", "missing_apis.py"),
    (r"@method_fixes_router\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", "method_fixes.py"),
    (r"@path_param_fixes_router\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']", "path_param_fixes.py"),
]


def scan_routes() -> list:
    """扫描项目中的所有路由定义。"""
    routes = []
    base_dir = Path(__file__).parent.parent

    # main.py
    main_file = base_dir / "app" / "main.py"
    if main_file.exists():
        content = main_file.read_text()
        for method, path in re.findall(
            r"@app\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']",
            content
        ):
            routes.append({"path": path, "method": method.upper(), "source": "main.py"})

    # adapters/*
    adapters_dir = base_dir / "app" / "adapters"
    for f in adapters_dir.glob("*.py"):
        if f.name == "__init__.py":
            continue
        content = f.read_text()
        for method, path in re.findall(
            r"@router\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']",
            content
        ):
            routes.append({"path": path, "method": method.upper(), "source": f.name})

    # 各模块 routers
    for router_file in (base_dir / "app").rglob("router.py"):
        if "adapters" in str(router_file):
            continue
        content = router_file.read_text()
        for method, path in re.findall(
            r"@router\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']",
            content
        ):
            rel = router_file.relative_to(base_dir)
            routes.append({"path": path, "method": method.upper(), "source": str(rel)})

    return routes


def check_conflicts(routes: list) -> list:
    """检查路由冲突。"""
    # 相同 path + method 为冲突
    path_method_map = defaultdict(list)
    conflicts = []

    for r in routes:
        key = (r["path"], r["method"])
        path_method_map[key].append(r["source"])

    for (path, method), sources in path_method_map.items():
        if len(sources) > 1:
            conflicts.append({
                "path": path,
                "method": method,
                "sources": sources,
            })

    return conflicts


def generate_mapping(routes: list) -> str:
    """生成 API 映射文档。"""
    lines = ["# API 映射表（自动生成）", ""]
    lines.append(f"共扫描到 **{len(routes)}** 个路由端点。")
    lines.append("")

    # 按路径前缀分组
    grouped = defaultdict(list)
    for r in routes:
        path = r["path"]
        # 提取一级前缀
        parts = path.strip("/").split("/")
        prefix = parts[0] if parts else "(root)"
        grouped[prefix].append(r)

    for prefix in sorted(grouped.keys()):
        items = grouped[prefix]
        lines.append(f"## `/{prefix}` ({len(items)} 个路由)")
        lines.append("")
        lines.append("| Method | Path | Source |")
        lines.append("|--------|------|--------|")
        for r in sorted(items, key=lambda x: (x["method"], x["path"])):
            lines.append(f"| {r['method']} | `{r['path']}` | `{r['source']}` |")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="路由冲突检测工具")
    parser.add_argument("--check", action="store_true", help="检查路由冲突")
    parser.add_argument("--generate", action="store_true", help="生成 API 映射文档")
    args = parser.parse_args()

    routes = scan_routes()

    if args.check:
        conflicts = check_conflicts(routes)
        if conflicts:
            print(f"❌ 发现 {len(conflicts)} 处路由冲突:")
            for c in conflicts:
                print(f"  [{c['method']}] {c['path']}: {', '.join(c['sources'])}")
            sys.exit(1)
        else:
            print(f"✅ 未发现路由冲突（共 {len(routes)} 个路由）")
        return

    if args.generate:
        doc = generate_mapping(routes)
        output = Path(__file__).parent.parent / "docs" / "api_mapping_generated.md"
        output.write_text(doc)
        print(f"✅ 已生成 API 映射文档: {output}")
        return

    # 默认输出摘要
    print(f"共发现 {len(routes)} 个路由端点")
    by_source = defaultdict(int)
    for r in routes:
        by_source[r["source"]] += 1
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {source}: {count} 个路由")


if __name__ == "__main__":
    main()
