"""
teacher_db.py - 教师数据层

使用 SQLite 存储教师相关数据：
- classes          班级表（一个老师可带多个班）
- class_students   班级-学生关系表（支持多对多，学生可属于多个班）
- homework         作业表（含题目ID列表、截止时间）
- submission       提交+批改表（客观题自动批改 + 主观题手动评分双字段）

数据库路径: ./teacher_data/teacher.db

设计约定（可调整）：
- 师生关系：班级制（teacher → classes → class_students → student_id），学生 user_id 复用现有学生体系
- 批改：auto_score 由客观题对答案自动生成，manual_score 由教师手动填写主观题分数
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

DB_PATH = Path("./teacher_data/teacher.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

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
    """初始化所有表（幂等）"""
    with _get_conn() as conn:
        # 班级表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS classes (
                class_id    TEXT PRIMARY KEY,
                teacher_id  TEXT NOT NULL,
                class_name  TEXT NOT NULL,
                description TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        # 班级-学生关系表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS class_students (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id    TEXT NOT NULL,
                student_id  TEXT NOT NULL,
                added_at    TEXT NOT NULL,
                UNIQUE(class_id, student_id),
                FOREIGN KEY (class_id) REFERENCES classes(class_id) ON DELETE CASCADE
            )
        """)
        # 作业表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS homework (
                homework_id   TEXT PRIMARY KEY,
                class_id      TEXT NOT NULL,
                teacher_id    TEXT NOT NULL,
                title         TEXT NOT NULL,
                description   TEXT,
                question_ids  TEXT,
                auto_grade    INTEGER DEFAULT 1,
                due_at        TEXT,
                created_at    TEXT NOT NULL,
                FOREIGN KEY (class_id) REFERENCES classes(class_id) ON DELETE CASCADE
            )
        """)
        # 提交+批改表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submission (
                submission_id   TEXT PRIMARY KEY,
                homework_id     TEXT NOT NULL,
                student_id      TEXT NOT NULL,
                answers         TEXT,
                auto_score       REAL,
                manual_score     REAL,
                teacher_comment  TEXT,
                submitted_at     TEXT NOT NULL,
                graded_at       TEXT,
                status           TEXT DEFAULT 'submitted',
                FOREIGN KEY (homework_id) REFERENCES homework(homework_id) ON DELETE CASCADE
            )
        """)
        # 索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cs_tid ON class_students(student_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cs_cid ON class_students(class_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hw_tid ON homework(teacher_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_hw_cid ON homework(class_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sub_hid ON submission(homework_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sub_sid ON submission(student_id)")


# 模块加载时初始化
_init_db()


# ============ 班级 ============

def create_class(teacher_id: str, class_id: str, class_name: str,
                 description: str = "") -> Dict[str, Any]:
    """创建班级"""
    now = datetime.now().isoformat(timespec='seconds')
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO classes(class_id, teacher_id, class_name, description, created_at) VALUES(?,?,?,?,?)",
            (class_id, teacher_id, class_name, description, now)
        )
    return {"class_id": class_id, "teacher_id": teacher_id, "class_name": class_name, "created_at": now}


def list_classes(teacher_id: str) -> List[Dict[str, Any]]:
    """列出教师的所有班级（含学生数）"""
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT c.class_id, c.class_name, c.description, c.created_at,
                   (SELECT COUNT(*) FROM class_students cs WHERE cs.class_id = c.class_id) AS student_count
            FROM classes c
            WHERE c.teacher_id = ?
            ORDER BY c.created_at DESC
        """, (teacher_id,)).fetchall()
    return [dict(r) for r in rows]


def add_students_to_class(class_id: str, student_ids: List[str]) -> int:
    """批量把学生加入班级（跳过已存在的）"""
    now = datetime.now().isoformat(timespec='seconds')
    rows = [(class_id, sid, now) for sid in student_ids]
    with _get_conn() as conn:
        cur = conn.executemany(
            "INSERT OR IGNORE INTO class_students(class_id, student_id, added_at) VALUES(?,?,?)",
            rows
        )
        return cur.rowcount


def list_class_students(class_id: str) -> List[Dict[str, Any]]:
    """列出班级所有学生"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT student_id, added_at FROM class_students WHERE class_id = ? ORDER BY added_at",
            (class_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ============ 作业 ============

def create_homework(teacher_id: str, class_id: str, homework_id: str,
                    title: str, description: str = "",
                    question_ids: Optional[List[str]] = None,
                    auto_grade: bool = True,
                    due_at: Optional[str] = None) -> Dict[str, Any]:
    """创建作业"""
    now = datetime.now().isoformat(timespec='seconds')
    qids_json = json.dumps(question_ids or [], ensure_ascii=False)
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO homework(homework_id, class_id, teacher_id, title, description,
               question_ids, auto_grade, due_at, created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (homework_id, class_id, teacher_id, title, description,
             qids_json, 1 if auto_grade else 0, due_at, now)
        )
    return {"homework_id": homework_id, "class_id": class_id, "title": title, "created_at": now}


def list_homework(teacher_id: Optional[str] = None,
                  class_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出作业（可按教师或班级过滤）"""
    sql = "SELECT * FROM homework WHERE 1=1"
    params: List[Any] = []
    if teacher_id:
        sql += " AND teacher_id = ?"
        params.append(teacher_id)
    if class_id:
        sql += " AND class_id = ?"
        params.append(class_id)
    sql += " ORDER BY created_at DESC"
    with _get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["question_ids"] = json.loads(d["question_ids"]) if d["question_ids"] else []
        d["auto_grade"] = bool(d["auto_grade"])
        result.append(d)
    return result


def get_homework(homework_id: str) -> Optional[Dict[str, Any]]:
    """获取单个作业"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM homework WHERE homework_id = ?", (homework_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["question_ids"] = json.loads(d["question_ids"]) if d["question_ids"] else []
    d["auto_grade"] = bool(d["auto_grade"])
    return d


# ============ 提交与批改 ============

def submit_homework(homework_id: str, student_id: str,
                    submission_id: str, answers: Dict[str, Any],
                    auto_score: Optional[float] = None) -> Dict[str, Any]:
    """学生提交作业（auto_score 由客观题自动批改填入，无则 None）"""
    now = datetime.now().isoformat(timespec='seconds')
    answers_json = json.dumps(answers, ensure_ascii=False)
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO submission(submission_id, homework_id, student_id, answers,
               auto_score, submitted_at, status) VALUES(?,?,?,?,?,?,?)""",
            (submission_id, homework_id, student_id, answers_json, auto_score, now, 'submitted')
        )
    return {"submission_id": submission_id, "auto_score": auto_score, "submitted_at": now}


def grade_submission(submission_id: str, manual_score: float,
                     teacher_comment: str = "") -> Dict[str, Any]:
    """教师手动批改（主观题评分 + 评语）"""
    now = datetime.now().isoformat(timespec='seconds')
    with _get_conn() as conn:
        conn.execute(
            """UPDATE submission SET manual_score=?, teacher_comment=?, graded_at=?, status='graded'
               WHERE submission_id=?""",
            (manual_score, teacher_comment, now, submission_id)
        )
    return {"submission_id": submission_id, "manual_score": manual_score, "graded_at": now}


def list_submissions(homework_id: str) -> List[Dict[str, Any]]:
    """列出某作业的所有提交（供教师查看批改进度）"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM submission WHERE homework_id = ? ORDER BY submitted_at DESC",
            (homework_id,)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["answers"] = json.loads(d["answers"]) if d["answers"] else {}
        result.append(d)
    return result


def get_student_submissions(student_id: str) -> List[Dict[str, Any]]:
    """查某学生的所有提交（学情查看）"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM submission WHERE student_id = ? ORDER BY submitted_at DESC",
            (student_id,)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["answers"] = json.loads(d["answers"]) if d["answers"] else {}
        result.append(d)
    return result


# ============ 学情查询（只读聚合） ============

def get_class_progress(class_id: str) -> Dict[str, Any]:
    """班级学情概览：学生数、作业数、平均分、提交率"""
    with _get_conn() as conn:
        student_count = conn.execute(
            "SELECT COUNT(*) FROM class_students WHERE class_id=?", (class_id,)
        ).fetchone()[0]
        homework_rows = conn.execute(
            "SELECT homework_id FROM homework WHERE class_id=?", (class_id,)
        ).fetchall()
        homework_ids = [r["homework_id"] for r in homework_rows]
        if homework_ids:
            placeholders = ",".join("?" * len(homework_ids))
            sub_rows = conn.execute(
                f"SELECT student_id, auto_score, manual_score, status FROM submission WHERE homework_id IN ({placeholders})",
                homework_ids
            ).fetchall()
        else:
            sub_rows = []
    total_sub = len(sub_rows)
    graded = [r for r in sub_rows if r["status"] == "graded"]
    scores = []
    for r in graded:
        a = r["auto_score"] if r["auto_score"] is not None else None
        m = r["manual_score"] if r["manual_score"] is not None else None
        # 综合分：优先取平均，单一存在取单一
        if a is not None and m is not None:
            scores.append((a + m) / 2)
        elif a is not None:
            scores.append(a)
        elif m is not None:
            scores.append(m)
    avg_score = sum(scores) / len(scores) if scores else 0.0
    submit_rate = (total_sub / (student_count * len(homework_ids))) if (student_count and homework_ids) else 0.0
    return {
        "class_id": class_id,
        "student_count": student_count,
        "homework_count": len(homework_ids),
        "submission_count": total_sub,
        "graded_count": len(graded),
        "avg_score": round(avg_score, 2),
        "submit_rate": round(submit_rate, 3)
    }


if __name__ == "__main__":
    # 简单自测
    print("DB at:", DB_PATH)
    print("create_class:", create_class("teacher_001", "cls_demo", "演示班级"))
    print("add_students:", add_students_to_class("cls_demo", ["stu_1", "stu_2", "stu_3"]))
    print("list_classes:", list_classes("teacher_001"))
    print("create_homework:", create_homework("teacher_001", "cls_demo", "hw_1", "第一周作业",
                                              question_ids=["q1", "q2"], due_at="2026-09-01T23:59:59"))
    print("submit:", submit_homework("hw_1", "stu_1", "sub_1", {"q1": "A", "q2": "B"}, auto_score=80.0))
    print("grade:", grade_submission("sub_1", 85.0, "主观题不错"))
    print("class_progress:", get_class_progress("cls_demo"))
