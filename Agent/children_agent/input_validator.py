"""
输入验证智能体 - 判断用户输入是否为有效的学习相关指令

使用 LLM 判断用户输入是否为有意义的指令，替代规则匹配和置信度阈值判断。
支持通过 SSE 推送验证过程中的思考内容。

返回结构化结果：
  - is_valid: bool    输入是否有效
  - reason: str       判断理由
  - action_type: str   建议的处理方式
"""

import json
import time
from typing import Dict, Optional
from utils.llm_config import get_chat_openai, set_llm_callback


_VALIDATOR_PROMPT = """你是一个严格的输入验证助手。判断用户输入是否为有意义的指令。

【有效输入定义】
- 与学习相关的问题（编程、数学、英语、物理、考试等）
- 闲聊问候（你好、再见、谢谢、今天天气等）
- 功能请求（出题、练习、查资料、总结等）
- 个人信息修改（改名字、改专业等）

【无效输入定义】
- 纯乱码：'alskdjfhg'、'xcvb'、'qwerty'、'sdfghjkl' 等键盘乱按
- 纯数字或数字重复：'1'、'123'、'666'、'111'、'000' 等
- 纯符号/标点：'...'、'!!!'、'？'、'。。' 等
- 单字母无意义输入：'a'、'd'、'f' 等
- 无实质意义的重复字符：'哈哈哈哈哈'（单纯的语气词）、'啊啊啊啊' 等

【思考步骤】
1. 先看输入是否包含任何有意义的语义内容
2. 如果看起来像键盘乱按（连续无意义字母组合）、纯数字、纯符号 → 无效
3. 如果有意义（即使是闲聊或简单学习问题）→ 有效

【输出规则 - 严格遵循】
你必须始终输出一个完整的 JSON 对象，格式如下，不要输出任何其他内容：
{{
    "is_valid": true 或 false,
    "reason": "简要说明判断理由",
    "action_type": "learning" 或 "chat" 或 "unrecognized"
}}

其中 action_type 取值：
- "learning": 与学习有关的有效指令
- "chat": 闲聊问候等非学习但有效内容
- "unrecognized": 无效输入

用户输入：{user_input}"""


# 缓存 LLM 实例（非 SSE 模式使用）
_validator_llm = None


def _get_validator_llm():
    """获取或创建 LLM 实例"""
    global _validator_llm
    if _validator_llm is None:
        _validator_llm = get_chat_openai(temperature=0.0, max_tokens=300)
    return _validator_llm


def _extract_json(text: str) -> Optional[dict]:
    """从 LLM 输出中鲁棒地提取 JSON 对象，只返回 dict 类型"""
    text = text.strip()

    # 1. 尝试直接解析
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 2. 尝试提取 ```json ... ``` 块
    if "```json" in text:
        for part in text.split("```json"):
            if "```" in part:
                candidate = part.split("```")[0].strip()
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    continue

    # 3. 尝试提取 ``` ... ``` 块
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("{") and part.endswith("}"):
                try:
                    result = json.loads(part)
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    continue

    # 4. 正则搜索第一个 { ... } 对象
    import re
    brace_match = re.search(r'\{[^{}]*\}', text)
    if brace_match:
        # 递归展开嵌套括号
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == '{':
                if start == -1:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    candidate = text[start:i+1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        start = -1

    return None


def _validate_json_result(result) -> Optional[dict]:
    """确保解析结果是 dict 类型，排除裸字符串/数字等"""
    if isinstance(result, dict):
        return result
    return None


# ==================== SSE 事件推送（仅提供给 async 路径使用） ====================

async def _emit_thinking(node: str, content: str):
    """向 SSE 队列推送思考内容"""
    try:
        from Agent.main_agent_conduct import _node_status_queue
        queue = _node_status_queue
        if queue is not None:
            await queue.put({
                "type": "thinking",
                "node": node,
                "content": content,
                "timestamp": time.time()
            })
    except Exception:
        pass


async def _emit_node_status(node: str, status: str, detail: str = ""):
    """向 SSE 队列推送节点状态"""
    try:
        from Agent.main_agent_conduct import _node_status_queue
        queue = _node_status_queue
        if queue is not None:
            await queue.put({
                "type": "node_status",
                "node": node,
                "status": status,
                "detail": detail,
                "timestamp": time.time()
            })
    except Exception:
        pass


# ==================== 核心接口 ====================


async def validate_input_async(user_input: str, sse_node_name: Optional[str] = None) -> Dict:
    """
    异步验证用户输入是否有效（支持 SSE 流式推送思考过程）

    Args:
        user_input: 用户原始输入
        sse_node_name: 可选，SSE 节点名称。传此值时会：
          - 推送节点状态（start/complete）
          - 启用 LLM 流式输出，逐词推送验证思考过程

    Returns:
        Dict: 同 validate_input
    """
    if not user_input or not user_input.strip():
        return {
            "is_valid": False,
            "reason": "输入为空",
            "action_type": "unrecognized"
        }

    text = user_input.strip()

    # 快速预检（无需 LLM，也无需 SSE）
    if text.isdigit():
        reason = f"纯数字输入 '{text}'，无实际意义"
        if sse_node_name:
            await _emit_node_status(sse_node_name, "start")
            await _emit_thinking(sse_node_name, f"⚠️ {reason}")
            await _emit_node_status(sse_node_name, "complete", "invalid_digit")
        return {"is_valid": False, "reason": reason, "action_type": "unrecognized"}
    _SYMBOLS = set(".,!?;:'\"()【】「」『』《》—…·、，。！？；：""''（）~`@#$%^&*+-=<>/\\| ")
    if text and all(c in _SYMBOLS for c in text):
        reason = f"纯符号输入 '{text}'，无实际意义"
        if sse_node_name:
            await _emit_node_status(sse_node_name, "start")
            await _emit_thinking(sse_node_name, f"⚠️ {reason}")
            await _emit_node_status(sse_node_name, "complete", "invalid_symbol")
        return {"is_valid": False, "reason": reason, "action_type": "unrecognized"}
    # ★★★ 单字母/单数字输入 → 直接拦截 ★★★
    if len(text) <= 2 and text.isalpha() and text.isascii():
        reason = f"单字母输入 '{text}'，无实际意义"
        if sse_node_name:
            await _emit_node_status(sse_node_name, "start")
            await _emit_thinking(sse_node_name, f"⚠️ {reason}")
            await _emit_node_status(sse_node_name, "complete", "invalid_letter")
        return {"is_valid": False, "reason": reason, "action_type": "unrecognized"}

    # ★★★ 调用 LLM 判断，带 SSE 流式推送 ★★★
    # 最多重试 1 次
    max_attempts = 2
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            # 推送节点状态（仅首次）
            if attempt == 1 and sse_node_name:
                await _emit_node_status(sse_node_name, "start")
                await _emit_thinking(sse_node_name, "🔍 正在验证输入内容是否有效...")

            # 如果启用了 SSE，注入 callback handler 实现逐词推送
            if sse_node_name:
                from Agent.main_agent_conduct import SSEThinkingCallbackHandler
                handler = SSEThinkingCallbackHandler(sse_node_name)
                set_llm_callback(handler)

            try:
                prompt = _VALIDATOR_PROMPT.format(user_input=text[:200])
                llm = get_chat_openai(temperature=0.0, max_tokens=500)
                response = await llm.ainvoke(prompt)
                raw_content = response.content.strip()
                result = _extract_json(raw_content)
                result = _validate_json_result(result)
            finally:
                # 确保 callback 被清理，防止异常时泄漏
                if sse_node_name:
                    set_llm_callback(None)

            if result is None:
                last_error = f"无法从 LLM 输出中提取 JSON (attempt {attempt}): {raw_content[:300]}"
                print(f"  ⚠️ [InputValidator] {last_error}")
                # 重试前先等待一小段时间
                import asyncio
                await asyncio.sleep(0.5)
                continue

            is_valid = result.get("is_valid", False)
            reason = result.get("reason", "")
            action_type = result.get("action_type", "unrecognized")

            # 推送验证结论
            if sse_node_name:
                if not is_valid:
                    await _emit_thinking(sse_node_name, f"❌ 无效: {reason}")
                    await _emit_node_status(sse_node_name, "complete", f"invalid_{action_type}")
                else:
                    await _emit_thinking(sse_node_name, f"✅ 有效: {reason}")
                    await _emit_node_status(sse_node_name, "complete", f"valid_{action_type}")

            return {
                "is_valid": is_valid,
                "reason": reason,
                "action_type": action_type
            }
        except Exception as e:
            last_error = str(e)
            print(f"  ⚠️ [InputValidator] LLM 调用异常 (attempt {attempt}): {e}")
            # 清除 SSE callback 防止泄漏
            if sse_node_name:
                set_llm_callback(None)
            import asyncio
            await asyncio.sleep(0.5)

    # 所有重试都失败
    print(f"❌ [InputValidator] LLM 验证失败（已重试 {max_attempts} 次）: {last_error}")
    if sse_node_name:
        await _emit_thinking(sse_node_name, f"⚠️ 验证服务异常，按无效拦截")
        await _emit_node_status(sse_node_name, "complete", "fallback_invalid")
    return {
        "is_valid": False,
        "reason": "验证服务异常，已拦截",
        "action_type": "unrecognized"
    }
