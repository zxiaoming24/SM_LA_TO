"""
主动触发引擎 - 轻量级Agent主动消息生成

功能：
1. 时段问候：用户登录时根据时段（早上/下午/晚上）生成问候
2. 犹豫模式：检测到用户输入卡顿（连续删除3次以上）时生成建议

设计原则：
- 不依赖 SuperAgent（不走 LangGraph 流程）
- 轻量 LLM 单次调用（不走工具调用和多步推理）
- 延迟低，token消耗极小
"""

import re
from typing import Optional, Dict, Any
from datetime import datetime
from utils.llm_config import get_chat_openai
from memory.memory_hub import MemoryHub

# ==================== 时段定义 ====================

def _get_period_text() -> str:
    """根据当前小时返回时段问候词"""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "早上好"
    elif 12 <= hour < 14:
        return "中午好"
    elif 14 <= hour < 18:
        return "下午好"
    elif 18 <= hour < 22:
        return "晚上好"
    else:
        return "夜深了"


# ★★★ 缓存 MemoryHub 实例，避免每次调用重新创建 ★★★
_HUB_CACHE = None

def _get_memory_hub():
    global _HUB_CACHE
    if _HUB_CACHE is None:
        _HUB_CACHE = MemoryHub()
    return _HUB_CACHE


def _build_user_context_text(user_id: str) -> str:
    """从 MemoryHub 拉取用户学习上下文，返回纯文本摘要（失败时返回空字符串）"""
    try:
        hub = _get_memory_hub()
        data = hub.recall(
            user_id=user_id,
            include_working=True,
            include_knowledge=True,
            include_features=True,
            include_stats=True,
            include_reviews=False,
            include_history=False,
            include_study_plan=False,
        )
        parts = []

        # 最近学习主题
        wm = data.get("working_memory", {})
        topic = wm.get("current_topic", "")
        if topic:
            parts.append(f"最近学习主题: {topic}")

        # 知识点掌握
        km = data.get("knowledge_mastery", {})
        if km and "error" not in km:
            summary = km.get("summary", "")
            if summary:
                parts.append(f"知识点掌握: {summary}")
            all_mastery = km.get("all_mastery", [])
            if all_mastery:
                # 取掌握度最高的和最低的
                mastered = [m for m in all_mastery if isinstance(m, dict) and m.get("mastery_level", 0) >= 3]
                weak = [m for m in all_mastery if isinstance(m, dict) and m.get("mastery_level", 0) < 2]
                if mastered:
                    parts.append(f"已掌握: {'、'.join([m.get('knowledge_point','') for m in mastered[:3]])}")
                if weak:
                    parts.append(f"薄弱: {'、'.join([m.get('knowledge_point','') for m in weak[:3]])}")

        # 学习统计
        ls = data.get("learning_stats", {})
        if ls and "error" not in ls:
            stats = []
            solved = ls.get("total_solved", 0)
            if solved:
                stats.append(f"总做题{solved}道")
            acc = ls.get("accuracy", 0)
            if acc:
                stats.append(f"正确率{acc}%")
            if stats:
                parts.append("学习统计: " + "、".join(stats))
            weak_topics = ls.get("weak_topics", [])
            if weak_topics:
                parts.append(f"薄弱点: {'、'.join([w.get('topic','') for w in weak_topics[:3]])}")

        if not parts:
            parts.append("暂无学习记录")

        return "；".join(parts)
    except Exception as e:
        return f""


class ProactiveTriggerEngine:
    """主动触发引擎"""

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        """延迟初始化 LLM 实例（避免每次创建新实例）"""
        if self._llm is None:
            self._llm = get_chat_openai(temperature=0.7, max_tokens=150)
        return self._llm

    # ==================== 时段问候 ====================

    def check_greeting(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        检查是否需要发送时段问候。
        返回: {"text": "消息文本", "keywords": ["关键词1", "关键词2"]}
               或 None（不应触发）
        """
        period = _get_period_text()
        user_context = _build_user_context_text(user_id)

        prompt = f"""你是一位温和的教育AI助教，请根据以下信息生成一句自然的主动问候。

当前时间：{period}
用户学习情况：{user_context}

要求：
1. 以"{period}！"开头，语气温和自然，像真人助教
2. 结合用户的学习内容，提出一个具体的后续学习建议或询问
3. 控制在 80 字以内
4. 对关键知识点名词用单引号括起来（如'CNN卷积'）

示例：
"早上好！昨天你学完了'CNN卷积'，今天要接着看'池化层'吗？还是想复盘错题？"
"下午好！检测到你正在学'循环神经网络'，要不要练几道RNN的题目巩固一下？"
"晚上好！最近你的薄弱点是'梯度消失'，需要我帮你讲解一下吗？"
"夜深了，还在学习呢！你正在看'注意力机制'，要不要我给你总结一下核心要点？"

直接输出问候语，不要带序号和额外说明。"""
        
        try:
            reply = self._get_llm().invoke(prompt)
            text = reply.content.strip() if hasattr(reply, 'content') else str(reply).strip()
            print(f"[ProactiveTrigger] LLM问候回复: {repr(text)}")
            if not text:
                text = None
        except Exception as e:
            print(f"[ProactiveTrigger] LLM问候调用失败: {e}")
            text = None

        # LLM失败或无回复时，使用兜底模板
        if not text:
            text = f"{period}！欢迎回来，有什么想学的吗？"
            keywords = []
        else:
            keywords = [m.group(1) for m in re.finditer(r"'([^']+)'", text)]

        return {
            "text": text,
            "keywords": keywords,
            "type": "greeting"
        }

    # ==================== 犹豫模式 ====================

    def check_hesitation(self, user_id: str, input_prefix: str) -> Optional[Dict[str, Any]]:
        """
        检测到用户输入卡顿后生成建议。
        Args:
            user_id: 用户ID
            input_prefix: 用户当前已输入的部分文本（可能为空）
        返回: {"text": "消息文本", "keywords": ["关键词"]}
               或 None
        """
        user_context = _build_user_context_text(user_id)

        prompt = f"""你是一位温和的教育AI助教。用户正在输入时犹豫不决（打了一些字又删掉了），请根据上下文推测用户可能想问什么。

用户当前输入的部分内容："{input_prefix}"
用户学习情况：{user_context}

要求：
1. 语气温柔、不打断思路，以"看到你在犹豫～"开头
2. 推测 1-2 个用户可能想问的问题
3. 控制在 70 字以内
4. 对关键名词用单引号括起来

示例：
"看到你在犹豫～你是想问'反向传播的链式法则'吗？还是'梯度消失怎么解决'？"
"看到你在犹豫～你是想练习'循环神经网络'的编程题吗？"

直接输出，不要带序号和额外说明。"""
        
        try:
            reply = self._get_llm().invoke(prompt)
            text = reply.content.strip() if hasattr(reply, 'content') else str(reply).strip()
            print(f"[ProactiveTrigger] LLM犹豫回复: {repr(text)}")
            if not text:
                text = None
        except Exception as e:
            print(f"[ProactiveTrigger] LLM犹豫调用失败: {e}")
            text = None

        if not text:
            return None

        keywords = [m.group(1) for m in re.finditer(r"'([^']+)'", text)]

        return {
            "text": text,
            "keywords": keywords,
            "type": "hesitation"
        }
