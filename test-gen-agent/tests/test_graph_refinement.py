"""
test_graph_refinement.py — 测试修复模块单元测试

测试覆盖:
  - 功能: 错误诊断分类
  - 功能: 代码提取
  - 功能: 错误截断
  - 功能: 可恢复性判断
  - 功能: 条件路由判断
  - 异常: LLM 调用失败时的处理
"""

import pytest
from app.graph.refinement import (
    _diagnose_error,
    _extract_code,
    _truncate,
    is_recoverable,
    should_retry,
    REFINE_PROMPT,
    ERROR_PATTERNS,
)


class TestErrorDiagnosis:
    """错误诊断分类测试"""

    def test_diagnose_assertion_error(self):
        """功能: 断言错误诊断"""
        result = {
            "passed": False,
            "stdout": "1 failed",
            "stderr": "AssertionError: assert 1 == 2",
        }
        diagnosis = _diagnose_error(result)
        assert "断言失败" in diagnosis
        assert "1 个用例失败" in diagnosis

    def test_diagnose_import_error(self):
        """功能: 导入错误诊断"""
        result = {
            "passed": False,
            "stdout": "1 error",
            "stderr": "ModuleNotFoundError: No module named 'nonexistent'",
        }
        diagnosis = _diagnose_error(result)
        assert "导入错误" in diagnosis
        assert "1 个用例发生错误" in diagnosis

    def test_diagnose_type_error(self):
        """功能: 类型错误诊断"""
        result = {
            "passed": False,
            "stderr": "TypeError: add() missing 1 required positional argument",
        }
        diagnosis = _diagnose_error(result)
        assert "类型" in diagnosis

    def test_diagnose_syntax_error(self):
        """功能: 语法错误诊断"""
        result = {
            "passed": False,
            "stderr": "SyntaxError: invalid syntax",
        }
        diagnosis = _diagnose_error(result)
        assert "语法" in diagnosis

    def test_diagnose_fixture_error(self):
        """功能: fixture 错误诊断"""
        result = {
            "passed": False,
            "stderr": "fixture 'db' not found",
        }
        diagnosis = _diagnose_error(result)
        assert "fixture" in diagnosis.lower()

    def test_diagnose_mock_error(self):
        """功能: Mock 错误诊断"""
        result = {
            "passed": False,
            "stderr": "AttributeError: Mock object has no attribute 'query'",
        }
        diagnosis = _diagnose_error(result)
        assert "Mock" in diagnosis

    def test_diagnose_name_error(self):
        """功能: 名称错误诊断"""
        result = {
            "passed": False,
            "stderr": "NameError: name 'undefined_var' is not defined",
        }
        diagnosis = _diagnose_error(result)
        assert "未定义" in diagnosis

    def test_diagnose_value_error(self):
        """功能: 值错误诊断"""
        result = {
            "passed": False,
            "stderr": "ValueError: invalid literal for int()",
        }
        diagnosis = _diagnose_error(result)
        assert "取值错误" in diagnosis

    def test_diagnose_key_error(self):
        """功能: 键错误诊断"""
        result = {
            "passed": False,
            "stderr": "KeyError: 'missing_key'",
        }
        diagnosis = _diagnose_error(result)
        assert "键错误" in diagnosis

    def test_diagnose_multiple_errors(self):
        """功能: 多个错误同时诊断"""
        result = {
            "passed": False,
            "stdout": "2 failed, 1 error",
            "stderr": "AssertionError: assert 1 == 2\nImportError: No module named 'x'",
        }
        diagnosis = _diagnose_error(result)
        assert "2 个用例失败" in diagnosis
        assert "1 个用例发生错误" in diagnosis
        assert "断言失败" in diagnosis
        assert "导入错误" in diagnosis

    def test_diagnose_unknown_error(self):
        """功能: 无法分类的错误"""
        result = {
            "passed": False,
            "stderr": "Unknown weird error",
        }
        diagnosis = _diagnose_error(result)
        assert "未能自动分类" in diagnosis


class TestExtractCode:
    """代码提取测试"""

    def test_extract_python_block(self):
        """功能: 提取 Python 代码块"""
        text = '```python\ndef test_foo():\n    assert True\n```'
        result = _extract_code(text)
        assert "def test_foo" in result
        assert "```" not in result

    def test_extract_plain_code_block(self):
        """功能: 提取无语言标记的代码块"""
        text = '```\nprint("hello")\n```'
        result = _extract_code(text)
        assert 'print("hello")' in result

    def test_extract_multiple_blocks_takes_longest(self):
        """功能: 多个代码块取最长"""
        text = '```python\na = 1\n```\n```python\ndef long_test():\n    x = 1\n    y = 2\n    return x + y\n```'
        result = _extract_code(text)
        assert "long_test" in result
        assert "a = 1" not in result

    def test_extract_plain_text(self):
        """功能: 纯文本直接返回"""
        text = "def test_foo(): pass"
        result = _extract_code(text)
        assert result == text

    def test_extract_empty_text(self):
        """边界: 空文本"""
        result = _extract_code("")
        assert result == ""


class TestTruncate:
    """错误输出截断测试"""

    def test_short_text_not_truncated(self):
        """功能: 短文本不截断"""
        text = "short error"
        assert _truncate(text, max_len=100) == text

    def test_long_text_truncated(self):
        """功能: 长文本截断保留尾部"""
        text = "x" * 5000
        result = _truncate(text, max_len=100)
        assert len(result) < 200
        assert "已截断前部" in result
        assert result.endswith("x" * 100)

    def test_truncate_preserves_error_tail(self):
        """功能: 截断保留错误输出尾部（pytest 错误通常在末尾）"""
        text = "prefix" + "x" * 100 + "\nError: the actual error at the end"
        result = _truncate(text, max_len=50)
        assert "the actual error" in result


class TestRecoverability:
    """错误可恢复性测试"""

    def test_assertion_error_recoverable(self):
        """功能: 断言错误可恢复"""
        result = {"passed": False, "stderr": "AssertionError: assert 1 == 2"}
        assert is_recoverable(result) is True

    def test_system_error_not_recoverable(self):
        """功能: SystemError 不可恢复"""
        result = {"passed": False, "stderr": "SystemError: syscall failed"}
        assert is_recoverable(result) is False

    def test_recursion_error_not_recoverable(self):
        """功能: RecursionError 不可恢复"""
        result = {"passed": False, "stderr": "RecursionError: maximum recursion depth"}
        assert is_recoverable(result) is False

    def test_memory_error_not_recoverable(self):
        """功能: MemoryError 不可恢复"""
        result = {"passed": False, "stderr": "MemoryError: out of memory"}
        assert is_recoverable(result) is False

    def test_segmentation_fault_not_recoverable(self):
        """功能: 段错误不可恢复"""
        result = {"passed": False, "stderr": "Segmentation fault (core dumped)"}
        assert is_recoverable(result) is False

    def test_killed_not_recoverable(self):
        """功能: 进程被杀不可恢复"""
        result = {"passed": False, "stderr": "Killed"}
        assert is_recoverable(result) is False

    def test_import_error_recoverable(self):
        """功能: 导入错误可恢复"""
        result = {"passed": False, "stderr": "ImportError: No module named 'x'"}
        assert is_recoverable(result) is True

    def test_type_error_recoverable(self):
        """功能: 类型错误可恢复"""
        result = {"passed": False, "stderr": "TypeError: bad type"}
        assert is_recoverable(result) is True

    def test_empty_result_recoverable(self):
        """边界: 空结果视为可恢复"""
        result = {}
        assert is_recoverable(result) is True


class TestShouldRetry:
    """条件路由测试"""

    def test_passed_goes_to_coverage(self):
        """功能: 测试通过直接到覆盖率分析"""
        state = {"test_result": {"passed": True}}
        assert should_retry(state, max_retries=3) == "coverage_analysis"

    def test_recoverable_error_retries(self):
        """功能: 可恢复错误进入修复"""
        state = {
            "test_result": {"passed": False, "stderr": "AssertionError"},
            "retry_count": 0,
        }
        assert should_retry(state, max_retries=3) == "refinement_node"

    def test_fatal_error_stops(self):
        """功能: 致命错误停止修复"""
        state = {
            "test_result": {"passed": False, "stderr": "MemoryError"},
            "retry_count": 0,
        }
        assert should_retry(state, max_retries=3) == "coverage_analysis"

    def test_max_retries_reached(self):
        """边界: 达到重试上限停止"""
        state = {
            "test_result": {"passed": False, "stderr": "AssertionError"},
            "retry_count": 3,
        }
        assert should_retry(state, max_retries=3) == "coverage_analysis"

    def test_custom_max_retries(self):
        """功能: 自定义重试上限"""
        state = {
            "test_result": {"passed": False, "stderr": "AssertionError"},
            "retry_count": 1,
        }
        assert should_retry(state, max_retries=2) == "refinement_node"
        state["retry_count"] = 2
        assert should_retry(state, max_retries=2) == "coverage_analysis"


class TestRefinePrompt:
    """修复 Prompt 模板测试"""

    def test_prompt_contains_key_sections(self):
        """功能: Prompt 包含必要组成部分"""
        assert "被测源代码" in REFINE_PROMPT
        assert "上一轮生成的测试代码" in REFINE_PROMPT
        assert "可用 Mock 提示" in REFINE_PROMPT
        assert "测试运行错误输出" in REFINE_PROMPT
        assert "错误分类诊断" in REFINE_PROMPT
        assert "只返回完整" in REFINE_PROMPT

    def test_error_patterns_cover_common_errors(self):
        """功能: 错误模式覆盖常见类型"""
        patterns = ERROR_PATTERNS
        assert any("ModuleNotFoundError" in p for p in patterns)
        assert any("AssertionError" in p for p in patterns)
        assert any("SyntaxError" in p for p in patterns)
        assert any("TypeError" in p for p in patterns)
        assert any("ValueError" in p for p in patterns)
        assert any("KeyError" in p for p in patterns)
