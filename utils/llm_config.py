"""
统一 LLM 配置模块
所有 Agent 通过此模块获取 LLM 客户端实例，统一管理模型、API Key、Base URL。

三层缓存架构：
  第1层：精确匹配缓存（Redis-backed）- 字符串完全一致时命中
  第2层：语义缓存（GPTCache）- 语义相似时命中（需安装 gptcache）
  第3层：服务端前缀缓存（DeepSeek Prefix Cache）- 自动生效
"""

import os
import time
import json
import hashlib
import contextvars
from collections import OrderedDict
from typing import Optional, Dict, Any, List
from openai import OpenAI, AsyncOpenAI
from langchain_openai import ChatOpenAI
from langchain_core.caches import BaseCache
from langchain_core.globals import set_llm_cache
from langchain_core.outputs import Generation

# 加载 .env 文件中的环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ==================== 全局配置 ====================
MODEL = "deepseek-v4-flash"
API_KEY = os.getenv("LLM_API_KEY", "")
if not API_KEY:
    print("⚠️ [LLM Config] 警告: 环境变量 LLM_API_KEY 未设置，LLM 调用将失败")
BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")

# Redis 配置（通过环境变量配置，默认 localhost）
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "4"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
if not REDIS_PASSWORD:
    print("⚠️ [LLM Config] 警告: 环境变量 REDIS_PASSWORD 未设置")
REDIS_PREFIX = "llm_cache_v1:"  # 缓存键前缀


# ==================== SSE LLM Callback 上下文 ====================
_llm_callback_var = contextvars.ContextVar("llm_callback", default=None)

def set_llm_callback(callback):
    _llm_callback_var.set(callback)

def get_current_llm_callback():
    return _llm_callback_var.get()


# ==================== Redis 客户端 ====================

_redis_client = None
_redis_available = False

def get_redis_client():
    """获取 Redis 客户端实例（单例）"""
    global _redis_client, _redis_available
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        import redis
        
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
            protocol=2,  # ★★★ 强制 RESP2 协议，兼容 Redis 5.x 及以下版本 ★★★
        )
        _redis_client.ping()
        _redis_available = True
        print(f"✓ Redis 连接成功 ({REDIS_HOST}:{REDIS_PORT})")
    except Exception as e:
        print(f"⚠️ Redis 连接失败: {e}，将使用内存缓存降级")
        _redis_client = None
        _redis_available = False
    
    return _redis_client


# ==================== 策略1：精确匹配缓存（Redis 后端，自动降级内存） ====================

class LLMExactMatchCache(BaseCache):
    """
    精确匹配缓存 - LangChain BaseCache 接口
    
    默认使用 Redis 后端（持久化、多实例共享），
    Redis 不可用时自动降级为内存缓存。
    """
    
    def __init__(self, max_size: int = 500, ttl_seconds: int = 7200):
        self._max_size = max_size
        self._ttl = ttl_seconds
        
        self._redis_client = get_redis_client()
        self._use_redis = self._redis_client is not None
        
        # 内存缓存降级: {key: (timestamp, [Generation, ...])}
        self._mem_cache: Dict[str, tuple] = {}
        self._mem_access_order: OrderedDict = OrderedDict()
    
    def _rkey(self, key: str) -> str:
        return f"{REDIS_PREFIX}{key}"
    
    def _lru_list_key(self) -> str:
        return f"{REDIS_PREFIX}lru_order"
    
    def _generate_key(self, prompt: str, llm_string: str) -> str:
        key_str = f"{llm_string}_{prompt}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def lookup(self, prompt: str, llm_string: str) -> Optional[List[Generation]]:
        """查找缓存"""
        key = self._generate_key(prompt, llm_string)
        
        if self._use_redis:
            return self._redis_lookup(key)
        else:
            return self._mem_lookup(key)
    
    def _redis_lookup(self, key: str) -> Optional[List[Generation]]:
        try:
            data = self._redis_client.get(self._rkey(key))
            if data is None:
                return None
            
            entry = json.loads(data)
            # 检查 TTL
            if time.time() - entry["ts"] > self._ttl:
                self._redis_client.delete(self._rkey(key))
                self._redis_client.lrem(self._lru_list_key(), 0, key)
                return None
            
            self._redis_client.lrem(self._lru_list_key(), 0, key)
            self._redis_client.lpush(self._lru_list_key(), key)
            self._redis_client.ltrim(self._lru_list_key(), 0, self._max_size - 1)
            
            gens = [Generation(text=g["text"]) for g in entry["gens"]]
            print(f"  🚀 [Redis缓存命中]")
            return gens
        except Exception:
            return None
    
    def _mem_lookup(self, key: str) -> Optional[List[Generation]]:
        if key not in self._mem_cache:
            return None
        
        ts, gens = self._mem_cache[key]
        if time.time() - ts > self._ttl:
            del self._mem_cache[key]
            if key in self._mem_access_order:
                del self._mem_access_order[key]
            return None
        
        self._mem_access_order.move_to_end(key)
        
        print(f"  🚀 [内存缓存命中]")
        return gens
    
    def update(self, prompt: str, llm_string: str, return_val: List[Generation]):
        """更新缓存"""
        key = self._generate_key(prompt, llm_string)
        now = time.time()
        
        if self._use_redis:
            self._redis_update(key, return_val, now)
        else:
            self._mem_update(key, return_val, now)
    
    def _redis_update(self, key: str, return_val: List[Generation], now: float):
        try:
            data = json.dumps({
                "ts": now,
                "gens": [{"text": g.text} for g in return_val],
            }, ensure_ascii=False)
            self._redis_client.setex(self._rkey(key), self._ttl, data)
            self._redis_client.lpush(self._lru_list_key(), key)
            self._redis_client.ltrim(self._lru_list_key(), 0, self._max_size - 1)
        except Exception:
            pass
    
    def _mem_update(self, key: str, return_val: List[Generation], now: float):
        if key in self._mem_access_order:
            del self._mem_access_order[key]
        
        if len(self._mem_cache) >= self._max_size:
            oldest_key, _ = self._mem_access_order.popitem(last=False)
            del self._mem_cache[oldest_key]
        
        self._mem_cache[key] = (now, return_val)
        self._mem_access_order[key] = None
    
    def clear(self):
        if self._use_redis:
            try:
                cursor = 0
                while True:
                    cursor, keys = self._redis_client.scan(cursor, match=f"{REDIS_PREFIX}*")
                    if keys:
                        self._redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                pass
        else:
            self._mem_cache.clear()
            self._mem_access_order.clear()


# ==================== 策略2：语义缓存（GPTCache） ====================

_semantic_cache_available = False
_semantic_cache = None

try:
    from gptcache import Cache
    from gptcache.embedding import SBERT
    from gptcache.processor.pre import get_prompt
    
    _semantic_cache_available = True
    print("✓ GPTCache 语义缓存模块已加载")
except ImportError:
    print("⚠️ GPTCache 未安装，语义缓存功能不可用（pip install gptcache sentence-transformers）")


def get_semantic_cache(threshold: float = 0.85):
    """获取语义缓存实例"""
    global _semantic_cache
    
    if not _semantic_cache_available:
        return None
    
    if _semantic_cache is None:
        try:
            embedding = SBERT(model="all-MiniLM-L6-v2")
            
            _semantic_cache = Cache()
            _semantic_cache.init(
                pre_func=get_prompt,
                embedding_func=embedding,
                similarity_threshold=threshold,
            )
            print(f"✓ 语义缓存初始化完成（相似度阈值: {threshold}）")
        except Exception as e:
            print(f"⚠️ 语义缓存初始化失败: {e}")
            _semantic_cache = None
    
    return _semantic_cache


# ==================== 超时配置 ====================

class TimeoutConfig:
    SHORT = 15
    MEDIUM = 30
    LONG = 60
    EXTRA_LONG = 120


def _get_timeout_by_max_tokens(max_tokens: Optional[int]) -> int:
    if max_tokens is None:
        return TimeoutConfig.MEDIUM
    if max_tokens <= 500:
        return TimeoutConfig.SHORT
    elif max_tokens <= 2000:
        return TimeoutConfig.MEDIUM
    elif max_tokens <= 5000:
        return TimeoutConfig.LONG
    else:
        return TimeoutConfig.EXTRA_LONG


# ==================== 初始化全局缓存 ====================

_exact_match_cache = LLMExactMatchCache(max_size=500, ttl_seconds=7200)


def enable_cache(cache_type: str = "all"):
    """
    启用缓存
    
    Args:
        cache_type: "exact"（仅精确匹配）、"semantic"（仅语义）、"all"（两者叠加）
    """
    if cache_type in ["exact", "all"]:
        set_llm_cache(_exact_match_cache)
        if _exact_match_cache._use_redis:
            print("✓ 已启用 Redis 精确匹配缓存")
        else:
            print("✓ 已启用内存精确匹配缓存（降级模式）")
    
    if cache_type in ["semantic", "all"]:
        semantic_cache = get_semantic_cache()
        if semantic_cache:
            print("⚠️ 语义缓存实例可用，但 gptcache LangChainAdapter 已过时，跳过 LangChain 集成语义缓存")


def disable_cache():
    """禁用所有缓存"""
    set_llm_cache(None)
    print("✓ 已禁用所有缓存")


# ==================== 工厂函数 ====================

def get_chat_openai(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    use_cache: bool = True,
    **kwargs
) -> ChatOpenAI:
    """
    获取 langchain ChatOpenAI 实例
    
    Args:
        model: 模型名称
        temperature: 温度参数（>0.5时不建议启用缓存）
        max_tokens: 最大输出 token 数
        timeout: 请求超时秒数（默认根据 max_tokens 自动计算）
        use_cache: 是否启用缓存
        **kwargs: 其他传递给 ChatOpenAI 的参数
    
    Returns:
        ChatOpenAI 实例
    """
    if timeout is None:
        timeout = _get_timeout_by_max_tokens(max_tokens)
    
    cb = get_current_llm_callback()
    if cb is not None:
        kwargs.setdefault("callbacks", [])
        kwargs["callbacks"].append(cb)
        kwargs.setdefault("streaming", True)
    
    custom_api_key = kwargs.pop("api_key", None)
    custom_base_url = kwargs.pop("base_url", None)
    
    llm = ChatOpenAI(
        model=model or MODEL,
        api_key=custom_api_key or API_KEY,
        base_url=custom_base_url or BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        **kwargs
    )
    
    return llm


""" def get_openai_client(
    model: Optional[str] = None,
    **kwargs
) -> OpenAI:
    return OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        **kwargs
    )


def get_async_openai_client(
    model: Optional[str] = None,
    **kwargs
) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        **kwargs
    ) """


# ==================== 缓存状态查询 ====================

def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    stats = {
        "backend": "redis" if _exact_match_cache._use_redis else "memory",
        "exact_match_cache": {
            "max_size": _exact_match_cache._max_size,
            "ttl_seconds": _exact_match_cache._ttl,
        },
        "semantic_cache_available": _semantic_cache_available,
        "semantic_cache_active": _semantic_cache is not None,
    }
    
    if _exact_match_cache._use_redis:
        try:
            cursor = 0
            count = 0
            while True:
                cursor, keys = _exact_match_cache._redis_client.scan(
                    cursor, match=f"{REDIS_PREFIX}*", count=100
                )
                count += len(keys)
                if cursor == 0:
                    break
            stats["exact_match_cache"]["size"] = count
        except Exception:
            stats["exact_match_cache"]["size"] = "unknown"
    else:
        stats["exact_match_cache"]["size"] = len(_exact_match_cache._mem_cache)
    
    return stats


# ==================== 防幻觉回调 ====================

try:
    from utils.hallucination_guard import HallucinationGuard, get_hallucination_guard
    _hallucination_available = True
except ImportError:
    _hallucination_available = False
    print("⚠️ 防幻觉模块未加载，请确保 hallucination_guard.py 存在")


class HallucinationCallback:
    """防幻觉回调 - 在LLM输出后自动执行防幻觉检查"""
    
    def __init__(self, context: str = "", expected_format: str = "", strict_mode: bool = False):
        self.context = context
        self.expected_format = expected_format
        self.strict_mode = strict_mode
        self.guard = None
        self.check_result = None
    
    def on_llm_start(self, serialized, prompts, **kwargs):
        pass
    
    def on_llm_end(self, response, **kwargs):
        if not _hallucination_available:
            return
        
        try:
            from langchain_core.messages import BaseMessage
            
            self.guard = get_hallucination_guard(self.strict_mode)
            
            if hasattr(response, 'generations') and response.generations:
                for gen_list in response.generations:
                    for gen in gen_list:
                        output = gen.text if hasattr(gen, 'text') else str(gen)
                        
                        import asyncio
                        try:
                            loop = asyncio.get_running_loop()
                        except RuntimeError:
                            loop = None
                        
                        if loop and loop.is_running():
                            # 已在异步事件循环中，无法使用 asyncio.run()
                            # 创建新线程执行协程
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                                future = executor.submit(asyncio.run, self.guard.check(output, self.context, self.expected_format))
                                self.check_result = future.result(timeout=30)
                        else:
                            self.check_result = asyncio.run(
                                self.guard.check(output, self.context, self.expected_format)
                            )
                        
                        if not self.check_result.passed:
                            print(f"⚠️ [防幻觉] 检测到问题: {self.check_result.errors}")
                            print(f"   置信度: {self.check_result.confidence.value}")
                            print(f"   安全等级: {self.check_result.safety.value}")
            
        except Exception as e:
            print(f"⚠️ 防幻觉回调执行失败: {e}")
    
    def on_llm_error(self, error, **kwargs):
        pass
    
    def on_chain_start(self, serialized, inputs, **kwargs):
        pass
    
    def on_chain_end(self, outputs, **kwargs):
        pass
    
    def on_chain_error(self, error, **kwargs):
        pass
    
    def on_tool_start(self, serialized, input_str, **kwargs):
        pass
    
    def on_tool_end(self, output, **kwargs):
        pass
    
    def on_tool_error(self, error, **kwargs):
        pass


def get_hallucination_callback(context: str = "", expected_format: str = "", 
                               strict_mode: bool = False) -> HallucinationCallback:
    """获取防幻觉回调实例"""
    return HallucinationCallback(context, expected_format, strict_mode)


def get_chat_openai_with_guard(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    use_cache: bool = True,
    hallucination_context: str = "",
    hallucination_format: str = "",
    strict_mode: bool = False,
    **kwargs
) -> ChatOpenAI:
    """
    获取带防幻觉检查的 langchain ChatOpenAI 实例
    
    Args:
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大输出 token 数
        timeout: 请求超时秒数
        use_cache: 是否启用缓存
        hallucination_context: 参考文档上下文（用于事实校验）
        hallucination_format: 期望的输出格式（如 "json"）
        strict_mode: 严格模式，更严格的校验规则
        **kwargs: 其他传递给 ChatOpenAI 的参数
    
    Returns:
        ChatOpenAI 实例（带防幻觉回调）
    """
    llm = get_chat_openai(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        use_cache=use_cache,
        **kwargs
    )
    
    if _hallucination_available and hallucination_context:
        callback = HallucinationCallback(
            context=hallucination_context,
            expected_format=hallucination_format,
            strict_mode=strict_mode
        )
        llm.callbacks = llm.callbacks or []
        llm.callbacks.append(callback)
        print(f"✅ 已为LLM添加防幻觉回调")
    
    return llm
