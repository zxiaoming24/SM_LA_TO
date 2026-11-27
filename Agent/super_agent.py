"""
超级智能体 - 基于 LangGraph ReAct 模式

核心能力：
1. 自主分析复杂问题，拆解为多步执行计划
2. 动态调用子Agent工具（练习/出题/文档/视频/导图/PPT等）
3. 支持顺序执行和并行执行
4. 思维链可见（SSE推送）
5. 未知问题灵活应对（先用通用知识回答，再推荐相关工具）

与现有架构的关系：
- SuperAgent 是上层封装，不替代现有子Agent
- 现有子Agent作为底层工具被调用
- 简单任务继续走原快速路径（des/conduct/chat）
- 复杂/未知/复合任务走 SuperAgent 路径
"""

import json
import asyncio
from typing import Dict, Any, List, TypedDict, Optional, Callable
from langgraph.graph import StateGraph, END
from utils.llm_config import get_chat_openai, set_llm_callback
from utils.super_agent_tools import TOOL_REGISTRY, TOOL_FUNCTIONS


# ==================== SSE 状态推送 ====================

async def _emit_status(node: str, status: str, detail: str = ""):
    """推送节点状态到 SSE 流"""
    try:
        from Agent.main_agent_conduct import _node_status_queue
        queue = _node_status_queue.get()  # 使用ContextVar不是全局  避免队列覆盖
        if queue is not None:
            import time
            await queue.put({
                "type": "node_status",
                "node": f"super_{node}",
                "status": status,
                "detail": detail,
                "timestamp": time.time()
            })
    except Exception:
        pass


async def _emit_thinking(node: str, content: str):
    """推送思考内容到 SSE 流"""
    try:
        from Agent.main_agent_conduct import _node_status_queue
        queue = _node_status_queue.get()
        if queue is not None:
            import time
            await queue.put({
                "type": "thinking",
                "node": f"super_{node}",
                "content": content,
                "timestamp": time.time()
            })
    except Exception:
        pass


# ==================== 构建工具描述 ====================

# ★★★ 缓存工具描述，避免每轮迭代重复构建 ★★★
_CACHED_TOOL_DESC: Optional[str] = None

def _build_tool_descriptions() -> str:
    """为 LLM 生成工具列表描述（结果缓存，运行期间不变）"""
    global _CACHED_TOOL_DESC
    if _CACHED_TOOL_DESC is not None:
        return _CACHED_TOOL_DESC
    lines = []
    for name, info in TOOL_REGISTRY.items():
        params_desc = "\n      ".join(
            [f"- {k}: {v}" for k, v in info["parameters"].items()]
        )
        lines.append(f"  {name}:")
        lines.append(f"    描述: {info['description']}")
        lines.append(f"    参数:")
        lines.append(f"      {params_desc}")
    _CACHED_TOOL_DESC = "\n".join(lines)
    return _CACHED_TOOL_DESC


SUPER_SYSTEM_PROMPT = """你是一个能力极强的**超级智能教育助手**，名叫"SuperTutor"。

## 核心能力
你拥有多种专业工具，可以解决学生学习中遇到的各种问题。
你会像人类专家一样思考：分析问题 → 制定计划 → 调用工具 → 综合结果。

## 可用工具

{tool_descriptions}

## 输出铁律（必须严格遵守）
你的每次回复都必须是一个**严格的单个 JSON 对象**，只输出 JSON 本身，不要输出任何其他文字。
禁止输出：解释、前言、客套话（如"好的，我来为您…"）、思考过程说明、markdown 代码块。
- 调用工具时输出：{{"action": "工具名", "thought": "原因", "params": {{...}}}}
- 任务完成时输出：{{"action": "final", "thought": "总结", "result": {{"summary": "...", "details": {{...}}}}}}

## 工作流程

### 第一步：分析问题
仔细阅读用户输入，判断：
1. 这是一个简单问题（只需一个工具或直接回答）？
2. 还是一个复杂问题（需要多个工具按顺序/并行执行）？

### 第二步：制定计划（仅复杂任务需要）
如果是复杂任务，先规划执行步骤再开始。

**复杂任务示例：**
- 用户说"帮我全面学习二叉树" → 计划：先文档→再导图→再练题→再视频
- 用户说"学完指针后帮我生成PPT和练习题" → 计划：先PPT→再练题（可并行）
- 用户说"解释RESTful API并找个视频" → 计划：先search_video找视频→再用knowledge_qa解释概念
- 用户说"找视频资料并生成编程题" → 计划：先search_video找视频→再generate_practice生成编程题

### 第三步：执行工具
每次只调用一个工具。调用的输出格式：
```json
{{
  "thought": "分析当前情况，解释为什么要调用这个工具",
  "action": "工具名称",
  "params": {{
    "user_input": "★ 只传递与当前工具有关的部分，不要传递完整的原始用户输入",
    "user_id": "用户ID（如有）"
  }}
}}
```

**参数提取示例：**
- 用户说"帮我找视频学Python循环，再出一道题" → 调 search_video 时传 `"Python循环教程"`，调 generate_practice 时传 `"Python循环编程题"`
- 用户说"生成PPT和练习题" → 调 generate_ppt 时传 PPT主题，调 generate_practice 时传知识点
- 用户说"解释指针并出题" → 调 knowledge_qa 时传 `"指针的概念"`，调 generate_practice 时传 `"指针"`

**关键规则：每个工具的 user_input 必须是该工具所需的简短关键词或短语，绝不能是用户整段原文。**

### 第四步：观察结果
工具会返回结果。根据结果决定：
- 还需要调用其他工具吗？→ 继续调用
- 已经得到全部结果？→ 给出最终回答

### 第五步：给出最终回答
```json
{{
  "thought": "总结所有步骤的结果",
  "action": "final",
  "result": {{
    "summary": "给用户的完整回复，包含所有生成结果的摘要",
    "details": {{
      "task_type": "super_agent",
      "steps_completed": ["使用的工具列表"],
      "results": {{"工具名": "结果摘要"}}
    }}
  }}
}}
```

## 重要规则
1. **一次只能调用一个工具**，不要同时调用多个
2. 每个工具调用后必须等待结果再决定下一步
3. 最多执行 {max_tool_calls} 步工具调用
4. 如果用户问的是专业知识，优先使用 knowledge_qa 或 general_qa
5. 如果用户的问题与学习无关（天气、新闻等），用 general_qa 回答
6. **不要编造工具不存在的功能**，只使用上面列出的工具
7. 始终使用中文回复

## 最终回答的 summary 撰写规则

summary 中不同类型资源有不同的写法：

- **通用问答 / 代码评判**：写完整内容（用户直接阅读）
- **编程练习 / 理论题**：只写"已生成XXX"一句话，前端展示题目卡片
- **视频**：只写"已为您找到相关视频"一句，不要写标题/作者/链接，前端用播放器渲染
- **思维导图 / 动画 / PPT / 文档 / 拓展阅读 / 学习计划**：只写"已生成XXX"一句话，前端展示对应渲染组件

示例：
- 同时做代码评判和找视频 → summary 只写代码评判的完整分析，"已为您找到相关视频"一句带过
- 同时生成PPT和练习题 → summary 写"已生成PPT：XXX。已生成练习题：XXX"各一句话
"""


# ==================== 状态定义 ====================

class SuperState(TypedDict):
    """SuperAgent 运行状态"""
    user_id: str
    user_input: str
    messages: List[Dict[str, Any]]       # 对话历史
    tool_call_count: int                 # 已执行的工具调用次数
    max_tool_calls: int                  # 最大工具调用次数
    intermediate_results: Dict[str, Any]  # 中间结果缓存
    final_result: Optional[Dict[str, Any]]
    error: Optional[str]


# ==================== 节点函数 ====================

async def think_node(state: SuperState) -> SuperState:
    """
    LLM 思考节点：分析当前状态，决定下一步行动
    - 调用工具 → 返回 (action, params)
    - 给出最终答案 → 返回 (action="final", result)
    """
    user_id = state.get("user_id", "")
    messages = state.get("messages", [])
    tool_call_count = state.get("tool_call_count", 0)
    max_tool_calls = state.get("max_tool_calls", 10)

    await _emit_status("think", "start", f"第 {tool_call_count + 1} 轮思考")
    await _emit_thinking("think", f"🤔 正在分析问题...")

    if tool_call_count >= max_tool_calls:
        await _emit_thinking("think", "⚠️ 已达到最大工具调用次数，将汇总已有结果")
        return {
            **state,
            "final_result": {
                "summary": "已达到最大工具调用次数，请简化您的问题或分步提问。",
                "details": {"task_type": "super_agent", "steps_completed": []}
            },
            "error": "max_tool_calls_reached"
        }

    try:
        # 构建系统提示
        tool_desc = _build_tool_descriptions()
        system_prompt = SUPER_SYSTEM_PROMPT.format(
            tool_descriptions=tool_desc,
            max_tool_calls=max_tool_calls
        )

        # 构建消息列表
        llm_messages = [{"role": "system", "content": system_prompt}]

        # 添加历史消息（取最近10轮）
        recent_messages = messages[-20:] if len(messages) > 20 else messages
        for msg in recent_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            llm_messages.append({"role": role, "content": content})

        # 如果这已经是第N轮，在最后一条加提示
        if tool_call_count > 0:
            llm_messages.append({
                "role": "user",
                "content": (
                    "请根据上面的工具执行结果，决定下一步行动。\n"
                    "如果任务已完成，请输出 final 结果。\n"
                    "如果还需要其他工具，请输出下一个要调用的工具。"
                )
            })

        # 调用 LLM
        llm = get_chat_openai(temperature=0.3, max_tokens=2000)
        await _emit_thinking("think", "🔄 正在调用 LLM 进行推理...")

        response = await llm.ainvoke(llm_messages)
        content = response.content if hasattr(response, 'content') else str(response)

        # 解析响应（提取 JSON）
        parsed = _parse_llm_response(content)

        # ★★★ 解析失败时重试一次（强制只输出 JSON），避免模型闲聊导致工具未执行 ★★★
        if not parsed:
            await _emit_thinking("think", "⚠️ LLM输出格式异常，正在重试并强制要求输出 JSON")
            try:
                retry_messages = llm_messages + [{
                    "role": "user",
                    "content": (
                        "你刚才的输出不符合要求：必须只输出一个 JSON 对象，不要任何解释、前言或客套话。\n"
                        "调用工具请输出 {\"action\": \"工具名\", \"thought\": \"...\", \"params\": {...}}；"
                        "任务完成请输出 {\"action\": \"final\", \"result\": {\"summary\": \"...\"}}。"
                    )
                }]
                retry_response = await llm.ainvoke(retry_messages)
                retry_content = retry_response.content if hasattr(retry_response, 'content') else str(retry_response)
                parsed = _parse_llm_response(retry_content)
                content = retry_content
            except Exception:
                parsed = None

        if not parsed:
            # 解析失败，尝试用 general_qa 兜底
            await _emit_thinking("think", "⚠️ LLM输出格式异常，使用通用问答兜底")
            # 把内容作为最终结果
            return {
                **state,
                "final_result": {
                    "summary": content,
                    "details": {
                        "task_type": "super_agent",
                        "steps_completed": [],
                        "raw_response": content
                    }
                }
            }

        action = parsed.get("action", "")
        thought = parsed.get("thought", "")

        if thought:
            await _emit_thinking("think", f"💡 {thought}")

        if action == "final":
            # 最终回答
            result_data = parsed.get("result", {})
            summary = result_data.get("summary", content)
            details = result_data.get("details", {})
            await _emit_thinking("think", f"✅ 思考完成，准备给出最终回答")
            return {
                **state,
                "final_result": {
                    "summary": summary,
                    "details": details
                }
            }

        # 检查工具是否存在
        if action not in TOOL_FUNCTIONS:
            await _emit_thinking("think", f"⚠️ 工具 '{action}' 不存在，尝试用 general_qa 回答")
            # 用 general_qa 兜底
            return {
                **state,
                "final_result": {
                    "summary": f"抱歉，'{action}' 功能暂不可用。请尝试其他问题或使用通用问答。",
                    "details": {"task_type": "super_agent", "steps_completed": []}
                }
            }

        # 记录要调用的工具
        tool_params = parsed.get("params", {})
        tool_params["user_id"] = user_id
        if "user_input" not in tool_params or not tool_params["user_input"]:
            fallback_input = state.get("user_input", "")
            # ★★★ 如果原始输入过长（超过60字符），说明可能是复合请求，
            # 用 action 名做关键词提取主题，避免把整段原文传给子Agent导致验证失败 ★★★
            if len(fallback_input) > 60:
                # 取原始输入的最后一句或最后50字（通常是离工具调用最近的需求）
                import re
                sentences = re.split(r'[，。；？\n]', fallback_input)
                last_relevant = sentences[-1] if len(sentences) > 1 else fallback_input
                last_relevant = last_relevant.strip()
                # 如果最后一句也太长，截取前40字
                if len(last_relevant) > 50:
                    last_relevant = last_relevant[:50]
                tool_params["user_input"] = last_relevant if last_relevant else fallback_input[:50]
                print(f"  ⚠️ [SuperAgent] fallback user_input 过长({len(fallback_input)}字)，截取为: '{tool_params['user_input']}'")
            else:
                tool_params["user_input"] = fallback_input

        await _emit_thinking("think",
            f"🔧 决定调用工具: {action}\n参数: {json.dumps(tool_params, ensure_ascii=False)}")

        # 保存工具调用信息到消息历史
        new_messages = messages + [
            {
                "role": "assistant",
                "content": json.dumps({
                    "thought": thought,
                    "action": action,
                    "params": tool_params
                }, ensure_ascii=False)
            }
        ]

        # 执行工具（同步方式调用异步函数）
        await _emit_status("action", "start", f"执行工具: {action}")
        await _emit_thinking("action", f"⚙️ 正在执行工具: {action}...")

        # ★★★ 上报 AgentMonitor：工具调用开始 ★★★
        try:
            from Agent.agent_monitor import report_call_start
            report_call_start(action, user_id, f"SuperAgent调用{action}")
        except Exception:
            pass

        try:
            tool_func = TOOL_FUNCTIONS[action]
            tool_result = await tool_func(tool_params)

            # ★★★ 上报 AgentMonitor：工具调用结束 ★★★
            try:
                from Agent.agent_monitor import report_call_end
                report_call_end(action, tool_result.get("success", False))
            except Exception:
                pass

            await _emit_thinking("action",
                f"✅ 工具 {action} 执行完成\n结果摘要: {tool_result.get('summary', str(tool_result)[:200])}")
            await _emit_status("action", "complete", action)

            # 将工具结果加入消息
            new_messages.append({
                "role": "user",
                "content": f"工具 {action} 返回结果:\n{json.dumps(tool_result, ensure_ascii=False, indent=2)}"
            })

            # 更新中间结果
            intermediate = dict(state.get("intermediate_results", {}))
            if tool_result.get("success"):
                intermediate[action] = tool_result

        except Exception as e:
            error_msg = f"工具 {action} 执行异常: {str(e)}"
            # ★★★ 上报 AgentMonitor：工具调用异常结束 ★★★
            try:
                from Agent.agent_monitor import report_call_end
                report_call_end(action, False)
            except Exception:
                pass
            await _emit_thinking("action", f"❌ {error_msg}")
            await _emit_status("action", "error", error_msg)

            new_messages.append({
                "role": "user",
                "content": f"工具 {action} 执行失败: {str(e)}"
            })
            intermediate = state.get("intermediate_results", {})

        return {
            **state,
            "messages": new_messages,
            "tool_call_count": tool_call_count + 1,
            "intermediate_results": intermediate
        }

    except Exception as e:
        error_msg = f"思考节点异常: {str(e)}"
        await _emit_thinking("think", f"❌ {error_msg}")
        await _emit_status("think", "error", error_msg)
        return {
            **state,
            "error": error_msg,
            "final_result": {
                "summary": f"处理过程中出现错误：{str(e)}",
                "details": {"task_type": "super_agent", "steps_completed": []}
            }
        }


def should_continue(state: SuperState) -> str:
    """判断是否继续循环还是结束"""
    if state.get("final_result") is not None:
        return "end"
    if state.get("error") is not None:
        return "end"
    return "continue"


# ==================== LLM 响应解析 ====================

def _parse_llm_response(content: str) -> Optional[Dict[str, Any]]:
    """从 LLM 输出中提取 JSON"""
    if not content:
        return None

    # 尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试从 ```json ... ``` 中提取
    if "```json" in content:
        try:
            parts = content.split("```json")
            if len(parts) > 1:
                json_str = parts[1].split("```")[0].strip()
                return json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            pass

    # 尝试从 ``` ... ``` 中提取
    if "```" in content:
        try:
            parts = content.split("```")
            for i, part in enumerate(parts):
                part = part.strip()
                if part.startswith("{") and part.endswith("}"):
                    return json.loads(part)
                if i > 0:
                    candidate = part.strip()
                    if candidate.startswith("{") and candidate.endswith("}"):
                        return json.loads(candidate)
        except (json.JSONDecodeError, IndexError):
            pass

    # 尝试在文本中查找 {...}
    import re
    brace_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            # 尝试找更大的括号块
            brace_match = re.search(r'\{.*\}', content, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group())
                except json.JSONDecodeError:
                    pass

    return None


# ==================== 创建 LangGraph ====================

def create_super_agent() -> StateGraph:
    """创建 SuperAgent 的 LangGraph 工作流"""
    workflow = StateGraph(SuperState)

    # 添加节点
    workflow.add_node("think", think_node)

    # 设置入口
    workflow.set_entry_point("think")

    # 条件边：继续思考 或 结束
    workflow.add_conditional_edges(
        "think",
        should_continue,
        {
            "continue": "think",  # 循环
            "end": END            # 结束
        }
    )

    return workflow.compile()


# ==================== SuperAgent 入口类 ====================

class SuperAgent:
    """超级智能体 - 处理复杂/复合学习任务"""

    def __init__(self):
        self.graph = create_super_agent()

    async def process(
        self,
        user_input: str,
        user_id: Optional[str] = None,
        max_tool_calls: int = 10
    ) -> Dict[str, Any]:
        """
        处理用户请求

        Args:
            user_input: 用户输入
            user_id: 用户ID
            max_tool_calls: 最大工具调用次数

        Returns:
            Dict: 处理结果
        """
        await _emit_status("super_agent", "start", f"用户: {user_id}")
        await _emit_thinking("super_agent",
            f"🎯 SuperAgent 开始处理\n用户输入: {user_input}")

        # 注入 SSE callback
        callback_handler = None
        try:
            from Agent.main_agent_conduct import SSEThinkingCallbackHandler
            callback_handler = SSEThinkingCallbackHandler("super_agent")
            set_llm_callback(callback_handler)
        except Exception:
            pass

        try:
            # 初始状态
            initial_state: SuperState = {
                "user_id": user_id or "",
                "user_input": user_input,
                "messages": [
                    {"role": "user", "content": user_input}
                ],
                "tool_call_count": 0,
                "max_tool_calls": max_tool_calls,
                "intermediate_results": {},
                "final_result": None,
                "error": None
            }

            # 执行 LangGraph
            final_state = await self.graph.ainvoke(initial_state)

            # 获取最终结果
            result = final_state.get("final_result")

            if result:
                # 收集中间结果中的资源
                intermediate = final_state.get("intermediate_results", {})
                resources = {}
                for tool_name, tool_result in intermediate.items():
                    if tool_result.get("success"):
                        resources[tool_name] = tool_result

                await _emit_thinking("super_agent",
                    f"✅ SuperAgent 处理完成\n最终回复: {result.get('summary', '')[:200]}...")
                await _emit_status("super_agent", "complete")

                # ★★★ 后处理：过滤掉 reply 中媒体类资源的详细内容，
                # 确保视频/动画/PPT 等由前端渲染，不混在文本回复中 ★★★
                reply = result.get("summary", "")
                media_tools = {"search_video", "generate_ppt", "generate_mindmap"}
                for tool_name in media_tools:
                    if tool_name in resources:
                        # 从 resources 中取出标题/主题，只保留一句话提示
                        tool_res = resources[tool_name]
                        task_type = tool_res.get("task_type", tool_name)
                        # 在 reply 中查找并替换可能的视频详情描述
                        # 兜底：如果 reply 中没有"已为您找到相关视频"之类的简短提示，追加一句
                        if task_type == "video" and "已为您找到相关视频" not in reply:
                            reply = reply.rstrip() + "\n\n已为您找到相关视频，请在播放器中查看。"
                        elif task_type == "ppt" and "已生成PPT" not in reply:
                            reply = reply.rstrip() + f"\n\n已生成PPT。"
                        elif task_type == "mindmap" and "已生成思维导图" not in reply:
                            reply = reply.rstrip() + "\n\n已生成思维导图。"

                return {
                    "success": True,
                    "layer": "super",
                    "reply": reply,
                    "resources": resources,
                    "details": result.get("details", {}),
                    "tool_call_count": final_state.get("tool_call_count", 0),
                    "metadata": {
                        "user_id": user_id,
                        "session_id": None
                    }
                }

            # 检查是否有 error
            error = final_state.get("error")
            if error:
                await _emit_status("super_agent", "error", error)
                return {
                    "success": False,
                    "layer": "super",
                    "error": error,
                    "metadata": {
                        "user_id": user_id,
                        "session_id": None
                    }
                }

            # 兜底
            return {
                "success": False,
                "layer": "super",
                "message": "SuperAgent 无法处理该请求",
                "metadata": {
                    "user_id": user_id,
                    "session_id": None
                }
            }

        except Exception as e:
            await _emit_status("super_agent", "error", str(e))
            await _emit_thinking("super_agent", f"❌ SuperAgent 异常: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "data": {
                    "status": "error",
                    "layer": "super",
                    "error": f"SuperAgent 异常: {str(e)}"
                },
                "suggestion_warning": "",
                "metadata": {
                    "user_id": user_id,
                    "session_id": None
                }
            }
        finally:
            if callback_handler is not None:
                try:
                    set_llm_callback(None)
                except Exception:
                    pass
