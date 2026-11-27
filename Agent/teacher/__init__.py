"""
教师角色模块

提供教师身份下的核心功能：
- 数据层 (teacher_db.py)：班级、师生关系、作业、提交批改 4 张表
- 路由层 (teacher_server.py)：/teacher/* REST 接口
- Agent 层 (teacher_helper_agent.py)：LLM + 工具集，支持自然语言调用

身份校验暂未实现，user_id 由前端约定传入（如 teacher_xxx），后续可在路由层加 Depends 校验。
"""

# 模块导出（按需添加，避免循环导入）
__all__ = []
