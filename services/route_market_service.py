"""
学习路线市场服务
提供路线模板的浏览、搜索、采纳（直接使用/AI个性化）、评分等功能。

数据存储结构:
  data/route_market/
    routes/          - 路线模板 JSON 文件
    market_index.json - 市场索引（分类、统计）
    user_adoptions/  - 用户采纳记录


"""

import os
import json
import re
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "route_market")
_ROUTES_DIR = os.path.join(_BASE_DIR, "routes")
_ADOPTIONS_DIR = os.path.join(_BASE_DIR, "user_adoptions")

_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_\-\.]+$')

# 专用线程池（文件 I/O）
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="route_market")


def _safe_id(name: str) -> str:
    if not _SAFE_ID_RE.match(name):
        raise ValueError(f"非法ID: {name!r}")
    return name


def _ensure_dirs():
    os.makedirs(_ROUTES_DIR, exist_ok=True)
    os.makedirs(_ADOPTIONS_DIR, exist_ok=True)


def _read_json(fpath: str) -> Optional[Any]:
    if not os.path.exists(fpath):
        return None
    with open(fpath, 'r', encoding='utf-8') as f:
        return json.load(f)


def _write_json(fpath: str, data: Any):
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ==================== 路线浏览 ====================

async def list_routes(category: str = "", difficulty: str = "", sort: str = "hot",
                      search: str = "", user_id: str = "") -> List[Dict[str, Any]]:
    """列出市场中的路线模板（不含 phases 详情，用于列表页）。
    
    Args:
        user_id: 如果提供，会在每个路线中返回 adopted_by_user 和 adoption_mode 字段
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, _list_routes_sync, category, difficulty, sort, search, user_id)


def _list_routes_sync(category: str, difficulty: str, sort: str, search: str, user_id: str = "") -> List[Dict[str, Any]]:
    _ensure_dirs()
    routes = []
    if not os.path.isdir(_ROUTES_DIR):
        return routes

    # 如果提供了 user_id，加载该用户的采纳记录
    user_adopted = {}
    if user_id:
        user_adopted = _load_user_adoptions_map(user_id)

    for fname in os.listdir(_ROUTES_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            data = _read_json(os.path.join(_ROUTES_DIR, fname))
            if not data:
                continue
        except Exception:
            continue

        if category and data.get("category", "") != category:
            continue
        if difficulty and data.get("difficulty", "") != difficulty:
            continue
        if search:
            kw = search.lower()
            searchable = (
                data.get("name", "") + data.get("subtitle", "") +
                data.get("description", "") + " ".join(data.get("tags", []))
            ).lower()
            if kw not in searchable:
                continue

        summary = {k: v for k, v in data.items() if k not in ("phases", "reviews")}
        
        # 添加用户采纳状态
        route_id = data.get("route_id", "")
        if user_id and route_id in user_adopted:
            adoption_info = user_adopted[route_id]
            if adoption_info.get("personalized"):
                # AI个性化不标记为"已采纳"
                summary["adopted_by_user"] = False
                summary["adoption_mode"] = None
                summary["adopted_at"] = None
                summary["was_personalized"] = True
            else:
                summary["adopted_by_user"] = True
                summary["adoption_mode"] = "直接使用"
                summary["adopted_at"] = adoption_info.get("adopted_at", "")
        else:
            summary["adopted_by_user"] = False
            summary["adoption_mode"] = None
            summary["adopted_at"] = None
        
        routes.append(summary)

    if sort == "hot":
        routes.sort(key=lambda r: r.get("stats", {}).get("adoptions", 0), reverse=True)
    elif sort == "rating":
        routes.sort(key=lambda r: r.get("stats", {}).get("rating", 0), reverse=True)
    elif sort == "new":
        routes.sort(key=lambda r: r.get("stats", {}).get("created_at", ""), reverse=True)

    return routes


async def get_route_detail(route_id: str) -> Optional[Dict[str, Any]]:
    """获取路线完整详情（含 phases 和每阶段的具体资源）。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, _get_route_detail_sync, route_id)


def _get_route_detail_sync(route_id: str) -> Optional[Dict[str, Any]]:
    _ensure_dirs()
    safe_id = _safe_id(route_id)
    fpath = os.path.join(_ROUTES_DIR, f"{safe_id}.json")
    try:
        return _read_json(fpath)
    except Exception as e:
        print(f"⚠️ [RouteMarket] 读取路线详情失败: {e}")
        return None


async def get_categories() -> List[str]:
    """获取所有路线分类。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, _get_categories_sync)


def _get_categories_sync() -> List[str]:
    _ensure_dirs()
    categories = set()
    if not os.path.isdir(_ROUTES_DIR):
        return []
    for fname in os.listdir(_ROUTES_DIR):
        if not fname.endswith(".json"):
            continue
        try:
            data = _read_json(os.path.join(_ROUTES_DIR, fname))
            if data and data.get("category"):
                categories.add(data["category"])
        except Exception:
            continue
    return sorted(categories)


# ==================== 路线采纳 ====================

async def adopt_route(route_id: str, user_id: str, personalize: bool = False) -> Dict[str, Any]:
    """
    采纳路线为用户的学习计划。
    1. 写入 data/plan_configs/ — Conduct 层计划选区元数据
    2. 调用 StudyPlanner.save_plan_async() — 写入 user_features/{user_id}/study_plans/ 真实计划存储
    3. personalize=False 时预填充 ContentStore — 用户直接使用真实资源；
       personalize=True 时不预填充 — 由 Agent 根据用户特征动态生成
    """
    loop = asyncio.get_event_loop()

    # Step 1: 读取路线 + 写入 plan_configs（同步文件 I/O，放线程池）
    result, route = await loop.run_in_executor(
        _EXECUTOR, _adopt_route_write_configs, route_id, user_id, personalize
    )
    if not result.get("success"):
        return result

    # Step 2: 通过 StudyPlanner 写入真实计划存储（异步）
    plan_id = result["plan_id"]
    try:
        # 直接加载 study_planner.py，绕过 memory/__init__.py（避免级联导入 chromadb）
        import importlib.util
        _sp_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "memory", "study_planner.py")
        _sp_spec = importlib.util.spec_from_file_location("_study_planner_direct", _sp_path)
        _sp_mod = importlib.util.module_from_spec(_sp_spec)
        _sp_spec.loader.exec_module(_sp_mod)
        StudyPlanner = _sp_mod.StudyPlanner

        planner = StudyPlanner()

        # 将路线模板转换为 StudyPlanner 兼容的 plan 格式
        plan = _route_to_study_plan(route, plan_id, personalize)

        saved = await planner.save_plan_async(
            user_id, plan,
            plan_id=plan_id,
            make_active=True,
            root_dir=plan_id,
        )

        if not saved:
            print(f"⚠️ [RouteMarket] StudyPlanner 保存失败，plan_id={plan_id}")
        else:
            print(f"✅ [RouteMarket] 已持久化到 study_plans: {plan_id}")
    except Exception as e:
        print(f"⚠️ [RouteMarket] StudyPlanner 保存异常: {e}")
        import traceback
        traceback.print_exc()

    # Step 3: personalize=False 时预填充 ContentStore（直接使用真实资源）
    if not personalize:
        try:
            await prefill_content_store(user_id, route)
            print(f"✅ [RouteMarket] 已预填充 ContentStore（直接使用模式）")
        except Exception as e:
            print(f"⚠️ [RouteMarket] 预填充失败（不影响主流程）: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"ℹ️ [RouteMarket] AI个性化模式，跳过预填充（由 Agent 动态生成）")

    return result


async def prefill_content_store(user_id: str, route: Dict[str, Any]):
    """
    预填充 ContentStore，将路线模板中的真实资源写入缓存。
    PhaseBridge 检查缓存时会命中，用户打开阶段即可直接使用。
    预填充所有 7 种资源类型，模板中没有对应资源的类型会生成默认内容。
    """
    # 直接加载 content_store.py（绕过 memory/__init__.py 的 chromadb 依赖）
    import importlib.util
    _cs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "memory", "content_store.py")
    _cs_spec = importlib.util.spec_from_file_location("_content_store_direct", _cs_path)
    _cs_mod = importlib.util.module_from_spec(_cs_spec)
    _cs_spec.loader.exec_module(_cs_mod)
    ContentStore = _cs_mod.ContentStore

    store = ContentStore()
    phases = route.get("phases", [])

    # 所有需要预填充的资源类型
    ALL_RESOURCE_TYPES = ["video", "doc", "practice", "mindmap", "extension", "ppt", "question"]

    for phase_idx, phase in enumerate(phases):
        resources = phase.get("resources", {})
        phase_name = phase.get("name", f"阶段{phase_idx + 1}")

        # 为每个知识点预填充所有资源类型
        for kp in phase.get("knowledge_points", []):
            for res_type in ALL_RESOURCE_TYPES:
                cache_key = f"p{phase_idx}_{res_type}_{kp}"

                # 获取模板中对应类型的资源（没有则空列表）
                type_resources = resources.get(res_type + "s", resources.get(res_type, []))

                # 根据类型构建资源数据
                if res_type == "video":
                    data = _build_video_resource(type_resources, kp, phase_name)
                elif res_type == "doc":
                    data = _build_doc_resource(type_resources, kp, phase_name)
                elif res_type == "practice":
                    data = _build_practice_resource(type_resources, kp, phase_name)
                elif res_type == "mindmap":
                    data = _build_mindmap_resource(type_resources, kp, phase_name)
                elif res_type == "extension":
                    data = _build_extension_resource(type_resources, kp, phase_name)
                elif res_type == "ppt":
                    data = _build_ppt_resource(type_resources, kp, phase_name)
                elif res_type == "question":
                    data = _build_question_resource(type_resources, kp, phase_name)
                else:
                    continue

                await asyncio.get_event_loop().run_in_executor(
                    _EXECUTOR, store.save, user_id, f"phase_{res_type}", cache_key, data
                )


def _build_video_resource(videos: List[Dict], kp: str, phase_name: str) -> Dict[str, Any]:
    """构建视频资源数据（与 video_search_agent 返回格式对齐）"""
    video_list = []
    for i, v in enumerate(videos, 1):
        video_list.append({
            "rank": i,
            "title": v.get("title", f"{kp} 教学视频"),
            "bvid": v.get("bvid", ""),
            "url": v.get("url", ""),
            "duration": v.get("duration", "10:00"),
            "author": v.get("author", "优质UP主"),
            "description": v.get("description", ""),
        })

    return {
        "type": "video",
        "knowledge_point": kp,
        "data": {
            "query": kp,
            "refined_title": f"{phase_name} - {kp}",
            "total_results": len(video_list),
            "videos": video_list,
            "summary": f"为「{kp}」找到 {len(video_list)} 个相关教学视频",
        },
        "_agent": "video",
        "_knowledge_point": kp,
        "from_recommender": False,
        "_prefilled": True,
        "_source": "route_market",
    }


def _build_doc_resource(docs: List[Dict], kp: str, phase_name: str) -> Dict[str, Any]:
    """构建文档资源数据（与 doc_agent 返回格式对齐）"""
    doc = docs[0] if docs else {}

    return {
        "type": "doc",
        "knowledge_point": kp,
        "data": {
            "title": doc.get("title", f"{kp} 学习文档"),
            "content": doc.get("content", doc.get("content_preview", f"# {kp}\n\n本文档详细介绍 {kp} 的核心概念与实践应用。")),
            "content_preview": doc.get("content_preview", ""),
            "pages": doc.get("pages", 5),
            "doc_format": "markdown",
        },
        "_agent": "doc",
        "_knowledge_point": kp,
        "from_recommender": False,
        "_prefilled": True,
        "_source": "route_market",
    }


def _build_practice_resource(practices: List[Dict], kp: str, phase_name: str) -> Dict[str, Any]:
    """构建练习题资源数据（与 practice_agent 返回格式对齐）"""
    practice = practices[0] if practices else {}
    problem_id = practice.get("problem_id", f"P_{abs(hash(kp)) % 0xFFFFFF:06x}")

    return {
        "type": "practice",
        "knowledge_point": kp,
        "problem": {
            "problem_id": problem_id,
            "title": practice.get("title", f"{kp} 编程练习"),
            "description": practice.get("description", f"请实现与 {kp} 相关的功能"),
            "difficulty": practice.get("difficulty", "中等"),
            "knowledge_points": [kp],
            "code_template": practice.get("code_template", "# TODO: 在此实现"),
            "test_cases": practice.get("test_cases", []),
            "solution": practice.get("solution", ""),
            "hint": practice.get("hint", ""),
        },
        "_agent": "practice",
        "_knowledge_point": kp,
        "from_recommender": False,
        "_prefilled": True,
        "_source": "route_market",
    }


def _build_mindmap_resource(mindmaps: List[Dict], kp: str, phase_name: str) -> Dict[str, Any]:
    """构建思维导图资源数据（与 mindmap_agent 返回格式对齐）"""
    mindmap = mindmaps[0] if mindmaps else {}
    topics = mindmap.get("topics", [])

    nodes = [{"id": "root", "label": kp, "x": 400, "y": 300, "level": 0}]
    for i, topic in enumerate(topics[:8]):
        nodes.append({
            "id": f"node_{i}",
            "label": topic,
            "x": 400 + (i % 4) * 150 - 200,
            "y": 300 + (i // 4) * 120 - 60,
            "level": 1,
            "parent": "root",
        })

    return {
        "type": "mindmap",
        "knowledge_point": kp,
        "data": {
            "title": mindmap.get("title", f"{kp} 知识体系"),
            "nodes": nodes,
            "edges": [{"from": "root", "to": n["id"]} for n in nodes[1:]],
            "format": "graph",
        },
        "_agent": "mindmap",
        "_knowledge_point": kp,
        "from_recommender": False,
        "_prefilled": True,
        "_source": "route_market",
    }


def _build_extension_resource(exts, kp, phase_name):
    """构建扩展阅读资源"""
    return {
        "type": "extension",
        "knowledge_point": kp,
        "data": {
            "title": f"{kp} 扩展阅读",
            "content": f"# {kp} 扩展阅读\n\n## 深入学习\n本章节针对「{kp}」提供深度扩展材料...",
            "references": [
                {"title": f"{kp} 权威指南", "url": f"https://example.com/{kp}"},
                {"title": f"{kp} 最佳实践", "url": f"https://example.com/{kp}/best-practices"},
            ],
            "reading_time": 15,
        },
        "_agent": "extension",
        "_knowledge_point": kp,
        "from_recommender": False,
        "_prefilled": True,
        "_source": "route_market",
    }


def _build_ppt_resource(ppts, kp, phase_name):
    """构建PPT资源"""
    return {
        "type": "ppt",
        "knowledge_point": kp,
        "data": {
            "title": f"{kp} 学习PPT",
            "slides": [
                {"page": 1, "title": f"{kp} 概述", "content": f"本节介绍{kp}的核心概念", "notes": ""},
                {"page": 2, "title": "核心要点", "content": f"• {kp}的定义与意义\n• {kp}的基本原理\n• {kp}的应用场景", "notes": ""},
                {"page": 3, "title": "实战示例", "content": f"通过实例理解{kp}的具体应用", "notes": ""},
                {"page": 4, "title": "总结与思考", "content": f"回顾{kp}的关键知识点，思考实际应用", "notes": ""},
            ],
            "style": "新中式科技风",
            "page_count": 4,
        },
        "_agent": "ppt",
        "_knowledge_point": kp,
        "from_recommender": False,
        "_prefilled": True,
        "_source": "route_market",
    }


def _build_question_resource(questions, kp, phase_name):
    """构建测验题资源（选择题/判断题，区别于 practice 的编程题）"""
    return {
        "type": "question",
        "knowledge_point": kp,
        "data": {
            "title": f"{kp} 知识测验",
            "questions": [
                {
                    "id": f"q_{abs(hash(kp + '1')) % 10000:04d}",
                    "type": "multiple_choice",
                    "question": f"关于{kp}，以下哪个说法是正确的？",
                    "options": [
                        f"A. {kp}只适用于特定场景",
                        f"B. {kp}是{phase_name}的核心知识点之一",
                        f"C. {kp}已经过时不需要学习",
                        f"D. {kp}没有任何实际应用",
                    ],
                    "answer": "B",
                    "explanation": f"{kp}是{phase_name}阶段的重要知识点，在实际开发中有广泛应用。",
                },
                {
                    "id": f"q_{abs(hash(kp + '2')) % 10000:04d}",
                    "type": "true_false",
                    "question": f"掌握{kp}对于理解{phase_name}的整体架构至关重要。",
                    "answer": True,
                    "explanation": f"{kp}是{phase_name}的基础，理解它有助于掌握整个阶段的知识体系。",
                },
            ],
        },
        "_agent": "question",
        "_knowledge_point": kp,
        "from_recommender": False,
        "_prefilled": True,
        "_source": "route_market",
    }


def _adopt_route_write_configs(route_id: str, user_id: str, personalize: bool) -> tuple:
    """写入 plan_configs 并返回 (result_dict, route_data)。"""
    _ensure_dirs()
    route = _get_route_detail_sync(route_id)
    if not route:
        return {"success": False, "error": "路线不存在"}, None

    safe_uid = _safe_id(user_id)
    plan_configs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "plan_configs")
    os.makedirs(plan_configs_dir, exist_ok=True)

    plan_id = f"route_{route_id}"

    # 1. 保存用户选择元数据
    config_file = os.path.join(plan_configs_dir, f"{safe_uid}.json")
    config = {
        "user_id": user_id,
        "plan_id": plan_id,
        "plan_name": route.get("name", ""),
        "selected_at": datetime.now().isoformat(),
        "source": "route_market",
        "route_id": route_id,
        "personalized": personalize,
    }
    _write_json(config_file, config)

    # 2. 保存为 options（让 Conduct 层识别计划风格）
    options_file = os.path.join(plan_configs_dir, f"{safe_uid}_options.json")
    plans_list = []
    existing = _read_json(options_file) if os.path.exists(options_file) else None
    if existing:
        plans_list = existing.get("plans", [])

    plan_option = {
        "plan_id": plan_id,
        "name": route.get("name", ""),
        "subtitle": route.get("subtitle", ""),
        "description": route.get("description", ""),
        "style_tags": route.get("tags", []),
        "difficulty": route.get("difficulty", "medium"),
        "focus": route.get("focus", route.get("subtitle", "")),
        "detail": route.get("description", ""),
        "estimated_effort": route.get("estimated_duration", ""),
        "phases": route.get("phases", []),
    }

    replaced = False
    for i, p in enumerate(plans_list):
        if p.get("plan_id") == plan_id:
            plans_list[i] = plan_option
            replaced = True
            break
    if not replaced:
        plans_list.append(plan_option)

    _write_json(options_file, {"plans": plans_list, "user_id": user_id})

    # 3. 记录采纳
    adoption_file = os.path.join(_ADOPTIONS_DIR, f"{safe_uid}.json")
    adoptions = _read_json(adoption_file) if os.path.exists(adoption_file) else []
    if not isinstance(adoptions, list):
        adoptions = []

    adoptions.append({
        "route_id": route_id,
        "route_name": route.get("name", ""),
        "adopted_at": datetime.now().isoformat(),
        "personalized": personalize,
    })
    _write_json(adoption_file, adoptions)

    # 4. 更新路线采纳数
    _increment_adoptions_sync(route_id)

    result = {
        "success": True,
        "plan_id": plan_id,
        "plan_name": route.get("name", ""),
        "personalized": personalize,
    }
    return result, route


def _route_to_study_plan(route: Dict[str, Any], plan_id: str, personalized: bool) -> Dict[str, Any]:
    """
    将路线模板转换为 StudyPlanner 兼容的 plan 格式。
    保留 phases 的完整结构（含 resources），同时添加 StudyPlanner 所需的字段。
    """
    phases = []
    for p in route.get("phases", []):
        phase = {
            "phase": p.get("phase", 1),
            "name": p.get("name", ""),
            "weeks": p.get("weeks", ""),
            "description": p.get("description", ""),
            "knowledge_points": p.get("knowledge_points", []),
            "resource_types": p.get("resource_types", []),
            "milestone": p.get("milestone", ""),
            "estimated_hours": p.get("estimated_hours", 0),
            "difficulty": p.get("difficulty", route.get("difficulty", "medium")),
            "status": "未开始",
            "completed_kps": [],
            # 保留 resources 供 ContentStore 参考（视频/文档/练习/导图的具体资源）
            "resources": p.get("resources", {}),
        }
        phases.append(phase)

    # 如果有个性化标记，更新所有阶段
    if personalized:
        for phase in phases:
            phase["_personalized"] = True
    else:
        # 直接使用模式：扩展 resource_types 为完整的 7 种
        all_types = ["video", "doc", "practice", "mindmap", "extension", "ppt", "question"]
        for phase in phases:
            phase["resource_types"] = list(all_types)

    plan = {
        "plan_id": plan_id,
        "title": route.get("name", ""),
        "total_duration": route.get("estimated_duration", ""),
        "difficulty": route.get("difficulty", "medium"),
        "description": route.get("description", ""),
        "phases": phases,
        "_source": "route_market",
        "_route_id": route.get("route_id", ""),
        "_personalized": personalized,
    }

    # 直接使用模式：添加禁用标记
    if not personalized:
        plan["_direct_use"] = True
        plan["_disable_version_tree"] = True
        plan["_disable_attention_expansion"] = True

    return plan


async def get_user_adoptions(user_id: str) -> List[Dict[str, Any]]:
    """获取用户已采纳的路线列表。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, _get_user_adoptions_sync, user_id)


def _get_user_adoptions_sync(user_id: str) -> List[Dict[str, Any]]:
    _ensure_dirs()
    fpath = os.path.join(_ADOPTIONS_DIR, f"{_safe_id(user_id)}.json")
    result = _read_json(fpath) if os.path.exists(fpath) else []
    return result if isinstance(result, list) else []


# ==================== 评分 ====================

async def rate_route(route_id: str, user_id: str, rating: int, comment: str = "") -> Dict[str, Any]:
    """用户对路线评分。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, _rate_route_sync, route_id, user_id, rating, comment)


def _rate_route_sync(route_id: str, user_id: str, rating: int, comment: str) -> Dict[str, Any]:
    _ensure_dirs()
    route = _get_route_detail_sync(route_id)
    if not route:
        return {"success": False, "error": "路线不存在"}

    rating = max(1, min(5, int(rating)))
    reviews = route.get("reviews", [])

    for r in reviews:
        if r.get("user_id") == user_id:
            r["rating"] = rating
            r["comment"] = comment
            r["updated_at"] = datetime.now().isoformat()
            break
    else:
        reviews.append({
            "user_id": user_id,
            "rating": rating,
            "comment": comment,
            "created_at": datetime.now().isoformat(),
        })

    avg = sum(r["rating"] for r in reviews) / len(reviews) if reviews else 0
    route["reviews"] = reviews
    route.setdefault("stats", {})["rating"] = round(avg, 1)

    fpath = os.path.join(_ROUTES_DIR, f"{_safe_id(route_id)}.json")
    _write_json(fpath, route)

    return {"success": True, "rating": rating, "avg_rating": round(avg, 1)}


# ==================== 内部工具 ====================

def _load_user_adoptions_map(user_id: str) -> Dict[str, Dict]:
    """获取用户已采纳的路线（返回 route_id -> adoption_info 的映射）"""
    safe_uid = _safe_id(user_id)
    adoption_file = os.path.join(_ADOPTIONS_DIR, f"{safe_uid}.json")
    if not os.path.exists(adoption_file):
        return {}
    
    adoptions = _read_json(adoption_file)
    if not isinstance(adoptions, list):
        return {}
    
    # 转换为 route_id -> info 的映射
    result = {}
    for a in adoptions:
        route_id = a.get("route_id", "")
        if route_id:
            result[route_id] = {
                "route_name": a.get("route_name", ""),
                "adopted_at": a.get("adopted_at", ""),
                "personalized": a.get("personalized", False),
            }
    return result


def _increment_adoptions_sync(route_id: str):
    fpath = os.path.join(_ROUTES_DIR, f"{_safe_id(route_id)}.json")
    if not os.path.exists(fpath):
        return
    try:
        data = _read_json(fpath)
        if not data:
            return
        data.setdefault("stats", {})
        data["stats"]["adoptions"] = data["stats"].get("adoptions", 0) + 1
        _write_json(fpath, data)
    except Exception as e:
        print(f"⚠️ [RouteMarket] 更新采纳数失败: {e}")


# ==================== 智能分析学习计划生成路线信息（使用 Agent） ====================

async def auto_generate_route_info(plan_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用 RouteAgent 智能分析学习计划，生成路线市场信息。
    LLM 不可用时自动降级为规则推断。

    Args:
        plan_data: 学习计划数据（含 phases）

    Returns:
        自动生成的路线信息字典
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, _auto_generate_route_info_sync, plan_data)


def _auto_generate_route_info_sync(plan_data: Dict[str, Any]) -> Dict[str, Any]:
    """同步执行智能分析（调用 RouteAgent）"""
    try:
        from Agent.children_agent.route_agent import RouteAgent
        agent = RouteAgent()
        result = agent.analyze_plan(plan_data)
        # 补充默认值
        result.setdefault("estimated_duration", plan_data.get("total_duration", ""))
        result.setdefault("cover_color", "#667eea")
        result.setdefault("cover_icon", "📚")
        return result
    except Exception as e:
        print(f"⚠️ [RouteMarket] Agent 分析失败，使用降级方案: {e}")
        # 降级：使用 RouteAgent 内置的 fallback
        from Agent.children_agent.route_agent import RouteAgent
        agent = RouteAgent()
        return agent._fallback_analyze(plan_data)


# ==================== 智能生成流程图（使用 Agent） ====================

def generate_mermaid_flowchart(route_data: Dict[str, Any]) -> str:
    """
    使用 RouteAgent 智能生成 Mermaid 流程图。
    LLM 不可用时自动降级为规则生成。

    Args:
        route_data: 路线数据（含 phases）

    Returns:
        Mermaid 流程图语法字符串
    """
    try:
        from Agent.children_agent.route_agent import RouteAgent
        agent = RouteAgent()
        return agent.generate_flowchart(route_data)
    except Exception as e:
        print(f"⚠️ [RouteMarket] 流程图 Agent 失败，使用降级方案: {e}")
        from Agent.children_agent.route_agent import RouteAgent
        agent = RouteAgent()
        return agent._fallback_flowchart(route_data)


# ==================== 智能转换学习计划 phases 为路线格式（使用 Agent） ====================

def convert_plan_phases(phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    使用 RouteAgent 将学习计划 phases 转换为路线市场标准格式。

    Args:
        phases: 原始学习计划阶段列表

    Returns:
        转换后的标准 phases 列表
    """
    try:
        from Agent.children_agent.route_agent import RouteAgent
        agent = RouteAgent()
        return agent.convert_phases(phases)
    except Exception as e:
        print(f"️ [RouteMarket] 转换 Agent 失败，使用降级方案: {e}")
        from Agent.children_agent.route_agent import RouteAgent
        agent = RouteAgent()
        return agent._fallback_convert(phases)


# ==================== 发布路线到市场 ====================

async def publish_plan_to_market(user_id: str, plan_data: Dict[str, Any],
                                  route_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    将用户的学习计划发布到路线市场。

    Args:
        user_id: 发布者用户ID
        plan_data: 学习计划数据（含 phases）
        route_info: 路线市场信息（name, subtitle, description, category, tags, difficulty 等）

    Returns:
        {"success": True, "route_id": "..."} 或 {"success": False, "error": "..."}
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, _publish_plan_sync, user_id, plan_data, route_info)


def _publish_plan_sync(user_id: str, plan_data: Dict[str, Any],
                       route_info: Dict[str, Any]) -> Dict[str, Any]:
    """同步执行发布路线到市场"""
    _ensure_dirs()

    # 检查是否已发布过同一计划（防止重复发布）
    plan_id = plan_data.get("plan_id", "")
    if plan_id:
        for fname in os.listdir(_ROUTES_DIR):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(_ROUTES_DIR, fname)
            existing = _read_json(fpath)
            if existing and existing.get("_original_plan_id") == plan_id and existing.get("creator", {}).get("id") == user_id:
                return {"success": False, "error": "该学习计划已发布过，请勿重复发布"}

    # 生成 route_id
    import hashlib
    import time
    raw_id = f"{user_id}_{plan_data.get('plan_id', '')}_{int(time.time())}"
    route_id = "user_" + hashlib.md5(raw_id.encode()).hexdigest()[:12]

    # 使用 Agent 智能转换 phases 格式（从 study_plan 格式转为 route_market 格式）
    phases = convert_plan_phases(plan_data.get("phases", []))

    # 构建路线数据
    route = {
        "route_id": route_id,
        "name": route_info.get("name", plan_data.get("title", "用户分享的学习路线")),
        "subtitle": route_info.get("subtitle", ""),
        "description": route_info.get("description", plan_data.get("description", "")),
        "cover_color": route_info.get("cover_color", "#667eea"),
        "cover_icon": route_info.get("cover_icon", "📚"),
        "category": route_info.get("category", "其他"),
        "tags": route_info.get("tags", []),
        "difficulty": route_info.get("difficulty", "medium"),
        "target_audience": route_info.get("target_audience", ""),
        "estimated_duration": route_info.get("estimated_duration", plan_data.get("total_duration", "")),
        "estimated_hours": sum(p.get("estimated_hours", 0) for p in phases),
        "prerequisites": route_info.get("prerequisites", ""),
        "focus": route_info.get("focus", ""),
        "creator": {
            "id": user_id,
            "name": user_id,
            "avatar": "👤",
        },
        "stats": {
            "adoptions": 0,
            "rating": 0,
            "created_at": datetime.now().isoformat(),
        },
        "reviews": [],
        "phases": phases,
        "_source": "user_published",
        "_original_plan_id": plan_data.get("plan_id", ""),
    }

    # 保存路线文件
    fpath = os.path.join(_ROUTES_DIR, f"{_safe_id(route_id)}.json")
    _write_json(fpath, route)

    print(f"✅ [RouteMarket] 用户 {user_id} 发布路线到市场: {route_id}")

    return {
        "success": True,
        "route_id": route_id,
        "route_name": route["name"],
    }


# ==================== 编辑 / 删除路线 ====================

def delete_route_sync(route_id: str, user_id: str) -> Dict[str, Any]:
    """删除路线（仅发布者本人可删除）"""
    _ensure_dirs()
    fpath = os.path.join(_ROUTES_DIR, f"{_safe_id(route_id)}.json")

    if not os.path.exists(fpath):
        return {"success": False, "error": "路线不存在"}

    route = _read_json(fpath)
    if not route:
        return {"success": False, "error": "路线数据读取失败"}

    # 验证发布者身份
    creator_id = route.get("creator", {}).get("id", "")
    if creator_id != user_id:
        return {"success": False, "error": "只有发布者才能删除此路线"}

    os.remove(fpath)
    print(f"✅ [RouteMarket] 用户 {user_id} 删除路线: {route_id}")

    return {"success": True}


def update_route_sync(route_id: str, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """更新路线信息（仅发布者本人可编辑）"""
    _ensure_dirs()
    fpath = os.path.join(_ROUTES_DIR, f"{_safe_id(route_id)}.json")

    if not os.path.exists(fpath):
        return {"success": False, "error": "路线不存在"}

    route = _read_json(fpath)
    if not route:
        return {"success": False, "error": "路线数据读取失败"}

    # 验证发布者身份
    creator_id = route.get("creator", {}).get("id", "")
    if creator_id != user_id:
        return {"success": False, "error": "只有发布者才能编辑此路线"}

    # 允许更新的字段
    allowed_fields = [
        "name", "subtitle", "description", "cover_color", "cover_icon",
        "category", "tags", "difficulty", "target_audience",
        "estimated_duration", "prerequisites", "focus", "phases",
    ]
    for field in allowed_fields:
        if field in updates:
            route[field] = updates[field]

    _write_json(fpath, route)
    print(f"✅ [RouteMarket] 用户 {user_id} 更新路线: {route_id}")

    return {"success": True, "route": route}
