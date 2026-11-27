from typing import Dict, Any, Optional, List
from utils.llm_config import MODEL
import os
import asyncio

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

class MindMapAgent:
    def __init__(self):
        self.model_name = MODEL
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
        return get_chat_openai(temperature=0.2, max_tokens=4000, streaming=True)

    def _build_student_profile_section(self, features: Dict[str, Any]) -> str:
        """将8维度特征压缩为可读段落用于Prompt"""
        if not features:
            return "【学生画像】未获取到（将使用通用导图风格）"
        jzon = self.feature_updater._compact_features_for_prompt(features, compression_level="balanced")
        lines = ["【学生画像 - 请据此调整导图的详细程度与结构复杂度】"]
        schema_map = jzon.get("z.f", {})
        values_map = jzon.get("z.c", {})
        for dim, fields in schema_map.items():
            values = values_map.get(dim, [])
            for field_name, val in zip(fields, values):
                if val is not None:
                    lines.append(f"  - {field_name}: {val}")
        return "\n".join(lines) if len(lines) > 1 else "【学生画像】信息不足（将使用通用导图风格）"

    async def generate_mindmap_json_async(self, info: Dict[str, Any], enable_tts: bool = False) -> Dict[str, Any]:
        """
        异步版本的思维导图JSON生成（支持TTS）
        
        Args:
            info: 包含major/course_name/weak_points/learn_level/student_feature
            enable_tts: 是否启用TTS语音合成
            
        Returns:
            Dict: 思维导图JSON数据 + 可选的tts_audio_path
        """
        major = info.get("major", "")
        course_name = info.get("course_name", "")
        weak_points = info.get("weak_points", "")
        level = info.get("learn_level", "")
        student_feature = self._build_student_profile_section(info.get("student_feature", {}))
        loop = asyncio.get_running_loop()

        prompt = f"""你是一个严格的JSON生成器，只输出符合Schema的JSON，不输出任何其他文字。

## 课程学情
专业：{major}
课程：{course_name}
薄弱点：{weak_points}
层次：{level}

## 学生特征
{student_feature}

## 强制要求
1. 每个知识点必须包含：name（名称） + content（详细内容解释）
2. 薄弱点内容要更详细、更基础、更通俗
3. 【必须】根据学生特征自动适配（对照以下规则选择适用项）：
   - foundation_level=薄弱/入门 → 内容简单、例子多、概念要类比生活、拆到最小粒度
   - knowledge_level=薄弱 → 重点在"是什么"和"怎么用"，减少"为什么"的深层解释
   - problem_solving/logical_thinking=弱 → 内容要细、步骤要多，减少跨模块跳连
   - learning_style=动手型 → 增加应用场景、实战案例、行业用例作为叶节点
   - learning_style=视觉型 → content字段中多描述图形配合方式、多表格对比
   - learning_pace=快速学习者 → 导图可以更精简、跨度更大，增加横向拓展节点
   - learning_pace=深度思考者 → 导图更细更全，保留更多中间步骤和思考节点
   - frustration_tolerance=低 → 避免一次性展示太多节点造成压迫，分层逐步展开
   - creativity_innovation=高 → 增加"思考题"节点和"延伸探索"分支
4. 输出严格JSON，结构必须为3层（大主题 → 子模块 → 知识点）：

第1层（根节点）：name = 课程/大主题名称（如"Python基础"）
第2层（子模块）：name = 模块名称（如"变量与数据类型"），无content字段
第3层（知识点）：name = 具体知识点名称 + content = 详细解释

示例结构：
{{"name": "Python基础", "children": [
  {{"name": "变量与数据类型", "children": [
    {{"name": "整型int", "content": "整型用于表示整数..."}},
    {{"name": "浮点型float", "content": "浮点型用于表示小数..."}}
  ]}},
  {{"name": "运算符与表达式", "children": [
    {{"name": "算术运算符", "content": "加减乘除取余..."}},
    {{"name": "比较运算符", "content": "大于小于等于..."}}
  ]}}
]}}

## 输出格式硬性规则
- 只输出JSON，不要任何解释、标记、代码块
- 不要```json或```包裹
- 不要有注释（// 或 /* */）
- 字符串必须用双引号，不要用单引号
- 最后一个属性后面不要有逗号
- 确保JSON是合法可解析的
- 必须严格3层结构，第2层只有name和children，第3层有name和content
"""

        response = await self.llm.ainvoke(prompt)
        import json
        import re
        json_data = response.content.strip()

        json_data = re.sub(r'^```(?:json)?\s*', '', json_data)
        json_data = re.sub(r'\s*```$', '', json_data)
        json_data = re.sub(r',\s*}', '}', json_data)
        json_data = re.sub(r',\s*]', ']', json_data)

        try:
            result = json.loads(json_data)
        except json.JSONDecodeError as e:
            print(f"  ⚠️ 思维导图 JSON 解析失败，尝试修复: {e}")
            # ★★★ 先用正则进行基础修复（尾部逗号、多余换行、注释等）★★★
            _clean = json_data
            # 移除 // 和 /* */ 注释
            _clean = re.sub(r'//[^\n]*', '', _clean)
            _clean = re.sub(r'/\*.*?\*/', '', _clean, flags=re.DOTALL)
            # 移除首尾非 JSON 内容（保留 { } 包裹的部分）
            _brace_start = _clean.find('{')
            _brace_end = _clean.rfind('}')
            if _brace_start != -1 and _brace_end != -1 and _brace_end > _brace_start:
                _clean = _clean[_brace_start:_brace_end+1]
            # 移除尾逗号
            _clean = re.sub(r',\s*}', '}', _clean)
            _clean = re.sub(r',\s*]', ']', _clean)
            try:
                result = json.loads(_clean)
                print(f"  ✅ 正则修复JSON成功")
            except json.JSONDecodeError as e2:
                print(f"  ⚠️ 正则修复仍失败: {e2}，尝试 LLM 修复")
                try:
                    from utils.llm_config import get_chat_openai
                    fix_llm = get_chat_openai(temperature=0.1)
                    fix_prompt = f"""你是一个JSON修复器。以下JSON有语法错误，请修复。

错误信息: {e2}

要求:
1. 只输出修复后的JSON，不要任何解释
2. 不要用```包裹
3. 确保所有字符串用双引号
4. 删除所有注释
5. 修复所有尾逗号
6. 结构必须为: {{"name": "标题", "children": [{{"name": "模块", "children": [{{"name": "知识点", "content": "内容"}}]}}]}}

待修复JSON:
{_clean[:2000]}
"""
                    fix_resp = await fix_llm.ainvoke(fix_prompt)
                    fixed = fix_resp.content if hasattr(fix_resp, 'content') else str(fix_resp)
                    # 提取 {} 包裹的 JSON 部分
                    _start = fixed.find('{')
                    _end = fixed.rfind('}')
                    if _start != -1 and _end != -1:
                        fixed = fixed[_start:_end+1]
                    result = json.loads(fixed)
                    print(f"  ✅ LLM修复JSON成功")
                except Exception as e3:
                    print(f"  ❌ LLM修复也失败: {e3}")
                    return {"status": "error", "message": f"思维导图生成JSON格式错误", "name": "思维导图", "children": []}
        
        # TTS语音合成（可选）- 提取思维导图节点摘要
        if enable_tts and result:
            user_id = info.get("user_id", "unknown")
            tts_text = self._extract_mindmap_summary(result)
            tts_path = await generate_tts_audio(
                text=tts_text,
                agent_name="mindmap_agent",
                user_id=user_id
            )
            if tts_path:
                result["tts_audio_path"] = tts_path

        # ★★★ 将生成的思维导图自动入库（供推荐系统使用）★★★
        try:
            from Agent.children_agent.recommendation.resource_db import ResourceDB
            from Agent.children_agent.recommendation.semantic_store import SemanticStore
            _rdb = ResourceDB()
            _sem = SemanticStore()
            import hashlib, json
            uid = info.get("user_id", "unknown")
            topic = info.get("user_input", info.get("course_name", "思维导图"))
            mm_name = result.get("name", topic)
            mid = f"mm_{hashlib.md5(f'{uid}_{topic}'.encode()).hexdigest()[:12]}"
            mindmap_json = await loop.run_in_executor(None, lambda: json.dumps(result, ensure_ascii=False))
            summary = self._extract_mindmap_summary(result, max_depth=1)
            await loop.run_in_executor(None, lambda: _rdb.upsert_document(
                did=mid, category="mindmap",
                title=mm_name, topic=topic,
                difficulty=3, knowledge_points=[topic],
                content=mindmap_json, summary=summary,
                metadata={"user_id": uid, "format": "json"}
            ))
            await loop.run_in_executor(None, lambda: _sem.store_document(
                did=mid, category="mindmap",
                topic=topic, difficulty=3,
                title=mm_name, content=mindmap_json,
                summary=summary
            ))
            print(f"   ✅ 思维导图已入库")
        except Exception as e:
            print(f"   ⚠️ 思维导图入库失败（不影响使用）: {e}")

        # ★★★ MemoryHub：记录工作记忆 ★★★
        try:
            if self.memory_hub and user_id:
                topic = info.get("user_input", info.get("course_name", ""))
                if topic:
                    await loop.run_in_executor(None, lambda: self.memory_hub.working.set_current_topic(user_id, topic))
                    await loop.run_in_executor(None, lambda: self.memory_hub.working.add_focus_knowledge(user_id, topic))
                    await loop.run_in_executor(None, lambda: self.memory_hub.working.set_current_task(user_id, "mindmap", f"思维导图: {topic}"))
        except Exception:
            pass

        return result

    def _extract_mindmap_summary(self, mindmap_data: Dict[str, Any], max_depth: int = 2) -> str:
        """从思维导图JSON中提取节点摘要用于TTS"""
        parts = []
        name = mindmap_data.get('name', '思维导图')
        parts.append(f"思维导图：{name}")
        
        def _collect_nodes(node: Dict[str, Any], depth: int):
            if depth > max_depth:
                return
            children = node.get('children', [])
            for child in children:
                child_name = child.get('name', '')
                child_content = child.get('content', '')
                if child_name:
                    if child_content:
                        parts.append(f"{child_name}：{child_content[:80]}")
                    else:
                        parts.append(child_name)
                _collect_nodes(child, depth + 1)
        
        _collect_nodes(mindmap_data, 0)
        # 合并并截断
        summary = "。".join(parts[:10])
        return summary[:1000]
    
    async def update_features_after_creation(
        self,
        student_features: Dict[str, Any],
        creation_data: Dict[str, Any],
        mindmap_info: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        根据思维导图创建行为动态更新学生特征（异步版本）
        
        Args:
            student_features: 当前学生特征（如果不提供且有user_id，会从中央管理器获取）
            creation_data: 创建行为数据
                - node_count: 节点数量
                - depth_level: 深度层级
                - time_spent: 花费时间
                - structure_quality: 结构质量 (high/medium/low)
                - logical_clarity: 逻辑清晰度 (high/medium/low)
                - creativity_score: 创新性评分 (0-100)
            mindmap_info: 思维导图信息（可选）
            user_id: 用户ID（如果提供，会自动保存更新后的特征到中央管理器）
            
        Returns:
            Dict: 更新后的特征数据
        """
        try:
            loop = asyncio.get_running_loop()
            # ★★★ 关键：如果没有提供student_features但有user_id，从中央管理器获取 ★★★
            if student_features is None and user_id:
                student_features = await self.feature_updater.get_latest_features_async(user_id)
                if student_features:
                    print(f"📖 [思维导图Agent] 从中央管理器获取了用户 {user_id} 的最新特征")
            
            if not student_features:
                print("⚠️ [思维导图Agent] 没有学生特征数据，跳过更新")
                return {
                    "status": "skipped",
                    "message": "没有学生特征数据"
                }
            
            # 构建性能数据
            performance_data = {
                "node_count": creation_data.get('node_count', 0),
                "depth_level": creation_data.get('depth_level', 0),
                "time_spent": creation_data.get('time_spent', ''),
                "structure_quality": creation_data.get('structure_quality', 'medium'),
                "logical_clarity": creation_data.get('logical_clarity', 'medium'),
                "creativity_score": creation_data.get('creativity_score', 50)
            }
            
            if mindmap_info:
                performance_data['course_name'] = mindmap_info.get('course_name', '')
                performance_data['topic'] = mindmap_info.get('topic', '')
            
            # 评估完成质量
            structure = creation_data.get('structure_quality', 'medium')
            logic = creation_data.get('logical_clarity', 'medium')
            creativity = creation_data.get('creativity_score', 50)
            
            if structure == 'high' and logic == 'high' and creativity >= 75:
                completion_quality = "high"
            elif structure in ['medium', 'high'] and creativity >= 50:
                completion_quality = "medium"
            else:
                completion_quality = "low"
            
            # ★★★ 后台异步更新特征，不阻塞资源返回 ★★★
            asyncio.create_task(
                self.feature_updater.update_features_async(
                    current_features=student_features,
                    task_type="mindmap_creation",
                    task_content=f"思维导图：{mindmap_info.get('topic', '') if mindmap_info else '未知'}",
                    performance_data=performance_data,
                    completion_quality=completion_quality,
                    time_spent=creation_data.get('time_spent', ''),
                    user_id=user_id
                )
            )
            
            print(f"🔄 [思维导图Agent] 特征更新已触发（后台）")
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