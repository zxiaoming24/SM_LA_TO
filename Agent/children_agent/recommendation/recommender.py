"""
recommender.py - 个性化推荐引擎

整合三大推荐策略 + 遗忘曲线调度：
1. 内容推荐（Content-based）     → 基于用户画像特征匹配
2. 协同过滤（Collaborative）     → 相似用户做过的题
3. 遗忘曲线（Spaced Repetition） → 根据艾宾浩斯调度复习（资源级 + 知识点级）
4. ChromaDB 语义搜索             → 找相似资源

使用流程：
    recommender = PersonalizedRecommender()
    recommendations = recommender.recommend(
        user_id="user_001",
        resource_type="question",
        user_features=features,   # 8维度特征（可选）
        topic="循环结构",          # 可选：限定知识点
        n=5
    )
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from .resource_db import ResourceDB
from .learning_record_db import LearningRecordDB
from .semantic_store import SemanticStore
from .forgetting_curve import ForgettingCurveScheduler

logger = logging.getLogger(__name__)

# ★★★ 知识点级遗忘曲线（MemoryHub）★★★
try:
    from memory.knowledge_mastery import KnowledgeMasteryGraph
except ImportError:
    KnowledgeMasteryGraph = None

# ★★★ 采纳建议权重考虑 ★★★
try:
    from Agent.children_agent.learning_assessment_agent import LearningAssessmentAgent
except ImportError:
    try:
        from children_agent.learning_assessment_agent import LearningAssessmentAgent
    except ImportError:
        LearningAssessmentAgent = None


class PersonalizedRecommender:
    """
    个性化推荐引擎主类。

    推荐策略优先级：
        1. 遗忘曲线到期项（必须推荐）
        2. 协同过滤（找相似用户做过的好题）
        3. 内容推荐（基于用户画像 + ChromaDB 语义搜索）
        4. 随机补充（保证资源多样性）
    """

    def __init__(self):
        self.resource_db = ResourceDB()
        self.record_db = LearningRecordDB()
        self.semantic = SemanticStore()
        self.scheduler = ForgettingCurveScheduler()
        # ★★★ 知识点级掌握图谱（延迟初始化）★★★
        self._knowledge = None

    @property
    def knowledge(self):
        if self._knowledge is None and KnowledgeMasteryGraph:
            self._knowledge = KnowledgeMasteryGraph()
        return self._knowledge

    # =========================================================================
    # 主入口
    # =========================================================================

    def recommend(self,
                 user_id: str,
                 resource_type: str = "question",
                 user_features: Dict[str, Any] = None,
                 topic: str = None,
                 difficulty: int = None,
                 n: int = 5,
                 exclude_done: bool = True) -> Dict[str, Any]:
        """
        获取个性化推荐结果。

        Args:
            user_id: 用户ID
            resource_type: 资源类型（question / document / video）
            user_features: 用户8维度特征（从 DynamicFeatureUpdater 获取）
            topic: 限定知识点（可选，如"循环结构"）
            difficulty: 限定难度（可选）
            n: 推荐数量
            exclude_done: 是否排除已做过的资源

        Returns:
            {
                "due_reviews": [...],      # 遗忘曲线到期项
                "collaborative": [...],    # 协同过滤推荐
                "content_based": [...],    # 内容推荐
                "source": "..."            # 主要来源标签
            }
        """
        recommendations: List[Dict] = []
        sources = []

        # ---- 策略1：遗忘曲线到期复习（优先级最高）----
        due = self.scheduler.get_due_reviews(user_id, resource_type, limit=n * 3)
        if due:
            recs = self._enrich_due_reviews(due, resource_type)
            if recs:
                recommendations.extend(recs)
                sources.append("forgetting_curve")

        # ---- 策略1.5：知识点级遗忘曲线到期复习 ----
        if self.knowledge and len(recommendations) < n:
            try:
                due_knowledge = self.knowledge.get_due_knowledge_reviews(user_id, limit=n)
                for dk in due_knowledge:
                    kp = dk["knowledge_point"]
                    # ★★★ 如果调用方传了 topic，优先匹配 topic ★★★
                    if topic and topic not in kp:
                        continue
                    pool = self.resource_db.find_questions(topic=kp, limit=n)
                    for q in pool:
                        q["recommendation_reason"] = f"知识点复习: {kp}"
                        recommendations.append(q)
                        if len(recommendations) >= n:
                            break
                    if len(recommendations) >= n:
                        break
                if due_knowledge:
                    sources.append("knowledge_forgetting_curve")
            except Exception:
                pass

        # ---- 策略2：协同过滤（相似用户做过且做对的题）----
        collab = self.record_db.get_collaborative_questions(
            user_id, topic=topic, limit=n
        )
        if collab:
            recs = self._enrich_collab(collab, resource_type)
            recommendations.extend(recs)
            sources.append("collaborative")

        # ---- 策略3：内容推荐（基于用户画像 + ChromaDB 语义搜索）----
        if user_features and len(recommendations) < n:
            content_recs = self._content_based_recommend(
                user_id, resource_type, user_features,
                topic=topic, difficulty=difficulty,
                limit=n, exclude_done=exclude_done
            )
            recommendations.extend(content_recs)
            if content_recs:
                sources.append("content_based")

        # ---- 策略4：随机补充（保证多样性）----
        if len(recommendations) < n:
            random_recs = self._random_fill(
                user_id, resource_type, topic, difficulty,
                limit=n - len(recommendations), exclude_done=exclude_done
            )
            recommendations.extend(random_recs)
            if random_recs:
                sources.append("random")

        # 去重 + 过滤无内容脏数据 + 截取
        seen = set()
        unique_recs = []
        for r in recommendations:
            rid = r.get("id") or r.get("resource_id")
            if rid and rid not in seen:
                # ★★★ 跳过 content 和 title 都空的脏数据 ★★★
                if not r.get("content") and not r.get("title") and not r.get("question"):
                    continue
                seen.add(rid)
                unique_recs.append(r)

        # ★★★ 根据已采纳的建议调整推荐排序 ★★★
        unique_recs = self._apply_adoption_weights(user_id, unique_recs, resource_type)

        # ★★★ 注意力偏好标记（供调试用）★★★
        _pref_debug = {}
        try:
            from .attention_profile import get_profile
            profile = get_profile(user_id)
            prefs = profile.get_effective_preferences()
            _pref_debug = prefs
        except Exception:
            pass

        primary_source = sources[0] if sources else "random"
        return self._build_result(unique_recs[:n], primary_source, n, _pref_debug)

    # =========================================================================
    # 各策略实现
    # =========================================================================

    def _content_based_recommend(self,
                                  user_id: str,
                                  resource_type: str,
                                  features: Dict[str, Any],
                                  topic: str = None,
                                  difficulty: int = None,
                                  limit: int = 5,
                                  exclude_done: bool = True) -> List[Dict]:
        """
        内容推荐：基于8维度特征自动推断 difficulty + topic，
        用 ChromaDB 语义搜索匹配资源，SQLite 做精确过滤。
        """
        # ---- 自动推断 difficulty ----
        inferred_diff = difficulty
        if inferred_diff is None:
            foundation = features.get("academic_background", {}).get(
                "foundation_level", "中等")
            if foundation in ("薄弱", "入门"):
                inferred_diff = 1
            elif foundation in ("中等", "一般"):
                inferred_diff = 2
            elif foundation in ("扎实", "良好"):
                inferred_diff = 3
            elif foundation in ("优秀", "精通"):
                inferred_diff = 4

        # ---- 推断 topic（优先薄弱点）----
        weak = self.record_db.get_user_weak_topics(user_id, threshold=0.6)
        topics_to_try = []
        if topic:
            topics_to_try.append(topic)
        if weak:
            topics_to_try.extend([w["topic"] for w in weak[:3]])

        results = []
        for t in topics_to_try or [None]:
            if resource_type == "question":
                # SQLite 精确过滤
                pool = self.resource_db.find_questions(
                    topic=t, difficulty=inferred_diff, limit=limit * 2
                )
                # ★★★ 如果 exact topic 无结果，尝试 knowledge_point LIKE 搜索 ★★★
                if not pool and t:
                    pool = self.resource_db.find_questions(
                        knowledge_point=t, difficulty=inferred_diff, limit=limit * 2
                    )
                # ChromaDB 语义排序
                if pool:
                    query_text = f"{t} {' '.join([p.get('sub_topic', '') for p in pool[:3]])}"
                    sem = self.semantic.search_similar_questions(
                        query=query_text, topic=t,
                        difficulty=inferred_diff, limit=limit
                    )
                    results.extend(sem)
            elif resource_type == "document":
                pool = self.resource_db.find_documents(
                    topic=t, difficulty=inferred_diff, limit=limit * 2
                )
                if pool:
                    sem = self.semantic.search_similar_documents(
                        query=t, category=t, difficulty=inferred_diff, limit=limit
                    )
                    results.extend(sem)
            elif resource_type == "video":
                pool = self.resource_db.find_videos(
                    topic=t, difficulty=inferred_diff, limit=limit * 2
                )
                if pool:
                    sem = self.semantic.search_similar_videos(
                        query=t, topic=t, difficulty=inferred_diff, limit=limit
                    )
                    results.extend(sem)

            if len(results) >= limit:
                break

        # ★★★ 过滤 content 为空的脏数据 ★★★
        results = [r for r in results if r.get("content") or r.get("title")]

        # 排除已做过的
        if exclude_done:
            done = self._get_done_ids(user_id, resource_type)
            results = [r for r in results if r.get("id") not in done]

        return results[:limit]

    def _random_fill(self,
                     user_id: str,
                     resource_type: str,
                     topic: str,
                     difficulty: int,
                     limit: int,
                     exclude_done: bool) -> List[Dict]:
        """从题库/文档库/视频库随机抽取补充推荐。"""
        if resource_type == "question":
            pool = self.resource_db.get_user_unseen_questions(
                user_id, topic=topic, difficulty=difficulty, limit=limit
            )
        elif resource_type == "document":
            pool = self.resource_db.find_documents(
                topic=topic, difficulty=difficulty, limit=limit
            )
        elif resource_type == "video":
            pool = self.resource_db.find_videos(
                topic=topic, difficulty=difficulty, limit=limit
            )
        else:
            pool = []
        return pool[:limit]

    def _enrich_due_reviews(self, due_items: List[Dict],
                            resource_type: str) -> List[Dict]:
        """将到期复习项补充完整信息。"""
        results = []
        for item in due_items:
            rid = item["resource_id"]
            if resource_type == "question":
                obj = self.resource_db.get_question(rid)
            elif resource_type == "document":
                obj = self.resource_db.get_document(rid)
            elif resource_type == "video":
                obj = self.resource_db.get_video(rid)
            else:
                obj = None
            if obj:
                # ★★★ 过滤 content/title 为空的脏数据 ★★★
                if not obj.get("content") and not obj.get("title"):
                    continue
                results.append({**item, **obj, "recommendation_reason": "遗忘曲线复习"})
        return results

    def _enrich_collab(self, collab_items: List[Dict],
                        resource_type: str) -> List[Dict]:
        """补充协同过滤结果详情。"""
        results = []
        for item in collab_items:
            rid = item.get("id") or item.get("resource_id")
            if resource_type == "question":
                obj = self.resource_db.get_question(rid)
            elif resource_type == "document":
                obj = self.resource_db.get_document(rid)
            elif resource_type == "video":
                obj = self.resource_db.get_video(rid)
            else:
                obj = None
            if obj:
                # ★★★ 过滤 content/title 为空的脏数据 ★★★
                if not obj.get("content") and not obj.get("title"):
                    continue
                results.append({
                    **item,
                    **obj,
                    "recommendation_reason": f"相似用户推荐({item.get('recommender_count', 0)}人做过)"
                })
        return results

    def _apply_adoption_weights(self, user_id: str,
                                 recommendations: List[Dict],
                                 resource_type: str) -> List[Dict]:
        """根据用户已采纳的评估建议，调整推荐列表的排序"""
        if not LearningAssessmentAgent or not recommendations:
            return recommendations

        try:
            agent = LearningAssessmentAgent()
            weights = agent.build_adoption_weights(user_id)
        except Exception:
            return recommendations

        if not weights:
            return recommendations

        # 解析权重配置
        increase_types = weights.get("increase_resource_types", [])
        decrease_types = weights.get("decrease_resource_types", [])
        knowledge_priority = weights.get("knowledge_priority", [])
        difficulty = weights.get("difficulty", None)

        # 给每条推荐加分/减分
        scored = []
        for rec in recommendations:
            boost = 0.0
            adoption_reasons = []

            # 资源类型匹配
            rt = resource_type
            if rt in increase_types:
                boost += 0.3
                adoption_reasons.append(f"你采纳了增加{rt}类资源的建议")
            elif rt in decrease_types:
                boost -= 0.2
                adoption_reasons.append(f"你采纳了减少{rt}类资源的建议")

            # 知识点优先级匹配
            if knowledge_priority:
                kps = rec.get("knowledge_points", []) or rec.get("tags", [])
                for kp in knowledge_priority:
                    if any(kp in str(k) for k in kps):
                        boost += 0.4
                        adoption_reasons.append(f"你采纳了优先学习「{kp}」的建议")
                        break

            # 难度调整
            if difficulty == "调高" and rec.get("difficulty", 3) >= 4:
                boost += 0.2
                adoption_reasons.append(f"你采纳了提高难度的建议")
            elif difficulty == "调低" and rec.get("difficulty", 3) <= 2:
                boost += 0.2
                adoption_reasons.append(f"你采纳了降低难度的建议")

            rec["_adoption_boost"] = boost
            rec["_adoption_reasons"] = adoption_reasons
            scored.append(rec)

        # 原始顺序分数（越靠前原始分越高）
        base_score = 1.0
        for i, rec in enumerate(scored):
            order_score = base_score - (i / len(scored)) * 0.5
            rec["_final_score"] = order_score + rec.get("_adoption_boost", 0)

        # 按最终分数重新排序
        scored.sort(key=lambda x: x.get("_final_score", 0), reverse=True)

        return scored

    def _get_done_ids(self, user_id: str, resource_type: str) -> set:
        rows = self.record_db.get_user_solutions(user_id, resource_type, limit=1000)
        return {r["resource_id"] for r in rows if r.get("resource_id")}

    def _build_result(self, recs: List[Dict], source: str, n: int, attention_prefs: dict = None) -> Dict[str, Any]:
        result = {
            "recommendations": recs[:n],
            "count": len(recs[:n]),
            "primary_source": source,
            "timestamp": datetime.now().isoformat()
        }
        if attention_prefs:
            result["attention_preferences"] = attention_prefs
        return result

    # =========================================================================
    # 记录学习行为（做题/看文档/看视频后调用）
    # =========================================================================

    def record_learning(self,
                        user_id: str,
                        resource_type: str,
                        resource_id: str,
                        is_correct: bool = None,
                        time_spent: int = 0,
                        user_features: Dict[str, Any] = None):
        """
        记录一次学习行为，同时：
        1. 写入学习记录（SQLite）
        2. 更新遗忘曲线调度（资源级 + 知识点级）
        3. 更新 ChromaDB 薄弱点向量
        """
        # 1. 记录做题
        self.record_db.record_solution(
            user_id, resource_type, resource_id,
            is_correct, time_spent
        )

        # 2. 更新遗忘曲线（资源级）
        review_info = self.scheduler.schedule_review(
            user_id, resource_type, resource_id, is_correct,
            time_spent=time_spent,
        )

        # 2.5 更新知识点级遗忘曲线（通过 resource_db 查知识点）
        try:
            kp = None
            if resource_type == "question":
                q = self.resource_db.get_question(resource_id)
                if q:
                    kps = q.get("knowledge_points", "")
                    if isinstance(kps, str) and kps:
                        kp = kps.split(",")[0].strip()
            elif resource_type == "document":
                d = self.resource_db.get_document(resource_id)
                if d:
                    kps = d.get("knowledge_points", "")
                    if isinstance(kps, str) and kps:
                        kp = kps.split(",")[0].strip()

            if kp:
                try:
                    from memory.knowledge_mastery import KnowledgeMasteryGraph
                    kg = KnowledgeMasteryGraph()
                    kg.record_activity(
                        user_id=user_id,
                        knowledge_point=kp,
                        correct=is_correct,
                        activity_type=resource_type,
                        time_spent=time_spent,
                    )
                except Exception as e:
                    print(f"  ⚠️ [推荐引擎] 更新知识点掌握度失败: {e}")
        except Exception as e:
            print(f"  ⚠️ [推荐引擎] 查找知识点失败: {e}")

        # 3. 更新用户薄弱点向量（每 10 次学习行为更新一次）
        if user_features:
            self.semantic.store_user_weakness_pattern(user_id, user_features)

        return review_info

    # =========================================================================
    # 复习提醒（供前端调用）
    # =========================================================================

    def get_review_reminder(self, user_id: str) -> Dict[str, Any]:
        """获取用户的今日复习提醒（增强版）。"""
        from memory.knowledge_mastery import KnowledgeMasteryGraph, MASTERY_LABELS, _get_conn
        
        now = datetime.now().isoformat()
        
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT knowledge_point, mastery_level, mastery_points, 
                       interval_days, next_review, easiness, repetitions
                FROM knowledge_mastery
                WHERE user_id = ? AND next_review <= ?
                ORDER BY next_review ASC
                LIMIT 30
            """, (user_id, now)).fetchall()
            
            upcoming_rows = conn.execute("""
                SELECT knowledge_point, mastery_level, next_review
                FROM knowledge_mastery
                WHERE user_id = ? AND next_review > ?
                ORDER BY next_review ASC
                LIMIT 10
            """, (user_id, now)).fetchall()
            
            mastered_count = conn.execute("""
                SELECT COUNT(*) FROM review_session
                WHERE user_id = ? AND status = 'completed' AND completed_at >= ?
            """, (user_id, (datetime.now() - timedelta(days=7)).isoformat())).fetchone()[0]
            
            total_count = conn.execute("""
                SELECT COUNT(*) FROM knowledge_mastery
                WHERE user_id = ?
            """, (user_id,)).fetchone()[0]
        finally:
            conn.close()

        grouped = {}
        for row in rows:
            kp = row["knowledge_point"]
            if kp not in grouped:
                grouped[kp] = []
            grouped[kp].append({
                "topic": kp,
                "title": kp,
                "mastery_level": row["mastery_level"],
                "mastery_label": MASTERY_LABELS.get(row["mastery_level"], "未知"),
                "mastery_points": row["mastery_points"],
                "interval_days": row["interval_days"],
                "easiness": row["easiness"],
                "repetitions": row["repetitions"],
                "next_review": row["next_review"],
                "type": "knowledge"
            })

        upcoming = [{
            "topic": r["knowledge_point"],
            "mastery_level": r["mastery_level"],
            "next_review": r["next_review"]
        } for r in upcoming_rows] if upcoming_rows else []

        due_count = len(rows)

        return {
            "user_id": user_id,
            "today_due_count": due_count,
            "grouped_due": grouped,
            "overdue_priority": [],
            "upcoming_items": upcoming,
            "mastered_count": mastered_count,
            "total_items": total_count,
            "message": (
                f"今日有 {due_count} 个知识点需要复习，"
                f"近7天已复习 {mastered_count} 个，继续加油！"
                if due_count > 0
                else "今日无复习任务，继续学习新内容吧！"
            )
        }
