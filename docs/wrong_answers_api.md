# 错题模块 — 路由与字段手册

## 路由总览

| # | 方法 | 路由 | 用途 |
|---|---|---|---|
| 1 | GET | `/wrong-answers/{user_id}` | 获取错题列表（分页） |
| 2 | GET | `/wrong-answers/{user_id}/stats` | 获取错题统计 |
| 3 | GET | `/wrong-answers/{user_id}/mastered` | 获取已掌握列表 |
| 4 | GET | `/wrong-answers/{record_id}/recommend/{user_id}` | 获取推荐学习资料 |
| 5 | POST | `/wrong-answers/llm-generate` | AI生成补充资料 |
| 6 | DELETE | `/wrong-answers/{record_id}/{user_id}` | 删除错题 |
| 7 | POST | `/practice/rejudge` | 错题重练（编程题） |
| 8 | POST | `/theory/submit` | 提交理论题答案 |

---

## 路由1：`GET /wrong-answers/{user_id}`

### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `user_id` | path:str | ✅ | - | 用户ID |
| `page` | query:int | ❌ | 1 | 页码 |
| `page_size` | query:int | ❌ | 20 | 每页条数 |
| `question_type` | query:str\|None | ❌ | null | 筛选：`programming` / `single_choice` / `multiple_choice` / `judge` / `fill_blank` / `short_answer` |
| `source` | query:str\|None | ❌ | null | 筛选来源：`programming` / `theory` |
| `show_resolved` | query:bool | ❌ | false | 是否包含已掌握 |

### 响应结构

```json
{
  "success": true,
  "records": [
    {
      "id": 1,
      "record_id": "wa_abc123",
      "user_id": "user_001",
      "question_type": "programming",
      "question_data": { /* 见下方 question_data 二义性说明 */ },
      "user_answer": "print('hello')",
      "correct_answer": "",
      "score": 30,
      "problem_id": "P_xxx",
      "question_id": "",
      "knowledge_points": ["循环结构", "数组操作"],
      "source": "programming",
      "attempt_count": 3,
      "resolved": 0,
      "created_at": "2026-06-07T12:00:00",
      "mastered_at": "",
      "mastered_score": 0,
      "attempts": [
        {
          "attempt_number": 1,
          "user_answer": "print('hi')",
          "score": 20,
          "verdict": "Wrong Answer",
          "created_at": "2026-06-07T12:00:00"
        }
      ]
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

### ⚠️ `question_data` 二义性

`question_data` 是 JSON 存入的，但结构根据题型不同而不同：

| 字段 | 编程题（`source=programming`） | 理论题（`source=theory`） |
|---|---|---|
| 题目内容 | `title` + `description` | `question` |
| 选项 | ❌ | `options: ["A. ...", "B. ..."]` |
| 标准答案 | ❌ | `answer: "A"` |
| 示例 | `examples: [{input, output, explanation}]` | ❌ |
| 提示 | `hints: ["..."]` | ❌ |
| 输入/输出格式 | `input_format` + `output_format` | ❌ |

前端统一读取方式：

```js
const qd = record.question_data || {};
const content = qd.question || qd.title || qd.description || '';
const options = qd.options || [];
const answer = qd.answer || qd.solution || '';
```

---

## 路由2：`GET /wrong-answers/{user_id}/stats`

### 请求参数

| 参数 | 类型 | 必填 |
|---|---|---|
| `user_id` | path:str | ✅ |

### 响应

```json
{
  "success": true,
  "total": 50,
  "pending": 35,
  "resolved": 15,
  "by_type": {
    "programming": 20,
    "single_choice": 8,
    "judge": 7
  },
  "by_source": {
    "programming": 30,
    "theory": 20
  }
}
```

---

## 路由3：`GET /wrong-answers/{user_id}/mastered`

### 请求参数

| 参数 | 类型 | 必填 | 默认值 |
|---|---|---|---|
| `user_id` | path:str | ✅ | - |
| `page` | query:int | ❌ | 1 |
| `page_size` | query:int | ❌ | 20 |
| `question_type` | query:str\|None | ❌ | null |

### 响应

字段结构与路由1完全相同，区别：

- 只返回 `resolved=1` 的记录
- 按 `mastered_at DESC` 排序
- `attempts` 列表不足时自动补伪记录

---

## 路由4：`GET /wrong-answers/{record_id}/recommend/{user_id}`

### 请求参数

| 参数 | 类型 | 必填 |
|---|---|---|
| `record_id` | path:str | ✅ |
| `user_id` | path:str | ✅ |

### 响应（错题数 < 3 次）

```json
{
  "success": true,
  "should_recommend": false,
  "attempt_count": 1
}
```

### 响应（错题数 ≥ 3 次）

```json
{
  "success": true,
  "should_recommend": true,
  "attempt_count": 3,
  "resource_types": ["question", "practice"],
  "knowledge_points": ["排序算法"],
  "learning_style": "综合型",
  "materials": {
    "question": [
      {
        "id": "q_xxx",
        "title": "冒泡排序实现",
        "content": "实现一个冒泡排序函数...",
        "difficulty": 3,
        "knowledge_points": ["排序算法"],
        "topic": "排序算法",
        "recommendation_reason": "相似用户推荐(5人做过)",
        "sub_topic": "programming",
        "source": "agent_generated"
      }
    ]
  }
}
```

### 执行逻辑

1. 查 `resource_db` 库检索（`recommender.recommend(resource_type="question")`）
2. 无匹配 → 走 **LLM 同步生成**（`_generate_llm_materials` 同步版，绕过 PhaseBridge 缓存/追踪）

---

## 路由5：`POST /wrong-answers/llm-generate`

### 请求体

```json
{
  "user_id": "user_001",
  "knowledge_points": ["排序算法"],
  "resource_types": ["question", "practice"]
}
```

`resource_types` 默认值：`["question", "practice"]`

### 响应

```json
{
  "success": true,
  "materials": {
    "question": [
      {
        "id": "P_9bbb6497",
        "title": "冒泡排序过程展示",
        "content": "题目描述...",
        "examples": [{ "input": "...", "output": "...", "explanation": "..." }],
        "sub_topic": "programming",
        "knowledge_points": ["排序算法"],
        "source": "agent_generated"
      },
      {
        "id": "",
        "title": "Python中列表的索引从几开始？",
        "content": "Python中列表的索引从几开始？",
        "options": ["A. 0", "B. 1", "C. -1", "D. 2"],
        "answer": "A",
        "explanation": "数组索引从0开始的规则...",
        "sub_topic": "single_choice",
        "knowledge_points": ["排序算法", "single_choice"],
        "source": "agent_generated"
      },
      {
        "...": "..."
      }
    ]
  }
}
```

### 执行逻辑  

- **不走任何缓存或 PhaseBridge**
- 直接调 Agent：
  - `practice` → `PracticeAgent.generate_problem_async()`（跳过查库）
  - `question` → `QuestionGeneratorAgent.generate_all_questions_async()`，取前 2 道

---

## 路由6：`DELETE /wrong-answers/{record_id}/{user_id}`

### 请求参数

| 参数 | 类型 | 必填 |
|---|---|---|
| `record_id` | path:str | ✅ |
| `user_id` | path:str | ✅ |

### 响应

```json
{
  "success": true,
  "message": "错题记录已删除"
}
```

---

## 路由7：`POST /practice/rejudge`

### 请求体

```json
{
  "user_id": "user_001",
  "problem_data": {
    "problem_id": "P_xxx",
    "title": "冒泡排序",
    "description": "实现冒泡排序...",
    "knowledge_points": ["循环结构", "数组操作"],
    "examples": [{ "input": "3 1 2", "output": "1 2 3" }],
    "hints": ["使用双层循环"]
  },
  "user_code": "print('hello')",
  "language": "python",
  "record_id": "wa_abc123"
}
```

### 响应

```json
{
  "success": true,
  "judge_result": {
    "verdict": "Wrong Answer",
    "score": 30,
    "passed_tests": 1,
    "total_tests": 5,
    "completeness_check": {
      "has_main": true,
      "has_input_handling": true,
      "has_algorithm": true,
      "has_output": true,
      "is_complete": true
    },
    "analysis": {
      "correctness": "代码逻辑有误...",
      "logic": "循环边界条件错误",
      "code_quality": "代码可读性良好",
      "efficiency": "时间复杂度 O(n²)"
    },
    "bugs": ["内层循环条件应为 j < n-i-1"],
    "missing_parts": [],
    "suggestions": ["注意循环边界条件"],
    "reference_solution": "正确解法：使用双层循环...",
    "encouragement": "继续加油，你已经很接近了！"
  },
  "auto_marked_as_resolved": false,
  "material_recommendations": null
}
```

### 错题本侧写逻辑

| 条件 | 行为 |
|---|---|
| `score >= 60` | `mark_resolved()` + 记录最后一次尝试 |
| `score < 60` | `recommend_materials_for_wrong_answer(attempt_count)`，≥3次时返回推荐 |

---

## 路由8：`POST /theory/submit`

### 请求体

```json
{
  "user_id": "user_001",
  "question_type": "single_choice",
  "question": {
    "question": "Python中列表的索引从几开始？",
    "options": ["A. 0", "B. 1", "C. -1", "D. 2"],
    "answer": "A",
    "explanation": "Python中列表索引从0开始..."
  },
  "user_answer": "B",
  "knowledge_points": ["Python基础", "列表"],
  "source": "theory"
}
```

### 响应

```json
{
  "is_correct": false,
  "score": 0,
  "correct_answer": "A",
  "user_answer": "B",
  "question_type": "single_choice",
  "wrong_answer_recorded": true,
  "question_id": "q_xxx",
  "message": "答案错误，已自动加入错题本（已错3次，推荐学习资料）",
  "material_recommendations": null,
  "memoryhub_recorded": true
}
```

### 判断逻辑

| 题型 | 判题方式 |
|---|---|
| `single_choice` | 精确匹配（`user_answer.upper() == correct_answer.upper()`） |
| `judge` | 精确匹配 |
| `multiple_choice` | 拆分后无序集合比较 |
| `fill_blank` | 去空白后比较 |
| `short_answer` | 去空白后比较 |

### 错题本侧写逻辑

- 答对 → `mark_resolved()` + `MemoryHub` 记录
- 答错 → 记入错题本，≥3次 `recommend_materials_for_wrong_answer()`

---

## 字段不一致清单（已修）

| # | 问题 | 修改 |
|---|---|---|
| 1 | `_parse_agent_result` practice 分支没设 `sub_topic` | 两个分支都加了 `sub_topic: "programming"` |
| 2 | 后端 set `source = "agent_generated"`，前端查 `"llm_generated"` | 前端改为查 `"agent_generated"` |
| 3 | `renderCard` 只读 `qd.question`，编程题没有这个字段 | 改为 `qd.question \|\| qd.title \|\| qd.description` |
| 4 | `question_data` 编程题/理论题结构不同 | 前端统一用 `\|\|` 兜底读取 |
