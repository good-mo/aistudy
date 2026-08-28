"""
test_cli.py — CLI 命令测试

测试覆盖:
  - 功能: argparse 解析
  - 功能: 命令分派
  - 异常: 无效参数
  - 边界: 无参数
"""

import sys
import pytest
from unittest.mock import patch, MagicMock


class TestCLICommands:
    """CLI 命令测试"""

    def test_main_no_command(self):
        """边界: 无命令时打印帮助并返回 0"""
        from app.cli import main
        with patch.object(sys, "argv", ["app.cli"]):
            with patch("argparse.ArgumentParser.print_help") as mock_help:
                result = main()
                mock_help.assert_called_once()
                assert result == 0

    def test_main_generate_command(self):
        """功能: generate 命令分派"""
        from app.cli import main
        with patch.object(sys, "argv", ["app.cli", "generate"]):
            with patch("app.cli.cmd_generate") as mock_cmd:
                mock_cmd.return_value = 0
                result = main()
                assert result == 0
                mock_cmd.assert_called_once()

    def test_main_list_cases_command(self):
        """功能: list-cases 命令分派"""
        from app.cli import main
        with patch.object(sys, "argv", ["app.cli", "list-cases"]):
            with patch("app.cli.cmd_list_cases") as mock_cmd:
                mock_cmd.return_value = 0
                result = main()
                assert result == 0
                mock_cmd.assert_called_once()

    def test_main_defects_command(self):
        """功能: defects 命令分派"""
        from app.cli import main
        with patch.object(sys, "argv", ["app.cli", "defects"]):
            with patch("app.cli.cmd_defects") as mock_cmd:
                mock_cmd.return_value = 0
                result = main()
                assert result == 0
                mock_cmd.assert_called_once()

    def test_unknown_command(self):
        """异常: 未知命令"""
        from app.cli import main
        with patch.object(sys, "argv", ["app.cli", "unknown-cmd"]):
            with patch("argparse.ArgumentParser.print_help"):
                result = main()
                assert result == 0


class TestCmdGenerate:
    """generate 命令测试"""

    def test_no_source(self):
        """异常: 无源码输入"""
        from app.cli import cmd_generate
        args = MagicMock()
        args.source_file = None
        args.project_path = None
        args.output_dir = "output"
        args.report = False
        args.format = "html"

        with patch.object(sys, "stdin") as mock_stdin:
            mock_stdin.read.return_value = ""
            result = cmd_generate(args)
            assert result == 1

    def test_invalid_source_file(self):
        """异常: 无效源文件"""
        from app.cli import cmd_generate
        args = MagicMock()
        args.source_file = "/nonexistent/file.py"
        args.project_path = None
        args.output_dir = "output"
        args.report = False
        args.format = "html"

        with patch("app.cli.collect_sources_from_paths", return_value=[]):
            result = cmd_generate(args)
            assert result == 1

    def test_stdin_source(self):
        """功能: 从 stdin 读取源码"""
        from app.cli import cmd_generate
        args = MagicMock()
        args.source_file = None
        args.project_path = None
        args.output_dir = "output"
        args.report = False
        args.format = "html"

        mock_graph = MagicMock()
        mock_graph.ainvoke.return_value = {
            "generated_tests": "def test_add(): pass",
            "test_result": {"passed": True},
            "coverage_report": {"line_coverage_pct": 90.0},
            "retry_count": 0,
        }

        with patch.object(sys, "stdin") as mock_stdin:
            mock_stdin.read.return_value = "def add(a, b): return a + b\n"
            with patch("app.cli.build_graph", return_value=mock_graph):
                result = cmd_generate(args)
                assert result == 0


class TestCmdListCases:
    """list-cases 命令测试"""

    def test_list_empty(self):
        """功能: 空列表"""
        from app.cli import cmd_list_cases
        args = MagicMock()
        args.status = None
        args.priority = None
        args.limit = 50
        args.json = False

        with patch("app.cli.list_cases", return_value=[]):
            with patch("builtins.print") as mock_print:
                result = cmd_list_cases(args)
                assert result == 0
                assert mock_print.called

    def test_list_with_cases(self):
        """功能: 有用例时展示"""
        from app.cli import cmd_list_cases
        args = MagicMock()
        args.status = None
        args.priority = None
        args.limit = 50
        args.json = False

        cases = [
            {"title": "测试用例A", "priority": "P0", "status": "draft", "tags": ["smoke"], "id": "abc123"},
        ]
        with patch("app.cli.list_cases", return_value=cases):
            with patch("builtins.print") as mock_print:
                result = cmd_list_cases(args)
                assert result == 0

    def test_list_json_output(self):
        """功能: JSON 输出"""
        from app.cli import cmd_list_cases
        args = MagicMock()
        args.status = None
        args.priority = None
        args.limit = 50
        args.json = True

        cases = [{"title": "用例", "id": "abc123"}]
        with patch("app.cli.list_cases", return_value=cases):
            with patch("builtins.print") as mock_print:
                result = cmd_list_cases(args)
                assert result == 0
                # JSON 输出应该被调用
                assert any("json" in str(call) for call in mock_print.call_args_list)


class TestCmdDefects:
    """defects 命令测试"""

    def test_defects_empty(self):
        """功能: 空缺陷列表"""
        from app.cli import cmd_defects
        args = MagicMock()
        args.status = None
        args.severity = None
        args.limit = 50
        args.json = False

        with patch("app.cli.list_defects", return_value=[]):
            result = cmd_defects(args)
            assert result == 0

    def test_defects_with_data(self):
        """功能: 有缺陷时展示"""
        from app.cli import cmd_defects
        args = MagicMock()
        args.status = None
        args.severity = None
        args.limit = 50
        args.json = False

        defects = [
            {"title": "Bug A", "severity": "critical", "status": "open", "file_path": "login.py"},
        ]
        with patch("app.cli.list_defects", return_value=defects):
            with patch("builtins.print") as mock_print:
                result = cmd_defects(args)
                assert result == 0

    def test_defects_json(self):
        """功能: JSON 输出"""
        from app.cli import cmd_defects
        args = MagicMock()
        args.status = None
        args.severity = None
        args.limit = 50
        args.json = True

        defects = [{"title": "Bug", "id": "def123"}]
        with patch("app.cli.list_defects", return_value=defects):
            with patch("builtins.print") as mock_print:
                result = cmd_defects(args)
                assert result == 0
                assert any("json" in str(call) for call in mock_print.call_args_list)
