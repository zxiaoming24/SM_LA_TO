"""
forgetting_curve.py - 艾宾浩斯遗忘曲线调度器

基于 SuperMemo SM-2 算法实现间隔重复复习调度。
修复了原实现的多个问题：
  1. q 值不再从 easiness 推导，而是基于响应时间+正确性
  2. easiness 公式正确计算，不再单向膨胀
  3. 间隔遵循 SM-2 标准：第1次1天，第2次6天，之后 interval * EF
  4. 接收 time_spent 参数评估回忆质量
"""

import sqlite3
import math
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

DB_PATH = Path("./recommendation_data/learning_records.db")


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


class ForgettingCurveScheduler:
    """
    艾宾浩斯遗忘曲线调度器 - 决定下次复习时间。
    正确 → 延长间隔  错误 → 缩短间隔（重新来过）
    """

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        conn = _get_conn()
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
                metadata     TEXT,
                UNIQUE(user_id, resource_type, resource_id)
            )
        """)
        conn.commit()

    @staticmethod
    def _calc_quality(is_correct: bool, time_spent: int = 0) -> int:
        """
        根据正确性和响应时间计算 SM-2 回忆质量 q（0-5）。

        SM-2 质量标准:
          5 = 完美回忆（秒答对）
          4 = 正确，略有犹豫（<2分钟）
          3 = 正确，但有困难（>=2分钟）
          2 = 错误，但正确答案看起来简单
          1 = 错误，看到答案后才想起来
          0 = 完全忘记
        """
        if is_correct:
            if time_spent <= 0:
                return 4
            if time_spent < 30:
                return 5
            elif time_spent < 120:
                return 4
            else:
                return 3
        else:
            if time_spent <= 0:
                return 1
            if time_spent < 30:
                return 2
            else:
                return 1

    def schedule_review(self, user_id: str, resource_type: str,
                        resource_id: str, is_correct: bool,
                        time_spent: int = 0,
                        metadata: Dict = None) -> Dict[str, Any]:
        """
        安排/更新复习时间（修复版 SM-2）。

        Args:
            time_spent: 响应时间（秒），用于评估回忆质量

        Returns:
            next_review_dt: 下次复习时间（datetime）
            interval_days: 间隔天数
            repetitions: 累计正确次数
        """
        conn = _get_conn()
        row = conn.execute("""
            SELECT * FROM review_schedule
            WHERE user_id=? AND resource_type=? AND resource_id=?
        """, (user_id, resource_type, resource_id)).fetchone()

        now = datetime.now()
        q = self._calc_quality(is_correct, time_spent)

        if row is None:
            # --- 新建记录 ---
            if is_correct:
                new_interval = 1
                new_reps = 1
            else:
                new_interval = 1
                new_reps = 0

            new_easiness = 2.5
            next_dt = now + timedelta(days=new_interval)

            conn.execute("""
                INSERT INTO review_schedule
                    (user_id, resource_type, resource_id, easiness,
                     interval_days, repetitions, next_review, last_review, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, resource_type, resource_id,
                round(new_easiness, 3),
                new_interval, new_reps,
                next_dt.isoformat(),
                now.isoformat(),
                str(metadata or {})
            ))
        else:
            # --- 更新已有记录 ---
            current_easiness = float(row[4])
            current_interval = int(row[5])
            current_reps = int(row[6])

            if is_correct:
                # SM-2 easiness update: EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
                new_easiness = max(1.3, current_easiness + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
                new_reps = current_reps + 1
                # SM-2 interval: I(1)=1, I(2)=6, I(n)=I(n-1)*EF
                if new_reps == 1:
                    new_interval = 1
                elif new_reps == 2:
                    new_interval = 6
                else:
                    new_interval = round(current_interval * new_easiness)
                new_interval = min(new_interval, 365)
            else:
                new_easiness = max(1.3, current_easiness - 0.2)
                new_interval = 1
                new_reps = 0

            next_dt = now + timedelta(days=new_interval)
            conn.execute("""
                UPDATE review_schedule
                SET easiness=?, interval_days=?, repetitions=?,
                    next_review=?, last_review=?
                WHERE user_id=? AND resource_type=? AND resource_id=?
            """, (
                round(new_easiness, 3),
                new_interval,
                new_reps,
                next_dt.isoformat(),
                now.isoformat(),
                user_id, resource_type, resource_id
            ))

        conn.commit()

        print(f"  🧠 [遗忘曲线] {resource_type}/{resource_id}: {'✓' if is_correct else '✗'} "
              f"q={q} EF={new_easiness:.2f} 间隔={new_interval}天 重复={new_reps}次")

        return {
            "next_review": next_dt.isoformat(),
            "interval_days": new_interval,
            "repetitions": new_reps,
            "quality": q,
            "easiness": round(new_easiness, 3),
        }

    def get_due_reviews(self, user_id: str,
                         resource_type: str = None,
                         limit: int = 20) -> List[Dict]:
        """
        获取当前用户所有已到期的复习项（next_review <= now）。
        """
        now = datetime.now().isoformat()
        conn = _get_conn()
        sql = """
            SELECT * FROM review_schedule
            WHERE user_id = ? AND next_review <= ?
        """
        params: List[Any] = [user_id, now]
        if resource_type:
            sql += " AND resource_type = ?"
            params.append(resource_type)
        sql += " ORDER BY next_review ASC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()

        result = []
        for r in rows:
            result.append({
                "user_id": r[1],
                "resource_type": r[2],
                "resource_id": r[3],
                "easiness": r[4],
                "interval_days": r[5],
                "repetitions": r[6],
                "next_review": r[7],
                "last_review": r[8]
            })
        return result

    def get_upcoming_reviews(self, user_id: str,
                              days_ahead: int = 7,
                              limit: int = 20) -> List[Dict]:
        """获取未来 N 天内的复习计划。"""
        now = datetime.now()
        future = (now + timedelta(days=days_ahead)).isoformat()
        now_str = now.isoformat()
        conn = _get_conn()
        rows = conn.execute("""
            SELECT * FROM review_schedule
            WHERE user_id = ?
              AND next_review > ?
              AND next_review <= ?
            ORDER BY next_review ASC
            LIMIT ?
        """, (user_id, now_str, future, limit)).fetchall()
        return [{
            "resource_type": r[2],
            "resource_id": r[3],
            "interval_days": r[5],
            "next_review": r[7]
        } for r in rows]

    def get_due_reviews_grouped(self, user_id: str, limit: int = 20) -> Dict[str, List[Dict]]:
        """
        获取到期复习项，按资源类型分组。
        用于前端展示不同类型资源的复习提醒。
        """
        due = self.get_due_reviews(user_id, limit=limit * 3)
        grouped = {}
        for item in due:
            rt = item["resource_type"]
            if rt not in grouped:
                grouped[rt] = []
            grouped[rt].append(item)
        return grouped

    def schedule_phase_review(self, user_id: str, knowledge_points: list):
        """
        阶段完成时：为该阶段的所有知识点安排一次主动复习。
        在知识点掌握图谱中记录一次"阶段复习"活动，触发遗忘曲线更新。
        """
        try:
            from memory.knowledge_mastery import KnowledgeMasteryGraph
            kg = KnowledgeMasteryGraph()
            for kp in knowledge_points:
                kg.record_activity(
                    user_id=user_id,
                    knowledge_point=kp,
                    correct=None,
                    activity_type="phase_review",
                    difficulty="中等",
                )
            print(f"  📅 [遗忘曲线] 已为阶段知识点安排复习: {knowledge_points}")
        except Exception as e:
            print(f"  ⚠️ [遗忘曲线] 安排阶段复习失败: {e}")

    def get_review_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户的复习统计。"""
        conn = _get_conn()
        now = datetime.now().isoformat()
        total = conn.execute("""
            SELECT COUNT(*) FROM review_schedule WHERE user_id = ?
        """, (user_id,)).fetchone()[0]

        due = conn.execute("""
            SELECT COUNT(*) FROM review_schedule
            WHERE user_id = ? AND next_review <= ?
        """, (user_id, now)).fetchone()[0]

        mastered = conn.execute("""
            SELECT COUNT(*) FROM review_schedule
            WHERE user_id = ? AND repetitions >= 3
        """, (user_id,)).fetchone()[0]

        return {
            "total_items": total,
            "due_today": due,
            "mastered": mastered,
            "learning": total - mastered
        }

    def get_overdue_priority(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        获取最紧急的复习项（逾期越久优先级越高）。
        """
        now = datetime.now().isoformat()
        conn = _get_conn()
        rows = conn.execute("""
            SELECT *,
                   ROUND((julianday(?) - julianday(next_review)) * 
                   CASE WHEN repetitions < 2 THEN 1.5 ELSE 1.0 END, 1) as urgency
            FROM review_schedule
            WHERE user_id = ? AND next_review <= ?
            ORDER BY urgency DESC
            LIMIT ?
        """, (now, user_id, now, limit)).fetchall()
        return [dict(r) for r in rows]
