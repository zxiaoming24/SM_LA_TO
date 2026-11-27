"""
resource_db.py - 资源数据库（题库 / 文档库 / 视频库）

使用 SQLite 存储资源的结构化元数据，支持精确条件过滤。
ChromaDB 负责语义搜索，见 semantic_store.py

数据库路径: ./recommendation_data/resource_bank.db
"""

import sqlite3
import json
import uuid
import hashlib
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

DB_PATH = Path("./recommendation_data/resource_bank.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_RECORDS_DB_PATH = DB_PATH.parent / "learning_records.db"

# =============================================================================
# 资源基类 + 三类资源表
# =============================================================================

# ★★★ 使用单连接 + 线程锁替代多线程各自连接方案，
# 彻底消除 WAL 模式下多连接并发写导致的 [Errno 36] Resource deadlock avoided ★★★
_db_lock = threading.RLock()
_shared_conn: Optional[sqlite3.Connection] = None

def _get_conn() -> sqlite3.Connection:
    """
    获取共享 SQLite 连接。
    使用单连接避免 WAL 模式下多连接并发写导致的死锁。
    """
    global _shared_conn
    if _shared_conn is None:
        _shared_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10)
        _shared_conn.row_factory = sqlite3.Row
        _shared_conn.execute("PRAGMA journal_mode=WAL")
        _shared_conn.execute("PRAGMA busy_timeout=10000")
    return _shared_conn


@contextmanager
def _locked_conn():
    """线程安全的数据库连接上下文管理器，单连接 + 互斥锁消除死锁。"""
    conn = _get_conn()
    _db_lock.acquire()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _db_lock.release()


def _init_db():
    with _locked_conn() as conn:
        # ---------- 题目 ----------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id           TEXT PRIMARY KEY,
                topic        TEXT NOT NULL,
                sub_topic    TEXT,
                difficulty   INTEGER NOT NULL CHECK(difficulty BETWEEN 1 AND 5),
                knowledge_points TEXT NOT NULL,
                content      TEXT NOT NULL,
                solution     TEXT,
                hints        TEXT,
                metadata     TEXT,
                times_shown  INTEGER DEFAULT 0,
                times_correct INTEGER DEFAULT 0,
                created_at   TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_q_topic   ON questions(topic)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_q_diff    ON questions(difficulty)")
        # ★ 兼容旧表没有 title 列 ★
        try:
            conn.execute("ALTER TABLE questions ADD COLUMN title TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # 列已存在，忽略
        # ★ 选择题选项（JSON数组字符串）★
        try:
            conn.execute("ALTER TABLE questions ADD COLUMN options TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # 列已存在，忽略

        # ---------- 文档 ----------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id           TEXT PRIMARY KEY,
                category     TEXT NOT NULL,
                title        TEXT NOT NULL,
                topic        TEXT NOT NULL,
                difficulty   INTEGER NOT NULL CHECK(difficulty BETWEEN 1 AND 5),
                knowledge_points TEXT,
                content      TEXT,
                summary      TEXT,
                metadata     TEXT,
                times_accessed INTEGER DEFAULT 0,
                times_completed INTEGER DEFAULT 0,
                created_at   TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_d_cat    ON documents(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_d_topic  ON documents(topic)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_d_diff   ON documents(difficulty)")

        # ---------- 视频 ----------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id           TEXT PRIMARY KEY,
                platform     TEXT NOT NULL,
                title        TEXT NOT NULL,
                topic        TEXT NOT NULL,
                difficulty   INTEGER NOT NULL CHECK(difficulty BETWEEN 1 AND 5),
                knowledge_points TEXT,
                duration_sec INTEGER,
                url          TEXT,
                thumbnail    TEXT,
                metadata     TEXT,
                times_played INTEGER DEFAULT 0,
                completion_rate REAL DEFAULT 0.0,
                rating       REAL DEFAULT 0.0,
                created_at   TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v_topic  ON videos(topic)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v_diff   ON videos(difficulty)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v_dur   ON videos(duration_sec)")

        conn.commit()

_init_db()


class ResourceDB:
    _local = threading.local()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            self._local.conn = _get_conn()
        return self._local.conn

    # -------------------------------------------------------------------------
    # 内容指纹去重工具
    # -------------------------------------------------------------------------

    @staticmethod
    def _content_fingerprint(content: str) -> str:
        """
        计算内容指纹：对内容做标准化处理后取 MD5 哈希。
        用于检测内容重复，即使 LLM 输出有细微差异也能识别相同题目。
        """
        if not content:
            return ""
        # 标准化：去首尾空白、转小写、合并连续空白
        normalized = " ".join(content.strip().lower().split())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def _find_by_content(self, content: str, topic: str = None,
                          conn: sqlite3.Connection = None) -> Optional[str]:
        """
        通过内容指纹查找是否已存在相同内容的题目。
        返回已存在的题目 ID，找不到返回 None。

        Args:
            conn: 可选，外部传入的连接（用于避免嵌套 with 导致事务冲突）
        """
        fp = self._content_fingerprint(content)
        if not fp:
            return None
        sql = "SELECT id, content FROM questions WHERE content IS NOT NULL AND content != ''"
        params: List[Any] = []
        if topic:
            sql += " AND topic = ?"
            params.append(topic)
        if conn is not None:
            rows = conn.execute(sql, params).fetchall()
        else:
            with _locked_conn() as c:
                rows = c.execute(sql, params).fetchall()
        for row in rows:
            if self._content_fingerprint(row["content"]) == fp:
                return row["id"]
        return None

    # -------------------------------------------------------------------------
    # 题目 CRUD
    # -------------------------------------------------------------------------

    def add_question(self, topic: str, sub_topic: str, difficulty: int,
                     knowledge_points: List[str], content: str,
                     solution: str = "", hints: List[str] = None,
                     metadata: Dict = None,
                     title: str = "",
                     options: List[str] = None) -> str:
        # ★★★ 先检查内容是否已存在 ★★★
        existing_id = self._find_by_content(content, topic)
        if existing_id:
            print(f"  📦 [题库] 内容相同的题目已存在（{existing_id}），跳过新建")
            return existing_id
        qid = f"q_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        with _locked_conn() as conn:
            conn.execute("""
                INSERT INTO questions
                    (id, topic, sub_topic, difficulty, knowledge_points,
                     title, content, solution, hints, options, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                qid, topic, sub_topic, difficulty,
                ",".join(knowledge_points), title, content, solution,
                json.dumps(hints or [], ensure_ascii=False),
                json.dumps(options or [], ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False),
                now
            ))
            conn.commit()
        return qid

    def upsert_question(self, qid: str, topic: str, sub_topic: str, difficulty: int,
                        knowledge_points: List[str], content: str,
                        solution: str = "", hints: List[str] = None,
                        metadata: Dict = None,
                        title: str = "",
                        options: List[str] = None) -> str:
        """写入题目到题库。如果已存在则不覆盖，保留首次生成的内容。"""
        now = datetime.now().isoformat()
        with _locked_conn() as conn:
            # ★★★ 先按 ID 检查 ★★★
            existing = conn.execute(
                "SELECT id FROM questions WHERE id = ?", (qid,)
            ).fetchone()
            if existing:
                # print(f"  [题库] 题目 {qid} 已存在，跳过覆盖（保留首次生成内容）")
                return qid
            # ★★★ 再按内容指纹检查（防内容相同但 ID 不同）★★★
            # 传入 conn 避免嵌套 with 导致事务冲突
            dup_id = self._find_by_content(content, conn=conn)
            if dup_id:
                print(f"  📦 [题库] 内容相同的题目已存在（{dup_id}），跳过新建（传入ID={qid}）")
                return dup_id
            conn.execute("""
                INSERT INTO questions
                    (id, topic, sub_topic, difficulty, knowledge_points,
                     title, content, solution, hints, options, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                qid, topic, sub_topic, difficulty,
                ",".join(knowledge_points), title, content, solution,
                json.dumps(hints or [], ensure_ascii=False),
                json.dumps(options or [], ensure_ascii=False),
                json.dumps(metadata or {}, ensure_ascii=False),
                now
            ))
            conn.commit()
        return qid

    def get_question(self, qid: str) -> Optional[Dict]:
        with _locked_conn() as conn:
            row = conn.execute(
                "SELECT * FROM questions WHERE id = ?", (qid,)
            ).fetchone()
        return self._parse_question_row(row)

    @staticmethod
    def _parse_question_row(row) -> Optional[Dict]:
        """将 DB row 转为 dict，解析 JSON 字段为 Python 对象"""
        if not row:
            return None
        d = dict(row)
        for field in ("options", "hints", "metadata"):
            val = d.get(field)
            if val and isinstance(val, str):
                try:
                    d[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[field] = [] if field != "metadata" else {}
        if not d.get("options"):
            d["options"] = []
        # ★★★ 从 metadata 中提取 source（如 agent_generated），供前端展示徽章 ★★★
        meta = d.get("metadata")
        if isinstance(meta, dict) and meta.get("source") and not d.get("source"):
            d["source"] = meta["source"]
        return d

    def _parse_question_rows(self, rows) -> List[Dict]:
        return [self._parse_question_row(r) for r in rows]

    def get_document(self, did: str) -> Optional[Dict]:
        with _locked_conn() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (did,)
            ).fetchone()
        return dict(row) if row else None

    def find_questions(self, topic: str = None, difficulty: int = None,
                       knowledge_point: str = None,
                       limit: int = 20) -> List[Dict]:
        sql = "SELECT * FROM questions WHERE content IS NOT NULL AND content != ''"
        params = []
        if topic:
            sql += " AND (topic = ? OR knowledge_points LIKE ?)"
            params.append(topic)
            params.append(f"%{topic}%")
        if difficulty:
            sql += " AND difficulty = ?"
            params.append(difficulty)
        if knowledge_point:
            sql += " AND knowledge_points LIKE ?"
            params.append(f"%{knowledge_point}%")
        sql += " ORDER BY RANDOM() LIMIT ?"
        params.append(limit)
        with _locked_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return self._parse_question_rows(rows)

    def increment_question_stat(self, qid: str, correct: bool):
        _VALID_COLS = {"times_correct": "times_correct", "times_shown": "times_shown"}
        col = "times_correct" if correct else "times_shown"
        col = _VALID_COLS.get(col, "times_shown")
        with _locked_conn() as conn:
            conn.execute(f"UPDATE questions SET {col} = {col} + 1 WHERE id = ?", (qid,))
            conn.commit()

    def get_user_unseen_questions(self, user_id: str, topic: str = None,
                                   difficulty: int = None, question_type: str = None,
                                   limit: int = 10) -> List[Dict]:
        with _locked_conn() as conn:
            conn.execute(f"ATTACH DATABASE '{_RECORDS_DB_PATH}' AS recdb")
            sql = """
                SELECT q.* FROM questions q
                WHERE q.content IS NOT NULL AND q.content != ''
                AND q.id NOT IN (
                    SELECT resource_id FROM recdb.user_solutions WHERE user_id = ?
                )
            """
            params: List[Any] = [user_id]
            if topic:
                sql += " AND q.topic = ?"
                params.append(topic)
            if difficulty:
                sql += " AND q.difficulty = ?"
                params.append(difficulty)
            if question_type == 'theory':
                sql += " AND q.sub_topic IN ('single_choice','multiple_choice','judge','fill_blank','short_answer')"
            elif question_type == 'practice':
                sql += " AND (q.sub_topic IS NULL OR q.sub_topic = '' OR q.sub_topic NOT IN ('single_choice','multiple_choice','judge','fill_blank','short_answer'))"
            sql += " ORDER BY RANDOM() LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            conn.execute("DETACH DATABASE recdb")
        return self._parse_question_rows(rows)

    # -------------------------------------------------------------------------
    # 文档 CRUD
    # -------------------------------------------------------------------------

    def add_document(self, category: str, title: str, topic: str,
                    difficulty: int, knowledge_points: List[str] = None,
                    content: str = "", summary: str = "",
                    metadata: Dict = None) -> str:
        did = f"d_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        with _locked_conn() as conn:
            conn.execute("""
                INSERT INTO documents
                    (id, category, title, topic, difficulty,
                     knowledge_points, content, summary, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                did, category, title, topic, difficulty,
                ",".join(knowledge_points or []),
                content, summary,
                json.dumps(metadata or {}, ensure_ascii=False),
                now
            ))
            conn.commit()
        return did

    def _find_doc_by_content(self, content: str, topic: str = None,
                              conn: sqlite3.Connection = None) -> Optional[str]:
        """通过内容指纹查找是否已存在相同内容的文档。"""
        fp = self._content_fingerprint(content)
        if not fp:
            return None
        sql = "SELECT id, content FROM documents WHERE content IS NOT NULL AND content != ''"
        params: List[Any] = []
        if topic:
            sql += " AND topic = ?"
            params.append(topic)
        if conn is not None:
            rows = conn.execute(sql, params).fetchall()
        else:
            with _locked_conn() as c:
                rows = c.execute(sql, params).fetchall()
        for row in rows:
            if self._content_fingerprint(row["content"]) == fp:
                return row["id"]
        return None

    def upsert_document(self, did: str, category: str, title: str, topic: str,
                        difficulty: int, knowledge_points: List[str] = None,
                        content: str = "", summary: str = "",
                        metadata: Dict = None) -> str:
        now = datetime.now().isoformat()
        with _locked_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM documents WHERE id = ?", (did,)
            ).fetchone()
            if existing:
                # print(f"  [题库] 文档 {did} 已存在，跳过覆盖")
                return did
            # ★★★ 按内容指纹检查（传入 conn 避免嵌套事务冲突）★★★
            dup_id = self._find_doc_by_content(content, conn=conn)
            if dup_id:
                print(f"  📦 [题库] 内容相同的文档已存在（{dup_id}），跳过新建（传入ID={did}）")
                return dup_id
            conn.execute("""
                INSERT INTO documents
                    (id, category, title, topic, difficulty,
                     knowledge_points, content, summary, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                did, category, title, topic, difficulty,
                ",".join(knowledge_points or []),
                content, summary,
                json.dumps(metadata or {}, ensure_ascii=False),
                now
            ))
            conn.commit()
        return did

    def find_documents(self, category: str = None, topic: str = None,
                       difficulty: int = None, limit: int = 10) -> List[Dict]:
        sql = "SELECT * FROM documents WHERE content IS NOT NULL AND content != ''"
        params = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if topic:
            sql += " AND (topic = ? OR knowledge_points LIKE ?)"
            params.append(topic)
            params.append(f"%{topic}%")
        if difficulty:
            sql += " AND difficulty = ?"
            params.append(difficulty)
        sql += " ORDER BY RANDOM() LIMIT ?"
        params.append(limit)
        with _locked_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # 视频 CRUD
    # -------------------------------------------------------------------------

    def add_video(self, platform: str, title: str, topic: str,
                  difficulty: int, duration_sec: int = 0,
                  url: str = "", knowledge_points: List[str] = None,
                  metadata: Dict = None) -> str:
        vid = f"v_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()
        with _locked_conn() as conn:
            conn.execute("""
                INSERT INTO videos
                    (id, platform, title, topic, difficulty,
                     duration_sec, url, knowledge_points, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                vid, platform, title, topic, difficulty,
                duration_sec, url,
                ",".join(knowledge_points or []),
                json.dumps(metadata or {}, ensure_ascii=False),
                now
            ))
            conn.commit()
        return vid

    def upsert_video(self, vid: str, platform: str, title: str, topic: str,
                     difficulty: int, duration_sec: int = 0,
                     url: str = "", knowledge_points: List[str] = None,
                     metadata: Dict = None) -> str:
        now = datetime.now().isoformat()
        with _locked_conn() as conn:
            # ★★★ 先按 URL 去重（视频最稳定的标识）★★★
            if url:
                existing_url = conn.execute(
                    "SELECT id FROM videos WHERE url = ?", (url,)
                ).fetchone()
                if existing_url:
                    # print(f"  [题库] 视频 URL 已存在（{existing_url['id']}），跳过新建（传入ID={vid}）")
                    return existing_url["id"]
            # ★★★ 再按 ID 检查 ★★★
            existing = conn.execute(
                "SELECT id FROM videos WHERE id = ?", (vid,)
            ).fetchone()
            if existing:
                return vid
            conn.execute("""
                INSERT INTO videos
                    (id, platform, title, topic, difficulty,
                     duration_sec, url, knowledge_points, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                vid, platform, title, topic, difficulty,
                duration_sec, url,
                ",".join(knowledge_points or []),
                json.dumps(metadata or {}, ensure_ascii=False),
                now
            ))
            conn.commit()
        return vid

    def find_videos(self, topic: str = None, difficulty: int = None,
                    max_duration: int = None, limit: int = 10) -> List[Dict]:
        sql = "SELECT * FROM videos WHERE title IS NOT NULL AND title != '' AND url IS NOT NULL AND url != ''"
        params = []
        if topic:
            sql += " AND (topic = ? OR knowledge_points LIKE ?)"
            params.append(topic)
            params.append(f"%{topic}%")
        if difficulty:
            sql += " AND difficulty = ?"
            params.append(difficulty)
        if max_duration:
            sql += " AND duration_sec <= ?"
            params.append(max_duration)
        sql += " ORDER BY RANDOM() LIMIT ?"
        params.append(limit)
        with _locked_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_video(self, vid: str) -> Optional[Dict]:
        with _locked_conn() as conn:
            row = conn.execute(
                "SELECT * FROM videos WHERE id = ?", (vid,)
            ).fetchone()
        return dict(row) if row else None

    def increment_video_stat(self, vid: str, completed: bool = False,
                              completion_rate: float = 0.0):
        with _locked_conn() as conn:
            conn.execute(
                "UPDATE videos SET times_played = times_played + 1"
                + (", completion_rate = ? " if completed else " ")
                + "WHERE id = ?",
                (completion_rate, vid) if completed else (vid,)
            )
            conn.commit()

    # -------------------------------------------------------------------------
    # 统计
    # -------------------------------------------------------------------------

    def get_topic_stats(self) -> Dict[str, int]:
        with _locked_conn() as conn:
            rows = conn.execute("""
                SELECT topic, COUNT(*) as cnt FROM questions GROUP BY topic
                UNION ALL
                SELECT topic, COUNT(*) as cnt FROM documents GROUP BY topic
                UNION ALL
                SELECT topic, COUNT(*) as cnt FROM videos GROUP BY topic
            """).fetchall()
        stats = {}
        for r in rows:
            stats[r["topic"]] = stats.get(r["topic"], 0) + r["cnt"]
        return stats

    def get_all_topics(self) -> List[str]:
        with _locked_conn() as conn:
            rows = conn.execute("""
                SELECT topic FROM questions
                UNION SELECT topic FROM documents
                UNION SELECT topic FROM videos
            """).fetchall()
        return [r["topic"] for r in rows]

    def get_question_topics(self) -> List[str]:
        """仅获取 questions 表中的知识点列表（用于编程题匹配）"""
        with _locked_conn() as conn:
            rows = conn.execute("SELECT DISTINCT topic FROM questions").fetchall()
        return [r["topic"] for r in rows]

    # -------------------------------------------------------------------------
    # 管理端 CRUD 补充
    # -------------------------------------------------------------------------

    def update_question(self, qid: str, **kwargs) -> bool:
        """
        更新题目信息。仅更新传入的字段，不修改未传入的字段。

        支持的字段: topic, sub_topic, difficulty, knowledge_points, title,
                     content, solution, hints, options, metadata
        """
        allowed = {"topic", "sub_topic", "difficulty", "knowledge_points",
                    "title", "content", "solution", "hints", "options", "metadata"}
        sets = []
        params = []
        for key, val in kwargs.items():
            if key not in allowed:
                continue
            if key in ("hints", "options", "metadata"):
                val = json.dumps(val, ensure_ascii=False) if val is not None else ""
            elif key == "knowledge_points" and isinstance(val, (list, tuple)):
                val = ",".join(val)
            sets.append(f"{key} = ?")
            params.append(val)
        if not sets:
            return False
        params.append(qid)
        with _locked_conn() as conn:
            conn.execute(
                f"UPDATE questions SET {', '.join(sets)} WHERE id = ?", params
            )
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0

    def delete_question(self, qid: str) -> bool:
        """从题库中删除指定题目"""
        with _locked_conn() as conn:
            conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0

    def count_questions(self, topic: str = None, difficulty: int = None,
                        question_type: str = None) -> int:
        """统计符合条件的题目数量
        question_type: 'theory'=理论题, 'practice'=编程题, None=全部
        """
        sql = "SELECT COUNT(*) as cnt FROM questions WHERE 1=1"
        params = []
        if topic:
            sql += " AND topic = ?"
            params.append(topic)
        if difficulty:
            sql += " AND difficulty = ?"
            params.append(difficulty)
        if question_type == 'theory':
            sql += " AND sub_topic IN ('single_choice','multiple_choice','judge','fill_blank','short_answer')"
        elif question_type == 'practice':
            sql += " AND (sub_topic IS NULL OR sub_topic = '' OR sub_topic NOT IN ('single_choice','multiple_choice','judge','fill_blank','short_answer'))"
        with _locked_conn() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["cnt"] if row else 0

    def list_questions(self, topic: str = None, difficulty: int = None,
                       keyword: str = None, page: int = 1, page_size: int = 20,
                       order_by: str = "created_at DESC",
                       question_type: str = None) -> dict:
        """
        分页列出题目，支持按 topic / difficulty / keyword / question_type 过滤。
        question_type: 'theory'=理论题, 'practice'=编程题, None=全部
        返回: {"total": N, "page": P, "page_size": S, "items": [...]}
        """
        sql = "SELECT * FROM questions WHERE 1=1"
        count_sql = "SELECT COUNT(*) as cnt FROM questions WHERE 1=1"
        params = []
        if topic:
            sql += " AND topic = ?"
            count_sql += " AND topic = ?"
            params.append(topic)
        if difficulty:
            sql += " AND difficulty = ?"
            count_sql += " AND difficulty = ?"
            params.append(difficulty)
        if keyword:
            sql += " AND (title LIKE ? OR content LIKE ? OR knowledge_points LIKE ?)"
            count_sql += " AND (title LIKE ? OR content LIKE ? OR knowledge_points LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])
        if question_type == 'theory':
            sql += " AND sub_topic IN ('single_choice','multiple_choice','judge','fill_blank','short_answer')"
            count_sql += " AND sub_topic IN ('single_choice','multiple_choice','judge','fill_blank','short_answer')"
        elif question_type == 'practice':
            sql += " AND (sub_topic IS NULL OR sub_topic = '' OR sub_topic NOT IN ('single_choice','multiple_choice','judge','fill_blank','short_answer'))"
            count_sql += " AND (sub_topic IS NULL OR sub_topic = '' OR sub_topic NOT IN ('single_choice','multiple_choice','judge','fill_blank','short_answer'))"
        # 排序 & 分页
        order_map = {"created_at": "created_at", "difficulty": "difficulty",
                     "topic": "topic", "title": "title"}
        order_col = order_map.get(order_by.split()[0], "created_at")
        order_dir = "ASC" if "asc" in order_by.lower() else "DESC"
        sql += f" ORDER BY {order_col} {order_dir}"
        offset = (page - 1) * page_size
        sql += " LIMIT ? OFFSET ?"
        params_limit = params + [page_size, offset]

        with _locked_conn() as conn:
            total = conn.execute(count_sql, params).fetchone()["cnt"]
            rows = conn.execute(sql, params_limit).fetchall()
        items = self._parse_question_rows(rows)
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    # -------------------------------------------------------------------------
    # 管理端视频 CRUD
    # -------------------------------------------------------------------------

    def update_video(self, vid: str, **kwargs) -> bool:
        """更新视频信息。仅更新传入的字段。"""
        allowed = {"platform", "title", "topic", "difficulty", "duration_sec",
                    "url", "knowledge_points", "metadata"}
        sets = []
        params = []
        for key, val in kwargs.items():
            if key not in allowed:
                continue
            if key == "metadata":
                val = json.dumps(val, ensure_ascii=False) if val is not None else ""
            elif key == "knowledge_points" and isinstance(val, (list, tuple)):
                val = ",".join(val)
            sets.append(f"{key} = ?")
            params.append(val)
        if not sets:
            return False
        params.append(vid)
        with _locked_conn() as conn:
            conn.execute(f"UPDATE videos SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0

    def delete_video(self, vid: str) -> bool:
        """从库中删除指定视频"""
        with _locked_conn() as conn:
            conn.execute("DELETE FROM videos WHERE id = ?", (vid,))
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0

    def count_videos(self, topic: str = None, difficulty: int = None,
                     platform: str = None) -> int:
        """统计符合条件的视频数量"""
        sql = "SELECT COUNT(*) as cnt FROM videos WHERE 1=1"
        params = []
        if topic:
            sql += " AND (topic = ? OR knowledge_points LIKE ?)"
            params.extend([topic, f"%{topic}%"])
        if difficulty:
            sql += " AND difficulty = ?"
            params.append(difficulty)
        if platform:
            sql += " AND platform = ?"
            params.append(platform)
        with _locked_conn() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["cnt"] if row else 0

    def list_videos(self, topic: str = None, difficulty: int = None,
                    platform: str = None, keyword: str = None,
                    page: int = 1, page_size: int = 20,
                    order_by: str = "created_at DESC") -> dict:
        """分页列出视频"""
        sql = "SELECT * FROM videos WHERE 1=1"
        count_sql = "SELECT COUNT(*) as cnt FROM videos WHERE 1=1"
        params = []
        if topic:
            sql += " AND (topic = ? OR knowledge_points LIKE ?)"
            count_sql += " AND (topic = ? OR knowledge_points LIKE ?)"
            params.extend([topic, f"%{topic}%"])
        if difficulty:
            sql += " AND difficulty = ?"
            count_sql += " AND difficulty = ?"
            params.append(difficulty)
        if platform:
            sql += " AND platform = ?"
            count_sql += " AND platform = ?"
            params.append(platform)
        if keyword:
            sql += " AND (title LIKE ? OR topic LIKE ?)"
            count_sql += " AND (title LIKE ? OR topic LIKE ?)"
            kw = f"%{keyword}%"
            params.extend([kw, kw])
        order_map = {"created_at": "created_at", "difficulty": "difficulty",
                     "title": "title", "duration_sec": "duration_sec"}
        order_col = order_map.get(order_by.split()[0], "created_at")
        order_dir = "ASC" if "asc" in order_by.lower() else "DESC"
        sql += f" ORDER BY {order_col} {order_dir}"
        offset = (page - 1) * page_size
        sql += " LIMIT ? OFFSET ?"
        params_limit = params + [page_size, offset]
        with _locked_conn() as conn:
            total = conn.execute(count_sql, params).fetchone()["cnt"]
            rows = conn.execute(sql, params_limit).fetchall()
        return {"total": total, "page": page, "page_size": page_size,
                "items": [dict(r) for r in rows]}

    def get_video_topics(self) -> List[str]:
        """获取视频表中的所有主题"""
        with _locked_conn() as conn:
            rows = conn.execute("SELECT DISTINCT topic FROM videos").fetchall()
        return [r["topic"] for r in rows]
