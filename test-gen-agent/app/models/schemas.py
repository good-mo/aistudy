# app/models/schemas.py
"""共享 Pydantic 数据模型（从 main.py 迁移）。"""
from typing import Optional, List
from pydantic import BaseModel


class ChatRequest(BaseModel):
    source_code: str
    file_path: str = "demo.py"
    test_type: str = "functional"
    generate_script: bool = True


class CaseRequest(BaseModel):
    title: str
    description: str = ""
    source_code: str = ""
    test_code: str = ""
    file_path: str = ""
    tags: List[str] = []
    status: str = "draft"
    priority: str = "P2"
    requirement_ref: str = ""
    test_type: str = "functional"
    structured_cases: list = []


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    source_code: Optional[str] = None
    test_code: Optional[str] = None
    file_path: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    requirement_ref: Optional[str] = None
    test_type: Optional[str] = None
    structured_cases: Optional[list] = None


class DefectRequest(BaseModel):
    title: str
    description: str = ""
    severity: str = "major"
    file_path: str = ""
    test_case_id: str = ""
    error_snippet: str = ""
    assignee: str = ""


class DefectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    file_path: Optional[str] = None
    test_case_id: Optional[str] = None
    error_snippet: Optional[str] = None
    assignee: Optional[str] = None


class ProjectScanRequest(BaseModel):
    project_path: str


class ReportRequest(BaseModel):
    file_path: Optional[str] = None
    format: str = "html"


class ApiDefinitionRequest(BaseModel):
    name: str
    method: str = "GET"
    path: str = ""
    protocol: str = "HTTP"
    description: str = ""
    request_headers: Optional[dict] = None
    request_params: Optional[dict] = None
    request_body: str = ""
    request_body_type: str = "json"
    response_code: str = "200"
    response_headers: Optional[dict] = None
    response_body: str = ""
    response_body_type: str = "json"
    tags: Optional[List[str]] = None


class ApiTestCaseRequest(BaseModel):
    name: str
    definition_id: Optional[str] = None
    method: str = "GET"
    path: str = ""
    request_headers: Optional[dict] = None
    request_params: Optional[dict] = None
    request_body: str = ""
    request_body_type: str = "json"
    assertions: Optional[list] = None
    pre_scripts: Optional[list] = None
    post_scripts: Optional[list] = None
    pre_sql: str = ""
    post_sql: str = ""
    variables: Optional[dict] = None
    environment_id: Optional[str] = None
    timeout: int = 30
    retry_count: int = 0


class ScenarioRequest(BaseModel):
    name: str
    description: str = ""
    steps: Optional[list] = None
    environment_id: Optional[str] = None


class MockServiceRequest(BaseModel):
    name: str
    method: str = "GET"
    path: str = ""
    response_code: int = 200
    response_headers: Optional[dict] = None
    response_body: str = ""
    delay_ms: int = 0


class EnvironmentRequest(BaseModel):
    name: str
    description: str = ""
    base_url: str = ""
    headers: Optional[dict] = None
    variables: Optional[dict] = None


class AssertionRuleRequest(BaseModel):
    name: str
    rule_type: str = ""
    target: str = ""
    expression: str = ""
    expected: str = ""
    description: str = ""


class ApiDebugRequest(BaseModel):
    method: str = "GET"
    url: str = ""
    headers: Optional[dict] = None
    params: Optional[dict] = None
    body: str = ""
    body_type: str = "json"
    timeout: int = 30


class ProjectRequest(BaseModel):
    name: str
    description: str = ""
    repo_url: str = ""
    language: str = ""
    path: str = ""


__all__ = [
    "ChatRequest",
    "CaseRequest",
    "CaseUpdate",
    "DefectRequest",
    "DefectUpdate",
    "ProjectScanRequest",
    "ReportRequest",
    "ApiDefinitionRequest",
    "ApiTestCaseRequest",
    "ScenarioRequest",
    "MockServiceRequest",
    "EnvironmentRequest",
    "AssertionRuleRequest",
    "ApiDebugRequest",
    "ProjectRequest",
]
