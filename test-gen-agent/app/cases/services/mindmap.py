from app.cases.services.common import *


def invalidate_mindmap_cache() -> None:
    """用例数据变更时主动清空脑图缓存。"""
    global _mindmap_cache
    _mindmap_cache.clear()


def get_case_mindmap(project_filter: str = "") -> Dict[str, Any]:
    """
    生成用例脑图树形结构。
    返回层级结构：项目 → 测试类型 → 优先级 → 用例列表
    带 10s 内存缓存，避免高频只读请求反复构建树。
    每个 cache_key 独立计时，避免不同 key 相互影响 TTL。
    """
    global _mindmap_cache
    cache_key = f"mindmap:{project_filter}"
    now = time.time()
    cached_entry = _mindmap_cache.get(cache_key)
    if cached_entry is not None and (now - cached_entry[0]) < _MINDMAP_CACHE_TTL:
        return cached_entry[1]

    cases = _list_base_cases(limit=1000)
    if project_filter:
        cases = [c for c in cases if project_filter in (c.get("file_path") or "")]

    # 构建树
    tree = {
        "id": "root",
        "text": "测试用例库",
        "children": [],
    }

    # 按测试类型分组
    type_groups: Dict[str, List[Dict]] = {}
    for c in cases:
        tt = c.get("test_type") or "functional"
        type_groups.setdefault(tt, []).append(c)

    test_type_names = {
        "functional": "功能测试", "api": "接口测试", "ui": "UI 测试",
        "performance": "性能测试", "security": "安全测试",
        "compatibility": "兼容性测试", "reliability": "可靠性测试",
    }

    for tt, tcases in type_groups.items():
        type_node = {
            "id": f"type_{tt}",
            "text": f"{test_type_names.get(tt, tt)} ({len(tcases)})",
            "children": [],
        }
        # 按优先级分组
        for prio in ["P0", "P1", "P2", "P3"]:
            pcases = [c for c in tcases if (c.get("priority") or "P2") == prio]
            if pcases:
                prio_node = {
                    "id": f"prio_{prio}",
                    "text": f"{prio} 优先级 ({len(pcases)})",
                    "children": [],
                }
                for c in pcases:
                    prio_node["children"].append({
                        "id": c["id"],
                        "text": c.get("title", ""),
                        "status": c.get("status", "draft"),
                        "case_id": c["id"],
                        "type": "case",
                    })
                type_node["children"].append(prio_node)
        tree["children"].append(type_node)

    _mindmap_cache[cache_key] = (time.time(), tree)
    return tree


# ════════════════════════════════════════════════════════════
# 3. 用例导入/导出（Excel / XMind JSON）
# ════════════════════════════════════════════════════════════

