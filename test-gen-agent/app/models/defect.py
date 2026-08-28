# app/models/defect.py
"""缺陷管理 Pydantic 模型。"""
from pydantic import BaseModel, Field
from typing import Optional, List


class DefectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("")
    severity: str = Field("major", pattern="^(blocker|critical|major|minor)$")
    status: str = Field("open", pattern="^(open|in_progress|fixed|closed|wont_fix)$")
    file_path: str = Field("")
    test_case_id: str = Field("")
    error_snippet: str = Field("")
    assignee: str = Field("")


class DefectUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    severity: Optional[str] = Field(None, pattern="^(blocker|critical|major|minor)$")
    status: Optional[str] = Field(None, pattern="^(open|in_progress|fixed|closed|wont_fix)$")
    file_path: Optional[str] = None
    test_case_id: Optional[str] = None
    error_snippet: Optional[str] = None
    assignee: Optional[str] = None


class DefectPageQuery(BaseModel):
    keyword: str = Field("")
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)
    status: Optional[str] = None
    severity: Optional[str] = None
