"""
课程讲解文档Agent - 多智能体资源生成
负责根据学生专业、课程、知识短板、学习层次生成结构化专业课程讲解文档
支持动态特征更新 - 根据阅读行为实时更新学生画像
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from langchain_core.prompts import PromptTemplate
from utils.llm_config import get_chat_openai

# TTS辅助函数
try:
    from utils.tts_helper import generate_tts_audio
except ImportError:
    from utils.tts_helper import generate_tts_audio

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


class CourseDocAgent:
    """
    课程文档生成Agent - 生成结构化专业课程讲解文档
    """

    def __init__(self):
        """初始化课程文档Agent"""
        self.llm = self._initialize_llm()
        self.doc_template = self._create_doc_template()
        
        # 初始化动态特征更新器
        self.feature_updater = DynamicFeatureUpdater()

        # ★★★ MemoryHub 统一记忆中心 ★★★
        try:
            self.memory_hub = MemoryHub()
        except Exception:
            self.memory_hub = None
        
        # ★★★ 新增：初始化RAG知识库增强器 ★★★
        self._rag_enhancer = None

    def _initialize_llm(self):
        """初始化LLM模型（使用统一配置）"""
        try:
            return get_chat_openai(temperature=0.5, max_tokens=20000, streaming=True)
        except Exception as e:
            raise Exception(f"初始化课程文档Agent LLM失败: {e}")

    def _create_doc_template(self) -> PromptTemplate:
        """创建课程讲解文档生成提示词模板（纯提示词控制论文格式，支持RAG增强）"""
        template = """
    你是资深高校专业课授课教师，专门为本科大学生撰写**正式学术讲义、课程讲解文档**。
    所有输出严格遵守人类Word排版规范，**不使用任何Markdown符号、不使用#、*、`等特殊符号**。

    学生画像信息：
    专业：{major}
    课程名称：{course_name}
    知识短板：{weak_points}
    学习层次：{learn_level}

    学生特征画像（必须根据这个个性化生成文档难度与讲解风格）：
    {student_feature}

    {rag_context_section}

    {adopted_suggestions_section}

    【根据学生特征生成规则 - 必须严格执行】
    1. foundation_level=薄弱/入门 → 讲解更通俗、更慢、更细、多举例，概念要类比生活
    2. knowledge_level=薄弱 → 重点讲概念、不讲复杂推导，避免跳跃式讲解
    3. problem_solving/logical_thinking=弱 → 少抽象、多步骤拆解、少专业术语，每步有示例
    4. learning_style=动手型/实践型 → 多案例、多实操说明，代码演示占更大比重
    5. learning_style=视觉型 → 增加图解、流程图、表格对比，文字配合图形呈现
    6. learning_pace=快速学习者 → 节奏紧凑，可适当增加深度和拓展内容
    7. learning_pace=深度思考者 → 节奏放缓，给予充分思考空间，不急于推进
    8. motivation_strength=内在动机强 → 可以讲更多"为什么"，深入原理激发兴趣
    9. motivation_strength=外在动机弱 → 语言更易懂、目标更具体，先建立信心
    10. frustration_tolerance=低 → 先肯定再给建议，不直接指出错误，多用"我们可以…"

    【★★★ 内容详细程度要求 - 必须严格执行 ★★★】
    1. **课程整体概述**：至少500字，包括课程背景、重要性、应用场景
    2. **知识脉络框架**：至少800字，详细梳理知识体系结构，用文字描述各模块关系
    3. **核心知识点精讲**：这是重点！每个主要知识点至少600-800字，包括：
       - 定义和概念解释（200字）
       - 原理和机制说明（200字）
       - 具体示例和代码演示（200字）
       - 注意事项和常见误区（100字）
    4. **重难点针对性解析**：至少1000字，深入剖析难点，提供多种理解角度
    5. **常见易错点总结**：至少600字，列举5-8个典型错误，每个都要详细说明
    6. **个性化学习建议**：至少400字，给出具体可行的学习计划和方法
    
    **总体目标：整篇文档不少于2000字，确保内容详实、全面、深入**

    【强制排版硬性规定，必须严格执行】
    1、全文字体统一为**宋体**，所有正文、标题、注释全部宋体；
    2、所有正文段落**强制首行缩进两个汉字**，段落间距自然分段；
    3、标题层级严格使用中文正式层级：
       一级标题：一、二、三、
       二级标题：（一）（二）（三）
       三级标题：1. 2. 3.
       禁止任何英文符号、禁止markdown格式；
    4、文中**重点概念、难点、专有名词、学生薄弱知识点{weak_points}必须加粗强调**；
    5、整篇文档文风严肃学术化，适配本科教学标准，通俗易懂、逻辑严谨；
    6、针对学生知识短板：{weak_points}，必须重点扩写、通俗拆解、详细讲解，篇幅多于普通知识点；
    7、**重要：如果提供了【相关知识库内容】，必须严格基于这些内容生成讲解，确保知识点准确性和权威性**；
    8、整篇文档结构固定，顺序不可打乱：
       ①课程整体概述 ②知识脉络框架 ③核心知识点精讲 ④重难点针对性解析 ⑤常见易错点总结 ⑥个性化学习建议；
    9、不要多余前言、不要多余结语、不要解释自己的工作，只输出纯净正式文档；
    10、生成的文本**复制粘贴进Word不需要任何格式调整，直接是标准本科论文排版样式**。

    请严格按照以下固定JSON格式返回，**只返回纯JSON，不要多余字符、不要注释、不要markdown代码块**：
    {{
      "doc_title": "课程完整标题",
      "course_name": "对应课程名",
      "major": "所属专业",
      "doc_content": "这里输出整篇已经排版完毕、宋体规范、首行缩进、重点加粗、层级清晰的纯中文正式课程文档",
      "generate_time": "生成时间",
      "target_level": "适配学习层次"
    }}
    """.strip()
        return PromptTemplate.from_template(template)

    def _build_student_profile_section(self, features: Dict[str, Any]) -> str:
        """将8维度特征压缩为可读段落用于Prompt"""
        if not features:
            return "【学生画像】未获取到（将使用通用讲解风格）"
        jzon = self.feature_updater._compact_features_for_prompt(features, compression_level="balanced")
        lines = ["【学生画像 - 请据此调整讲解难度与风格】"]
        schema_map = jzon.get("z.f", {})
        values_map = jzon.get("z.c", {})
        for dim, fields in schema_map.items():
            values = values_map.get(dim, [])
            for field_name, val in zip(fields, values):
                if val is not None:
                    lines.append(f"  - {field_name}: {val}")
        return "\n".join(lines) if len(lines) > 1 else "【学生画像】信息不足（将使用通用讲解风格）"

    async def generate_course_document_async(self, student_info: Dict[str, Any], save_to_file: bool = True, user_id: Optional[str] = None, enable_tts: bool = False) -> Optional[Dict[str, Any]]:
        """
        异步生成专业课程讲解文档（支持RAG增强 + 个性化学生画像）
        :param student_info: 学生画像字典，包含major/course_name/weak_points/learn_level/student_feature
        :param save_to_file: 是否自动保存到文件(默认True)
        :param user_id: 用户ID（可选，用于RAG检索）
        :param enable_tts: 是否启用TTS语音合成
        :return: 结构化文档JSON数据(包含file_path字段)
        """
        try:
            major = student_info.get("major", "计算机科学与技术")
            course_name = student_info.get("course_name", "人工智能导论")
            weak_points = student_info.get("weak_points", "神经网络、大模型基础原理")
            learn_level = student_info.get("learn_level", "本科大二 基础一般")
            loop = asyncio.get_running_loop()
            # ★★★ 获取并压缩学生特征 ★★★
            student_feature = self._build_student_profile_section(
                student_info.get("student_feature", {})
            )

            # ★★★ RAG知识库检索（如果提供了user_id）★★★
            rag_context = ""
            if user_id:
                # 优先使用薄弱点，如果没有则使用课程名称作为检索关键词
                search_query = weak_points if weak_points else course_name
                
                if search_query:
                    print(f"\n📚 [课程文档Agent] 正在检索知识库中关于'{search_query}'的资料...")
                    rag_result = await self._query_knowledge_for_document(search_query, user_id)
                    if rag_result.get("status") == "success":
                        rag_context = rag_result.get("context", "")
                        print(f"✅ 检索到 {rag_result.get('doc_count', 0)} 个相关知识点，将融入文档生成")
                    else:
                        print(f"⚠️  知识库中未找到相关内容，将使用LLM通用知识")
                else:
                    print(f"⚠️  没有提供检索关键词，跳过RAG检索")

            # 动态构建RAG上下文部分
            if rag_context:
                rag_context_section = f"""
    【相关知识库内容 - 针对薄弱点的权威资料】
    {rag_context}

    **请基于上述知识库内容，针对学生薄弱点进行重点讲解**
    """
            else:
                rag_context_section = ""

            # ★★★ 从动态特征中获取已采纳的评估建议，影响文档生成 ★★★
            adopted_suggestions_section = ""
            if user_id:
                try:
                    from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
                    updater = DynamicFeatureUpdater()
                    adopted = updater.get_adopted_suggestions(user_id)
                    if adopted:
                        print(f"📌 [课程文档Agent] 读取到 {len(adopted)} 条已采纳的评估建议，将影响文档生成")
                        lines = ["【用户已采纳的学习建议 - 请严格遵守】"]
                        for s in adopted:
                            s_type = s.get("type", "")
                            s_content = s.get("content", "")
                            s_weight = s.get("weight", 0.5)
                            if s_type == "knowledge_priority":
                                lines.append(f"  - 📖 优先知识点（权重{s_weight}）: 重点讲解「{s_content}」相关的内容")
                            elif s_type == "difficulty_adjustment":
                                lines.append(f"  - ⚡ 难度倾向（权重{s_weight}）: {s_content}")
                            elif s_type == "resource_adjustment":
                                lines.append(f"  - 📚 资源偏好（权重{s_weight}）: {s_content}")
                            elif s_type == "pace_advice":
                                lines.append(f"  - 🏃 学习节奏（权重{s_weight}）: {s_content}")
                        adopted_suggestions_section = "\n".join(lines)
                except Exception as e:
                    print(f"  ⚠️ [课程文档Agent] 读取采纳建议失败（不影响生成）: {e}")

            prompt = self.doc_template.format(
                major=major,
                course_name=course_name,
                weak_points=weak_points,
                learn_level=learn_level,
                student_feature=student_feature,
                rag_context_section=rag_context_section,
                adopted_suggestions_section=adopted_suggestions_section
            )

            print("\n📄 [课程文档Agent] 正在生成专业课程讲解文档...")
            response = await self.llm.ainvoke(prompt)
            doc_text = response.content if hasattr(response, 'content') else str(response)

            # 解析JSON响应
            result = self._parse_json_response(doc_text)
            if result:
                print(f"✅ 课程文档生成完成: {result.get('doc_title', '')}")
                
                # ✅ 自动保存到文件
                if save_to_file:
                    file_path = self._save_document_to_file(result)
                    if file_path:
                        result['file_path'] = file_path
                        print(f"💾 文档已保存: {file_path}")
                        # ★★★ 上传 .docx 到 OSS ★★★
                        try:
                            from services.oss_storage import upload_file as oss_upload, get_public_url
                            oss_key = oss_upload(
                                local_path=file_path,
                                user_id=user_id or "unknown",
                                resource_type="document",
                                filename=result.get("doc_title", "文档") + ".docx",
                            )
                            if oss_key:
                                result["oss_key"] = oss_key
                                result["oss_url"] = get_public_url(oss_key)
                                print(f"  ✅ 文档已上传 OSS: {result['oss_url']}")
                        except Exception as e:
                            print(f"  ⚠️ 文档上传 OSS 失败（不影响使用）: {e}")
                
                # TTS语音合成（可选）- 提取文档摘要进行TTS
                if enable_tts:
                    # 提取文档标题和概述作为TTS文本（避免过长）
                    tts_text = result.get('doc_title', '')
                    doc_content = result.get('doc_content', '')
                    if doc_content:
                        # 取前500字作为TTS摘要
                        tts_text += "。" + doc_content
                    tts_path = await generate_tts_audio(
                        text=tts_text,
                        agent_name="course_doc_agent",
                        user_id=user_id
                    )
                    if tts_path:
                        result["tts_audio_path"] = tts_path

                # ★★★ 将生成的文档自动入库（供推荐系统使用）★★★
                try:
                    if ResourceDB and SemanticStore:
                        import hashlib
                        doc_title = result.get("doc_title", "课程文档")
                        course_name = result.get("course_name", "未知课程")
                        did = f"d_{hashlib.md5(f'{course_name}_{doc_title}'.encode()).hexdigest()[:12]}"
                        topic = course_name
                        content = result.get("doc_content", "")
                        def _do_doc_import():
                            _rdb = ResourceDB()
                            _sem = SemanticStore()
                            _did = _rdb.upsert_document(
                                did=did, category="course_document",
                                title=doc_title, topic=topic,
                                difficulty=3, knowledge_points=[],
                                content=content,
                                summary=content[:300] if content else "",
                                metadata={
                                    "major": result.get("major", ""),
                                    "target_level": result.get("target_level", ""),
                                    "file_path": result.get("file_path", ""),
                                    "oss_url": result.get("oss_url", ""),
                                    "oss_key": result.get("oss_key", "")
                                }
                            )
                            _sem.store_document(
                                did=_did or did, category="course_document",
                                topic=topic, difficulty=3,
                                title=doc_title, content=content,
                                summary=content[:300] if content else ""
                            )
                        await loop.run_in_executor(None, _do_doc_import)
                        print(f"   ✅ 课程文档已入库")
                except Exception as e:
                    print(f"   ⚠️ 文档入库失败（不影响使用）: {e}")

                # ★★★ MemoryHub：记录工作记忆 ★★★
                try:
                    if self.memory_hub and user_id:
                        topic = student_info.get("course_name", student_info.get("user_input", ""))
                        if topic:
                            await loop.run_in_executor(None, self.memory_hub.working.set_current_topic, user_id, topic)
                            await loop.run_in_executor(None, self.memory_hub.working.add_focus_knowledge, user_id, topic)
                            await loop.run_in_executor(None, self.memory_hub.working.set_current_task, user_id, "doc_gen", f"生成文档: {topic}")
                except Exception:
                    pass

                # ContentStore 持久化由 Conduct 层 integrator_node 统一负责，此处不再重复写入
                return result
            else:
                print("❌ 课程文档生成JSON解析失败")
                return None

        except Exception as e:
            print(f"❌ 生成课程文档失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析LLM返回的JSON响应（使用边界锚点法处理 doc_content 中的未转义引号）"""
        import json
        import re

        try:
            # 提取原始JSON字符串
            # 1) 优先提取 ```json ... ``` 代码块
            json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
            match = json_pattern.search(response)
            source = match.group(1) if match else response.strip()

            # 2) 找到 { 和 } 的匹配位置，提取最外层 JSON
            brace_start = source.find('{')
            brace_end = source.rfind('}')
            if brace_start == -1 or brace_end == -1 or brace_end <= brace_start:
                print("❌ 未找到有效的JSON格式")
                print(f"   响应内容预览: {response[:200]}...")
                return None
            source = source[brace_start:brace_end + 1]

            json_str = self._fix_doc_content_json(source)
            data = json.loads(json_str)
            return data

        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            print(f"   失败位置: 行{e.lineno} 列{e.colno}")
            print(f"   响应内容预览: {response[:400]}...")
            return None
        except Exception as e:
            print(f"❌ 解析响应时发生错误: {e}")
            return None

    def _fix_doc_content_json(self, raw: str) -> str:
        """
        修复 doc_content 字段的 JSON 转义问题。
        
        已知问题：
          1. doc_content 中的双引号未转义，如：她说"你好"
          2. doc_content 中含有原始控制字符（换行符 \\n 等）
        
        策略：利用已知的固定后续字段名作为锚点，
        定位 doc_content 的结束位置，然后转义其中的问题字符。
        """
        import re
        
        MARKER = '"doc_content": "'
        
        idx_marker = raw.find(MARKER)
        if idx_marker == -1:
            return raw  # 没有 doc_content 字段，直接返回
        
        value_start = idx_marker + len(MARKER)
        
        # 找到 doc_content 的结束位置：找下一个已知字段名前的 "，
        # 按优先级尝试：generate_time, target_level, 或者 JSON 结尾
        end_anchor = None
        for anchor in ['", "generate_time"', '", "target_level"', '", "doc_title"']:
            idx = raw.find(anchor, value_start)
            if idx != -1:
                end_anchor = idx
                break
        
        if end_anchor is None:
            # 找不到已知锚点，尝试末尾
            last_brace = raw.rfind('}')
            if last_brace > value_start:
                last_quote = raw.rfind('"', value_start, last_brace)
                if last_quote > value_start:
                    end_anchor = last_quote
                else:
                    return raw
            else:
                return raw
        
        # 提取 doc_content 的原始内容
        content_raw = raw[value_start:end_anchor]
        
        # 1. 转义未转义的双引号
        content_escaped = re.sub(r'(?<!\\)"', '\\"', content_raw)
        # 2. 转义控制字符（换行、回车、制表符等）
        #    注意：已经转义的 \\n 不能重复转义
        #    将原始的换行符（不是 \\n）转义
        content_escaped = content_escaped.replace('\r\n', '\\n')
        content_escaped = content_escaped.replace('\r', '\\n')
        #    将单独的 \n 替换，但避免把已经存在的 \\n 变成 \\\\n
        #    策略：先标记已有的 \\n，替换后再还原
        content_escaped = content_escaped.replace('\\n', '\x00ESC_NL\x00')
        content_escaped = content_escaped.replace('\n', '\\n')
        content_escaped = content_escaped.replace('\x00ESC_NL\x00', '\\n')
        # 3. 转义制表符
        content_escaped = content_escaped.replace('\t', '\\t')
        
        # 重组 JSON：替换 content 部分
        result = raw[:value_start] + content_escaped + raw[end_anchor:]
        
        # 移除尾部多余的逗号
        result = re.sub(r',\s*(\]|\})', r'\1', result)
        
        return result

    def _save_document_to_file(self, doc_data: Dict[str, Any]) -> Optional[str]:
        """
        将文档保存为真正的.docx格式文件
        :param doc_data: 文档数据
        :return: 文件路径
        """
        try:
            from docx import Document
            from docx.shared import Pt, Inches
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from datetime import datetime
            
            # ★★★ 使用绝对路径，避免 CWD 不同导致路径错误 ★★★
            base_dir = Path(__file__).resolve().parent.parent.parent
            save_dir = base_dir / "generated_documents"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名: 课程名_时间戳.docx
            course_name = doc_data.get('course_name', 'unknown').replace('/', '_').replace('\\', '_')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{course_name}_{timestamp}.docx"
            file_path = save_dir / filename
            
            # 创建Word文档
            doc = Document()
            
            # 设置默认字体为宋体
            style = doc.styles['Normal']
            style.font.name = '宋体'
            style.font.size = Pt(12)
            style.paragraph_format.first_line_indent = Inches(0.5)  # 首行缩进2字符
            
            # 添加居中标题
            title = doc.add_heading(doc_data.get('doc_title', '专业课程讲解文档'), level=1)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER
            
            # 添加元信息
            doc.add_paragraph(f"专业：{doc_data.get('major', '')}")
            doc.add_paragraph(f"课程：{doc_data.get('course_name', '')}")
            doc.add_paragraph(f"适配层次：{doc_data.get('target_level', '')}")
            doc.add_paragraph(f"生成时间：{doc_data.get('generate_time', '')}")
            doc.add_paragraph()  # 空行
            
            # 添加文档内容
            doc_content = doc_data.get('doc_content', '')
            if doc_content:
                # 按段落分割内容
                paragraphs = doc_content.split('\n')
                for para_text in paragraphs:
                    para_text = para_text.strip()
                    if para_text:
                        # 识别标题层级并设置不缩进
                        if para_text.startswith('一、') or para_text.startswith('二、') or para_text.startswith('三、'):
                            heading = doc.add_heading(para_text, level=1)
                            heading.paragraph_format.first_line_indent = 0
                        elif para_text.startswith('（一）') or para_text.startswith('（二）'):
                            heading = doc.add_heading(para_text, level=2)
                            heading.paragraph_format.first_line_indent = 0
                        elif para_text.startswith('1.') or para_text.startswith('2.') or para_text.startswith('3.'):
                            heading = doc.add_heading(para_text, level=3)
                            heading.paragraph_format.first_line_indent = 0
                        else:
                            # 普通段落(保持首行缩进)
                            doc.add_paragraph(para_text)
            
            # 保存文档
            doc.save(str(file_path))
            
            return str(file_path)
            
        except ImportError:
            print("⚠️  缺少python-docx库，正在安装...")
            import subprocess
            subprocess.check_call(['pip', 'install', 'python-docx'])
            print("✅ python-docx安装完成，请重新运行")
            return None
        except Exception as e:
            print(f"⚠️  保存Word文档失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def display_document(self, doc_data: Dict[str, Any]):
        """美观打印输出课程文档（对齐你display_problem风格）"""
        print("\n" + "="*70)
        print(f"📚 {doc_data.get('doc_title', '专业课程讲解文档')}")
        print("="*70)
        print(f"专业：{doc_data.get('major', '')}")
        print(f"适配层次：{doc_data.get('target_level', '')}")
        print("="*70)
        print("\n【文档正文】")
        print(doc_data.get("doc_content", ""))
        print("="*70)

    def get_agent_info(self) -> Dict[str, Any]:
        """获取Agent基本信息（和你PracticeAgent格式统一）"""
        return {
            "name": "课程文档Agent",
            "role": "专业课程讲师",
            "description": "根据学生专业、课程、知识短板生成个性化结构化课程讲解文档",
            "capabilities": [
                "生成标准化课程讲解文档",
                "针对知识短板定向强化讲解",
                "输出规范Markdown学习资料",
                "适配不同专业与学习层次",
                "动态更新学生特征画像"
            ]
        }
    
    async def update_features_after_reading(
        self,
        student_features: Dict[str, Any],
        reading_data: Dict[str, Any],
        doc_info: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None  # 新增：用户ID
    ) -> Dict[str, Any]:
        """
        根据文档阅读行为动态更新学生特征（异步版本）
        
        Args:
            student_features: 当前学生特征（如果不提供且有user_id，会从中央管理器获取）
            reading_data: 阅读行为数据
                - reading_time: 阅读时长
                - pages_read: 阅读页数
                - total_pages: 总页数
                - highlight_count: 高亮次数
                - note_count: 笔记数量
                - comprehension_score: 理解测验分数（如果有）
                - revisit_sections: 重读章节
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
                    print(f"📖 [课程文档Agent] 从中央管理器获取了用户 {user_id} 的最新特征")
            
            if not student_features:
                print("⚠️ [课程文档Agent] 没有学生特征数据，跳过更新")
                return {
                    "status": "skipped",
                    "message": "没有学生特征数据"
                }
            
            # 构建性能数据
            performance_data = {
                "reading_time": reading_data.get('reading_time', ''),
                "pages_read": reading_data.get('pages_read', 0),
                "total_pages": reading_data.get('total_pages', 0),
                "highlight_count": reading_data.get('highlight_count', 0),
                "note_count": reading_data.get('note_count', 0),
                "comprehension_quiz": reading_data.get('comprehension_score', None),
                "revisit_sections": reading_data.get('revisit_sections', []),
                "reading_speed": reading_data.get('reading_speed', '正常')
            }
            
            if doc_info:
                performance_data['document_title'] = doc_info.get('doc_title', '')
                performance_data['course_name'] = doc_info.get('course_name', '')
            
            # 评估完成质量
            pages_read = reading_data.get('pages_read', 0)
            total_pages = reading_data.get('total_pages', 1)
            completion_rate = pages_read / total_pages if total_pages > 0 else 0
            
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
                    task_type="document_reading",
                    task_content=f"文档阅读：{doc_info.get('doc_title', '') if doc_info else '未知'}",
                    performance_data=performance_data,
                    completion_quality=completion_quality,
                    time_spent=reading_data.get('reading_time', ''),
                    user_id=user_id
                )
            )
            
            print(f"🔄 [课程文档Agent] 特征更新已触发（后台）")
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
    
    async def _query_knowledge_for_document(self, weak_points: str, user_id: str) -> Dict[str, Any]:
        """
        为文档生成检索知识库中关于薄弱点的知识
        
        Args:
            weak_points: 学生的薄弱知识点（可能是多个，用逗号分隔）
            user_id: 用户ID
            
        Returns:
            Dict: 检索结果，包含context和doc_count
        """
        try:
            # 延迟导入KnowledgeBaseAgent（避免循环依赖）
            if self._rag_enhancer is None:
                from .knowledge_base_agent import KnowledgeBaseAgent
                self._rag_enhancer = KnowledgeBaseAgent()
            
            # 分割薄弱点（可能多个）
            points = [p.strip() for p in weak_points.split(',') if p.strip()]
            
            all_contexts = []
            total_docs = 0
            
            # 对每个薄弱点进行检索（使用统一的截断长度400）
            for point in points[:3]:
                print(f"   🔍 检索薄弱点: {point}")
                result = await self._rag_enhancer.query_knowledge(
                    question=point,
                    user_id=user_id,
                    context_truncate_length=500
                )
                
                if result.get("status") == "success":
                    retrieved_docs = result.get("retrieved_docs", [])
                    for i, doc in enumerate(retrieved_docs[:2], 1):
                        all_contexts.append(f"【{point} - 参考资料{i}】\n{doc['content']}")
                        total_docs += 1
            
            if all_contexts:
                context = "\n\n".join(all_contexts)
                return {
                    "status": "success",
                    "context": context,
                    "doc_count": total_docs
                }
            else:
                return {
                    "status": "no_result",
                    "context": "",
                    "doc_count": 0
                }
                
        except Exception as e:
            print(f"⚠️  知识库查询失败: {e}")
            return {
                "status": "error",
                "context": "",
                "doc_count": 0
            }