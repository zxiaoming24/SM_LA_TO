"""
推荐系统模块 - 个性化资源推荐引擎

核心组件：
├── resource_db.py           - SQLite 资源数据库
├── learning_record_db.py    - SQLite 学习记录
├── semantic_store.py        - ChromaDB 语义存储
├── forgetting_curve.py      - 艾宾浩斯遗忘曲线调度器
├── attention_profile.py     - 注意力偏好画像（眼动/行为信号）
└── recommender.py           - 推荐引擎

数据库选型说明：
- SQLite  → 精确过滤、结构化统计、调度记录
- ChromaDB → 语义相似搜索、薄弱点模式
"""

from .resource_db import ResourceDB
from .learning_record_db import LearningRecordDB
from .semantic_store import SemanticStore
from .forgetting_curve import ForgettingCurveScheduler
from .recommender import PersonalizedRecommender
from .attention_profile import AttentionProfile, get_profile

__all__ = [
    "ResourceDB",
    "LearningRecordDB",
    "SemanticStore",
    "ForgettingCurveScheduler",
    "PersonalizedRecommender",
    "AttentionProfile",
    "get_profile",
]
