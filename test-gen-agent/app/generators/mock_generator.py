"""
mock_generator.py
基于 AST 规则识别外部依赖，并生成 pytest mock 配置。
"""
import ast
from typing import List, Dict, Any


# ── 规则库：依赖特征 → mock 策略 ──────────────────────────────
DEPENDENCY_RULES = {
    # 数据库
    "database": {
        "modules": {"sqlalchemy", "psycopg2", "pymysql", "sqlite3",
                    "pymongo", "redis", "asyncpg"},
        "call_patterns": {"execute", "query", "commit", "fetchall",
                          "fetchone", "find", "insert_one", "save"},
        "mock_return": "MagicMock()",
    },
    # HTTP / 网络请求
    "http": {
        "modules": {"requests", "httpx", "aiohttp", "urllib"},
        "call_patterns": {"get", "post", "put", "delete", "patch", "request"},
        "mock_return": 'MagicMock(status_code=200, json=lambda: {})',
    },
    # 文件 IO
    "filesystem": {
        "modules": {"os", "pathlib", "shutil", "io"},
        "call_patterns": {"open", "read", "write", "remove", "mkdir", "exists"},
        "mock_return": 'mock_open(read_data="")',
    },
    # 云 SDK
    "cloud": {
        "modules": {"boto3", "google.cloud", "azure"},
        "call_patterns": {"client", "resource", "upload", "download"},
        "mock_return": "MagicMock()",
    },
    # 时间 / 随机（不确定性来源）
    "nondeterministic": {
        "modules": {"datetime", "time", "random", "uuid"},
        "call_patterns": {"now", "today", "time", "random", "uuid4"},
        "mock_return": "MagicMock()",
    },
}


class DependencyDetector(ast.NodeVisitor):
    """遍历 AST，识别 import 与外部调用。"""

    def __init__(self):
        self.imported_modules: Dict[str, str] = {}  # alias -> real module
        self.detected: List[Dict[str, Any]] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name
            self.imported_modules[name] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            name = alias.asname or alias.name
            self.imported_modules[name] = f"{module}.{alias.name}"
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        call_name, target_module = self._resolve_call(node.func)
        if call_name:
            category = self._classify(call_name, target_module)
            if category:
                self.detected.append({
                    "category": category,
                    "call_name": call_name,
                    "target": target_module,
                    "lineno": node.lineno,
                    "mock_return": DEPENDENCY_RULES[category]["mock_return"],
                })
        self.generic_visit(node)

    def _resolve_call(self, func):
        """解析调用名 与 所属模块。"""
        if isinstance(func, ast.Attribute):
            attr = func.attr
            if isinstance(func.value, ast.Name):
                base = func.value.id
                real_module = self.imported_modules.get(base, base)
                return attr, real_module
            return attr, None
        if isinstance(func, ast.Name):
            real = self.imported_modules.get(func.id)
            return func.id, real
        return None, None

    def _classify(self, call_name: str, module: str):
        """根据规则库匹配类别。"""
        module_root = (module or "").split(".")[0]
        for category, rule in DEPENDENCY_RULES.items():
            module_hit = module_root in rule["modules"]
            call_hit = call_name in rule["call_patterns"]
            if module_hit or call_hit:
                return category
        return None


def _build_mock_target(dep: Dict[str, Any]) -> str:
    """生成 patch 目标路径。"""
    if dep["target"]:
        return dep["target"]
    return dep["call_name"]


def generate_mocks(state: dict) -> dict:
    """
    LangGraph 节点：扫描源码，生成 mock 配置。
    输入: state["source_code"]
    输出: state["mocks"]
    """
    source = state["source_code"]
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"mocks": {"error": f"语法错误，无法解析: {e}"}}

    detector = DependencyDetector()
    detector.visit(tree)

    # 去重（按 target + category）
    unique = {}
    for dep in detector.detected:
        key = (dep["category"], dep["target"], dep["call_name"])
        unique[key] = dep

    mock_specs = []
    needs_mock_open = False
    for dep in unique.values():
        target = _build_mock_target(dep)
        if dep["category"] == "filesystem" and dep["call_name"] == "open":
            needs_mock_open = True
        mock_specs.append({
            "patch_target": target,
            "category": dep["category"],
            "return_value": dep["mock_return"],
            "line": dep["lineno"],
        })

    # 生成给 LLM 的 mock 提示文本（用于 test_generator）
    mock_hint = _render_mock_hint(mock_specs, needs_mock_open)

    return {
        "mocks": {
            "specs": mock_specs,
            "hint": mock_hint,
            "needs_mock_open": needs_mock_open,
            "count": len(mock_specs),
        }
    }


def _render_mock_hint(specs: List[Dict], needs_mock_open: bool) -> str:
    """把 mock 规格渲染成可读提示，供 LLM 在生成测试时遵循。"""
    if not specs:
        return "该代码无外部依赖，无需 mock。"

    lines = ["检测到以下外部依赖，请在测试中使用对应 mock：\n"]
    imports = {"from unittest.mock import MagicMock, patch"}
    if needs_mock_open:
        imports.add("from unittest.mock import mock_open")

    for s in specs:
        lines.append(
            f"  • [{s['category']}] 第{s['line']}行 `{s['patch_target']}` "
            f"→ 使用 @patch('{s['patch_target']}') 并设置 "
            f"return_value = {s['return_value']}"
        )

    hint = "\n".join(sorted(imports)) + "\n\n" + "\n".join(lines)
    return hint