# app/apitest/scenario_runner.py
"""接口场景编排执行引擎

按顺序执行场景中的步骤，支持：
- 调用接口用例（step type=case）
- 调用接口定义（step type=definition）
- 逻辑控制器（loop/condition/wait/transaction）
- 变量在步骤间传递（前一步提取的变量供后一步引用）
"""
import json
from typing import Any, Dict, List

from app.logging_config import get_logger
from app.apitest import store, engine

logger = get_logger(__name__)


def _resolve_step_request(step: Dict[str, Any], definition: Dict[str, Any],
                          case: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
    """解析步骤的请求对象，合并定义、用例与环境。"""
    if case and case.get("request"):
        req = json.loads(case["request"])
    elif definition:
        req = {
            "protocol": definition.get("protocol", "HTTP"),
            "method": definition.get("method", "GET"),
            "path": definition.get("path", ""),
            "headers": definition.get("headers", {}),
            "body": definition.get("body", ""),
            "query": definition.get("query", {}),
            "params": definition.get("params", {}),
        }
    else:
        req = dict(step.get("request") or {})

    req.setdefault("protocol", definition.get("protocol", "HTTP") if definition else "HTTP")
    req.setdefault("method", step.get("method", "GET"))
    # 应用变量
    req = engine.render_request_vars(req, variables)
    return req


def run_scenario(scenario: Dict[str, Any], env_override: str = "") -> Dict[str, Any]:
    """执行场景，返回执行结果。env_override 可覆盖场景环境。"""
    steps = scenario.get("steps") or []
    env = None
    env_id = env_override or scenario.get("environment_id") or ""
    if env_id:
        env = store.get_environment(env_id)

    variables = {}
    step_results = []
    all_passed = True

    for idx, step in enumerate(steps):
        stype = step.get("type", "case")
        result = {"index": idx, "type": stype, "name": step.get("name", f"步骤{idx+1}"), "passed": False}

        if stype == "controller":
            ctrl = dict(step.get("controller") or {})
            ctrl.setdefault("type", "loop")
            cr = engine.evaluate_logic_controller(ctrl, {"vars": variables})
            result.update({"passed": cr["passed"], "message": cr["message"], "iterations": cr.get("iterations")})
            all_passed = all_passed and cr["passed"]
        elif stype in ("case", "definition"):
            # 解析要执行的接口
            definition = None
            case = None
            if step.get("case_id"):
                case = store.get_api_case(step["case_id"])
                if case and case.get("api_definition_id"):
                    definition = store.get_definition(case["api_definition_id"])
            elif step.get("definition_id"):
                definition = store.get_definition(step["definition_id"])

            if not definition and not case:
                result["message"] = "未找到对应的接口定义或用例"
                step_results.append(result)
                all_passed = False
                continue

            # 前置脚本
            pre_scripts = step.get("pre_scripts") or (case.get("pre_scripts") if case else []) or []
            for sp in pre_scripts:
                engine.execute_script(sp, {"vars": variables})

            # 解析请求
            req = _resolve_step_request(step, definition, case, variables)
            # 合并环境：步骤环境优先，其次 case 自带环境，最后场景环境
            step_env = env
            if not step_env and case and case.get("environment_id"):
                step_env = store.get_environment(case["environment_id"])
            req = engine.merge_environment(req, step_env)

            # 执行请求
            resp = engine.execute_request(req)

            # 断言
            asserts = step.get("asserts") or (case.get("asserts") if case else []) or []
            if asserts:
                ar = engine.evaluate_asserts(asserts, resp)
                result["asserts"] = ar
                result["passed"] = ar["passed"]
                all_passed = all_passed and ar["passed"]
            else:
                result["passed"] = resp.get("ok", False)
                all_passed = all_passed and result["passed"]

            # 变量提取
            var_rules = step.get("variables") or (case.get("variables") if case else []) or []
            if var_rules:
                extracted = engine.extract_variables_from_response(resp, var_rules)
                variables.update(extracted)
                result["extracted"] = extracted

            result["status_code"] = resp.get("status_code")
            result["elapsed_ms"] = resp.get("elapsed_ms", 0)
            result["message"] = f"{definition.get('method','GET') if definition else 'HTTP'} {req.get('path','')}"
            if resp.get("error"):
                result["error"] = resp["error"]

            # 后置脚本
            post_scripts = step.get("post_scripts") or (case.get("post_scripts") if case else []) or []
            for sp in post_scripts:
                engine.execute_script(sp, {"vars": variables, "response": resp})

        step_results.append(result)

    return {
        "scenario_id": scenario.get("id"),
        "name": scenario.get("name"),
        "passed": all_passed,
        "total_steps": len(step_results),
        "passed_steps": sum(1 for s in step_results if s.get("passed")),
        "steps": step_results,
        "final_variables": variables,
    }
