"""
test_coverage_analyzer.py — 覆盖率分析模块单元测试

测试覆盖:
  - 功能: 行号到函数名映射
  - 功能: 覆盖率报告构建
  - 功能: 分支覆盖率计算
  - 功能: 覆盖率补测建议
  - 功能: 人类可读摘要
  - 异常: 目标模块未找到
"""

import pytest
from app.coverage.analyzer import (
    _map_lines_to_functions,
    _build_report,
    _branch_percent,
    _suggest_for_gaps,
    _human_summary,
)


class TestMapLinesToFunctions:
    """行号到函数名映射测试"""

    def test_map_simple_functions(self):
        """功能: 简单函数映射"""
        source = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
        mapping = _map_lines_to_functions(source)
        assert mapping[1] == "foo"
        assert mapping[2] == "foo"
        assert mapping[4] == "bar"
        assert mapping[5] == "bar"

    def test_map_class_methods(self):
        """功能: 类方法映射"""
        source = "class MyClass:\n    def method1(self):\n        return 1\n    def method2(self):\n        return 2\n"
        mapping = _map_lines_to_functions(source)
        # method1 和 method2 都应该被映射
        names = set(mapping.values())
        assert "method1" in names
        assert "method2" in names

    def test_map_multiline_function(self):
        """功能: 多行函数映射"""
        source = "def long_func(a):\n    if a > 0:\n        return 1\n    return 0\n"
        mapping = _map_lines_to_functions(source)
        for line in range(1, 5):
            assert mapping[line] == "long_func"

    def test_map_async_function(self):
        """功能: 异步函数映射"""
        source = "async def fetch_data():\n    return await api()\n"
        mapping = _map_lines_to_functions(source)
        assert mapping[1] == "fetch_data"
        assert mapping[2] == "fetch_data"

    def test_syntax_error_returns_empty(self):
        """异常: 语法错误返回空映射"""
        assert _map_lines_to_functions("def broken(:") == {}

    def test_empty_source(self):
        """边界: 空源码"""
        assert _map_lines_to_functions("") == {}


class TestBuildReport:
    """覆盖率报告构建测试"""

    @pytest.fixture
    def sample_cov_data(self):
        return {
            "files": {
                "test_module.py": {
                    "summary": {
                        "percent_covered": 85.5,
                        "covered_lines": 100,
                        "missing_lines": 20,
                        "num_branches": 10,
                        "covered_branches": 8,
                    },
                    "missing_lines": [5, 10, 15],
                    "excluded_lines": [],
                }
            }
        }

    def test_build_report_basic(self, sample_cov_data):
        """功能: 基本报告构建"""
        source = "def f1():\n    return 1\ndef f2():\n    return 2\n"
        report = _build_report(sample_cov_data, source, "test_module")
        assert report["line_coverage_pct"] == 85.5
        assert report["branch_coverage_pct"] == 80.0
        assert report["passed_threshold"] is True
        assert report["covered_lines"] == 100

    def test_build_report_missing_lines(self, sample_cov_data):
        """功能: 缺失行正确标记"""
        source = "def f1():\n    return 1\ndef f2():\n    return 2\n"
        report = _build_report(sample_cov_data, source, "test_module")
        assert 5 in report["missing_lines"]
        assert 10 in report["missing_lines"]
        assert 15 in report["missing_lines"]

    def test_build_report_gaps_by_function(self, sample_cov_data):
        """功能: 按函数聚合未覆盖行"""
        source = "def foo():\n    return 1\n\ndef bar():\n    return 2\n\ndef baz():\n    return 3\n"
        report = _build_report(sample_cov_data, source, "test_module")
        assert len(report["gaps_by_function"]) > 0
        # 每个 gap 包含函数名、未覆盖行和建议
        for gap in report["gaps_by_function"]:
            assert "function" in gap
            assert "uncovered_lines" in gap
            assert "suggestion" in gap

    def test_target_module_not_found(self):
        """异常: 目标模块不在覆盖率数据中"""
        cov_data = {"files": {"other.py": {}}}
        report = _build_report(cov_data, "source", "target_module")
        assert "error" in report

    def test_zero_coverage(self):
        """边界: 零覆盖率"""
        cov_data = {
            "files": {
                "test_module.py": {
                    "summary": {
                        "percent_covered": 0,
                        "covered_lines": 0,
                        "missing_lines": 100,
                        "num_branches": 0,
                        "covered_branches": 0,
                    },
                    "missing_lines": [1, 2, 3],
                    "excluded_lines": [],
                }
            }
        }
        report = _build_report(cov_data, "def f():\n    return 1\n", "test_module")
        assert report["line_coverage_pct"] == 0.0
        assert report["passed_threshold"] is False

    def test_full_coverage(self):
        """边界: 100% 覆盖率"""
        cov_data = {
            "files": {
                "test_module.py": {
                    "summary": {
                        "percent_covered": 100,
                        "covered_lines": 50,
                        "missing_lines": 0,
                        "num_branches": 0,
                        "covered_branches": 0,
                    },
                    "missing_lines": [],
                    "excluded_lines": [],
                }
            }
        }
        report = _build_report(cov_data, "def f():\n    return 1\n", "test_module")
        assert report["line_coverage_pct"] == 100.0
        assert report["passed_threshold"] is True
        assert report["missing_lines"] == []


class TestBranchPercent:
    """分支覆盖率计算测试"""

    def test_no_branches_returns_100(self):
        """边界: 无分支返回 100%"""
        assert _branch_percent({"num_branches": 0, "covered_branches": 0}) == 100.0

    def test_full_branch_coverage(self):
        """功能: 全分支覆盖"""
        assert _branch_percent({"num_branches": 10, "covered_branches": 10}) == 100.0

    def test_partial_branch_coverage(self):
        """功能: 部分分支覆盖"""
        assert _branch_percent({"num_branches": 10, "covered_branches": 5}) == 50.0

    def test_zero_branches_covered(self):
        """边界: 零分支覆盖"""
        assert _branch_percent({"num_branches": 8, "covered_branches": 0}) == 0.0

    def test_rounding(self):
        """功能: 百分比四舍五入"""
        result = _branch_percent({"num_branches": 3, "covered_branches": 1})
        assert result == 33.33


class TestSuggestForGaps:
    """覆盖率补测建议测试"""

    def test_suggest_raise_branch(self):
        """功能: 异常分支建议"""
        gaps = [{"code": "raise ValueError('error')"}]
        suggestion = _suggest_for_gaps(gaps)
        assert "异常分支" in suggestion

    def test_suggest_condition_branch(self):
        """功能: 条件分支建议"""
        gaps = [{"code": "if x > 0:"}]
        suggestion = _suggest_for_gaps(gaps)
        assert "条件分支" in suggestion

    def test_suggest_return_path(self):
        """功能: 返回路径建议"""
        gaps = [{"code": "return result"}]
        suggestion = _suggest_for_gaps(gaps)
        assert "返回路径" in suggestion

    def test_suggest_loop(self):
        """功能: 循环体建议"""
        gaps = [{"code": "for item in items:"}]
        suggestion = _suggest_for_gaps(gaps)
        assert "循环体" in suggestion

    def test_generic_suggestion(self):
        """功能: 通用建议"""
        gaps = [{"code": "x = 42"}]
        suggestion = _suggest_for_gaps(gaps)
        assert "未覆盖代码" in suggestion


class TestHumanSummary:
    """人类可读摘要测试"""

    def test_summary_with_gaps(self):
        """功能: 有覆盖率缺口时的摘要"""
        suggestions = [{
            "function": "foo",
            "uncovered_lines": [1, 2],
            "suggestion": "补充测试",
        }]
        summary = _human_summary(80.5, 70.0, suggestions)
        assert "80.5%" in summary
        assert "70.0%" in summary
        assert "1 个函数存在覆盖缺口" in summary
        assert "foo" in summary

    def test_summary_no_gaps(self):
        """功能: 无缺口时的摘要"""
        summary = _human_summary(100.0, 100.0, [])
        assert "100.0%" in summary
        assert "全部代码已覆盖" in summary

    def test_summary_multiple_gaps(self):
        """功能: 多个缺口"""
        suggestions = [
            {"function": "foo", "uncovered_lines": [1], "suggestion": "a"},
            {"function": "bar", "uncovered_lines": [2], "suggestion": "b"},
        ]
        summary = _human_summary(70.0, 60.0, suggestions)
        assert "2 个函数存在覆盖缺口" in summary
