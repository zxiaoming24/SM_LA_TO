"""
全局用户综合排行榜服务

核心功能：
1. 聚合多数据源计算用户综合分数
2. 按综合分数排序生成排行榜
3. 支持查询用户排名位置
4. 提供缓存机制优化性能

数据来源：
- user_features/{user_id}.json: 用户8维度特征、学习时长
- leaderboard.db/submissions: 编程题提交记录（分数、准确率、做题数量）

综合评分公式（可配置权重）：
综合分数 = w1 × 编程能力分 + w2 × 准确率分 + w3 × 学习时长分 + w4 × 做题数量分 + w5 × 综合特征分

设计原则：
- 所有 IO 密集操作（文件读取、数据库查询）均使用 asyncio.to_thread 异步执行
- 避免在服务层使用 run_in_threadpool，由 API 层决定执行方式
- 缓存机制减少重复计算
"""

import json
import os
import sqlite3
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class GlobalRankingService:
    """全局用户综合排行榜服务"""
    
    DEFAULT_WEIGHTS = {
        "coding_score": 0.30,
        "accuracy_score": 0.25,
        "learning_time_score": 0.15,
        "problem_count_score": 0.15,
        "overall_feature_score": 0.15
    }
    
    CACHE_TTL = 300
    
    _instance = None
    
    def __new__(cls, weights: Dict[str, float] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, weights: Dict[str, float] = None):
        if self._initialized:
            if weights is not None:
                self.update_weights(weights)
            return
        
        self.weights = weights or self.DEFAULT_WEIGHTS
        self._validate_weights()
        
        project_root = Path(__file__).resolve().parent.parent
        
        self.user_features_dir = project_root / "user_features"
        self.db_path = project_root / "leaderboard_data" / "leaderboard.db"
        
        self._cache = {}
        self._cache_time = 0
        self._lock = asyncio.Lock()
        
        self._initialized = True
        print(f"✅ GlobalRankingService 初始化完成")
    
    def _validate_weights(self):
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"权重总和必须为1.0，当前总和: {total}")
        
        for key, value in self.weights.items():
            if value < 0 or value > 1:
                raise ValueError(f"权重值必须在0~1之间，{key}: {value}")
    
    def _get_db_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _sync_load_user_features(self, user_id: str) -> Optional[Dict[str, Any]]:
        feature_file = self.user_features_dir / f"{user_id}.json"
        if not feature_file.exists():
            return None
        
        try:
            with open(feature_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("current_features", {})
        except Exception as e:
            print(f"❌ 加载用户特征失败 {user_id}: {e}")
            return None
    
    def _sync_get_user_submission_stats(self, user_id: str) -> Dict[str, Any]:
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) as total_submissions,
                       AVG(score) as avg_score,
                       SUM(CASE WHEN verdict = 'Accepted' THEN 1 ELSE 0 END) as accepted_count
                FROM submissions
                WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row["total_submissions"] > 0:
                total = row["total_submissions"]
                avg_score = row["avg_score"] or 0
                accepted = row["accepted_count"] or 0
                accuracy = (accepted / total) * 100
                
                return {
                    "total_submissions": total,
                    "avg_score": round(avg_score, 2),
                    "accuracy": round(accuracy, 2),
                    "accepted_count": accepted
                }
            
            return {
                "total_submissions": 0,
                "avg_score": 0,
                "accuracy": 0,
                "accepted_count": 0
            }
            
        except Exception as e:
            print(f"❌ 获取用户提交统计失败 {user_id}: {e}")
            return {
                "total_submissions": 0,
                "avg_score": 0,
                "accuracy": 0,
                "accepted_count": 0
            }
    
    def _sync_get_all_user_ids(self) -> List[str]:
        user_ids = []
        if not self.user_features_dir.exists():
            return user_ids
        
        for file in self.user_features_dir.glob("*.json"):
            user_id = file.stem
            if user_id:
                user_ids.append(user_id)
        
        return user_ids
    
    def _calculate_problem_count_score(self, count: int, max_count: int) -> float:
        if max_count == 0:
            return 0
        
        ratio = count / max_count
        score = 100 * (1 - pow(1 - ratio, 3))
        return min(100, max(0, score))
    
    def _calculate_user_composite_score(self, user_features: Dict[str, Any], submission_stats: Dict[str, Any], global_stats: Dict[str, Any]) -> Dict[str, Any]:
        coding_score = submission_stats["avg_score"]
        
        accuracy_score = submission_stats["accuracy"]
        
        time_score = user_features.get("time_management", {}).get("score", 0)
        
        problem_count = submission_stats["total_submissions"]
        max_problem_count = global_stats.get("max_problem_count", 1)
        problem_count_score = self._calculate_problem_count_score(problem_count, max_problem_count)
        
        overall_feature_score = user_features.get("summary_scores", {}).get("overall_score", 0)
        
        weights = self.weights
        composite_score = (
            coding_score * weights["coding_score"] +
            accuracy_score * weights["accuracy_score"] +
            time_score * weights["learning_time_score"] +
            problem_count_score * weights["problem_count_score"] +
            overall_feature_score * weights["overall_feature_score"]
        ) * 10
        
        return {
            "composite_score": round(composite_score, 2),
            "dimension_scores": {
                "coding_score": round(coding_score, 2),
                "accuracy_score": round(accuracy_score, 2),
                "learning_time_score": round(time_score, 2),
                "problem_count_score": round(problem_count_score, 2),
                "overall_feature_score": round(overall_feature_score, 2)
            },
            "submission_stats": submission_stats
        }
    
    def _compute_global_stats(self, all_user_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not all_user_data:
            return {"max_problem_count": 1}
        
        max_problem_count = max(
            data.get("submission_stats", {}).get("total_submissions", 0)
            for data in all_user_data
        )
        
        return {
            "max_problem_count": max(max_problem_count, 1)
        }
    
    def _invalidate_cache(self):
        self._cache = {}
        self._cache_time = 0
    
    async def _run_sync(self, func, *args):
        """兼容 Python 3.8+ 的同步函数转异步执行"""
        try:
            return await asyncio.to_thread(func, *args)
        except AttributeError:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, func, *args)
    
    async def load_user_features(self, user_id: str) -> Optional[Dict[str, Any]]:
        """异步加载用户特征数据"""
        return await self._run_sync(self._sync_load_user_features, user_id)
    
    async def get_user_submission_stats(self, user_id: str) -> Dict[str, Any]:
        """异步获取用户编程题提交统计"""
        return await self._run_sync(self._sync_get_user_submission_stats, user_id)
    
    async def get_all_user_ids(self) -> List[str]:
        """异步获取所有用户ID列表"""
        return await self._run_sync(self._sync_get_all_user_ids)
    
    async def get_global_ranking(
        self,
        limit: int = 50,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        异步获取全局用户排行榜
        
        Args:
            limit: 返回的记录数量限制
            user_id: 当前用户ID（用于标记当前位置）
            
        Returns:
            Dict: 排行榜数据
        """
        try:
            current_time = datetime.now().timestamp()
            
            async with self._lock:
                if self._cache and (current_time - self._cache_time) < self.CACHE_TTL:
                    print(f"✅ 使用缓存数据")
                    result = dict(self._cache["result"])
                    
                    if user_id and "user_rank" not in result:
                        result["user_rank"] = self._find_user_rank(result["rankings"], user_id)
                    
                    return result
            
            user_ids = await self.get_all_user_ids()
            
            if not user_ids:
                return {
                    "success": True,
                    "total_users": 0,
                    "rankings": [],
                    "user_rank": None,
                    "last_updated": datetime.now().isoformat()
                }
            
            all_user_data = []
            
            for uid in user_ids:
                features = await self.load_user_features(uid)
                if not features:
                    continue
                
                submission_stats = await self.get_user_submission_stats(uid)
                
                user_data = {
                    "user_id": uid,
                    "features": features,
                    "submission_stats": submission_stats
                }
                all_user_data.append(user_data)
            
            global_stats = self._compute_global_stats(all_user_data)
            
            ranking_items = []
            
            for user_data in all_user_data:
                result = self._calculate_user_composite_score(
                    user_data["features"],
                    user_data["submission_stats"],
                    global_stats
                )
                
                ranking_items.append({
                    "user_id": user_data["user_id"],
                    "composite_score": result["composite_score"],
                    "dimension_scores": result["dimension_scores"],
                    "submission_stats": result["submission_stats"]
                })
            
            ranking_items.sort(key=lambda x: x["composite_score"], reverse=True)
            
            ranked_list = []
            current_rank = 1
            prev_score = None
            
            for idx, item in enumerate(ranking_items):
                if prev_score is not None and item["composite_score"] < prev_score:
                    current_rank = idx + 1
                prev_score = item["composite_score"]
                
                ranked_list.append({
                    "rank": current_rank,
                    "user_id": item["user_id"],
                    "composite_score": item["composite_score"],
                    "dimension_scores": item["dimension_scores"],
                    "submission_stats": item["submission_stats"]
                })
            
            user_rank = None
            if user_id:
                for item in ranked_list:
                    if item["user_id"] == user_id:
                        user_rank = item["rank"]
                        break
            
            result = {
                "success": True,
                "total_users": len(ranked_list),
                "rankings": ranked_list[:limit],
                "user_rank": user_rank,
                "weights": self.weights,
                "last_updated": datetime.now().isoformat()
            }
            
            async with self._lock:
                self._cache = {
                    "result": {k: v for k, v in result.items() if k != "user_rank"},
                    "rankings_full": ranked_list
                }
                self._cache_time = current_time
            
            print(f"✅ 全局排行榜计算完成，共 {len(ranked_list)} 个用户")
            
            return result
            
        except Exception as e:
            print(f"❌ 获取全局排行榜失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }
    
    def _find_user_rank(self, rankings: List[Dict[str, Any]], user_id: str) -> Optional[int]:
        for item in rankings:
            if item["user_id"] == user_id:
                return item["rank"]
        return None
    
    async def get_user_rank_detail(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        异步获取用户的排名详情
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 用户排名详情，None表示用户不存在
        """
        try:
            result = await self.get_global_ranking(limit=9999)
            if not result.get("success"):
                return None
            
            for item in result.get("rankings", []):
                if item["user_id"] == user_id:
                    return item
            
            return None
            
        except Exception as e:
            print(f"❌ 获取用户排名详情失败 {user_id}: {e}")
            return None
    
    async def get_top_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        异步获取排名前N的用户
        
        Args:
            limit: 返回数量
            
        Returns:
            List: 排名列表
        """
        result = await self.get_global_ranking(limit=limit)
        if result.get("success"):
            return result.get("rankings", [])
        return []
    
    def update_weights(self, new_weights: Dict[str, float]):
        """
        更新权重配置（同步方法，权重变更不需要异步）
        
        Args:
            new_weights: 新的权重配置
        """
        self.weights = new_weights
        self._validate_weights()
        self._invalidate_cache()
        print(f"✅ 权重配置已更新: {self.weights}")
    
    def get_weights(self) -> Dict[str, float]:
        """获取当前权重配置（同步方法）"""
        return dict(self.weights)