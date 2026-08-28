# app/graph/refinement.py
"""
Refinement Module
=================
LangGraph 工作流中的「测试修复优化」节点。

工作机制（self-reflective 循环）：
    test_runner 运行失败
        → refine_tests 节点
            1. 从 pytest 输出解析并分类错误
            2. 将【源代码 + 上一轮测试 + 错误输出 + 诊断 + mock 提示】喂给 LLM
            3. LLM 定向修复（而非整体重写）
            4. 记录修复历史
        → 回到 test_runner 重新验证（条件边控制重试上限）

依赖:
    app.config.get_llm  —— 统一 LLM 工厂（支持多 provider）
"""
import re
from typing import Dict, Any, List

from app.config import get_llm, settings
from app.llm.retry import invoke_llm_with_retry
from app.logging_config import get_logger

logger = get_logger(__name__)

# 使用统一 LLM 配置工厂（多 provider 支持）
# 延迟初始化，避免模块导入时就因缺少 API Key 而崩溃
_llm = None


def _get_llm_instance():
    """延迟获取 LLM 实例。"""
    global _llm
    if _llm is None:
        _llm = get_llm(temperature=0)
    return _llm


# ════════════════════════════════════════════════════════════
# 1. 修复 Prompt 模板
# ════════════════════════════════════════════════════════════


REFINE_PROMPT = """你是资深测试修复工程师。上一轮生成的 pytest 测试运行失败了。
请根据【错误输出】精确修复测试代码，严格遵守以下规则：

1. 只修复导致失败的问题，不要做无关重写。
2. 区分错误类型并对症处理：
   - 断言失败(AssertionError)        → 修正期望值或测试逻辑
   - 导入错误(ImportError/ModuleNotFoundError) → 修正 import 路径
   - mock 错误                       → 修正 patch 目标路径或 return_value
   - 语法/缩进错误(SyntaxError)      → 修正语法
   - fixture 错误                    → 修正 fixture 定义或拼写
   - 类型错误(TypeError)             → 修正调用参数的类型/数量
3. 保留所有已正确通过的用例。
4. 外部依赖必须使用提供的 mock 提示。
5. patch 时应 patch「被测模块中引用的名字」，而非原始定义位置。

【被测源代码】
```python
{source_code}
```

【上一轮生成的测试代码】
```python
{previous_tests}
```
【可用 Mock 提示】

{mock_hint}

【测试运行错误输出】
{error_output}
【错误分类诊断】
{error_diagnosis}
请只返回完整、可运行的修复后测试代码（不要任何解释文字，不要 markdown 说明）。"""


# 2. 错误分类诊断
# 错误特征正则 → 诊断建议（顺序影响优先级）
ERROR_PATTERNS: Dict[str, str] = {
    r"ModuleNotFoundError|ImportError":
        "存在导入错误，请检查模块路径与被测模块的导入方式。",
    r"AssertionError":
        "存在断言失败，请重新核对期望值是否符合函数实际逻辑。",
    r"AttributeError.*Mock|Mock\.AttributeError":
        "Mock 对象属性错误，请检查 patch 目标与 return_value 配置。",
    r"SyntaxError|IndentationError":
        "测试代码存在语法/缩进错误。",
    r"fixture .* not found":
        "缺少 pytest fixture 定义或拼写错误。",
    r"TypeError":
        "调用参数类型/数量不匹配，请检查函数签名调用。",
    r"could not be patched|does not have the attribute|No module named":
        "patch 路径错误，应 patch 被测模块中引用的名字，而非原始定义位置。",
    r"NameError":
        "存在未定义的名称，请检查是否漏写 import 或变量名拼写错误。",
    r"ValueError":
        "存在取值错误，请检查传入参数的取值范围。",
    r"KeyError":
        "存在键错误，请检查字典访问或 mock 返回结构是否正确。",
}


def _diagnose_error(test_result: Dict[str, Any]) -> str:
    """
    从 pytest 输出做轻量错误分类，给 LLM 更明确的修复方向。

    Args:
        test_result: {"passed": bool, "stdout": str, "stderr": str}
    Returns:
        多行诊断文本
    """
    stderr = test_result.get("stderr", "") or ""
    stdout = test_result.get("stdout", "") or ""
    combined = stderr + "\n" + stdout
    diagnoses: List[str] = []

    # 提取失败/错误用例数量
    failed_match = re.search(r"(\d+)\s+failed", combined)
    error_match = re.search(r"(\d+)\s+error", combined)
    if failed_match:
        diagnoses.append(f" • 共 {failed_match.group(1)} 个用例失败。")
    if error_match:
        diagnoses.append(
            f" • 共 {error_match.group(1)} 个用例发生错误"
            f"（collection/setup 阶段）。"
        )

    # 按特征匹配错误类型（去重）
    seen = set()
    for pattern, message in ERROR_PATTERNS.items():
        if re.search(pattern, combined) and message not in seen:
            diagnoses.append(f" • {message}")
            seen.add(message)

    if not diagnoses:
        return " • 未能自动分类，请通读错误输出定位问题。"
    return "\n".join(diagnoses)


# 3. 工具函数
def _extract_code(text: str) -> str:
    """
    从 LLM 返回中提取代码块。
    优先提取 ```python ... ``` 代码块（取最长块）；若无则返回纯文本。
    """
    # 匹配 ```python ... ``` 或 ``` ... ``` 代码块
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip()
    return text.strip()


def _truncate(text: str, max_len: int = 4000) -> str:
    """截断过长的错误输出，保留末尾（pytest 错误通常集中在末尾）。"""
    if len(text) <= max_len:
        return text
    return "...(已截断前部)...\n" + text[-max_len:]


# 4. LangGraph 节点：refine_tests
def refine_tests(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph 节点：修复运行失败的测试。

    输入 state 字段:
        - source_code: 被测源代码
        - generated_tests: 上一轮生成的测试代码
        - test_result: 上一轮运行结果 {passed, stdout, stderr}
        - mocks: mock 配置（含 hint）
        - retry_count: 已重试次数
    返回（合并进 state）:
        - generated_tests: 修复后的测试代码
        - retry_count: +1
        - refine_history: 修复历史记录（追加）
    """
    test_result = state.get("test_result", {}) or {}
    error_output = (
        (test_result.get("stderr", "") or "") + "\n" +
        (test_result.get("stdout", "") or "")
    )

    # 1. 错误诊断
    diagnosis = _diagnose_error(test_result)

    # 2. 组装 prompt
    prompt = REFINE_PROMPT.format(
        source_code=state.get("source_code", ""),
        previous_tests=state.get("generated_tests", ""),
        mock_hint=(state.get("mocks", {}) or {}).get("hint", "无外部依赖。"),
        error_output=_truncate(error_output, 4000),
        error_diagnosis=diagnosis,
    )

    # 3. 调用 LLM 修复（延迟初始化）
    try:
        llm = _get_llm_instance()
        # 使用限流重试机制：遇到 RateLimitError/FreeUsageLimitError 自动退避重试
        resp = invoke_llm_with_retry(
            llm.invoke,
            prompt,
            max_retries=settings.llm_rate_limit_max_retries,
            base_delay=settings.llm_rate_limit_base_delay,
            max_delay=settings.llm_rate_limit_max_delay,
            backoff_factor=settings.llm_rate_limit_backoff_factor,
        )
        refined_code = _extract_code(resp.content)
        # 防止 LLM 返回空内容导致后续验证崩溃
        if not refined_code.strip():
            refined_code = state.get("generated_tests", "")
            diagnosis += "\n • ⚠️ LLM 返回空内容，已保留上一轮测试。"
    except Exception as e:
        # LLM 调用失败时保留原测试，避免中断整个流程
        refined_code = state.get("generated_tests", "")
        diagnosis += f"\n • ⚠️ LLM 修复调用异常: {e}"

    # 4. 记录修复历史（可观测性）
    history: List[Dict[str, Any]] = list(state.get("refine_history", []))
    attempt_no = state.get("retry_count", 0) + 1
    history.append({
        "attempt": attempt_no,
        "diagnosis": diagnosis,
        "error_snippet": error_output[-500:],
    })
    logger.info(f"[Refinement] 第 {attempt_no} 次修复完成")
    logger.info(diagnosis)
    return {
        "generated_tests": refined_code,
        "retry_count": attempt_no,
        "refine_history": history,
    }


# 5. 辅助：判断错误是否可修复（供条件边复用）

def is_recoverable(test_result: Dict[str, Any]) -> bool:
    """
    判断错误是否「可修复」。
    某些致命错误（如运行环境崩溃）不应反复重试，避免浪费 token。

    Returns:
        True -> 值得让 LLM 再修一次
        False -> 不可恢复，应停止重试
    """
    combined = (
        (test_result.get("stderr", "") or "") + "\n" +
        (test_result.get("stdout", "") or "")
    )
    fatal_patterns = [
        r"SystemError",
        r"RecursionError",
        r"MemoryError",
        r"Killed",
        r"Segmentation fault",
    ]
    for pat in fatal_patterns:
        if re.search(pat, combined):
            return False
    return True


# 6. 条件路由函数（可直接在 builder.py 中复用）

def should_retry(state: Dict[str, Any], max_retries: int = 3) -> str:
    """
    test_runner 之后的条件路由：
    - 测试通过 → coverage_analysis
    - 不可恢复的致命错误 → coverage_analysis（放弃修复）
    - 超过重试上限 → coverage_analysis
    - 否则 → refinement_node（继续修复）
    """
    test_result = state.get("test_result", {}) or {}
    if test_result.get("passed"):
        return "coverage_analysis"
    if not is_recoverable(test_result):
        return "coverage_analysis"
    if state.get("retry_count", 0) >= max_retries:
        return "coverage_analysis"
    return "refinement_node"
