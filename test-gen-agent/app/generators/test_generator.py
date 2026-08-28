from app.config import get_llm, settings
from app.graph.state import AgentState
from app.llm.retry import invoke_llm_with_retry
from app.logging_config import get_logger
import os
import re
from app.generators.test_types import get_default_test_type
from app.generators.prompts import get_prompt, get_script_generation_prompt

logger = get_logger(__name__)


# 兼容旧代码：保留原 TEST_PROMPT 导出
TEST_PROMPT = get_prompt("functional")


def _extract_json_array(text: str) -> list:
    """
    从 LLM 返回中提取 JSON 数组。
    优先尝试直接解析；若被 markdown 代码块包裹，则提取代码块内容。
    """
    import json
    import re

    # 先尝试直接解析
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 提取 ```json ... ``` 或 ``` ... ``` 代码块
    blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    for block in blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    # 尝试提取第一个 [ 到最后一个 ] 之间的内容
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError("无法从 LLM 输出中解析结构化测试用例 JSON")


def _extract_code(text: str) -> str:
    """
    从 LLM 返回中提取代码块。
    优先提取 ```python ... ``` 代码块（取最长块）；若无则返回纯文本。
    """
    import re
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip()
    return text.strip()


def _parse_test_type(test_type: str) -> str:
    """确保 test_type 是合法值。"""
    from app.generators.test_types import is_valid_test_type
    if not is_valid_test_type(test_type):
        logger.warning("未知测试类型 %s，回退到 functional", test_type)
        return get_default_test_type()
    return test_type


def generate_structured_cases(state: AgentState) -> dict:
    """
    生成结构化测试用例（方案A第一步）。

    根据 state["test_type"] 选择不同 Prompt 模板，LLM 输出结构化 JSON。
    """
    test_type = _parse_test_type(state.get("test_type") or get_default_test_type())
    prompt_template = get_prompt(test_type)

    # 注意：模板中包含结构化 JSON 示例字面量（含大括号），
    # 不能使用 .format()（会把 JSON 中的 {...} 当作占位符导致 KeyError），
    # 改用 .replace() 仅替换签名/mock 占位符。
    prompt = (
        prompt_template
        .replace("{signatures}", str(state.get("signatures", [])))
        .replace("{mocks}", str(state.get("mocks", {})))
        .replace("{test_type_key}", test_type)
    )
    try:
        sig_count = len(state.get("signatures", []))
        logger.info("开始生成结构化用例 [type=%s, functions=%d]", test_type, sig_count)
        llm = get_llm()
        resp = invoke_llm_with_retry(
            llm.invoke,
            prompt,
            max_retries=settings.llm_rate_limit_max_retries,
            base_delay=settings.llm_rate_limit_base_delay,
            max_delay=settings.llm_rate_limit_max_delay,
            backoff_factor=settings.llm_rate_limit_backoff_factor,
        )
        content = resp.content
        structured_cases = _extract_json_array(content)
        logger.info("结构化用例生成成功 [type=%s, cases=%d]", test_type, len(structured_cases))
        return {
            "structured_cases": structured_cases,
            "test_type": test_type,
        }
    except Exception as e:
        # 结构化生成失败时，记录错误但继续
        logger.error("结构化用例生成失败 [type=%s, err=%s]", test_type, e, exc_info=True)
        raise


def generate_script_from_cases(state: AgentState) -> dict:
    """
    从结构化用例生成 pytest 脚本（方案A第二步，可选）。

    使用结构化用例数据 + 源代码，生成可执行的 pytest 测试。
    """
    structured_cases = state.get("structured_cases", [])
    if not structured_cases:
        return {"generated_tests": ""}

    test_type = _parse_test_type(state.get("test_type") or get_default_test_type())
    prompt = get_script_generation_prompt()

    import json
    prompt_text = prompt.format(
        signatures=state["signatures"],
        mocks=state["mocks"],
        structured_cases=json.dumps(structured_cases, ensure_ascii=False, indent=2),
    )
    try:
        logger.info("从结构化用例生成 pytest 脚本 [type=%s, cases=%d]",
                    test_type, len(structured_cases))
        llm = get_llm()
        resp = invoke_llm_with_retry(
            llm.invoke,
            prompt_text,
            max_retries=settings.llm_rate_limit_max_retries,
            base_delay=settings.llm_rate_limit_base_delay,
            max_delay=settings.llm_rate_limit_max_delay,
            backoff_factor=settings.llm_rate_limit_backoff_factor,
        )
        code = _extract_code(resp.content)
        return {"generated_tests": code}
    except Exception as e:
        # 脚本生成失败不影响已有结构化用例
        logger.warning("pytest 脚本生成失败 [err=%s]", e)
        return {"generated_tests": ""}


def generate_tests(state: AgentState) -> dict:
    """
    LangGraph 节点：生成测试用例（方案A两阶段生成）。

    第一阶段：LLM 生成结构化用例描述
    第二阶段：从结构化用例生成 pytest 测试代码

    根据 state["test_type"] 选择不同的 Prompt 模板：
      - functional  功能测试（默认）
      - api         接口测试
      - ui          UI 测试
      - performance 性能测试
      - security    安全测试
      - compatibility 兼容性测试
      - reliability 可靠性测试
    """
    # 第一阶段：生成结构化用例
    result = generate_structured_cases(state)

    # 第二阶段：从结构化用例生成 pytest 脚本（可选）
    generate_script = state.get("generate_script", True)
    script_result = {}
    if generate_script:
        # 将 structured_cases 合并到 state 中再调用脚本生成
        script_result = generate_script_from_cases({
            **state,
            "structured_cases": result.get("structured_cases", []),
        })

    return {
        **result,
        **script_result,
    }
