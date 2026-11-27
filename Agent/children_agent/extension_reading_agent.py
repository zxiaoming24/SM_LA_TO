from utils.llm_config import MODEL
import os
import asyncio
from typing import Dict, Any, Optional

# TTS辅助函数
try:
    from utils.tts_helper import generate_tts_audio
except ImportError:
    from utils.tts_helper import generate_tts_audio

# 支持直接运行和包导入两种方式
try:
    from .dynamic_feature_updater import DynamicFeatureUpdater
    from memory.memory_hub import MemoryHub
except ImportError:
    from dynamic_feature_updater import DynamicFeatureUpdater
    from memory.memory_hub import MemoryHub


class ExtensionReadingAgent:
    """
    拓展阅读材料生成智能体
    结合学生特征画像 + 课程知识点 生成个性化拓展阅读材料
    """

    def __init__(self):
        self.model = MODEL
        # ★★★ LangChain LLM 实例（用于SSE逐词推送）★★★
        self.llm = self._initialize_llm()

        # 初始化动态特征更新器
        self.feature_updater = DynamicFeatureUpdater()

        # ★★★ MemoryHub 统一记忆中心 ★★★
        try:
            self.memory_hub = MemoryHub()
        except Exception:
            self.memory_hub = None

    def _initialize_llm(self):
        """初始化LangChain LLM（用于SSE逐词推送）"""
        from utils.llm_config import get_chat_openai
        return get_chat_openai(temperature=0.3, max_tokens=4000, streaming=True)

    def _build_student_profile_section(self, features: Dict[str, Any]) -> str:
        """将8维度特征压缩为可读段落用于Prompt"""
        return self.feature_updater.build_student_profile_for_prompt(features)

    async def generate_reading_material_async(self, info: Dict[str, Any], enable_tts: bool = False) -> Dict[str, Any]:
        """
        异步版本的拓展阅读材料生成（支持TTS）
        
        Args:
            info: 包含major/course_name/weak_points/learn_level/user_input/student_feature/user_id
            enable_tts: 是否启用TTS语音合成
            
        Returns:
            Dict: 拓展阅读数据 + 可选的tts_audio_path
        """
        user_id = info.get("user_id", "unknown")
        major = info.get("major", "")
        course_name = info.get("course_name", "")
        weak_points = info.get("weak_points", "")
        learn_level = info.get("learn_level", "")
        user_input = info.get("user_input", "")
        student_feature = self._build_student_profile_section(info.get("student_feature", {}))
        loop = asyncio.get_running_loop()

        prompt = f"""
你是专业教育拓展阅读生成智能体，需结合【课程信息】+【学生个人特征画像】，
为学生生成**个性化、适配其基础水平与学习风格**的拓展阅读材料，只输出标准JSON，无多余解释、无```包裹。

==== 基础课程信息 ====
所属专业：{major}
课程名称：{course_name}
知识薄弱点：{weak_points}
预设学习层次：{learn_level}
指定知识点：{user_input}

==== 学生个性化特征画像 ====
{student_feature}

==== 生成要求 ====
1. 严格围绕指定知识点和薄弱点做课外延伸，不重复课内基础讲义内容；
2. 【必须】根据学生特征自动适配（对照以下规则选择适用项）：
   - foundation_level=薄弱 → 语言极通俗、类比生活场景、多用图解、不用专业术语
   - knowledge_level=薄弱 → 重点讲"是什么"和"怎么用"，不讲"为什么"的深层原理
   - problem_solving/logical_thinking=弱 → 增加思维步骤拆解、多流程图、减少复杂推理
   - learning_style=动手型 → 侧重实际应用、行业场景、个人项目案例
   - learning_style=视觉型 → 增加配图描述、图形化解释、对比表格
   - learning_pace=快速学习者 → 内容紧凑，适当增加挑战性拓展和延伸阅读
   - learning_pace=深度思考者 → 内容展开更充分，提供多种理解角度和思考题
   - frustration_tolerance=低 → 误区部分要先说"这很正常"再给建议，语气温和
   - confidence_level=低 → 先肯定读者能力，语言更有鼓励感，降低压迫感
   - motivation_strength=内在动机 → 可以讲热爱和兴趣，适当引入学科之美
3. 拓展阅读必须包含板块：
   ①知识点背景溯源
   ②易混淆知识点深度辨析
   ③底层原理通俗拓展
   ④新手学习误区与避坑建议
   ⑤行业实际应用场景拓展
   ⑥专属个性化学习建议
4. 语言适合大一学生阅读，段落清晰、条理分明；
5. 严格按下面固定JSON结构输出，字段不能删减改名。

==== 输出固定格式 ====
{{
  "title": "拓展阅读材料标题",
  "background": "知识点背景溯源内容",
  "knowledge_distinguish": "易混淆知识点深度辨析内容",
  "principle_extend": "底层原理通俗拓展内容",
  "mistake_avoid": "新手学习误区与避坑建议",
  "application_scene": "行业实际应用场景拓展",
  "personal_suggest": "结合学生特征的专属个性化学习建议"
}}
"""

        response = await self.llm.ainvoke(prompt)
        import json
        content = response.content.strip()
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # 尝试从 markdown 代码块中提取 JSON
            import re
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group(1).strip())
                except json.JSONDecodeError:
                    print(f"  ⚠️ [拓展阅读] LLM 输出不是合法 JSON，使用空结果")
                    result = {}
            else:
                print(f"  ⚠️ [拓展阅读] LLM 输出不是合法 JSON，使用空结果")
                result = {}
        
        # TTS语音合成（可选）
        if enable_tts and result:
            title = result.get('title', '拓展阅读')
            background = result.get('background', '')[:300]
            tts_text = f"{title}。{background}" if background else title
            
            tts_path = await generate_tts_audio(
                text=tts_text,
                agent_name="extension_reading",
                user_id=user_id
            )
            if tts_path:
                result["tts_audio_path"] = tts_path

        # ★★★ 将生成的拓展阅读自动入库（供推荐系统使用）★★★
        try:
            from Agent.children_agent.recommendation.resource_db import ResourceDB
            from Agent.children_agent.recommendation.semantic_store import SemanticStore
            import hashlib
            topic = info.get("user_input", info.get("course_name", "拓展阅读"))
            ext_title = result.get("title", "拓展阅读材料")
            doc_id = f"ext_{hashlib.md5(f'{user_id}_{topic}'.encode()).hexdigest()[:12]}"
            content = "\n\n".join([
                f"背景溯源：{result.get('background', '')}",
                f"易混淆辨析：{result.get('knowledge_distinguish', '')}",
                f"底层原理：{result.get('principle_extend', '')}",
                f"避坑建议：{result.get('mistake_avoid', '')}",
                f"应用场景：{result.get('application_scene', '')}",
                f"个性化建议：{result.get('personal_suggest', '')}",
            ])
            summary = result.get("background", "")[:300]
            def _do_extension_import():
                _rdb = ResourceDB()
                _sem = SemanticStore()
                _did = _rdb.upsert_document(
                    did=doc_id, category="extension",
                    title=ext_title, topic=topic,
                    difficulty=3, knowledge_points=[topic],
                    content=content, summary=summary,
                    metadata={"user_id": user_id}
                )
                _sem.store_document(
                    did=_did or doc_id, category="extension",
                    topic=topic, difficulty=3,
                    title=ext_title, content=content,
                    summary=summary
                )
            await loop.run_in_executor(None, _do_extension_import)
            print(f"   ✅ 拓展阅读已入库")
        except Exception as e:
            print(f"   ⚠️ 拓展阅读入库失败（不影响使用）: {e}")

        # ★★★ MemoryHub：记录工作记忆 ★★★
        try:
            if self.memory_hub and user_id:
                topic = info.get("user_input", info.get("course_name", ""))
                if topic:
                    await loop.run_in_executor(None, lambda: self.memory_hub.working.set_current_topic(user_id, topic))
                    await loop.run_in_executor(None, lambda: self.memory_hub.working.add_focus_knowledge(user_id, topic))
                    await loop.run_in_executor(None, lambda: self.memory_hub.working.set_current_task(user_id, "extension", f"拓展阅读: {topic}"))
                    await loop.run_in_executor(
                        None, lambda: self.memory_hub.knowledge.record_activity(
                            user_id, topic, correct=None, activity_type="document"
                        )
                    )
        except Exception:
            pass

        return result
    
    async def update_features_after_reading(
        self,
        student_features: Dict[str, Any],
        reading_data: Dict[str, Any],
        doc_info: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        根据扩展阅读行为动态更新学生特征（异步版本）
        
        Args:
            student_features: 当前学生特征（如果不提供且有user_id，会从中央管理器获取）
            reading_data: 阅读行为数据
                - reading_time: 阅读时长
                - completion_rate: 完成率
                - highlight_count: 高亮次数
                - note_count: 笔记数量
                - engagement_level: 参与度 (high/medium/low)
                - topics_explored: 探索的主题列表
            doc_info: 文档信息（可选）
            user_id: 用户ID（如果提供，会自动保存更新后的特征到中央管理器）
            
        Returns:
            Dict: 更新后的特征数据
        """
        try:
            # ★★★ 关键：如果没有提供student_features但有user_id，从中央管理器获取 ★★★
            if student_features is None and user_id:
                student_features = await self.feature_updater.get_latest_features_async(user_id)
                if student_features:
                    print(f"📖 [扩展阅读Agent] 从中央管理器获取了用户 {user_id} 的最新特征")
            
            if not student_features:
                print("⚠️ [扩展阅读Agent] 没有学生特征数据，跳过更新")
                return {
                    "status": "skipped",
                    "message": "没有学生特征数据"
                }
            
            # 构建性能数据
            performance_data = {
                "reading_time": reading_data.get('reading_time', ''),
                "completion_rate": reading_data.get('completion_rate', 0),
                "highlight_count": reading_data.get('highlight_count', 0),
                "note_count": reading_data.get('note_count', 0),
                "engagement_level": reading_data.get('engagement_level', 'medium'),
                "topics_explored": reading_data.get('topics_explored', [])
            }
            
            if doc_info:
                performance_data['document_title'] = doc_info.get('doc_title', '')
                performance_data['course_name'] = doc_info.get('course_name', '')
            
            # 评估完成质量
            completion_rate = reading_data.get('completion_rate', 0)
            engagement = reading_data.get('engagement_level', 'medium')
            
            if completion_rate >= 0.9 and engagement == 'high':
                completion_quality = "high"
            elif completion_rate >= 0.6:
                completion_quality = "medium"
            else:
                completion_quality = "low"
            
            # ★★★ 后台异步更新特征，不阻塞资源返回 ★★★
            asyncio.create_task(
                self.feature_updater.update_features_async(
                    current_features=student_features,
                    task_type="extension_reading",
                    task_content=f"扩展阅读：{doc_info.get('doc_title', '') if doc_info else '未知'}",
                    performance_data=performance_data,
                    completion_quality=completion_quality,
                    time_spent=reading_data.get('reading_time', ''),
                    user_id=user_id
                )
            )
            
            print(f"🔄 [扩展阅读Agent] 特征更新已触发（后台）")
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