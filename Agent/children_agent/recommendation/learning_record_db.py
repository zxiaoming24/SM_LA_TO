"""
learning_record_db.py - 学习记录数据库

使用 SQLite 记录用户每道题的做题情况：做题结果、用时、尝试次数。
用于：薄弱点分析（8维度特征更新）、协同过滤推荐、遗忘曲线调度。

数据库路径: ./recommendation_data/learning_records.db
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

DB_PATH = Path("./recommendation_data/learning_records.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_RESOURCE_DB_PATH = DB_PATH.parent / "resource_bank.db"

_thread_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """获取线程本地 SQLite 连接，避免 WAL 快照失效"""
    conn = getattr(_thread_local, 'conn', None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        _thread_local.conn = conn
    return conn


def _init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_solutions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT NOT NULL,
                resource_type TEXT NOT NULL CHECK(resource_type IN ('question','document','video')),
                resource_id  TEXT NOT NULL,
                is_correct   INTEGER,
                time_spent  INTEGER,
                attempt_count INTEGER DEFAULT 1,
                solved_at    TEXT NOT NULL,
                metadata     TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS review_schedule (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id  TEXT NOT NULL,
                easiness     REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 1,
                repetitions  INTEGER DEFAULT 0,
                next_review  TEXT NOT NULL,
                last_review  TEXT,
                metadata     TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS learning_stats (
                user_id      TEXT PRIMARY KEY,
                total_solved INTEGER DEFAULT 0,
                total_correct INTEGER DEFAULT 0,
                total_time   INTEGER DEFAULT 0,
                weak_topics  TEXT,
                strong_topics TEXT,
                last_active  TEXT,
                dimension_scores TEXT
            )
        """)
        # 索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_us_uid  ON user_solutions(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rs_uid ON review_schedule(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rs_next ON review_schedule(next_review)")

        conn.commit()

_init_db()


class LearningRecordDB:
    _local = threading.local()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = _get_conn()
        return self._local.conn

    # -------------------------------------------------------------------------
    # 做题记录
    # -------------------------------------------------------------------------

    def record_solution(self, user_id: str, resource_type: str,
                        resource_id: str, is_correct: bool = None,
                        time_spent: int = 0,
                        metadata: Dict = None) -> int:
        """
        记录一次学习行为（做题/看文档/看视频）
        返回 record id
        """
        now = datetime.now().isoformat()
        with _get_conn() as conn:
            # 尝试更新已有记录（同一资源多次尝试）
            existing = conn.execute("""
                SELECT id, attempt_count FROM user_solutions
                WHERE user_id=? AND resource_type=? AND resource_id=?
                ORDER BY id DESC LIMIT 1
            """, (user_id, resource_type, resource_id)).fetchone()

            if existing:
                new_attempt = existing["attempt_count"] + 1
                # 正确率只更新：用新的 is_correct 覆盖
                conn.execute("""
                    UPDATE user_solutions
                    SET is_correct=?, time_spent=?, attempt_count=?, solved_at=?
                    WHERE id=?
                """, (
                    int(is_correct) if is_correct is not None else None,
                    time_spent, new_attempt, now, existing["id"]
                ))
                record_id = existing["id"]
            else:
                cur = conn.execute("""
                    INSERT INTO user_solutions
                        (user_id, resource_type, resource_id, is_correct,
                         time_spent, attempt_count, solved_at, metadata)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """, (
                    user_id, resource_type, resource_id,
                    int(is_correct) if is_correct is not None else None,
                    time_spent, now,
                    json.dumps(metadata or {}, ensure_ascii=False)
                ))
                record_id = cur.lastrowid

            # 更新学习统计
            self._update_stats(conn, user_id, is_correct, time_spent)

            conn.commit()
        return record_id

    def _update_stats(self, conn: sqlite3.Connection, user_id: str,
                      is_correct: Optional[bool], time_spent: int):
        row = conn.execute(
            "SELECT * FROM learning_stats WHERE user_id = ?", (user_id,)
        ).fetchone()
        now = datetime.now().isoformat()
        if row:
            conn.execute("""
                UPDATE learning_stats
                SET total_solved = total_solved + 1,
                    total_correct = total_correct + ?,
                    total_time = total_time + ?,
                    last_active = ?
                WHERE user_id = ?
            """, (
                1 if is_correct else 0,
                time_spent,
                now,
                user_id
            ))
        else:
            conn.execute("""
                INSERT INTO learning_stats
                    (user_id, total_solved, total_correct, total_time, last_active)
                VALUES (?, 1, ?, ?, ?)
            """, (user_id, 1 if is_correct else 0, time_spent, now))

    def get_user_solutions(self, user_id: str,
                           resource_type: str = None,
                           limit: int = 50) -> List[Dict]:
        sql = "SELECT * FROM user_solutions WHERE user_id = ?"
        params: List[Any] = [user_id]
        if resource_type:
            sql += " AND resource_type = ?"
            params.append(resource_type)
        sql += " ORDER BY solved_at DESC LIMIT ?"
        params.append(limit)
        with _get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_user_weak_topics(self, user_id: str,
                               resource_type: str = "question",
                               threshold: float = 0.5) -> List[str]:
        """
        分析用户的薄弱知识点：
        统计该用户正确率 < threshold 的 topic，
        按正确率升序返回。
        """
        with _get_conn() as conn:
            conn.execute(f"ATTACH DATABASE '{_RESOURCE_DB_PATH}' AS resdb")
            rows = conn.execute("""
                SELECT r.topic,
                       SUM(CASE WHEN us.is_correct = 1 THEN 1 ELSE 0 END) * 1.0
                       / COUNT(*) as correct_rate,
                       COUNT(*) as attempt_count
                FROM user_solutions us
                JOIN (
                    SELECT id, topic FROM resdb.questions
                    UNION ALL
                    SELECT id, topic FROM resdb.documents
                ) r ON us.resource_id = r.id
                WHERE us.user_id = ?
                  AND us.resource_type = ?
                  AND us.is_correct IS NOT NULL
                GROUP BY r.topic
                HAVING correct_rate < ?
                ORDER BY correct_rate ASC
            """, (user_id, resource_type, threshold)).fetchall()
            conn.execute("DETACH DATABASE resdb")
        return [dict(r) for r in rows]

    def get_user_strong_topics(self, user_id: str,
                                 resource_type: str = "question",
                                 threshold: float = 0.7) -> List[str]:
        """正确率 > threshold 的强项知识点"""
        with _get_conn() as conn:
            conn.execute(f"ATTACH DATABASE '{_RESOURCE_DB_PATH}' AS resdb")
            rows = conn.execute("""
                SELECT r.topic,
                       SUM(CASE WHEN us.is_correct = 1 THEN 1 ELSE 0 END) * 1.0
                       / COUNT(*) as correct_rate,
                       COUNT(*) as attempt_count
                FROM user_solutions us
                JOIN (
                    SELECT id, topic FROM resdb.questions
                    UNION ALL
                    SELECT id, topic FROM resdb.documents
                ) r ON us.resource_id = r.id
                WHERE us.user_id = ?
                  AND us.resource_type = ?
                  AND us.is_correct IS NOT NULL
                GROUP BY r.topic
                HAVING correct_rate >= ?
                ORDER BY correct_rate DESC
            """, (user_id, resource_type, threshold)).fetchall()
            conn.execute("DETACH DATABASE resdb")
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # 协同过滤：找相似用户做过的好题
    # -------------------------------------------------------------------------

    def get_collaborative_questions(self, user_id: str,
                                     topic: str = None,
                                     limit: int = 10) -> List[Dict]:
        """
        协同过滤：找与当前用户相似的用户（做对了同样类型题的用户）
        再推荐那些用户做对但当前用户没做过的题。
        """
        with _get_conn() as conn:
            conn.execute(f"ATTACH DATABASE '{_RESOURCE_DB_PATH}' AS resdb")
            # 1. 找到与当前用户做对题类型重叠最多的相似用户
            similar_users = conn.execute("""
                SELECT us2.user_id,
                       COUNT(*) as overlap
                FROM user_solutions us1
                JOIN user_solutions us2 ON us1.resource_id = us2.resource_id
                    AND us1.is_correct = 1 AND us2.is_correct = 1
                    AND us1.user_id = ? AND us2.user_id != ?
                GROUP BY us2.user_id
                ORDER BY overlap DESC
                LIMIT 20
            """, (user_id, user_id)).fetchall()

            if not similar_users:
                conn.execute("DETACH DATABASE resdb")
                return []

            user_list = [u["user_id"] for u in similar_users]
            placeholders = ",".join("?" * len(user_list))

            # 2. 这些用户做对但当前用户没做过的题
            sql = f"""
                SELECT r.id, r.topic, r.difficulty, r.knowledge_points,
                       COUNT(DISTINCT us.user_id) as recommender_count
                FROM user_solutions us
                JOIN resdb.questions r ON us.resource_id = r.id
                WHERE us.user_id IN ({placeholders})
                  AND us.is_correct = 1
                  AND us.resource_id NOT IN (
                      SELECT resource_id FROM user_solutions
                      WHERE user_id = ? AND resource_type = 'question'
                  )
            """
            params = user_list + [user_id]
            if topic:
                sql += " AND r.topic = ?"
                params.append(topic)
            sql += " GROUP BY r.id ORDER BY recommender_count DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            conn.execute("DETACH DATABASE resdb")
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # 统计摘要
    # -------------------------------------------------------------------------

    def get_learning_summary(self, user_id: str) -> Dict:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM learning_stats WHERE user_id = ?", (user_id,)
            ).fetchone()
        if not row:
            return {
                "total_solved": 0,
                "total_correct": 0,
                "overall_accuracy": 0.0,
                "weak_topics": [],
                "strong_topics": [],
                "last_active": None
            }
        total = row["total_solved"] or 1
        correct = row["total_correct"] or 0
        return {
            "total_solved": total,
            "total_correct": correct,
            "overall_accuracy": round(correct / total, 3),
            "weak_topics": json.loads(row["weak_topics"] or "[]"),
            "strong_topics": json.loads(row["strong_topics"] or "[]"),
            "last_active": row["last_active"],
            "total_time": row["total_time"],
            "dimension_scores": json.loads(row["dimension_scores"] or "{}")
        }
