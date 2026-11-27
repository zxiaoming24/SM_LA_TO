"""
并发执行管理器 - 提供线程池和异步支持

核心功能:
1. 线程池管理: 为不同用户分配独立的执行线程
2. 任务隔离: 确保用户A和用户B的任务互不阻塞
3. 资源控制: 限制最大并发数,避免系统过载
4. 异步包装: 将同步Agent调用包装为异步任务
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Callable, Optional
import threading
from datetime import datetime


class ConcurrentExecutor:
    """
    并发执行器 - 管理多用户任务的并发执行
    
    设计原则:
    1. 每个用户的请求在独立线程中执行
    2. 使用线程池限制最大并发数
    3. 支持异步等待和超时控制
    4. 线程安全的结果收集
    """
    
    def __init__(self, max_workers: int = 16):
        """
        初始化并发执行器
        
        Args:
            max_workers: 最大工作线程数(建议值: CPU核心数 * 2)
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="AgentWorker"
        )
        
        # 跟踪活跃任务
        self.active_tasks: Dict[str, dict] = {}
        self._tasks_lock = threading.Lock()
        
        print(f"✅ 并发执行器初始化完成 (最大并发数: {max_workers})")
    
    async def execute_async(self, func: Callable, *args, task_id: str = None, **kwargs) -> Any:
        """
        异步执行同步函数(在线程池中运行)
        
        Args:
            func: 要执行的同步函数
            *args: 位置参数
            task_id: 任务ID(用于追踪)
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果
        """
        loop = asyncio.get_running_loop()
        
        # 生成任务ID
        if not task_id:
            task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(func)}"
        
        # 记录任务开始
        self._register_task(task_id, func.__name__)
        
        try:
            # ★★★ 关键优化:在线程池中执行,每个线程有独立的事件循环 ★★★
            def run_in_thread():
                """在线程中创建新的事件循环并执行"""
                import concurrent.futures
                
                # 为每个线程创建独立的事件循环
                thread_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(thread_loop)
                
                try:
                    # 如果func是协程函数,直接运行
                    if asyncio.iscoroutinefunction(func):
                        return thread_loop.run_until_complete(func(*args, **kwargs))
                    else:
                        # 如果是普通函数,直接调用
                        return func(*args, **kwargs)
                finally:
                    thread_loop.close()
            
            # 在线程池中执行
            result = await loop.run_in_executor(
                self.executor,
                run_in_thread
            )
            
            # 记录任务完成
            self._complete_task(task_id, success=True)
            
            return result
            
        except Exception as e:
            # 记录任务失败
            self._complete_task(task_id, success=False, error=str(e))
            raise
    
    def execute_sync(self, func: Callable, *args, timeout: int = 300, **kwargs) -> Any:
        """
        同步执行函数(带超时控制)
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            timeout: 超时时间(秒)
            **kwargs: 关键字参数
            
        Returns:
            函数执行结果
        """
        future = self.executor.submit(func, *args, **kwargs)
        
        try:
            result = future.result(timeout=timeout)
            return result
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"任务执行超时 ({timeout}秒)")
    
    def execute_batch_async(self, tasks: list) -> list:
        """
        批量异步执行多个任务
        
        Args:
            tasks: 任务列表,每个元素是 (func, args, kwargs) 元组
            
        Returns:
            结果列表
        """
        futures = []
        
        for func, args, kwargs in tasks:
            future = self.executor.submit(func, *args, **kwargs)
            futures.append(future)
        
        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append({"success": True, "result": result})
            except Exception as e:
                results.append({"success": False, "error": str(e)})
        
        return results
    
    def get_active_tasks_count(self) -> int:
        """获取当前活跃任务数"""
        with self._tasks_lock:
            return len([t for t in self.active_tasks.values() if t.get("status") == "running"])
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        with self._tasks_lock:
            running = len([t for t in self.active_tasks.values() if t.get("status") == "running"])
            completed = len([t for t in self.active_tasks.values() if t.get("status") == "completed"])
            failed = len([t for t in self.active_tasks.values() if t.get("status") == "failed"])
        
        return {
            "max_workers": self.max_workers,
            "active_tasks": running,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "total_tasks": len(self.active_tasks)
        }
    
    def _register_task(self, task_id: str, func_name: str):
        """注册任务开始"""
        with self._tasks_lock:
            self.active_tasks[task_id] = {
                "func_name": func_name,
                "start_time": datetime.now().isoformat(),
                "status": "running"
            }
    
    _MAX_COMPLETED_TASKS = 1000  # 已完成任务最大保留数，超出则清理最早的

    def _complete_task(self, task_id: str, success: bool, error: str = None):
        """标记任务完成，并清理超量的历史记录防止内存泄漏"""
        with self._tasks_lock:
            if task_id in self.active_tasks:
                self.active_tasks[task_id].update({
                    "status": "completed" if success else "failed",
                    "end_time": datetime.now().isoformat(),
                    "error": error
                })
            # 清理超量的已完成/已失败任务
            completed = [k for k, v in self.active_tasks.items() if v.get("status") in ("completed", "failed")]
            if len(completed) > self._MAX_COMPLETED_TASKS:
                for k in sorted(completed, key=lambda x: self.active_tasks[x].get("start_time", ""))[:len(completed) - self._MAX_COMPLETED_TASKS]:
                    del self.active_tasks[k]
    
    def shutdown(self, wait: bool = True):
        """关闭执行器"""
        print("🔄 正在关闭并发执行器...")
        self.executor.shutdown(wait=wait)
        print("✅ 并发执行器已关闭")





# ==================== 同步中运行异步的辅助函数 ====================

def run_async(coro, timeout: int = 300):
    """
    在同步上下文中安全地执行异步协程
    
    为每次调用创建独立的事件循环，确保在Windows上也能正常工作。
    适用于 LangGraph 节点函数中需要调用异步方法的情况。
    
    Args:
        coro: 要执行的协程对象（如 async_function() 的返回值）
        timeout: 超时时间(秒)
        
    Returns:
        协程执行结果
        
    使用示例:
        result = run_async(some_async_function(arg1, arg2))
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            # ★★★ 先运行一轮让 call_soon 注册的清理回调（如 HTTPX AsyncClient）执行完 ★★★
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass
        try:
            # ★★★ 再取消仍未完成的 Task ★★★
            _cancel_pending_tasks(loop)
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        finally:
            try:
                loop.close()
            except RuntimeError:
                pass


def _cancel_pending_tasks(loop):
    """取消事件循环中所有未完成的任务，并抑制 httpx 等库的清理异常"""
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    # ★★★ 收集并丢弃异常，避免 "Task exception was never retrieved" ★★★
    for task in pending:
        if task.done() and not task.cancelled() and task.exception():
            try:
                task.exception()  # 检索异常以消除警告
            except (asyncio.CancelledError, RuntimeError):
                pass
