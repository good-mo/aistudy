from app.cases.services.common import *


def get_case_full_info(case_id: str) -> Optional[Dict[str, Any]]:
    """获取用例完整信息（含关联/依赖/评审/版本/变更/需求）。"""
    case = _get_base_case(case_id)
    if not case:
        return None
    case["relations"] = list_case_relations(case_id)
    case["dependencies"] = list_case_dependencies(case_id)
    case["reviews"] = get_case_reviews(case_id)
    case["versions"] = list_case_versions(case_id)
    case["changes"] = list_case_changes(case_id)
    case["requirements"] = list_case_requirements(case_id)
    return case

