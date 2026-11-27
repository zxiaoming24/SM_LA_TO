"""
端到端测试：YOLO情绪检测 → 8维度emotional_state特征更新

这个测试模拟真实场景：
1. 启动WebRTC服务器（端口8000）
2. 打开摄像头进行实时情绪检测
3. 将检测结果映射到8维度特征的emotional_state
4. 通过WebSocket向前端发送更新后的特征数据
"""

import asyncio
import json
import sys
import os
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotion_state_mapper import EmotionStateMapper
from Agent.children_agent.dynamic_feature_updater import DynamicFeatureUpdater


class EmotionFeatureIntegrationTest:
    """情绪特征集成测试类"""
    
    def __init__(self, user_id="test_user_emotion"):
        self.user_id = user_id
        self.emotion_mapper = EmotionStateMapper()
        self.feature_updater = DynamicFeatureUpdater()
        
        # 初始化用户特征
        self._initialize_user_features()
        
    def _initialize_user_features(self):
        """初始化用户的8维度特征"""
        initial_features = {
            "academic_background": {
                "major_preference": "计算机科学",
                "knowledge_level": "中等",
                "ability_tendency": "实践应用",
                "foundation_level": "中级",
                "score": 75
            },
            "learning_behavior": {
                "learning_style": "混合型",
                "learning_pace": "稳定学习者",
                "interaction_level": "中",
                "resource_preference": "视频+实践",
                "score": 70
            },
            "goal_motivation": {
                "short_term_goals": "掌握Python编程基础",
                "long_term_career": "软件工程师",
                "motivation_strength": "内在动机",
                "achievement_expectation": "高",
                "score": 80
            },
            "cognitive_abilities": {
                "logical_thinking": "较强",
                "creative_thinking": "中等",
                "problem_solving": "系统性",
                "metacognition": "良好",
                "score": 78
            },
            "emotional_state": {
                "interest_level": "高",
                "frustration_tolerance": "中等",
                "anxiety_level": "低",
                "confidence_level": "较高",
                "score": 72
            },
            "social_interaction": {
                "collaboration_tendency": "愿意合作",
                "help_seeking_pattern": "主动求助",
                "knowledge_sharing_willingness": "中等",
                "peer_influence": "适度",
                "score": 68
            },
            "time_management": {
                "learning_regularity": "较规律",
                "priority_judgment": "良好",
                "procrastination_tendency": "轻微拖延",
                "time_allocation_efficiency": "中等",
                "score": 65
            },
            "creativity_innovation": {
                "divergent_thinking": "中等",
                "cross_domain_association": "较弱",
                "experimental_exploration": "谨慎尝试",
                "original_expression": "一般",
                "score": 62
            }
        }
        
        self.feature_updater.initialize_user_features(self.user_id, initial_features)
        print(f"✅ 已初始化用户 {self.user_id} 的8维度特征")
        
    def simulate_yolo_detection(self, emotion_type: str, confidence: float) -> dict:
        """
        模拟YOLO情绪检测结果
        
        Args:
            emotion_type: 情绪类型 (happy/sad/angry/fear/surprise/disgust/neutral)
            confidence: 置信度 (0-1)
            
        Returns:
            YOLO检测结果格式
        """
        return [{
            "emotion": emotion_type,
            "confidence": confidence,
            "bbox": [100, 100, 300, 300],
            "centroid": [200, 200],
            "size": {"width": 200, "height": 200}
        }]
    
    def process_and_update_features(self, yolo_result: list) -> dict:
        """
        处理YOLO检测结果并更新8维度特征
        
        Args:
            yolo_result: YOLO情绪检测结果
            
        Returns:
            更新后的完整特征数据
        """
        # 步骤1: 获取当前特征
        current_features = self.feature_updater.get_latest_features(self.user_id)
        
        if not current_features:
            print("❌ 无法获取当前用户特征")
            return {}
        
        # 步骤2: 使用情绪状态映射器处理检测结果
        emotion_result = self.emotion_mapper.process_emotion_detection(
            yolo_result,
            current_features
        )
        
        # 步骤3: 提取情绪状态更新建议
        emotional_state_update = emotion_result.get('emotional_state_update')
        
        if emotional_state_update:
            print(f"\n📊 检测到情绪: {emotion_result['detected_emotion']['chinese_name']} "
                  f"(置信度: {emotion_result['detected_emotion']['confidence']:.2%})")
            print(f"💡 建议: {emotion_result.get('recommendation', 'N/A')}")
            
            # 步骤4: 根据情绪影响计算特征调整量
            impact = emotion_result.get('dimension_impact', {})
            
            # 计算emotional_state评分的变化
            # 基于各子维度的变化综合计算总分变化
            total_impact = sum(impact.values())
            score_delta = int(total_impact * 10)  # 转换为分数变化
            
            # 限制变化范围在±10分内
            score_delta = max(-10, min(10, score_delta))
            
            # 步骤5: 使用DynamicFeatureUpdater更新特征
            updated_features = self.feature_updater.quick_update(
                current_features=current_features,
                task_type="video_learning",  # 视频学习场景
                score_change=score_delta,
                affected_dimensions=["emotional_state"]  # 只更新情绪状态维度
            )
            
            # 步骤6: 手动更新emotional_state的子维度值
            if 'emotional_state' in updated_features:
                for key, value in emotional_state_update.items():
                    if key != 'score':
                        updated_features['emotional_state'][key] = value
            
            # 保存更新后的特征
            self.feature_updater._features_cache[self.user_id] = updated_features
            
            return updated_features
        else:
            print("⚠️ 未生成情绪状态更新建议")
            return current_features
    
    def display_feature_comparison(self, before: dict, after: dict):
        """显示特征对比"""
        print("\n" + "="*80)
        print("📈 情绪状态维度变化对比")
        print("="*80)
        
        before_emotional = before.get('emotional_state', {})
        after_emotional = after.get('emotional_state', {})
        
        dimensions = [
            ('interest_level', '兴趣水平'),
            ('frustration_tolerance', '挫折承受力'),
            ('anxiety_level', '焦虑水平'),
            ('confidence_level', '自信心'),
            ('score', '综合评分')
        ]
        
        for key, name in dimensions:
            before_val = before_emotional.get(key, 'N/A')
            after_val = after_emotional.get(key, 'N/A')
            
            if before_val != after_val:
                print(f"  {name:<12}: {str(before_val):<10} → {str(after_val):<10}")
        
        print("="*80)
    
    def run_realtime_simulation(self, duration_seconds=30):
        """
        运行实时模拟测试
        
        Args:
            duration_seconds: 模拟持续时间（秒）
        """
        print("\n" + "🎭"*40)
        print(f"开始{duration_seconds}秒实时情绪检测模拟")
        print("🎭"*40 + "\n")
        
        start_time = time.time()
        detection_count = 0
        
        # 模拟不同的情绪序列
        import random
        
        emotion_sequence = [
            ('surprise', 0.7),   # 惊讶
            ('happy', 0.8),      # 快乐
            ('neutral', 0.9),    # 中性
            ('fear', 0.6),       # 恐惧
            ('angry', 0.5),      # 愤怒
            ('sad', 0.65),       # 悲伤
        ]
        
        while time.time() - start_time < duration_seconds:
            # 随机选择一个情绪
            emotion_type, base_confidence = random.choice(emotion_sequence)
            
            # 添加一些随机波动
            confidence = max(0.3, min(0.95, base_confidence + random.uniform(-0.1, 0.1)))
            
            # 模拟YOLO检测
            yolo_result = self.simulate_yolo_detection(emotion_type, confidence)
            
            print(f"\n--- 检测 #{detection_count + 1} ({time.strftime('%H:%M:%S')}) ---")
            
            # 处理并更新特征
            before_features = self.feature_updater.get_latest_features(self.user_id).copy()
            updated_features = self.process_and_update_features(yolo_result)
            
            # 显示变化
            if updated_features:
                self.display_feature_comparison(before_features, updated_features)
            
            detection_count += 1
            
            # 每3秒进行一次聚合分析
            if detection_count % 3 == 0:
                print("\n📊 聚合情绪分析:")
                aggregated = self.emotion_mapper.aggregate_emotions_over_time(
                    time_window_seconds=10
                )
                if aggregated.get('status') == 'success':
                    dominant = aggregated.get('dominant_emotion', {})
                    print(f"  主导情绪: {dominant.get('chinese_name')} "
                          f"({dominant.get('percentage'):.1f}%)")
                    print(f"  整体效价: {aggregated.get('overall_valence')}")
                    print(f"  趋势: {aggregated.get('trend_analysis')}")
            
            # 等待一段时间模拟真实帧率
            time.sleep(2)
        
        print(f"\n✅ 模拟完成！共进行 {detection_count} 次情绪检测")
        
        # 显示最终特征状态
        final_features = self.feature_updater.get_latest_features(self.user_id)
        print("\n📋 最终情绪状态:")
        emotional = final_features.get('emotional_state', {})
        for key, value in emotional.items():
            print(f"  {key}: {value}")


def test_with_websocket_integration():
    """
    测试与WebSocket的集成（模拟前端通信）
    """
    print("\n" + "="*80)
    print("🔌 WebSocket集成测试")
    print("="*80)
    
    test_instance = EmotionFeatureIntegrationTest(user_id="websocket_test_user")
    
    # 模拟从前端接收的情绪检测数据
    mock_ws_messages = [
        {
            "type": "emotion_detection",
            "data": [{"emotion": "happy", "confidence": 0.85}]
        },
        {
            "type": "emotion_detection", 
            "data": [{"emotion": "surprise", "confidence": 0.72}]
        },
        {
            "type": "emotion_detection",
            "data": [{"emotion": "angry", "confidence": 0.6}]
        }
    ]
    
    for i, msg in enumerate(mock_ws_messages):
        print(f"\n--- WebSocket消息 #{i+1} ---")
        print(f"接收数据: {json.dumps(msg['data'], ensure_ascii=False)}")
        
        # 处理情绪检测
        updated_features = test_instance.process_and_update_features(msg['data'])
        
        # 模拟发送回前端的响应
        response = {
            "type": "feature_update",
            "user_id": test_instance.user_id,
            "updated_dimension": "emotional_state",
            "new_values": updated_features.get('emotional_state', {}),
            "timestamp": time.time()
        }
        
        print(f"发送到前端: {json.dumps(response, ensure_ascii=False, indent=2)}")
        
        time.sleep(1)


def main():
    """主测试函数"""
    print("\n" + "🎯"*40)
    print("YOLO情绪检测 → 8维度特征更新 端到端测试")
    print("🎯"*40 + "\n")
    
    try:
        # 测试1: 基础功能测试
        print("="*80)
        print("🧪 测试1: 基础情绪检测与特征更新")
        print("="*80)
        
        test_instance = EmotionFeatureIntegrationTest(user_id="basic_test_user")
        
        # 测试不同情绪的影响
        test_cases = [
            ("happy", 0.85, "快乐情绪应该提升兴趣和自信"),
            ("angry", 0.7, "愤怒情绪应该降低兴趣和增加焦虑"),
            ("fear", 0.65, "恐惧情绪应该显著增加焦虑"),
        ]
        
        for emotion, confidence, description in test_cases:
            print(f"\n📋 测试场景: {description}")
            yolo_result = test_instance.simulate_yolo_detection(emotion, confidence)
            before = test_instance.feature_updater.get_latest_features(test_instance.user_id).copy()
            after = test_instance.process_and_update_features(yolo_result)
            test_instance.display_feature_comparison(before, after)
        
        # 测试2: 实时模拟
        print("\n\n")
        test_instance.run_realtime_simulation(duration_seconds=15)
        
        # 测试3: WebSocket集成
        print("\n\n")
        test_with_websocket_integration()
        
        print("\n" + "="*80)
        print("🎉 所有测试完成！")
        print("="*80)
        
        print("\n💡 使用说明:")
        print("1. 运行 main_webrtc.py 启动服务器 (端口8000)")
        print("2. 打开 test_webrtc_simple.html 连接摄像头")
        print("3. 查看日志中的情绪状态映射输出")
        print("4. 前端会收到包含emotional_state更新的WebSocket消息")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
