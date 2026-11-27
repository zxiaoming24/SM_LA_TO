from utils.async_llm_caller import call_llm_with_retry
from utils.llm_config import MODEL
import os
import asyncio
import hashlib
import json
import re
from typing import Dict, Any, Optional, List

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

def _repair_truncated_json(text: str) -> Optional[Dict[str, Any]]:
    """
    多层修复策略：尝试从截断/损坏的 LLM 输出中提取并修复 JSON。
    
    按优先级执行：
    1. 直接 json.loads()
    2. 从 ```json 代码块中提取
    3. 用正则提取最外层 {...} 
    4. 修复截断（闭合未关闭的字符串、平衡花括号/方括号）
    5. [兜底] 逐字段正则提取
    """
    if not text:
        return None

    # 1. 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. 从 markdown 代码块提取
    code_match = re.search(r'```(?:json)?\s*\n?(.*?)(?:\n?```|$)', text, re.DOTALL)
    if code_match:
        candidate = code_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            text = candidate  # 用提取后的内容继续尝试

    # 3. 提取最外层 {...}
    brace_match = re.search(r'\{.*', text, re.DOTALL)
    if not brace_match:
        return None
    text = brace_match.group()

    # 4. 修复截断后重试
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 4a. 尝试修复：关闭未闭合的字符串 + 平衡括号
    fixed = _fix_incomplete_json(text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 4b. 尝试删除最后一个不完整的字段后修复
    for _ in range(3):
        text = _strip_last_incomplete_field(text)
        if not text:
            break
        fixed = _fix_incomplete_json(text)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            continue

    # 5. [兜底] 逐字段正则提取（确保至少能拿回部分数据）
    partial = _extract_partial_json(text)
    if partial:
        return partial

    return None


def _fix_incomplete_json(text: str) -> str:
    """
    修复截断的 JSON 字符串：
    - 闭合未关闭的字符串（末尾的 " 缺失）
    - 平衡花括号 {} 和方括号 []（按正确的嵌套顺序）
    - 注意跳过转义的引号和字符串内部的括号
    """
    in_string = False
    escaped = False
    close_stack = []  # 用栈跟踪需要闭合的括号顺序

    for c in text:
        if escaped:
            escaped = False
            continue
        if c == '\\' and in_string:
            escaped = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            close_stack.append('}')
        elif c == '}':
            if close_stack and close_stack[-1] == '}':
                close_stack.pop()
        elif c == '[':
            close_stack.append(']')
        elif c == ']':
            if close_stack and close_stack[-1] == ']':
                close_stack.pop()

    # 闭合未关闭的字符串
    if in_string:
        text += '"'

    # 按正确的嵌套顺序闭合（栈顺序：先入后出）
    if close_stack:
        text += ''.join(reversed(close_stack))

    return text


def _strip_last_incomplete_field(text: str) -> Optional[str]:
    """
    从末尾截断最后一个不完整的字段/值对。
    从右向左找最后一个完整的 key-value 分隔符。
    """
    # 尝试找到最后一个完整的 } 或 ]，截断到那里
    # 这样能丢掉被截断的最后一个题目对象
    last_close_brace = text.rfind('}')
    last_close_bracket = text.rfind(']')
    cutoff = max(last_close_brace, last_close_bracket)
    if cutoff > 0:
        return text[:cutoff + 1]
    return None


def _extract_partial_json(text: str) -> Optional[Dict[str, Any]]:
    """
    兜底方案：通过正则提取顶级字段，至少能拿回部分完整的题目。
    适用于 JSON 严重损坏无法修复的场景。
    """
    result = {}
    # 匹配顶级 key（single_choice, multiple_choice, judge, fill_blank, short_answer）
    top_keys = ['single_choice', 'multiple_choice', 'judge', 'fill_blank', 'short_answer']
    for key in top_keys:
        pattern = re.compile(
            rf'"{re.escape(key)}"\s*:\s*\[(.*?)\]',
            re.DOTALL
        )
        match = pattern.search(text)
        if match:
            array_text = '[' + match.group(1) + ']'
            # 尝试修复并解析该数组
            try:
                items = json.loads(_fix_incomplete_json(array_text))
                if isinstance(items, list):
                    # 过滤掉非 dict 的项
                    items = [item for item in items if isinstance(item, dict)]
                    if items:
                        result[key] = items
            except (json.JSONDecodeError, TypeError):
                # 尝试逐条提取
                obj_pattern = re.compile(r'\{(.*?)\}', re.DOTALL)
                items = []
                for obj_match in obj_pattern.finditer(match.group(1)):
                    try:
                        obj = json.loads(_fix_incomplete_json('{' + obj_match.group(1) + '}'))
                        if isinstance(obj, dict):
                            items.append(obj)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if items:
                    result[key] = items

    return result if result else None


class QuestionGeneratorAgent:
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
        return get_chat_openai(temperature=0.3, max_tokens=4096, streaming=True)

    async def generate_all_questions_async(self, info: Dict[str, Any], enable_tts: bool = False) -> Dict[str, Any]:
        """
        异步版本的个性化练习题生成（支持TTS）
        
        Args:
            info: 包含major/course_name/weak_points/learn_level/user_input/student_feature/user_id
            enable_tts: 是否启用TTS语音合成
            
        Returns:
            Dict: 题目数据 + 可选的tts_audio_path
        """
        user_id = info.get("user_id", "unknown")
        major = info.get("major", "")
        course_name = info.get("course_name", "")
        weak_points = info.get("weak_points", "")
        learn_level = info.get("learn_level", "")
        user_input = info.get("user_input", "")
        student_feature = info.get("student_feature", {})

        # ★★★ 从动态特征中获取已采纳的评估建议，影响出题 ★★★
        adopted_suggestions_section = ""
        if user_id:
            try:
                adopted = await self.feature_updater.get_adopted_suggestions_async(user_id)
                if adopted:
                    print(f"📌 [理论题Agent] 读取到 {len(adopted)} 条已采纳的评估建议，将影响出题")
                    lines = ["【用户已采纳的学习建议 - 请严格遵守】"]
                    for s in adopted:
                        s_type = s.get("type", "")
                        s_content = s.get("content", "")
                        s_weight = s.get("weight", 0.5)
                        if s_type == "knowledge_priority":
                            lines.append(f"  - 📖 优先知识点（权重{s_weight}）: 重点考察「{s_content}」相关的题目")
                        elif s_type == "difficulty_adjustment":
                            action = "适当提高难度" if "调高" in s_content or "难" in s_content else ("适当降低难度" if "调低" in s_content or "简单" in s_content else "保持当前难度")
                            lines.append(f"  - ⚡ 难度倾向（权重{s_weight}）: {action} — {s_content}")
                        elif s_type == "resource_adjustment":
                            lines.append(f"  - 📚 资源偏好（权重{s_weight}）: {s_content}")
                        elif s_type == "pace_advice":
                            lines.append(f"  - 🏃 学习节奏（权重{s_weight}）: {s_content}")
                    adopted_suggestions_section = "\n".join(lines)
            except Exception as e:
                print(f"  ⚠️ [理论题Agent] 读取采纳建议失败（不影响出题）: {e}")

        prompt = f"""
你是专业个性化出题智能体，需结合【学生画像特征】+ 指定知识点，生成适配学生水平的个性化练习题，只输出标准JSON，无任何多余解释、无```包裹。

=== 基础课程信息 ===
课程专业：{major}
课程名称：{course_name}
知识薄弱点：{weak_points}
预设学习层次：{learn_level}
用户指定知识点：{user_input}

=== 学生个性化特征画像 ===
{student_feature}

{adopted_suggestions_section}

=== 出题个性化要求 ===
1. 严格围绕【用户指定知识点】和【知识薄弱点】出题
2. 根据学生画像自动适配：
   - 学术基础强弱 → 调整题目基础/拔高难度
   - 逻辑思维能力 → 调整推理类、代码分析类题目占比
   - 学习风格(视觉/动手/理论) → 侧重理论题还是编程实操题
   - 整体评分高低 → 控制题目难度、题量复杂度
3. 必须生成5类题目：单选题、多选题、判断题、填空题、简答题
4. 每类至少3道，全部附带标准答案
5. 难度、题型配比、题干表述完全贴合当前学生个人特征，做到千人千题
6. 严格按固定JSON结构输出，字段不能增删改名

=== 输出固定格式 ===
{{
  "single_choice": [
    {{
      "question": "题目内容",
      "options": ["A","B","C","D"],
      "answer": "A",
      "explanation": "选项A是正确答案的详细解析，说明为什么选这个选项"
    }}
  ],
  "multiple_choice": [
    {{
      "question": "题目内容",
      "options": ["A","B","C","D"],
      "answer": "A,C",
      "explanation": "本题中A和C是正确的，因为...（详细解析每个选项为什么对/错）"
    }}
  ],
  "judge": [
    {{
      "question": "题干",
      "answer": "正确",
      "explanation": "为什么这个判断是正确的/错误的，解释原理"
    }}
  ],
  "fill_blank": [
    {{
      "question": "题干___",
      "answer": "答案",
      "explanation": "解释为什么填入这个答案，相关知识点说明"
    }}
  ],
  "short_answer": [
    {{
      "question": "题目",
      "answer": "答案",
      "explanation": "对答案的详细解析，包含相关概念、原理和举例说明"
    }}
  ]
}}
"""

        #  实现对由于网络抖动情况的重试情况
        response = await call_llm_with_retry(self.llm, prompt, error_msg="出题Agent LLM调用")
        if response is None:
            print("  ❌ [出题] LLM调用返回空（已达最大重试次数），无法生成题目")
            return {}

        content = response.content.strip() if hasattr(response, 'content') else str(response).strip()
        if not content:
            print(f"  ❌ [出题] LLM返回内容为空，无法生成题目")
            print(f"  📋 [出题] response类型={type(response).__name__}, 完整response={str(response)[:200]}")
            return {}

        # ★★★ 使用多层修复策略解析 JSON，兼容截断/损坏的非标准输出 ★★★
        result = _repair_truncated_json(content)
        if result is None:
            print(f"  ❌ [出题] JSON解析失败（已尝试全部修复策略），无法生成题目")
            print(f"  📋 [出题] 原始内容前300字符: {content[:300]}")
            return {}

        # ★★★ 后处理：过滤掉缺少选项的选择题/多选题，确保数据质量 ★★★
        for _qt in ['single_choice', 'multiple_choice']:
            if _qt in result and isinstance(result[_qt], list):
                _before = len(result[_qt])
                result[_qt] = [q for q in result[_qt] if q.get('options') and len(q['options']) >= 2]
                _after = len(result[_qt])
                if _before != _after:
                    print(f"  ⚠️ [出题] {_qt} 过滤掉 {_before - _after} 道缺少选项的题目（保留 {_after} 道）")
                # 如果过滤后某题型为空，删除该键
                if _after == 0:
                    del result[_qt]
                    print(f"  ⚠️ [出题] {_qt} 题型因缺少有效选项被整体移除")

        # ★★★ 过滤掉缺少正确答案或内容的题目 ★★★
        _all_types = ['single_choice', 'multiple_choice', 'judge', 'fill_blank', 'short_answer']
        for _qt in _all_types:
            if _qt in result and isinstance(result[_qt], list):
                _before = len(result[_qt])
                result[_qt] = [q for q in result[_qt]
                               if q.get('answer') and str(q['answer']).strip()
                               and q.get('question') and str(q['question']).strip()]
                _after = len(result[_qt])
                if _before != _after:
                    print(f"  ⚠️ [出题] {_qt} 过滤掉 {_before - _after} 道缺少正确答案或内容的题目（保留 {_after} 道）")
                if _after == 0:
                    del result[_qt]
                    print(f"  ⚠️ [出题] {_qt} 题型因缺少正确答案或内容被整体移除")
        
        # TTS语音合成（可选）- 提取题目摘要
        if enable_tts and result:
            # 构建TTS摘要文本
            tts_parts = []
            for q_type in ['single_choice', 'short_answer', 'code_practice']:
                questions = result.get(q_type, [])
                if questions and len(questions) > 0:
                    first_q = questions[0].get('question', '')
                    if first_q:
                        tts_parts.append(first_q[:100])
            tts_text = "练习题摘要：" + "。".join(tts_parts[:3]) if tts_parts else "练习题已生成"
            
            tts_path = await generate_tts_audio(
                text=tts_text,
                agent_name="question_generator",
                user_id=user_id
            )
            if tts_path:
                result["tts_audio_path"] = tts_path

        # ★★★ 将生成的理论题自动入库（供推荐系统使用）★★★
        try:
            if ResourceDB and SemanticStore and result:
                import hashlib
                _loop = asyncio.get_running_loop()
                _results = result  # 捕获循环变量
                _info_topic = info.get("user_input", info.get("course_name", "通用"))
                _is_valid = self._is_valid_question_content
                topic = _info_topic
                def _do_question_import():
                    _rdb = ResourceDB()
                    _sem = SemanticStore()
                    for q_type, questions in _results.items():
                        if not isinstance(questions, list) or q_type == "tts_audio_path":
                            continue
                        if q_type not in ("single_choice", "multiple_choice", "judge", "fill_blank", "short_answer"):
                            continue
                        for q in questions:
                            if not isinstance(q, dict) or "question" not in q:
                                continue
                            content = q.get("question", "")
                            if not _is_valid(content):
                                print(f"  ⚠️ [出题] 跳过无效题目（含模板上下文）: {content[:60]}...")
                                continue
                            _norm = " ".join(content.strip().lower().split())
                            _fp = hashlib.md5(f"{topic}_{q_type}_{_norm}".encode()).hexdigest()[:12]
                            qid = f"q_{_fp}"
                            _rdb.upsert_question(
                                qid=qid, topic=topic, sub_topic=q_type,
                                difficulty=3,
                                knowledge_points=[topic, q_type],
                                content=content,
                                solution=q.get("answer", ""),
                                options=q.get("options", []),
                                metadata={"source": "QuestionGeneratorAgent"}
                            )
                            _sem.store_question(
                                qid=qid, topic=topic, sub_topic=q_type,
                                difficulty=3,
                                knowledge_points=[topic, q_type],
                                content=content
                            )
                await _loop.run_in_executor(None, _do_question_import)
                print(f"   ✅ 理论题已入库")
        except Exception as e:
            print(f"   ⚠️ 理论题入库失败（不影响使用）: {e}")

        # ★★★ MemoryHub：记录工作记忆 ★★★
        try:
            if self.memory_hub and user_id:
                topic = info.get("user_input", info.get("course_name", ""))
                if topic:
                    _loop = asyncio.get_running_loop()
                    await _loop.run_in_executor(None, self.memory_hub.working.set_current_topic, user_id, topic)
                    await _loop.run_in_executor(None, self.memory_hub.working.add_focus_knowledge, user_id, topic)
                    await _loop.run_in_executor(None, self.memory_hub.working.set_current_task, user_id, "question_gen", f"生成理论题: {topic}")
        except Exception:
            pass

        # ★★★ 给每道题注入 knowledge_points（前端提交/错题本推荐需要用到）★★★
        try:
            _kp = info.get("user_input", info.get("course_name", "通用"))
            for q_type, questions in result.items():
                if not isinstance(questions, list) or q_type == "tts_audio_path":
                    continue
                for q in questions:
                    if isinstance(q, dict) and "question" in q:
                        q["knowledge_points"] = [_kp, q_type]
        except Exception:
            pass

        # ★★★ 归一化 knowledge_points：统一为数组格式，兼容 LLM 可能输出的字符串格式 ★★★
        try:
            for q_type, questions in result.items():
                if not isinstance(questions, list) or q_type == "tts_audio_path":
                    continue
                for q in questions:
                    if not isinstance(q, dict):
                        continue
                    kp = q.get("knowledge_points")
                    if isinstance(kp, str):
                        q["knowledge_points"] = [kp]
                    elif kp is None:
                        q["knowledge_points"] = [info.get("user_input", info.get("course_name", "通用"))]
        except Exception:
            pass

        return result

    @staticmethod
    def _is_valid_question_content(content: str) -> bool:
        """校验题目内容是否有效：过滤掉 LLM 泄露的模板上下文"""
        if not content or not content.strip():
            return False
        # 包含用户画像/对话历史等模板标记 → 无效
        _template_markers = [
            "【最近对话】", "【用户画像】", "【知识点掌握状态】",
            "【学习统计】", "【复习提醒】", "【学习计划】",
            "[user]", "[assistant]",
            "综合评分:", "各维度:", "薄弱点:", "待复习:",
        ]
        for marker in _template_markers:
            if marker in content:
                return False
        # 题目过长（超过 500 字符）→ 大概率混入了上下文
        if len(content) > 500:
            return False
        return True

    @staticmethod
    async def judge_theory_answer(
        question_data: Dict[str, Any],
        user_answer: str,
        question_type: str = ""
    ) -> Dict[str, Any]:
        """
        基于生成的标准答案直接判题（异步，统一判题入口）

        Args:
            question_data: 单道题目的完整数据（必须包含 answer 字段）
            user_answer: 用户提交的答案
            question_type: 题目类型 (single_choice / multiple_choice / judge / fill_blank / short_answer)

        Returns:
            Dict: {
                "is_correct": bool,
                "score": int (0 或 100),
                "correct_answer": str,
                "user_answer": str,
                "question_type": str,
                "analysis": {
                    "correctness": str,       # 正误分析描述
                    "hint": str,              # 可选，错误时的提示
                    "explanation": str,        # 可选，题目答案解析（LLM生成）
                }
            }
        """
        correct_answer = question_data.get("answer", "")
        # ★★★ 兼容 LLM 偶尔把 answer 生成为数组的情况 ★★★
        if isinstance(correct_answer, list):
            correct_answer = ",".join(str(a).strip() for a in correct_answer)
        correct_answer = str(correct_answer).strip()
        user_answer = str(user_answer).strip()

        # ★★★ 标准化辅助函数 ★★★
        def _norm(s: str) -> str:
            """去除空白、全角转半角、统一小写"""
            s = s.replace(" ", "").replace("\u3000", "").replace("\xa0", "")
            result = []
            for c in s:
                code = ord(c)
                if 0xFF01 <= code <= 0xFF5E:
                    result.append(chr(code - 0xFEE0))
                else:
                    result.append(c)
            return "".join(result).lower()

        def _strip_letter_prefix(s: str) -> str:
            """去除选项前的字母前缀：'A. xxx' → 'xxx'
            注意：纯字母（如 "A"）不会被剥掉，避免降级时误剥正确答案标签
            """
            # 如果剥掉后还有内容才剥，否则保留原样（避免 "A" → ""）
            stripped = re.sub(r'^[a-d][.、)\s\u3000\u00a0]+', '', s, flags=re.IGNORECASE).strip()
            return stripped if stripped else s.strip()

        def _resolve_answer_via_options(
            target: str,
            options: List[str],
            resolve_to: str = "letter"
        ) -> List[str]:
            """通过 options 列表解析目标值对应的可能取值，
            resolve_to="letter" → 返回目标值对应的选项字母（如 "A"）
            resolve_to="content" → 返回目标值对应的选项内容（如 "变量"）
            """
            results = []
            if not options:
                return results
            target_norm = _norm(target)
            for i, opt in enumerate(options):
                opt_letter = chr(65 + i)  # A, B, C, D...
                opt_content = _norm(_strip_letter_prefix(opt))
                if target_norm == _norm(opt_letter) or target_norm == opt_content:
                    if resolve_to == "letter":
                        results.append(opt_letter)
                    else:
                        results.append(opt_content)
            return results

        # 单选题：按索引字母比较 + 文本降级
        if question_type == "single_choice":
            user_norm = _norm(user_answer)
            correct_norm = _norm(correct_answer)
            # 精确匹配（最严格）
            is_correct = user_norm == correct_norm
            if not is_correct:
                # 降级1：去除字母前缀后比较（answer="A", user="A. xxx" or vice versa）
                user_stripped = _norm(_strip_letter_prefix(user_answer))
                correct_stripped = _norm(_strip_letter_prefix(correct_answer))
                is_correct = user_stripped == correct_stripped
            if not is_correct:
                # 降级2：用户提交的是完整字母，answer存的是文本（或反之）
                # 例如 user="A" answer="A. 变量" → 都去前缀比较
                if len(user_norm) == 1 and 'a' <= user_norm <= 'd':
                    # user选了字母，把correct也转字母（取首字母）
                    correct_first = correct_norm[0] if correct_norm else ''
                    is_correct = user_norm == correct_first
                elif len(correct_norm) == 1 and 'a' <= correct_norm <= 'd':
                    user_first = user_norm[0] if user_norm else ''
                    is_correct = user_first == correct_norm
            if not is_correct:
                # 降级3：通过 options 列表匹配内容 ↔ 字母
                # 场景：correct_answer="A", user_answer="变量"(选项A的内容文本)
                # 或者 correct_answer="变量"(选项A的内容), user_answer="A"
                options = question_data.get("options", [])
                if options:
                    # 尝试把 correct_answer 转成字母后再与 user_norm 比较
                    correct_letters = _resolve_answer_via_options(correct_answer, options, "letter")
                    if correct_letters and _norm(correct_letters[0]) == user_norm:
                        is_correct = True
                    if not is_correct:
                        # 尝试把 user_answer 转成字母后再与 correct_norm 比较
                        user_letters = _resolve_answer_via_options(user_answer, options, "letter")
                        if user_letters and _norm(user_letters[0]) == correct_norm:
                            is_correct = True
                    if not is_correct:
                        # 尝试把 correct_answer 转成内容文本后再与 user_norm 比较
                        correct_contents = _resolve_answer_via_options(correct_answer, options, "content")
                        if correct_contents and _norm(correct_contents[0]) == user_norm:
                            is_correct = True
                    if not is_correct:
                        # 尝试把 user_answer 转成内容文本后再与 correct_norm 比较
                        user_contents = _resolve_answer_via_options(user_answer, options, "content")
                        if user_contents and _norm(user_contents[0]) == correct_norm:
                            is_correct = True

        # 判断题：统一标准化后比较
        elif question_type == "judge":
            # 先用 _norm 做基础标准化（去空格、全角转半角）
            correct_base = _norm(correct_answer)
            user_base = _norm(user_answer)

            # 标准化正确答案
            if correct_base in ("正确", "对", "true", "t", "✓", "✅", "1", "是"):
                correct_norm = "正确"
            elif correct_base in ("错误", "错", "false", "f", "✗", "❌", "0", "否", "不是"):
                correct_norm = "错误"
            else:
                correct_norm = correct_base

            # 标准化用户答案
            if user_base in ("正确", "对", "true", "t", "✓", "✅", "1", "是"):
                user_norm = "正确"
            elif user_base in ("错误", "错", "false", "f", "✗", "❌", "0", "否", "不是"):
                user_norm = "错误"
            else:
                user_norm = user_base

            is_correct = user_norm == correct_norm

        # 多选题：按分隔符拆分后无序比较
        elif question_type == "multiple_choice":
            user_set = {a.strip().upper() for a in user_answer.replace("，", ",").split(",") if a.strip()}
            correct_set = {a.strip().upper() for a in correct_answer.replace("，", ",").split(",") if a.strip()}
            is_correct = user_set == correct_set
            if not is_correct:
                # 降级：通过 options 列表解析内容 ↔ 字母的匹配
                options = question_data.get("options", [])
                if options:
                    resolved_user = set()
                    for ua in user_set:
                        matched = _resolve_answer_via_options(ua, options, "letter")
                        if matched:
                            resolved_user.update(m.upper() for m in matched)
                        else:
                            resolved_user.add(ua)
                    resolved_correct = set()
                    for ca in correct_set:
                        matched = _resolve_answer_via_options(ca, options, "letter")
                        if matched:
                            resolved_correct.update(m.upper() for m in matched)
                        else:
                            resolved_correct.add(ca)
                    is_correct = resolved_user == resolved_correct

        # 填空题/简答题：去除空白后比较
        elif question_type in ("fill_blank", "short_answer"):
            is_correct = _norm(user_answer) == _norm(correct_answer)

        # 兜底：直接比较
        else:
            is_correct = _norm(user_answer) == _norm(correct_answer)

        # 构建分析
        analysis = {}
        explanation = question_data.get("explanation", "")

        if is_correct:
            analysis["correctness"] = f"回答正确！你的答案「{user_answer}」与标准答案一致。"
        else:
            analysis["correctness"] = f"回答错误。你的答案是「{user_answer}」，正确答案是「{correct_answer}」。"
            # 对不同题型给出具体分析
            if question_type in ("single_choice", "multiple_choice", "judge"):
                analysis["hint"] = "请仔细阅读题目和选项，理解每个选项的含义后再作答。"
            elif question_type == "fill_blank":
                analysis["hint"] = "注意关键词和核心概念，确保答案的准确性。"
            elif question_type == "short_answer":
                analysis["hint"] = "简答题需要准确表述核心概念，可以参考标准答案的关键要点。"

        if explanation:
            analysis["explanation"] = explanation

        return {
            "is_correct": is_correct,
            "score": 100 if is_correct else 0,
            "correct_answer": correct_answer,
            "user_answer": user_answer,
            "question_type": question_type,
            "analysis": analysis,
        }

    async def update_features_after_practice(
        self,
        student_features: Dict[str, Any],
        practice_data: Dict[str, Any],
        question_info: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        根据练习题作答行为动态更新学生特征（异步版本）
        
        Args:
            student_features: 当前学生特征（如果不提供且有user_id，会从中央管理器获取）
            practice_data: 练习行为数据
                - total_questions: 总题数
                - correct_count: 正确数量
                - accuracy_rate: 正确率 (0-1)
                - time_per_question: 平均每题用时
                - difficulty_level: 题目难度 (easy/medium/hard)
                - question_types: 题型分布
                - weak_points_found: 发现的薄弱点列表
            question_info: 题目信息（可选）
            user_id: 用户ID（如果提供，会自动保存更新后的特征到中央管理器）
            
        Returns:
            Dict: 更新后的特征数据
        """
        try:
            # ★★★ 关键：如果没有提供student_features但有user_id，从中央管理器获取 ★★★
            if student_features is None and user_id:
                student_features = await self.feature_updater.get_latest_features_async(user_id)
                if student_features:
                    print(f"📖 [题目生成Agent] 从中央管理器获取了用户 {user_id} 的最新特征")
            
            if not student_features:
                print("⚠️ [题目生成Agent] 没有学生特征数据，跳过更新")
                return {
                    "status": "skipped",
                    "message": "没有学生特征数据"
                }
            
            # 构建性能数据
            performance_data = {
                "total_questions": practice_data.get('total_questions', 0),
                "correct_count": practice_data.get('correct_count', 0),
                "accuracy_rate": practice_data.get('accuracy_rate', 0),
                "time_per_question": practice_data.get('time_per_question', ''),
                "difficulty_level": practice_data.get('difficulty_level', 'medium'),
                "question_types": practice_data.get('question_types', []),
                "weak_points_found": practice_data.get('weak_points_found', [])
            }
            
            if question_info:
                performance_data['course_name'] = question_info.get('course_name', '')
                performance_data['knowledge_point'] = question_info.get('knowledge_point', '')
            
            # 评估完成质量
            accuracy = practice_data.get('accuracy_rate', 0)
            
            if accuracy >= 0.85:
                completion_quality = "high"
            elif accuracy >= 0.6:
                completion_quality = "medium"
            else:
                completion_quality = "low"
            
            # ★★★ 后台异步更新特征，不阻塞资源返回 ★★★
            asyncio.create_task(
                self.feature_updater.update_features_async(
                    current_features=student_features,
                    task_type="practice",
                    task_content=f"练习题：{question_info.get('knowledge_point', '') if question_info else '未知'}",
                    performance_data=performance_data,
                    completion_quality=completion_quality,
                    time_spent=practice_data.get('time_per_question', ''),
                    user_id=user_id
                )
            )
            
            print(f"🔄 [题目生成Agent] 特征更新已触发（后台）")
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