"""
日常对话子Agent - 负责与用户进行自然交流和情感互动

核心功能：
1. 日常闲聊：处理问候、寒暄、情感交流
2. 生活咨询：回答非学习类问题（娱乐、生活建议等）
3. 情感支持：提供情绪疏导、鼓励和陪伴
4. 上下文记忆：记住对话历史，保持连贯性
5. 智能边界识别：识别何时应该转交给学习相关Agent

设计理念：
- 温暖友好：像朋友一样自然交流
- 适度引导：在闲聊中巧妙引导回学习目标
- 情感共鸣：理解用户情绪，给予适当回应
- 记忆连贯：基于历史对话提供个性化回应
"""

import os
import re
import json
import uuid
import asyncio
import requests
from typing import Dict, Any, Optional, List, AsyncGenerator
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from utils.async_llm_caller import call_llm_with_retry
from utils.llm_config import get_chat_openai

# TTS辅助函数
try:
    from utils.tts_helper import generate_tts_audio
except ImportError:
    from utils.tts_helper import generate_tts_audio

# 支持直接运行和包导入两种方式
try:
    from .dynamic_feature_updater import DynamicFeatureUpdater
    from memory.comprehensive_user_memory import UserMemoryManager
    from memory.conversation_summarizer import ConversationSummarizer
    from memory.memory_hub import MemoryHub
except ImportError:
    from dynamic_feature_updater import DynamicFeatureUpdater
    from memory.comprehensive_user_memory import UserMemoryManager
    from memory.conversation_summarizer import ConversationSummarizer
    from memory.memory_hub import MemoryHub


# ==================== 工具 Schema（Pydantic 模型 → 自动转为 tool schema）====================

class GeneratePracticeInput(BaseModel):
    """生成练习题，用于巩固某个知识点"""
    topic: str = Field(description="知识点")
    difficulty: int = Field(default=3, description="难度等级（1-5），默认3")
    count: int = Field(default=3, description="题目数量，默认3")


class GenerateDocumentInput(BaseModel):
    """生成讲解文档，用于深入理解某个知识点"""
    topic: str = Field(description="知识点")
    difficulty: int = Field(default=3, description="难度等级（1-5），默认3")
    user_id: str = Field(default="", description="用户ID，用于获取个性化学生画像（可选）")


class SearchLocalVideoInput(BaseModel):
    """搜索本地视频库中的教学视频"""
    keyword: str = Field(description="搜索关键词（知识点名称），如'二分查找'、'排序'、'数据结构'等")
    top_k: int = Field(default=1, description="返回的视频数量上限，默认1")


# ==================== 工具函数注册 ====================

_CHAT_TOOL_FUNCTIONS: Dict[str, callable] = {}


def _register_chat_tool(func):
    _CHAT_TOOL_FUNCTIONS[func.__name__] = func
    return func


@_register_chat_tool
async def generate_practice(topic: str, difficulty: int = 3, count: int = 3, user_id: str = "") -> Dict:
    """生成练习题"""
    print(f"\n📝 [ChatTool] 生成练习题: topic={topic}, difficulty={difficulty}, count={count}, user_id={user_id}")
    try:
        from .practice_agent import PracticeAgent
        practice_agent = PracticeAgent()
        
        questions = []
        for _ in range(min(count, 3)):
            result = await practice_agent.generate_problem_async(
                learning_problem=f"{topic}，难度{difficulty}",
                user_id=user_id or "chat_tool_user",
                confirmed=True
            )
            if result and not result.get("needs_confirmation"):
                questions.append(result)
        
        return {
            "status": "success",
            "tool_type": "practice_gen",
            "topic": topic,
            "difficulty": difficulty,
            "data": questions,
            "count": len(questions)
        }
    except Exception as e:
        print(f"❌ [ChatTool] 练习题生成失败: {e}")
        return {
            "status": "error",
            "tool_type": "practice_gen",
            "topic": topic,
            "error": str(e)
        }


@_register_chat_tool
async def generate_document(topic: str, difficulty: int = 3, user_id: str = "") -> Dict:
    """生成讲解文档"""
    print(f"\n📄 [ChatTool] 生成讲解文档: topic={topic}, difficulty={difficulty}, user_id={user_id}")
    try:
        from .course_doc_agent_ali import CourseDocAgent
        doc_agent = CourseDocAgent()
        
        features = None
        if user_id:
            try:
                from .dynamic_feature_updater import DynamicFeatureUpdater
                feature_updater = DynamicFeatureUpdater()
                features = await feature_updater.get_latest_features_async(user_id)
                print(f"   ✅ 获取到用户 {user_id} 的特征数据")
            except Exception as e:
                print(f"   ⚠️ 获取用户特征失败: {e}")
        
        student_info = {
            "major": features.get("academic_background", {}).get("major_preference", "计算机") if features else "计算机",
            "course_name": topic,
            "weak_points": topic,
            "learn_level": "medium",
            "student_feature": features or {}
        }
        
        result = await doc_agent.generate_course_document_async(
            student_info=student_info,
            user_id=user_id or "chat_tool_user",
            enable_tts=False
        )
        
        if result:
            doc_title = result.get("title", "") or result.get("doc_title", "") or f"文档：{topic}"
            doc_content = result.get("content", "") or result.get("doc_content", "")
            resource_id = result.get("resource_id", "") or result.get("id", "")
            
            data = {
                "title": doc_title,
                "content": doc_content,
                "knowledge_points": result.get("knowledge_points", []) or result.get("knowledge_points_list", []),
                "file_path": result.get("file_path", ""),
                "resource_id": resource_id,
                "oss_url": result.get("oss_url", "")
            }
            
            if user_id and resource_id:
                try:
                    from memory.content_store import ContentStore
                    store = ContentStore()
                    store.save(user_id, "document", resource_id, data)
                    print(f"   ✅ 文档已保存到用户资源库 (doc/{resource_id})")
                except Exception as e:
                    print(f"   ⚠️ 文档保存到资源库失败: {e}")
            
            return {
                "status": "success",
                "tool_type": "doc_gen",
                "topic": topic,
                "difficulty": difficulty,
                "data": data
            }
        else:
            return {
                "status": "error",
                "tool_type": "doc_gen",
                "topic": topic,
                "error": "文档生成返回空结果"
            }
    except Exception as e:
        print(f"❌ [ChatTool] 文档生成失败: {e}")
        return {
            "status": "error",
            "tool_type": "doc_gen",
            "topic": topic,
            "error": str(e)
        }


@_register_chat_tool
async def search_local_video(keyword: str, top_k: int = 1, user_id: str = "") -> Dict:
    """搜索视频库中的教学视频（优先 OSS，OSS 不可用时回退本地目录）"""
    print(f"\n🎬 [ChatTool] 搜索视频: keyword={keyword}, top_k={top_k}, user_id={user_id}")

    # 优先从 OSS 搜索
    try:
        from services.oss_storage import list_files as oss_list_files, get_object_url as oss_get_url

        oss_files = oss_list_files(prefix="video/", max_keys=200)
        if oss_files:
            results = []
            for f in oss_files:
                ext = f.get("ext", "").lower()
                if ext not in ('.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'):
                    continue
                name_without_ext = os.path.splitext(f["filename"])[0]
                if keyword.lower() not in name_without_ext.lower():
                    continue
                url = oss_get_url(f["key"], public=True) or ""
                results.append({
                    "filename": f["filename"],
                    "title": name_without_ext,
                    "url": url,
                    "size": f["size"],
                    "ext": ext,
                    "modified": f["last_modified"],
                    "source": "oss"
                })

            results.sort(key=lambda x: x["modified"], reverse=True)
            results = results[:top_k]

            print(f"   ✅ [OSS] 找到 {len(results)} 个视频")
            return {
                "status": "success",
                "tool_type": "local_video_search",
                "keyword": keyword,
                "data": results,
                "count": len(results),
                "source": "oss"
            }
    except Exception as e:
        print(f"  ⚠️ [OSS] 视频搜索失败 ({e})，回退本地目录")

    # 回退：搜索本地视频目录
    print("  -- 回退到本地视频目录搜索 --")
    try:
        video_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "rag_knowledge", "video_data"
        )

        if not os.path.exists(video_dir):
            print(f"   ⚠️ 视频目录不存在: {video_dir}")
            return {
                "status": "success",
                "tool_type": "local_video_search",
                "keyword": keyword,
                "data": [],
                "count": 0,
                "message": "视频库为空"
            }

        results = []
        for f in os.listdir(video_dir):
            fp = os.path.join(video_dir, f)
            if not os.path.isfile(fp):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in ('.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'):
                continue

            name_without_ext = os.path.splitext(f)[0]
            if keyword.lower() not in name_without_ext.lower():
                continue

            results.append({
                "filename": f,
                "title": name_without_ext,
                "url": f"/video-data/{f}",
                "size": os.path.getsize(fp),
                "ext": ext,
                "modified": os.path.getmtime(fp),
                "source": "local"
            })

        results.sort(key=lambda x: x["modified"], reverse=True)
        results = results[:top_k]

        print(f"   ✅ [本地] 找到 {len(results)} 个视频")
        return {
            "status": "success",
            "tool_type": "local_video_search",
            "keyword": keyword,
            "data": results,
            "count": len(results),
            "source": "local"
        }

    except Exception as e:
        print(f"❌ [ChatTool] 视频搜索失败: {e}")
        return {
            "status": "error",
            "tool_type": "local_video_search",
            "keyword": keyword,
            "error": str(e)
        }


# 工具 Schema 列表
_CHAT_TOOL_SCHEMAS = [
    GeneratePracticeInput,
    GenerateDocumentInput,
    SearchLocalVideoInput,
]


class ChatAgent:
    """
    日常对话Agent - 提供自然交流和情感互动功能
    """

    def __init__(self):
        """初始化日常对话Agent"""
        self.llm = self._initialize_llm()
        self.chat_template = self._create_chat_template()
        self.intent_template = self._create_intent_template()
        
        # 初始化动态特征更新器（用于记录情感状态）
        self.feature_updater = DynamicFeatureUpdater()
        
        # 初始化记忆管理器（用于保存对话历史）
        self.memory_manager = UserMemoryManager()
        
        # ★★★ 初始化对话摘要生成器 ★★★
        self.summarizer = ConversationSummarizer()
        
        # ★★★ 验证工具函数注册情况 ★★★
        print(f"✅ ChatAgent 工具函数注册状态: {list(_CHAT_TOOL_FUNCTIONS.keys())}")

        # ★★★ MemoryHub 统一记忆中心 ★★★
        try:
            self.memory_hub = MemoryHub()
        except Exception:
            self.memory_hub = None

        # 对话历史缓存（内存中）
        self._conversation_cache = {}
        
        # 摘要触发阈值：每N轮对话生成一次摘要
        self.summary_trigger_threshold = 10

    def _initialize_llm(self):
        """初始化LLM模型（使用统一配置，绑定多模态工具）"""
        try:
            llm = get_chat_openai(temperature=0.8, max_tokens=1000)
            return llm.bind_tools(_CHAT_TOOL_SCHEMAS)
        except Exception as e:
            raise Exception(f"初始化日常对话Agent LLM失败: {e}")

    def _create_chat_template(self) -> PromptTemplate:
        """创建日常对话的提示词模板"""
        template = """
你是一位温暖、友善、善解人意的AI伙伴，名叫"小助手"。你的特点是：

**角色定位：**
- 像朋友一样自然交流，不机械、不生硬
- 善于倾听和理解用户的情感需求
- 幽默风趣但不轻浮，专业但不刻板
- 能够适时给予鼓励和支持

**重要原则（必须严格遵守）：**
1. **禁止编造用户信息**：如果不知道用户的名字或其他信息，直接说不知道，不要编造任何虚假信息
2. **诚实回应**：当用户问你"你知道我叫什么吗"时，如果没有历史记录，就诚实地说"我还不知道你的名字呢"
3. **基于事实**：只使用提供的用户信息和对话历史，不要臆测或编造
4. **精准报告数字**：当用户问"有几个/多少"时，严格使用【用户实时上下文】中的具体数字回答，不要自己估算或编造。如果上下文中有多个来源的同类数据（如"知识点复习"和"资源复习"），要区分清楚
5. **自然流畅**：像真人聊天一样，避免机器人式的回答
6. **情感共鸣**：理解用户的情绪，给予适当的共情回应
7. **适度引导**：在闲聊中可以巧妙提及学习目标，但不要强行推销
8. **个性化**：根据用户的历史对话和特征提供个性化回应

**当前用户信息（如果有）：**
{user_info}

**用户特征画像（8维度得分，用于主动调整回复风格）：**
{user_features}

**用户最新评估报告（薄弱点和评估状态）：**
{user_assessment}

**用户实时上下文（当前在做什么、最近学习情况）：**
{user_real_time_context}

【重要说明】上面的【用户实时上下文】是系统自动感知到的信息，请基于此主动关心用户当前的学习状态。例如：
- **如果上下文中有「视频回溯-用户刚标记困惑，优先处理」标签**：这是最高优先级信息！用户刚回退了视频并确认有困惑。**请先基于该标签下的字幕内容主动解答**，而不是推荐学习计划或做题。例如询问用户是否对字幕中的某个概念有疑问，或直接解释该段内容。
- 如果用户在做题且得分低，主动询问是否需要帮助
- 如果用户在看学习计划，主动询问是否需要调整
- 如果用户最近有错题，主动提出可以一起分析原因
- **不要等用户问才提及这些上下文**，要在回复中自然体现你"看到了"用户在做什么

**【关键】回复语气必须根据用户画像动态调整：**
- **confidence_level = 低/不自信/沮丧** → 多用鼓励语言（"你一定能学会"、"没关系慢慢来"），降低语气严肃感，增加温暖感，避免直接指出错误
- **confidence_level = 高/自信/积极** → 语气可以更直接有力，适当增加挑战感和成就感，适度推进学习目标
- **interest_level = 高** → 回复可以更有热情，主动延伸话题
- **interest_level = 低** → 回复简洁轻松，避免长篇大论，多用轻松话题引导
- **frustration_tolerance = 低** → 遇到用户抱怨时先共情再给方案，不直接讲道理
- **frustration_tolerance = 高** → 可以更直接给建议，信任用户的承受能力

**对话历史（最近5轮）：**
{conversation_history}

**参考证据（知识库 / 联网搜索结果）：**
{rag_context}

**专家回答规则（当有参考证据时必须遵守）：**
1. 回答必须基于上述参考证据，不要编造证据中没有的信息
2. 如果证据与问题不完全相关，基于证据回答相关部分，对不相关部分诚实说明"我没有找到确切资料"
3. 回答末尾用【来源】标注引用了哪些证据来源（如"来源：知识库"或"来源：联网搜索"）
4. 如果没有任何参考证据，基于自身知识回答，但要在开头注明"以下回答基于通用知识，未找到权威参考资料"
5. 回答要专业、准确、有条理，像一位真正的专家在解答

**当前用户输入：**
{user_input}

**请按照以下要求回复：**
1. **如果用户询问自己的特征、得分或学习状态**：请根据【用户特征画像】中的数据给出准确、客观的回答。例如："根据你的最新记录，你的认知能力得分是90分，表现非常出色！"
2. **【必须】对照【回复语气规则】主动调整本次回复的语气**，不要等用户问"我的情绪怎么样"才引用画像
3. 理解用户的意图和情感状态，给出自然、温暖、个性化的回应。
4. 保持对话的连贯性和趣味性，口语化、亲切自然。
5. **绝对不要编造用户的姓名或其他个人信息**，如果画像中没有某项信息，请诚实告知。

**回复风格：**
- 知识问答时专业、有条理，像专家解答
- 日常闲聊时口语化、亲切自然
- 可以适当使用表情符号（但不要过多）
- 可以提出问题延续对话

**工具调用规则（非常重要）：**

**何时调用工具：**
当用户明确表达以下需求时，必须调用相应工具：
1. **本地视频搜索**：用户说"看视频"、"搜视频"、"播放视频"、"我想看...视频"、"有没有...的视频"、"找...的视频"、"视频教程"、"视频讲解"、询问某个知识点是否有视频等 → **立即调用** search_local_video 工具（不要先回答知识内容，先搜索视频）
2. **练习题生成**：用户说"生成题目"、"出几道题"、"练习题"、"做题"、"练习"等 → 调用 generate_practice 工具
3. **文档生成**：用户说"生成文档"、"讲解文档"、"写个文档"、"资料"、"教程"等 → 调用 generate_document 工具  

**何时直接回复（不调用工具）：**
以下情况直接回复，不需要调用任何工具：
1. **日常闲聊**：打招呼、问候、聊天、情感交流（如"你好"、"今天天气不错"、"我心情不好"）
2. **知识问答**：询问概念、解释原理、讨论问题（如"什么是递归"、"Python和Java有什么区别"）
3. **学习建议**：询问学习方法、建议（如"怎么学好编程"、"推荐什么书"）

**工具调用示例：**
- 用户："我想看二分查找的视频" → 调用 search_local_video(keyword="二分查找")
- 用户："搜索冒泡排序的视频" → 调用 search_local_video(keyword="冒泡排序")
- 用户："帮我生成一道关于循环的编程题" → 调用 generate_practice(topic="循环", difficulty=2, count=1)
- 用户："写一份递归的讲解文档" → 调用 generate_document(topic="递归", difficulty=2)

**直接回复示例：**
- 用户："你好" → 直接回复"你好呀！有什么我可以帮你的吗？"
- 用户："什么是递归" → 直接解释递归的概念
- 用户："今天心情不太好" → 直接共情回复

请根据用户输入判断：如果是明确要求生成资源，则调用工具；否则直接回复。
""".strip()

        return PromptTemplate.from_template(template)

    def _create_intent_template(self) -> PromptTemplate:
        """创建意图识别的提示词模板"""
        template = """
你是一个意图分类专家，负责判断用户输入的意图类型。

**用户输入：**
{user_input}

**请判断以下维度：**

1. **主要意图类型**（选择一个）：
   - casual_chat: 日常闲聊、问候、寒暄
   - emotional_support: 寻求情感支持、倾诉烦恼
   - life_advice: 生活建议、娱乐咨询
   - learning_related: 学习/技术/知识类问题（如问概念、原理、最新技术动态、编程、算法等）
   - system_query: 系统功能查询
   - other: 其他

2. **情感倾向**：
   - positive: 积极、开心、兴奋
   - neutral: 中性、平静
   - negative: 消极、焦虑、沮丧
   - mixed: 混合情绪

3. **是否需要转交学习Agent**：
   - true: 涉及具体学习任务（编程、视频、文档等）
   - false: 纯闲聊或情感交流

4. **紧急程度**：
   - high: 需要立即关注（如严重情绪问题）
   - medium: 正常对话
   - low: 简单问候

**输出格式（JSON）：**
{{
  "intent_type": "casual_chat/emotional_support/life_advice/learning_related/system_query/other",
  "emotion": "positive/neutral/negative/mixed",
  "need_learning_agent": true/false,
  "urgency": "high/medium/low",
  "confidence": 0-100,
  "reason": "判断理由",
  "suggested_action": "继续对话/转交学习Agent/提供情感支持/其他建议"
}}

**示例：**
- 输入："你好啊，今天心情不错" 
  → {{"intent_type": "casual_chat", "emotion": "positive", "need_learning_agent": false, ...}}
  
- 输入："我好焦虑，考试快到了还没复习"
  → {{"intent_type": "emotional_support", "emotion": "negative", "need_learning_agent": true, ...}}
  
- 输入："帮我生成一道Python练习题"
  → {{"intent_type": "learning_related", "emotion": "neutral", "need_learning_agent": true, ...}}

**重要提醒：**
- 只输出JSON格式
- 判断要准确合理
- 对于模糊情况，倾向于继续对话而非转交
""".strip()

        return PromptTemplate.from_template(template)

    def _get_user_context_service(self):
        """延迟加载 UserContextService"""
        try:
            from services.user_context_service import UserContextService
            return UserContextService()
        except Exception:
            return None

    async def _get_latest_assessment(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户最新的评估报告（异步，避免阻塞事件循环）"""
        try:
            from .learning_assessment_agent import LearningAssessmentAgent
            agent = LearningAssessmentAgent()
            return await asyncio.to_thread(agent.get_latest_assessment, user_id)
        except Exception as e:
            print(f"   ⚠️ 获取评估报告失败: {e}")
            return None

    def _format_assessment_for_prompt(self, assessment: Dict[str, Any]) -> str:
        """格式化评估报告供prompt使用，突出薄弱点"""
        lines = []
        
        # 评估基本信息
        assessment_id = assessment.get('assessment_id', '')
        if assessment_id:
            lines.append(f"- 评估ID: {assessment_id}")
        
        # 总体评估等级
        overall_level = assessment.get('overall_level', '')
        if overall_level:
            lines.append(f"- 总体评估: {overall_level}")
        
        # 薄弱点（重点突出）
        weak_points = assessment.get('weak_points', [])
        if weak_points:
            lines.append("\n【薄弱点（需重点关注）】")
            for i, wp in enumerate(weak_points, 1):
                point = wp.get('point', '')
                priority = wp.get('priority', '')
                performance = wp.get('performance', '')
                line = f"{i}. {point}"
                if priority:
                    line += f" (优先级: {priority})"
                if performance:
                    line += f" - {performance}"
                lines.append(line)
        
        # 维度评分
        dimensions = assessment.get('dimensions', [])
        if dimensions:
            lines.append("\n【各维度评分】")
            for dim in dimensions:
                name = dim.get('name', '')
                score = dim.get('score', '')
                analysis = dim.get('analysis', '')[:30] if dim.get('analysis') else ''
                if name and score:
                    line = f"- {name}: {score}分"
                    if analysis:
                        line += f" ({analysis}...)"
                    lines.append(line)
        
        # 建议
        suggestions = assessment.get('suggestions', [])
        if suggestions:
            lines.append("\n【评估建议】")
            for i, suggestion in enumerate(suggestions, 1):
                suggestion_text = suggestion.get('suggestion', '')[:50]
                lines.append(f"{i}. {suggestion_text}...")
        
        return "\n".join(lines) if lines else "暂无评估报告"

    async def chat_async(
        self,
        user_input: str,
        user_id: Optional[str] = None,
        conversation_context: Optional[List[Dict[str, str]]] = None,
        enable_tts: bool = False,
        raw_user_input: Optional[str] = None,
        page_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        异步进行日常对话
        
        Args:
            user_input: 用户输入（可能包含记忆上下文）
            user_id: 用户ID（**必需**，用于隔离不同用户的对话历史）
            conversation_context: 对话上下文历史
            enable_tts: 是否启用TTS
            raw_user_input: 用户原始输入（用于判断是否检索知识库，不含记忆上下文）
            
        Returns:
            Dict: 对话结果
        """
        try:
            # ★★★ 强制要求 user_id ★★★
            if not user_id:
                print("❌ [日常对话Agent] 错误：缺少 user_id")
                return {
                    "status": "error",
                    "type": "casual_chat",
                    "reply": "抱歉，我需要知道您的用户ID才能与您聊天。请提供用户ID后再试。",
                    "error": "Missing user_id"
                }
            
            print(f"\n💬 [日常对话Agent] 处理用户输入 (user_id: {user_id})...")
            
            # 步骤1: 意图识别(异步)
            intent_result = await self._identify_intent_async(user_input)
            print(f"   意图类型: {intent_result.get('intent_type')}")
            print(f"   情感倾向: {intent_result.get('emotion')}")
            
            # 步骤2: 检测学习相关意图（仅记录日志，不再拒绝）
            # ★★★ ChatAgent 具备通过 RAG + LLM 回答概念解释类问题的能力，
            # 不应拒绝学习相关问题。生成资源类任务已在总控层由意图分类器分流到 conduct 层。★★★
            need_learning_agent = intent_result.get('need_learning_agent', False)
            is_profile_query = any(keyword in user_input for keyword in ["特征", "画像", "我的信息", "我的资料", "我是谁", "我的专业", "我的年级"])
            if need_learning_agent:
                print(f"   📚 检测到学习相关意图，ChatAgent将通过 RAG + LLM 回答")
            if is_profile_query:
                print(f"   👤 检测到画像查询意图")
            
            # 步骤3: 获取用户信息和特征
            user_info = ""
            user_features = ""
            
            if user_id:
                # ★★★ 异步获取最新的8维度特征（避免文件IO阻塞事件循环）★★★
                features = await self.feature_updater.get_latest_features_async(user_id)
                if features:
                    # 格式化特征字符串，方便LLM阅读
                    user_features = json.dumps(features, ensure_ascii=False, indent=2)
                
                # 构建用户信息摘要
                user_info = f"用户ID: {user_id}"
            
            # 步骤4: 格式化对话历史
            conversation_history = self._format_conversation_history(
                conversation_context or self._get_conversation_history(user_id)
            )
            
            # ★★★ 步骤4.5+4.6: 并发获取证据(知识库+联网搜索) + 用户实时上下文 ★★★
            rag_context = ""
            evidence_sources = []
            evidence_method = "none"
            user_real_time_context = ""
            query_for_knowledge = raw_user_input or user_input

            async def _fetch_rag():
                nonlocal rag_context, evidence_sources, evidence_method
                if not user_id:
                    return

                # ★★★ 仅学习类问题才走知识库检索和联网兜底 ★★★
                if intent_result.get("intent_type") != "learning_related":   #  识别关键 只有识别到是知识学习情况才会联网精确进行
                    print(f"   💬 非学习类问题（{intent_result.get('intent_type')}），跳过知识库和联网搜索")
                    return

                # ★★★ 学习类问题走 KB 检索 → 不足则联网兜底 ★★★
                try:
                    evidence = await self._gather_evidence(query_for_knowledge, user_id)
                    rag_context = evidence.get("context", "")
                    evidence_sources = evidence.get("sources", [])
                    evidence_method = evidence.get("method", "none")
                    if evidence_sources:
                        print(f"   ✅ 收集到 {len(evidence_sources)} 条证据（方式: {evidence_method}）")
                except Exception as e:
                    print(f"   ⚠️  证据收集失败: {e}")

            async def _fetch_context():
                nonlocal user_real_time_context
                if not user_id:
                    return
                try:
                    ctx_service = self._get_user_context_service()
                    if ctx_service:
                        if page_context:
                            await ctx_service.update_page_context(user_id, page_context)
                        # ★★★ 【三层记忆架构】使用三层记忆 Prompt（短期/中期/长期）★★★
                        context_text = await ctx_service.build_three_tier_prompt_async(user_id)
                        if context_text:
                            user_real_time_context = context_text
                            print(f"   📡 已获取用户实时上下文（三层记忆）({len(context_text)} chars)")
                except Exception as e:
                    print(f"   ⚠️ 获取用户实时上下文失败: {e}")

            await asyncio.gather(_fetch_rag(), _fetch_context(), return_exceptions=True)
            
            # ★★★ 获取用户最新评估报告（注入对话上下文）★★★
            user_assessment = ""
            if user_id:
                assessment = await self._get_latest_assessment(user_id)
                if assessment:
                    # 格式化评估报告，突出薄弱点
                    assessment_summary = self._format_assessment_for_prompt(assessment)
                    if assessment_summary:
                        user_assessment = assessment_summary
                        print(f"   📋 已获取用户评估报告 ({len(user_assessment)} chars)")
            
            # 步骤5: 构建对话消息列表（支持工具调用）
            prompt = self.chat_template.format(
                user_info=user_info,
                user_features=user_features,
                user_assessment=user_assessment,
                user_real_time_context=user_real_time_context,
                conversation_history=conversation_history,
                rag_context=rag_context,
                user_input=user_input
            )
            
            messages = [{"role": "system", "content": prompt}]
            
            # 添加用户消息
            messages.append({"role": "user", "content": user_input})
            
            # 步骤6: 工具调用循环（类似 admin_helper_agent 的处理方式）
            tool_results = []
            max_rounds = 10
            
            for _ in range(max_rounds):
                response = await call_llm_with_retry(self.llm, messages, error_msg="ChatAgent LLM调用")
                
                raw_calls = getattr(response, 'tool_calls', None) or response.additional_kwargs.get('tool_calls', [])
                
                if raw_calls:
                    response_content = getattr(response, 'content', '')
                    if isinstance(response_content, list):
                        response_content = ''.join(str(c) for c in response_content)
                    elif response_content is None:
                        response_content = ''

                    assistant_msg_dict = {
                        "role": "assistant",
                        "content": response_content,
                        "tool_calls": []
                    }

                    valid_tool_calls = []
                    for tc in raw_calls:
                        tool_name = ""
                        tool_args = {}
                        tool_call_id = ""
                        
                        if isinstance(tc, dict):
                            if 'function' in tc:
                                tool_name = tc['function'].get('name', '')
                                raw_args = tc['function'].get('arguments', '{}')
                                try:
                                    tool_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                                except json.JSONDecodeError:
                                    tool_args = {}
                                tool_call_id = tc.get('id', '')
                            elif 'name' in tc:
                                tool_name = tc.get('name', '')
                                tool_args = tc.get('args', {})
                                tool_call_id = tc.get('id', '')
                        else:
                            tool_name = tc.name
                            tool_args = tc.args
                            tool_call_id = tc.id

                        if not tool_name:
                            continue

                        if not tool_call_id:
                            tool_call_id = f"auto_gen_{uuid.uuid4().hex[:8]}"

                        arguments_str = json.dumps(tool_args, ensure_ascii=False) if isinstance(tool_args, dict) else str(tool_args)
                        valid_tool_calls.append({
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": arguments_str
                            }
                        })

                    if not valid_tool_calls:
                        messages.append({"role": "assistant", "content": response.content or ""})
                        reply_content = response.content or ""
                        break

                    assistant_msg_dict["tool_calls"] = valid_tool_calls
                    messages.append(assistant_msg_dict)

                    for tc in valid_tool_calls:
                        tool_name = tc["function"]["name"]
                        tool_args = json.loads(tc["function"]["arguments"])
                        tool_call_id = tc["id"]

                        # 将 user_id 注入工具参数，用于获取个性化用户画像
                        if user_id and "user_id" not in tool_args:
                            tool_args["user_id"] = user_id

                        # 执行工具并获取结果
                        tool_result_data = None
                        async for ev in self._execute_chat_tool(tool_name, tool_args, tool_call_id):
                            tool_results.append(ev)
                            if ev.get('result'):
                                tool_result_data = ev['result']

                        # ★★★ 关键：将工具结果添加到 messages 列表，否则 LLM 会报错 ★★★
                        messages.append({
                            "role": "tool",
                            "content": json.dumps(tool_result_data or {}, ensure_ascii=False),
                            "tool_call_id": tool_call_id
                        })
                            
                    continue

                reply_content = response.content if hasattr(response, 'content') else str(response)
                messages.append({"role": "assistant", "content": reply_content})
                break
            
            print(f"   ✅ 生成回复完成")
            
            # 步骤6.5: 防幻觉检查
            reply_content = await self._check_hallucination(reply_content, rag_context)

            # ★★★ 步骤6.6: 自动图片搜索（仅学习类且证据不足时才搜）★★★
            image_results = []
            query_for_image = raw_user_input or user_input
            is_learning = intent_result.get("intent_type") == "learning_related"
            need_image_search = is_learning and evidence_method not in ("knowledge_base",)
            if need_image_search:
                print(f"   🖼️ 证据不足，自动搜索相关图片...")
                image_results = await self._web_image_search(query_for_image, max_results=2)
                if image_results:
                    print(f"   ✅ 已获取 {len(image_results)} 张相关图片")
            elif is_learning:
                print(f"   📚 知识库已提供足够证据，跳过图片搜索")
            
            # 步骤7: 保存对话到记忆系统
            if user_id:
                await self._save_conversation(user_id, user_input, reply_content)

                emotion = intent_result.get('emotion', 'neutral')
                intent_type = intent_result.get('intent_type', 'casual_chat')
                if emotion in ['positive', 'negative', 'mixed'] or intent_type in ['learning_related', 'system_query']:
                    asyncio.create_task(self._update_features_from_chat(
                        user_id, user_input, reply_content, intent_result
                    ))

                if self.memory_hub:
                    learning_kws = ["循环", "递归", "函数", "数组", "指针", "链表",
                                    "排序", "搜索", "类", "对象", "继承", "多态",
                                    "文件", "异常", "正则", "线程", "协程", "数据库",
                                    "网络", "算法", "数据结构", "编程", "代码",
                                    "Python", "Java", "C++", "JavaScript"]
                    query_for_kp = raw_user_input or user_input
                    found_kps = [kw for kw in learning_kws if kw in query_for_kp]
                    for kp in found_kps:
                        self.memory_hub.working.add_focus_knowledge(user_id, kp)
                    if found_kps:
                        self.memory_hub.working.set_current_topic(user_id, found_kps[0])
                        self.memory_hub.knowledge.record_activity(
                            user_id, found_kps[0],
                            correct=None, activity_type="chat_discussion"
                        )
                        print(f"   📌 [ChatAgent] 已记录知识点焦点: {found_kps}")
            
            # 步骤8: 构建返回结果
            result = {
                "status": "success",
                "type": "casual_chat",
                "reply": reply_content.strip(),
                "intent": intent_result,
                "sources": evidence_sources,          # ★★★ 证据来源列表 ★★★
                "evidence_method": evidence_method,   # ★★★ 证据收集方式 ★★★
                "tool_results": tool_results,         # ★★★ 工具执行结果 ★★★
                "images": image_results,              # ★★★ 自动搜索的相关图片 ★★★
                "metadata": {
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat(),
                    "emotion": intent_result.get('emotion'),
                    "urgency": intent_result.get('urgency')
                }
            }
            
            # 步骤9: TTS语音合成（可选）
            if enable_tts:
                tts_path = await generate_tts_audio(
                    text=reply_content.strip(),
                    agent_name="chat_agent",
                    user_id=user_id
                )
                if tts_path:
                    result["tts_audio_path"] = tts_path
            
            return result
            
        except Exception as e:
            print(f"❌ 日常对话Agent执行失败: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "status": "error",
                "type": "casual_chat",
                "reply": "抱歉，我刚才走神了😅 能再说一遍吗？",
                "error": str(e)
            }

    async def _identify_intent_async(self, user_input: str) -> Dict[str, Any]:
        """异步识别用户意图"""
        try:
            prompt = self.intent_template.format(user_input=user_input)
            response = await call_llm_with_retry(self.llm, prompt, error_msg="ChatAgent意图识别LLM调用")
            intent_text = response.content if hasattr(response, 'content') else str(response)
            
            # 解析JSON
            intent_data = self._parse_json_response(intent_text)
            
            if intent_data:
                return intent_data
            else:
                # 默认意图
                return {
                    "intent_type": "casual_chat",
                    "emotion": "neutral",
                    "need_learning_agent": False,
                    "urgency": "medium",
                    "confidence": 50,
                    "reason": "无法准确识别意图，默认为日常闲聊",
                    "suggested_action": "继续对话"
                }
                
        except Exception as e:
            print(f"⚠️ 意图识别失败: {e}")
            return {
                "intent_type": "casual_chat",
                "emotion": "neutral",
                "need_learning_agent": False,
                "urgency": "medium",
                "confidence": 30,
                "reason": f"意图识别出错: {str(e)}",
                "suggested_action": "继续对话"
            }

    def _map_intent_to_task(self, intent_result: Dict[str, Any]) -> Optional[str]:
        """将意图映射到具体的任务类型"""
        intent_type = intent_result.get('intent_type', '')
        
        # 根据意图类型推断可能的任务
        if '练习' in intent_result.get('reason', '') or '编程' in intent_result.get('reason', ''):
            return 'practice'
        elif '视频' in intent_result.get('reason', ''):
            return 'video'
        elif '文档' in intent_result.get('reason', '') or '讲解' in intent_result.get('reason', ''):
            return 'doc_gen'
        elif '题目' in intent_result.get('reason', '') or '测试' in intent_result.get('reason', ''):
            return 'question_gen'
        else:
            return None
    
    # ==================== 工具执行方法 ====================
    
    @staticmethod
    def _model_name_to_func_name(model_name: str) -> str:
        """将 Pydantic 模型名称转换为工具函数名称"""
        if model_name.endswith('Input'):
            model_name = model_name[:-5]
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', model_name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    async def _execute_chat_tool(self, tool_name: str, tool_args: dict, tool_call_id: str = "") -> AsyncGenerator[Dict, None]:
        """执行工具并返回结果（类似 admin_helper_agent 的处理方式）"""
        final_tool_name = tool_name
        result = None

        print(f"[ChatTool] 尝试执行工具: tool_name={tool_name}, tool_args={tool_args}")
        
        func = _CHAT_TOOL_FUNCTIONS.get(tool_name)
        if not func:
            converted_name = self._model_name_to_func_name(tool_name)
            print(f"[ChatTool] 转换工具名称: {tool_name} -> {converted_name}")
            func = _CHAT_TOOL_FUNCTIONS.get(converted_name)
            if func:
                print(f"[ChatTool] 转换成功，找到函数: {converted_name}")
                final_tool_name = converted_name
            else:
                print(f"[ChatTool] 转换失败，未找到函数: {converted_name}")

        if func is not None:
            print(f"[ChatTool] 开始调用函数: {final_tool_name}")
            try:
                result = await func(**tool_args)
                print(f"[ChatTool] 函数调用成功，结果: {result}")
            except Exception as e:
                print(f"[ChatTool] 函数调用失败: {e}")
                result = {"error": str(e)}
        else:
            result = {"error": f"未知工具: {tool_name}"}
            print(f"[ChatTool] 未找到工具函数: {tool_name}")

        yield {"type": "tool_result", "tool": final_tool_name, "args": tool_args, "result": result}
    
    def _is_knowledge_question(self, user_input: str) -> bool:
        """
        判断用户问题是否是知识性问题（需要检索知识库）
        
        Args:
            user_input: 用户输入
            
        Returns:
            True表示是知识性问题，False表示是闲聊
        """
        # 知识性问题的关键词
        knowledge_keywords = [
            "什么是", "怎么理解", "如何理解", "解释一下", "说明一下",
            "为什么", "原理是什么", "概念", "定义", "区别",
            "怎么用", "如何使用", "如何实现", "怎么写",
            "举例", "示例", "例子", "演示",
            "数据结构", "算法", "链表", "栈", "队列", "树", "图",
            "指针", "数组", "排序", "查找", "递归",
            "类", "对象", "函数", "方法", "变量",
            "python", "java", "c++", "javascript", "html", "css"
        ]
        
        user_input_lower = user_input.lower()
        return any(kw in user_input_lower for kw in knowledge_keywords)
    
    async def _query_knowledge_base(self, question: str, user_id: str) -> Dict[str, Any]:
        """
        查询知识库（RAG）
        
        Args:
            question: 用户问题
            user_id: 用户ID
            
        Returns:
            检索结果，包含context、doc_count和完整的retrieved_docs
        """
        try:
            from .knowledge_base_agent import KnowledgeBaseAgent
            kb_agent = KnowledgeBaseAgent()
            
            result = await kb_agent.query_knowledge(
                question=question,
                user_id=user_id
            )
            
            if result.get("status") == "success":
                retrieved_docs = result.get("retrieved_docs", [])
                context_parts = []
                for i, doc in enumerate(retrieved_docs, 1):
                    context_parts.append(f"[参考资料{i}] {doc['content']}")
                
                context = "\n\n".join(context_parts)
                
                return {
                    "status": "success",
                    "context": context,
                    "doc_count": len(retrieved_docs),
                    "retrieved_docs": retrieved_docs
                }
            else:
                return {
                    "status": "no_result",
                    "context": "",
                    "doc_count": 0,
                    "retrieved_docs": []
                }
                
        except Exception as e:
            print(f"⚠️  知识库查询失败: {e}")
            return {
                "status": "error",
                "context": "",
                "doc_count": 0,
                "retrieved_docs": []
            }

    # ==================== 专家模式：联网搜索 + 证据收集 ====================

    async def _web_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        联网搜索（使用 ddgs 库，支持中文）

        Args:
            query: 搜索关键词
            max_results: 最大返回结果数

        Returns:
            结果列表 [{title, snippet, url, source}]
        """
        results = []
        try:
            print(f"   🌐 联网搜索（ddgs）: {query}")
            from ddgs import DDGS

            def _do_search():
                return DDGS().text(query, max_results=max_results)

            raw_results = await asyncio.to_thread(_do_search)

            for item in raw_results:
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("body", "")[:300],
                    "url": item.get("href", ""),
                    "source": "DuckDuckGo"
                })

            print(f"   ✅ ddgs 返回 {len(results)} 条结果")
        except Exception as e:
            print(f"   ⚠️ 联网搜索失败: {e}")

        return results[:max_results]

    # ★★★ 图片搜索安全拦截词库（含常见违法/违规类别）★★★
    _IMAGE_BLOCK_KEYWORDS = {
        "暴力", "血腥", "恐怖袭击", "爆炸物", "枪支", "毒品", "色情",
        "裸体", "性爱", "成人", "赌博", "诈骗", "赌博", "杀人",
        "自杀", "自残", "虐待", "儿童色情", "反动", "分裂",
        "枪支弹药", "制作炸药", "毒品制作", "暴力血腥",
        "violent", "naked", "porn", "drug", "weapon", "bomb",
    }

    async def _verify_image_safety(self, query: str, results: List[Dict]) -> List[Dict]:
        """
        第三层安全校验：用 LLM 批量验证图片搜索结果的安全性
        
        对通过关键词过滤的结果做语义级别的安全审核，拦截标题含义模糊
        但实际内容不安全的搜索结果。
        """
        if not results:
            return results

        try:
            titles = [r.get("title", "")[:50] for r in results]
            prompt = f"""你是一个严格的内容安全审核员。请判断以下图片搜索结果的标题中是否可能包含违法、暴力、色情、赌博、毒品等违规内容。

搜索关键词：{query}

图片标题列表：
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(titles))}

请逐个判断，只输出安全的图片序号（从1开始），用逗号分隔。
如果全部安全，输出 "all"。
如果全部不安全，输出 "none"。
只输出结果，不要解释。"""
            
            response = await call_llm_with_retry(
                self.llm, prompt, error_msg="图片安全审核LLM调用"
            )
            answer = (response.content if hasattr(response, 'content') else str(response)).strip()
            
            if answer.lower() == "none":
                print(f"   ⛔ LLM安全审核: 全部 {len(results)} 条结果均包含违规内容，已全部拦截")
                return []
            
            if answer.lower() == "all":
                print(f"   ✅ LLM安全审核: 全部 {len(results)} 条结果通过")
                return results
            
            # 解析安全的序号
            safe_indices = set()
            for part in answer.split(","):
                part = part.strip()
                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(results):
                        safe_indices.add(idx)
                except ValueError:
                    continue
            
            if safe_indices:
                filtered = [results[i] for i in safe_indices]
                print(f"   ✅ LLM安全审核: {len(results)} 条中通过 {len(filtered)} 条")
                return filtered
            else:
                print(f"   ⚠️ LLM安全审核结果无法解析，保留全部结果")
                return results
                
        except Exception as e:
            print(f"   ⚠️ LLM安全审核失败（不影响使用）: {e}")
            return results

    async def _verify_image_relevance(self, query: str, results: List[Dict]) -> List[Dict]:
        """
        第四层相关性校验：用 LLM 检查图片是否与搜索关键词相关。
        不相关的图片直接丢弃，不返回给用户。

        如果全部不相关，返回空列表（什么都不展示）。
        """
        if not results:
            return results

        try:
            items_text = []
            for i, r in enumerate(results):
                title = (r.get("title", "") or "")[:60]
                source_url = (r.get("url", "") or "")[:80]
                items_text.append(f'{i+1}. 标题: {title}  来源: {source_url}')

            prompt = f"""你是一个严格的内容相关性审核员。请判断以下图片搜索结果是否与用户的搜索关键词相关。

用户搜索关键词：{query}

图片结果列表：
{chr(10).join(items_text)}

请逐个判断每张图片是否与「{query}」相关（即图片主题内容是否与搜索关键词有关联）。
只输出相关的图片序号（从1开始），用逗号分隔。
如果全部相关，输出 "all"。
如果全部不相关，输出 "none"。
只输出结果，不要解释。"""
            
            response = await call_llm_with_retry(
                self.llm, prompt, error_msg="图片相关性审核LLM调用"
            )
            answer = (response.content if hasattr(response, 'content') else str(response)).strip()
            
            if answer.lower() == "none":
                print(f"   🚫 LLM相关性审核: 全部 {len(results)} 条结果均不相关，已全部丢弃")
                return []
            
            if answer.lower() == "all":
                print(f"   ✅ LLM相关性审核: 全部 {len(results)} 条结果相关")
                return results
            
            # 解析相关的序号
            relevant_indices = set()
            for part in answer.split(","):
                part = part.strip()
                try:
                    idx = int(part) - 1
                    if 0 <= idx < len(results):
                        relevant_indices.add(idx)
                except ValueError:
                    continue
            
            if relevant_indices:
                filtered = [results[i] for i in relevant_indices]
                print(f"   ✅ LLM相关性审核: {len(results)} 条中通过 {len(filtered)} 条（丢弃 {len(results) - len(filtered)} 条不相关）")
                return filtered
            else:
                print(f"   ⚠️ LLM相关性审核结果无法解析，保留全部结果")
                return results
                
        except Exception as e:
            print(f"   ⚠️ LLM相关性审核失败（不影响使用）: {e}")
            return results

    async def _web_image_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        联网图片搜索（多源：DDGS → Bing → og:image 逐级降级）

        Args:
            query: 搜索关键词
            max_results: 最大返回结果数

        Returns:
            结果列表 [{title, image_url, thumbnail_url, url}]
        """
        # ---- 第一层：搜索词安全检测 ----
        query_lower = query.lower()
        for blocked in self._IMAGE_BLOCK_KEYWORDS:
            if blocked in query_lower:
                print(f"   ⛔ 搜索词包含违规内容（命中: {blocked}），已拦截")
                return []

        results = []
        errors = []

        # ========== 方案 1：DDGS 图片搜索（带超时 + 区域轮换）==========
        if not results:
            try:
                print(f"   🖼️ 图片搜索（DDGS）: {query}")
                from ddgs import DDGS
                import random as _random
                import time as _time

                def _search_ddg_images():
                    # 文章建议：轮换 region 提高成功率
                    regions = ['us-en', 'de-de', 'uk-en', 'fr-fr', 'wt-wt', 'cn-zh']
                    for region in regions:
                        try:
                            with DDGS(timeout=20) as ddgs:
                                raw = list(ddgs.images(
                                    query=query, region=region, max_results=max_results
                                ))
                                if raw:
                                    return raw
                        except Exception:
                            _time.sleep(_random.uniform(0.5, 1.5))
                    return []

                raw = await asyncio.wait_for(
                    asyncio.to_thread(_search_ddg_images), timeout=30.0
                )
                for item in raw:
                    # 修复协议相对路径（//xxx → https://xxx）
                    img_url = item.get("image", "") or ""
                    thumb_url = item.get("thumbnail", "") or ""
                    page_url = item.get("url", "") or ""
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    if thumb_url.startswith("//"):
                        thumb_url = "https:" + thumb_url
                    if page_url.startswith("//"):
                        page_url = "https:" + page_url
                    results.append({
                        "title": item.get("title", ""),
                        "image_url": img_url,
                        "thumbnail_url": thumb_url,
                        "url": page_url,
                        "source": "DuckDuckGo"
                    })
                if results:
                    print(f"   ✅ DDGS 图片搜索返回 {len(results)} 条结果")
            except asyncio.TimeoutError:
                errors.append("DDGS 超时")
                print(f"   ⏱️ DDGS 图片搜索超时")
            except Exception as e:
                errors.append(f"DDGS 失败: {e}")
                print(f"   ⚠️ DDGS 图片搜索失败: {e}")

        # ========== 方案 2：Bing 直搜 ==========
        if not results:
            try:
                print(f"   🖼️ 图片搜索（Bing）: {query}")
                import requests as _req
                import re as _re
                import json as _json
                from urllib.parse import quote

                def _search_bing_images():
                    headers = {
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    }
                    url = f"https://www.bing.com/images/search?q={quote(query)}&form=HDRSC2"
                    resp = _req.get(url, headers=headers, timeout=10.0, allow_redirects=True)
                    resp.raise_for_status()
                    html = resp.text
                    items = []
                    # 解析 <a class="iusc" m="{...}">
                    for m in _re.finditer(r'<a\s+class="iusc"[^>]*?m="([^"]+)"', html):
                        try:
                            d = _json.loads(m.group(1).replace("&quot;", '"'))
                            if d.get("murl"):
                                items.append({
                                    "title": d.get("t", ""),
                                    "image_url": d["murl"],
                                    "thumbnail_url": d.get("turl", ""),
                                    "url": d.get("purl", ""),
                                    "source": "Bing"
                                })
                        except _json.JSONDecodeError:
                            continue
                    return items[:max_results]

                bing_results = await asyncio.wait_for(
                    asyncio.to_thread(_search_bing_images), timeout=10.0
                )
                results.extend(bing_results)
                if results:
                    print(f"   ✅ Bing 图片搜索返回 {len(results)} 条结果")
            except asyncio.TimeoutError:
                errors.append("Bing 超时")
                print(f"   ⏱️ Bing 图片搜索超时")
            except Exception as e:
                errors.append(f"Bing 失败: {e}")
                print(f"   ⚠️ Bing 图片搜索失败: {e}")

        # ========== 方案 3：og:image 降级 ==========
        if not results:
            print(f"   🔄 前两方案均失败（{'; '.join(errors)}），尝试 og:image 降级...")
            results = await self._fallback_image_search(query, max_results)

        # ---- 第二层：结果标题安全过滤 ----
        filtered = []
        for item in results:
            title_lower = (item.get("title", "") or "").lower()
            blocked = any(kw in title_lower for kw in self._IMAGE_BLOCK_KEYWORDS)
            if blocked:
                print(f"   ⛔ 过滤违规图片: {item.get('title', '')[:40]}")
                continue
            filtered.append(item)

        # ---- 第三层：LLM 语义安全审核 ----
        filtered = await self._verify_image_safety(query, filtered)

        # ---- 第四层：LLM 相关性审核（不相关即丢弃）----
        filtered = await self._verify_image_relevance(query, filtered)

        return filtered[:max_results]

    async def _fallback_image_search(self, query: str, max_results: int = 4) -> List[Dict[str, Any]]:
        """
        降级图片搜索：从文字搜索结果页中提取 Open Graph 图片
        
        Args:
            query: 搜索关键词
            max_results: 最大返回结果数
            
        Returns:
            结果列表 [{title, image_url, url}]
        """
        results = []
        try:
            print(f"   🔄 降级方案：从文字搜索结果提取图片...")
            # 先用 DDGS 文本搜索获取相关页面
            web_results = await self._web_search(query, max_results=5)
            
            import requests as _req
            
            async def _fetch_page_image(item: dict) -> dict:
                url = item.get("url", "")
                title = item.get("title", "")
                if not url:
                    return None
                try:
                    resp = await asyncio.to_thread(
                        lambda: _req.get(url, timeout=5.0,
                            headers={"User-Agent": "Mozilla/5.0"},
                            allow_redirects=True)
                    )
                    if resp.status_code != 200:
                        return None
                    html = resp.text
                    # 提取 og:image
                    import re
                    og_match = re.search(
                        r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
                        html
                    )
                    if og_match:
                        img_url = og_match.group(1)
                        if img_url.startswith("//"):
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            img_url = f"{parsed.scheme}:{img_url}"
                        elif img_url.startswith("/"):
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
                        return {
                            "title": title,
                            "image_url": img_url,
                            "thumbnail_url": img_url,
                            "url": url,
                            "source": "WebFallback"
                        }
                except Exception:
                    pass
                return None

            # 并发获取所有页面的 og:image
            fetch_tasks = [_fetch_page_image(item) for item in web_results]
            page_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            
            for r in page_results:
                if r and isinstance(r, dict) and r.get("image_url"):
                    results.append(r)
                    
            if results:
                print(f"   ✅ 降级方案获取到 {len(results)} 张图片")
            else:
                print(f"   ℹ️ 降级方案未找到图片")
                
        except Exception as e:
            print(f"   ⚠️ 降级图片搜索失败: {e}")
            
        return results[:max_results]

    async def _gather_evidence(self, question: str, user_id: str) -> Dict[str, Any]:
        """
        证据收集器：先查本地知识库，证据不足时联网搜索兜底

        Args:
            question: 用户问题
            user_id: 用户ID

        Returns:
            {
                "context": str,           # 组装好的上下文文本（注入 prompt）
                "sources": List[Dict],     # 证据来源列表（返回给前端展示）
                "method": str             # "knowledge_base" / "web_search" / "both" / "none"
            }
        """
        sources = []
        context_parts = []
        method = "none"

        # ---- 第一步：查本地知识库 ----
        kb_result = await self._query_knowledge_base(question, user_id)
        if kb_result.get("status") == "success" and kb_result.get("doc_count", 0) > 0:
            method = "knowledge_base"
            context_parts.append(kb_result["context"])
            # 直接从第一次查询结果中提取来源信息（避免重复查询）
            for doc in kb_result.get("retrieved_docs", []):
                sources.append({
                    "title": doc.get("source", "知识库"),
                    "snippet": doc.get("content", "")[:200],
                    "url": "",
                    "source_type": "knowledge_base",
                    "distance": doc.get("distance"),
                    "keyword_score": doc.get("keyword_score", 0)
                })

            # ★★★ 相关性质量检查：用 BM25 得分 + 向量距离判断是否真正相关 ★★★
            # RRF 得分（1/(60+rank)）天然在 0.01~0.02 范围，不能作为相关性指标。
            # 真正有意义的信号是 BM25 keyword_score（越高越相关）和 vector distance（越低越相关）。
            all_keyword_scores = [
                s.get("keyword_score", 0) or 0
                for s in sources if s.get("keyword_score") is not None
            ]
            all_distances = [
                s.get("distance", 2.0) or 2.0
                for s in sources if s.get("distance") is not None
            ]

            max_keyword_score = max(all_keyword_scores) if all_keyword_scores else 0
            best_distance = min(all_distances) if all_distances else 2.0

            # 判断规则：BM25 弱（<5）或 向量检索无结果（距离=2.0 = 完全无匹配）
            # BM25=6.6 但 距离=2.00 说明只是关键词巧合碰到，语义完全不相关
            bm25_weak = (max_keyword_score < 5.0)
            vector_empty = (best_distance > 1.0)  # 超过距离阈值=向量检索认为不相关
            is_weak = bm25_weak or vector_empty    #  测试目前最佳效果

            if is_weak:
                print(f"   ⚠️ 本地知识库结果相关性过低（最高BM25={max_keyword_score:.1f}, "
                      f"最佳距离={best_distance:.2f}），视为无匹配")
                sources.clear()
                context_parts.clear()
                method = "none"
            else:
                print(f"   📚 本地知识库提供 {len(sources)} 条证据 "
                      f"（最高BM25={max_keyword_score:.1f}, 最佳距离={best_distance:.2f}）")

        # ---- 第二步：证据不足（<2条）或相关性过低时联网搜索兜底 ----
        if len(sources) < 3:
            print(f"   🌐 本地证据不足（{len(sources)}条），启动联网搜索兜底...")
            web_results = await self._web_search(question, max_results=5)

            if web_results:
                if method == "knowledge_base":
                    method = "both"
                else:
                    method = "web_search"

                # 构建联网搜索上下文
                web_context_parts = []
                for i, item in enumerate(web_results, 1):
                    web_context_parts.append(
                        f"[网络来源{i} - {item['source']}]\n{item['title']}\n{item['snippet']}"
                    )
                    sources.append({
                        "title": item["title"],
                        "snippet": item["snippet"][:200],
                        "url": item.get("url", ""),
                        "source_type": "web_search"
                    })

                context_parts.append("\n\n".join(web_context_parts))
                print(f"   🌐 联网搜索补充 {len(web_results)} 条证据")

        # ---- 组装最终上下文 ----
        context = "\n\n".join(context_parts) if context_parts else ""

        if not context:
            method = "none"
            print(f"   ⚠️ 未收集到任何证据")

        return {
            "context": context,
            "sources": sources,
            "method": method
        }

    def _format_features_for_chat(self, features: Dict[str, Any]) -> str:
        """格式化用户特征用于对话上下文"""
        if not features:
            return "无可用用户信息"
        
        lines = []
        
        # ★★★ 优先展示 basic_info 中的用户基本信息（DES 注册/修改后持久化） ★★★
        basic = features.get('basic_info', {})
        if basic:
            name = basic.get('name', '')
            if name and name != '未知':
                lines.append(f"- 姓名: {name}")
            major = basic.get('major', '')
            if major and major != '未知':
                lines.append(f"- 专业: {major}")
            grade = basic.get('grade', '')
            if grade and grade != '未知':
                lines.append(f"- 年级: {grade}")
            goal = basic.get('learning_goal', '')
            if goal and goal != '未知':
                lines.append(f"- 学习目标: {goal}")
        
        # 提取关键信息
        academic = features.get('academic_background', {})
        if academic:
            major = academic.get('major_preference', '')
            if major and major != '未知':
                lines.append(f"- 专业背景: {major}")
            
            knowledge = academic.get('knowledge_level', '')
            if knowledge and knowledge != '未知':
                lines.append(f"- 知识水平: {knowledge[:50]}...")
        
        emotional = features.get('emotional_state', {})
        if emotional:
            interest = emotional.get('interest_level', '')
            if interest and interest != '未知':
                lines.append(f"- 当前情绪状态: {interest}")
        
        goal = features.get('goal_motivation', {})
        if goal:
            goals = goal.get('short_term_goals', '')
            if goals and goals != '未知':
                lines.append(f"- 学习目标: {goals[:50]}...")
        
        return "\n".join(lines) if lines else "无详细特征"

    def _format_conversation_history(self, history: List[Dict[str, str]]) -> str:
        """格式化对话历史（智能截断，避免token超限）"""
        if not history:
            return "无历史对话"
        
        lines = []
        total_chars = 0
        max_total_chars = 2500  # ★★★ 限制格式化后的总字符数 ★★★
        
        # 从最近的对话开始（倒序）
        for msg in reversed(history[-10:]):  # 最多取10条消息
            role = "用户" if msg.get('role') == 'user' else "助手"
            content = msg.get('content', '')
            
            # 如果单条消息太长，截断
            if len(content) > 200:
                content = content[:197] + "..."
            
            line = f"{role}: {content}"
            
            # 检查是否会超限
            if total_chars + len(line) > max_total_chars and lines:
                break
            
            lines.append(line)
            total_chars += len(line)
        
        # 反转回正序
        lines.reverse()
        
        return "\n".join(lines) if lines else "无历史对话"

    def _get_conversation_history(self, user_id: str) -> List[Dict[str, str]]:
        """
        从缓存或记忆系统获取对话历史（★★★ 智能摘要版本 ★★★）
        
        策略：
        1. 保留最近3轮完整对话
        2. 更早的对话使用摘要形式
        3. 自动去重和精简
        """
        # 先从缓存获取
        if user_id in self._conversation_cache:
            return self._conversation_cache[user_id]
        
        # 从记忆系统获取智能精简的上下文
        try:
            context = self.memory_manager.get_summarized_context(
                user_id=user_id,
                recent_rounds=3,  # 保留最近3轮完整对话
                max_summary_chars=1500  # 摘要部分最多1500字符
            )
            
            history = []
            
            # 添加摘要部分（作为背景信息）
            for summary_item in context.get('summaries', []):
                summary_text = summary_item['summary']
                original_count = summary_item.get('original_count', 0)
                history.append({
                    'role': 'system',
                    'content': f'[历史对话摘要 - 包含{original_count}轮对话] {summary_text}'
                })
            
            # 添加最近的完整对话
            for interaction in context.get('recent_messages', []):
                messages = interaction.get('messages', [])
                history.extend(messages)
            
            print(f"   📚 加载对话历史: {len(context.get('recent_messages', []))}轮完整 + {len(context.get('summaries', []))}个摘要")
            
            return history
            
        except Exception as e:
            print(f"⚠️ 获取对话历史失败: {e}")
            return []

    async def _save_conversation(self, user_id: str, user_message: str, assistant_message: str):
        """保存对话到记忆系统和缓存（★★★ 支持自动摘要 ★★★）"""
        try:
            # 保存到ChromaDB
            interaction_id = self.memory_manager.add_messages(user_id, [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message}
            ])
            
            # 更新缓存
            if user_id not in self._conversation_cache:
                self._conversation_cache[user_id] = []
            
            self._conversation_cache[user_id].append({"role": "user", "content": user_message})
            self._conversation_cache[user_id].append({"role": "assistant", "content": assistant_message})
            
            # 限制缓存大小（最多保留20条）
            if len(self._conversation_cache[user_id]) > 20:
                self._conversation_cache[user_id] = self._conversation_cache[user_id][-20:]
            
            # ★★★ 检查是否需要生成摘要 ★★★
            await self._check_and_generate_summary(user_id, interaction_id)
                
        except Exception as e:
            print(f"⚠️ 保存对话失败: {e}")
    
    async def _check_and_generate_summary(self, user_id: str, current_interaction_id: str):
        """
        检查是否需要生成对话摘要，并在需要时触发
        
        Args:
            user_id: 用户ID
            current_interaction_id: 当前交互ID（来自ChromaDB，用于确保最新交互被包含）
        """
        try:
            # 获取用户的对话总数
            interactions = self.memory_manager.get_user_interactions(user_id, limit=1000)
            conversation_count = len(interactions)
            
            # 每N轮对话生成一次摘要
            if conversation_count > 0 and conversation_count % self.summary_trigger_threshold == 0:
                print(f"\n📝 检测到已进行{conversation_count}轮对话，触发生成摘要...")
                
                # 获取最近的N轮对话用于生成摘要
                recent_interactions = interactions[:self.summary_trigger_threshold]
                
                # ★★★ 确保当前交互被包含在摘要中 ★★★
                if current_interaction_id:
                    current_found = False
                    for interaction in recent_interactions:
                        if interaction.get('interaction_id') == current_interaction_id:
                            current_found = True
                            break
                    if not current_found:
                        print(f"   ↳ 当前交互 {current_interaction_id} 未在最近N轮中，尝试单独获取...")
                        # 尝试获取当前交互并插入到列表开头
                        all_interactions = self.memory_manager.get_user_interactions(user_id, limit=1000)
                        for interaction in all_interactions:
                            if interaction.get('interaction_id') == current_interaction_id:
                                recent_interactions.insert(0, interaction)
                                recent_interactions = recent_interactions[:self.summary_trigger_threshold]
                                print(f"   ↳ 已补充当前交互到摘要列表")
                                break
                
                # 提取消息和时间信息
                all_messages = []
                interaction_ids = []
                timestamps = []
                for interaction in recent_interactions:
                    messages = interaction.get('messages', [])  
                    all_messages.extend(messages)
                    interaction_ids.append(interaction.get('interaction_id'))
                    timestamps.append(interaction.get('timestamp', ''))
                
                # 确定时间范围
                time_range = ""
                if timestamps:
                    try:
                        times = [datetime.fromisoformat(ts) for ts in timestamps if ts]
                        if times:
                            earliest = min(times)
                            latest = max(times)
                            time_range = f"{earliest.strftime('%Y-%m-%d %H:%M')} ~ {latest.strftime('%Y-%m-%d %H:%M')}"
                    except Exception:
                        pass
                
                # 生成摘要（异步），传递时间范围
                summary = await self.summarizer.summarize_session_async(
                    all_messages,
                    time_range=time_range,
                    knowledge_points=""
                )
                
                # 保存摘要
                self.memory_manager.add_conversation_summary(
                    user_id=user_id,
                    summary=summary,
                    original_interaction_ids=interaction_ids
                )
                print(f"✅ 摘要生成完成，压缩了{len(recent_interactions)}轮对话")

                # ★★★ 后台异步：时间窗口摘要 + 摘要合并 + 事实提取 ★★★
                # 这些操作依赖 LLM（2-5s），放在已有异步路径中执行，不阻塞对话
                try:
                    # ① summarize_by_time_window_async → 按24h窗口切分摘要
                    msgs_with_ts = []
                    for interaction in recent_interactions:
                        for msg in interaction.get('messages', []):
                            msgs_with_ts.append({
                                "role": msg.get("role", "user"),
                                "content": msg.get("content", ""),
                                "timestamp": interaction.get("timestamp", datetime.now().isoformat()),
                            })

                    window_results = await self.summarizer.summarize_by_time_window_async(
                        msgs_with_ts, window_hours=24
                    )
                    window_count = len(window_results)
                    print(f"   ↳ 时间窗口摘要完成: {window_count} 个窗口")

                    # ② merge_summaries_async → 合并摘要
                    summaries_text = [w["summary"] for w in window_results if w.get("summary")]
                    if len(summaries_text) > 1:
                        merged = await self.summarizer.merge_summaries_async(summaries_text)
                        if merged:
                            # 合并后的概要也保存为摘要
                            self.memory_manager.add_conversation_summary(
                                user_id=user_id,
                                summary=merged,
                                original_interaction_ids=interaction_ids
                            )
                            print(f"   ↳ 多窗口摘要合并完成")

                    # ③ extract_key_facts_async → 提取结构化事实
                    facts = await self.summarizer.extract_key_facts_async(all_messages)
                    if facts:
                        # 结构化事实存入长期记忆（用户画像）
                        await self._update_features_from_chat(
                            user_id=user_id,
                            user_input=str(facts),
                            reply="",
                            intent_result={}
                        )
                        print(f"   ↳ 提取结构化事实: {len(facts)} 项")

                except Exception as e2:
                    print(f"   ⚠️ 后台摘要增强失败（不影响对话）: {e2}")
            
        except Exception as e:
            print(f"⚠️ 生成摘要失败: {e}")

    async def _check_hallucination(self, reply_content: str, context: str = "") -> str:
        """
        防幻觉检查 - 验证回复内容的安全性和事实一致性
        
        Args:
            reply_content: LLM生成的回复内容
            context: 参考文档上下文（RAG检索结果）
            
        Returns:
            校验后的回复内容（可能被修正）
        """
        try:
            from utils.hallucination_guard import get_hallucination_guard
            
            guard = get_hallucination_guard(strict_mode=False, llm_client=self.llm)
            result, check_result = await guard.validate_and_correct(reply_content, context)
            
            if check_result.warnings:
                print(f"⚠️ [防幻觉] 检测到警告: {check_result.warnings}")
                
            if check_result.confidence.value == "low" and context:
                print(f"⚠️ [防幻觉] 置信度低，建议重新生成")
                
            if check_result.safety.value != "safe":
                print(f"⚠️ [防幻觉] 安全等级: {check_result.safety.value}")
                
            return result
            
        except ImportError:
            print("⚠️ 防幻觉模块未安装，跳过校验")
            return reply_content
        except Exception as e:
            print(f"⚠️ 防幻觉校验失败: {e}")
            return reply_content
    
    async def _update_features_from_chat(self, user_id: str, user_input: str, reply: str, intent_result: Dict[str, Any]):
        """基于对话内容使用 LLM 分析并更新特征（与其他 Agent 一致的异步方式）"""
        try:
            current_features = await self.feature_updater.get_latest_features_async(user_id)
            if not current_features:
                print(f"   ⚠️ [Chat→特征] 用户 {user_id} 无特征记录，跳过")
                return

            performance_data = {
                "emotion": intent_result.get('emotion', 'neutral'),
                "intent_type": intent_result.get('intent_type', 'casual_chat'),
                "user_input": user_input[:200],
                "assistant_reply": reply[:200],
            }

            updated_result = await self.feature_updater.update_features_async(
                current_features=current_features,
                task_type="chat_conversation",
                task_content=f"日常对话：用户说'{user_input[:50]}'",
                performance_data=performance_data,
                completion_quality="medium",
                user_id=user_id
            )

            changes = updated_result.get('changes', [])
            if changes:
                print(f"   📊 [Chat→特征] 已更新特征: {', '.join(changes)}")
            else:
                print(f"   📊 [Chat→特征] 本次对话未触发特征变化")

        except Exception as e:
            print(f"⚠️ [Chat→特征] 更新失败: {e}")

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析LLM返回的JSON响应"""
        import json
        import re
        
        try:
            # 尝试提取JSON块
            json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
            json_match = json_pattern.search(response)
            
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接匹配JSON对象
                json_only_pattern = re.compile(r'\{.*\}', re.DOTALL)
                json_match = json_only_pattern.search(response)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    cleaned_response = response.strip()
                    if cleaned_response.startswith('{') and cleaned_response.endswith('}'):
                        json_str = cleaned_response
                    else:
                        return None

            json_str = json_str.strip()
            data = json.loads(json_str)
            return data

        except Exception as e:
            print(f"❌ JSON解析失败: {e}")
            return None


    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数量（粗略估算）
        
        Args:
            text: 输入文本
            
        Returns:
            int: 估算的token数
        """
        # 中文：约1.5-2个字符 = 1 token
        # 英文：约4个字符 = 1 token
        # 这里使用保守估算：3个字符 = 1 token
        return len(text) // 3

    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent的基本信息"""
        return {
            "name": "日常对话Agent",
            "role": "AI聊天伙伴",
            "description": "提供自然流畅的日常交流、情感支持和轻度生活咨询",
            "capabilities": [
                "日常闲聊和问候",
                "情感支持和疏导",
                "生活建议和娱乐咨询",
                "上下文记忆和个性化回应",
                "智能意图识别和路由",
                "情绪状态追踪"
            ],
            "personality": {
                "tone": "温暖友好",
                "style": "自然口语化",
                "humor_level": "适中",
                "empathy_level": "高"
            }
        }
