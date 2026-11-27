"""
group_service.py - 学习小组 + 比赛系统服务

功能：
1. 小组管理：创建/加入/退出/解散
2. 小组聊天：文本消息 + 图片上传(OSS)
3. 比赛管理：创建比赛/生成赛题/开启/结束
4. 比赛排行：ACM 风格实时排名（得分 + 罚时）
"""

import json
import sqlite3
import uuid
import math
import threading
import random
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

DB_PATH = Path(__file__).parent.parent / "recommendation_data" / "companion.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _get_conn()
    # --- 小组表 ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_groups (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL,
            description     TEXT DEFAULT '',
            avatar_url      TEXT DEFAULT '',
            creator_id      TEXT NOT NULL,
            max_members     INTEGER DEFAULT 50,
            created_at      TEXT NOT NULL
        )
    """)
    # --- 小组成员表 ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id        INTEGER NOT NULL,
            user_id         TEXT NOT NULL,
            role            TEXT DEFAULT 'member',  -- owner / admin / member
            joined_at       TEXT NOT NULL,
            UNIQUE(group_id, user_id)
        )
    """)
    # --- 小组消息表（支持图片） ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id        INTEGER NOT NULL,
            sender_id       TEXT NOT NULL,
            msg_type        TEXT DEFAULT 'text',  -- text / image
            content         TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )
    """)
    # --- 比赛表 ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_competitions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id        INTEGER NOT NULL,
            title           TEXT NOT NULL,
            description     TEXT DEFAULT '',
            status          TEXT DEFAULT 'pending',  -- pending / running / finished
            start_at        TEXT,
            end_at          TEXT,
            created_by      TEXT NOT NULL,
            created_at      TEXT NOT NULL
        )
    """)
    # --- 比赛题目表 ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS competition_problems (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id  INTEGER NOT NULL,
            problem_index   INTEGER NOT NULL,       -- 题号 A/B/C/D...
            title           TEXT NOT NULL,
            description     TEXT NOT NULL,
            difficulty      TEXT DEFAULT '中等',
            score           INTEGER DEFAULT 100,
            created_at      TEXT NOT NULL
        )
    """)
    # --- 比赛提交记录表 ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS competition_submissions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id  INTEGER NOT NULL,
            problem_id      INTEGER NOT NULL,
            user_id         TEXT NOT NULL,
            score           INTEGER DEFAULT 0,
            passed          INTEGER DEFAULT 0,      -- 通过数
            total_tests     INTEGER DEFAULT 0,
            time_cost_sec   INTEGER DEFAULT 0,      -- 耗时（秒）
            status          TEXT DEFAULT 'pending',  -- pending / accepted / wrong / partial
            submitted_at    TEXT NOT NULL,
            UNIQUE(problem_id, user_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gm_group ON group_members(group_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gm_user ON group_members(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gmsg_group ON group_messages(group_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gc_group ON group_competitions(group_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cp_comp ON competition_problems(competition_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cs_comp ON competition_submissions(competition_id)")
    # --- 小组邀请表（私密小组用） ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS group_invitations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id        INTEGER NOT NULL,
            inviter_id      TEXT NOT NULL,
            invitee_id      TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',  -- pending / accepted / rejected
            created_at      TEXT NOT NULL,
            responded_at    TEXT,
            UNIQUE(group_id, invitee_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gi_group ON group_invitations(group_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gi_invitee ON group_invitations(invitee_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cs_user ON competition_submissions(user_id)")
    # 兼容：给已有 study_groups 表添加 is_public 列
    try:
        conn.execute("ALTER TABLE study_groups ADD COLUMN is_public INTEGER DEFAULT 1")
    except Exception:
        pass
    conn.commit()
    conn.close()


_init_db()


def _now() -> str:
    """返回 UTC 时间的 ISO 格式字符串，与前端传的 start_at/end_at 一致"""
    return datetime.utcnow().isoformat() + 'Z'


def _get_letter_index(i: int) -> str:
    """0 -> A, 1 -> B, ... 25 -> Z"""
    return chr(65 + i)


class GroupService:
    """学习小组 + 比赛服务"""

    # ==================== 小组管理 ====================

    def create_group(self, name: str, creator_id: str, description: str = "",
                     max_members: int = 50, is_public: bool = True) -> Dict[str, Any]:
        """创建小组（is_public=True 公开，False 私密）"""
        now = _now()
        conn = _get_conn()
        try:
            cur = conn.execute("""
                INSERT INTO study_groups (name, description, creator_id, max_members, is_public, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, description, creator_id, max_members, 1 if is_public else 0, now))
            group_id = cur.lastrowid
            conn.execute("""
                INSERT INTO group_members (group_id, user_id, role, joined_at)
                VALUES (?, ?, 'owner', ?)
            """, (group_id, creator_id, now))
            conn.commit()
            return {"success": True, "group_id": group_id, "name": name,
                    "is_public": is_public}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def join_group(self, group_id: int, user_id: str) -> Dict[str, Any]:
        """加入小组（私密小组不允许自由加入）"""
        now = _now()
        conn = _get_conn()
        try:
            group = conn.execute("SELECT * FROM study_groups WHERE id = ?",
                                 (group_id,)).fetchone()
            if not group:
                return {"success": False, "error": "小组不存在"}
            # 私密小组禁止自由加入
            if not dict(group).get("is_public", 1):
                return {"success": False, "error": "该小组为私密小组，需要群主邀请才能加入",
                        "need_invite": True}
            count = conn.execute("""
                SELECT COUNT(*) as cnt FROM group_members WHERE group_id = ?
            """, (group_id,)).fetchone()["cnt"]
            if count >= group["max_members"]:
                return {"success": False, "error": "小组已满"}
            try:
                conn.execute("""
                    INSERT INTO group_members (group_id, user_id, role, joined_at)
                    VALUES (?, ?, 'member', ?)
                """, (group_id, user_id, now))
                conn.commit()
                return {"success": True, "message": "已加入小组"}
            except sqlite3.IntegrityError:
                return {"success": False, "error": "已在该小组中"}
        finally:
            conn.close()

    def leave_group(self, group_id: int, user_id: str) -> Dict[str, Any]:
        """退出小组"""
        conn = _get_conn()
        try:
            member = conn.execute("""
                SELECT * FROM group_members WHERE group_id = ? AND user_id = ?
            """, (group_id, user_id)).fetchone()
            if not member:
                return {"success": False, "error": "不在该小组中"}
            if member["role"] == "owner":
                return {"success": False, "error": "创建者不能退出，请先转让或解散小组"}
            conn.execute("DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
                         (group_id, user_id))
            conn.commit()
            return {"success": True, "message": "已退出小组"}
        finally:
            conn.close()

    def dissolve_group(self, group_id: int, user_id: str) -> Dict[str, Any]:
        """解散小组（仅创建者）"""
        conn = _get_conn()
        try:
            member = conn.execute("""
                SELECT * FROM group_members WHERE group_id = ? AND user_id = ? AND role = 'owner'
            """, (group_id, user_id)).fetchone()
            if not member:
                return {"success": False, "error": "只有创建者可以解散小组"}
            # 级联删除
            conn.execute("DELETE FROM competition_submissions WHERE competition_id IN "
                         "(SELECT id FROM group_competitions WHERE group_id = ?)", (group_id,))
            conn.execute("DELETE FROM competition_problems WHERE competition_id IN "
                         "(SELECT id FROM group_competitions WHERE group_id = ?)", (group_id,))
            conn.execute("DELETE FROM group_competitions WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_messages WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
            conn.execute("DELETE FROM study_groups WHERE id = ?", (group_id,))
            conn.commit()
            return {"success": True, "message": "小组已解散"}
        finally:
            conn.close()

    def list_user_groups(self, user_id: str) -> List[Dict]:
        """获取用户加入的所有小组"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT g.*, gm.role,
                       (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count
                FROM study_groups g
                JOIN group_members gm ON g.id = gm.group_id
                WHERE gm.user_id = ?
                ORDER BY g.created_at DESC
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_group_detail(self, group_id: int) -> Optional[Dict]:
        """获取小组详情（含成员列表）"""
        conn = _get_conn()
        try:
            group = conn.execute("""
                SELECT g.*,
                       (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count
                FROM study_groups g WHERE g.id = ?
            """, (group_id,)).fetchone()
            if not group:
                return None
            result = dict(group)
            members = conn.execute("""
                SELECT user_id, role, joined_at FROM group_members
                WHERE group_id = ? ORDER BY joined_at ASC
            """, (group_id,)).fetchall()
            result["members"] = [dict(m) for m in members]
            return result
        finally:
            conn.close()

    def list_all_groups(self) -> List[Dict]:
        """获取所有公开可见小组（发现页用）"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT g.*,
                       (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count
                FROM study_groups g
                WHERE g.is_public = 1
                ORDER BY member_count DESC, g.created_at DESC
                LIMIT 50
            """).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ==================== 小组邀请（私密小组）====================

    def invite_to_group(self, group_id: int, inviter_id: str, invitee_id: str) -> Dict[str, Any]:
        """邀请用户加入小组
        - 公开小组：任何成员均可邀请
        - 私密小组：仅 owner/admin 可邀请
        """
        now = _now()
        conn = _get_conn()
        try:
            group = conn.execute("SELECT * FROM study_groups WHERE id = ?", (group_id,)).fetchone()
            if not group:
                return {"success": False, "error": "小组不存在"}

            # 检查邀请者是否是小组成员
            member = conn.execute("""
                SELECT * FROM group_members WHERE group_id = ? AND user_id = ?
            """, (group_id, inviter_id)).fetchone()
            if not member:
                return {"success": False, "error": "你不是该小组成员，无法邀请"}

            # 权限判断：私密小组仅 owner/admin，公开小组任何成员均可
            g = dict(group)
            is_public = g.get("is_public", 1)
            if not is_public and member["role"] not in ("owner", "admin"):
                return {"success": False, "error": "私密小组仅组长或管理员可以邀请"}

            # 检查是否已加入
            existing = conn.execute("""
                SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?
            """, (group_id, invitee_id)).fetchone()
            if existing:
                return {"success": False, "error": "该用户已是小组成员"}

            # 检查人数上限
            count = conn.execute("""
                SELECT COUNT(*) as cnt FROM group_members WHERE group_id = ?
            """, (group_id,)).fetchone()["cnt"]
            if count >= group["max_members"]:
                return {"success": False, "error": "小组已满"}

            # 插入或更新邀请（允许重新邀请）
            existing_inv = conn.execute("""
                SELECT * FROM group_invitations
                WHERE group_id = ? AND invitee_id = ?
            """, (group_id, invitee_id)).fetchone()
            if existing_inv:
                if existing_inv["status"] == "pending":
                    return {"success": False, "error": "已向该用户发送过邀请，等待回应"}
                conn.execute("""
                    UPDATE group_invitations SET status = 'pending', responded_at = NULL, created_at = ?
                    WHERE id = ?
                """, (now, existing_inv["id"]))
            else:
                conn.execute("""
                    INSERT INTO group_invitations (group_id, inviter_id, invitee_id, status, created_at)
                    VALUES (?, ?, ?, 'pending', ?)
                """, (group_id, inviter_id, invitee_id, now))
            conn.commit()
            return {"success": True, "message": f"已邀请 {invitee_id} 加入小组"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def respond_group_invite(self, invitation_id: int, invitee_id: str, accept: bool) -> Dict[str, Any]:
        """接受/拒绝小组邀请"""
        conn = _get_conn()
        now = _now()
        try:
            inv = conn.execute("""
                SELECT * FROM group_invitations WHERE id = ?
            """, (invitation_id,)).fetchone()
            if not inv:
                return {"success": False, "error": "邀请不存在"}
            if inv["invitee_id"] != invitee_id:
                return {"success": False, "error": "无权操作"}
            if inv["status"] != "pending":
                return {"success": False, "error": "邀请已处理"}

            conn.execute("""
                UPDATE group_invitations SET status = ?, responded_at = ? WHERE id = ?
            """, ("accepted" if accept else "rejected", now, invitation_id))

            if accept:
                # 检查人数上限
                group = conn.execute("SELECT * FROM study_groups WHERE id = ?",
                                     (inv["group_id"],)).fetchone()
                if group:
                    count = conn.execute("""
                        SELECT COUNT(*) as cnt FROM group_members WHERE group_id = ?
                    """, (inv["group_id"],)).fetchone()["cnt"]
                    if count >= group["max_members"]:
                        return {"success": False, "error": "小组已满"}
                conn.execute("""
                    INSERT OR IGNORE INTO group_members (group_id, user_id, role, joined_at)
                    VALUES (?, ?, 'member', ?)
                """, (inv["group_id"], invitee_id, now))

            conn.commit()
            return {"success": True, "message": "已接受邀请" if accept else "已拒绝邀请",
                    "group_id": inv["group_id"]}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def get_pending_group_invites(self, user_id: str) -> List[Dict]:
        """获取用户待处理的入组邀请"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT gi.*, g.name as group_name, g.description as group_desc,
                       (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) as member_count
                FROM group_invitations gi
                JOIN study_groups g ON gi.group_id = g.id
                WHERE gi.invitee_id = ? AND gi.status = 'pending'
                ORDER BY gi.created_at DESC
            """, (user_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_group_invitations(self, group_id: int) -> List[Dict]:
        """获取小组所有待处理的邀请（owner/admin 查看）"""
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM group_invitations
                WHERE group_id = ? AND status = 'pending'
                ORDER BY created_at DESC
            """, (group_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ==================== 小组聊天 ====================

    def send_message(self, group_id: int, sender_id: str, content: str,
                     msg_type: str = "text") -> Dict[str, Any]:
        """发送消息（文本/图片）"""
        conn = _get_conn()
        now = _now()
        try:
            member = conn.execute("""
                SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?
            """, (group_id, sender_id)).fetchone()
            if not member:
                return {"success": False, "error": "不在该小组中"}
            conn.execute("""
                INSERT INTO group_messages (group_id, sender_id, msg_type, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (group_id, sender_id, msg_type, content, now))
            conn.commit()
            return {"success": True, "message": "发送成功"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def get_messages(self, group_id: int, limit: int = 50,
                     before_id: Optional[int] = None) -> List[Dict]:
        """获取聊天消息"""
        conn = _get_conn()
        try:
            if before_id:
                rows = conn.execute("""
                    SELECT * FROM group_messages
                    WHERE group_id = ? AND id < ?
                    ORDER BY id DESC LIMIT ?
                """, (group_id, before_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM group_messages
                    WHERE group_id = ?
                    ORDER BY id DESC LIMIT ?
                """, (group_id, limit)).fetchall()
            result = [dict(r) for r in rows]
            result.reverse()
            return result
        finally:
            conn.close()

    # ==================== 自动开始比赛 ====================

    def _auto_start_competitions(self):
        """检查所有待开始的比赛，到达开始时间自动设为 running"""
        try:
            conn = _get_conn()
            now = _now()
            conn.execute("""
                UPDATE group_competitions
                SET status = 'running', start_at = COALESCE(start_at, ?)
                WHERE status = 'pending' AND start_at IS NOT NULL AND start_at <= ?
            """, (now, now))
            # 同时自动结束已过期的比赛
            conn.execute("""
                UPDATE group_competitions
                SET status = 'finished', end_at = ?
                WHERE status = 'running' AND end_at IS NOT NULL AND end_at <= ?
            """, (now, now))
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ==================== 比赛管理 ====================

    def create_competition(self, group_id: int, title: str, created_by: str,
                           description: str = "",
                           problem_count: int = 3,
                           start_at: Optional[str] = None,
                           end_at: Optional[str] = None) -> Dict[str, Any]:
        """创建比赛（仅owner/admin），可指定开始/结束时间"""
        conn = _get_conn()
        now = _now()
        try:
            member = conn.execute("""
                SELECT * FROM group_members WHERE group_id = ? AND user_id = ? AND role IN ('owner','admin')
            """, (group_id, created_by)).fetchone()
            if not member:
                return {"success": False, "error": "只有组长或管理员可以创建比赛"}

            # 如果提供了开始时间且在现在或之前，自动开始
            status = 'pending'
            final_start = start_at
            final_end = end_at
            if start_at and start_at <= now:
                status = 'running'
            if not end_at and start_at:
                # 默认2小时
                import datetime as dtmod
                end_dt = dtmod.datetime.fromisoformat(start_at) + timedelta(hours=2)
                final_end = end_dt.isoformat()

            cur = conn.execute("""
                INSERT INTO group_competitions (group_id, title, description, status, created_by, start_at, end_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (group_id, title, description, status, created_by, final_start, final_end, now))
            competition_id = cur.lastrowid
            conn.commit()
            return {
                "success": True, "competition_id": competition_id,
                "status": status,
                "message": "比赛已创建，请继续生成赛题"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def update_competition(self, competition_id: int, user_id: str,
                           title: Optional[str] = None,
                           description: Optional[str] = None,
                           start_at: Optional[str] = None,
                           end_at: Optional[str] = None) -> Dict[str, Any]:
        """更新比赛基本信息（仅创建者，仅 pending 状态可修改）"""
        conn = _get_conn()
        try:
            comp = conn.execute("""
                SELECT * FROM group_competitions WHERE id = ?
            """, (competition_id,)).fetchone()
            if not comp:
                return {"success": False, "error": "比赛不存在"}
            if comp["created_by"] != user_id:
                return {"success": False, "error": "只有比赛创建者可以修改"}
            if comp["status"] != "pending":
                return {"success": False, "error": "比赛已开始或已结束，无法修改"}

            updates = {}
            if title is not None:
                updates["title"] = title
            if description is not None:
                updates["description"] = description
            if start_at is not None:
                updates["start_at"] = start_at
            if end_at is not None:
                updates["end_at"] = end_at

            if not updates:
                return {"success": False, "error": "没有需要更新的字段"}

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(competition_id)
            conn.execute(f"UPDATE group_competitions SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return {"success": True, "message": "比赛已更新"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def generate_problems(self, competition_id: int, user_id: str,
                          input_text: str, problem_count: int = 3) -> Dict[str, Any]:
        """根据用户输入生成比赛赛题"""
        conn = _get_conn()
        now = _now()
        try:
            comp = conn.execute("""
                SELECT * FROM group_competitions WHERE id = ?
            """, (competition_id,)).fetchone()
            if not comp:
                return {"success": False, "error": "比赛不存在"}
            if comp["status"] == "finished":
                return {"success": False, "error": "比赛已结束，无法修改赛题"}

            # 用 LLM 生成题目，覆盖旧题
            problems = self._ai_generate_problems(input_text, problem_count)

            conn.execute("DELETE FROM competition_problems WHERE competition_id = ?",
                         (competition_id,))
            for i, p in enumerate(problems):
                conn.execute("""
                    INSERT INTO competition_problems
                        (competition_id, problem_index, title, description, difficulty, score, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (competition_id, i, p["title"], p["description"],
                      p.get("difficulty", "中等"), p.get("score", 100), now))
            conn.commit()
            return {"success": True, "problems": problems, "count": len(problems)}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def save_problems_manual(self, competition_id: int, user_id: str,
                              problems: List[Dict], replace: bool = True) -> Dict[str, Any]:
        """手动保存赛题
        - replace=True: 覆盖旧题（AI生成用）
        - replace=False: 追加到末尾（手动添加用）
        """
        conn = _get_conn()
        now = _now()
        try:
            comp = conn.execute("""
                SELECT * FROM group_competitions WHERE id = ?
            """, (competition_id,)).fetchone()
            if not comp:
                return {"success": False, "error": "比赛不存在"}
            if comp["created_by"] != user_id:
                return {"success": False, "error": "只有比赛创建者可以设置赛题"}
            if comp["status"] == "finished":
                return {"success": False, "error": "比赛已结束，无法修改赛题"}

            if not problems or not isinstance(problems, list):
                return {"success": False, "error": "题目列表为空"}

            # 校验每题的必要字段
            for i, p in enumerate(problems):
                if not p.get("title") or not p.get("description"):
                    return {"success": False, "error": f"第 {i+1} 题缺少标题(title)或描述(description)"}
                p.setdefault("difficulty", "中等")
                p.setdefault("score", 100)

            if replace:
                # 覆盖：删除旧题，写入新题
                conn.execute("DELETE FROM competition_problems WHERE competition_id = ?",
                             (competition_id,))
                start_index = 0
            else:
                # 追加：获取当前最大索引
                max_idx = conn.execute("""
                    SELECT COALESCE(MAX(problem_index), -1) as mi FROM competition_problems WHERE competition_id = ?
                """, (competition_id,)).fetchone()["mi"]
                start_index = max_idx + 1

            for i, p in enumerate(problems):
                conn.execute("""
                    INSERT INTO competition_problems
                        (competition_id, problem_index, title, description, difficulty, score, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (competition_id, start_index + i, p["title"], p["description"],
                      p.get("difficulty", "中等"), p.get("score", 100), now))
            conn.commit()
            return {"success": True, "problems": problems, "count": len(problems)}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def _ai_generate_problems(self, input_text: str, count: int = 3) -> List[Dict]:
        """
        基于用户输入用 AI 生成赛题。
        使用大模型生成高质量题目，失败则用模板兜底。
        """
        # 优先尝试用 LLM 生成
        try:
            from utils.llm_config import get_chat_openai
            import asyncio
            import json
            import re

            llm = get_chat_openai(temperature=0.7, max_tokens=4096, timeout=120)

            prompt = f"""你是一个编程竞赛出题专家。请根据主题「{input_text}」生成 {count} 道编程题目。

要求：
1. 每道题包含标题(title)、题目描述(description)、难度(difficulty 可选 简单/中等/困难)、分值(score 默认100)
2. 题目从易到难排列
3. 题目描述要清晰完整，包含输入输出说明和示例
4. 返回纯 JSON 数组，不要 markdown 包裹

示例格式：
[
  {{"title": "两数之和", "description": "给定一个整数数组和一个目标值...", "difficulty": "简单", "score": 100}},
  ...
]"""

            import concurrent.futures

            def _run_llm():
                """在独立线程中运行 LLM 调用，避免事件循环冲突"""
                inner_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(inner_loop)
                try:
                    return inner_loop.run_until_complete(llm.ainvoke(prompt))
                finally:
                    inner_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(_run_llm)
                response = future.result(timeout=120)

            raw = response.content if hasattr(response, 'content') else str(response)
            # 提取 JSON
            json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', raw, re.DOTALL)
            if json_match:
                raw = json_match.group(1).strip()
            problems = json.loads(raw)
            if isinstance(problems, list) and len(problems) >= 1:
                valid = []
                for p in problems:
                    if p.get("title") and p.get("description"):
                        p.setdefault("difficulty", "中等")
                        p.setdefault("score", 100)
                        valid.append(p)
                if valid:
                    return valid[:count]
        except Exception as e:
            print(f"  ⚠️ LLM 生成赛题失败，使用模板兜底: {e}")

        # 兜底：使用模板
        topics = [
            ("数组求和", "给定一个整数数组 nums 和一个目标值 target，请找出数组中两个数的和等于 target 的索引。"),
            ("字符串反转", "给定一个字符串，将其按照单词为单位进行反转，单词内部字符顺序不变。"),
            ("排序去重", "给定一个包含重复元素的整数数组，请去除重复元素并按升序输出。"),
            ("最大子数组", "给定一个整数数组，找出一个具有最大和的连续子数组。"),
            ("斐波那契", "编写一个函数计算斐波那契数列的第 n 项。"),
            ("括号匹配", "给定一个只包含 '(' 和 ')' 的字符串，判断括号是否匹配。"),
            ("链表反转", "反转一个单向链表。"),
            ("二分查找", "在有序数组中查找目标值的索引，不存在返回 -1。"),
        ]
        random.shuffle(topics)
        problems = []
        for i in range(count):
            idx = i % len(topics)
            t, d = topics[idx]
            problems.append({
                "title": f"{_get_letter_index(i)}. {t}",
                "description": d,
                "difficulty": ["简单", "中等", "困难"][i % 3],
                "score": 100,
            })
        return problems

    def start_competition(self, competition_id: int, user_id: str) -> Dict[str, Any]:
        """开始比赛（使用预设的 end_at，未设置则默认2小时）"""
        conn = _get_conn()
        now = _now()
        try:
            comp = conn.execute("""
                SELECT c.*, g.name as group_name
                FROM group_competitions c
                JOIN study_groups g ON c.group_id = g.id
                WHERE c.id = ?
            """, (competition_id,)).fetchone()
            if not comp:
                return {"success": False, "error": "比赛不存在"}
            if comp["created_by"] != user_id:
                return {"success": False, "error": "只有比赛创建者可以开始"}
            if comp["status"] != "pending":
                return {"success": False, "error": "比赛已开始或已结束"}

            # 检查是否有题目
            problem_count = conn.execute("""
                SELECT COUNT(*) as cnt FROM competition_problems WHERE competition_id = ?
            """, (competition_id,)).fetchone()["cnt"]
            if problem_count == 0:
                return {"success": False, "error": "比赛暂无题目，请先生成赛题"}

            # 使用预设的开始/结束时间，未设置则用当前时间
            stored_start = dict(comp).get("start_at")
            stored_end = dict(comp).get("end_at")
            final_start = stored_start if stored_start else now
            final_end = stored_end if stored_end else (datetime.utcnow() + timedelta(hours=2)).isoformat() + 'Z'
            conn.execute("""
                UPDATE group_competitions SET status = 'running', start_at = ?, end_at = ?
                WHERE id = ?
            """, (final_start, final_end, competition_id))
            conn.commit()
            return {
                "success": True, "message": "比赛已开始",
                "start_at": final_start, "end_at": final_end
            }
        finally:
            conn.close()

    def end_competition(self, competition_id: int, user_id: str) -> Dict[str, Any]:
        """结束比赛"""
        conn = _get_conn()
        now = _now()
        try:
            comp = conn.execute("""
                SELECT * FROM group_competitions WHERE id = ?
            """, (competition_id,)).fetchone()
            if not comp:
                return {"success": False, "error": "比赛不存在"}
            if comp["created_by"] != user_id:
                return {"success": False, "error": "只有比赛创建者可以结束"}
            conn.execute("""
                UPDATE group_competitions SET status = 'finished', end_at = ? WHERE id = ?
            """, (now, competition_id))
            conn.commit()
            return {"success": True, "message": "比赛已结束"}
        finally:
            conn.close()

    def delete_competition(self, competition_id: int, user_id: str) -> Dict[str, Any]:
        """删除比赛（仅创建者，级联删除题目和提交记录）"""
        conn = _get_conn()
        try:
            comp = conn.execute("""
                SELECT * FROM group_competitions WHERE id = ?
            """, (competition_id,)).fetchone()
            if not comp:
                return {"success": False, "error": "比赛不存在"}
            if comp["created_by"] != user_id:
                return {"success": False, "error": "只有比赛创建者可以删除"}
            conn.execute("DELETE FROM competition_submissions WHERE competition_id = ?", (competition_id,))
            conn.execute("DELETE FROM competition_problems WHERE competition_id = ?", (competition_id,))
            conn.execute("DELETE FROM group_competitions WHERE id = ?", (competition_id,))
            conn.commit()
            return {"success": True, "message": "比赛已删除"}
        finally:
            conn.close()

    def get_competitions(self, group_id: int) -> List[Dict]:
        """获取小组的所有比赛（自动启动已到开始时间的比赛）"""
        self._auto_start_competitions()
        conn = _get_conn()
        try:
            rows = conn.execute("""
                SELECT c.*,
                       (SELECT COUNT(*) FROM competition_problems WHERE competition_id = c.id) as problem_count
                FROM group_competitions c
                WHERE c.group_id = ?
                ORDER BY c.created_at DESC
            """, (group_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_competition_detail(self, competition_id: int) -> Optional[Dict]:
        """获取比赛详情（含题目，自动启动已到开始时间的比赛）"""
        self._auto_start_competitions()
        conn = _get_conn()
        try:
            comp = conn.execute("""
                SELECT * FROM group_competitions WHERE id = ?
            """, (competition_id,)).fetchone()
            if not comp:
                return None
            result = dict(comp)
            problems = conn.execute("""
                SELECT * FROM competition_problems
                WHERE competition_id = ? ORDER BY problem_index ASC
            """, (competition_id,)).fetchall()
            result["problems"] = [dict(p) for p in problems]
            return result
        finally:
            conn.close()

    # ==================== 比赛提交/判分 ====================

    def submit_solution(self, competition_id: int, problem_id: int,
                        user_id: str, answer_text: str) -> Dict[str, Any]:
        """提交答案并使用 PracticeAgent 评分"""
        conn = _get_conn()
        now = _now()
        try:
            comp = conn.execute("""
                SELECT * FROM group_competitions WHERE id = ?
            """, (competition_id,)).fetchone()
            if not comp or comp["status"] != "running":
                return {"success": False, "error": "比赛未在进行中"}

            member = conn.execute("""
                SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?
            """, (comp["group_id"], user_id)).fetchone()
            if not member:
                return {"success": False, "error": "你不是该小组成员"}

            problem = conn.execute("""
                SELECT * FROM competition_problems WHERE id = ? AND competition_id = ?
            """, (problem_id, competition_id)).fetchone()
            if not problem:
                return {"success": False, "error": "题目不存在"}

            # 构造题目数据结构，供 PracticeAgent 使用
            problem_data = {
                "problem_id": f"comp_{competition_id}_{problem_id}",
                "title": problem["title"],
                "description": problem["description"],
                "difficulty": problem["difficulty"],
                "knowledge_points": ["编程"],
            }

            # 调用 PracticeAgent 评判
            score = 0
            passed = 0
            total = 5
            verdict = "Wrong"
            judge_detail = {}

            try:
                import asyncio
                from Agent.children_agent.practice_agent import PracticeAgent

                def _run_judge():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        agent = PracticeAgent()
                        result = loop.run_until_complete(
                            agent.judge_code_async(
                                problem_id=problem_data["problem_id"],
                                problem=problem_data,
                                user_code=answer_text,
                                language="python",
                                user_id=user_id,
                            )
                        )
                        return result
                    finally:
                        loop.close()

                # 在线程中执行异步评判，超时120秒
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(_run_judge)
                    result = future.result(timeout=120)

                if result:
                    score = result.get("score", 0)
                    passed = result.get("passed_tests", 0)
                    total = result.get("total_tests", 5)
                    verdict = result.get("verdict", "Wrong")
                    judge_detail = result.get("analysis", {})
            except Exception as e:
                print(f"  ⚠️ PracticeAgent 评判失败，使用规则兜底: {e}")
                score, passed, total = self._auto_judge(problem["description"], answer_text)
                verdict = "Accepted" if passed == total else "Partial" if passed > 0 else "Wrong"

            # 计算耗时（从比赛开始到提交）
            start_str = comp["start_at"].replace('Z', '') if comp["start_at"] else now
            start = datetime.fromisoformat(start_str)
            elapsed = int((datetime.now() - start).total_seconds())

            # 状态映射
            status = "accepted" if verdict.lower() == "accepted" else "partial" if passed > 0 else "wrong"

            # 更新或插入提交记录
            existing = conn.execute("""
                SELECT id, score FROM competition_submissions
                WHERE problem_id = ? AND user_id = ?
            """, (problem_id, user_id)).fetchone()

            if existing:
                if score > existing["score"]:
                    conn.execute("""
                        UPDATE competition_submissions SET score = ?, passed = ?,
                            total_tests = ?, time_cost_sec = ?, status = ?, submitted_at = ?
                        WHERE id = ?
                    """, (score, passed, total, elapsed, status, now, existing["id"]))
            else:
                conn.execute("""
                    INSERT INTO competition_submissions
                        (competition_id, problem_id, user_id, score, passed, total_tests,
                         time_cost_sec, status, submitted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (competition_id, problem_id, user_id, score, passed, total,
                      elapsed, status, now))
            conn.commit()
            return {
                "success": True, "score": score,
                "passed": passed, "total": total,
                "status": status,
                "detail": judge_detail,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            conn.close()

    def _auto_judge(self, problem_desc: str, answer: str) -> Tuple[int, int, int]:
        """
        自动评分的简化实现。
        实际生产环境应接入代码执行沙箱 + 测试用例。
        这里用启发式规则模拟评分。
        """
        answer = answer.strip()
        if not answer:
            return (0, 0, 5)

        total = 5
        passed = 0

        # 规则1：答案有合理长度
        if len(answer) >= 20:
            passed += 1
        # 规则2：包含代码相关关键词
        code_keywords = ["def ", "function", "class", "import", "for ", "while ", "if ", "return",
                         "int ", "float ", "string", "var ", "let ", "const"]
        if any(kw in answer for kw in code_keywords):
            passed += 2
        # 规则3：包含注释或说明
        if "#" in answer or "//" in answer or "/*" in answer or "说明" in answer:
            passed += 1
        # 规则4：结构性完整（有成对括号/花括号）
        if answer.count("{") == answer.count("}") and answer.count("(") == answer.count(")"):
            passed += 1

        score = int((passed / total) * 100)
        return (score, passed, total)

    # ==================== 实时排行 ====================

    def get_ranking(self, competition_id: int) -> List[Dict]:
        """
        获取比赛实时排行（ACM 风格）
        按总得分降序，总罚时升序排列
        """
        conn = _get_conn()
        try:
            comp = conn.execute("""
                SELECT * FROM group_competitions WHERE id = ?
            """, (competition_id,)).fetchone()
            if not comp:
                return []

            problems = conn.execute("""
                SELECT id, problem_index, title FROM competition_problems
                WHERE competition_id = ? ORDER BY problem_index ASC
            """, (competition_id,)).fetchall()

            members = conn.execute("""
                SELECT user_id FROM group_members WHERE group_id = ?
            """, (comp["group_id"],)).fetchall()

            # 构建每个用户的提交记录
            submissions = conn.execute("""
                SELECT * FROM competition_submissions
                WHERE competition_id = ?
            """, (competition_id,)).fetchall()

            problem_map = {p["id"]: {"index": p["problem_index"], "title": p["title"]}
                          for p in problems}

            user_stats = {}
            for m in members:
                uid = m["user_id"]
                user_stats[uid] = {
                    "user_id": uid,
                    "total_score": 0,
                    "total_penalty": 0,  # 罚时秒数
                    "solved": 0,
                    "problems": {},
                }

            for s in submissions:
                uid = s["user_id"]
                if uid not in user_stats:
                    continue
                p_info = problem_map.get(s["problem_id"])
                if not p_info:
                    continue
                pid = s["problem_id"]
                p_idx = p_info["index"]
                letter = _get_letter_index(p_idx)

                # 只取最高分
                if pid not in user_stats[uid]["problems"] or \
                   s["score"] > user_stats[uid]["problems"][pid]["score"]:
                    user_stats[uid]["problems"][pid] = {
                        "letter": letter,
                        "score": s["score"],
                        "time_cost": s["time_cost_sec"],
                        "status": s["status"],
                    }

            # 计算总和
            for uid, stats in user_stats.items():
                for pid, pdata in stats["problems"].items():
                    if pdata["status"] == "accepted" and pdata["score"] >= 80:
                        stats["solved"] += 1
                        stats["total_penalty"] += pdata["time_cost"]
                    stats["total_score"] += pdata["score"]

            # 排序
            ranked = sorted(user_stats.values(),
                           key=lambda x: (-x["total_score"], x["total_penalty"]))

            # 添加排名
            for i, r in enumerate(ranked):
                r["rank"] = i + 1
                # 转 problems 为列表
                r["problem_list"] = list(r["problems"].values())
                del r["problems"]

            return ranked
        finally:
            conn.close()
