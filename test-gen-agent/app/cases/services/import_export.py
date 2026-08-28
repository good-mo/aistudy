from app.cases.services.common import *


def export_cases_excel(cases: List[Dict[str, Any]]) -> bytes:
    """将用例导出为 Excel 格式（CSV with BOM for Excel compatibility）。"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "标题", "描述", "类型", "优先级", "状态",
                     "标签", "文件路径", "需求关联", "创建时间"])
    for c in cases:
        tags = ",".join(c.get("tags") or [])
        writer.writerow([
            c.get("id", ""),
            c.get("title", ""),
            c.get("description", ""),
            c.get("test_type", "functional"),
            c.get("priority", "P2"),
            c.get("status", "draft"),
            tags,
            c.get("file_path", ""),
            c.get("requirement_ref", ""),
            datetime.fromtimestamp(c.get("created_at") or 0).strftime("%Y-%m-%d %H:%M:%S"),
        ])
    csv_data = output.getvalue()
    # 加 BOM 让 Excel 正确识别 UTF-8
    return ("\ufeff" + csv_data).encode("utf-8")


def export_cases_mindmap(cases: List[Dict[str, Any]]) -> str:
    """将用例导出为 XMind 兼容的 JSON 格式。"""
    from app.cases.management import get_case_mindmap
    mindmap = get_case_mindmap()
    return json.dumps(mindmap, ensure_ascii=False, indent=2)


def import_cases_from_excel(csv_text: str, operator: str = "") -> Dict[str, Any]:
    """从 Excel (CSV) 导入用例。"""
    from app.cases.repository import create_case
    reader = csv.DictReader(io.StringIO(csv_text))
    imported = 0
    errors = []
    for row in reader:
        try:
            title = (row.get("标题") or row.get("title") or "").strip()
            if not title:
                continue
            test_type = (row.get("类型") or row.get("test_type") or "functional").strip()
            priority = (row.get("优先级") or row.get("priority") or "P2").strip()
            tags_str = (row.get("标签") or row.get("tags") or "").strip()
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            case = create_case(
                title=title,
                description=row.get("描述") or row.get("description") or "",
                file_path=row.get("文件路径") or row.get("file_path") or "",
                tags=tags,
                status="draft",
                priority=priority if priority in ("P0", "P1", "P2", "P3") else "P2",
                test_type=test_type,
                requirement_ref=row.get("需求关联") or row.get("requirement_ref") or "",
            )
            imported += 1
            _record_change(case.get("id", ""), CHANGE_IMPORTED, operator=operator)
        except Exception as e:
            errors.append(f"行 {reader.line_num}: {str(e)}")
    return {"imported": imported, "errors": errors}


def import_cases_from_xmind(mindmap_json: str, operator: str = "") -> Dict[str, Any]:
    """从 XMind JSON 导入用例。"""
    from app.cases.repository import create_case
    try:
        data = json.loads(mindmap_json)
    except json.JSONDecodeError as e:
        return {"imported": 0, "errors": [f"JSON 解析失败: {e}"]}

    imported = 0
    errors = []

    def walk_node(node, parent_type=""):
        nonlocal imported
        text = node.get("text", "")
        node_type = node.get("type", "")
        case_id = node.get("case_id", "")
        children = node.get("children", [])

        # 如果是用例节点，创建用例
        if node_type == "case" and case_id:
            existing = _get_base_case(case_id)
            if existing:
                return
            try:
                case = create_case(
                    title=text,
                    status="draft",
                    test_type=parent_type or "functional",
                )
                imported += 1
                _record_change(case.get("id", ""), CHANGE_IMPORTED, operator=operator)
            except Exception as e:
                errors.append(f"节点「{text}」: {str(e)}")
        elif case_id:
            existing = _get_base_case(case_id)
            if not existing:
                try:
                    case = create_case(title=text, status="draft")
                    imported += 1
                except Exception as e:
                    errors.append(f"节点「{text}」: {str(e)}")

        for child in children:
            walk_node(child, parent_type=node.get("id", "") or parent_type)

    walk_node(data)
    return {"imported": imported, "errors": errors}


# ════════════════════════════════════════════════════════════
# 4. 用例评审流程
# ════════════════════════════════════════════════════════════

