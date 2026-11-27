"""
Java 结果适配器 — 将 MasterController 的原始嵌套结果转换为 Java 后端可直接使用的整洁 JSON。

当 /chat SSE 流推送完毕后，自动调用此模块将结果转换并缓存。
Java 后端通过 /chat-json 接口获取转换结果并更新数据库。
"""

from typing import Dict, Optional, Any
import threading


# ==================== 缓存存储 ====================

_JAVA_RESULTS: Dict[str, dict] = {}  # key: user_id → 最新转换结果
_JAVA_RESULTS_LOCK = threading.Lock()


def get_java_result(user_id: str) -> Optional[dict]:
    """获取缓存的 Java 友好 JSON"""
    with _JAVA_RESULTS_LOCK:
        return _JAVA_RESULTS.get(user_id)


def set_java_result(user_id: str, result: dict) -> None:
    """存储 Java 友好 JSON"""
    with _JAVA_RESULTS_LOCK:
        _JAVA_RESULTS[user_id] = result


# ==================== 提取辅助 ====================

def _extract_suggestion_warning(result: Dict[str, Any]) -> str:
    """从任意深度的结果结构中提取 suggestion_warning"""
    if not isinstance(result, dict):
        return ""
    if result.get("suggestion_warning"):
        return result["suggestion_warning"]
    for key in ("data", "problem", "practice"):
        child = result.get(key)
        if isinstance(child, dict):
            if child.get("suggestion_warning"):
                return child["suggestion_warning"]
            deeper = _extract_suggestion_warning(child)
            if deeper:
                return deeper
        if key == "data" and isinstance(child, dict):
            practice = child.get("practice")
            if isinstance(practice, dict) and practice.get("suggestion_warning"):
                return practice["suggestion_warning"]
    return ""


# ==================== 核心转换 ====================

def transform_to_java_result(raw_result: dict) -> dict:
    """
    将 MasterController 的原始结果（任意 layer）转换为 Java 后端可直接使用的整洁 JSON。

    支持的 layer 类型：
      - conduct  → 提取 practice/doc/question/... 等资源（按 task_type 分派）
      - des      → 提取 student_data/analysis/guidance，或 need_more_info 追问
      - unrecognized → 提取 message
      - unknown  → 提取 error
    
    返回格式（以 practice 为例）：
      { "success": true, "task_type": "practice", "problem": {...}, "suggestion_warning": "", "needs_confirmation": false }
    """
    if not isinstance(raw_result, dict):
        return {"success": False, "error": "无效的结果格式"}

    # 从顶层获取 success, suggestion_warning, metadata
    success = raw_result.get("success", False)
    suggestion_warning = raw_result.get("suggestion_warning", "")
    top_metadata = raw_result.get("metadata", {})

    # 从 data 中获取 layer
    data_layer = raw_result.get("data", {})
    if not isinstance(data_layer, dict):
        return {"success": False, "error": "data 层无效"}

    layer = data_layer.get("layer", "unknown")

    # ==================== Conduct 层 ====================
    if layer == "conduct":
        return {
            "success": success,
            "data": data_layer,
            "suggestion_warning": suggestion_warning,
            "metadata": top_metadata
        }

    # ==================== Chat 层 ====================
    if layer == "chat":
        return {
            "success": success,
            "data": data_layer,
            "suggestion_warning": suggestion_warning,
            "metadata": top_metadata
        }

    # ==================== DES 层 ====================
    if layer == "des":
        if not isinstance(data_layer, dict):
            return {"success": False, "error": "des 层 data 无效"}

        des_status = data_layer.get("status", "")

        if des_status == "need_more_info":
            return {
                "success": success,
                "layer": layer,
                "des_status": "need_more_info",
                "message": data_layer.get("message", ""),
                "extracted_info": data_layer.get("extracted_info", {}),
                "follow_up_questions": data_layer.get("follow_up_questions", []),
                "missing_fields": data_layer.get("missing_fields", []),
            }

        if des_status == "success":
            return {
                "success": success,
                "layer": layer,
                "des_status": "completed",
                "student_data": data_layer.get("student_data", {}),
                "extracted_user_info": data_layer.get("extracted_user_info", {}),
                "features": data_layer.get("analysis", {}).get("features", {}),
                "scores": data_layer.get("analysis", {}).get("scores", {}),
                "guidance": data_layer.get("guidance", ""),
                "refined_outline": data_layer.get("refined_outline", {}),
            }

        des_type = data_layer.get("type", "")
        if des_type == "refine_ppt":
            return {"success": success, "layer": layer, "des_type": "refine_ppt", "ppt_title": data_layer.get("ppt_title", "")}
        if des_type == "animation":
            return {"success": success, "layer": layer, "des_type": "animation", "animation": data_layer}

        return {"success": success, "layer": layer, "data": data_layer}

    # ==================== Unrecognized 层 ====================
    if layer == "unrecognized":
        return {
            "success": success,
            "layer": layer,
            "message": raw_result.get("message", "无法识别当前输入"),
            "data": data_layer,
        }

    # ==================== Unknown（错误） ====================
    return {"success": success, "layer": layer, "error": raw_result.get("error", "未知错误")}


def cache_java_result(user_id: str, raw_result: dict) -> Optional[dict]:
    """转换并缓存 Java 友好 JSON，返回转换结果（出错返回 None）"""
    try:
        java_json = transform_to_java_result(raw_result)
        set_java_result(user_id, java_json)
        print(f"✅ Java JSON 已存储: user_id={user_id}, layer={java_json.get('layer')}, task_type={java_json.get('task_type', 'N/A')}")
        return java_json
    except Exception as e:
        print(f"⚠️ Java JSON 转换失败: {e}")
        return None
