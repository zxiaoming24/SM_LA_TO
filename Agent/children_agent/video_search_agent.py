"""
视频搜索Agent
负责解析用户需求并调用B站API搜索教学视频
可以复用项目中的 question_refiner 来优化搜索关键词
支持动态特征更新 - 根据观看行为实时更新学生画像
"""

import os
import asyncio
from typing import Dict, Any, List, Optional
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai

# TTS辅助函数
try:
    from utils.tts_helper import generate_tts_audio
except ImportError:
    from utils.tts_helper import generate_tts_audio

# 导入项目现有的子agent
from Agent.children_agent.question_refiner import QuestionRefinerAgent
from services.video_search_service import BilibiliSearchService
from utils.video_ranker import VideoRanker
from utils.multimodal_assembler import MultimodalAssembler

# 推荐系统资源入库
try:
    from Agent.children_agent.recommendation.resource_db import ResourceDB
    from Agent.children_agent.recommendation.semantic_store import SemanticStore
except ImportError:
    try:
        from recommendation.resource_db import ResourceDB
        from recommendation.semantic_store import SemanticStore
    except ImportError:
        ResourceDB = None
        SemanticStore = None

# 支持直接运行和包导入两种方式
try:
    from .dynamic_feature_updater import DynamicFeatureUpdater
    from memory.memory_hub import MemoryHub
except ImportError:
    from dynamic_feature_updater import DynamicFeatureUpdater
    from memory.memory_hub import MemoryHub


class VideoSearchAgent:
    """
    视频搜索Agent - 基于用户需求搜索B站教学视频
    """

    def __init__(self):
        """初始化视频搜索Agent"""
        self.llm = self._initialize_llm()
        self.keyword_prompt = self._create_keyword_prompt()   #  创建prompt提示词

        # 组合其他组件
        self.question_refiner = QuestionRefinerAgent()  # 复用问题提炼agent
        self.search_service = BilibiliSearchService()   # B站搜索服务
        self.ranker = VideoRanker()                     # 视频排序器
        self.assembler = MultimodalAssembler()          # 多模态组装器

        # 初始化动态特征更新器（用于个性化视频推荐）
        try:
            from .dynamic_feature_updater import DynamicFeatureUpdater
        except ImportError:
            from dynamic_feature_updater import DynamicFeatureUpdater
        self.feature_updater = DynamicFeatureUpdater()

        # ★★★ MemoryHub 统一记忆中心 ★★★
        try:
            self.memory_hub = MemoryHub()
        except Exception:
            self.memory_hub = None

    def _build_student_profile_section(self, features: Dict[str, Any]) -> str:
        """将8维度特征压缩为可读段落用于Prompt"""
        return self.feature_updater.build_student_profile_for_prompt(features)

    def _initialize_llm(self):
        """初始化LLM模型（使用统一配置）"""
        try:
            return get_chat_openai(temperature=0.3, max_tokens=200, streaming=True)
        except Exception as e:
            raise Exception(f"初始化视频搜索Agent LLM失败: {e}")

    def _create_keyword_prompt(self) -> PromptTemplate:
        """创建关键词提取提示词模板"""
        template = """
你是一位专业的教育内容分析师，擅长从学生的学习问题中提取精准的搜索关键词。

**任务：**
将用户的学习问题转换为适合在B站搜索教学视频的关键词。

**要求：**
1. 提取核心知识点作为关键词
2. 可以添加"教程"、"讲解"、"入门"等后缀提高搜索质量
3. 保持简洁，最多2个关键词组合
4. 只输出关键词，不要解释

**示例：**
- 输入："指针这里不会，搞不懂怎么用"
  输出："C语言指针教程"

- 输入："我不太理解递归是怎么工作的"
  输出："递归算法讲解"

- 输入："PyTorch自动求导原理"
  输出："PyTorch自动求导教程"

- 输入："Transformer模型怎么实现"
  输出："Transformer模型讲解"

**用户问题：**
{user_question}

**请输出搜索关键词：**
""".strip()

        return PromptTemplate.from_template(template)

    async def search_videos_for_question_async(
        self, 
        user_question: str, 
        top_k: int = 3,
        student_features: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        enable_tts: bool = False,
        raw_query: bool = False
    ) -> Dict[str, Any]:
        """
        异步根据用户问题搜索相关教学视频
        
        Args:
            user_question: 用户的学习问题
            top_k: 返回的视频数量
            student_features: 学生特征数据（可选，如果不提供则从中央管理器获取）
            user_id: 用户ID（如果提供，会自动从中央管理器获取最新特征）
            enable_tts: 是否启用TTS语音合成
            raw_query: 是否跳过提炼步骤，直接用 user_question 作为搜索关键词
                       （从学习计划触发的搜索应设为 True，因为知识点已经精确）
            
        Returns:
            多模态响应结果
        """
        print("\n" + "="*70)
        print("🎬 视频搜索Agent 开始工作")
        print("="*70)
        
        try:
            # ★★★ 获取学生画像（用于个性化视频推荐）★★★
            if student_features is None and user_id:
                student_features = await self.feature_updater.get_latest_features_async(user_id)
            if student_features:
                print(f"📖 [视频搜索Agent] 获取学生画像进行个性化视频推荐")
                student_profile = self._build_student_profile_section(student_features)
            else:
                student_profile = ""

            # ★★★ 从学习计划触发的搜索，跳过LLM提炼和关键词生成，直接用原始知识点 ★★★
            if raw_query:
                refined_title = user_question[:30]
                search_keywords = user_question[:50]
                print(f"\n⚡ [视频搜索Agent] raw_query模式，跳过提炼步骤")
                print(f"   ✅ 搜索关键词 = '{search_keywords}'")
            else:
                # 步骤1: 使用 question_refiner 提炼问题标题(异步)
                print("\n📝 步骤1: 提炼问题标题...")
                refined_title = await self.question_refiner.refine_question_async(user_question)
                print(f"✅ 提炼结果: {refined_title}")
                
                # 步骤2: 使用LLM生成搜索关键词(异步)
                print("\n🔑 步骤2: 生成搜索关键词...")
                search_keywords = await self._generate_search_keywords_async(user_question)
                print(f"✅ 搜索关键词: {search_keywords}")
            
            # 步骤3: 调用B站API搜索视频
            print(f"\n🔍 步骤3: 搜索B站视频 (关键词: {search_keywords})...")
            raw_videos = self.search_service.search_videos(
                keyword=search_keywords,
                page=1,
                page_size=top_k * 2  # 搜索更多以便筛选
            )
            print(f"✅ 找到 {len(raw_videos)} 个原始结果")
            
            if not raw_videos:
                print(f"   ❌ B站服务暂时不可用，无法获取搜索结果")
                return self._get_empty_result(user_question, refined_title)
            
            # 步骤4: 对视频进行排序和评分
            print("\n📊 步骤4: 视频排序和评分...")
            print(f"   原始视频数量: {len(raw_videos)}")
            ranked_videos = self.ranker.rank_videos(raw_videos, search_keywords)
            print(f"   排序后视频数量: {len(ranked_videos)}")
            print(f"✅ 已完成排序，取前 {top_k} 个")
            
            # 步骤5: 组装多模态响应
            print("\n📦 步骤5: 组装多模态响应...")
            videos_to_assemble = ranked_videos[:top_k]
            print(f"   准备组装的视频数量: {len(videos_to_assemble)}")
            result = self.assembler.assemble_response(
                videos=videos_to_assemble,
                query=user_question,
                refined_title=refined_title
            )
            
            print("\n✅ 视频搜索完成！")
            print("="*70)
            
            # TTS语音合成（可选）- 将搜索摘要转为语音
            if enable_tts:
                summary_text = result.get('summary', '')
                if summary_text:
                    tts_path = await generate_tts_audio(
                        text=summary_text,
                        agent_name="video_search",
                        user_id=user_id
                    )
                    if tts_path:
                        result["tts_audio_path"] = tts_path

            # ★★★ 记录学生画像用于后续特征更新 ★★★
            if student_features:
                result["_student_features"] = student_features
                result["_student_profile"] = student_profile

            # ★★★ 将搜索到的视频自动入库（供推荐系统使用）★★★
            try:
                if ResourceDB and SemanticStore and videos_to_assemble:
                    _rdb = ResourceDB()
                    _sem = SemanticStore()
                    import hashlib
                    for v in videos_to_assemble:
                        vid = v.get("bvid") or f"v_{hashlib.md5(v.get('url', '').encode()).hexdigest()[:12]}"
                        dur_str = v.get("duration", "0:0")
                        parts = str(dur_str).split(":")
                        dur_sec = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
                        topic = refined_title or user_question
                        vid = _rdb.upsert_video(
                            vid=vid, platform="bilibili",
                            title=v.get("title", ""), topic=topic,
                            difficulty=3, duration_sec=dur_sec,
                            url=v.get("url", ""),
                            knowledge_points=[topic],
                            metadata={
                                "author": v.get("author", ""),
                                "play_count": v.get("play_count", 0),
                                "quality_score": v.get("quality_score", 0),
                                "description": v.get("description", "")
                            }
                        )
                        _sem.store_video(
                            vid=vid, topic=topic,
                            title=v.get("title", ""),
                            difficulty=3,
                            knowledge_points=[topic],
                            description=v.get("description", "")
                        )
                    print(f"   ✅ {len(videos_to_assemble)} 个视频已入库")
            except Exception as e:
                print(f"   ⚠️ 视频入库失败（不影响使用）: {e}")

            # ★★★ MemoryHub：记录工作记忆 ★★★
            try:
                if self.memory_hub and user_id and videos_to_assemble:
                    query_for_kp = refined_title or user_question
                    learning_kws = ["循环", "递归", "函数", "数组", "指针", "链表",
                                    "排序", "搜索", "类", "对象", "继承", "多态",
                                    "文件", "异常", "正则", "线程", "协程", "数据库",
                                    "网络", "算法", "数据结构", "编程", "代码",
                                    "Python", "Java", "C++", "JavaScript"]
                    found_kps = [kw for kw in learning_kws if kw in query_for_kp]
                    if found_kps:
                        topic = found_kps[0]
                    else:
                        topic = query_for_kp[:20]
                    self.memory_hub.working.set_current_topic(user_id, topic)
                    self.memory_hub.working.add_focus_knowledge(user_id, topic)
                    self.memory_hub.working.set_current_task(user_id, "video", f"搜索视频: {topic}")
                    self.memory_hub.knowledge.record_activity(
                        user_id, topic, correct=None, activity_type="video"
                    )
            except Exception:
                pass

            return result
            
        except Exception as e:
            print(f"\n❌ 视频搜索失败: {e}")
            import traceback
            traceback.print_exc()
            return self._get_error_result(user_question, str(e))

    async def _generate_search_keywords_async(self, user_question: str) -> str:
        """异步使用LLM生成搜索关键词"""
        try:
            prompt = self.keyword_prompt.format(user_question=user_question)
            response = await self.llm.ainvoke(prompt)
            keywords = response.content if hasattr(response, 'content') else str(response)
            return keywords.strip().replace('"', '').replace('\n', '')
        except Exception as e:
            print(f"⚠️ 关键词生成失败，使用原始问题: {e}")
            return user_question[:30]

    def _get_empty_result(self, query: str, refined_title: str) -> Dict[str, Any]:
        """返回空结果"""
        return {
            'query': query,
            'refined_title': refined_title,
            'total_results': 0,
            'videos': [],
            'summary': f'抱歉，B站搜索服务暂时不可用，无法获取「{query}」的相关视频。请稍后重试。',
            'metadata': {
                'search_keywords': [],
                'ranking_criteria': [],
                'timestamp': self.assembler._get_timestamp(),
                'error': 'no_results'
            }
        }

    def _get_error_result(self, query: str, error_msg: str) -> Dict[str, Any]:
        """返回错误结果"""
        return {
            'query': query,
            'refined_title': '',
            'total_results': 0,
            'videos': [],
            'summary': f"搜索过程中出现错误：{error_msg}",
            'metadata': {
                'search_keywords': [],
                'ranking_criteria': [],
                'timestamp': self.assembler._get_timestamp(),
                'error': error_msg
            }
        }

    def display_result(self, result: Dict[str, Any]):
        """美观地展示搜索结果"""
        print("\n" + "🎯"*35)
        print(f"  查询: {result.get('query', '')}")
        print(f"  提炼标题: {result.get('refined_title', '')}")
        print("🎯"*35)
        
        videos = result.get('videos', [])
        if not videos:
            print("\n😕 未找到相关视频")
            return
        
        print(f"\n📺 找到 {len(videos)} 个相关视频:\n")
        
        for i, video in enumerate(videos, 1):
            print(f"{'─'*60}")
            print(f"📌 排名 #{video.get('rank', i)}")
            print(f"📝 标题: {video.get('title', '')}")
            print(f"👤 UP主: {video.get('author', '')}")
            print(f"⏱️  时长: {video.get('duration', '')}")
            print(f"▶️  播放: {video.get('play_count', '')}")
            print(f"⭐ 质量分: {video.get('quality_score', 0)}")
            print(f"🔗 链接: {video.get('url', '')}")
            if video.get('description'):
                print(f"📄 简介: {video.get('description', '')[:80]}...")
            print()
        
        print(f"\n💡 总结: {result.get('summary', '')}")
        print("🎯"*35)

    def get_agent_info(self) -> Dict[str, str]:
        """获取Agent信息"""
        return {
            "name": "视频搜索Agent",
            "role": "B站教学视频搜索引擎",
            "description": "基于用户学习问题搜索B站优质教学视频",
            "capabilities": [
                "问题提炼与关键词生成",
                "B站视频搜索",
                "视频质量评分与排序",
                "多模态结果组装",
                "动态更新学生特征画像"
            ],
            "components": [
                "QuestionRefinerAgent (复用)",
                "BilibiliSearchService",
                "VideoRanker",
                "MultimodalAssembler",
                "DynamicFeatureUpdater"
            ]
        }
    
    async def update_features_after_watch(
        self,
        student_features: Dict[str, Any],
        watch_data: Dict[str, Any],
        video_info: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None  # 新增：用户ID
    ) -> Dict[str, Any]:
        """
        根据视频观看行为动态更新学生特征（异步版本）
        
        Args:
            student_features: 当前学生特征（如果不提供且有user_id，会从中央管理器获取）
            watch_data: 观看行为数据
                - watch_duration: 观看时长
                - total_duration: 视频总时长
                - completion_rate: 完成率
                - pause_count: 暂停次数
                - rewind_count: 回看次数
                - note-taking: 是否记笔记
                - quiz_score: 课后测验分数（如果有）
            video_info: 视频信息（可选）
            user_id: 用户ID（如果提供，会自动保存更新后的特征到中央管理器）
            
        Returns:
            Dict: 更新后的特征数据
        """
        try:
            # ★★★ 关键：如果没有提供student_features但有user_id，从中央管理器获取 ★★★
            if student_features is None and user_id:
                student_features = await self.feature_updater.get_latest_features_async(user_id)
                if student_features:
                    print(f"📖 [视频搜索Agent] 从中央管理器获取了用户 {user_id} 的最新特征")
            
            if not student_features:
                print("⚠️ [视频搜索Agent] 没有学生特征数据，跳过更新")
                return {
                    "status": "skipped",
                    "message": "没有学生特征数据"
                }
            
            # 构建性能数据
            performance_data = {
                "watch_duration": watch_data.get('watch_duration', ''),
                "total_duration": watch_data.get('total_duration', ''),
                "completion_rate": watch_data.get('completion_rate', ''),
                "pause_count": watch_data.get('pause_count', 0),
                "rewind_count": watch_data.get('rewind_count', 0),
                "note_taking": watch_data.get('note-taking', False),
                "quiz_score": watch_data.get('quiz_score', None),
                "engagement_signals": watch_data.get('engagement_signals', [])
            }
            
            if video_info:
                performance_data['video_title'] = video_info.get('title', '')
                performance_data['topic'] = video_info.get('topic', '')
            
            # 评估完成质量
            completion_rate_str = watch_data.get('completion_rate', '0%')
            if isinstance(completion_rate_str, str):
                completion_rate = float(completion_rate_str.replace('%', '')) / 100
            else:
                completion_rate = completion_rate_str
            
            if completion_rate >= 0.9:
                completion_quality = "high"
            elif completion_rate >= 0.6:
                completion_quality = "medium"
            else:
                completion_quality = "low"
            
            # ★★★ 后台异步更新特征，不阻塞资源返回 ★★★
            asyncio.create_task(
                self.feature_updater.update_features_async(
                    current_features=student_features,
                    task_type="video_learning",
                    task_content=f"视频学习：{video_info.get('title', '') if video_info else '未知'}",
                    performance_data=performance_data,
                    completion_quality=completion_quality,
                    time_spent=watch_data.get('watch_duration', ''),
                    user_id=user_id
                )
            )
            
            print(f"🔄 [视频搜索Agent] 特征更新已触发（后台）")
            return {
                "status": "success",
                "updated_features": student_features,
                "message": "特征更新已后台执行"
            }
            
        except Exception as e:
            print(f"⚠️ 特征更新失败: {e}")
            return {
                "status": "error",
                "updated_features": student_features,
                "message": str(e)
            }
