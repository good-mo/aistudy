"""
test_mock_generator_extended.py — Mock 生成模块扩展测试

测试覆盖:
  - 功能: 各类依赖检测（HTTP/DB/文件/云SDK/时间随机）
  - 功能: Mock 规格生成
  - 功能: Mock 提示渲染
  - 边界: 无依赖/去重/别名导入
  - 异常: 语法错误
"""

import ast
import pytest
from app.generators.mock_generator import (
    DependencyDetector,
    generate_mocks,
    _build_mock_target,
    _render_mock_hint,
    DEPENDENCY_RULES,
)


class TestDependencyDetector:
    """依赖检测器测试"""

    def test_detect_http_requests(self):
        """功能: 检测 requests HTTP 依赖"""
        source = """
import requests

def fetch_data():
    resp = requests.get('https://api.example.com')
    return resp.json()
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        categories = [d["category"] for d in detector.detected]
        assert "http" in categories
        assert detector.detected[0]["call_name"] == "get"

    def test_detect_httpx(self):
        """功能: 检测 httpx 依赖"""
        source = """
import httpx

def make_request():
    with httpx.Client() as client:
        resp = client.get('/api/data')
        return resp
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) > 0
        assert detector.detected[0]["category"] == "http"

    def test_detect_sqlalchemy_db(self):
        """功能: 检测数据库依赖"""
        source = """
from sqlalchemy import create_engine

def query_data():
    engine = create_engine('sqlite:///test.db')
    conn = engine.connect()
    result = conn.execute("SELECT * FROM users")
    return result
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) > 0
        assert detector.detected[0]["category"] == "database"

    def test_detect_sqlite3(self):
        """功能: 检测 sqlite3 依赖"""
        source = """
import sqlite3

def read_from_db():
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items")
    return cursor.fetchall()
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        categories = [d["category"] for d in detector.detected]
        assert "database" in categories

    def test_detect_filesystem_open(self):
        """功能: 检测文件系统依赖"""
        source = """
def read_file(path):
    with open(path, 'r') as f:
        return f.read()
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) > 0
        assert detector.detected[0]["category"] == "filesystem"

    def test_detect_os_operations(self):
        """功能: 检测 os 模块依赖"""
        source = """
import os

def manage_files(path):
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        categories = [d["category"] for d in detector.detected]
        assert "filesystem" in categories

    def test_detect_boto3_cloud(self):
        """功能: 检测云 SDK 依赖"""
        source = """
import boto3

def upload_to_s3(bucket, key, data):
    s3 = boto3.client('s3')
    s3.upload_file(data, bucket, key)
    return True
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        categories = [d["category"] for d in detector.detected]
        assert "cloud" in categories

    def test_detect_datetime(self):
        """功能: 检测时间依赖"""
        source = """
import datetime

def get_timestamp():
    return datetime.datetime.now().isoformat()
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        categories = [d["category"] for d in detector.detected]
        assert "nondeterministic" in categories

    def test_detect_random(self):
        """功能: 检测随机依赖"""
        source = """
import random

def generate_id():
    return random.randint(1, 1000000)
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        categories = [d["category"] for d in detector.detected]
        assert "nondeterministic" in categories

    def test_alias_import(self):
        """功能: 别名导入检测"""
        source = """
import requests as req

def fetch():
    return req.get('https://api.example.com')
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) > 0
        # 别名应解析到真实模块
        assert "requests" in detector.detected[0]["target"]

    def test_no_dependency(self):
        """边界: 无外部依赖的纯函数"""
        source = """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) == 0

    def test_nested_calls(self):
        """功能: 嵌套调用检测"""
        source = """
import requests

def complex_func():
    result = requests.post(
        'https://api.example.com',
        data=requests.get('https://other.com').content
    )
    return result
"""
        detector = DependencyDetector()
        detector.visit(ast.parse(source))
        assert len(detector.detected) >= 2


class TestGenerateMocks:
    """generate_mocks 函数测试"""

    def test_generate_mocks_normal(self):
        """功能: 正常生成 Mock"""
        state = {
            "source_code": """
import requests

def fetch_data():
    return requests.get('https://api.example.com')
"""
        }
        result = generate_mocks(state)
        assert "mocks" in result
        assert result["mocks"]["count"] >= 1
        assert result["mocks"]["specs"][0]["category"] == "http"
        assert "patch_target" in result["mocks"]["specs"][0]

    def test_generate_mocks_syntax_error(self):
        """异常: 语法错误返回错误信息"""
        result = generate_mocks({"source_code": "def broken(:"})
        assert "error" in result["mocks"]
        assert "语法错误" in result["mocks"]["error"]

    def test_generate_mocks_dedup(self):
        """功能: 相同依赖去重"""
        source = """
import requests

def get_a():
    return requests.get('/a')

def get_b():
    return requests.get('/b')
"""
        result = generate_mocks({"source_code": source})
        # 多次调用相同的 requests.get 应去重
        assert result["mocks"]["count"] >= 1

    def test_generate_mocks_needs_open(self):
        """功能: 文件 open 标记 needs_mock_open"""
        source = """
def read_file(path):
    with open(path, 'r') as f:
        return f.read()
"""
        result = generate_mocks({"source_code": source})
        assert result["mocks"]["needs_mock_open"] is True

    def test_generate_mocks_empty_source(self):
        """边界: 空源码"""
        result = generate_mocks({"source_code": ""})
        assert result["mocks"]["count"] == 0

    def test_generate_mocks_hint_contains_imports(self):
        """功能: Mock 提示包含导入语句"""
        source = """
import requests

def fetch():
    return requests.get('https://api.example.com')
"""
        result = generate_mocks({"source_code": source})
        hint = result["mocks"]["hint"]
        assert "MagicMock" in hint
        assert "patch" in hint

    def test_no_dep_hint(self):
        """功能: 无依赖时的提示"""
        result = generate_mocks({"source_code": "def add(a, b): return a + b\n"})
        assert "无外部依赖" in result["mocks"]["hint"]


class TestBuildMockTarget:
    """Mock 目标构建测试"""

    def test_with_target(self):
        """功能: 有目标模块"""
        dep = {"target": "requests", "call_name": "get", "category": "http"}
        assert _build_mock_target(dep) == "requests"

    def test_without_target(self):
        """功能: 无目标模块使用调用名"""
        dep = {"target": None, "call_name": "get", "category": "http"}
        assert _build_mock_target(dep) == "get"

    def test_alias_module_target(self):
        """功能: 别名模块目标"""
        dep = {"target": "requests", "call_name": "post", "category": "http"}
        assert _build_mock_target(dep) == "requests"


class TestRenderMockHint:
    """Mock 提示渲染测试"""

    def test_render_with_specs(self):
        """功能: 有 Mock 规格时渲染"""
        specs = [{
            "patch_target": "requests",
            "category": "http",
            "return_value": "MagicMock()",
            "line": 3,
        }]
        hint = _render_mock_hint(specs, False)
        assert "MagicMock" in hint
        assert "patch" in hint
        assert "requests" in hint

    def test_render_with_open(self):
        """功能: 需要 mock_open 时包含导入"""
        specs = [{
            "patch_target": "open",
            "category": "filesystem",
            "return_value": 'mock_open(read_data="")',
            "line": 2,
        }]
        hint = _render_mock_hint(specs, True)
        assert "mock_open" in hint

    def test_render_empty(self):
        """边界: 无规格"""
        hint = _render_mock_hint([], False)
        assert "无外部依赖" in hint

    def test_render_contains_sorted_imports(self):
        """功能: 导入语句排序"""
        specs = [
            {"patch_target": "requests", "category": "http", "return_value": "MagicMock()", "line": 1},
            {"patch_target": "sqlalchemy", "category": "database", "return_value": "MagicMock()", "line": 2},
        ]
        hint = _render_mock_hint(specs, False)
        assert "from unittest.mock import MagicMock, patch" in hint


class TestDependencyRules:
    """依赖规则库测试"""

    def test_rules_cover_all_categories(self):
        """功能: 规则覆盖所有类别"""
        expected_categories = {"database", "http", "filesystem", "cloud", "nondeterministic"}
        assert expected_categories == set(DEPENDENCY_RULES.keys())

    def test_database_modules(self):
        """功能: 数据库模块清单"""
        assert "sqlalchemy" in DEPENDENCY_RULES["database"]["modules"]
        assert "psycopg2" in DEPENDENCY_RULES["database"]["modules"]
        assert "pymongo" in DEPENDENCY_RULES["database"]["modules"]
        assert "redis" in DEPENDENCY_RULES["database"]["modules"]

    def test_http_modules(self):
        """功能: HTTP 模块清单"""
        assert "requests" in DEPENDENCY_RULES["http"]["modules"]
        assert "httpx" in DEPENDENCY_RULES["http"]["modules"]
        assert "aiohttp" in DEPENDENCY_RULES["http"]["modules"]

    def test_filesystem_modules(self):
        """功能: 文件系统模块清单"""
        assert "os" in DEPENDENCY_RULES["filesystem"]["modules"]
        assert "pathlib" in DEPENDENCY_RULES["filesystem"]["modules"]
        assert "io" in DEPENDENCY_RULES["filesystem"]["modules"]

    def test_cloud_modules(self):
        """功能: 云模块清单"""
        assert "boto3" in DEPENDENCY_RULES["cloud"]["modules"]

    def test_nondeterministic_modules(self):
        """功能: 非确定性模块清单"""
        assert "datetime" in DEPENDENCY_RULES["nondeterministic"]["modules"]
        assert "random" in DEPENDENCY_RULES["nondeterministic"]["modules"]
        assert "uuid" in DEPENDENCY_RULES["nondeterministic"]["modules"]
