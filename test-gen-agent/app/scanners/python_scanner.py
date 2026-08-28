import ast
from typing import List, Dict, Any
from app.graph.state import AgentState
from app.logging_config import get_logger
logger = get_logger(__name__)


def scan_python_code(source_code: str) -> Dict[str, Any]:
    """
    扫描 Python 源代码，提取函数签名（独立函数，供非 LangGraph 场景使用）。
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        logger.error("源码解析失败 [err=%s]", e)
        return {"functions": []}

    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            params = [
                {"name": a.arg,
                 "annotation": ast.unparse(a.annotation) if a.annotation else None}
                for a in node.args.args
            ]
            functions.append({
                "name": node.name,
                "params": params,
                "returns": ast.unparse(node.returns) if node.returns else None,
                "docstring": ast.get_docstring(node) or "",
            })
    logger.info("扫描完成 [functions=%d]", len(functions))
    return {"functions": functions}


def scan_python_file(state: AgentState) -> dict:
    """LangGraph 节点：扫描源码提取函数签名（兼容原有接口）。"""
    logger.debug("开始扫描源码 [file=%s]", state.get("file_path"))
    result = scan_python_code(state["source_code"])
    signatures = result["functions"]
    logger.info("扫描完成 [file=%s, functions=%d]",
                state.get("file_path"), len(signatures))
    return {"signatures": signatures}
