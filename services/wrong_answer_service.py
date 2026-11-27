"""
错题本服务 - 自动记录用户的错题

错题来源：
1. 编程题：judge_code_async 评分后 score < 60 自动录入
2. 理论题（选择题/判断题等）：提交答案后判断错误自动录入

核心功能：
1. 记录错题（含题目原文、用户答案、正确答案、得分）
2. 查询错题列表（分页、按类型筛选、按知识点筛选）
3. 统计错题分布
"""

import sqlite3
import json
import asyncio
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import sys


class WrongAnswerError(Exception):
    """错题本服务异常基类"""
    pass


DB_PATH = Path("./wrong_answer_data/wrong_answers.db")

# ★★★ 缓存数据库连接（连接池），避免每次操作新建连接 ★★★
# 使用 threading.local 保证每个线程独立连接，避免 SQLite 多线程写冲突
_conn_local = threading.local()

# 辅助函数
def normalize_kps(fallback_kp: str, kps: Any) -> List[str]:
    """统一知识点格式：字符串→列表，空值→fallback"""
    if isinstance(kps, list):
        return [str(k) for k in kps if k] or [fallback_kp]
    if isinstance(kps, str):
        return [s.strip() for s in kps.split(",") if s.strip()] or [fallback_kp]
    return [fallback_kp]


def _get_conn() -> sqlite3.Connection:
    """每个线程获取独立的数据库连接，避免多线程并发写冲突"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = getattr(_conn_local, 'conn', None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _conn_local.conn = conn
    return conn


# ★★★ 数据库迁移标记：模块首次导入时只执行一次 ★★★
_DB_MIGRATED = False

def _init_db():
    global _DB_MIGRATED
    if _DB_MIGRATED:
        return
    _DB_MIGRATED = True
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wrong_answers (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id       TEXT NOT NULL UNIQUE,
                user_id         TEXT NOT NULL,
                question_type   TEXT NOT NULL,
                question_data   TEXT NOT NULL,
                user_answer     TEXT NOT NULL DEFAULT '',
                correct_answer  TEXT NOT NULL DEFAULT '',
                score           INTEGER NOT NULL DEFAULT 0,
                problem_id      TEXT DEFAULT '',
                question_id     TEXT DEFAULT '',
                knowledge_points TEXT DEFAULT '',
                source          TEXT DEFAULT 'programming',
                attempt_count   INTEGER NOT NULL DEFAULT 1,
                resolved        INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_user ON wrong_answers(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_type ON wrong_answers(question_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_created ON wrong_answers(created_at DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_problem ON wrong_answers(problem_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_user_problem ON wrong_answers(user_id, problem_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_user_question ON wrong_answers(user_id, question_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_wa_resolved ON wrong_answers(user_id, resolved)
        """)
        # 数据库迁移（用 _DB_MIGRATED 确保只跑一次，不再每次都 try/except）
        _migrate(conn)


#将 DDL 和迁移逻辑从 for 循环内移到循环外，避免重复执行；添加模块级 _init_db() 调用修复数据库从未初始化的问题
def _migrate(conn):
    """执行数据库迁移（模块导入时仅执行一次）"""
    _columns = [row[1] for row in conn.execute("PRAGMA table_info(wrong_answers)").fetchall()]
    _migrations = {
        "attempt_count": 'ALTER TABLE wrong_answers ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 1',
        "resolved": 'ALTER TABLE wrong_answers ADD COLUMN resolved INTEGER NOT NULL DEFAULT 0',
        "mastered_at": 'ALTER TABLE wrong_answers ADD COLUMN mastered_at TEXT DEFAULT ""',
        "mastered_score": 'ALTER TABLE wrong_answers ADD COLUMN mastered_score INTEGER DEFAULT 0',
        "difficulty": 'ALTER TABLE wrong_answers ADD COLUMN difficulty TEXT DEFAULT ""',
    }
    for col, stmt in _migrations.items():
        if col not in _columns:
            try:
                conn.execute(stmt)
                print(f"  [DB迁移] 添加列: {col}")
            except Exception as e:
                print(f"  ⚠️ [DB迁移] {col} 失败: {e}")

    # 回填编程题难度字段（仅执行一次）
    try:
        empty_rows = conn.execute(
            "SELECT id, question_data FROM wrong_answers WHERE question_type = 'programming' AND (difficulty IS NULL OR difficulty = '')"
        ).fetchall()
        for row in empty_rows:
            rid = row["id"]
            qdata_str = row["question_data"]
            d = ""
            if qdata_str:
                try:
                    qdata = json.loads(qdata_str)
                    d = qdata.get("difficulty", "")
                except Exception:
                    pass
            if not d:
                d = "简单"
            conn.execute("UPDATE wrong_answers SET difficulty = ? WHERE id = ?", (d, rid))
        if empty_rows:
            print(f"   🔄 已回填 {len(empty_rows)} 条编程题的难度字段")
    except Exception:
        pass

    # 创建扩展表（仅执行一次，IF NOT EXISTS 保证幂等）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wrong_answer_attempts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            wrong_answer_id INTEGER NOT NULL,
            user_id         TEXT NOT NULL,
            attempt_number  INTEGER NOT NULL,
            user_answer     TEXT NOT NULL DEFAULT '',
            score           INTEGER NOT NULL DEFAULT 0,
            verdict         TEXT DEFAULT '',
            created_at      TEXT NOT NULL,
            FOREIGN KEY (wrong_answer_id) REFERENCES wrong_answers(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_waa_wa ON wrong_answer_attempts(wrong_answer_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_waa_user ON wrong_answer_attempts(user_id)
    """)
    
    # ★★★ 新增：推荐缓存表 - 将推荐资源与具体错题记录关联 ★★★
    conn.execute("""
        CREATE TABLE IF NOT EXISTS wrong_answer_recommendations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id       TEXT NOT NULL,
            user_id         TEXT NOT NULL,
            materials       TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            expires_at      TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_record ON wrong_answer_recommendations(record_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_user ON wrong_answer_recommendations(user_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_war_expires ON wrong_answer_recommendations(expires_at)
    """)

    # ★★★ 易错题独立表 - attempt_count 跨过阈值时自动写入，resolved=1 表示已掌握 ★★★
    conn.execute("""
        CREATE TABLE IF NOT EXISTS frequently_wrong (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            wrong_answer_id   INTEGER NOT NULL UNIQUE,
            user_id           TEXT NOT NULL,
            attempt_count     INTEGER NOT NULL DEFAULT 0,
            entered_at        TEXT NOT NULL,
            resolved          INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (wrong_answer_id) REFERENCES wrong_answers(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fw_user ON frequently_wrong(user_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fw_attempts ON frequently_wrong(attempt_count DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fw_user_attempts ON frequently_wrong(user_id, attempt_count DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_fw_resolved ON frequently_wrong(user_id, resolved)
    """)

    # 迁移：给旧表加 resolved 列
    fw_cols = [row[1] for row in conn.execute("PRAGMA table_info(frequently_wrong)").fetchall()]
    if "resolved" not in fw_cols:
        try:
            conn.execute("ALTER TABLE frequently_wrong ADD COLUMN resolved INTEGER NOT NULL DEFAULT 0")
            print(f"  [DB迁移] frequently_wrong 添加列: resolved")
        except Exception as e:
            print(f"  [DB迁移] frequently_wrong resolved 列添加失败: {e}")

    # 回填：将已有 attempt_count > 4 且未掌握的错题补全到 frequently_wrong
    # 使用 NOT IN 保证幂等：已在表中的不会重复插入，新用户的旧数据也能被补全
    try:
        threshold = 4
        conn.execute("""
            INSERT INTO frequently_wrong (wrong_answer_id, user_id, attempt_count, entered_at, resolved)
            SELECT id, user_id, attempt_count, created_at, 0
            FROM wrong_answers
            WHERE attempt_count > ? AND resolved = 0
              AND id NOT IN (SELECT wrong_answer_id FROM frequently_wrong)
        """, (threshold,))
    except Exception:
        pass

    conn.commit()

# 模块导入时自动初始化数据库
_init_db()


class WrongAnswerService:

    # 易错题阈值：同一题答错超过此次数自动进入 frequently_wrong 表
    FREQUENTLY_WRONG_THRESHOLD = 4

    def add_wrong_answer(
        self,
        user_id: str,
        question_type: str,
        question_data: Dict[str, Any],
        user_answer: str = "",
        correct_answer: str = "",
        score: int = 0,
        problem_id: str = "",
        question_id: str = "",
        knowledge_points: Optional[List[str]] = None,
        source: str = "programming",
        verdict: str = "",
        difficulty: str = "",
        record_id: str = "",
    ) -> bool:
        """
        添加或更新错题记录（同一题目重复错误只累加次数，不重复插入）
        每次调用自动记录一条尝试历史到 wrong_answer_attempts 表。

        Args:
            user_id: 用户ID
            question_type: 题目类型
            question_data: 题目完整数据（JSON字典）
            user_answer: 用户的答案
            correct_answer: 正确答案
            score: 得分（0-100）
            problem_id: 编程题ID
            question_id: 理论题ID
            knowledge_points: 相关知识点列表
            source: 来源 (programming/theory)
            verdict: 评判结果（Accepted/Wrong Answer/Compile Error 等）
            difficulty: 难度（编程题："简单/中等偏易/中等/中等偏难/困难/挑战"）
            record_id: 错题记录ID（优先级最高，精准定位已有记录）
        """
        import uuid
        now = datetime.now().isoformat()
        kp_str = ",".join(knowledge_points) if knowledge_points else ""

        try:
            with _get_conn() as conn:
                # ★★★ 查重优先级: record_id > problem_id > question_id ★★★
                existing = None
                if record_id:
                    existing = conn.execute(
                        "SELECT id, record_id, attempt_count FROM wrong_answers "
                        "WHERE user_id = ? AND record_id = ?",
                        (user_id, record_id)
                    ).fetchone()
                if not existing:
                    lookup_field = "problem_id" if problem_id else "question_id"
                    lookup_value = problem_id or question_id
                    if lookup_value:
                        existing = conn.execute(
                            f"SELECT id, record_id, attempt_count FROM wrong_answers "
                            f"WHERE user_id = ? AND {lookup_field} = ? AND question_type = ?",
                            (user_id, lookup_value, question_type)
                        ).fetchone()

                if existing:
                    old_attempts = existing["attempt_count"]
                    new_attempts = old_attempts + 1
                    row_id = existing["id"]
                    conn.execute("""
                        UPDATE wrong_answers
                        SET user_answer = ?, correct_answer = ?, score = ?,
                            question_data = ?, knowledge_points = ?, source = ?,
                            attempt_count = ?, resolved = 0, created_at = ?,
                            difficulty = ?
                        WHERE id = ?
                    """, (
                        user_answer, correct_answer, score,
                        json.dumps(question_data, ensure_ascii=False),
                        kp_str, source, new_attempts, now,
                        difficulty,
                        row_id
                    ))
                    conn.execute("""
                        INSERT INTO wrong_answer_attempts
                            (wrong_answer_id, user_id, attempt_number, user_answer, score, verdict, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (row_id, user_id, new_attempts, user_answer, score, verdict, now))
                    print(f"   ✅ [错题本] 已更新错题(第{new_attempts}次): {question_type} (得分: {score})")
                else:
                    record_id = f"wa_{uuid.uuid4().hex[:12]}"
                    conn.execute("""
                        INSERT INTO wrong_answers
                            (record_id, user_id, question_type, question_data, user_answer,
                             correct_answer, score, problem_id, question_id,
                             knowledge_points, source, attempt_count, created_at, difficulty)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """, (
                        record_id, user_id, question_type,
                        json.dumps(question_data, ensure_ascii=False),
                        user_answer, correct_answer, score,
                        problem_id, question_id, kp_str, source, now,
                        difficulty
                    ))
                    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    conn.execute("""
                        INSERT INTO wrong_answer_attempts
                            (wrong_answer_id, user_id, attempt_number, user_answer, score, verdict, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (row_id, user_id, 1, user_answer, score, verdict, now))
                    print(f"   ✅ [错题本] 已记录错题: {question_type} (得分: {score})")

                # ★★★ 易错题自动入库：attempt_count 跨过阈值时写入 frequently_wrong 表 ★★★
                current_attempts = conn.execute(
                    "SELECT attempt_count FROM wrong_answers WHERE id = ?", (row_id,)
                ).fetchone()
                if current_attempts and current_attempts["attempt_count"] > self.FREQUENTLY_WRONG_THRESHOLD:
                    conn.execute("""
                        INSERT INTO frequently_wrong (wrong_answer_id, user_id, attempt_count, entered_at, resolved)
                        VALUES (?, ?, ?, ?, 0)
                        ON CONFLICT(wrong_answer_id) DO UPDATE SET attempt_count = ?, resolved = 0
                    """, (row_id, user_id, current_attempts["attempt_count"], now,
                          current_attempts["attempt_count"]))
                    if existing and old_attempts <= self.FREQUENTLY_WRONG_THRESHOLD:
                        print(f"   🔥 [易错题] 第{current_attempts['attempt_count']}次错误，自动进入易错题本")

                conn.commit()
            return True
        except Exception as e:
            print(f"   ❌ [错题本] 记录失败: {e}")
            return False

    def get_wrong_answers(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        question_type: Optional[str] = None,
        source: Optional[str] = None,
        show_resolved: bool = False
    ) -> Dict[str, Any]:
        """
        获取用户的错题列表（分页，按时间倒序）

        Args:
            user_id: 用户ID
            page: 页码（从1开始）
            page_size: 每页条数
            question_type: 筛选题目类型
            source: 筛选来源
            show_resolved: 是否包含已掌握的题目（默认只显示待巩固）
        """
        offset = (page - 1) * page_size
        conditions = ["user_id = ?"]
        params: List[Any] = [user_id]

        if not show_resolved:
            conditions.append("resolved = 0")
        if question_type:
            conditions.append("question_type = ?")
            params.append(question_type)
        if source:
            conditions.append("source = ?")
            params.append(source)

        where = "WHERE " + " AND ".join(conditions)

        with _get_conn() as conn:
            count_row = conn.execute(f"""
                SELECT COUNT(*) as cnt FROM wrong_answers {where}
            """, params).fetchone()
            total = count_row["cnt"] if count_row else 0

            rows = conn.execute(f"""
                SELECT * FROM wrong_answers {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset]).fetchall()

        records = []
        with _get_conn() as conn:
            ids = [row["id"] for row in rows]
            if ids:
                placeholders = ",".join("?" * len(ids))
                all_attempts = conn.execute(f"""
                    SELECT wrong_answer_id, attempt_number, user_answer, score, verdict, created_at
                    FROM wrong_answer_attempts
                    WHERE wrong_answer_id IN ({placeholders})
                    ORDER BY wrong_answer_id ASC, attempt_number ASC
                """, ids).fetchall()
            else:
                all_attempts = []

        attempts_by_wa_id: Dict[int, List] = {}
        for a in all_attempts:
            wa_id = a["wrong_answer_id"]
            if wa_id not in attempts_by_wa_id:
                attempts_by_wa_id[wa_id] = []
            attempts_by_wa_id[wa_id].append({
                "attempt_number": a["attempt_number"],
                "user_answer": a["user_answer"],
                "score": a["score"],
                "verdict": a["verdict"],
                "created_at": a["created_at"],
            })

        for row in rows:
            r = dict(row)
            r["question_data"] = json.loads(r["question_data"])
            r["knowledge_points"] = r["knowledge_points"].split(",") if r["knowledge_points"] else []
            r["attempts"] = attempts_by_wa_id.get(r["id"], [])
            records.append(r)

        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }

    def mark_resolved(self, user_id: str, problem_id: str = "", question_id: str = "", score: int = 0,
                      record_id: str = "") -> bool:
        """
        标记错题为已掌握（答对时调用，不删除记录）
        记录掌握时间戳和得分，方便追溯掌握历程。

        Args:
            user_id: 用户ID
            problem_id: 编程题ID
            question_id: 理论题ID
            score: 掌握时的得分
            record_id: 错题记录ID（可选，优先使用）
        """
        lookup_field = "problem_id" if problem_id else "question_id"
        lookup_value = problem_id or question_id
        if not lookup_value and not record_id:
            return False
        now = datetime.now().isoformat()
        with _get_conn() as conn:
            # ★★★ 优先使用 record_id 精准定位（确保即使已掌握也能覆盖更新 mastered_score）★★★
            if record_id:
                cur = conn.execute("""
                    UPDATE wrong_answers SET resolved = 1, mastered_at = ?, mastered_score = ?
                    WHERE record_id = ? AND user_id = ?
                """, (now, score, record_id, user_id))
            else:
                # ★★★ 不用 resolved=0 条件：每个(user_id, question_id, question_type)组合最多一条记录，不会误伤
                # 去掉此条件确保已掌握状态的得分也能被后续正确覆盖更新
                cur = conn.execute(f"""
                    UPDATE wrong_answers SET resolved = 1, mastered_at = ?, mastered_score = ?
                    WHERE user_id = ? AND {lookup_field} = ?
                """, (now, score, user_id, lookup_value))
                # ★★★ 兼容老 judge_ 前缀：q_ 匹配不到时，尝试 judge_ 前缀 ★★★
                if cur.rowcount == 0 and not problem_id and lookup_value.startswith("q_"):
                    alt_id = f"judge_{lookup_value[2:]}"
                    conn.execute(f"""
                        UPDATE wrong_answers SET resolved = 1, mastered_at = ?, mastered_score = ?,
                            question_id = ?
                        WHERE user_id = ? AND question_id = ?
                    """, (now, score, lookup_value, user_id, alt_id))

            # ★★★ 易错题标记已掌握：使用 record_id 或 question_id 定位 ★★★
            if record_id:
                conn.execute("""
                    UPDATE frequently_wrong SET resolved = 1
                    WHERE wrong_answer_id IN (
                        SELECT id FROM wrong_answers
                        WHERE record_id = ? AND user_id = ?
                    )
                """, (record_id, user_id))
            else:
                conn.execute("""
                    UPDATE frequently_wrong SET resolved = 1
                    WHERE wrong_answer_id IN (
                        SELECT id FROM wrong_answers
                        WHERE user_id = ? AND {lookup_field} = ?
                    )
                """, (user_id, lookup_value))
                if not problem_id and lookup_value.startswith("q_"):
                    alt_id2 = f"judge_{lookup_value[2:]}"
                    conn.execute("""
                        UPDATE frequently_wrong SET resolved = 1
                        WHERE wrong_answer_id IN (
                            SELECT id FROM wrong_answers
                            WHERE user_id = ? AND question_id = ?
                        )
                    """, (user_id, alt_id2))

            conn.commit()
        print(f"   ✅ [错题本] 已标记为已掌握: {user_id}/{lookup_value} (得分: {score})")
        return True

    def unmark_resolved(self, user_id: str, record_id: str) -> bool:
        """
        取消已掌握标记，将错题移回待巩固列表

        Args:
            user_id: 用户ID
            record_id: 错题记录的record_id
        """
        now = datetime.now().isoformat()
        try:
            with _get_conn() as conn:
                # 查找对应 wrong_answers 记录
                row = conn.execute(
                    "SELECT id FROM wrong_answers WHERE record_id = ? AND user_id = ?",
                    (record_id, user_id)
                ).fetchone()
                if not row:
                    print(f"   ⚠️ [错题本] 取消掌握失败：记录不存在 record_id={record_id}")
                    return False

                wa_id = row["id"]

                # 重置 wrong_answers 的掌握状态
                conn.execute("""
                    UPDATE wrong_answers SET resolved = 0, mastered_at = '', mastered_score = 0
                    WHERE id = ?
                """, (wa_id,))

                # 同步重置 frequently_wrong 的掌握状态（如果存在）
                conn.execute("""
                    UPDATE frequently_wrong SET resolved = 0
                    WHERE wrong_answer_id = ?
                """, (wa_id,))

                conn.commit()
            print(f"   ✅ [错题本] 已取消掌握: {user_id}/{record_id}")
            return True
        except Exception as e:
            print(f"   ❌ [错题本] 取消掌握失败: {e}")
            return False

    def get_wrong_answer_stats(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户的错题统计

        Args:
            user_id: 用户ID
        """
        with _get_conn() as conn:
            total = conn.execute("""
                SELECT COUNT(*) as cnt FROM wrong_answers WHERE user_id = ?
            """, (user_id,)).fetchone()["cnt"]

            pending = conn.execute("""
                SELECT COUNT(*) as cnt FROM wrong_answers WHERE user_id = ? AND resolved = 0
            """, (user_id,)).fetchone()["cnt"]

            resolved = conn.execute("""
                SELECT COUNT(*) as cnt FROM wrong_answers WHERE user_id = ? AND resolved = 1
            """, (user_id,)).fetchone()["cnt"]

            type_rows = conn.execute("""
                SELECT question_type, COUNT(*) as cnt
                FROM wrong_answers WHERE user_id = ? AND resolved = 0
                GROUP BY question_type ORDER BY cnt DESC
            """, (user_id,)).fetchall()

            source_rows = conn.execute("""
                SELECT source, COUNT(*) as cnt
                FROM wrong_answers WHERE user_id = ? AND resolved = 0
                GROUP BY source
            """, (user_id,)).fetchall()

        return {
            "total": total,
            "pending": pending,
            "resolved": resolved,
            "by_type": {r["question_type"]: r["cnt"] for r in type_rows},
            "by_source": {r["source"]: r["cnt"] for r in source_rows},
        }

    def get_mastered_answers(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        question_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取用户已掌握的错题列表（分页，按掌握时间倒序）

        展示掌握历程信息：错误次数、掌握时间、掌握得分等。

        Args:
            user_id: 用户ID
            page: 页码
            page_size: 每页条数
            question_type: 筛选题目类型
        """
        offset = (page - 1) * page_size
        conditions = ["user_id = ? AND resolved = 1"]
        params: List[Any] = [user_id]

        if question_type:
            conditions.append("question_type = ?")
            params.append(question_type)

        where = "WHERE " + " AND ".join(conditions)

        with _get_conn() as conn:
            count_row = conn.execute(f"""
                SELECT COUNT(*) as cnt FROM wrong_answers {where}
            """, params).fetchone()
            total = count_row["cnt"] if count_row else 0

            rows = conn.execute(f"""
                SELECT * FROM wrong_answers {where}
                ORDER BY mastered_at DESC, created_at DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset]).fetchall()

        records = []
        for row in rows:
            r = dict(row)
            r["question_data"] = json.loads(r["question_data"])
            r["knowledge_points"] = r["knowledge_points"].split(",") if r["knowledge_points"] else []
            records.append(r)

        if records:
            ids = [r["id"] for r in records]
            placeholders = ",".join("?" * len(ids))
            with _get_conn() as conn:
                attempt_rows = conn.execute(f"""
                    SELECT wrong_answer_id, attempt_number, user_answer, score, verdict, created_at
                    FROM wrong_answer_attempts
                    WHERE wrong_answer_id IN ({placeholders})
                    ORDER BY wrong_answer_id ASC, attempt_number ASC
                """, ids).fetchall()
            attempts_by_id: Dict[int, List] = {}
            for a in attempt_rows:
                wa_id = a["wrong_answer_id"]
                if wa_id not in attempts_by_id:
                    attempts_by_id[wa_id] = []
                attempts_by_id[wa_id].append({
                    "attempt_number": a["attempt_number"],
                    "user_answer": a["user_answer"],
                    "score": a["score"],
                    "verdict": a["verdict"],
                    "created_at": a["created_at"],
                })
            for r in records:
                real = attempts_by_id.get(r["id"], [])
                if real:
                    r["attempts"] = real
                else:
                    syn = []
                    ac = r.get("attempt_count", 1)
                    c = r.get("created_at", "")
                    ms = r.get("mastered_score", 0)
                    ma = r.get("mastered_at", "")
                    for i in range(ac):
                        syn.append({
                            "attempt_number": i + 1,
                            "user_answer": r.get("user_answer", "") if i == ac - 1 else "",
                            "score": ms if i == ac - 1 else 0,
                            "verdict": "Accepted" if i == ac - 1 else "Wrong Answer",
                            "created_at": ma if i == ac - 1 else c,
                        })
                    r["attempts"] = syn

        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }

    # ===== 易错题查询（直接查 frequently_wrong 独立表）=====

    async def get_frequently_wrong_answers(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        question_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        异步获取用户的易错题列表（直接查 frequently_wrong 表，JOIN wrong_answers 获取详情）

        易错题入库/出库时机：
        - 入库：add_wrong_answer 中 attempt_count 跨过阈值时自动写入
        - 出库：mark_resolved 中掌握后自动移除
        """
        def _query():
            offset = (page - 1) * page_size
            join_conditions = ["fw.user_id = ?", "fw.resolved = 0"]
            params: List[Any] = [user_id]

            if question_type:
                join_conditions.append("wa.question_type = ?")
                params.append(question_type)
            if source:
                join_conditions.append("wa.source = ?")
                params.append(source)

            where = "WHERE " + " AND ".join(join_conditions)

            with _get_conn() as conn:
                count_row = conn.execute(f"""
                    SELECT COUNT(*) as cnt
                    FROM frequently_wrong fw
                    JOIN wrong_answers wa ON fw.wrong_answer_id = wa.id
                    {where}
                """, params).fetchone()
                total = count_row["cnt"] if count_row else 0

                rows = conn.execute(f"""
                    SELECT wa.*, fw.attempt_count as fw_attempt_count, fw.entered_at
                    FROM frequently_wrong fw
                    JOIN wrong_answers wa ON fw.wrong_answer_id = wa.id
                    {where}
                    ORDER BY fw.attempt_count DESC, fw.entered_at DESC
                    LIMIT ? OFFSET ?
                """, params + [page_size, offset]).fetchall()

            records = []
            if rows:
                with _get_conn() as conn:
                    ids = [row["id"] for row in rows]
                    placeholders = ",".join("?" * len(ids))
                    all_attempts = conn.execute(f"""
                        SELECT wrong_answer_id, attempt_number, user_answer, score, verdict, created_at
                        FROM wrong_answer_attempts
                        WHERE wrong_answer_id IN ({placeholders})
                        ORDER BY wrong_answer_id ASC, attempt_number ASC
                    """, ids).fetchall()

                attempts_by_wa_id: Dict[int, List] = {}
                for a in all_attempts:
                    wa_id = a["wrong_answer_id"]
                    if wa_id not in attempts_by_wa_id:
                        attempts_by_wa_id[wa_id] = []
                    attempts_by_wa_id[wa_id].append({
                        "attempt_number": a["attempt_number"],
                        "user_answer": a["user_answer"],
                        "score": a["score"],
                        "verdict": a["verdict"],
                        "created_at": a["created_at"],
                    })

                for row in rows:
                    r = dict(row)
                    r["question_data"] = json.loads(r["question_data"])
                    r["knowledge_points"] = r["knowledge_points"].split(",") if r["knowledge_points"] else []
                    r["attempts"] = attempts_by_wa_id.get(r["id"], [])
                    r["is_frequently_wrong"] = True
                    records.append(r)

            return {
                "records": records,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
                "threshold": self.FREQUENTLY_WRONG_THRESHOLD,
            }

        return await asyncio.to_thread(_query)

    async def get_frequently_wrong_stats(self, user_id: str) -> Dict[str, Any]:
        """异步获取用户易错题专项统计（直接查 frequently_wrong 表）"""
        threshold = self.FREQUENTLY_WRONG_THRESHOLD

        def _query():
            with _get_conn() as conn:
                total = conn.execute("""
                    SELECT COUNT(*) as cnt FROM frequently_wrong WHERE user_id = ? AND resolved = 0
                """, (user_id,)).fetchone()["cnt"]

                by_type_rows = conn.execute("""
                    SELECT wa.question_type, COUNT(*) as cnt, MAX(fw.attempt_count) as max_attempts
                    FROM frequently_wrong fw
                    JOIN wrong_answers wa ON fw.wrong_answer_id = wa.id
                    WHERE fw.user_id = ? AND fw.resolved = 0
                    GROUP BY wa.question_type ORDER BY cnt DESC
                """, (user_id,)).fetchall()

                avg_row = conn.execute("""
                    SELECT AVG(attempt_count) as avg_attempts, MAX(attempt_count) as max_attempts
                    FROM frequently_wrong WHERE user_id = ? AND resolved = 0
                """, (user_id,)).fetchone()

                kp_rows = conn.execute("""
                    SELECT wa.knowledge_points, COUNT(*) as cnt
                    FROM frequently_wrong fw
                    JOIN wrong_answers wa ON fw.wrong_answer_id = wa.id
                    WHERE fw.user_id = ? AND fw.resolved = 0
                    GROUP BY wa.knowledge_points ORDER BY cnt DESC LIMIT 10
                """, (user_id,)).fetchall()

            return total, by_type_rows, avg_row, kp_rows

        total, by_type_rows, avg_row, kp_rows = await asyncio.to_thread(_query)

        kp_counter: Dict[str, int] = {}
        for row in kp_rows:
            for kp in row["knowledge_points"].split(","):
                kp = kp.strip()
                if kp:
                    kp_counter[kp] = kp_counter.get(kp, 0) + row["cnt"]
        sorted_kps = sorted(kp_counter.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total": total,
            "threshold": threshold,
            "by_type": {r["question_type"]: {"count": r["cnt"], "max_attempts": r["max_attempts"]} for r in by_type_rows},
            "avg_attempts": round(avg_row["avg_attempts"] or 0, 1),
            "max_attempts": avg_row["max_attempts"] or 0,
            "weak_knowledge_points": [{"knowledge_point": kp, "count": cnt} for kp, cnt in sorted_kps],
        }

    def delete_wrong_answer(self, record_id: str, user_id: str) -> bool:
        """删除一条错题记录（同时清理 frequently_wrong 表）"""
        with _get_conn() as conn:
            # 先删 frequently_wrong（通过 record_id 找到 wrong_answer_id）
            conn.execute("""
                DELETE FROM frequently_wrong
                WHERE wrong_answer_id IN (
                    SELECT id FROM wrong_answers WHERE record_id = ? AND user_id = ?
                )
            """, (record_id, user_id))
            result = conn.execute("""
                DELETE FROM wrong_answers WHERE record_id = ? AND user_id = ?
            """, (record_id, user_id))
            conn.commit()
            return result.rowcount > 0

    def clear_user_wrong_answers(self, user_id: str) -> bool:
        """清空用户所有错题记录（同时清理 frequently_wrong 表）"""
        with _get_conn() as conn:
            conn.execute("DELETE FROM frequently_wrong WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM wrong_answers WHERE user_id = ?", (user_id,))
            conn.commit()
            return True

    def get_wrong_answer_detail(self, record_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取单条错题的完整详情（含 attempt_count、knowledge_points 等）"""
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM wrong_answers WHERE record_id = ? AND user_id = ?",
                (record_id, user_id)
            ).fetchone()
        if not row:
            return None
        r = dict(row)
        r["question_data"] = json.loads(r["question_data"])
        r["knowledge_points"] = r["knowledge_points"].split(",") if r["knowledge_points"] else []
        return r

    async def _save_recommendations_for_record(
        self,
        record_id: str,
        user_id: str,
        materials: Dict[str, Any],
        expires_hours: int = 24
    ) -> bool:
        """
        异步 - 将推荐资源保存到缓存表，与具体错题记录关联
        
        Args:
            record_id: 错题记录ID
            user_id: 用户ID
            materials: 推荐资源数据
            expires_hours: 过期时间（小时），默认24小时
        """
        def _save():
            try:
                now = datetime.now()
                expires_at = (now + timedelta(hours=expires_hours)).isoformat()
                materials_json = json.dumps(materials)
                
                with _get_conn() as conn:
                    # 先删除旧记录
                    conn.execute(
                        "DELETE FROM wrong_answer_recommendations WHERE record_id = ? AND user_id = ?",
                        (record_id, user_id)
                    )
                    # 插入新记录
                    conn.execute(
                        """
                        INSERT INTO wrong_answer_recommendations 
                        (record_id, user_id, materials, created_at, expires_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (record_id, user_id, materials_json, now.isoformat(), expires_at)
                    )
                    conn.commit()
                return True
            except Exception as e:
                print(f"  ⚠️ 保存推荐缓存失败: {e}")
                return False
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _save)

    async def _get_recommendations_for_record(self, record_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        异步 - 从缓存表获取与具体错题记录关联的推荐资源
        
        Args:
            record_id: 错题记录ID
            user_id: 用户ID
        
        Returns:
            推荐资源数据（如果存在且未过期），否则返回 None
        """
        def _get():
            try:
                now = datetime.now().isoformat()
                with _get_conn() as conn:
                    row = conn.execute(
                        "SELECT materials FROM wrong_answer_recommendations "
                        "WHERE record_id = ? AND user_id = ? AND expires_at > ?",
                        (record_id, user_id, now)
                    ).fetchone()
                if row:
                    return json.loads(row["materials"])
                return None
            except Exception as e:
                print(f"  ⚠️ 获取推荐缓存失败: {e}")
                return None
        
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _get)

    def _infer_resource_types(self, features: Optional[Dict] = None) -> List[str]:
        """错题推荐只生成编程题(question/practice)和理论题(question)两类资源"""
        return ["question", "practice"]

    # 难度文本 → 整数映射（questions 表 difficulty 为 1-5）
    DIFFICULTY_MAP = {
        "简单": 1,
        "中等偏易": 2,
        "中等": 3,
        "中等偏难": 4,
        "困难": 5,
        "挑战": 5,
    }

    def recommend_materials_for_wrong_answer(
        self,
        user_id: str,
        knowledge_points: List[str],
        attempt_count: int,
        difficulty: Optional[str] = None,
        features: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        为顽固错题（连续错3次及以上）推荐个性化学习资料

        根据用户特征（学习风格）自动选择资料类型：
        - 动手型 → 练习题
        - 视觉型 → 视频/思维导图
        - 阅读型 → 学习文档

        Args:
            user_id: 用户ID
            knowledge_points: 相关知识点列表
            attempt_count: 当前错误次数
            difficulty: 错题难度（文本，如"中等"），用于筛选同难度的推荐资料
            features: 用户特征（可选，不传则自动获取）

        Returns:
            {
                "should_recommend": bool,
                "attempt_count": int,
                "resource_types": [...],
                "learning_style": "...",
                "materials": { "document": [...], "question": [...], "video": [...] }
            }
        """
        if attempt_count < 3:
            return {"should_recommend": False}

        try:
            if not features:
                from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
                updater = DynamicFeatureUpdater()
                features = updater.get_latest_features(user_id)

            resource_types = self._infer_resource_types(features)

            learning_style = ""
            if features:
                try:
                    learning_style = features.get("learning_behavior", {}).get("learning_style", "综合型")
                except Exception:
                    learning_style = "综合型"

            from Agent.children_agent.recommendation.recommender import PersonalizedRecommender
            recommender = PersonalizedRecommender()

            # 文本难度 → 整数难度（不匹配则 None，不限制难度）
            diff_int = self.DIFFICULTY_MAP.get(difficulty) if difficulty else None

            materials: Dict[str, List] = {}

            for kp in knowledge_points[:2]:
                for rt in resource_types:
                    try:
                        rec_result = recommender.recommend(
                            user_id=user_id,
                            resource_type=rt,
                            user_features=features,
                            topic=kp,
                            difficulty=diff_int,
                            n=6
                        )
                        recs = rec_result.get("recommendations", [])
                        if recs:
                            if rt not in materials:
                                materials[rt] = []
                            materials[rt].extend(recs)
                    except Exception as inner_e:
                        print(f"  ⚠️ 推荐 {rt}({kp}) 失败: {inner_e}")

            # ★★★ 直接查共享库（绕开推荐引擎难度过滤，确保 AI 生成的题能查到）★★★
            total_recs = sum(len(v) for v in materials.values())
            if total_recs == 0:
                print(f"   [错题本] 直接查共享库...")
                try:
                    # ★★★ 获取用户已做过的题目ID，用于后续过滤 ★★★
                    try:
                        done_ids = recommender._get_done_ids(user_id, "question")
                    except Exception:
                        done_ids = set()
                    from Agent.children_agent.recommendation.resource_db import ResourceDB
                    _rdb = ResourceDB()
                    for kp in knowledge_points[:2]:
                        # ★★★ 优先：topic 精确匹配 + 过滤用户已做题 ★★★
                        pool = _rdb.get_user_unseen_questions(
                            user_id=user_id, topic=kp, limit=4
                        )
                        # ★★★ 次优：knowledge_point 模糊匹配 + done_ids 过滤 ★★★
                        if not pool:
                            pool = _rdb.find_questions(knowledge_point=kp, limit=8)
                            pool = [q for q in pool if q.get("id") not in done_ids][:4]
                        if pool:
                            print(f"   [错题本] 直接查库命中 {len(pool)} 条 (kp={kp})")
                            for q in pool:
                                q["recommendation_reason"] = "内容推荐"
                                if not q.get("source"):
                                    meta = q.get("metadata", "")
                                    if isinstance(meta, str) and '"source": "agent_generated"' in meta:
                                        q["source"] = "agent_generated"
                                    elif isinstance(meta, dict) and meta.get("source") == "agent_generated":
                                        q["source"] = "agent_generated"
                            materials.setdefault("question", []).extend(pool)
                except Exception as e:
                    print(f"   ⚠️ 直接查库失败: {e}")

            # ★★★ 库推荐为空时自动 LLM 生成兜底 ★★★
            total_recs = sum(len(v) for v in materials.values())
            if total_recs == 0:
                print(f"   [错题本] 库中无匹配资源，尝试 LLM 生成学习材料...")
                llm_materials = self._generate_llm_materials(
                    user_id=user_id,
                    knowledge_points=knowledge_points,
                    resource_types=resource_types,
                )
                if llm_materials:
                    materials = llm_materials

            # ★★★ 过滤掉 title 和 content 都为空的条目 ★★★
            materials = self._clean_materials(materials)

            return {
                "should_recommend": True,
                "attempt_count": attempt_count,
                "resource_types": resource_types,
                "knowledge_points": knowledge_points,
                "learning_style": learning_style,
                "difficulty": difficulty,
                "materials": materials,
            }

        except Exception as e:
            print(f"  ❌ 推荐学习资料失败: {e}")
            return {"should_recommend": False, "error": str(e)}

    async def recommend_materials_for_wrong_answer_async(
        self,
        user_id: str,
        knowledge_points: List[str],
        attempt_count: int,
        difficulty: Optional[str] = None,
        features: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        异步版 - 为顽固错题（连续错3次及以上）推荐个性化学习资料

        【补救学习策略】与普通推荐的区别：
        1. 优先使用内容推荐（基于知识点匹配），跳过遗忘曲线复习（避免返回已做过的题）
        2. 强制排除用户已做过的题目，确保推荐新鲜内容
        3. 降低难度推荐（帮助用户理解基础概念）
        4. 协同过滤找相似用户做对的题

        与 sync 版区别：LLM 兜底走 async Agent 调用，不阻塞事件循环
        """
        if attempt_count < 3:
            return {"should_recommend": False}

        try:
            if not features:
                from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
                updater = DynamicFeatureUpdater()
                features = updater.get_latest_features(user_id)

            resource_types = self._infer_resource_types(features)

            learning_style = ""
            if features:
                try:
                    learning_style = features.get("learning_behavior", {}).get("learning_style", "综合型")
                except Exception:
                    learning_style = "综合型"

            from Agent.children_agent.recommendation.recommender import PersonalizedRecommender
            from Agent.children_agent.recommendation.resource_db import ResourceDB
            
            recommender = PersonalizedRecommender()
            resource_db = ResourceDB()

            # ★★★ 补救学习特殊处理：降低难度一级，帮助用户理解 ★★★
            diff_int = self.DIFFICULTY_MAP.get(difficulty) if difficulty else None
            if diff_int and diff_int > 1:
                diff_int = diff_int - 1  # 降低难度一级

            # ★★★ 获取用户已做过的题目ID（用于过滤）★★★
            done_ids = recommender._get_done_ids(user_id, "question")

            materials: Dict[str, List] = {}

            # ★★★ 补救学习推荐策略：跳过遗忘曲线，优先内容推荐和协同过滤 ★★★
            # ★★★ 使用 asyncio.to_thread 避免阻塞事件循环 ★★★
            for kp in knowledge_points[:2]:
                for rt in resource_types:
                    try:
                        # 使用专门的补救学习推荐方法（在线程池中执行，不阻塞事件循环）
                        rec_result = await asyncio.to_thread(
                            self._remedial_recommend,
                            user_id=user_id,
                            resource_type=rt,
                            user_features=features,
                            topic=kp,
                            difficulty=diff_int,
                            n=6,
                            done_ids=done_ids,
                            recommender=recommender,
                            resource_db=resource_db
                        )
                        recs = rec_result.get("recommendations", [])
                        if recs:
                            if rt not in materials:
                                materials[rt] = []
                            materials[rt].extend(recs)
                    except Exception as inner_e:
                        print(f"  ⚠️ 补救推荐 {rt}({kp}) 失败: {inner_e}")

            # ★★★ 直接查共享库（绕开推荐引擎难度过滤，确保 AI 生成的题能查到）★★★
            total_recs = sum(len(v) for v in materials.values())
            if total_recs == 0:
                print(f"   [错题本] 直接查共享库...")
                try:
                    from Agent.children_agent.recommendation.resource_db import ResourceDB
                    _rdb = ResourceDB()
                    for kp in knowledge_points[:2]:
                        pool = _rdb.find_questions(topic=kp, limit=4)
                        if not pool:
                            pool = _rdb.find_questions(knowledge_point=kp, limit=4)
                        if pool:
                            print(f"   [错题本] 直接查库命中 {len(pool)} 条 (topic={kp})")
                            for q in pool:
                                q["recommendation_reason"] = "内容推荐"
                                if not q.get("source"):
                                    meta = q.get("metadata", "")
                                    if isinstance(meta, str) and '"source": "agent_generated"' in meta:
                                        q["source"] = "agent_generated"
                                    elif isinstance(meta, dict) and meta.get("source") == "agent_generated":
                                        q["source"] = "agent_generated"
                            materials.setdefault("question", []).extend(pool)
                except Exception as e:
                    print(f"   ⚠️ 直接查库失败: {e}")

            # ★★★ 库推荐为空时，只生成理论题（不生成编程题，避免耗时过长）★★★
            total_recs = sum(len(v) for v in materials.values())
            if total_recs == 0:
                print(f"   [错题本] 库中无匹配资源，尝试生成理论题...")
                llm_materials = await self._async_generate_materials(
                    user_id=user_id,
                    knowledge_points=knowledge_points,
                    resource_types=["question"],  # ★★★ 只生成理论题，快且匹配错题类型 ★★★
                )
                if llm_materials:
                    materials = llm_materials

            materials = self._clean_materials(materials)

            return {
                "should_recommend": True,
                "attempt_count": attempt_count,
                "resource_types": resource_types,
                "knowledge_points": knowledge_points,
                "learning_style": learning_style,
                "difficulty": difficulty,
                "materials": materials,
            }

        except Exception as e:
            print(f"  ❌ 推荐学习资料失败: {e}")
            return {"should_recommend": False, "error": str(e)}

    # ======================================================================
    # 补救学习专用推荐策略
    # ======================================================================

    def _remedial_recommend(
        self,
        user_id: str,
        resource_type: str,
        user_features: Dict,
        topic: str,
        difficulty: int,
        n: int,
        done_ids: set,
        recommender,
        resource_db
    ) -> Dict[str, Any]:
        """
        补救学习专用推荐策略 - 为做错3次以上的用户推荐学习资料

        策略优先级（与普通推荐不同）：
        1. 协同过滤（找相似用户做对但当前用户没做过的题）
        2. 内容推荐（基于知识点匹配 + ChromaDB 语义搜索）
        3. 随机补充（从未做过的题库中抽取）

        关键特性：
        - 跳过遗忘曲线复习（避免返回用户已做过的错题）
        - 强制过滤已做过的题目
        - 基于知识点精确匹配
        """
        recommendations = []
        sources = []

        # ---- 策略1：协同过滤（优先推荐相似用户做对的题）----
        if resource_type == "question":
            collab = recommender.record_db.get_collaborative_questions(
                user_id, topic=topic, limit=n * 2
            )
            if collab:
                recs = recommender._enrich_collab(collab, resource_type)
                # 过滤已做过的
                recs = [r for r in recs if r.get("id") not in done_ids]
                recommendations.extend(recs)
                sources.append("collaborative_remedial")

        # ---- 策略2：内容推荐（基于知识点匹配）----
        if user_features and len(recommendations) < n:
            content_recs = recommender._content_based_recommend(
                user_id, resource_type, user_features,
                topic=topic, difficulty=difficulty,
                limit=n * 2, exclude_done=True
            )
            # 再次过滤已做过的（双重保险）
            content_recs = [r for r in content_recs if r.get("id") not in done_ids]
            recommendations.extend(content_recs)
            if content_recs:
                sources.append("content_based_remedial")

        # ---- 策略3：直接从题库查找未做过的题 ----
        if len(recommendations) < n and resource_type == "question":
            pool = resource_db.get_user_unseen_questions(
                user_id, topic=topic, difficulty=difficulty, limit=n * 2
            )
            # 过滤已做过的（双重保险）
            pool = [r for r in pool if r.get("id") not in done_ids]
            recommendations.extend(pool)
            if pool:
                sources.append("unseen_pool")

        # 去重 + 截取
        seen = set()
        unique_recs = []
        for r in recommendations:
            rid = r.get("id") or r.get("resource_id")
            if rid and rid not in seen:
                if not r.get("content") and not r.get("title") and not r.get("question"):
                    continue
                seen.add(rid)
                unique_recs.append(r)

        # 添加推荐原因
        for r in unique_recs:
            if "recommendation_reason" not in r:
                r["recommendation_reason"] = "补救学习推荐"

        primary_source = sources[0] if sources else "unseen_pool"
        return {
            "recommendations": unique_recs[:n],
            "count": len(unique_recs[:n]),
            "primary_source": primary_source,
            "timestamp": self._get_current_time()
        }

    @staticmethod
    def _get_current_time():
        from datetime import datetime
        return datetime.now().isoformat()

    # ======================================================================
    # LLM 生成兜底（覆盖 doc/ppt/video/extension/mindmap/question 全类型）
    # ======================================================================

    async def generate_llm_materials(
        self,
        user_id: str,
        knowledge_points: List[str],
        resource_types: List[str],
        difficulty: str = "",
    ) -> Optional[Dict[str, List]]:
        """
        对外公开的方法（供 API 调用）：调用真实 Agent 生成学习资料
        """
        return await self._async_generate_materials(
            user_id=user_id,
            knowledge_points=knowledge_points,
            resource_types=resource_types,
            difficulty=difficulty,
        )

    async def _async_generate_materials(
        self,
        user_id: str,
        knowledge_points: List[str],
        resource_types: List[str],
        difficulty: str = "",
    ) -> Optional[Dict[str, List]]:
        """
        直接调用Agent生成学习资料，不经过PhaseBridge。
        生成：1道编程题 + 2道理论题（一次性调用question agent取前2道）
        """
        materials: Dict[str, List] = {}
        kp = knowledge_points[0] if knowledge_points else "编程"

        # ★★★ 从错题难度映射到整数难度 ★★★
        _diff_map = {"简单": 1, "中等偏易": 2, "中等": 3, "中等偏难": 4, "困难": 5, "挑战": 5}
        _int_diff = _diff_map.get(difficulty, 3)

        for rt in resource_types:
            rt_lower = rt.lower()
            try:
                if rt_lower == "practice":
                    # ---- 生成1道编程题 ----
                    from Agent.children_agent.practice_agent import PracticeAgent
                    agent = PracticeAgent()
                    result = await agent.generate_problem_async(
                        learning_problem=kp,
                        user_id=user_id,
                    )
                    if result and result.get("problem_id"):
                        desc = result.get("description", "")
                        materials.setdefault("question", []).append({
                            "id": result.get("problem_id", ""),
                            "title": result.get("title", "")[:60] or kp,
                            "content": desc,
                            "examples": result.get("examples", []),
                            "knowledge_points": [kp],
                            "source": "agent_generated",
                            "sub_topic": "programming",
                            "difficulty": _int_diff,
                        })
                        print(f"  ✅ 生成编程题: {result.get('title', '')}")

                elif rt_lower == "question":
                    # ---- 生成理论题，只取2道 ----）
                    from Agent.children_agent.question_generator_agent import QuestionGeneratorAgent
                    agent = QuestionGeneratorAgent()
                    result = await agent.generate_all_questions_async(
                        info={"topic": kp, "course_name": kp,
                              "user_input": kp, "user_id": user_id}
                    )
                    if result:
                        count = 0
                        for q_type in ("single_choice", "multiple_choice", "judge",
                                        "fill_blank", "short_answer"):
                            q_list = result.get(q_type, [])
                            for q in q_list:
                                if count >= 2:
                                    break
                                if not isinstance(q, dict) or not q.get("question"):
                                    continue
                                # ★★★ 跳过缺少正确答案的题目 ★★★
                                if not q.get("answer") or not str(q.get("answer", "")).strip():
                                    print(f"  ⚠️ [错题本] 跳过无正确答案的理论题: {str(q.get('question', ''))[:40]}...")
                                    continue
                                materials.setdefault("question", []).append({
                                    "id": q.get("id", ""),
                                    "title": q.get("question", "")[:60],
                                    "content": q.get("question", ""),
                                    "options": q.get("options", []),
                                    "answer": q.get("answer", ""),
                                    "explanation": q.get("explanation", ""),
                                    "sub_topic": q_type,
                                    "knowledge_points": [kp, q_type],
                                    "source": "agent_generated",
                                    "difficulty": _int_diff,
                                })
                                count += 1
                            if count >= 2:
                                break
                        print(f"  ✅ 生成理论题 {count} 道")

            except Exception as e:
                print(f"  ⚠️ AI生成 {rt_lower} 异常: {e}")
                continue

        total = sum(len(v) for v in materials.values())
        if total > 0:
            print(f"  ✅ [错题本] AI共生成 {total} 条学习材料 ({', '.join(materials.keys())})")
            # ★★★ 将生成的题目写入共享库，下次可直接检索 ★★★
            self._save_generated_to_resource_db(materials, user_id)
        else:
            print(f"  ⚠️ [错题本] AI全部生成失败，无推荐资源")
        return self._clean_materials(materials)


    def _generate_llm_materials(
        self,
        user_id: str,
        knowledge_points: List[str],
        resource_types: List[str],
    ) -> Optional[Dict[str, List]]:
        """同步版 Agent 生成（供 recommend_materials_for_wrong_answer 内部调用）"""
        # ★★★ 只允许编程题/理论题两类 ★★★
        ALLOWED = {"question", "practice"}
        try:
            from services.phase_bridge import PhaseResourceBridge
            bridge = PhaseResourceBridge()
            materials: Dict[str, List] = {}
            kp = knowledge_points[0] if knowledge_points else "编程"

            for rt in resource_types:
                rt_lower = rt.lower()
                if rt_lower not in ALLOWED:
                    continue
                try:
                    # 使用线程池隔离 asyncio.run()，避免在已有事件循环的线程中调用
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _pool:
                        future = _pool.submit(
                            lambda: asyncio.run(bridge.generate_phase_resource(
                                user_id=user_id,
                                phase_index=0,
                                resource_type=rt_lower,
                                knowledge_point=kp,
                                force_generate=True,
                            ))
                        )
                        result = future.result(timeout=300)
                    if not result.get("success"):
                        continue
                    self._parse_agent_result(materials, result, rt_lower, kp, knowledge_points)
                except concurrent.futures.TimeoutError:
                    print(f"   ⚠️ [错题本] LLM生成超时(300s): {rt_lower}")
                    continue
                except Exception:
                    continue

            if sum(len(v) for v in materials.values()) > 0:
                self._save_generated_to_resource_db(materials, user_id)
                return self._clean_materials(materials)
            return {}
        except Exception:
            return {}

    def _parse_agent_result(self, materials: Dict[str, List], result: Dict, rt_lower: str, kp: str, knowledge_points: List[str]):
        """解析 Agent 生成结果并添加到 materials 中"""
        import json
        resource = result.get("resource", {})
        print(f"  ✅ Agent 生成 {rt_lower} 成功")
        # 用内容截断做兜底标题，避免所有条目都显示成「{kp}」XXX 完全无法区分
        idx = sum(len(v) for v in materials.values()) + 1

        if rt_lower == "doc":
            doc_data = resource.get("document", resource)
            materials.setdefault("document", []).append({
                "title": doc_data.get("doc_title") or doc_data.get("title") or self._title_from_content(doc_data.get("doc_content") or doc_data.get("content"), kp, idx, "学习文档"),
                "content": doc_data.get("doc_content", doc_data.get("content", "")),
                "file_path": resource.get("file_path", doc_data.get("file_path", "")),
                "knowledge_points": knowledge_points,
                "source": "agent_generated",
                "downloadable": True,
                "file_type": "document",
            })

        elif rt_lower == "practice":
            problem = resource.get("problem", resource)
            if resource.get("recommendations"):
                for rec in resource["recommendations"]:
                    materials.setdefault("question", []).append({
                        "id": rec.get("problem_id", rec.get("id", "")),
                        "title": rec.get("title") or self._title_from_content(rec.get("description") or rec.get("content"), kp, idx, "练习题"),
                        "content": rec.get("description", rec.get("content", "")),
                        "sub_topic": "programming",
                        "knowledge_points": normalize_kps(kp, rec.get("knowledge_points", [])),
                        "source": "agent_generated",
                    })
                    idx += 1
            else:
                desc = problem.get("description", "")
                materials.setdefault("question", []).append({
                    "id": problem.get("problem_id", ""),
                    "title": problem.get("title") or self._title_from_content(desc, kp, idx, "编程题"),
                    "content": desc,
                    "examples": problem.get("examples", []),
                    "sub_topic": "programming",
                    "knowledge_points": normalize_kps(kp, problem.get("knowledge_points", [])),
                    "source": "agent_generated",
                })

        elif rt_lower == "question":
            """理论题生成结果解析：将各题型展平为 question 类型条目"""
            questions_dict = resource.get("questions", {})
            if questions_dict:
                # Agent 生成路径：questions dict 包含各题型列表
                for q_type, q_list in questions_dict.items():
                    if not isinstance(q_list, list):
                        continue
                    for q in q_list:
                        if not isinstance(q, dict) or not q.get("question"):
                            continue
                        materials.setdefault("question", []).append({
                            "id": q.get("id", ""),
                            "title": q.get("question", "")[:60],
                            "content": q.get("question", ""),
                            "options": q.get("options", []),
                            "answer": q.get("answer", ""),
                            "explanation": q.get("explanation", ""),
                            "sub_topic": q_type,
                            "knowledge_points": normalize_kps(kp, [kp, q_type]),
                            "source": "agent_generated",
                        })
                        idx += 1
            else:
                # 推荐引擎路径：recommendations 列表，用 description/title 作为内容
                recs = resource.get("recommendations", [])
                for rec in recs:
                    if not isinstance(rec, dict):
                        continue
                    content = rec.get("description") or rec.get("content") or rec.get("title") or ""
                    if not content:
                        continue
                    materials.setdefault("question", []).append({
                        "id": rec.get("problem_id", rec.get("id", "")),
                        "title": rec.get("title", "")[:60] or content[:60],
                        "content": content,
                        "options": rec.get("options", []),
                        "answer": rec.get("answer", rec.get("solution", "")),
                        "knowledge_points": normalize_kps(kp, rec.get("knowledge_points", [])),
                        "source": rec.get("_source_type", "recommender"),
                    })
                    idx += 1

        elif rt_lower == "video":
            videos = resource.get("videos", [])
            for v in videos[:3]:
                materials.setdefault("video", []).append({
                    "title": v.get("title") or self._title_from_content(v.get("description") or v.get("url", ""), kp, idx, "视频讲解"),
                    "url": v.get("url", ""),
                    "platform": v.get("platform", ""),
                    "author": v.get("author", ""),
                    "duration": v.get("duration", ""),
                    "source": "agent_generated",
                })
                idx += 1

        elif rt_lower == "ppt":
            ppt_data = resource.get("ppt", resource)
            materials.setdefault("ppt", []).append({
                "title": ppt_data.get("topic") or ppt_data.get("title") or self._title_from_content("", kp, idx, "演示文稿"),
                "content": json.dumps(ppt_data, ensure_ascii=False),
                "filename": ppt_data.get("filename", ""),
                "oss_url": ppt_data.get("oss_url", resource.get("oss_url", "")),
                "filepath": ppt_data.get("filepath", resource.get("filepath", "")),
                "pages": ppt_data.get("pages", 0),
                "knowledge_points": knowledge_points,
                "source": "agent_generated",
                "downloadable": True,
                "file_type": "ppt",
            })

        elif rt_lower in ("extension", "extension_reading"):
            material = resource.get("material", resource)
            materials.setdefault("extension", []).append({
                "title": material.get("title") or self._title_from_content(material.get("content"), kp, idx, "拓展阅读"),
                "content": material.get("content", ""),
                "knowledge_points": knowledge_points,
                "source": "agent_generated",
            })

        elif rt_lower == "mindmap":
            mm_data = resource.get("mindmap", resource)
            materials.setdefault("mindmap", []).append({
                "title": self._title_from_content("", kp, idx, "思维导图"),
                "content": json.dumps(mm_data, ensure_ascii=False),
                "knowledge_points": knowledge_points,
                "source": "agent_generated",
            })

        elif rt_lower in ("animation",):
            materials.setdefault("animation", []).append({
                "title": self._title_from_content("", kp, idx, "动画演示"),
                "content": resource.get("html", ""),
                "source": "agent_generated",
            })

    def _save_generated_to_resource_db(self, materials: Dict[str, List], user_id: str = "") -> None:
        """将 AI 生成的题目保存到共享库 resource_db + ChromaDB，下次可直接从库中检索。"""
        try:
            from Agent.children_agent.recommendation.resource_db import ResourceDB
            db = ResourceDB()
        except Exception as e:
            print(f"  ⚠️ [错题本] 无法加载 ResourceDB: {e}")
            return

        question_items = materials.get("question", [])
        if not question_items:
            return

        # ★★★ 同时尝试加载 ChromaDB 语义存储 ★★★
        semantic = None
        try:
            from Agent.children_agent.recommendation.semantic_store import SemanticStore
            semantic = SemanticStore()
        except Exception:
            pass

        import hashlib
        saved = 0
        for item in question_items:
            qid = item.get("id", "")
            if not qid:
                # 无 ID 则用内容 hash 生成
                content_key = (item.get("content", "") or item.get("title", "") or "")
                if not content_key.strip():
                    continue
                qid = f"ag_{hashlib.md5(content_key.encode()).hexdigest()[:12]}"

            # ★★★ topic 只用第一个知识点名称，方便路由按 topic 精确检索 ★★★
            raw_kps = item.get("knowledge_points", []) or []
            topic = raw_kps[0] if raw_kps else "编程"
            sub_topic = item.get("sub_topic", "programming")
            difficulty = item.get("difficulty", 3)
            content = item.get("content", item.get("description", ""))
            title = item.get("title", "")
            options = item.get("options", [])
            solution = item.get("answer", item.get("solution", ""))
            hints = item.get("hints", [])
            if isinstance(hints, list):
                hints = [h for h in hints if h]
            else:
                hints = []

            # ★★★ 内容质量校验：过滤掉泄露了模板上下文的无效题目 ★★★
            if not self._is_valid_question_content(content):
                print(f"  ⚠️ [错题本] 跳过无效题目（含模板上下文）: {content[:60]}...")
                continue

            kps = item.get("knowledge_points", [])
            if isinstance(kps, str):
                kps = [k.strip() for k in kps.split(",") if k.strip()]
            if not kps:
                kps = ["编程"]

            metadata = {"source": "agent_generated", "generated_by": "wrong_answer_service"}

            try:
                qid = db.upsert_question(
                    qid=qid, topic=topic, sub_topic=sub_topic,
                    difficulty=difficulty,
                    knowledge_points=kps,
                    content=content, title=title,
                    solution=solution, hints=hints,
                    options=options,
                    metadata=metadata,
                )
                # ★★★ 同步写入 ChromaDB，使基于内容的推荐也能检索到 ★★★
                if semantic:
                    try:
                        semantic.store_question(
                            qid=qid, topic=topic, sub_topic=sub_topic,
                            difficulty=difficulty,
                            knowledge_points=kps,
                            content=content,
                        )
                    except Exception as e:
                        print(f"  ⚠️ [错题本] ChromaDB 存储失败: {e}")
                saved += 1
            except Exception as e:
                print(f"  ⚠️ [错题本] 保存题目 {qid} 到 resource_db 失败: {e}")

        if saved > 0:
            print(f"  ✅ [错题本] 已保存 {saved} 道 AI 生成题目到共享库")

    @staticmethod
    def _is_valid_question_content(content: str) -> bool:
        """校验题目内容是否有效：过滤掉 LLM 泄露的模板上下文"""
        if not content or not content.strip():
            return False
        _template_markers = [
            "【最近对话】", "【用户画像】", "【知识点掌握状态】",
            "【学习统计】", "【复习提醒】", "【学习计划】",
            "[user]", "[assistant]",
            "综合评分:", "各维度:", "薄弱点:", "待复习:",
        ]
        for marker in _template_markers:
            if marker in content:
                return False
        if len(content) > 500:
            return False
        return True

    @staticmethod
    def _title_from_content(content: str, kp: str, idx: int, label: str) -> str:
        """从内容文本截取标题；内容为空时回退到「知识点」+ 标签 + 序号"""
        if content and content.strip():
            # 取第一行或前 30 个字符作为标题
            first_line = content.strip().split("\n")[0].strip()
            if len(first_line) > 40:
                return first_line[:37] + "..."
            return first_line
        return f"「{kp}」{label}{idx}"

    @staticmethod
    def _clean_materials(materials: Optional[Dict[str, List]]) -> Dict[str, List]:
        """过滤掉 title 和 content/description 都为空（或只有空壳 info）的条目"""
        if not materials:
            return {}
        cleaned: Dict[str, List] = {}
        for rt, items in materials.items():
            valid = []
            for item in items:
                title = item.get("title") or item.get("name") or ""
                content = item.get("content") or item.get("description") or ""
                if title.strip() or content.strip():
                    valid.append(item)
            if valid:
                cleaned[rt] = valid
        return cleaned

    def record_attempt(
        self,
        user_id: str,
        problem_id: str = "",
        question_id: str = "",
        question_type: str = "programming",
        user_answer: str = "",
        score: int = 0,
        verdict: str = "",
        record_id: str = "",
    ) -> bool:
        """
        手动记录一次尝试历史（用于答对时补记掌握的那次尝试）

        Args:
            user_id: 用户ID
            problem_id: 编程题ID
            question_id: 理论题ID
            question_type: 题目类型
            user_answer: 用户的答案
            score: 得分
            verdict: 评判结果
            record_id: 错题记录ID（优先使用，精准定位）
        """
        now = datetime.now().isoformat()
        try:
            with _get_conn() as conn:
                # ★★★ 优先用 record_id 精准定位（避免 exam_xxx vs q_xxx 前缀不匹配）★★★
                if record_id:
                    row = conn.execute(
                        "SELECT id, attempt_count FROM wrong_answers WHERE record_id = ? AND user_id = ?",
                        (record_id, user_id)
                    ).fetchone()
                else:
                    lookup_field = "problem_id" if problem_id else "question_id"
                    lookup_value = problem_id or question_id
                    if not lookup_value:
                        return False
                    row = conn.execute(
                        f"SELECT id, attempt_count FROM wrong_answers "
                        f"WHERE user_id = ? AND {lookup_field} = ? AND question_type = ?",
                        (user_id, lookup_value, question_type)
                    ).fetchone()
                if not row:
                    return False
                new_num = (row["attempt_count"] or 0) + 1
                conn.execute("""
                    UPDATE wrong_answers SET attempt_count = ? WHERE id = ?
                """, (new_num, row["id"]))
                conn.execute("""
                    INSERT INTO wrong_answer_attempts
                        (wrong_answer_id, user_id, attempt_number, user_answer, score, verdict, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (row["id"], user_id, new_num, user_answer, score, verdict, now))
                conn.commit()
            return True
        except Exception as e:
            print(f"  ⚠️ [错题本] 记录尝试失败: {e}")
            return False

    def handle_judge_result(
        self,
        user_id: str,
        record_id: Optional[str],
        problem_id: str,
        score: int,
        knowledge_points: Optional[List[str]] = None,
        problem_data: Optional[Dict] = None,
        user_answer: str = "",
        verdict: str = "",
    ) -> Dict[str, Any]:
        """
        处理评判结果后的错题本逻辑（答对标记掌握，答错3次+推荐资料）

        这是 /practice/rejudge 端点的核心业务逻辑，
        API 层只需调用此方法，不包含业务判断。

        Returns:
            {
                "auto_marked_as_resolved": bool,
                "wrong_answer_updated": bool,
                "material_recommendations": {...} 或 None,
                "_need_async_recommend": bool,        # ★★★ 标记是否需要异步推荐 ★★★
                "_recommend_kps": [...],               # ★★★ 传给推荐的知识点 ★★★
                "_recommend_attempt": 0,               # ★★★ 当前错误次数 ★★★
                "_recommend_diff": "",                 # ★★★ 难度 ★★★
            }
        """
        result = {
            "auto_marked_as_resolved": False,
            "wrong_answer_updated": False,
            "material_recommendations": None,
            "_need_async_recommend": False,
            "_recommend_kps": [],
            "_recommend_attempt": 0,
            "_recommend_diff": "",
        }

        if score >= 60 and record_id:
            self.record_attempt(
                user_id=user_id,
                problem_id=problem_id,
                question_type="programming",
                user_answer=user_answer,
                score=score,
                verdict=verdict or "Accepted",
                record_id=record_id or "",
            )
            self.mark_resolved(user_id=user_id, problem_id=problem_id, score=score, record_id=record_id or "")
            result["auto_marked_as_resolved"] = True

        if score < 60:
            if record_id:
                detail = self.get_wrong_answer_detail(record_id, user_id)
                if detail:
                    attempt_count = detail.get("attempt_count", 0)
                    kps = knowledge_points or detail.get("knowledge_points", [])
                    diff = detail.get("difficulty", "")
                    result["_need_async_recommend"] = True
                    result["_recommend_kps"] = kps
                    result["_recommend_attempt"] = attempt_count
                    result["_recommend_diff"] = diff
            else:
                kps = knowledge_points or []
                if problem_data:
                    kps = kps or problem_data.get("knowledge_points", [])
                try:
                    with _get_conn() as conn:
                        lookup_field = "problem_id" if problem_id else "question_id"
                        lookup_value = problem_id or problem_data.get("question_id", "")
                        if lookup_value:
                            row = conn.execute(
                                f"SELECT attempt_count, knowledge_points, difficulty FROM wrong_answers "
                                f"WHERE user_id = ? AND {lookup_field} = ? AND question_type = ?",
                                (user_id, lookup_value, "programming")
                            ).fetchone()
                            if row:
                                attempt_count = row["attempt_count"]
                                db_kps = row["knowledge_points"]
                                diff = row["difficulty"] or ""
                                if not kps and db_kps:
                                    kps = db_kps.split(",")
                                result["_need_async_recommend"] = True
                                result["_recommend_kps"] = kps
                                result["_recommend_attempt"] = attempt_count
                                result["_recommend_diff"] = diff
                except Exception as e:
                    print(f"   ⚠️ 查询错题次数失败: {e}")

        return result

    async def handle_judge_result_async(
        self,
        user_id: str,
        record_id: Optional[str],
        problem_id: str,
        score: int,
        knowledge_points: Optional[List[str]] = None,
        problem_data: Optional[Dict] = None,
        user_answer: str = "",
        verdict: str = "",
    ) -> Dict[str, Any]:
        """
        异步处理评判结果（推荐部分使用 async Agent，不阻塞事件循环）
        """
        # 同步的 DB 操作部分在线程池执行
        result = await asyncio.to_thread(
            self._handle_judge_result_sync,
            user_id=user_id,
            record_id=record_id,
            problem_id=problem_id,
            score=score,
            knowledge_points=knowledge_points,
            problem_data=problem_data,
            user_answer=user_answer,
            verdict=verdict,
        )

        # ★★★ 推荐部分在主事件循环中执行（走异步 Agent，不阻塞）★★★
        if result.get("_need_async_recommend") and result.get("_recommend_attempt", 0) >= 3:
            try:
                rec_result = await self.recommend_materials_for_wrong_answer_async(
                    user_id=user_id,
                    knowledge_points=result.get("_recommend_kps", []),
                    attempt_count=result["_recommend_attempt"],
                    difficulty=result.get("_recommend_diff", ""),
                )
                if rec_result.get("should_recommend"):
                    result["material_recommendations"] = rec_result
                    # ★★★ 保存到缓存表，确保后续 API 调用返回相同推荐 ★★★
                    if record_id:
                        await self._save_recommendations_for_record(
                            record_id=record_id,
                            user_id=user_id,
                            materials=rec_result,
                        )
            except Exception as e:
                print(f"   ⚠️ [错题本] 编程题推荐失败: {e}")

        # 清理内部标记
        for k in ("_need_async_recommend", "_recommend_kps", "_recommend_attempt", "_recommend_diff"):
            result.pop(k, None)

        return result

    def _handle_judge_result_sync(self, **kwargs) -> Dict[str, Any]:
        """handle_judge_result 的同步 DB 操作部分"""
        # 复用原有的同步逻辑
        return self.handle_judge_result(**kwargs)

    async def submit_theory_answer(
        self,
        user_id: str,
        question_type: str,
        question: Dict[str, Any],
        user_answer: str,
        knowledge_points: Optional[List[str]] = None,
        source: str = "theory",
        record_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        提交理论题答案：使用 QuestionGeneratorAgent 统一判题，错误自动记入错题本

        Args:
            user_id: 用户ID
            question_type: 题目类型
            question: 题目完整数据（含answer字段）
            user_answer: 用户提交的答案
            knowledge_points: 知识点列表
            source: 来源

        Returns:
            Dict: 包含 is_correct、correct_answer、score、wrong_answer_recorded、message 等
        """
        from Agent.children_agent.question_generator_agent import QuestionGeneratorAgent

        judge_result = await QuestionGeneratorAgent.judge_theory_answer(
            question_data=question,
            user_answer=user_answer,
            question_type=question_type,
        )

        is_correct = judge_result["is_correct"]
        score = judge_result["score"]
        correct_answer = judge_result["correct_answer"]

        # ★★★ 如果 correct_answer 为空，兜底从 question 各字段尝试提取 ★★★
        if not correct_answer:
            # 尝试从 question 中其他可能的 answer 字段提取
            for _key in ("correct_answer", "correct", "solution", "right"):
                if question.get(_key):
                    correct_answer = str(question[_key])
                    break
            if not correct_answer:
                print(f"  ⚠️ [错题本] 题目缺少正确答案字段! question_type={question_type}, question={str(question)[:100]}")

        import hashlib
        kps = knowledge_points or []
        # ★★★ 兼容 knowledge_points 可能是字符串的情况 ★★★
        if isinstance(kps, str):
            kps = [k.strip() for k in kps.replace("，", ",").split(",") if k.strip()]
        q_text = question.get("question", question.get("description", ""))
        qid = f"q_{hashlib.md5(q_text.encode()).hexdigest()[:12]}"

        result = {
            "is_correct": is_correct,
            "score": score,
            "correct_answer": correct_answer,
            "user_answer": user_answer,
            "question_type": question_type,
        }

        if not is_correct:
            await asyncio.to_thread(
                self.add_wrong_answer,
                user_id=user_id,
                question_type=question_type,
                question_data=question,
                user_answer=user_answer,
                correct_answer=correct_answer,
                score=score,
                question_id=qid,
                knowledge_points=kps,
                source=source,
                verdict="Wrong",
                difficulty=question.get('difficulty', ''),
                record_id=record_id or "",
            )
            result["wrong_answer_recorded"] = True
            result["question_id"] = qid
            result["message"] = "答案错误，已自动加入错题本"
        else:
            await asyncio.to_thread(
                self.record_attempt,
                user_id=user_id,
                question_id=qid,
                question_type=question_type,
                user_answer=user_answer,
                score=score,
                verdict="Correct",
                record_id=record_id or "",
            )
            await asyncio.to_thread(self.mark_resolved, user_id=user_id, question_id=qid, score=score,
                                     record_id=record_id or "")
            result["wrong_answer_recorded"] = False
            result["question_id"] = qid
            result["message"] = "回答正确！已标记为已掌握"

        # 更新用户特征（DynamicFeatureUpdater）— 后台异步执行，不阻塞评分结果返回
        try:
            from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater
            updater = DynamicFeatureUpdater()
            features = await updater.get_latest_features_async(user_id)
            if features:
                # ★★★ 不 await，让特征更新在后台执行，评分结果先返回前端 ★★★
                asyncio.ensure_future(
                    updater.update_features_async(
                        current_features=features,
                        task_type="theory",
                        task_content=q_text,
                        performance_data={
                            "correct": is_correct,
                            "score": score,
                            "question_type": question_type,
                            "user_answer": user_answer,
                            "correct_answer": correct_answer,
                        },
                        completion_quality="high" if is_correct else "low",
                        user_id=user_id
                    )
                )
                result["feature_updated"] = True
        except Exception as e:
            print(f"  ⚠️ [错题本] 理论题特征更新失败: {e}")
            result["feature_updated"] = False

        # 记录到 MemoryHub（知识点掌握度 + 做题统计 + 遗忘曲线）
        try:
            from memory.memory_hub import MemoryHub
            memory_hub = MemoryHub()
            for kp in kps:
                await asyncio.to_thread(
                    memory_hub.record_learning,
                    user_id=user_id,
                    knowledge_point=kp,
                    resource_type="question",
                    resource_id=qid,
                    correct=is_correct,
                    time_spent=0
                )
            result["memoryhub_recorded"] = True
        except Exception as e:
            print(f"  ⚠️ [错题本] 理论题 MemoryHub 记录失败: {e}")
            result["memoryhub_recorded"] = False

        # 答错时检查是否达到3次，推荐学习资料（fire-and-forget，不阻塞响应）
        if not is_correct:
            async def _do_recommend():
                try:
                    with _get_conn() as conn:
                        row = conn.execute(
                            "SELECT record_id, attempt_count, difficulty FROM wrong_answers "
                            "WHERE user_id = ? AND question_id = ? AND question_type = ?",
                            (user_id, qid, question_type)
                        ).fetchone()
                    if row:
                        record_id = row["record_id"]
                        attempt_count = row["attempt_count"]
                        diff = row["difficulty"] or ""
                        rec_result = await self.recommend_materials_for_wrong_answer_async(
                            user_id=user_id,
                            knowledge_points=kps or [],
                            attempt_count=attempt_count,
                            difficulty=diff,
                        )
                        if rec_result.get("should_recommend"):
                            material_count = sum(len(v) for v in rec_result.get("materials", {}).values())
                            print(f"  ✅ [错题本] 学习资料推荐已生成 ({material_count} 条)")
                            # ★★★ 保存到缓存表，确保后续 API 调用返回相同推荐 ★★★
                            if record_id:
                                await self._save_recommendations_for_record(
                                    record_id=record_id,
                                    user_id=user_id,
                                    materials=rec_result,
                                )
                except Exception as e:
                    print(f"  ⚠️ [错题本] 理论题推荐失败: {e}")
            asyncio.ensure_future(_do_recommend())

        return result
