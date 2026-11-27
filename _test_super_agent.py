"""临时验证脚本：直接调用 SuperAgent 处理复合任务，检查是否实际执行工具"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Agent.super_agent import SuperAgent


async def main():
    from utils.llm_config import set_llm_callback
    set_llm_callback(None)  # 不注入 SSE callback，避免流式干扰

    agent = SuperAgent()
    result = await agent.process(
        user_input="解释一下什么叫做冒泡排序，并生成关于它的编程题",
        user_id="user_001",
        max_tool_calls=10,
    )
    print("=" * 60)
    print(json.dumps({
        "success": result.get("success"),
        "layer": result.get("layer"),
        "reply": result.get("reply", "")[:500],
        "tool_call_count": result.get("tool_call_count"),
        "resources": list(result.get("resources", {}).keys()),
        "details": result.get("details", {}),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
