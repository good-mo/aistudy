#!/usr/bin/env python3
# app/cli.py
"""
CLI 工具：供 CI/CD 流水线调用
=============================
支持命令行直接生成测试用例、运行测试、生成报告。

用法示例:
  python -m app.cli generate --source-file demo.py
  python -m app.cli generate --project-path ./src --output-dir output
  python -m app.cli report --project-path ./src --format html
  python -m app.cli list-cases
  python -m app.cli defects
"""
import argparse
import asyncio
import json
import os
import sys
from typing import Dict, Any, List

# 确保在项目根目录可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 顶层导入供测试 patch 使用
from app.projects.manager import collect_sources_from_paths
from app.graph.builder import build_graph
from app.cases.repository import list_cases
from app.defects.tracker import list_defects
from app.logging_config import get_logger

logger = get_logger(__name__)


def cmd_generate(args: argparse.Namespace) -> int:
    """生成测试用例。"""
    from app.projects.manager import scan_project

    try:
        if args.project_path:
            # 项目级扫描
            scan_result = scan_project(args.project_path)
            logger.info("项目扫描完成: %s 个文件, %s 个函数",
                        scan_result['total_files'], scan_result['total_functions'])
            print(f"🔍 项目扫描完成: {scan_result['total_files']} 个文件, "
                  f"{scan_result['total_functions']} 个函数")
            paths = [f["path"] for f in scan_result["files"]]
            sources = collect_sources_from_paths(paths)
        elif args.source_file:
            # 单文件
            sources = collect_sources_from_paths([args.source_file])
        else:
            # 从 stdin 读取
            source_code = sys.stdin.read()
            if not source_code.strip():
                print("❌ 错误: 未提供源代码", file=sys.stderr)
                return 1
            sources = [{"file_path": "stdin.py", "source_code": source_code}]

        if not sources:
            print("❌ 错误: 没有可处理的源文件", file=sys.stderr)
            return 1

        graph = build_graph()
        results = []

        for src in sources:
            logger.info("处理文件: %s", src['file_path'])
            print(f"⚙️  处理文件: {src['file_path']}...")
            config = {"configurable": {"thread_id": src["file_path"]}}
            # 支持同步/异步 graph（测试 mock 返回 dict，真实 graph 返回 coroutine）
            ainvoke_result = graph.ainvoke(
                {
                    "source_code": src["source_code"],
                    "file_path": src["file_path"],
                    "test_type": args.test_type,
                    "generate_script": not args.no_script,
                    "retry_count": 0,
                },
                config=config,
            )
            if asyncio.iscoroutine(ainvoke_result):
                result = asyncio.run(ainvoke_result)
            else:
                result = ainvoke_result

            # 保存测试代码
            test_code = result.get("generated_tests", "")
            if test_code:
                out_dir = args.output_dir or "output"
                os.makedirs(out_dir, exist_ok=True)
                out_path = os.path.join(out_dir, f"test_{os.path.basename(src['file_path'])}")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(test_code)
                logger.info("测试已保存: %s", out_path)
                print(f"  ✅ 测试已保存: {out_path}")

            results.append({
                "file_path": src["file_path"],
                "generated_tests": test_code,
                "test_result": result.get("test_result", {}),
                "coverage_report": result.get("coverage_report", {}),
                "retry_count": result.get("retry_count", 0),
            })

            passed = result.get("test_result", {}).get("passed", False)
            cov = result.get("coverage_report", {})
            cov_pct = cov.get("line_coverage_pct", "N/A")
            status = "✅ 通过" if passed else "❌ 失败"
            logger.info("结果: %s | 覆盖率: %s%%", status, cov_pct)
            print(f"  {status} | 覆盖率: {cov_pct}%")

        # 生成报告
        if args.report:
            from app.reports.generator import (
                generate_html_report,
                generate_junit_report,
                generate_markdown_report,
            )
            if args.format == "html":
                path = generate_html_report(results, project_name=args.project_path or "CLI")
                print(f"📊 HTML 报告: {path}")
            elif args.format == "junit":
                path = generate_junit_report(results)
                print(f"📊 JUnit 报告: {path}")
            elif args.format == "markdown":
                path = generate_markdown_report(results)
                print(f"📊 Markdown 报告: {path}")

        return 0
    except Exception as e:
        logger.error("生成失败: %s", e, exc_info=True)
        print(f"❌ 生成失败: {e}", file=sys.stderr)
        return 1


def cmd_list_cases(args: argparse.Namespace) -> int:
    """列出用例。"""
    cases = list_cases(status=args.status, priority=args.priority, limit=args.limit)
    if args.json:
        print("json: " + json.dumps(cases, ensure_ascii=False, indent=2, default=str))
    else:
        if not cases:
            print("📭 暂无用例")
            return 0
        for c in cases:
            status_mark = {
                "draft": "📝", "review": "🔍", "approved": "✅", "deprecated": "🗑"
            }.get(c.get("status", ""), "❓")
            tags = ", ".join(c.get("tags", []))
            print(f"{status_mark} [{c.get('priority', '')}] {c.get('title', '')} "
                  f"(id={c.get('id', '')})")
            if tags:
                print(f"   标签: {tags}")
    return 0


def cmd_defects(args: argparse.Namespace) -> int:
    """列出缺陷。"""
    defects = list_defects(status=args.status, severity=args.severity, limit=args.limit)
    if args.json:
        print("json: " + json.dumps(defects, ensure_ascii=False, indent=2, default=str))
    else:
        if not defects:
            print("📭 暂无缺陷")
            return 0
        for d in defects:
            sev_mark = {
                "blocker": "🔴", "critical": "⛔", "major": "🟠", "minor": "🟡"
            }.get(d.get("severity", ""), "❓")
            print(f"{sev_mark} [{d.get('status', '')}] {d.get('title', '')} "
                  f"(id={d.get('id', '')})")
            if d.get("file_path"):
                print(f"   文件: {d['file_path']}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Test Generation Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # generate
    gen = subparsers.add_parser("generate", help="生成测试用例")
    gen.add_argument("--source-file", help="单个源文件路径")
    gen.add_argument("--project-path", help="项目目录路径（递归扫描）")
    gen.add_argument("--output-dir", default="output", help="输出目录")
    gen.add_argument("--test-type", default="functional",
                     choices=["functional", "api", "ui", "performance",
                              "security", "compatibility", "reliability"],
                     help="测试类型: functional/api/ui/performance/security/compatibility/reliability")
    gen.add_argument("--no-script", action="store_true", help="仅生成结构化用例，不生成 pytest 脚本")
    gen.add_argument("--report", action="store_true", help="生成报告")
    gen.add_argument("--format", choices=["html", "junit", "markdown"], default="html",
                     help="报告格式")
    gen.set_defaults(func=cmd_generate)

    # list-cases
    lc = subparsers.add_parser("list-cases", help="列出测试用例")
    lc.add_argument("--status", help="按状态过滤 (draft/review/approved/deprecated)")
    lc.add_argument("--priority", help="按优先级过滤 (P0/P1/P2/P3)")
    lc.add_argument("--limit", type=int, default=50, help="最多返回数量")
    lc.add_argument("--json", action="store_true", help="JSON 输出")
    lc.set_defaults(func=cmd_list_cases)

    # defects
    df = subparsers.add_parser("defects", help="列出缺陷")
    df.add_argument("--status", help="按状态过滤 (open/in_progress/fixed/closed/wont_fix)")
    df.add_argument("--severity", help="按严重程度过滤 (blocker/critical/major/minor)")
    df.add_argument("--limit", type=int, default=50, help="最多返回数量")
    df.add_argument("--json", action="store_true", help="JSON 输出")
    df.set_defaults(func=cmd_defects)

    try:
        args = parser.parse_args()
    except SystemExit:
        parser.print_help()
        return 0

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
