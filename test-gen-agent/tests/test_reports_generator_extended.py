"""
test_reports_generator_extended.py — 报告生成模块扩展测试

测试覆盖:
  - 功能: HTML 报告生成
  - 功能: JUnit XML 报告生成
  - 功能: Markdown 报告生成
  - 边界: 空结果、单结果、多结果
  - 异常: 异常数据
"""

import os
import re
import xml.etree.ElementTree as ET
import pytest
from app.reports.generator import (
    generate_html_report,
    generate_junit_report,
    generate_markdown_report,
    ensure_output_dir,
    _render_details,
    OUTPUT_DIR,
)


@pytest.fixture
def sample_results():
    return [
        {
            "file_path": "module_a.py",
            "generated_tests": "def test_a(): pass\ndef test_b(): pass",
            "test_result": {"passed": True, "stdout": "ok", "stderr": ""},
            "coverage_report": {"line_coverage_pct": 85.5},
            "retry_count": 0,
        },
        {
            "file_path": "module_b.py",
            "generated_tests": "def test_c(): pass",
            "test_result": {"passed": False, "stdout": "fail", "stderr": "AssertionError: assert 1 == 2"},
            "coverage_report": {"line_coverage_pct": 70.0},
            "retry_count": 2,
        },
    ]


@pytest.fixture(autouse=True)
def cleanup_reports():
    yield
    # 清理生成的测试报告文件
    report_dir = OUTPUT_DIR
    if os.path.isdir(report_dir):
        for f in os.listdir(report_dir):
            if f.startswith(("report_", "junit_")):
                os.remove(os.path.join(report_dir, f))


class TestHTMLReport:
    """HTML 报告生成测试"""

    def test_generate_basic_report(self, sample_results):
        """功能: 生成基本 HTML 报告"""
        path = generate_html_report(sample_results)
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "<html" in content
        assert "测试生成报告" in content
        assert "module_a.py" in content
        assert "module_b.py" in content

    def test_report_shows_statistics(self, sample_results):
        """功能: 统计信息展示"""
        path = generate_html_report(sample_results)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "总文件数" in content
        assert "通过" in content
        assert "失败" in content
        assert "平均行覆盖率" in content

    def test_report_counts(self, sample_results):
        """功能: 通过/失败计数"""
        path = generate_html_report(sample_results)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "1" in re.search(r'class="value pass">(\d+)<', content).group(1)
        assert "1" in re.search(r'class="value fail">(\d+)<', content).group(1)

    def test_report_average_coverage(self, sample_results):
        """功能: 平均覆盖率计算"""
        path = generate_html_report(sample_results)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # 平均覆盖率 = (85.5 + 70.0) / 2 = 77.75
        assert "77.75" in content

    def test_report_empty_results(self):
        """边界: 空结果"""
        path = generate_html_report([])
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "总文件数" in content

    def test_report_custom_title(self, sample_results):
        """功能: 自定义标题"""
        path = generate_html_report(sample_results, title="自定义报告标题")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "自定义报告标题" in content

    def test_report_single_result(self):
        """边界: 单结果"""
        results = [{
            "file_path": "single.py",
            "generated_tests": "",
            "test_result": {"passed": True, "stdout": "", "stderr": ""},
            "coverage_report": {},
            "retry_count": 0,
        }]
        path = generate_html_report(results)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "single.py" in content
        assert "通过" in content


class TestJUnitReport:
    """JUnit XML 报告生成测试"""

    def test_generate_junit_report(self, sample_results):
        """功能: 生成 JUnit 报告"""
        path = generate_junit_report(sample_results)
        assert os.path.exists(path)
        tree = ET.parse(path)
        root = tree.getroot()
        assert root.tag == "testsuite"
        assert root.get("tests") == "2"
        assert root.get("failures") == "1"

    def test_junit_testcases(self, sample_results):
        """功能: testcase 元素"""
        path = generate_junit_report(sample_results)
        tree = ET.parse(path)
        root = tree.getroot()
        testcases = root.findall("testcase")
        assert len(testcases) == 2
        assert testcases[0].get("name") == "module_a.py"
        assert testcases[1].get("name") == "module_b.py"

    def test_junit_failures(self, sample_results):
        """功能: 失败用例包含 failure 元素"""
        path = generate_junit_report(sample_results)
        tree = ET.parse(path)
        root = tree.getroot()
        failures = root.findall("testcase/failure")
        assert len(failures) == 1
        assert "AssertionError" in failures[0].text

    def test_junit_empty_results(self):
        """边界: 空结果"""
        path = generate_junit_report([])
        tree = ET.parse(path)
        root = tree.getroot()
        assert root.get("tests") == "0"
        assert root.get("failures") == "0"

    def test_junit_utf8_declaration(self):
        """功能: UTF-8 XML 声明"""
        path = generate_junit_report([{
            "file_path": "test.py",
            "generated_tests": "",
            "test_result": {"passed": True},
            "coverage_report": {},
            "retry_count": 0,
        }])
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "<?xml version='1.0' encoding='utf-8'?>" in content


class TestMarkdownReport:
    """Markdown 报告生成测试"""

    def test_generate_markdown_report(self, sample_results):
        """功能: 生成 Markdown 报告"""
        path = generate_markdown_report(sample_results)
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "# 测试生成报告" in content
        assert "module_a.py" in content
        assert "module_b.py" in content

    def test_markdown_table_format(self, sample_results):
        """功能: 表格格式正确"""
        path = generate_markdown_report(sample_results)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "| # | 文件 | 状态 | 覆盖率 | 重试 |" in content
        assert "|------|" in content

    def test_markdown_empty_results(self):
        """边界: 空结果"""
        path = generate_markdown_report([])
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "总文件数: 0" in content

    def test_markdown_stats(self, sample_results):
        """功能: 统计信息"""
        path = generate_markdown_report(sample_results)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "总文件数: 2" in content
        assert "通过: 1" in content
        assert "失败: 1" in content


class TestEnsureOutputDir:
    """输出目录测试"""

    def test_directory_created(self):
        """功能: 确保目录存在"""
        path = ensure_output_dir()
        assert os.path.isdir(path)

    def test_directory_is_reports(self):
        """功能: 目录名为 reports"""
        assert ensure_output_dir().endswith("reports")


class TestRenderDetails:
    """详情渲染测试"""

    def test_render_details(self, sample_results):
        """功能: 渲染详情"""
        details = _render_details(sample_results)
        assert len(details) == 2
        assert "module_a.py" in details[0]
        assert "module_b.py" in details[1]

    def test_render_details_content(self, sample_results):
        """功能: 详情包含关键信息"""
        details = _render_details(sample_results)
        assert "状态" in details[0]
        assert "覆盖率" in details[0]
        assert "生成的测试代码" in details[0]
        assert "测试输出" in details[0]

    def test_render_details_empty(self):
        """边界: 空结果"""
        details = _render_details([])
        assert details == []
