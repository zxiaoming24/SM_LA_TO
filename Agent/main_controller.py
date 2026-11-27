"""
总控制器 - 协调Des层和Conduct层
基于LangGraph实现智能路由
支持异步并发处理多用户请求
"""

from typing import Dict, Any, TypedDict, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
import asyncio
import sys
import threading
import json
import os
import time

# 导入两层主Agent
from Agent.main_agent_des import MainAgent as DesAgent
from Agent.main_agent_conduct import ConductAgent

# ★★★ SuperAgent 超级智能体（处理复杂/未知任务）★★★
from Agent.super_agent import SuperAgent

# ★★★ 通用 SSE 事件发射辅助 ★★★
async def _emit_sse(event_type: str, **kwargs):
    """向 SSE 队列发射任意事件（如果当前有 SSE 队列）"""
    try:
        from Agent.main_agent_conduct import _node_status_queue
        queue = _node_status_queue.get()
        if queue is not None:
            import time
            payload = {"type": event_type, "timestamp": time.time(), **kwargs}
            await queue.put(payload)
    except Exception:
        pass  # SSE不可用时不阻塞

async def _emit_node_status(node: str, status: str, detail: str = ""):
    await _emit_sse("node_status", node=node, status=status, detail=detail)

async def _emit_thinking(node: str, content: str):
    await _emit_sse("thinking", node=node, content=content)

async def _emit_task_result(result: dict):
    await _emit_sse("task_result", result=result)

# ★★★ 主控制器节点包装器（给 LangGraph 节点加 SSE 状态推送）★★★
def _wrap_master_node(node_name: str, node_func):
    """包装主控制器 LangGraph 节点，自动推送 node_status 事件"""
    async def wrapped(state) -> dict:
        task_type = state.get("action_type", "")
        await _emit_node_status(node_name, "start", f"task_type={task_type}")
        await _emit_thinking(node_name, f"🚀 {node_name} 节点开始执行")
        try:
            result = await node_func(state) if asyncio.iscoroutinefunction(node_func) else node_func(state)
            if result.get("error"):
                await _emit_node_status(node_name, "error", str(result["error"]))
                await _emit_thinking(node_name, f"❌ {node_name} 执行出错: {result['error']}")
            else:
                await _emit_node_status(node_name, "complete")
                await _emit_thinking(node_name, f"✅ {node_name} 节点执行完成")
            return result
        except Exception as e:
            await _emit_node_status(node_name, "error", str(e))
            await _emit_thinking(node_name, f"❌ {node_name} 异常: {str(e)}")
            raise
    return wrapped

# ★★★ MemoryHub 统一记忆召回 ★★★
try:
    from memory import get_shared_memory_hub
    _MEMORY_HUB = get_shared_memory_hub()
except Exception as e:
    print(f"⚠️ MemoryHub 加载失败: {e}")
    _MEMORY_HUB = None
from Agent.children_agent.chat_agent import ChatAgent
from Agent.children_agent.input_validator import validate_input_async
from utils.intent_classifier import get_intent_classifier


# ==================== 复合意图检测（模块级别，供预分类和LangGraph节点共用） ====================

_COMPOUND_KEYWORDS = {
    "explain":     ["解释", "讲解", "介绍", "什么是", "什么叫", "说明"],
    "judge":       ["检查", "报错", "debug", "调试", "bug", "错误", "编译错误", "段错误", "空指针", "死循环"],
    "practice":    ["练习", "编程题", "写代码", "做道题"],
    "question":    ["出题", "考题", "选择题", "判断题", "填空题", "简答题", "检验概念"],
    "doc":         ["文档", "笔记", "总结"],
    "video":       ["视频", "教程", "看"],
    "mindmap":     ["导图", "脑图", "思维导图"],
    "ppt":         ["PPT", "幻灯片", "演示文稿"],
    "animation":   ["动画", "可视化", "动态演示", "演示动画", "过程动画", "步骤动画", "算法动画", "链表动画"],
    "study_plan":  ["学习计划", "学习路线", "路线图", "制定计划", "学习规划", "学习安排"],
    "extension":   ["拓展", "延伸阅读", "进阶", "推荐阅读", "深入理解", "扩展知识"],
}
_INTENT_TO_CATEGORY = {
    "practice": "practice", "judge_code": "judge",
    "question_gen": "question", "doc_gen": "doc",
    "extension": "extension", "video": "video",
    "mindmap": "mindmap", "animation": "animation",
    "ppt": "ppt", "study_plan": "study_plan",
}

def _has_compound_intent(text: str, detected_intent: str) -> bool:
    """
    检测是否包含多个不同类别的任务关键词。
    
    纯关键词驱动（不依赖分类器预测的意图类别，避免分类错误导致误触发）：
      当文本实际包含属于2个及以上不同任务类别的关键词时返回 True。
      例如 "帮我生成PPT顺便出几道题" → PPT(ppt) + 出题(question) → True
      例如 "二分查找编程题" → 编程题(practice) → False
    """
    matched_categories = set()
    detected_cat = _INTENT_TO_CATEGORY.get(detected_intent)
    for category, keywords in _COMPOUND_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matched_categories.add(category)
                break
    # ★★★ 排除纯关键词误判：只匹配到检测意图自身类别的关键词 → 不算复合 ★★★
    if len(matched_categories) == 1 and detected_cat and detected_cat in matched_categories:
        return False
    return len(matched_categories) >= 2


# ★★★ 裸露关键词拦截：某些意图需要具体的主题/目标信息，仅意图关键词本身不构成有效指令 ★★★
_BARE_KEYWORD_MAP = {
    # intent → {裸露关键词集合}，当用户输入只包含这些词（无具体主题）时判定为无效
    "ppt": {"ppt", "幻灯片", "演示文稿", "课件", "演示"},
    "video": {"视频", "教程", "看视频", "教学视频", "课程视频"},
    "mindmap": {"思维导图", "导图", "脑图", "知识框架"},
    "animation": {"动画", "html动画", "动态演示", "演示动画"},
    "practice": {"练习", "编程练习", "写代码", "敲代码", "写程序", "练习题", "编程题", "做道题"},
    "study_plan": {"学习计划", "计划", "学习路线", "规划", "路线图", "安排学习"},
    "doc_gen": {"文档", "笔记", "总结", "报告", "文件"},
    "extension": {"拓展", "拓展阅读", "延伸阅读", "推荐阅读"},
}

_TOPIC_REQUIRED_INTENTS = set(_BARE_KEYWORD_MAP.keys())


def _is_bare_keyword_input(text: str, intent: str) -> bool:
    """
    检查用户输入是否仅为裸露的意图关键词，缺乏具体的主题/目标信息。
    
    例如 "PPT" → bare（无主题），"二叉树的PPT" → not bare（有主题"二叉树"）
    
    Returns:
        True 表示输入过短/仅含关键词，应判定为无效指令
        False 表示输入包含具体主题信息，可以继续执行
    """
    if intent not in _TOPIC_REQUIRED_INTENTS:
        return False  # 非目标意图不拦截

    bare_set = _BARE_KEYWORD_MAP[intent]
    stripped = text.strip().lower()

    # ★★★ 情形 1：输入本身就是裸露关键词（或仅带"的"）★★★
    # 如 "PPT"、"幻灯片"、"的PPT"、"做PPT"、"帮我做PPT"
    if stripped in bare_set:
        return True

    # ★★★ 情形 2：去除常见的辅助词后，剩下的仅为裸露关键词 ★★★
    # 辅助词：帮我、生成、做、制作、画、找、看、推荐、弄、写、来、要、我想、我要、一个
    _helper_words = ["帮我", "生成", "做", "制作", "画", "找", "看", "推荐",
                     "弄", "写", "来", "要", "我想", "我要", "一个", "一下", "的"]
    
    cleaned = stripped
    for w in _helper_words:
        cleaned = cleaned.replace(w, "")

    # 去空白和标点
    import re
    cleaned = re.sub(r'[\s,，。！？、；：""''（）()【】\[\]]', '', cleaned)

    # 如果清理后只剩下裸露关键词 → bare
    if cleaned in bare_set or cleaned == "":
        return True

    # ★★★ 情形 3：检查是否包含"具体主题词" ★★★
    # 只要包含 2 个以上的中文字符且不是裸露关键词 → 有具体主题
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', cleaned)
    chinese_text = ''.join(chinese_chars)

    if chinese_text and chinese_text not in bare_set:
        return False  # 有具体中文内容 → 有效

    return True  # 兜底拦截


# ★★★ MLP 置信度预检已移除 ★★★
# 原 _mlp_low_confidence() 因直接调用 MLP 而不经过余弦相似度降级，导致
# MLP 置信度低但余弦相似度能正确分类的输入被误拦截。统一由
# IntentClassifier.classify() 内部的 MLP→余弦相似度→LLM 三级流水线处理。


# ==================== 注册状态管理（文件锁，进程安全） ====================

_REGISTERING_LOCK_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "user_features", ".registering_locks"
)

def _registering_lock_path(user_id: str) -> str:
    os.makedirs(_REGISTERING_LOCK_DIR, exist_ok=True)
    return os.path.join(_REGISTERING_LOCK_DIR, f"{user_id}.lock")

def _cleanup_stale_registering_locks(max_age_seconds: int = 300):
    """清理过期的注册锁文件（进程崩溃后残留）"""
    try:
        if os.path.exists(_REGISTERING_LOCK_DIR):
            for lock_file in os.listdir(_REGISTERING_LOCK_DIR):
                if lock_file.endswith(".lock"):
                    lock_path = os.path.join(_REGISTERING_LOCK_DIR, lock_file)
                    if time.time() - os.path.getmtime(lock_path) > max_age_seconds:
                        os.remove(lock_path)
                        print(f"🗑️ [MainController] 清理过期注册锁文件: {lock_file}")
    except Exception:
        pass

import threading as _threading
_registering_lock = _threading.Lock()

def _is_registering(user_id: str) -> bool:
    with _registering_lock:
        lock_path = _registering_lock_path(user_id)
        if not os.path.exists(lock_path):
            return False
        if time.time() - os.path.getmtime(lock_path) > 300:
            try:
                os.remove(lock_path)
            except Exception:
                pass
            return False
        return True

def _start_registering(user_id: str):
    with _registering_lock:
        path = _registering_lock_path(user_id)
        with open(path, 'w') as f:
            pass

def _finish_registering(user_id: str):
    with _registering_lock:
        try:
            os.remove(_registering_lock_path(user_id))
        except FileNotFoundError:
            pass


# ==================== 状态定义 ====================

class MasterState(TypedDict):
    """总控层状态"""
    # 输入
    user_id: Optional[str]
    user_input: str               # 含记忆上下文的 enriched_input（供 LLM Prompt 使用）
    raw_user_input: str           # 用户原始输入（供意图分类和路由使用）
    
    # 意图识别结果
    intent: str               # des/conduct/chat/unrecognized
    action_type: str          # 具体动作类型
    pre_intent: Optional[str]        # _pre_classify 已确定的意图（避免双重分类）
    pre_confidence: Optional[float]  # _pre_classify 已确定的置信度
    pre_validation: Optional[Dict[str, Any]]  # _pre_classify 的 InputValidator 结果（避免重复 LLM 调用+结果不一致）
    
    # Des层多轮对话状态
    previous_extracted_info: Optional[Dict[str, Any]]  # 保存上一轮提取的用户信息
    
    # 各层执行结果
    des_result: Optional[Dict[str, Any]]
    conduct_result: Optional[Dict[str, Any]]
    unrecognized_result: Optional[Dict[str, Any]]  # 无法识别的无效指令结果
    
    # 最终输出
    final_response: Optional[Dict[str, Any]]
    error: Optional[str]
    
    # 日志
    execution_log: list
    
    # TTS语音合成开关
    enable_tts: bool
    
    # 用户确认覆盖采纳建议
    confirmed: bool
    override_suggestions: bool
    
    # 学习计划焦点参数
    ignore_weak_points: bool
    focus_weak_points: bool


# ==================== 节点函数 ====================

# ★★★ Des层多轮对话状态持久化（磁盘+内存双写）★★★
_EXTRACTED_INFO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "user_features", ".extracted_info_cache")


def _get_extracted_info_path(user_id: str) -> str:
    path = os.path.join(_EXTRACTED_INFO_DIR, f"{user_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def _save_extracted_info(user_id: str, extracted_info: Dict[str, Any]):
    """保存用户已提取的信息（磁盘持久化，服务重启不丢失）"""
    if user_id and extracted_info:
        path = _get_extracted_info_path(user_id)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(extracted_info, f, ensure_ascii=False, indent=2)
            print(f"📌 [Des状态] 已持久化保存 {user_id} 的提取信息: {list(extracted_info.keys())}")
        except Exception as e:
            print(f"⚠️ [Des状态] 持久化失败: {e}")


def _load_extracted_info(user_id: str) -> Optional[Dict[str, Any]]:
    """加载用户已提取的信息"""
    path = _get_extracted_info_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                info = json.load(f)
            print(f"📌 [Des状态] 从磁盘加载 {user_id} 的已有提取信息: {list(info.keys())}")
            return info
        except Exception as e:
            print(f"⚠️ [Des状态] 从磁盘加载失败: {e}")
    return None


def _clear_extracted_info(user_id: str):
    """清除用户已提取的信息（注册完成后调用）"""
    path = _get_extracted_info_path(user_id)
    try:
        if os.path.exists(path):
            os.remove(path)
        print(f"📌 [Des状态] 已清除 {user_id} 的持久化提取信息")
    except Exception as e:
        print(f"⚠️ [Des状态] 清除失败: {e}")


def _check_des_completed(user_id: str) -> bool:
    """
    检查用户是否已完成Des层注册
    
    Args:
        user_id: 用户ID
        
    Returns:
        bool: 是否已完成Des层
    """
    if not user_id:
        return False
    
    try:
        # 从动态特征更新器获取用户特征
        from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        updater = DynamicFeatureUpdater()
        features = updater.get_latest_features(user_id)  # ★★★ 使用正确的方法名 ★★★
        
        if not features:
            return False
        
        # ★★★ 严格检查 des_completed 标记（新用户走此路径）★★★
        if features.get('des_completed', False):
            return True
        
        # ★★★ 向后兼容：旧用户没有 des_completed 标记 ★★★
        # 但如果有 summary_scores.overall_score 字段，
        # 说明完整注册（feature_extractor → teacher → integrator）已完成，
        # 自动迁移添加 des_completed 标记，避免重复注册。
        summary_scores = features.get('summary_scores', {})
        if summary_scores and summary_scores.get('overall_score', 0) > 0:
            print(f"📌 [Des状态] 检测到旧版用户 {user_id}，自动迁移 des_completed 标记")
            # ★★★ 清理残留的注册锁和信息缓存（之前失败中断留下的）★★★
            _finish_registering(user_id)
            _clear_extracted_info(user_id)
            _mark_des_completed(user_id)
            return True
            
    except Exception as e:
        print(f"⚠️  检查Des层状态失败: {e}")
    
    return False


def _mark_des_completed(user_id: str):
    """
    标记用户已完成Des层注册
    
    Args:
        user_id: 用户ID
    """
    if not user_id:
        return
    
    try:
        from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
        updater = DynamicFeatureUpdater()
        
        # 获取当前特征
        features = updater.get_latest_features(user_id) or {}  # ★★★ 使用正确的方法名 ★★★
        
        # 添加完成标记
        features['des_completed'] = True
        features['des_completed_time'] = datetime.now().isoformat()
        
        # 保存更新
        updater._save_features_to_disk(user_id, features)
        
        # ★★★ 同步更新内存缓存，避免下次 get_latest_features 仍返回旧数据 ★★★
        if hasattr(updater, '_features_cache'):
            updater._features_cache[user_id] = features.copy()
        
        print(f"✅ 已标记用户 {user_id} 完成Des层注册")
        
    except Exception as e:
        print(f"⚠️  标记Des层完成状态失败: {e}")



async def _check_compound_with_llm(text: str) -> bool:
    """
    用 LLM 判断用户输入是否为复合任务（需要 SuperAgent 处理）。

    替代原有的关键词匹配 _has_compound_intent()，语义理解更准确。
    """
    try:
        from utils.llm_config import get_chat_openai
        llm = get_chat_openai(temperature=0.0, max_tokens=10, timeout=15)
        prompt = f"""判断用户输入是否包含多个不同的学习任务。

## 任务类型列表
- PPT制作：做PPT、幻灯片、演示文稿、课件
- 视频学习：找视频、看教程、网课、视频讲解
- 学习规划：学习计划、学习路线、学习安排
- 编程练习：写代码、编程题、算法实现
- 出题做题：出题、测验、考试、刷题
- 代码调试：debug、检查代码、找bug、报错
- 文档笔记：写文档、写笔记、写总结、整理
- 思维导图：脑图、导图、知识框架
- 动画可视化：动画、可视化、动态演示
- 学习建议：学习方法、怎么学、困惑、求教
- 拓展延伸：推荐阅读、进阶、深入、原理
- 知识问答：解释概念、讲解知识、答疑

## 判断规则

### 是（复合任务）
用户明显要求处理2个以上不同类型的任务，缺一不可。
例如：
- "做个PPT顺便出几道练习题" → PPT + 出题 → 是
- "帮我找视频学Python，再写个练习题" → 视频 + 练习 → 是
- "学完二叉树后帮我做导图和PPT" → 导图 + PPT → 是
- "解释指针概念并找视频教程" → 问答 + 视频 → 是
- "生成链表思维导图，再出几道题" → 导图 + 出题 → 是
- "整理学习笔记再生成复习题" → 文档 + 出题 → 是

### 否（单一任务）
用户只有一个核心任务，其他内容只是修饰或附带说明。
例如：
- "帮我做二叉树的PPT" → 只有PPT → 否
- "找一个Python视频教程" → 只有视频 → 否
- "写一个快排算法" → 只有编程练习 → 否
- "做个关于链表的思维导图" → 只有导图 → 否
- "出几道二叉树的题" → 只有出题 → 否
- "帮我debug这段代码" → 只有调试 → 否
- "解释一下什么是多态" → 只有问答 → 否
- "制定Rust学习计划" → 只有学习规划 → 否
- "帮我整理二叉树笔记" → 只有文档 → 否

### 边界情况
- "帮我做PPT里面放个视频" → PPT本身就包含视频是制作的一部分 → 单一任务 → 否
- "先解释概念再出题" → 解释是为了出题服务的，核心是出题 → 单一任务 → 否
- "学完排序帮我总结并出题" → 总结+出题是两个独立任务 → 复合 → 是

只回答"是"或"否"。

用户输入：{text}"""
        response = llm.invoke(prompt)
        result = response.content.strip()
        return "是" in result
    except Exception as e:
        print(f"  ⚠️ [复合判断LLM] 失败（降级为不复合）: {e}")
        return False


async def _intent_for_registered_user(state: MasterState, user_input: str) -> MasterState:
    """
    已注册用户的意图识别（使用语义嵌入分类器）
    
    Args:
        state: 当前状态
        user_input: 用户输入（原始文本，不转小写）
        
    Returns:
        MasterState: 更新后的状态
    """
    # ★★★ 安全校验：未注册用户不应进入此函数 ★★★
    user_id = state.get("user_id")
    if user_id and not _check_des_completed(user_id):
        print(f"⚠️  [安全校验] 用户 {user_id} 未完成DES注册，强制路由到 DES 层")
        _start_registering(user_id)
        return {
            **state,
            "intent": "des",
            "action_type": "register",
            "execution_log": state.get("execution_log", []) + ["intent_recognition"]
        }

    # ★★★ ★★★ 复用预分类结果：跳过冗余的 classifier.classify() 和 validate_input_async() ★★★ ★★★
    # _pre_classify 已在 process_request 中调用了 classifier.classify() 和 validate_input_async()，
    # 结果已存入 state.pre_intent / state.pre_confidence / state.pre_validation。
    pre_intent = state.get("pre_intent")
    pre_confidence = state.get("pre_confidence")
    pre_validation = state.get("pre_validation")
    if pre_intent is not None and pre_confidence is not None:
        # ★★★ 复用预分类的 InputValidator 结果（避免重复 LLM 调用+结果不一致）★★★
        if pre_validation is not None:
            validation = pre_validation
            print(f"  ℹ️ [复用预分类] intent={pre_intent}({pre_confidence:.2f}), validation=复用，跳过重复 LLM 调用")
        else:
            validation = await validate_input_async(user_input)
        if not validation["is_valid"]:
            print(f"⚠️  [InputValidator] 输入 '{user_input}' 无效: {validation['reason']}")
            return {
                **state,
                "intent": "unrecognized",
                "action_type": "unrecognized",
                "execution_log": state.get("execution_log", []) + ["intent_recognition"]
            }
        # ★★★ 冲突消解：当 pre_intent 已有高置信度具体意图时，信任 pre_intent 而非 Validator ★★★
        if validation["action_type"] == "chat":
            if pre_intent not in ("chat", "unrecognized") and pre_confidence >= 0.65:
                print(f"  ℹ️ [复用预分类] InputValidator判chat，但预分类为 {pre_intent}({pre_confidence:.2f})，信任预分类")
                # 不 return，继续往下走路由逻辑
            else:
                print(f"💬  [InputValidator] 输入判定为聊天内容，路由到 chat")
                return {
                    **state,
                    "intent": "chat",
                    "action_type": "chat",
                    "execution_log": state.get("execution_log", []) + ["intent_recognition"]
                }
        intent, confidence = pre_intent, pre_confidence
        print(f"  ℹ️ [复用预分类] intent={intent}({confidence:.2f})，跳过重复分类")
    else:
        # ★★★ 没有预分类结果 → 走完整分类流程（容错降级）★★★
        validation = await validate_input_async(user_input)
        if not validation["is_valid"]:
            print(f"⚠️  [InputValidator] 输入 '{user_input}' 无效: {validation['reason']}")
            return {
                **state,
                "intent": "unrecognized",
                "action_type": "unrecognized",
                "execution_log": state.get("execution_log", []) + ["intent_recognition"]
            }
        # ★★★ 始终运行分类器，做冲突消解 ★★★
        classifier = get_intent_classifier()
        intent, confidence = classifier.classify(user_input)
        if validation["action_type"] == "chat":
            if intent not in ("chat", "unrecognized") and confidence >= 0.65:
                print(f"  ℹ️ [降级分类] InputValidator判chat，但分类器高置信为 {intent}({confidence:.2f})，覆盖Validator")
            else:
                print(f"💬  [InputValidator] 输入判定为聊天内容，路由到 chat")
                return {
                    **state,
                    "intent": "chat",
                    "action_type": "chat",
                    "execution_log": state.get("execution_log", []) + ["intent_recognition"]
                }

    conduct_intents = {"practice", "judge_code", "question_gen", "doc_gen",
                       "extension", "video", "mindmap", "animation", "study_plan", "ppt"}
    des_intents = {"register", "refine_ppt", "teacher_advice"}
    profile_modify_intents = {"profile_modify"}

    if intent in conduct_intents:
        layer = "conduct"
        print(f"✅ 语义识别为Conduct层意图 ({intent}, 置信度: {confidence:.2f})")

        # ★★★ 裸露关键词拦截：仅意图关键词（无具体主题）→ 无效指令 ★★★
        if _is_bare_keyword_input(user_input, intent):
            print(f"⚠️  [裸露关键词拦截] 输入'{user_input}'仅为{intent}的裸露关键词，无具体目标信息")
            return {
                **state,
                "intent": "unrecognized",
                "action_type": "unrecognized",
                "execution_log": state.get("execution_log", []) + ["intent_recognition"]
            }

        # ★★★ 检测复合意图：先用关键词预筛（免费），再 LLM 确认 ★★★
        if confidence >= 0.7 and _has_compound_intent(user_input, intent) and await _check_compound_with_llm(user_input):
            print(f"⚠️  [总控] 单意图={intent}({confidence:.2f})，关键词+LLM均检测为复合任务，路由到 SuperAgent")
            return {
                **state,
                "intent": "super",
                "action_type": intent,
                "execution_log": state.get("execution_log", []) + ["intent_recognition"]
            }
    elif intent in profile_modify_intents:
        layer = "profile_modify"
        print(f"✅ 语义识别为profile_modify意图 ({intent}, 置信度: {confidence:.2f})，路由到 profile_modify 处理")
    elif intent in des_intents:
        if intent == "register":
            # ★★★ 已注册用户的注册意图 → profile_modify（不进入 DES 层）★★★
            layer = "profile_modify"
            print(f"✅ 语义识别为Des层意图 ({intent}, 置信度: {confidence:.2f})，已注册用户路由到 profile_modify 处理")
        else:
            # ★★★ refine_ppt/teacher_advice 不是注册类功能，仍需走 DES 层 ★★★
            layer = "des"
            print(f"✅ 语义识别为Des层意图 ({intent}, 置信度: {confidence:.2f})，路由到 Des层")
    elif intent == "unrecognized":
        layer = "unrecognized"
        print(f"⚠️ 语义识别为unrecognized意图 ({intent}, 置信度: {confidence:.2f})，路由到 unrecognized")
    else:
        layer = "chat"
        print(f"✅ 语义识别为Chat层意图 ({intent}, 置信度: {confidence:.2f})")

    return {
        **state,
        "intent": layer,
        "action_type": intent,
        "execution_log": state.get("execution_log", []) + ["intent_recognition"]
    }


async def intent_recognition_node(state: MasterState) -> MasterState:
    """意图识别节点 - 判断请求属于Des层、Conduct层还是Chat层"""
    print("\n🔍 [总控] 意图识别中...")
    
    # ★★★ 意图分类使用原始用户输入（不用 enriched_input），避免历史上下文污染 ★★★
    user_input = state.get("raw_user_input", "").lower()
    user_id = state.get("user_id")
    
    # ★★★ 检查用户是否已完成Des层注册 ★★★
    des_completed = _check_des_completed(user_id)
    
    if des_completed:
        # ★★★ 安全网：des_completed 为 True 但注册锁残留（上一轮异常中断遗留），
        # 清理残留锁和信息缓存，不要强制回 DES ★★★
        if _is_registering(user_id):
            print(f"⚠️  用户 {user_id} 的注册锁残留，但 DES 已完成，自动清理")
            _finish_registering(user_id)
            _clear_extracted_info(user_id)
        
        print(f"✅ 用户 {user_id} 已完成Des层注册，跳过信息抽取")
        
        # ★★★ 延续检测：如果是"换一道/再找一些/继续"等延续性请求，从工作记忆获取上一轮任务类型，不重新分类 ★★★
        continue_keywords = [
            "换一道", "换一个", "再来一道", "再来一个", "换题", "换一题",
            "换道题", "别的题", "另一道", "换道", "换个",
            "再找一些", "在找一些", "再找", "再推荐", "再来",
            "还有吗", "还有没有", "还有",
            "继续", "继续找", "继续推荐", "继续看",
        ]
        is_change_request = any(kw in user_input for kw in continue_keywords)
        
        if is_change_request and user_id and _MEMORY_HUB:
            try:
                prev_task = _MEMORY_HUB.working.get_current_task(user_id)
                if prev_task and prev_task.get("type") in {"practice", "judge_code", "question_gen", "doc_gen",
                                                            "extension", "video", "mindmap", "animation", "study_plan", "ppt"}:
                    prev_type = prev_task["type"]
                    print(f"🔄 检测到换题请求，沿用上一轮任务类型: {prev_type}")
                    return {
                        **state,
                        "intent": "conduct",
                        "action_type": prev_type,
                        "execution_log": state.get("execution_log", []) + ["intent_recognition"]
                    }
            except Exception as e:
                print(f"   ⚠️ 获取上一轮任务类型失败: {e}")
        
        # 已注册用户：直接识别是Chat还是Conduct
        return await _intent_for_registered_user(state, user_input)
    else:
        print(f"⚠️  用户 {user_id} 未完成Des层注册")
        # ★★★ 强制进入Des层完成注册，无论用户输入是什么 ★★★
        # 新用户必须先完成基础特征构建才能使用其他功能
        _start_registering(user_id)  # 标记开始注册
        print(f"✅ 强制路由到Des层进行注册")
        return {
            **state,
            "intent": "des",
            "action_type": "register",
            "execution_log": state.get("execution_log", []) + ["intent_recognition"]
        }


async def integrator_node(state: MasterState) -> MasterState:
    """整合最终响应"""
    print("\n📦 [总控] 整合最终响应...")
    loop = asyncio.get_running_loop()
    
    error = state.get("error")
    des_result = state.get("des_result")
    conduct_result = state.get("conduct_result")
    unrecognized_result = state.get("unrecognized_result")
    
    if error:
        final_response = {
            "success": False,
            "data": {
                "status": "error",
                "layer": "unknown",
                "error": error
            },
            "suggestion_warning": "",
            "metadata": {
                "user_id": state.get("user_id"),
                "session_id": None
            }
        }
    elif unrecognized_result:
        final_response = {
            "success": False,
            "data": {
                "status": "unrecognized",
                "layer": "unrecognized",
                "message": unrecognized_result.get("message", "无法识别当前输入"),
                "raw_input": unrecognized_result.get("raw_input", "")
            },
            "suggestion_warning": "",
            "metadata": {
                "user_id": state.get("user_id"),
                "session_id": None
            }
        }
    elif conduct_result:
        final_response = {
            "success": conduct_result.get("status") == "success",
            "data": conduct_result,
            "suggestion_warning": conduct_result.get("suggestion_warning", ""),
            "metadata": {
                "user_id": state.get("user_id"),
                "session_id": None
            }
        }
    elif des_result:
        final_response = {
            "success": des_result.get("status") == "success",
            "data": des_result,
            "suggestion_warning": "",
            "metadata": {
                "user_id": state.get("user_id"),
                "session_id": None
            }
        }
        
        # ★★★ 返回提取的用户信息，供下一轮使用 ★★★
        extracted_info = state.get("previous_extracted_info", {})
        if extracted_info:
            final_response["extracted_info"] = extracted_info
    else:
        final_response = {
            "success": False,
            "data": {
                "status": "unknown",
                "message": "未产生有效结果"
            },
            "suggestion_warning": "",
            "metadata": {
                "user_id": state.get("user_id"),
                "session_id": None
            }
        }

    # ★★★ MemoryHub：记录助手回复到工作记忆（用可读文本替代dict截断）★★★
    try:
        user_id = state.get("user_id")
        if _MEMORY_HUB and user_id:
            reply_text = ""
            if isinstance(final_response, dict):
                reply_text = final_response.get("reply", "")
                if not reply_text:
                    data = final_response.get("data", {})
                    if isinstance(data, dict):
                        task_type = data.get("task_type", "")
                        if task_type == "practice":
                            p = data.get("practice", {})
                            reply_text = f"已生成练习题: {p.get('title', '')} (难度: {p.get('difficulty', '')})" if p else "已生成练习题"
                        elif task_type == "doc_gen":
                            reply_text = f"已生成课程文档"
                        elif task_type == "question_gen":
                            reply_text = "已生成理论题"
                        elif task_type == "extension":
                            reply_text = "已生成拓展阅读材料"
                        elif task_type == "video":
                            reply_text = "已搜索到相关教学视频"
                        elif task_type == "mindmap":
                            reply_text = "已生成思维导图"
                        elif task_type == "study_plan":
                            sp = data.get("study_plan", {})
                            reply_text = f"已生成学习计划: {sp.get('title', '')}" if sp else "已生成学习计划"
                        elif task_type == "judge_code":
                            jr = data.get("judge", {})
                            err_type = jr.get("error_type", "") if jr else ""
                            has_err = jr.get("has_error", False) if jr else False
                            reply_text = f"代码评判完成：{'发现错误 - ' + err_type if has_err else '未发现明显错误'}"
                        elif task_type == "ppt":
                            ppt = data.get("ppt", {})
                            topic = ppt.get("topic", "") if ppt else ""
                            reply_text = f"已生成PPT: {topic}" if topic else "已生成PPT"
                        elif task_type == "animation":
                            anim = data.get("animation", {})
                            title = anim.get("title", "") if anim else ""
                            reply_text = f"已生成动画: {title}" if title else "已生成教育动画"
                        elif data.get("type") == "casual_chat":
                            reply_text = data.get("reply", "")[:500]
                        else:
                            reply_text = f"已完成{task_type}任务"
                    else:
                        reply_text = str(data)[:200]
            await loop.run_in_executor(None, lambda: _MEMORY_HUB.working.add_turn(user_id, "assistant", reply_text[:500]))
            
            # 更新当前任务状态
            intent = state.get("action_type", "")
            if intent:
                await loop.run_in_executor(None, lambda: _MEMORY_HUB.working.set_current_task(user_id, intent))
    except Exception:
        pass

    print("✅ 最终响应整合完成")
    
    return {
        **state,
        "final_response": final_response,
        "execution_log": state.get("execution_log", []) + ["integrator"]
    }


# ==================== 总控类 ====================

class MasterController:
    """
    总控制器 - 协调Des层和Conduct层
    
    每个MasterController实例拥有独立的DesAgent和ConductAgent，
    支持多用户独立使用（每个用户一个实例）。
    """
    
    def __init__(self):
        """初始化总控制器，创建独立的DesAgent和ConductAgent实例"""
        print("🚀 初始化Master Controller（独立实例）...")
        
        _cleanup_stale_registering_locks()
        
        # ★★★ 每个实例拥有自己的Agent（不再共享全局单例）★★★
        self.des_agent = DesAgent()
        self.conduct_agent = ConductAgent()
        
        # 构建LangGraph工作流
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile()
        
        print("✅ Master Controller初始化完成")
    
    def _build_workflow(self):
        """构建工作流"""
        workflow = StateGraph(MasterState)
        
        # ★★★ 节点函数使用实例持有的Agent，而非单例 ★★★
        des_agent = self.des_agent
        conduct_agent = self.conduct_agent
        
        # ---------- Des层节点 ----------
        async def _des_layer_node(state: MasterState) -> MasterState:
            """调用Des层处理"""
            print("\n📋 [总控] 调用Des层处理...")
            try:
                user_id = state.get("user_id")
                user_input = state.get("user_input", "")
                action_type = state.get("action_type", "")
                previous_info = state.get("previous_extracted_info")
                
                if action_type == "register":
                    result = await des_agent.process_natural_language_input(
                        user_input, 
                        previous_extracted_info=previous_info,
                        user_id=user_id
                    )
                    
                    if result.get("status") == "need_more_info":
                        extracted_info = result.get("extracted_info", {})
                        _save_extracted_info(user_id, extracted_info)
                        return {
                            **state,
                            "des_result": result,
                            "previous_extracted_info": extracted_info,
                            "execution_log": state.get("execution_log", []) + ["des_layer"]
                        }
                    elif result.get("status") == "success":
                        _mark_des_completed(user_id)
                        _finish_registering(user_id)
                        # ★★★ 将提取的用户信息持久化到 basic_info，重启后依然可识别 ★★★
                        extracted_user_info = result.get("extracted_user_info", {})
                        if extracted_user_info and user_id:
                            try:
                                from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
                                updater = DynamicFeatureUpdater()
                                features = updater.get_latest_features(user_id) or {}
                                if "basic_info" not in features:
                                    features["basic_info"] = {}
                                for key in ["name", "major", "grade", "learning_goal", "learning_habits"]:
                                    val = extracted_user_info.get(key)
                                    if val and val not in ("未知", "", [], {}):
                                        features["basic_info"][key] = val
                                updater._save_features_to_disk(user_id, features)
                                # 同步更新内存缓存
                                if hasattr(updater, '_features_cache'):
                                    updater._features_cache[user_id] = features.copy()
                                print(f"✅ 已将注册信息持久化到 basic_info: {list(features['basic_info'].keys())}")
                            except Exception as e:
                                print(f"⚠️  保存注册信息到 basic_info 失败: {e}")
                        _clear_extracted_info(user_id)
                        # ★★★ 标记注册完成，前端据此播报"初次画像构建成功" ★★★
                        result["des_stage"] = "registration_complete"
                        try:
                            from memory.comprehensive_user_memory import UserMemoryManager
                            memory_manager = UserMemoryManager()
                            if extracted_user_info:
                                user_message = user_input
                                assistant_message = f"已为您完成注册！\n"
                                assistant_message += f"姓名: {extracted_user_info.get('name', '未知')}\n"
                                assistant_message += f"专业: {extracted_user_info.get('major', '未知')}\n"
                                assistant_message += f"年级: {extracted_user_info.get('grade', '未知')}\n"
                                assistant_message += f"学习目标: {extracted_user_info.get('learning_goal', '未知')}"
                                memory_manager.add_messages(user_id, [
                                    {"role": "user", "content": user_message},
                                    {"role": "assistant", "content": assistant_message}
                                ])
                                print(f"✅ 已将注册信息保存到ChromaDB对话历史")
                        except Exception as e:
                            print(f"⚠️  保存注册信息到ChromaDB失败: {e}")
                
                elif action_type == "refine_ppt":
                    refiner = des_agent.question_refiner
                    title = await refiner.refine_question_async(user_input)
                    result = {"status": "success", "type": "refine_ppt", "ppt_title": title, "length": len(title)}
                else:
                    result = await des_agent.process_natural_language_input(
                        user_input, previous_extracted_info=previous_info, user_id=user_id
                    )
                
                print(f"✅ Des层处理完成")
                return {
                    **state, "des_result": result,
                    "execution_log": state.get("execution_log", []) + ["des_layer"]
                }
            except Exception as e:
                print(f"❌ Des层处理失败: {e}")
                # ★★★ 出错时也要清理注册锁，避免锁残留导致后续请求永远被路由到DES但一直出错 ★★★
                _finish_registering(user_id)
                return {
                    **state, "error": f"Des层失败: {str(e)}",
                    "execution_log": state.get("execution_log", []) + ["des_layer"]
                }
        
        # ---------- Conduct层节点 ----------
        async def _conduct_layer_node(state: MasterState) -> MasterState:
            """调用Conduct层处理"""
            print("\n⚡ [总控] 调用Conduct层处理...")
            # ★★★ 立即标记 conduct_layer 为完成，内部节点（路由/动画/整合等）自己显示状态 ★★★
            await _emit_node_status("conduct_layer", "complete", "delegated to internal nodes")
            try:
                user_id = state.get("user_id", "temp_user")
                user_input = state.get("raw_user_input", "")
                action_type = state.get("action_type", "")
                confirmed = state.get("confirmed", False)
                override_suggestions = state.get("override_suggestions", False)
                ignore_weak_points = state.get("ignore_weak_points", False)
                focus_weak_points = state.get("focus_weak_points", False)
                result = await conduct_agent.execute_task_async(
                    user_id=user_id, user_input=user_input,
                    task_type=action_type, enable_tts=state.get("enable_tts", False),
                    confirmed=confirmed, override_suggestions=override_suggestions,
                    ignore_weak_points=ignore_weak_points, focus_weak_points=focus_weak_points
                )
                print(f"✅ Conduct层处理完成")
                return {
                    **state, "conduct_result": result,
                    "execution_log": state.get("execution_log", []) + ["conduct_layer"]
                }
            except Exception as e:
                print(f"❌ Conduct层处理失败: {e}")
                return {
                    **state, "error": f"Conduct层失败: {str(e)}",
                    "execution_log": state.get("execution_log", []) + ["conduct_layer"]
                }
        
        # ---------- unrecognized层节点 ----------
        async def _unrecognized_layer_node(state: MasterState) -> MasterState:
            """处理无法识别的无效指令"""
            raw_input = state.get("raw_user_input", "")
            print(f"⚠️ [总控] 输入无法识别: \"{raw_input[:50]}\"")
            return {
                **state,
                "unrecognized_result": {
                    "status": "unrecognized",
                    "type": "invalid_instruction",
                    "message": "无法识别当前输入，请提供具体的学习问题或指令。如果只是说「PPT」「视频」「练习」这类关键词，请加上具体主题，如「二叉树的PPT」。",
                    "raw_input": raw_input
                },
                "execution_log": state.get("execution_log", []) + ["unrecognized_layer"]
            }
        
        # ---------- SuperAgent 超级智能体层节点 ----------
        async def _super_layer_node(state: MasterState) -> MasterState:
            """调用 SuperAgent 处理复杂/未知任务"""
            print("\n🤖 [总控] SuperAgent 层执行中...")
            try:
                user_id = state.get("user_id")
                user_input = state.get("raw_user_input", "")
                if not user_input:
                    user_input = state.get("user_input", "")
                super_agent = SuperAgent()
                super_result = await super_agent.process(
                    user_input=user_input,
                    user_id=user_id,
                    max_tool_calls=10
                )
                return {
                    **state,
                    "conduct_result": super_result,
                    "execution_log": state.get("execution_log", []) + ["super_layer"]
                }
            except Exception as e:
                print(f"❌ [总控] SuperAgent 层执行失败: {e}")
                import traceback
                traceback.print_exc()
                return {
                    **state,
                    "error": f"SuperAgent 处理失败: {str(e)}",
                    "execution_log": state.get("execution_log", []) + ["super_layer"]
                }
        
        # ---------- 聊天层节点 ----------
        async def _chat_layer_node(state: MasterState) -> MasterState:
            """调用日常对话Agent处理聊天内容"""
            print("\n💬 [总控] 调用聊天层处理...")
            try:
                from Agent.children_agent.chat_agent import ChatAgent
                user_id = state.get("user_id", "temp_user")
                user_input = state.get("raw_user_input", "")
                enable_tts = state.get("enable_tts", False)
                chat_agent = ChatAgent()
                result = await chat_agent.chat_async(
                    user_input=user_input,
                    user_id=user_id,
                    enable_tts=enable_tts
                )
                print(f"✅ 聊天层处理完成")
                return {
                    **state,
                    "conduct_result": result,
                    "execution_log": state.get("execution_log", []) + ["chat_layer"]
                }
            except Exception as e:
                print(f"❌ 聊天层处理失败: {e}")
                import traceback
                traceback.print_exc()
                return {
                    **state,
                    "conduct_result": {
                        "status": "error",
                        "type": "casual_chat",
                        "reply": f"抱歉，我暂时无法回复您。"
                    },
                    "execution_log": state.get("execution_log", []) + ["chat_layer"]
                }

        # ---------- 画像修改层节点 ----------
        async def _profile_modify_layer_node(state: MasterState) -> MasterState:
            """调用画像修改处理"""
            print("\n✏️ [总控] 调用画像修改处理...")
            try:
                user_id = state.get("user_id")
                user_input = state.get("user_input", "")
                result = await self._handle_profile_modify(user_input, user_id)
                return {
                    **state,
                    "des_result": result,
                    "execution_log": state.get("execution_log", []) + ["profile_modify_layer"]
                }
            except Exception as e:
                print(f"❌ [总控] 画像修改处理失败: {e}")
                return {
                    **state, "error": f"画像修改失败: {str(e)}",
                    "execution_log": state.get("execution_log", []) + ["profile_modify_layer"]
                }
        
        # 添加节点（所有节点用 _wrap_master_node 包装以推送 SSE 状态）
        workflow.add_node("intent_recognition", _wrap_master_node("intent_recognition", intent_recognition_node))
        workflow.add_node("des_layer", _wrap_master_node("des_layer", _des_layer_node))
        workflow.add_node("conduct_layer", _wrap_master_node("conduct_layer", _conduct_layer_node))
        workflow.add_node("chat_layer", _wrap_master_node("chat_layer", _chat_layer_node))
        workflow.add_node("unrecognized_layer", _wrap_master_node("unrecognized_layer", _unrecognized_layer_node))
        workflow.add_node("profile_modify_layer", _wrap_master_node("profile_modify_layer", _profile_modify_layer_node))
        workflow.add_node("super_layer", _wrap_master_node("super_layer", _super_layer_node))
        workflow.add_node("integrator", _wrap_master_node("integrator", integrator_node))
        
        # 设置入口点
        workflow.set_entry_point("intent_recognition")
        
        # 条件路由
        def route_by_intent(state: MasterState) -> str:
            intent = state.get("intent", "conduct")
            print(f"🔀 总控路由到: {intent}_layer")
            return f"{intent}_layer"
        
        workflow.add_conditional_edges(
            "intent_recognition",
            route_by_intent,
            {
                "des_layer": "des_layer",
                "conduct_layer": "conduct_layer",
                "chat_layer": "chat_layer",
                "unrecognized_layer": "unrecognized_layer",
                "profile_modify_layer": "profile_modify_layer",
                "super_layer": "super_layer"
            }
        )
        
        workflow.add_edge("des_layer", "integrator")
        workflow.add_edge("conduct_layer", "integrator")
        workflow.add_edge("chat_layer", "integrator")
        workflow.add_edge("unrecognized_layer", "integrator")
        workflow.add_edge("profile_modify_layer", "integrator")
        workflow.add_edge("super_layer", "integrator")
        workflow.add_edge("integrator", END)
        
        return workflow

    # ==================== 画像个人信息修改（LangGraph 节点调用的处理函数） ====================

    async def _handle_profile_modify(self, user_input: str, user_id: str) -> Dict[str, Any]:
        """
        处理已注册用户的个人信息修改请求
        
        不进入 DES 层，直接用 LLM 提取用户想修改的字段和新值，
        更新到 DynamicFeatureUpdater 的特征中。
        
        Args:
            user_input: 用户原始输入
            user_id: 用户ID
            
        Returns:
            Dict: 处理结果
        """
        print(f"\n✏️ [画像修改] 处理用户 {user_id} 的个人信息修改请求")
        await _emit_node_status("profile_modify", "start")
        await _emit_thinking("profile_modify", "正在分析您的修改请求...")

        try:
            from utils.llm_config import get_chat_openai, set_llm_callback
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            from Agent.main_agent_conduct import SSEThinkingCallbackHandler

            # ★★★ 注入 SSE LLM callback，实现逐词推送 ★★★
            _modify_handler = SSEThinkingCallbackHandler("profile_modify")
            set_llm_callback(_modify_handler)
            llm = get_chat_openai(temperature=0.1)

            prompt = f"""你是一个用户信息修改助手。分析用户的输入，提取出用户想要修改的个人信息字段和对应的新值。

可修改的字段：
- name: 姓名
- major: 专业  
- grade: 年级（如：大一、大二、大三、大四、研一、研二、研三）
- learning_goal: 学习目标
- learning_habits: 学习习惯

如果用户没有明确表达要修改某字段，而是笼统地说"注册""重新注册"之类的，
则返回 modified_fields 为空数组。

请以JSON格式输出，不要输出其他内容：
{{
    "modified_fields": ["字段名"],
    "new_values": {{"字段名": "新值"}},
    "is_redundant": true/false,   // 是否是无意义的重复注册请求
    "message": "对用户的回复"
}}

用户输入：{user_input}
"""

            response = await llm.ainvoke(prompt)
            content = response.content.strip()
            # 尝试提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            import json as _json
            parsed = _json.loads(content)
            modified_fields = parsed.get("modified_fields", [])
            new_values = parsed.get("new_values", {})
            is_redundant = parsed.get("is_redundant", False)
            reply_msg = parsed.get("message", "已收到您的修改请求。")

            if is_redundant or not modified_fields:
                print(f"📌 [画像修改] 用户 {user_id} 的请求为冗余注册，已提示无需重复注册")
                await _emit_node_status("profile_modify", "complete", "redundant_request")
                await _emit_thinking("profile_modify", "已完成处理")
                return {
                    "status": "success",
                    "message": reply_msg or "您已完成学习画像构建，无需重复注册。如需修改信息，请告知具体需要修改的项目。",
                    "modified_fields": [],
                    "is_modified": False
                }

            # ★★★ 有实际修改字段：更新到 DynamicFeatureUpdater ★★★
            updater = DynamicFeatureUpdater()
            features = updater.get_latest_features(user_id) or {}

            # 确保 basic_info 字段存在
            if "basic_info" not in features:
                features["basic_info"] = {}

            # 更新字段
            for field, value in new_values.items():
                if value:
                    features["basic_info"][field] = value
                    print(f"📌 [画像修改] 用户 {user_id} 的 {field} 已更新为: {value}")

            # 保存到磁盘
            updater._save_features_to_disk(user_id, features)
            # ★★★ 同步更新内存缓存，避免同一次会话中后续读取仍是旧数据 ★★★
            if hasattr(updater, '_features_cache'):
                updater._features_cache[user_id] = features.copy()

            # 构建确认消息
            field_names = {"name": "姓名", "major": "专业", "grade": "年级",
                           "learning_goal": "学习目标", "learning_habits": "学习习惯"}
            changed_desc = "、".join([field_names.get(f, f) for f in modified_fields])
            confirm_msg = f"已为您更新{changed_desc}。"

            await _emit_node_status("profile_modify", "complete", "modified")
            await _emit_thinking("profile_modify", f"✅ 已更新{changed_desc}")
            return {
                "status": "success",
                "message": confirm_msg,
                "modified_fields": modified_fields,
                "new_values": new_values,
                "is_modified": True
            }

        except Exception as e:
            print(f"❌ [画像修改] 处理失败: {e}")
            await _emit_node_status("profile_modify", "error", str(e))
            return {
                "status": "error",
                "message": "处理修改请求时出现错误，请稍后重试。",
                "modified_fields": [],
                "is_modified": False
            }

    # ==================== 预分类 ====================

    async def _pre_classify(self, user_input: str, user_id: Optional[str]) -> Dict[str, Any]:
        """
        快速预分类：先用 InputValidator 判断输入有效性，再用语义分类器判断具体意图。
        
        Returns:
            Dict with keys:
              - layer: str  (chat/des/conduct/super/unrecognized/profile_modify)
              - intent: Optional[str]  (classifier 输出的具体意图)
              - confidence: Optional[float]  (classifier 输出的置信度)
        """
        result = {"layer": "chat", "intent": None, "confidence": None, "validation": None}

        if not user_id:
            return result

        des_completed = _check_des_completed(user_id)

        if not des_completed:
            _start_registering(user_id)
            return {**result, "layer": "des"}

        # ★★★ 安全网：清理残留锁 ★★★
        if _is_registering(user_id):
            print(f"⚠️  [预分类] 用户 {user_id} 的注册锁残留，但 DES 已完成，自动清理")
            _finish_registering(user_id)
            _clear_extracted_info(user_id)

        # 延续检测
        continue_keywords = [
            "换一道", "换一个", "再来一道", "再来一个", "换题", "换一题",
            "换道题", "别的题", "另一道", "换道", "换个",
            "再找一些", "在找一些", "再找", "再推荐", "再来",
            "还有吗", "还有没有", "还有",
            "继续", "继续找", "继续推荐", "继续看",
        ]
        if any(kw in user_input for kw in continue_keywords) and user_id and _MEMORY_HUB:
            try:
                prev_task = _MEMORY_HUB.working.get_current_task(user_id)
                if prev_task and prev_task.get("type") in {"practice", "judge_code", "question_gen", "doc_gen",
                                                            "extension", "video", "mindmap", "animation", "study_plan", "ppt"}:
                    return {**result, "layer": "conduct", "intent": prev_task["type"], "confidence": 0.9}
            except Exception:
                pass

        # ★★★ InputValidator：用 LLM 判断输入是否有效 ★★★
        validation = await validate_input_async(user_input)
        result["validation"] = validation  # ★★★ 缓存结果，避免 LangGraph 内重复 LLM 调用+结果不一致 ★★★
        if not validation["is_valid"]:
            print(f"⚠️  [预分类][InputValidator] 输入无效: {validation['reason']}")
            return {**result, "layer": "unrecognized"}

        # ★★★ 始终运行语义分类器（即使 InputValidator 判为 chat），做冲突消解 ★★★
        classifier = get_intent_classifier()
        intent, confidence = classifier.classify(user_input)
        result = {**result, "intent": intent, "confidence": confidence}

        # ★★★ 冲突消解：InputValidator 判 chat 但分类器给出高置信度具体意图 → 信任分类器 ★★★
        if validation["action_type"] == "chat":
            if intent not in ("chat", "unrecognized") and confidence >= 0.65:
                print(f"  ℹ️ [预分类] InputValidator判chat，但分类器高置信为 {intent}({confidence:.2f})，覆盖Validator")
            else:
                print(f"💬  [预分类][InputValidator] 输入为聊天内容，路由到 chat")
                return {**result, "layer": "chat"}

        conduct_intents = {"practice", "judge_code", "question_gen", "doc_gen",
                           "extension", "video", "mindmap", "animation", "study_plan", "ppt"}
        des_intents = {"register", "refine_ppt", "teacher_advice"}
        profile_modify_intents = {"profile_modify"}

        if intent in conduct_intents:
            # ★★★ 裸露关键词拦截：仅意图关键词（无具体主题）→ 无效指令 ★★★
            if _is_bare_keyword_input(user_input, intent):
                print(f"⚠️  [预分类][裸露关键词拦截] 输入'{user_input}'仅为{intent}的裸露关键词，无具体目标信息")
                return {**result, "layer": "unrecognized"}

            # 检测复合意图：置信度≥0.7 且 关键词预筛命中 且 LLM 确认
            if confidence >= 0.7 and _has_compound_intent(user_input, intent) and await _check_compound_with_llm(user_input):
                print(f"⚠️  [预分类] 单意图={intent}({confidence:.2f})，关键词+LLM均检测为复合任务，路由到 SuperAgent")
                return {**result, "layer": "super"}
            return {**result, "layer": "conduct"}
        elif intent in profile_modify_intents:
            print(f"✅ [预分类] 语义识别为profile_modify意图 (置信度: {confidence:.2f})，路由到 profile_modify")
            return {**result, "layer": "profile_modify"}
        elif intent in des_intents:
            if intent == "register":
                print(f"✅ [预分类] 语义识别为register意图 (置信度: {confidence:.2f})，已注册用户路由到 profile_modify")
                return {**result, "layer": "profile_modify"}
            else:
                print(f"✅ [预分类] 语义识别为{intent}意图 (置信度: {confidence:.2f})，路由到 Des层")
                return {**result, "layer": "des"}
        elif intent == "unrecognized":
            print(f"⚠️ [预分类] 语义识别为unrecognized意图 (置信度: {confidence:.2f})，路由到 unrecognized")
            return {**result, "layer": "unrecognized"}

        # 兜底：无法匹配到已知意图的学习类输入 → conduct 层处理
        print(f"✅ [预分类] 学习类输入但未匹配到具体意图 (置信度: {confidence:.2f})，路由到 conduct")
        return {**result, "layer": "conduct"}

    def _build_chat_response(self, chat_result: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        """将 ChatAgent 的结果格式化为标准响应格式"""
        if chat_result.get("status") == "redirect_to_learning":
            return {
                "success": False,
                "data": {
                    "status": "redirect",
                    "layer": "chat",
                    "message": chat_result.get("message", ""),
                    "suggested_task_type": chat_result.get("suggested_task_type"),
                    "intent": chat_result.get("intent"),
                    "metadata": {}
                },
                "suggestion_warning": "",
                "metadata": {
                    "user_id": user_id,
                    "session_id": None
                }
            }

        # 正常对话结果
        reply = chat_result.get("reply", "")
        # ★★★ MemoryHub：记录助手回复到工作记忆 ★★★
        if _MEMORY_HUB and user_id and reply:
            _MEMORY_HUB.working.add_turn(user_id, "assistant", reply[:500])

        return {
            "success": chat_result.get("status") == "success",
            "data": {
                "status": chat_result.get("status", "success"),
                "layer": "chat",
                "data": chat_result,
                "reply": reply,
                "metadata": {
                    "emotion": chat_result.get("metadata", {}).get("emotion"),
                    "urgency": chat_result.get("metadata", {}).get("urgency"),
                }
            },
            "suggestion_warning": "",
            "metadata": {
                "user_id": user_id,
                "session_id": None
            }
        }

    async def process_request(self, user_input: str, user_id: Optional[str] = None, previous_extracted_info: Optional[Dict[str, Any]] = None, enable_tts: bool = False, confirmed: bool = False, override_suggestions: bool = False, ignore_weak_points: bool = False, focus_weak_points: bool = False) -> Dict[str, Any]:
        """
        处理用户请求的主入口(异步)
        
        Args:
            user_input: 用户输入
            user_id: 用户ID(可选)
            previous_extracted_info: 之前提取的用户信息（用于多轮对话）
            enable_tts: 是否启用TTS语音合成
            confirmed: 用户是否已确认覆盖采纳建议
            override_suggestions: 是否忽略已采纳建议按用户要求执行
            ignore_weak_points: 是否忽略薄弱点提示直接生成学习计划
            focus_weak_points: 是否针对薄弱点制定学习计划
        
        Returns:
            Dict: 处理结果
        """
        print("\n" + "="*70)
        print("🎯 Master Controller 开始处理请求")
        print("="*70)
        print(f"用户输入: {user_input}")
        print(f"用户ID: {user_id or '未指定'}")
        if previous_extracted_info:
            print(f"📌 携带历史信息: {list(previous_extracted_info.keys())}")

        if _MEMORY_HUB and user_id:
            _MEMORY_HUB.working.add_turn(user_id, "user", user_input)
            memory_context = _MEMORY_HUB.build_prompt_context(user_id, user_input)
            if memory_context:
                enriched_input = f"{memory_context}\n\n【用户当前问题】{user_input}"
            else:
                enriched_input = user_input
        else:
            enriched_input = user_input

        pre_result = await self._pre_classify(user_input, user_id)
        layer = pre_result.get("layer", "conduct")
        pre_intent = pre_result.get("intent")
        pre_confidence = pre_result.get("confidence")
        pre_validation = pre_result.get("validation")  # ★★★ 复用 InputValidator 结果，避免 LangGraph 内重复调用 ★★★
        if layer == "chat":
            print(f"🔀 Chat层独立处理（绕过LangGraph）")
            await _emit_node_status("chat", "start")
            await _emit_thinking("chat", "💬 开始聊天回复")
            # ★★★ 注入 SSE LLM callback，实现逐词推送 ★★★
            _chat_handler = None
            try:
                from utils.llm_config import set_llm_callback
                from Agent.main_agent_conduct import SSEThinkingCallbackHandler
                _chat_handler = SSEThinkingCallbackHandler("chat")
                set_llm_callback(_chat_handler)
            except Exception:
                pass

            # ★★★ 上报 AgentMonitor：ChatAgent 开始工作 ★★★
            try:
                from Agent.agent_monitor import report_call_start
                report_call_start("tool_general_qa", user_id or "", "ChatAgent独立聊天")  #为了和super执行聊天情况有效结合不出现偏差导致这样写节点
            except Exception:
                pass

            _chat_success = False
            try:
                chat_agent = ChatAgent()
                try:
                    # ★★★ 刷新 LLM 以绑定 callback ★★★
                    chat_agent.llm = chat_agent._initialize_llm()
                except Exception:
                    pass
                chat_result = await chat_agent.chat_async(
                    user_input=enriched_input,
                    user_id=user_id,
                    enable_tts=enable_tts,
                    raw_user_input=user_input
                )
                _chat_success = chat_result.get("status") == "success"
            finally:
                # ★★★ 清除 callback ★★★
                try:
                    from utils.llm_config import set_llm_callback
                    set_llm_callback(None)
                except Exception:
                    pass
                # ★★★ 上报 AgentMonitor：ChatAgent 工作结束（确保无论异常都执行）★★★
                try:
                    from Agent.agent_monitor import report_call_end
                    report_call_end("tool_general_qa", _chat_success)
                except Exception:
                    pass

            result = self._build_chat_response(chat_result, user_id)
            await _emit_node_status("chat", "complete")
            await _emit_thinking("chat", "✅ 聊天回复完成")
            await _emit_task_result(result)
            return result

        # ★★★ SuperAgent 超级智能体处理 ★★★
        if layer == "super":
            print(f"🤖 SuperAgent 独立处理（绕过LangGraph）")
            await _emit_node_status("super", "start")
            await _emit_thinking("super", "🚀 SuperAgent 开始处理复杂任务")

            # ★★★ 上报 AgentMonitor：SuperAgent 开始工作 ★★★
            try:
                from Agent.agent_monitor import report_call_start
                report_call_start("super_agent", user_id or "", "SuperAgent处理复杂任务")
            except Exception:
                pass

            try:
                super_agent = SuperAgent()
                # ★★★ 将原始输入传给 SuperAgent（不添加记忆上下文，避免干扰推理）★★★
                super_result = await super_agent.process(
                    user_input=user_input,  # 使用原始输入
                    user_id=user_id,
                    max_tool_calls=10
                )
                # 如果 SuperAgent 成功返回，使用其结果
                if super_result.get("success"):
                    result = super_result
                else:
                    # SuperAgent 失败，回退到原来的 unrecognized 流程
                    print(f"⚠️ SuperAgent 处理失败，回退到 unrecognized 流程")
                    result = {
                        "success": False,
                        "data": {
                            "status": "unrecognized",
                            "layer": "unrecognized",
                            "type": "invalid_instruction",
                            "message": super_result.get("error", "无法处理该请求"),
                            "raw_input": user_input
                        },
                        "suggestion_warning": "",
                        "metadata": {
                            "user_id": user_id,
                            "session_id": None
                        }
                    }
            except Exception as e:
                print(f"❌ SuperAgent 异常: {e}")
                import traceback
                traceback.print_exc()
                result = {
                    "success": False,
                    "data": {
                        "status": "error",
                        "layer": "super",
                        "error": f"SuperAgent 出错: {str(e)}"
                    },
                    "suggestion_warning": "",
                    "metadata": {
                        "user_id": user_id,
                        "session_id": None
                    }
                }

            # ★★★ 上报 AgentMonitor：SuperAgent 工作结束 ★★★
            try:
                from Agent.agent_monitor import report_call_end
                report_call_end("super_agent", result.get("success", False))
            except Exception:
                pass

            await _emit_node_status("super", "complete")
            await _emit_thinking("super", "✅ SuperAgent 处理完成")
            await _emit_task_result(result)
            return result

        if layer == "unrecognized":
            print(f"⚠️  输入无法识别，直接返回无效指令提示（绕过LangGraph）")
            await _emit_node_status("router", "start")
            await _emit_thinking("router", "⚠️ 输入无法识别，返回提示信息")
            result = {
                "success": False,
                "data": {
                    "status": "unrecognized",
                    "layer": "unrecognized",
                    "type": "invalid_instruction",
                    "message": "无法识别当前输入，请提供具体的学习问题或指令。如果只是说「PPT」「视频」「练习」这类关键词，请加上具体主题，如「二叉树的PPT」。",
                    "raw_input": user_input
                },
                "suggestion_warning": "",
                "metadata": {
                    "user_id": user_id,
                    "session_id": None
                }
            }
            await _emit_node_status("router", "complete")
            await _emit_thinking("router", "✅ 返回无法识别提示")
            await _emit_task_result(result)
            return result
        
        if not previous_extracted_info and user_id and _is_registering(user_id):
            cached_info = _load_extracted_info(user_id)
            if cached_info:
                previous_extracted_info = cached_info

        initial_state = MasterState(
            user_id=user_id,
            user_input=enriched_input,
            raw_user_input=user_input,
            previous_extracted_info=previous_extracted_info,
            intent="",
            action_type="",
            pre_intent=pre_intent,          # ★★★ 复用预分类结果，避免 LanGGraph 内重复分类 ★★★
            pre_confidence=pre_confidence,
            pre_validation=pre_validation,  # ★★★ 复用 InputValidator 结果，避免重复 LLM 调用+结果不一致 ★★★
            des_result=None,
            conduct_result=None,
            final_response=None,
            error=None,
            execution_log=[],
            enable_tts=enable_tts,
            confirmed=confirmed,
            override_suggestions=override_suggestions,
            ignore_weak_points=ignore_weak_points,
            focus_weak_points=focus_weak_points
        )
        
        final_state = await self.app.ainvoke(initial_state)
        
        print("\n" + "="*70)
        print("✅ 请求处理完成")
        print("="*70)
        
        result = final_state.get("final_response", {})
        # ★★★ DES/Conduct 路径完成后也发射 task_result（只发 data 层，避免前端被外层 {success, data, ...} 覆盖导致 task_type 丢失）★★★
        await _emit_task_result(result.get("data", result))
        return result
    
    async def process_request_async(self, user_input: str, user_id: Optional[str] = None, previous_extracted_info: Optional[Dict[str, Any]] = None, enable_tts: bool = False, confirmed: bool = False, override_suggestions: bool = False, ignore_weak_points: bool = False, focus_weak_points: bool = False) -> Dict[str, Any]:
        """异步处理用户请求（直接调用 process_request，无需线程池）"""
        return await self.process_request(
            user_input, user_id, previous_extracted_info, enable_tts,
            confirmed=confirmed, override_suggestions=override_suggestions,
            ignore_weak_points=ignore_weak_points, focus_weak_points=focus_weak_points
        )
