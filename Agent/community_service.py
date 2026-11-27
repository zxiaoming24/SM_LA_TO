"""
community_service.py - 学习社区服务

提供类似论坛的社区功能：
1. 发布学习困惑/分享
2. 回复帖子（支持嵌套回复）
3. 帖子列表与搜索
4. 用户维度特征与社区行为关联

数据库路径: ./community_data/community.db
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


DB_PATH = Path("./community_data/community.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# 用户特征存储路径
USER_FEATURES_PATH = Path("./user_features")


def _validate_user(user_id: str) -> bool:
    """验证用户是否存在于用户特征库中"""
    if not user_id:
        return False
    feature_file = USER_FEATURES_PATH / f"{user_id}.json"
    return feature_file.exists()


from contextlib import contextmanager

@contextmanager
def _get_conn():
    """获取数据库连接（上下文管理器），退出时自动 commit 并关闭连接"""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==================== 社区区域定义 ====================

COMMUNITY_ZONES = {
    "learning": {
        "id": "learning",
        "name": "学习区",
        "description": "学习困惑、知识点讨论、作业帮助",
        "tags": ["学习", "编程", "算法", "知识点", "作业", "考试"]
    },
    "life": {
        "id": "life",
        "name": "生活区",
        "description": "日常生活分享、校园生活、闲谈",
        "tags": ["生活", "日常", "校园", "闲聊"]
    },
    "resource": {
        "id": "resource",
        "name": "资源共享区",
        "description": "学习资料、工具推荐、资源分享",
        "tags": ["资源", "资料", "工具", "推荐", "分享"]
    },
    "feedback": {
        "id": "feedback",
        "name": "反馈建议区",
        "description": "系统反馈、功能建议、问题报告",
        "tags": ["反馈", "建议", "bug", "功能"]
    }
}

def get_zone_by_content(content: str, title: str = "") -> str:
    """根据内容自动判断适合的社区区域"""
    content_lower = (content + title).lower()
    
    learning_keywords = ["学习", "编程", "代码", "算法", "作业", "考试", "知识点", 
                         "不懂", "疑惑", "不会", "问题", "题目", "教程", "理解"]
    life_keywords = ["生活", "日常", "校园", "吃饭", "睡觉", "周末", "放假", "闲聊"]
    resource_keywords = ["资源", "资料", "工具", "推荐", "分享", "下载", "视频", "文档"]
    
    learning_score = sum(1 for kw in learning_keywords if kw in content_lower)
    life_score = sum(1 for kw in life_keywords if kw in content_lower)
    resource_score = sum(1 for kw in resource_keywords if kw in content_lower)
    
    max_score = max(learning_score, life_score, resource_score)
    
    if max_score == 0:
        return "learning"
    elif learning_score == max_score:
        return "learning"
    elif life_score == max_score:
        return "life"
    else:
        return "resource"


def _init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS community_posts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id       TEXT NOT NULL UNIQUE,
                user_id       TEXT NOT NULL,
                title         TEXT NOT NULL,
                content       TEXT NOT NULL,
                zone          TEXT DEFAULT 'learning',
                tags          TEXT DEFAULT '',
                reply_count   INTEGER DEFAULT 0,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS community_replies (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                reply_id        TEXT NOT NULL UNIQUE,
                post_id         TEXT NOT NULL,
                user_id         TEXT NOT NULL,
                content         TEXT NOT NULL,
                parent_reply_id TEXT DEFAULT NULL,
                created_at      TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cp_user ON community_posts(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cp_tags ON community_posts(tags)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cp_created ON community_posts(created_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cr_post ON community_replies(post_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cr_user ON community_replies(user_id)")
        conn.commit()


_init_db()

# ★★★ 数据库迁移：为旧表补充 zone 列（在表创建后执行） ★★★
try:
    with _get_conn() as conn:
        cursor = conn.execute("PRAGMA table_info(community_posts)")
        columns = [row[1] for row in cursor.fetchall()]
        if "zone" not in columns:
            conn.execute("ALTER TABLE community_posts ADD COLUMN zone TEXT DEFAULT 'learning'")
            conn.commit()
            print("📌 [DB迁移] 已为 community_posts 表添加 zone 列")
except Exception as e:
    print(f"⚠️ [DB迁移] zone列添加失败（可能已存在）: {e}")


class CommunityService:
    _local = threading.local()

    def __init__(self):
        pass

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = _get_conn()
        return self._local.conn

    # -------------------------------------------------------------------------
    # 帖子 CRUD
    # -------------------------------------------------------------------------

    def create_post(self, user_id: str, title: str, content: str,
                    tags: Optional[List[str]] = None,
                    zone: Optional[str] = None) -> Dict[str, Any]:
        """创建帖子（仅限已注册用户）

        Args:
            user_id: 用户ID
            title: 帖子标题
            content: 帖子内容
            tags: 标签列表（可选）
            zone: 社区区域（可选，默认自动判断）
        """
        if not _validate_user(user_id):
            raise ValueError(f"用户 {user_id} 未注册或不存在，请先完成初始化")
        import uuid
        post_id = f"post_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        tags_str = ",".join(tags) if tags else ""
        
        if zone is None:
            zone = get_zone_by_content(content, title)
        elif zone not in COMMUNITY_ZONES:
            zone = "learning"

        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO community_posts
                    (post_id, user_id, title, content, zone, tags, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (post_id, user_id, title, content, zone, tags_str, now, now))
            conn.commit()

        result = {
            "post_id": post_id,
            "user_id": user_id,
            "title": title,
            "content": content,
            "zone": zone,
            "zone_name": COMMUNITY_ZONES.get(zone, {}).get("name", "学习区"),
            "tags": tags or [],
            "reply_count": 0,
            "created_at": now,
        }

        return result

    def get_post(self, post_id: str) -> Optional[Dict[str, Any]]:
        """获取单个帖子详情"""
        with _get_conn() as conn:
            row = conn.execute("""
                SELECT * FROM community_posts WHERE post_id = ?
            """, (post_id,)).fetchone()

        if not row:
            return None

        post = dict(row)
        post["tags"] = post["tags"].split(",") if post["tags"] else []
        post["zone_name"] = COMMUNITY_ZONES.get(post.get("zone", "learning"), {}).get("name", "学习区")
        return post

    def update_post(self, post_id: str, user_id: str, title: Optional[str] = None,
                    content: Optional[str] = None, tags: Optional[List[str]] = None,
                    zone: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """编辑帖子（仅作者可编辑）

        Args:
            post_id: 帖子ID
            user_id: 用户ID（需与作者一致）
            title: 新标题（可选）
            content: 新内容（可选）
            tags: 新标签列表（可选）
            zone: 新区域（可选）

        Returns:
            更新后的帖子，或 None（无权限/不存在）
        """
        with _get_conn() as conn:
            post = conn.execute("""
                SELECT * FROM community_posts WHERE post_id = ?
            """, (post_id,)).fetchone()
            if not post or post["user_id"] != user_id:
                return None

            now = datetime.now().isoformat()
            updates = []
            params = []

            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if content is not None:
                updates.append("content = ?")
                params.append(content)
            if tags is not None:
                updates.append("tags = ?")
                params.append(",".join(tags))
            if zone is not None:
                updates.append("zone = ?")
                params.append(zone)

            if not updates:
                return self.get_post(post_id)

            updates.append("updated_at = ?")
            params.append(now)
            params.append(post_id)

            conn.execute(f"""
                UPDATE community_posts SET {', '.join(updates)}
                WHERE post_id = ?
            """, params)
            conn.commit()

        return self.get_post(post_id)

    def list_posts(self, page: int = 1, page_size: int = 20,
                   tag: Optional[str] = None,
                   user_id: Optional[str] = None,
                   zone: Optional[str] = None) -> Dict[str, Any]:
        """列出帖子（分页，按时间倒序）

        Args:
            page: 页码（从1开始）
            page_size: 每页数量
            tag: 按标签筛选（可选）
            user_id: 按用户ID筛选（可选）
            zone: 按社区区域筛选（可选）
        """
        offset = (page - 1) * page_size
        conditions = []
        params: List[Any] = []

        if tag:
            conditions.append("tags LIKE ?")
            params.append(f"%{tag}%")
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if zone:
            conditions.append("zone = ?")
            params.append(zone)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        with _get_conn() as conn:
            count_row = conn.execute(f"""
                SELECT COUNT(*) as cnt FROM community_posts {where}
            """, params).fetchone()
            total = count_row["cnt"] if count_row else 0

            rows = conn.execute(f"""
                SELECT * FROM community_posts {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset]).fetchall()

        posts = []
        for row in rows:
            p = dict(row)
            p["tags"] = p["tags"].split(",") if p["tags"] else []
            p["zone_name"] = COMMUNITY_ZONES.get(p.get("zone", "learning"), {}).get("name", "学习区")
            posts.append(p)

        return {
            "posts": posts,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
            "zones": COMMUNITY_ZONES,
        }

    def delete_post(self, post_id: str, user_id: str) -> bool:
        """删除帖子（仅作者可删，需用户已注册）"""
        # 验证用户是否存在
        if not _validate_user(user_id):
            return False
        with _get_conn() as conn:
            post = conn.execute("""
                SELECT user_id FROM community_posts WHERE post_id = ?
            """, (post_id,)).fetchone()
            if not post or post["user_id"] != user_id:
                return False
            conn.execute("DELETE FROM community_replies WHERE post_id = ?", (post_id,))
            conn.execute("DELETE FROM community_posts WHERE post_id = ?", (post_id,))
            conn.commit()
        return True

    # -------------------------------------------------------------------------
    # 回复 CRUD
    # -------------------------------------------------------------------------

    def create_reply(self, post_id: str, user_id: str, content: str,
                     parent_reply_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """回复帖子（支持嵌套回复，仅限已注册用户）"""
        # 验证用户是否存在
        if not _validate_user(user_id):
            raise ValueError(f"用户 {user_id} 未注册或不存在，请先完成初始化")
        import uuid
        reply_id = f"reply_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        with _get_conn() as conn:
            post = conn.execute("""
                SELECT post_id FROM community_posts WHERE post_id = ?
            """, (post_id,)).fetchone()
            if not post:
                return None

            conn.execute("""
                INSERT INTO community_replies
                    (reply_id, post_id, user_id, content, parent_reply_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (reply_id, post_id, user_id, content, parent_reply_id, now))

            conn.execute("""
                UPDATE community_posts SET reply_count = reply_count + 1, updated_at = ?
                WHERE post_id = ?
            """, (now, post_id))
            conn.commit()

        result = {
            "reply_id": reply_id,
            "post_id": post_id,
            "user_id": user_id,
            "content": content,
            "parent_reply_id": parent_reply_id,
            "created_at": now,
        }

        # 特征更新已移至 API 层异步执行

        return result

    def get_replies(self, post_id: str) -> List[Dict[str, Any]]:
        """获取帖子的所有回复（按时间正序）"""
        with _get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM community_replies
                WHERE post_id = ?
                ORDER BY created_at ASC
            """, (post_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_reply(self, reply_id: str, user_id: str) -> bool:
        """删除回复（仅作者可删，需用户已注册）"""
        # 验证用户是否存在
        if not _validate_user(user_id):
            return False
        with _get_conn() as conn:
            reply = conn.execute("""
                SELECT user_id, post_id FROM community_replies WHERE reply_id = ?
            """, (reply_id,)).fetchone()
            if not reply or reply["user_id"] != user_id:
                return False
            conn.execute("DELETE FROM community_replies WHERE reply_id = ?", (reply_id,))
            conn.execute("""
                UPDATE community_posts SET reply_count = MAX(0, reply_count - 1)
                WHERE post_id = ?
            """, (reply["post_id"],))
            conn.commit()
        return True

    # -------------------------------------------------------------------------
    # 统计
    # -------------------------------------------------------------------------

    def get_user_post_count(self, user_id: str) -> int:
        """获取用户的发帖数"""
        with _get_conn() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as cnt FROM community_posts WHERE user_id = ?
            """, (user_id,)).fetchone()
        return row["cnt"] if row else 0

    def get_user_reply_count(self, user_id: str) -> int:
        """获取用户的回复数"""
        with _get_conn() as conn:
            row = conn.execute("""
                SELECT COUNT(*) as cnt FROM community_replies WHERE user_id = ?
            """, (user_id,)).fetchone()
        return row["cnt"] if row else 0
