import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import sqlite3

conn = sqlite3.connect('./wrong_answer_data/wrong_answers.db')
conn.row_factory = sqlite3.Row

# 查所有 wrong_answer_attempts 中 score 不为 100 但 verdict 为 Correct 的记录
rows = conn.execute("""
    SELECT wa.id, wa.record_id, wa.question_type, wa.question_id, wa.mastered_score,
           att.attempt_number, att.score as att_score, att.verdict, att.created_at
    FROM wrong_answer_attempts att
    JOIN wrong_answers wa ON att.wrong_answer_id = wa.id
    WHERE wa.user_id = 'user_001'
    ORDER BY wa.id DESC, att.attempt_number ASC
    LIMIT 30
""").fetchall()

for r in rows:
    flag = " <-- score=0 but verdict=Correct!" if r['att_score'] == 0 and r['verdict'] == 'Correct' else ""
    print(f"  record_id={r['record_id']} type={r['question_type']} qid={r['question_id']} "
          f"mastered_score={r['mastered_score']} | "
          f"attempt#{r['attempt_number']} score={r['att_score']} verdict={r['verdict']}{flag}")

conn.close()
