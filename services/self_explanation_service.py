"""
自我表述（Self-Explanation）服务 - 独立模块

核心理念：
  让用户用自己的话解释错题或知识点，比单纯做题更能暴露真实理解盲区。
  基于费曼学习法：真正掌握 = 能用简单的话讲清楚。

设计原则：
  1. 完全独立：不依赖 wrong_answer_service 的内部实现
  2. 字段隔离：不修改任何错题本现有字段
  3. 轻量存储：独立的 DB 表，只存表述内容和分析结果
  4. 可挂载：通过 record_id 与错题记录关联，但不耦合

数据流：
  用户答错 → explain_required=true → 前端弹出表述框
    → 用户写一段话解释 / 讲述思路
    → 本服务调用 LLM 分析表述质量
    → 返回：理解深度、具体盲区、针对性建议
"""

import json
import uuid
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

# ★★★ 独立的数据库，与错题本完全隔离 ★★★
DB_PATH = Path("./wrong_answer_data/self_explanations.db")


# ==================== 数据库 ====================

_conn_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = getattr(_conn_local, 'conn', None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        _conn_local.conn = conn
    return conn


_DB_INITIALIZED = False


def _init_db():
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    _DB_INITIALIZED = True
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS self_explanations (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id        TEXT NOT NULL UNIQUE,
                user_id           TEXT NOT NULL,
                record_id         TEXT NOT NULL DEFAULT '',
                question_type     TEXT NOT NULL DEFAULT '',
                question_title    TEXT DEFAULT '',
                question_content  TEXT DEFAULT '',
                correct_answer    TEXT DEFAULT '',
                user_answer       TEXT DEFAULT '',
                knowledge_points  TEXT DEFAULT '',
                status            TEXT NOT NULL DEFAULT 'pending',
                user_explanation  TEXT DEFAULT '',
                analysis_level    TEXT DEFAULT '',
                analysis_gaps     TEXT DEFAULT '',
                analysis_suggestions TEXT DEFAULT '',
                llm_raw_feedback  TEXT DEFAULT '',
                created_at        TEXT NOT NULL,
                submitted_at      TEXT,
                analyzed_at       TEXT,
                UNIQUE(session_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_se_user ON self_explanations(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_se_record ON self_explanations(record_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_se_status ON self_explanations(status)
        """)

        # ★★★ 迁移：添加 recommendation_triggered 列（标记是否已触发了推荐）★★★
        try:
            conn.execute("ALTER TABLE self_explanations ADD COLUMN recommendation_triggered INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # 列已存在则忽略

        conn.commit()


_init_db()


# ==================== LLM 分析提示词 ====================

EXPLANATION_ANALYSIS_PROMPT = """你是一位资深的学习诊断专家。你的任务是分析学生对自己错误的解释，判断他们的理解深度。

## 背景

题目内容：
{question_content}

正确答案：
{correct_answer}

学生的错误答案：
{user_answer}

相关知识点：
{knowledge_points}

## 学生的自我解释

{user_explanation}

## 分析要求

请从以下维度进行分析：

1. **理解深度 (analysis_level)**：
   - `deep_understanding`：学生能准确识别错误原因，清晰阐述正确逻辑，表述完整
   - `surface_understanding`：学生大概知道错在哪，但表述模糊、不完整、避重就轻
   - `misunderstanding`：学生的解释本身就存在概念错误或逻辑错误
   - `no_understanding`：学生说不清为什么错，或回避解释

2. **具体盲区 (analysis_gaps)**：学生理解中的具体缺口或错误概念（列出1-3点）

3. **针对性建议 (analysis_suggestions)**：基于盲区，给出下一步学习建议（列出1-2条）

## 输出格式

严格以 JSON 格式输出，不要包含其他内容：
{{
    "analysis_level": "deep_understanding | surface_understanding | misunderstanding | no_understanding",
    "analysis_gaps": ["盲区1（具体）", "盲区2（具体）"],
    "analysis_suggestions": ["建议1", "建议2"],
    "summary": "一段简要的总结评语"
}}
"""


# ==================== 服务类 ====================

class SelfExplanationService:
    """自我表述服务 - 完全独立模块"""

    @staticmethod
    def _generate_session_id() -> str:
        return f"se_{uuid.uuid4().hex[:12]}"

    def start_session(
        self,
        user_id: str,
        record_id: str = "",
        question_type: str = "",
        question_title: str = "",
        question_content: str = "",
        correct_answer: str = "",
        user_answer: str = "",
        knowledge_points: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        创建一次自我表述会话

        Args:
            user_id: 用户ID
            record_id: 错题记录ID（与错题本关联，但不修改错题本字段）
            question_type: 题目类型
            question_title: 题目标题
            question_content: 题目内容/描述
            correct_answer: 正确答案
            user_answer: 用户的错误答案
            knowledge_points: 相关知识点

        Returns:
            {"session_id": str, "status": "pending"}
        """
        session_id = self._generate_session_id()
        now = datetime.now().isoformat()
        kp_str = ",".join(knowledge_points) if knowledge_points else ""

        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO self_explanations
                    (session_id, user_id, record_id, question_type,
                     question_title, question_content, correct_answer,
                     user_answer, knowledge_points, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (
                session_id, user_id, record_id, question_type,
                question_title[:200] if question_title else "",
                question_content, correct_answer,
                user_answer, kp_str, now,
            ))
            conn.commit()

        return {
            "session_id": session_id,
            "status": "pending",
            "message": "请用自己的话解释这道题为什么选错/做错，或者说说正确的思路应该是什么。",
            "prompt_hint": self._generate_prompt_hint(question_type, knowledge_points),
        }

    @staticmethod
    def _generate_prompt_hint(question_type: str, knowledge_points: Optional[List[str]]) -> str:
        """根据题目类型生成提示语"""
        kp_hint = f"（知识点：{'、'.join(knowledge_points)}）" if knowledge_points else ""
        if question_type == "programming":
            return f"你的代码在哪里出了问题？正确的解法思路是什么？能用你自己的话把逻辑理顺一遍吗？{kp_hint}"
        elif question_type in ("single_choice", "multiple_choice", "judge", "true_false"):
            return f"你为什么会选这个选项？你觉得这道题考的是什么知识点？正确的思路应该是怎样的？{kp_hint}"
        elif question_type in ("fill_blank", "short_answer"):
            return f"你觉得你漏掉了什么关键信息？正确的答案是怎么推导出来的？{kp_hint}"
        else:
            return f"你能说说你做错的原因是什么吗？正确的解法应该是怎样的？{kp_hint}"

    async def submit_explanation(
        self,
        session_id: str,
        user_id: str,
        user_explanation: str,
    ) -> Dict[str, Any]:
        """
        提交用户的自我表述，并调用 LLM 分析

        Args:
            session_id: 会话ID
            user_id: 用户ID（校验用）
            user_explanation: 用户的表述内容

        Returns:
            {
                "session_id": str,
                "status": "analyzed",
                "analysis_level": str,
                "analysis_gaps": [str],
                "analysis_suggestions": [str],
                "summary": str,
            }
        """
        now = datetime.now().isoformat()

        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM self_explanations WHERE session_id = ? AND user_id = ?",
                (session_id, user_id)
            ).fetchone()

        if not row:
            return {"error": "会话不存在", "session_id": session_id}
        if row["status"] != "pending":
            return {"error": "该会话已提交或已过期", "session_id": session_id}

        # 保存用户表述
        with _get_conn() as conn:
            conn.execute(
                "UPDATE self_explanations SET status = 'submitted', user_explanation = ?, submitted_at = ? "
                "WHERE session_id = ?",
                (user_explanation, now, session_id)
            )
            conn.commit()

        # 调用 LLM 分析
        analysis = await self._analyze_explanation(row, user_explanation)

        # 保存分析结果
        with _get_conn() as conn:
            conn.execute("""
                UPDATE self_explanations SET
                    status = 'analyzed',
                    analysis_level = ?,
                    analysis_gaps = ?,
                    analysis_suggestions = ?,
                    llm_raw_feedback = ?,
                    analyzed_at = ?
                WHERE session_id = ?
            """, (
                analysis.get("analysis_level", ""),
                json.dumps(analysis.get("analysis_gaps", []), ensure_ascii=False),
                json.dumps(analysis.get("analysis_suggestions", []), ensure_ascii=False),
                json.dumps(analysis, ensure_ascii=False),
                datetime.now().isoformat(),
                session_id,
            ))
            conn.commit()

        return {
            "session_id": session_id,
            "status": "analyzed",
            "analysis_level": analysis.get("analysis_level", ""),
            "analysis_gaps": analysis.get("analysis_gaps", []),
            "analysis_suggestions": analysis.get("analysis_suggestions", []),
            "summary": analysis.get("summary", ""),
        }

    async def _analyze_explanation(self, row: sqlite3.Row, user_explanation: str) -> Dict[str, Any]:
        """调用 LLM 分析用户的自我表述"""
        try:
            from utils.llm_config import get_chat_openai

            llm = get_chat_openai(temperature=0.3)

            prompt = EXPLANATION_ANALYSIS_PROMPT.format(
                question_content=row["question_content"] or row["question_title"] or "(未记录题目内容)",
                correct_answer=row["correct_answer"] or "(未记录)",
                user_answer=row["user_answer"] or "(未记录)",
                knowledge_points=row["knowledge_points"] or "无",
                user_explanation=user_explanation,
            )

            from utils.async_llm_caller import AsyncLLMCaller
            result = await AsyncLLMCaller.call_llm_async(llm, prompt, timeout=60)

            content = result.content if hasattr(result, 'content') else str(result)
            # 尝试解析 JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                analysis = json.loads(json_match.group())
                return {
                    "analysis_level": analysis.get("analysis_level", "no_understanding"),
                    "analysis_gaps": analysis.get("analysis_gaps", ["未能分析具体盲区"]),
                    "analysis_suggestions": analysis.get("analysis_suggestions", ["建议重新学习相关知识点"]),
                    "summary": analysis.get("summary", "分析完成"),
                }
            else:
                return {
                    "analysis_level": "surface_understanding",
                    "analysis_gaps": ["LLM 分析结果格式异常"],
                    "analysis_suggestions": ["建议查看标准答案和解析"],
                    "summary": content[:200],
                }
        except Exception as e:
            print(f"  ⚠️ [自我表述] LLM分析失败: {e}")
            return {
                "analysis_level": "surface_understanding",
                "analysis_gaps": ["分析服务暂时不可用"],
                "analysis_suggestions": ["建议回顾标准答案和解析"],
                "summary": f"分析暂时不可用（{str(e)}），请先参考正确答案。",
            }

    def get_session(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取会话详情"""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM self_explanations WHERE session_id = ? AND user_id = ?",
                (session_id, user_id)
            ).fetchone()

        if not row:
            return None

        result = dict(row)
        # 反序列化 JSON 字段
        if result.get("analysis_gaps"):
            try:
                result["analysis_gaps"] = json.loads(result["analysis_gaps"])
            except (json.JSONDecodeError, TypeError):
                result["analysis_gaps"] = []
        if result.get("analysis_suggestions"):
            try:
                result["analysis_suggestions"] = json.loads(result["analysis_suggestions"])
            except (json.JSONDecodeError, TypeError):
                result["analysis_suggestions"] = []

        return result

    def get_user_sessions(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """获取用户的所有自我表述历史"""
        offset = (page - 1) * page_size
        with _get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM self_explanations WHERE user_id = ?",
                (user_id,)
            ).fetchone()["cnt"]

            rows = conn.execute(
                "SELECT * FROM self_explanations WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset)
            ).fetchall()

        records = []
        for row in rows:
            r = dict(row)
            if r.get("analysis_gaps"):
                try:
                    r["analysis_gaps"] = json.loads(r["analysis_gaps"])
                except (json.JSONDecodeError, TypeError):
                    r["analysis_gaps"] = []
            if r.get("analysis_suggestions"):
                try:
                    r["analysis_suggestions"] = json.loads(r["analysis_suggestions"])
                except (json.JSONDecodeError, TypeError):
                    r["analysis_suggestions"] = []
            records.append(r)

        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }

    def get_pending_session_for_record(self, user_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        """获取某条错题记录关联的待处理表述会话"""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM self_explanations "
                "WHERE user_id = ? AND record_id = ? AND status = 'pending' "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id, record_id)
            ).fetchone()
        if row:
            return dict(row)
        return None

    # ==================== 推荐标记管理（防止3次重复推荐）====================

    def has_recommendation_been_triggered(self, record_id: str, user_id: str) -> bool:
        """
        检查某条错题记录是否已经通过自我表述触发了推荐

        用在第3次重练时：如果已提前推荐过，不再重复推荐
        """
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM self_explanations "
                "WHERE user_id = ? AND record_id = ? AND recommendation_triggered = 1",
                (user_id, record_id)
            ).fetchone()
        return row is not None and row["cnt"] > 0

    async def trigger_recommendation(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        基于自我表述分析结果，触发错题推荐（提前推荐场景）

        调用时机：用户自我表述后，LLM评估为"理解差"时
        效果：生成推荐资源并缓存，标记已推荐，后续第3次重练不再重复推荐
        """
        # 1. 获取会话信息
        session = self.get_session(session_id, user_id)
        if not session:
            return {"error": "会话不存在", "should_recommend": False}

        record_id = session.get("record_id", "")
        if not record_id:
            return {"error": "缺少错题记录ID", "should_recommend": False}

        # 2. 从错题本获取题目信息
        from services.wrong_answer_service import WrongAnswerService
        wa_service = WrongAnswerService()
        detail = wa_service.get_wrong_answer_detail(record_id, user_id)
        if not detail:
            return {"error": "错题记录不存在", "should_recommend": False}

        # 3. 提取推荐所需参数
        kps_raw = session.get("knowledge_points", "")
        if isinstance(kps_raw, str):
            kps = [s.strip() for s in kps_raw.split(",") if s.strip()]
        else:
            kps = kps_raw or []
        if not kps:
            kps = detail.get("knowledge_points", [])
        attempt_count = detail.get("attempt_count", 0) or 0
        difficulty = detail.get("difficulty", "")

        # 4. 调用错题推荐引擎
        # ★★★ 强制 attempt_count >= 3：推荐引擎内部有 attempt_count < 3 的守卫 ★★★
        # 此处是"提前推荐"场景，必须绕过守卫才能生成内容
        rec_result = await wa_service.recommend_materials_for_wrong_answer_async(
            user_id=user_id,
            knowledge_points=kps if isinstance(kps, list) else [kps],
            attempt_count=max(attempt_count, 3),  # 绕过 >=3 守卫
            difficulty=difficulty,
        )

        # 5. 将推荐缓存到错题推荐表（确保前端 restoreRecommendations 能读到）
        if rec_result.get("should_recommend") and record_id:
            await wa_service._save_recommendations_for_record(
                record_id=record_id,
                user_id=user_id,
                materials=rec_result,
            )

        # 6. 标记已推荐（第3次重练时跳过）
        with _get_conn() as conn:
            conn.execute(
                "UPDATE self_explanations SET recommendation_triggered = 1 WHERE session_id = ?",
                (session_id,)
            )
            conn.commit()

        if rec_result.get("should_recommend"):
            print(f"  ✅ [自我表述] 提前推荐完成 (session={session_id})")
        else:
            print(f"  ⚠️ [自我表述] 推荐引擎未生成内容 (session={session_id})")

        return rec_result

    def get_latest_analysis_for_record(self, record_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取某条错题记录最新的自我表述分析结果

        用于第3次重练时，后端将分析数据一并返回，前端可展示历史分析按钮

        Returns:
            {"analysis_level": str, "analysis_gaps": [str], "analysis_suggestions": [str], "summary": str}
            或 None（没有分析记录）
        """
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT analysis_level, analysis_gaps, analysis_suggestions, llm_raw_feedback "
                "FROM self_explanations "
                "WHERE user_id = ? AND record_id = ? AND status = 'analyzed' "
                "ORDER BY created_at DESC LIMIT 1",
                (user_id, record_id)
            ).fetchone()

        if not row:
            return None

        result = dict(row)
        # 反序列化 JSON 字段
        for field in ("analysis_gaps", "analysis_suggestions"):
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    result[field] = []

        # 从 llm_raw_feedback 提取 summary
        try:
            raw = result.get("llm_raw_feedback", "{}")
            if raw:
                parsed = json.loads(raw)
                result["summary"] = parsed.get("summary", "")
        except (json.JSONDecodeError, TypeError):
            result["summary"] = ""

        return {
            "analysis_level": result.get("analysis_level", ""),
            "analysis_gaps": result.get("analysis_gaps", []),
            "analysis_suggestions": result.get("analysis_suggestions", []),
            "summary": result.get("summary", ""),
        }
