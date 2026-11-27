"""
链式特征更新示例 - 演示真正的"随学随新"流程

关键概念：
1. DynamicFeatureUpdater是单例，所有Agent共享同一个实例
2. Agent A更新特征后 → 自动保存到中央管理器
3. Agent B获取特征时 → 从中央管理器拿到的是A更新后的最新特征
4. 实现真正的链式更新：原始特征 → Agent A更新 → Agent B基于A的结果继续更新
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dynamic_feature_updater import DynamicFeatureUpdater
from practice_agent import PracticeAgent
from video_search_agent import VideoSearchAgent
from course_doc_agent_ali import CourseDocAgent
from user_info_extractor import extract_user_info
from feature_extractor import StudentFeatureExtractor


def demo_chain_update():
    """
    演示链式更新流程：
    用户user_001依次进行：练题 → 看视频 → 读文档
    每个步骤都基于上一步更新后的特征
    """
    
    print("="*80)
    print("🚀 链式特征更新演示")
    print("="*80)
    
    # 初始化（注意：由于是单例，所有Agent共享同一个DynamicFeatureUpdater）
    feature_updater = DynamicFeatureUpdater()
    practice_agent = PracticeAgent()
    video_agent = VideoSearchAgent()
    doc_agent = CourseDocAgent()
    feature_extractor = StudentFeatureExtractor()  # 特征提取器
    
    user_id = "user_001"
    
    # ==================== 第1步：从自然语言提取初始特征 ====================
    print("\n" + "="*80)
    print("第1步：从自然语言描述中提取用户初始特征")
    print("="*80)
    
    # 学生的自然语言自我介绍
    student_natural_language = """
    我叫张三，是计算机科学与技术专业的大二学生。
    
    我对编程很感兴趣，特别是Python和Web开发。之前学过C语言基础，成绩还可以，大概75分左右，主要是通过看书和做作业来学习。
    
    我的学习目标是掌握Python编程基础，希望以后能成为一名软件工程师。我平时喜欢看视频教程学习，因为比较直观易懂，但有时候也会动手实践写代码。
    
    我每天都会花1-2小时学习编程，学习节奏比较稳定。遇到问题时，我会先自己尝试解决，如果不行就去查资料或问同学。
    
    我觉得自己的逻辑思维能力一般，创造性思维还需要加强。在学习过程中，我经常会反思自己的学习方法，希望能找到更高效的学习方式。
    """
    
    print(f"\n📝 学生自述:\n{student_natural_language}")
    
    # ★★★ 第1.1步：使用 user_info_extractor 提取基本信息 ★★★
    print("\n🔄 步骤1.1: 使用 extract_user_info 提取基本信息...")
    basic_info = extract_user_info(student_natural_language)
    
    print(f"✅ 基本信息提取完成:")
    print(f"   姓名: {basic_info.get('name', '未知')}")
    print(f"   专业: {basic_info.get('major', '未知')}")
    print(f"   年级: {basic_info.get('grade', '未知')}")
    
    # ★★★ 第1.2步：将基本信息转换为自然语言描述 ★★★
    description = f"""
    姓名：{basic_info.get('name', '未知')}
    专业：{basic_info.get('major', '未知')}
    年级：{basic_info.get('grade', '未知')}
    学习目标：{basic_info.get('learning_goal', '未知')}
    学习历史：{basic_info.get('learning_history', [])}
    学习习惯：{basic_info.get('learning_habits', '未知')}
    """
    
    # ★★★ 第1.3步：使用 feature_extractor 提取特征评分 ★★★
    print("\n🔄 步骤1.2: 使用 StudentFeatureExtractor 提取特征评分...")
    feature_extractor = StudentFeatureExtractor()
    initial_features = feature_extractor.extract_features(description)
    
    print(f"\n✅ 特征提取完成！")
    print(f"   学术背景: {initial_features['academic_background']['score']}")
    print(f"   学习行为: {initial_features['learning_behavior']['score']}")
    print(f"   目标动机: {initial_features['goal_motivation']['score']}")
    print(f"   认知能力: {initial_features['cognitive_abilities']['score']}")
    
    # 将提取的特征保存到中央管理器
    feature_updater.initialize_user_features(user_id, initial_features)
    
    print(f"\n✅ 初始特征:")
    print(f"   学术背景: {initial_features['academic_background']['score']}")
    print(f"   学习行为: {initial_features['learning_behavior']['score']}")
    print(f"   目标动机: {initial_features['goal_motivation']['score']}")
    print(f"   认知能力: {initial_features['cognitive_abilities']['score']}")
    
    # ==================== 第2步：学生做练习题 ====================
    print("\n" + "="*80)
    print("第2步：学生完成编程练习")
    print("="*80)
    
    # 模拟练习题数据
    problem = {
        "title": "Python递归实现斐波那契数列",
        "difficulty": "中等",
        "knowledge_points": ["递归", "动态规划"]
    }
    
    judge_result = {
        "verdict": "Accepted",
        "score": 85,
        "passed_tests": 8,
        "total_tests": 10,
        "bugs": ["边界条件处理不够完善"],
        "analysis": {
            "correctness": "基本正确",
            "logic": "思路清晰",
            "code_quality": "良好",
            "efficiency": "可优化"
        }
    }
    
    # ★★★ 关键：只传user_id，不传student_features
    # Agent会自动从中央管理器获取最新特征（当前是初始特征）
    result = practice_agent.judge_code(
        problem=problem,
        user_code="def fib(n): ...",
        language="python",
        user_id=user_id  # 只需传user_id！
    )
    
    print(f"\n✅ 练习完成，特征已自动更新并保存")
    
    # 验证：从中央管理器获取更新后的特征
    features_after_practice = feature_updater.get_latest_features(user_id)
    print(f"\n📊 练习后的特征:")
    print(f"   学术背景: {features_after_practice['academic_background']['score']}")
    print(f"   学习行为: {features_after_practice['learning_behavior']['score']}")
    print(f"   目标动机: {features_after_practice['goal_motivation']['score']}")
    print(f"   认知能力: {features_after_practice['cognitive_abilities']['score']}")
    
    # ==================== 第3步：学生观看视频教程 ====================
    print("\n" + "="*80)
    print("第3步：学生观看视频教程")
    print("="*80)
    
    # 模拟观看数据
    watch_data = {
        "watch_duration": "45分钟",
        "total_duration": "50分钟",
        "completion_rate": "90%",
        "pause_count": 8,
        "rewind_count": 5,
        "note-taking": True,
        "quiz_score": 88,
        "engagement_signals": ["多次暂停记笔记", "关键部分重复观看"]
    }
    
    video_info = {
        "title": "Python递归深度解析",
        "topic": "递归算法"
    }
    
    # ★★★ 关键：同样只传user_id
    # Agent会自动从中央管理器获取最新特征（现在是练习后更新过的特征！）
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        update_result = loop.run_until_complete(
            video_agent.update_features_after_watch(
                student_features=None,  # 不传，让Agent自己从中央管理器获取
                watch_data=watch_data,
                video_info=video_info,
                user_id=user_id
            )
        )
    finally:
        loop.close()
    
    print(f"\n✅ 视频学习完成，特征已自动更新并保存")
    
    # 验证：从中央管理器获取更新后的特征
    features_after_video = feature_updater.get_latest_features(user_id)
    print(f"\n📊 视频学习后的特征:")
    print(f"   学术背景: {features_after_video['academic_background']['score']}")
    print(f"   学习行为: {features_after_video['learning_behavior']['score']}")
    print(f"   目标动机: {features_after_video['goal_motivation']['score']}")
    print(f"   认知能力: {features_after_video['cognitive_abilities']['score']}")
    
    # ==================== 第4步：学生阅读课程文档 ====================
    print("\n" + "="*80)
    print("第4步：学生阅读课程文档")
    print("="*80)
    
    # 模拟阅读数据
    reading_data = {
        "reading_time": "30分钟",
        "pages_read": 18,
        "total_pages": 20,
        "highlight_count": 12,
        "note_count": 8,
        "comprehension_score": 82,
        "revisit_sections": ["递归优化", "记忆化技术"],
        "reading_speed": "正常"
    }
    
    doc_info = {
        "doc_title": "递归算法完全指南",
        "course_name": "数据结构与算法"
    }
    
    # ★★★ 关键：同样只传user_id
    # Agent会自动从中央管理器获取最新特征（现在是视频学习后更新过的特征！）
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        update_result = loop.run_until_complete(
            doc_agent.update_features_after_reading(
                student_features=None,  # 不传，让Agent自己从中央管理器获取
                reading_data=reading_data,
                doc_info=doc_info,
                user_id=user_id
            )
        )
    finally:
        loop.close()
    
    print(f"\n✅ 文档阅读完成，特征已自动更新并保存")
    
    # 验证：从中央管理器获取最终的特征
    final_features = feature_updater.get_latest_features(user_id)
    print(f"\n📊 最终特征:")
    print(f"   学术背景: {final_features['academic_background']['score']}")
    print(f"   学习行为: {final_features['learning_behavior']['score']}")
    print(f"   目标动机: {final_features['goal_motivation']['score']}")
    print(f"   认知能力: {final_features['cognitive_abilities']['score']}")
    
    # ==================== 总结对比 ====================
    print("\n" + "="*80)
    print("📈 特征演化总结")
    print("="*80)
    
    print(f"\n{'维度':<12} {'初始':>6} {'练习后':>8} {'视频后':>8} {'文档后':>8} {'总变化':>8}")
    print("-" * 60)
    
    dimensions = ["academic_background", "learning_behavior", "goal_motivation", "cognitive_abilities"]
    dim_names = ["学术背景", "学习行为", "目标动机", "认知能力"]
    
    for dim, name in zip(dimensions, dim_names):
        initial = initial_features[dim]['score']
        after_practice = features_after_practice[dim]['score']
        after_video = features_after_video[dim]['score']
        final = final_features[dim]['score']
        total_change = final - initial
        
        sign = "+" if total_change > 0 else ""
        print(f"{name:<10} {initial:>6} {after_practice:>8} {after_video:>8} {final:>8} {sign}{total_change:>7}")
    
    print("\n✅ 链式更新成功！")
    print("   - 每次更新都基于最新的特征")
    print("   - 所有更新自动保存到中央管理器")
    print("   - 实现了真正的'随学随新'")
    
    # ==================== 查看更新历史 ====================
    print("\n" + "="*80)
    print("📜 更新历史记录")
    print("="*80)
    
    history = feature_updater.get_update_history(user_id)
    print(f"\n共有 {len(history)} 次更新记录:\n")
    
    for i, record in enumerate(history, 1):
        print(f"更新 #{i}:")
        print(f"  时间: {record['timestamp']}")
        print(f"  任务类型: {record['metadata'].get('task_type', 'unknown')}")
        print(f"  分数变化: {record['old_scores']} → {record['new_scores']}")
        print()


if __name__ == "__main__":
    demo_chain_update()
