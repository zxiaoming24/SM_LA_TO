"""
companion_search.py - 学伴搜索与匹配服务

根据用户自身的8维度特征 + 学习进度，自动搜索特征相似/互补的其他用户。
用户只需点一下"找学伴"，系统自动匹配。
"""

import json
import sqlite3
import math
import threading
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

USER_FEATURES_DIR = Path(__file__).parent.parent / "user_features"
DB_PATH = Path(__file__).parent.parent / "recommendation_data" / "companion.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DIMENSION_NAMES = [
    "academic_background", "learning_behavior", "goal_motivation",
    "cognitive_abilities", "emotional_state", "social_interaction",
    "time_management", "creativity_innovation"
]

DIMENSION_LABELS = {
    "academic_background": "学术背景",
    "learning_behavior": "学习行为",
    "goal_motivation": "目标动机",
    "cognitive_abilities": "认知能力",
    "emotional_state": "情绪状态",
    "social_interaction": "社交互动",
    "time_management": "时间管理",
    "creativity_innovation": "创新创造",
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companion_relationships (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id_a       TEXT NOT NULL,
            user_id_b       TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            invited_by      TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL,
            UNIQUE(user_id_a, user_id_b)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companion_interactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            relation_id     INTEGER NOT NULL,
            sender_id       TEXT NOT NULL,
            content_type    TEXT DEFAULT 'message',
            content         TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shared_resources (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sharer_id       TEXT NOT NULL,
            receiver_id     TEXT NOT NULL,
            resource_type   TEXT NOT NULL,
            resource_id     TEXT NOT NULL,
            title           TEXT DEFAULT '',
            knowledge_point TEXT DEFAULT '',
            message         TEXT DEFAULT '',
            read_at         TEXT,
            created_at      TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            resource_type   TEXT NOT NULL,
            resource_id     TEXT NOT NULL,
            title           TEXT DEFAULT '',
            knowledge_point TEXT DEFAULT '',
            source_user_id  TEXT DEFAULT '',
            created_at      TEXT NOT NULL,
            UNIQUE(user_id, resource_type, resource_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cr_user_a ON companion_relationships(user_id_a)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cr_user_b ON companion_relationships(user_id_b)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cr_status ON companion_relationships(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sr_sharer ON shared_resources(sharer_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sr_receiver ON shared_resources(receiver_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fav_user ON favorites(user_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS co_study_invitations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            inviter_id      TEXT NOT NULL,
            invitee_id      TEXT NOT NULL,
            resource_type   TEXT NOT NULL,
            resource_id     TEXT NOT NULL,
            title           TEXT DEFAULT '',
            status          TEXT DEFAULT 'pending',
            created_at      TEXT NOT NULL,
            responded_at    TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_csi_invitee ON co_study_invitations(invitee_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_csi_status ON co_study_invitations(status)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS co_study_messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            invitation_id   INTEGER NOT NULL,
            sender_id       TEXT NOT NULL,
            content         TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_csm_invitation ON co_study_messages(invitation_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pair_programming_sessions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            invitation_id   INTEGER NOT NULL UNIQUE,
            problem_id      TEXT NOT NULL,
            problem_data    TEXT DEFAULT '{}',
            code_content    TEXT DEFAULT '',
            language        TEXT DEFAULT 'python',
            submitted       INTEGER DEFAULT 0,
            submitter_id    TEXT,
            submit_result   TEXT DEFAULT '{}',
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pps_invitation ON pair_programming_sessions(invitation_id)")
    try:
        conn.execute("ALTER TABLE co_study_invitations ADD COLUMN mode TEXT DEFAULT 'separate'")
    except Exception:
        pass
    conn.commit()
    conn.close()


_init_db()


def _load_user_features(user_id: str) -> Optional[Dict]:
    """读取用户特征文件"""
    path = USER_FEATURES_DIR / f"{user_id}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("current_features") or data
    except Exception:
        return None


def _load_user_plan(user_id: str) -> Optional[Dict]:
    """读取用户学习计划（通过 StudyPlanner 获取活跃计划）"""
    try:
        from memory.study_planner import StudyPlanner
        planner = StudyPlanner()
        plan = planner.get_plan(user_id)
        return plan
    except Exception:
        return None


def _get_dimension_scores(features: Dict) -> List[int]:
    """从特征中提取8维度分数数组"""
    scores = features.get("summary_scores", {}).get("dimension_scores", [])
    if scores and len(scores) == 8:
        return scores
    return [features.get(dim, {}).get("score", 0) for dim in DIMENSION_NAMES]


def _get_user_knowledge_points(user_id: str) -> set:
    """获取用户学习计划中的所有知识点"""
    plan = _load_user_plan(user_id)
    if not plan:
        return set()
    kps = set()
    for phase in plan.get("phases", []):
        for kp in phase.get("knowledge_points", []):
            kps.add(kp)
    return kps


def _get_user_phase_index(user_id: str) -> int:
    """获取用户当前进行中的阶段索引"""
    plan = _load_user_plan(user_id)
    if not plan:
        return -1
    phases = plan.get("phases", [])
    for i, phase in enumerate(phases):
        if phase.get("status") == "进行中":
            return i
    return -1


def _euclidean_distance(scores_a: List[int], scores_b: List[int]) -> float:
    """计算欧氏距离（越小越相似）"""
    if not scores_a or not scores_b:
        return 999
    n = min(len(scores_a), len(scores_b))
    return math.sqrt(sum((scores_a[i] - scores_b[i]) ** 2 for i in range(n)))


def _feature_similarity(scores_a: List[int], scores_b: List[int]) -> float:
    """特征相似度 0-100，越大越相似"""
    dist = _euclidean_distance(scores_a, scores_b)
    max_dist = math.sqrt(8 * 100 ** 2)
    return max(0, round((1 - dist / max_dist) * 100, 1))


def _get_all_user_ids() -> List[str]:
    """扫描 user_features 目录获取所有用户ID（排除无特征文件的目录）"""
    users = set()
    for f in USER_FEATURES_DIR.iterdir():
        if f.suffix == ".json" and f.stem != "current":
            users.add(f.stem)
        if f.is_dir() and (f / "study_plan.json").exists():
            users.add(f.name)
    return sorted(users)


class CompanionSearchService:
    """学伴搜索与匹配服务"""

    def __init__(self):
        pass

    def find_matches(self, user_id: str, limit: int = 10) -> Dict[str, Any]:
        """
        根据当前用户特征自动搜索匹配的学伴。

        Args:
            user_id: 当前用户ID
            limit: 返回结果数量

        Returns:
            {
                "matches": [
                    {
                        "user_id": "user_xxx",
                        "similarity": 85.0,
                        "reason": "...",
                        "dimension_scores": [...],
                        "phase_index": 0,
                        "knowledge_points": [...],
                        "relationship_status": "none/pending/accepted"
                    }
                ],
                "my_scores": [...],
                "my_knowledge_points": [...],
                "total_users_scanned": 10
            }
        """
        my_features = _load_user_features(user_id)
        if not my_features:
            return {"error": f"用户 {user_id} 特征不存在", "matches": []}

        my_scores = _get_dimension_scores(my_features)
        my_kps = _get_user_knowledge_points(user_id)
        my_phase = _get_user_phase_index(user_id)

        all_users = _get_all_user_ids()
        all_users = [u for u in all_users if u != user_id]

        scored = []
        for other_id in all_users:
            other_features = _load_user_features(other_id)
            if not other_features:
                continue

            other_scores = _get_dimension_scores(other_features)
            other_kps = _get_user_knowledge_points(other_id)
            other_phase = _get_user_phase_index(other_id)

            sim = _feature_similarity(my_scores, other_scores)
            kp_overlap = len(my_kps & other_kps)
            phase_diff = abs(my_phase - other_phase) if my_phase >= 0 and other_phase >= 0 else 999

            kp_score = min(kp_overlap * 10, 30)
            phase_score = max(0, 15 - phase_diff * 3) if phase_diff < 5 else 0
            total = min(100, sim * 0.6 + kp_score + phase_score)

            reasons = []
            if sim > 60:
                dim_labels = [DIMENSION_LABELS.get(d, d) for d in DIMENSION_NAMES]
                close_dims = []
                for i in range(8):
                    if abs(my_scores[i] - other_scores[i]) <= 15:
                        close_dims.append(dim_labels[i])
                if close_dims:
                    reasons.append(f"特征维度相似: {'、'.join(close_dims[:3])}")
            if kp_overlap > 0:
                reasons.append(f"共同知识点: {kp_overlap}个")
            if phase_diff <= 1 and my_phase >= 0:
                reasons.append("学习阶段相近")
            if not reasons:
                reasons.append("综合匹配")

            relationship_status = self._get_relationship_status(user_id, other_id)

            scored.append({
                "user_id": other_id,
                "similarity": round(total, 1),
                "reason": "；".join(reasons[:3]),
                "dimension_scores": other_scores,
                "phase_index": other_phase,
                "knowledge_points": sorted(other_kps)[:10],
                "relationship_status": relationship_status,
            })

        scored.sort(key=lambda x: x["similarity"], reverse=True)

        return {
            "matches": scored[:limit],
            "my_scores": my_scores,
            "my_knowledge_points": sorted(my_kps),
            "my_phase_index": my_phase,
            "total_users_scanned": len(scored),
        }

    def _get_relationship_status(self, user_id_a: str, user_id_b: str) -> str:
        """查询两个用户之间的关系状态"""
        conn = _get_conn()
        try:
            row = conn.execute("""
                SELECT status FROM companion_relationships
                WHERE (user_id_a = ? AND user_id_b = ?)
                   OR (user_id_a = ? AND user_id_b = ?)
            """, (user_id_a, user_id_b, user_id_b, user_id_a)).fetchone()
            return row["status"] if row else "none"
        finally:
            conn.close()

    def invite(self, from_user: str, to_user: str) -> Dict[str, Any]:
        """发送学伴邀请"""
        now = datetime.now().isoformat()
        conn = _get_conn()
        try:
            existing = conn.execute("""
                SELECT * FROM companion_relationships
                WHERE (user_id_a = ? AND user_id_b = ?)
                   OR (user_id_a = ? AND user_id_b = ?)
            """, (from_user, to_user, to_user, from_user)).fetchone()

            if existing:
                status = existing["status"]
                if status == "accepted":
                    return {"success": False, "error": "已经成为学伴", "status": status}
                if status == "pending":
                    return {"success": False, "error": "已发送过邀请，等待对方回应", "status": status}
                if status == "rejected":
                    conn.execute("""
                        UPDATE companion_relationships
                        SET status = 'pending', updated_at = ?
                        WHERE id = ?
                    """, (now, existing["id"]))
                    conn.commit()
                    return {"success": True, "companion_id": existing["id"], "status": "pending", "message": f"已重新向 {to_user} 发送学伴邀请"}

            cur = conn.execute("""
                INSERT INTO companion_relationships
                    (user_id_a, user_id_b, status, invited_by, created_at, updated_at)
                VALUES (?, ?, 'pending', ?, ?, ?)
            """, (from_user, to_user, from_user, now, now))
            conn.commit()
            return {"success": True, "companion_id": cur.lastrowid, "status": "pending", "message": f"已向 {to_user} 发送学伴邀请"}
        finally:
            conn.close()

    def respond(self, user_id: str, companion_id: int, accept: bool) -> Dict[str, Any]:
        """接受或拒绝学伴邀请"""
        conn = _get_conn()
        now = datetime.now().isoformat()
        try:
            row = conn.execute("""
                SELECT * FROM companion_relationships WHERE id = ?
            """, (companion_id,)).fetchone()

            if not row:
                return {"success": False, "error": "邀请不存在"}
            if row["user_id_b"] != user_id:
                return {"success": False, "error": "无权操作"}
            if row["status"] != "pending":
                return {"success": False, "error": "邀请已处理"}

            new_status = "accepted" if accept else "rejected"
            conn.execute("""
                UPDATE companion_relationships
                SET status = ?, updated_at = ?
                WHERE id = ?
            """, (new_status, now, companion_id))
            conn.commit()

            other_id = row["user_id_a"] if row["user_id_b"] == user_id else row["user_id_b"]
            return {
                "success": True,
                "status": new_status,
                "message": f"已{'接受' if accept else '拒绝'}来自 {other_id} 的学伴邀请"
            }
        finally:
            conn.close()

    def list_companions(self, user_id: str) -> Dict[str, Any]:
        """获取用户的所有学伴"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM companion_relationships
                WHERE (user_id_a = ? OR user_id_b = ?)
                  AND status = 'accepted'
                ORDER BY updated_at DESC
            """, (user_id, user_id)).fetchall()
        finally:
            conn.close()

        companions = []
        for row in rows:
            other_id = row["user_id_b"] if row["user_id_a"] == user_id else row["user_id_a"]
            features = _load_user_features(other_id)
            scores = _get_dimension_scores(features) if features else []
            plan = _load_user_plan(other_id)
            phase_name = ""
            if plan:
                phases = plan.get("phases", [])
                for p in phases:
                    if p.get("status") == "进行中":
                        phase_name = p.get("name", "")
                        break

            companions.append({
                "companion_id": row["id"],
                "user_id": other_id,
                "dimension_scores": scores,
                "current_phase": phase_name,
                "established_at": row["created_at"],
            })

        return {"companions": companions}

    def send_message(self, relation_id: int, sender_id: str, content: str) -> Dict[str, Any]:
        """学伴之间发消息"""
        now = datetime.now().isoformat()
        conn = _get_conn()
        try:
            row = conn.execute("""
                SELECT * FROM companion_relationships WHERE id = ?
            """, (relation_id,)).fetchone()
            if not row or row["status"] != "accepted":
                return {"success": False, "error": "学伴关系不存在或未激活"}
            if sender_id not in (row["user_id_a"], row["user_id_b"]):
                return {"success": False, "error": "无权操作"}

            conn.execute("""
                INSERT INTO companion_interactions
                    (relation_id, sender_id, content_type, content, created_at)
                VALUES (?, ?, 'message', ?, ?)
            """, (relation_id, sender_id, content, now))
            conn.commit()
            return {"success": True, "message": "消息已发送"}
        finally:
            conn.close()

    def get_pending_invites(self, user_id: str) -> List[Dict]:
        """获取待处理的邀请"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM companion_relationships
                WHERE user_id_b = ? AND status = 'pending'
                ORDER BY created_at DESC
            """, (user_id,)).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def get_interactions(self, relation_id: int, limit: int = 50) -> List[Dict]:
        """获取学伴互动记录"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM companion_interactions
                WHERE relation_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (relation_id, limit)).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def check_new_messages(self, user_id: str, since: str = None) -> List[Dict]:
        """检查是否有新消息"""
        conn = _get_conn()
        try:
            relations = conn.execute("""
                SELECT id, user_id_a, user_id_b FROM companion_relationships
                WHERE (user_id_a = ? OR user_id_b = ?) AND status = 'accepted'
            """, (user_id, user_id)).fetchall()

            relation_ids = [r["id"] for r in relations]
            if not relation_ids:
                return []

            placeholders = ",".join("?" * len(relation_ids))
            sql = f"""
                SELECT ci.*, cr.user_id_a, cr.user_id_b
                FROM companion_interactions ci
                JOIN companion_relationships cr ON ci.relation_id = cr.id
                WHERE ci.relation_id IN ({placeholders})
                  AND ci.sender_id != ?
            """
            params = relation_ids + [user_id]
            if since:
                sql += " AND ci.created_at > ?"
                params.append(since)
            sql += " ORDER BY ci.created_at DESC LIMIT 20"

            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    # ==================== 资源共享 ====================

    def share_to_companion(self, sharer_id: str, receiver_id: str,
                           resource_type: str, resource_id: str,
                           title: str = "", knowledge_point: str = "",
                           message: str = "") -> Dict[str, Any]:
        """
        分享资源给指定的学伴。

        通过后自动在 companion_interactions 中生成一条通知消息。
        """
        now = datetime.now().isoformat()
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO shared_resources
                    (sharer_id, receiver_id, resource_type, resource_id,
                     title, knowledge_point, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (sharer_id, receiver_id, resource_type, resource_id,
                  title, knowledge_point, message, now))

            conn.execute("""
                INSERT INTO companion_interactions
                    (relation_id, sender_id, content_type, content, created_at)
                VALUES (?, ?, 'share', ?, ?)
            """, (0, sharer_id,
                  f"分享了一份「{knowledge_point}」的{title}", now))
            conn.commit()
            return {"success": True, "message": f"已分享给 {receiver_id}"}
        finally:
            conn.close()

    def share_to_community(self, sharer_id: str,
                           resource_type: str, resource_id: str,
                           title: str = "", knowledge_point: str = "",
                           message: str = "") -> Dict[str, Any]:
        """分享资源到社区（receiver_id = __community__）
        加载真实资源内容创建社区帖子，使其他用户可以直接查看。
        """
        now = datetime.now().isoformat()
        conn = _get_conn()

        resource_data = self.load_shared_resource(sharer_id, resource_type, resource_id)

        post_title = f"分享{title} - {knowledge_point}" if knowledge_point else f"分享{title}"
        post_content = f"分享者: {sharer_id}\n"
        if knowledge_point:
            post_content += f"知识点: {knowledge_point}\n"
        post_content += f"资源ID: {resource_id}\n\n"

        if resource_data:
            if resource_type == "video":
                videos = resource_data.get("videos", [])
                if videos:
                    for v in videos[:3]:
                        post_content += f"🎬 {v.get('title','')}\n  链接: {v.get('url','')}\n  作者: {v.get('author','')} 时长: {v.get('duration','')}\n\n"
                else:
                    recs = resource_data.get("recommendations", [])
                    if recs:
                        for r in recs[:3]:
                            post_content += f"🎬 {r.get('title','')}\n  内容: {(r.get('description','') or '')[:200]}...\n\n"
            elif resource_type in ("doc", "document"):
                # ★★★ 社区帖子始终用服务端代理路径（oss_url是预签名URL会过期）★★★
                dl_url = "/document/download/" + sharer_id + "/" + resource_id
                post_content += f"📄 {dl_url}\n"
            elif resource_type == "extension":
                # ★★★ 拓展阅读直接展示文本内容，不提供下载链接 ★★★
                content = resource_data.get("content", "") if resource_data else ""
                title = resource_data.get("title", "") if resource_data else ""
                if title:
                    post_content += f"📖 {title}\n\n"
                if content:
                    post_content += f"{content[:2000]}\n\n"
                else:
                    post_content += "📖 拓展材料（内容暂不可预览）\n"
            elif resource_type == "ppt":
                # ★★★ 社区帖子始终用服务端代理路径（oss_url是预签名URL会过期）★★★
                fn = resource_data.get("filename", "") if resource_data else ""
                dl_url = "/ppt/download/" + fn if fn else ""
                if dl_url:
                    post_content += f"📊 {dl_url}\n"
                else:
                    post_content += "📊 PPT（下载链接不可用）\n"
            elif resource_type == "practice":
                problem = resource_data.get("problem", resource_data)
                post_content += f"💻 {problem.get('title','编程题')}\n"
                post_content += f"难度: {problem.get('difficulty','中等')}\n"
                post_content += f"描述: {(problem.get('description','') or '')[:300]}\n"
                kps = problem.get("knowledge_points", [])
                if kps:
                    post_content += f"知识点: {', '.join(kps)}\n"
            elif resource_type == "mindmap":
                mm = resource_data.get("mindmap", resource_data)
                topic = mm.get("topic", "思维导图")
                post_content += f"🧠 {topic}\n"
                post_content += f"数据: 思维导图内容，共{len(mm.get('nodes', mm.get('children', [])))}个节点\n"
            elif resource_type == "question":
                questions = resource_data.get("questions", [resource_data])
                post_content += f"📝 理论题 ({len(questions)}道)\n"
            else:
                post_content += str(resource_data)[:500]
        else:
            post_content += f"（资源内容暂不可直接预览，请前往分享者处查看）\n"

        if message:
            post_content += f"\n分享留言: {message}\n"

        tag_list = [resource_type]
        if knowledge_point:
            tag_list.append(knowledge_point)

        try:
            import sqlite3 as _sqlite3
            community_db_path = Path(__file__).parent.parent / "community_data" / "community.db"
            if community_db_path.exists():
                cconn = _sqlite3.connect(str(community_db_path))
                cconn.execute("""
                    INSERT INTO community_posts
                        (post_id, user_id, title, content, zone, tags, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'resource', ?, ?, ?)
                """, (
                    f"share_{uuid.uuid4().hex[:12]}",
                    sharer_id,
                    post_title[:100],
                    post_content[:2000],
                    ",".join(tag_list),
                    now, now,
                ))
                cconn.commit()
                cconn.close()
                print(f"  ✅ [学伴] 社区帖子已创建")
        except Exception as e:
            print(f"  ⚠️ [学伴] 创建社区帖子失败: {e}")

        conn.execute("""
            INSERT INTO shared_resources
                (sharer_id, receiver_id, resource_type, resource_id,
                 title, knowledge_point, message, created_at)
            VALUES (?, '__community__', ?, ?, ?, ?, ?, ?)
        """, (sharer_id, resource_type, resource_id,
              title, knowledge_point, message, now))
        conn.commit()
        conn.close()

        return {"success": True, "message": "已分享到社区"}

    def _shared_row_to_minimal(self, row: sqlite3.Row) -> Dict:
        """将 shared_resources 行转为仅含下载信息的精简 dict"""
        rtype = "doc" if row["resource_type"] in ("doc", "document") else row["resource_type"]
        item = {
            "resource_type": rtype,
            "resource_id": row["resource_id"],
            "title": row["title"],
            "sharer_id": row["sharer_id"],
            "created_at": row["created_at"],
        }
        if rtype == "doc":
            self._attach_doc_data(item, row["sharer_id"])
        elif rtype == "ppt":
            self._attach_ppt_data(item, row["sharer_id"])
        return item

    def get_shared_to_me(self, user_id: str) -> List[Dict]:
        """获取别人分享给我的资源（仅下载信息）"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT resource_type, resource_id, sharer_id, title, created_at
                FROM shared_resources
                WHERE receiver_id = ?
                ORDER BY created_at DESC LIMIT 50
            """, (user_id,)).fetchall()
        finally:
            conn.close()
        return [self._shared_row_to_minimal(r) for r in rows]

    def get_shared_by_me(self, user_id: str) -> List[Dict]:
        """获取我分享出去的资源（仅下载信息）"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT resource_type, resource_id, sharer_id, title, created_at
                FROM shared_resources
                WHERE sharer_id = ?
                ORDER BY created_at DESC LIMIT 50
            """, (user_id,)).fetchall()
        finally:
            conn.close()
        return [self._shared_row_to_minimal(r) for r in rows]

    def get_community_shared(self, limit: int = 50) -> List[Dict]:
        """获取分享到社区的所有资源（仅下载信息）"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT resource_type, resource_id, sharer_id, title, created_at
                FROM shared_resources
                WHERE receiver_id = '__community__'
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
        finally:
            conn.close()
        return [self._shared_row_to_minimal(r) for r in rows]

    def _attach_doc_data(self, item: Dict, owner_id: str) -> None:
        """从ContentStore加载文档数据，仅附加上下载信息"""
        info = self._extract_doc_download_info(owner_id, item.get("resource_id", ""))
        item["oss_url"] = info.get("oss_url", "")
        item["file_path"] = info.get("file_path", "")

    def _attach_ppt_data(self, item: Dict, owner_id: str) -> None:
        """从ContentStore加载PPT数据，仅附加上下载信息"""
        info = self._extract_ppt_download_info(owner_id, item.get("resource_id", ""))
        item["oss_url"] = info.get("oss_url", "")
        item["filename"] = info.get("filename", "")

    def _extract_doc_download_info(self, owner_id: str, resource_id: str) -> Dict[str, str]:
        """从ContentStore加载文档，返回仅含 oss_url/file_path 的精简dict"""
        if not owner_id or not resource_id:
            return {"oss_url": "", "file_path": ""}
        try:
            from memory.content_store import ContentStore
            store = ContentStore()
            for prefix in ("phase_doc", "document", "doc"):
                doc = store.load(owner_id, prefix, resource_id)
                if doc and isinstance(doc, dict):
                    # ★★★ 优先读顶层字段（phase_bridge 已传播到顶层）★★★
                    if doc.get("oss_url") or doc.get("file_path"):
                        return {
                            "oss_url": doc.get("oss_url", ""),
                            "file_path": doc.get("file_path", ""),
                        }
                    # 回退：从嵌套 document 中读
                    inner = doc.get("document")
                    if inner and isinstance(inner, dict):
                        doc = inner
                    return {
                        "oss_url": doc.get("oss_url", ""),
                        "file_path": doc.get("file_path", ""),
                    }
        except Exception:
            pass
        return {"oss_url": "", "file_path": ""}

    def _extract_ppt_download_info(self, owner_id: str, resource_id: str) -> Dict[str, str]:
        """从ContentStore加载PPT，返回仅含 oss_url/filename 的精简dict"""
        if not owner_id or not resource_id:
            return {"oss_url": "", "filename": ""}
        try:
            from memory.content_store import ContentStore
            store = ContentStore()
            for prefix in ("phase_ppt", "ppt"):
                doc = store.load(owner_id, prefix, resource_id)
                if doc and isinstance(doc, dict):
                    return {
                        "oss_url": doc.get("oss_url", ""),
                        "filename": doc.get("filename", ""),
                    }
        except Exception:
            pass
        return {"oss_url": "", "filename": ""}

    def load_shared_resource(self, sharer_id: str,
                             resource_type: str, resource_id: str) -> Optional[Dict]:
        """读取分享者存储的原始资源内容（只读引用）
        doc/document 类型返回下载信息 + 内容预览，
        extension 返回完整文本内容供在线阅读，
        ppt 返回下载信息，
        其余类型返回完整内容。
        """
        if resource_type in ("doc", "document"):
            info = self._extract_doc_download_info(sharer_id, resource_id)
            # 同时加载内容预览
            try:
                from memory.content_store import ContentStore
                store = ContentStore()
                for prefix in ("phase_doc", "document", "doc"):
                    doc = store.load(sharer_id, prefix, resource_id)
                    if doc and isinstance(doc, dict):
                        inner = doc.get("document") or doc
                        info["doc_title"] = inner.get("doc_title", inner.get("title", ""))
                        info["doc_content"] = inner.get("doc_content", inner.get("content", ""))
                        break
            except Exception:
                pass
            return info
        if resource_type == "extension":
            # extension 没有文件，直接返回完整内容供在线阅读
            try:
                from memory.content_store import ContentStore
                store = ContentStore()
                for prefix in ("phase_extension", "extension"):
                    doc = store.load(sharer_id, prefix, resource_id)
                    if doc and isinstance(doc, dict):
                        # ★★★ PhaseBridge 路径：material 内有 title/background 等字段 ★★★
                        material = doc.get("material") or doc
                        title = material.get("title", "")
                        content = material.get("content", "")
                        # ★★★ 从子字段拼接 content ★★★
                        if not content:
                            sections = []
                            for key in ["background", "knowledge_distinguish", "principle_extend",
                                         "mistake_avoid", "application_scene", "personal_suggest"]:
                                val = material.get(key, "")
                                if val:
                                    sections.append(val)
                            if sections:
                                content = "\n\n".join(sections)
                        # ★★★ 推荐器路径：从 recommendations/problem 提取 ★★★
                        if not title:
                            recs = doc.get("recommendations", [])
                            if recs and isinstance(recs, list) and len(recs) > 0:
                                title = recs[0].get("title", "")
                                if not content:
                                    content = recs[0].get("description", "")
                            if not title:
                                problem = doc.get("problem", {})
                                title = problem.get("title", "")
                                if not content:
                                    content = problem.get("description", "")
                        if not title:
                            title = doc.get("knowledge_point", "拓展阅读")
                        if title or content:
                            return {
                                "type": "extension",
                                "title": title,
                                "content": content,
                                "oss_url": "",
                            }
            except Exception:
                pass
            return {"type": "extension", "title": "", "content": "", "oss_url": ""}
        if resource_type == "ppt":
            return self._extract_ppt_download_info(sharer_id, resource_id)
        try:
            from memory.content_store import ContentStore
            store = ContentStore()

            def _normalize(doc: dict) -> dict:
                if doc and isinstance(doc, dict):
                    inner = doc.get("document")
                    if inner and isinstance(inner, dict):
                        for key in ("_content_id", "_content_type", "_saved_at", "_user_id"):
                            if key in doc and key not in inner:
                                inner[key] = doc[key]
                        doc = inner
                return doc

            result = store.load(sharer_id, f"phase_{resource_type}", resource_id)
            if result:
                return _normalize(result)
            result = store.load(sharer_id, resource_type, resource_id)
            if result:
                return _normalize(result)
            type_fallbacks = {"doc": "document", "ppt": "ppt", "question": "question",
                              "extension": "extension", "mindmap": "mindmap",
                              "animation": "animation", "practice": "practice",
                              "video": "video"}
            fallback_type = type_fallbacks.get(resource_type, resource_type)
            if fallback_type != resource_type:
                result = store.load(sharer_id, fallback_type, resource_id)
                if result:
                    return _normalize(result)
            if resource_type == "practice":
                try:
                    from Agent.children_agent.recommendation.resource_db import ResourceDB
                    db = ResourceDB()
                    q = db.get_question(resource_id)
                    if q:
                        return {"problem": q, "_from_resource_db": True}
                except Exception:
                    pass
            return None
        except Exception as e:
            print(f"  ⚠️ 读取共享资源失败: {e}")
            return None

    # ==================== 收藏 ====================

    def add_favorite(self, user_id: str, resource_type: str, resource_id: str,
                     title: str = "", knowledge_point: str = "",
                     source_user_id: str = "") -> Dict[str, Any]:
        """收藏一个资源"""
        now = datetime.now().isoformat()
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT OR IGNORE INTO favorites
                    (user_id, resource_type, resource_id, title,
                     knowledge_point, source_user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, resource_type, resource_id, title,
                  knowledge_point, source_user_id, now))
            conn.commit()
            return {"success": True, "message": "已收藏"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def remove_favorite(self, user_id: str, resource_type: str,
                        resource_id: str) -> Dict[str, Any]:
        """取消收藏"""
        conn = _get_conn()
        try:
            conn.execute("""
                DELETE FROM favorites
                WHERE user_id = ? AND resource_type = ? AND resource_id = ?
            """, (user_id, resource_type, resource_id))
            conn.commit()
            return {"success": True, "message": "已取消收藏"}
        finally:
            conn.close()

    def _fav_row_to_minimal(self, row: sqlite3.Row) -> Dict:
        """将 favorites 行转为仅含下载信息的精简 dict"""
        rtype = "doc" if row["resource_type"] in ("doc", "document") else row["resource_type"]
        item = {
            "resource_type": rtype,
            "resource_id": row["resource_id"],
            "title": row["title"],
            "source_user_id": row["source_user_id"],
            "created_at": row["created_at"],
        }
        if rtype == "doc":
            self._attach_doc_data(item, row["source_user_id"])
        elif rtype == "ppt":
            self._attach_ppt_data(item, row["source_user_id"])
        return item

    def get_favorites(self, user_id: str) -> List[Dict]:
        """获取用户的所有收藏（仅下载信息）"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT resource_type, resource_id, source_user_id, title, created_at
                FROM favorites WHERE user_id = ?
                ORDER BY created_at DESC LIMIT 50
            """, (user_id,)).fetchall()
        finally:
            conn.close()
        return [self._fav_row_to_minimal(r) for r in rows]

    def is_favorited(self, user_id: str, resource_type: str,
                     resource_id: str) -> bool:
        """检查是否已收藏"""
        conn = _get_conn()
        try:
            row = conn.execute("""
                SELECT 1 FROM favorites
                WHERE user_id = ? AND resource_type = ? AND resource_id = ?
            """, (user_id, resource_type, resource_id)).fetchone()
            return row is not None
        finally:
            conn.close()

    # ==================== 学伴动态感知 ====================

    def get_companion_activities(self, user_id: str) -> List[Dict]:
        """获取所有学伴的当前学习动态"""
        companions = self.list_companions(user_id).get("companions", [])
        results = []
        for c in companions:
            other_id = c["user_id"]
            try:
                from memory.memory_hub import MemoryHub
                hub = MemoryHub()
                task = hub.working.get_current_task(other_id)
                topic = hub.working.get_current_topic(other_id)
                activity = {"user_id": other_id}
                if task:
                    type_labels = {"practice": "💻 练题", "video": "🎬 看视频", "doc": "📄 看文档",
                                   "question": "📝 做理论题", "mindmap": "🧠 看思维导图",
                                   "extension": "📖 拓展阅读", "ppt": "📊 看PPT"}
                    activity["task_type"] = task.get("type", "")
                    activity["task_detail"] = task.get("detail", "")
                    activity["label"] = type_labels.get(task.get("type", ""), f"📚 {task.get('type','')}")
                if topic:
                    activity["topic"] = topic
                results.append(activity)
            except Exception:
                results.append({"user_id": other_id})
        return results

    # ==================== 共学邀请 ====================

    def invite_co_study(self, inviter_id: str, invitee_id: str,
                        resource_type: str, resource_id: str,
                        title: str = "", mode: str = "separate") -> Dict[str, Any]:
        """发送共学邀请 (mode: separate=各自练习, pair=结对编程)"""
        now = datetime.now().isoformat()
        conn = _get_conn()
        try:
            try:
                cur = conn.execute("""
                    INSERT INTO co_study_invitations
                        (inviter_id, invitee_id, resource_type, resource_id, title, mode, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """, (inviter_id, invitee_id, resource_type, resource_id, title, mode, now))
            except Exception:
                try:
                    conn.execute("ALTER TABLE co_study_invitations ADD COLUMN mode TEXT DEFAULT 'separate'")
                except Exception:
                    pass
                cur = conn.execute("""
                    INSERT INTO co_study_invitations
                        (inviter_id, invitee_id, resource_type, resource_id, title, mode, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """, (inviter_id, invitee_id, resource_type, resource_id, title, mode, now))
            inv_id = cur.lastrowid

            if mode == "pair" and resource_type == "practice":
                try:
                    from memory.content_store import USER_FEATURES_DIR
                    import json as _json, glob as _glob
                    content_dir = str(USER_FEATURES_DIR)
                    # ★★★ 优先从邀请方目录加载（与 get_pair_session 一致）★★★
                    problem_data = self._load_pair_problem(inviter_id, resource_id)
                    # 用邀请标题作为兜底
                    if not problem_data.get("title") and title:
                        problem_data["title"] = title
                    conn.execute("""
                        INSERT INTO pair_programming_sessions
                            (invitation_id, problem_id, problem_data, code_content, language, created_at, updated_at)
                        VALUES (?, ?, ?, '', 'python', ?, ?)
                    """, (inv_id, resource_id, _json.dumps(problem_data, ensure_ascii=False), now, now))
                except Exception:
                    import traceback
                    traceback.print_exc()

            conn.commit()
            return {"success": True, "message": f"已邀请 {invitee_id} 一起学习", "mode": mode}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def respond_co_study(self, invite_id: int, accept: bool) -> Dict[str, Any]:
        """接受/拒绝共学邀请"""
        now = datetime.now().isoformat()
        conn = _get_conn()
        try:
            row = conn.execute("""
                SELECT * FROM co_study_invitations WHERE id = ?
            """, (invite_id,)).fetchone()
            if not row:
                return {"success": False, "error": "邀请不存在"}
            if row["status"] != "pending":
                return {"success": False, "error": "邀请已处理"}
            new_status = "accepted" if accept else "rejected"
            conn.execute("""
                UPDATE co_study_invitations SET status = ?, responded_at = ?
                WHERE id = ?
            """, (new_status, now, invite_id))
            conn.commit()
            inviter = row["inviter_id"]
            return {
                "success": True, "status": new_status,
                "inviter_id": inviter,
                "resource_type": row["resource_type"],
                "resource_id": row["resource_id"],
                "title": row["title"],
                "mode": row["mode"] if "mode" in row.keys() else "separate",
                "message": f"已{'接受' if accept else '拒绝'}共学邀请"
            }
        finally:
            conn.close()

    def get_co_study_invites(self, user_id: str) -> List[Dict]:
        """获取待处理的共学邀请"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM co_study_invitations
                WHERE invitee_id = ? AND status = 'pending'
                ORDER BY created_at DESC
            """, (user_id,)).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def get_my_co_study_sessions(self, user_id: str) -> List[Dict]:
        """获取用户相关的所有已接受共学记录"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM co_study_invitations
                WHERE (inviter_id = ? OR invitee_id = ?) AND status = 'accepted'
                ORDER BY created_at DESC LIMIT 50
            """, (user_id, user_id)).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def get_sent_co_study_invites(self, user_id: str) -> List[Dict]:
        """获取我发出的共学邀请（含状态）"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM co_study_invitations
                WHERE inviter_id = ?
                ORDER BY created_at DESC LIMIT 50
            """, (user_id,)).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def check_co_study_notifications(self, user_id: str, since: str = None) -> List[Dict]:
        """检查是否有邀被接受的共学通知（作为邀请方）"""
        conn = _get_conn()
        try:
            sql = """
                SELECT * FROM co_study_invitations
                WHERE inviter_id = ? AND status = 'accepted'
            """
            params = [user_id]
            if since:
                sql += " AND responded_at > ?"
                params.append(since)
            sql += " ORDER BY responded_at DESC LIMIT 10"
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def get_invitation(self, invite_id: int) -> Optional[Dict]:
        """获取单个共学邀请详情"""
        conn = _get_conn()
        try:
            row = conn.execute("""
                SELECT * FROM co_study_invitations WHERE id = ?
            """, (invite_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ==================== 共学交流消息 ====================

    def send_co_study_message(self, invitation_id: int, sender_id: str, content: str) -> Dict[str, Any]:
        """在共学会话中发送消息"""
        now = datetime.now().isoformat()
        conn = _get_conn()
        try:
            inv = conn.execute("""
                SELECT * FROM co_study_invitations WHERE id = ?
            """, (invitation_id,)).fetchone()
            if not inv or inv["status"] != "accepted":
                return {"success": False, "error": "共学会话不存在或未激活"}
            if sender_id not in (inv["inviter_id"], inv["invitee_id"]):
                return {"success": False, "error": "无权发言"}
            conn.execute("""
                INSERT INTO co_study_messages (invitation_id, sender_id, content, created_at)
                VALUES (?, ?, ?, ?)
            """, (invitation_id, sender_id, content, now))
            conn.commit()
            return {"success": True, "message": "消息已发送"}
        finally:
            conn.close()

    def get_co_study_messages(self, invitation_id: int, limit: int = 100) -> List[Dict]:
        """获取共学会话的交流消息"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM co_study_messages
                WHERE invitation_id = ?
                ORDER BY created_at ASC LIMIT ?
            """, (invitation_id, limit)).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def delete_co_study_invitation(self, invitation_id: int, user_id: str) -> Dict[str, Any]:
        """删除共学记录（邀请方或被邀请方均可删除）"""
        conn = _get_conn()
        try:
            row = conn.execute("""
                SELECT * FROM co_study_invitations WHERE id = ?
            """, (invitation_id,)).fetchone()
            if not row:
                return {"success": False, "error": "共学记录不存在"}
            if user_id not in (row["inviter_id"], row["invitee_id"]):
                return {"success": False, "error": "无权删除"}
            conn.execute("DELETE FROM co_study_messages WHERE invitation_id = ?", (invitation_id,))
            conn.execute("DELETE FROM co_study_invitations WHERE id = ?", (invitation_id,))
            conn.commit()
            return {"success": True, "message": "共学记录已删除"}
        finally:
            conn.close()

    @staticmethod
    def _load_pair_problem(user_id: str, problem_id: str) -> Dict[str, Any]:
        """从用户目录加载结对编程题目（与 get_pair_session 共享）"""
        import json as _json, glob as _glob
        from memory.content_store import USER_FEATURES_DIR
        content_dir = str(USER_FEATURES_DIR)

        for p in (f"{content_dir}/{user_id}/content/practice_{problem_id}.json",):
            for m in _glob.glob(p):
                try:
                    with open(m, "r", encoding="utf-8") as f:
                        raw = _json.load(f)
                    data = raw.get("problem", raw)
                    kps = data.get("knowledge_points", [])
                    has_title = data.get("title")
                    has_kps = bool(kps) and not (len(kps) == 1 and kps[0] in ("编程", ""))
                    if has_title and has_kps:
                        return data
                except Exception:
                    continue

        for p in (f"{content_dir}/{user_id}/content/phase_practice_{problem_id}.json",):
            for m in _glob.glob(p):
                try:
                    with open(m, "r", encoding="utf-8") as f:
                        raw = _json.load(f)
                    recs = raw.get("recommendations") or raw.get("problem")
                    if isinstance(recs, list) and recs:
                        inner = recs[0].get("problem") or recs[0]
                        if isinstance(inner, dict) and inner.get("title"):
                            inner_kps = inner.get("knowledge_points", [])
                            if inner_kps and not (len(inner_kps) == 1 and inner_kps[0] in ("编程", "")):
                                return inner
                    elif isinstance(recs, dict) and recs.get("title"):
                        recs_kps = recs.get("knowledge_points", [])
                        if recs_kps and not (len(recs_kps) == 1 and recs_kps[0] in ("编程", "")):
                            return recs
                except Exception:
                    continue

        return {}

    # ==================== 结对编程 ====================

    def get_pair_session(self, invitation_id: int) -> Optional[Dict]:
        """获取结对编程会话（强制从邀请方目录加载题目，确保双方看到同一内容）"""
        import json as _json
        conn = _get_conn()
        try:
            row = conn.execute("""
                SELECT p.*, c.inviter_id, c.invitee_id, c.title as inv_title
                FROM pair_programming_sessions p
                JOIN co_study_invitations c ON p.invitation_id = c.id
                WHERE p.invitation_id = ?
            """, (invitation_id,)).fetchone()
            session = dict(row) if row else None
            if not session:
                return None

            problem_id = session["problem_id"]
            inviter_id = session.get("inviter_id", "")
            inv_title = session.get("inv_title", "")

            # ★★★ 强制从邀请方目录重新加载题目，保证一致性 ★★★
            fresh_problem = self._load_pair_problem(inviter_id, problem_id)

            # 3. ResourceDB 兜底
            if not fresh_problem or not fresh_problem.get("knowledge_points"):
                try:
                    from Agent.children_agent.recommendation.resource_db import ResourceDB
                    q = ResourceDB().get_question(problem_id)
                    if q:
                        raw_kps = q.get("knowledge_points", "").split(",") if q.get("knowledge_points") else []
                        filtered_kps = [kp for kp in raw_kps if kp.strip() and kp.strip() not in ("编程", "")]
                        fresh_problem = {
                            "title": _json.loads(q.get("metadata", "{}")).get("title") if q.get("metadata") else (q.get("topic") or "编程题"),
                            "difficulty": q.get("difficulty", 3),
                            "description": q.get("content", ""),
                            "knowledge_points": filtered_kps,
                            "examples": _json.loads(q.get("metadata", "{}")).get("examples", []) if q.get("metadata") else [],
                            "hints": _json.loads(q.get("hints", "[]")) if isinstance(q.get("hints"), str) else (q.get("hints") or []),
                        }
                except Exception:
                    pass

            # 4. 用 stored 作为后备
            if not fresh_problem or not fresh_problem.get("title"):
                fresh_problem = _json.loads(session.get("problem_data", "{}") or "{}")
                if isinstance(fresh_problem, dict):
                    stored_kps = fresh_problem.get("knowledge_points", [])
                    if stored_kps and not (len(stored_kps) == 1 and stored_kps[0] in ("编程", "")):
                        pass
                    else:
                        fresh_problem["knowledge_points"] = []

            # 5. 标题兜底
            if not fresh_problem.get("title"):
                fresh_problem["title"] = inv_title or "编程题"
            kps = fresh_problem.get("knowledge_points", [])
            if not kps or (len(kps) == 1 and kps[0] in ("编程", "")):
                fresh_problem["knowledge_points"] = []

            session["problem_data"] = fresh_problem
            return session
        except Exception as e:
            print(f"  ⚠️ get_pair_session 失败: {e}")
            return None
        finally:
            conn.close()

    def update_pair_code(self, invitation_id: int, user_id: str, code_content: str, language: str = None) -> Dict[str, Any]:
        """更新结对编程代码（支持更新语言）"""
        conn = _get_conn()
        now = datetime.now().isoformat()
        try:
            session = conn.execute("""
                SELECT * FROM pair_programming_sessions WHERE invitation_id = ?
            """, (invitation_id,)).fetchone()
            session = dict(session) if session else None  # ★★★ 转换为字典，支持 .get() 方法 ★★★
            if not session:
                return {"success": False, "error": "会话不存在"}
            if session["submitted"]:
                return {"success": False, "error": "已提交，无法修改"}
            
            # 如果提供了语言参数，同时更新语言
            if language:
                conn.execute("""
                    UPDATE pair_programming_sessions
                    SET code_content = ?, language = ?, updated_at = ?
                    WHERE invitation_id = ?
                """, (code_content, language, now, invitation_id))
            else:
                conn.execute("""
                    UPDATE pair_programming_sessions
                    SET code_content = ?, updated_at = ?
                    WHERE invitation_id = ?
                """, (code_content, now, invitation_id))
            conn.commit()
            return {"success": True, "message": "代码已更新"}
        finally:
            conn.close()

    def submit_pair_code(self, invitation_id: int, submitter_id: str, language: str = None) -> Dict[str, Any]:
        """提交结对编程代码（结果算提交者的）"""
        import json
        import traceback
        conn = _get_conn()
        now = datetime.now().isoformat()
        print(f"[结对编程] 开始提交评判: invitation_id={invitation_id}, submitter_id={submitter_id}, language={language}")
        try:
            session = conn.execute("""
                SELECT * FROM pair_programming_sessions WHERE invitation_id = ?
            """, (invitation_id,)).fetchone()
            session = dict(session) if session else None  # ★★★ 转换为字典，支持 .get() 方法 ★★★
            if not session:
                print(f"[结对编程] 会话不存在: {invitation_id}")
                return {"success": False, "error": "会话不存在"}
            if session["submitted"]:
                return {"success": False, "error": "已提交过"}

            code = session["code_content"]
            problem_id = session["problem_id"]
            problem_data = json.loads(session["problem_data"] or "{}")

            if not code.strip():
                return {"success": False, "error": "代码为空，请先编写代码"}

            # ★★★ 使用传入的语言，如果没有传入则使用会话中保存的语言 ★★★
            final_language = language or session.get("language", "python")

            try:
                from Agent.children_agent.practice_agent import PracticeAgent
                import asyncio
                import concurrent.futures
                practice_agent = PracticeAgent()
                
                # ★★★ 使用线程执行评判，避免事件循环问题 ★★★
                def run_judge():
                    import threading
                    import queue
                    result_queue = queue.Queue()
                    
                    def _run():
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                result = loop.run_until_complete(
                                    practice_agent.judge_code_async(
                                        problem_id=problem_id,
                                        problem=problem_data,
                                        user_code=code,
                                        language=final_language,
                                        user_id=submitter_id,
                                    )
                                )
                                result_queue.put(("success", result))
                            finally:
                                loop.close()
                        except Exception as e:
                            result_queue.put(("error", e))
                    
                    thread = threading.Thread(target=_run)
                    thread.daemon = True
                    thread.start()
                    thread.join(timeout=120)  # ★★★ 120秒超时 ★★★
                    
                    if thread.is_alive():
                        raise Exception("评判超时，请稍后重试")
                    
                    if result_queue.empty():
                        raise Exception("评判异常，未返回结果")
                    
                    status, data = result_queue.get()
                    if status == "error":
                        raise data
                    return data
                
                print(f"[结对编程] 开始执行评判...")
                result = run_judge()
                print(f"[结对编程] 评判完成，结果: {result}")

                conn.execute("""
                    UPDATE pair_programming_sessions
                    SET submitted = 1, submitter_id = ?, submit_result = ?, updated_at = ?
                    WHERE invitation_id = ?
                """, (submitter_id, json.dumps(result, ensure_ascii=False), now, invitation_id))
                conn.commit()
                return {"success": True, "result": result}
            except Exception as e:
                print(f"[结对编程] 评判失败: {str(e)}")
                traceback.print_exc()
                return {"success": False, "error": f"评判失败: {str(e)}"}
        finally:
            conn.close()

    # ==================== 练习进度对比 ====================

    def compare_practice_results(self, problem_id: str,
                                 user_id_a: str, user_id_b: str) -> Dict[str, Any]:
        """对比两个用户在同一道编程题上的成绩"""
        try:
            from services.leaderboard_service import LeaderboardService
            lb = LeaderboardService()
            score_a = lb.get_user_best_score(problem_id, user_id_a)
            score_b = lb.get_user_best_score(problem_id, user_id_b)

            a_data = {
                "score": score_a.get("score", 0) if score_a else 0,
                "verdict": score_a.get("verdict", "") if score_a else "未作答",
                "passed": score_a.get("passed_tests", "0/0") if score_a else "0/0",
                "submitted_at": score_a.get("submitted_at", "") if score_a else ""
            } if score_a else {"score": 0, "verdict": "未作答", "passed": "0/0"}

            b_data = {
                "score": score_b.get("score", 0) if score_b else 0,
                "verdict": score_b.get("verdict", "") if score_b else "未作答",
                "passed": score_b.get("passed_tests", "0/0") if score_b else "0/0",
                "submitted_at": score_b.get("submitted_at", "") if score_b else ""
            } if score_b else {"score": 0, "verdict": "未作答", "passed": "0/0"}

            winner = None
            if a_data["score"] > b_data["score"]:
                winner = user_id_a
            elif b_data["score"] > a_data["score"]:
                winner = user_id_b
            else:
                winner = "平局"

            return {
                "success": True,
                "problem_id": problem_id,
                "user_a": user_id_a,
                "user_b": user_id_b,
                "a_result": a_data,
                "b_result": b_data,
                "winner": winner
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== 记录学习活动（供前端调用） ====================

    def record_user_activity(self, user_id: str, task_type: str,
                             task_detail: str = "", topic: str = "") -> Dict[str, Any]:
        """记录用户当前学习活动到工作记忆"""
        try:
            from memory.memory_hub import MemoryHub
            hub = MemoryHub()
            if task_type:
                hub.working.set_current_task(user_id, task_type, task_detail)
            if topic:
                hub.working.set_current_topic(user_id, topic)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
