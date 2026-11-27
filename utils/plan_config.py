"""
方案配置工具 - 读取用户已选择的学习方案

提供统一的 plan_config 读取接口，供 Conduct 层各资源节点调用。
方案选择存储位置: data/plan_configs/{user_id}.json
"""

import json
import os
import re
from typing import Optional, Dict, Any

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "plan_configs")

# 合法的 user_id 模式：仅允许字母、数字、下划线、中划线、点
_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_\-\.]+$')


def _safe_user_id(user_id: str) -> str:
    """校验 user_id 是否安全，防止路径穿越攻击"""
    if not _SAFE_ID_RE.match(user_id):
        raise ValueError(f"非法的 user_id: {user_id!r}")
    return user_id


def get_plan_config(user_id: str) -> Optional[Dict[str, Any]]:
    """
    获取用户已选择的学习方案配置。
    
    Args:
        user_id: 用户ID
        
    Returns:
        方案配置字典，包含 plan_id, plan_name, selected_at
        如未选择返回 None
    """
    if not user_id:
        return None
    config_file = os.path.join(_CONFIG_DIR, f"{_safe_user_id(user_id)}.json")
    if not os.path.exists(config_file):
        return None
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ [PlanConfig] 读取方案配置失败: {e}")
        return None


def get_plan_options(user_id: str) -> list:
    """
    获取用户所有可选方案列表。
    
    Args:
        user_id: 用户ID
        
    Returns:
        方案列表，每项含 name, subtitle, style_tags, difficulty, focus, detail 等
    """
    if not user_id:
        return []
    options_file = os.path.join(_CONFIG_DIR, f"{_safe_user_id(user_id)}_options.json")
    if not os.path.exists(options_file):
        return []
    try:
        with open(options_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("plans", [])
    except Exception as e:
        print(f"⚠️ [PlanConfig] 读取方案选项失败: {e}")
        return []


def get_plan_context_text(user_id: str) -> str:
    """
    获取方案上下文字段，供 LLM Prompt 拼接用。
    返回如: "用户选择了'实践驱动'学习方案（难度:medium，侧重项目实战）"
    如未选择方案，返回空字符串。
    """
    plan = get_plan_config(user_id)
    if not plan:
        return ""
    
    plan_id = plan.get("plan_id", "")
    plan_name = plan.get("plan_name", "")
    
    # 查找方案详情
    options = get_plan_options(user_id)
    detail_text = ""
    for opt in options:
        if opt.get("plan_id") == plan_id or opt.get("name") == plan_name:
            focus = opt.get("focus", "")
            difficulty = opt.get("difficulty", "")
            style = "、".join(opt.get("style_tags", []))
            parts = []
            if focus:
                parts.append(f"侧重{focus}")
            if style:
                parts.append(f"风格{style}")
            if difficulty:
                parts.append(f"难度{difficulty}")
            if parts:
                detail_text = "（" + "，".join(parts) + "）"
            break
    
    return f"用户选择了'{plan_name}'学习方案{detail_text}"
