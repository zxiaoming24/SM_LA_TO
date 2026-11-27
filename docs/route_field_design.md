# 五功能路由与字段设计文档

> 项目：all-tame-channel (FastAPI + SQLite/JSON)

---

## 目录

1. [功能一：上传文档 → 知识图谱](#功能一上传文档--知识图谱)
2. [功能二：语音学伴聊天](#功能二语音学伴聊天)
3. [功能三：视频内容整理 → 知识图谱](#功能三视频内容整理--知识图谱)
4. [功能四：笔记 AI 优化对比 + 思维导图](#功能四笔记-ai-优化对比--思维导图)
5. [学习计划市场](#学习计划市场)
6. [易错题](#易错题)

---

## 功能一：上传文档 → 知识图谱

### 说明

用户上传文档（PDF/MD/DOCX/TXT/XMind），服务端解析内容后调用 LLM 提取知识图谱。**已有完整实现**，本表列出全部已有路由和字段，供参考。

### 路由

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/knowledge-graph/upload/{user_id}` | 上传文档 → 解析 → LLM 提取 → 生成知识图谱 | 已有 |
| GET | `/knowledge-graph/{user_id}` | 获取用户所有知识图谱列表 | 已有 |
| GET | `/knowledge-graph/{user_id}/{graph_id}/enriched` | 获取融合掌握度数据的增强知识图谱 | 已有 |
| POST | `/knowledge-graph/{user_id}/merge` | 合并多个知识图谱为一个 | 已有 |
| DELETE | `/knowledge-graph/{user_id}/{graph_id}` | 删除知识图谱 | 已有 |


### 请求参数

#### `POST /knowledge-graph/upload/{user_id}` — 上传文档生成图谱

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| user_id | path | `str` | 是 | 用户ID |
| file | body | `UploadFile` | 是 | 文档文件（支持 PDF/MD/DOCX/TXT/XMind） |

#### `GET /knowledge-graph/{user_id}` — 图谱列表

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| user_id | path | `str` | 是 | 用户ID |



#### `GET /knowledge-graph/{user_id}/{graph_id}/enriched` — 增强图谱（含掌握度）

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| user_id | path | `str` | 是 | 用户ID |
| graph_id | path | `str` | 是 | 图谱ID |

#### `POST /knowledge-graph/{user_id}/merge` — 合并图谱

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|    需要user_id和body参数  （body封装数据如下）
| user_id | path | `str` | 是 | 用户ID |
| graph_ids | body | `string[]` | 是 | 待合并的图谱ID列表 |
| title | body | `string` | 否 | 合并后的图谱标题（可选） | 
！！！！！！！    !!!!!!!!!！！！！！！！ graph_id和title需要在body中（其才是必要参数） body: dict

#### `DELETE /knowledge-graph/{user_id}/{graph_id}` — 删除图谱

| 参数 | 位置 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| user_id | path | `str` | 是 | 用户ID |
| graph_id | path | `str` | 是 | 图谱ID |



### 响应字段

#### `POST /knowledge-graph/upload/{user_id}` — 上传文档生成图谱

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| data.graph_id | `str` | 图谱唯一ID |
| data.title | `str` | 图谱标题 |
| data.source_file | `str` | 源文件名 |
| data.created_at | `str` | 创建时间 ISO |
| data.node_count | `int` | 节点数 |
| data.edge_count | `int` | 边数 |
| data.total_chars | `int` | 源文档字符数 |

#### `GET /knowledge-graph/{user_id}` — 图谱列表

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| data | `array` | 图谱列表 |
| data[].graph_id | `str` | 图谱唯一ID |
| data[].title | `str` | 图谱标题 |
| data[].source_file | `str` | 源文件名 |
| data[].created_at | `str` | 创建时间 ISO |
| data[].node_count | `int` | 节点数 |
| data[].edge_count | `int` | 边数 |
| data[].total_chars | `int` | 源文档字符数 |



#### `GET /knowledge-graph/{user_id}/{graph_id}/enriched` — 增强图谱

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| data.title | `str` | 图谱标题 |
| data.nodes | `array` | 知识点节点列表（含掌握度） |
| data.nodes[].id | `str` | 节点唯一ID |
| data.nodes[].name | `str` | 知识点名称 |
| data.nodes[].description | `str` | 简短描述 |
| data.nodes[].category | `str` | 分类 |
| data.nodes[].mastery_level | `int` | 掌握度等级（0-5） |
| data.nodes[].mastery_points | `int` | 掌握度分数 |
| data.nodes[].mastery_label | `str` | 掌握度标签（如"未掌握"/"部分掌握"/"已掌握"） |
| data.edges | `array` | 关系边列表 |
| data.edges[].source | `str` | 前置知识点ID |
| data.edges[].target | `str` | 后置知识点ID |
| data.edges[].relation | `str` | 关系 |

#### `POST /knowledge-graph/{user_id}/merge` — 合并图谱

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| data.graph_id | `str` | 合并后图谱ID |
| data.title | `str` | 图谱标题 |
| data.node_count | `int` | 节点数 |
| data.edge_count | `int` | 边数 |
| data._is_merged | `bool` | 是否为合并结果 |
| data._cross_edges | `int` | 跨图谱边数 |
| data.created_at | `str` | 创建时间 ISO |

#### `DELETE /knowledge-graph/{user_id}/{graph_id}` — 删除图谱

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| message | `str` | 提示信息（如"已删除"） |






## 功能二：语音学伴聊天

### 说明

用户与 AI 学伴进行**语音 + 文字**对话聊天（非题目的语音通话，而是独立聊天场景）。支持：
- 文字消息
- 语音消息（TTS合成 + ASR识别）
- 对话历史管理

### 路由

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| WebSocket | `/companion/voice/ws` | 语音通话 WebSocket 信令（P2P通话） | 已有 |
| GET | `/companion/voice/history/{user_id}` | 获取通话历史列表 | 已有 |

### 请求参数

#### WebSocket `/companion/voice/ws` — 通话信令

WebSocket 消息类型及字段：     ！！！！  直接使用websocket本身作为参数   call等本身就是其参数

| 消息类型 | 字段 | 类型 | 必填 | 说明 |
|---------|------|------|------|------|
| call | caller_id | `str` | 是 | 主叫用户ID |
| call | callee_id | `str` | 是 | 被叫用户ID |
| join | room_id | `str` | 是 | 房间ID |
| join | user_id | `str` | 是 | 用户ID |
| accept | room_id | `str` | 是 | 房间ID |
| accept | user_id | `str` | 是 | 用户ID |
| reject | room_id | `str` | 是 | 房间ID |
| reject | user_id | `str` | 是 | 用户ID |
| hangup | room_id | `str` | 是 | 房间ID |
| hangup | user_id | `str` | 是 | 用户ID |
| offer | sdp | `str` | 是 | SDP 描述 |
| answer | sdp | `str` | 是 | SDP 描述 |
| ice-candidate | candidate | `object` | 是 | ICE 候选者信息 |

#### `GET /companion/voice/history/{user_id}` — 通话记录

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| user_id | path | `str` | 是 | — | 用户ID |
| limit | query | `int` | 否 | `20` | 返回记录条数 |

### 响应字段

#### `GET /companion/voice/history/{user_id}` — 通话记录

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| history | `array` | 通话记录列表 |
| history[].id | `int` | 记录ID |
| history[].room_id | `str` | 房间ID |
| history[].caller_id | `str` | 主叫用户ID |
| history[].callee_id | `str` | 被叫用户ID |
| history[].status | `str` | 通话状态 |
| history[].duration_sec | `int` | 通话时长（秒） |
| history[].started_at | `str` | 通话开始时间 ISO |
| history[].ended_at | `str` | 通话结束时间 ISO |
| history[].created_at | `str` | 记录创建时间 ISO |









## 功能三：视频内容整理 → 知识图谱

### 说明

用户在视频页面下方，可以一键整理当前视频的**核心内容**，并生成对应的**知识图谱**。支持：
- 通过字幕/语音识别提取视频内容摘要
- 调用 LLM 提取知识点和关系生成知识图谱
- 整理结果作为"用户生成资源"保存

### 路由

| 方法 | 路径 | 说明 | 状态 |    具体实现是在  #services/bili_stream_service.py中  ！！！！！
|------|------|------|------|
| POST | `/api/video-summary` | 基于字幕 + LLM 生成视频结构化总结 | 已有 |
| POST | `/api/video-mindmap` | 从视频字幕提取知识点关系生成知识图谱 | **新增** |

### 请求参数

#### `POST /api/video-summary`    可以传递req 里面封装bvid等字段 之后进入方法之后再通过json转换（你可以直接写）直接使用下面参数，再方法中再进行封装

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| bvid | body | `str` | 是 | — | 视频BVID |
| page | body | `int` | 否 | `1` | 视频分P编号 |

#### `POST /api/video-mindmap`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| bvid | body | `str` | 是 | — | 视频BVID |
| page | body | `int` | 否 | `1` | 视频分P编号 |

### 响应字段

#### `POST /api/video-summary`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| data.summary | `str` | 视频整体内容总结（150-250字） |
| data.key_points | `str[]` | 核心要点列表 |
| data.sections | `object[]` | 结构化章节总结 |
| data.sections[].title | `str` | 章节标题 |
| data.sections[].content | `str` | 章节内容总结 |
| video_title | `str` | 视频标题 |

#### `POST /api/video-knowledge-graph`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| data.graph_id | `str` | 图谱ID |
| data.title | `str` | 图谱标题 |
| data.nodes | `object[]` | 知识点节点列表 |
| data.nodes[].id | `str` | 节点ID |
| data.nodes[].name | `str` | 知识点名称 |
| data.nodes[].description | `str` | 描述 |
| data.nodes[].category | `str` | 分类：概念/原理/方法/工具/应用 |
| data.edges | `object[]` | 关系边列表 |
| data.edges[].source | `str` | 前置知识点ID |
| data.edges[].target | `str` | 后置知识点ID |
| data.edges[].relation | `str` | 关系类型 |
| data.node_count | `int` | 节点数 |
| data.edge_count | `int` | 边数 |

---

## 功能四：笔记 AI 优化对比 + 思维导图

### 说明

笔记功能包含两个 AI 能力：

1. **AI 结构化整理**（已有）：LLM 对笔记做术语补充、易错点标记、错误纠正、结构化重组。前端展示 diff 对比，用户确认后一键接受。
2. **AI 文本优化**（已有逻辑，新增路由）：LLM 修正语病错字、优化表达。前端展示 diff 对比，用户确认后一键接受。
3. **思维导图笔记**（已有）：从笔记内容生成思维导图 JSON，前端渲染。

### 路由

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|

| POST | `/notes/{user_id}/{note_id}/organize-preview` | **AI 结构化整理预览**（返回 diff） | 已有 |
| POST | `/notes/{user_id}/{note_id}/organize-preview/accept` | **接受整理结果**（一键保存） | 已有 |
| POST | `/api/note/mindmap` | 从笔记内容生成思维导图 JSON | 已有 |

  像前端显示的下载图片，再导图中双击节点之后修改对应的笔记内容会修改，这些纯前端实现

#### `POST /notes/{user_id}/{note_id}/organize-preview` — AI整理预览

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| user_id | path | `str` | 是 | — | 用户ID |
| note_id | path | `str` | 是 | — | 笔记ID |
| title | body | `str` | 是 | — | 笔记标题 |
| content | body | `str` | 是 | — | 笔记内容 |    后2个需要封装为 request这个传递

**对应 Pydantic 模型：** `NoteOrganizeRequest`

#### `POST /notes/{user_id}/{note_id}/organize-preview/accept` — 接受整理结果

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| user_id | path | `str` | 是 | — | 用户ID |
| note_id | path | `str` | 是 | — | 笔记ID |
| title | body | `str` | 是 | — | 整理后的标题 |
| organized_content | body | `str` | 是 | — | 整理后的内容 |
| ai_result | body | `dict` | 是 | — | AI 整理结果 |   后3个封装为 request这个传递

**对应 Pydantic 模型：** `NoteAcceptOrganizeRequest`

#### `POST /api/note/mindmap` — 生成思维导图

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| title | body | `str` | 是 | — | 笔记标题 |
| content | body | `str` | 是 | — | 笔记内容 |

**对应 Pydantic 模型：** `NoteMindmapRequest`



### 响应字段

#### `POST /notes/{user_id}/{note_id}/organize-preview` — AI整理预览

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| preview.original | `str` | 原始内容 |
| preview.organized | `str` | 整理后的内容 |
| preview.organized_title | `str` | 整理后的标题 |
| preview.diff_lines | `array` | 行级 diff |
| preview.diff_lines[].type | `str` | diff 类型：same / added / removed |
| preview.diff_lines[].line | `str` | diff 行内容 |
| preview.diff_stats.added | `int` | 新增行数 |
| preview.diff_stats.removed | `int` | 删除行数 |
| preview.diff_stats.total_original | `int` | 原文总行数 |
| preview.diff_stats.total_organized | `int` | 整理后总行数 |
| preview.ai_result.terms | `array` | 术语列表 |
| preview.ai_result.error_prone_points | `array` | 易错点列表 |
| preview.ai_result.corrections | `array` | 修正列表 |
| preview.ai_result.summary | `str` | AI 总结 |
| preview.ai_result.knowledge_points | `str[]` | 知识点标签 |

#### `POST /notes/{user_id}/{note_id}/organize-preview/accept` — 接受整理结果

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| note | `object` | 更新后的笔记对象（字段同详情接口） |

#### `POST /api/note/mindmap` — 生成思维导图

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| mindmap.name | `str` | 根节点名称 |
| mindmap.children | `array` | 一级子节点列表 |
| mindmap.children[].name | `str` | 子节点名称 |
| mindmap.children[].keywords | `str[]` | 关键词标签 |
| mindmap.children[].children | `array` | 二级子节点列表 |
| mindmap.children[].children[].name | `str` | 二级节点名称 |
| mindmap.children[].children[].content | `str` | 二级节点内容 |
| mindmap.children[].children[].keywords | `str[]` | 二级节点关键词 |

---




## 易错题

### 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wrong-answers/{user_id}/frequently-wrong` | 获取易错题列表（同一题答错超过4次且未掌握） |
| GET | `/wrong-answers/{user_id}/frequently-wrong/stats` | 获取易错题专项统计（薄弱知识点分布） |

### 请求参数

#### `GET /wrong-answers/{user_id}/frequently-wrong`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| user_id | path | `str` | 是 | — | 用户ID |
| page | query | `int` | 否 | `1` | 页码 |
| page_size | query | `int` | 否 | `20` | 每页条数 |
| question_type | query | `str` | 否 | `null` | 筛选题型：programming / single_choice multiple_choice / judge / fill_blank / short_answer |   这个不是参数是question_type的类型
| source | query | `str` | 否 | `null` | 筛选来源：programming / theory |

#### `GET /wrong-answers/{user_id}/frequently-wrong/stats`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| user_id | path | `str` | 是 | — | 用户ID |

### 响应字段

#### `GET /wrong-answers/{user_id}/frequently-wrong`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| records | `array` | 易错题记录列表 |
| records[].record_id | `str` | 错题记录唯一ID |
| records[].question_type | `str` | 题目类型 |
| records[].question_data | `object` | 题目完整数据 |
| records[].user_answer | `str` | 用户的答案 |
| records[].correct_answer | `str` | 正确答案 |
| records[].score | `int` | 得分（0-100） |
| records[].knowledge_points | `str[]` | 知识点列表 |
| records[].attempt_count | `int` | 累计答错次数 |
| records[].difficulty | `str` | 难度 |
| records[].created_at | `str` | 首次录入时间 |
| records[].fw_attempt_count | `int` | 易错题表中的错误次数 |
| records[].entered_at | `str` | 进入易错题表的时间 |
| records[].is_frequently_wrong | `bool` | 是否为易错题（固定true） |
| records[].attempts | `array` | 每次尝试历史 |
| records[].attempts[].attempt_number | `int` | 第几次尝试 |
| records[].attempts[].user_answer | `str` | 本次答案 |
| records[].attempts[].score | `int` | 本次得分 |
| records[].attempts[].verdict | `str` | 评判结果 |
| records[].attempts[].created_at | `str` | 尝试时间 |
| total | `int` | 易错题总数 |
| page | `int` | 当前页码 |
| page_size | `int` | 每页条数 |
| total_pages | `int` | 总页数 |
| threshold | `int` | 易错题判定阈值（固定4） |

#### `GET /wrong-answers/{user_id}/frequently-wrong/stats`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| total | `int` | 易错题总数 |
| threshold | `int` | 判定阈值（固定4） |
| by_type | `object` | 按题型分布 |
| by_type.{type}.count | `int` | 该题型易错题数量 |
| by_type.{type}.max_attempts | `int` | 该题型最高错误次数 |
| avg_attempts | `float` | 平均错误次数 |
| max_attempts | `int` | 最高错误次数 |
| weak_knowledge_points | `array` | 薄弱知识点 TOP |
| weak_knowledge_points[].knowledge_point | `str` | 知识点名称 |
| weak_knowledge_points[].count | `int` | 出现次数 |

---

## 附录：新增路由汇总

### 需新建的路由

| 功能 | 方法 | 路径 | 用途 |
|------|------|------|------|

| 学伴聊天 | POST | `/companion/chat/{user_id}` | 发送文字消息给AI学伴 |
| 学伴聊天 | POST | `/companion/chat/{user_id}/stream` | 流式对话 SSE |
| 学伴聊天 | POST | `/companion/chat/{user_id}/voice` | 发送语音消息 |
| 学伴聊天 | GET | `/companion/chat/{user_id}/history` | 获取聊天记录 |
| 学伴聊天 | DELETE | `/companion/chat/{user_id}/session/{session_id}` | 删除会话 |
| 学伴聊天 | POST | `/companion/chat/{user_id}/session/{session_id}/title` | 更新会话标题 |
| 视频整理 | POST | `/video/{user_id}/summarize` | 整理视频内容 |
| 视频整理 | POST | `/video/{user_id}/knowledge-graph` | 从视频生成知识图谱 |
| 视频整理 | GET | `/video/{user_id}/summaries` | 视频整理列表 |
| 视频整理 | GET | `/video/{user_id}/summaries/{summary_id}` | 视频整理详情 |
| 视频整理 | GET | `/video/{user_id}/knowledge-graphs` | 视频知识图谱列表 |
| 视频整理 | DELETE | `/video/{user_id}/summaries/{summary_id}` | 删除视频整理 |

| 笔记优化 | POST | `/notes/{user_id}/{note_id}/optimize/accept` | 接受优化结果 |
| 笔记导图 | GET | `/notes/{user_id}/{note_id}/mindmap` | 获取笔记思维导图 |

### 需新建的数据存储

| 存储位置 | 内容 | 说明 |
|----------|------|------|
| `recommendation_data/companion.db` | `voice_chat_sessions` 表 | 学伴聊天会话 |
| `recommendation_data/companion.db` | `voice_chat_messages` 表 | 学伴聊天消息 |
| `recommendation_data/video.db` | `video_summaries` 表 | 视频内容整理 |
| `recommendation_data/video.db` | `video_knowledge_graphs` 表 | 视频知识图谱 |
| `note_data/{user_id}/{note_id}.json` | `optimization_history` 字段 | 笔记优化历史（追加到笔记JSON） |
| `note_data/{user_id}/mindmaps/{mindmap_id}.json` | 思维导图数据 | 笔记思维导图 |






## 学习计划市场

### 说明

路线市场提供学习路线模板的浏览、发布、采纳、评分等功能。存储于 `data/route_market/` 目录，以 JSON 文件组织。

### 路由

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/route-market/categories` | 获取所有路线分类 | 已有 |   没有参数 
| GET | `/api/route-market/list` | 列出市场路线模板（支持分类/难度/排序/搜索/用户采纳状态） | 已有 |
| GET | `/api/route-market/{route_id}` | 获取路线完整详情（含阶段和资源） | 已有 |
| POST | `/api/route-market/{route_id}/adopt` | 采纳路线为用户的学习计划 | 已有 |
| GET | `/api/route-market/{user_id}/adopted` | 获取用户已采纳的路线列表 | 已有 |  # 没有必要写
| POST | `/api/route-market/{route_id}/rate` | 用户对路线评分 | 已有 |
| POST | `/api/route-market/auto-generate` | 自动分析学习计划生成路线市场信息 | 已有 |   尽量再计划中实现，作用是发布的时候自动填充发布内容---与自动发布社区类似

| POST | `/api/route-market/publish` | 用户将学习计划发布到路线市场 | 已有 |
| GET | `/api/route-market/check-published` | 检查学习计划是否已发布 | 已有 |   同一计划不能重复发送
| GET | `/route-share/{route_id}` | 分享学习计划流程图页面（HTML渲染） | 已有 |   不用实现
| DELETE | `/api/route-market/{route_id}/delete` | 删除路线（仅发布者本人） | 已有 |
| PUT | `/api/route-market/{route_id}/update` | 更新路线信息（仅发布者本人） | 已有 |

### 请求参数

#### `GET /api/route-market/list`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| category | query | `str` | 否 | `""` | 筛选分类 |
| difficulty | query | `str` | 否 | `""` | 筛选难度 |
| sort | query | `str` | 否 | `"hot"` | 排序：hot / rating / new |
| search | query | `str` | 否 | `""` | 搜索关键词（匹配标题/描述/标签） |
| user_id | query | `str` | 否 | `""` | 传入后返回该用户的采纳状态 |

#### `GET /api/route-market/{route_id}`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| route_id | path | `str` | 是 | — | 路线ID |
| user_id | query | `str` | 否 | `""` | 传入后返回该用户的采纳状态 |

#### `POST /api/route-market/{route_id}/adopt`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |   实际参数  route_id  和  data
|------|------|------|------|--------|------|
| route_id | path | `str` | 是 | — | 路线ID |
| user_id | body | `str` | 是 | — | 用户ID |
| personalize | body | `bool` | 否 | `false` | 是否AI个性化适配 |  后2个封装再data中

#### `POST /api/route-market/{route_id}/rate`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| route_id | path | `str` | 是 | — | 路线ID |
| user_id | body | `str` | 是 | — | 用户ID |
| rating | body | `int` | 否 | `5` | 评分（1-5） |
| comment | body | `str` | 否 | `""` | 评价内容 |  后3个封装再data中

#### `POST /api/route-market/auto-generate`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| plan_data | body | `object` | 是 | — | 学习计划数据（含phases） |

#### `POST /api/route-market/publish` — 发布计划到市场

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| user_id | body | `str` | 是 | — | 发布者用户ID |
| plan_data | body | `object` | 是 | — | 学习计划完整数据（含phases） |
| route_info | body | `object` | 是 | — | 路线市场信息 |

#### `GET /api/route-market/check-published`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| user_id | query | `str` | 否 | `""` | 发布者用户ID |
| plan_id | query | `str` | 否 | `""` | 计划ID（精确匹配） |
| plan_name | query | `str` | 否 | `""` | 计划名称（兼容旧数据） |

#### `DELETE /api/route-market/{route_id}/delete`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| route_id | path | `str` | 是 | — | 路线ID |
| user_id | body | `str` | 是 | — | 用户ID（必须与发布者匹配） |

#### `PUT /api/route-market/{route_id}/update`

| 参数 | 位置 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|------|--------|------|
| route_id | path | `str` | 是 | — | 路线ID |
| user_id | body | `str` | 是 | — | 用户ID（必须与发布者匹配） 

### 响应字段

#### `GET /api/route-market/categories`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| categories | `str[]` | 所有路线分类列表 |

#### `GET /api/route-market/list`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| routes | `object[]` | 路线摘要列表（不含phases） |
| routes[].route_id | `str` | 路线ID |
| routes[].name | `str` | 路线名称 |
| routes[].subtitle | `str` | 副标题 |
| routes[].description | `str` | 描述 |
| routes[].category | `str` | 分类 |
| routes[].tags | `str[]` | 标签 |
| routes[].difficulty | `str` | 难度 |
| routes[].estimated_duration | `str` | 预估时长 |
| routes[].estimated_hours | `int` | 预估总小时数 |
| routes[].cover_color | `str` | 封面颜色 |
| routes[].cover_icon | `str` | 封面图标 |
| routes[].creator | `object` | 发布者信息 `{id, name, avatar}` |
| routes[].stats | `object` | 统计 `{adoptions, rating, created_at}` |
| routes[].adopted_by_user | `bool` | 当前用户是否已采纳（需传入user_id） |
| routes[].adoption_mode | `str\|null` | 采纳模式：直接使用 / null |
| routes[].adopted_at | `str\|null` | 采纳时间 |
| total | `int` | 总数 |

#### `GET /api/route-market/{route_id}`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| route | `object` | 路线完整数据（含 phases 和 reviews） |
| route.route_id | `str` | 路线ID |
| route.name | `str` | 路线名称 |
| route.phases | `object[]` | 阶段列表 |
| route.phases[].phase | `int` | 阶段序号 |
| route.phases[].name | `str` | 阶段名称 |
| route.phases[].weeks | `str` | 周数 |
| route.phases[].description | `str` | 阶段描述 |
| route.phases[].knowledge_points | `str[]` | 知识点列表 |
| route.phases[].resource_types | `str[]` | 资源类型 |
| route.phases[].milestone | `str` | 里程碑 |
| route.phases[].estimated_hours | `int` | 预估小时数 |
| route.phases[].difficulty | `str` | 阶段难度 |
| route.phases[].resources | `object` | 阶段资源（video/doc/practice等） |
| route.reviews | `object[]` | 评价列表 |
| route.adopted_by_user | `bool` | 当前用户是否已采纳 |
| route.stats | `object` | 统计信息 |

#### `POST /api/route-market/{route_id}/adopt`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| plan_id | `str` | 生成的学习计划ID |
| plan_name | `str` | 计划名称 |
| personalized | `bool` | 是否个性化适配 |

#### `POST /api/route-market/publish`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| route_id | `str` | 新发布的路线ID |
| route_name | `str` | 路线名称 |

#### `GET /api/route-market/check-published`

| 字段 | 类型 | 说明 |
|------|------|------|
| published | `bool` | 是否已发布 |
| route_id | `str` | 已发布路线的ID（published=true时） |

#### `PUT /api/route-market/{route_id}/update`

| 字段 | 类型 | 说明 |
|------|------|------|
| success | `bool` | 是否成功 |
| route | `object` | 更新后的路线完整数据 |

