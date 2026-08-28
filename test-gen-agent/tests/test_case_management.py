"""
测试用例高级管理模块测试
========================
覆盖：用例关联 / 脑图视图 / 导入导出 / 评审流程 / 依赖关系 /
      回收站 / 版本管理 / 变更记录 / 需求关联
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("LLM_PROVIDER", "local")

from app.cases.repository import create_case, get_case, update_case
from app.cases import management as mgmt


@pytest.fixture
def sample_case():
    """创建一个临时用例供测试使用。"""
    case = create_case(title="测试用例管理-接口测试", test_type="api", priority="P1")
    yield case
    try:
        mgmt.purge_case(case["id"])
    except Exception:
        pass


@pytest.fixture
def related_case():
    """创建第二个用例用于关联测试。"""
    case = create_case(title="测试用例管理-场景测试", test_type="functional", priority="P0")
    yield case
    try:
        mgmt.purge_case(case["id"])
    except Exception:
        pass


class TestCaseRelations:
    """用例关联（接口/场景/性能）测试。"""

    def test_add_relation(self, sample_case, related_case):
        rel = mgmt.add_case_relation(sample_case["id"], related_case["id"], "related")
        assert rel["duplicated"] is False
        assert rel["id"]

    def test_duplicate_relation(self, sample_case, related_case):
        mgmt.add_case_relation(sample_case["id"], related_case["id"], "related")
        rel = mgmt.add_case_relation(sample_case["id"], related_case["id"], "related")
        assert rel["duplicated"] is True

    def test_list_relations(self, sample_case, related_case):
        mgmt.add_case_relation(sample_case["id"], related_case["id"], "related")
        relations = mgmt.list_case_relations(sample_case["id"])
        assert len(relations) == 1
        assert relations[0]["related_title"] == "测试用例管理-场景测试"

    def test_remove_relation(self, sample_case, related_case):
        mgmt.add_case_relation(sample_case["id"], related_case["id"], "related")
        removed = mgmt.remove_case_relation(sample_case["id"], related_case["id"])
        assert removed is True
        assert len(mgmt.list_case_relations(sample_case["id"])) == 0

    def test_relation_self_error(self, sample_case):
        with pytest.raises(ValueError):
            mgmt.add_case_relation(sample_case["id"], sample_case["id"])


class TestCaseMindmap:
    """用例脑图视图测试。"""

    def test_get_mindmap(self, sample_case, related_case):
        tree = mgmt.get_case_mindmap()
        assert tree["id"] == "root"
        assert tree["text"] == "测试用例库"
        assert len(tree["children"]) >= 1

    def test_mindmap_structure(self, sample_case, related_case):
        tree = mgmt.get_case_mindmap()
        # 找到 api 类型节点
        api_nodes = [n for n in tree["children"] if n["id"] == "type_api"]
        assert len(api_nodes) >= 1
        # API 类型节点下应有优先级分组
        assert len(api_nodes[0]["children"]) >= 1


class TestCaseImportExport:
    """用例导入/导出测试。"""

    def test_export_excel(self, sample_case):
        data = mgmt.export_cases_excel([sample_case])
        assert isinstance(data, bytes)
        assert b"title" in data or b"\xe6\xa0\x87\xe9\xa2\x98" in data  # title 或 标题

    def test_import_excel(self):
        csv_text = "标题,类型,优先级,标签\n导入测试用例,api,P1,smoke\n导入测试用例2,functional,P2,regression"
        result = mgmt.import_cases_from_excel(csv_text)
        assert result["imported"] >= 1
        assert not result["errors"]

    def test_export_mindmap(self, sample_case):
        data = mgmt.export_cases_mindmap([sample_case])
        parsed = json.loads(data)
        assert parsed["id"] == "root"

    def test_import_xmind(self):
        mindmap_json = json.dumps({
            "id": "root", "text": "测试用例库",
            "children": [{
                "id": "type_api", "text": "接口测试",
                "children": [
                    {"id": "case1", "text": "导入的接口用例", "case_id": "case_import_1", "type": "case"}
                ]
            }]
        })
        result = mgmt.import_cases_from_xmind(mindmap_json)
        assert result["imported"] >= 0  # 因为 case_id 已存在时跳过


class TestCaseReview:
    """用例评审流程测试。"""

    def test_submit_for_review(self, sample_case):
        result = mgmt.submit_for_review(sample_case["id"], reviewer="admin", comment="请评审")
        assert result["review_status"] == mgmt.REVIEW_STATUS_PENDING
        case = get_case(sample_case["id"])
        assert case["status"] == "review"

    def test_approve_review(self, sample_case):
        mgmt.submit_for_review(sample_case["id"], reviewer="admin")
        result = mgmt.approve_review(sample_case["id"], reviewer="qa_lead", comment="通过")
        assert result["review_status"] == mgmt.REVIEW_STATUS_APPROVED
        case = get_case(sample_case["id"])
        assert case["status"] == "approved"

    def test_reject_review(self, sample_case):
        mgmt.submit_for_review(sample_case["id"], reviewer="admin")
        result = mgmt.reject_review(sample_case["id"], reviewer="qa_lead", comment="需修改")
        assert result["review_status"] == mgmt.REVIEW_STATUS_REJECTED
        case = get_case(sample_case["id"])
        assert case["status"] == "draft"

    def test_get_reviews(self, sample_case):
        mgmt.submit_for_review(sample_case["id"], reviewer="admin")
        reviews = mgmt.get_case_reviews(sample_case["id"])
        assert len(reviews) == 1
        assert reviews[0]["reviewer"] == "admin"


class TestCaseDependency:
    """用例依赖关系测试。"""

    def test_add_dependency(self, sample_case, related_case):
        dep = mgmt.add_case_dependency(
            sample_case["id"], related_case["id"], "before", "前置场景"
        )
        assert dep["duplicated"] is False
        assert dep["id"]

    def test_self_dependency_error(self, sample_case):
        with pytest.raises(ValueError):
            mgmt.add_case_dependency(sample_case["id"], sample_case["id"])

    def test_list_dependencies(self, sample_case, related_case):
        mgmt.add_case_dependency(sample_case["id"], related_case["id"], "before")
        deps = mgmt.list_case_dependencies(sample_case["id"])
        assert len(deps) == 1
        assert deps[0]["dep_title"] == "测试用例管理-场景测试"

    def test_remove_dependency(self, sample_case, related_case):
        mgmt.add_case_dependency(sample_case["id"], related_case["id"], "before")
        removed = mgmt.remove_case_dependency(sample_case["id"], related_case["id"])
        assert removed is True
        assert len(mgmt.list_case_dependencies(sample_case["id"])) == 0


class TestCaseRecycleBin:
    """用例回收站测试。"""

    def test_soft_delete(self, sample_case):
        deleted = mgmt.soft_delete_case(sample_case["id"], deleted_by="admin", reason="不再需要")
        assert deleted is True
        trash = mgmt.list_trash_cases()
        assert len(trash) >= 1

    def test_restore(self, sample_case):
        mgmt.soft_delete_case(sample_case["id"], deleted_by="admin")
        restored = mgmt.restore_case(sample_case["id"])
        assert restored is True
        case = get_case(sample_case["id"])
        assert case["status"] == "draft"

    def test_purge(self, sample_case):
        mgmt.soft_delete_case(sample_case["id"], deleted_by="admin")
        purged = mgmt.purge_case(sample_case["id"])
        assert purged is True
        assert get_case(sample_case["id"]) is None


class TestCaseVersion:
    """用例版本管理测试。"""

    def test_create_version_on_create(self, sample_case):
        versions = mgmt.list_case_versions(sample_case["id"])
        assert len(versions) >= 1
        assert versions[0]["version"] >= 1

    def test_create_version_on_update(self, sample_case):
        mgmt.list_case_versions(sample_case["id"])  # initial
        update_case(sample_case["id"], title="更新后的标题")
        versions = mgmt.list_case_versions(sample_case["id"])
        assert len(versions) >= 2

    def test_get_version(self, sample_case):
        versions = mgmt.list_case_versions(sample_case["id"])
        version = mgmt.get_case_version(sample_case["id"], versions[0]["version"])
        assert version is not None
        assert "snapshot" in version

    def test_rollback(self, sample_case):
        update_case(sample_case["id"], title="新标题")
        versions = mgmt.list_case_versions(sample_case["id"])
        # 回滚到第一个版本
        oldest = versions[-1]
        rolled = mgmt.rollback_case(sample_case["id"], oldest["version"])
        assert rolled is True
        case = get_case(sample_case["id"])
        # 标题应恢复为初始版本的内容
        assert case["title"] != "新标题"


class TestCaseChangeLog:
    """用例变更记录测试。"""

    def test_change_log_created(self, sample_case):
        changes = mgmt.list_case_changes(sample_case["id"])
        assert len(changes) >= 1
        # 变更记录中应包含 created 动作
        created_changes = [c for c in changes if c["action"] == mgmt.CHANGE_CREATED]
        assert len(created_changes) >= 1

    def test_change_log_updated(self, sample_case):
        update_case(sample_case["id"], title="变更标题")
        changes = mgmt.list_case_changes(sample_case["id"])
        update_changes = [c for c in changes if c["action"] == mgmt.CHANGE_UPDATED]
        assert len(update_changes) >= 1


class TestCaseRequirement:
    """用例关联需求测试。"""

    def test_add_requirement(self, sample_case):
        result = mgmt.add_case_requirement(
            sample_case["id"], "JIRA-1001", "jira", "登录功能需求"
        )
        assert result["duplicated"] is False
        assert result["id"]

    def test_add_tapd_requirement(self, sample_case):
        result = mgmt.add_case_requirement(
            sample_case["id"], "TAPD-2001", "tapd", "支付流程"
        )
        assert result["duplicated"] is False

    def test_list_requirements(self, sample_case):
        mgmt.add_case_requirement(sample_case["id"], "JIRA-1001", "jira")
        reqs = mgmt.list_case_requirements(sample_case["id"])
        assert len(reqs) == 1
        assert reqs[0]["requirement_id"] == "JIRA-1001"

    def test_remove_requirement(self, sample_case):
        mgmt.add_case_requirement(sample_case["id"], "JIRA-1001", "jira")
        removed = mgmt.remove_case_requirement(sample_case["id"], "JIRA-1001")
        assert removed is True
        assert len(mgmt.list_case_requirements(sample_case["id"])) == 0


class TestCaseFullInfo:
    """用例完整信息测试。"""

    def test_get_full_info(self, sample_case, related_case):
        # 添加各种关联数据
        mgmt.add_case_relation(sample_case["id"], related_case["id"], "related")
        mgmt.add_case_dependency(sample_case["id"], related_case["id"], "before")
        mgmt.submit_for_review(sample_case["id"], reviewer="admin")
        mgmt.add_case_requirement(sample_case["id"], "JIRA-1001", "jira")

        full = mgmt.get_case_full_info(sample_case["id"])
        assert full is not None
        assert len(full["relations"]) >= 1
        assert len(full["dependencies"]) >= 1
        assert len(full["reviews"]) >= 1
        assert len(full["versions"]) >= 1
        assert len(full["changes"]) >= 1
        assert len(full["requirements"]) >= 1
