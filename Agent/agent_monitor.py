"""
agent_monitor.py - Agent 调用监控与实时状态追踪

提供轻量级的 Agent 调用计数、实时状态追踪和排行。
数据持久化到 JSON 文件，同时维护内存缓存。
线程安全，支持多用户并发访问。
"""

import json
import os
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime

# ==================== Agent 名称映射 ====================
# 统一系统中所有 agent 的显示名称
AGENT_INFO: Dict[str, dict] = {
    # Conduct 层子 Agent
    "practice": {
        "name": "PracticeAgent",
        "icon": "💻",
        "desc": "编程练习生成",
        "group": "资源生成"
    },
    "judge_code": {
        "name": "JudgeAgent",
        "icon": "⚖️",
        "desc": "代码评判",
        "group": "资源生成"
    },
    "question_gen": {
        "name": "QuestionGeneratorAgent",
        "icon": "📝",
        "desc": "理论题生成",
        "group": "资源生成"
    },
    "doc_gen": {
        "name": "CourseDocAgent",
        "icon": "📚",
        "desc": "课程文档生成",
        "group": "资源生成"
    },
    "extension": {
        "name": "ExtensionReadingAgent",
        "icon": "📖",
        "desc": "拓展阅读生成",
        "group": "资源生成"
    },
    "video": {
        "name": "VideoSearchAgent",
        "icon": "🎬",
        "desc": "视频搜索入库",
        "group": "资源生成"
    },
    "mindmap": {
        "name": "MindMapAgent",
        "icon": "🧠",
        "desc": "思维导图生成",
        "group": "资源生成"
    },
    "animation": {
        "name": "AnimationAgent",
        "icon": "🎨",
        "desc": "动画 HTML 生成",
        "group": "资源生成"
    },
    "study_plan": {
        "name": "StudyPlanAgent",
        "icon": "📋",
        "desc": "学习计划生成",
        "group": "资源生成"
    },
    "ppt": {
        "name": "PPTCreationAgent",
        "icon": "📊",
        "desc": "PPT 课件生成",
        "group": "资源生成"
    },
    # SuperAgent 工具
    "tool_general_qa": {
        "name": "ChatAgent",
        "icon": "💬",
        "desc": "日常对话问答",
        "group": "对话交互"
    },
    "tool_knowledge_qa": {
        "name": "KnowledgeBaseAgent",
        "icon": "📘",
        "desc": "知识库问答",
        "group": "对话交互"
    },
    # DES 层
    "des_layer": {
        "name": "MainAgent(DES)",
        "icon": "👤",
        "desc": "用户画像与注册",
        "group": "系统服务"
    },
    "super_agent": {
        "name": "SuperAgent",
        "icon": "🧩",
        "desc": "超级智能体(ReAct)",
        "group": "系统服务"
    }
}


class AgentMonitor:
    """Agent 调用监控器（单例，线程安全）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data_lock = threading.Lock()

        # 存储路径
        self._data_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data"
        )
        os.makedirs(self._data_dir, exist_ok=True)
        self._file_path = os.path.join(self._data_dir, "agent_monitor.json")

        # ★★★ 写入去抖动：高频调用时合并写入，避免频繁磁盘 I/O ★★★
        self._dirty = False
        self._last_save_time = 0
        self._save_interval = 3.0  # 最小写入间隔（秒）

        # 内存数据
        # call_stats: {agent_key: {"count": int, "last_call": timestamp, "total_duration": float}}
        self._call_stats: Dict[str, dict] = {}
        # status: {agent_key: "idle" | "working" | "busy"}
        self._status: Dict[str, str] = {}
        # concurrent_count: {agent_key: int} — 当前同时调用该 agent 的用户数（引用计数）
        self._concurrent_count: Dict[str, int] = {}
        # current_tasks: {agent_key: {"task_info": str, "user_id": str, "start_time": float}}
        # 只保留最近一个任务用于展示，实际状态由 concurrent_count 决定
        self._current_tasks: Dict[str, dict] = {}
        # history: list of recent calls (ring buffer, max 500)
        self._history: List[dict] = []
        self._max_history = 500

        # 初始化所有 agent 状态
        for key in AGENT_INFO:
            self._status[key] = "idle"
            self._concurrent_count[key] = 0
            self._call_stats[key] = {"count": 0, "last_call": 0, "total_duration": 0.0}

        # 从磁盘加载
        self._load()

    def _load(self):
        """从 JSON 文件加载持久化数据"""
        try:
            if os.path.exists(self._file_path):
                # ★★★ 修复：读取和写入全部在锁内执行，避免并发读写损坏 ★★★
                with self._data_lock:
                    with open(self._file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "call_stats" in data:
                        for k, v in data["call_stats"].items():
                            if k in self._call_stats:
                                self._call_stats[k] = v
                    # 不恢复 status（状态是运行时的）
                    if "history" in data:
                        self._history = data["history"][-self._max_history:]
        except Exception as e:
            print(f"  ⚠️ [AgentMonitor] 加载数据失败: {e}")

    def _save(self):
        """持久化到 JSON 文件（含去抖动：高频调用时合并写入，最小间隔 self._save_interval 秒）"""
        now = time.time()
        if now - self._last_save_time < self._save_interval:
            # 距离上次写入不足间隔，标记为 dirty 延迟写入
            self._dirty = True
            return
        self._flush_save()

    def _flush_save(self):
        """立即执行磁盘写入（无去抖动）"""
        try:
            # ★★★ 修复：整个读-改-写操作在锁内完成，避免并发写入损坏 ★★★
            with self._data_lock:
                data = {
                    "call_stats": self._call_stats,
                    "history": self._history[-self._max_history:],
                    "last_update": time.time()
                }
                with open(self._file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                self._last_save_time = time.time()
                self._dirty = False
        except Exception as e:
            print(f"  ⚠️ [AgentMonitor] 保存数据失败: {e}")

    # ==================== 公共方法 ====================

    def report_call_start(self, agent_key: str, user_id: str = "",
                          task_info: str = "") -> None:
        """
        报告 Agent 开始被调用

        Args:
            agent_key: Agent 标识（如 practice, question_gen）
            user_id: 发起调用的用户 ID
            task_info: 任务描述
        """
        if agent_key not in AGENT_INFO:
            agent_key = self._resolve_agent_key(agent_key)

        with self._data_lock:
            if agent_key not in self._call_stats:
                self._call_stats[agent_key] = {"count": 0, "last_call": 0, "total_duration": 0.0}
            if agent_key not in self._concurrent_count:
                self._concurrent_count[agent_key] = 0
            self._concurrent_count[agent_key] += 1
            self._status[agent_key] = "working"
            self._current_tasks[agent_key] = {
                "task_info": task_info,
                "user_id": user_id,
                "start_time": time.time()
            }

    def report_call_end(self, agent_key: str, success: bool = True) -> None:
        """
        报告 Agent 调用结束

        Args:
            agent_key: Agent 标识
            success: 是否成功
        """
        if agent_key not in AGENT_INFO:
            agent_key = self._resolve_agent_key(agent_key)

        with self._data_lock:
            if agent_key not in self._call_stats:
                return

            # 减少引用计数
            self._concurrent_count[agent_key] = max(0, self._concurrent_count.get(agent_key, 0) - 1)

            # 更新计数
            self._call_stats[agent_key]["count"] += 1
            self._call_stats[agent_key]["last_call"] = time.time()

            # 计算耗时
            task = self._current_tasks.get(agent_key, {})
            start = task.get("start_time", time.time())
            duration = time.time() - start
            self._call_stats[agent_key]["total_duration"] += duration

            # 更新状态：仅当没有其他用户在使用时才变为 idle
            if self._concurrent_count[agent_key] <= 0:
                self._status[agent_key] = "idle"
            task_info = task.get("task_info", "")
            user_id = task.get("user_id", "")

            # 记录历史
            self._history.append({
                "agent": agent_key,
                "agent_name": AGENT_INFO.get(agent_key, {}).get("name", agent_key),
                "icon": AGENT_INFO.get(agent_key, {}).get("icon", "🤖"),
                "user_id": user_id,
                "task_info": task_info,
                "duration": round(duration, 2),
                "success": success,
                "timestamp": time.time()
            })

            # 清理当前任务
            self._current_tasks.pop(agent_key, None)

        # 每次调用都持久化，防止数据丢失
        self._save()

    def set_status(self, agent_key: str, status: str) -> None:
        """手动设置 Agent 状态"""
        with self._data_lock:
            self._status[agent_key] = status

    def get_stats(self) -> Dict[str, Any]:
        """获取所有 Agent 统计和状态"""
        self._flush_if_dirty()
        with self._data_lock:
            # 排行数据（按调用次数降序）
            ranking = []
            for key, stats in self._call_stats.items():
                info = AGENT_INFO.get(key, {})
                avg_duration = (stats["total_duration"] / stats["count"]) if stats["count"] > 0 else 0
                ranking.append({
                    "agent_key": key,
                    "icon": info.get("icon", "🤖"),
                    "name": info.get("name", key),
                    "desc": info.get("desc", ""),
                    "group": info.get("group", ""),
                    "call_count": stats["count"],
                    "last_call": stats["last_call"],
                    "avg_duration": round(avg_duration, 1),
                    "total_duration": round(stats["total_duration"], 1),
                    "status": self._status.get(key, "idle"),
                    "current_task": self._current_tasks.get(key, {})
                })
            ranking.sort(key=lambda x: x["call_count"], reverse=True)

            # 当前工作中的 agent
            working = [
                {**r} for r in ranking
                if r["status"] == "working"
            ]

            return {
                "ranking": ranking,
                "working": working,
                "total_calls": sum(r["call_count"] for r in ranking),
                "total_agents": len(ranking),
                "working_count": len(working),
                "update_time": time.time()
            }

    def get_history(self, limit: int = 50) -> List[dict]:
        """获取最近的调用历史"""
        self._flush_if_dirty()
        with self._data_lock:
            return list(self._history[-limit:])

    def _flush_if_dirty(self):
        """如果有未刷新的脏数据且已过间隔时间，执行写入"""
        if self._dirty:
            now = time.time()
            if now - self._last_save_time >= self._save_interval:
                self._flush_save()

    def reset_stats(self):
        """重置所有统计数据"""
        with self._data_lock:
            for key in self._call_stats:
                self._call_stats[key] = {"count": 0, "last_call": 0, "total_duration": 0.0}
                self._status[key] = "idle"
                self._concurrent_count[key] = 0
            self._current_tasks.clear()
            self._history.clear()
        self._flush_save()  # 重置操作需要立即持久化

    @staticmethod
    def _resolve_agent_key(key: str) -> str:
        """解析可能的别名到标准 agent_key"""
        # 如果 key 本身就匹配，直接返回
        if key in AGENT_INFO:
            return key
        # 尝试匹配 name
        for k, v in AGENT_INFO.items():
            if v["name"] == key:
                return k
        # 尝试匹配工具名
        tool_map = {
            "tool_generate_practice": "practice",
            "tool_generate_questions": "question_gen",
            "tool_generate_document": "doc_gen",
            "tool_generate_extension": "extension",
            "tool_search_video": "video",
            "tool_generate_mindmap": "mindmap",
            "tool_generate_animation": "animation",
            "tool_generate_study_plan": "study_plan",
            "tool_generate_ppt": "ppt",
            "tool_judge_code": "judge_code",
            "tool_knowledge_qa": "tool_knowledge_qa",
            "tool_general_qa": "tool_general_qa",
            # SuperAgent 直接传 action 名（不含 tool_ 前缀）
            "search_video": "video",
            "generate_practice": "practice",
            "generate_questions": "question_gen",
            "generate_document": "doc_gen",
            "generate_extension": "extension",
            "generate_mindmap": "mindmap",
            "generate_study_plan": "study_plan",
            "generate_ppt": "ppt",
            "judge_code": "judge_code",
            "knowledge_qa": "tool_knowledge_qa",
            "general_qa": "tool_general_qa",
            # Conduct 层节点名 → AGENT_INFO key 映射
            "judge": "judge_code",
        }
        return tool_map.get(key, key)


# ==================== 全局单例 ====================
_monitor: Optional[AgentMonitor] = None


def get_monitor() -> AgentMonitor:
    """获取全局 AgentMonitor 单例"""
    global _monitor
    if _monitor is None:
        _monitor = AgentMonitor()
    return _monitor


# ==================== 便捷包装函数 ====================

def report_call_start(agent_key: str, user_id: str = "", task_info: str = ""):
    """便捷函数：报告调用开始"""
    get_monitor().report_call_start(agent_key, user_id, task_info)


def report_call_end(agent_key: str, success: bool = True):
    """便捷函数：报告调用结束"""
    get_monitor().report_call_end(agent_key, success)


def get_agent_stats() -> Dict[str, Any]:
    """便捷函数：获取统计数据"""
    return get_monitor().get_stats()


def get_agent_history(limit: int = 50) -> List[dict]:
    """便捷函数：获取历史"""
    return get_monitor().get_history(limit)
