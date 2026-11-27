# 学习计划 API 文档

## 概述

学习计划模块提供个性化学习路径的生成、查看、阶段管理和进度追踪等功能。所有路由定义在 `api_server.py` 中。

支持**多计划并存**：每个用户可以拥有多个学习计划，通过 `plan_id` 区分，其中一个是「活跃计划」，
系统内部的阶段追踪、进度更新等操作默认作用于活跃计划。用户可以随时切换活跃计划或查看历史计划。

---

## 1. 生成学习计划

### `POST /study_plan/generate`

生成个性化学习路径规划（异步版本，不阻塞其他用户请求）。

#### 请求参数

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `user_id` | string | 是 | 用户ID |
| `user_input` | string | 是 | 学习目标描述，如"3个月学完Python" |
| `enable_tts` | bool | 否 | 是否启用TTS语音反馈（默认 false） |

#### 请求示例

```json
{
  "user_id": "user_001",
  "user_input": "我想在3个月内学完Python，从零开始",
  "enable_tts": false
}
```

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `plan_id` | string | 新生成的计划ID |
| `plan` | object | 完整的计划对象（含 phases 数组） |
| `message` | string | 附带消息 |
| `study_plan_summary` | object | 计划摘要 |
| `study_plan_summary.plan_id` | string | 计划ID |
| `study_plan_summary.title` | string | 计划标题 |
| `study_plan_summary.total_duration` | string | 总时长描述 |
| `study_plan_summary.phases_count` | int | 阶段数量 |
| `study_plan_summary.total_estimated_hours` | string | 总预估小时数 |

生成新计划时，**不会覆盖**已有的旧计划。新计划自动成为「活跃计划」，旧计划保留在历史列表中。

---

## 2. 获取学习计划

### `GET /study_plan/{user_id}`

获取用户的学习计划完整数据。

#### 查询参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `plan_id` | string | 否 | 计划ID。不传则返回当前活跃计划 |

#### 示例

```
GET /study_plan/user_001                     ← 获取活跃计划
GET /study_plan/user_001?plan_id=plan_xxx    ← 获取指定计划
```

获取用户的学习计划完整数据。

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `plan` | object | 完整的计划对象（含 phases 数组、_phase_completed_notification、_regenerating_phases 等） |

#### 附加注入字段

在返回前，接口会向 phases 注入考试状态：

| 字段 | 类型 | 描述 |
|------|------|------|
| `_exam_completed_info` | object | 考试完成信息（若已完成） |
| `_exam_completed_info.score` | int | 考试得分 |
| `_exam_completed_info.total` | int | 总分 |
| `_exam_completed_info.results` | array | 答题结果 |
| `_exam_completed_info.exam_data` | object | 考试数据 |
| `_exam_completed_info.phase_name` | string | 阶段名称 |
| `_exam_pending` | bool | 未完成考试（含跳过）为 true |

---

## 3. 获取学习计划摘要

### `GET /study_plan/{user_id}/summary`

获取用户学习计划的进度摘要信息。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `summary` | object | 摘要对象（由 StudyPlanner.get_plan_summary_async 返回） |

---

## 4. 获取所有阶段

### `GET /study_plan/{user_id}/phases`

获取用户学习计划的所有阶段（含考试状态）。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `phases` | array | 阶段列表 |

每个阶段可能附加的字段：

| 字段 | 类型 | 描述 |
|------|------|------|
| `_exam_completed_info` | object | 考试完成信息 |
| `_exam_pending` | bool | 考试待处理标志 |

---

## 5. 获取阶段资源缓存状态

### `GET /study_plan/{user_id}/phase/{phase_index}/status`

获取某阶段资源缓存状态（不触发生成）。

#### 路径参数

| 参数 | 类型 | 描述 |
|------|------|------|
| `user_id` | string | 用户ID |
| `phase_index` | int | 阶段索引（从0开始） |

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| ... | ... | 其余字段由 PhaseResourceBridge.get_phase_resource_status 返回 |

---

## 6. 生成阶段资源

### `POST /study_plan/{user_id}/phase/{phase_index}/generate/{resource_type}`

为某阶段生成指定知识点+资源类型。已有缓存直接返回，未缓存则调用对应 Agent 生成。

#### 路径参数

| 参数 | 类型 | 描述 |
|------|------|------|
| `user_id` | string | 用户ID |
| `phase_index` | int | 阶段索引 |
| `resource_type` | string | 资源类型（practice/video/doc/mindmap/ppt 等） |

#### 查询参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `knowledge_point` | string | 否 | 知识点名称。若不传且阶段只有一个知识点则自动使用；多个知识点时返回错误要求指定 |
| `entry` | string | 否 | `"plan"` = 管道模式（一键生成全套资源）；`"quick"` = 独立模式，只生成指定类型（默认 `"quick"`） |

#### 响应错误

> 若阶段包含多个知识点且未指定 `knowledge_point`，返回：
> ```json
> {"success": false, "error": "need_knowledge_point", "knowledge_points": ["知识点A", "知识点B"]}
> ```

---

## 7. 生成阶段全部资源

### `POST /study_plan/{user_id}/phase/{phase_index}/generate-all`

生成某阶段所有未缓存的资源（逐个按序生成），已缓存的不重复生成。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| ... | ... | 其余字段由 PhaseResourceBridge.generate_all_pending 返回 |

---

## 8. 获取管道状态

### `GET /study_plan/{user_id}/pipeline-status`    ---- 不要写 ----！！！！

获取用户的管道状态摘要。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| ... | ... | 由 CollaborationOrchestrator.get_pipeline_status 返回 |

---

## 9. 获取阶段进度（全部）

### `GET /study_plan/{user_id}/progress`

获取用户所有阶段的完成度详情。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `user_id` | string | 用户ID |
| `phases` | array | 各阶段进度详情 |

---

## 10. 获取单个阶段进度详情

### `GET /study_plan/{user_id}/phase/{phase_index}/progress`

获取某个阶段的详细完成度。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| ... | ... | 由 PhaseProgressTracker.get_phase_detail 返回 |

---

## 11. 检查阶段完成通知

### `GET /study_plan/{user_id}/notification`

检查是否有阶段完成通知（前端弹窗用）。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `notification` | object/null | 通知对象，无通知时为 null |

#### notification 对象字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `phase_index` | int | 阶段索引 |
| `phase_name` | string | 阶段名称 |
| `triggered_at` | string | 触发时间 |
| `assessment_ready` | bool | 评估报告是否已生成 |
| `assessment` | object/null | 评估报告内容 |
| `exam_ready` | bool | 考试是否已就绪 |
| `exam_data` | object | 考试数据 |
| `exam_completed` | bool | 考试是否已完成 |
| `exam_score` | int/null | 考试分数 |
| `exam_skipped` | bool | 考试是否跳过 |

---

## 12. 确认阶段完成通知

### `POST /study_plan/{user_id}/notification/ack`

确认阶段完成通知（关闭弹窗后调用），将 notification 标记为已确认。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |

---

## 13. 阶段心跳上报                -------不要写————————————————————————————————————————

### `POST /study_plan/{user_id}/phase/{phase_index}/heartbeat`

前端心跳上报，每30秒调用一次，累加用户活跃时间。

#### 逻辑说明

- 只有状态为 `"进行中"` 或 `"active"` 的阶段才接受心跳
- 每次上报累加30秒到 `_total_active_seconds`

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `total_seconds` | int | 该阶段累计活跃秒数 |

---

## 14. 考试相关 API

### 14.1 用户选择是否参加考试

#### `POST /study_plan/{user_id}/phase/{phase_index}/exam/choice`

#### 请求参数

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `take_exam` | bool | 是 | 是否参加考试 |

#### 请求示例

```json
{"take_exam": true}
```

---

### 14.2 获取考试题目

#### `GET /study_plan/{user_id}/phase/{phase_index}/exam`

获取阶段考试题目数据。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `exam_data` | object | 考试题目数据 |

---

### 14.3 提交考试答案

#### `POST /study_plan/{user_id}/phase/{phase_index}/exam/submit`

#### 请求参数

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `answers` | object | 是 | 用户答案，格式如 `{"programming_0": "代码", "theory_0": "A"}` |

#### 请求示例

```json
{
  "answers": {
    "programming_0": "print('Hello')",
    "theory_0": "A",
    "theory_1": "AB"
  }
}
```

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| ... | ... | 由 PhaseProgressTracker.submit_exam_answers 返回 |

---

## 15. 阶段性评估 API

### 15.1 获取阶段性评估报告

#### `GET /assessment/phase/{user_id}/{phase_index}`  ——————————目前没有用到不要写——

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `assessment` | object | 评估报告内容（无评估时 success=false） |

---

### 15.2 接受阶段性评估

#### `POST /assessment/phase-apply/{user_id}/{phase_index}`

接受阶段性评估：保存到评估页面，供用户自行采纳建议。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `result` | object | 应用结果 |

---

## 16. 复习提醒

### `GET /study_plan/{user_id}/review-reminder`  ——————————————有点问题，不要写——————————————————————————————

获取用户复习提醒（今日到期 + 即将到期）。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `reminder` | object | 提醒数据 |
| `reminder.today` | array | 今日到期内容 |
| `reminder.upcoming` | array | 即将到期内容 |

---

## 17. 前端页面路由

### `GET /study-plan-page`

提供学习计划前端页面（HTML）。

| 字段 | 说明 |
|------|------|
| 响应类型 | `text/html` |
| 模板文件 | `templates/study_plan.html` |

---

## 请求模型汇总

| 模型类 | 路由 | 字段 |
|--------|------|------|
| `StudyPlanRequest` | `POST /study_plan/generate` | `user_id: str`, `user_input: str`, `enable_tts: bool` |
| `SwitchPlanRequest` | `POST */switch-plan` | `plan_id: str` |
| `ExamChoiceRequest` | `POST */exam/choice` | `take_exam: bool` |
| `ExamSubmissionRequest` | `POST */exam/submit` | `answers: Dict[str, Any]` |

---

## 18. 多计划管理 API

### 18.1 获取计划列表

#### `GET /study_plans/{user_id}`

获取用户的所有学习计划列表（只含元信息）。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `plans` | array | 计划列表，每个元素包含 plan_id, title, created_at, updated_at, total_duration, is_active |
| `active_plan_id` | string | 当前活跃计划ID |
| `count` | int | 计划总数 |

---

### 18.2 切换活跃计划

#### `POST /study_plan/{user_id}/switch-plan`

切换用户的活跃学习计划。

#### 请求参数

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `plan_id` | string | 是 | 目标计划ID |

#### 请求示例

```json
{
  "plan_id": "plan_20260601_abc123"
}
```

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `message` | string | 结果消息 |

---

### 18.3 删除学习计划

#### `DELETE /study_plan/{user_id}/plan/{plan_id}`

删除用户指定的学习计划（文件和数据会被永久删除）。

#### 响应字段

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | bool | 是否成功 |
| `message` | string | 结果消息 |

---

## 完整路由速查表

| # | 方法 | 路由 | 用途 |
|---|------|------|------|
| 1 | POST | `/study_plan/generate` | 生成个性化学习路径规划 |
| 2 | GET | `/study_plan/{user_id}` | 获取用户学习计划（支持 ?plan_id=） |
| 3 | GET | `/study_plan/{user_id}/summary` | 获取学习计划摘要（支持 ?plan_id=） |
| 4 | GET | `/study_plan/{user_id}/phases` | 获取所有阶段（含考试状态） |
| 5 | GET | `/study_plan/{user_id}/phase/{phase_index}/status` | 获取阶段资源缓存状态 |
| 6 | POST | `/study_plan/{user_id}/phase/{phase_index}/generate/{resource_type}` | 生成阶段指定资源 |
| 7 | POST | `/study_plan/{user_id}/phase/{phase_index}/generate-all` | 生成阶段全部未缓存资源 |
| 8 | GET | `/study_plan/{user_id}/pipeline-status` | 获取管道状态摘要 |
| 9 | GET | `/study_plan/{user_id}/progress` | 获取所有阶段完成度 |
| 10 | GET | `/study_plan/{user_id}/phase/{phase_index}/progress` | 获取单个阶段完成度详情 |
| 11 | GET | `/study_plan/{user_id}/notification` | 检查阶段完成通知 |
| 12 | POST | `/study_plan/{user_id}/notification/ack` | 确认阶段完成通知 |
| 13 | POST | `/study_plan/{user_id}/phase/{phase_index}/heartbeat` | 阶段心跳上报（30s间隔） |
| 14 | POST | `/study_plan/{user_id}/phase/{phase_index}/exam/choice` | 用户选择是否参加考试 |
| 15 | GET | `/study_plan/{user_id}/phase/{phase_index}/exam` | 获取考试题目数据 |
| 16 | POST | `/study_plan/{user_id}/phase/{phase_index}/exam/submit` | 提交考试答案 |
| 17 | GET | `/assessment/phase/{user_id}/{phase_index}` | 获取阶段性评估报告 |
| 18 | POST | `/assessment/phase-apply/{user_id}/{phase_index}` | 接受阶段性评估 |
| 19 | GET | `/study_plan/{user_id}/review-reminder` | 获取复习提醒 |
| 20 | GET | `/study-plan-page` | 学习计划前端页面 |
| 21 | **GET** | **`/study_plans/{user_id}`** | **获取所有计划列表（新增）** |
| 22 | **POST** | **`/study_plan/{user_id}/switch-plan`** | **切换活跃计划（新增）** |
| 23 | **DELETE** | **`/study_plan/{user_id}/plan/{plan_id}`** | **删除指定计划（新增）** |
