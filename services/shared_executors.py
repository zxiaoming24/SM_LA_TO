"""
shared_executors.py - 共享线程池（供所有模块引用）

隔离不同类型的阻塞操作用各自的线程池，避免互相抢占导致卡死：
  - STUDY_PLAN_EXECUTOR: 学习计划查询（文件读 + SQLite）
  - CACHE_EXECUTOR: 内容缓存读写（ContentStore、FeatureUpdater 等）
"""
from concurrent.futures import ThreadPoolExecutor

CACHE_EXECUTOR = ThreadPoolExecutor(max_workers=16, thread_name_prefix="cache_ops")
