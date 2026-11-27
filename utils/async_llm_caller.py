"""
异步LLM调用工具 - 解决底层Agent的同步阻塞问题

核心功能:
1. 将所有同步的llm.invoke()改为异步的llm.ainvoke()
2. 提供统一的异步调用接口
3. 支持超时控制和重试机制
"""

import asyncio
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI


class AsyncLLMCaller:
    """
    异步LLM调用器
    
    设计原则:
    1. 所有LLM调用都使用ainvoke()而非invoke()
    2. 在线程池中运行(因为LangChain的ainvoke内部可能仍有同步操作)
    3. 支持超时和重试
    """
    
    @staticmethod
    async def call_llm_async(llm: ChatOpenAI, prompt, timeout: int = 60, max_retries: int = 2) -> Any:
        """
        异步调用LLM
        
        Args:
            llm: LangChain LLM实例
            prompt: 提示词
            timeout: 超时时间(秒)
            max_retries: 最大重试次数
            
        Returns:
            LLM响应结果
        """
        for attempt in range(max_retries + 1):
            try:
                # ★★★ 使用异步调用 ★★★
                if hasattr(llm, 'ainvoke'):
                    response = await asyncio.wait_for(
                        llm.ainvoke(prompt),
                        timeout=timeout
                    )
                else:
                    # 降级:如果LLM不支持ainvoke,在线程池中执行同步调用
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: llm.invoke(prompt)
                    )
                
                return response
                
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    print(f"⚠️  LLM调用超时(尝试{attempt+1}/{max_retries+1}),重试中...")
                    await asyncio.sleep(1)
                else:
                    raise TimeoutError(f"LLM调用超时({timeout}秒)")
                    
            except Exception as e:
                if attempt < max_retries:
                    print(f"⚠️  LLM调用失败(尝试{attempt+1}/{max_retries+1}): {e},重试中...")
                    await asyncio.sleep(1)
                else:
                    raise
    
    @staticmethod
    def call_llm_sync_with_timeout(llm: ChatOpenAI, prompt, timeout: int = 60) -> Any:
        """
        同步调用LLM(带超时控制,用于向后兼容)
        
        Args:
            llm: LangChain LLM实例
            prompt: 提示词
            timeout: 超时时间(秒)
            
        Returns:
            LLM响应结果
        """
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(llm.invoke, prompt)
            try:
                result = future.result(timeout=timeout)
                return result
            except concurrent.futures.TimeoutError:
                future.cancel()
                raise TimeoutError(f"LLM调用超时({timeout}秒)")


# ==================== 辅助函数 ====================

async def safe_llm_invoke(llm: ChatOpenAI, prompt, timeout: int = 60) -> Any:
    """
    安全的LLM异步调用(推荐在所有Agent中使用)
    
    用法示例:
        from utils.async_llm_caller import safe_llm_invoke
        
        # 原来的代码:
        # response = self.llm.invoke(prompt)
        
        # 改为:
        response = await safe_llm_invoke(self.llm, prompt)
    """
    caller = AsyncLLMCaller()
    return await caller.call_llm_async(llm, prompt, timeout=timeout)


def safe_llm_invoke_sync(llm: ChatOpenAI, prompt, timeout: int = 60) -> Any:
    """
    安全的LLM同步调用(带超时,用于无法改为async的场景)
    
    用法示例:
        from utils.async_llm_caller import safe_llm_invoke_sync
        
        # 原来的代码:
        # response = self.llm.invoke(prompt)
        
        # 改为:
        response = safe_llm_invoke_sync(self.llm, prompt, timeout=60)
    """
    caller = AsyncLLMCaller()
    return caller.call_llm_sync_with_timeout(llm, prompt, timeout=timeout)


# ==================== LLM 调用重试工具 ====================

async def call_llm_with_retry(
    llm,
    prompt,
    max_retries: int = 2,
    parse_json: bool = False,
    error_msg: str = "LLM调用失败"
) -> Any:
    """
    带重试机制的 LLM 调用封装
    
    Args:
        llm: LLM 实例（支持 ainvoke）
        prompt: 输入 prompt（str 或 Message 列表）
        max_retries: 最大重试次数
        parse_json: 是否尝试解析返回结果为 JSON
        error_msg: 失败时的错误日志前缀
        
    Returns:
        LLM 响应，解析失败时返回 None
    """
    import asyncio
    import json
    
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"  ⚠️ {error_msg} 重试第 {attempt}/{max_retries} 次...")
                await asyncio.sleep(1 * attempt)  # 退避等待
                
            response = await asyncio.wait_for(
                llm.ainvoke(prompt),
                timeout=60.0
            )
            
            if parse_json:
                text = response.content if hasattr(response, 'content') else str(response)
                # 尝试提取 JSON
                import re
                json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
                if json_match:
                    text = json_match.group(1).strip()
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    if attempt < max_retries:
                        continue
                    return None
                    
            return response
            
        except (asyncio.TimeoutError, Exception) as e:
            print(f"  ⚠️ {error_msg} 失败 (attempt {attempt+1}/{max_retries+1}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(1 * (attempt + 1))
            else:
                print(f"  ❌ {error_msg} 已达到最大重试次数")
                return None
    
    return None


async def call_llm_with_retry_typed(
    llm,
    prompt,
    response_model,
    max_retries: int = 2,
    error_msg: str = "LLM调用失败"
) -> Any:
    """
    带重试机制的 LLM 调用封装（带结构化输出，适用于 with_structured_output）
    
    Args:
        llm: LLM 实例（支持 ainvoke + with_structured_output）
        prompt: 输入 prompt
        response_model: Pydantic 模型
        max_retries: 最大重试次数
        error_msg: 失败时的错误日志前缀
        
    Returns:
        结构化输出结果，失败时返回 None
    """
    import asyncio
    
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"  ⚠️ {error_msg} 重试第 {attempt}/{max_retries} 次...")
                await asyncio.sleep(1 * attempt)
                
            structured_llm = llm.with_structured_output(response_model)
            result = await asyncio.wait_for(
                structured_llm.ainvoke(prompt),
                timeout=60.0
            )
            return result
            
        except (asyncio.TimeoutError, Exception) as e:
            print(f"  ⚠️ {error_msg} 失败 (attempt {attempt+1}/{max_retries+1}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(1 * (attempt + 1))
            else:
                print(f"  ❌ {error_msg} 已达到最大重试次数")
                return None
    
    return None
