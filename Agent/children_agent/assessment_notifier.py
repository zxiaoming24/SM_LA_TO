"""
评估报告通知服务 - 负责主动推送评估报告给用户

核心功能：
1. 新评估报告生成时的即时推送
2. 定时检测并推送待处理的评估报告
3. 支持WebSocket实时推送
4. 支持多种推送渠道
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass


@dataclass
class Notification:
    """通知消息结构"""
    user_id: str
    assessment_id: str
    type: str  # 'new_assessment', 'reminder', 'update'
    title: str
    content: str
    timestamp: str
    read: bool = False


class AssessmentNotifier:
    """评估报告通知服务"""
    
    def __init__(self):
        self._notification_store = {}  # user_id -> list[Notification]
        self._listeners = []  # 订阅者回调函数
        self._push_interval = 60  # 推送检查间隔（秒）
        self._running = False
        self._task = None
    
    def add_listener(self, callback: Callable[[Notification], None]):
        """添加推送监听器"""
        if callback not in self._listeners:
            self._listeners.append(callback)
    
    def remove_listener(self, callback: Callable[[Notification], None]):
        """移除推送监听器"""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    async def notify_new_assessment(self, user_id: str, assessment: Dict[str, Any]):
        """
        新评估报告生成时发送通知
        
        Args:
            user_id: 用户ID
            assessment: 评估报告数据
        """
        notification = Notification(
            user_id=user_id,
            assessment_id=assessment.get("assessment_id", ""),
            type="new_assessment",
            title="新的学习评估报告",
            content=self._format_assessment_summary(assessment),
            timestamp=datetime.now().isoformat(),
            read=False
        )
        
        # 保存通知
        self._save_notification(user_id, notification)
        
        # 触发实时推送
        await self._push_notification(notification)
        
        print(f"✅ [评估通知] 已发送新评估报告通知: user_id={user_id}, assessment_id={notification.assessment_id}")
    
    def _format_assessment_summary(self, assessment: Dict[str, Any]) -> str:
        """格式化评估报告摘要"""
        overall_level = assessment.get("overall_level", "")
        overall_score = assessment.get("overall_score", "")
        
        summary = f"您的学习评估已完成！\n"
        if overall_level:
            summary += f"总体评估等级：{overall_level}\n"
        if overall_score:
            summary += f"综合得分：{overall_score}分\n"
        
        # 添加薄弱点摘要
        weak_points = assessment.get("weak_points", [])[:2]
        if weak_points:
            summary += "\n薄弱点：\n"
            for wp in weak_points:
                summary += f"- {wp.get('point', '')} ({wp.get('priority', '')})\n"
        
        # 添加建议摘要
        suggestions = assessment.get("suggestions", [])[:2]
        if suggestions:
            summary += "\n建议：\n"
            for i, s in enumerate(suggestions, 1):
                summary += f"{i}. {s.get('suggestion', '')[:30]}...\n"
        
        return summary.strip()
    
    async def _push_notification(self, notification: Notification):
        """推送通知给所有订阅者"""
        for callback in self._listeners:
            try:
                # 支持同步和异步回调
                if asyncio.iscoroutinefunction(callback):
                    await callback(notification)
                else:
                    callback(notification)
            except Exception as e:
                print(f"⚠️ [评估通知] 推送失败: {e}")
    
    def _save_notification(self, user_id: str, notification: Notification):
        """保存通知到本地存储"""
        if user_id not in self._notification_store:
            self._notification_store[user_id] = []
        
        # 限制每个用户最多保存20条通知
        notifications = self._notification_store[user_id]
        notifications.insert(0, notification)
        self._notification_store[user_id] = notifications[:20]
        
        # 持久化到磁盘
        self._persist_notifications(user_id)
    
    def _persist_notifications(self, user_id: str):
        """持久化通知到磁盘"""
        try:
            notif_dir = Path(f"./user_assessments/{user_id}/notifications")
            notif_dir.mkdir(parents=True, exist_ok=True)
            
            notifications = self._notification_store.get(user_id, [])
            data = [
                {
                    "user_id": n.user_id,
                    "assessment_id": n.assessment_id,
                    "type": n.type,
                    "title": n.title,
                    "content": n.content,
                    "timestamp": n.timestamp,
                    "read": n.read
                }
                for n in notifications
            ]
            
            with open(notif_dir / "notifications.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ [评估通知] 持久化失败: {e}")
    
    def _load_notifications(self, user_id: str):
        """从磁盘加载通知"""
        try:
            notif_file = Path(f"./user_assessments/{user_id}/notifications/notifications.json")
            if notif_file.exists():
                with open(notif_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    notifications = [
                        Notification(
                            user_id=n["user_id"],
                            assessment_id=n["assessment_id"],
                            type=n["type"],
                            title=n["title"],
                            content=n["content"],
                            timestamp=n["timestamp"],
                            read=n.get("read", False)
                        )
                        for n in data
                    ]
                    self._notification_store[user_id] = notifications
        except Exception as e:
            print(f"⚠️ [评估通知] 加载失败: {e}")
    
    def get_unread_count(self, user_id: str) -> int:
        """获取用户未读通知数量"""
        if user_id not in self._notification_store:
            self._load_notifications(user_id)
        
        notifications = self._notification_store.get(user_id, [])
        return sum(1 for n in notifications if not n.read)
    
    def get_notifications(self, user_id: str, limit: int = 10) -> list:
        """获取用户通知列表"""
        if user_id not in self._notification_store:
            self._load_notifications(user_id)
        
        notifications = self._notification_store.get(user_id, [])[:limit]
        return [
            {
                "assessment_id": n.assessment_id,
                "type": n.type,
                "title": n.title,
                "content": n.content,
                "timestamp": n.timestamp,
                "read": n.read
            }
            for n in notifications
        ]
    
    def mark_as_read(self, user_id: str, assessment_id: Optional[str] = None):
        """标记通知为已读"""
        if user_id not in self._notification_store:
            self._load_notifications(user_id)
        
        notifications = self._notification_store.get(user_id, [])
        for n in notifications:
            if assessment_id is None or n.assessment_id == assessment_id:
                n.read = True
        
        self._persist_notifications(user_id)
    
    def clear_notifications(self, user_id: str):
        """清除用户所有通知"""
        if user_id in self._notification_store:
            del self._notification_store[user_id]
        
        try:
            notif_dir = Path(f"./user_assessments/{user_id}/notifications")
            if notif_dir.exists():
                import shutil
                shutil.rmtree(notif_dir)
        except Exception as e:
            print(f"⚠️ [评估通知] 清除失败: {e}")
    
    async def start(self):
        """启动定时推送服务"""
        if self._running:
            return
        
        self._running = True
        print("🚀 [评估通知] 启动评估报告推送服务...")
        
        # 启动定时检查任务
        self._task = asyncio.create_task(self._periodic_check())
    
    async def stop(self):
        """停止定时推送服务"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("🛑 [评估通知] 评估报告推送服务已停止")
    
    async def _periodic_check(self):
        """定时检查待推送的评估报告"""
        while self._running:
            try:
                await self._check_pending_assessments()
            except Exception as e:
                print(f"⚠️ [评估通知] 定时检查失败: {e}")
            
            await asyncio.sleep(self._push_interval)
    
    async def _check_pending_assessments(self):
        """检查是否有未推送的评估报告"""
        # 扫描所有用户的评估目录，查找未推送的报告
        assess_root = Path("./user_assessments")
        if not assess_root.exists():
            return
        
        for user_dir in assess_root.iterdir():
            if not user_dir.is_dir():
                continue
            
            user_id = user_dir.name
            
            # 检查新的评估报告（最近10分钟内生成且未推送）
            for assess_file in user_dir.glob("assess_*.json"):
                try:
                    mtime = datetime.fromtimestamp(assess_file.stat().st_mtime)
                    if datetime.now() - mtime < timedelta(minutes=10):
                        # 检查是否已推送
                        with open(assess_file, "r", encoding="utf-8") as f:
                            assessment = json.load(f)
                        
                        if not assessment.get("notified", False):
                            # 发送通知
                            await self.notify_new_assessment(user_id, assessment)
                            
                            # 标记已推送
                            assessment["notified"] = True
                            with open(assess_file, "w", encoding="utf-8") as f:
                                json.dump(assessment, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"⚠️ [评估通知] 检查评估文件失败 {assess_file}: {e}")


# 创建全局单例
_notifier = None

def get_assessment_notifier() -> AssessmentNotifier:
    """获取评估通知服务单例"""
    global _notifier
    if _notifier is None:
        _notifier = AssessmentNotifier()
    return _notifier
