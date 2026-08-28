

"""
analyzer.py
运行 coverage.py 测量测试覆盖率，分析未覆盖代码行并定位到函数。
"""
import ast
import json
import os
import tempfile
import subprocess
import shutil
from typing import Dict, List, Any
from app.config import settings
from app.sandbox.docker_runner import run_in_sandbox, _CompletedProcess
from app.logging_config import get_logger

logger = get_logger(__name__)


def _map_lines_to_functions(source_code: str) -> Dict[int, str]:
    """把每一行号映射到所属函数名。"""
    line_func = {}
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return line_func

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            for ln in range(start, end + 1):
                line_func[ln] = node.name
    return line_func


def analyze_coverage(state: dict) -> dict:
    """
    LangGraph 节点：分析覆盖率差距（Docker 沙箱隔离运行）。
    输入: source_code, generated_tests, file_path
    输出: coverage_report
    """
    source = state["source_code"]
    tests = state["generated_tests"]
    raw_name = os.path.basename(state.get("file_path", "module.py"))
    module_name = os.path.splitext(raw_name)[0]

    # 在沙箱/宿主机中运行覆盖率并拿到 JSON 报告
    cov_data = _measure_coverage(source, tests, module_name)

    if not cov_data:
        return {"coverage_report": {"error": "未能生成覆盖率报告，测试可能未运行成功。"}}

    return {"coverage_report": _build_report(cov_data, source, module_name)}


def _measure_coverage(source: str, tests: str, module_name: str):
    """
    执行覆盖率测量，返回 coverage.json 解析后的 dict。

    优先在 Docker 沙箱中通过单个 shell 命令链完成
    （coverage run → coverage json → 输出 JSON 内容），
    Docker 不可用时降级为宿主机子进程执行。
    """
    import subprocess
    from app.sandbox.docker_runner import run_in_sandbox, _docker_available

    use_docker = settings.sandbox_enabled and _docker_available()
    if use_docker:
        # 沙箱内一次性完成 coverage run + json，并从 stdout 取回 JSON
        cmd = [
            "sh", "-c",
            f"coverage run --branch --source={module_name} -m pytest "
            f"test_{module_name}.py -q >/dev/null 2>&1; "
            f"coverage json -o coverage.json >/dev/null 2>&1; "
            f"cat coverage.json 2>/dev/null",
        ]
        result = run_in_sandbox(
            source_code=source,
            test_code=tests,
            module_name=module_name,
            command=cmd,
            timeout=150,
        )
        out = (result.stdout or "").strip()
        if out.startswith("{"):
            try:
                return json.loads(out)
            except Exception:
                pass
        # 沙箱结果不可用，回退宿主机
        logger.warning("沙箱覆盖率数据不可用，降级宿主机测量")

    # 宿主机测量
    workdir = tempfile.mkdtemp(prefix="cov_")
    json_path = os.path.join(workdir, "coverage.json")
    try:
        with open(os.path.join(workdir, f"{module_name}.py"), "w", encoding="utf-8") as f:
            f.write(source)
        with open(os.path.join(workdir, f"test_{module_name}.py"), "w", encoding="utf-8") as f:
            f.write(tests)
        subprocess.run(
            ["coverage", "run", "--branch",
             f"--source={module_name}", "-m", "pytest", f"test_{module_name}.py", "-q"],
            cwd=workdir, capture_output=True, text=True, timeout=120,
        )
        subprocess.run(
            ["coverage", "json", "-o", json_path],
            cwd=workdir, capture_output=True, text=True, timeout=30,
        )
        if os.path.exists(json_path):
            with open(json_path, encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error("覆盖率测量失败 [err=%s]", e, exc_info=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return None


def _build_report(cov_data: dict, source: str, module_name: str) -> Dict[str, Any]:
    """构建可行动的覆盖率差距报告。"""
    files = cov_data.get("files", {})
    # 找到目标文件键
    target_key = next(
        (k for k in files if k.endswith(f"{module_name}.py")), None
    )
    if not target_key:
        return {"error": "覆盖率数据中未找到目标模块。"}

    file_cov = files[target_key]
    summary = file_cov.get("summary", {})
    missing_lines = file_cov.get("missing_lines", [])
    excluded = file_cov.get("excluded_lines", [])

    # 行号 → 函数名
    line_func = _map_lines_to_functions(source)
    source_lines = source.splitlines()

    # 按函数聚合未覆盖行
    gaps_by_func: Dict[str, List[Dict]] = {}
    for ln in missing_lines:
        func = line_func.get(ln, "<module-level>")
        code = source_lines[ln - 1].strip() if 0 < ln <= len(source_lines) else ""
        gaps_by_func.setdefault(func, []).append({"line": ln, "code": code})

    # 生成针对每个函数的改进建议
    suggestions = []
    for func, gaps in gaps_by_func.items():
        gap_lines = [g["line"] for g in gaps]
        suggestions.append({
            "function": func,
            "uncovered_lines": gap_lines,
            "uncovered_snippets": [g["code"] for g in gaps],
            "suggestion": _suggest_for_gaps(gaps),
        })

    total_pct = summary.get("percent_covered", 0)
    branch_pct = _branch_percent(summary)

    return {
        "module": module_name,
        "line_coverage_pct": round(total_pct, 2),
        "branch_coverage_pct": branch_pct,
        "covered_lines": summary.get("covered_lines", 0),
        "missing_lines_count": summary.get("missing_lines", 0),
        "missing_lines": missing_lines,
        "excluded_lines": excluded,
        "gaps_by_function": suggestions,
        "passed_threshold": total_pct >= settings.coverage_threshold,   # 可配置阈值
        "human_summary": _human_summary(total_pct, branch_pct, suggestions),
    }


def _branch_percent(summary: dict) -> float:
    total = summary.get("num_branches", 0)
    covered = summary.get("covered_branches", 0)
    if not total:
        return 100.0
    return round(covered / total * 100, 2)


def _suggest_for_gaps(gaps: List[Dict]) -> str:
    """根据未覆盖代码内容给出补测建议。"""
    snippets = " ".join(g["code"] for g in gaps).lower()
    if any(k in snippets for k in ("raise", "except", "error")):
        return "存在未覆盖的异常分支，建议补充触发异常的测试用例。"
    if any(k in snippets for k in ("if", "elif", "else")):
        return "存在未覆盖的条件分支，建议补充使该分支为真/假的边界用例。"
    if "return" in snippets:
        return "存在未覆盖的返回路径，建议补充对应输入以覆盖该 return。"
    if "for" in snippets or "while" in snippets:
        return "存在未覆盖的循环体，建议补充非空集合/多次迭代的用例。"
    return "存在未覆盖代码，建议补充相应输入以触发这些行。"


def _human_summary(line_pct: float, branch_pct: float, suggestions: List) -> str:
    lines = [
        f"📊 行覆盖率: {line_pct:.1f}% | 分支覆盖率: {branch_pct:.1f}%",
    ]
    if not suggestions:
        lines.append("✅ 全部代码已覆盖！")
    else:
        lines.append(f"⚠️ 有 {len(suggestions)} 个函数存在覆盖缺口：")
        for s in suggestions:
            lines.append(
                f"  • {s['function']}(): 未覆盖行 {s['uncovered_lines']} — {s['suggestion']}"
            )
    return "\n".join(lines)