"""
动画生成子Agent - 负责生成教育动画HTML页面
支持动态动画、语音解说、精美视觉效果

核心功能：
1. 根据主题生成教育动画HTML
2. 支持TTS语音解说
3. 精美的CSS/JS动画效果
4. 完整的教学流程设计

设计理念：
- 视觉吸引：精美的动画和现代设计
- 教学有效：循序渐进的知识讲解
- 互动性强：支持语音解说
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from utils.llm_config import  MODEL

# 导入TTS模块（统一使用异步辅助函数）
try:
    from utils.tts_helper import generate_tts_audio
except ImportError:
    from utils.tts_helper import generate_tts_audio

# 支持直接运行和包导入两种方式
try:
    from .dynamic_feature_updater import DynamicFeatureUpdater
except ImportError:
    from dynamic_feature_updater import DynamicFeatureUpdater


class AnimationAgent:
    """
    动画生成Agent - 提供教育动画HTML生成功能
    """

    @staticmethod
    def _clean_html_output(html_content: str) -> str:
        """清理LLM输出的HTML内容，去除前置文字和markdown代码块标记"""
        import re
        content = html_content.strip()

        # 0. 先去掉 markdown 代码块标记（```html / ```），避免干扰后续提取
        content = re.sub(r'^```(?:html)?\s*', '', content, flags=re.IGNORECASE)
        content = re.sub(r'\s*```\s*$', '', content, flags=re.IGNORECASE)

        # 1. 尝试找 <!DOCTYPE ... </html>
        html_full = re.search(r'(<!DOCTYPE.*?</html>)', content, re.DOTALL | re.IGNORECASE)
        if html_full:
            return html_full.group(1).strip()

        # 2. 尝试找 <html ... </html>
        html_tag = re.search(r'(<html.*?</html>)', content, re.DOTALL | re.IGNORECASE)
        if html_tag:
            return html_tag.group(1).strip()

        # 3. 兜底：如果提取不到完整标签，直接返回去掉 markdown 标记后的内容
        return content

    def _initialize_llm(self):
        """初始化LangChain ChatOpenAI（DashScope通义千问 - OpenAI兼容模式）"""
        from utils.llm_config import get_chat_openai
        return get_chat_openai(
            model="qwen3.7-max",
            temperature=0.8,
            max_tokens=16384,
            streaming=True,
            api_key="sk-b524efccda47492d92168ed3470593a8",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    def __init__(self):
        """初始化动画生成Agent"""
        self.llm = self._initialize_llm()
        # ★★★ Gemini 备用（保持原样）★★★
        self.gemini_client = None
        self.use_gemini = False
        # ★★★ 初始化动态特征更新器 ★★★
        self.feature_updater = DynamicFeatureUpdater()

    def _build_student_profile_section(self, features: Dict[str, Any]) -> str:
        """将8维度特征压缩为可读段落用于Prompt"""
        return self.feature_updater.build_student_profile_for_prompt(features)

    @staticmethod
    def _scene_templates() -> dict:
        """场景模板：针对特定主题注入固定结构"""
        return {
            "binary_tree": """
【强制固定二叉树结构】
节点数量：固定6个节点，编号为A、B、C、D、E、F
节点关系：
- 根节点：A
- A的左子节点：B；A的右子节点：C
- B的左子节点：D；B的右子节点：E
- C的右子节点：F（C无左子节点）
标准遍历顺序：
- 中序遍历：D → B → E → A → C → F（规则：左子树 → 根节点 → 右子树）
- 前序遍历：A → B → D → E → C → F（规则：根节点 → 左子树 → 右子树）
- 后序遍历：D → E → B → F → C → A（规则：左子树 → 右子树 → 根节点）
        """.strip(),
            "sorting": """
【排序算法通用规则】
- 使用柱状图/方块表示待排序数组，每个元素标注数值
- 比较操作：两个元素高亮闪烁（青绿色）→ 判断大小
- 交换操作：两个元素平滑位移互换位置，带发光轨迹
- 每轮完成后，已排序部分渐变为完成色（青色）
- 顶部显示当前轮次、比较次数、交换次数
        """.strip(),
        }

    @staticmethod
    def _detect_scene(topic: str) -> str:
        """检测主题所属场景，返回对应模板"""
        templates = AnimationAgent._scene_templates()
        keywords_map = {
            "binary_tree": ["二叉树", "遍历", "中序", "前序", "后序", "BST", "二叉搜索树"],
            "sorting": ["排序", "冒泡", "选择排序", "插入排序", "快速排序", "归并"],
        }
        for scene, keywords in keywords_map.items():
            if any(kw in topic for kw in keywords):
                return templates.get(scene, "")
        return ""

    def _create_animation_prompt(self, topic: str, student_profile: str = "") -> str:
        """创建动画生成的系统提示词（增强版：场景模板+深色科技风）"""
        scene_template = self._detect_scene(topic)
        scene_section = ""
        if scene_template:
            scene_section = f"""
【场景模板 - 必须严格遵守】
{scene_template}
"""

        return f"""请生成一个精美的教育动画HTML页面，讲解主题：{topic}

{student_profile}

{scene_section}

**【关键】必须根据学生画像动态调整动画风格：**
- foundation_level=薄弱/入门 → 动画更慢、每步停留更久、例子更生活化、解说要非常详细
- knowledge_level=薄弱 → 概念解释要更细致，避免跳过中间步骤，解说语速慢
- problem_solving/logical_thinking=弱 → 动画要拆解到最小步骤，每个步骤之间有过渡动画连接
- learning_style=视觉型 → 动画要有丰富配色、图形演示、图解说明，减少纯文字
- learning_style=动手型 → 增加"跟着做"环节、步骤高亮可点击、实战模拟
- learning_pace=快速学习者 → 动画节奏紧凑，减少重复讲解，语速适中，可增加挑战关卡
- learning_pace=深度思考者 → 动画放缓，每步有思考提示，提供多种理解角度入口
- frustration_tolerance=低 → 错误提示要温和（"没关系，再试一次"），不要红色警告，减少压迫感
- confidence_level=低 → 解说要多用鼓励语言，多肯定，适当降低题目难度暗示
- emotional_state.interest_level=高 → 动画可以更有趣，增加小惊喜元素，扩展相关话题
- emotional_state.interest_level=低 → 动画简洁明快，不拖沓，用轻松话题引导

**核心要求（非常重要）：**
1. **必须是动态动画，不是静态页面！**
   - 使用CSS `@keyframes` 动画让元素动起来
   - 或使用JavaScript `setInterval` / `requestAnimationFrame` 实现动画效果
   - 元素要有进入动画、过渡动画、强调动画
   - 整个页面应该像一个正在播放的视频

2. **必须有交互控件和重播控制（非常重要！）**
   - 页面内添加 **「▶ 开始」** 和 **「🔄 重置/重新播放」** 按钮，点击后从头开始播放动画
   - 所有核心动画播放完毕后，应**自动循环**重新开始，或显示明显的「重新播放」提示
   - 示例按钮样式：`<button onclick="restartAnimation()" style="..." >🔄 重新播放</button>`
   - 必须在 JavaScript 中实现 `restartAnimation()` 函数来重置所有动画状态
   - 使用 `animation-play-state: paused/running` 或 JS 重置动画类来实现重播

3. **完整的HTML结构**：
   - 必须包含 `<!DOCTYPE html>`、`<html>`、`<head>`、`<body>` 等完整标签
   - 所有CSS和JavaScript都内联在HTML中

4. **动画效果要求**：
   - **开场动画**：元素依次淡入、滑入、缩放出现
   - **过程动画**：图形移动、旋转、变形、颜色渐变
   - **强调动画**：重要内容闪烁、脉动、高亮（使用青绿色发光效果）
   - **转场动画**：场景切换时平滑过渡
   - **循环动画**：背景元素持续运动（如粒子、光晕）

5. **视觉设计规范（清新浅色风）**：
   - **背景**：纯白或浅灰背景（#ffffff / #f8f9fa），主色调使用蓝色（#3b82f6 / #667eea）作为高亮色
   - **元素**：圆角卡片（border-radius:12px），浅色背景轻阴影（box-shadow: 0 4px 12px rgba(0,0,0,0.08)）
   - **强调**：关键节点使用蓝色/紫色渐变高亮，适当阴影深度
   - **布局**：全屏居中，元素层次分明，2K分辨率下清晰可见
   - 动画节奏适中（每个动画2-5秒），不要太快或太慢

6. **语音解说文本（TTS）**：
   - 在HTML中添加 `<p class="narration">` 标签包裹解说文字
   - 解说文字简洁明了，适合朗读（每段20-40字）
   - 解说与动画内容同步，帮助理解
   - 示例：`<p class="narration">光合作用是植物利用阳光制造食物的过程。</p>`

7. **技术要求**：
   - 使用现代CSS动画（`@keyframes`, `animation`, `transition`）
   - 或使用JavaScript实现复杂动画逻辑
   - 添加 `animation-delay` 实现元素依次出现的效果
   - 确保动画流畅，使用 `transform` 和 `opacity` 属性
   - 不要使用外部依赖（如CDN），所有资源内联

8. **内容组织与节奏**：
   - **0-3秒**：标题和主题淡入出现
   - **3-10秒**：核心概念动画展示
   - **10-20秒**：详细过程逐步展开
   - **20-25秒**：重点内容强调和总结
   - **25-30秒**：结尾淡出或循环播放

**输出格式：**
只输出完整的HTML代码，不要包含代码块标记，不要有其他解释文字。
直接从 `<!DOCTYPE html>` 开始，到 `</html>` 结束。"""

    async def generate_animation(
        self,
        topic: str,
        user_id: Optional[str] = None,
        enable_tts: bool = True,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        生成教育动画HTML（完整版本，非流式）
        
        Args:
            topic: 动画主题
            user_id: 用户ID（可选）
            enable_tts: 是否启用TTS语音解说
            history: 对话历史（可选）
            
        Returns:
            Dict: 包含html内容和音频文件路径
        """
        try:
            print(f"\n🎨 [动画Agent] 开始生成动画: {topic}")

            # ★★★ 获取学生画像（用于个性化动画难度与讲解）★★★
            student_profile = ""
            anim_features = None  # 保存特征引用，供后台更新使用
            if user_id:
                anim_features = await self.feature_updater.get_latest_features_async(user_id)
                if anim_features:
                    print(f"📖 [动画Agent] 获取学生画像进行个性化动画生成")
                    student_profile = self._build_student_profile_section(anim_features)
                else:
                    student_profile = "【学生画像】未获取到（将使用通用动画风格）"
            else:
                student_profile = "【学生画像】未提供（将使用通用动画风格）"

            # 构建消息 - 使用LangChain消息对象（兼容ainvoke）
            system_prompt = self._create_animation_prompt(topic, student_profile)
            from langchain_core.messages import SystemMessage, HumanMessage
            msgs = [SystemMessage(content=system_prompt)]
            
            # 添加历史对话（如果有）
            if history:
                for msg in history:
                    if msg.get("role") == "system":
                        msgs.append(SystemMessage(content=msg.get("content", "")))
                    elif msg.get("role") == "user":
                        msgs.append(HumanMessage(content=msg.get("content", "")))
                    elif msg.get("role") == "assistant":
                        from langchain_core.messages import AIMessage
                        msgs.append(AIMessage(content=msg.get("content", "")))
                    else:
                        msgs.append(HumanMessage(content=msg.get("content", "")))
            
            # 添加用户输入
            msgs.append(HumanMessage(content=topic))
            
            # 调用LLM生成HTML
            print(" 正在调用LLM生成动画HTML...")
            
            if self.use_gemini:
                # Gemini API
                full_prompt = system_prompt + "\n\n" + topic
                if history:
                    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
                    full_prompt = history_text + "\n\n" + full_prompt
                
                response = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self.gemini_client.models.generate_content(
                        model="sdfsg",
                        contents=full_prompt
                    )   #  该参数没用 方法只是测试
                )
                html_content = response.text
            else:
                # OpenAI兼容接口（阿里云DashScope）- 使用ChatOpenAI实现SSE逐词推送
                response = await self.llm.ainvoke(msgs)
                html_content = response.content if response.content else ""
            
            print(f"✅ HTML生成完成，长度: {len(html_content)} 字符")

            # 清理HTML内容（去除LLM前置文字和markdown代码块）
            html_content = self._clean_html_output(html_content)
            print(f"✅ HTML清理完成，长度: {len(html_content)} 字符")

            # 构建返回结果
            result = {
                "status": "success",
                "type": "animation",
                "html": html_content,
                "topic": topic
            }
            
            # 如果启用TTS，生成语音（统一使用异步辅助函数）
            if enable_tts:
                try:
                    print("🎤 正在生成TTS语音...")
                    tts_text = self._extract_tts_text(html_content, topic)
                    
                    if tts_text:
                        audio_url = await generate_tts_audio(
                            text=tts_text,
                            agent_name="animation_agent",
                            user_id=user_id
                        )
                        
                        if audio_url:
                            result["tts_audio_path"] = audio_url
                            result["audio_url"] = audio_url
                            print(f"✅ TTS音频生成成功: {audio_url}")
                            
                except Exception as e:
                    print(f"⚠️ TTS生成失败: {e}，继续返回HTML内容")
            
            # ★★★ 后台异步更新特征（不阻塞动画返回）★★★
            if user_id and anim_features:
                asyncio.create_task(
                    self.feature_updater.update_features_async(
                        current_features=anim_features,
                        task_type="animation_generation",
                        task_content=f"动画生成：{topic}",
                        performance_data={
                            "animation_generated": True,
                            "html_length": len(html_content),
                            "has_tts": "tts_audio_path" in result,
                        },
                        completion_quality="good",
                        time_spent="2分钟",
                        user_id=user_id
                    )
                )
            
            # ★★★ 将生成的动画自动入库（供推荐系统使用）★★★
            try:
                from Agent.children_agent.recommendation.resource_db import ResourceDB
                from Agent.children_agent.recommendation.semantic_store import SemanticStore
                _rdb = ResourceDB()
                _sem = SemanticStore()
                import hashlib
                uid = user_id or "unknown"
                anim_topic = topic
                anim_title = f"动画：{anim_topic}"
                aid = f"anim_{hashlib.md5(f'{uid}_{anim_topic}'.encode()).hexdigest()[:12]}"
                summary = self._extract_tts_text(html_content, anim_topic)[:300]
                _rdb.upsert_document(
                    did=aid, category="animation",
                    title=anim_title, topic=anim_topic,
                    difficulty=3, knowledge_points=[anim_topic],
                    content=html_content, summary=summary,
                    metadata={"user_id": uid, "format": "html", "has_tts": "tts_audio_path" in result}
                )
                _sem.store_document(
                    did=aid, category="animation",
                    topic=anim_topic, difficulty=3,
                    title=anim_title, content=html_content,
                    summary=summary
                )
                print(f"   ✅ 动画已入库")
            except Exception as e:
                print(f"   ⚠️ 动画入库失败（不影响使用）: {e}")

            return result
            
        except Exception as e:
            print(f"❌ 动画生成失败: {e}")
            return {
                "status": "error",
                "type": "animation",
                "error": str(e),
                "topic": topic
            }

    def _extract_tts_text(self, html_content: str, topic: str) -> str:
        """
        从HTML内容中提取适合TTS的文本
        
        Args:
            html_content: HTML内容
            topic: 主题
            
        Returns:
            str: 提取的TTS文本
        """
        import re
        
        # 尝试提取中文解说文本
        patterns = [
            r'<p[^>]*>([^<]*?)</p>',
            r'<div[^>]*class="[^"]*subtitle[^"]*"[^>]*>([^<]*?)</div>',
            r'<!-- narration -->\s*(.*?)\s*<!-- end narration -->',
            r'<span[^>]*class="[^"]*caption[^"]*"[^>]*>([^<]*?)</span>',
        ]
        
        extracted_texts = []
        for pattern in patterns:
            matches = re.findall(pattern, html_content, re.DOTALL)
            for match in matches:
                clean_text = re.sub(r'<[^>]+>', '', match)
                clean_text = clean_text.strip()
                if clean_text and len(clean_text) > 5:
                    extracted_texts.append(clean_text)
        
        # 如果没有找到特定模式，返回主题作为备选
        if not extracted_texts:
            return f"关于{topic}的知识讲解"
        
        # 合并并限制长度
        combined_text = " ".join(extracted_texts[:3])
        return combined_text[:500]

    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent的基本信息"""
        return {
            "name": "动画生成Agent",
            "role": "教育动画设计师",
            "description": "生成精美的教育动画HTML页面，支持TTS语音解说",
            "capabilities": [
                "根据主题生成教育动画HTML",
                "支持CSS/JS动态动画效果",
                "自动生成TTS语音解说",
                "精美的视觉设计",
                "完整的教学流程"
            ]
        }


# -----------------------------------------------------------------------
# 保留原有的FastAPI应用代码（用于独立测试）
# -----------------------------------------------------------------------
if __name__ == '__main__':
    from fastapi import FastAPI
    import uvicorn
    
    app = FastAPI(title="AI Animation Backend", version="1.0.0")
    
    @app.post("/generate")
    async def generate_animation_api():
        """测试接口"""
        agent = AnimationAgent()
        result = await agent.generate_animation(
            topic="光合作用",
            enable_tts=True
        )
        return result
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
