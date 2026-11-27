"""
盘问评估Agent - 基于场景应用题的多轮盘问，评估用户对知识点的掌握程度

核心功能：
1. 基于指定知识点，自动生成场景应用题（每次1题）
2. 多轮盘问（至少3轮）：每轮根据用户回答动态调整下一题
3. LLM评估用户回答：判断是否正确、理解是否深入
4. 综合评估：最终给出"已掌握"/"基本掌握"/"不了解"的结论
5. 提供可视化数据：预期掌握度 vs 实际掌握度的对比数据

设计理念：
- 场景应用题式：将知识点融入实际场景，考察应用能力
- 自适应追问：根据前一轮回答动态调整难度和方向
- 多维度评估：从概念理解、应用能力、边缘情况三个维度打分
"""

import os
import re
import json
import uuid
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from utils.async_llm_caller import call_llm_with_retry
from utils.llm_config import get_chat_openai

# 支持直接运行和包导入两种方式
try:
    from memory.knowledge_mastery import KnowledgeMasteryGraph, MASTERY_LABELS
except ImportError:
    from knowledge_mastery import KnowledgeMasteryGraph, MASTERY_LABELS


# ==================== 评估等级 ====================

ASSESSMENT_LABELS = {
    "mastered": "已掌握",
    "basically_mastered": "基本掌握",
    "not_understood": "不了解",
}

ASSESSMENT_SCORES = {
    "mastered": 85,
    "basically_mastered": 60,
    "not_understood": 30,
}


# ==================== 盘问会话存储 ====================

class InterrogationSession:
    """盘问会话 - 管理单次盘问的全部状态"""

    def __init__(self, session_id: str, user_id: str, knowledge_point: str):
        self.session_id = session_id
        self.user_id = user_id
        self.knowledge_point = knowledge_point
        self.rounds: List[Dict[str, Any]] = []  # 每轮对话记录
        self.current_round = 0
        self.max_rounds = 4  # 至少3轮+1次最终评估
        self.status = "active"  # active / completed
        self.final_assessment: Optional[Dict[str, Any]] = None
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "knowledge_point": self.knowledge_point,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "status": self.status,
            "rounds": self.rounds,
            "final_assessment": self.final_assessment,
            "created_at": self.created_at,
        }


# ==================== 全局会话管理 ====================

# 内存存储，每个盘问会话一个实例（短生命周期，重启丢失可接受）
_sessions: Dict[str, InterrogationSession] = {}


def get_session(session_id: str) -> Optional[InterrogationSession]:
    return _sessions.get(session_id)


def create_session(user_id: str, knowledge_point: str) -> InterrogationSession:
    session_id = f"iq_{uuid.uuid4().hex[:12]}"
    session = InterrogationSession(session_id, user_id, knowledge_point)
    _sessions[session_id] = session
    return session


# ==================== 盘问结果持久化存储 ====================

_RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "interrogation_data")


def _get_results_path(user_id: str) -> str:
    """获取用户盘问结果文件路径"""
    os.makedirs(_RESULTS_DIR, exist_ok=True)
    return os.path.join(_RESULTS_DIR, f"results_{user_id}.json")


def _load_user_results(user_id: str) -> Dict[str, Any]:
    """加载用户所有盘问结果"""
    path = _get_results_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return {}
    return {}


def _save_user_results(user_id: str, data: Dict[str, Any]):
    """保存用户盘问结果"""
    path = _get_results_path(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_interrogation_result(user_id: str, knowledge_point: str, result: Dict[str, Any]):
    """持久化存储盘问结果（自动按分数矫正 verdict）"""
    score = result.get("overall_score", 0)
    raw_verdict = result.get("verdict", "not_understood")

    # ★★★ 按分数矫正 verdict（LLM可能不严格遵循prompt）★★★
    if score >= 75:
        final_verdict = "mastered"
    elif score >= 50:
        final_verdict = "basically_mastered"
    else:
        final_verdict = "not_understood"

    data = _load_user_results(user_id)
    data[knowledge_point] = {
        "verdict": final_verdict,
        "verdict_label": ASSESSMENT_LABELS.get(final_verdict, "未知"),
        "overall_score": score,
        "summary": result.get("summary", ""),
        "dimensions": result.get("dimensions", {}),
        "interrogated_at": datetime.now().isoformat(),
    }
    _save_user_results(user_id, data)


def get_interrogation_results(user_id: str) -> Dict[str, Any]:
    """获取用户所有知识点盘问结果"""
    return _load_user_results(user_id)


# ==================== 盘问Agent ====================

class QuizInterrogationAgent:
    """
    盘问评估Agent

    工作流程：
    1. start() → 生成第1题 + 返回给用户
    2. submit_answer() → 评估答案 → 生成下一题（共至少3轮）
    3. 第3轮后 → 综合评估 → 返回最终结果
    """

    def __init__(self):
        self.llm = self._initialize_llm()
        self.knowledge_mastery = KnowledgeMasteryGraph()

    def _initialize_llm(self):
        """初始化LangChain LLM"""
        return get_chat_openai(temperature=0.5, max_tokens=2048, streaming=False)

    # ==================== 核心公共方法 ====================

    async def start_interrogation(self, user_id: str, knowledge_point: str) -> Dict[str, Any]:
        """
        开始一个新的盘问会话

        Returns:
            {session_id, knowledge_point, round_number, question, question_scenario}
        """
        # 获取该知识点的已有掌握信息
        mastery_info = self.knowledge_mastery.get_mastery(user_id, knowledge_point)

        session = create_session(user_id, knowledge_point)

        # 生成第1轮问题
        question_data = await self._generate_question(
            session=session,
            round_num=1,
            mastery_info=mastery_info,
            history=[],
        )

        session.rounds.append({
            "round": 1,
            "type": "question",
            "content": question_data,
            "timestamp": datetime.now().isoformat(),
        })
        session.current_round = 1

        # ★★★ 如果有配图需求，异步生成图片 ★★★
        image_url = None
        if question_data.get("needs_image"):
            image_url = await self._generate_image(
                knowledge_point, question_data.get("scenario", ""), question_data["question"]
            )

        # 从错题数据获取预期掌握度的基础信息
        expected_data = self._get_expected_mastery(user_id, knowledge_point)

        return {
            "session_id": session.session_id,
            "knowledge_point": knowledge_point,
            "round_number": 1,
            "total_rounds": session.max_rounds,
            "question": question_data["question"],
            "scenario": question_data.get("scenario", ""),
            "hint": question_data.get("hint", ""),
            "image_url": image_url,
            "expected_data": expected_data,
        }

    async def submit_answer(self, session_id: str, user_answer: str) -> Dict[str, Any]:
        """
        提交用户答案，获取评估和下一轮问题

        Args:
            session_id: 会话ID
            user_answer: 用户答案

        Returns:
            {
                session_id, knowledge_point,
                is_final: bool,
                round_number: int,
                evaluation: {score, verdict, feedback, strengths, weaknesses},
                next_question: str (if not final),
                next_scenario: str (if not final),
                result: Dict (if final)
            }
        """
        session = get_session(session_id)
        if not session:
            return {"error": "会话不存在", "session_id": session_id}
        if session.status == "completed":
            return {"error": "会话已结束", "session_id": session_id, "result": session.final_assessment}

        # 评估当前回答
        evaluation = await self._evaluate_answer(
            session=session,
            user_answer=user_answer,
            current_round=session.current_round,
        )

        # 记录本轮完整信息
        session.rounds.append({
            "round": session.current_round,
            "type": "answer",
            "user_answer": user_answer,
            "evaluation": evaluation,
            "timestamp": datetime.now().isoformat(),
        })

        # 判断是否还需要继续盘问
        if session.current_round >= session.max_rounds - 1:  # 第3轮或之后
            # 进行最终评估
            final_assessment = await self._final_evaluation(session)
            session.final_assessment = final_assessment
            session.status = "completed"

            # 持久化存储盘问结果
            try:
                save_interrogation_result(session.user_id, session.knowledge_point, final_assessment)
                print(f"  💾 [盘问Agent] 已保存盘问结果: {session.knowledge_point} -> {final_assessment['verdict']}")
            except Exception as e:
                print(f"  ⚠️ [盘问Agent] 保存结果失败: {e}")

            # 记录学习活动到知识图谱
            try:
                is_understood = final_assessment["verdict"] in ("mastered", "basically_mastered")
                self.knowledge_mastery.record_activity(
                    user_id=session.user_id,
                    knowledge_point=session.knowledge_point,
                    correct=is_understood,
                    activity_type="review",
                    difficulty="中等",
                )
            except Exception as e:
                print(f"  ⚠️ [盘问Agent] 记录学习活动失败: {e}")

            # 准备可视化数据
            visualization_data = self._build_visualization_data(session, final_assessment)

            return {
                "session_id": session.session_id,
                "knowledge_point": session.knowledge_point,
                "is_final": True,
                "round_number": session.current_round,
                "evaluation": {
                    "score": evaluation["score"],
                    "verdict": evaluation["verdict"],
                    "feedback": evaluation["feedback"],
                    "strengths": evaluation.get("strengths", []),
                    "weaknesses": evaluation.get("weaknesses", []),
                },
                "result": {
                    "verdict": final_assessment["verdict"],
                    "verdict_label": ASSESSMENT_LABELS.get(final_assessment["verdict"], "未知"),
                    "overall_score": final_assessment["overall_score"],
                    "summary": final_assessment["summary"],
                    "dimensions": final_assessment["dimensions"],
                    "improvement_suggestions": final_assessment.get("improvement_suggestions", []),
                },
                "visualization_data": visualization_data,
            }

        # 生成下一轮问题
        next_round = session.current_round + 1
        mastery_info = self.knowledge_mastery.get_mastery(session.user_id, session.knowledge_point)
        history = [
            {"round": session.rounds[i]["round"], "question": session.rounds[i]["content"]["question"],
             "answer": session.rounds[i+1]["user_answer"],
             "evaluation": session.rounds[i+1]["evaluation"]}
            for i in range(0, len(session.rounds), 2)
            if i+1 < len(session.rounds)
        ]

        question_data = await self._generate_question(
            session=session,
            round_num=next_round,
            mastery_info=mastery_info,
            history=history,
        )

        session.rounds.append({
            "round": next_round,
            "type": "question",
            "content": question_data,
            "timestamp": datetime.now().isoformat(),
        })
        session.current_round = next_round

        # ★★★ 如果有配图需求，异步生成图片 ★★★
        next_image_url = None
        if question_data.get("needs_image"):
            next_image_url = await self._generate_image(
                session.knowledge_point, question_data.get("scenario", ""), question_data["question"]
            )

        return {
            "session_id": session.session_id,
            "knowledge_point": session.knowledge_point,
            "is_final": False,
            "round_number": next_round,
            "total_rounds": session.max_rounds,
            "evaluation": {
                "score": evaluation["score"],
                "verdict": evaluation["verdict"],
                "feedback": evaluation["feedback"],
                "strengths": evaluation.get("strengths", []),
                "weaknesses": evaluation.get("weaknesses", []),
            },
            "next_question": question_data["question"],
            "next_scenario": question_data.get("scenario", ""),
            "next_hint": question_data.get("hint", ""),
            "next_image_url": next_image_url,
        }

    async def get_result(self, session_id: str) -> Dict[str, Any]:
        """获取已完成的盘问结果"""
        session = get_session(session_id)
        if not session:
            return {"error": "会话不存在"}
        if session.status != "completed" or not session.final_assessment:
            return {"error": "会话尚未完成", "session_id": session_id}

        visualization_data = self._build_visualization_data(session, session.final_assessment)

        return {
            "session_id": session.session_id,
            "knowledge_point": session.knowledge_point,
            "result": {
                "verdict": session.final_assessment["verdict"],
                "verdict_label": ASSESSMENT_LABELS.get(session.final_assessment["verdict"], "未知"),
                "overall_score": session.final_assessment["overall_score"],
                "summary": session.final_assessment["summary"],
                "dimensions": session.final_assessment["dimensions"],
                "improvement_suggestions": session.final_assessment.get("improvement_suggestions", []),
            },
            "rounds": [
                {"round": r["round"], "type": r["type"],
                 "content": r.get("content", {}).get("question", "") if r["type"] == "question" else r.get("user_answer", ""),
                 "evaluation": r.get("evaluation")}
                for r in session.rounds
            ],
            "visualization_data": visualization_data,
        }

    # ==================== LLM Prompt 方法 ====================

    async def _generate_question(self, session: InterrogationSession, round_num: int,
                                  mastery_info: Dict[str, Any],
                                  history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成场景应用题

        Args:
            session: 会话对象
            round_num: 第几轮
            mastery_info: 当前掌握度信息
            history: 历史问答记录（用于后续轮的针对性提问）

        Returns:
            {question, scenario, hint}
        """
        knowledge_point = session.knowledge_point
        mastery_label = mastery_info.get("mastery_label", "未接触")
        mastery_level = mastery_info.get("mastery_level", 0)
        total_practiced = mastery_info.get("total_practiced", 0)
        correct_rate = (mastery_info.get("total_correct", 0) / max(total_practiced, 1)) * 100

        history_text = ""
        if history:
            history_lines = []
            for h in history:
                ev = h.get("evaluation", {})
                history_lines.append(
                    f"第{h['round']}轮: 问题「{h['question']}」, "
                    f"用户回答: 「{h['answer'][:200]}」, "
                    f"评估: {ev.get('score', 0)}分, {ev.get('feedback', '')}"
                )
            history_text = "\n".join(history_lines)

        difficulty_guide = ""
        if round_num == 1:
            difficulty_guide = "第1轮: 出中等难度场景题，考察基础应用能力"
        elif round_num == 2:
            difficulty_guide = "第2轮（基于第1轮表现）: 如果第1轮答得好则加深难度，否则巩固基础"
        else:
            difficulty_guide = "第3轮+: 出较有深度的复合场景题，考察综合应用和边缘情况处理"

        prompt = f"""
你是专业的知识点盘问智能体，需要针对指定知识点出一道【场景应用题】。

=== 知识点信息 ===
知识点: {knowledge_point}
用户当前掌握等级: {mastery_label}({mastery_level}/4)
总练习次数: {total_practiced}，正确率: {correct_rate:.1f}%

=== 出题轮次 ===
当前是第 {round_num} 轮盘问
{difficulty_guide}

=== 历史问答（如果不是第1轮） ===
{history_text or "（第1轮，无历史）"}

=== 出题要求 ===
1. 将「{knowledge_point}」这个知识点融入到【实际应用场景】中出题
2. 题目要有具体的场景描述（如开发一个功能、分析一个系统问题、设计一个方案等）
3. 问题必须是开放式的，能考察用户的理解深度和应用能力
4. 避免简单的概念背诵或选择题
5. 第2轮起根据用户前一轮的回答情况动态调整方向和难度
6. 题目要引导用户展示出对知识点的真实理解水平

=== 输出格式（严格JSON，无多余内容） ===
{{
  "scenario": "场景描述（50-100字，描述业务背景和上下文）",
  "question": "具体问题（30-80字，清晰明确的提问）",
  "hint": "思考提示（10-30字，给用户的思考方向，不要透露答案）",
  "needs_image": true 或 false   /* 此题配一张说明图是否有助于用户理解？如算法流程、数据结构、对比图等可配 */
}}
"""

        try:
            result_text = await call_llm_with_retry(
                llm=self.llm,
                prompt=prompt,
                max_retries=2,
            )

            content = result_text.content if hasattr(result_text, 'content') else str(result_text)
            # 提取JSON
            question_data = self._extract_json(content)
            if not question_data:
                # 兜底
                question_data = {
                    "scenario": f"请思考以下关于{knowledge_point}的应用场景",
                    "question": f"请结合实际开发经验，阐述你对{knowledge_point}的理解和应用方式",
                    "hint": "可以从原理、应用场景、注意事项等角度思考",
                }
            return question_data

        except Exception as e:
            print(f"  ⚠️ [盘问Agent] 生成第{round_num}轮问题失败: {e}")
            return {
                "scenario": f"让我们通过一个实际场景来考察你对{knowledge_point}的理解",
                "question": f"请用你自己的话解释什么是{knowledge_point}，并给出一个实际应用例子",
                "hint": "考虑它在什么场景下使用，解决了什么问题",
            }

    async def _generate_image(self, knowledge_point: str, scenario: str, question: str) -> Optional[str]:
        """根据知识点+场景+问题自动生成配图，上传OSS持久化，返回OSS URL"""
        prompt_text = (
            f"Educational illustration for the concept '{knowledge_point}'. "
            f"Scene: {scenario[:100]}. "
            f"Question: {question[:100]}. "
            f"Clean, professional diagram style, suitable for computer science education, "
            f"with clear labels and visual elements. No text overlay in Chinese."
        )
        try:
            from dashscope import ImageSynthesis
            # 读取最新的 API key
            _api_key = os.getenv("DASHSCOPE_API_KEY", "sk-ws-H.EHEXPER.yUFF.MEYCIQD5dksUxv1hLfiF5kqi_LKN2WLrHmUUQXfPLKBdmJnoFwIhAIHSxUX4b71Lpa56Vu2J6ad_M9Kx4-TAD4_UbxbmFrSy")
            rsp = await asyncio.to_thread(
                ImageSynthesis.call,
                api_key=_api_key,
                model="wanx2.1-t2i-plus",
                prompt=prompt_text.strip(),
                n=1,
                size="1280*720",
            )
            if rsp and rsp.status_code == 200 and rsp.output.results:
                image_url = rsp.output.results[0].url
                print(f"  🖼️ [盘问Agent] 配图生成成功: {image_url}")

                # ★★★ 下载到本地并上传 OSS 持久化 ★★★
                import tempfile, requests as sync_req
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    img_data = sync_req.get(image_url).content
                    tmp.write(img_data)
                    local_path = tmp.name

                try:
                    from services.oss_storage import upload_file
                    cfg_bucket = "all-tame-max-oss"
                    cfg_endpoint = "oss-cn-beijing.aliyuncs.com"
                    obj_key = upload_file(local_path, "agent", "interrogation_img", f"{knowledge_point}.png")
                    if obj_key:
                        oss_url = f"https://{cfg_bucket}.{cfg_endpoint}/{obj_key}"
                        print(f"  ✅ [盘问Agent] 配图已上传OSS: {oss_url}")
                        return oss_url
                except Exception as e:
                    print(f"  ⚠️ [盘问Agent] OSS上传失败，使用原始URL: {e}")
                finally:
                    try:
                        os.unlink(local_path)
                    except Exception:
                        pass

                return image_url  # OSS 上传失败时兜底返回原始 URL
            else:
                print(f"  ⚠️ [盘问Agent] 配图生成失败: {rsp}")
                return None
        except ImportError as e:
            print(f"  ⚠️ [盘问Agent] 图片生成依赖缺失: {e}")
            return None
        except Exception as e:
            print(f"  ⚠️ [盘问Agent] 图片生成异常: {e}")
            return None

    async def _evaluate_answer(self, session: InterrogationSession, user_answer: str,
                                current_round: int) -> Dict[str, Any]:
        """
        评估用户的回答

        Returns:
            {score: 0-100, verdict: "correct"/"partially_correct"/"incorrect",
             feedback: str, strengths: [], weaknesses: []}
        """
        knowledge_point = session.knowledge_point

        # 找到本轮的问题
        question_record = None
        for r in session.rounds:
            if r["round"] == current_round and r["type"] == "question":
                question_record = r["content"]
                break

        question_text = question_record.get("question", "") if question_record else ""
        scenario_text = question_record.get("scenario", "") if question_record else ""

        prompt = f"""
你是严格的盘问评估专家，需要评估用户对知识点的理解程度。

=== 知识点 ===
{knowledge_point}

=== 本轮场景题 ===
场景: {scenario_text}
问题: {question_text}

=== 用户回答 ===
{user_answer[:1000]}

=== 评估要求 ===
1. 判断用户的理解是否正确、深入
2. 从以下维度评分：
   - 概念正确性：核心概念表述是否正确
   - 应用能力：是否能正确应用到场景中
   - 思考深度：是否有深入的分析和思考
3. 给出0-100的综合得分
4. 指出用户的亮点和不足
5. 给出简短的建设性反馈

=== 输出格式（严格JSON，无多余内容） ===
{{
  "score": <0-100整数>,
  "verdict": "correct" 或 "partially_correct" 或 "incorrect",
  "feedback": "简短反馈（30-60字）",
  "strengths": ["亮点1", "亮点2"],
  "weaknesses": ["不足1", "不足2"]
}}

评分标准：
- correct (>=70): 理解正确，能应用，思路清晰
- partially_correct (40-69): 基本理解但有偏差或不够深入
- incorrect (<40): 明显误解或完全不会
"""

        try:
            result_text = await call_llm_with_retry(
                llm=self.llm,
                prompt=prompt,
                max_retries=2,
            )

            content = result_text.content if hasattr(result_text, 'content') else str(result_text)
            evaluation = self._extract_json(content)
            if not evaluation:
                evaluation = {"score": 50, "verdict": "partially_correct",
                              "feedback": "无法准确评估，请继续下一轮", "strengths": [], "weaknesses": []}
            return evaluation

        except Exception as e:
            print(f"  ⚠️ [盘问Agent] 评估第{current_round}轮回答失败: {e}")
            return {"score": 50, "verdict": "partially_correct",
                    "feedback": "评估异常，请继续作答", "strengths": [], "weaknesses": []}

    async def _final_evaluation(self, session: InterrogationSession) -> Dict[str, Any]:
        """
        综合所有轮次的回答，给出最终评估

        Returns:
            {verdict, overall_score, summary, dimensions, improvement_suggestions}
        """
        knowledge_point = session.knowledge_point
        round_summaries = []

        # 整理各轮次信息
        i = 0
        while i < len(session.rounds):
            r = session.rounds[i]
            if r["type"] == "question":
                question_content = r["content"].get("question", "")
                if i + 1 < len(session.rounds) and session.rounds[i + 1]["type"] == "answer":
                    answer = session.rounds[i + 1]
                    ev = answer.get("evaluation", {})
                    round_summaries.append(
                        f"第{r['round']}轮: 问题「{question_content}」\n"
                        f"用户答: 「{answer.get('user_answer', '')[:200]}」\n"
                        f"评估: {ev.get('score', 0)}分, 评语: {ev.get('feedback', '')}"
                    )
            i += 1

        rounds_text = "\n\n".join(round_summaries)

        prompt = f"""
你是严格的盘问评估专家，需要根据多轮盘问记录，对用户的知识点掌握情况进行最终综合评估。

=== 评估知识点 ===
{knowledge_point}

=== 多轮盘问记录 ===
{rounds_text}

=== 评估要求 ===
1. 综合所有轮次的表现进行判断
2. 评估以下三个维度并分别打分（0-100）：
   - concept_understanding: 概念理解是否正确、完整
   - application_ability: 应用能力如何，能否将知识运用到实际场景
   - depth_of_thinking: 思考深度，是否能举一反三、考虑边界情况
3. 给出综合评估结论
4. 如果用户还有不足，给出针对性的提升建议

=== 输出格式（严格JSON，无多余内容） ===
{{
  "verdict": "mastered" 或 "basically_mastered" 或 "not_understood",
  "overall_score": <0-100整数>,
  "summary": "综合总结（50-100字）",
  "dimensions": {{
    "concept_understanding": <0-100>,
    "application_ability": <0-100>,
    "depth_of_thinking": <0-100>
  }},
  "improvement_suggestions": ["建议1", "建议2", "建议3"]
}}

评估标准：
- mastered (>=75): 概念清晰，应用熟练，思考深入，可以举一反三
- basically_mastered (50-74): 基本掌握核心概念，能应用但不够深入，偶尔有偏差
- not_understood (<50): 概念模糊，无法正确应用，存在明显理解偏差
"""

        try:
            result_text = await call_llm_with_retry(
                llm=self.llm,
                prompt=prompt,
                max_retries=2,
            )

            content = result_text.content if hasattr(result_text, 'content') else str(result_text)
            assessment = self._extract_json(content)
            if not assessment:
                assessment = {
                    "verdict": "basically_mastered",
                    "overall_score": 60,
                    "summary": "评估异常，基于现有数据给出保守评估",
                    "dimensions": {"concept_understanding": 60, "application_ability": 60, "depth_of_thinking": 50},
                    "improvement_suggestions": ["建议重新评估"],
                }
            return assessment

        except Exception as e:
            print(f"  ⚠️ [盘问Agent] 最终评估失败: {e}")
            return {
                "verdict": "basically_mastered",
                "overall_score": 60,
                "summary": "系统评估异常，基于现有数据给出保守评估",
                "dimensions": {"concept_understanding": 60, "application_ability": 60, "depth_of_thinking": 50},
                "improvement_suggestions": ["建议重新进行一次盘问评估"],
            }

    # ==================== 辅助方法 ====================

    def _get_expected_mastery(self, user_id: str, knowledge_point: str) -> Dict[str, Any]:
        """获取预期掌握度数据（基于历史数据）"""
        mastery = self.knowledge_mastery.get_mastery(user_id, knowledge_point)
        return {
            "mastery_level": mastery.get("mastery_level", 0),
            "mastery_label": mastery.get("mastery_label", "未接触"),
            "mastery_points": mastery.get("mastery_points", 0.0),
            "total_practiced": mastery.get("total_practiced", 0),
            "total_correct": mastery.get("total_correct", 0),
            "correct_rate": (mastery.get("total_correct", 0) / max(mastery.get("total_practiced", 0), 1)) * 100,
        }

    def _build_visualization_data(self, session: InterrogationSession,
                                   assessment: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建可视化对比数据

        - 预期掌握度: 基于历史数据（错题次数、之前得分、掌握度等级）
        - 实际掌握度: 基于盘问评估结果

        Returns:
            {expected, actual, dimensions, radar_data, bar_data}
        """
        expected = self._get_expected_mastery(session.user_id, session.knowledge_point)
        dimensions = assessment.get("dimensions", {})

        # 计算预期各维度分数（从历史数据推算）
        mastery_level = expected.get("mastery_level", 0)
        correct_rate = expected.get("correct_rate", 0)

        # 预期维度分：基于 mastery_level 和 correct_rate 估算
        base_expected = min(mastery_level * 25, 100)
        expected_concept = min(base_expected + correct_rate * 0.2, 100)
        expected_application = min(base_expected * 0.8 + correct_rate * 0.15, 100)
        expected_depth = min(base_expected * 0.6 + correct_rate * 0.1, 100)

        # 实际维度分
        actual_concept = dimensions.get("concept_understanding", 50)
        actual_application = dimensions.get("application_ability", 50)
        actual_depth = dimensions.get("depth_of_thinking", 50)

        # 柱状图数据
        bar_data = {
            "categories": ["综合掌握度"],
            "expected": [expected.get("mastery_level", 0) * 25],
            "actual": [assessment.get("overall_score", 50)],
        }

        # 雷达图数据
        radar_data = {
            "indicators": [
                {"name": "概念理解", "max": 100},
                {"name": "应用能力", "max": 100},
                {"name": "思考深度", "max": 100},
            ],
            "expected": [round(expected_concept, 1), round(expected_application, 1), round(expected_depth, 1)],
            "actual": [actual_concept, actual_application, actual_depth],
        }

        return {
            "knowledge_point": session.knowledge_point,
            "expected": {
                "mastery_level": mastery_level,
                "mastery_label": expected.get("mastery_label", "未接触"),
                "correct_rate": round(correct_rate, 1),
                "overall_score": round((expected_concept + expected_application + expected_depth) / 3, 1),
            },
            "actual": {
                "verdict": assessment["verdict"],
                "verdict_label": ASSESSMENT_LABELS.get(assessment["verdict"], "未知"),
                "overall_score": assessment["overall_score"],
            },
            "bar_data": bar_data,
            "radar_data": radar_data,
        }

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """从LLM输出中提取JSON"""
        if not text:
            return None

        # 1. 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. 从代码块提取
        code_match = re.search(r'```(?:json)?\s*\n?(.*?)(?:\n?```|$)', text, re.DOTALL)
        if code_match:
            candidate = code_match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                text = candidate

        # 3. 提取最外层 {}
        brace_match = re.search(r'\{.*', text, re.DOTALL)
        if brace_match:
            candidate = brace_match.group()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        return None


# ==================== 独立运行测试 ====================

if __name__ == "__main__":
    async def test():
        agent = QuizInterrogationAgent()
        result = await agent.start_interrogation("test_user_001", "排序算法")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    asyncio.run(test())
