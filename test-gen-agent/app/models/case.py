# app/models/case.py
"""用例管理 Pydantic 模型。"""
from pydantic import BaseModel, Field
from typing import Optional, List


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="用例标题")
    description: str = Field("", description="用例描述")
    source_code: str = Field("", description="源码")
    test_code: str = Field("", description="测试代码")
    file_path: str = Field("", description="文件路径")
    tags: List[str] = Field([], description="标签")
    status: str = Field("draft", pattern="^(draft|review|approved|deprecated)$")
    priority: str = Field("P2", pattern="^(P0|P1|P2|P3)$")
    requirement_ref: str = Field("", description="需求引用")
    test_type: str = Field("functional", description="测试类型")
    structured_cases: list = Field([], description="结构化用例")


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    source_code: Optional[str] = None
    test_code: Optional[str] = None
    file_path: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = Field(None, pattern="^(draft|review|approved|deprecated)$")
    priority: Optional[str] = Field(None, pattern="^(P0|P1|P2|P3)$")
    requirement_ref: Optional[str] = None
    test_type: Optional[str] = None
    structured_cases: Optional[list] = None


class CasePageQuery(BaseModel):
    keyword: str = Field("", description="搜索关键字")
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)
    status: Optional[str] = None
    priority: Optional[str] = None
    test_type: Optional[str] = None


class CaseRelationAdd(BaseModel):
    related_case_id: str = Field(..., description="关联用例ID")
    relation_type: str = Field("related", description="关联类型")


class CaseDependencyAdd(BaseModel):
    depends_on: str = Field(..., description="依赖用例ID")
    dep_type: str = Field("before", description="依赖类型: before/after")
    description: str = Field("", description="依赖描述")


class CaseReviewSubmit(BaseModel):
    comment: str = Field("", description="评审意见")


class CaseRequirementAdd(BaseModel):
    requirement_id: str = Field(..., description="需求ID")


class CaseRollback(BaseModel):
    version: int = Field(..., ge=1, description="要回滚到的版本号")
