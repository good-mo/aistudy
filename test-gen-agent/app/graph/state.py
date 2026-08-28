from typing import TypedDict, List, Optional


class AgentState(TypedDict, total=False):
    file_path: str
    source_code: str
    test_type: str             # ← 测试类型: functional/api/ui/performance/security/compatibility/reliability
    generate_script: bool      # ← 是否同时生成 pytest 脚本（方案A）
    signatures: List[dict]
    mocks: dict                # ← mock_generator 输出
    structured_cases: list     # ← 结构化测试用例（方案A）
    generated_tests: str
    test_result: dict
    retry_count: int
    refine_history: List[dict]  # ← refinement 记录
    coverage_report: dict       # ← coverage analyzer 输出
