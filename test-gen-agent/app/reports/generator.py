# app/reports/generator.py
"""
报告中心模块
============
生成测试报告，支持 HTML / JUnit XML / Markdown 三种格式导出。
"""
import json
import os
import time
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional

from app.logging_config import get_logger

logger = get_logger(__name__)

OUTPUT_DIR = "reports"


def ensure_output_dir() -> str:
    """确保报告输出目录存在。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return OUTPUT_DIR


def generate_html_report(
    results: List[Dict[str, Any]],
    project_name: str = "Test Generation",
    title: str = "测试生成报告",
) -> str:
    """
    生成 HTML 格式测试报告，返回文件路径。

    Args:
        results: 每个文件的测试结果列表
        project_name: 项目名称
        title: 报告标题
    """
    ensure_output_dir()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(OUTPUT_DIR, f"report_{timestamp}.html")

    passed = sum(1 for r in results if r.get("test_result", {}).get("passed"))
    failed = len(results) - passed
    total = len(results)

    # 计算覆盖率平均值
    cov_values = [
        r.get("coverage_report", {}).get("line_coverage_pct", 0)
        for r in results
        if r.get("coverage_report", {}).get("line_coverage_pct")
    ]
    avg_cov = round(sum(cov_values) / len(cov_values), 2) if cov_values else 0

    rows_html = []
    for i, r in enumerate(results):
        test_result = r.get("test_result", {})
        cov = r.get("coverage_report", {})
        status_class = "pass" if test_result.get("passed") else "fail"
        status_text = "✅ 通过" if test_result.get("passed") else "❌ 失败"
        cov_pct = cov.get("line_coverage_pct", "N/A")

        rows_html.append(f"""
        <tr class="{status_class}">
            <td>{i+1}</td>
            <td>{r.get('file_path', 'N/A')}</td>
            <td>{r.get('generated_tests', '').count('def test_') if r.get('generated_tests') else 0}</td>
            <td>{status_text}</td>
            <td>{cov_pct}{'%' if isinstance(cov_pct, (int, float)) else ''}</td>
            <td>{r.get('retry_count', 0)}</td>
        </tr>
        """)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {project_name}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: system-ui, sans-serif; background: #0f1117; color: #e6e6e6; padding: 24px; }}
        h1 {{ font-size: 22px; margin-bottom: 16px; color: #4f8cff; }}
        h2 {{ font-size: 16px; margin-bottom: 12px; color: #8a91a8; }}
        .stats {{ display: flex; gap: 16px; margin-bottom: 24px; }}
        .stat-card {{ background: #1a1d27; border: 1px solid #2d3142; border-radius: 10px; padding: 16px 24px; }}
        .stat-card .label {{ font-size: 12px; color: #8a91a8; margin-bottom: 4px; }}
        .stat-card .value {{ font-size: 28px; font-weight: bold; }}
        .stat-card .value.pass {{ color: #4ade80; }}
        .stat-card .value.fail {{ color: #f87171; }}
        .stat-card .value.info {{ color: #4f8cff; }}
        table {{ width: 100%; border-collapse: collapse; background: #1a1d27; border-radius: 10px; overflow: hidden; }}
        th {{ background: #2d3142; padding: 12px; text-align: left; font-size: 13px; color: #8a91a8; }}
        td {{ padding: 12px; border-bottom: 1px solid #2d3142; font-size: 13px; }}
        tr.pass td {{ color: #4ade80; }}
        tr.fail td {{ color: #f87171; }}
        .footer {{ margin-top: 24px; font-size: 12px; color: #5a6070; }}
        .detail-section {{ margin-top: 24px; }}
        .detail-block {{ background: #1a1d27; border: 1px solid #2d3142; border-radius: 10px; padding: 16px; margin-bottom: 16px; }}
        .detail-block h3 {{ font-size: 14px; margin-bottom: 8px; color: #4f8cff; }}
        pre {{ background: #0f1117; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; white-space: pre-wrap; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <h2>项目: {project_name} | 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}</h2>

    <div class="stats">
        <div class="stat-card">
            <div class="label">总文件数</div>
            <div class="value info">{total}</div>
        </div>
        <div class="stat-card">
            <div class="label">通过</div>
            <div class="value pass">{passed}</div>
        </div>
        <div class="stat-card">
            <div class="label">失败</div>
            <div class="value fail">{failed}</div>
        </div>
        <div class="stat-card">
            <div class="label">平均行覆盖率</div>
            <div class="value info">{avg_cov}%</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>文件</th>
                <th>用例数</th>
                <th>状态</th>
                <th>覆盖率</th>
                <th>重试</th>
            </tr>
        </thead>
        <tbody>{''.join(rows_html)}</tbody>
    </table>

    <div class="detail-section">
        <h2>详细输出</h2>
        {"".join(_render_details(results))}
    </div>

    <div class="footer">由 Test Generation Agent 自动生成</div>
</body>
</html>"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("HTML 报告已生成 [path=%s]", report_path)
    return report_path


def _render_details(results: List[Dict[str, Any]]) -> List[str]:
    """渲染详细输出 HTML。"""
    details = []
    for i, r in enumerate(results):
        test_result = r.get("test_result", {})
        cov = r.get("coverage_report", {})
        details.append(f"""
        <div class="detail-block">
            <h3>{i+1}. {r.get('file_path', 'N/A')}</h3>
            <p><strong>状态:</strong> {'通过' if test_result.get('passed') else '失败'}</p>
            <p><strong>覆盖率:</strong> {cov.get('line_coverage_pct', 'N/A')}%</p>
            <p><strong>生成的测试代码:</strong></p>
            <pre>{r.get('generated_tests', '（无）')}</pre>
            <p><strong>测试输出:</strong></p>
            <pre>{test_result.get('stdout', '（无）')[:2000]}</pre>
        </div>
        """)
    return details


def generate_junit_report(results: List[Dict[str, Any]]) -> str:
    """
    生成 JUnit XML 格式测试报告，返回文件路径。
    """
    ensure_output_dir()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(OUTPUT_DIR, f"junit_{timestamp}.xml")

    testsuite = ET.Element("testsuite", {
        "name": "test-generation-agent",
        "tests": str(len(results)),
        "failures": str(sum(1 for r in results if not r.get("test_result", {}).get("passed"))),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })

    for r in results:
        test_result = r.get("test_result", {})
        passed = test_result.get("passed", False)
        tc = ET.SubElement(testsuite, "testcase", {
            "name": r.get("file_path", "unknown"),
            "classname": "TestGeneration",
        })
        if not passed:
            failure = ET.SubElement(tc, "failure", {
                "message": "Test execution failed",
            })
            failure.text = test_result.get("stderr", "")[:2000]

    tree = ET.ElementTree(testsuite)
    tree.write(report_path, encoding="utf-8", xml_declaration=True)
    logger.info("JUnit 报告已生成 [path=%s]", report_path)
    return report_path


def generate_markdown_report(results: List[Dict[str, Any]]) -> str:
    """生成 Markdown 格式报告。"""
    ensure_output_dir()
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(OUTPUT_DIR, f"report_{timestamp}.md")

    lines = [
        "# 测试生成报告",
        "",
        f"- 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 总文件数: {len(results)}",
        f"- 通过: {sum(1 for r in results if r.get('test_result', {}).get('passed'))}",
        f"- 失败: {sum(1 for r in results if not r.get('test_result', {}).get('passed'))}",
        "",
        "| # | 文件 | 状态 | 覆盖率 | 重试 |",
        "|---|------|------|--------|------|",
    ]

    for i, r in enumerate(results):
        test_result = r.get("test_result", {})
        cov = r.get("coverage_report", {})
        status = "✅ 通过" if test_result.get("passed") else "❌ 失败"
        cov_str = cov.get("line_coverage_pct", "N/A")
        lines.append(
            f"| {i+1} | {r.get('file_path', 'N/A')} | {status} | {cov_str}% | {r.get('retry_count', 0)} |"
        )

    lines.extend(["", "---", "", "详细测试代码已保存至 output/ 目录。"])

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info("Markdown 报告已生成 [path=%s]", report_path)
    return report_path
